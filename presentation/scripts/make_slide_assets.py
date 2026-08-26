#!/usr/bin/env python3
"""Slide-ready graphics for the Kolloquium deck, sections 4-6
(Model Architecture · Transaction Logic · Outputs & Validation).

Run:  uv run python presentation/make_slide_assets.py

Writes NEW graphics into presentation/slide_assets/ (PNG 200dpi + SVG) and copies
the relevant already-generated figures/diagrams into the same folder with
slide-prefixed names, so everything for a slide sits in one place. See
presentation/slide_assets/SLIDE_MAP.md for which asset goes on which slide.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from synthitaly import numbers as N
from synthitaly.model import ItalyModel

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "slide_assets"
OUT.mkdir(parents=True, exist_ok=True)

BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948",
)
BROWN = "#8a5a2b"
INK, INK2, MUTED, LINE, BASE = "#121820", "#47505b", "#898781", "#e4e8ee", "#c3c2b7"
PANEL = "#f4f6f9"
SUBTYPE = {"climber": AQUA, "chronic": RED, "subsister": YELLOW}

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Segoe UI", "Arial"],
    "figure.facecolor": "white", "savefig.facecolor": "white",
    "axes.edgecolor": BASE, "text.color": INK, "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED,
})


def save(fig, name):
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  {name}")


# -- box helpers (shared style with make_diagrams) --------------------------- #
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


def canvas(w=13, h=7.3):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, text, face=PANEL, edge=BASE, tc=INK, fs=11, weight="normal",
        align="center", lw=1.4, va="center"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=2.2",
                                facecolor=face, edgecolor=edge, linewidth=lw, mutation_aspect=0.55))
    tx = x + w / 2 if align == "center" else x + 2.4
    ha = "center" if align == "center" else "left"
    ty = y + h / 2 if va == "center" else (y + h - 3 if va == "top" else y + 2.6)
    ax.text(tx, ty, text, ha=ha, va=va, color=tc, fontsize=fs, weight=weight, linespacing=1.4)


def arrow(ax, p0, p1, color=INK2, lw=2.0, style="-|>", ls="-", rad=0.0):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=15, color=color,
                                 lw=lw, linestyle=ls, connectionstyle=f"arc3,rad={rad}",
                                 shrinkA=3, shrinkB=3))


def lab(ax, x, y, t, color=INK2, fs=10, weight="normal", style="normal", ha="center"):
    ax.text(x, y, t, ha=ha, va="center", color=color, fontsize=fs, weight=weight, style=style)


def title(ax, t, sub=None):
    ax.text(0, 99, t, ha="left", va="top", fontsize=17, weight="bold", color=INK)
    if sub:
        ax.text(0, 92, sub, ha="left", va="top", fontsize=11.5, color=MUTED)


def axstyle(ax, t=None, xl=None, yl=None, grid="y"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color(BASE); ax.spines["bottom"].set_color(BASE)
    ax.tick_params(length=0); ax.grid(axis=grid, color=LINE, lw=0.8); ax.set_axisbelow(True)
    if t: ax.set_title(t, color=INK, loc="left", fontsize=15, weight="bold", pad=10)
    if xl: ax.set_xlabel(xl);
    if yl: ax.set_ylabel(yl)


# =========================================================================== #
# SECTION 4 — MODEL ARCHITECTURE (slide 11)
# =========================================================================== #
def s11_agents_and_objects():
    fig, ax = canvas(13, 7.3)
    title(ax, "Agents and the financial objects they hold",
          "three agent types · money lives in accounts, not in the agents")
    # agents
    box(ax, 2, 66, 30, 20,
        "Consumer  (household)\n\nthe only active decision-maker\npays bills · services debt ·\nbuys · sweeps surplus",
        face="#eaf7f2", edge=AQUA, fs=10.5, weight="bold", va="top")
    box(ax, 35, 66, 30, 20,
        "IncomeSource  (per area)\n\nthe “employer”\ncredits salary on the 27th\n(+ December tredicesima)",
        face="#e9f5ec", edge=GREEN, fs=10.5, weight="bold", va="top")
    box(ax, 68, 66, 30, 20,
        "Merchant  (shop)\n\npassive payee\none per (category × area)\nreceives purchases",
        face="#fdf3e8", edge=ORANGE, fs=10.5, weight="bold", va="top")
    # objects belt
    lab(ax, 0, 60, "FINANCIAL OBJECTS (separate from agents)", color=MUTED, fs=11, weight="bold", ha="left")
    box(ax, 2, 34, 30, 22,
        "AccountSet  (per consumer)\n──────\ncurrent  ·  savings  ·  pension\n\neach = a BankAccount:\nbalance + list of BankEntry\n(date, in/out, amount)",
        face=PANEL, edge=VIOLET, fs=9.6, align="left", va="top")
    box(ax, 35, 34, 30, 22,
        "Debt as a STOCK\n──────\ndebt_balance (principal)\naccrues 0.5%/month interest\n\noverdraft = a floor, not an\naccount (chronic: −1 mo service)",
        face=PANEL, edge=RED, fs=9.6, align="left", va="top")
    box(ax, 68, 34, 30, 22,
        "Obligations & lenders\n──────\nrecurring bill subscriptions\n(+ overdue queue)\n\ncredit_line stand-in\n(subsister borrows cash)",
        face=PANEL, edge=BROWN, fs=9.6, align="left", va="top")
    box(ax, 12, 8, 76, 16,
        "Not modelled:  physical cash / wallets  ·  payment-method choice (card vs cash vs transfer)  ·  ATM withdrawal.\n"
        "Every movement is an account debit/credit — “cash_advance” is a spending category, not a cash transaction.",
        face="#fff6f0", edge=ORANGE, fs=10, align="center")
    save(fig, "s11_a_agents_and_objects")


def s11_time_calendar():
    fig, ax = plt.subplots(figsize=(13, 4.6))
    ax.set_xlim(0.3, 30.7); ax.set_ylim(0, 10); ax.axis("off")
    ax.text(0.3, 9.4, "The clock: a daily step, monthly cadence on top",
            fontsize=17, weight="bold", color=INK, ha="left")
    ax.text(0.3, 8.5, "one representative month — discretionary purchases can happen any day; scheduled events fall on fixed days",
            fontsize=11.5, color=MUTED, ha="left")
    # day axis
    for d in range(1, 31):
        ax.plot([d, d], [2.0, 2.4], color=BASE, lw=1)
        if d % 5 == 0 or d == 1:
            ax.text(d, 1.4, str(d), ha="center", va="center", color=MUTED, fontsize=9)
    ax.plot([1, 30], [2.0, 2.0], color=BASE, lw=1.3)
    # discretionary band
    ax.add_patch(plt.Rectangle((1, 3.0), 29, 1.1, color=BLUE, alpha=0.12))
    ax.text(15.5, 3.55, "discretionary purchases — daily, probability ∝ intensity (weekday × season × holiday × payday spike)",
            ha="center", va="center", color=BLUE, fontsize=10, weight="bold")
    # scheduled events
    # (day, label, colour, stem-top) — 25th sits low, 27th high so their labels don't collide
    events = [
        (1, "1st\nmonth-close\n+ savings sweep", VIOLET, 6.2),
        (5, "5th\nmortgage", BROWN, 6.2), (10, "10th\nutilities", BROWN, 6.2),
        (15, "15th\ntelecom", BROWN, 6.2), (20, "20th\nconsumer loan", BROWN, 6.2),
        (25, "25th · debt service", RED, 5.0),
        (27, "27th\nSALARY in\n(+Dec bonus)", GREEN, 7.0),
    ]
    for d, txt, c, top in events:
        ax.plot([d, d], [4.4, top], color=c, lw=2.2)
        ax.plot(d, top, "o", color=c, ms=7)
        ha = "right" if d == 25 else "center"
        dx = -0.4 if d == 25 else 0
        ax.text(d + dx, top + 0.35, txt, ha=ha, va="bottom", color=c, fontsize=8.6, weight="bold", linespacing=1.15)
    save(fig, "s11_b_time_calendar")


# =========================================================================== #
# SECTION 5 — TRANSACTION LOGIC (slide 13)
# =========================================================================== #
def s13_generation_flow():
    fig, ax = canvas(13, 7.6)
    title(ax, "How one simulated day is generated, per consumer",
          "scheduled financial events + one probabilistic discretionary draw, both through an affordability gate")
    box(ax, 33, 79, 34, 8, "For each consumer, this day", face="#e7f0fb", edge=BLUE, weight="bold", fs=11.5)
    # scheduled column
    box(ax, 4, 54, 40, 21,
        "SCHEDULED (by calendar)\n──────\n• month-close + savings sweep (1st)\n• settle overdue bills (when cash allows)\n• pay bills whose due-day = today\n• service debt (25th)\n• receive salary (27th)",
        face=PANEL, edge=BROWN, fs=9.8, align="left", va="top")
    box(ax, 56, 54, 40, 21,
        "PROBABILISTIC (discretionary)\n──────\nbuy today?  draw ~ daily_intensity(date)\n= weekday × month × holiday × payday spike\n\nif yes: pick category (by paper share),\ndraw ticket € from its lognormal",
        face=PANEL, edge=BLUE, fs=9.8, align="left", va="top")
    arrow(ax, (44, 80), (24, 75), color=BLUE); arrow(ax, (56, 80), (76, 75), color=BLUE)
    # affordability gate
    box(ax, 26, 37, 48, 11,
        "Affordability gate  _can_afford()\nallowed unless it would breach the consumer's overdraft floor\n(reserves the €30 fee); floor = 0, or −1 month service for chronic debtors",
        face="#fff6f0", edge=ORANGE, fs=9.8)
    arrow(ax, (24, 54), (40, 48), color=MUTED); arrow(ax, (76, 54), (60, 48), color=MUTED)
    # outcomes
    box(ax, 3, 16, 28, 14, "PAY\n(debit → credit,\npaired)\ncharge €30 if it\ncrosses €0", face="#e9f5ec", edge=GREEN, fs=9.6, va="top")
    box(ax, 36, 16, 28, 14, "DEFER → overdue queue\nretried later with an\n11% late fee\n(liquidity-constrained\nhousehold)", face="#fdf3e8", edge=ORANGE, fs=9.6, va="top")
    box(ax, 69, 16, 28, 14, "BORROW  (subsister)\ndraw cash on the\ncredit_line stand-in\n→ raises debt_balance", face="#f3eefb", edge=VIOLET, fs=9.6, va="top")
    for x in (17, 50, 83):
        arrow(ax, (50, 38), (x, 30), color=MUTED, rad=0.0)
    box(ax, 20, 2, 60, 9, "Every outcome is logged to the transaction ledger (money stays conserved)",
        face="#e7f0fb", edge=BLUE, fs=10, weight="bold")
    save(fig, "s13_a_generation_flow")


def s13_transaction_types():
    fig, ax = canvas(13, 6.6)
    title(ax, "The five transaction types the model emits",
          "the `kind` field — no payment-method dimension; all flows are account debit/credit")
    rows = [
        ("salary", GREEN, "IncomeSource → Consumer on the 27th", "monthly net income (per-source lognormal) + Dec bonus"),
        ("purchase", BLUE, "discretionary draw ∝ daily intensity", "per-category lognormal ticket (share-weighted mean ≈ €38)"),
        ("bill", BROWN, "subscription due-day = today", "fixed mean € per bill type (incl. debt-service repayment)"),
        ("fee", RED, "balance crosses €0 / bill paid late", "flat €30 overdraft  ·  or 11% of the overdue bill"),
        ("loan", VIOLET, "subsister can't cover a shortfall", "credit draw sized to the gap (raises debt_balance)"),
    ]
    y = 74; h = 13
    lab(ax, 4, 88, "TYPE", color=MUTED, fs=10, weight="bold", ha="left")
    lab(ax, 26, 88, "WHAT TRIGGERS IT", color=MUTED, fs=10, weight="bold", ha="left")
    lab(ax, 62, 88, "HOW THE AMOUNT IS SET", color=MUTED, fs=10, weight="bold", ha="left")
    for name, c, trig, amt in rows:
        box(ax, 3, y, 20, h - 3, name, face="white", edge=c, tc=c, fs=13, weight="bold")
        lab(ax, 26, y + (h - 3) / 2, trig, color=INK2, fs=10.3, ha="left")
        lab(ax, 62, y + (h - 3) / 2, amt, color=INK2, fs=10.3, ha="left")
        y -= h
    box(ax, 3, 2, 94, 10,
        "Dataset columns per row:  date · kind · from · to · category · amount_eur · macro_area.   "
        "Not modelled: cash, ATM withdrawal, direct debit, P2P, or a card-vs-cash choice.",
        face=PANEL, edge=BASE, fs=10)
    save(fig, "s13_b_transaction_types")


def s13_daily_intensity():
    import datetime as dt
    days = [dt.date(2017, 1, 1) + dt.timedelta(days=i) for i in range(365)]
    inten = [N.daily_intensity(d) for d in days]
    x = np.arange(365)
    fig, ax = plt.subplots(figsize=(12, 5.2))
    ax.plot(x, inten, color=BLUE, lw=1.1, alpha=0.9)
    # monthly mean envelope
    import calendar
    for m in range(1, 13):
        idx = [i for i, d in enumerate(days) if d.month == m]
        mean = np.mean([inten[i] for i in idx])
        ax.plot([idx[0], idx[-1]], [mean, mean], color=ORANGE, lw=3, solid_capstyle="round")
        ax.text((idx[0] + idx[-1]) / 2, 0.42, calendar.month_abbr[m], ha="center", color=MUTED, fontsize=9)
    ax.text(0.99, 0.96, "orange = monthly mean", transform=ax.transAxes, ha="right", va="top",
            color=ORANGE, fontsize=10, weight="bold")
    axstyle(ax, "Spending intensity over a year — what drives the purchase probability",
            xl="day of year", yl="daily intensity multiplier", grid="y")
    ax.set_xlim(0, 364); ax.set_ylim(0.4, None)
    ax.annotate("December peak", (350, inten[349]), (300, 1.5), color=RED, fontsize=9.5,
                arrowprops=dict(arrowstyle="->", color=RED))
    ax.annotate("August trough", (220, min(inten[200:240])), (150, 0.62), color=INK2, fontsize=9.5,
                arrowprops=dict(arrowstyle="->", color=MUTED))
    save(fig, "s13_c_daily_intensity")


def s13_ticket_sizes():
    cats = N.CATEGORY_TICKET_LOGNORMAL
    means = {c: np.exp(mu + sig ** 2 / 2) for c, (mu, sig) in cats.items()}
    order = sorted(means, key=means.get)
    vals = [means[c] for c in order]
    fig, ax = plt.subplots(figsize=(10.5, 5.6))
    bars = ax.barh(range(len(order)), vals, color=BLUE, height=0.66)
    for b, v in zip(bars, vals):
        ax.text(v, b.get_y() + b.get_height() / 2, f" €{v:,.0f}", va="center", color=INK2, fontsize=10)
    ax.set_yticks(range(len(order))); ax.set_yticklabels(order)
    axstyle(ax, "Mean purchase ticket by category (lognormal draws)",
            xl="mean ticket €", grid="x")
    # The share-weighted mean, computed from the same two constants the bars come
    # from, rather than the hand-typed "€28" that used to sit here. That number was
    # attributed to Emiliozzi et al. §9; the paper has no §9 and no such figure.
    # Weighting is by the SELECTION probability, not the euro share — those differ.
    probs = dict(zip(N._CATEGORY_KEYS, N._CATEGORY_PROBS, strict=True))
    overall = sum(probs[c] * means[c] for c in means)
    ax.axvline(overall, color=ORANGE, lw=2, ls=(0, (4, 3)))
    ax.text(overall, len(order) - 0.4, f" overall ≈ €{overall:,.0f}", color=ORANGE,
            fontsize=10, weight="bold")
    save(fig, "s13_d_ticket_sizes")


# =========================================================================== #
# SECTION 6 — OUTPUTS & VALIDATION (slides 15-16)
# =========================================================================== #
def s15_outputs_schema():
    fig, ax = canvas(13, 6.8)
    title(ax, "What a run produces — three reconcilable views",
          "the engine writes nothing itself; callers persist these (deterministic for a fixed seed)")
    box(ax, 2, 40, 30, 48,
        "1 · Transaction ledger\n──────\none row per money movement\n\ndate\nkind  (salary/purchase/\n      bill/fee/loan)\nfrom · to\ncategory\namount_eur\nmacro_area",
        face="#e7f0fb", edge=BLUE, fs=10, align="left", va="top")
    box(ax, 35, 40, 30, 48,
        "2 · Accounts snapshot\n──────\none row per (consumer, account)\n\nmacro_area · income_source\nincome_level / quartile / quintile\nfinancial_status\ndebtor_subtype · debt_balance\naccount_type (current/\n   savings/pension)\nbalance · total_in / out",
        face="#eaf7f2", edge=AQUA, fs=10, align="left", va="top")
    box(ax, 68, 40, 30, 48,
        "3 · Per-day time series\n──────\none row per simulated day\n\ndaily_txn_count\ndaily_eur_total\ndebt_total / n per subtype\nmean balance by\n  income source\n  income level\n  debtor subtype",
        face="#f3eefb", edge=VIOLET, fs=10, align="left", va="top")
    box(ax, 14, 8, 72, 22,
        "The flat stream        →        the end-state portfolio + labels        →        the accounts moving over time\n\n"
        "Active path writes 2 CSVs (7-col ledger + 17-col accounts).  A parked engine writes a 21-column Parquet\nledger + run_meta.json (provenance: seed, dates, paper checksums).",
        face=PANEL, edge=BASE, fs=10)
    save(fig, "s15_a_outputs_schema")


def s15_txn_type_breakdown():
    m = ItalyModel(n_consumers=800, n_merchants_per_category=3, n_days=720, seed=42)
    m.run()
    import pandas as pd
    df = pd.DataFrame(m.transactions)
    kinds = ["salary", "purchase", "bill", "fee", "loan"]
    colors = {"salary": GREEN, "purchase": BLUE, "bill": BROWN, "fee": RED, "loan": VIOLET}
    cnt = df.groupby("kind").size().reindex(kinds).fillna(0)
    eur = df.groupby("kind")["amount_eur"].sum().reindex(kinds).fillna(0)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12.5, 5.2))
    a1.bar(kinds, cnt.values, color=[colors[k] for k in kinds], width=0.62)
    for i, v in enumerate(cnt.values):
        a1.text(i, v, f"{int(v):,}", ha="center", va="bottom", color=INK2, fontsize=10)
    axstyle(a1, "Transactions by type — count", yl="rows in the ledger")
    a2.bar(kinds, eur.values, color=[colors[k] for k in kinds], width=0.62)
    for i, v in enumerate(eur.values):
        a2.text(i, v, f"€{v/1000:,.0f}k", ha="center", va="bottom", color=INK2, fontsize=10)
    axstyle(a2, "Transactions by type — euro volume", yl="total € moved")
    fig.suptitle("The generated dataset, broken down by transaction type  (800 consumers · 720 days)",
                 x=0.01, ha="left", fontsize=15, weight="bold", color=INK)
    save(fig, "s15_b_txn_type_breakdown")


# =========================================================================== #
# Copy the already-generated figures/diagrams into one folder (slide-prefixed)
# =========================================================================== #
COPIES = {
    # section 4 — architecture
    "diagrams/d01_architecture": "s11_ref_architecture_uml",
    "diagrams/d03_money_flow": "s11_ref_money_flow",
    "diagrams/d02_day_step": "s11_ref_day_step_sequence",
    # section 5 — transaction logic
    "figures/f04_payday_spike": "s13_ref_payday_spike",
    "figures/f01_txn_volume": "s13_ref_txn_volume",
    "figures/f02_spend_mix_vs_paper": "s13_ref_spend_mix_vs_paper",
    "figures/f08_income_distribution": "s13_ref_income_distribution",
    # section 6 — outputs
    "figures/f03_spend_by_area": "s15_ref_spend_by_area",
    "figures/f06_income_composition": "s15_ref_income_composition",
    "figures/f07_balance_by_source": "s15_ref_balance_by_source",
    "figures/f05_behavioural_events": "s15_ref_fee_events",
    "figures/f09_debt_stock_by_subtype": "s15_ref_debt_stock",
    "figures/f10_balance_by_subtype": "s15_ref_balance_by_subtype",
    "figures/f11_debtor_composition": "s15_ref_debtor_composition",
    "figures/f12_still_in_debt": "s15_ref_still_in_debt",
    # section 6 — validation
    "figures/f13_clustering_pca": "s16_ref_clustering_pca",
    "figures/f14_cluster_recovery": "s16_ref_cluster_recovery",
    "figures/f15_prediction": "s16_ref_prediction",
}


def copy_existing():
    n = 0
    for src, dest in COPIES.items():
        for ext in ("png", "svg"):
            s = ROOT / f"{src}.{ext}"
            if s.exists():
                shutil.copy(s, OUT / f"{dest}.{ext}")
                n += 1
    print(f"  copied {n} existing files")


def main():
    print("NEW graphics:")
    s11_agents_and_objects()
    s11_time_calendar()
    s13_generation_flow()
    s13_transaction_types()
    s13_daily_intensity()
    s13_ticket_sizes()
    s15_outputs_schema()
    s15_txn_type_breakdown()
    print("Copying existing figures/diagrams:")
    copy_existing()
    print(f"Done: {OUT}")


if __name__ == "__main__":
    main()
