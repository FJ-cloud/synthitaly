#!/usr/bin/env python3
"""Shared HTML furniture for the generated report pages.

Four pages are built from this module — ``build_results_page.py`` (validation),
``build_flows_page.py`` (money flows + paper map), ``build_savers_debt_page.py``
(the savers & debt study) and ``build_data_appendix.py`` (the dataset appendix).
They used to be one page; the CSS and the little fragment helpers were on their
way to being copy-pasted four times, which is exactly how the numbers in this
repo drifted apart once before (see the header of ``synthitaly/features.py``).
One definition, four callers.

Every page produced here is **self-contained**: images are inlined as base64
data-URIs and there is not a single network request, so the file can be mailed,
zipped, or opened from a USB stick years from now and still render.

Nothing in here knows anything about the model — it is presentation only.
"""
from __future__ import annotations

import html as _html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "presentation" / "figures"

# --------------------------------------------------------------------------- #
# The stylesheet. Kept as a plain string (single braces) so callers can drop it
# into an f-string page without doubling every brace.
#
# Colours are defined once on :root as light, then *redefined* under
# prefers-color-scheme: dark. No colour gets its only definition inside the
# media query, so a viewer with no preference still gets a complete palette.
# --------------------------------------------------------------------------- #
CSS = """
:root {
  --bg:#fbfbf9; --card:#fff; --ink:#14140f; --ink2:#4b4a44; --muted:#8a887f;
  --line:#e4e3db; --accent:#2a78d6; --ok:#008300; --warn:#c23b3b; --hl:#f5f2e6;
  --tier1:#0f7a52; --tier2:#b9761f; --tier3:#c23b3b; --tierM:#5b6470;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
          --bg:#131311; --card:#1c1c19; --ink:#f0efe9; --ink2:#b8b6ad; --muted:#86847c;
          --line:#33322c; --accent:#6ea8ee; --ok:#4fbb6a; --warn:#e8756f; --hl:#26261f;
          --tier1:#4fbb8a; --tier2:#d9a05b; --tier3:#e8756f; --tierM:#9aa2ad; }
}
/* Some hosts (the claude.ai artifact viewer among them) stamp an explicit theme on
   the root element instead of relying on the OS preference. Repeating the dark
   palette here lets an explicit choice win in both directions: the guard above keeps
   data-theme="light" light on a dark OS, and this keeps data-theme="dark" dark on a
   light one. Tokens only — no component ever takes a colour from inside these
   blocks, so an unstamped document still gets a complete palette from :root. */
:root[data-theme="dark"] {
          --bg:#131311; --card:#1c1c19; --ink:#f0efe9; --ink2:#b8b6ad; --muted:#86847c;
          --line:#33322c; --accent:#6ea8ee; --ok:#4fbb6a; --warn:#e8756f; --hl:#26261f;
          --tier1:#4fbb8a; --tier2:#d9a05b; --tier3:#e8756f; --tierM:#9aa2ad; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:16px/1.65 -apple-system,
  "Segoe UI", system-ui, sans-serif; }
.wrap { max-width:1080px; margin:0 auto; padding:0 24px 80px; }
header { padding:56px 0 8px; }
h1 { font-size:2.4rem; margin:0 0 6px; letter-spacing:-.02em; }
.sub { color:var(--ink2); font-size:1.05rem; margin:0; }
.meta { color:var(--muted); font-size:.85rem; margin-top:10px; }
nav { position:sticky; top:0; background:var(--bg); border-bottom:1px solid var(--line);
  padding:10px 0; margin:24px 0 0; z-index:5; display:flex; gap:18px; flex-wrap:wrap; }
nav a { color:var(--ink2); text-decoration:none; font-size:.86rem; font-weight:600; }
nav a:hover { color:var(--accent); }
section { padding:44px 0 8px; border-bottom:1px solid var(--line); }
.kicker { font-size:.74rem; letter-spacing:.14em; text-transform:uppercase;
  color:var(--muted); font-weight:700; }
h2 { font-size:1.6rem; margin:4px 0 16px; letter-spacing:-.01em; }
h3 { font-size:1.05rem; margin:30px 0 10px; color:var(--ink2); }
h4 { font-size:.92rem; margin:22px 0 8px; color:var(--ink2); }
p { margin:0 0 14px; max-width:74ch; }
a { color:var(--accent); }
code { font:.88em ui-monospace, "SF Mono", Menlo, monospace; background:var(--hl);
  padding:1px 5px; border-radius:4px; }
pre { background:var(--card); border:1px solid var(--line); border-radius:8px;
  padding:14px 16px; overflow-x:auto; font:.84rem/1.6 ui-monospace, "SF Mono", Menlo, monospace; }
pre code { background:none; padding:0; }
.scroll { overflow-x:auto; margin:16px 0 20px; }
table { border-collapse:collapse; width:100%; font-size:.9rem; background:var(--card); }
th, td { text-align:left; padding:9px 12px; border-bottom:1px solid var(--line);
  vertical-align:top; }
th { font-size:.76rem; letter-spacing:.06em; text-transform:uppercase; color:var(--muted);
  border-bottom:2px solid var(--line); white-space:nowrap; }
td.r, th.r { text-align:right; font-variant-numeric:tabular-nums; }
td.c, th.c { text-align:center; }
tbody tr:hover { background:var(--hl); }
.note { color:var(--muted); font-size:.82rem; }
.hl { font-weight:700; }
.ok { color:var(--ok); font-weight:700; }
.warn { color:var(--warn); font-weight:700; }
.pill { background:var(--accent); color:#fff; font-size:.68rem; font-weight:700; padding:2px 7px;
  border-radius:10px; letter-spacing:.05em; text-transform:uppercase; }
.pill.warn { background:var(--warn); color:#fff; }
.pill.ok { background:var(--ok); color:#fff; }
.pill.mute { background:var(--muted); color:#fff; }
.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px;
  margin:22px 0 8px; }
.tile { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }
.tl { font-size:.72rem; letter-spacing:.09em; text-transform:uppercase; color:var(--muted);
  font-weight:700; }
.tv { font-size:1.9rem; font-weight:700; letter-spacing:-.02em; font-variant-numeric:tabular-nums;
  line-height:1.2; margin:2px 0; }
.ts { font-size:.78rem; color:var(--ink2); }
.gallery { display:grid; grid-template-columns:repeat(auto-fit,minmax(400px,1fr)); gap:20px;
  margin:20px 0; }
.plate { margin:0; background:var(--card); border:1px solid var(--line); border-radius:10px;
  padding:12px; }
.plate img { width:100%; height:auto; display:block; border-radius:4px; background:#fff; }
.plate figcaption { font-size:.8rem; color:var(--ink2); margin-top:9px; line-height:1.5; }
.plate.missing { border-style:dashed; color:var(--muted); padding:26px; text-align:center; }
.callout { background:var(--hl); border-left:3px solid var(--accent); border-radius:0 8px 8px 0;
  padding:14px 18px; margin:20px 0; font-size:.92rem; max-width:74ch; }
.callout.warn { border-left-color:var(--warn); }
.callout.ok { border-left-color:var(--ok); }
.callout p:last-child { margin-bottom:0; }
.tier { font-size:.68rem; font-weight:700; padding:2px 7px; border-radius:10px; color:#fff;
  letter-spacing:.05em; text-transform:uppercase; white-space:nowrap; }
.tier1 { background:var(--tier1); }
.tier2 { background:var(--tier2); }
.tier3 { background:var(--tier3); }
.tierM { background:var(--tierM); }
.cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:16px;
  margin:20px 0; }
.card { background:var(--card); border:1px solid var(--line); border-radius:10px; padding:16px 18px; }
.card h4 { margin:0 0 8px; font-size:1rem; color:var(--ink); }
.card p { font-size:.88rem; margin-bottom:8px; }
.steps { counter-reset:step; margin:18px 0; padding:0; list-style:none; }
.steps li { counter-increment:step; position:relative; padding:0 0 14px 40px; font-size:.93rem;
  max-width:74ch; }
.steps li::before { content:counter(step); position:absolute; left:0; top:0; width:26px;
  height:26px; border-radius:50%; background:var(--accent); color:#fff; font-size:.78rem;
  font-weight:700; display:flex; align-items:center; justify-content:center; }
footer { padding:32px 0; color:var(--muted); font-size:.83rem; }
@media (max-width:860px) {
  h1 { font-size:1.9rem; }
  .gallery { grid-template-columns:1fr; }
}
@media print {
  nav { position:static; }
  section { break-inside:avoid; }
}
"""

