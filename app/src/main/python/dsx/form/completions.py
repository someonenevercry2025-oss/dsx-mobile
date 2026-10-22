"""Data autocomplete untuk mode kode (fondasi fase editor).

Menghasilkan daftar completion item dari schema bahasa + snippet blok form.
"""

from __future__ import annotations

from typing import Any

from ..schema import SPECS
from .blocks import BLOCK_CATALOG, list_block_types
from .schema_export import export_language_schema


def build_completions() -> dict[str, Any]:
    """Paket completion untuk editor (Monaco / VS Code / web)."""
    components: list[dict[str, Any]] = []
    for name, spec in sorted(SPECS.items()):
        params = []
        for p in spec.params:
            item: dict[str, Any] = {
                "name": p.name,
                "type": p.type,
                "required": bool(p.required),
            }
            if p.choices:
                item["choices"] = list(p.choices)
            if p.unit:
                item["unit"] = p.unit
            params.append(item)
        # snippet kasar: NAME(|)
        required = [p.name for p in spec.params if p.required and p.positional]
        if required:
            snippet = f"{name}(${{1}})"
        else:
            snippet = f"{name}($0)"
        # markdown docs for hover
        lines = [f"**{name}** — kategori `{spec.category}`", ""]
        if params:
            lines.append("Parameter:")
            for p in params:
                req = "wajib" if p.get("required") else "opsional"
                extra = []
                if p.get("choices"):
                    extra.append("choices: " + ", ".join(f"`{c}`" for c in p["choices"][:12]))
                if p.get("unit"):
                    extra.append(f"unit: {p['unit']}")
                tail = (" — " + "; ".join(extra)) if extra else ""
                lines.append(f"- `{p['name']}` ({p['type']}, {req}){tail}")
        else:
            lines.append("_Tanpa parameter._")
        components.append({
            "label": name,
            "kind": "function",
            "category": spec.category,
            "detail": f"DSX {spec.category}",
            "insertText": snippet,
            "params": params,
            "documentation": f"Komponen {name} ({spec.category})",
            "documentationMarkdown": "\n".join(lines),
        })

    # Snippet blok form → potongan DSX tipikal
    snippets: list[dict[str, Any]] = []
    for type_id, meta in BLOCK_CATALOG.items():
        snippets.append({
            "label": f"block:{type_id}",
            "kind": "snippet",
            "detail": meta["label"],
            "insertText": _block_hint(type_id),
            "documentation": f"Blok form: {meta['label']}",
        })

    # Snippet dokumen umum
    doc_snippets = [
        {
            "label": "doc:minimal",
            "kind": "snippet",
            "detail": "Kerangka DSX minimal",
            "insertText": (
                'DSX(version="2.6")\n'
                'DOC(title="${1:Judul}", author="${2:Author}")\n'
                'PAGE(size="A4", margin=2.5cm)\n\n'
                'H1("${3:Bab 1}")\n'
                'P("${4:Paragraf...}", first_line_indent=1.25cm)\n'
            ),
        },
        {
            "label": "doc:kop-bottom",
            "kind": "snippet",
            "detail": "Tabel kop dengan border bottom",
            "insertText": (
                'TABLE(\n'
                '  border="bottom", border_width=1.5,\n'
                '  cell_padding=0.08cm, widths=["*"],\n'
                '  rows=[[CELL([BOLD("${1:NAMA}")], align="center")]]\n'
                ')\n'
            ),
        },
    ]

    schema = export_language_schema()
    return {
        "version": 1,
        "components": components,
        "block_types": list_block_types(),
        "snippets": doc_snippets + snippets,
        "ui_presets": schema.get("ui_presets"),
        "triggerCharacters": ["(", "=", '"', ","],
    }


def _block_hint(type_id: str) -> str:
    hints = {
        "kop": 'TABLE(border="bottom", border_width=1.5, rows=[[CELL([BOLD("${1:NAMA}")], align="center")]])',
        "paragraph": 'P("${1:teks}", first_line_indent=1.0cm, space_after=6)',
        "heading": 'H1("${1:Judul}")',
        "hr": 'HR(style="solid", thickness=1.5, space_before=2, space_after=8)',
        "signature": 'TABLE(border="none", widths=["*","*"], rows=[[CELL("Jabatan", align="center"), CELL("Jabatan", align="center")]])',
    }
    return hints.get(type_id, f"# block {type_id}")
