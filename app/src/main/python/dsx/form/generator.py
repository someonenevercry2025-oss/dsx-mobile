"""Generate document.dsx dari data form JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .escape import dsx_str
from .models import default_form, load_form
from .validate import validate_form


def generate_dsx(data: dict[str, Any]) -> str:
    """Kembalikan sumber DSX lengkap sebagai string."""
    kind = str(data.get("kind") or "surat-resmi").lower()
    if kind == "custom":
        return _gen_custom(data)
    if kind == "surat-resmi":
        return _gen_surat(data)
    if kind == "laporan":
        return _gen_laporan(data)
    if kind == "makalah":
        return _gen_makalah(data)
    raise ValueError(f"Jenis form tidak didukung: {kind}")


def _gen_custom(d: dict[str, Any]) -> str:
    """Form fleksibel berbasis blocks[]."""
    from .block_render import render_blocks

    meta = d.get("meta") or {}
    page = d.get("page") or {}
    style = d.get("style") or {}
    mt = float(page.get("margin_top_cm", page.get("margin_cm", 2.5)))
    mb = float(page.get("margin_bottom_cm", page.get("margin_cm", 2.5)))
    ml = float(page.get("margin_left_cm", page.get("margin_cm", 2.5)))
    mr = float(page.get("margin_right_cm", page.get("margin_cm", 2.5)))
    size = page.get("size") or "A4"
    font = style.get("font") or "Times New Roman"
    fsize = float(style.get("size") or 12)
    line = float(style.get("line") or 1.15)

    lines: list[str] = [
        'DSX(version="2.6")',
        "DOC(",
        f"  title={dsx_str(meta.get('title') or 'Dokumen')},",
        f"  author={dsx_str(meta.get('author') or '')}",
        ")",
        "PAGE(",
        f'  size={dsx_str(size)},',
        f"  margin_top={mt}cm,",
        f"  margin_bottom={mb}cm,",
        f"  margin_left={ml}cm,",
        f"  margin_right={mr}cm",
        ")",
        f'STYLEDEF(normal, font={dsx_str(font)}, size={fsize}, line={line})',
        "",
        "# === generated from custom blocks ===",
        "",
    ]
    lines.extend(render_blocks(list(d.get("blocks") or [])))
    return "\n".join(lines) + "\n"


def generate_project(
    form_path: str | Path | None = None,
    *,
    data: dict[str, Any] | None = None,
    out_dir: str | Path,
    dsx_name: str = "document.dsx",
    form_name: str = "form.json",
    write_form_copy: bool = True,
) -> dict[str, Any]:
    """
    Tulis form.json + document.dsx ke out_dir.
    Returns {ok, issues, dsx_path, form_path}.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    if data is None:
        if form_path is None:
            raise ValueError("Perlu form_path atau data")
        data = load_form(form_path)
    else:
        kind = str(data.get("kind") or "surat-resmi")
        base = default_form(kind)
        base.update(data)
        data = base

    issues = validate_form(data)
    errors = [i for i in issues if i["level"] == "error"]
    if errors:
        return {
            "ok": False,
            "issues": issues,
            "dsx_path": None,
            "form_path": None,
        }

    dsx_text = generate_dsx(data)
    dsx_path = out / dsx_name
    dsx_path.parent.mkdir(parents=True, exist_ok=True)
    dsx_path.write_text(dsx_text, encoding="utf-8")

    form_out = out / form_name
    if write_form_copy:
        form_out.parent.mkdir(parents=True, exist_ok=True)
        form_out.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "ok": True,
        "issues": issues,
        "dsx_path": str(dsx_path),
        "form_path": str(form_out) if write_form_copy else None,
    }


# ---------------------------------------------------------------------------
# Surat resmi
# ---------------------------------------------------------------------------

