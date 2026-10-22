"""Renderer DOCX berbasis python-docx.

Catatan pemetaan:
- Style DSX dipetakan ke style paragraf Word. Style bawaan (Normal, Title,
  Subtitle, Heading 1-9, Quote, Caption) dimodifikasi; style lain dibuat baru.
- Properti lama pada style bawaan dibersihkan lebih dulu agar hasil sama persis
  dengan style hasil resolusi (mis. border Title, atribut tema font).
- Heading mendapat identitas struktural: style Heading N atau style custom yang
  berbasis Heading N, ditambah outline level pada paragraf.
"""

from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime
from typing import Any

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Cm, Pt, RGBColor, Twips

from ..ir.nodes import (
    Callout, DocumentIR, Figure, HeaderFooter, ListBlock, MathBlock, MathSeg,
    PageNumber, Paragraph, Table, TableCell, TextBlock, TextSeg, ImageSeg, LinkSeg,
    FootnoteSeg, TocBlock, CodeBlock, ChartBlock, LabelMarker,
    BibliographyBlock, ColumnsStart, ColumnsEnd, SectionBreak, RefSeg, CiteSeg,
    HorizontalRule, FormLine, ShapeBlock, ListOfTablesBlock, ListOfFiguresBlock, CommentSeg,
)
from . import _v12_helpers as _v12
from ..limits import Deadline
from ..styles.defaults import CALLOUT_THEMES
from ..styles.registry import ResolvedStyle
from .base import Renderer
from .omml import build_inline_math, build_math_para

_FIXED_TIMESTAMP = datetime(2000, 1, 1, 0, 0, 0)
_ALIGN = {
    "left": WD_ALIGN_PARAGRAPH.LEFT,
    "center": WD_ALIGN_PARAGRAPH.CENTER,
    "right": WD_ALIGN_PARAGRAPH.RIGHT,
    "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
}
_TABLE_ALIGN = {
    "left": WD_TABLE_ALIGNMENT.LEFT,
    "center": WD_TABLE_ALIGNMENT.CENTER,
    "right": WD_TABLE_ALIGNMENT.RIGHT,
}
_BUILTIN_NAMES = {
    "normal": "Normal",
    "title": "Title",
    "subtitle": "Subtitle",
    "quote": "Quote",
    "caption": "Caption",
}
for _n in range(1, 10):
    _BUILTIN_NAMES[f"heading-{_n}"] = f"Heading {_n}"
_NUMERIC = re.compile(r"^[+-]?\d+([.,]\d+)?$")
_FIELD_SPLIT = re.compile(r"(\{pages?\})")
# Teks sel tabel satu spasi (tidak mewarisi jarak baris isi dokumen, mis. 1.5).
TABLE_LINE_SPACING = 1.0
# Tabel dengan baris (termasuk header) <= nilai ini tidak dipecah antarhalaman.
TABLE_KEEP_TOGETHER_MAX_ROWS = 8

_FONT_KEYS = ("font", "size", "bold", "italic", "underline", "color")


class DocxRenderError(RuntimeError):
    pass



def _fill_segments(par: Any, segments: tuple, plain: str, math_size: float | None = None) -> list[Any]:
    """Isi paragraf dengan segmen kaya atau teks polos; kembalikan daftar run."""
    runs: list[Any] = []
    if segments:
        for seg in segments:
            if isinstance(seg, TextSeg):
                run = par.add_run(seg.text)
                if seg.bold:
                    run.bold = True
                if seg.italic:
                    run.italic = True
                if seg.underline:
                    run.underline = True
                if getattr(seg, "highlight", None):
                    _v12.apply_highlight(run, seg.highlight)
                runs.append(run)
            elif isinstance(seg, ImageSeg):
                run = par.add_run()
                try:
                    w = float(getattr(seg, "width_cm", None) or 2.2)
                    h = getattr(seg, "height_cm", None)
                    if h is not None:
                        run.add_picture(io.BytesIO(seg.data), width=Cm(w), height=Cm(float(h)))
                    else:
                        run.add_picture(io.BytesIO(seg.data), width=Cm(w))
                except Exception:
                    run.add_text("[gambar]")
                runs.append(run)
            elif isinstance(seg, CommentSeg):
                _v12.add_comment_markers(par, seg)
                runs.append(par.add_run(""))
            elif isinstance(seg, LinkSeg):
                run = _add_hyperlink(par, seg.text, seg.url)
                if seg.bold:
                    run.bold = True
                if seg.italic:
                    run.italic = True
                run.underline = True
                runs.append(run)
            elif isinstance(seg, FootnoteSeg):
                runs.append(_add_footnote_ref(par, seg.note_id))
            elif isinstance(seg, MathSeg):
                par._p.append(parse_xml(etree_tostring(build_inline_math(seg.tree, math_size))))
            elif isinstance(seg, (RefSeg, CiteSeg)):
                runs.append(par.add_run(seg.display))
            else:
                # fallback
                runs.append(par.add_run(getattr(seg, "text", getattr(seg, "display", ""))))
    elif plain:
        runs.append(par.add_run(plain))
    return runs

