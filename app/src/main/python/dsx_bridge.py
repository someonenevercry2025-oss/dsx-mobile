"""
dsx_bridge.py — thin JSON-in/JSON-out layer over the DSX engine.

All public functions accept/return JSON strings so Kotlin never holds
Python objects. Exceptions are never raised to the caller; every
failure is wrapped as {"ok": false, ...}.
"""

from __future__ import annotations

import json
import os
import traceback
from pathlib import Path
from typing import Any

# Ensure the bundled dsx package is importable (Chaquopy puts python/ on sys.path)
import dsx
from dsx import __version__ as DSX_VERSION
from dsx import LANGUAGE_VERSION
from dsx.api.service import generate_from_directory
from dsx.diagnostics import Diagnostic
from dsx.form.blocks import form_from_preset, list_block_types, new_block
from dsx.form.dsx_to_form import dsx_to_form as _dsx_to_form
from dsx.form.format_dsx import format_dsx as _format_dsx
from dsx.form.blocks import surat_as_blocks
from dsx.form.generator import generate_dsx as _generate_dsx_text
from dsx.form.generator import generate_project
from dsx.form.models import default_form, load_form
from dsx.form.validate import validate_form as _validate_form
from dsx.form.user_presets import (
    list_user_presets as _list_user_presets,
    save_user_preset as _save_user_preset,
    load_user_preset as _load_user_preset,
    delete_user_preset as _delete_user_preset,
)
from dsx.source import normalize_image_bytes


def _ok(data: Any = None, diagnostics: list | None = None, warnings: list | None = None) -> str:
    return json.dumps(
        {
            "ok": True,
            "data": data,
            "diagnostics": diagnostics or [],
            "warnings": warnings or [],
        },
        ensure_ascii=False,
        default=str,
    )


def _fail(code: str, message: str, **extra: Any) -> str:
    payload = {
        "ok": False,
        "data": None,
        "diagnostics": [{"code": code, "message": message, **extra}],
        "warnings": [],
    }
    return json.dumps(payload, ensure_ascii=False, default=str)


def _diag_to_dict(d: Diagnostic) -> dict:
    loc = None
    if d.location is not None:
        loc = {
            "source": getattr(d.location, "source", None),
            "line": getattr(d.location, "line", None),
            "column": getattr(d.location, "column", None),
        }
    return {
        "severity": d.severity.value if hasattr(d.severity, "value") else str(d.severity),
        "code": d.code,
        "message": d.message,
        "location": loc,
    }


def _parse_json(s: str) -> Any:
    return json.loads(s) if s else None


# ---------------------------------------------------------------------------
# Public API (called from Kotlin via PythonBridge)
# ---------------------------------------------------------------------------

def version() -> str:
    """Return package and language versions."""
    try:
        return _ok({
            "package": DSX_VERSION,
            "language": LANGUAGE_VERSION,
        })
    except Exception as e:
        return _fail("BRIDGE_ERROR", str(e), traceback=traceback.format_exc())


def list_blocks() -> str:
    """Return the 20-block catalogue for the custom form editor."""
    try:
        catalog = list_block_types()
        return _ok(catalog)
    except Exception as e:
        return _fail("BRIDGE_ERROR", str(e), traceback=traceback.format_exc())


def get_preset(name: str) -> str:
    """Return a full form.json for a named built-in preset."""
    try:
        form = form_from_preset(name)
        return _ok(form)
    except Exception as e:
        return _fail("PRESET_NOT_FOUND", str(e))


def default_form_kind(kind: str) -> str:
    """Return the default form.json for surat-resmi / laporan / makalah / custom."""
    try:
        form = default_form(kind)
        return _ok(form)
    except Exception as e:
        return _fail("INVALID_FORM_KIND", str(e))