def _gen_surat(d: dict[str, Any]) -> str:
    meta = d.get("meta") or {}
    page = d.get("page") or {}
    kop = d.get("kop") or {}
    ident = d.get("identitas") or {}
    penerima = d.get("penerima") or {}
    mengetahui = d.get("mengetahui") or {}

    mt = float(page.get("margin_top_cm", 2.0))
    mb = float(page.get("margin_bottom_cm", 2.0))
    ml = float(page.get("margin_left_cm", 2.5))
    mr = float(page.get("margin_right_cm", 2.5))
    size = page.get("size") or "A4"

    lines: list[str] = [
        'DSX(version="2.6")',
        "DOC(",
        f"  title={dsx_str(meta.get('title') or 'Surat')},",
        f"  author={dsx_str(meta.get('author') or '')}",
        ")",
        "PAGE(",
        f'  size={dsx_str(size)},',
        f"  margin_top={mt}cm,",
        f"  margin_bottom={mb}cm,",
        f"  margin_left={ml}cm,",
        f"  margin_right={mr}cm",
        ")",
        "",
        "# === KOP (generated from form) ===",
    ]

    from .block_render import render_blocks
    kop_block = {
        "type": "kop",
        "lines": list(kop.get("lines") or []),
        "alamat": kop.get("alamat") or "",
        "kontak": kop.get("kontak") or "",
        "logo": kop.get("logo"),
        "logo_kanan": kop.get("logo_kanan"),
        "logo_lebar_cm": float(kop.get("logo_lebar_cm") or 2.2),
        "logo_mode": kop.get("logo_mode") or "auto",
        "garis": kop.get("garis") or "bottom",
        "garis_tebal_pt": float(kop.get("garis_tebal_pt") or 1.5),
        "garis_warna": kop.get("garis_warna") or "000000",
    }
    lines.extend(render_blocks([kop_block]))
    lines.append("")
    lines += ["", 'P("", space_after=6)', "", "# === IDENTITAS ==="]

    perihal = str(ident.get("perihal") or "")
    perihal_cell = (
        f'CELL([BOLD({dsx_str(perihal)})], align="left")'
        if ident.get("perihal_bold", True)
        else f'CELL({dsx_str(perihal)}, align="left")'
    )
    lines += [
        "TABLE(",
        '  border="none",',
        "  cell_padding=0.05cm,",
        '  widths=["2.8cm", "0.4cm", "*"],',
        "  rows=[",
        f'    [CELL("Nomor", align="left"), CELL(":", align="left"), CELL({dsx_str(ident.get("nomor") or "")}, align="left")],',
        f'    [CELL("Lampiran", align="left"), CELL(":", align="left"), CELL({dsx_str(ident.get("lampiran") or "-")}, align="left")],',
        f"    [CELL(\"Perihal\", align=\"left\"), CELL(\":\", align=\"left\"), {perihal_cell}]",
        "  ]",
        ")",
        "",
        'P("", space_after=4)',
        f'P({dsx_str(ident.get("kota_tanggal") or "")}, align="left", space_after=10)',
        "",
        f'P({dsx_str("Yth. " + str(penerima.get("yth") or ""))}, space_after=0)',
    ]
    for extra in penerima.get("baris_tambahan") or []:
        lines.append(f'P({dsx_str(str(extra))}, space_after=0)')
    lines += [
        'P("di", space_after=0)',
        f'P({dsx_str(penerima.get("di") or "Tempat")}, space_after=10)',
        "",
        f'P({dsx_str(d.get("pembuka") or "Dengan hormat,")}, space_after=8)',
        "",
    ]

    for p in d.get("paragraf") or []:
        lines.append(
            f'P({dsx_str(str(p))}, first_line_indent=1.0cm, space_after=6)'
        )

    if d.get("tampilkan_rincian"):
        intro = d.get("rincian_intro") or ""
        if intro:
            lines.append(f'P({dsx_str(str(intro))}, first_line_indent=1.0cm, space_after=6)')
        lines.append("")
        lines.append("# === RINCIAN ===")
        rows_src: list[str] = []
        for i, item in enumerate(d.get("rincian") or [], start=1):
            label = str((item or {}).get("label") or "")
            nilai = str((item or {}).get("nilai") or "")
            rows_src.append(
                f'    [CELL("{i}.", align="left"), CELL({dsx_str(label)}, align="left"), '
                f'CELL(":", align="left"), CELL({dsx_str(nilai)}, align="left")]'
            )
        if rows_src:
            lines += [
                "TABLE(",
                '  border="none",',
                "  cell_padding=0.06cm,",
                '  widths=["0.6cm", "4.2cm", "0.4cm", "*"],',
                "  rows=[",
                ",\n".join(rows_src),
                "  ]",
                ")",
                "",
                'P("", space_after=4)',
            ]

    for p in d.get("penutup") or []:
        lines.append(
            f'P({dsx_str(str(p))}, first_line_indent=1.0cm, space_after=6)'
        )

    lines += [
        "",
        f'P({dsx_str(d.get("penutup_hormat") or "Hormat kami,")}, space_after=2)',
    ]
    for org in d.get("organisasi_bawah") or []:
        lines.append(f'P({dsx_str(str(org))}, space_after=0)')
    lines.append('P("", space_after=6)')
    lines.append("")
    lines.append("# === TTD ===")

    ttd_list = d.get("ttd") or []
    if ttd_list:
        n = len(ttd_list)
        widths = ", ".join(['"*"'] * n)
        jab = ", ".join(
            f'CELL({dsx_str(str(t.get("jabatan") or ""))}, align="center")' for t in ttd_list
        )
        spasi = ", ".join(['CELL("\\n\\n\\n\\n", align="center")'] * n)
        nama = ", ".join(
            f'CELL([BOLD({dsx_str(str(t.get("nama") or ""))})], align="center")' for t in ttd_list
        )
        lines += [
            "TABLE(",
            '  border="none",',
            "  cell_padding=0.05cm,",
            f"  widths=[{widths}],",
            "  rows=[",
            f"    [{jab}],",
            f"    [{spasi}],",
            f"    [{nama}]",
            "  ]",
            ")",
        ]

    if mengetahui.get("aktif"):
        lines += [
            "",
            'P("", space_after=10)',
            f'P({dsx_str(mengetahui.get("label") or "Mengetahui,")}, space_after=0)',
            'P("\\n\\n\\n", space_after=0)',
            f'P([BOLD({dsx_str(str(mengetahui.get("nama") or ""))})], space_after=0)',
            f'P({dsx_str(str(mengetahui.get("nip") or ""))}, space_after=0)',
        ]

    lines.append("")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Laporan
