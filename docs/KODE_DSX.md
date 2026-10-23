# Bahasa DSX (ringkas untuk mode Kode)

## Kerangka

```
DSX(version="2.6")
DOC(title="...", author="...")
PAGE(size="A4", margin_top=2.0cm, margin_bottom=2.0cm, margin_left=2.5cm, margin_right=2.5cm)
STYLEDEF(normal, font="Times New Roman", size=12, line=1.15)
```

## Komponen isi umum

| Komponen | Kegunaan |
|----------|----------|
| `P("teks", space_after=6, first_line_indent=1.0cm)` | Paragraf |
| `BOLD("...")` / `ITALIC("...")` | Dalam richtext |
| `TABLE(... rows=[[CELL(...)]])` | Tabel / kop / TTD |
| `IMAGE("assets/logo.png")` | Gambar **di dalam** CELL |
| `FIGURE(src="assets/x.png", width=4cm)` | Blok gambar sendiri (bukan di CELL) |
| `HR(style="solid", thickness=1.0)` | Garis |

## Aturan penting

- Di dalam `CELL`, jangan pakai `FIGURE` — pakai `IMAGE("path")`.
- `valign` hanya: `top`, `center`, `bottom` (bukan `middle`).
- String tidak boleh newline mentah di dalam kutip; escape sebagai `\n`.
- Path gambar relatif ke folder proyek: `assets/nama.png`.

## Diagnostik umum

| Kode | Arti |
|------|------|
| `NOT_A_VALUE_FUNCTION` | Komponen dokumen dipakai sebagai nilai (mis. FIGURE di CELL) |
| `UNTERMINATED_STRING` | Kutip string tidak tertutup / newline di string |
| `INVALID_VALUE` | Enum salah (mis. valign) |

Ketuk baris `L12:...` di app untuk loncat ke baris tersebut.
