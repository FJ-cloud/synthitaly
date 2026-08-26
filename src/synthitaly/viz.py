"""
viz.py — interactive Solara app for the model.

Launch with::

    uv run solara run src/synthitaly/viz.py

A browser opens at ``http://localhost:8765``. Move the sliders, press play,
and the panels update live.

PANELS
------
1.  SpendingByArea        — bar chart of total EUR purchased per macro-area.
2.  NetworkPanel          — who-pays-whom structure in three clean columns:
                            IncomeSource (▲) → Consumers (●) → Merchants (■).
3.  KPIPanel              — Mesa's line plot of daily txn count and EUR total.
4.  BehaviouralEventsPanel — daily overdraft / late-payment fee counts plus
                            daily spend with payday markers.
5.  IncomeCompositionPanel — headcount per income source (with low/middle/high
                            level mix) and mean income per source.
6.  BalanceTrajectoryPanel — mean current-account balance over time, one line
                            per income source (how accounts move, not just end).
7.  DebtorCompositionPanel — population split across the three debtor archetypes.
8.  DebtTrajectoryPanel   — outstanding principal per archetype over the run.
9.  ChronicDebtorPanel    — focused view of the chronically-indebted cohort:
                            balance pinned at the overdraft floor + fee burden.
10. AccountInspectorPanel — pick a consumer, inspect statements + sparklines.
11. ArchetypesPanel       — a static reference card of kinds/categories/bills.

WHY THIS APP WORKS WHEN THE OLD ONE DIDN'T
------------------------------------------
The previous attempt (kept in the parked prototype, which is not published here)
hit two issues. Both are fixed here:

1. Eager model construction wrote files to ``runs/`` at import time. This
   ``ItalyModel`` writes nothing to disk during ``__init__``.
2. ``make_space_component`` is hardcoded to render ``model.grid``. We use a
   custom ``@solara.component`` for the network panel instead.
"""

from __future__ import annotations

import io
import math
from collections import defaultdict

import matplotlib.pyplot as plt
import pandas as pd
import solara
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from mesa.visualization import (
    Slider,
    SolaraViz,
    make_plot_component,
)
from mesa.visualization.utils import update_counter

from synthitaly import numbers
from synthitaly.model import ItalyModel

# ----------------------------------------------------------------------------
# Presentation styling — applied to every Figure created below.
# Slightly larger fonts and a crisp default DPI so the panels read well both
# live in the browser and when screenshotted for slides.
# ----------------------------------------------------------------------------
plt.rcParams.update(
    {
        "figure.dpi": 110,
        "savefig.dpi": 200,
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "legend.fontsize": 8,
    }
)


