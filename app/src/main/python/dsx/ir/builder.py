"""IR builder: mengubah komponen isi yang sudah terikat menjadi blok Document IR."""

from __future__ import annotations

import dataclasses
import re
from typing import Any

from ..diagnostics import DiagnosticBag, Location
from ..limits import Deadline, Limits
from ..resolver import Resolver
from ..schema import SPECS
from ..source import ContentStore
from ..styles.registry import ResolvedStyle, StyleRegistry
from ..syntax import CallExpr
from ..textutil import collapse_spaces
from ..validator import BoundCall, hint_for
from ..values import CsvRef, TextRef, StyledText, LinkValue, FootnoteValue, RefValue, CiteValue, CellValue, CommentValue
from ..styles.defaults import CALLOUT_THEMES
from ..mathexpr import ParsedMath
from .nodes import (
    Block, Callout, Figure, ImageAsset, ListBlock, ListItem, MathBlock, MathSeg,
    PageConfig, Paragraph, Table, TableCell, TextBlock, TextSeg, ImageSeg, LinkSeg,
    FootnoteSeg, TocBlock, FootnoteDef, CodeBlock, ChartBlock, LabelMarker,
    BibliographyBlock, ColumnsStart, ColumnsEnd, SectionBreak, Watermark, RefSeg, CiteSeg,
    HorizontalRule, FormLine, CommentSeg, CommentDef, ShapeBlock, ListOfTablesBlock, ListOfFiguresBlock,
)

_HEADING_SHORTCUT = re.compile(r"^H([1-9])$")


def split_paragraphs(text: str, preserve_breaks: bool) -> list[str]:
    """Aturan TEXTBLOCK (Blueprint V.3): baris kosong memisahkan paragraf,
    baris berurutan digabung menjadi satu paragraf."""
    groups: list[list[str]] = []
    current: list[str] = []
    for line in text.split("\n"):
        if line.strip() == "":
            if current:
                groups.append(current)
                current = []
        else:
            current.append(line)
    if current:
        groups.append(current)
    result: list[str] = []
    for lines in groups:
        if preserve_breaks:
            result.append("\n".join(line.rstrip() for line in lines))
        else:
            result.append(collapse_spaces(" ".join(collapse_spaces(line) for line in lines)))
    return result



def raw_to_segments(raw_items: list, footnote_sink: list, footnote_seq: list) -> tuple[list, str]:
    """Ubah list nilai (str/StyledText/Link/Footnote/ParsedMath) menjadi Segment + plain text.

    footnote_seq is a single-element list holding the current counter (mutable).
    """
    segments: list = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            text = re.sub(r"[ \t\f\v\n]+", " ", "".join(buffer))
            buffer.clear()
            if text:
                segments.append(TextSeg(text))

    for item in raw_items:
        if isinstance(item, ParsedMath):
            flush()
            segments.append(MathSeg(item.source, item.tree))
        elif isinstance(item, StyledText):
            flush()
            t = re.sub(r"[ \t\f\v\n]+", " ", item.text)
            if t:
                segments.append(TextSeg(t, bold=item.bold, italic=item.italic, underline=item.underline, highlight=getattr(item, 'highlight', None)))
        elif isinstance(item, LinkValue):
            flush()
            t = re.sub(r"[ \t\f\v\n]+", " ", item.text)
            if t:
                segments.append(LinkSeg(t, item.url, bold=item.bold, italic=item.italic, underline=item.underline))
        elif isinstance(item, FootnoteValue):
            flush()
            footnote_seq[0] += 1
            fid = footnote_seq[0]
            footnote_sink.append(FootnoteDef(fid, item.text))
            segments.append(FootnoteSeg(fid, item.text))
        elif isinstance(item, RefValue):
            flush()
            display = item.text or f"[{item.label_id}]"
            segments.append(RefSeg(item.label_id, display))
        elif isinstance(item, CiteValue):
            flush()
            display = f"[{item.key}]" + (f", {item.pages}" if item.pages else "")
            segments.append(CiteSeg(item.key, display, item.pages))
        elif isinstance(item, ImageSeg):
            flush()
            segments.append(item)
        else:
            buffer.append(str(item))
    flush()
    plain_parts = []
    for s in segments:
        if isinstance(s, TextSeg):
            plain_parts.append(s.text)
        elif isinstance(s, LinkSeg):
            plain_parts.append(s.text)
        elif isinstance(s, FootnoteSeg):
            plain_parts.append(f"[{s.note_id}]")
    plain = "".join(plain_parts)
    needs = any(
        isinstance(s, (MathSeg, LinkSeg, FootnoteSeg, RefSeg, CiteSeg, ImageSeg))
        or (isinstance(s, TextSeg) and (s.bold or s.italic or s.underline or getattr(s, "highlight", None)))
        for s in segments
    )
    return (segments if needs else []), plain


