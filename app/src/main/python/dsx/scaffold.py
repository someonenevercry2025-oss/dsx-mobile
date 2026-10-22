"""Generate starter DSX projects from academic structure presets (P3)."""

from __future__ import annotations

from pathlib import Path

from .presets import STRUCTURE_OUTLINES


def scaffold_dsx(
    name: str,
    *,
    title: str = "Judul Dokumen",
    author: str = "Penulis",
    numbering: str = "roman_then_decimal",
) -> str:
    """Return a complete starter document.dsx text."""
    name = name.lower().strip()
    if name not in ("makalah", "skripsi", "laporan", "praktikum", "artikel"):
        name = "makalah"
    outline = STRUCTURE_OUTLINES.get(name) or STRUCTURE_OUTLINES["makalah"]
    lines = [
        'DSX(version="2.5")',
        f'PRESET("{name}", numbering="{numbering}")',
        f'DOC(title="{title}", author="{author}")',
        f'HEADER("{title[:40]}", distance=1.0cm)',
        'PAGENUM(preset="academic_footer", placement="bottom_center", show=true)',
        "",
        f'P("{title}")',
        f'P("Oleh: {author}")',
        'PAGEBREAK()',
        'H1("Kata Pengantar")',
        'P("Tuliskan kata pengantar di sini.")',
        'TOC(title="Daftar Isi", depth=2)',
        'PAGEBREAK()',
    ]
    skip = {
        "HALAMAN JUDUL", "HALAMAN PENGESAHAN", "Kata Pengantar", "Daftar Isi",
        "Abstrak", "Ringkasan Eksekutif", "Judul", "Judul Praktikum",
    }
    for item in outline:
        if item in skip:
            continue
        if item == "Daftar Pustaka":
            lines.extend([
                "",
                f'H1("{item}")',
                'BIBITEM("contoh2024", author="Contoh, A.", title="Judul Referensi", year="2024", publisher="Penerbit")',
                'BIBLIOGRAPHY(title="", style="apa")',
            ])
        else:
            lines.extend(["", f'H1("{item}")', 'P("Konten bagian ini.")'])
    return "\n".join(lines) + "\n"


def write_scaffold(project_dir: str | Path, name: str, **kwargs) -> Path:
    root = Path(project_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "document.dsx"
    # ensure real newlines
    text = scaffold_dsx(name, **kwargs)
    if "\\n" in repr(text)[:20]:
        pass
    path.write_text(text, encoding="utf-8")
    (root / "data").mkdir(exist_ok=True)
    (root / "content").mkdir(exist_ok=True)
    return path
