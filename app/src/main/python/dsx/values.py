"""Tipe nilai DSX hasil evaluasi ekspresi."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Union


class _Invalid:
    """Sentinel: ekspresi gagal dievaluasi dan kesalahannya sudah dilaporkan."""

    _instance: "_Invalid | None" = None

    def __new__(cls) -> "_Invalid":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "<invalid>"

    def __bool__(self) -> bool:
        return False


INVALID = _Invalid()


@dataclass(frozen=True)
class Length:
    """Angka bersatuan (cm, pt, in), mis. ``1.25cm``."""

    value: float
    unit: str


@dataclass(frozen=True)
class TextRef:
    path: str


@dataclass(frozen=True)
class ImageRef:
    path: str


@dataclass(frozen=True)
class CsvRef:
    path: str
    delimiter: str = ","


@dataclass(frozen=True)
class StyledText:
    """Teks dengan format sebaris (bold/italic/underline/highlight)."""

    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    highlight: str | None = None  # Word highlight name or hex


@dataclass(frozen=True)
class LinkValue:
    """Hyperlink sebaris."""

    text: str
    url: str
    bold: bool = False
    italic: bool = False
    underline: bool = False


@dataclass(frozen=True)
class FootnoteValue:
    """Referensi catatan kaki (teks catatan disimpan di value)."""

    text: str


@dataclass(frozen=True)
class RefValue:
    """Referensi silang (REF)."""

    label_id: str
    text: str = ""  # optional override


@dataclass(frozen=True)
class CiteValue:
    """Sitasi (CITE)."""

    key: str
    pages: str = ""


@dataclass(frozen=True)
class CellValue:
    """Sel tabel dengan opsi merge, gaya sel, dan border per sisi."""

    text: object  # str | list | rich
    rowspan: int = 1
    colspan: int = 1
    shading: str | None = None
    align: str | None = None
    valign: str | None = None
    borders: dict | None = None  # side -> {style, color, width_pt}


@dataclass(frozen=True)
class CommentValue:
    """Komentar Word native (sebaris)."""

    text: str
    author: str = "DSX"
    initials: str = ""


Value = Union[
    str,
    int,
    float,
    bool,
    list,
    TextRef,
    ImageRef,
    CsvRef,
    StyledText,
    LinkValue,
    FootnoteValue,
    RefValue,
    CiteValue,
    CellValue,
    CommentValue,
]


def type_name(value: object) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "bilangan bulat"
    if isinstance(value, float):
        return "angka desimal"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if isinstance(value, TextRef):
        return "referensi file teks"
    if isinstance(value, ImageRef):
        return "referensi gambar"
    if isinstance(value, CsvRef):
        return "referensi CSV"
    if isinstance(value, Length):
        return "ukuran bersatuan"
    if isinstance(value, StyledText):
        return "teks berformat"
    if isinstance(value, LinkValue):
        return "hyperlink"
    if isinstance(value, FootnoteValue):
        return "catatan kaki"
    if isinstance(value, RefValue):
        return "referensi silang"
    if isinstance(value, CiteValue):
        return "sitasi"
    if isinstance(value, CellValue):
        return "sel tabel"
    if isinstance(value, CommentValue):
        return "komentar"
    if type(value).__name__ == "ParsedMath":
        return "ekspresi matematika (IMATH)"
    return type(value).__name__
