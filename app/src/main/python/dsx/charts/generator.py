
"""Generate chart images (PNG). Prefer matplotlib; fall back to pure PIL."""

from __future__ import annotations

import io
import math
from typing import Any, Sequence


class ChartError(Exception):
    pass


def generate_chart(
    chart_type: str,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    *,
    x_col: str | None = None,
    y_col: str | None = None,
    series: Sequence[str] | None = None,
    title: str = "",
    xlabel: str = "",
    ylabel: str = "",
    width_cm: float = 12.0,
    height_cm: float = 7.0,
) -> bytes:
    if not headers or not rows:
        raise ChartError("Data chart kosong.")
    try:
        return _matplotlib_chart(
            chart_type, headers, rows,
            x_col=x_col, y_col=y_col, series=series,
            title=title, xlabel=xlabel, ylabel=ylabel,
            width_cm=width_cm, height_cm=height_cm,
        )
    except Exception:
        return _pil_chart(
            chart_type, headers, rows,
            x_col=x_col, y_col=y_col, series=series,
            title=title, xlabel=xlabel, ylabel=ylabel,
            width_cm=width_cm, height_cm=height_cm,
        )


def _col_index(headers: Sequence[str], name: str | None, default: int) -> int:
    if name and name in headers:
        return list(headers).index(name)
    return default


def _numeric(vals: list[Any]) -> list[float]:
    out: list[float] = []
    for v in vals:
        try:
            out.append(float(v))
        except (TypeError, ValueError):
            out.append(0.0)
    return out


def _extract(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    x_col: str | None,
    y_col: str | None,
    series: Sequence[str] | None,
) -> tuple[list[str], list[list[float]], list[str]]:
    xi = _col_index(headers, x_col, 0)
    labels = [str(r[xi]) if xi < len(r) else "" for r in rows]
    if series:
        ycols = list(series)
    elif y_col:
        ycols = [y_col]
    else:
        ycols = [headers[1]] if len(headers) > 1 else [headers[0]]
    series_vals: list[list[float]] = []
    for s in ycols:
        yi = _col_index(headers, s, 1 if len(headers) > 1 else 0)
        series_vals.append(_numeric([r[yi] if yi < len(r) else 0 for r in rows]))
    return labels, series_vals, ycols


def _matplotlib_chart(
    chart_type: str,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    *,
    x_col: str | None,
    y_col: str | None,
    series: Sequence[str] | None,
    title: str,
    xlabel: str,
    ylabel: str,
    width_cm: float,
    height_cm: float,
) -> bytes:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels, series_vals, ycols = _extract(headers, rows, x_col, y_col, series)
    ctype = chart_type.lower()
    fig_w = max(width_cm / 2.54, 3.0)
    fig_h = max(height_cm / 2.54, 2.0)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=120)
    try:
        if ctype == "pie":
            ax.pie(series_vals[0], labels=labels, autopct="%1.1f%%", startangle=90)
            ax.axis("equal")
        elif ctype in ("bar", "hbar"):
            import numpy as np

            x = np.arange(len(labels))
            n = len(series_vals)
            width = 0.8 / max(n, 1)
            for i, (vals, name) in enumerate(zip(series_vals, ycols)):
                offset = (i - n / 2) * width + width / 2
                if ctype == "hbar":
                    ax.barh(x + offset, vals, height=width, label=name)
                else:
                    ax.bar(x + offset, vals, width=width, label=name)
            if ctype == "hbar":
                ax.set_yticks(x)
                ax.set_yticklabels(labels)
            else:
                ax.set_xticks(x)
                ax.set_xticklabels(labels, rotation=30, ha="right")
            if n > 1:
                ax.legend()
        elif ctype in ("line", "area", "scatter"):
            xs = list(range(len(labels)))
            for vals, name in zip(series_vals, ycols):
                if ctype == "scatter":
                    ax.scatter(xs, vals, label=name)
                elif ctype == "area":
                    ax.fill_between(xs, vals, alpha=0.4, label=name)
                    ax.plot(xs, vals)
                else:
                    ax.plot(xs, vals, marker="o", label=name)
            ax.set_xticks(xs)
            ax.set_xticklabels(labels, rotation=30, ha="right")
            if len(ycols) > 1:
                ax.legend()
        else:
            raise ChartError(f"Jenis chart tidak didukung: {chart_type}")
        if title:
            ax.set_title(title)
        if xlabel:
            ax.set_xlabel(xlabel)
        if ylabel:
            ax.set_ylabel(ylabel)
        fig.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        return buf.getvalue()
    finally:
        plt.close(fig)


