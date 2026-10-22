from __future__ import annotations

import base64
import html as html_mod
from typing import Any

from ..ir.nodes import (
    BibliographyBlock, Callout, ChartBlock, CodeBlock, ColumnsEnd, ColumnsStart,
    DocumentIR, Figure, FormLine, HorizontalRule, ListBlock, MathBlock, Paragraph, SectionBreak, Table, TextBlock, TocBlock,
    TextSeg, LinkSeg, FootnoteSeg, MathSeg, RefSeg, CiteSeg, LabelMarker,
)
from ..limits import Deadline
from .base import Renderer


def _esc(s: str) -> str:
    return html_mod.escape(s or "")


def _segs_html(segments: tuple, plain: str) -> str:
    if not segments:
        return _esc(plain)
    parts: list[str] = []
    for seg in segments:
        if isinstance(seg, TextSeg):
            t = _esc(seg.text)
            if seg.bold:
                t = f"<strong>{t}</strong>"
            if seg.italic:
                t = f"<em>{t}</em>"
            if seg.underline:
                t = f"<u>{t}</u>"
            parts.append(t)
        elif isinstance(seg, LinkSeg):
            parts.append(f'<a href="{_esc(seg.url)}">{_esc(seg.text)}</a>')
        elif isinstance(seg, FootnoteSeg):
            parts.append(f"<sup>[{seg.note_id}]</sup>")
        elif isinstance(seg, MathSeg):
            parts.append(f"<code class='math'>{_esc(seg.expression)}</code>")
        elif isinstance(seg, (RefSeg, CiteSeg)):
            parts.append(_esc(seg.display))
        else:
            parts.append(_esc(getattr(seg, "text", "")))
    return "".join(parts)




def _html_list_block(block) -> str:
    items = list(block.items)
    ordered = block.ordered
    start = getattr(block, "start", 1) or 1

    def render_range(lo: int, hi: int, level: int, start_at: int) -> str:
        tag = "ol" if ordered else "ul"
        attr = f' start="{start_at}"' if ordered and start_at != 1 else ""
        out = [f"<{tag}{attr}>"]
        i = lo
        while i < hi:
            if items[i].level < level:
                break
            if items[i].level > level:
                i += 1
                continue
            content = _segs_html(items[i].segments, items[i].text) if items[i].segments else _esc(items[i].text)
            for cont in items[i].continuations:
                content += f"<br/>{_esc(cont)}"
            j = i + 1
            while j < hi and items[j].level > level:
                j += 1
            child_html = render_range(i + 1, j, level + 1, 1) if j > i + 1 else ""
            out.append(f"<li>{content}{child_html}</li>")
            i = j
        out.append(f"</{tag}>")
        return "".join(out)

    if not items:
        return ""
    return render_range(0, len(items), 0, start)


