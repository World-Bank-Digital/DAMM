"""Offline, deterministic presentation primitives for DAR working papers.

The stage modules retain their domain semantics. This module owns the visual grammar:
safe standalone HTML, print rules, common hierarchy, restrained tables and charts, and
the language that prevents planning ranges or proposals from masquerading as rankings
or findings. It has no network or third-party runtime dependency.
"""

from __future__ import annotations

from collections import defaultdict
from html import escape
import math
from typing import Any, Iterable, Mapping, Sequence


INK = "#17322a"
FOREST = "#245844"
SAGE = "#719783"
MOSS = "#e9f0eb"
SAND = "#f4efe5"
AMBER = "#b7791f"
RED = "#9b3b32"
PALETTE = (FOREST, SAGE, "#9cb7a8", "#d8b66a", "#c67d62", "#8096a5")

_STYLE = r"""
:root{--ink:#17322a;--forest:#245844;--sage:#719783;--moss:#e9f0eb;
--sand:#f4efe5;--amber:#b7791f;--red:#9b3b32;--line:#d7e0da;--muted:#5c6d65}
*{box-sizing:border-box}html{background:#eef2ef;color:var(--ink)}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}
body{margin:0;font:15px/1.62 Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.page{width:min(1040px,calc(100% - 32px));margin:28px auto;background:#fff;
box-shadow:0 16px 48px rgba(23,50,42,.12);border:1px solid rgba(23,50,42,.08)}
.masthead{padding:42px 48px 34px;background:linear-gradient(135deg,#173f33,#245844);color:#fff;position:relative}
.masthead:after{content:"";position:absolute;inset:auto 0 0;height:5px;background:linear-gradient(90deg,#d8b66a 0 24%,#8fb19f 24% 67%,#fff 67% 100%)}
.eyebrow{font-size:11px;font-weight:700;letter-spacing:.16em;text-transform:uppercase;opacity:.8}
h1{max-width:850px;margin:.45rem 0 .6rem;font:600 clamp(30px,5vw,52px)/1.05 Georgia,serif;letter-spacing:-.025em}
.subtitle{max-width:760px;margin:0;color:#e5eee9;font-size:17px}.country{margin-top:1.1rem;font-weight:650}
.lifecycle{display:flex;gap:12px;align-items:flex-start;padding:15px 48px;background:#fff7e8;border-bottom:1px solid #ecd8ad;color:#664613}
.lifecycle strong{font-size:12px;letter-spacing:.08em;text-transform:uppercase}.lifecycle span{color:#735b32}
.metadata{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1px;background:var(--line);border-bottom:1px solid var(--line)}
.metadata div{padding:14px 20px;background:#f8faf8}.metadata dt{color:var(--muted);font-size:10px;font-weight:700;letter-spacing:.1em;text-transform:uppercase}.metadata dd{margin:3px 0 0;font-weight:650}
main{padding:20px 48px 54px}section{padding:24px 0;border-bottom:1px solid #e7ece8}section:last-child{border-bottom:0}
h2{margin:0 0 14px;font:600 27px/1.18 Georgia,serif;letter-spacing:-.01em}h3{margin:22px 0 8px;font-size:17px}p{margin:8px 0 12px}p,td,li,.notice,.card{overflow-wrap:anywhere;word-break:break-word}
.lede{font:19px/1.55 Georgia,serif;color:#28483d}.muted{color:var(--muted)}
.notice{margin:14px 0;padding:13px 15px;border-left:4px solid var(--sage);background:#f5f8f6}.notice strong{display:block;margin-bottom:3px}.notice.proposal{border-color:var(--amber);background:#fff8eb}.notice.risk{border-color:var(--red);background:#fff4f1}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(155px,1fr));gap:12px;margin:16px 0}.card{padding:15px;border:1px solid var(--line);border-radius:6px;background:#fbfcfb}.card .value{font:600 27px/1 Georgia,serif;color:var(--forest)}.card .label{margin-top:8px;font-size:11px;font-weight:750;text-transform:uppercase;letter-spacing:.06em}.card .note{margin-top:4px;color:var(--muted);font-size:12px}
.table-wrap{max-width:100%;overflow-x:auto;margin:15px 0}table{border-collapse:collapse;width:100%;font-size:12.5px}th{padding:9px 10px;background:var(--ink);color:#fff;text-align:left;font-size:10px;letter-spacing:.07em;text-transform:uppercase}td{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}tbody tr:nth-child(even){background:#f8faf8}td.num{text-align:right;font-variant-numeric:tabular-nums}
a{color:#1b6550;text-decoration-thickness:1px;text-underline-offset:2px}ul,ol{padding-left:1.35rem}li{margin:.3rem 0}
.chart{margin:18px 0;padding:16px;border:1px solid var(--line);border-radius:7px;background:#fbfcfb}.chart svg{display:block;width:100%;height:auto}.chart figcaption{margin-top:9px;color:var(--muted);font-size:11px}.chart-title{font-size:15px;font-weight:700;fill:var(--ink)}.chart-label{font-size:11px;fill:var(--ink)}.chart-note{font-size:10px;fill:#5c6d65}.chart-value{font-size:10px;font-weight:700;fill:var(--ink)}
.footer{padding:18px 48px 24px;border-top:1px solid var(--line);color:var(--muted);font-size:10px}
@page{size:A4;margin:14mm 13mm 16mm}@media print{*{-webkit-print-color-adjust:exact;print-color-adjust:exact}html{background:#fff}.page{width:100%;margin:0;border:0;box-shadow:none}.masthead{padding:24px 28px;border-bottom:5px solid var(--sage)}.lifecycle{padding:10px 28px}main{padding:10px 28px 24px}.metadata div{break-inside:avoid}.chart,.card,tr{break-inside:avoid}.notice,.cards,.short-table,.keep-together{break-inside:avoid}.table-wrap{overflow:visible}thead{display:table-header-group}tfoot{display:table-footer-group}h2,h3{break-after:avoid-page}.lede,.notice{orphans:3;widows:3}a{color:inherit;text-decoration:none}.footer{padding:12px 28px}}
@media(max-width:640px){.page{width:100%;margin:0;border:0}.masthead,.lifecycle,main,.footer{padding-left:22px;padding-right:22px}.lifecycle{display:block}.metadata{grid-template-columns:1fr 1fr}}
"""


