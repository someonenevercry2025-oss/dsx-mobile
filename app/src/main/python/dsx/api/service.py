"""Layanan tingkat atas: DSX + file proyek -> dokumen, dengan diagnostik terstruktur.

Kontrak: fungsi publik TIDAK melempar eksepsi untuk input yang salah. Kesalahan
validasi input (INVALID_INPUT, INVALID_PROJECT_FILES, UNSUPPORTED_FORMAT, ...)
dibedakan dari kesalahan internal (INTERNAL_ERROR).
"""

from __future__ import annotations

import os
import stat
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ..compiler import compile_dsx
from ..diagnostics import Diagnostic, DiagnosticBag, FatalDsxError, Severity
from ..inspectors.docx_inspector import inspect_docx
from ..limits import Deadline, Limits
from ..renderers.base import SUPPORTED_FORMATS, get_renderer
from ..source import DirectorySource, MemorySource, Source, SourceError, normalize_relpath

_FORMAT_EXT = {'docx': '.docx', 'pdf': '.pdf', 'html': '.html'}


@dataclass
class GenerationResult:
    status: str  # "success" | "failed"
    output: bytes | None = None
    output_file: str | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    warnings: list[Diagnostic] = field(default_factory=list)
    render_summary: dict[str, Any] = field(default_factory=dict)
    referenced_files: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "success"


def _err(code: str, message: str, **details: Any) -> Diagnostic:
    from ..diagnostics import make_details

    return Diagnostic(Severity.ERROR, code, message, None, make_details(**details))


def _failed(*diagnostics: Diagnostic, bag: DiagnosticBag | None = None, referenced: list[str] | None = None) -> GenerationResult:
    bag = bag or DiagnosticBag()
    for d in diagnostics:
        bag.add_diagnostic(d)
    return GenerationResult("failed", None, None, bag.errors, bag.warnings, {}, referenced or [])


def _check_limits(limits: Any) -> tuple[Limits | None, Diagnostic | None]:
    if limits is None:
        return Limits(), None
    if not isinstance(limits, Limits):
        return None, _err("INVALID_INPUT", f"limits harus berupa instance dsx.Limits, ditemukan {type(limits).__name__}.")
    return limits, None


def _check_common(output_format: Any, source_name: Any) -> Diagnostic | None:
    if not isinstance(source_name, str) or not source_name.strip():
        return _err("INVALID_INPUT", "source_name harus berupa string yang tidak kosong.")
    if not isinstance(output_format, str) or output_format.lower() not in SUPPORTED_FORMATS:
        return _err(
            "UNSUPPORTED_FORMAT",
            f"Format keluaran {output_format!r} belum didukung. Didukung: {', '.join(SUPPORTED_FORMATS)}.",
        )
    return None



def _quality_scan_output(data: bytes, output_format: str, diag: DiagnosticBag) -> None:
    """Detect leaked internal objects / placeholders in rendered output."""
    try:
        text = ""
        if output_format == "html":
            text = data.decode("utf-8", errors="replace")
        elif output_format == "docx":
            import zipfile, io, re
            z = zipfile.ZipFile(io.BytesIO(data))
            parts = []
            for name in z.namelist():
                if name.endswith(".xml"):
                    parts.append(z.read(name).decode("utf-8", errors="replace"))
            text = "\n".join(parts)
        else:
            return
        leaks = []
        for token in ("RefValue(", "CiteValue(", "FootnoteValue(", "LabelMarker("):
            if token in text:
                leaks.append(token.rstrip("("))
        if "«" in text and "»" in text:
            leaks.append("guillemet-placeholder")
        if leaks:
            diag.warning(
                "OUTPUT_PLACEHOLDER_LEAK",
                "Keluaran memuat penanda internal yang tidak terselesaikan: " + ", ".join(leaks),
            )
    except Exception:
        pass

