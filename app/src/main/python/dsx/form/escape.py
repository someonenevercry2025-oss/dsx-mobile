"""Escape string untuk literal DSX."""

from __future__ import annotations


def dsx_str(text: str) -> str:
    """Bungkus string sebagai literal DSX (tanda kutip ganda)."""
    s = str(text).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def dsx_rich_line(text: str, bold: bool = False, italic: bool = False) -> str:
    """Satu segmen teks; jika bold/italic → BOLD()/ITALIC()."""
    inner = dsx_str(text)
    if bold and italic:
        return f"BOLD(ITALIC({inner}))"  # engine may not nest; prefer bold only
    if bold:
        return f"BOLD({inner})"
    if italic:
        return f"ITALIC({inner})"
    return inner
