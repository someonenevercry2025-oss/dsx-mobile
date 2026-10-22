"""Skema komponen dan properti DSX.

Satuan (Blueprint IV/VII.3):
- size, space_before, space_after : point (pt)
- indent_*, margin, width, height : sentimeter (cm)
- line                            : pengali jarak baris (1.0 = tunggal)
"""

from __future__ import annotations

from dataclasses import dataclass

ROLES = ("body", "heading", "title", "subtitle", "caption", "quote", "note", "warning", "code", "callout")
CALLOUT_TYPES = ("info", "note", "warning", "tip", "important")
ALIGNS = ("left", "center", "right", "justify")
BLOCK_ALIGNS = ("left", "center", "right")
PAGE_SIZES = {
    "A3": (29.7, 42.0),
    "A4": (21.0, 29.7),
    "A5": (14.8, 21.0),
    "Letter": (21.59, 27.94),
    "Legal": (21.59, 35.56),
}
VISUAL_KEYS = (
    "font",
    "size",
    "bold",
    "italic",
    "underline",
    "color",
    "align",
    "line",
    "space_before",
    "space_after",
    "indent_left",
    "indent_right",
    "indent_first",
    "page_break_before",
)
SUPPORTED_VERSIONS = ("2.1", "2.2", "2.3", "2.4", "2.5", "2.6")
CHART_TYPES = ("bar", "line", "pie", "scatter", "area", "hbar")
CODE_LANGUAGES = (
    "plain", "python", "js", "javascript", "typescript", "ts", "java", "c", "cpp",
    "csharp", "go", "rust", "ruby", "php", "sql", "html", "css", "json", "yaml",
    "xml", "bash", "shell", "sh", "r", "matlab", "latex", "markdown", "md",
)


@dataclass(frozen=True)
class ParamSpec:
    name: str
    type: str
    required: bool = False
    positional: bool = False
    choices: tuple[str, ...] = ()
    min: float | None = None
    max: float | None = None
    step: float | None = None
    code: str | None = None
    max_len: int | None = None
    unit: str | None = None  # satuan dasar bila param menerima angka bersatuan: pt | cm


@dataclass(frozen=True)
class Spec:
    name: str
    category: str  # meta | styledef | content | value
    params: tuple[ParamSpec, ...]
    visual: bool = False

    def all_params(self) -> dict[str, ParamSpec]:
        merged: dict[str, ParamSpec] = {}
        if self.visual:
            merged.update({p.name: p for p in VISUAL_PARAMS})
        merged.update({p.name: p for p in self.params})
        return merged


def _p(name: str, type_: str, **kw: object) -> ParamSpec:
    return ParamSpec(name, type_, **kw)  # type: ignore[arg-type]


# Nama alternatif (selaras dengan istilah paragraf umum) -> nama kanonik.
ALIASES = {
    "first_line_indent": "indent_first",
    "left_indent": "indent_left",
    "right_indent": "indent_right",
    "line_spacing": "line",
    "alignment": "align",
}

VISUAL_PARAMS: tuple[ParamSpec, ...] = (
    _p("font", "font"),
    _p("size", "num", min=1, max=400, step=0.5, unit="pt"),
    _p("bold", "bool"),
    _p("italic", "bool"),
    _p("underline", "bool"),
    _p("color", "color"),
    _p("align", "enum_ci", choices=ALIGNS),
    _p("line", "num", min=0.5, max=10),
    _p("space_before", "num", min=0, max=1000, unit="pt"),
    _p("space_after", "num", min=0, max=1000, unit="pt"),
    _p("indent_left", "num", min=-50, max=50, unit="cm"),
    _p("indent_right", "num", min=-50, max=50, unit="cm"),
    _p("indent_first", "num", min=-50, max=50, unit="cm"),
    _p("hanging_indent", "num", min=0, max=50, unit="cm"),  # diterjemahkan menjadi indent_first negatif
    _p("page_break_before", "bool"),
)

SPECS: dict[str, Spec] = {}


def _add(name: str, category: str, params: list[ParamSpec], visual: bool = False) -> None:
    SPECS[name] = Spec(name, category, tuple(params), visual)