def _pil_chart(
    chart_type: str,
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    *,
    x_col: str | None,
    y_col: str | None,
    series: Sequence[str] | None,
    title: str,
    xlabel: str,
    ylabel: str,
    width_cm: float,
    height_cm: float,
) -> bytes:
    """Minimal chart renderer using only Pillow (always available via python-docx stack or std)."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as e:
        raise ChartError(
            "Tidak bisa membuat chart: butuh matplotlib atau Pillow. "
            "pip install matplotlib  atau  pip install pillow"
        ) from e

    labels, series_vals, ycols = _extract(headers, rows, x_col, y_col, series)
    ctype = chart_type.lower()
    dpi = 120
    W = max(int(width_cm / 2.54 * dpi), 400)
    H = max(int(height_cm / 2.54 * dpi), 280)
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
        font_sm = font
    except Exception:
        font = None
        font_sm = None

    margin_l, margin_r, margin_t, margin_b = 50, 20, 40, 50
    plot_x0, plot_y0 = margin_l, margin_t
    plot_x1, plot_y1 = W - margin_r, H - margin_b
    pw, ph = plot_x1 - plot_x0, plot_y1 - plot_y0

    if title and font:
        draw.text((W // 2 - len(title) * 3, 8), title, fill="black", font=font)

    colors = ["#4C78A8", "#F58518", "#E45756", "#72B7B2", "#54A24B", "#B279A2"]

    if ctype == "pie":
        vals = series_vals[0]
        total = sum(vals) or 1.0
        cx, cy = (plot_x0 + plot_x1) // 2, (plot_y0 + plot_y1) // 2
        r = min(pw, ph) // 2 - 10
        bbox = [cx - r, cy - r, cx + r, cy + r]
        start = -90.0
        for i, v in enumerate(vals):
            extent = 360.0 * v / total
            draw.pieslice(bbox, start, start + extent, fill=colors[i % len(colors)], outline="white")
            start += extent
        # legend
        ly = plot_y0
        for i, lab in enumerate(labels):
            draw.rectangle([plot_x1 - 90, ly, plot_x1 - 78, ly + 10], fill=colors[i % len(colors)])
            if font_sm:
                draw.text((plot_x1 - 74, ly - 2), str(lab)[:12], fill="black", font=font_sm)
            ly += 14
    else:
        all_vals = [v for s in series_vals for v in s] or [0.0]
        vmin, vmax = min(0.0, min(all_vals)), max(all_vals) or 1.0
        if vmax == vmin:
            vmax = vmin + 1.0
        n = len(labels) or 1
        nseries = len(series_vals)

        # axes
        draw.line([(plot_x0, plot_y1), (plot_x1, plot_y1)], fill="#333")
        draw.line([(plot_x0, plot_y0), (plot_x0, plot_y1)], fill="#333")

        if ctype in ("bar", "hbar"):
            if ctype == "bar":
                group_w = pw / n
                bar_w = group_w * 0.8 / nseries
                for si, vals in enumerate(series_vals):
                    for i, v in enumerate(vals):
                        h = int((v - vmin) / (vmax - vmin) * ph)
                        x = int(plot_x0 + i * group_w + group_w * 0.1 + si * bar_w)
                        y = plot_y1 - h
                        draw.rectangle([x, y, x + max(int(bar_w) - 1, 1), plot_y1], fill=colors[si % len(colors)])
                for i, lab in enumerate(labels):
                    if font_sm:
                        draw.text((int(plot_x0 + i * group_w + 4), plot_y1 + 4), str(lab)[:8], fill="black", font=font_sm)
            else:  # hbar
                group_h = ph / n
                bar_h = group_h * 0.8 / nseries
                for si, vals in enumerate(series_vals):
                    for i, v in enumerate(vals):
                        w = int((v - vmin) / (vmax - vmin) * pw)
                        y = int(plot_y0 + i * group_h + group_h * 0.1 + si * bar_h)
                        draw.rectangle([plot_x0, y, plot_x0 + max(w, 1), y + max(int(bar_h) - 1, 1)], fill=colors[si % len(colors)])
                for i, lab in enumerate(labels):
                    if font_sm:
                        draw.text((4, int(plot_y0 + i * group_h + 2)), str(lab)[:8], fill="black", font=font_sm)
        else:  # line / area / scatter
            for si, vals in enumerate(series_vals):
                pts = []
                for i, v in enumerate(vals):
                    x = plot_x0 + (i / max(n - 1, 1)) * pw
                    y = plot_y1 - (v - vmin) / (vmax - vmin) * ph
                    pts.append((x, y))
                if ctype == "area" and len(pts) >= 2:
                    poly = [(plot_x0, plot_y1)] + pts + [(plot_x1, plot_y1)]
                    draw.polygon(poly, fill=colors[si % len(colors)] + "55" if False else colors[si % len(colors)])
                    # solid fill without alpha: darker outline
                    draw.line(pts, fill="#222", width=2)
                elif ctype == "scatter":
                    for x, y in pts:
                        draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=colors[si % len(colors)])
                else:
                    if len(pts) >= 2:
                        draw.line(pts, fill=colors[si % len(colors)], width=2)
                    for x, y in pts:
                        draw.ellipse([x - 2, y - 2, x + 2, y + 2], fill=colors[si % len(colors)])
            for i, lab in enumerate(labels):
                if font_sm:
                    x = plot_x0 + (i / max(n - 1, 1)) * pw
                    draw.text((int(x) - 8, plot_y1 + 4), str(lab)[:8], fill="black", font=font_sm)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
