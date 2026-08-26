#!/usr/bin/env python3
"""Draw f00_overview — the one figure that says what the model *is*.

Run:  uv run python presentation/scripts/make_overview_figure.py

Answers three questions and nothing else: what enters the model, what happens
during a simulated day, what comes out. A reader who stops at this figure should
still come away with the shape of the thing:

    SynthItaly takes public evidence and explicit assumptions, applies financial
    rules repeatedly to persistent consumers and accounts, and produces linked
    records over time.

Deliberately absent, because they belong in the text, the code and the appendix:
filenames, class and method names, individual parameters, fee amounts, the eight
daily processing steps, validation methods, dataset names.

Two things make this a separate script rather than another function in
generate_figures.py:

  * It carries no data. Folding it in would force an 800 x 720 model run every
    time a box moves. Nothing here imports synthitaly; the script runs in about
    a second.
  * generate_figures.py rewrites CAPTIONS.md wholesale from its own list, so a
    caption appended from here would be deleted on its next run. The caption for
    this figure lives in the thesis LaTeX instead.

Two variants are drawn. ``f00_overview_v2`` corrects the one substantive error
in the original: the arrows between Income, Bills and debt, Purchases and Saving
asserted a within-day ordering the model does not have. Those events fire on
different scheduled dates, and fees arise from payment conditions rather than
from a step that follows saving. v2 shows them as event *categories* on one row
with a single arrow from the row as a whole, which is what the code actually
does. ``f00_overview`` is kept unchanged only so the two can be compared; delete
whichever loses.

It does NOT extend make_diagrams.py, which draws d01-d06 in an older slide look
(DejaVu Sans, 13 in landscape, eight colours, no PDF) and fills its boxes with
exactly the class and method names this figure must not show. Note that importing
that module would silently clobber the Economist theme — it calls
plt.rcParams.update at module level. The two box/arrow helpers below are small
enough to keep local.
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
from matplotlib.patches import FancyArrowPatch, Rectangle

from _style import (  # noqa: E402  (script dir is on sys.path, as in generate_figures.py)
    BLUE, BLUE_RAMP, GREY, INK, INK2, RED,
    econ_fig, frame, save_figure,
)

FIG_DIR = Path(__file__).resolve().parent.parent / "figures"

# 0.9 x the 6.3 in text block, so the authored size IS the printed size at
# \includegraphics[width=0.9\textwidth] and no label shrinks on its way to the
# page. Taller than any preset in _style.py because the flow is vertical and
# those are all landscape chart shapes.
SIZE = (5.67, 5.2)

# Three colours, assigned by role. BLUE carries the model, GREY recedes, RED is
# the single accent and marks the one thing a reader must not miss: the loop.
# Everything else is ink on white. The tiers separate by lightness and line
# weight, not hue, so the figure survives greyscale.
FILL = BLUE_RAMP[0]        # #CCE1EB — the only filled box in the figure

INPUTS = [
    "Italian financial\nstatistics",
    "Published behavioural\nfindings",
    "Explicit modelling\nassumptions",
]
COMPONENTS = ["Consumers", "Accounts\nand debt", "Payment\ncounterparties"]

# The two variants differ only in data — four event labels, one row label,
# whether arrows are drawn between the event chips, the loop's colour and text,
# one output heading, and the vertical room the longer heading needs. The
# drawing code below is single-copy; forking it would let the baseline drift.
VARIANTS = {
    "f00_overview": dict(
        # Kept exactly as first drawn, as the comparison baseline. Do not touch:
        # every number here is load-bearing for its hash.
        events=["Income", "Bills and\ndebt", "Purchases", "Saving or\nfees"],
        event_label=None,
        chain_arrows=True,          # asserts an ordering the model does not have
        upd_y=34.0,
        loop_frac=0.5,          # no fan below the row, so the centre is clear
        loop_color=RED,
        loop_text="Repeated for each\nsimulated day",
        account_head="Account records",
        out_y=2.0, out_h=19.0, head_y=18.6, rail_y=25.0, out_top=21.0,
    ),
    "f00_overview_v2": dict(
        events=["Income", "Bills and\ndebt", "Purchases", "Saving, arrears\nand fees"],
        event_label="Scheduled financial events",
        chain_arrows=False,         # a set of categories, not a sequence
        upd_y=33.0,
        loop_frac=0.25,         # clear of the fan stub under the centre
        loop_color=BLUE,            # red read as a warning; this is just the clock
        loop_text="Next simulated day",
        account_head="Terminal account portfolio",   # \u00a74.6 terminology
        out_y=2.0, out_h=21.0, head_y=20.6, rail_y=26.0, out_top=23.0,
    ),
}

OUTPUTS = [
    ("Transaction ledger",
     "Dated income, purchases, bills, debt payments and fees"),
    (None,   # filled from the variant
     "Consumer balances, saving and debt positions"),
    ("Daily time series",
     "Aggregate spending, balances and debt development"),
]


# --------------------------------------------------------------------------- #
# Helpers. Squared corners rather than the rounded ones in make_diagrams.py —
# the house style has no rounded boxes, and it sidesteps the mutation_aspect
# correction that non-square data units would otherwise need.
# --------------------------------------------------------------------------- #
def box(ax, x, y, w, h, *, face="white", edge=GREY, lw=1.0):
    ax.add_patch(Rectangle((x, y), w, h, facecolor=face, edgecolor=edge,
                           linewidth=lw, zorder=2))


def text(ax, x, y, s, *, size=9.5, color=INK, weight="normal", va="center",
         ha="center"):
    ax.text(x, y, s, ha=ha, va=va, fontsize=size, color=color, weight=weight,
            linespacing=1.25, zorder=4)


def arrow(ax, p0, p1, *, color=INK2, lw=1.1, ls="-", rad=0.0, scale=8):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=scale,
                                 color=color, lw=lw, linestyle=ls,
                                 connectionstyle=f"arc3,rad={rad}",
                                 shrinkA=0, shrinkB=0, zorder=3))


def row(n, *, left=0.0, right=100.0, gap=3.5):
    """Left edges and width for ``n`` equal boxes spanning ``left``..``right``."""
    w = (right - left - gap * (n - 1)) / n
    return [left + i * (w + gap) for i in range(n)], w


def fan(ax, y_from, y_to, xs, x_join):
    """The ``\\__|__/`` connector: stubs from each x, a rail, one arrow onward."""
    y_rail = (y_from + y_to) / 2
    for x in xs:
        ax.plot([x, x], [y_from, y_rail], color=INK2, lw=1.1, zorder=3)
    ax.plot([min(xs), max(xs)], [y_rail, y_rail], color=INK2, lw=1.1, zorder=3)
    arrow(ax, (x_join, y_rail), (x_join, y_to))


def draw(name: str, v: dict) -> None:
    fig, ax = econ_fig(SIZE)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")

    # ---- 1. what enters ---------------------------------------------------- #
    xs, w = row(3)
    for x, label in zip(xs, INPUTS):
        box(ax, x, 87, w, 13)
        text(ax, x + w / 2, 93.5, label, color=INK2)
    fan(ax, 87, 82, [x + w / 2 for x in xs], 50)

    # ---- 2. what happens --------------------------------------------------- #
    # The only filled box, the heaviest rule and the largest type: this is what
    # the eye should land on first.
    box(ax, 0, 30, 100, 52, face=FILL, edge=BLUE, lw=2.0)
    text(ax, 50, 78, "SynthItaly daily simulation", size=10.5, weight="bold")

    cxs, cw = row(3, left=4, right=96, gap=4)
    for x, label in zip(cxs, COMPONENTS):
        box(ax, x, 66, cw, 9, edge=BLUE, lw=1.0)
        text(ax, x + cw / 2, 70.5, label)

    # The event row. Without arrows between the chips the row needs saying what
    # it is, or four boxes just sit there with nothing between them.
    if v["event_label"]:
        text(ax, 50, 60.5, v["event_label"], size=9, weight="semibold",
             color=INK2)

    dxs, dw = row(4, left=4, right=96, gap=4)
    for i, (x, label) in enumerate(zip(dxs, v["events"])):
        box(ax, x, 49, dw, 9, edge=BLUE, lw=1.0)
        text(ax, x + dw / 2, 53.5, label)
        if i and v["chain_arrows"]:
            arrow(ax, (dxs[i - 1] + dw, 53.5), (x, 53.5), scale=7)

    upd_y = v["upd_y"]
    box(ax, 33, upd_y, 34, 9, edge=BLUE, lw=1.0)
    text(ax, 50, upd_y + 4.5, "Updated financial state", weight="semibold")
    if v["chain_arrows"]:
        arrow(ax, (50, 49), (50, upd_y + 9))
    else:
        # One arrow from the row as a whole — the same stub/rail/arrow idiom the
        # input and output rows use, so it reads as "all of these together".
        fan(ax, 49, upd_y + 9, [x + dw / 2 for x in dxs], 50)

    # The point of the whole figure: today's events move balances and debt, and
    # those move tomorrow's. The only dashed curve in the figure.
    arrow(ax, (33, upd_y + 4.5), (dxs[0] + dw * v["loop_frac"], 48.4),
          color=v["loop_color"],
          ls=(0, (3, 2)), rad=0.35)
    text(ax, 69, upd_y + 4.5, v["loop_text"], size=9, color=v["loop_color"],
         ha="left")

    # ---- 3. what comes out ------------------------------------------------- #
    oxs, ow = row(3)
    ocentres = [x + ow / 2 for x in oxs]
    heads = [v["account_head"] if h is None else h for h, _ in OUTPUTS]
    for x, head, (_, detail) in zip(oxs, heads, OUTPUTS):
        box(ax, x, v["out_y"], ow, v["out_h"], edge=BLUE, lw=1.4)
        head = "\n".join(textwrap.wrap(head, 22))
        text(ax, x + ow / 2, v["head_y"], head, weight="semibold", va="top")
        # Start the detail below however many lines the heading took, rather
        # than at a fixed offset — "Terminal account portfolio" needs two.
        text(ax, x + ow / 2,
             v["head_y"] - 4.2 * (head.count("\n") + 1),
             "\n".join(textwrap.wrap(detail, 26)),
             size=9, color=INK2, va="top")
    y_rail = v["rail_y"]
    ax.plot([50, 50], [30, y_rail], color=INK2, lw=1.1, zorder=3)
    ax.plot([min(ocentres), max(ocentres)], [y_rail, y_rail], color=INK2,
            lw=1.1, zorder=3)
    for x in ocentres:
        arrow(ax, (x, y_rail), (x, v["out_top"]))

    frame(fig, "SynthItaly generating process",
          "Public evidence and explicit assumptions, applied daily to persistent consumers",
          "Schematic — no simulation data",
          top=0.875, bottom=0.052, left=0.02, right=0.98)
    save_figure(fig, FIG_DIR, name)
    print(f"  wrote {name}.png / .pdf / .svg")


def main() -> None:
    for name, v in VARIANTS.items():
        draw(name, v)


if __name__ == "__main__":
    main()
