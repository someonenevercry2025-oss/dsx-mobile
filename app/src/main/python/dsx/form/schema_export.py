"""Export SPECS bahasa DSX ke JSON untuk editor / autocomplete / form UI."""

from __future__ import annotations

from typing import Any

from .. import LANGUAGE_VERSION, __version__
from ..schema import ALIASES, SPECS, SUPPORTED_VERSIONS


def _param_to_dict(p: Any) -> dict[str, Any]:
    d: dict[str, Any] = {
        "name": p.name,
        "type": p.type,
        "required": bool(p.required),
        "positional": bool(p.positional),
    }
    if p.choices:
        d["choices"] = list(p.choices)
    if p.min is not None:
        d["min"] = p.min
    if p.max is not None:
        d["max"] = p.max
    if p.step is not None:
        d["step"] = p.step
    if p.max_len is not None:
        d["max_len"] = p.max_len
    if p.unit:
        d["unit"] = p.unit
    return d


def export_language_schema() -> dict[str, Any]:
    """Skema lengkap komponen DSX untuk language service & UI."""
    components: dict[str, Any] = {}
    for name, spec in SPECS.items():
        components[name] = {
            "category": spec.category,
            "visual": bool(getattr(spec, "visual", False)),
            "params": [_param_to_dict(p) for p in spec.params],
        }
    return {
        "dsx_version": LANGUAGE_VERSION,
        "package_version": __version__,
        "supported_versions": list(SUPPORTED_VERSIONS),
        "aliases": dict(ALIASES),
        "components": components,
        # Hint UI untuk preset yang sering dipakai di form
        "ui_presets": {
            "table_border": [
                "none", "single", "outer", "grid", "bottom", "top",
                "double", "dashed", "dotted",
            ],
            "hr_style": ["solid", "dashed", "dotted", "double", "thick", "wave"],
            "align": ["left", "center", "right", "justify"],
            "callout_type": ["info", "note", "tip", "warning", "important"],
            "page_size": ["A4", "Letter", "Legal", "A5"],
        },
        "form_kinds": ["surat-resmi", "laporan", "makalah", "custom"],
    }