def _run(
    dsx_text: Any,
    source: Source,
    output_format: str,
    limits: Limits,
    source_name: str,
    render: bool,
    before_render: Any = None,
) -> GenerationResult:
    diag = DiagnosticBag(limits.max_diagnostics)
    if isinstance(dsx_text, (bytes, bytearray)):
        try:
            dsx_text = bytes(dsx_text).decode("utf-8-sig")
        except UnicodeDecodeError:
            return _failed(_err("INVALID_ENCODING", "File DSX bukan UTF-8 yang valid."))
    if not isinstance(dsx_text, str):
        return _failed(_err("INVALID_INPUT", f"dsx_text harus berupa string atau bytes, ditemukan {type(dsx_text).__name__}."))
    referenced: list[str] = []
    try:
        deadline = Deadline(limits.max_render_seconds)
        compiled = compile_dsx(dsx_text, source, limits=limits, filename=source_name, deadline=deadline)
        referenced = compiled.referenced_files
        for item in compiled.diagnostics.items:
            diag.add_diagnostic(item)
        ir = compiled.ir
        if ir is None or diag.has_errors:
            return _failed(bag=diag, referenced=referenced)
        summary: dict[str, Any] = dict(ir.summary())
        summary["format"] = output_format
        if not render:
            return GenerationResult("success", None, None, [], diag.warnings, summary, referenced)
        if before_render is not None:
            blocked = before_render(referenced)
            if blocked is not None:
                return _failed(blocked, bag=diag, referenced=referenced)
        renderer = get_renderer(output_format)
        assert renderer is not None
        try:
            data = renderer.render(ir, deadline)
        except Exception as render_exc:  # DocxRenderError / PdfRenderError
            from ..renderers.docx import DocxRenderError
            from ..renderers.pdf import PdfRenderError

            if isinstance(render_exc, (DocxRenderError, PdfRenderError)):
                return _failed(
                    _err("RENDER_FAILED", str(render_exc)),
                    bag=diag,
                    referenced=referenced,
                )
            raise
        if output_format == "docx":
            report = inspect_docx(data, ir)
            if not report.ok:
                hard = []
                for problem in report.problems:
                    # Body-order drift (SECTION/PAGEBREAK/H1) → warning; paket rusak → error
                    if (
                        problem.startswith("Jumlah elemen body")
                        or problem.startswith("Elemen body #")
                    ):
                        diag.warning("INSPECTION_DRIFT", problem, None)
                    else:
                        hard.append(problem)
                        diag.error("INSPECTION_FAILED", problem)
                if hard:
                    return _failed(bag=diag, referenced=referenced)
            summary["inspection"] = report.stats
        summary["bytes"] = len(data)
        if data is not None:
            _quality_scan_output(data, output_format.lower(), diag)
        return GenerationResult("success", data, None, [], diag.warnings, summary, referenced)
    except FatalDsxError as exc:
        return _failed(exc.diagnostic, bag=diag, referenced=referenced)
    except Exception as exc:  # noqa: BLE001 - kesalahan internal: jangan bocor ke pemanggil
        return _failed(
            _err("INTERNAL_ERROR", f"Terjadi kesalahan internal: {type(exc).__name__}: {exc}"),
            bag=diag,
            referenced=referenced,
        )


def _memory_source(project_files: Any) -> tuple[Source | None, Diagnostic | None]:
    try:
        return MemorySource(project_files), None
    except ValueError as exc:
        return None, _err("INVALID_PROJECT_FILES", str(exc))


def generate_document(
    dsx_text: str,
    project_files: Mapping[str, bytes | str] | None = None,
    output_format: str = "docx",
    *,
    limits: Limits | None = None,
    source_name: str = "document.dsx",
) -> GenerationResult:
    """Kompilasi dan render DSX menjadi dokumen (bytes pada ``result.output``)."""
    lim, bad = _check_limits(limits)
    if bad is not None:
        return _failed(bad)
    bad = _check_common(output_format, source_name)
    if bad is not None:
        return _failed(bad)
    source, bad = _memory_source(project_files)
    if bad is not None:
        return _failed(bad)
    return _run(dsx_text, source, output_format.lower(), lim, source_name, render=True)  # type: ignore[arg-type]


