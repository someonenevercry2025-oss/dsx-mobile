"""Konversi best-effort sumber DSX → form custom (blocks).

Ditingkatkan (v1.9.1):
- deteksi penerima (Yth./di)
- deteksi mengetahui
- text_line vs paragraph vs spacer lebih akurat
- gabung paragraf berurutan → paragraphs
- identitas + kota_tanggal
- signature / kv_table / kop lebih stabil
"""

from __future__ import annotations

import re
from typing import Any

from .blocks import default_custom_form, new_block


def dsx_to_form(source: str) -> dict[str, Any]:
    form = default_custom_form()
    form["blocks"] = []
    form["_converted_from"] = "dsx"
    text = source or ""

    _parse_meta(text, form)
    _parse_page(text, form)

    raw_blocks: list[dict[str, Any]] = []
    for name, body in _iter_calls(text):
        block = _call_to_block(name, body)
        if block:
            raw_blocks.append(block)

    form["blocks"] = _post_process(raw_blocks)
    if not form["blocks"]:
        form["blocks"] = [new_block("paragraph", text="(tidak ada blok yang dikenali)")]
    return form


def _unesc(s: str) -> str:
    return (
        (s or "")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace('\\"', '"')
        .replace("\\\\", "\\")
    )


def _parse_meta(text: str, form: dict[str, Any]) -> None:
    m = re.search(r'DOC\s*\(\s*title\s*=\s*"((?:\\.|[^"\\])*)"', text)
    if m:
        form.setdefault("meta", {})["title"] = _unesc(m.group(1))
    m = re.search(r'DOC\s*\([^)]*author\s*=\s*"((?:\\.|[^"\\])*)"', text, re.S)
    if m:
        form.setdefault("meta", {})["author"] = _unesc(m.group(1))


def _parse_page(text: str, form: dict[str, Any]) -> None:
    page: dict[str, Any] = form.setdefault("page", {})
    m = re.search(r"PAGE\s*\(([^)]*)\)", text, re.S)
    if not m:
        return
    args = m.group(1)
    sm = re.search(r'size\s*=\s*"([^"]+)"', args)
    if sm:
        page["size"] = sm.group(1)
    for key, dest in (
        ("margin_top", "margin_top_cm"),
        ("margin_bottom", "margin_bottom_cm"),
        ("margin_left", "margin_left_cm"),
        ("margin_right", "margin_right_cm"),
    ):
        mm = re.search(rf"{key}\s*=\s*([0-9.]+)\s*cm", args)
        if mm:
            page[dest] = float(mm.group(1))
    mm = re.search(r"margin\s*=\s*([0-9.]+)\s*cm", args)
    if mm and "margin_top_cm" not in page:
        v = float(mm.group(1))
        page.update(
            margin_top_cm=v,
            margin_bottom_cm=v,
            margin_left_cm=v,
            margin_right_cm=v,
        )


_SKIP_CALLS = {
    "BOLD", "ITALIC", "UNDERLINE", "HIGHLIGHT", "LINK", "FOOTNOTE",
    "CELL", "CSV", "FILE", "IMAGE", "IMATH", "REF", "CITE", "LABEL",
}