class IRBuilder:
    def __init__(
        self,
        resolver: Resolver,
        registry: StyleRegistry,
        page: PageConfig,
        limits: Limits,
        deadline: Deadline,
        diag: DiagnosticBag,
        store: ContentStore,
    ) -> None:
        self.resolver = resolver
        self.registry = registry
        self.page = page
        self.limits = limits
        self.deadline = deadline
        self.diag = diag
        self.store = store
        self.used_styles: set[str] = set()
        self._paragraph_count = 0
        self._footnotes: list[FootnoteDef] = []
        self._footnote_seq = 0
        self._comments: list[CommentDef] = []
        self._comment_seq = 0
        self.labels: dict[str, str] = {}
        self._label_counters: dict[str, int] = {}
        self.bib_items: list[dict[str, str]] = []
        self.watermark: Watermark | None = None
        self._cite_order: list[str] = []


    # ------------------------------------------------------------ public API
    def build(self, calls: list[CallExpr]) -> list[Block]:
        blocks: list[Block] = []
        pending_break: Location | None = None
        for call in calls:
            self.deadline.check()
            bound = self.resolver.binder.bind(call, SPECS[call.name])
            if bound is None:
                continue
            if call.name == "PAGEBREAK":
                if pending_break is not None:
                    self.diag.warning("DUPLICATE_PAGEBREAK", "PAGEBREAK berurutan digabung menjadi satu.", call.loc)
                else:
                    pending_break = call.loc
                continue
            new_blocks = self._build_call(bound)
            for block in new_blocks:
                if pending_break is not None:
                    already = getattr(block, "page_break_before", False)
                    if isinstance(block, Paragraph):
                        already = already or bool(
                            block.effective.get("page_break_before") or block.overrides.get("page_break_before")
                        )
                    # SectionBreak next_page/even/odd already forces a new page
                    if isinstance(block, SectionBreak) and block.break_type in (
                        "next_page", "even_page", "odd_page"
                    ):
                        already = True
                    if already:
                        pending_break = None
                    else:
                        block = self._with_break(block)
                        pending_break = None
                blocks.append(block)
        if pending_break is not None:
            self.diag.warning("TRAILING_PAGEBREAK", "PAGEBREAK tanpa konten sesudahnya diabaikan.", pending_break)
        return blocks

    def _build_call(self, b: BoundCall) -> list[Block]:
        name = b.name
        if name in ("TEXT", "P") or _HEADING_SHORTCUT.match(name):
            para = self._text_component(b)
            if para is not None:
                suppress = getattr(self, "_suppress_next_h1_break", False)
                para = self._apply_heading_page_break(para, b, suppress=suppress)
                if para.is_heading and para.level == 1:
                    self._suppress_next_h1_break = False
            return [para] if para is not None else []
        if name == "TEXTBLOCK":
            block = self._textblock(b)
            return [block] if block is not None else []
        if name == "FIGURE":
            fig = self._figure(b)
            return [fig] if fig is not None else []
        if name == "TABLE":
            table = self._table(b)
            return [table] if table is not None else []
        if name in ("LIST", "BULLET"):
            lst = self._list(b)
            return [lst] if lst is not None else []
        if name == "CALLOUT":
            callout = self._callout(b)
            return [callout] if callout is not None else []
        if name == "MATH":
            return [self._math(b)]
        if name == "TOC":
            return [self._toc(b)]
        if name == "LISTOFTABLES":
            return [ListOfTablesBlock(title=str(b.args.get("title") or "Daftar Tabel"), source=b.loc)]
        if name == "LISTOFFIGURES":
            return [ListOfFiguresBlock(title=str(b.args.get("title") or "Daftar Gambar"), source=b.loc)]
        if name == "SHAPE":
            return [self._shape(b)] if self._shape(b) else []
        if name == "CODE":
            return [self._code(b)]
        if name == "CHART":
            chart = self._chart(b)
            return [chart] if chart is not None else []
        if name == "LABEL":
            return [self._label(b)]
        if name == "BIBLIOGRAPHY":
            return [self._bibliography(b)]
        if name == "COLUMNS":
            return [self._columns_start(b)]
        if name == "ENDCOLUMNS":
            return [ColumnsEnd(source=b.loc)]
        if name == "SECTION":
            sec = self._section(b)
            if sec.break_type in ("next_page", "even_page", "odd_page"):
                self._suppress_next_h1_break = True
            return [sec]
        if name == "HR":
            return [self._hr(b)]
        if name == "LINE":
            return [self._line(b)]
        raise AssertionError(f"komponen isi tidak dikenal: {name}")  # pragma: no cover

    # ------------------------------------------------------------ page break
    def _with_break(self, block: Block) -> Block:
        if isinstance(block, Paragraph):
            return self._paragraph_with_break(block)
        if isinstance(block, TextBlock):
            first = self._paragraph_with_break(block.paragraphs[0])
            return dataclasses.replace(block, paragraphs=(first,) + block.paragraphs[1:])
        return dataclasses.replace(block, page_break_before=True)

    @staticmethod
    def _paragraph_with_break(p: Paragraph) -> Paragraph:
        return dataclasses.replace(
            p,
            overrides={**p.overrides, "page_break_before": True},
            effective={**p.effective, "page_break_before": True},
        )

    # ----------------------------------------------------------------- style
    def _select_style(
        self,
        b: BoundCall,
        style_key: str = "style",
        role: str | None = None,
        level: int | None = None,
    ) -> tuple[ResolvedStyle, str, int | None] | None:
        style_name = b.get(style_key)
        if style_name is not None:
            loc = b.loc_of(style_key)
            if not self.registry.exists(style_name):
                self.diag.error(
                    "STYLE_NOT_FOUND",
                    f"Style {style_name!r} tidak ditemukan.",
                    loc,
                    hint=hint_for(style_name, self.registry.names()),
                )
                return None
            st = self.registry.get(style_name)
            if st is None:
                return None  # kesalahan style sudah dilaporkan
            if role is not None and st.role not in (None, "body") and role != st.role:
                self.diag.error(
                    "ROLE_STYLE_CONFLICT",
                    f"Role {role!r} bertentangan dengan role style {style_name!r} ({st.role!r}).",
                    loc,
                )
                return None
            eff_role = role if role is not None else (st.role or "body")
        else:
            eff_role = role if role is not None else "body"
            st = None
        eff_level: int | None = None
        if eff_role == "heading":
            if level is not None:
                eff_level = level
                if st is not None and st.role == "heading" and st.level is not None and st.level != level:
                    self.diag.error(
                        "ROLE_STYLE_CONFLICT",
                        f"Level {level} bertentangan dengan level style {st.name!r} ({st.level}).",
                        b.loc_of("level") if "level" in b else b.loc,
                    )
                    return None
            elif st is not None and st.role == "heading":
                eff_level = st.level
            if eff_level is None:
                self.diag.error(
                    "MISSING_HEADING_LEVEL",
                    "Role 'heading' membutuhkan level 1-9 (melalui argumen level atau style).",
                    b.loc,
                )
                return None
            if st is None:
                st = self.registry.heading_style(eff_level)
        else:
            if level is not None:
                self.diag.error("LEVEL_WITHOUT_HEADING", "Argumen level hanya berlaku untuk role 'heading'.", b.loc_of("level") if "level" in b else b.loc)
                return None
            if st is None:
                st = self.registry.style_for_role(eff_role)
        if st is None:
            return None
        return st, eff_role, eff_level

    def _make_paragraph(
        self,
        text: str,
        st: ResolvedStyle,
        role: str,
        level: int | None,
        overrides: dict[str, Any],
        loc: Location,
        segments: tuple = (),
    ) -> Paragraph:
        self._paragraph_count += 1
        if self._paragraph_count > self.limits.max_paragraphs:
            from ..diagnostics import Diagnostic, FatalDsxError, Severity

            raise FatalDsxError(
                Diagnostic(Severity.ERROR, "LIMIT_EXCEEDED", f"Jumlah paragraf melebihi batas {self.limits.max_paragraphs}.", loc)
            )
        self.used_styles.add(st.name)
        effective = {**st.props, **overrides}
        if ("indent_left" in overrides or "indent_first" in overrides) and effective["indent_left"] + effective["indent_first"] < -1e-6:
            self.diag.warning(
                "INDENT_OUTSIDE_MARGIN",
                "Baris pertama paragraf berada di luar margin kiri (indent_left + indent_first < 0). "
                "Untuk hanging indent, kombinasikan hanging_indent dengan left_indent yang sama besar.",
                loc,
            )
        return Paragraph(
            text=text,
            role=role,
            level=level,
            style=st.name,
            overrides=dict(overrides),
            effective=effective,
            source=loc,
            segments=segments,
        )

    # ------------------------------------------------------------------ text
    def _text_value(self, value: Any) -> str:
        if isinstance(value, TextRef):
            return self.store.text(value.path)
        return value

    def _role_level_args(self, b: BoundCall) -> tuple[str | None, int | None]:
        m = _HEADING_SHORTCUT.match(b.name)
        if m:
            return "heading", int(m.group(1))
        return b.get("role"), b.get("level")

    def _text_component(self, b: BoundCall) -> Paragraph | None:
        role, level = self._role_level_args(b)
        selected = self._select_style(b, role=role, level=level)
        if selected is None:
            return None
        st, eff_role, eff_level = selected
        raw = b.args["text"]
        if isinstance(raw, list):
            return self._segmented_paragraph(b, raw, st, eff_role, eff_level)
        parts = split_paragraphs(self._text_value(raw), preserve_breaks=eff_role == "code")
        if not parts:
            self.diag.warning("EMPTY_TEXT", f"{b.name}() menerima teks kosong; paragraf kosong dibuat.", b.loc_of("text"))
            text = ""
        else:
            if len(parts) > 1:
                self.diag.warning(
                    "TEXT_MULTIPLE_PARAGRAPHS",
                    f"Teks pada {b.name}() berisi beberapa paragraf dan digabung menjadi satu; gunakan TEXTBLOCK() untuk memisahkannya.",
                    b.loc_of("text"),
                )
            text = ("\n\n" if eff_role == "code" else " ").join(parts)
        return self._make_paragraph(text, st, eff_role, eff_level, b.visual_overrides(), b.loc)

    def _segmented_paragraph(self, b: BoundCall, raw: list, st: ResolvedStyle, role: str, level: int | None) -> Paragraph | None:
        """Paragraf dari list segmen: teks, IMATH, BOLD/ITALIC/UNDERLINE, LINK, FOOTNOTE."""
        if role == "code":
            self.diag.error(
                "INLINE_MATH_NOT_ALLOWED",
                "Segmen list tidak dapat dipakai pada role 'code'; teks kode harus berupa string biasa.",
                b.loc_of("text"),
            )
            return None
        segments: list = []
        buffer: list[str] = []

        def flush() -> None:
            if buffer:
                text = re.sub(r"[ \t\f\v\n]+", " ", "".join(buffer))
                buffer.clear()
                if text:
                    segments.append(TextSeg(text))

        for item in raw:
            if isinstance(item, ParsedMath):
                flush()
                segments.append(MathSeg(item.source, item.tree))
            elif isinstance(item, StyledText):
                flush()
                t = re.sub(r"[ \t\f\v\n]+", " ", item.text)
                if t:
                    segments.append(TextSeg(t, bold=item.bold, italic=item.italic, underline=item.underline, highlight=getattr(item, 'highlight', None)))
            elif isinstance(item, LinkValue):
                flush()
                t = re.sub(r"[ \t\f\v\n]+", " ", item.text)
                if t:
                    segments.append(
                        LinkSeg(t, item.url, bold=item.bold, italic=item.italic, underline=item.underline)
                    )
            elif isinstance(item, FootnoteValue):
                flush()
                self._footnote_seq += 1
                fid = self._footnote_seq
                self._footnotes.append(FootnoteDef(fid, item.text))
                segments.append(FootnoteSeg(fid, item.text))
            elif isinstance(item, CommentValue):
                flush()
                self._comment_seq += 1
                cid = self._comment_seq
                self._comments.append(CommentDef(cid, item.text, author=item.author, initials=item.initials))
                segments.append(CommentSeg(cid, item.text, author=item.author, initials=item.initials))
            elif isinstance(item, RefValue):
                flush()
                display = item.text or f"[{item.label_id}]"
                segments.append(RefSeg(item.label_id, display))
            elif isinstance(item, CiteValue):
                flush()
                display = f"[{item.key}]" + (f", {item.pages}" if item.pages else "")
                segments.append(CiteSeg(item.key, display, item.pages))
            else:
                buffer.append(str(item))
        flush()
        # trim outer plain TextSeg only
        if segments and isinstance(segments[0], TextSeg) and not (segments[0].bold or segments[0].italic or segments[0].underline):
            segments[0] = TextSeg(segments[0].text.lstrip(" "), segments[0].bold, segments[0].italic, segments[0].underline)
        if segments and isinstance(segments[-1], TextSeg) and not (segments[-1].bold or segments[-1].italic or segments[-1].underline):
            segments[-1] = TextSeg(segments[-1].text.rstrip(" "), segments[-1].bold, segments[-1].italic, segments[-1].underline)
        segments = [s for s in segments if not (isinstance(s, TextSeg) and s.text == "")]
        needs_segments = any(
            isinstance(s, (MathSeg, LinkSeg, FootnoteSeg, RefSeg, CiteSeg, CommentSeg))
            or (isinstance(s, TextSeg) and (s.bold or s.italic or s.underline or getattr(s, 'highlight', None)))
            for s in segments
        )
        plain = "".join(
            s.text if isinstance(s, (TextSeg, LinkSeg))
            else (s.display if isinstance(s, (RefSeg, CiteSeg)) else "")
            for s in segments
        )
        if not segments:
            self.diag.warning("EMPTY_TEXT", f"{b.name}() menerima teks kosong; paragraf kosong dibuat.", b.loc_of("text"))
        return self._make_paragraph(
            plain, st, role, level, b.visual_overrides(), b.loc, tuple(segments) if needs_segments else ()
        )

    def _toc(self, b: BoundCall) -> TocBlock:
        title = str(b.get("title", "Daftar Isi"))
        depth = int(b.get("depth", 3))
        return TocBlock(title, depth, False, b.loc)

    def _textblock(self, b: BoundCall) -> TextBlock | None:
        role, level = self._role_level_args(b)
        selected = self._select_style(b, role=role, level=level)
        if selected is None:
            return None
        st, eff_role, eff_level = selected
        if eff_role == "heading":
            self.diag.error(
                "HEADING_IN_TEXTBLOCK",
                "TEXTBLOCK() tidak dapat berperan sebagai heading; gunakan TEXT() atau H1()-H9().",
                b.loc,
            )
            return None
        parts = split_paragraphs(self._text_value(b.args["text"]), preserve_breaks=eff_role == "code")
        if not parts:
            self.diag.warning("EMPTY_CONTENT", "Konten TEXTBLOCK() kosong; tidak ada paragraf yang dibuat.", b.loc_of("text"))
            return None
        overrides = b.visual_overrides()
        paragraphs = tuple(self._make_paragraph(t, st, eff_role, eff_level, overrides, b.loc) for t in parts)
        return TextBlock(paragraphs, b.loc)

    # ---------------------------------------------------------------- figure
    def _caption(self, b: BoundCall, text: str, overrides: dict[str, Any] | None = None) -> Paragraph | None:
        selected = self._select_style(b, style_key="caption_style", role="caption")
        if selected is None:
            return None
        st, eff_role, eff_level = selected
        cleaned = collapse_spaces(" ".join(collapse_spaces(l) for l in text.split("\n")))
        return self._make_paragraph(cleaned, st, "caption", None, overrides or {}, b.loc_of("caption"))

    def _figure(self, b: BoundCall) -> Figure | None:
        ref = b.args["src"]
        info = self.store.image(ref.path)
        data = self.store.bytes_of(ref.path)
        native_w = info.px_width / info.dpi_x * 2.54
        native_h = info.px_height / info.dpi_y * 2.54
        width = b.get("width")
        height = b.get("height")
        if width is not None and height is not None:
            w, h = float(width), float(height)
        elif width is not None:
            w = float(width)
            h = w * native_h / native_w
        elif height is not None:
            h = float(height)
            w = h * native_w / native_h
        else:
            w, h = native_w, native_h
        max_w = self.page.content_width
        max_h = self.page.content_height
        factor = min(1.0, max_w / w, max_h / h)
        if factor < 1.0:
            self.diag.warning(
                "FIGURE_RESIZED",
                f"Gambar {ref.path!r} diperkecil agar muat pada area halaman ({max_w:.2f} x {max_h:.2f} cm).",
                b.loc,
            )
            w *= factor
            h *= factor
        w = max(w, 0.01)
        h = max(h, 0.01)
        caption = None
        if "caption" in b:
            caption = self._caption(b, b.args["caption"])
            if caption is None:
                return None
        asset = ImageAsset(ref.path, data, info.content_type)
        label_id = b.args.get("id") if isinstance(b.args.get("id"), str) else None
        if label_id:
            self._register_label(label_id, "figure")
        return Figure(asset, round(w, 4), round(h, 4), b.get("align", "center"), b.get("alt", ""), caption, False, b.loc, label_id)

    # ----------------------------------------------------------------- table
    def _to_cell(self, value: Any) -> TableCell:
        """Nilai sel → TableCell (dukung list segmen kaya dan CELL merge)."""
        from ..values import CellValue
        if isinstance(value, CellValue):
            inner = self._to_cell(value.text)
            return TableCell(
                inner.text,
                inner.segments,
                rowspan=value.rowspan,
                colspan=value.colspan,
                shading=value.shading,
                align=value.align,
                valign=value.valign,
                borders=getattr(value, "borders", None),
            )
        if isinstance(value, list):
            from ..values import ImageRef
            expanded = []
            for item in value:
                if isinstance(item, ImageRef):
                    try:
                        data = self.store.load(item.path, "image")
                        info = self.store.image(item.path)
                        expanded.append(ImageSeg(item.path, data, info.content_type, width_cm=2.2))
                    except Exception as exc:
                        self.diag.error("SOURCE_ERROR", str(exc), None)
                        expanded.append("")
                else:
                    expanded.append(item)
            footnote_seq = [self._footnote_seq]
            segs, plain = raw_to_segments(expanded, self._footnotes, footnote_seq)
            self._footnote_seq = footnote_seq[0]
            return TableCell(plain, tuple(segs))
        if isinstance(value, (StyledText, LinkValue, FootnoteValue, ParsedMath)):
            footnote_seq = [self._footnote_seq]
            segs, plain = raw_to_segments([value], self._footnotes, footnote_seq)
            self._footnote_seq = footnote_seq[0]
            return TableCell(plain, tuple(segs))
        from ..values import ImageRef as _ImageRef
        if isinstance(value, _ImageRef):
            try:
                data = self.store.load(value.path, "image")
                info = self.store.image(value.path)
                seg = ImageSeg(value.path, data, info.content_type, width_cm=2.2)
                return TableCell("", (seg,))
            except Exception as exc:
                self.diag.error("SOURCE_ERROR", str(exc), None)
                return TableCell("", ())
        if isinstance(value, bool):
            t = "true" if value else "false"
        elif isinstance(value, float):
            t = format(value, ".15g")
        else:
            t = str(value)
        return TableCell(t, ())


    def _hr(self, b: BoundCall) -> HorizontalRule:
        style = str(b.args.get("style") or "solid").lower()
        width = str(b.args.get("width") or "100%")
        thickness = float(b.args["thickness"]) if b.args.get("thickness") is not None else 1.0
        color = str(b.args.get("color") or "000000").lstrip("#")
        align = str(b.args.get("align") or "center").lower()
        sb = float(b.args["space_before"]) if b.args.get("space_before") is not None else 6.0
        sa = float(b.args["space_after"]) if b.args.get("space_after") is not None else 6.0
        return HorizontalRule(
            style=style,
            width=width,
            thickness_pt=thickness,
            color=color,
            align=align,
            space_before_pt=sb,
            space_after_pt=sa,
            page_break_before=False,
            source=b.loc,
        )

    def _line(self, b: BoundCall) -> FormLine:
        count = int(b.args.get("count") or 1)
        style = str(b.args.get("style") or "dots").lower()
        length = str(b.args.get("length") or "40")
        label = str(b.args.get("label") or "")
        gap = float(b.args["gap"]) if b.args.get("gap") is not None else 6.0
        return FormLine(
            count=count,
            style=style,
            length=length,
            label=label,
            gap_pt=gap,
            page_break_before=False,
            source=b.loc,
        )


    def _shape(self, b: BoundCall) -> ShapeBlock | None:
        stype = str(b.args.get("type") or "rect")
        stype = {"rect": "rect", "ellipse": "ellipse", "line": "line", "roundrect": "roundRect"}.get(stype.strip().lower(), "rect")
        w = float(b.args["width"]) if b.args.get("width") is not None else 5.0
        h = float(b.args["height"]) if b.args.get("height") is not None else 3.0
        fill = b.args.get("fill")
        stroke = b.args.get("stroke")
        sw = float(b.args["stroke_width"]) if b.args.get("stroke_width") is not None else 1.0
        corner = float(b.args["corner"]) if b.args.get("corner") is not None else 0.3
        x1 = float(b.args["x1"]) if b.args.get("x1") is not None else 0.0
        y1 = float(b.args["y1"]) if b.args.get("y1") is not None else 0.0
        x2 = float(b.args["x2"]) if b.args.get("x2") is not None else w
        y2 = float(b.args["y2"]) if b.args.get("y2") is not None else 0.0
        align = str(b.args.get("align") or "center").lower()
        fill_img = None
        img_ref = b.args.get("fill_image")
        if img_ref is not None:
            from ..values import ImageRef
            if isinstance(img_ref, ImageRef):
                try:
                    data = self.store.load(img_ref.path, "image")
                    info = self.store.image(img_ref.path)
                    fill_img = ImageAsset(img_ref.path, data, info.content_type)
                except Exception as exc:
                    self.diag.error("SOURCE_ERROR", str(exc), b.loc)
                    return None
        return ShapeBlock(
            shape_type=stype, width_cm=w, height_cm=h,
            fill=str(fill).lstrip("#") if fill else None,
            stroke=str(stroke).lstrip("#") if stroke is not None else "000000",
            stroke_width_pt=sw, corner_cm=corner,
            x1=x1, y1=y1, x2=x2, y2=y2, fill_image=fill_img, align=align, source=b.loc,
        )

    def _build_table_border_sides(self, args: dict, default_w: float, default_c: str) -> dict | None:
        """Parse optional per-side border_* args on TABLE into a sides dict.
        Returns None when no side-specific args are present (use preset only).
        """
        side_map = {
            "top": "top",
            "bottom": "bottom",
            "left": "left",
            "right": "right",
            "inside_h": "insideH",
            "inside_v": "insideV",
        }
        result: dict = {}
        for arg_key, edge in side_map.items():
            style = args.get(f"border_{arg_key}")
            color = args.get(f"border_{arg_key}_color")
            width = args.get(f"border_{arg_key}_width")
            if style is None and color is None and width is None:
                continue
            result[edge] = {
                "style": str(style or "single").lower(),
                "color": str(color or default_c).lstrip("#"),
                "width_pt": float(width) if width is not None else default_w,
            }
        return result or None

    def _table(self, b: BoundCall) -> Table | None:
        has_data = "data" in b
        has_inline = "rows" in b or "headers" in b
        if has_data and has_inline:
            self.diag.error("TABLE_CONFLICT", "TABLE() tidak boleh memakai data sekaligus headers/rows.", b.loc)
            return None
        if not has_data and not has_inline:
            self.diag.error("MISSING_ARGUMENT", "TABLE() membutuhkan headers/rows atau data=CSV(...).", b.loc)
            return None
        header: list[str] | None
        body: list[list[str]]
        if has_data:
            ref: CsvRef = b.args["data"]
            rows = self.store.csv_rows(ref.path, ref.delimiter)
            if not rows:
                self.diag.error("EMPTY_TABLE", "CSV tidak berisi baris data.", b.loc_of("data"), reference=ref.path)
                return None
            if b.get("header", True):
                header = list(rows[0])
                body = [list(r) for r in rows[1:]]
            else:
                header = None
                body = [list(r) for r in rows]
        else:
            if "header" in b:
                self.diag.error("ARGUMENT_NOT_APPLICABLE", "Argumen 'header' hanya berlaku bersama data=CSV(...).", b.loc_of("header"))
                return None
            header = list(b.args["headers"]) if "headers" in b else None
            body = [[self._to_cell(c) for c in row] for row in b.get("rows", [])]
        def _col_span(cell) -> int:
            from ..values import CellValue
            from .nodes import TableCell as TC
            if isinstance(cell, CellValue):
                return max(1, cell.colspan)
            if isinstance(cell, TC):
                return max(1, cell.colspan)
            return 1

        if header is not None:
            columns = sum(_col_span(c) for c in header) if header and not isinstance(header[0], str) else len(header)
            # header from CSV/strlist is plain strings
            if header and isinstance(header[0], str):
                columns = len(header)
        else:
            columns = sum(_col_span(c) for c in body[0]) if body else 0
        if columns == 0:
            self.diag.error("EMPTY_TABLE", "Tabel tidak memiliki kolom.", b.loc)
            return None
        # Validate row widths accounting for rowspan occupancy from previous rows
        ok = True
        # occupancy[r][c] = True if covered by a rowspan originating above
        from ..values import CellValue as _CV
        from .nodes import TableCell as _TC

        def _rs(cell) -> int:
            if isinstance(cell, (_CV, _TC)):
                return max(1, int(getattr(cell, "rowspan", 1) or 1))
            return 1

        # We only validate body rows here; build virtual grid
        occ: set[tuple[int, int]] = set()
        for number, row in enumerate(body, start=0):
            c = 0
            consumed = 0
            for cell in row:
                while (number, c) in occ and c < columns:
                    c += 1
                if c >= columns:
                    self.diag.error(
                        "TABLE_ROW_WIDTH_MISMATCH",
                        f"Baris data ke-{number + 1} memiliki terlalu banyak sel setelah rowspan/colspan.",
                        b.loc_of("rows") if "rows" in b else b.loc,
                    )
                    ok = False
                    break
                cs = _col_span(cell)
                rs = _rs(cell)
                for dr in range(rs):
                    for dc in range(cs):
                        if dr == 0 and dc == 0:
                            continue
                        occ.add((number + dr, c + dc))
                c += cs
                consumed += cs
            # remaining columns must be covered by occupancy
            while c < columns:
                if (number, c) not in occ:
                    self.diag.error(
                        "TABLE_ROW_WIDTH_MISMATCH",
                        f"Baris data ke-{number + 1} memiliki lebar efektif kurang dari {columns} kolom (rowspan/colspan).",
                        b.loc_of("rows") if "rows" in b else b.loc,
                    )
                    ok = False
                    break
                c += 1
        if not ok:
            return None
        total_rows = len(body) + (1 if header is not None else 0)
        if columns > self.limits.max_table_columns or total_rows > self.limits.max_table_rows + 1 or total_rows * columns > self.limits.max_table_cells:
            self.diag.error(
                "LIMIT_EXCEEDED",
                f"Ukuran tabel melebihi batas ({self.limits.max_table_columns} kolom, {self.limits.max_table_rows} baris, {self.limits.max_table_cells} sel).",
                b.loc,
            )
            return None
        caption = None
        if "caption" in b:
            caption = self._caption(b, b.args["caption"])
            if caption is None:
                return None
        def as_cells(row):
            out = []
            for c in row:
                if isinstance(c, TableCell):
                    out.append(c)
                else:
                    out.append(self._to_cell(c))
            return tuple(out)

        header_cells = as_cells(header) if header is not None else None
        body_cells = tuple(as_cells(r) for r in body)
        # length limit on plain text
        for cell in (list(header_cells) if header_cells else []) + [c for row in body_cells for c in row]:
            if len(cell.text) > self.limits.max_cell_chars:
                self.diag.error("LIMIT_EXCEEDED", f"Sel tabel melebihi {self.limits.max_cell_chars} karakter.", b.loc)
                return None
        label_id = b.args.get("id") if isinstance(b.args.get("id"), str) else None
        if label_id:
            self._register_label(label_id, "table")
        # human-readable labels for header
        labels = b.args.get("labels")
        if labels and header_cells is not None:
            labs = list(labels)
            new_header = []
            for i, cell in enumerate(header_cells):
                if i < len(labs) and labs[i]:
                    new_header.append(TableCell(str(labs[i]), cell.segments, cell.rowspan, cell.colspan, cell.merged, cell.shading, cell.align, cell.valign))
                else:
                    new_header.append(cell)
            header_cells = tuple(new_header)
        repeat_header = b.args.get("repeat_header")
        if repeat_header is None:
            repeat_header = True
        num_fmt = str(b.args["number_format"]) if b.args.get("number_format") else None
        # apply number format to body cells that look numeric
        if num_fmt and body_cells:
            body_cells = self._format_table_numbers(body_cells, num_fmt)
        widths = b.args.get("widths")
        col_widths = tuple(str(x) for x in widths) if widths else None
        keep_rows = bool(b.args.get("keep_rows", False))
        autofit = bool(b.args.get("autofit", False))
        border = str(b.args.get("border") or "grid").lower()
        bw = float(b.args["border_width"]) if b.args.get("border_width") is not None else 0.5
        bc = str(b.args.get("border_color") or "000000").lstrip("#")
        # Build optional per-side border overrides (TABLE level)
        border_sides = self._build_table_border_sides(b.args, bw, bc)
        hs = b.args.get("header_shading")
        if hs is None:
            hs = "D9D9D9"
        else:
            hs = str(hs).lstrip("#") if str(hs).lower() not in ("none", "") else None
        pad = float(b.args["cell_padding"]) if b.args.get("cell_padding") is not None else None
        return Table(
            header_cells,
            body_cells,
            b.get("align", "center"),
            caption,
            False,
            b.loc,
            label_id,
            bool(repeat_header),
            num_fmt,
            col_widths,
            keep_rows,
            autofit,
            border,
            bw,
            bc,
            border_sides,
            hs,
            pad,
            float(b.args["row_height"]) if b.args.get("row_height") is not None else None,
        )

    # ------------------------------------------------------------------ list
    def _list(self, b: BoundCall) -> ListBlock | None:
        selected = self._select_style(b, role=None) if "style" in b else None
        if "style" in b and selected is None:
            return None
        st = selected[0] if selected else self.registry.get("list-item")
        if st is None:
            return None
        items: list[ListItem] = []
        footnote_seq = [self._footnote_seq]

        def is_segment_list(entry: list) -> bool:
            """True hanya bila list memuat segmen kaya (bukan sub-daftar string murni)."""
            if not entry or any(isinstance(x, list) for x in entry):
                return False
            return any(isinstance(x, (ParsedMath, StyledText, LinkValue, FootnoteValue, RefValue, CiteValue)) for x in entry)

        def walk(seq: list, level: int) -> None:
            for entry in seq:
                if isinstance(entry, list) and not is_segment_list(entry):
                    walk(entry, level + 1)
                    continue
                if isinstance(entry, list):
                    # rich segment item
                    segs, plain = raw_to_segments(entry, self._footnotes, footnote_seq)
                    if not plain and not segs:
                        self.diag.warning("EMPTY_LIST_ITEM", "Item daftar kosong dilewati.", b.loc_of("items"))
                        continue
                    items.append(ListItem(plain, level, (), tuple(segs)))
                    continue
                # single rich value as item
                if isinstance(entry, (RefValue, CiteValue, StyledText, LinkValue, FootnoteValue, ParsedMath)):
                    segs, plain = raw_to_segments([entry], self._footnotes, footnote_seq)
                    items.append(ListItem(plain, level, (), tuple(segs)))
                    continue
                # plain string item
                parts = split_paragraphs(str(entry), preserve_breaks=False)
                if not parts:
                    self.diag.warning("EMPTY_LIST_ITEM", "Item daftar kosong dilewati.", b.loc_of("items"))
                    continue
                items.append(ListItem(parts[0], level, tuple(parts[1:]), ()))

        walk(b.args["items"], 0)
        self._footnote_seq = footnote_seq[0]
        if not items:
            self.diag.warning("EMPTY_LIST", f"{b.name}() tidak memiliki item; tidak ada daftar yang dibuat.", b.loc_of("items"))
            return None
        if items[0].level != 0:
            base = min(i.level for i in items)
            items = [ListItem(i.text, i.level - base, i.continuations, i.segments) for i in items]
        ordered = True if b.name == "LIST" and b.get("ordered", False) else False
        if "start" in b and not ordered:
            self.diag.error("ARGUMENT_NOT_APPLICABLE", "Argumen 'start' hanya berlaku untuk daftar berurutan (ordered=true).", b.loc_of("start"))
            return None
        indent = float(b.get("indent", 1.0))
        hanging = float(b.get("hanging", 0.7))
        if hanging > indent:
            self.diag.error(
                "LIST_INDENT_INVALID",
                "hanging tidak boleh lebih besar dari indent (teks item tingkat 0 akan berada di luar margin).",
                b.loc_of("hanging"),
                found=f"indent={indent:g}cm hanging={hanging:g}cm",
            )
            return None
        self._paragraph_count += len(items) + sum(len(i.continuations) for i in items)
        if self._paragraph_count > self.limits.max_paragraphs:
            from ..diagnostics import Diagnostic, FatalDsxError, Severity

            raise FatalDsxError(Diagnostic(Severity.ERROR, "LIMIT_EXCEEDED", f"Jumlah paragraf melebihi batas {self.limits.max_paragraphs}.", b.loc))
        self.used_styles.add(st.name)
        overrides = b.visual_overrides()
        return ListBlock(
            tuple(items), ordered, int(b.get("start", 1)), st.name, overrides, {**st.props, **overrides}, False, b.loc, indent, hanging
        )

    # --------------------------------------------------------------- callout
    def _callout(self, b: BoundCall) -> Callout | None:
        variant = b.get("type", "note")
        if "style" in b:
            selected = self._select_style(b, role="callout")
            if selected is None:
                return None
            body_style = selected[0]
        else:
            body_style = self.registry.get(f"callout-{variant}")
        title_style = self.registry.get("callout-title")
        if body_style is None or title_style is None:
            return None
        raw_text = b.args["text"]
        title_text = collapse_spaces(" ".join(collapse_spaces(l) for l in b.get("title", "").split("\n")))
        theme = CALLOUT_THEMES[variant]
        title = None
        if title_text:
            title = self._make_paragraph(title_text, title_style, "callout", None, {"color": theme["title"]}, b.loc_of("title"))
        overrides = b.visual_overrides()
        body_paras: list[Paragraph] = []
        if isinstance(raw_text, list):
            footnote_seq = [self._footnote_seq]
            segs, plain = raw_to_segments(raw_text, self._footnotes, footnote_seq)
            self._footnote_seq = footnote_seq[0]
            if not plain and not segs and not title_text:
                self.diag.error("EMPTY_CALLOUT", "CALLOUT() membutuhkan teks atau judul yang tidak kosong.", b.loc_of("text"))
                return None
            if not plain and not segs:
                self.diag.warning("EMPTY_TEXT", "Teks CALLOUT() kosong; hanya judul yang ditampilkan.", b.loc_of("text"))
            else:
                body_paras.append(
                    self._make_paragraph(plain, body_style, "callout", None, overrides, b.loc, tuple(segs) if segs else ())
                )
        else:
            parts = split_paragraphs(self._text_value(raw_text), preserve_breaks=False)
            if len(parts) > self.limits.max_callout_paragraphs:
                self.diag.error("LIMIT_EXCEEDED", f"Callout melebihi {self.limits.max_callout_paragraphs} paragraf.", b.loc)
                return None
            if not parts and not title_text:
                self.diag.error("EMPTY_CALLOUT", "CALLOUT() membutuhkan teks atau judul yang tidak kosong.", b.loc_of("text"))
                return None
            if not parts:
                self.diag.warning("EMPTY_TEXT", "Teks CALLOUT() kosong; hanya judul yang ditampilkan.", b.loc_of("text"))
            body_paras = [self._make_paragraph(t, body_style, "callout", None, overrides, b.loc) for t in parts]
        return Callout(variant, title, tuple(body_paras), False, b.loc)

    # ------------------------------------------------------------------ math
    def _math(self, b: BoundCall) -> MathBlock:
        parsed = b.args["expr"]
        st = self.registry.get("equation")
        assert st is not None
        self.used_styles.add(st.name)
        self._paragraph_count += 1
        label_id = b.args.get("id") if isinstance(b.args.get("id"), str) else None
        if label_id:
            self._register_label(label_id, "equation")
        return MathBlock(
            parsed.source, parsed.tree, b.get("align", "center"), b.get("size"), st.name, {}, dict(st.props), False, b.loc, label_id
        )


    # ---------------------------------------------------------------- v0.5
    def _next_label(self, kind: str) -> str:
        self._label_counters[kind] = self._label_counters.get(kind, 0) + 1
        n = self._label_counters[kind]
        names = {
            "figure": "Gambar",
            "table": "Tabel",
            "equation": "Persamaan",
            "section": "Bagian",
            "chart": "Gambar",
            "code": "Kode",
        }
        return f"{names.get(kind, kind.capitalize())} {n}"

    def _register_label(self, label_id: str | None, kind: str) -> str | None:
        if not label_id:
            return None
        display = self._next_label(kind)
        self.labels[label_id] = display
        return label_id

    def _code(self, b: BoundCall) -> CodeBlock:
        raw = b.args.get("text")
        text = self._text_value(raw) if raw is not None else ""
        lang = (b.args.get("lang") or b.args.get("language") or "plain")
        if isinstance(lang, str):
            lang = lang.lower()
        else:
            lang = "plain"
        line_numbers = bool(b.args.get("line_numbers", False))
        caption_text = b.args.get("caption")
        caption = self._caption(b, str(caption_text)) if caption_text else None
        st = self.registry.get("code") or self.registry.get("normal")
        assert st is not None
        self.used_styles.add(st.name)
        label_id = b.args.get("id") if isinstance(b.args.get("id"), str) else None
        if label_id:
            self._register_label(label_id, "code")
        overrides = b.visual_overrides() if hasattr(b, "visual_overrides") else {}
        return CodeBlock(
            text=text,
            language=lang,
            caption=caption,
            line_numbers=line_numbers,
            style=st.name,
            overrides=overrides,
            effective=dict(st.props),
            source=b.loc,
            label_id=label_id,
        )

    def _chart(self, b: BoundCall) -> ChartBlock | None:
        from ..charts import ChartError, generate_chart
        from ..values import CsvRef

        ctype = str(b.args.get("type") or "bar").lower()
        data = b.args.get("data")
        headers: list[str] = []
        rows: list[list] = []
        if isinstance(data, CsvRef):
            csv_rows = self.store.csv_rows(data.path, data.delimiter)
            if not csv_rows:
                self.diag.error("EMPTY_TABLE", "CSV chart kosong.", b.loc_of("data"), reference=data.path)
                return None
            headers = list(csv_rows[0])
            rows = [list(r) for r in csv_rows[1:]]
        elif data is None:
            self.diag.error("MISSING_ARGUMENT", "CHART membutuhkan data=CSV(...).", b.loc)
            return None
        else:
            self.diag.error("INVALID_VALUE", "CHART.data harus CSV(...).", b.loc)
            return None

        width = float(b.args.get("width") or 12.0)
        height = float(b.args.get("height") or 7.0)
        title = str(b.args.get("title") or "")
        xlabel = str(b.args.get("xlabel") or "")
        ylabel = str(b.args.get("ylabel") or "")
        x_col = b.args.get("x")
        y_col = b.args.get("y")
        series = b.args.get("series")
        if series is not None and not isinstance(series, (list, tuple)):
            series = None
        align = str(b.args.get("align") or "center").lower()
        caption_text = b.args.get("caption")
        caption = self._caption(b, str(caption_text)) if caption_text else None
        label_id = b.args.get("id") if isinstance(b.args.get("id"), str) else None
        if label_id:
            self._register_label(label_id, "chart")

        try:
            png = generate_chart(
                ctype,
                headers,
                rows,
                x_col=str(x_col) if x_col else None,
                y_col=str(y_col) if y_col else None,
                series=list(series) if series else None,
                title=title,
                xlabel=xlabel,
                ylabel=ylabel,
                width_cm=width,
                height_cm=height,
            )
        except ChartError as e:
            self.diag.error("CHART_ERROR", str(e), b.loc)
            return None
        except Exception as e:  # pragma: no cover
            self.diag.error("CHART_ERROR", f"Gagal membuat chart: {e}", b.loc)
            return None

        asset = ImageAsset(path="chart.png", data=png, content_type="image/png")
        return ChartBlock(
            image=asset,
            width_cm=width,
            height_cm=height,
            align=align,
            chart_type=ctype,
            title=title,
            caption=caption,
            source=b.loc,
            label_id=label_id,
        )

    def _label(self, b: BoundCall) -> LabelMarker:
        lid = str(b.args.get("id") or "")
        kind = str(b.args.get("kind") or "section").lower()
        if lid:
            self._register_label(lid, kind)
        return LabelMarker(label_id=lid, kind=kind, source=b.loc)

    def _bibliography(self, b: BoundCall) -> BibliographyBlock:
        if "title" in b.args:
            title = str(b.args.get("title") or "")
        else:
            title = "Daftar Pustaka"
        style_name = str(b.args.get("style") or "simple").lower()
        return BibliographyBlock(
            title=title,
            style_name=style_name,
            items=tuple(self.bib_items),
            source=b.loc,
        )

    def _columns_start(self, b: BoundCall) -> ColumnsStart:
        count = int(b.args.get("count") or 2)
        gap = float(b.args.get("gap") or 0.5)
        return ColumnsStart(count=count, gap_cm=gap, source=b.loc)




    def _apply_heading_page_break(self, para: Paragraph, b: BoundCall, *, suppress: bool = False) -> Paragraph:
        """H1 defaults to page_break_before unless overridden or suppressed (e.g. after SECTION next_page)."""
        import dataclasses
        if not para.is_heading or para.level != 1:
            return para
        ov = dict(para.overrides)
        if "page_break_before" in ov:
            return para
        if "page_break_before" in b.args:
            return para
        if suppress:
            return para
        ov["page_break_before"] = True
        eff = dict(para.effective)
        eff["page_break_before"] = True
        return dataclasses.replace(para, overrides=ov, effective=eff)


    def _format_table_numbers(self, rows: tuple, fmt: str) -> tuple:
        """Format numeric cell text: thousands | percent | decimal:N | currency[:IDR|USD|EUR]."""
        def fmt_val(text: str) -> str:
            s = text.strip()
            try:
                v = float(s.replace(",", ""))
            except ValueError:
                return text
            import math as _math
            if not _math.isfinite(v):
                return text
            if fmt == "thousands":
                if v == int(v):
                    return f"{int(v):,}".replace(",", ".")
                return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            if fmt == "percent":
                return f"{v:.1f}%"
            if fmt.startswith("decimal:"):
                try:
                    n = int(fmt.split(":", 1)[1])
                except ValueError:
                    n = 2
                return f"{v:.{n}f}"
            if fmt == "currency" or fmt.startswith("currency:"):
                cur = "IDR"
                if ":" in fmt:
                    cur = fmt.split(":", 1)[1].upper() or "IDR"
                symbols = {"IDR": "Rp", "USD": "US$", "EUR": "€", "JPY": "¥"}
                sym = symbols.get(cur, cur + " ")
                if cur == "IDR":
                    return f"{sym}{int(round(v)):,}".replace(",", ".")
                return f"{sym}{v:,.2f}"
            return text

        from .nodes import TableCell
        out = []
        for row in rows:
            nr = []
            for c in row:
                if isinstance(c, TableCell) and c.text and not c.segments:
                    nr.append(TableCell(fmt_val(c.text), (), c.rowspan, c.colspan, c.merged))
                else:
                    nr.append(c)
            out.append(tuple(nr))
        return tuple(out)

    def _section(self, b: BoundCall) -> SectionBreak:
        br = str(b.args.get("break") or b.args.get("type") or "next_page").lower()
        if br not in ("next_page", "continuous", "even_page", "odd_page"):
            br = "next_page"
        orient = b.args.get("orientation")
        pnf = b.args.get("page_number_format")
        pns = b.args.get("page_number_start")
        restart = bool(b.args.get("page_number_restart", pns is not None))
        show = b.args.get("show_page_number")
        if show is None:
            show = True
        cols = int(b.args.get("columns") or 1)
        gap = float(b.args.get("column_gap") or 0.5)
        title = str(b.args.get("title") or "")
        # margins
        mt = mb = ml = mr = None
        if b.args.get("margin") is not None:
            m = float(b.args["margin"])
            mt = mb = ml = mr = m
        if b.args.get("margin_top") is not None:
            mt = float(b.args["margin_top"])
        if b.args.get("margin_bottom") is not None:
            mb = float(b.args["margin_bottom"])
        if b.args.get("margin_left") is not None:
            ml = float(b.args["margin_left"])
        if b.args.get("margin_right") is not None:
            mr = float(b.args["margin_right"])
        return SectionBreak(
            break_type=br,
            orientation=str(orient) if orient else None,
            page_size=str(b.args["size"]) if b.args.get("size") else None,
            mirror_margins=bool(b.args.get("mirror_margins", False)),
            gutter_cm=float(b.args["gutter"]) if b.args.get("gutter") is not None else 0.0,
            page_number_format=str(pnf).lower() if pnf else None,
            page_number_start=int(pns) if pns is not None else None,
            page_number_restart=restart,
            show_page_number=bool(show),
            columns=cols,
            column_gap_cm=gap,
            title=title,
            margin_top=mt,
            margin_bottom=mb,
            margin_left=ml,
            margin_right=mr,
            header_text=str(b.args["header"]) if b.args.get("header") is not None else None,
            footer_text=str(b.args["footer"]) if b.args.get("footer") is not None else None,
            different_first_page=bool(b.args.get("different_first_page", False)),
            page_number_align=str(b.args.get("page_number_align") or "center").lower(),
            page_number_position=str(b.args.get("page_number_position") or "footer").lower(),
            page_number_placement=str(b.args["page_number_placement"]).lower() if b.args.get("page_number_placement") else None,
            page_number_format_text=str(b.args["page_number_format_text"]) if b.args.get("page_number_format_text") else None,
            page_number_continue=bool(b.args.get("page_number_continue", False)),
            header_distance_cm=float(b.args["header_distance"]) if b.args.get("header_distance") is not None else None,
            footer_distance_cm=float(b.args["footer_distance"]) if b.args.get("footer_distance") is not None else None,
            odd_even_header=bool(b.args.get("odd_even_header", False)),
            header_odd=str(b.args["header_odd"]) if b.args.get("header_odd") is not None else None,
            header_even=str(b.args["header_even"]) if b.args.get("header_even") is not None else None,
            footer_odd=str(b.args["footer_odd"]) if b.args.get("footer_odd") is not None else None,
            footer_even=str(b.args["footer_even"]) if b.args.get("footer_even") is not None else None,
            source=b.loc,
        )

    def resolve_references(self, blocks: list) -> None:
        """Second pass: resolve REF/CITE display text from labels and bibliography."""
        labels = self.labels
        # citation order: first appearance order for numeric styles
        cite_keys: list[str] = []
        bib_by_key = {it["key"]: it for it in self.bib_items if it.get("key")}

        def resolve_segs(segs: tuple) -> tuple:
            if not segs:
                return segs
            out = []
            for s in segs:
                if isinstance(s, RefSeg):
                    if s.label_id in labels:
                        display = labels[s.label_id]
                        # keep override text if user provided explicit text that isn't placeholder
                        if s.display and not s.display.startswith("["):
                            display = s.display
                        out.append(RefSeg(s.label_id, display))
                    else:
                        self.diag.warning(
                            "UNDEFINED_REF",
                            f"REF({s.label_id!r}) tidak menemukan target label.",
                            None,
                        )
                        out.append(RefSeg(s.label_id, s.display or f"[{s.label_id}?]"))
                elif isinstance(s, CiteSeg):
                    key = s.key
                    if key not in cite_keys:
                        cite_keys.append(key)
                    if key not in bib_by_key:
                        self.diag.warning(
                            "UNDEFINED_CITE",
                            f"CITE({key!r}) tidak menemukan BIBITEM.",
                            None,
                        )
                        out.append(CiteSeg(key, s.display or f"[{key}?]", s.pages))
                    else:
                        # Number by bibliography order (stable match with BIBLIOGRAPHY list)
                        bib_order = [it["key"] for it in self.bib_items if it.get("key")]
                        n = (bib_order.index(key) + 1) if key in bib_order else (cite_keys.index(key) + 1)
                        it = bib_by_key[key]
                        author = (it.get("author") or "").split(",")[0].strip()
                        year = it.get("year") or ""
                        if author and year:
                            display = f"({author}, {year}" + (f", hlm. {s.pages}" if s.pages else "") + ")"
                        else:
                            display = f"[{n}]" + (f", {s.pages}" if s.pages else "")
                        out.append(CiteSeg(key, display, s.pages))
                else:
                    out.append(s)
            return tuple(out)

        import dataclasses
        from .nodes import Paragraph, Table, ListBlock, Callout, Figure, ChartBlock, CodeBlock

        for i, block in enumerate(blocks):
            if isinstance(block, Paragraph) and block.segments:
                new_segs = resolve_segs(block.segments)
                plain = "".join(
                    s.text if isinstance(s, (TextSeg, LinkSeg))
                    else (s.display if isinstance(s, (RefSeg, CiteSeg)) else "")
                    for s in new_segs
                )
                blocks[i] = dataclasses.replace(block, segments=new_segs, text=plain)
            elif isinstance(block, ListBlock):
                new_items = []
                for item in block.items:
                    if item.segments:
                        ns = resolve_segs(item.segments)
                        plain = "".join(
                            s.text if isinstance(s, (TextSeg, LinkSeg))
                            else (s.display if isinstance(s, (RefSeg, CiteSeg)) else "")
                            for s in ns
                        )
                        new_items.append(dataclasses.replace(item, segments=ns, text=plain))
                    else:
                        new_items.append(item)
                blocks[i] = dataclasses.replace(block, items=tuple(new_items))
            elif isinstance(block, Callout):
                new_body = []
                for p in block.body:
                    if p.segments:
                        ns = resolve_segs(p.segments)
                        plain = "".join(
                            s.text if isinstance(s, (TextSeg, LinkSeg))
                            else (s.display if isinstance(s, (RefSeg, CiteSeg)) else "")
                            for s in ns
                        )
                        new_body.append(dataclasses.replace(p, segments=ns, text=plain))
                    else:
                        new_body.append(p)
                blocks[i] = dataclasses.replace(block, body=tuple(new_body))
            elif isinstance(block, Table):
                def fix_cell(c):
                    if not c.segments:
                        return c
                    ns = resolve_segs(c.segments)
                    plain = "".join(
                        s.text if isinstance(s, (TextSeg, LinkSeg))
                        else (s.display if isinstance(s, (RefSeg, CiteSeg)) else "")
                        for s in ns
                    )
                    return dataclasses.replace(c, segments=ns, text=plain)
                header = tuple(fix_cell(c) for c in block.header) if block.header else None
                rows = tuple(tuple(fix_cell(c) for c in row) for row in block.rows)
                blocks[i] = dataclasses.replace(block, header=header, rows=rows)
        self._cite_order = cite_keys