# ---------------------------------------------------------------------------

def _gen_laporan(d: dict[str, Any]) -> str:
    meta = d.get("meta") or {}
    page = d.get("page") or {}
    margin = float(page.get("margin_cm", 2.5))
    size = page.get("size") or "A4"
    lines = [
        'DSX(version="2.6")',
        f'DOC(title={dsx_str(meta.get("title") or "Laporan")}, author={dsx_str(meta.get("author") or "")})',
        f'PAGE(size={dsx_str(size)}, margin={margin}cm)',
        f'HEADER({dsx_str(d.get("header_text") or "")}, align="right", size=9)',
        'PAGENUM(format="Halaman {page}", align="center")',
        "",
        'STYLEDEF(isi, extends="normal", font="Times New Roman", size=12, align="justify", first_line_indent=1.25cm, line=1.5, space_after=6)',
        "",
        f'TEXT({dsx_str(d.get("judul") or "Laporan")}, role="title")',
    ]
    if d.get("subjudul"):
        lines.append(f'TEXT({dsx_str(d.get("subjudul"))}, role="subtitle")')
    lines.append("")

    for bab in d.get("bab") or []:
        lines.append(f'H1({dsx_str(str(bab.get("judul") or ""))})')
        for p in bab.get("paragraf") or []:
            lines.append(f'P({dsx_str(str(p))}, style="isi")')
        lines.append("")

    tabel = d.get("tabel_acara") or {}
    if tabel.get("aktif"):
        headers = tabel.get("headers") or ["No", "Kegiatan", "Waktu"]
        h = ", ".join(dsx_str(str(x)) for x in headers)
        row_parts = []
        for row in tabel.get("rows") or []:
            cells = ", ".join(dsx_str(str(c)) for c in row)
            row_parts.append(f"[{cells}]")
        rows_joined = ", ".join(row_parts)
        lines += [
            "TABLE(",
            f"  headers=[{h}],",
            f"  rows=[{rows_joined}],",
            '  border="grid",',
            "  border_width=0.5,",
            '  header_shading="D9D9D9",',
            f'  caption={dsx_str(tabel.get("caption") or "")}',
            ")",
            "",
        ]

    csv_t = d.get("csv_tabel")
    if isinstance(csv_t, dict) and csv_t.get("path"):
        lines += [
            "TABLE(",
            f'  data=CSV({dsx_str(csv_t["path"])}),',
            "  header=true,",
            '  border="grid",',
            f'  caption={dsx_str(csv_t.get("caption") or "")}',
            ")",
            "",
        ]

    ttd = d.get("ttd") or {}
    lines += [
        f'P({dsx_str(ttd.get("kota_tanggal") or "")}, align="right", space_after=2)',
        f'P({dsx_str(ttd.get("jabatan") or "Penyusun,")}, align="right", space_after=0)',
        'P("\\n\\n\\n", align="right", space_after=0)',
        f'P([BOLD({dsx_str(ttd.get("nama") or "")})], align="right")',
        "",
    ]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Makalah