def _iter_calls(text: str) -> list[tuple[str, str]]:
    cleaned = re.sub(r"#[^\n]*", "", text)
    results: list[tuple[str, str]] = []
    i = 0
    n = len(cleaned)
    while i < n:
        m = re.match(r"\s*", cleaned[i:])
        if m:
            i += m.end()
        if i >= n:
            break
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(", cleaned[i:])
        if not m:
            i += 1
            continue
        name = m.group(1)
        start_body = i + m.end()
        depth = 1
        j = start_body
        in_str = False
        quote = ""
        escape = False
        while j < n and depth:
            ch = cleaned[j]
            if in_str:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == quote:
                    in_str = False
            else:
                if ch in "\"'":
                    in_str = True
                    quote = ch
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
            j += 1
        body = cleaned[start_body : j - 1]
        if name.upper() not in _SKIP_CALLS:
            results.append((name, body))
        i = j
    return results


def _str_arg(body: str, name: str | None = None, positional: bool = False) -> str | None:
    if name:
        m = re.search(rf'{re.escape(name)}\s*=\s*"((?:\\.|[^"\\])*)"', body)
        if m:
            return _unesc(m.group(1))
    if positional:
        m = re.match(r'\s*"((?:\\.|[^"\\])*)"', body)
        if m:
            return _unesc(m.group(1))
        m = re.search(r'BOLD\s*\(\s*"((?:\\.|[^"\\])*)"', body)
        if m and body.lstrip().startswith("["):
            return _unesc(m.group(1))
    return None


def _num_arg(body: str, name: str, default: float | None = None) -> float | None:
    m = re.search(rf"{re.escape(name)}\s*=\s*([0-9.]+)", body)
    if m:
        return float(m.group(1))
    return default


def _bool_arg(body: str, name: str) -> bool | None:
    m = re.search(rf"{re.escape(name)}\s*=\s*(true|false)", body, re.I)
    if m:
        return m.group(1).lower() == "true"
    return None


def _call_to_block(name: str, body: str) -> dict[str, Any] | None:
    n = name.upper()

    if n in {f"H{i}" for i in range(1, 10)}:
        return new_block(
            "heading",
            level=int(n[1]),
            text=_str_arg(body, positional=True) or "",
        )

    if n == "P":
        return _p_to_block(body)

    if n == "TEXT":
        text = _str_arg(body, "text") or _str_arg(body, positional=True) or ""
        role = _str_arg(body, "role") or ""
        if role == "title":
            return new_block("title", text=text, subtitle="")
        if role == "subtitle":
            return new_block("title", text="", subtitle=text)
        return new_block("text_line", text=text)

    if n == "HR":
        return new_block(
            "hr",
            style=_str_arg(body, "style") or "solid",
            thickness=_num_arg(body, "thickness", 1.0) or 1.0,
            color=(_str_arg(body, "color") or "000000").lstrip("#"),
            space_before=int(_num_arg(body, "space_before", 4) or 4),
            space_after=int(_num_arg(body, "space_after", 8) or 8),
        )

    if n == "PAGEBREAK":
        return new_block("pagebreak")

    if n == "TOC":
        return new_block(
            "toc",
            title=_str_arg(body, "title") or "Daftar Isi",
            depth=int(_num_arg(body, "depth", 3) or 3),
        )

    if n == "FIGURE":
        return new_block(
            "figure",
            src=_str_arg(body, "src") or "",
            width_cm=_num_arg(body, "width", 10) or 10,
            caption=_str_arg(body, "caption") or "",
            align=_str_arg(body, "align") or "center",
        )

    if n == "CALLOUT":
        return new_block(
            "callout",
            text=_str_arg(body, "text") or _str_arg(body, positional=True) or "",
            title=_str_arg(body, "title") or "",
            callout_type=_str_arg(body, "type") or "info",
        )

    if n in ("BULLET", "LIST"):
        items = [_unesc(x) for x in re.findall(r'"((?:\\.|[^"\\])*)"', body)]
        ordered = n == "LIST" and (
            _bool_arg(body, "ordered") is True
            or "ordered=true" in body.replace(" ", "").lower()
        )
        return new_block("list", ordered=ordered, items=items)

    if n == "TABLE":
        return _table_to_block(body)

    if n in ("DSX", "DOC", "PAGE", "STYLEDEF", "STYLE", "HEADER", "FOOTER", "PAGENUM", "LET"):
        return None
    return None


def _p_to_block(body: str) -> dict[str, Any]:
    sa = int(_num_arg(body, "space_after", 6) or 6)
    indent = _num_arg(body, "first_line_indent", 0) or 0
    align = _str_arg(body, "align") or "left"

    if body.lstrip().startswith("["):
        bm = re.search(r'BOLD\s*\(\s*"((?:\\.|[^"\\])*)"', body)
        if bm:
            return new_block(
                "text_line",
                text=_unesc(bm.group(1)),
                bold=True,
                align=align,
                space_after=sa,
            )

    text = _str_arg(body, "text")
    if text is None:
        text = _str_arg(body, positional=True)
    if text is None:
        text = ""

    if not str(text).strip():
        return new_block("spacer", space_after=max(sa, 6))

    if indent == 0 and "\n" not in text and len(text) < 80 and align in ("left", "center"):
        return new_block(
            "text_line",
            text=text,
            bold=False,
            align=align,
            space_after=sa,
        )

    return new_block(
        "paragraph",
        text=text,
        first_line_indent_cm=indent if indent else 1.0,
        align=align if align != "left" else "justify",
        space_after=sa,
    )


def _table_to_block(body: str) -> dict[str, Any] | None:
    border = _str_arg(body, "border") or "grid"
    bolds = [_unesc(x) for x in re.findall(r'BOLD\s*\(\s*"((?:\\.|[^"\\])*)"', body)]
    italics = [_unesc(x) for x in re.findall(r'ITALIC\s*\(\s*"((?:\\.|[^"\\])*)"', body)]
    widths_star = bool(re.search(r'widths\s*=\s*\[\s*"\*"\s*\]', body))

    if border == "bottom" or (border == "none" and bolds and widths_star):
        return new_block(
            "kop",
            lines=bolds or ["LEMBAGA"],
            alamat=italics[0] if italics else "",
            kontak=italics[1] if len(italics) > 1 else "",
            garis="bottom" if border == "bottom" else "none",
            garis_tebal_pt=_num_arg(body, "border_width", 1.5) or 1.5,
            garis_warna=(_str_arg(body, "border_color") or "000000").lstrip("#"),
        )

    strings = [_unesc(x) for x in re.findall(r'"((?:\\.|[^"\\])*)"', body)]

    if any(s == "Nomor" for s in strings) and any(s == "Perihal" for s in strings):
        nomor, lampiran, perihal = "", "-", ""
        perihal_bold = bool(bolds)
        if bolds:
            perihal = bolds[0]
        for i, s in enumerate(strings):
            if s == "Nomor" and i + 1 < len(strings):
                j = i + 1
                if strings[j] == ":" and j + 1 < len(strings):
                    nomor = strings[j + 1]
                else:
                    nomor = strings[j]
            if s == "Lampiran" and i + 1 < len(strings):
                j = i + 1
                if strings[j] == ":" and j + 1 < len(strings):
                    lampiran = strings[j + 1]
                else:
                    lampiran = strings[j]
            if s == "Perihal" and not perihal and i + 1 < len(strings):
                j = i + 1
                if strings[j] == ":" and j + 1 < len(strings):
                    perihal = strings[j + 1]
                else:
                    perihal = strings[j]
        return new_block(
            "identitas_surat",
            nomor=nomor,
            lampiran=lampiran,
            perihal=perihal,
            perihal_bold=perihal_bold,
            kota_tanggal="",
        )

    center_count = len(re.findall(r'align\s*=\s*"center"', body))
    if border == "none" and center_count >= 2 and (
        "\\n\\n\\n" in body or center_count >= 4
    ):
        jabs = re.findall(
            r'CELL\s*\(\s*"((?:\\.|[^"\\])*)"\s*,\s*align\s*=\s*"center"',
            body,
        )
        names = bolds
        cols = []
        name_i = 0
        for jab in jabs:
            jab_clean = _unesc(jab).replace("\n", "").strip()
            if not jab_clean:
                continue
            nama = names[name_i] if name_i < len(names) else ""
            name_i += 1
            cols.append({"jabatan": jab_clean, "nama": nama})
        if cols:
            return new_block("signature", columns=cols)

    if border == "none" and re.search(r'CELL\s*\(\s*"\d+\."', body):
        parts = [_unesc(p) for p in re.findall(r'CELL\s*\(\s*"((?:\\.|[^"\\])*)"', body)]
        vals = [p for p in parts if not re.match(r"^\d+\.$", p) and p != ":"]
        rows = []
        for i in range(0, len(vals) - 1, 2):
            rows.append({"label": vals[i], "nilai": vals[i + 1]})
        if rows:
            return new_block("kv_table", rows=rows, numbered=True)

    if border == "none" and ":" in strings and not re.search(r"headers\s*=", body):
        rows = []
        for i, s in enumerate(strings):
            if s == ":" and i > 0 and i + 1 < len(strings):
                rows.append({"label": strings[i - 1], "nilai": strings[i + 1]})
        if rows and not any(s == "Nomor" for s in strings):
            return new_block("kv_table", rows=rows, numbered=False)

    cm = re.search(r'CSV\s*\(\s*"((?:\\.|[^"\\])*)"', body)
    if cm:
        return new_block(
            "csv_table",
            path=_unesc(cm.group(1)),
            caption=_str_arg(body, "caption") or "",
            border=border,
        )

    hm = re.search(r"headers\s*=\s*\[(.*?)\]", body, re.S)
    if hm:
        headers = [_unesc(x) for x in re.findall(r'"((?:\\.|[^"\\])*)"', hm.group(1))]
        rows: list[list[str]] = []
        rm = re.search(r"rows\s*=\s*\[(.*)\]", body, re.S)
        if rm:
            for row_m in re.finditer(r"\[([^\[\]]*)\]", rm.group(1)):
                cells = [_unesc(x) for x in re.findall(r'"((?:\\.|[^"\\])*)"', row_m.group(1))]
                if cells:
                    rows.append(cells)
        return new_block(
            "table",
            headers=headers,
            rows=rows or [[""] * max(1, len(headers))],
            border=border,
            caption=_str_arg(body, "caption") or "",
        )

    return None


def _post_process(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    blocks = _merge_title_subtitle(blocks)
    blocks = _detect_penerima(blocks)
    blocks = _attach_kota_tanggal(blocks)
    blocks = _detect_mengetahui(blocks)
    blocks = _merge_paragraphs(blocks)
    blocks = _collapse_spacers(blocks)
    return blocks


def _block_text(b: dict[str, Any]) -> str:
    if not b:
        return ""
    if b.get("type") == "paragraphs":
        items = b.get("items") or []
        return str(items[0]) if items else ""
    return str(b.get("text") or "")


def _merge_title_subtitle(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        if (
            b.get("type") == "title"
            and i + 1 < len(blocks)
            and blocks[i + 1].get("type") == "title"
            and not b.get("subtitle")
            and not blocks[i + 1].get("text")
            and blocks[i + 1].get("subtitle")
        ):
            b = dict(b)
            b["subtitle"] = blocks[i + 1]["subtitle"]
            out.append(b)
            i += 2
            continue
        if b.get("type") == "title" and not b.get("text") and b.get("subtitle"):
            if out and out[-1].get("type") == "title" and not out[-1].get("subtitle"):
                out[-1] = dict(out[-1])
                out[-1]["subtitle"] = b["subtitle"]
                i += 1
                continue
        out.append(b)
        i += 1
    return out


def _detect_penerima(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        text = _block_text(b)
        if re.match(r"(?i)^yth\.?\s*", text):
            yth = re.sub(r"(?i)^yth\.?\s*", "", text).strip()
            baris: list[str] = []
            di_val = "Tempat"
            j = i + 1
            while j < len(blocks):
                t2 = _block_text(blocks[j])
                if not t2.strip():
                    j += 1
                    continue
                if t2.strip().lower() == "di":
                    if j + 1 < len(blocks) and _block_text(blocks[j + 1]).strip():
                        di_val = _block_text(blocks[j + 1]).strip()
                        j += 2
                    else:
                        j += 1
                    break
                if blocks[j].get("type") in ("text_line", "paragraph") and len(t2) < 80:
                    baris.append(t2)
                    j += 1
                    continue
                break
            out.append(new_block("penerima", yth=yth, baris_tambahan=baris, di=di_val))
            i = j
            continue
        out.append(b)
        i += 1
    return out


def _attach_kota_tanggal(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for b in blocks:
        if (
            b.get("type") in ("text_line", "paragraph")
            and out
            and out[-1].get("type") == "identitas_surat"
            and not out[-1].get("kota_tanggal")
        ):
            t = _block_text(b)
            if t and ("," in t) and re.search(
                r"\d{4}|Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember",
                t,
                re.I,
            ):
                prev = dict(out[-1])
                prev["kota_tanggal"] = t
                out[-1] = prev
                continue
        out.append(b)
    return out


def _detect_mengetahui(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        t = _block_text(b)
        if re.match(r"(?i)^(mengetahui|dosen\s+pendamping)\b", t.strip()):
            label = t.strip() or "Mengetahui,"
            nama = ""
            nip = ""
            j = i + 1
            while j < len(blocks) and blocks[j].get("type") == "spacer":
                j += 1
            if j < len(blocks) and blocks[j].get("type") in ("text_line", "paragraph"):
                nama = _block_text(blocks[j])
                j += 1
            if j < len(blocks) and blocks[j].get("type") in ("text_line", "paragraph"):
                cand = _block_text(blocks[j])
                if re.search(r"(?i)nip|nidn|\d{5,}", cand) or len(cand) < 40:
                    nip = cand
                    j += 1
            out.append(new_block("mengetahui", label=label, nama=nama, nip=nip))
            i = j
            continue
        out.append(b)
        i += 1
    return out


def _merge_paragraphs(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    buf: list[str] = []
    indent = 1.0

    def flush() -> None:
        nonlocal buf, indent
        if not buf:
            return
        if len(buf) == 1:
            out.append(
                new_block(
                    "paragraph",
                    text=buf[0],
                    first_line_indent_cm=indent,
                    align="justify",
                    space_after=6,
                )
            )
        else:
            out.append(new_block("paragraphs", items=list(buf), first_line_indent_cm=indent))
        buf = []

    for b in blocks:
        if b.get("type") == "paragraph" and (b.get("text") or "").strip():
            indent = float(b.get("first_line_indent_cm") or 1.0)
            buf.append(str(b.get("text") or ""))
        else:
            flush()
            out.append(b)
    flush()
    return out


def _collapse_spacers(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for b in blocks:
        if b.get("type") == "spacer":
            if out and out[-1].get("type") == "spacer":
                if int(b.get("space_after") or 0) > int(out[-1].get("space_after") or 0):
                    out[-1] = b
                continue
            out.append(b)
            continue
        out.append(b)
    while out and out[0].get("type") == "spacer":
        out.pop(0)
    while out and out[-1].get("type") == "spacer":
        out.pop()
    return out