def validate_form(form_json: str) -> str:
    """Validate a form dict; return list of issues (empty = ok)."""
    try:
        form = _parse_json(form_json)
        issues = _validate_form(form)
        # issues may be list of Diagnostic or plain dicts
        out = []
        for i in issues or []:
            if isinstance(i, Diagnostic):
                out.append(_diag_to_dict(i))
            elif isinstance(i, dict):
                out.append(i)
            else:
                out.append({"message": str(i)})
        return _ok(out)
    except Exception as e:
        return _fail("VALIDATE_ERROR", str(e), traceback=traceback.format_exc())


def generate_dsx(form_json: str, project_dir: str) -> str:
    """Generate document.dsx (and supporting files) from form.json into project_dir."""
    try:
        form = _parse_json(form_json)
        project_dir = os.path.abspath(project_dir)
        os.makedirs(project_dir, exist_ok=True)
        # generate_project(data=..., out_dir=...) writes document.dsx + form.json
        result = generate_project(data=form, out_dir=project_dir)
        if not result.get("ok"):
            errs = [i for i in (result.get("issues") or []) if i.get("level") == "error"]
            msg = "; ".join(f'{i.get("path") or "form"}: {i.get("message")}' for i in errs) or "Form tidak valid"
            return _fail("FORM_INVALID", msg, issues=result.get("issues") or [])
        dsx_path = os.path.join(project_dir, "document.dsx")
        if not os.path.isfile(dsx_path):
            return _fail("GENERATE_DSX_FAILED", "document.dsx tidak dihasilkan", detail=str(result))
        return _ok({"path": dsx_path, "result": result})
    except Exception as e:
        return _fail("GENERATE_DSX_FAILED", str(e), traceback=traceback.format_exc())


def build(project_dir: str, fmt: str = "docx", out_name: str | None = None) -> str:
    """
    Build document from project directory.
    fmt: docx | html  (pdf via LibreOffice is not available on Android)
    """
    try:
        project_dir = os.path.abspath(project_dir)
        if not os.path.isdir(project_dir):
            return _fail("PROJECT_NOT_FOUND", f"Folder proyek tidak ada: {project_dir}")

        fmt = (fmt or "docx").lower()
        if fmt not in ("docx", "html"):
            return _fail(
                "OUTPUT_EXTENSION_INVALID",
                f"Format {fmt!r} tidak didukung di Android. Gunakan docx atau html.",
            )

        out_dir = os.path.join(project_dir, "output")
        os.makedirs(out_dir, exist_ok=True)

        if out_name is None:
            out_name = f"document.{fmt}"
        elif not out_name.endswith(f".{fmt}"):
            out_name = f"{out_name}.{fmt}"

        out_path = os.path.join(out_dir, out_name)

        result = generate_from_directory(
            project_dir,
            output_format=fmt,
            output_path=out_path,
        )

        diagnostics = [_diag_to_dict(d) for d in (result.diagnostics or [])]
        warnings = [_diag_to_dict(d) for d in (result.warnings or [])]

        if not result.ok:
            return json.dumps(
                {
                    "ok": False,
                    "data": None,
                    "diagnostics": diagnostics,
                    "warnings": warnings,
                },
                ensure_ascii=False,
                default=str,
            )

        # Prefer path written by engine; fall back to our path
        final_path = result.output_file or out_path
        if result.output is not None and not os.path.isfile(final_path):
            with open(final_path, "wb") as f:
                f.write(result.output)

        size = os.path.getsize(final_path) if os.path.isfile(final_path) else 0
        return _ok(
            {
                "path": final_path,
                "size": size,
                "format": fmt,
                "render_summary": result.render_summary or {},
            },
            diagnostics=diagnostics,
            warnings=warnings,
        )
    except Exception as e:
        return _fail("BUILD_FAILED", str(e), traceback=traceback.format_exc())


