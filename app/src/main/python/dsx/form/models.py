"""Model data form (JSON) per jenis dokumen."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

FORM_KINDS = ("surat-resmi", "laporan", "makalah", "custom")

_SURAT_DEFAULT: dict[str, Any] = {
    "kind": "surat-resmi",
    "version": 1,
    "meta": {
        "title": "Surat Permohonan",
        "author": "",
    },
    "page": {
        "size": "A4",
        "margin_top_cm": 2.0,
        "margin_bottom_cm": 2.0,
        "margin_left_cm": 2.5,
        "margin_right_cm": 2.5,
    },
    "kop": {
        "lines": [
            "UNIT KEGIATAN MAHASISWA (UKM)",
            "SENI ZAORAH SAPAN STKIP ANDI MATAPPA",
        ],
        "alamat": "Kampus STKIP Andi Matappa, Jl. Lamaruddani, Kel. Tumampua, Kec. Pangkajene",
        "kontak": "Email: ukmzaorahsapan@gmail.com",
        "logo": None,  # path relatif kiri/tunggal, mis. assets/logo.png
        "logo_kanan": None,  # path logo kanan (opsional)
        "logo_lebar_cm": 2.2,
        "logo_mode": "auto",  # auto | one | two
        "garis": "bottom",  # bottom | hr | none
        "garis_tebal_pt": 1.5,
        "garis_warna": "000000",
    },
    "identitas": {
        "nomor": "[Nomor]/B/KODE/[Bulan Romawi]/[Tahun]",
        "lampiran": "-",
        "perihal": "Permohonan Izin Kunjungan Museum",
        "perihal_bold": True,
        "kota_tanggal": "Pangkajene, [Hari, Tanggal Bulan Tahun]",
    },
    "penerima": {
        "yth": "Kepala/Pengelola Museum Karst dan Budaya Pangkep",
        "baris_tambahan": [],
        "di": "Tempat",
    },
    "salam_buka": "",
    "pembuka": "Dengan hormat,",
    "salam_tutup": "",
    "paragraf": [
        "Dalam rangka menambah wawasan serta meningkatkan apresiasi terhadap seni, sejarah, dan kebudayaan, kami bermaksud mengajukan permohonan izin untuk melaksanakan kunjungan edukatif.",
        "Kegiatan ini bertujuan memperluas pengetahuan anggota mengenai sejarah, seni, dan budaya, serta menjadi sarana pembelajaran langsung.",
    ],
    "tampilkan_rincian": True,
    "rincian_intro": "Adapun rencana pelaksanaan kegiatan tersebut adalah sebagai berikut.",
    "rincian": [
        {"label": "Nama Kegiatan", "nilai": "Kunjungan Edukatif ke Museum Karst dan Budaya Pangkep"},
        {"label": "Hari/Tanggal", "nilai": "[Hari, Tanggal Bulan Tahun]"},
        {"label": "Waktu", "nilai": "[Pukul Mulai–Selesai]"},
        {"label": "Tempat", "nilai": "Museum Karst dan Budaya Pangkep"},
        {"label": "Jumlah Peserta", "nilai": "[Jumlah] orang"},
        {"label": "Penanggung Jawab", "nilai": "[Nama Ketua]"},
    ],
    "penutup": [
        "Sehubungan dengan hal tersebut, kami memohon kesediaan pihak terkait untuk memberikan izin sesuai waktu yang direncanakan.",
        "Kami berkomitmen mematuhi seluruh peraturan yang berlaku serta menjaga ketertiban selama kegiatan berlangsung.",
        "Demikian surat permohonan ini kami sampaikan. Atas perhatian dan kerja sama yang diberikan, kami mengucapkan terima kasih.",
    ],
    "penutup_hormat": "Hormat kami,",
    "organisasi_bawah": ["UKM Seni Zaorah Sapan Matappa", "STKIP Andi Matappa"],
    "ttd": [
        {
            "label": "",
            "jabatan": "Sekretaris Umum",
            "nama": "[Nama Sekretaris]",
            "identitas": "",
            "jabatan_bawah": "",
        },
        {
            "label": "",
            "jabatan": "Ketua Umum",
            "nama": "[Nama Ketua]",
            "identitas": "",
            "jabatan_bawah": "",
        },
    ],
    # Baris TTD tambahan full-width (mis. Menyetujui)
    "ttd_extra": [],
    "mengetahui": {
        "aktif": True,
        "label": "Dosen Pendamping,",
        "jabatan": "",
        "nama": "[Nama Dosen]",
        "nip": "[NIDN/NIP]",
    },
    "tembusan": [],
    "footer": {
        "aktif": False,
        "motto": "",
        "kontak": "",
    },
}

_LAPORAN_DEFAULT: dict[str, Any] = {
    "kind": "laporan",
    "version": 1,
    "meta": {"title": "Laporan Kegiatan", "author": "[Nama Penyusun]"},
    "page": {"size": "A4", "margin_cm": 2.5},
    "header_text": "[Nama Instansi]",
    "judul": "[JUDUL LAPORAN]",
    "subjudul": "[Subjudul — Tanggal]",
    "bab": [
        {"judul": "1. Pendahuluan", "paragraf": ["[Latar belakang dan tujuan.]"]},
        {"judul": "2. Pelaksanaan", "paragraf": ["[Uraian pelaksanaan.]"]},
        {"judul": "3. Hasil dan Pembahasan", "paragraf": ["[Temuan utama.]"]},
        {"judul": "4. Kesimpulan dan Saran", "paragraf": ["[Kesimpulan singkat.]"]},
    ],
    "tabel_acara": {
        "aktif": True,
        "caption": "Tabel 1. Susunan acara",
        "headers": ["No", "Kegiatan", "Waktu", "Keterangan"],
        "rows": [
            ["1", "[Sesi 1]", "[08.00–09.00]", "[...]"],
            ["2", "[Sesi 2]", "[09.00–10.30]", "[...]"],
        ],
    },
    "csv_tabel": None,  # {"path": "data/hasil.csv", "caption": "Tabel 2. Hasil"}
    "ttd": {"kota_tanggal": "[Kota], [Tanggal]", "jabatan": "Penyusun,", "nama": "[Nama]"},
}

_MAKALAH_DEFAULT: dict[str, Any] = {
    "kind": "makalah",
    "version": 1,
    "meta": {"title": "[Judul Makalah]", "author": "[Nama Penulis]", "language": "id-ID"},
    "page": {"size": "A4", "margin_cm": 3.0},
    "header_text": "[Judul Singkat]",
    "judul": "[JUDUL MAKALAH]",
    "subjudul": "",
    "penulis": ["[Nama Penulis]", "[Afiliasi]", "[Email]"],
    "toc": True,
    "bab": [
        {"judul": "1. Pendahuluan", "paragraf": ["[Latar belakang.]"], "sub": []},
        {
            "judul": "2. Kajian Pustaka",
            "paragraf": ["[Ringkasan teori.]"],
            "sub": [
                {"judul": "2.1 [Subtopik]", "paragraf": ["[Uraian.]"]},
            ],
        },
        {"judul": "3. Metode", "paragraf": ["[Pendekatan dan data.]"], "sub": []},
        {"judul": "4. Hasil dan Pembahasan", "paragraf": ["[Temuan.]"], "sub": []},
        {"judul": "5. Kesimpulan", "paragraf": ["[Kesimpulan dan saran.]"], "sub": []},
    ],
    "pustaka": [
        "[Penulis, A. (Tahun). Judul buku. Kota: Penerbit.]",
        "[Penulis, B. (Tahun). Judul artikel. Nama Jurnal, Vol(No), halaman.]",
    ],
}


def default_form(kind: str = "surat-resmi") -> dict[str, Any]:
    kind = (kind or "surat-resmi").strip().lower()
    if kind == "custom":
        from .blocks import default_custom_form
        return default_custom_form()
    if kind == "laporan":
        return deepcopy(_LAPORAN_DEFAULT)
    if kind == "makalah":
        return deepcopy(_MAKALAH_DEFAULT)
    return deepcopy(_SURAT_DEFAULT)


def load_form(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("form.json harus berupa objek JSON")
    kind = str(data.get("kind") or "surat-resmi")
    base = default_form(kind)
    # shallow-merge top-level keys from file over defaults
    base.update(data)
    base["kind"] = kind
    return base


def form_ui_schema(kind: str = "surat-resmi") -> dict[str, Any]:
    """Deskripsi field untuk membangun UI form (F02 pendukung editor)."""
    kind = kind.strip().lower()
    if kind == "surat-resmi":
        return {
            "kind": kind,
            "title": "Surat Resmi / Permohonan",
            "sections": [
                {
                    "id": "kop",
                    "label": "Kop surat",
                    "fields": [
                        {"name": "kop.lines", "type": "string_list", "label": "Baris nama (tebal)"},
                        {"name": "kop.alamat", "type": "text", "label": "Alamat"},
                        {"name": "kop.kontak", "type": "text", "label": "Email / Telp"},
                        {"name": "kop.logo", "type": "file_image", "label": "Logo"},
                        {
                            "name": "kop.garis",
                            "type": "enum",
                            "label": "Garis bawah kop",
                            "choices": ["bottom", "hr", "none"],
                        },
                        {"name": "kop.garis_tebal_pt", "type": "number", "label": "Ketebalan garis (pt)", "min": 0.5, "max": 3},
                    ],
                },
                {
                    "id": "identitas",
                    "label": "Identitas surat",
                    "fields": [
                        {"name": "identitas.nomor", "type": "text", "label": "Nomor"},
                        {"name": "identitas.lampiran", "type": "text", "label": "Lampiran"},
                        {"name": "identitas.perihal", "type": "text", "label": "Perihal"},
                        {"name": "identitas.perihal_bold", "type": "bool", "label": "Perihal tebal"},
                        {"name": "identitas.kota_tanggal", "type": "text", "label": "Kota, tanggal"},
                    ],
                },
                {
                    "id": "penerima",
                    "label": "Penerima",
                    "fields": [
                        {"name": "penerima.yth", "type": "text", "label": "Yth."},
                        {"name": "penerima.di", "type": "text", "label": "di"},
                    ],
                },
                {
                    "id": "isi",
                    "label": "Isi surat",
                    "fields": [
                        {"name": "paragraf", "type": "string_list", "label": "Paragraf isi"},
                        {"name": "tampilkan_rincian", "type": "bool", "label": "Tampilkan tabel rincian"},
                        {"name": "rincian", "type": "kv_list", "label": "Rincian (label / nilai)"},
                        {"name": "penutup", "type": "string_list", "label": "Paragraf penutup"},
                    ],
                },
                {
                    "id": "ttd",
                    "label": "Tanda tangan",
                    "fields": [
                        {"name": "ttd", "type": "ttd_list", "label": "Kolom TTD"},
                        {"name": "mengetahui.aktif", "type": "bool", "label": "Tambah Mengetahui / Pendamping"},
                        {"name": "mengetahui.nama", "type": "text", "label": "Nama mengetahui"},
                        {"name": "mengetahui.nip", "type": "text", "label": "NIP/NIDN"},
                    ],
                },
            ],
        }
    return {"kind": kind, "title": kind, "sections": []}