class DocxRenderer(Renderer):
    format = "docx"

    def render(self, ir: DocumentIR, deadline: Deadline | None = None) -> bytes:
        self._deadline = deadline
        doc = Document()
        body = doc._element.body
        for child in list(body):
            if child.tag != qn("w:sectPr"):
                body.remove(child)
        self._style_map: dict[str, Any] = {}
        self._numbering = _Numbering(doc)
        self._set_properties(doc, ir)
        self._setup_page(doc, ir)
        self._materialize_styles(doc, ir)
        self._set_language(doc, ir)
        self._section_plan: list[Any] = []  # SectionBreak configs in order
        for block in ir.blocks:
            if self._deadline is not None:
                self._deadline.check()
            if isinstance(block, Paragraph):
                self._paragraph(doc, block)
            elif isinstance(block, TextBlock):
                for p in block.paragraphs:
                    self._paragraph(doc, p)
            elif isinstance(block, Figure):
                self._figure(doc, block)
            elif isinstance(block, HorizontalRule):
                self._hr(doc, block)
            elif isinstance(block, FormLine):
                self._form_line(doc, block)
            elif isinstance(block, Table):
                self._table(doc, block, ir)
            elif isinstance(block, ListBlock):
                self._list(doc, block)
            elif isinstance(block, Callout):
                self._callout(doc, block, ir)
            elif isinstance(block, MathBlock):
                self._math(doc, block)
            elif isinstance(block, TocBlock):
                self._toc(doc, block, ir)
            elif isinstance(block, ListOfTablesBlock):
                _v12.list_of_block(self, doc, block, "Table")
            elif isinstance(block, ListOfFiguresBlock):
                _v12.list_of_block(self, doc, block, "Figure")
            elif isinstance(block, ShapeBlock):
                _v12.shape_block(self, doc, block)
            elif isinstance(block, CodeBlock):
                self._code(doc, block)
            elif isinstance(block, ChartBlock):
                self._chart(doc, block)
            elif isinstance(block, LabelMarker):
                pass  # label only registers; no visual
            elif isinstance(block, BibliographyBlock):
                self._bibliography(doc, block, ir)
            elif isinstance(block, (ColumnsStart, ColumnsEnd)):
                self._columns_marker(doc, block)
            elif isinstance(block, SectionBreak):
                self._section_break(doc, block, ir)
        if not ir.blocks:
            doc.add_paragraph(style=self._style_map["normal"])
        self._apply_multi_section_headers_footers(doc, ir)
        self._footnotes(doc, ir)
        buffer = io.BytesIO()
        doc.save(buffer)
        data = _normalize_zip(buffer.getvalue())
        if ir.footnotes:
            data = _inject_native_footnotes(data, ir.footnotes)
            data = _normalize_zip(data)
        if getattr(ir, "comments", None):
            data = _v12.inject_native_comments(data, ir.comments)
            data = _normalize_zip(data)
        return data

    # ------------------------------------------------------------- document
    @staticmethod
    def _set_properties(doc: Any, ir: DocumentIR) -> None:
        props = doc.core_properties
        props.title = ir.metadata.title
        props.author = ir.metadata.author
        props.subject = ir.metadata.subject
        props.last_modified_by = ""
        props.comments = ""
        props.keywords = ""
        props.category = ""
        props.revision = 1
        props.created = _FIXED_TIMESTAMP
        props.modified = _FIXED_TIMESTAMP

    @staticmethod
    def _setup_page(doc: Any, ir: DocumentIR) -> None:
        page = ir.page
        section = doc.sections[0]
        section.orientation = WD_ORIENT.LANDSCAPE if page.orientation == "landscape" else WD_ORIENT.PORTRAIT
        section.page_width = Cm(page.width_cm)
        section.page_height = Cm(page.height_cm)
        section.top_margin = Cm(page.margin_top)
        section.bottom_margin = Cm(page.margin_bottom)
        section.left_margin = Cm(page.margin_left)
        section.right_margin = Cm(page.margin_right)
        section.header_distance = Cm(min(1.25, page.margin_top / 2))
        section.footer_distance = Cm(min(1.25, page.margin_bottom / 2))
        section.gutter = Cm(0)

    @staticmethod
    def _set_language(doc: Any, ir: DocumentIR) -> None:
        defaults = doc.styles.element.find(qn("w:docDefaults"))
        if defaults is None:
            return
        rpr_default = defaults.find(qn("w:rPrDefault"))
        rpr = rpr_default.find(qn("w:rPr")) if rpr_default is not None else None
        if rpr is None:
            return
        normal = ir.styles["normal"].props["font"]
        fonts = rpr.find(qn("w:rFonts"))
        if fonts is None:
            fonts = OxmlElement("w:rFonts")
            rpr.insert(0, fonts)
        for attr in list(fonts.attrib):
            del fonts.attrib[attr]
        for attr in ("ascii", "hAnsi", "eastAsia", "cs"):
            fonts.set(qn(f"w:{attr}"), normal)
        if ir.metadata.language:
            lang = rpr.find(qn("w:lang"))
            if lang is None:
                lang = OxmlElement("w:lang")
                rpr.append(lang)
            for attr in list(lang.attrib):
                del lang.attrib[attr]
            lang.set(qn("w:val"), ir.metadata.language)

    # --------------------------------------------------------------- styles
    def _materialize_styles(self, doc: Any, ir: DocumentIR) -> None:
        existing = {s.name.casefold() for s in doc.styles}
        existing_ids = {s.style_id for s in doc.styles}
        order = ["normal"] + [n for n in sorted(ir.styles) if n != "normal"]
        for name in order:
            rs = ir.styles[name]
            docx_name = _BUILTIN_NAMES.get(name)
            if docx_name is not None:
                try:
                    style = doc.styles[docx_name]
                except KeyError:
                    raise DocxRenderError(f"Style bawaan Word {docx_name!r} tidak tersedia pada template.") from None
            else:
                candidate = name
                counter = 0
                while candidate.casefold() in existing or candidate.replace(" ", "") in existing_ids:
                    counter += 1
                    candidate = f"DSX {name}" if counter == 1 else f"DSX {counter} {name}"
                style = doc.styles.add_style(candidate, WD_STYLE_TYPE.PARAGRAPH)
                existing.add(candidate.casefold())
                existing_ids.add(style.style_id)
                if rs.role == "heading" and rs.level is not None:
                    style.base_style = doc.styles[f"Heading {rs.level}"]
                else:
                    style.base_style = doc.styles["Normal"]
                style.quick_style = True
            self._apply_style(style, rs)
            self._style_map[name] = style

    @staticmethod
    def _apply_style(style: Any, rs: ResolvedStyle) -> None:
        element = style.element
        for tag in ("w:pPr", "w:rPr", "w:link"):
            for child in element.findall(qn(tag)):
                element.remove(child)
        props = rs.props
        font = style.font
        font.name = props["font"]
        rfonts = element.rPr.rFonts
        rfonts.set(qn("w:eastAsia"), props["font"])
        rfonts.set(qn("w:cs"), props["font"])
        font.size = Pt(props["size"])
        font.bold = props["bold"]
        font.italic = props["italic"]
        font.underline = props["underline"]
        font.color.rgb = RGBColor.from_string(props["color"].lstrip("#").upper())
        pf = style.paragraph_format
        pf.alignment = _ALIGN[props["align"]]
        pf.line_spacing = float(props["line"])
        pf.space_before = Pt(props["space_before"])
        pf.space_after = Pt(props["space_after"])
        pf.left_indent = Cm(props["indent_left"])
        pf.right_indent = Cm(props["indent_right"])
        pf.first_line_indent = Cm(props["indent_first"])
        pf.page_break_before = bool(props["page_break_before"])
        if rs.role == "heading":
            pf.keep_with_next = True
            pf.keep_together = True
            if rs.level is not None:
                _set_outline_level(style.element.get_or_add_pPr(), rs.level)

    # ----------------------------------------------------------- paragraphs
    def _paragraph(self, container: Any, p: Paragraph) -> Any:
        par = container.add_paragraph(style=self._style_map[p.style])
        runs = _fill_segments(par, p.segments, p.text, p.overrides.get("size"))
        _apply_overrides(par, runs, p.overrides)
        if p.is_heading and p.level is not None:
            _set_outline_level(par._p.get_or_add_pPr(), p.level)
        return par

    # --------------------------------------------------------------- figure
    def _figure(self, doc: Any, fig: Figure) -> None:
        par = doc.add_paragraph(style=self._style_map["normal"])
        overrides: dict[str, Any] = {
            "align": fig.align,
            "indent_first": 0,
            "indent_left": 0,
            "indent_right": 0,
        }
        if fig.page_break_before:
            overrides["page_break_before"] = True
        run = par.add_run()
        shape = run.add_picture(io.BytesIO(fig.image.data), width=Cm(fig.width_cm), height=Cm(fig.height_cm))
        if fig.alt:
            shape._inline.docPr.set("descr", fig.alt)
        _apply_overrides(par, [], overrides)
        if fig.caption is not None:
            par.paragraph_format.keep_with_next = True
            self._paragraph(doc, fig.caption)

    # ---------------------------------------------------------------- table

    def _resolve_col_widths(self, specs: tuple[str, ...] | None, ncols: int, content_w_cm: float) -> list[float]:
        """Parse widths like ['2cm','3cm','*'] or relative ['1','2','1'] into cm list."""
        if not specs or len(specs) == 0:
            return [content_w_cm / ncols] * ncols
        specs = list(specs)[:ncols]
        while len(specs) < ncols:
            specs.append("*")
        fixed = []
        stars = 0
        rel = []
        all_relative = True
        for s in specs:
            s = str(s).strip().lower()
            if s in ("*", "auto", ""):
                fixed.append(None)
                stars += 1
                rel.append(1.0)
            elif s.endswith("cm"):
                try:
                    fixed.append(float(s[:-2]))
                    all_relative = False
                    rel.append(0)
                except ValueError:
                    fixed.append(None)
                    stars += 1
                    rel.append(1.0)
            elif s.endswith("mm"):
                try:
                    fixed.append(float(s[:-2]) / 10.0)
                    all_relative = False
                    rel.append(0)
                except ValueError:
                    fixed.append(None)
                    stars += 1
                    rel.append(1.0)
            else:
                try:
                    rel.append(float(s))
                    fixed.append(None)
                    stars += 1  # treat pure numbers as relative weights
                except ValueError:
                    fixed.append(None)
                    stars += 1
                    rel.append(1.0)
        if all_relative and sum(rel) > 0:
            total = sum(rel)
            return [content_w_cm * (r / total) for r in rel]
        used = sum(x for x in fixed if x is not None)
        remain = max(content_w_cm - used, 0.5)
        star_weight = sum(rel[i] for i, x in enumerate(fixed) if x is None) or 1
        out = []
        for i, x in enumerate(fixed):
            if x is not None:
                out.append(x)
            else:
                out.append(remain * (rel[i] / star_weight))
        return out


    def _hr(self, doc: Any, block: HorizontalRule) -> None:
        """Horizontal rule via bottom border on an empty paragraph."""
        if block.page_break_before:
            doc.add_paragraph().paragraph_format.page_break_before = True
        par = doc.add_paragraph()
        pf = par.paragraph_format
        pf.space_before = Pt(block.space_before_pt)
        pf.space_after = Pt(block.space_after_pt)
        align_map = {"left": 0, "center": 1, "right": 2, "justify": 3}
        pf.alignment = align_map.get(block.align, 1)
        # width as left/right indent approximation for non-100%
        width = (block.width or "100%").strip()
        if width.endswith("%"):
            try:
                pct = float(width[:-1]) / 100.0
            except ValueError:
                pct = 1.0
            if pct < 1.0:
                # indent both sides proportionally (assume ~16cm content)
                side = (1.0 - pct) * 8.0  # cm half
                pf.left_indent = Cm(side)
                pf.right_indent = Cm(side)
        elif width.endswith("cm"):
            try:
                w = float(width[:-2])
                # center a fixed-width line via equal indents when possible
                pass
            except ValueError:
                pass
        pPr = par._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        style_map = {
            "solid": "single",
            "dashed": "dashed",
            "dotted": "dotted",
            "double": "double",
            "thick": "thick",
            "wave": "wave",
        }
        bottom.set(qn("w:val"), style_map.get(block.style, "single"))
        thick_pt = block.thickness_pt
        if block.style == "thick" and thick_pt < 2.0:
            thick_pt = 2.25
        bottom.set(qn("w:sz"), str(int(round(thick_pt * 8))))  # eighths of a point
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), block.color or "000000")
        pBdr.append(bottom)
        pPr.append(pBdr)

    def _form_line(self, doc: Any, block: FormLine) -> None:
        """Fill-in lines for forms (dots / underscores / dashes)."""
        length = block.length or "40"
        n_chars = 40
        if length.endswith("cm"):
            try:
                n_chars = max(10, int(float(length[:-2]) * 4))
            except ValueError:
                n_chars = 40
        else:
            try:
                n_chars = max(5, int(float(length)))
            except ValueError:
                n_chars = 40
        if block.style == "dots":
            fill = "." * n_chars
        elif block.style == "dashed":
            fill = ("- " * ((n_chars + 1) // 2)).strip()
        elif block.style == "solid":
            fill = "_" * n_chars
        else:  # underscore
            fill = "_" * n_chars
        for i in range(max(1, block.count)):
            prefix = block.label
            if not prefix and block.count > 1:
                prefix = f"{i + 1}. "
            text = f"{prefix}{fill}" if prefix else fill
            par = doc.add_paragraph(text)
            gap = getattr(block, "gap_pt", 6.0) or 6.0
            par.paragraph_format.space_before = Pt(gap / 2)
            par.paragraph_format.space_after = Pt(gap / 2)

    def _apply_table_borders(self, table: Any, tbl: Table) -> None:
        """Set table-level borders from Table IR properties.

        Supports presets: none | single (outer) | double | dashed | dotted | grid |
                          bottom | top | outer
        Plus optional per-side overrides via tbl.border_sides.
        """
        border = getattr(tbl, "border", "grid") or "grid"
        color = (getattr(tbl, "border_color", None) or "000000").lstrip("#")
        default_sz = str(int(round((getattr(tbl, "border_width_pt", 0.5) or 0.5) * 8)))
        style_map = {
            "none": "nil",
            "single": "single",
            "double": "double",
            "dashed": "dashed",
            "dotted": "dotted",
            "thick": "thick",
            "grid": "single",
        }
        preset_edges: dict[str, set] = {
            "none": set(),
            "single": {"top", "left", "bottom", "right"},
            "outer": {"top", "left", "bottom", "right"},
            "double": {"top", "left", "bottom", "right", "insideH", "insideV"},
            "dashed": {"top", "left", "bottom", "right", "insideH", "insideV"},
            "dotted": {"top", "left", "bottom", "right", "insideH", "insideV"},
            "grid": {"top", "left", "bottom", "right", "insideH", "insideV"},
            "bottom": {"bottom"},
            "top": {"top"},
        }
        active = preset_edges.get(border, preset_edges["grid"])
        if border in ("grid", "outer", "single", "bottom", "top"):
            preset_val = "single"
        elif border == "none":
            preset_val = "nil"
        else:
            preset_val = style_map.get(border, "single")

        side_overrides = getattr(tbl, "border_sides", None) or {}

        tbl_pr = table._tbl.tblPr
        if tbl_pr is None:
            return
        for old in tbl_pr.findall(qn("w:tblBorders")):
            tbl_pr.remove(old)
        borders = OxmlElement("w:tblBorders")
        edges = ["top", "left", "bottom", "right", "insideH", "insideV"]
        for e in edges:
            if e in side_overrides:
                info = side_overrides[e]
                st = info.get("style", "single")
                val = "nil" if st == "none" else style_map.get(st, "single")
                sz = str(int(round(float(info.get("width_pt", 0.5)) * 8)))
                col = str(info.get("color", color)).lstrip("#")
            elif e in active:
                val = preset_val
                sz = default_sz
                col = color
            else:
                val, sz, col = "nil", "0", "auto"
            el = OxmlElement(f"w:{e}")
            el.set(qn("w:val"), val)
            el.set(qn("w:sz"), sz if val != "nil" else "0")
            el.set(qn("w:space"), "0")
            el.set(qn("w:color"), col if val != "nil" else "auto")
            borders.append(el)
        tbl_pr.append(borders)

    def _table(self, doc: Any, tbl: Table, ir: DocumentIR) -> None:
        if tbl.page_break_before and tbl.caption is None:
            # page break before table: empty paragraph with break (cell pPr break is unreliable)
            br = doc.add_paragraph(style=self._style_map["normal"])
            br.paragraph_format.page_break_before = True
            br.paragraph_format.space_before = Pt(0)
            br.paragraph_format.space_after = Pt(0)
        if tbl.caption is not None:
            cap = self._paragraph(doc, tbl.caption)
            cap.paragraph_format.keep_with_next = True
            if tbl.page_break_before:
                cap.paragraph_format.page_break_before = True
        ncols = tbl.column_count
        table = doc.add_table(rows=tbl.row_count, cols=ncols)
        table.style = doc.styles["Table Grid"]
        table.alignment = _TABLE_ALIGN[tbl.align]
        self._apply_table_borders(table, tbl)
        if getattr(tbl, "cell_padding_cm", None) is not None:
            pad = float(tbl.cell_padding_cm)
            tbl_pr = table._tbl.tblPr
            for old in tbl_pr.findall(qn("w:tblCellMar")):
                tbl_pr.remove(old)
            mar = OxmlElement("w:tblCellMar")
            for edge in ("top", "left", "bottom", "right"):
                el = OxmlElement(f"w:{edge}")
                el.set(qn("w:w"), str(int(round(pad * 567))))
                el.set(qn("w:type"), "dxa")
                mar.append(el)
            tbl_pr.append(mar)
        use_autofit = bool(getattr(tbl, "autofit", False))
        table.autofit = use_autofit
        content_w = ir.page.content_width
        width_cms = self._resolve_col_widths(getattr(tbl, "col_widths", None), ncols, content_w)
        col_twips_list = [int(round(Cm(w).twips)) for w in width_cms]
        total_twips = sum(col_twips_list) or int(round(Cm(content_w).twips))
        col_cm = content_w / ncols  # fallback for merge width math
        col_twips = int(round(Cm(col_cm).twips))
        tbl_pr = table._tbl.tblPr
        layout = tbl_pr.find(qn("w:tblLayout"))
        if layout is None:
            layout = OxmlElement("w:tblLayout")
            tbl_pr.append(layout)
        layout.set(qn("w:type"), "autofit" if use_autofit else "fixed")
        tbl_w = tbl_pr.find(qn("w:tblW"))
        if tbl_w is None:
            tbl_w = OxmlElement("w:tblW")
            tbl_pr.append(tbl_w)
        tbl_w.set(qn("w:type"), "dxa")
        tbl_w.set(qn("w:w"), str(total_twips))
        tbl_el = table._tbl
        existing_grid = tbl_el.find(qn("w:tblGrid"))
        if existing_grid is not None:
            tbl_el.remove(existing_grid)
        grid = OxmlElement("w:tblGrid")
        for tw in col_twips_list:
            grid_col = OxmlElement("w:gridCol")
            grid_col.set(qn("w:w"), str(tw))
            grid.append(grid_col)
        tbl_pr.addnext(grid)
        for i, column in enumerate(table.columns):
            column.width = Cm(width_cms[i] if i < len(width_cms) else col_cm)
        all_rows = ([tbl.header] if tbl.header is not None else []) + list(tbl.rows)
        normal = self._style_map["normal"]
        keep_together = bool(getattr(tbl, 'keep_rows', False)) or len(all_rows) <= TABLE_KEEP_TOGETHER_MAX_ROWS
        # Build grid map: for each logical (r,c) store TableCell or None if covered by merge
        grid: list[list[TableCell | None]] = []
        occupied: set[tuple[int, int]] = set()
        for r_index, values in enumerate(all_rows):
            row_cells: list[TableCell | None] = [None] * ncols
            c_logical = 0
            for raw in values:
                while c_logical < ncols and (r_index, c_logical) in occupied:
                    c_logical += 1
                if c_logical >= ncols:
                    break
                if isinstance(raw, TableCell):
                    cell_obj = raw
                else:
                    cell_obj = TableCell(str(raw) if raw is not None else "", ())
                rs = max(1, getattr(cell_obj, "rowspan", 1) or 1)
                cs = max(1, getattr(cell_obj, "colspan", 1) or 1)
                row_cells[c_logical] = cell_obj
                for dr in range(rs):
                    for dc in range(cs):
                        if dr == 0 and dc == 0:
                            continue
                        rr, cc = r_index + dr, c_logical + dc
                        if rr < len(all_rows) and cc < ncols:
                            occupied.add((rr, cc))
                c_logical += cs
            grid.append(row_cells)

        for r_index, values in enumerate(all_rows):
            if self._deadline is not None and r_index % 200 == 0:
                self._deadline.check()
            is_header = tbl.header is not None and r_index == 0
            row = table.rows[r_index]
            tr_pr = row._tr.get_or_add_trPr()
            for tag in ("w:cantSplit", "w:tblHeader"):
                for old_el in tr_pr.findall(qn(tag)):
                    tr_pr.remove(old_el)
            tr_pr.append(OxmlElement("w:cantSplit"))
            if is_header and getattr(tbl, "repeat_header", True):
                tr_pr.append(OxmlElement("w:tblHeader"))
            if getattr(tbl, "row_height_cm", None) and not is_header:
                for old in tr_pr.findall(qn("w:trHeight")):
                    tr_pr.remove(old)
                th = OxmlElement("w:trHeight")
                th.set(qn("w:val"), str(int(round(float(tbl.row_height_cm) * 567))))
                th.set(qn("w:hRule"), "atLeast")
                tr_pr.append(th)

            to_remove: list[int] = []
            for c_index in range(ncols):
                if (r_index, c_index) in occupied:
                    # covered by rowspan from above — leave cell for vMerge marker already set
                    continue
                cell_obj = grid[r_index][c_index]
                if cell_obj is None:
                    cell_obj = TableCell("", ())
                cell = row.cells[c_index]
                rs = max(1, cell_obj.rowspan or 1)
                cs = max(1, cell_obj.colspan or 1)
                # Apply merge via OOXML gridSpan / vMerge (keeps grid structure stable)
                if rs > 1 or cs > 1:
                    tc_pr = cell._tc.get_or_add_tcPr()
                    if cs > 1:
                        for old_gs in tc_pr.findall(qn("w:gridSpan")):
                            tc_pr.remove(old_gs)
                        gs = OxmlElement("w:gridSpan")
                        gs.set(qn("w:val"), str(cs))
                        tc_pr.append(gs)
                        # Defer removal of covered cells until after the row is fully written
                        for dc in range(1, cs):
                            if c_index + dc < ncols:
                                to_remove.append(c_index + dc)
                    if rs > 1:
                        for old_vm in tc_pr.findall(qn("w:vMerge")):
                            tc_pr.remove(old_vm)
                        vm = OxmlElement("w:vMerge")
                        vm.set(qn("w:val"), "restart")
                        tc_pr.append(vm)
                        for dr in range(1, rs):
                            if r_index + dr < len(all_rows):
                                other = table.rows[r_index + dr].cells[c_index]
                                otp = other._tc.get_or_add_tcPr()
                                for old_vm in otp.findall(qn("w:vMerge")):
                                    otp.remove(old_vm)
                                vm2 = OxmlElement("w:vMerge")
                                otp.append(vm2)

                cell.width = Cm(col_cm * cs)
                tc_pr = cell._tc.get_or_add_tcPr()
                tc_w = tc_pr.find(qn("w:tcW"))
                if tc_w is None:
                    tc_w = OxmlElement("w:tcW")
                    tc_pr.insert(0, tc_w)
                tc_w.set(qn("w:type"), "dxa")
                tc_w.set(qn("w:w"), str(col_twips * cs))
                v_align = tc_pr.find(qn("w:vAlign"))
                if v_align is None:
                    v_align = OxmlElement("w:vAlign")
                    tc_pr.append(v_align)
                va = getattr(cell_obj, "valign", None) or "center"
                v_align.set(qn("w:val"), va)
                # per-cell shading
                cell_sh = getattr(cell_obj, "shading", None)
                if cell_sh:
                    shd = tc_pr.find(qn("w:shd"))
                    if shd is None:
                        shd = OxmlElement("w:shd")
                        tc_pr.append(shd)
                    shd.set(qn("w:val"), "clear")
                    shd.set(qn("w:color"), "auto")
                    shd.set(qn("w:fill"), str(cell_sh).lstrip("#"))
                if is_header and getattr(tbl, "header_shading", None):
                    shd = tc_pr.find(qn("w:shd"))
                    if shd is None:
                        shd = OxmlElement("w:shd")
                        tc_pr.append(shd)
                    shd.set(qn("w:val"), "clear")
                    shd.set(qn("w:color"), "auto")
                    shd.set(qn("w:fill"), str(tbl.header_shading))
                cell_borders = getattr(cell_obj, "borders", None)
                if cell_borders:
                    _v12.apply_cell_borders(tc_pr, cell_borders)
                par = cell.paragraphs[0]
                par.style = normal
                # clear leftover empty paragraphs after merge
                runs = _fill_segments(par, cell_obj.segments, cell_obj.text)
                if is_header:
                    for run in runs:
                        try:
                            run.bold = True
                        except Exception:
                            pass
                is_numeric = (not is_header) and bool(_NUMERIC.match(cell_obj.text.strip()))
                cell_align = getattr(cell_obj, "align", None)
                if cell_align:
                    al = cell_align
                elif is_header:
                    al = "center"
                elif is_numeric:
                    al = "right"
                else:
                    al = "left"
                overrides = {
                    "align": al,
                    "indent_first": 0,
                    "indent_left": 0,
                    "indent_right": 0,
                    "space_before": 0,
                    "space_after": 0,
                    "line": TABLE_LINE_SPACING,
                }
                _apply_overrides(par, runs, overrides)
                if keep_together and r_index < len(all_rows) - 1:
                    par.paragraph_format.keep_with_next = True
            # Optionally collapse covered cells — keep for vMerge stability; gridSpan handles width
            # (Removing tc can make row cell counts non-uniform and confuse some validators.)
            to_remove.clear()
        self._spacer(doc)

    # ----------------------------------------------------------------- lists
    def _list(self, doc: Any, block: ListBlock) -> None:
        kind = "ordered" if block.ordered else "bullet"
        step, hanging = int(round(Cm(block.indent_cm).twips)), int(round(Cm(block.hanging_cm).twips))
        num_id = self._numbering.num_for(kind, step, hanging, block.start if block.ordered else None)
        style = self._style_map[block.style]
        first_paragraph = True
        for item in block.items:
            left = step * (item.level + 1)
            par = doc.add_paragraph(style=style)
            _fill_segments(par, item.segments, item.text)
            num_pr = par._p.get_or_add_pPr().get_or_add_numPr()
            num_pr.get_or_add_ilvl().val = item.level
            num_pr.get_or_add_numId().val = num_id
            par.paragraph_format.left_indent = Twips(left)
            par.paragraph_format.first_line_indent = Twips(-hanging)
            par.paragraph_format.keep_together = True  # item tidak terpotong antarhalaman
            par.paragraph_format.keep_with_next = bool(item.continuations)
            overrides = dict(block.overrides)
            if block.page_break_before and first_paragraph:
                overrides["page_break_before"] = True
            first_paragraph = False
            _apply_overrides(par, par.runs, overrides)
            for index, extra in enumerate(item.continuations):
                cont = doc.add_paragraph(style=style)
                cont.add_run(extra)
                cont.paragraph_format.left_indent = Twips(left)  # sejajar dengan teks item, tanpa nomor
                cont.paragraph_format.first_line_indent = Twips(0)
                cont.paragraph_format.keep_together = True
                cont.paragraph_format.keep_with_next = index < len(item.continuations) - 1
                _apply_overrides(cont, cont.runs, {k: v for k, v in block.overrides.items() if k not in ("indent_first",)})

    # ---------------------------------------------------------------- callout
    def _callout(self, doc: Any, block: Callout, ir: DocumentIR) -> None:
        theme = CALLOUT_THEMES[block.variant]
        paragraphs = ([block.title] if block.title is not None else []) + list(block.body)
        table = doc.add_table(rows=1, cols=1)
        table.style = doc.styles["Table Grid"]
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        width = Cm(ir.page.content_width)
        table.columns[0].width = width
        tbl_pr = table._tbl.tblPr
        tbl_w = tbl_pr.find(qn("w:tblW"))
        if tbl_w is not None:
            tbl_w.set(qn("w:type"), "dxa")
            tbl_w.set(qn("w:w"), str(int(round(width.twips))))
        label = block.title.text if block.title is not None else block.variant
        for tag, value in (("w:tblCaption", f"dsx-callout:{block.variant}"), ("w:tblDescription", label)):
            element = OxmlElement(tag)
            element.set(qn("w:val"), value)
            tbl_pr.append(element)
        row = table.rows[0]
        row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        cell = row.cells[0]
        cell.width = width
        tc_pr = cell._tc.get_or_add_tcPr()
        borders = parse_xml(
            f'<w:tcBorders {nsdecls("w")}>'
            f'<w:top w:val="single" w:sz="4" w:space="0" w:color="{theme["border"]}"/>'
            f'<w:left w:val="single" w:sz="36" w:space="0" w:color="{theme["border"]}"/>'
            f'<w:bottom w:val="single" w:sz="4" w:space="0" w:color="{theme["border"]}"/>'
            f'<w:right w:val="single" w:sz="4" w:space="0" w:color="{theme["border"]}"/>'
            "</w:tcBorders>"
        )
        tc_pr.append(borders)
        tc_pr.append(parse_xml(f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="{theme["fill"]}"/>'))
        tc_pr.append(
            parse_xml(
                f'<w:tcMar {nsdecls("w")}><w:top w:w="100" w:type="dxa"/><w:left w:w="180" w:type="dxa"/>'
                '<w:bottom w:w="100" w:type="dxa"/><w:right w:w="180" w:type="dxa"/></w:tcMar>'
            )
        )
        for index, p in enumerate(paragraphs):
            par = cell.paragraphs[0] if index == 0 else cell.add_paragraph()
            par.style = self._style_map[p.style]
            runs = _fill_segments(par, p.segments, p.text, p.overrides.get("size"))
            overrides = dict(p.overrides)
            if block.page_break_before and index == 0:
                overrides["page_break_before"] = True
            _apply_overrides(par, runs, overrides)
            if block.title is not None and index == 0 and len(paragraphs) > 1:
                par.paragraph_format.keep_with_next = True
        self._spacer(doc)

    # ------------------------------------------------------------------- math
    def _math(self, doc: Any, block: MathBlock) -> None:
        par = doc.add_paragraph(style=self._style_map[block.style])
        overrides = dict(block.overrides)
        if block.page_break_before:
            overrides["page_break_before"] = True
        _apply_overrides(par, [], overrides)
        par.paragraph_format.keep_together = True
        omml = build_math_para(block.tree, block.align, block.size)
        par._p.append(parse_xml(etree_tostring(omml)))

    def _spacer(self, doc: Any) -> None:
        spacer = doc.add_paragraph(style=self._style_map["normal"])
        spacer.paragraph_format.space_before = Pt(0)
        spacer.paragraph_format.space_after = Pt(0)
        spacer.paragraph_format.first_line_indent = Cm(0)
        spacer.paragraph_format.line_spacing = Pt(8)

    def _toc(self, doc: Any, block: TocBlock, ir: DocumentIR | None = None) -> None:
        if block.title:
            title = doc.add_paragraph(block.title)
            title.style = self._style_map.get("heading-1", self._style_map["normal"])
            if block.page_break_before:
                title.paragraph_format.page_break_before = True
        par = doc.add_paragraph()
        run = par.add_run()
        fld_begin = OxmlElement("w:fldChar")
        fld_begin.set(qn("w:fldCharType"), "begin")
        run._r.append(fld_begin)
        run2 = par.add_run()
        instr = OxmlElement("w:instrText")
        instr.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        instr.text = f' TOC \\o "1-{block.depth}" \\h \\z \\u '
        run2._r.append(instr)
        run3 = par.add_run()
        fld_sep = OxmlElement("w:fldChar")
        fld_sep.set(qn("w:fldCharType"), "separate")
        run3._r.append(fld_sep)
        # Preview entries from IR headings (until user updates fields in Word)
        preview_lines = []
        for b in (ir.blocks if ir is not None else ()):
            if isinstance(b, Paragraph) and b.is_heading and b.level and b.level <= block.depth:
                indent = "    " * (b.level - 1)
                preview_lines.append(f"{indent}{b.text}")
        preview = "\n".join(preview_lines) if preview_lines else "(Daftar isi — perbarui field di Word/LibreOffice)"
        par.add_run(preview)
        run4 = par.add_run()
        fld_end = OxmlElement("w:fldChar")
        fld_end.set(qn("w:fldCharType"), "end")
        run4._r.append(fld_end)
        self._spacer(doc)


    def _code(self, doc: Any, block: CodeBlock) -> None:
        if block.page_break_before:
            doc.add_paragraph().paragraph_format.page_break_before = True
        if block.caption is not None:
            self._paragraph(doc, block.caption)
        lines = block.text.split("\n") if block.text else [""]
        for i, line in enumerate(lines):
            display = f"{i+1:>3} | {line}" if block.line_numbers else line
            par = doc.add_paragraph()
            par.paragraph_format.space_before = Pt(0)
            par.paragraph_format.space_after = Pt(0)
            par.paragraph_format.line_spacing = 1.0
            pPr = par._p.get_or_add_pPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), "F5F5F5")
            pPr.append(shd)
            run = par.add_run(display)
            run.font.name = "Consolas"
            try:
                run._element.rPr.rFonts.set(qn("w:eastAsia"), "Consolas")
            except Exception:
                pass
            run.font.size = Pt(9)
        doc.add_paragraph()

    def _chart(self, doc: Any, block: ChartBlock) -> None:
        from ..ir.nodes import Figure as Fig
        fig = Fig(
            image=block.image,
            width_cm=block.width_cm,
            height_cm=block.height_cm,
            align=block.align,
            alt=block.title or "chart",
            caption=block.caption,
            page_break_before=block.page_break_before,
            source=block.source,
            label_id=block.label_id,
        )
        self._figure(doc, fig)

    def _bibliography(self, doc: Any, block: BibliographyBlock, ir: DocumentIR) -> None:
        if block.page_break_before:
            doc.add_paragraph().paragraph_format.page_break_before = True
        # Skip title when empty (user already provided H1("Daftar Pustaka"))
        if block.title and block.title.strip():
            title = doc.add_paragraph(block.title)
            try:
                title.style = self._style_map.get("heading-1", self._style_map["normal"])
            except Exception:
                pass
        items = block.items or ir.bib_items
        style = block.style_name
        for i, it in enumerate(items, 1):
            author = it.get("author") or ""
            title_t = it.get("title") or ""
            year = it.get("year") or ""
            journal = it.get("journal") or ""
            publisher = it.get("publisher") or ""
            url = it.get("url") or ""
            pages = it.get("pages") or ""
            volume = it.get("volume") or ""
            if style == "apa":
                text = f"{author} ({year}). {title_t}."
                if journal:
                    text += f" {journal}"
                    if volume:
                        text += f", {volume}"
                    if pages:
                        text += f", {pages}"
                    text += "."
                elif publisher:
                    text += f" {publisher}."
                if url:
                    text += f" {url}"
            elif style == "ieee":
                text = f'[{i}] {author}, "{title_t},"'
                if journal:
                    text += f" {journal},"
                if volume:
                    text += f" vol. {volume},"
                if pages:
                    text += f" pp. {pages},"
                if year:
                    text += f" {year}."
                else:
                    text = text.rstrip(",") + "."
                if url:
                    text += f" {url}"
            else:
                parts = [p for p in (author, title_t, journal or publisher, year, pages) if p]
                text = f"[{i}] " + ". ".join(parts) + ("." if parts else "")
                if url:
                    text += f" {url}"
            par = doc.add_paragraph(text)
            par.paragraph_format.left_indent = Cm(0.75)
            par.paragraph_format.first_line_indent = Cm(-0.75)



    @staticmethod
    def _resolve_pn_placement(block: Any = None, page_number: Any = None) -> tuple[str, str]:
        """Return (position, align) from placement or explicit fields."""
        placement = None
        if block is not None:
            placement = getattr(block, "page_number_placement", None)
        if placement is None and page_number is not None:
            placement = getattr(page_number, "placement", None)
        if placement:
            pl = str(placement).lower()
            position = "header" if pl.startswith("top_") else "footer"
            if pl.endswith("_left"):
                align = "left"
            elif pl.endswith("_right"):
                align = "right"
            else:
                align = "center"
            return position, align
        if block is not None:
            return (
                getattr(block, "page_number_position", None) or "footer",
                getattr(block, "page_number_align", None) or "center",
            )
        if page_number is not None:
            return (
                getattr(page_number, "position", None) or "footer",
                getattr(page_number, "align", None) or "center",
            )
        return "footer", "center"

    def _section_break(self, doc: Any, block: SectionBreak, ir: DocumentIR) -> None:
        """Start a new Word section with full page/HF configuration."""
        type_map = {
            "next_page": WD_SECTION.NEW_PAGE,
            "continuous": WD_SECTION.CONTINUOUS,
            "even_page": WD_SECTION.EVEN_PAGE,
            "odd_page": WD_SECTION.ODD_PAGE,
        }
        start = type_map.get(block.break_type, WD_SECTION.NEW_PAGE)
        # add_section() closes current section and opens a new one
        sec = doc.add_section(start)
        self._configure_section_geometry(sec, block, ir)
        self._section_plan.append(block)

    def _configure_section_geometry(self, sec: Any, block: SectionBreak, ir: DocumentIR) -> None:
        """Apply orientation, margins, page size, columns, page number format to a Section."""
        from ..schema import PAGE_SIZES
        page = ir.page
        # optional size override for this section
        w_cm, h_cm = page.width_cm, page.height_cm
        if block.page_size and block.page_size in PAGE_SIZES:
            w_cm, h_cm = PAGE_SIZES[block.page_size]
        orient = block.orientation or page.orientation
        if orient == "landscape":
            sec.orientation = WD_ORIENT.LANDSCAPE
            sec.page_width = Cm(max(w_cm, h_cm))
            sec.page_height = Cm(min(w_cm, h_cm))
            if w_cm > h_cm:
                sec.page_width = Cm(w_cm)
                sec.page_height = Cm(h_cm)
            else:
                sec.page_width = Cm(h_cm)
                sec.page_height = Cm(w_cm)
        else:
            sec.orientation = WD_ORIENT.PORTRAIT
            sec.page_width = Cm(min(w_cm, h_cm) if orient == "portrait" and block.page_size else w_cm)
            sec.page_height = Cm(max(w_cm, h_cm) if orient == "portrait" and block.page_size else h_cm)
            # prefer explicit size dimensions
            if block.page_size and block.page_size in PAGE_SIZES:
                pw, ph = PAGE_SIZES[block.page_size]
                if orient == "landscape":
                    sec.page_width, sec.page_height = Cm(max(pw, ph)), Cm(min(pw, ph))
                else:
                    sec.page_width, sec.page_height = Cm(pw), Cm(ph)
            else:
                sec.page_width = Cm(page.width_cm)
                sec.page_height = Cm(page.height_cm)
        # margins
        top = block.margin_top if block.margin_top is not None else page.margin_top
        bottom = block.margin_bottom if block.margin_bottom is not None else page.margin_bottom
        left = block.margin_left if block.margin_left is not None else page.margin_left
        right = block.margin_right if block.margin_right is not None else page.margin_right
        sec.top_margin = Cm(top)
        sec.bottom_margin = Cm(bottom)
        sec.left_margin = Cm(left)
        sec.right_margin = Cm(right)
        if block.gutter_cm:
            sec.gutter = Cm(block.gutter_cm)
        if block.mirror_margins:
            # OOXML: pgMar mirror / sectPr mirrorMargins
            sectPr = sec._sectPr
            for old in sectPr.findall(qn("w:mirrorMargins")):
                sectPr.remove(old)
            sectPr.append(OxmlElement("w:mirrorMargins"))
            # outer page numbers: rely on odd/even HF + align when odd_even set by user
        # page number format / start via oxml
        sectPr = sec._sectPr
        for old in sectPr.findall(qn("w:pgNumType")):
            sectPr.remove(old)
        if (
            block.page_number_format
            or block.page_number_start is not None
            or block.page_number_restart
            or block.page_number_continue
        ):
            pgNum = OxmlElement("w:pgNumType")
            fmt_map = {
                "decimal": "decimal",
                "lower_roman": "lowerRoman",
                "upper_roman": "upperRoman",
                "lower_letter": "lowerLetter",
                "upper_letter": "upperLetter",
            }
            if block.page_number_format:
                pgNum.set(qn("w:fmt"), fmt_map.get(block.page_number_format, "decimal"))
            # continue=true → do not set start (Word continues previous sequence)
            if not block.page_number_continue and block.page_number_start is not None:
                pgNum.set(qn("w:start"), str(block.page_number_start))
            elif block.page_number_restart and block.page_number_start is not None:
                pgNum.set(qn("w:start"), str(block.page_number_start))
            sectPr.append(pgNum)
        # columns
        for old in sectPr.findall(qn("w:cols")):
            sectPr.remove(old)
        if block.columns and block.columns > 1:
            cols = OxmlElement("w:cols")
            cols.set(qn("w:num"), str(block.columns))
            cols.set(qn("w:space"), str(int(round(block.column_gap_cm * 567))))
            cols.set(qn("w:equalWidth"), "1")
            sectPr.append(cols)
        # different first page
        sec.different_first_page_header_footer = bool(block.different_first_page)
        # odd/even
        if block.odd_even_header:
            sec.odd_and_even_pages_header_footer = True

    def _columns_marker(self, doc: Any, block: Any) -> None:
        """Start/end a multi-column region via continuous section breaks.

        Content AFTER ColumnsStart and BEFORE ColumnsEnd is multi-column.
        """
        if isinstance(block, ColumnsStart):
            sec = doc.add_section(WD_SECTION.CONTINUOUS)
            self._set_section_columns(sec, block.count, block.gap_cm)
        elif isinstance(block, ColumnsEnd):
            sec = doc.add_section(WD_SECTION.CONTINUOUS)
            self._set_section_columns(sec, 1, 0.5)

    def _set_section_columns(self, sec: Any, count: int, gap_cm: float) -> None:
        sectPr = sec._sectPr
        for old in sectPr.findall(qn("w:cols")):
            sectPr.remove(old)
        cols = OxmlElement("w:cols")
        cols.set(qn("w:num"), str(max(1, count)))
        cols.set(qn("w:space"), str(int(round(gap_cm * 567))))
        if count > 1:
            cols.set(qn("w:equalWidth"), "1")
        sectPr.append(cols)

    def _insert_section_cols(self, doc: Any, count: int, gap_cm: float) -> None:
        """Append a paragraph whose pPr contains sectPr (continuous) with w:cols."""
        from copy import deepcopy
        par = doc.add_paragraph()
        pPr = par._p.get_or_add_pPr()
        for old in pPr.findall(qn("w:sectPr")):
            pPr.remove(old)
        sect = OxmlElement("w:sectPr")
        ptype = OxmlElement("w:type")
        ptype.set(qn("w:val"), "continuous")
        sect.append(ptype)
        body = doc._element.body
        last_sect = body.find(qn("w:sectPr"))
        if last_sect is not None:
            for tag in ("w:pgSz", "w:pgMar", "w:pgNumType", "w:docGrid"):
                src = last_sect.find(qn(tag))
                if src is not None:
                    sect.append(deepcopy(src))
        cols = OxmlElement("w:cols")
        cols.set(qn("w:num"), str(max(1, count)))
        cols.set(qn("w:space"), str(int(round(gap_cm * 567))))
        if count > 1:
            cols.set(qn("w:equalWidth"), "1")
        sect.append(cols)
        pPr.append(sect)


    def _footnotes(self, doc: Any, ir: DocumentIR) -> None:
        """Native footnotes are injected post-save via _inject_native_footnotes.
        No end-of-document list is rendered in the body.
        """
        return

    # ------------------------------------------------------ header / footer
    def _apply_multi_section_headers_footers(self, doc: Any, ir: DocumentIR) -> None:
        """Apply header/footer/page-number to every section (global + per-SECTION overrides)."""
        sections = list(doc.sections)
        plan = getattr(self, "_section_plan", []) or []
        # Section 0: content before first SECTION → global HEADER/FOOTER/PAGENUM
        # Sections 1..n: each matches plan[i-1] if plan started after content, or plan[i]
        # Our SECTION() calls add_section(), so after N SECTION calls we have N+1 sections.
        # sections[0] = before first SECTION (or whole doc if no SECTION)
        # sections[k] for k>=1 corresponds to plan[k-1]
        for idx, sec in enumerate(sections):
            if idx == 0:
                pn0 = None
                show0 = False
                if ir.page_number is not None and getattr(ir.page_number, "show", True):
                    pos, align = self._resolve_pn_placement(None, ir.page_number)
                    from ..ir.nodes import PageNumber
                    pn0 = PageNumber(
                        position=pos,
                        format=ir.page_number.format,
                        style=ir.page_number.style,
                        overrides={**ir.page_number.overrides, "align": align},
                        number_format=ir.page_number.number_format,
                        align=align,
                        placement=ir.page_number.placement,
                        start=ir.page_number.start,
                        show=True,
                    )
                    show0 = True
                self._fill_section_hf(
                    sec,
                    header_text=ir.header.text if ir.header else None,
                    footer_text=ir.footer.text if ir.footer else None,
                    header_style=ir.header.style if ir.header else "normal",
                    footer_style=ir.footer.style if ir.footer else "normal",
                    header_overrides=ir.header.overrides if ir.header else {},
                    footer_overrides=ir.footer.overrides if ir.footer else {},
                    header_distance=getattr(ir.header, "distance_cm", None) if ir.header else None,
                    footer_distance=getattr(ir.footer, "distance_cm", None) if ir.footer else None,
                    page_number=pn0,
                    show_page_number=show0,
                    different_first=False,
                    odd_even=False,
                    header_odd=None,
                    header_even=None,
                    footer_odd=None,
                    footer_even=None,
                    is_first_section=True,
                )
            else:
                block = plan[idx - 1] if idx - 1 < len(plan) else None
                if block is None:
                    continue
                # inherit global HF text if section does not override
                h_text = block.header_text if block.header_text is not None else (ir.header.text if ir.header else None)
                f_text = block.footer_text if block.footer_text is not None else (ir.footer.text if ir.footer else None)
                # page number: section may hide
                pn = None
                pos, align = self._resolve_pn_placement(block, ir.page_number)
                if block.show_page_number:
                    from ..ir.nodes import PageNumber
                    base = ir.page_number
                    fmt = block.page_number_format_text or (
                        base.format if base is not None else "{page}"
                    )
                    style = base.style if base is not None else "normal"
                    nf = block.page_number_format or (
                        base.number_format if base is not None else "decimal"
                    )
                    start = None if block.page_number_continue else block.page_number_start
                    pn = PageNumber(
                        position=pos,
                        format=fmt,
                        style=style,
                        overrides={"align": align},
                        number_format=nf,
                        align=align,
                        placement=block.page_number_placement,
                        start=start,
                        show=True,
                    )
                # distance: section overrides global
                h_dist = block.header_distance_cm
                if h_dist is None and ir.header is not None:
                    h_dist = getattr(ir.header, "distance_cm", None)
                f_dist = block.footer_distance_cm
                if f_dist is None and ir.footer is not None:
                    f_dist = getattr(ir.footer, "distance_cm", None)
                use_odd_even = bool(block.odd_even_header or block.mirror_margins)
                # mirror book style: odd pages number on the right (outer), even on the left
                f_odd = block.footer_odd
                f_even = block.footer_even
                h_odd = block.header_odd
                h_even = block.header_even
                if block.mirror_margins and pn is not None:
                    # ensure primary (odd) align right, even align left for outer placement
                    if pn.position == "footer":
                        f_odd = f_odd if f_odd is not None else (f_text or "")
                        f_even = f_even if f_even is not None else (f_text or "")
                    else:
                        h_odd = h_odd if h_odd is not None else (h_text or "")
                        h_even = h_even if h_even is not None else (h_text or "")
                    # tweak page number align via overrides copy
                    from ..ir.nodes import PageNumber
                    pn = PageNumber(
                        position=pn.position,
                        format=pn.format,
                        style=pn.style,
                        overrides={**pn.overrides, "align": "right"},
                        number_format=pn.number_format,
                        align="right",
                        placement=pn.placement,
                        start=pn.start,
                        show=pn.show,
                    )
                self._fill_section_hf(
                    sec,
                    header_text=h_text,
                    footer_text=f_text,
                    header_style=ir.header.style if ir.header else "normal",
                    footer_style=ir.footer.style if ir.footer else "normal",
                    header_overrides=ir.header.overrides if ir.header else {},
                    footer_overrides=ir.footer.overrides if ir.footer else {},
                    header_distance=h_dist,
                    footer_distance=f_dist,
                    page_number=pn,
                    show_page_number=bool(block.show_page_number),
                    different_first=bool(block.different_first_page),
                    odd_even=use_odd_even,
                    header_odd=h_odd,
                    header_even=h_even,
                    footer_odd=f_odd,
                    footer_even=f_even,
                    is_first_section=False,
                )
        # Watermark on first section header
        if ir.watermark is not None and sections:
            self._add_watermark(sections[0], ir.watermark)

    def _clear_hf_part(self, part: Any) -> None:
        part.is_linked_to_previous = False
        # remove all paragraphs content
        for par in list(part.paragraphs):
            p = par._element
            p.getparent().remove(p)
        # ensure at least one empty paragraph
        part.add_paragraph()

    def _write_hf_paragraph(
        self,
        part: Any,
        text: str | None,
        style: str,
        overrides: dict,
        page_number: Any | None,
        page_number_here: bool,
    ) -> None:
        part.is_linked_to_previous = False
        # use first paragraph or add
        if part.paragraphs:
            par = part.paragraphs[0]
            # clear runs
            for r in list(par.runs):
                r._r.getparent().remove(r._r)
        else:
            par = part.add_paragraph()
        style_name = style if style in self._style_map else "normal"
        try:
            par.style = self._style_map[style_name]
        except Exception:
            pass
        runs: list[Any] = []
        if text:
            runs.append(par.add_run(text))
        if page_number is not None and page_number_here:
            if text:
                runs.append(par.add_run("  "))
            runs.extend(_page_number_runs(par, page_number.format))
        ov = dict(overrides or {})
        if page_number is not None and page_number_here:
            ov.setdefault("align", getattr(page_number, "align", None) or page_number.overrides.get("align", "center"))
        _apply_overrides(par, runs, ov)

    def _fill_section_hf(
        self,
        sec: Any,
        *,
        header_text: str | None,
        footer_text: str | None,
        header_style: str,
        footer_style: str,
        header_overrides: dict,
        footer_overrides: dict,
        header_distance: float | None,
        footer_distance: float | None,
        page_number: Any | None,
        show_page_number: bool,
        different_first: bool,
        odd_even: bool,
        header_odd: str | None,
        header_even: str | None,
        footer_odd: str | None,
        footer_even: str | None,
        is_first_section: bool,
    ) -> None:
        if header_distance is not None:
            sec.header_distance = Cm(header_distance)
        if footer_distance is not None:
            sec.footer_distance = Cm(footer_distance)
        sec.different_first_page_header_footer = different_first
        if odd_even:
            sec.odd_and_even_pages_header_footer = True

        pn_in_header = show_page_number and page_number is not None and page_number.position == "header"
        pn_in_footer = show_page_number and page_number is not None and page_number.position == "footer"

        # default header/footer
        self._write_hf_paragraph(
            sec.header, header_text, header_style, header_overrides, page_number, pn_in_header
        )
        self._write_hf_paragraph(
            sec.footer, footer_text, footer_style, footer_overrides, page_number, pn_in_footer
        )

        # first page: empty HF when different_first (cover / no number)
        if different_first:
            try:
                self._clear_hf_part(sec.first_page_header)
                self._clear_hf_part(sec.first_page_footer)
            except Exception:
                pass

        # odd/even variants
        if odd_even:
            try:
                self._write_hf_paragraph(
                    sec.even_page_header,
                    header_even if header_even is not None else header_text,
                    header_style,
                    header_overrides,
                    page_number,
                    pn_in_header,
                )
                self._write_hf_paragraph(
                    sec.even_page_footer,
                    footer_even if footer_even is not None else footer_text,
                    footer_style,
                    footer_overrides,
                    page_number,
                    pn_in_footer,
                )
                # odd uses primary header/footer; if header_odd set, overwrite primary
                if header_odd is not None:
                    self._write_hf_paragraph(
                        sec.header, header_odd, header_style, header_overrides, page_number, pn_in_header
                    )
                if footer_odd is not None:
                    self._write_hf_paragraph(
                        sec.footer, footer_odd, footer_style, footer_overrides, page_number, pn_in_footer
                    )
            except Exception:
                pass

        # page number format on this section
        if page_number is not None and show_page_number:
            self._apply_page_number_settings(sec, page_number)


    def _apply_page_number_settings(self, section: Any, pn: Any) -> None:
        """Set w:pgNumType on section for roman/decimal and start."""
        sectPr = section._sectPr
        for old in sectPr.findall(qn("w:pgNumType")):
            sectPr.remove(old)
        el = OxmlElement("w:pgNumType")
        fmt_map = {
            "decimal": "decimal",
            "lower_roman": "lowerRoman",
            "upper_roman": "upperRoman",
            "lower_letter": "lowerLetter",
            "upper_letter": "upperLetter",
        }
        el.set(qn("w:fmt"), fmt_map.get(getattr(pn, "number_format", None) or "decimal", "decimal"))
        if getattr(pn, "start", None) is not None:
            el.set(qn("w:start"), str(pn.start))
        sectPr.append(el)

    def _add_watermark(self, section: Any, wm: Any) -> None:
        """Diagonal text watermark in header via VML (Word-compatible)."""
        header = section.header
        header.is_linked_to_previous = False
        par = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
        text = (
            str(wm.text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )
        color = (wm.color or "808080").lstrip("#")
        color = color.upper() if len(color) == 6 else "808080"
        opacity = max(0.05, min(0.5, float(wm.opacity)))
        angle = float(wm.angle)
        size_pt = float(wm.size_pt)
        style = (
            "position:absolute;margin-left:0;margin-top:0;width:500pt;height:100pt;"
            "z-index:-251654144;mso-wrap-edited:f;mso-position-horizontal:center;"
            "mso-position-horizontal-relative:margin;mso-position-vertical:center;"
            "mso-position-vertical-relative:margin;rotation:%s" % angle
        )
        vml = (
            '<w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:v="urn:schemas-microsoft-com:vml" '
            'xmlns:o="urn:schemas-microsoft-com:office:office">'
            "<w:rPr><w:noProof/></w:rPr><w:pict>"
            '<v:shape id="DSXWatermark" type="#_x0000_t136" style="%s" fillcolor="#%s" stroked="f">'
            '<v:fill opacity="%s"/>'
            '<v:textpath style="font-family:Calibri;font-size:%spt" string="%s"/>'
            "</v:shape></w:pict></w:r>"
        ) % (style, color, opacity, size_pt, text)
        try:
            par._p.append(parse_xml(vml))
        except Exception:
            run = par.add_run(wm.text)
            run.font.size = Pt(size_pt)
            try:
                run.font.color.rgb = RGBColor.from_string(color)
            except Exception:
                pass



# ---------------------------------------------------------------------- util
def _set_outline_level(ppr: Any, level: int) -> None:
    for existing in ppr.findall(qn("w:outlineLvl")):
        ppr.remove(existing)
    element = OxmlElement("w:outlineLvl")
    element.set(qn("w:val"), str(level - 1))
    ppr.insert_element_before(element, "w:divId", "w:cnfStyle", "w:rPr", "w:sectPr", "w:pPrChange")


def _apply_overrides(par: Any, runs: list[Any], overrides: dict[str, Any]) -> None:
    pf = par.paragraph_format
    for key, value in overrides.items():
        if key == "align":
            pf.alignment = _ALIGN[value]
        elif key == "line":
            pf.line_spacing = float(value)
        elif key == "space_before":
            pf.space_before = Pt(value)
        elif key == "space_after":
            pf.space_after = Pt(value)
        elif key == "indent_left":
            pf.left_indent = Cm(value)
        elif key == "indent_right":
            pf.right_indent = Cm(value)
        elif key == "indent_first":
            pf.first_line_indent = Cm(value)
        elif key == "page_break_before":
            pf.page_break_before = bool(value)
    if not any(k in overrides for k in _FONT_KEYS):
        return
    for run in runs:
        font = run.font
        if "font" in overrides:
            font.name = overrides["font"]
            r = run._r
            rPr = r.get_or_add_rPr()
            rFonts = rPr.find(qn("w:rFonts"))
            if rFonts is None:
                rFonts = OxmlElement("w:rFonts")
                rPr.insert(0, rFonts)
            rFonts.set(qn("w:ascii"), overrides["font"])
            rFonts.set(qn("w:hAnsi"), overrides["font"])
            rFonts.set(qn("w:eastAsia"), overrides["font"])
            rFonts.set(qn("w:cs"), overrides["font"])
        if "size" in overrides:
            font.size = Pt(overrides["size"])
        if "bold" in overrides:
            font.bold = overrides["bold"]
        if "italic" in overrides:
            font.italic = overrides["italic"]
        if "underline" in overrides:
            font.underline = overrides["underline"]
        if "color" in overrides:
            font.color.rgb = RGBColor.from_string(overrides["color"].lstrip("#").upper())


def _field_run(par: Any, kind: str, text: str | None = None) -> Any:
    run = par.add_run()
    if kind in ("begin", "separate", "end"):
        element = OxmlElement("w:fldChar")
        element.set(qn("w:fldCharType"), kind)
        run._r.append(element)
    elif kind == "instr":
        element = OxmlElement("w:instrText")
        element.set(qn("xml:space"), "preserve")
        element.text = text
        run._r.append(element)
    return run


def _page_number_runs(par: Any, fmt: str) -> list[Any]:
    runs: list[Any] = []
    for part in _FIELD_SPLIT.split(fmt):
        if not part:
            continue
        if part in ("{page}", "{pages}"):
            instr = "PAGE" if part == "{page}" else "NUMPAGES"
            runs.append(_field_run(par, "begin"))
            runs.append(_field_run(par, "instr", f" {instr} "))
            runs.append(_field_run(par, "separate"))
            runs.append(par.add_run("1"))
            runs.append(_field_run(par, "end"))
        else:
            runs.append(par.add_run(part))
    return runs


def _normalize_zip(data: bytes) -> bytes:
    """Tulis ulang ZIP dengan timestamp tetap agar keluaran deterministik."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as dst:
        for info in src.infolist():
            entry = zipfile.ZipInfo(info.filename, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.create_system = 3
            entry.external_attr = 0o600 << 16
            dst.writestr(entry, src.read(info))
    return out.getvalue()


def etree_tostring(element: Any) -> bytes:
    from lxml import etree

    return etree.tostring(element, encoding="utf-8")


_BULLETS = ("\u2022", "\u25e6", "\u25aa")
_ORDERED_FORMATS = ("decimal", "lowerLetter", "lowerRoman")


class _Numbering:
    """Definisi penomoran native Word (numbering.xml).

    Satu abstractNum per kombinasi (jenis, indentasi, hanging); bullet berbagi satu w:num,
    sedangkan setiap daftar berurutan mendapat w:num sendiri dengan startOverride agar
    penomoran selalu mulai ulang. Memakai XML internal karena python-docx tidak memiliki
    API publik untuk numbering.
    """

    def __init__(self, doc: Any) -> None:
        self._root = doc.part.numbering_part.element
        self._abstracts: dict[tuple, int] = {}
        self._bullet_nums: dict[tuple, int] = {}

    def _next_id(self, tag: str, attr: str) -> int:
        ids = [int(e.get(qn(attr))) for e in self._root.findall(qn(tag))]
        return (max(ids) + 1) if ids else 1

    def _add_abstract(self, kind: str, step: int, hanging: int) -> int:
        abstract_id = self._next_id("w:abstractNum", "w:abstractNumId")
        levels = []
        for i in range(9):
            left = step * (i + 1)
            if kind == "bullet":
                fmt, text = "bullet", _BULLETS[i % 3]
                rpr = '<w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri" w:hint="default"/></w:rPr>'
            else:
                fmt, text, rpr = _ORDERED_FORMATS[i % 3], f"%{i + 1}.", ""
            levels.append(
                f'<w:lvl w:ilvl="{i}"><w:start w:val="1"/><w:numFmt w:val="{fmt}"/>'
                f'<w:lvlText w:val="{text}"/><w:lvlJc w:val="left"/>'
                f'<w:pPr><w:ind w:left="{left}" w:hanging="{hanging}"/></w:pPr>{rpr}</w:lvl>'
            )
        element = parse_xml(
            f'<w:abstractNum {nsdecls("w")} w:abstractNumId="{abstract_id}">'
            '<w:multiLevelType w:val="hybridMultilevel"/>' + "".join(levels) + "</w:abstractNum>"
        )
        first_num = self._root.find(qn("w:num"))
        if first_num is not None:
            first_num.addprevious(element)
        else:
            self._root.append(element)
        return abstract_id

    def _add_num(self, abstract_id: int, start: int | None = None) -> int:
        num_id = self._next_id("w:num", "w:numId")
        override = (
            f'<w:lvlOverride w:ilvl="0"><w:startOverride w:val="{start}"/></w:lvlOverride>' if start is not None else ""
        )
        self._root.append(
            parse_xml(f'<w:num {nsdecls("w")} w:numId="{num_id}"><w:abstractNumId w:val="{abstract_id}"/>{override}</w:num>')
        )
        return num_id

    def num_for(self, kind: str, step: int, hanging: int, start: int | None) -> int:
        key = (kind, step, hanging)
        if key not in self._abstracts:
            self._abstracts[key] = self._add_abstract(kind, step, hanging)
        if kind == "bullet":
            if key not in self._bullet_nums:
                self._bullet_nums[key] = self._add_num(self._abstracts[key])
            return self._bullet_nums[key]
        return self._add_num(self._abstracts[key], start)


def _add_hyperlink(paragraph: Any, text: str, url: str) -> Any:
    """Tambah hyperlink eksternal; mengembalikan proxy run untuk bold/italic."""
    part = paragraph.part
    r_id = part.relate_to(
        url,
        "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True,
    )
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)
    new_run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0563C1")
    rPr.append(color)
    u = OxmlElement("w:u")
    u.set(qn("w:val"), "single")
    rPr.append(u)
    new_run.append(rPr)
    t = OxmlElement("w:t")
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)

    class _RunProxy:
        def __init__(self, element: Any) -> None:
            self._r = element

        @property
        def bold(self) -> bool | None:
            return None

        @bold.setter
        def bold(self, value: bool) -> None:
            rPr = self._r.find(qn("w:rPr"))
            if rPr is None:
                rPr = OxmlElement("w:rPr")
                self._r.insert(0, rPr)
            existing = rPr.find(qn("w:b"))
            if value and existing is None:
                rPr.append(OxmlElement("w:b"))
            elif not value and existing is not None:
                rPr.remove(existing)

        @property
        def italic(self) -> bool | None:
            return None

        @italic.setter
        def italic(self, value: bool) -> None:
            rPr = self._r.find(qn("w:rPr"))
            if rPr is None:
                rPr = OxmlElement("w:rPr")
                self._r.insert(0, rPr)
            existing = rPr.find(qn("w:i"))
            if value and existing is None:
                rPr.append(OxmlElement("w:i"))
            elif not value and existing is not None:
                rPr.remove(existing)

        @property
        def underline(self) -> bool | None:
            return True

        @underline.setter
        def underline(self, value: bool) -> None:
            pass

        @property
        def font(self) -> Any:
            class F:
                name = None
                size = None
                color = type("C", (), {"rgb": None})()
            return F()

    return _RunProxy(new_run)


def _add_footnote_ref(paragraph: Any, note_id: int) -> Any:
    """Native Word footnote reference (w:footnoteReference)."""
    run = paragraph.add_run()
    r = run._r
    rPr = r.get_or_add_rPr()
    vert = OxmlElement("w:vertAlign")
    vert.set(qn("w:val"), "superscript")
    rPr.append(vert)
    ref = OxmlElement("w:footnoteReference")
    ref.set(qn("w:id"), str(note_id))
    r.append(ref)
    return run


def _build_footnotes_xml(footnotes: tuple) -> bytes:
    """Build word/footnotes.xml for native footnotes."""
    NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        f'<w:footnotes xmlns:w="{NS}">',
        # required separator + continuation separator
        '<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>',
        '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>',
    ]
    for fn in footnotes:
        # escape text
        body = (
            str(fn.text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        parts.append(
            f'<w:footnote w:id="{fn.note_id}">'
            f'<w:p>'
            f'<w:pPr><w:spacing w:after="0"/></w:pPr>'
            f'<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr>'
            f'<w:footnoteRef/></w:r>'
            f'<w:r><w:t xml:space="preserve"> {body}</w:t></w:r>'
            f'</w:p></w:footnote>'
        )
    parts.append("</w:footnotes>")
    return "".join(parts).encode("utf-8")


def _inject_native_footnotes(docx_bytes: bytes, footnotes: tuple) -> bytes:
    """Post-process DOCX zip: add footnotes.xml, content type, relationship."""
    if not footnotes:
        return docx_bytes
    import zipfile
    from io import BytesIO

    src = zipfile.ZipFile(BytesIO(docx_bytes), "r")
    out_buf = BytesIO()
    with zipfile.ZipFile(out_buf, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        rels_path = "word/_rels/document.xml.rels"
        ctypes_path = "[Content_Types].xml"
        for info in src.infolist():
            data = src.read(info.filename)
            if info.filename == ctypes_path:
                # ensure Override for footnotes
                if "footnotes" not in data.decode("utf-8", "replace"):
                    s = data.decode("utf-8")
                    s = s.replace(
                        "</Types>",
                        '<Override PartName="/word/footnotes.xml" '
                        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>'
                        "</Types>",
                    )
                    data = s.encode("utf-8")
            elif info.filename == rels_path:
                s = data.decode("utf-8")
                if "footnotes.xml" not in s:
                    # find max rId
                    import re
                    ids = [int(x) for x in re.findall(r'Id="rId(\d+)"', s)]
                    next_id = max(ids) + 1 if ids else 1
                    s = s.replace(
                        "</Relationships>",
                        f'<Relationship Id="rId{next_id}" '
                        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" '
                        'Target="footnotes.xml"/></Relationships>',
                    )
                    data = s.encode("utf-8")
            dst.writestr(info.filename, data)
        dst.writestr("word/footnotes.xml", _build_footnotes_xml(footnotes))
    src.close()
    return out_buf.getvalue()