def _png_bytes(fig: Figure) -> bytes:
    """Render a figure to PNG bytes for the 'Download PNG' buttons — gives a
    clean, high-resolution still for slides without a manual screenshot."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    return buf.getvalue()


# ----------------------------------------------------------------------------
# Sliders / inputs the user can move in the browser
# ----------------------------------------------------------------------------

model_params = {
    "seed": Slider("Random seed", value=42, min=1, max=9999, step=1),
    "n_consumers": Slider("Consumers", value=150, min=50, max=500, step=10),
    "n_merchants_per_category": Slider(
        "Merchants / category / area", value=3, min=1, max=10, step=1
    ),
    "n_days": Slider("Days to run", value=30, min=5, max=60, step=1),
}


# ----------------------------------------------------------------------------
# Panel 1 — Spending by macro-area (bar chart)
# ----------------------------------------------------------------------------


@solara.component
def SpendingByArea(model: ItalyModel):
    """Total EUR of purchases per macro-area so far. Bills + salary are
    excluded so the bar chart shows discretionary card-spend only."""
    update_counter.get()  # re-render every time the model steps

    totals = {"NORTH": 0.0, "CENTRE": 0.0, "SOUTH": 0.0}
    for t in model.transactions:
        if t["kind"] == "purchase":
            totals[t["macro_area"]] += t["amount_eur"]

    fig = Figure(figsize=(6, 3.5), layout="constrained")
    ax = fig.subplots()
    areas = list(totals.keys())
    values = [totals[a] for a in areas]
    colors = ["tab:blue", "tab:orange", "tab:red"]
    ax.bar(areas, values, color=colors)
    ax.set_ylabel("EUR (purchases)")
    ax.set_title("Spending by macro-area")
    for i, v in enumerate(values):
        ax.text(i, v, f"€{v:,.0f}", ha="center", va="bottom", fontsize=9)
    solara.FigureMatplotlib(fig)


# ----------------------------------------------------------------------------
# Panel 2 — Consumer / merchant / income-source network
# ----------------------------------------------------------------------------

_AREA_COLOR = {"NORTH": "tab:blue", "CENTRE": "tab:orange", "SOUTH": "tab:red"}
_AREA_ORDER = ["NORTH", "CENTRE", "SOUTH"]  # top → bottom in the layout
_TOP_CATS = ["retail", "food", "hotels_rest"]  # listed first when ordering merchants

# Two extra destination markers per area (besides the 10 purchase categories),
# so every consumer outflow has a visible target on the right.
_DEST_BILLS = "Bills & debt"
_DEST_FEES = "Fees → bank"

# Colour per money-flow TYPE (used for the live arrows, independent of area).
_FLOW_COLOR = {
    "salary": "tab:green",     # income → consumer
    "purchase": "tab:blue",    # consumer → merchant
    "billsdebt": "tab:brown",  # consumer → bills / debt service
    "fees": "red",             # consumer → bank (overdraft / late-payment)
}

# Colour per debtor archetype (numbers.DEBTOR_SUBTYPES), reused by the debtor
# composition panel, the debt-trajectory panel and the account inspector.
#   climber → digs out · chronic → stuck · subsister → ekes out · None → no debt
_DEBTOR_COLOR = {
    "climber": "tab:green",
    "chronic": "tab:red",
    "subsister": "tab:orange",
    None: "tab:gray",
}

# Colour per primary income SOURCE (numbers.INCOME_SOURCE_SHARE), reused by the
# income-composition and balance-trajectory panels and the account inspector.
_INCOME_COLOR = {
    "payroll":       "tab:blue",
    "self_employed": "tab:purple",
    "pension":       "tab:green",
    "transfers":     "tab:orange",
    "unemployed":    "tab:red",
}

# Colour per income LEVEL (absolute euro bands), low → high.
_LEVEL_COLOR = {
    "low":    "tab:red",
    "middle": "tab:orange",
    "high":   "tab:green",
}


def _latest_day_flows(model: ItalyModel):
    """Aggregate the most recent simulated day's transactions into the flows
    the arrows draw. Returns ``(latest_date, flows)`` where flows has keys
    'salary'/'billsdebt'/'fees' → {area: eur} and 'purchase' → {(area,cat): eur}.
    Pure read of ``model.transactions`` — no model mutation."""
    txns = model.transactions
    if not txns:
        return None, None
    latest = max(t["date"] for t in txns)
    flows = {
        "salary": defaultdict(float),
        "purchase": defaultdict(float),
        "billsdebt": defaultdict(float),  # kind "bill" incl. debt_service
        "fees": defaultdict(float),       # kind "fee": overdraft + late payment
    }
    for t in txns:
        if t["date"] != latest:
            continue
        area, amt, kind = t["macro_area"], t["amount_eur"], t["kind"]
        if kind == "salary":
            flows["salary"][area] += amt
        elif kind == "purchase":
            flows["purchase"][(area, t["category"])] += amt
        elif kind == "bill":
            flows["billsdebt"][area] += amt
        elif kind == "fee":
            flows["fees"][area] += amt
    return latest, flows


@solara.component
def NetworkPanel(model: ItalyModel):
    """Who-pays-whom structure of the simulation, in three clean columns, with
    **live arrows showing where the money goes on the most recent day**.

    Reading left → right is the direction money flows::

        IncomeSource (▲)  →  Consumers (●)  →  Merchants / Bills / Fees (■)

    Consumers are banded by macro-area (NORTH / CENTRE / SOUTH) and laid out as
    a compact block of dots so the ~150 of them never overlap. The faint grey
    lines are the fixed structure; the coloured arrows are the euros that moved
    on the latest simulated day (arrow width ∝ €), so as you press play the
    picture pulses with that day's salary-in, spending, bills and bank fees.
    """
    update_counter.get()

    g = model.graph

    # ---- group nodes by kind / area --------------------------------------
    consumers_by_area: dict[str, list] = {a: [] for a in _AREA_ORDER}
    income_by_area: dict[str, object] = {}
    # merchant categories present per area, in a stable order
    mcats_by_area: dict[str, list[str]] = {a: [] for a in _AREA_ORDER}
    for n, d in g.nodes(data=True):
        kind, area = d.get("kind"), d.get("macro_area")
        if kind == "consumer" and area in consumers_by_area:
            consumers_by_area[area].append(n)
        elif kind == "income_source":
            income_by_area[area] = n
        elif kind == "merchant" and area in mcats_by_area:
            cat = d.get("category")
            if cat not in mcats_by_area[area]:
                mcats_by_area[area].append(cat)
    for a in _AREA_ORDER:
        mcats_by_area[a].sort(key=lambda c: _TOP_CATS.index(c) if c in _TOP_CATS else 99)

    # Destination column per area = purchase categories + bills/debt + fees.
    dests_by_area = {a: mcats_by_area[a] + [_DEST_BILLS, _DEST_FEES] for a in _AREA_ORDER}

    # ---- geometry --------------------------------------------------------
    rows = 6          # consumer block height (dots stacked per column)
    dx = dy = 0.55    # spacing between consumer dots
    band_gap = 2.6    # vertical gap between macro-area bands
    x_income = 0.0
    x_consumer0 = 2.2
    max_cols = max(
        (math.ceil(len(consumers_by_area[a]) / rows) for a in _AREA_ORDER), default=1
    )
    max_cols = max(1, max_cols)
    x_merchant = x_consumer0 + (max_cols - 1) * dx + 2.6
    band_height = (rows - 1) * dy

    pos: dict[object, tuple[float, float]] = {}
    band_center: dict[str, float] = {}
    block_center: dict[str, tuple[float, float]] = {}
    for i, a in enumerate(_AREA_ORDER):
        origin_y = -i * (band_height + band_gap)
        band_center[a] = origin_y - band_height / 2.0

        nodes = consumers_by_area[a]
        ncols = max(1, math.ceil(len(nodes) / rows)) if nodes else 1
        for idx, n in enumerate(nodes):
            col, row = idx // rows, idx % rows
            pos[n] = (x_consumer0 + col * dx, origin_y - row * dy)
        block_center[a] = (x_consumer0 + (ncols - 1) * dx / 2.0, band_center[a])

        if a in income_by_area:
            pos[income_by_area[a]] = (x_income, band_center[a])

        # Stack the destinations so the whole stack fits inside the band height
        # (up to 10 categories + bills + fees) — otherwise tall stacks from
        # neighbouring areas would collide.
        dests = dests_by_area[a]
        n_d = len(dests)
        m_dy = (band_height / (n_d - 1)) if n_d > 1 else 0.0
        for j, key in enumerate(dests):
            y = band_center[a] + (j - (n_d - 1) / 2.0) * m_dy
            pos[(a, key)] = (x_merchant, y)

    # ---- draw ------------------------------------------------------------
    fig = Figure(figsize=(9, 6.5), layout="constrained")
    ax = fig.subplots()

    # Faint static connectors (structure): income → block, block → destinations.
    for a in _AREA_ORDER:
        bcx, bcy = block_center[a]
        if a in income_by_area:
            ix, iy = pos[income_by_area[a]]
            ax.plot([ix, bcx], [iy, bcy], color="grey", alpha=0.12, lw=1.0, zorder=1)
        for key in dests_by_area[a]:
            mx, my = pos[(a, key)]
            ax.plot([bcx, mx], [bcy, my], color="grey", alpha=0.12, lw=0.8, zorder=1)

    # Consumer dots, per area (so colour is vectorised cleanly).
    for a in _AREA_ORDER:
        nodes = consumers_by_area[a]
        if not nodes:
            continue
        xs = [pos[n][0] for n in nodes]
        ys = [pos[n][1] for n in nodes]
        ax.scatter(xs, ys, s=26, c=_AREA_COLOR[a], marker="o", alpha=0.85, zorder=2)

    # Income triangles + labels.
    for a in _AREA_ORDER:
        if a not in income_by_area:
            continue
        x, y = pos[income_by_area[a]]
        ax.scatter(
            [x], [y], s=420, c=_AREA_COLOR[a], marker="^",
            edgecolors="black", linewidths=1.4, zorder=3,
        )
        ax.annotate(
            f"income\n{a}", (x, y), xytext=(-10, 0), textcoords="offset points",
            ha="right", va="center", fontsize=9, fontweight="bold",
        )

    # Destination squares + labels. Purchase categories are area-coloured; the
    # two special destinations are styled to stand out (fees = red).
    for a in _AREA_ORDER:
        for key in dests_by_area[a]:
            x, y = pos[(a, key)]
            if key == _DEST_FEES:
                face, edge, lw, label_w, fs = "red", "black", 1.0, "bold", 8
            elif key == _DEST_BILLS:
                face, edge, lw, label_w, fs = _AREA_COLOR[a], "black", 1.0, "bold", 8
            else:
                face, edge, lw, label_w, fs = _AREA_COLOR[a], "black", 0.6, "normal", 8
            ax.scatter([x], [y], s=120, c=face, marker="s",
                       edgecolors=edge, linewidths=lw, alpha=0.95, zorder=3)
            ax.annotate(key, (x, y), xytext=(10, 0), textcoords="offset points",
                        ha="left", va="center", fontsize=fs, fontweight=label_w)

    # ---- live money-flow arrows (latest simulated day) -------------------
    latest, flows = _latest_day_flows(model)
    if flows is not None:
        all_vals = (
            list(flows["salary"].values()) + list(flows["purchase"].values())
            + list(flows["billsdebt"].values()) + list(flows["fees"].values())
        )
        vmax = max(all_vals) if all_vals else 0.0

        def _arrow(src, dst, eur, color):
            if eur <= 0 or vmax <= 0:
                return
            lw = 1.0 + 5.0 * math.sqrt(eur / vmax)  # compress range; keep visible
            ax.annotate(
                "", xy=dst, xytext=src,
                arrowprops={"arrowstyle": "-|>", "color": color, "lw": lw,
                            "alpha": 0.8, "shrinkA": 6, "shrinkB": 6,
                            "mutation_scale": 12 + 6 * lw},
                zorder=4,
            )

        for a in _AREA_ORDER:
            bc = block_center[a]
            if a in income_by_area:
                _arrow(pos[income_by_area[a]], bc, flows["salary"][a], _FLOW_COLOR["salary"])
            for cat in mcats_by_area[a]:
                _arrow(bc, pos[(a, cat)], flows["purchase"][(a, cat)], _FLOW_COLOR["purchase"])
            _arrow(bc, pos[(a, _DEST_BILLS)], flows["billsdebt"][a], _FLOW_COLOR["billsdebt"])
            _arrow(bc, pos[(a, _DEST_FEES)], flows["fees"][a], _FLOW_COLOR["fees"])

    # Column headers.
    top_y = band_center[_AREA_ORDER[0]] + band_height / 2.0 + 0.9
    ax.text(x_income, top_y, "Income", ha="center", fontweight="bold", fontsize=11)
    ax.text(block_center[_AREA_ORDER[0]][0], top_y, "Consumers",
            ha="center", fontweight="bold", fontsize=11)
    ax.text(x_merchant, top_y, "Where money goes", ha="center",
            fontweight="bold", fontsize=11)

    # Bottom legend: node shapes, area colours, and arrow (flow) types.
    handles = [
        Line2D([], [], marker="^", color="w", markerfacecolor="grey",
               markeredgecolor="black", markersize=12, label="Income source"),
        Line2D([], [], marker="o", color="w", markerfacecolor="grey",
               markersize=8, label="Consumer"),
        Line2D([], [], marker="s", color="w", markerfacecolor="grey",
               markeredgecolor="black", markersize=9, label="Destination"),
    ] + [
        Line2D([], [], marker="s", color="w", markerfacecolor=_AREA_COLOR[a],
               markersize=10, label=a.capitalize())
        for a in _AREA_ORDER
    ] + [
        Line2D([], [], color=_FLOW_COLOR["salary"], lw=3, label="→ salary in"),
        Line2D([], [], color=_FLOW_COLOR["purchase"], lw=3, label="→ purchases"),
        Line2D([], [], color=_FLOW_COLOR["billsdebt"], lw=3, label="→ bills/debt"),
        Line2D([], [], color=_FLOW_COLOR["fees"], lw=3, label="→ fees (bank)"),
    ]
    fig.legend(handles=handles, loc="outside lower center", ncol=5, frameon=False)

    # Reserve room on the right for the destination labels.
    ax.set_xlim(x_income - 1.4, x_merchant + 3.8)
    ax.set_axis_off()
    subtitle = f"arrows = € moved on {latest}" if latest else "press play to see flows"
    fig.suptitle(f"Who pays whom — money flows left → right\n{subtitle}",
                 fontsize=13, fontweight="bold")
    solara.FigureMatplotlib(fig)
    solara.FileDownload(
        lambda: _png_bytes(fig), filename="network_structure.png",
        label="Download PNG",
    )


# ----------------------------------------------------------------------------
# Panel 3 — KPIs (Mesa's built-in line plot)
# ----------------------------------------------------------------------------


def _post_process_lines(ax):
    ax.set_ylabel("count / EUR")
    ax.legend(loc="upper left")


KPIPanel = make_plot_component(
    {"daily_txn_count": "tab:blue", "daily_eur_total": "tab:orange"},
    post_process=_post_process_lines,
)


# ----------------------------------------------------------------------------
# Panel 3b — Behavioural-economics events (the thesis layer made visible)
# ----------------------------------------------------------------------------


@solara.component
def BehaviouralEventsPanel(model: ItalyModel):
    """Surface the behavioural mechanics that are otherwise invisible in the
    other panels, all read straight from ``model.transactions``:

      • Overdraft fees   (Stango & Zinman 2014) — €30 flat, ``category="overdraft_fee"``
      • Late-payment fees (Dahan & Nisan 2020)  — ``category="late_payment_fee"``
      • Payday spike     (Olafsson & Pagel 2018) — dashed lines on the payday
        (day ``numbers.PAYDAY_DAY_OF_MONTH``) so the spend bump lines up visibly.

    Top axis: daily counts of fee events (stacked). Bottom axis: daily
    purchase EUR with payday markers. No model changes — pure aggregation.
    """
    update_counter.get()

    overdraft = defaultdict(int)
    late = defaultdict(int)
    spend = defaultdict(float)
    for t in model.transactions:
        d = t["date"]
        if t["kind"] == "fee" and t["category"] == "overdraft_fee":
            overdraft[d] += 1
        elif t["kind"] == "fee" and t["category"] == "late_payment_fee":
            late[d] += 1
        elif t["kind"] == "purchase":
            spend[d] += t["amount_eur"]

    dates = sorted(set(overdraft) | set(late) | set(spend))
    if not dates:
        solara.Markdown("_No transactions yet — press play to populate._")
        return

    x = list(range(len(dates)))
    od_vals = [overdraft[d] for d in dates]
    late_vals = [late[d] for d in dates]
    spend_vals = [spend[d] for d in dates]
    payday_idx = [i for i, d in enumerate(dates) if int(d[8:10]) == numbers.PAYDAY_DAY_OF_MONTH]

    fig = Figure(figsize=(9, 5), layout="constrained")
    ax_top, ax_bot = fig.subplots(2, 1, sharex=True)

    ax_top.bar(x, od_vals, color="tab:red", label="Overdraft fees")
    ax_top.bar(x, late_vals, bottom=od_vals, color="tab:purple", label="Late payments")
    ax_top.set_ylabel("events / day")
    ax_top.set_title("Behavioural-economics events")
    ax_top.legend(loc="upper left")

    ax_bot.plot(x, spend_vals, color="tab:orange", lw=1.5)
    ax_bot.set_ylabel("EUR purchases / day")
    for i in payday_idx:
        ax_bot.axvline(i, color="grey", ls="--", lw=0.8, zorder=0)
    if payday_idx:
        ax_bot.axvline(payday_idx[0], color="grey", ls="--", lw=0.8,
                       label=f"payday (day {numbers.PAYDAY_DAY_OF_MONTH})")
        ax_bot.legend(loc="upper left")

    # Sparse, readable date ticks (MM-DD), at most ~8 of them.
    step = max(1, len(dates) // 8)
    ticks = list(range(0, len(dates), step))
    ax_bot.set_xticks(ticks)
    ax_bot.set_xticklabels([dates[i][5:] for i in ticks], rotation=45, ha="right")
    ax_bot.set_xlabel("date")

    solara.FigureMatplotlib(fig)
    solara.FileDownload(
        lambda: _png_bytes(fig), filename="behavioural_events.png",
        label="Download PNG",
    )


# ----------------------------------------------------------------------------
# Panel — Debtor composition (who is a climber / chronic / subsister)
# ----------------------------------------------------------------------------


@solara.component
def DebtorCompositionPanel(model: ItalyModel):
    """How the consumer population splits across the three debtor archetypes,
    and how much principal each archetype carries right now.

    Left: a count per subtype, split into *in debt* (solid) and *dug out /
    cleared* (faded) — a climber who repaid keeps the label but is no longer in
    debt. A grey 'never in debt' bar gives the non-debtor share for context.
    Right: total outstanding principal (EUR) per subtype."""
    update_counter.get()

    subtypes = list(numbers.DEBTOR_SUBTYPES)
    in_debt = {st: 0 for st in subtypes}
    cleared = {st: 0 for st in subtypes}
    total_debt = {st: 0.0 for st in subtypes}
    n_no_debt = 0
    for c in model.consumers:
        st = c.debtor_subtype
        if st is None or st not in in_debt:
            n_no_debt += 1
            continue
        total_debt[st] += c.debt_balance
        if c.has_debt:
            in_debt[st] += 1
        else:
            cleared[st] += 1

    fig = Figure(figsize=(9, 3.5), layout="constrained")
    ax_n, ax_eur = fig.subplots(1, 2)

    # Left — counts, stacked in-debt + cleared, plus a 'never in debt' bar.
    labels = subtypes + ["none"]
    x = list(range(len(labels)))
    bottoms = [in_debt[st] for st in subtypes] + [n_no_debt]
    colors = [_DEBTOR_COLOR[st] for st in subtypes] + [_DEBTOR_COLOR[None]]
    ax_n.bar(x, bottoms, color=colors, label="in debt")
    ax_n.bar(
        x[:-1], [cleared[st] for st in subtypes],
        bottom=[in_debt[st] for st in subtypes],
        color=[_DEBTOR_COLOR[st] for st in subtypes], alpha=0.4,
        label="dug out / cleared",
    )
    ax_n.set_xticks(x)
    ax_n.set_xticklabels(labels)
    ax_n.set_ylabel("consumers")
    ax_n.set_title("Debtor composition")
    ax_n.legend(loc="upper right")
    for i, st in enumerate(subtypes):
        tot = in_debt[st] + cleared[st]
        if tot:
            ax_n.text(i, tot, str(tot), ha="center", va="bottom", fontsize=9)
    if n_no_debt:
        ax_n.text(len(subtypes), n_no_debt, str(n_no_debt),
                  ha="center", va="bottom", fontsize=9)

    # Right — total outstanding principal per subtype.
    eur_vals = [total_debt[st] for st in subtypes]
    ax_eur.bar(subtypes, eur_vals, color=[_DEBTOR_COLOR[st] for st in subtypes])
    ax_eur.set_ylabel("EUR outstanding")
    ax_eur.set_title("Debt principal by subtype")
    for i, v in enumerate(eur_vals):
        ax_eur.text(i, v, f"€{v:,.0f}", ha="center", va="bottom", fontsize=9)

    solara.FigureMatplotlib(fig)
    solara.FileDownload(
        lambda: _png_bytes(fig), filename="debtor_composition.png",
        label="Download PNG",
    )


# ----------------------------------------------------------------------------
# Panel — Debt trajectory (mean principal per subtype over the run)
# ----------------------------------------------------------------------------


@solara.component
def DebtTrajectoryPanel(model: ItalyModel):
    """Total outstanding principal per archetype over the simulated days.

    This is the payoff view for the debt-as-stock layer: the climber line
    trends **down** (digging out), the chronic line stays roughly **flat**
    (interest-only), and the subsister line drifts **up** toward its ceiling."""
    update_counter.get()

    df = model.datacollector.get_model_vars_dataframe()
    cols = [f"debt_total_{st}" for st in numbers.DEBTOR_SUBTYPES]
    if df.empty or not all(col in df.columns for col in cols):
        solara.Markdown("_Press play to build the debt trajectory._")
        return

    fig = Figure(figsize=(6, 3.5), layout="constrained")
    ax = fig.subplots()
    for st in numbers.DEBTOR_SUBTYPES:
        ax.plot(df.index, df[f"debt_total_{st}"], color=_DEBTOR_COLOR[st],
                lw=1.6, label=st)
    ax.set_xlabel("day")
    ax.set_ylabel("EUR outstanding")
    ax.set_title("Debt trajectory by subtype")
    ax.legend(loc="upper right")
    solara.FigureMatplotlib(fig)
    solara.FileDownload(
        lambda: _png_bytes(fig), filename="debt_trajectory.png",
        label="Download PNG",
    )


# ----------------------------------------------------------------------------
# Panel 4 — Archetypes (reference card: what entity kinds + parameters exist)
# ----------------------------------------------------------------------------


def _build_category_table() -> pd.DataFrame:
    """One row per spending category: paper share + expected ticket EUR."""
    rows = []
    for cat, share in numbers.CATEGORY_SHARES.items():
        mu, sigma = numbers.CATEGORY_TICKET_LOGNORMAL[cat]
        expected_ticket = math.exp(mu + sigma * sigma / 2)
        rows.append({
            "category": cat,
            "paper_share": round(share, 3),
            "expected_ticket_eur": round(expected_ticket, 1),
        })
    return pd.DataFrame(rows).sort_values("paper_share", ascending=False)


def _build_bill_table() -> pd.DataFrame:
    rows = []
    for bill, spec in numbers.BILL_TYPES.items():
        rows.append({
            "bill_type": bill,
            "share_of_households": spec["share"],
            "mean_eur": spec["mean_eur"],
            "day_of_month": spec["day"],
        })
    return pd.DataFrame(rows).sort_values("mean_eur", ascending=False)


def _build_macro_area_table() -> pd.DataFrame:
    rows = [
        {"area": area, "population_share": round(w, 3)}
        for area, w in numbers.MACRO_AREA_WEIGHTS.items()
    ]
    return pd.DataFrame(rows)


def _build_agent_table() -> pd.DataFrame:
    rows = [
        {
            "agent_kind": "Consumer",
            "what_it_does": (
                "Pays bills + debt service, maybe buys at a merchant, sweeps "
                "the monthly residual into savings/pension."
            ),
            "attributes": (
                "macro_area, monthly_income, income_quartile/quintile, "
                "has_debt, debtor_subtype (climber/chronic/subsister), "
                "debt_balance, is_saver, accounts (current/savings/pension)"
            ),
        },
        {
            "agent_kind": "Merchant",
            "what_it_does": "Passive — receives spending into its own account.",
            "attributes": "category, macro_area, account.balance",
        },
        {
            "agent_kind": "IncomeSource",
            "what_it_does": "On the 27th of every month, credits every consumer it serves.",
            "attributes": "macro_area, served_consumers, account.balance",
        },
    ]
    return pd.DataFrame(rows)


@solara.component
def ArchetypesPanel(model: ItalyModel):
    """Static reference card. Lists the building blocks of the simulation
    so a reader can see at a glance what kinds of agents and parameters
    exist. Content is derived from ``numbers.py`` — change a number there
    and this panel reflects it on the next reload."""
    # No update_counter.get() — this panel is static.

    solara.Markdown(
        """