def _text(value: Any) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _bounded_label(value: Any, limit: int) -> str:
    normalized = " ".join(str(value or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(1, limit - 1)].rstrip() + "…"


def _compact_number(value: float) -> str:
    for divisor, suffix in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if value >= divisor:
            scaled = value / divisor
            return f"{scaled:.1f}".rstrip("0").rstrip(".") + suffix
    return f"{value:,.0f}"


def document(*, title: str, country: str, subtitle: str, status: str,
             body: str, metadata: Sequence[tuple[str, Any]] = (),
             footer: str = "DAR Studio · Evidence-backed working paper") -> str:
    """Return one standalone, offline, print-ready HTML document."""
    metadata_html = ""
    if metadata:
        cells = "".join(
            f"<div><dt>{_text(label)}</dt><dd>{_text(value)}</dd></div>"
            for label, value in metadata
        )
        metadata_html = f"<dl class=\"metadata\">{cells}</dl>"
    return "\n".join((
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        f"<title>{_text(title)} · {_text(country)}</title><style>{_STYLE}</style></head>",
        '<body><article class="page">',
        '<header class="masthead"><div class="eyebrow">DAR Studio · Analytical working paper</div>',
        f"<h1>{_text(title)}</h1><p class=\"subtitle\">{_text(subtitle)}</p>",
        f"<div class=\"country\">{_text(country)}</div></header>",
        '<div class="lifecycle"><strong>Lifecycle</strong>',
        f"<span>{_text(status)}</span></div>",
        metadata_html,
        f"<main>{body}</main>",
        f"<footer class=\"footer\">{_text(footer)}</footer>",
        "</article></body></html>\n",
    ))


def section(title: str, body: str, *, lede: str | None = None) -> str:
    lead = f'<p class="lede">{_text(lede)}</p>' if lede else ""
    return f"<section><h2>{_text(title)}</h2>{lead}{body}</section>"


def paragraph(value: Any, *, muted: bool = False) -> str:
    cls = ' class="muted"' if muted else ""
    return f"<p{cls}>{_text(value)}</p>"


def notice(title: str, text: Any, *, tone: str = "neutral") -> str:
    style = tone if tone in {"proposal", "risk"} else ""
    return f'<div class="notice {style}"><strong>{_text(title)}</strong>{_text(text)}</div>'


def safe_link(label: Any, url: Any) -> str:
    value = str(url or "").strip()
    if not (value.startswith("https://") or value.startswith("http://")):
        return _text(label)
    return f'<a href="{_text(value)}" rel="noreferrer">{_text(label)}</a>'


def metric_cards(items: Iterable[tuple[Any, Any, Any | None]]) -> str:
    cards = []
    for label, value, note_text in items:
        note_html = f'<div class="note">{_text(note_text)}</div>' if note_text else ""
        cards.append(
            f'<div class="card"><div class="value">{_text(value)}</div>'
            f'<div class="label">{_text(label)}</div>{note_html}</div>'
        )
    return f'<div class="cards">{"".join(cards)}</div>'


def keep_together(*parts: str) -> str:
    """Group a short explanatory lead with the visual or cards it introduces."""

    return f'<div class="keep-together">{"".join(parts)}</div>'


def table(headers: Sequence[Any], rows: Iterable[Sequence[Any]],
          *, numeric_columns: Iterable[int] = ()) -> str:
    numeric = set(numeric_columns)
    head = "".join(f'<th scope="col">{_text(cell)}</th>' for cell in headers)
    caption = "Table columns: " + "; ".join(str(cell) for cell in headers)
    body = []
    for row in rows:
        cells = "".join(
            f'<td class="num">{_text(cell)}</td>'
            if index in numeric
            else f'<td>{_text(cell)}</td>'
            for index, cell in enumerate(row)
        )
        body.append(f"<tr>{cells}</tr>")
    wrapper_class = "table-wrap short-table" if len(body) <= 5 else "table-wrap"
    return (
        f'<div class="{wrapper_class}"><table><caption class="sr-only">{_text(caption)}</caption>'
        '<thead><tr>' + head
        + "</tr></thead><tbody>" + "".join(body) + "</tbody></table></div>"
    )


def _figure(title: str, svg: str, caption: str, *, height: int | None = None) -> str:
    view_height = height if height is not None else svg.count("data-row") * 34 + 105
    return (
        '<figure class="chart">'
        f'<svg viewBox="0 0 760 {view_height}" role="img" '
        f'aria-label="{_text(title)}"><title>{_text(title)}</title>{svg}</svg>'
        f"<figcaption>{_text(caption)}</figcaption></figure>"
    )


def composition_bar_svg(title: str, items: Sequence[tuple[str, int]], *, missing: int = 0) -> str:
    values = [(str(label), max(0, int(count))) for label, count in items]
    if missing > 0:
        values.append(("Missing / unclassified", int(missing)))
    total = sum(count for _label, count in values)
    width = 650
    x = 80
    parts = [f'<text x="0" y="18" class="chart-title">{_text(title)}</text>']
    cursor = x
    for index, (label, count) in enumerate(values):
        segment = 0 if total == 0 else width * count / total
        parts.append(
            f'<rect x="{cursor:.2f}" y="36" width="{segment:.2f}" height="26" '
            f'fill="{PALETTE[index % len(PALETTE)]}" data-row="1"><title>'
            f'{_text(label)}: {count}</title></rect>'
        )
        cursor += segment
    legend_y = 84
    for index, (label, count) in enumerate(values):
        pct = 0 if total == 0 else count / total * 100
        column = index % 3
        row = index // 3
        lx = 10 + column * 245
        ly = legend_y + row * 22
        parts.extend((
            f'<rect x="{lx}" y="{ly - 10}" width="10" height="10" fill="{PALETTE[index % len(PALETTE)]}"/>',
            f'<text x="{lx + 16}" y="{ly}" class="chart-label">{_text(label)} — {count} ({pct:.0f}%)</text>',
        ))
    return _figure(title, "".join(parts), f"Composition uses {total} total records; denominator is shown explicitly.")


def milestone_timeline_svg(title: str, milestones: Sequence[Mapping[str, Any]]) -> str:
    ordered = sorted(
        (item for item in milestones if isinstance(item.get("year"), int)),
        key=lambda item: (int(item["year"]), str(item.get("label") or "")),
    )
    line_end = max(60, 48 + len(ordered) * 56)
    parts = [
        f'<text x="0" y="18" class="chart-title">{_text(title)}</text>',
        '<line x1="110" y1="48" x2="110" y2="{0}" stroke="#9cb7a8" stroke-width="3"/>'.format(line_end),
    ]
    for index, item in enumerate(ordered):
        y = 58 + index * 56
        candidate = bool(item.get("candidate"))
        color = AMBER if candidate else FOREST
        full_label = str(item.get("label") or "Untitled")
        visible_label = _bounded_label(full_label, 82 if candidate else 112)
        parts.extend((
            f'<circle cx="110" cy="{y}" r="8" fill="{color}" data-row="1"/>',
            f'<text x="8" y="{y + 4}" class="chart-value">{int(item["year"])}</text>',
            f'<g><title>{_text(full_label)}</title><text x="132" y="{y + 4}" '
            f'class="chart-label">{_text(visible_label)}</text></g>',
        ))
        if candidate:
            parts.append(
                f'<text x="132" y="{y + 20}" class="chart-note" fill="{AMBER}">'
                "candidate milestone · Proposed / unratified</text>"
            )
    return _figure(
        title,
        "".join(parts),
        "Amber milestones are proposals bound to candidate or unratified measures, not evidence findings.",
        height=line_end + 32,
    )


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) and number >= 0 else None


