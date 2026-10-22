"""Preset akademik, penomoran, dan struktur dokumen (P2)."""

from __future__ import annotations

from typing import Any

# Template name mapping
PRESET_TEMPLATE: dict[str, str] = {
    "makalah": "makalah",
    "skripsi": "skripsi",
    "laporan": "laporan",
    "praktikum": "praktikum",
    "artikel": "artikel",
    "academic_front_roman": "skripsi",
    "academic_body_decimal": "skripsi",
}

# Numbering recipes applied via SECTION/PAGENUM defaults (documentation + compiler hints)
NUMBERING_PRESETS: dict[str, dict[str, Any]] = {
    "roman_then_decimal": {
        "front": {
            "page_number_format": "lower_roman",
            "page_number_start": 1,
            "page_number_placement": "bottom_center",
            "show_page_number": True,
        },
        "body": {
            "page_number_format": "decimal",
            "page_number_start": 1,
            "page_number_restart": True,
            "page_number_placement": "bottom_right",
            "show_page_number": True,
        },
    },
    "decimal_only": {
        "front": {
            "page_number_format": "decimal",
            "page_number_start": 1,
            "page_number_placement": "bottom_center",
            "show_page_number": True,
        },
        "body": {
            "page_number_format": "decimal",
            "page_number_continue": True,
            "page_number_placement": "bottom_center",
            "show_page_number": True,
        },
    },
    "none": {
        "front": {"show_page_number": False},
        "body": {"show_page_number": False},
    },
}

PAGE_NUMBER_PLACEMENT_PRESETS: dict[str, dict[str, str]] = {
    "academic_footer": {"placement": "bottom_center", "format": "Halaman {page}"},
    "academic_header": {"placement": "top_right", "format": "{page}"},
    "top_left": {"placement": "top_left", "format": "{page}"},
    "top_center": {"placement": "top_center", "format": "{page}"},
    "top_right": {"placement": "top_right", "format": "{page}"},
    "bottom_left": {"placement": "bottom_left", "format": "{page}"},
    "bottom_center": {"placement": "bottom_center", "format": "{page}"},
    "bottom_right": {"placement": "bottom_right", "format": "{page}"},
}

# Suggested outline snippets (not auto-injected unless STRUCTURE used with expand)
STRUCTURE_OUTLINES: dict[str, list[str]] = {
    "makalah": [
        "HALAMAN JUDUL",
        "Kata Pengantar",
        "Daftar Isi",
        "BAB I PENDAHULUAN",
        "BAB II ISI",
        "BAB III PENUTUP",
        "Daftar Pustaka",
    ],
    "skripsi": [
        "HALAMAN JUDUL",
        "HALAMAN PENGESAHAN",
        "Kata Pengantar",
        "Abstrak",
        "Daftar Isi",
        "BAB I PENDAHULUAN",
        "BAB II TINJAUAN PUSTAKA",
        "BAB III METODE PENELITIAN",
        "BAB IV HASIL DAN PEMBAHASAN",
        "BAB V KESIMPULAN DAN SARAN",
        "Daftar Pustaka",
        "Lampiran",
    ],
    "laporan": [
        "HALAMAN JUDUL",
        "Ringkasan Eksekutif",
        "Daftar Isi",
        "1. Pendahuluan",
        "2. Metode",
        "3. Hasil",
        "4. Pembahasan",
        "5. Kesimpulan",
        "Daftar Pustaka",
    ],
    "praktikum": [
        "Judul Praktikum",
        "Tujuan",
        "Dasar Teori",
        "Alat dan Bahan",
        "Prosedur",
        "Hasil",
        "Pembahasan",
        "Kesimpulan",
        "Daftar Pustaka",
    ],
    "artikel": [
        "Judul",
        "Abstrak",
        "Pendahuluan",
        "Metode",
        "Hasil",
        "Pembahasan",
        "Kesimpulan",
        "Daftar Pustaka",
    ],
}


def list_presets() -> dict[str, Any]:
    return {
        "document": sorted(PRESET_TEMPLATE.keys()),
        "numbering": sorted(NUMBERING_PRESETS.keys()),
        "page_number_placement": sorted(PAGE_NUMBER_PLACEMENT_PRESETS.keys()),
        "structure": sorted(STRUCTURE_OUTLINES.keys()),
    }


def resolve_template_name(preset_name: str) -> str | None:
    return PRESET_TEMPLATE.get(preset_name.lower())
