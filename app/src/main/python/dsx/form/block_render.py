"""Render array blocks → baris sumber DSX."""

from __future__ import annotations

from typing import Any

from .escape import dsx_str


def render_blocks(blocks: list[Any]) -> list[str]:
    lines: list[str] = []
    for i, raw in enumerate(blocks or []):
        if not isinstance(raw, dict):
            continue
        btype = str(raw.get("type") or "").strip().lower()
        fn = _RENDERERS.get(btype)
        if fn is None:
            lines.append(f"# [blok tidak dikenal: {btype}]")
            continue
        chunk = fn(raw)
        if chunk:
            lines.append(f"# --- block[{i}] {btype} ---")
            lines.extend(chunk)
            lines.append("")
    return lines



def _r_kop(b: dict[str, Any]) -> list[str]:
    segs: list[str] = []
    for i, line in enumerate(b.get("lines") or []):
        if i:
            segs.append('"\\n"')
        segs.append(f"BOLD({dsx_str(str(line))})")
    if str(b.get("alamat") or "").strip():
        segs.append('"\\n"')
        segs.append(f"ITALIC({dsx_str(str(b['alamat']))})")
    if str(b.get("kontak") or "").strip():
        segs.append('"\\n"')
        segs.append(f"ITALIC({dsx_str(str(b['kontak']))})")
    seg_join = ",\n      ".join(segs) if segs else dsx_str("")
    garis = str(b.get("garis") or "bottom").lower()
    tebal = float(b.get("garis_tebal_pt") or 1.5)
    warna = str(b.get("garis_warna") or "000000").lstrip("#")
    logo_l = (str(b.get("logo") or "").strip() or None)
    logo_r = (str(b.get("logo_kanan") or "").strip() or None)
    mode = str(b.get("logo_mode") or "auto").lower()
    lebar = float(b.get("logo_lebar_cm") or 2.2)
    if mode == "one":
        logo_r = None
    use_two = bool(logo_l and logo_r) and mode != "one"

    out: list[str] = []
    if use_two:
        cell_text = f'CELL([{seg_join}], align="center")'
        cell_l = f'CELL([IMAGE({dsx_str(logo_l)})], align="center")'
        cell_r = f'CELL([IMAGE({dsx_str(logo_r)})], align="center")'
        if garis == "bottom":
            border_line = f'  border="bottom", border_width={tebal}, border_color={dsx_str(warna)},'
        else:
            border_line = '  border="none",'
        out += [
            "TABLE(",
            border_line,
            "  cell_padding=0.08cm,",
            f'  widths=["{lebar + 0.4}cm", "*", "{lebar + 0.4}cm"],',
            f"  rows=[[{cell_l}, {cell_text}, {cell_r}]]",
            ")",
        ]
        if garis == "hr":
            out.append(
                f'HR(style="solid", thickness={tebal}, color={dsx_str(warna)}, space_before=2, space_after=6)'
            )
    else:
        if logo_l:
            out.append(f'FIGURE(src={dsx_str(logo_l)}, width={lebar}cm, align="center")')
        if garis == "bottom":
            out += [
                "TABLE(",
                '  border="bottom",',
                f"  border_width={tebal},",
                f"  border_color={dsx_str(warna)},",
                "  cell_padding=0.08cm,",
                '  widths=["*"],',
                f'  rows=[[CELL([{seg_join}], align="center")]]',
                ")",
            ]
        elif garis == "hr":
            out += [
                "TABLE(",
                '  border="none", cell_padding=0.08cm, widths=["*"],',
                f'  rows=[[CELL([{seg_join}], align="center")]]',
                ")",
                f'HR(style="solid", thickness={tebal}, color={dsx_str(warna)}, space_before=2, space_after=6)',
            ]
        else:
            out += [
                "TABLE(",
                '  border="none", cell_padding=0.08cm, widths=["*"],',
                f'  rows=[[CELL([{seg_join}], align="center")]]',
                ")",
            ]
    return out



def _r_identitas(b: dict[str, Any]) -> list[str]:
    perihal = str(b.get("perihal") or "")
    perihal_cell = (
        f'CELL([BOLD({dsx_str(perihal)})], align="left")'
        if b.get("perihal_bold", True)
        else f'CELL({dsx_str(perihal)}, align="left")'
    )
    return [
        "TABLE(",
        '  border="none", cell_padding=0.05cm, widths=["2.8cm", "0.4cm", "*"],',
        "  rows=[",
        f'    [CELL("Nomor"), CELL(":"), CELL({dsx_str(b.get("nomor") or "")})],',
        f'    [CELL("Lampiran"), CELL(":"), CELL({dsx_str(b.get("lampiran") or "-")})],',
        f"    [CELL(\"Perihal\"), CELL(\":\"), {perihal_cell}]",
        "  ]",
        ")",
        f'P({dsx_str(b.get("kota_tanggal") or "")}, space_after=10)',
    ]