_MARGIN = dict(min=0, max=10, unit="cm")

_add("DSX", "meta", [_p("version", "str", max_len=20)])
_add(
    "DOC",
    "meta",
    [
        _p("title", "str", max_len=1000),
        _p("template", "str", max_len=100),
        _p("author", "str", max_len=1000),
        _p("subject", "str", max_len=1000),
        _p("language", "str", max_len=35),
    ],
)
_add(
    "PAGE",
    "meta",
    [
        _p("size", "enum", choices=tuple(PAGE_SIZES)),
        _p("orientation", "enum", choices=("portrait", "landscape")),
        _p("mirror_margins", "bool"),
        _p("gutter", "num", min=0, max=5, unit="cm"),
        _p("margin", "num", **_MARGIN),
        _p("margin_top", "num", **_MARGIN),
        _p("margin_bottom", "num", **_MARGIN),
        _p("margin_left", "num", **_MARGIN),
        _p("margin_right", "num", **_MARGIN),
    ],
)
_add("STYLE", "meta", [], visual=True)
_add(
    "STYLEDEF",
    "styledef",
    [
        _p("name", "name", required=True, positional=True),
        _p("extends", "str", max_len=64),
        _p("role", "enum", choices=ROLES),
        _p("level", "int", min=1, max=9, code="INVALID_HEADING_LEVEL"),
    ],
    visual=True,
)
_add("HEADER", "meta", [
    _p("text", "str", required=True, positional=True, max_len=2000),
    _p("style", "str", max_len=64),
    _p("distance", "num", min=0, max=10, unit="cm"),
], visual=True)
_add("FOOTER", "meta", [
    _p("text", "str", required=True, positional=True, max_len=2000),
    _p("style", "str", max_len=64),
    _p("distance", "num", min=0, max=10, unit="cm"),
], visual=True)
_add(
    "PAGENUM",
    "meta",
    [
        _p("position", "enum", choices=("header", "footer")),
        _p("format", "str", max_len=200),
        _p("number_format", "enum_ci", choices=("decimal", "lower_roman", "upper_roman", "lower_letter", "upper_letter")),
        _p("align", "enum_ci", choices=("left", "center", "right")),
        _p("placement", "enum_ci", choices=(
            "top_left", "top_center", "top_right",
            "bottom_left", "bottom_center", "bottom_right",
        )),
        _p("preset", "enum_ci", choices=(
            "top_left", "top_center", "top_right",
            "bottom_left", "bottom_center", "bottom_right",
            "academic_footer", "academic_header",
        )),
        _p("start", "int", min=0, max=99999),
        _p("show", "bool"),
        _p("style", "str", max_len=64),
    ],
    visual=True,
)
_add(
    "PRESET",
    "meta",
    [
        _p("name", "enum_ci", required=True, positional=True, choices=(
            "makalah", "skripsi", "laporan", "praktikum", "artikel",
            # numbering / structure aliases
            "academic_front_roman", "academic_body_decimal",
        )),
        _p("numbering", "enum_ci", choices=(
            "roman_then_decimal", "decimal_only", "none",
        )),
        _p("page_number_placement", "enum_ci", choices=(
            "top_left", "top_center", "top_right",
            "bottom_left", "bottom_center", "bottom_right",
        )),
    ],
)
_add(
    "STRUCTURE",
    "meta",
    [
        _p("name", "enum_ci", required=True, positional=True, choices=(
            "makalah", "skripsi", "laporan", "praktikum", "artikel",
        )),
        _p("expand", "bool"),  # if true, inject outline headings when body empty of H1
    ],
)
_add(
    "SECTION",
    "content",
    [
        _p("break", "enum_ci", choices=("next_page", "continuous", "even_page", "odd_page")),
        _p("type", "enum_ci", choices=("next_page", "continuous", "even_page", "odd_page")),
        _p("orientation", "enum", choices=("portrait", "landscape")),
        _p("size", "enum", choices=tuple(PAGE_SIZES)),
        _p("mirror_margins", "bool"),
        _p("gutter", "num", min=0, max=5, unit="cm"),
        _p("page_number_format", "enum_ci", choices=("decimal", "lower_roman", "upper_roman", "lower_letter", "upper_letter")),
        _p("page_number_start", "int", min=0, max=99999),
        _p("page_number_restart", "bool"),
        _p("show_page_number", "bool"),
        _p("columns", "int", min=1, max=4),
        _p("column_gap", "num", min=0.2, max=5, unit="cm"),
        _p("title", "str", max_len=200),
        _p("margin", "num", min=0, max=10, unit="cm"),
        _p("margin_top", "num", min=0, max=10, unit="cm"),
        _p("margin_bottom", "num", min=0, max=10, unit="cm"),
        _p("margin_left", "num", min=0, max=10, unit="cm"),
        _p("margin_right", "num", min=0, max=10, unit="cm"),
        _p("header", "str", max_len=2000),
        _p("footer", "str", max_len=2000),
        _p("different_first_page", "bool"),
        _p("page_number_align", "enum_ci", choices=("left", "center", "right")),
        _p("page_number_position", "enum", choices=("header", "footer")),
        _p("page_number_placement", "enum_ci", choices=(
            "top_left", "top_center", "top_right",
            "bottom_left", "bottom_center", "bottom_right",
        )),
        _p("page_number_format_text", "str", max_len=200),
        _p("page_number_continue", "bool"),  # true = lanjut (abaikan start), false/default+start = restart
        _p("header_distance", "num", min=0, max=10, unit="cm"),
        _p("footer_distance", "num", min=0, max=10, unit="cm"),
        _p("odd_even_header", "bool"),
        _p("header_odd", "str", max_len=2000),
        _p("header_even", "str", max_len=2000),
        _p("footer_odd", "str", max_len=2000),
        _p("footer_even", "str", max_len=2000),
    ],
)