# --------------------------------------------------------------------------- #
# Fragments
# --------------------------------------------------------------------------- #
def esc(s) -> str:
    """HTML-escape any value. Use on anything that came from data rather than
    from a literal in one of these scripts."""
    return _html.escape(str(s))


def table(headers: list[str], rows: list[list[str]], aligns: str = "") -> str:
    """A table wrapped in its own horizontal scroller.

    ``aligns`` is one character per column: ``l`` / ``r`` / ``c``. ``strict=True``
    on purpose — a row whose cell count disagrees with the header should be a loud
    error, not a silently truncated table in a document people read numbers off.
    """
    aligns = aligns or "l" * len(headers)
    cls = {"l": "", "r": ' class="r"', "c": ' class="c"'}
    head = "".join(f"<th{cls[a]}>{h}</th>" for h, a in zip(headers, aligns, strict=True))
    body = "".join(
        "<tr>" + "".join(f"<td{cls[a]}>{c}</td>"
                         for c, a in zip(r, aligns, strict=True)) + "</tr>"
        for r in rows
    )
    return ('<div class="scroll"><table><thead><tr>'
            f"{head}</tr></thead><tbody>{body}</tbody></table></div>")


def num(v, nd=4) -> str:
    """Format a number for a table cell. ``None`` renders as an em-dash rather
    than the string 'None', which would read as a value."""
    if v is None:
        return "—"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def eur(v, nd=2) -> str:
    """Euro amount with a thousands separator."""
    if v is None:
        return "—"
    return f"€{v:,.{nd}f}"