def _r_penerima(b: dict[str, Any]) -> list[str]:
    lines = [f'P({dsx_str("Yth. " + str(b.get("yth") or ""))}, space_after=0)']
    for extra in b.get("baris_tambahan") or []:
        lines.append(f'P({dsx_str(str(extra))}, space_after=0)')
    lines += [
        'P("di", space_after=0)',
        f'P({dsx_str(b.get("di") or "Tempat")}, space_after=10)',
    ]
    return lines


def _r_heading(b: dict[str, Any]) -> list[str]:
    level = max(1, min(9, int(b.get("level") or 1)))
    return [f'H{level}({dsx_str(str(b.get("text") or ""))})']


def _r_title(b: dict[str, Any]) -> list[str]:
    out = [f'TEXT({dsx_str(str(b.get("text") or ""))}, role="title")']
    if b.get("subtitle"):
        out.append(f'TEXT({dsx_str(str(b["subtitle"]))}, role="subtitle")')
    return out


def _r_paragraph(b: dict[str, Any]) -> list[str]:
    indent = float(b.get("first_line_indent_cm") or 0)
    align = str(b.get("align") or "justify")
    sa = int(b.get("space_after") or 6)
    args = [dsx_str(str(b.get("text") or ""))]
    if indent:
        args.append(f"first_line_indent={indent}cm")
    if align:
        args.append(f'align={dsx_str(align)}')
    args.append(f"space_after={sa}")
    return [f'P({", ".join(args)})']


def _r_paragraphs(b: dict[str, Any]) -> list[str]:
    indent = float(b.get("first_line_indent_cm") or 1.0)
    out = []
    for item in b.get("items") or []:
        out.append(
            f'P({dsx_str(str(item))}, first_line_indent={indent}cm, align="justify", space_after=6)'
        )
    return out


def _r_text_line(b: dict[str, Any]) -> list[str]:
    text = str(b.get("text") or "")
    align = str(b.get("align") or "left")
    sa = int(b.get("space_after") or 0)
    if b.get("bold"):
        return [f'P([BOLD({dsx_str(text)})], align={dsx_str(align)}, space_after={sa})']
    return [f'P({dsx_str(text)}, align={dsx_str(align)}, space_after={sa})']


def _r_kv_table(b: dict[str, Any]) -> list[str]:
    numbered = bool(b.get("numbered", True))
    lw = float(b.get("label_width_cm") or 4.2)
    rows_src = []
    for i, item in enumerate(b.get("rows") or [], start=1):
        label = str((item or {}).get("label") or "")
        nilai = str((item or {}).get("nilai") or "")
        if numbered:
            rows_src.append(
                f'    [CELL("{i}."), CELL({dsx_str(label)}), CELL(":"), CELL({dsx_str(nilai)})]'
            )
        else:
            rows_src.append(
                f'    [CELL({dsx_str(label)}), CELL(":"), CELL({dsx_str(nilai)})]'
            )
    if not rows_src:
        return []
    if numbered:
        widths = f'["0.6cm", "{lw}cm", "0.4cm", "*"]'
    else:
        widths = f'["{lw}cm", "0.4cm", "*"]'
    return [
        "TABLE(",
        '  border="none", cell_padding=0.06cm,',
        f"  widths={widths},",
        "  rows=[",
        ",\n".join(rows_src),
        "  ]",
        ")",
    ]


def _r_table(b: dict[str, Any]) -> list[str]:
    headers = b.get("headers") or []
    h = ", ".join(dsx_str(str(x)) for x in headers)
    row_parts = []
    for row in b.get("rows") or []:
        cells = ", ".join(dsx_str(str(c)) for c in row)
        row_parts.append(f"[{cells}]")
    border = str(b.get("border") or "grid")
    shading = b.get("header_shading")
    lines = [
        "TABLE(",
        f"  headers=[{h}],",
        f"  rows=[{', '.join(row_parts)}],",
        f'  border={dsx_str(border)},',
        "  border_width=0.5,",
    ]
    if shading:
        lines.append(f'  header_shading={dsx_str(str(shading))},')
    if b.get("caption"):
        lines.append(f'  caption={dsx_str(str(b["caption"]))},')
    lines.append(")")
    return lines


