"""DocScript AI (DSX): bahasa deklaratif untuk menyusun dokumen terstruktur."""

from __future__ import annotations

LANGUAGE_VERSION = "2.6"
__version__ = "2.0.3"  # + form mode (schema export, form→dsx)

from .api.service import (  # noqa: E402
    GenerationResult,
    check_document,
    compile_to_model,
    generate_document,
    generate_from_directory,
    get_structure_outline,
    list_presets,
    scaffold_project,
)
from .diagnostics import Diagnostic, Location, Severity  # noqa: E402
from .limits import Limits  # noqa: E402

__all__ = [
    "LANGUAGE_VERSION",
    "__version__",
    "Diagnostic",
    "GenerationResult",
    "Limits",
    "Location",
    "Severity",
    "check_document",
    "compile_to_model",
    "generate_document",
    "generate_from_directory",
    "get_structure_outline",
    "list_presets",
    "scaffold_project",
]
