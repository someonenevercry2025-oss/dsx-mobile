"""Update Word fields (TOC, LISTOFTABLES, page numbers) via LibreOffice."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


def find_soffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        path = shutil.which(name)
        if path:
            return path
    for candidate in (
        "/usr/bin/soffice",
        "/usr/bin/libreoffice",
        "/usr/lib/libreoffice/program/soffice",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def update_fields(docx_path: str | Path, output: str | Path | None = None, timeout: int = 120) -> Path:
    """Open DOCX in LibreOffice headless and rewrite it so fields are calculated.

    LibreOffice updates TOC/SEQ fields on open+save. Returns path to result file.
    """
    soffice = find_soffice()
    if soffice is None:
        raise RuntimeError(
            "LibreOffice (soffice) tidak ditemukan. Pasang LibreOffice untuk update field TOC."
        )
    src = Path(docx_path).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"File .docx tidak ditemukan: {src}")
    if src.suffix.lower() != ".docx":
        raise ValueError(f"Berkas harus berekstensi .docx: {src.name}")
    out = Path(output).resolve() if output else src
    with tempfile.TemporaryDirectory(prefix="dsx-fields-") as tmp:
        tmp_path = Path(tmp)
        in_dir = tmp_path / "in"
        out_dir = tmp_path / "out"
        in_dir.mkdir()
        out_dir.mkdir()
        work = in_dir / src.name
        work.write_bytes(src.read_bytes())
        # Macro-less approach: convert to ODT and back forces field update in many LO versions.
        # More reliable: use --convert-to docx which re-saves and updates fields.
        cmd = [
            soffice,
            "--headless",
            "--nologo",
            "--nolockcheck",
            "--nodefault",
            "--norestore",
            "--convert-to",
            "docx",
            "--outdir",
            str(out_dir),
            str(work),
        ]
        env = os.environ.copy()
        env.setdefault("HOME", tmp)
        proc = subprocess.run(cmd, capture_output=True, timeout=timeout, env=env, check=False)
        result = out_dir / src.name
        if not result.is_file():
            # LO may change extension casing
            candidates = list(out_dir.glob("*.docx"))
            if not candidates:
                err = (proc.stderr or b"").decode("utf-8", "replace")[:400]
                raise RuntimeError(f"Update field gagal (kode {proc.returncode}): {err}")
            result = candidates[0]
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(result.read_bytes())
        if not out.is_file():
            raise FileNotFoundError(f"File .docx hasil tidak ditemukan setelah ditulis: {out}")
        return out