def _r_csv_table(b: dict[str, Any]) -> list[str]:
    lines = [
        "TABLE(",
        f'  data=CSV({dsx_str(str(b.get("path") or "data/file.csv"))}),',
        "  header=true,",
        f'  border={dsx_str(str(b.get("border") or "grid"))},',
    ]
    if b.get("caption"):
        lines.append(f'  caption={dsx_str(str(b["caption"]))},')
    lines.append(")")
    return lines


def _r_list(b: dict[str, Any]) -> list[str]:
    items = b.get("items") or []
    inner = ", ".join(dsx_str(str(x)) for x in items)
    if b.get("ordered"):
        return [f"LIST([{inner}], ordered=true)"]
    return [f"BULLET([{inner}])"]


def _r_hr(b: dict[str, Any]) -> list[str]:
    return [
        "HR("
        f'style={dsx_str(str(b.get("style") or "solid"))}, '
        f'thickness={float(b.get("thickness") or 1.0)}, '
        f'color={dsx_str(str(b.get("color") or "000000"))}, '
        f'space_before={int(b.get("space_before") or 4)}, '
        f'space_after={int(b.get("space_after") or 8)}'
        ")"
    ]


def _r_spacer(b: dict[str, Any]) -> list[str]:
    return [f'P("", space_after={int(b.get("space_after") or 12)})']


def _r_pagebreak(_b: dict[str, Any]) -> list[str]:
    return ["PAGEBREAK()"]


def _r_figure(b: dict[str, Any]) -> list[str]:
    args = [
        f'src={dsx_str(str(b.get("src") or ""))}',
        f'width={float(b.get("width_cm") or 10)}cm',
        f'align={dsx_str(str(b.get("align") or "center"))}',
    ]
    if b.get("caption"):
        args.append(f'caption={dsx_str(str(b["caption"]))}')
    return [f'FIGURE({", ".join(args)})']


def _r_callout(b: dict[str, Any]) -> list[str]:
    args = [
        dsx_str(str(b.get("text") or "")),
        f'type={dsx_str(str(b.get("callout_type") or "info"))}',
    ]
    if b.get("title"):
        args.append(f'title={dsx_str(str(b["title"]))}')
    return [f'CALLOUT({", ".join(args)})']


def _r_signature(b: dict[str, Any]) -> list[str]:
    cols = b.get("columns") or []
    if not cols:
        return []
    n = len(cols)
    widths = ", ".join(['"*"'] * n)
    jab = ", ".join(f'CELL({dsx_str(str(c.get("jabatan") or ""))}, align="center")' for c in cols)
    spasi = ", ".join(['CELL("\\n\\n\\n\\n", align="center")'] * n)
    nama = ", ".join(
        f'CELL([BOLD({dsx_str(str(c.get("nama") or ""))})], align="center")' for c in cols
    )
    return [
        "TABLE(",
        '  border="none", cell_padding=0.05cm,',
        f"  widths=[{widths}],",
        "  rows=[",
        f"    [{jab}],",
        f"    [{spasi}],",
        f"    [{nama}]",
        "  ]",
        ")",
    ]


def _r_mengetahui(b: dict[str, Any]) -> list[str]:
    return [
        f'P({dsx_str(str(b.get("label") or "Mengetahui,"))}, space_after=0)',
        'P("\\n\\n\\n", space_after=0)',
        f'P([BOLD({dsx_str(str(b.get("nama") or ""))})], space_after=0)',
        f'P({dsx_str(str(b.get("nip") or ""))}, space_after=0)',
    ]


def _r_toc(b: dict[str, Any]) -> list[str]:
    return [
        f'TOC(title={dsx_str(str(b.get("title") or "Daftar Isi"))}, depth={int(b.get("depth") or 3)})'
    ]


_RENDERERS = {
    "kop": _r_kop,
    "identitas_surat": _r_identitas,
    "penerima": _r_penerima,
    "heading": _r_heading,
    "title": _r_title,
    "paragraph": _r_paragraph,
    "paragraphs": _r_paragraphs,
    "text_line": _r_text_line,
    "kv_table": _r_kv_table,
    "table": _r_table,
    "csv_table": _r_csv_table,
    "list": _r_list,
    "hr": _r_hr,
    "spacer": _r_spacer,
    "pagebreak": _r_pagebreak,
    "figure": _r_figure,
    "callout": _r_callout,
    "signature": _r_signature,
    "mengetahui": _r_mengetahui,
    "toc": _r_toc,
}
