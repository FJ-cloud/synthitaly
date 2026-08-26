#!/usr/bin/env python3
"""Economist-style matplotlib theme, shared by the figure scripts.

House style implemented here is the modern (post-2018) Economist chart:
white panel, a red tab top-left, a left-aligned bold title with a lighter
subtitle carrying the units, horizontal gridlines only, y tick labels on the
right, and a source line bottom-left.

Two things that differ from the previous local theme and matter for print:

  * Figures are authored at the width they will be *printed* at (6.3 in ≈ the
    16 cm text block of an A4 thesis page), not at 11 in and then scaled down.
    Type sizes are chosen for that width, so no downscaling is needed.
  * Margins are set explicitly with ``subplots_adjust`` and ``bbox_inches`` is
    NOT used, so every figure comes out at exactly the same pixel width. That
    is what makes a run of figures look like a set rather than a pile.

The Economist's own face is Econ Sans (an ITC Officina Sans cut) and is not
freely licensable; Fira Sans is the closest humanist sans installed here.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

# --------------------------------------------------------------------------- #
# Palette — The Economist's data-team colours
# --------------------------------------------------------------------------- #
# Two of the Economist's own hues are adjusted for print rather than used raw.
# Checked with the dataviz palette validator (six checks: lightness band, chroma
# floor, CVD separation, normal-vision floor, contrast vs surface):
#   * the house gold #EBB434 sits at L 0.80 — outside the band — and reaches only
#     1.84:1 against white. Darkened to #C68A00: inside the band, deutan ΔE 8.8
#     against the red (the raw pair was fine, the contrast was not), 2.91:1.
#   * teal #379A8B and plum #9A607F fall below the chroma floor and separate by
#     only ΔE 5.8 from each other under deuteranopia, so neither is used for a
#     series. GREEN below replaces them in the five-source chart.
# Everything else is the palette as published.
RED = "#E3120B"      # the tab; and the series that is the problem
BLUE = "#006BA2"     # the primary series
CYAN = "#3EBCD2"
YELLOW = "#C68A00"   # house gold, darkened for print — see note above
GREEN = "#2E7D32"
TEAL = "#379A8B"     # decorative only, never a series
PLUM = "#9A607F"     # decorative only, never a series
OLIVE = "#B4BA39"
TAN = "#D1B07C"
GREY = "#758D99"     # reference lines, baselines, "chance", "no subtype"

# Fixed order, never cycled. The first three are the validated working set.
CAT = [BLUE, RED, YELLOW, GREEN, CYAN, PLUM, OLIVE, TAN]

# For nominal groups that must NOT be read as the debtor archetypes — the KMeans
# cluster ids in f13, where using the archetype colours would imply a mapping
# between cluster 0 and "climber" that the confusion matrix contradicts.
NOMINAL = ["#8E4585", GREEN, CYAN]

INK = "#121316"      # title, data labels
INK2 = "#58585B"     # subtitle, secondary text
GRID = "#D9E0E3"     # gridlines
RULE = "#B7C4CB"     # the one axis spine we keep
PANEL = "#FFFFFF"

# ordinal ramp — income level, and the confusion-matrix heatmap
BLUE_RAMP = ["#CCE1EB", "#A2C4D5", "#7FA9C0", "#3E7D9B", "#006BA2", "#003D5B"]

# Fixed entity -> colour, so nothing repaints between charts.
SUBTYPE_COLOR = {"climber": BLUE, "chronic": RED, "subsister": YELLOW}
SUBTYPE_ORDER = ["climber", "chronic", "subsister"]
LEVEL_COLOR = {"low": "#CCE1EB", "middle": "#3E7D9B", "high": "#003D5B"}
SOURCE_COLOR = {  # income sources, f07 — validated as a five-way set
    "payroll": BLUE, "self_employed": GREEN, "pension": CYAN,
    "transfers": YELLOW, "unemployed": RED,
}

# --------------------------------------------------------------------------- #
# Sizes — inches. 6.3 in = 16 cm = the text block of a typical A4 thesis page.
# --------------------------------------------------------------------------- #
FULL = (6.3, 3.7)     # one chart across the column
WIDE = (6.3, 4.6)     # stacked panels, or a chart needing more vertical room
PAIR = (6.3, 3.2)     # two panels side by side
SHORT = (6.3, 2.9)    # sparse series that would otherwise swim in white

DPI = 300

# --------------------------------------------------------------------------- #
# rcParams
# --------------------------------------------------------------------------- #
SANS = ["Fira Sans", "Source Sans Pro", "Lato", "DejaVu Sans"]
SANS_CN = ["Fira Sans Condensed", "Fira Sans", "DejaVu Sans"]


def use_econ() -> None:
    """Install the theme. Idempotent; called at import."""
    plt.rcParams.update({
        "figure.facecolor": PANEL,
        "axes.facecolor": PANEL,
        "savefig.facecolor": PANEL,
        "figure.dpi": 110,
        "savefig.dpi": DPI,

        "font.family": "sans-serif",
        "font.sans-serif": SANS,
        "font.size": 8,
        "axes.titlesize": 9,
        "axes.titleweight": "semibold",
        "axes.labelsize": 8,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,

        "text.color": INK,
        "axes.labelcolor": INK2,
        "axes.titlecolor": INK,
        "xtick.color": INK2,
        "ytick.color": INK2,

        "axes.edgecolor": RULE,
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.7,
        "lines.linewidth": 1.6,
        "lines.solid_capstyle": "round",

        "legend.frameon": False,
        "legend.handlelength": 1.4,
        "legend.handletextpad": 0.5,
        "legend.columnspacing": 1.4,

        # keep text as text in the vector outputs, so LaTeX/Illustrator can use it
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
    })


use_econ()


# --------------------------------------------------------------------------- #
# Figure construction
# --------------------------------------------------------------------------- #
def econ_fig(size=FULL, nrows: int = 1, ncols: int = 1, **kw):
    """A figure at print size. Returns whatever ``plt.subplots`` returns."""
    return plt.subplots(nrows, ncols, figsize=size, **kw)


def frame(fig, title: str, subtitle: str | None = None, src: str | None = None,
          *, note: str | None = None, key: list[tuple[str, str]] | None = None,
          key_x: float = 0.02, key_gap: float = 0.012,
          top: float | None = None, bottom: float | None = None,
          left: float = 0.035, right: float = 0.885,
          wspace: float = 0.30, hspace: float = 0.32) -> None:
    """Draw the house furniture and set the margins.

    ``title`` is short and declarative; ``subtitle`` carries the units and any
    qualifier. ``key`` is an optional ``[(label, colour), …]`` row drawn under
    the subtitle — the house alternative to a legend box, and the one to reach
    for on multi-series line charts, where a right-hand direct label would land
    on the right-hand tick labels. ``note`` is a caveat that belongs on the
    chart rather than in the caption; it sits above ``src``, which is always the
    bottom-most line. Margins are explicit — do not call ``tight_layout``.
    """
    w, h = fig.get_size_inches()

    def frac(pt: float) -> float:            # points -> figure fraction of height
        return pt / (h * 72.0)

    def wfrac(pt: float) -> float:           # points -> figure fraction of width
        return pt / (w * 72.0)

    y = 1.0 - frac(6)
    # red tab
    fig.add_artist(Rectangle((0.02, y - frac(3.2)), 0.085, frac(3.2),
                             facecolor=RED, edgecolor="none",
                             transform=fig.transFigure, zorder=5))
    y -= frac(9)
    fig.text(0.02, y, title, ha="left", va="top", color=INK,
             fontsize=11, fontweight="bold")
    y -= frac(14)
    if subtitle:
        fig.text(0.02, y, subtitle, ha="left", va="top", color=INK2,
                 fontsize=8.5)
        y -= frac(11.5) * (1 + subtitle.count("\n"))

    if key:
        y -= frac(3)
        cy = y - frac(4)
        x = key_x
        swatch_w, swatch_h = wfrac(11), frac(3.0)
        for label, colour in key:
            fig.add_artist(Rectangle((x, cy - swatch_h / 2), swatch_w, swatch_h,
                                     facecolor=colour, edgecolor="none",
                                     transform=fig.transFigure, zorder=5))
            x += swatch_w + wfrac(3.5)
            fig.text(x, cy, label, ha="left", va="center", color=INK2,
                     fontsize=8)
            x += wfrac(4.9 * len(label)) + key_gap
        y -= frac(11)

    if top is None:
        top = y - frac(5)
        # Panel titles are drawn inside the axes' top margin, so they need room
        # carved out of the header or they land on the subtitle. Check every
        # loc: econ_style sets them with loc="left", and a bare get_title()
        # only ever reports the centred one.
        if any(ax.get_title(loc=loc) for ax in fig.axes
               for loc in ("left", "center", "right")):
            top -= frac(20)

    # Wrap the footer lines to the figure width rather than letting a long note
    # run off the right edge. ~0.47 em per character is a good average for Fira
    # Sans at this size; the 0.02 margins take 4% of the width.
    cols = max(40, int((w * 72 * 0.96) / (6.5 * 0.47)))

    foot = 7.0                                  # points above the figure bottom
    for text, colour in ((src, GREY), (note, INK2)):
        if not text:
            continue
        lines = textwrap.wrap(text, cols) or [text]
        fig.text(0.02, frac(foot), "\n".join(lines), ha="left", va="bottom",
                 color=colour, fontsize=6.5, linespacing=1.35)
        foot += 9.5 * len(lines)

    if bottom is None:
        # Reserve what the x-axis furniture actually needs: the tick labels
        # (which may be two lines) plus an axis title if one is set. Fixing this
        # by eye is what let the previous figures collide with their own
        # footnotes.
        # The bottom-most axes owns the x furniture — on a stacked pair that is
        # not fig.axes[0], and getting this wrong put f01's axis title on top of
        # its own source line.
        tick_lines, xlab = 1, 0.0
        if fig.axes:
            ax0 = min(fig.axes, key=lambda a: a.get_position().y0)
            texts = [t.get_text() for t in ax0.get_xticklabels()]
            tick_lines = max((t.count("\n") + 1 for t in texts if t), default=1)
            xlab = 13.0 if any(a.get_xlabel() for a in fig.axes) else 0.0
        bottom = frac(foot + 4 + 10.5 * tick_lines + xlab)

    fig.subplots_adjust(left=left, right=right, top=top, bottom=bottom,
                        wspace=wspace, hspace=hspace)


def econ_style(ax, title: str | None = None, xlabel: str | None = None,
               ylabel: str | None = None, *, grid: str = "y",
               yticks_right: bool = True, zero_line: bool = False) -> None:
    """Spines, grid and tick placement for one panel.

    ``grid`` is "y" (the default, for vertical bars and time series), "x" (for
    horizontal bars) or "both" (scatter). ``ylabel`` is normally left out — the
    units belong in the subtitle — and is kept only for panels where the axis
    is not a quantity, e.g. PC2.
    """
    for s in ("top", "left", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_visible(True)
    ax.spines["bottom"].set_color(RULE)
    ax.tick_params(length=0, pad=3)
    ax.grid(False)
    if grid in ("y", "both"):
        ax.grid(axis="y", color=GRID, linewidth=0.7)
    if grid in ("x", "both"):
        ax.grid(axis="x", color=GRID, linewidth=0.7)
    ax.set_axisbelow(True)

    if yticks_right:
        ax.yaxis.tick_right()
        ax.yaxis.set_label_position("right")

    if zero_line:
        ax.axhline(0, color=RULE, lw=0.8, zorder=1)

    if title:
        ax.set_title(title, loc="left", pad=6, fontsize=9,
                     fontweight="semibold", color=INK)
    if xlabel:
        ax.set_xlabel(xlabel, labelpad=4)
    if ylabel:
        ax.set_ylabel(ylabel, labelpad=4)


def label_lines(ax, entries, *, dx: float = 4, fontsize: float = 8,
                weight: str = "semibold") -> None:
    """Direct-label series at the right-hand end of each line.

    ``entries`` is an iterable of ``(x, y, text, colour)``. Direct labelling is
    the house convention and it is also what keeps legends from landing on top
    of the data, which is what went wrong in the previous f11 and f12.
    """
    for x, y, text, colour in entries:
        ax.annotate(text, xy=(x, y), xytext=(dx, 0),
                    textcoords="offset points", ha="left", va="center",
                    color=colour, fontsize=fontsize, fontweight=weight,
                    annotation_clip=False)


def below_legend(ax, *, ncol: int = 3, y: float = -0.22, **kw):
    """A legend under the plot, where it cannot cover data."""
    return ax.legend(loc="upper left", bbox_to_anchor=(0.0, y), ncol=ncol,
                     frameon=False, borderaxespad=0, **kw)


def darken(hex_colour: str, factor: float = 0.62) -> str:
    """A darker step of the same hue, for a part-of-whole shading within one bar."""
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(min(255, int(c * factor)) for c in (r, g, b))


def blue_cmap():
    """The ordinal blue ramp as a colormap, for the one heatmap in the set."""
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list("econ_blue", ["#FFFFFF"] + BLUE_RAMP)


def outline(colour: str = "#FFFFFF", lw: float = 2.0):
    """A halo, so an in-plot label stays readable where it crosses a mark."""
    from matplotlib import patheffects
    return [patheffects.withStroke(linewidth=lw, foreground=colour)]


# --------------------------------------------------------------------------- #
# Axis formatters
# --------------------------------------------------------------------------- #
def fmt_pct(ax, axis: str = "y", decimals: int = 0) -> None:
    getattr(ax, f"{axis}axis").set_major_formatter(
        lambda v, _: f"{v:.{decimals}%}")


def fmt_eur(ax, axis: str = "y") -> None:
    getattr(ax, f"{axis}axis").set_major_formatter(lambda v, _: f"€{v:,.0f}")


def fmt_thousands(ax, axis: str = "y", divisor: float = 1000.0,
                  decimals: int = 0) -> None:
    """Plain numbers on the axis; state the multiplier in the subtitle."""
    getattr(ax, f"{axis}axis").set_major_formatter(
        lambda v, _: f"{v / divisor:,.{decimals}f}")


def fmt_int(ax, axis: str = "y") -> None:
    getattr(ax, f"{axis}axis").set_major_formatter(lambda v, _: f"{v:,.0f}")


# --------------------------------------------------------------------------- #
# Machine name -> prose. Used for every tick label and legend entry, so no
# underscored column name reaches the page.
# --------------------------------------------------------------------------- #
PRETTY = {
    # spend categories
    "retail": "Retail",
    "food": "Food & groceries",
    "hotels_rest": "Hotels & restaurants",
    "travel": "Travel",
    "clothing": "Clothing",
    "home": "Home",
    "repairs": "Repairs",
    "cash_advance": "Cash withdrawals",
    "phones_web": "Phones & internet",
    "services": "Services",
    # income sources
    "payroll": "Payroll",
    "self_employed": "Self-employed",
    "pension": "Pension",
    "transfers": "Transfers",
    "unemployed": "Unemployed",
    # income levels
    "low": "Low",
    "middle": "Middle",
    "high": "High",
    # debtor archetypes
    "climber": "Climber",
    "chronic": "Chronic",
    "subsister": "Subsister",
    "none": "Not a debtor",
    # macro-areas
    "NORTH": "North",
    "CENTRE": "Centre",
    "SOUTH": "South",
    # fee kinds
    "overdraft_fee": "Overdraft fee",
    "late_payment_fee": "Late-payment fee",
    # feature columns (f15 coefficient panel)
    "cur_total_in": "Money in, current a/c",
    "cur_total_out": "Money out, current a/c",
    "cur_balance": "End balance, current a/c",
    "balance_std_proxy": "Balance volatility",
    "n_purchases": "Number of purchases",
    "n_bills": "Number of bills",
    "mean_ticket": "Average purchase size",
    "total_spend": "Total spend",
    "total_income": "Total income",
    "total_bills": "Total bills",
    "mean_income_credit": "Average income credit",
}


def pretty(name) -> str:
    """Prose for a machine name; falls back to de-underscored sentence case."""
    key = str(name)
    if key in PRETTY:
        return PRETTY[key]
    return key.replace("_", " ").capitalize()


def prettify(names) -> list[str]:
    return [pretty(n) for n in names]


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
FORMATS = ("png", "pdf", "svg")


def save_figure(fig, fig_dir: Path, name: str,
                formats: tuple[str, ...] = FORMATS) -> None:
    """Write one figure in every output format.

    PNG at 300 dpi and PDF are the thesis deliverables; SVG is what
    ``scripts/_report.py`` base64-inlines into the generated HTML pages, so it
    is not optional even though nothing in the thesis uses it directly.

    No ``bbox_inches="tight"``: the margins set by :func:`frame` are the
    layout, and honouring the declared figure size is what keeps all 19
    figures exactly the same width on the page.
    """
    fig_dir.mkdir(parents=True, exist_ok=True)
    for ext in formats:
        fig.savefig(fig_dir / f"{name}.{ext}", dpi=DPI, facecolor=PANEL)
    plt.close(fig)