def check_document(
    dsx_text: str,
    project_files: Mapping[str, bytes | str] | None = None,
    *,
    limits: Limits | None = None,
    source_name: str = "document.dsx",
) -> GenerationResult:
    """Validasi saja (parsing, resolusi, validasi semantik) tanpa rendering."""
    lim, bad = _check_limits(limits)
    if bad is not None:
        return _failed(bad)
    bad = _check_common("docx", source_name)
    if bad is not None:
        return _failed(bad)
    source, bad = _memory_source(project_files)
    if bad is not None:
        return _failed(bad)
    return _run(dsx_text, source, "docx", lim, source_name, render=False)  # type: ignore[arg-type]


# ------------------------------------------------------------ keluaran ke disk
def _same_file(a: Path, b: Path) -> bool:
    try:
        if a.resolve() == b.resolve():
            return True
    except (OSError, RuntimeError):
        pass
    try:
        return a.exists() and b.exists() and os.path.samefile(a, b)
    except OSError:
        return False


def _check_output_target(
    root: Path,
    output: Path,
    output_format: str,
    dsx_name: str,
    referenced: list[str],
    overwrite: bool,
) -> Diagnostic | None:
    """Tolak keluaran yang dapat merusak file sumber atau tidak dapat ditulis."""
    ext = _FORMAT_EXT[output_format]
    if output.suffix.lower() != ext:
        return _err(
            "OUTPUT_EXTENSION_INVALID",
            f"Berkas keluaran harus berekstensi {ext} untuk format {output_format}.",
            output=output,
        )
    if output.is_dir():
        return _err("OUTPUT_IS_DIRECTORY", "Path keluaran adalah direktori, bukan berkas.", output=output)
    protected = [root / dsx_name] + [root / rel for rel in referenced]
    try:
        protected += [p for p in root.glob("*.dsx")]
    except OSError:
        pass
    for source_file in protected:
        if _same_file(output, source_file):
            return _err(
                "OUTPUT_COLLIDES_WITH_SOURCE",
                "Path keluaran sama dengan file sumber proyek; operasi dibatalkan agar file sumber tidak tertimpa.",
                output=output,
                source=source_file,
            )
    parent = output.resolve().parent
    if not parent.is_dir():
        return _err("OUTPUT_DIRECTORY_MISSING", "Direktori keluaran tidak ada atau bukan direktori.", directory=parent)
    if not os.access(parent, os.W_OK):
        return _err("OUTPUT_WRITE_FAILED", "Direktori keluaran tidak dapat ditulis.", directory=parent)
    if output.exists() and not overwrite:
        return _err("OUTPUT_EXISTS", "Berkas keluaran sudah ada dan overwrite dinonaktifkan.", output=output)
    return None


def generate_from_directory(
    project_dir: str | os.PathLike[str],
    output_path: str | os.PathLike[str] | None = None,
    output_format: str = "docx",
    *,
    dsx_name: str = "document.dsx",
    limits: Limits | None = None,
    check_only: bool = False,
    overwrite: bool = True,
) -> GenerationResult:
    """Bangun dokumen dari direktori proyek; opsional tulis ke ``output_path``."""
    lim, bad = _check_limits(limits)
    if bad is not None:
        return _failed(bad)
    bad = _check_common(output_format, dsx_name)
    if bad is not None:
        return _failed(bad)
    fmt = output_format.lower()
    if output_path is not None and not isinstance(output_path, (str, os.PathLike)):
        return _failed(_err("INVALID_INPUT", f"output_path harus berupa str atau path, ditemukan {type(output_path).__name__}."))
    if not isinstance(project_dir, (str, os.PathLike)):
        return _failed(_err("INVALID_INPUT", f"project_dir harus berupa str atau path, ditemukan {type(project_dir).__name__}."))
    try:
        source = DirectorySource(project_dir)
    except (OSError, ValueError) as exc:
        return _failed(_err("PROJECT_NOT_FOUND", f"Direktori proyek tidak dapat dibuka: {exc}", directory=project_dir))
    try:
        dsx_rel = normalize_relpath(dsx_name)
        raw = source.read(dsx_rel, lim.max_dsx_bytes)
    except SourceError as exc:
        return _failed(_err(exc.code, f"File DSX tidak dapat dibaca: {exc.message}", reference=dsx_name))
    out = Path(output_path) if (output_path is not None and not check_only) else None

    def before_render(referenced: list[str]) -> Diagnostic | None:
        if out is None:
            return None
        return _check_output_target(source.root, out, fmt, dsx_rel, referenced, overwrite)

    result = _run(raw, source, fmt, lim, dsx_rel, render=not check_only, before_render=before_render)
    if result.ok and result.output is not None and out is not None:
        try:
            _write_atomic(out, result.output)
            result.output_file = str(out)
        except OSError as exc:
            result.status = "failed"
            result.output = None
            result.diagnostics.append(_err("OUTPUT_WRITE_FAILED", f"Gagal menulis berkas keluaran: {exc}", output=out))
    return result