class HtmlRenderer(Renderer):
    format = "html"

    def render(self, ir: DocumentIR, deadline: Deadline | None = None) -> bytes:
        body: list[str] = []
        title = _esc(ir.metadata.title or "Dokumen DSX")
        for block in ir.blocks:
            if deadline is not None:
                deadline.check()
            if isinstance(block, Paragraph):
                tag = f"h{block.level}" if block.is_heading and block.level else "p"
                body.append(f"<{tag}>{_segs_html(block.segments, block.text)}</{tag}>")
            elif isinstance(block, TextBlock):
                for p in block.paragraphs:
                    body.append(f"<p>{_segs_html(p.segments, p.text)}</p>")
            elif isinstance(block, Figure):
                b64 = base64.b64encode(block.image.data).decode("ascii")
                body.append(
                    f'<figure><img src="data:{block.image.content_type};base64,{b64}" '
                    f'alt="{_esc(block.alt)}" style="max-width:100%;width:{block.width_cm}cm"/>'
                )
                if block.caption:
                    body.append(f"<figcaption>{_esc(block.caption.text)}</figcaption>")
                body.append("</figure>")
            elif isinstance(block, ChartBlock):
                b64 = base64.b64encode(block.image.data).decode("ascii")
                body.append(
                    f'<figure><img src="data:image/png;base64,{b64}" alt="{_esc(block.title)}" '
                    f'style="max-width:100%;width:{block.width_cm}cm"/>'
                )
                if block.caption:
                    body.append(f"<figcaption>{_esc(block.caption.text)}</figcaption>")
                body.append("</figure>")
            elif isinstance(block, HorizontalRule):
                style_map = {"solid": "solid", "dashed": "dashed", "dotted": "dotted", "double": "double"}
                bs = style_map.get(block.style, "solid")
                body.append(
                    f"<hr class='dsx-hr' style='border:none;border-top:{block.thickness_pt}pt {bs} #{_esc(block.color)};"
                    f"width:{_esc(block.width)};margin:{block.space_before_pt}pt auto {block.space_after_pt}pt;'/>"
                )
            elif isinstance(block, FormLine):
                length = block.length or "40"
                try:
                    n = int(float(length.replace("cm",""))) if length else 40
                except ValueError:
                    n = 40
                if block.style == "dots":
                    fill = "." * max(5, n if not str(block.length).endswith("cm") else n * 4)
                elif block.style == "dashed":
                    fill = ("- " * 20).strip()
                else:
                    fill = "_" * max(5, n if not str(block.length).endswith("cm") else 40)
                for i in range(max(1, block.count)):
                    prefix = block.label or (f"{i+1}. " if block.count > 1 else "")
                    body.append(f"<p class='form-line'>{_esc(prefix + fill)}</p>")
            elif isinstance(block, Table):
                bdr = getattr(block, "border", "grid")
                if bdr == "none":
                    body.append("<table cellpadding='4' cellspacing='0' style='border-collapse:collapse;border:none'>")
                else:
                    body.append("<table border='1' cellpadding='4' cellspacing='0' style='border-collapse:collapse'>")
                if block.header:
                    body.append("<thead><tr>")
                    for c in block.header:
                        rs = f' rowspan="{c.rowspan}"' if c.rowspan > 1 else ""
                        cs = f' colspan="{c.colspan}"' if c.colspan > 1 else ""
                        body.append(f"<th{rs}{cs}>{_segs_html(c.segments, c.text)}</th>")
                    body.append("</tr></thead>")
                body.append("<tbody>")
                for row in block.rows:
                    body.append("<tr>")
                    for c in row:
                        if c.merged:
                            continue
                        rs = f' rowspan="{c.rowspan}"' if c.rowspan > 1 else ""
                        cs = f' colspan="{c.colspan}"' if c.colspan > 1 else ""
                        body.append(f"<td{rs}{cs}>{_segs_html(c.segments, c.text)}</td>")
                    body.append("</tr>")
                body.append("</tbody></table>")
                if block.caption:
                    body.append(f"<p class='caption'>{_esc(block.caption.text)}</p>")
            elif isinstance(block, ListBlock):
                body.append(_html_list_block(block))
            elif isinstance(block, Callout):
                body.append(f'<aside class="callout {block.variant}">')
                if block.title:
                    body.append(f"<strong>{_esc(block.title.text)}</strong>")
                for p in block.body:
                    body.append(f"<p>{_segs_html(p.segments, p.text)}</p>")
                body.append("</aside>")
            elif isinstance(block, MathBlock):
                body.append(f"<div class='math-block'><code>{_esc(block.expression)}</code></div>")
            elif isinstance(block, CodeBlock):
                body.append(f"<pre><code class='language-{_esc(block.language)}'>{_esc(block.text)}</code></pre>")
            elif isinstance(block, BibliographyBlock):
                if block.title and block.title.strip():
                    body.append(f"<h2>{_esc(block.title)}</h2>")
                style = (block.style_name or "simple").lower()
                body.append('<div class="bibliography">')
                for i, it in enumerate(block.items or ir.bib_items, 1):
                    author = it.get("author") or ""
                    title_t = it.get("title") or ""
                    year = it.get("year") or ""
                    journal = it.get("journal") or ""
                    publisher = it.get("publisher") or ""
                    url = it.get("url") or ""
                    pages = it.get("pages") or ""
                    volume = it.get("volume") or ""
                    if style == "apa":
                        line = f"{author} ({year}). <em>{_esc(title_t)}</em>."
                        if journal:
                            line += f" {_esc(journal)}"
                            if volume:
                                line += f", <em>{_esc(volume)}</em>"
                            if pages:
                                line += f", {_esc(pages)}"
                            line += "."
                        elif publisher:
                            line += f" {_esc(publisher)}."
                        if url:
                            line += f" {_esc(url)}"
                        # author/year already escaped partially - rebuild safely
                        line = _esc(f"{author} ({year}). {title_t}.")
                        if journal:
                            line += _esc(f" {journal}")
                            if volume:
                                line += _esc(f", {volume}")
                            if pages:
                                line += _esc(f", {pages}")
                            line += "."
                        elif publisher:
                            line += _esc(f" {publisher}.")
                        if url:
                            line += " " + _esc(url)
                    elif style == "ieee":
                        line = _esc(f'[{i}] {author}, "{title_t},"')
                        if journal:
                            line += _esc(f" {journal},")
                        if volume:
                            line += _esc(f" vol. {volume},")
                        if pages:
                            line += _esc(f" pp. {pages},")
                        if year:
                            line += _esc(f" {year}.")
                    else:
                        line = _esc(" — ".join(filter(None, [author, title_t, year, url])))
                    body.append(f'<p class="bib-item">{line}</p>')
                body.append("</div>")
            elif isinstance(block, TocBlock):
                body.append(f"<nav class='toc'><h2>{_esc(block.title or 'Daftar Isi')}</h2><ul>")
                depth = block.depth or 3
                for b in ir.blocks:
                    if isinstance(b, Paragraph) and b.is_heading and b.level and b.level <= depth:
                        body.append(f"<li class='toc-l{b.level}'>{_esc(b.text)}</li>")
                body.append("</ul></nav>")
            elif isinstance(block, SectionBreak):
                meta = [block.break_type or 'section']
                if block.page_number_format:
                    meta.append(str(block.page_number_format))
                if block.orientation:
                    meta.append(str(block.orientation))
                body.append("<hr class='section-break'/>")
                body.append(f"<div class='section-label'>Section: {_esc(' · '.join(meta))}</div>")
            elif isinstance(block, (LabelMarker, ColumnsStart, ColumnsEnd)):
                pass
        if ir.footnotes:
            body.append("<hr/><h3>Catatan kaki</h3><ol>")
            for fn in ir.footnotes:
                body.append(f"<li id='fn{fn.note_id}'>{_esc(fn.text)}</li>")
            body.append("</ol>")

        doc = f"""<!DOCTYPE html>
<html lang="{_esc(ir.metadata.language or 'id')}">
<head>
<meta charset="utf-8"/>
<title>{title}</title>
<style>
body {{ font-family: "Times New Roman", Times, serif; max-width: 48rem; margin: 2rem auto; line-height: 1.6; color: #222; }}
.doc-header, .doc-footer {{ font-size: 0.85rem; color: #555; border-bottom: 1px solid #ddd; padding-bottom: 0.5rem; margin-bottom: 1.5rem; }}
.doc-footer {{ border-bottom: none; border-top: 1px solid #ddd; margin-top: 2rem; padding-top: 0.5rem; }}
h1 {{ font-size: 1.25rem; text-align: center; margin-top: 2rem; }}
h2 {{ font-size: 1.1rem; margin-top: 1.5rem; }}
h3 {{ font-size: 1rem; font-style: italic; }}
p {{ text-align: justify; text-indent: 1.25em; margin: 0.4em 0; }}
table {{ border-collapse: collapse; margin: 1rem auto; width: 100%; }}
th, td {{ border: 1px solid #444; padding: 0.35rem 0.6rem; }}
th {{ background: #f0f0f0; }}
caption, .caption {{ text-align: center; font-size: 0.9rem; font-style: italic; margin: 0.5rem 0; }}
pre {{ background: #f5f5f5; padding: 0.75rem; overflow-x: auto; font-family: Consolas, monospace; }}
.callout {{ border-left: 4px solid #888; padding: 0.5rem 1rem; margin: 1rem 0; background: #fafafa; text-indent: 0; }}
.callout.warning {{ border-color: #e6a700; }}
.callout.tip {{ border-color: #2e7d32; }}
.callout.important {{ border-color: #c62828; }}
.bib-item {{ text-indent: -1.25em; padding-left: 1.25em; margin: 0.35em 0; }}
.bibliography {{ margin: 1rem 0; }}
.math-block {{ text-align: center; margin: 1rem 0; text-indent: 0; }}
.section-break {{ border: none; border-top: 2px dashed #aaa; margin: 2rem 0 0.5rem; }}
.section-label {{ font-size: 0.75rem; color: #888; text-align: center; margin-bottom: 1.5rem; text-indent: 0; }}
nav.toc ul {{ list-style: none; padding-left: 0; }}
nav.toc li.toc-l2 {{ padding-left: 1.25rem; }}
nav.toc li.toc-l3 {{ padding-left: 2.5rem; }}
@media print {{
  .section-label {{ display: none; }}
  .section-break {{ border-top: none; break-before: page; }}
}}
</style>
</head>
<body>
{''.join(body)}
</body>
</html>
"""
        return doc.encode("utf-8")
