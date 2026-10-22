"""Server lokal mode formulir: UI + generate + build + unggah aset.

Jalankan:  python -m dsx form serve -d ./proyek --port 8765
"""

from __future__ import annotations

import json
import mimetypes
import re
import shutil
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from .generator import generate_dsx, generate_project
from .models import FORM_KINDS, default_form, form_ui_schema, load_form
from .schema_export import export_language_schema
from .validate import validate_form


def _safe_rel(name: str) -> str | None:
    """Nama file aman (tanpa path traversal)."""
    name = unquote(name or "").replace("\\", "/").strip()
    if not name or name.startswith("/") or ".." in name.split("/"):
        return None
    base = Path(name).name
    if not base or base in (".", ".."):
        return None
    return base


_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp"}


def _clean_upload_name(name: str) -> str:
    """Nama file aman untuk DSX: hanya [A-Za-z0-9._-], ekstensi huruf kecil."""
    p = Path(name)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", p.stem).strip("._-") or "file"
    ext = re.sub(r"[^A-Za-z0-9.]", "", p.suffix).lower()
    return stem + ext


def _sniff_image(data: bytes) -> str | None:
    """Deteksi format asli dari isi file (bukan ekstensi). None bila tidak dikenal."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data.startswith(b"BM"):
        return "bmp"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[4:8] == b"ftyp":
        return "heic/avif"
    return None


def _convert_image_to_png(data: bytes) -> bytes | None:
    """Konversi webp/tiff/heic dll ke PNG bila Pillow tersedia; None jika gagal."""
    try:
        import io
        from PIL import Image  # type: ignore

        img = Image.open(io.BytesIO(data))
        if img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert("RGBA" if "A" in img.getbands() or "transparency" in img.info else "RGB")
        out = io.BytesIO()
        img.save(out, "PNG")
        return out.getvalue()
    except Exception:
        return None


def _diag_summary(diags: list[dict[str, Any]]) -> str:
    """Ringkas diagnostik build menjadi satu pesan yang bisa dibaca di UI."""
    parts: list[str] = []
    for d in diags[:5]:
        loc = d.get("location") or {}
        where = f" [{loc.get('file', '')}:{loc.get('line', '?')}]" if loc else ""
        det = d.get("details") or {}
        ref = next(iter(det.values()), "") if det else ""
        ref = f" ({ref})" if ref else ""
        parts.append(f"{d.get('code', 'ERROR')}: {d.get('message', '')}{ref}{where}")
    return " | ".join(parts) or "Build gagal"


def _project_files(root: Path) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for folder in ("assets", "data", "content"):
        d = root / folder
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*")):
            if f.is_file():
                rel = str(f.relative_to(root)).replace("\\", "/")
                out.append({"path": rel, "size": str(f.stat().st_size), "folder": folder})
    return out


def _check_form_assets(root: Path, data: dict[str, Any]) -> str | None:
    """Pastikan logo yang dirujuk form ada dan berformat gambar yang didukung."""
    kop = data.get("kop") if isinstance(data.get("kop"), dict) else {}
    for key in ("logo", "logo_kanan"):
        ref = str((kop or {}).get(key) or "").strip()
        if not ref:
            continue
        if Path(ref).suffix.lower() not in _IMAGE_EXTS:
            return f"Logo '{ref}' berformat tidak didukung (gunakan png/jpg/jpeg/gif/bmp)."
        fp = (root / ref).resolve()
        if root not in fp.parents or not fp.is_file():
            return f"File logo '{ref}' tidak ditemukan di proyek. Unggah ulang atau kosongkan kolom logo."
    return None


def make_handler(project_dir: Path, form_ui_dir: Path | None) -> type[BaseHTTPRequestHandler]:
    project_dir = project_dir.resolve()
    project_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("assets", "data", "content"):
        (project_dir / sub).mkdir(exist_ok=True)

    ui_root = form_ui_dir.resolve() if form_ui_dir else None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            print(f"[dsx-form] {self.address_string()} {fmt % args}")

        def _send(self, code: int, body: bytes, content_type: str = "application/json; charset=utf-8") -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, payload: Any) -> None:
            self._send(code, (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            data = json.loads(raw.decode("utf-8") or "{}")
            if not isinstance(data, dict):
                raise ValueError("Body harus objek JSON")
            return data

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._send(204, b"")

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = unquote(parsed.path or "/")

            if path in ("/", "/index.html"):
                return self._serve_ui("surat-resmi.html")
            if path.startswith("/ui/"):
                return self._serve_ui(path[4:])
            if path == "/api/health":
                return self._json(200, {"ok": True, "project": str(project_dir)})
            if path == "/api/schema":
                return self._json(200, export_language_schema())
            if path == "/api/blocks":
                from .blocks import list_block_types
                return self._json(200, {"ok": True, "blocks": list_block_types()})
            if path == "/api/user-presets":
                from .user_presets import list_user_presets
                return self._json(200, {"ok": True, "presets": list_user_presets(project_dir)})
            if path.startswith("/api/user-presets/"):
                from .user_presets import load_user_preset
                name = path[len("/api/user-presets/"):].strip("/")
                try:
                    return self._json(200, load_user_preset(project_dir, name))
                except FileNotFoundError as exc:
                    return self._json(404, {"ok": False, "error": str(exc)})
                except Exception as exc:
                    return self._json(400, {"ok": False, "error": str(exc)})
            if path == "/api/completions":
                from .completions import build_completions
                return self._json(200, build_completions())
            if path.startswith("/api/preset"):
                from .blocks import STRUCTURE_PRESETS, form_from_preset
                qs = parse_qs(parsed.query)
                name = (qs.get("name") or ["kosong"])[0]
                if name not in STRUCTURE_PRESETS:
                    return self._json(400, {"ok": False, "error": "preset tidak valid", "presets": list(STRUCTURE_PRESETS)})
                return self._json(200, form_from_preset(name))
            if path.startswith("/api/default"):
                qs = parse_qs(parsed.query)
                kind = (qs.get("kind") or ["surat-resmi"])[0]
                if kind not in FORM_KINDS:
                    return self._json(400, {"ok": False, "error": "kind tidak valid"})
                return self._json(200, default_form(kind))
            if path.startswith("/api/ui-schema"):
                qs = parse_qs(parsed.query)
                kind = (qs.get("kind") or ["surat-resmi"])[0]
                return self._json(200, form_ui_schema(kind))
            if path == "/api/form":
                fp = project_dir / "form.json"
                if fp.is_file():
                    return self._json(200, json.loads(fp.read_text(encoding="utf-8")))
                return self._json(200, default_form("surat-resmi"))
            if path == "/api/files":
                return self._json(200, {"ok": True, "files": _project_files(project_dir)})
            if path == "/api/dsx":
                fp = project_dir / "document.dsx"
                if not fp.is_file():
                    return self._json(404, {"ok": False, "error": "document.dsx belum ada"})
                return self._send(200, fp.read_text(encoding="utf-8").encode("utf-8"), "text/plain; charset=utf-8")
            if path.startswith("/api/download/"):
                return self._download(path[len("/api/download/") :])
            if path.startswith("/files/"):
                return self._static_project(path[len("/files/") :])

            return self._json(404, {"ok": False, "error": f"Tidak ditemukan: {path}"})

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = unquote(parsed.path or "/")
            try:
                if path == "/api/validate":
                    data = self._read_json()
                    issues = validate_form(data)
                    return self._json(200, {
                        "ok": not any(i["level"] == "error" for i in issues),
                        "issues": issues,
                    })
                if path == "/api/generate":
                    return self._api_generate(build=False, preview_html=False)
                if path == "/api/build":
                    return self._api_generate(build=True, preview_html=False)
                if path == "/api/preview":
                    return self._api_generate(build=True, preview_html=True)
                if path == "/api/upload":
                    return self._api_upload()
                if path == "/api/user-presets":
                    from .user_presets import save_user_preset
                    body = self._read_json()
                    name = str(body.get("name") or "").strip()
                    form = body.get("form")
                    if not isinstance(form, dict):
                        # allow full form at top level with name/description fields
                        form = {k: v for k, v in body.items() if k not in ("name", "description", "overwrite")}
                    try:
                        result = save_user_preset(
                            project_dir, name, form,
                            description=str(body.get("description") or ""),
                            overwrite=bool(body.get("overwrite", True)),
                        )
                    except Exception as exc:
                        return self._json(400, {"ok": False, "error": str(exc)})
                    return self._json(200, result)
                if path == "/api/user-presets/delete":
                    from .user_presets import delete_user_preset
                    body = self._read_json()
                    try:
                        return self._json(200, delete_user_preset(project_dir, str(body.get("name") or "")))
                    except Exception as exc:
                        return self._json(400, {"ok": False, "error": str(exc)})
                if path == "/api/dsx-to-form":
                    from .dsx_to_form import dsx_to_form
                    body = self._read_json()
                    source = str(body.get("source") or "")
                    if not source.strip():
                        # try project document.dsx
                        fp = project_dir / "document.dsx"
                        if fp.is_file():
                            source = fp.read_text(encoding="utf-8")
                    if not source.strip():
                        return self._json(400, {"ok": False, "error": "source kosong"})
                    form = dsx_to_form(source)
                    # optionally write
                    if body.get("save"):
                        (project_dir / "form.json").write_text(
                            json.dumps(form, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                        )
                    return self._json(200, {
                        "ok": True,
                        "form": form,
                        "blocks": len(form.get("blocks") or []),
                    })
                if path == "/api/suggest":
                    from .code_assist import suggest_at_cursor
                    body = self._read_json()
                    source = str(body.get("source") or "")
                    offset = int(body.get("offset") or 0)
                    limit = int(body.get("limit") or 30)
                    return self._json(200, {
                        "ok": True,
                        "items": suggest_at_cursor(source, offset, limit=limit),
                    })
                if path == "/api/highlight":
                    from .code_assist import highlight_dsx
                    body = self._read_json()
                    html = highlight_dsx(str(body.get("source") or ""))
                    return self._json(200, {"ok": True, "html": html})
                if path == "/api/save-dsx":
                    body = self._read_json()
                    source = str(body.get("source") or "")
                    if not source.strip():
                        return self._json(400, {"ok": False, "error": "source kosong"})
                    dsx_path = project_dir / "document.dsx"
                    dsx_path.write_text(source, encoding="utf-8")
                    build = bool(body.get("build", True))
                    payload = {"ok": True, "path": "document.dsx"}
                    if build:
                        from ..api.service import generate_from_directory
                        out_path = str(project_dir / "document.docx")
                        gen = generate_from_directory(
                            project_dir, out_path, "docx", dsx_name="document.dsx", overwrite=True
                        )
                        payload["build_ok"] = gen.ok
                        payload["output_file"] = "document.docx" if gen.ok else None
                        payload["diagnostics"] = [d.to_dict() for d in gen.diagnostics]
                        payload["warnings"] = [d.to_dict() for d in gen.warnings]
                        payload["message"] = "Build OK" if gen.ok else "Build gagal"
                        if not gen.ok:
                            payload["ok"] = False
                            payload["error"] = _diag_summary(payload["diagnostics"])
                            return self._json(400, payload)
                        payload["message"] = "document.dsx disimpan + document.docx siap"
                    return self._json(200, payload)
                if path == "/api/save-form":
                    data = self._read_json()
                    issues = validate_form(data)
                    if any(i["level"] == "error" for i in issues):
                        return self._json(400, {"ok": False, "issues": issues})
                    (project_dir / "form.json").write_text(
                        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                    )
                    return self._json(200, {"ok": True, "path": "form.json", "issues": issues})
            except Exception as exc:
                return self._json(500, {
                    "ok": False,
                    "error": str(exc),
                    "trace": traceback.format_exc()[-2000:],
                })
            return self._json(404, {"ok": False, "error": f"POST tidak dikenal: {path}"})

        def _api_generate(self, *, build: bool, preview_html: bool) -> None:
            data = self._read_json()
            # allow { "form": {...} } or raw form object
            if "form" in data and isinstance(data["form"], dict):
                data = data["form"]
            issues = validate_form(data)
            if any(i["level"] == "error" for i in issues):
                return self._json(400, {"ok": False, "issues": issues})

            missing = _check_form_assets(project_dir, data)
            if missing:
                return self._json(400, {"ok": False, "error": missing, "issues": [
                    {"level": "error", "path": "assets", "message": missing}]})

            result = generate_project(
                data=data,
                out_dir=project_dir,
                dsx_name="document.dsx",
                form_name="form.json",
                write_form_copy=True,
            )
            if not result["ok"]:
                return self._json(400, result)

            payload: dict[str, Any] = {
                "ok": True,
                "issues": result["issues"],
                "dsx_path": "document.dsx",
                "form_path": "form.json",
                "dsx_preview": (project_dir / "document.dsx").read_text(encoding="utf-8")[:12000],
            }

            if build or preview_html:
                from ..api.service import generate_from_directory

                fmt = "html" if preview_html else "docx"
                out_name = "preview.html" if preview_html else "document.docx"
                out_path = str(project_dir / out_name)
                gen = generate_from_directory(
                    project_dir, out_path, fmt, dsx_name="document.dsx", overwrite=True
                )
                payload["build_ok"] = gen.ok
                payload["output_file"] = out_name if gen.ok else None
                payload["diagnostics"] = [d.to_dict() for d in gen.diagnostics]
                payload["warnings"] = [d.to_dict() for d in gen.warnings]
                if preview_html and gen.ok:
                    html_text = Path(out_path).read_text(encoding="utf-8", errors="replace")
                    # batasi ukuran respons
                    payload["html"] = html_text[:200_000]
                if not gen.ok:
                    payload["ok"] = False
                    payload["error"] = _diag_summary(payload["diagnostics"])
                    return self._json(400, payload)

            self._json(200, payload)

        def _api_upload(self) -> None:
            """Multipart: field file (+ folder assets|data|content). Robust thd boundary & binary."""
            ctype = self.headers.get("Content-Type", "")
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""

            if "multipart/form-data" not in ctype:
                return self._json(400, {"ok": False, "error": "Gunakan multipart/form-data"})

            m = re.search(r'boundary="?([^";]+)"?', ctype, re.I)
            if not m:
                return self._json(400, {"ok": False, "error": "boundary tidak ada"})
            boundary = m.group(1).strip().encode("ascii", "ignore")
            sep = b"--" + boundary
            parts = body.split(sep)
            folder = "assets"
            filename = None
            filedata = None
            for part in parts:
                if b"Content-Disposition" not in part:
                    continue
                # strip leading CRLF
                if part.startswith(b"\r\n"):
                    part = part[2:]
                elif part.startswith(b"\n"):
                    part = part[1:]
                # hapus satu CRLF pemisah sebelum boundary (aman untuk data biner)
                if part.endswith(b"\r\n"):
                    part = part[:-2]
                elif part.endswith(b"\n"):
                    part = part[:-1]

                header, sep2, content = part.partition(b"\r\n\r\n")
                if not sep2:
                    header, sep2, content = part.partition(b"\n\n")
                if not sep2:
                    continue

                hs = header.decode("utf-8", "replace")
                if 'name="folder"' in hs:
                    folder = content.decode("utf-8", "replace").strip() or "assets"
                elif 'name="file"' in hs or "filename=" in hs:
                    fm = re.search(r'filename\*?=(?:UTF-8\'\'\')?"?([^";\r\n]+)"?', hs, re.I)
                    if not fm:
                        fm = re.search(r'filename="([^"]*)"', hs)
                    filename = (fm.group(1) if fm else "upload.bin").strip()
                    # decode RFC 5987-ish
                    try:
                        from urllib.parse import unquote
                        filename = unquote(filename)
                    except Exception:
                        pass
                    filedata = content

            if folder not in ("assets", "data", "content"):
                folder = "assets"
            safe = _safe_rel(filename or "")
            if safe:
                safe = _clean_upload_name(safe)
            if not safe or filedata is None:
                return self._json(400, {
                    "ok": False,
                    "error": "File tidak valid (pastikan field name=file dan server form serve aktif)",
                    "debug": {"filename": filename, "has_data": filedata is not None, "body_len": length},
                })

            if folder == "assets":
                from ..source import SourceError, normalize_image_bytes, sniff_image_format

                real = sniff_image_format(filedata) or _sniff_image(filedata)
                try:
                    # buang byte sampah / perbaiki PNG terpotong / konversi WEBP,TIFF via Pillow
                    fixed = normalize_image_bytes(filedata)
                except SourceError as exc:
                    return self._json(400, {
                        "ok": False,
                        "error": (
                            f"Isi file '{filename}' ({len(filedata)} byte, terdeteksi: "
                            f"{real or 'tidak dikenal'}) tidak dapat dibaca sebagai gambar. {exc.message}"
                        ),
                    })
                filedata = fixed
                real2 = sniff_image_format(filedata)
                ext = {"PNG": "png", "JPEG": "jpg", "GIF": "gif", "BMP": "bmp"}.get(real2 or "", "png")
                safe = Path(safe).stem + "." + ext
            dest_dir = project_dir / folder
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / safe
            dest.write_bytes(filedata)
            rel = f"{folder}/{safe}"
            return self._json(200, {"ok": True, "path": rel, "size": len(filedata)})

        def _download(self, name: str) -> None:
            safe = _safe_rel(name)
            if not safe:
                return self._json(400, {"ok": False, "error": "Nama tidak valid"})
            # allow known outputs or files under project (one level + assets/)
            candidates = [
                project_dir / safe,
                project_dir / "assets" / safe,
                project_dir / "data" / safe,
                project_dir / "content" / safe,
            ]
            for fp in candidates:
                if not fp.is_file():
                    continue
                resolved = fp.resolve()
                if resolved.parent == project_dir or project_dir in resolved.parents:
                    data = resolved.read_bytes()
                    ctype = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
                    self.send_response(200)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Content-Disposition", f'attachment; filename="{resolved.name}"')
                    self.end_headers()
                    self.wfile.write(data)
                    return
            self._json(404, {"ok": False, "error": "File tidak ada"})

        def _static_project(self, rel: str) -> None:
            rel = rel.replace("\\", "/")
            if ".." in rel.split("/"):
                return self._json(400, {"ok": False, "error": "Path tidak valid"})
            fp = (project_dir / rel).resolve()
            if not str(fp).startswith(str(project_dir)) or not fp.is_file():
                return self._json(404, {"ok": False, "error": "Tidak ditemukan"})
            data = fp.read_bytes()
            ctype = mimetypes.guess_type(str(fp))[0] or "application/octet-stream"
            self._send(200, data, ctype)

        def _serve_ui(self, name: str) -> None:
            name = Path(name).name
            if not name.endswith(".html"):
                name += ".html"
            candidates = []
            if ui_root:
                candidates.append(ui_root / name)
            # bundled next to package
            pkg_ui = Path(__file__).resolve().parents[3] / "form-ui" / name
            candidates.append(pkg_ui)
            candidates.append(Path(__file__).resolve().parent / "static" / name)

            for fp in candidates:
                if fp.is_file():
                    data = fp.read_text(encoding="utf-8").encode("utf-8")
                    return self._send(200, data, "text/html; charset=utf-8")
            self._json(404, {"ok": False, "error": f"UI tidak ditemukan: {name}"})

    return Handler


def run_server(
    project_dir: str | Path = ".",
    host: str = "127.0.0.1",
    port: int = 8765,
    form_ui_dir: str | Path | None = None,
) -> None:
    root = Path(project_dir).resolve()
    ui = Path(form_ui_dir).resolve() if form_ui_dir else None
    if ui is None:
        # default: dsx-src/form-ui
        cand = Path(__file__).resolve().parents[3] / "form-ui"
        if cand.is_dir():
            ui = cand

    handler = make_handler(root, ui)
    httpd = ThreadingHTTPServer((host, port), handler)
    print(f"DSX Form server: http://{host}:{port}/")
    print(f"  proyek : {root}")
    print(f"  UI     : {ui or '(bundled search)'}")
    print("  API    : /api/generate  /api/build  /api/preview  /api/upload")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer dihentikan.")
        httpd.server_close()