### Agent kinds

The simulation runs only three kinds of agent. Every transaction in the
output is one of these three talking to another.
        """
    )
    solara.DataFrame(_build_agent_table(), items_per_page=5)

    solara.Markdown(
        """
### Spending categories (10)

The ten card-visible categories from Emiliozzi et al. (2023) §5.
`paper_share` is how often each category is picked; `expected_ticket_eur`
is the mean ticket size derived from the per-category lognormal.
        """
    )
    solara.DataFrame(_build_category_table(), items_per_page=10)

    solara.Markdown(
        """
### Bill types (5)

Recurring bills from the BoI 2023-24 Payment Behaviour Survey §8.
A consumer subscribes to each bill type with probability `share_of_households`.
        """
    )
    solara.DataFrame(_build_bill_table(), items_per_page=6)

    solara.Markdown(
        """
### Macro-areas (3)

Population weights from Emiliozzi et al. (2023) §6, rolled up from the 20-region table.
A consumer is assigned to NORTH / CENTRE / SOUTH with these probabilities.
        """
    )
    solara.DataFrame(_build_macro_area_table(), items_per_page=3)


# ----------------------------------------------------------------------------
# Panel 5 — Account inspector (cluster → consumer → statements + sparkline)
# ----------------------------------------------------------------------------


@solara.component
def AccountInspectorPanel(model: ItalyModel):
    """Drill into one consumer's three accounts.

    Pick a **cluster** (macro-area | income quartile | financial status),
    then a consumer in it, and see the current/savings/pension statements
    plus a running-balance sparkline. Read-only — it never mutates the model
    and never writes to disk."""
    update_counter.get()

    # Hooks must run unconditionally and before any early return
    # (Solara rules-of-hooks). Default to "" and resolve below.
    sel_cluster, set_cluster = solara.use_state("")
    sel_subtype, set_subtype = solara.use_state("all")
    sel_agent, set_agent = solara.use_state("")

    clusters = model.clusters()
    cluster_labels = sorted(f"{a} | {b} | {s}" for (a, b, s) in clusters)
    if not cluster_labels:
        solara.Markdown("_No consumers in the model._")
        return

    if sel_cluster not in cluster_labels:
        sel_cluster = cluster_labels[0]
    key = tuple(sel_cluster.split(" | "))
    members = clusters.get(key, [])

    # Optional debtor-archetype filter on top of the cluster pick.
    subtype_values = ["all", *numbers.DEBTOR_SUBTYPES, "no debt"]
    if sel_subtype not in subtype_values:
        sel_subtype = "all"
    if sel_subtype == "no debt":
        members = [c for c in members if c.debtor_subtype is None]
    elif sel_subtype != "all":
        members = [c for c in members if c.debtor_subtype == sel_subtype]

    by_label = {f"#{c.unique_id}": c for c in members}
    member_labels = list(by_label)

    if sel_agent not in by_label and member_labels:
        sel_agent = member_labels[0]

    solara.Select(
        label="Cluster (area | income quartile | status)",
        value=sel_cluster, values=cluster_labels, on_value=set_cluster,
    )
    solara.Select(
        label="Debtor subtype", value=sel_subtype,
        values=subtype_values, on_value=set_subtype,
    )
    if not member_labels:
        solara.Markdown("_No consumers match this cluster + subtype._")
        return
    solara.Select(
        label="Consumer", value=sel_agent,
        values=member_labels, on_value=set_agent,
    )

    c = by_label.get(sel_agent)
    if c is None:
        solara.Markdown("_Pick a consumer._")
        return

    # Debtor archetype line — climber / chronic / subsister (or a former
    # debtor who already dug out: subtype label kept, has_debt now False).
    if c.debtor_subtype is None:
        debt_desc = "no debt"
    else:
        state = "in debt" if c.has_debt else "dug out — debt cleared"
        debt_desc = (
            f"{c.debtor_subtype} ({state}); "
            f"debt balance €{c.debt_balance:,.2f}"
        )

    vuln = " · ⚠ financially vulnerable" if c.is_financially_vulnerable else ""
    solara.Markdown(
        f"**Consumer #{c.unique_id}** — {c.macro_area}, "
        f"**{c.income_source}** income (€{c.monthly_income:,.0f}/mo, "
        f"**{c.income_level}**), "
        f"Q{c.income_quartile} / quintile {c.income_quintile}, "
        f"{'saver' if c.is_saver else 'non-saver'}"
        f"{' (pension)' if c.is_pension_saver else ''}, "
        f"{debt_desc}{vuln}.  \n"
        f"current €{c.accounts.current.balance:,.2f} · "
        f"savings €{c.accounts.savings.balance:,.2f} · "
        f"pension €{c.accounts.pension.balance:,.2f}"
    )

    # Running balance of the current account (start → after every entry).
    cur = c.accounts.current
    bal = cur.starting_balance
    xs, ys = [0], [bal]
    for i, e in enumerate(cur.entries, start=1):
        bal += e.amount_eur if e.direction == "in" else -e.amount_eur
        xs.append(i)
        ys.append(bal)
    fig = Figure(figsize=(6, 2.2), layout="constrained")
    ax = fig.subplots()
    ax.plot(xs, ys, color="tab:blue")
    ax.axhline(0, color="grey", lw=0.6, ls="--")
    ax.set_title("Current-account running balance")
    ax.set_xlabel("entry #")
    ax.set_ylabel("EUR")
    solara.FigureMatplotlib(fig)

    # Debt-balance trajectory for debtors (principal after each monthly
    # service; the last point is 0 if they have dug out). Colour by subtype.
    if c.debtor_subtype is not None and c._debt_history:
        color = _DEBTOR_COLOR.get(c.debtor_subtype, _DEBTOR_COLOR[None])
        fig_d = Figure(figsize=(6, 2.2), layout="constrained")
        ax_d = fig_d.subplots()
        months = list(range(1, len(c._debt_history) + 1))
        ax_d.plot(months, c._debt_history, color=color, marker="o", lw=1.6)
        ax_d.set_ylim(bottom=0)
        ax_d.set_title(f"Debt balance ({c.debtor_subtype})")
        ax_d.set_xlabel("debt-service month #")
        ax_d.set_ylabel("EUR outstanding")
        solara.FigureMatplotlib(fig_d)

    for name, acct in c.accounts.as_dict().items():
        solara.Markdown(
            f"**{name}** — {len(acct.entries)} entries, "
            f"balance €{acct.balance:,.2f}"
        )
        if acct.entries:
            dfa = pd.DataFrame([
                {
                    "date": e.date,
                    "dir": e.direction,
                    "counterparty": e.counterparty,
                    "category": e.category,
                    "amount_eur": round(e.amount_eur, 2),
                }
                for e in acct.entries
            ])
            solara.DataFrame(dfa, items_per_page=10)


# ----------------------------------------------------------------------------
# Panel — Income composition (sources × levels, and the scale of each)
# ----------------------------------------------------------------------------


@solara.component
def IncomeCompositionPanel(model: ItalyModel):
    """How the population splits across primary income *sources*, and the *scale*
    of each — so the different income types are legible at a glance.

    Left: headcount per source, with the low/middle/high level mix stacked inside
    each bar (Bank of Italy Payment Behaviour Survey euro bands). Right: mean
    monthly income per source — the scale gradient, self-employed highest down to
    unemployed lowest (SHIW relative levels)."""
    update_counter.get()

    sources = list(numbers.INCOME_SOURCE_SHARE.keys())
    levels = ["low", "middle", "high"]
    counts = {s: {lv: 0 for lv in levels} for s in sources}
    income_sum = {s: 0.0 for s in sources}
    n = {s: 0 for s in sources}
    for c in model.consumers:
        s = c.income_source
        if s not in counts:
            continue
        if c.income_level in counts[s]:
            counts[s][c.income_level] += 1
        income_sum[s] += c.monthly_income
        n[s] += 1

    fig = Figure(figsize=(9, 3.5), layout="constrained")
    ax_n, ax_eur = fig.subplots(1, 2)

    x = list(range(len(sources)))
    bottoms = [0] * len(sources)
    for lv in levels:
        heights = [counts[s][lv] for s in sources]
        ax_n.bar(x, heights, bottom=bottoms, color=_LEVEL_COLOR[lv], label=lv,
                 edgecolor="white", linewidth=0.5)
        bottoms = [b + h for b, h in zip(bottoms, heights, strict=True)]
    ax_n.set_xticks(x)
    ax_n.set_xticklabels(sources, rotation=20, ha="right")
    ax_n.set_ylabel("consumers")
    ax_n.set_title("Income sources (level mix)")
    ax_n.legend(loc="upper right", title="level")
    for i, s in enumerate(sources):
        if n[s]:
            ax_n.text(i, n[s], str(n[s]), ha="center", va="bottom", fontsize=9)

    means = [income_sum[s] / n[s] if n[s] else 0.0 for s in sources]
    ax_eur.bar(x, means, color=[_INCOME_COLOR[s] for s in sources])
    ax_eur.set_xticks(x)
    ax_eur.set_xticklabels(sources, rotation=20, ha="right")
    ax_eur.set_ylabel("mean €/month")
    ax_eur.set_title("Mean income by source")
    for i, v in enumerate(means):
        if v:
            ax_eur.text(i, v, f"€{v:,.0f}", ha="center", va="bottom", fontsize=9)

    solara.FigureMatplotlib(fig)
    solara.FileDownload(
        lambda: _png_bytes(fig), filename="income_composition.png",
        label="Download PNG",
    )


# ----------------------------------------------------------------------------
# Panel — Balance trajectory (mean current balance per income source over time)
# ----------------------------------------------------------------------------


@solara.component
def BalanceTrajectoryPanel(model: ItalyModel):
    """Mean current-account balance over the run, one line per income source.
    The payoff view for *how accounts move* (not just where they end): pensions
    glide, payroll shows the payday sawtooth, and the unemployed/transfers lines
    hug a low level near zero."""
    update_counter.get()

    df = model.datacollector.get_model_vars_dataframe()
    sources = list(numbers.INCOME_SOURCE_SHARE.keys())
    cols = [f"bal_cur_src_{s}" for s in sources]
    if df.empty or not all(col in df.columns for col in cols):
        solara.Markdown("_Press play to build the balance trajectories._")
        return

    fig = Figure(figsize=(6, 3.5), layout="constrained")
    ax = fig.subplots()
    for s in sources:
        ax.plot(df.index, df[f"bal_cur_src_{s}"], color=_INCOME_COLOR[s],
                lw=1.6, label=s)
    ax.axhline(0, color="grey", lw=0.6, ls="--")
    ax.set_xlabel("day")
    ax.set_ylabel("mean current balance (€)")
    ax.set_title("Account balance over time by income source")
    ax.legend(loc="upper left", fontsize=7)
    solara.FigureMatplotlib(fig)
    solara.FileDownload(
        lambda: _png_bytes(fig), filename="balance_trajectory.png",
        label="Download PNG",
    )


# ----------------------------------------------------------------------------
# Panel — Chronic debtors (the cohort the supervisor flagged as critical)
# ----------------------------------------------------------------------------


@solara.component
def ChronicDebtorPanel(model: ItalyModel):
    """Focused view of the chronically-indebted cohort — households that get
    stuck (interest-only repayment, principal never clears), tilted by SHIW 2022
    §3 financial vulnerability.

    Left: mean current-account balance over time for all three archetypes, so the
    contrast is visible — climbers rebuild a cash buffer as they dig out, while
    chronic and subsister households stay cash-poor. (The flat chronic *principal*
    itself is in the Debt-trajectory panel; here we show the household's everyday
    money.) Right: the fees the chronic cohort racks up (overdraft + late
    payment). The summary ties the cohort to the SHIW vulnerability definition."""
    update_counter.get()

    chronic = [c for c in model.consumers if c.debtor_subtype == "chronic"]
    if not chronic:
        solara.Markdown("_No chronic debtors in this run (try more consumers/seed)._")
        return

    chronic_ids = {str(c.unique_id) for c in chronic}
    fee_over = sum(
        t["amount_eur"] for t in model.transactions
        if t["kind"] == "fee" and t["category"] == "overdraft_fee"
        and t["from"] in chronic_ids
    )
    fee_late = sum(
        t["amount_eur"] for t in model.transactions
        if t["kind"] == "fee" and t["category"] == "late_payment_fee"
        and t["from"] in chronic_ids
    )

    n_chronic = len(chronic)
    n_vuln = sum(1 for c in chronic if c.is_financially_vulnerable)
    still = sum(1 for c in chronic if c.has_debt)
    mean_dsr = sum(c.debt_service_ratio for c in chronic) / n_chronic

    df = model.datacollector.get_model_vars_dataframe()

    fig = Figure(figsize=(9, 3.5), layout="constrained")
    ax_bal, ax_fee = fig.subplots(1, 2)

    if not df.empty:
        for st in numbers.DEBTOR_SUBTYPES:
            col = f"bal_cur_dst_{st}"
            if col in df.columns:
                lw = 2.2 if st == "chronic" else 1.2
                ax_bal.plot(df.index, df[col], color=_DEBTOR_COLOR[st],
                            lw=lw, label=st)
    ax_bal.axhline(0, color="grey", lw=0.6, ls="--")
    ax_bal.set_xlabel("day")
    ax_bal.set_ylabel("mean current balance (€)")
    ax_bal.set_title("Everyday balance by archetype")
    ax_bal.legend(loc="upper left", fontsize=8)

    ax_fee.bar(["overdraft", "late payment"], [fee_over, fee_late],
               color=["red", "tab:purple"])
    ax_fee.set_ylabel("EUR fees (cohort total)")
    ax_fee.set_title("Chronic fee burden")
    for i, v in enumerate([fee_over, fee_late]):
        ax_fee.text(i, v, f"€{v:,.0f}", ha="center", va="bottom", fontsize=9)

    solara.FigureMatplotlib(fig)
    solara.Markdown(
        f"**{n_chronic} chronic debtors** · always in debt {still}/{n_chronic} "
        f"(none dug out) · financially vulnerable {n_vuln}/{n_chronic} "
        f"(SHIW: below-median income & debt-service > 30%) · "
        f"mean debt-service ratio {mean_dsr:.0%}."
    )
    solara.FileDownload(
        lambda: _png_bytes(fig), filename="chronic_debtors.png",
        label="Download PNG",
    )


# ----------------------------------------------------------------------------
# Build the initial model + assemble the page
# ----------------------------------------------------------------------------

# This is the only place where the model is constructed at import time.
# Because ItalyModel does NOT write to disk and does NOT create UUIDs,
# this is fast (~50ms) and side-effect-free — so the Solara startup
# health check finds the page ready without issues.
model = ItalyModel(n_consumers=150, n_merchants_per_category=3, n_days=30, seed=42)

page = SolaraViz(
    model,
    components=[
        SpendingByArea, NetworkPanel, KPIPanel, BehaviouralEventsPanel,
        IncomeCompositionPanel, BalanceTrajectoryPanel,
        DebtorCompositionPanel, DebtTrajectoryPanel, ChronicDebtorPanel,
        AccountInspectorPanel, ArchetypesPanel,
    ],
    model_params=model_params,
    name="SynthItaly — bank-eye view",
)
page  # noqa: B018 (solara reads this at module load)


# Silence the noisy matplotlib warning about figures being created
# without a manager in headless environments. Cosmetic only.
plt.set_loglevel("error")
