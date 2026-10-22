"""Validasi konflik konfigurasi dan pemeriksaan aksesibilitas (P2)."""

from __future__ import annotations

from .diagnostics import DiagnosticBag
from .ir.nodes import ChartBlock, DocumentIR, Figure, Paragraph, SectionBreak


def validate_config_conflicts(ir: DocumentIR, diag: DiagnosticBag) -> None:
    """Warn on conflicting section / page-number settings."""
    prev_show = None
    for block in ir.blocks:
        if not isinstance(block, SectionBreak):
            continue
        if block.page_number_continue and block.page_number_start is not None:
            diag.warning(
                "CONFIG_CONFLICT",
                "SECTION memakai page_number_continue=true bersama page_number_start; "
                "start diabaikan saat continue aktif.",
                block.source,
            )
        if block.page_number_restart and block.page_number_continue:
            diag.warning(
                "CONFIG_CONFLICT",
                "SECTION memakai page_number_restart dan page_number_continue bersamaan; "
                "prioritas pada continue.",
                block.source,
            )
        if block.orientation == "landscape" and block.columns and block.columns > 2:
            diag.warning(
                "CONFIG_CONFLICT",
                "SECTION landscape dengan lebih dari 2 kolom dapat sulit dibaca.",
                block.source,
            )
        if prev_show is False and block.show_page_number and block.page_number_start is None and not block.page_number_continue:
            # informational
            pass
        prev_show = block.show_page_number


def validate_accessibility(ir: DocumentIR, diag: DiagnosticBag) -> None:
    """Soft checks: heading order, figure alt text."""
    last_level = 0
    for block in ir.blocks:
        if isinstance(block, Paragraph) and block.is_heading and block.level:
            if last_level and block.level > last_level + 1:
                diag.warning(
                    "A11Y_HEADING_SKIP",
                    f"Heading level {block.level} setelah level {last_level} "
                    f"(disarankan tidak meloncat level): {block.text[:60]!r}",
                    block.source,
                )
            last_level = block.level
        if isinstance(block, Figure) and not (block.alt or "").strip():
            diag.warning(
                "A11Y_MISSING_ALT",
                "Gambar tanpa teks alternatif (alt); penting untuk aksesibilitas.",
                block.source,
            )
        if isinstance(block, ChartBlock) and not (block.title or "").strip():
            diag.warning(
                "A11Y_CHART_TITLE",
                "Chart tanpa title; pertimbangkan memberi judul deskriptif.",
                block.source,
            )
