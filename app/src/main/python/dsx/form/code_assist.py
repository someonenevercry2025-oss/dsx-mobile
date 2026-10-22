"""Bantuan mode kode: highlight token sederhana + saran completion kontekstual."""

from __future__ import annotations

import re
from typing import Any

from .completions import build_completions

_TOKEN_RE = re.compile(
    r"(?P<comment>\#[^\n]*)|"
    r"(?P<string>\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')|"
    r"(?P<number>\b\d+(?:\.\d+)?(?:cm|pt|in)?\b)|"
    r"(?P<bool>\b(?:true|false)\b)|"
    r"(?P<ident>\b[A-Za-z_][A-Za-z0-9_]*\b)|"
    r"(?P<punct>[()\[\]{},=])|"
    r"(?P<ws>\s+)|"
    r"(?P<other>.)",
    re.MULTILINE,
)


def highlight_dsx(source: str) -> str:
    """HTML span-colored (aman di-escape)."""
    import html as html_mod

    parts: list[str] = []
    for m in _TOKEN_RE.finditer(source or ""):
        kind = m.lastgroup or "other"
        text = html_mod.escape(m.group(0))
        if kind == "ws":
            parts.append(text)
        else:
            parts.append(f'<span class="tok-{kind}">{text}</span>')
    return "".join(parts) or "&nbsp;"


def suggest_at_cursor(source: str, offset: int, limit: int = 30) -> list[dict[str, Any]]:
    """Saran completion berdasarkan prefix di posisi kursor."""
    offset = max(0, min(offset, len(source or "")))
    before = (source or "")[:offset]
    # prefix identifier yang sedang diketik
    m = re.search(r"([A-Za-z_][A-Za-z0-9_]*)$", before)
    prefix = m.group(1) if m else ""
    # apakah di dalam argumen pemanggilan?
    open_call = _innermost_call(before)

    data = build_completions()
    items: list[dict[str, Any]] = []

    if open_call:
        # saran parameter untuk komponen tersebut
        comp = next((c for c in data["components"] if c["label"] == open_call), None)
        if comp:
            for p in comp.get("params") or []:
                name = p["name"]
                if prefix and not name.lower().startswith(prefix.lower()):
                    continue
                insert = f"{name}="
                if p.get("choices"):
                    insert = f'{name}="{p["choices"][0]}"'
                elif p.get("type") == "bool":
                    insert = f"{name}=true"
                elif p.get("type") in ("num", "int"):
                    insert = f"{name}=1"
                elif p.get("type") in ("str", "richtext", "header_row", "rows"):
                    insert = f'{name}=""'
                items.append({
                    "label": name,
                    "detail": f"param {open_call}",
                    "insertText": insert,
                    "kind": "param",
                    "replacePrefix": prefix,
                })
            for p in comp.get("params") or []:
                for ch in p.get("choices") or []:
                    if prefix and not str(ch).lower().startswith(prefix.lower()):
                        continue
                    items.append({
                        "label": str(ch),
                        "detail": f"enum {p['name']}",
                        "insertText": f'"{ch}"',
                        "kind": "enum",
                        "replacePrefix": prefix,
                    })

    # komponen & snippet
    for c in data.get("components") or []:
        lab = c["label"]
        if prefix and not lab.lower().startswith(prefix.lower()):
            continue
        items.append({
            "label": lab,
            "detail": c.get("detail") or "component",
            "insertText": c.get("insertText") or f"{lab}()",
            "kind": "component",
            "replacePrefix": prefix,
        })
    for s in data.get("snippets") or []:
        lab = s["label"]
        if prefix and prefix.lower() not in lab.lower():
            continue
        items.append({
            "label": lab,
            "detail": s.get("detail") or "snippet",
            "insertText": s.get("insertText") or "",
            "kind": "snippet",
            "replacePrefix": prefix,
        })

    # dedupe by label
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for it in items:
        if it["label"] in seen:
            continue
        seen.add(it["label"])
        out.append(it)
        if len(out) >= limit:
            break
    return out


def _innermost_call(before: str) -> str | None:
    """Nama fungsi terdekat yang masih terbuka: FOO( ... kursor."""
    # hapus string agar kurung di string tidak mengganggu
    cleaned = re.sub(r'"(?:\\.|[^"\\])*"', '""', before)
    cleaned = re.sub(r"'(?:\\.|[^'\\])*'", "''", cleaned)
    depth = 0
    i = len(cleaned) - 1
    while i >= 0:
        ch = cleaned[i]
        if ch == ")":
            depth += 1
        elif ch == "(":
            if depth == 0:
                # cari ident sebelum (
                j = i - 1
                while j >= 0 and cleaned[j].isspace():
                    j -= 1
                end = j + 1
                while j >= 0 and (cleaned[j].isalnum() or cleaned[j] == "_"):
                    j -= 1
                name = cleaned[j + 1 : end]
                return name or None
            depth -= 1
        i -= 1
    return None