_TEXT_STYLE = [_p("style", "str", max_len=64)]
_add(
    "TEXT",
    "content",
    [
        _p("text", "richtext", required=True, positional=True),
        _p("role", "enum", choices=ROLES),
        _p("level", "int", min=1, max=9, code="INVALID_HEADING_LEVEL"),
        *_TEXT_STYLE,
    ],
    visual=True,
)
_add("P", "content", [_p("text", "richtext", required=True, positional=True), *_TEXT_STYLE], visual=True)
for _n in range(1, 10):
    _add(f"H{_n}", "content", [_p("text", "richtext", required=True, positional=True), *_TEXT_STYLE], visual=True)
_add(
    "TEXTBLOCK",
    "content",
    [
        _p("text", "text", required=True, positional=True),
        _p("role", "enum", choices=ROLES),
        _p("level", "int", min=1, max=9, code="INVALID_HEADING_LEVEL"),
        *_TEXT_STYLE,
    ],
    visual=True,
)
_add(
    "FIGURE",
    "content",
    [
        _p("src", "image", required=True),
        _p("caption", "str", max_len=5000),
        _p("width", "num", min=0.1, max=100, unit="cm"),
        _p("height", "num", min=0.1, max=100, unit="cm"),
        _p("align", "enum_ci", choices=BLOCK_ALIGNS),
        _p("alt", "str", max_len=2000),
        _p("caption_style", "str", max_len=64),
        _p("id", "str", max_len=64),
    ],
)
_add(
    "TABLE",
    "content",
    [
        _p("headers", "header_row"),
        _p("rows", "rows"),
        _p("data", "csv"),
        _p("header", "bool"),
        _p("caption", "str", max_len=5000),
        _p("align", "enum_ci", choices=BLOCK_ALIGNS),
        _p("caption_style", "str", max_len=64),
        _p("id", "str", max_len=64),
        _p("labels", "strlist"),
        _p("repeat_header", "bool"),
        _p("number_format", "str", max_len=40),  # thousands|percent|decimal:N|currency|currency:IDR|currency:USD
        _p("widths", "strlist"),
        _p("keep_rows", "bool"),
        _p("autofit", "bool"),
        # Preset: none | single (outer only) | double | dashed | dotted | grid | bottom | top | outer
        _p("border", "enum_ci", choices=(
            "none", "single", "double", "dashed", "dotted", "grid",
            "bottom", "top", "outer",
        )),
        _p("border_width", "num", min=0.25, max=12, unit="pt"),
        _p("border_color", "str", max_len=20),
        # Selective sides at TABLE level (override preset when any is set)
        _p("border_top", "enum_ci", choices=("none", "single", "double", "dashed", "dotted", "thick")),
        _p("border_bottom", "enum_ci", choices=("none", "single", "double", "dashed", "dotted", "thick")),
        _p("border_left", "enum_ci", choices=("none", "single", "double", "dashed", "dotted", "thick")),
        _p("border_right", "enum_ci", choices=("none", "single", "double", "dashed", "dotted", "thick")),
        _p("border_inside_h", "enum_ci", choices=("none", "single", "double", "dashed", "dotted", "thick")),
        _p("border_inside_v", "enum_ci", choices=("none", "single", "double", "dashed", "dotted", "thick")),
        _p("border_top_color", "str", max_len=20),
        _p("border_bottom_color", "str", max_len=20),
        _p("border_left_color", "str", max_len=20),
        _p("border_right_color", "str", max_len=20),
        _p("border_inside_h_color", "str", max_len=20),
        _p("border_inside_v_color", "str", max_len=20),
        _p("border_top_width", "num", min=0.25, max=12, unit="pt"),
        _p("border_bottom_width", "num", min=0.25, max=12, unit="pt"),
        _p("border_left_width", "num", min=0.25, max=12, unit="pt"),
        _p("border_right_width", "num", min=0.25, max=12, unit="pt"),
        _p("border_inside_h_width", "num", min=0.25, max=12, unit="pt"),
        _p("border_inside_v_width", "num", min=0.25, max=12, unit="pt"),
        _p("header_shading", "str", max_len=20),
        _p("cell_padding", "num", min=0, max=2, unit="cm"),
        _p("row_height", "num", min=0.3, max=20, unit="cm"),
    ],
)
_add(
    "CELL",
    "value",
    [
        _p("text", "richtext", required=True, positional=True),
        _p("rowspan", "int", min=1, max=50),
        _p("colspan", "int", min=1, max=50),
        _p("shading", "str", max_len=20),
        _p("align", "enum_ci", choices=("left", "center", "right", "justify")),
        _p("valign", "enum_ci", choices=("top", "center", "bottom")),
        _p("border_top", "enum_ci", choices=("none", "single", "double", "dashed", "dotted", "thick")),
        _p("border_bottom", "enum_ci", choices=("none", "single", "double", "dashed", "dotted", "thick")),
        _p("border_left", "enum_ci", choices=("none", "single", "double", "dashed", "dotted", "thick")),
        _p("border_right", "enum_ci", choices=("none", "single", "double", "dashed", "dotted", "thick")),
        _p("border_top_color", "str", max_len=20),
        _p("border_bottom_color", "str", max_len=20),
        _p("border_left_color", "str", max_len=20),
        _p("border_right_color", "str", max_len=20),
        _p("border_top_width", "num", min=0.25, max=12, unit="pt"),
        _p("border_bottom_width", "num", min=0.25, max=12, unit="pt"),
        _p("border_left_width", "num", min=0.25, max=12, unit="pt"),
        _p("border_right_width", "num", min=0.25, max=12, unit="pt"),
        _p("border_style", "enum_ci", choices=("none", "single", "double", "dashed", "dotted", "thick")),
        _p("border_color", "str", max_len=20),
        _p("border_width", "num", min=0.25, max=12, unit="pt"),
    ],
)
_add("PAGEBREAK", "content", [])
_add(
    "HR",
    "content",
    [
        _p("style", "enum_ci", choices=("solid", "dashed", "dotted", "double", "thick", "wave")),
        _p("width", "str", max_len=20),
        _p("thickness", "num", min=0.25, max=12, unit="pt"),
        _p("color", "str", max_len=20),
        _p("align", "enum_ci", choices=BLOCK_ALIGNS),
        _p("space_before", "num", min=0, max=72, unit="pt"),
        _p("space_after", "num", min=0, max=72, unit="pt"),
    ],
    visual=True,
)
_add(
    "LINE",
    "content",
    [
        _p("count", "int", min=1, max=30),
        _p("style", "enum_ci", choices=("dots", "solid", "dashed", "underscore")),
        _p("length", "str", max_len=20),
        _p("label", "str", max_len=200),
        _p("gap", "num", min=0, max=36, unit="pt"),
    ],
    visual=True,
)
_add(
    "CALLOUT",
    "content",
    [
        _p("text", "richtext", required=True, positional=True),
        _p("type", "enum_ci", choices=CALLOUT_TYPES),
        _p("title", "str", max_len=500),
        *_TEXT_STYLE,
    ],
    visual=True,
)
_add(
    "LIST",
    "content",
    [
        _p("items", "items", required=True, positional=True),
        _p("ordered", "bool"),
        _p("start", "int", min=1, max=100000),
        _p("indent", "num", min=0.25, max=5, unit="cm"),
        _p("hanging", "num", min=0.1, max=3, unit="cm"),
        *_TEXT_STYLE,
    ],
    visual=True,
)
_add(
    "BULLET",
    "content",
    [
        _p("items", "items", required=True, positional=True),
        _p("indent", "num", min=0.25, max=5, unit="cm"),
        _p("hanging", "num", min=0.1, max=3, unit="cm"),
        *_TEXT_STYLE,
    ],
    visual=True,
)
_add(
    "MATH",
    "content",
    [
        _p("expr", "math", required=True, positional=True),
        _p("align", "enum_ci", choices=BLOCK_ALIGNS),
        _p("size", "num", min=6, max=72, step=0.5, unit="pt"),
        _p("id", "str", max_len=64),
    ],
)