def check_dsx(project_dir: str) -> str:
    """Run diagnostics only (check_only) on a project directory."""
    try:
        project_dir = os.path.abspath(project_dir)
        result = generate_from_directory(
            project_dir,
            output_format="docx",
            check_only=True,
        )
        diagnostics = [_diag_to_dict(d) for d in (result.diagnostics or [])]
        warnings = [_diag_to_dict(d) for d in (result.warnings or [])]
        return _ok(
            {"status": result.status},
            diagnostics=diagnostics,
            warnings=warnings,
        )
    except Exception as e:
        return _fail("CHECK_FAILED", str(e), traceback=traceback.format_exc())


def dsx_to_form(text: str) -> str:
    """Best-effort conversion of DSX source text into a custom form."""
    try:
        form = _dsx_to_form(text)
        return _ok(form)
    except Exception as e:
        return _fail("DSX_TO_FORM_FAILED", str(e), traceback=traceback.format_exc())


def to_blocks(form_json: str) -> str:
    """Ubah form templat (surat/laporan/makalah) menjadi form kustom berbasis blok."""
    try:
        form = _parse_json(form_json)
        if not isinstance(form, dict):
            return _fail("INVALID_FORM", "Form harus objek JSON")
        kind = str(form.get("kind") or "")
        if kind == "custom":
            return _ok(form)
        if kind == "surat-resmi":
            new = surat_as_blocks(form)
        else:
            base = default_form(kind)
            base.update(form)
            new = _dsx_to_form(_generate_dsx_text(base))
        new["kind"] = "custom"
        return _ok(new)
    except Exception as e:
        return _fail("TO_BLOCKS_FAILED", str(e), traceback=traceback.format_exc())


def format_dsx(text: str) -> str:
    """Pretty-print / format DSX source."""
    try:
        formatted = _format_dsx(text)
        return _ok(formatted)
    except Exception as e:
        return _fail("FORMAT_FAILED", str(e), traceback=traceback.format_exc())


def normalize_image(path: str) -> str:
    """
    Validate and normalise an image file (Pillow).
    Returns the (possibly rewritten) absolute path on success.
    """
    try:
        path = os.path.abspath(path)
        if not os.path.isfile(path):
            return _fail("INVALID_IMAGE", f"Berkas gambar tidak ditemukan: {path}")

        with open(path, "rb") as f:
            data = f.read()

        try:
            normalised = normalize_image_bytes(data)
        except Exception as img_err:
            return _fail("INVALID_IMAGE", str(img_err))

        # Write back if content changed
        if normalised != data:
            with open(path, "wb") as f:
                f.write(normalised)

        return _ok({"path": path, "size": len(normalised)})
    except Exception as e:
        return _fail("INVALID_IMAGE", str(e), traceback=traceback.format_exc())


def new_block_json(block_type: str) -> str:
    """Return a fresh default payload for a single block type."""
    try:
        block = new_block(block_type)
        return _ok(block)
    except Exception as e:
        return _fail("UNKNOWN_BLOCK", str(e))


def list_presets(presets_root: str) -> str:
    """List user presets stored under presets_root (acts as pseudo project dir)."""
    try:
        items = _list_user_presets(presets_root)
        return _ok(items)
    except Exception as e:
        return _fail("PRESET_LIST_FAILED", str(e), traceback=traceback.format_exc())


def save_preset(presets_root: str, name: str, form_json: str, description: str = "") -> str:
    try:
        data = _parse_json(form_json)
        result = _save_user_preset(presets_root, name, data, description=description or "")
        return _ok(result)
    except Exception as e:
        return _fail("PRESET_SAVE_FAILED", str(e), traceback=traceback.format_exc())


def load_preset(presets_root: str, name: str) -> str:
    try:
        data = _load_user_preset(presets_root, name)
        # Strip internal meta before returning as form
        data.pop("_preset_meta", None)
        return _ok(data)
    except Exception as e:
        return _fail("PRESET_LOAD_FAILED", str(e), traceback=traceback.format_exc())


def delete_preset(presets_root: str, name: str) -> str:
    try:
        result = _delete_user_preset(presets_root, name)
        return _ok(result)
    except Exception as e:
        return _fail("PRESET_DELETE_FAILED", str(e), traceback=traceback.format_exc())
