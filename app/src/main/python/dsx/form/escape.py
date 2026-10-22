"""Escape string untuk literal DSX."""

from __future__ import annotations


def dsx_str(text: str) -> str:
    """Bungkus string sebagai literal DSX (tanda kutip ganda).

    Newline/tab di-escape agar sumber DSX tetap satu baris per literal
    dan lexer tidak melihat string tidak tertutup.
    """
    s = (
        str(text)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
        .replace("\r", "\\n")
        .replace("\t", "\\t")
    )
    return f'"{s}"'


def dsx_rich_line(text: str, bold: bool = False, italic: bool = False) -> str:
    """Satu segmen teks; jika bold/italic → BOLD()/ITALIC()."""
    inner = dsx_str(text)
    if bold and italic:
        return f"BOLD(ITALIC({inner}))"
    if bold:
        return f"BOLD({inner})"
    if italic:
        return f"ITALIC({inner})"
    return inner
