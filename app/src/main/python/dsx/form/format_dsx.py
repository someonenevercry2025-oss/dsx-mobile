"""Formatter sumber DSX sederhana (indent berdasarkan kedalaman kurung)."""

from __future__ import annotations


def format_dsx(source: str, *, indent: str = "  ") -> str:
    text = source.replace("\r\n", "\n").replace("\r", "\n")
    out: list[str] = []
    depth = 0
    i = 0
    n = len(text)
    line_parts: list[str] = []
    line_depth = 0
    in_str = False
    quote = ""
    escape = False

    def flush_line() -> None:
        nonlocal line_parts, line_depth
        raw = "".join(line_parts).rstrip()
        line_parts = []
        if raw == "":
            out.append("")
            return
        # if line starts with closing, use lower indent
        stripped = raw.lstrip()
        d = line_depth
        if stripped.startswith(")") or stripped.startswith("]") or stripped.startswith("}"):
            d = max(0, depth)  # depth already decremented
        out.append(indent * max(0, d) + stripped)

    while i < n:
        ch = text[i]
        if in_str:
            line_parts.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_str = False
            i += 1
            continue

        if ch in "\"'":
            in_str = True
            quote = ch
            line_parts.append(ch)
            i += 1
            continue

        if ch == "#":
            # rest of line is comment
            while i < n and text[i] != "\n":
                line_parts.append(text[i])
                i += 1
            continue

        if ch == "\n":
            flush_line()
            line_depth = depth
            i += 1
            continue

        if ch in "([{":
            line_parts.append(ch)
            # break after { [ ( if next non-space is not close
            depth += 1
            i += 1
            # optional: if followed by newline already handled
            continue

        if ch in ")]}":
            depth = max(0, depth - 1)
            line_parts.append(ch)
            i += 1
            continue

        if ch == ",":
            line_parts.append(ch)
            # soft break after comma at depth>=1: insert newline
            i += 1
            # peek skip spaces
            j = i
            while j < n and text[j] in " \t":
                j += 1
            if j < n and text[j] not in "\n#":
                flush_line()
                line_depth = depth
                # skip the spaces we would have copied
                i = j
            continue

        line_parts.append(ch)
        i += 1

    if line_parts:
        flush_line()

    # collapse excessive blank lines (max 2)
    cleaned: list[str] = []
    blanks = 0
    for line in out:
        if line.strip() == "":
            blanks += 1
            if blanks <= 2:
                cleaned.append("")
        else:
            blanks = 0
            cleaned.append(line)
    result = "\n".join(cleaned)
    if not result.endswith("\n"):
        result += "\n"
    return result