def _write_atomic(path: Path, data: bytes) -> None:
    """Tulis file secara atomik; jatuh ke penulisan langsung bila FS tidak mendukung
    (mis. penyimpanan bersama Android/Termux yang menolak chmod/rename)."""
    path = Path(path)
    directory = path.resolve().parent
    directory.mkdir(parents=True, exist_ok=True)
    tmp_name = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=".dsx-", suffix=".tmp", dir=directory)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            try:
                os.fsync(handle.fileno())
            except OSError:
                pass
        try:
            mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
            os.chmod(tmp_name, mode)
        except OSError:
            pass  # FS tanpa dukungan chmod: abaikan
        os.replace(tmp_name, path)
        tmp_name = None
    except OSError:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
        # cadangan: tulis langsung
        with open(path, "wb") as handle:
            handle.write(data)
    finally:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
    if not path.is_file() or path.stat().st_size != len(data):
        raise OSError(f"Berkas keluaran tidak ditemukan setelah ditulis: {path}")


def compile_to_model(
    dsx_source: str,
    *,
    files: Mapping[str, bytes | str] | None = None,
    source_name: str = "document.dsx",
    limits: Limits | None = None,
) -> tuple[Any | None, GenerationResult]:
    """Compile DSX to DocumentModel (tanpa render). Untuk editor / AI / preview struktur.

    Returns (model|None, GenerationResult) — model None jika gagal compile.
    """
    from ..ir.model import build_document_model
    from .. import LANGUAGE_VERSION

    limits, err = _check_limits(limits)
    if err is not None:
        return None, _failed(err)
    assert limits is not None
    common = _check_common("docx", source_name)
    if common is not None:
        return None, _failed(common)
    if not isinstance(dsx_source, str):
        return None, _failed(_err("INVALID_INPUT", "dsx_source harus string."))
    file_map = dict(files or {})
    file_map[source_name] = dsx_source
    source = MemorySource(file_map)
    diag = DiagnosticBag(limits.max_diagnostics)
    try:
        compiled = compile_dsx(dsx_source, source, limits=limits, filename=source_name)
        for item in compiled.diagnostics.items:
            diag.add_diagnostic(item)
        ir = compiled.ir
        if ir is None or diag.has_errors:
            return None, _failed(bag=diag)
        model = build_document_model(ir, LANGUAGE_VERSION)
        for hint in model.warnings_hints:
            diag.warning("MODEL_HINT", hint, None)
        return model, GenerationResult("success", None, None, [], diag.warnings, model.to_dict(), [])
    except FatalDsxError as exc:
        return None, _failed(exc.diagnostic, bag=diag)
    except Exception as exc:  # pragma: no cover
        return None, _failed(_err("INTERNAL_ERROR", f"Terjadi kesalahan internal: {exc}"), bag=diag)


def list_presets() -> dict:
    """Daftar preset dokumen, penomoran, posisi nomor, dan struktur."""
    from ..presets import list_presets as _lp
    return _lp()


def get_structure_outline(name: str) -> list[str]:
    """Outline disarankan untuk STRUCTURE/PRESET akademik."""
    from ..presets import STRUCTURE_OUTLINES
    return list(STRUCTURE_OUTLINES.get(name.lower(), []))


def scaffold_project(
    directory: str | Path,
    name: str,
    *,
    title: str = "Judul Dokumen",
    author: str = "Penulis",
) -> Path:
    """Tulis kerangka proyek akademik ke directory."""
    from ..scaffold import write_scaffold
    return write_scaffold(directory, name, title=title, author=author)