def range_bar_svg(title: str, ranges: Sequence[Mapping[str, Any]]) -> str:
    groups: dict[str, list[tuple[str, float, float]]] = defaultdict(list)
    for item in ranges:
        low = _finite_number(item.get("low"))
        high = _finite_number(item.get("high"))
        currency = str(item.get("currency") or "").strip()
        label = str(item.get("label") or "").strip()
        if low is None or high is None or high < low or not currency or not label:
            continue
        groups[currency].append((label, low, high))
    parts = [f'<text x="0" y="18" class="chart-title">{_text(title)}</text>']
    y = 48
    for currency in sorted(groups):
        entries = sorted(groups[currency], key=lambda item: item[0])
        scale = max((high for _label, _low, high in entries), default=1) or 1
        parts.append(
            f'<text x="0" y="{y}" class="chart-value">{_text(currency)} — independently scaled</text>'
        )
        y += 22
        for label, low, high in entries:
            start = 220 + 350 * low / scale
            width = max(2, 350 * (high - low) / scale)
            full_title = f"{label}: {low:,.0f}–{high:,.0f} {currency}"
            parts.extend((
                f'<g><title>{_text(full_title)}</title><text x="0" y="{y + 13}" '
                f'class="chart-label">{_text(_bounded_label(label, 32))}</text></g>',
                f'<line x1="220" y1="{y + 9}" x2="570" y2="{y + 9}" stroke="#e2e8e4"/>',
                f'<rect x="{start:.2f}" y="{y}" width="{width:.2f}" height="18" rx="3" fill="{FOREST}" data-row="1"/>',
                f'<text x="748" y="{y + 13}" text-anchor="end" class="chart-note">'
                f'{_text(_compact_number(low))}–{_text(_compact_number(high))}</text>',
            ))
            y += 30
        y += 12
    return _figure(
        title,
        "".join(parts),
        "Currencies use separate scales. Preliminary planning ranges are decision inputs, not a ranking.",
        height=max(130, y + 20),
    )