def section(sid: str, kicker: str, title: str, *blocks: str) -> str:
    return (f'<section id="{sid}"><div class="kicker">{kicker}</div><h2>{title}</h2>'
            + "".join(blocks) + "</section>")


def p(text: str) -> str:
    return f"<p>{text}</p>"


def h3(text: str) -> str:
    return f"<h3>{text}</h3>"


def callout(text: str, kind: str = "") -> str:
    cls = f"callout {kind}".strip()
    return f'<div class="{cls}">{text}</div>'


def tiles(items: list[tuple[str, str, str]]) -> str:
    """The KPI strip. Each item is (label, value, sublabel)."""
    return '<div class="tiles">' + "".join(
        f'<div class="tile"><div class="tl">{a}</div><div class="tv">{b}</div>'
        f'<div class="ts">{c}</div></div>' for a, b, c in items) + "</div>"


def cards(items: list[tuple[str, str]]) -> str:
    """A responsive grid of titled prose cards. Each item is (title, html_body)."""
    return '<div class="cards">' + "".join(
        f'<div class="card"><h4>{t}</h4>{b}</div>' for t, b in items) + "</div>"


def steps(items: list[str]) -> str:
    """An auto-numbered ordered list, for describing a sequence."""
    return '<ol class="steps">' + "".join(f"<li>{i}</li>" for i in items) + "</ol>"


def nav(links: list[tuple[str, str]]) -> str:
    """Sticky in-page navigation. Each link is (anchor_id, label)."""
    return "<nav>" + "".join(f'<a href="#{a}">{lbl}</a>' for a, lbl in links) + "</nav>"


def code(text: str) -> str:
    return f"<code>{esc(text)}</code>"


def src(path: str) -> str:
    """Render a ``file.py:123`` source reference. These are load-bearing in these
    reports — every claim points at the line that backs it."""
    return f'<code class="srcref">{esc(path)}</code>'


def pre(text: str) -> str:
    return f"<pre><code>{esc(text)}</code></pre>"


def plate(stem: str, caps: dict[str, str], fig_dir: Path | None = None) -> str:
    """One figure, inlined as a data-URI so the page stays self-contained.

    A missing figure renders as a visible dashed placeholder naming the command
    that would produce it — silently dropping it would make an incomplete page
    look complete.
    """
    from _inline import data_uri  # local import: presentation/scripts on sys.path

    d = fig_dir or FIG
    svg = d / f"{stem}.svg"
    if not svg.exists():
        return (f'<figure class="plate missing"><figcaption>{esc(stem)} — not generated yet; '
                f"run <code>generate_figures.py</code></figcaption></figure>")
    cap = caps.get(stem, "")
    return (f'<figure class="plate"><img loading="lazy" alt="{esc(stem)}" src="{data_uri(svg)}">'
            f'<figcaption><b>{esc(stem.split("_")[0])}</b> — {cap}</figcaption></figure>')


def gallery(stems: list[str], caps: dict[str, str], fig_dir: Path | None = None) -> str:
    return ('<div class="gallery">'
            + "".join(plate(s, caps, fig_dir) for s in stems) + "</div>")


def page(*, title: str, heading: str, sub: str, meta: str, navbar: str,
         body: str, footer: str) -> str:
    """Assemble a complete self-contained document.

    ``title`` is the browser-tab name; everything else is page furniture. The
    caller has already escaped anything that needed it.
    """
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>{CSS}</style></head>
<body><div class="wrap">
<header>
  <h1>{heading}</h1>
  <p class="sub">{sub}</p>
  <p class="meta">{meta}</p>
</header>
{navbar}
{body}
<footer>{footer}</footer>
</div></body></html>
"""