_add("FILE", "value", [_p("path", "str", required=True, positional=True)])
_add("IMAGE", "value", [_p("path", "str", required=True, positional=True)])
_add("IMATH", "value", [_p("expr", "math", required=True, positional=True)])
_add("CSV", "value", [_p("path", "str", required=True, positional=True), _p("delimiter", "str", max_len=1)])
_add("BOLD", "value", [_p("text", "str", required=True, positional=True, max_len=5000)])
_add("ITALIC", "value", [_p("text", "str", required=True, positional=True, max_len=5000)])
_add("UNDERLINE", "value", [_p("text", "str", required=True, positional=True, max_len=5000)])
_add(
    "HIGHLIGHT",
    "value",
    [
        _p("text", "str", required=True, positional=True, max_len=5000),
        _p("color", "str", max_len=20),
    ],
)
_add(
    "COMMENT",
    "value",
    [
        _p("text", "str", required=True, positional=True, max_len=5000),
        _p("author", "str", max_len=100),
        _p("initials", "str", max_len=10),
    ],
)
_add(
    "LINK",
    "value",
    [
        _p("text", "str", required=True, positional=True, max_len=2000),
        _p("url", "str", required=True, positional=True, max_len=2000),
    ],
)
_add("FOOTNOTE", "value", [_p("text", "str", required=True, positional=True, max_len=5000)])
_add(
    "TOC",
    "content",
    [
        _p("title", "str", max_len=200),
        _p("depth", "int", min=1, max=9),
    ],
)
_add(
    "LISTOFTABLES",
    "content",
    [
        _p("title", "str", max_len=200),
    ],
)
_add(
    "LISTOFFIGURES",
    "content",
    [
        _p("title", "str", max_len=200),
    ],
)
_add(
    "SHAPE",
    "content",
    [
        _p("type", "enum_ci", choices=("rect", "ellipse", "line", "roundRect"), required=True, positional=True),
        _p("width", "num", min=0.1, max=30, unit="cm"),
        _p("height", "num", min=0.1, max=30, unit="cm"),
        _p("fill", "str", max_len=20),
        _p("stroke", "str", max_len=20),
        _p("stroke_width", "num", min=0, max=12, unit="pt"),
        _p("corner", "num", min=0, max=5, unit="cm"),
        _p("x1", "num", min=0, max=30, unit="cm"),
        _p("y1", "num", min=0, max=30, unit="cm"),
        _p("x2", "num", min=0, max=30, unit="cm"),
        _p("y2", "num", min=0, max=30, unit="cm"),
        _p("fill_image", "image"),
        _p("align", "enum_ci", choices=BLOCK_ALIGNS),
    ],
)