# ---------------------------------------------------------------------------

def _gen_makalah(d: dict[str, Any]) -> str:
    meta = d.get("meta") or {}
    page = d.get("page") or {}
    margin = float(page.get("margin_cm", 3.0))
    lines = [
        'DSX(version="2.6")',
        "DOC(",
        f'  title={dsx_str(meta.get("title") or "Makalah")},',
        f'  author={dsx_str(meta.get("author") or "")},',
        f'  language={dsx_str(meta.get("language") or "id-ID")}',
        ")",
        f'PAGE(size={dsx_str(page.get("size") or "A4")}, margin={margin}cm)',
        f'HEADER({dsx_str(d.get("header_text") or "")}, align="right", size=9)',
        'PAGENUM(format="Halaman {page} dari {pages}", align="center")',
        "",
        'STYLEDEF(isi, extends="normal", font="Times New Roman", size=12, align="justify", first_line_indent=1.25cm, line=1.5, space_after=0)',
        'STYLEDEF(pustaka, extends="normal", font="Times New Roman", size=12, left_indent=1.25cm, hanging_indent=1.25cm, line=1.0, space_after=6)',
        "",
        f'TEXT({dsx_str(d.get("judul") or "")}, role="title")',
    ]
    if d.get("subjudul"):
        lines.append(f'TEXT({dsx_str(d.get("subjudul"))}, role="subtitle")')
    for p in d.get("penulis") or []:
        lines.append(f'P({dsx_str(str(p))}, align="center", space_after=0)')
    lines.append('P("", space_after=12)')
    if d.get("toc", True):
        lines.append('TOC(title="Daftar Isi", depth=3)')
        lines.append("")

    for bab in d.get("bab") or []:
        lines.append(f'H1({dsx_str(str(bab.get("judul") or ""))})')
        for p in bab.get("paragraf") or []:
            lines.append(f'P({dsx_str(str(p))}, style="isi")')
        for sub in bab.get("sub") or []:
            lines.append(f'H2({dsx_str(str(sub.get("judul") or ""))})')
            for p in sub.get("paragraf") or []:
                lines.append(f'P({dsx_str(str(p))}, style="isi")')
        lines.append("")

    if d.get("pustaka"):
        lines.append('H1("Daftar Pustaka")')
        for item in d["pustaka"]:
            lines.append(f'P({dsx_str(str(item))}, style="pustaka")')
        lines.append("")

    return "\n".join(lines) + "\n"
