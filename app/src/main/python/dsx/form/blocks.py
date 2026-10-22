"""Blok dokumen yang dapat disusun ulang (mode form kustom).

Setiap blok punya `type` + field spesifik. Urutan di array `blocks` = urutan di dokumen.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# Katalog blok: type → metadata UI + default payload
BLOCK_CATALOG: dict[str, dict[str, Any]] = {
    "kop": {
        "label": "Kop surat / header lembaga",
        "group": "header",
        "default": {
            "type": "kop",
            "lines": ["NAMA LEMBAGA", "NAMA UNIT"],
            "alamat": "",
            "kontak": "",
            "logo": None,       # path kiri / tunggal
            "logo_kanan": None, # path kanan (opsional → mode 2 logo)
            "logo_lebar_cm": 2.2,
            "logo_mode": "auto",  # auto | one | two
            "garis": "bottom",
            "garis_tebal_pt": 1.5,
            "garis_warna": "000000",
        },
    },
    "identitas_surat": {
        "label": "Nomor / Lampiran / Perihal",
        "group": "header",
        "default": {
            "type": "identitas_surat",
            "nomor": "",
            "lampiran": "-",
            "perihal": "",
            "perihal_bold": True,
            "kota_tanggal": "",
        },
    },
    "penerima": {
        "label": "Alamat penerima (Yth.)",
        "group": "header",
        "default": {
            "type": "penerima",
            "yth": "",
            "baris_tambahan": [],
            "di": "Tempat",
        },
    },
    "heading": {
        "label": "Judul / heading",
        "group": "teks",
        "default": {"type": "heading", "level": 1, "text": "Judul"},
    },
    "title": {
        "label": "Judul dokumen (role title)",
        "group": "teks",
        "default": {"type": "title", "text": "JUDUL", "subtitle": ""},
    },
    "paragraph": {
        "label": "Paragraf",
        "group": "teks",
        "default": {
            "type": "paragraph",
            "text": "",
            "first_line_indent_cm": 1.0,
            "align": "justify",
            "space_after": 6,
        },
    },
    "paragraphs": {
        "label": "Beberapa paragraf",
        "group": "teks",
        "default": {
            "type": "paragraphs",
            "items": [""],
            "first_line_indent_cm": 1.0,
        },
    },
    "text_line": {
        "label": "Baris teks pendek",
        "group": "teks",
        "default": {
            "type": "text_line",
            "text": "",
            "align": "left",
            "bold": False,
            "space_after": 0,
        },
    },
    "kv_table": {
        "label": "Tabel label : nilai (tanpa border)",
        "group": "data",
        "default": {
            "type": "kv_table",
            "rows": [{"label": "Field", "nilai": ""}],
            "numbered": True,
            "label_width_cm": 4.2,
        },
    },
    "table": {
        "label": "Tabel data (grid)",
        "group": "data",
        "default": {
            "type": "table",
            "headers": ["Kolom 1", "Kolom 2"],
            "rows": [["", ""]],
            "border": "grid",
            "caption": "",
            "header_shading": "D9D9D9",
        },
    },
    "csv_table": {
        "label": "Tabel dari file CSV",
        "group": "data",
        "default": {
            "type": "csv_table",
            "path": "data/file.csv",
            "caption": "",
            "border": "grid",
        },
    },
    "list": {
        "label": "Daftar bullet / bernomor",
        "group": "teks",
        "default": {
            "type": "list",
            "ordered": False,
            "items": ["Item 1", "Item 2"],
        },
    },
    "hr": {
        "label": "Garis horizontal",
        "group": "layout",
        "default": {
            "type": "hr",
            "style": "solid",
            "thickness": 1.0,
            "color": "000000",
            "space_before": 4,
            "space_after": 8,
        },
    },
    "spacer": {
        "label": "Spasi kosong",
        "group": "layout",
        "default": {"type": "spacer", "space_after": 12},
    },
    "pagebreak": {
        "label": "Pindah halaman",
        "group": "layout",
        "default": {"type": "pagebreak"},
    },
    "figure": {
        "label": "Gambar",
        "group": "media",
        "default": {
            "type": "figure",
            "src": "assets/gambar.png",
            "width_cm": 10,
            "caption": "",
            "align": "center",
        },
    },
    "callout": {
        "label": "Kotak catatan / callout",
        "group": "teks",
        "default": {
            "type": "callout",
            "callout_type": "info",
            "title": "",
            "text": "",
        },
    },
    "signature": {
        "label": "Blok tanda tangan",
        "group": "penutup",
        "default": {
            "type": "signature",
            "columns": [
                {"jabatan": "Sekretaris", "nama": "[Nama]"},
                {"jabatan": "Ketua", "nama": "[Nama]"},
            ],
        },
    },
    "mengetahui": {
        "label": "Mengetahui / atasan",
        "group": "penutup",
        "default": {
            "type": "mengetahui",
            "label": "Mengetahui,",
            "nama": "[Nama]",
            "nip": "",
        },
    },
    "toc": {
        "label": "Daftar isi",
        "group": "navigasi",
        "default": {"type": "toc", "title": "Daftar Isi", "depth": 3},
    },
}


def list_block_types() -> list[dict[str, Any]]:
    """Daftar tipe blok untuk UI / CLI."""
    out = []
    for type_id, meta in BLOCK_CATALOG.items():
        out.append({
            "type": type_id,
            "label": meta["label"],
            "group": meta.get("group", "lain"),
            "default": deepcopy(meta["default"]),
        })
    return out


def new_block(type_id: str, **overrides: Any) -> dict[str, Any]:
    if type_id not in BLOCK_CATALOG:
        raise ValueError(f"Tipe blok tidak dikenal: {type_id}")
    block = deepcopy(BLOCK_CATALOG[type_id]["default"])
    block.update(overrides)
    block["type"] = type_id
    return block


def default_custom_form() -> dict[str, Any]:
    """Kerangka kosong — pengguna menambah blok sendiri."""
    return {
        "kind": "custom",
        "version": 2,
        "meta": {"title": "Dokumen Kustom", "author": ""},
        "page": {
            "size": "A4",
            "margin_top_cm": 2.0,
            "margin_bottom_cm": 2.0,
            "margin_left_cm": 2.5,
            "margin_right_cm": 2.5,
        },
        "style": {
            "font": "Times New Roman",
            "size": 12,
            "line": 1.15,
        },
        "blocks": [],
    }


def surat_as_blocks(data: dict[str, Any]) -> dict[str, Any]:
    """Konversi form surat-resmi (v1) → custom blocks (v2)."""
    kop = data.get("kop") or {}
    ident = data.get("identitas") or {}
    penerima = data.get("penerima") or {}
    mengetahui = data.get("mengetahui") or {}
    blocks: list[dict[str, Any]] = []

    blocks.append(new_block(
        "kop",
        lines=list(kop.get("lines") or []),
        alamat=kop.get("alamat") or "",
        kontak=kop.get("kontak") or "",
        logo=kop.get("logo"),
        logo_kanan=kop.get("logo_kanan"),
        logo_lebar_cm=float(kop.get("logo_lebar_cm") or 2.2),
        logo_mode=kop.get("logo_mode") or "auto",
        garis=kop.get("garis") or "bottom",
        garis_tebal_pt=float(kop.get("garis_tebal_pt") or 1.5),
        garis_warna=kop.get("garis_warna") or "000000",
    ))
    blocks.append(new_block("spacer", space_after=6))
    blocks.append(new_block(
        "identitas_surat",
        nomor=ident.get("nomor") or "",
        lampiran=ident.get("lampiran") or "-",
        perihal=ident.get("perihal") or "",
        perihal_bold=bool(ident.get("perihal_bold", True)),
        kota_tanggal=ident.get("kota_tanggal") or "",
    ))
    blocks.append(new_block(
        "penerima",
        yth=penerima.get("yth") or "",
        baris_tambahan=list(penerima.get("baris_tambahan") or []),
        di=penerima.get("di") or "Tempat",
    ))
    blocks.append(new_block("text_line", text=data.get("pembuka") or "Dengan hormat,", space_after=8))
    for p in data.get("paragraf") or []:
        blocks.append(new_block("paragraph", text=str(p)))
    if data.get("tampilkan_rincian"):
        intro = data.get("rincian_intro") or ""
        if intro:
            blocks.append(new_block("paragraph", text=str(intro)))
        blocks.append(new_block(
            "kv_table",
            rows=[{"label": str(r.get("label") or ""), "nilai": str(r.get("nilai") or "")}
                  for r in (data.get("rincian") or [])],
            numbered=True,
        ))
    for p in data.get("penutup") or []:
        blocks.append(new_block("paragraph", text=str(p)))
    blocks.append(new_block("text_line", text=data.get("penutup_hormat") or "Hormat kami,", space_after=2))
    for org in data.get("organisasi_bawah") or []:
        blocks.append(new_block("text_line", text=str(org), space_after=0))
    blocks.append(new_block("spacer", space_after=6))
    ttd = data.get("ttd") or []
    if ttd:
        blocks.append(new_block(
            "signature",
            columns=[{"jabatan": t.get("jabatan") or "", "nama": t.get("nama") or ""} for t in ttd],
        ))
    if mengetahui.get("aktif"):
        blocks.append(new_block(
            "mengetahui",
            label=mengetahui.get("label") or "Mengetahui,",
            nama=mengetahui.get("nama") or "",
            nip=mengetahui.get("nip") or "",
        ))

    page = data.get("page") or {}
    return {
        "kind": "custom",
        "version": 2,
        "meta": dict(data.get("meta") or {"title": "Surat", "author": ""}),
        "page": {
            "size": page.get("size") or "A4",
            "margin_top_cm": float(page.get("margin_top_cm", 2.0)),
            "margin_bottom_cm": float(page.get("margin_bottom_cm", 2.0)),
            "margin_left_cm": float(page.get("margin_left_cm", 2.5)),
            "margin_right_cm": float(page.get("margin_right_cm", 2.5)),
        },
        "style": {"font": "Times New Roman", "size": 12, "line": 1.15},
        "blocks": blocks,
        "_converted_from": "surat-resmi",
    }


# Preset struktur siap pakai (hanya daftar type, diisi default)
STRUCTURE_PRESETS: dict[str, list[str]] = {
    "surat-resmi": [
        "kop", "spacer", "identitas_surat", "penerima", "text_line",
        "paragraphs", "kv_table", "paragraphs", "text_line", "signature", "mengetahui",
    ],
    "laporan-singkat": [
        "title", "heading", "paragraphs", "table", "heading", "paragraphs", "signature",
    ],
    "makalah": [
        "title", "toc", "heading", "paragraphs", "heading", "paragraphs", "heading", "paragraphs",
    ],
    "kosong": ["paragraph"],
}


def form_from_preset(preset: str) -> dict[str, Any]:
    names = STRUCTURE_PRESETS.get(preset) or STRUCTURE_PRESETS["kosong"]
    form = default_custom_form()
    form["meta"]["title"] = preset
    form["blocks"] = [new_block(t) for t in names]
    form["_preset"] = preset
    return form