# --- v0.5 / language 2.5 -------------------------------------------------
_add(
    "CODE",
    "content",
    [
        _p("text", "text", required=True, positional=True),
        _p("lang", "enum_ci", choices=CODE_LANGUAGES),
        _p("language", "enum_ci", choices=CODE_LANGUAGES),  # alias
        _p("caption", "str", max_len=500),
        _p("line_numbers", "bool"),
        *_TEXT_STYLE,
    ],
)
_add(
    "CHART",
    "content",
    [
        _p("type", "enum_ci", choices=CHART_TYPES, required=True),
        _p("data", "csv"),
        _p("x", "str", max_len=200),
        _p("y", "str", max_len=200),
        _p("series", "strlist"),
        _p("title", "str", max_len=500),
        _p("xlabel", "str", max_len=200),
        _p("ylabel", "str", max_len=200),
        _p("caption", "str", max_len=5000),
        _p("width", "num", min=0.1, max=100, unit="cm"),
        _p("height", "num", min=0.1, max=100, unit="cm"),
        _p("align", "enum_ci", choices=BLOCK_ALIGNS),
        _p("caption_style", "str", max_len=64),
        _p("id", "str", max_len=64),  # for cross-ref
    ],
)
_add(
    "LABEL",
    "content",
    [
        _p("id", "str", required=True, positional=True, max_len=64),
        _p("kind", "enum_ci", choices=("figure", "table", "equation", "section", "chart", "code")),
    ],
)
_add(
    "REF",
    "value",
    [
        _p("id", "str", required=True, positional=True, max_len=64),
        _p("text", "str", max_len=200),  # override display text
    ],
)
_add(
    "CITE",
    "value",
    [
        _p("key", "str", required=True, positional=True, max_len=64),
        _p("pages", "str", max_len=40),
    ],
)
_add(
    "BIBLIOGRAPHY",
    "content",
    [
        _p("title", "str", max_len=200),
        _p("style", "enum_ci", choices=("simple", "apa", "ieee")),
    ],
)
_add(
    "BIBITEM",
    "meta",
    [
        _p("key", "str", required=True, positional=True, max_len=64),
        _p("author", "str", max_len=500),
        _p("title", "str", max_len=1000),
        _p("year", "str", max_len=20),
        _p("publisher", "str", max_len=500),
        _p("journal", "str", max_len=500),
        _p("url", "str", max_len=2000),
        _p("volume", "str", max_len=40),
        _p("pages", "str", max_len=40),
    ],
)
_add(
    "COLUMNS",
    "content",
    [
        _p("count", "int", required=True, positional=True, min=2, max=4),
        _p("gap", "num", min=0.2, max=5, unit="cm"),
    ],
)
_add(
    "ENDCOLUMNS",
    "content",
    [],
)
_add(
    "WATERMARK",
    "meta",
    [
        _p("text", "str", required=True, positional=True, max_len=100),
        _p("opacity", "num", min=0.05, max=0.5),
        _p("angle", "num", min=-90, max=90),
        _p("size", "num", min=12, max=120, unit="pt"),
        _p("color", "color"),
    ],
)

# Extend TABLE with merge / id support (optional params; existing still valid)
# (params already defined; builder accepts extra keys via rows structure)

VALUE_FUNCTIONS = (
    "FILE",
    "IMAGE",
    "CSV",
    "IMATH",
    "BOLD",
    "ITALIC",
    "UNDERLINE",
    "HIGHLIGHT",
    "LINK",
    "FOOTNOTE",
    "COMMENT",
    "REF",
    "CITE",
    "CELL",
)
RESERVED_NAMES = frozenset({"LET", "true", "false"} | set(SPECS))
HIGHLIGHT_COLORS = (
    "yellow", "green", "cyan", "magenta", "blue", "red",
    "darkBlue", "darkCyan", "darkGreen", "darkMagenta", "darkRed",
    "darkYellow", "darkGray", "lightGray", "black",
)
