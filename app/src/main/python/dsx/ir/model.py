"""Document Model: representasi stabil IR untuk editor, preview, dan integrasi AI (P2)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from .nodes import (
    FormLine,
    HorizontalRule,
    BibliographyBlock,
    Callout,
    ChartBlock,
    CodeBlock,
    DocumentIR,
    Figure,
    ListBlock,
    MathBlock,
    Paragraph,
    SectionBreak,
    Table,
    TextBlock,
    TocBlock,
)


@dataclass
class OutlineEntry:
    level: int
    text: str
    label_id: str | None = None


@dataclass
class DocumentModel:
    """Snapshot terstruktur dokumen — independen dari renderer."""

    language_version: str
    title: str
    author: str
    template: str
    page: dict[str, Any]
    outline: list[OutlineEntry] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)
    block_counts: dict[str, int] = field(default_factory=dict)
    sections: list[dict[str, Any]] = field(default_factory=list)
    bibliography_keys: list[str] = field(default_factory=list)
    warnings_hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def build_document_model(ir: DocumentIR, language_version: str = "2.5") -> DocumentModel:
    outline: list[OutlineEntry] = []
    counts: dict[str, int] = {}
    sections: list[dict[str, Any]] = []
    bib_keys: list[str] = []
    hints: list[str] = []

    def bump(name: str) -> None:
        counts[name] = counts.get(name, 0) + 1

    for block in ir.blocks:
        if isinstance(block, Paragraph):
            bump("paragraph")
            if block.is_heading and block.level:
                bump("heading")
                lid = None
                outline.append(OutlineEntry(block.level, block.text, lid))
        elif isinstance(block, TextBlock):
            bump("textblock")
        elif isinstance(block, HorizontalRule):
            bump("hr")
        elif isinstance(block, FormLine):
            bump("line")
        elif isinstance(block, Table):
            bump("table")
        elif isinstance(block, Figure):
            bump("figure")
            if not block.alt:
                hints.append("Gambar tanpa teks alternatif (alt).")
        elif isinstance(block, ChartBlock):
            bump("chart")
        elif isinstance(block, ListBlock):
            bump("list")
        elif isinstance(block, Callout):
            bump("callout")
        elif isinstance(block, MathBlock):
            bump("equation")
        elif isinstance(block, CodeBlock):
            bump("code")
        elif isinstance(block, TocBlock):
            bump("toc")
        elif isinstance(block, BibliographyBlock):
            bump("bibliography")
            for it in block.items or ir.bib_items:
                if it.get("key"):
                    bib_keys.append(it["key"])
        elif isinstance(block, SectionBreak):
            bump("section")
            sections.append({
                "break": block.break_type,
                "orientation": block.orientation,
                "page_size": block.page_size,
                "page_number_format": block.page_number_format,
                "show_page_number": block.show_page_number,
            })

    # heading hierarchy soft check
    last_level = 0
    for e in outline:
        if last_level and e.level > last_level + 1:
            hints.append(
                f"Hierarki heading meloncat dari level {last_level} ke {e.level} ({e.text[:40]})."
            )
        last_level = e.level

    return DocumentModel(
        language_version=language_version,
        title=ir.metadata.title or "",
        author=ir.metadata.author or "",
        template=ir.metadata.template or "default",
        page={
            "size": ir.page.size_name,
            "orientation": ir.page.orientation,
            "margin_top": ir.page.margin_top,
            "margin_bottom": ir.page.margin_bottom,
            "margin_left": ir.page.margin_left,
            "margin_right": ir.page.margin_right,
        },
        outline=outline,
        labels=dict(ir.labels),
        block_counts=counts,
        sections=sections,
        bibliography_keys=bib_keys,
        warnings_hints=hints,
    )
