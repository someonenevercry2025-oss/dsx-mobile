"""Document IR: representasi dokumen yang sudah divalidasi dan bebas sintaks DSX."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Union

from ..diagnostics import Location
from ..mathexpr import Node as MathNode
from ..styles.registry import ResolvedStyle


@dataclass(frozen=True)
class Metadata:
    title: str = ""
    author: str = ""
    subject: str = ""
    template: str = "default"
    language: str | None = None


@dataclass(frozen=True)
class PageConfig:
    size_name: str
    orientation: str
    width_cm: float
    height_cm: float
    margin_top: float
    margin_bottom: float
    margin_left: float
    margin_right: float

    @property
    def content_width(self) -> float:
        return self.width_cm - self.margin_left - self.margin_right

    @property
    def content_height(self) -> float:
        return self.height_cm - self.margin_top - self.margin_bottom


@dataclass(frozen=True)
class TextSeg:
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    highlight: str | None = None


@dataclass(frozen=True)
class ImageSeg:
    """Gambar sebaris (mis. logo di dalam sel tabel)."""

    path: str
    data: bytes
    content_type: str
    width_cm: float = 2.2
    height_cm: float | None = None


@dataclass(frozen=True)
class MathSeg:
    """Persamaan sebaris di dalam alur paragraf."""

    expression: str
    tree: MathNode


@dataclass(frozen=True)
class LinkSeg:
    """Hyperlink sebaris."""

    text: str
    url: str
    bold: bool = False
    italic: bool = False
    underline: bool = False


@dataclass(frozen=True)
class FootnoteSeg:
    """Tanda referensi catatan kaki di dalam alur paragraf."""

    note_id: int  # 1-based
    text: str  # isi catatan


# Segment union extended after RefSeg/CiteSeg are defined (see below).
Segment = Union[TextSeg, MathSeg, LinkSeg, FootnoteSeg]  # provisional; reassigned later


@dataclass(frozen=True)
class HorizontalRule:
    style: str = "solid"  # solid|dashed|dotted|double|thick|wave
    width: str = "100%"
    thickness_pt: float = 1.0
    color: str = "000000"
    align: str = "center"
    space_before_pt: float = 6.0
    space_after_pt: float = 6.0
    page_break_before: bool = False
    source: Location | None = None


@dataclass(frozen=True)
class FormLine:
    """Garis isian formulir (titik/underscore) untuk nama, tanda tangan, dll."""
    count: int = 1
    style: str = "dots"  # dots|solid|dashed|underscore
    length: str = "40"  # char count or cm
    label: str = ""
    gap_pt: float = 6.0
    page_break_before: bool = False
    source: Location | None = None


@dataclass(frozen=True)
class TocBlock:
    """Daftar isi (field TOC Word)."""

    title: str
    depth: int
    page_break_before: bool = False
    source: Location | None = None


@dataclass(frozen=True)
class ListOfTablesBlock:
    title: str = "Daftar Tabel"
    page_break_before: bool = False
    source: Location | None = None


@dataclass(frozen=True)
class ListOfFiguresBlock:
    title: str = "Daftar Gambar"
    page_break_before: bool = False
    source: Location | None = None


@dataclass(frozen=True)
class ShapeBlock:
    shape_type: str  # rect|ellipse|line|roundRect
    width_cm: float = 5.0
    height_cm: float = 3.0
    fill: str | None = None
    stroke: str | None = "000000"
    stroke_width_pt: float = 1.0
    corner_cm: float = 0.3
    x1: float = 0.0
    y1: float = 0.0
    x2: float = 5.0
    y2: float = 0.0
    fill_image: "ImageAsset | None" = None
    align: str = "center"
    page_break_before: bool = False
    source: Location | None = None


@dataclass(frozen=True)
class CommentSeg:
    comment_id: int
    text: str
    author: str = "DSX"
    initials: str = ""


@dataclass(frozen=True)
class CommentDef:
    comment_id: int
    text: str
    author: str = "DSX"
    initials: str = ""


@dataclass(frozen=True)
class FootnoteDef:
    """Definisi catatan kaki (disimpan di DocumentIR)."""

    note_id: int
    text: str


@dataclass(frozen=True)
class Paragraph:
    text: str  # teks polos; pada paragraf bersegmen hanya gabungan segmen teks (tanpa matematika)
    role: str
    level: int | None
    style: str
    overrides: dict[str, Any] = field(default_factory=dict)
    effective: dict[str, Any] = field(default_factory=dict)
    source: Location | None = None
    segments: tuple[Segment, ...] = ()  # terisi hanya bila paragraf memuat matematika sebaris

    @property
    def is_heading(self) -> bool:
        return self.role == "heading"


@dataclass(frozen=True)
class TextBlock:
    paragraphs: tuple[Paragraph, ...]
    source: Location | None = None


@dataclass(frozen=True)
class ImageAsset:
    path: str
    data: bytes
    content_type: str


@dataclass(frozen=True)
class Figure:
    image: ImageAsset
    width_cm: float
    height_cm: float
    align: str
    alt: str
    caption: Paragraph | None
    page_break_before: bool = False
    source: Location | None = None
    label_id: str | None = None


@dataclass(frozen=True)
class TableCell:
    """Isi sel: teks polos atau segmen kaya. Mendukung merge dan border per sisi."""
    text: str
    segments: tuple = ()
    rowspan: int = 1
    colspan: int = 1
    merged: bool = False
    shading: str | None = None
    align: str | None = None
    valign: str | None = None
    borders: dict | None = None


@dataclass(frozen=True)
class Table:
    header: tuple[TableCell, ...] | None
    rows: tuple[tuple[TableCell, ...], ...]
    align: str
    caption: Paragraph | None
    page_break_before: bool = False
    source: Location | None = None
    label_id: str | None = None
    repeat_header: bool = True
    number_format: str | None = None
    col_widths: tuple[str, ...] | None = None
    keep_rows: bool = False
    autofit: bool = False
    border: str = "grid"  # none|single|double|dashed|dotted|grid|bottom|top|outer
    border_width_pt: float = 0.5
    border_color: str = "000000"
    # Optional per-side overrides: side -> {style, color, width_pt}
    # Sides: top, bottom, left, right, insideH, insideV
    border_sides: dict | None = None
    header_shading: str | None = "D9D9D9"
    cell_padding_cm: float | None = None
    row_height_cm: float | None = None

    @property
    def column_count(self) -> int:
        if self.header is not None:
            return sum(c.colspan for c in self.header)
        if self.rows:
            return sum(c.colspan for c in self.rows[0])
        return 0

    @property
    def row_count(self) -> int:
        return len(self.rows) + (1 if self.header is not None else 0)


@dataclass(frozen=True)
class HeaderFooter:
    text: str
    style: str
    overrides: dict[str, Any]
    distance_cm: float | None = None


@dataclass(frozen=True)
class PageNumber:
    position: str
    format: str
    style: str
    overrides: dict[str, Any]
    number_format: str = "decimal"
    align: str = "center"
    placement: str | None = None
    start: int | None = None
    show: bool = True


@dataclass(frozen=True)
class ListItem:
    text: str  # plain fallback / expected_structure
    level: int  # 0 = tingkat teratas
    continuations: tuple[str, ...] = ()  # paragraf lanjutan plain (tanpa nomor/bullet)
    segments: tuple = ()  # Segment... bila item memuat format sebaris / IMATH


@dataclass(frozen=True)
class ListBlock:
    items: tuple[ListItem, ...]
    ordered: bool
    start: int
    style: str
    overrides: dict[str, Any]
    effective: dict[str, Any]
    page_break_before: bool = False
    source: Location | None = None
    indent_cm: float = 1.0  # tambahan indentasi kiri per tingkat
    hanging_cm: float = 0.7  # lebar area nomor/bullet


@dataclass(frozen=True)
class Callout:
    variant: str
    title: Paragraph | None
    body: tuple[Paragraph, ...]
    page_break_before: bool = False
    source: Location | None = None


@dataclass(frozen=True)
class MathBlock:
    expression: str
    tree: MathNode
    align: str
    size: float | None
    style: str
    overrides: dict[str, Any]
    effective: dict[str, Any]
    page_break_before: bool = False
    source: Location | None = None
    label_id: str | None = None


@dataclass(frozen=True)
class CodeBlock:
    """Blok kode monospace dengan background."""
    text: str
    language: str
    caption: Paragraph | None
    line_numbers: bool
    style: str
    overrides: dict[str, Any]
    effective: dict[str, Any]
    page_break_before: bool = False
    source: Location | None = None
    label_id: str | None = None


@dataclass(frozen=True)
class ChartBlock:
    """Grafik yang digenerate (PNG) lalu di-embed seperti FIGURE."""
    image: ImageAsset
    width_cm: float
    height_cm: float
    align: str
    chart_type: str
    title: str
    caption: Paragraph | None
    page_break_before: bool = False
    source: Location | None = None
    label_id: str | None = None


@dataclass(frozen=True)
class LabelMarker:
    """Penanda label silang-referensi (tidak menghasilkan output visual sendiri)."""
    label_id: str
    kind: str  # figure | table | equation | section | chart | code
    source: Location | None = None


@dataclass(frozen=True)
class BibliographyBlock:
    title: str
    style_name: str  # simple | apa | ieee
    items: tuple[dict[str, str], ...]  # from BIBITEM
    page_break_before: bool = False
    source: Location | None = None


@dataclass(frozen=True)
class SectionBreak:
    """Pemisah section dengan konfigurasi halaman/penomoran."""
    break_type: str  # next_page | continuous | even_page | odd_page
    orientation: str | None = None
    page_size: str | None = None
    mirror_margins: bool = False
    gutter_cm: float = 0.0
    page_number_format: str | None = None
    page_number_start: int | None = None
    page_number_restart: bool = False
    show_page_number: bool = True
    columns: int = 1
    column_gap_cm: float = 0.5
    title: str = ""
    margin_top: float | None = None
    margin_bottom: float | None = None
    margin_left: float | None = None
    margin_right: float | None = None
    header_text: str | None = None
    footer_text: str | None = None
    different_first_page: bool = False
    page_number_align: str = "center"
    page_number_position: str = "footer"
    page_number_placement: str | None = None  # top_left ... bottom_right
    page_number_format_text: str | None = None
    page_number_continue: bool = False
    header_distance_cm: float | None = None
    footer_distance_cm: float | None = None
    odd_even_header: bool = False
    header_odd: str | None = None
    header_even: str | None = None
    footer_odd: str | None = None
    footer_even: str | None = None
    page_break_before: bool = False
    source: Location | None = None


@dataclass(frozen=True)
class ColumnsStart:
    count: int
    gap_cm: float
    page_break_before: bool = False
    source: Location | None = None


@dataclass(frozen=True)
class ColumnsEnd:
    page_break_before: bool = False
    source: Location | None = None


@dataclass(frozen=True)
class Watermark:
    text: str
    opacity: float
    angle: float
    size_pt: float
    color: str


@dataclass(frozen=True)
class RefSeg:
    """Referensi silang sebaris (ditampilkan sebagai teks yang di-resolve)."""
    label_id: str
    display: str  # resolved text e.g. "Gambar 1"


@dataclass(frozen=True)
class CiteSeg:
    """Sitasi sebaris."""
    key: str
    display: str  # e.g. "[1]" or "(Smith, 2024)"
    pages: str = ""


# Extend Segment union
Segment = Union[TextSeg, MathSeg, LinkSeg, FootnoteSeg, RefSeg, CiteSeg, CommentSeg]


Block = Union[
    Paragraph, TextBlock, Figure, Table, ListBlock, Callout, MathBlock, TocBlock,
    CodeBlock, ChartBlock, LabelMarker, BibliographyBlock, ColumnsStart, ColumnsEnd, SectionBreak,
    HorizontalRule, FormLine, ShapeBlock, ListOfTablesBlock, ListOfFiguresBlock,
]


@dataclass(frozen=True)
class DocumentIR:
    metadata: Metadata
    page: PageConfig
    styles: dict[str, ResolvedStyle]
    blocks: tuple[Block, ...]
    header: HeaderFooter | None = None
    footer: HeaderFooter | None = None
    page_number: PageNumber | None = None
    footnotes: tuple[FootnoteDef, ...] = ()
    comments: tuple[CommentDef, ...] = ()
    source_name: str = "document.dsx"
    labels: dict[str, str] = field(default_factory=dict)  # id -> display text
    bib_items: tuple[dict[str, str], ...] = ()
    watermark: Watermark | None = None

    def iter_paragraphs(self):
        for block in self.blocks:
            if isinstance(block, Paragraph):
                yield block
            elif isinstance(block, TextBlock):
                yield from block.paragraphs
            elif isinstance(block, Figure) and block.caption is not None:
                yield block.caption
            elif isinstance(block, Table) and block.caption is not None:
                yield block.caption
            elif isinstance(block, Callout):
                if block.title is not None:
                    yield block.title
                yield from block.body

    def expected_structure(self) -> list[tuple]:
        """Urutan elemen body yang diharapkan pada keluaran DOCX.

        Aturan renderer: caption tabel di atas tabel, caption gambar di bawah
        gambar, dan satu paragraf pemisah kosong setelah setiap tabel.
        """
        out: list[tuple] = []
        for block in self.blocks:
            if isinstance(block, Paragraph):
                text = block.text
                if block.segments:
                    parts = []
                    for s in block.segments:
                        if isinstance(s, TextSeg):
                            parts.append(s.text)
                        elif isinstance(s, LinkSeg):
                            parts.append(s.text)
                        elif isinstance(s, FootnoteSeg):
                            parts.append("")  # native footnoteReference has no plain text
                        elif isinstance(s, (RefSeg, CiteSeg)):
                            parts.append(s.display)
                        # MathSeg: no plain text contribution
                    text = "".join(parts)
                out.append(("p", text, block.level if block.is_heading else None))
            elif isinstance(block, TextBlock):
                for p in block.paragraphs:
                    out.append(("p", p.text, p.level if p.is_heading else None))
            elif isinstance(block, Figure):
                out.append(("figure",))
                if block.caption is not None:
                    out.append(("p", block.caption.text, None))
            elif isinstance(block, HorizontalRule):
                out.append(("p", None, None))
            elif isinstance(block, FormLine):
                for _ in range(max(1, block.count)):
                    out.append(("p", None, None))
            elif isinstance(block, Table):
                if block.caption is not None:
                    out.append(("p", block.caption.text, None))
                out.append(("tbl", block.row_count, block.column_count))
                out.append(("spacer",))
            elif isinstance(block, ListBlock):
                for item in block.items:
                    out.append(("li", item.text, item.level, block.ordered))
                    for extra in item.continuations:
                        out.append(("p", extra, None))
            elif isinstance(block, Callout):
                count = len(block.body) + (1 if block.title is not None else 0)
                out.append(("callout", block.variant, count))
                out.append(("spacer",))
            elif isinstance(block, MathBlock):
                out.append(("math",))
            elif isinstance(block, TocBlock):
                if block.title:
                    out.append(("p", block.title, None))
                # TOC field body: heading preview (dynamic) — use wildcard text
                out.append(("p", None, None))
                out.append(("p", "", None))  # spacer
            elif isinstance(block, CodeBlock):
                if block.caption is not None:
                    out.append(("p", block.caption.text, None))
                for _ in (block.text.split(chr(10)) if block.text else [""]):
                    out.append(("p", None, None))
                out.append(("p", "", None))
            elif isinstance(block, ShapeBlock):
                if block.page_break_before:
                    out.append(("p", None, None))
                out.append(("figure",))
            elif isinstance(block, ChartBlock):
                out.append(("figure",))
                if block.caption is not None:
                    out.append(("p", block.caption.text, None))
            elif isinstance(block, BibliographyBlock):
                out.append(("p", block.title, None))
                items = block.items
                for _ in items:
                    out.append(("p", None, None))
            elif isinstance(block, LabelMarker):
                pass
            elif isinstance(block, ColumnsStart):
                out.append(("p", None, None))  # continuous section break
            elif isinstance(block, ColumnsEnd):
                out.append(("p", None, None))  # restore single-column section
            elif isinstance(block, SectionBreak):
                # python-docx add_section() leaves a section-break paragraph in body
                out.append(("p", None, None))
        # Native footnotes live in word/footnotes.xml — not body paragraphs.
        if not out:
            out.append(("p", "", None))  # dokumen kosong dirender dengan satu paragraf kosong
        return out

    def inline_math_count(self) -> int:
        n = sum(1 for p in self.iter_paragraphs() for s in p.segments if isinstance(s, MathSeg))
        for block in self.blocks:
            if isinstance(block, ListBlock):
                for item in block.items:
                    n += sum(1 for s in item.segments if isinstance(s, MathSeg))
            elif isinstance(block, Table):
                cells = []
                if block.header:
                    cells.extend(block.header)
                for row in block.rows:
                    cells.extend(row)
                n += sum(1 for c in cells for s in c.segments if isinstance(s, MathSeg))
        return n

    def summary(self) -> dict[str, int]:
        paragraphs = list(self.iter_paragraphs())
        return {
            "paragraphs": len(paragraphs),
            "headings": sum(1 for p in paragraphs if p.is_heading),
            "figures": sum(1 for b in self.blocks if isinstance(b, (Figure, ChartBlock))),
            "tables": sum(1 for b in self.blocks if isinstance(b, Table)),
            "lists": sum(1 for b in self.blocks if isinstance(b, ListBlock)),
            "list_items": sum(len(b.items) for b in self.blocks if isinstance(b, ListBlock)),
            "callouts": sum(1 for b in self.blocks if isinstance(b, Callout)),
            "equations": sum(1 for b in self.blocks if isinstance(b, MathBlock)),
            "inline_equations": self.inline_math_count(),
            "tocs": sum(1 for b in self.blocks if isinstance(b, TocBlock)),
            "footnotes": len(self.footnotes),
            "styles": len(self.styles),
        }
