"""Preset pengguna: simpan / muat / daftar / hapus form kustom per proyek.

Disimpan di:  <project>/presets/<nama>.json
Metadata opsional: _preset_meta { name, description, created, updated }
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SAFE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sanitize_name(name: str) -> str:
    name = (name or "").strip().replace(" ", "-")
    if not _SAFE.match(name):
        raise ValueError(
            "Nama preset hanya boleh huruf, angka, titik, underscore, strip "
            "(1–64 karakter, diawali alfanumerik)."
        )
    return name


def presets_dir(project_dir: str | Path) -> Path:
    d = Path(project_dir).resolve() / "presets"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_user_presets(project_dir: str | Path) -> list[dict[str, Any]]:
    root = presets_dir(project_dir)
    out: list[dict[str, Any]] = []
    for fp in sorted(root.glob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            out.append({"name": fp.stem, "path": str(fp), "error": "JSON rusak"})
            continue
        meta = data.get("_preset_meta") or {}
        out.append({
            "name": fp.stem,
            "path": str(fp.relative_to(Path(project_dir).resolve())).replace("\\", "/"),
            "title": (data.get("meta") or {}).get("title") or fp.stem,
            "kind": data.get("kind"),
            "blocks": len(data.get("blocks") or []) if isinstance(data.get("blocks"), list) else None,
            "description": meta.get("description") or "",
            "created": meta.get("created"),
            "updated": meta.get("updated"),
        })
    return out


def save_user_preset(
    project_dir: str | Path,
    name: str,
    data: dict[str, Any],
    *,
    description: str = "",
    overwrite: bool = True,
) -> dict[str, Any]:
    name = sanitize_name(name)
    if not isinstance(data, dict):
        raise ValueError("Data form harus objek JSON")
    root = presets_dir(project_dir)
    dest = root / f"{name}.json"
    if dest.exists() and not overwrite:
        raise FileExistsError(f"Preset sudah ada: {name}")

    payload = dict(data)
    old_meta = {}
    if dest.exists():
        try:
            old_meta = (json.loads(dest.read_text(encoding="utf-8")).get("_preset_meta")) or {}
        except Exception:
            old_meta = {}
    payload["_preset_meta"] = {
        "name": name,
        "description": description or old_meta.get("description") or "",
        "created": old_meta.get("created") or _now(),
        "updated": _now(),
    }
    dest.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "name": name,
        "path": str(dest.relative_to(Path(project_dir).resolve())).replace("\\", "/"),
    }


def load_user_preset(project_dir: str | Path, name: str) -> dict[str, Any]:
    name = sanitize_name(name)
    fp = presets_dir(project_dir) / f"{name}.json"
    if not fp.is_file():
        raise FileNotFoundError(f"Preset tidak ditemukan: {name}")
    data = json.loads(fp.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Preset rusak")
    return data


def delete_user_preset(project_dir: str | Path, name: str) -> dict[str, Any]:
    name = sanitize_name(name)
    fp = presets_dir(project_dir) / f"{name}.json"
    if not fp.is_file():
        raise FileNotFoundError(f"Preset tidak ditemukan: {name}")
    fp.unlink()
    return {"ok": True, "name": name, "deleted": True}
