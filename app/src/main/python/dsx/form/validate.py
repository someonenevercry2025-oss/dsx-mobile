"""Validasi data form sebelum generate."""

from __future__ import annotations

from typing import Any

from .models import FORM_KINDS


def validate_form(data: dict[str, Any]) -> list[dict[str, str]]:
    """Kembalikan daftar issue: {level, path, message}. level: error|warning."""
    issues: list[dict[str, str]] = []
    if not isinstance(data, dict):
        return [{"level": "error", "path": "", "message": "Form harus objek JSON"}]

    kind = str(data.get("kind") or "").strip().lower()
    if kind not in FORM_KINDS:
        issues.append({
            "level": "error",
            "path": "kind",
            "message": f"kind harus salah satu: {', '.join(FORM_KINDS)}",
        })
        return issues

    if kind == "custom":
        _validate_custom(data, issues)
    elif kind == "surat-resmi":
        _validate_surat(data, issues)
    elif kind == "laporan":
        if not str(data.get("judul") or "").strip():
            issues.append({"level": "warning", "path": "judul", "message": "Judul laporan masih kosong"})
    elif kind == "makalah":
        if not str(data.get("judul") or "").strip():
            issues.append({"level": "warning", "path": "judul", "message": "Judul makalah masih kosong"})

    return issues


def _validate_custom(data: dict[str, Any], issues: list[dict[str, str]]) -> None:
    from .blocks import BLOCK_CATALOG

    blocks = data.get("blocks")
    if not isinstance(blocks, list):
        issues.append({"level": "error", "path": "blocks", "message": "custom form wajib punya array blocks"})
        return
    if len(blocks) == 0:
        issues.append({"level": "warning", "path": "blocks", "message": "blocks kosong — dokumen hampir kosong"})
    for i, block in enumerate(blocks):
        if not isinstance(block, dict):
            issues.append({"level": "error", "path": f"blocks[{i}]", "message": "setiap blok harus objek"})
            continue
        btype = str(block.get("type") or "").strip()
        if not btype:
            issues.append({"level": "error", "path": f"blocks[{i}].type", "message": "type wajib"})
        elif btype not in BLOCK_CATALOG:
            issues.append({
                "level": "error",
                "path": f"blocks[{i}].type",
                "message": f"type tidak dikenal: {btype}",
            })


def _validate_surat(data: dict[str, Any], issues: list[dict[str, str]]) -> None:
    kop = data.get("kop") or {}
    if not isinstance(kop, dict):
        issues.append({"level": "error", "path": "kop", "message": "kop harus objek"})
        return
    lines = kop.get("lines") or []
    if not lines or not any(str(x).strip() for x in lines):
        issues.append({"level": "error", "path": "kop.lines", "message": "Minimal satu baris nama di kop"})

    garis = str(kop.get("garis") or "bottom").lower()
    if garis not in ("bottom", "hr", "none"):
        issues.append({
            "level": "error",
            "path": "kop.garis",
            "message": "garis harus bottom, hr, atau none",
        })

    ident = data.get("identitas") or {}
    if not str((ident or {}).get("perihal") or "").strip():
        issues.append({"level": "warning", "path": "identitas.perihal", "message": "Perihal masih kosong"})

    penerima = data.get("penerima") or {}
    if not str((penerima or {}).get("yth") or "").strip():
        issues.append({"level": "warning", "path": "penerima.yth", "message": "Penerima (Yth) masih kosong"})

    if data.get("tampilkan_rincian"):
        rincian = data.get("rincian") or []
        if not rincian:
            issues.append({
                "level": "warning",
                "path": "rincian",
                "message": "tampilkan_rincian aktif tetapi daftar rincian kosong",
            })

    ttd = data.get("ttd") or []
    if not ttd:
        issues.append({"level": "warning", "path": "ttd", "message": "Belum ada kolom tanda tangan"})
