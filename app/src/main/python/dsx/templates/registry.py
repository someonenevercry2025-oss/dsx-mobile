"""Template: konfigurasi lapisan kedua (setelah default engine)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Template:
    name: str
    normal: dict[str, Any] = field(default_factory=dict)
    styles: dict[str, dict[str, Any]] = field(default_factory=dict)
    page: dict[str, Any] = field(default_factory=dict)


_HEADING_COLOR = "#1F3864"

TEMPLATES: dict[str, Template] = {
    "default": Template("default"),
    "academic-paper": Template(
        "academic-paper",
        normal={"font": "Times New Roman", "size": 12, "line": 1.5, "align": "justify", "space_after": 6},
        styles={
            "title": {"size": 16, "space_after": 18},
            "heading-1": {"size": 14, "align": "center", "space_before": 12, "space_after": 12},
            "heading-2": {"size": 12, "space_before": 12, "space_after": 6},
            "heading-3": {"size": 12, "italic": True, "space_before": 12, "space_after": 6},
            "heading-4": {"size": 12},
            "heading-5": {"size": 12},
            "heading-6": {"size": 12},
            "heading-7": {"size": 12},
            "heading-8": {"size": 12},
            "heading-9": {"size": 12},
            "caption": {"size": 10},
            "quote": {"line": 1.0, "indent_left": 1.25, "indent_right": 0, "align": "justify"},
        },
        page={"size": "A4", "margin_top": 3, "margin_left": 4, "margin_right": 3, "margin_bottom": 3},
    ),
    "project-report": Template(
        "project-report",
        normal={"font": "Arial", "size": 11, "line": 1.15, "align": "left", "space_after": 8},
        styles={
            **{f"heading-{n}": {"color": _HEADING_COLOR} for n in range(1, 10)},
            "title": {"color": _HEADING_COLOR},
        },
        page={"size": "A4", "margin_top": 2.5, "margin_bottom": 2.5, "margin_left": 2.5, "margin_right": 2.5},
    ),
    "makalah": Template(
        "makalah",
        normal={"font": "Times New Roman", "size": 12, "line": 1.5, "align": "justify", "space_after": 6, "indent_first": 1.25},
        styles={
            "title": {"size": 14, "bold": True, "align": "center", "space_after": 12},
            "heading-1": {"size": 12, "bold": True, "align": "center", "space_before": 12, "space_after": 12},
            "heading-2": {"size": 12, "bold": True, "space_before": 10, "space_after": 6},
            "caption": {"size": 10, "align": "center"},
        },
        page={"size": "A4", "margin_top": 3, "margin_bottom": 3, "margin_left": 3, "margin_right": 3},
    ),
    "skripsi": Template(
        "skripsi",
        normal={"font": "Times New Roman", "size": 12, "line": 2.0, "align": "justify", "space_after": 0, "indent_first": 1.25},
        styles={
            "title": {"size": 14, "bold": True, "align": "center"},
            "heading-1": {"size": 12, "bold": True, "align": "center", "space_before": 24, "space_after": 12},
            "heading-2": {"size": 12, "bold": True, "space_before": 12, "space_after": 6},
            "heading-3": {"size": 12, "bold": True, "italic": True, "space_before": 12, "space_after": 6},
            "caption": {"size": 10, "align": "center"},
        },
        page={"size": "A4", "margin_top": 3, "margin_bottom": 3, "margin_left": 4, "margin_right": 3},
    ),
    "laporan": Template(
        "laporan",
        normal={"font": "Arial", "size": 11, "line": 1.15, "align": "justify", "space_after": 8},
        styles={
            "heading-1": {"size": 14, "bold": True, "color": _HEADING_COLOR, "space_before": 14, "space_after": 8},
            "heading-2": {"size": 12, "bold": True, "color": _HEADING_COLOR, "space_before": 10, "space_after": 6},
            "caption": {"size": 9, "align": "center"},
        },
        page={"size": "A4", "margin_top": 2.5, "margin_bottom": 2.5, "margin_left": 2.5, "margin_right": 2.5},
    ),
    "praktikum": Template(
        "praktikum",
        normal={"font": "Arial", "size": 11, "line": 1.15, "align": "left", "space_after": 6},
        styles={
            "heading-1": {"size": 13, "bold": True, "space_before": 12, "space_after": 6},
            "heading-2": {"size": 11, "bold": True, "space_before": 8, "space_after": 4},
            "code": {"font": "Consolas", "size": 9},
        },
        page={"size": "A4", "margin_top": 2, "margin_bottom": 2, "margin_left": 2.5, "margin_right": 2},
    ),
    "artikel": Template(
        "artikel",
        normal={"font": "Times New Roman", "size": 11, "line": 1.15, "align": "justify", "space_after": 6},
        styles={
            "title": {"size": 14, "bold": True, "align": "center"},
            "heading-1": {"size": 11, "bold": True, "space_before": 10, "space_after": 6},
            "caption": {"size": 9},
        },
        page={"size": "A4", "margin_top": 2, "margin_bottom": 2, "margin_left": 2, "margin_right": 2},
    ),
}


def get_template(name: str) -> Template | None:
    return TEMPLATES.get(name)
