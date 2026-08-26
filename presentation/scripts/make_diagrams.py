#!/usr/bin/env python3
"""Render the five presentation diagrams as standalone PNG+SVG (matplotlib) and
also emit their Mermaid source (.mmd) — the source doubles as the live diagrams
embedded in status_deck.html (Artifacts render Mermaid natively).

Run:  uv run python presentation/make_diagrams.py

Three of the five (architecture, day-step sequence, money-flow) reproduce the
Mermaid diagrams already in docs/WALKTHROUGH.md; two (methodology pipeline,
provenance tiers) are new for this deck.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent.parent / "diagrams"
OUT.mkdir(parents=True, exist_ok=True)

BLUE, ORANGE, AQUA, YELLOW, MAGENTA, GREEN, VIOLET, RED = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948",
)
BROWN = "#8a5a2b"
INK, INK2, MUTED, BASE = "#0b0b0b", "#52514e", "#898781", "#c3c2b7"
PANEL = "#f4f6f9"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans", "Segoe UI", "Arial"],
    "figure.facecolor": "white", "savefig.facecolor": "white",
})


def save(fig, name):
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {name}.png / .svg")


def new_ax(w=13, h=7.5):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, text, face=PANEL, edge=BASE, tc=INK, fs=11, weight="normal",
        round_=0.02, align="center", lw=1.4):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle=f"round,pad=0.3,rounding_size={round_*100}",
        facecolor=face, edgecolor=edge, linewidth=lw, mutation_aspect=0.6))
    ha = {"center": "center", "left": "left"}[align]
    tx = x + w / 2 if align == "center" else x + 2.2
    ax.text(tx, y + h / 2, text, ha=ha, va="center", color=tc, fontsize=fs,
            weight=weight, linespacing=1.35)


def arrow(ax, p0, p1, color=INK2, lw=2.0, style="-|>", ls="-", rad=0.0):
    ax.add_patch(FancyArrowPatch(
        p0, p1, arrowstyle=style, mutation_scale=16, color=color, lw=lw,
        linestyle=ls, connectionstyle=f"arc3,rad={rad}", shrinkA=3, shrinkB=3))


def label(ax, x, y, t, color=INK2, fs=10, weight="normal", style="normal", ha="center"):
    ax.text(x, y, t, ha=ha, va="center", color=color, fontsize=fs, weight=weight, style=style)


def title(ax, t, sub=None):
    ax.text(0, 99, t, ha="left", va="top", fontsize=17, weight="bold", color=INK)
    if sub:
        ax.text(0, 92.5, sub, ha="left", va="top", fontsize=11.5, color=MUTED)


# --------------------------------------------------------------------------- #
# d01 — architecture / class diagram
# --------------------------------------------------------------------------- #
def d01_architecture():
    fig, ax = new_ax(13, 8)
    title(ax, "System architecture — agents, accounts, and the model",
          "src/synthitaly/model.py · one ItalyModel orchestrates three agent types over a daily clock")
    box(ax, 32, 78, 36, 12,
        "ItalyModel\n────────────\ntoday · transactions · datacollector\nstep() · run() · group_balances()\ndebt_by_subtype() · export_accounts()",
        face="#e7f0fb", edge=BLUE, tc=INK, fs=10.5, weight="bold", align="left")
    # agents row
    box(ax, 2, 52, 30, 16,
        "Consumer  (household)\n────────────\nmacro_area · income_source\nincome_level · has_debt\ndebtor_subtype · debt_balance\n────────────\nstep() · _pay_due_bills()\n_service_debt() · _can_afford()\n_maybe_buy_from_merchant()",
        face=PANEL, edge=AQUA, fs=9.5, align="left")
    box(ax, 36, 56, 26, 12,
        "IncomeSource  (employer)\n────────────\nmacro_area · served_consumers\n────────────\nstep()  → credits on payday",
        face=PANEL, edge=GREEN, fs=9.5, align="left")
    box(ax, 66, 56, 26, 12,
        "Merchant  (shop)\n────────────\ncategory · macro_area\n────────────\nstep()  (passive payee)",
        face=PANEL, edge=ORANGE, fs=9.5, align="left")
    # accounts
    box(ax, 4, 30, 26, 12,
        "AccountSet\n────────────\ncurrent · savings · pension",
        face=PANEL, edge=VIOLET, fs=10, align="left")
    box(ax, 36, 30, 26, 12,
        "BankAccount\n────────────\nbalance · entries\ndebit() · credit()",
        face=PANEL, edge=MUTED, fs=10, align="left")
    box(ax, 68, 30, 26, 12,
        "BankEntry\n────────────\ndate · direction\ncategory · amount_eur",
        face=PANEL, edge=MUTED, fs=10, align="left")
    # relations
    arrow(ax, (40, 78), (22, 68), color=AQUA)
    arrow(ax, (49, 78), (49, 68), color=GREEN)
    arrow(ax, (60, 78), (79, 68), color=ORANGE)
    label(ax, 30, 74, "1 → *", color=MUTED, fs=9)
    arrow(ax, (17, 52), (17, 42), color=VIOLET)
    label(ax, 21, 47, "1 has 1", color=MUTED, fs=9)
    arrow(ax, (30, 36), (36, 36), color=MUTED)
    label(ax, 33, 39, "3", color=MUTED, fs=9)
    arrow(ax, (62, 36), (68, 36), color=MUTED)
    label(ax, 65, 39, "1 → *", color=MUTED, fs=9)
    arrow(ax, (49, 56), (30, 40), color=GREEN, ls=(0, (3, 2)), style="->")
    label(ax, 6, 20, "IncomeSource ⋯credits on payday⋯▶ Consumer   ·   Consumer ⋯_pay()⋯▶ Merchant",
          color=MUTED, fs=9.5, ha="left")
    save(fig, "d01_architecture")


# --------------------------------------------------------------------------- #
# d02 — day-step sequence diagram
# --------------------------------------------------------------------------- #
def d02_day_step():
    fig, ax = new_ax(13, 8)
    title(ax, "One simulated day — ItalyModel.step()",
          "synchronous across days, randomised within a day (income paid before consumers act)")
    lanes = {
        "ItalyModel.step()": (10, BLUE),
        "IncomeSource": (36, GREEN),
        "Consumer": (62, AQUA),
        "DataCollector": (88, VIOLET),
    }
    for name, (x, c) in lanes.items():
        box(ax, x - 9, 84, 18, 6, name, face="white", edge=c, tc=c, fs=10, weight="bold")
        ax.plot([x, x], [10, 84], color=BASE, lw=1.2, ls=(0, (2, 3)), zorder=0)
    steps = [
        (78, "ItalyModel.step()", "IncomeSource", "do('step')", BLUE),
        (71, "IncomeSource", "Consumer", "credit income on the 27th  (+Dec tredicesima)", GREEN),
        (58, "ItalyModel.step()", "Consumer", "shuffle_do('step')", BLUE),
        (30, "Consumer", "DataCollector", "append to model.transactions", AQUA),
        (22, "ItalyModel.step()", "DataCollector", "collect(self)  → KPIs + grouped balances", VIOLET),
    ]
    for y, a, b, txt, c in steps:
        xa, xb = lanes[a][0], lanes[b][0]
        arrow(ax, (xa, y), (xb, y), color=c, lw=2.0)
        mid = (xa + xb) / 2
        label(ax, mid, y + 2.4, txt, color=INK2, fs=9.5)
    # consumer internal note
    box(ax, 46, 38, 34, 15,
        "per Consumer, in order:\n_month_close (1st)  →  _settle_overdue_bills\n→  _pay_due_bills  →  _service_debt (25th)\n→  _maybe_buy_from_merchant",
        face="#eaf7f2", edge=AQUA, fs=9.5, align="center")
    arrow(ax, (10, 14), (10, 10), color=BLUE, style="->")
    label(ax, 10, 7, "today += 1 day", color=MUTED, fs=9.5)
    save(fig, "d02_day_step")


# --------------------------------------------------------------------------- #
# d03 — money-flow
# --------------------------------------------------------------------------- #
def d03_money_flow():
    fig, ax = new_ax(13, 7)
    title(ax, "Money flow — what the bank sees",
          "salary = green · purchases = blue · bills/debt = brown · fees = red  (money is conserved system-wide)")
    box(ax, 2, 46, 20, 14, "IncomeSource ▲\n(per macro-area)", face="#e9f5ec", edge=GREEN, tc=INK, fs=10.5, weight="bold")
    box(ax, 38, 46, 20, 14, "Consumer ●\n(household)", face="#e7f0fb", edge=BLUE, tc=INK, fs=11, weight="bold")
    box(ax, 76, 78, 22, 12, "Merchants\n10 spending categories", face=PANEL, edge=BLUE, fs=10)
    box(ax, 76, 56, 22, 14, "Bills & debt\nutilities · rent · telecom\nmortgage · loan · debt-service", face=PANEL, edge=BROWN, fs=9.5)
    box(ax, 76, 36, 22, 12, "Fees → bank\noverdraft €30 · late 11%", face=PANEL, edge=RED, fs=10)
    box(ax, 38, 20, 20, 12, "credit_line\n(subsister lender)", face=PANEL, edge=VIOLET, fs=10)
    box(ax, 8, 14, 22, 12, "savings / pension\n(internal accounts)", face=PANEL, edge=MUTED, fs=10)

    arrow(ax, (22, 53), (38, 53), color=GREEN, lw=2.6); label(ax, 30, 56, "salary", color=GREEN, fs=10, weight="bold")
    arrow(ax, (58, 56), (76, 82), color=BLUE, lw=2.4, rad=-0.15); label(ax, 69, 74, "purchase", color=BLUE, fs=9.5)
    arrow(ax, (58, 53), (76, 62), color=BROWN, lw=2.4, rad=-0.05); label(ax, 68, 60, "bill / debt-service", color=BROWN, fs=9.5)
    arrow(ax, (58, 50), (76, 42), color=RED, lw=2.4, rad=0.12); label(ax, 68, 44, "overdraft / late", color=RED, fs=9.5)
    arrow(ax, (48, 20), (48, 46), color=VIOLET, lw=2.2, style="-|>"); label(ax, 58, 30, "borrow (subsister)", color=VIOLET, fs=9.5)
    arrow(ax, (38, 47), (24, 26), color=MUTED, lw=2.0, ls=(0, (3, 2)), rad=0.1); label(ax, 20, 36, "month-end sweep\n(internal)", color=MUTED, fs=9)
    save(fig, "d03_money_flow")


# --------------------------------------------------------------------------- #
# d04 — methodology pipeline (NEW)
# --------------------------------------------------------------------------- #
def d04_pipeline():
    fig, ax = new_ax(14, 7.2)
    title(ax, "Methodology pipeline — from papers to analysis",
          "every empirical number is traceable; nothing is written to disk until a caller asks")
    stages = [
        ("1 · Papers", "4 Italian sources\n+ 3 behavioural\n+ 1 method paper", "#eef2f7", MUTED),
        ("2 · numbers.py", "every constant,\npaper-cited;\nsamplers + calendar", "#e7f0fb", BLUE),
        ("3 · Initialise", "build merchants,\nincome sources,\nconsumers; assign\nbands · debt · savings", "#eaf7f2", AQUA),
        ("4 · Simulate", "daily loop ×N:\nincome → bills →\ndebt → purchases →\nmonth-end sweep", "#fdf3e8", ORANGE),
        ("5 · Outputs", "transaction ledger ·\naccounts snapshot ·\nper-day time series", "#f3eefb", VIOLET),
        ("6 · Analysis", "clustering &\nprediction ·\nSolara dashboard", "#fdeef0", RED),
    ]
    n = len(stages)
    w, gap = 14.0, 2.0
    x0 = 1
    for i, (head, body, face, edge) in enumerate(stages):
        x = x0 + i * (w + gap)
        box(ax, x, 40, w, 34, f"{head}\n────────\n{body}", face=face, edge=edge, tc=INK, fs=9.7, weight="bold")
        if i < n - 1:
            arrow(ax, (x + w, 57), (x + w + gap, 57), color=MUTED, lw=2.2)
    # provenance ribbon underneath
    label(ax, 8, 30, "reproducible: a single seeded RNG → byte-identical runs", color=MUTED, fs=10, ha="left", style="italic")
    box(ax, 1, 8, 97, 15,
        "Provenance tiers carried through every stage:   "
        "① Italian calibrated   ·   ② behavioural (shape grounded, magnitude swept)   ·   ③ structural modelling choice (flagged, swept)",
        face="#f7f7f4", edge=BASE, fs=10.5, align="center")
    save(fig, "d04_methodology_pipeline")


# --------------------------------------------------------------------------- #
# d05 — provenance tiers (NEW)
# --------------------------------------------------------------------------- #
def d05_provenance():
    fig, ax = new_ax(13, 7.6)
    title(ax, "The calibrated-vs-modelled bright line",
          "the thesis never hides a choice as a fact — every number carries its tier")
    tiers = [
        (66, "#e9f5ec", GREEN, "TIER 1 — Italian, calibrated",
         "Taken directly from a public Italian source, section-cited.\n"
         "SHIW 2022 · Payment Behaviour Survey 2023-24 · Emiliozzi et al. (2023) card data · wire-transfer / structural-inequalities",
         "income by source · debt participation & service · saver rates · bills · spending categories · calendar · payday · macro-areas"),
        (38, "#fdf3e8", ORANGE, "TIER 2 — Behavioural: shape grounded, magnitude swept ⚠",
         "The behaviour's existence is paper-grounded; the euro/percentage size is a modelling choice and is swept.\n"
         "Olafsson & Pagel 2018 · Stango & Zinman 2014 · Dahan & Nisan 2020 · Campbell 2006 (conceptual)",
         "payday spike ×1.5 · overdraft €30 · late fee 11% · chronic-debtor tilt toward the SHIW-vulnerable"),
        (10, "#fdeef0", RED, "TIER 3 — Structural modelling choice ⚠",
         "No paper at all — flagged at point of use and swept in scripts/sweep_behavioural.py.",
         "debt as a stock (SHIW gives only the flow) · the three debtor archetypes · per-source income dispersion"),
    ]
    for y, face, edge, head, desc, items in tiers:
        box(ax, 1, y, 97, 24, "", face=face, edge=edge, lw=1.8)
        ax.text(4, y + 20, head, ha="left", va="top", fontsize=12.5, weight="bold", color=INK)
        ax.text(4, y + 13.5, desc, ha="left", va="top", fontsize=9.8, color=INK2, linespacing=1.3)
        ax.text(4, y + 4.5, "→ " + items, ha="left", va="top", fontsize=9.3, color=edge, weight="bold",
                linespacing=1.3)
    save(fig, "d05_provenance_tiers")


# --------------------------------------------------------------------------- #
# d06 — the composite ODD figure (thesis figure for docs/ODD.md)
# --------------------------------------------------------------------------- #
def d06_odd_overview():
    """One full-page schematic of the whole ODD protocol, in ODD order.

    Panel A mirrors ODD 1.2 (entities, state variables, scales), panel B mirrors
    1.3 (process overview and scheduling) plus the month calendar, and panel C
    mirrors 3.3 (submodels) laid over the 2 Interaction payment topology. The
    warning glyph marks a parameter that ODD.md flags as a modelling choice
    rather than a calibrated value.
    """
    H_IN = 13.5
    fig, ax = new_ax(17.5, H_IN)
    title(ax, "ODD protocol — synthitaly at a glance",
          "Grimm et al. (2010).  A · entities & state (ODD 1.2)   B · process overview & scheduling (1.3)   "
          "C · submodels & money flows (3.3)   ⚠ = modelling choice, not a calibrated value")

    # Axes-units per typographic point, so a box can be sized from its line count.
    # Measured off the real axes box, not the figure — the default subplot margins
    # leave the axes at ~77% of figure height, and assuming otherwise under-sizes
    # every box (the tallest one then clips its last line).
    upl = 100.0 / (ax.get_position().height * H_IN * 72.0)

    def stack(x, w, top, head, body, edge, face=PANEL, fs=8.2, hfs=9.2, pad=3.4, gap=1.4):
        """Draw a head+body box whose height is computed from the text, top-aligned
        at `top`. Returns the y of the next free slot below it."""
        n = body.count("\n") + 1
        h = pad + (hfs * 1.42 if head else 0) * upl + n * fs * 1.42 * upl
        box(ax, x, top - h, w, h, "", face=face, edge=edge, lw=1.4)
        y = top - pad / 2
        if head:
            ax.text(x + 1.7, y, head, ha="left", va="top", fontsize=hfs, weight="bold", color=edge)
            y -= hfs * 1.42 * upl
        ax.text(x + 1.7, y, body, ha="left", va="top", fontsize=fs, color=INK2, linespacing=1.42)
        return top - h - gap

    # ---- panel frames ----------------------------------------------------- #
    for x, w, head, edge in ((0.5, 30.5, "A · Entities, state variables, scales", AQUA),
                             (32.5, 32.0, "B · Process overview & scheduling", BLUE),
                             (66.0, 33.5, "C · Submodels & money flows", BROWN)):
        box(ax, x, 2, w, 86, "", face="white", edge=edge, lw=1.8)
        ax.text(x + 1.8, 86.6, head, ha="left", va="top", fontsize=11.5, weight="bold", color=edge)

    # ---- A: entities ------------------------------------------------------ #
    cur = stack(2, 27.5, 83, "Consumer  (household)",
                "the only active decision-maker\n"
                "macro_area · monthly_income\n"
                "income_source ∈ {payroll, self_employed,\n"
                "   pension, transfers, unemployed}\n"
                "income_level · quartile · quintile\n"
                "debt:  has_debt · debtor_subtype\n"
                "   ∈ {climber, chronic, subsister}\n"
                "   debt_balance · debt_service_ratio\n"
                "   is_financially_vulnerable · overdraft\n"
                "saving:  is_saver · is_pension_saver\n"
                "3 × BankAccount · bills_subscribed\n"
                "_overdue_bills queue",
                AQUA, face="#eaf7f2")
    cur = stack(2, 27.5, cur, "IncomeSource  (the employer)",
                "one per macro-area · pays on payday\n"
                "its account runs negative by the total paid",
                GREEN, face="#e9f5ec")
    cur = stack(2, 27.5, cur, "Merchant  (passive payee)",
                "one (category, area) · receive-only account",
                ORANGE, face="#fdf3e8")
    cur = stack(2, 27.5, cur, "Stand-in payees",
                "bills · debt_service · overdraft_fee ·\n"
                "credit_line — so every flow has a counterparty",
                VIOLET)
    cur = stack(2, 27.5, cur, "ItalyModel  (collective / environment)",
                "today · population · networkx graph ·\n"
                "Mesa DataCollector",
                BLUE, face="#e7f0fb")
    stack(2, 27.5, cur, "Scales",
          "1 step = 1 day · default 30 d, run to ~2 y\n"
          "for debt dynamics\n"
          "3 macro-areas, ISTAT weights .46/.20/.34;\n"
          "no distance or coordinates, but area sets\n"
          "the income level (South ×0.554)\n"
          "≈150 consumers · 10 categories × 3 areas\n"
          "× k merchants · money in euros",
          MUTED, face="#f7f6f2")

    # ---- B: the daily loop ------------------------------------------------ #
    cur = stack(34, 29, 83, "1 · IncomeSource agents act",
                "on the 27th, credit every served consumer\n"
                "+ December tredicesima (payroll / pension)\n"
                "one income stream per consumer",
                GREEN, face="#e9f5ec", gap=3.4)
    arrow(ax, (48.5, cur + 4.0), (48.5, cur + 0.6), color=INK2, lw=1.8)
    cur = stack(34, 29, cur, "2 · Consumer agents act — shuffle_do",
                "randomised order within the day:\n"
                "   a. pay bills due → defer if unaffordable\n"
                "   b. settle overdue bills (+ penalty)\n"
                "   c. discretionary purchase × daily intensity\n"
                "   d. service debt (the 25th), by archetype\n"
                "   e. month-end sweep of positive residual",
                AQUA, face="#eaf7f2", gap=3.4)
    arrow(ax, (48.5, cur + 4.0), (48.5, cur + 0.6), color=INK2, lw=1.8)
    cur = stack(34, 29, cur, "3 · Model records & advances",
                "KPIs + grouped balance snapshot →\n"
                "DataCollector.collect() → today += 1 day",
                VIOLET, face="#f0edf9", gap=2.0)
    label(ax, 48.5, cur - 1.0, "↺  and the next day begins", color=MUTED, fs=8.6, style="italic")
    cur -= 4.0

    cur = stack(34, 29, cur, "",
                "Synchronous across days, randomised within a day. Income\n"
                "is paid before consumers act, so a consumer paid today\n"
                "can spend today.",
                BASE, face="white", fs=8.0, gap=2.2)

    # the month calendar strip
    ax.text(35.7, cur, "The month, as the agents experience it", ha="left", va="top",
            fontsize=9.2, weight="bold", color=INK)
    cur -= 3.8
    box(ax, 34, cur - 11, 29, 11, "", face=PANEL, edge=BASE, lw=1.4)
    mid = cur - 5.5
    ax.plot([36.5, 60.5], [mid, mid], color=BASE, lw=1.6, zorder=1)
    marks = [(36.5, "1", "sweep", MUTED), (40.5, "5", "", BROWN), (44.5, "10", "bills", BROWN),
             (48.5, "15", "", BROWN), (52.5, "20", "", BROWN), (56.5, "25", "debt", RED),
             (60.5, "27", "salary", GREEN)]
    for x, day, cap, c in marks:
        ax.plot([x], [mid], marker="o", ms=6.0, color=c, zorder=3)
        ax.text(x, mid - 2.7, day, ha="center", va="center", fontsize=8.2, color=INK, weight="bold")
        if cap:
            ax.text(x, mid + 2.9, cap, ha="center", va="center", fontsize=8.0, color=c, weight="bold")
    cur -= 12.6

    stack(34, 29, cur, "",
          "Initialization (3.1) is deterministic given the seed. Input\n"
          "data (3.2): none at run time — every constant lives in\n"
          "numbers.py; the only input is the calendar.",
          BASE, face="white", fs=8.0)

    # ---- C: submodels ----------------------------------------------------- #
    subs = [
        ("Income payment", GREEN,
         "IncomeSource.step, the 27th\nSHIW 2022 · Semeraro et al. 2020 (calendar)"),
        ("Income draw: source × area", GREEN,
         "lognormal, both multipliers mean-preserving\n"
         "SHIW §2B (source) · Semeraro p.5/p.27 (area) · σ ⚠"),
        ("Discretionary purchase", BLUE,
         "p × daily_intensity, lognormal ticket\nEmiliozzi et al. 2023 · payday spike ⚠"),
        ("Bill payment & late fees", BROWN,
         "defer if unaffordable · 11% penalty · write off at 90 d\nPayment Behaviour Survey §4 · Dahan & Nisan 2020 ⚠"),
        ("Overdraft fee", RED,
         "flat €30 the moment a payment crosses zero\nStango & Zinman 2014 · magnitude ⚠"),
        ("Debt service", RED,
         "day 25 · climber clears · chronic interest-only ·\nsubsister token   SHIW 2022 §3 · stock & archetypes ⚠"),
        ("Borrowing", VIOLET,
         "subsister draws on the per-area credit_line ⚠"),
        ("Month-close sweep", MUTED,
         "saver moves the positive residual to savings / pension\nSHIW 2022 §2F · the sweep itself is emergent"),
    ]
    cur = 83
    for head, c, body in subs:
        cur = stack(67.5, 30.5, cur, head, body, c, face="white",
                    fs=7.2, hfs=8.2, pad=2.5, gap=1.0)

    stack(67.5, 30.5, cur - 1.2, "Design concepts (ODD §2)",
          "Emergence — savings, fee incidence and the divergence of\n"
          "debtor outcomes emerge from per-agent rules, not imposed.\n"
          "Adaptation — reactive only: defer a bill, or borrow.\n"
          "Objectives / learning / prediction — none.\n"
          "Sensing — own balance, overdraft floor, and the calendar.\n"
          "Interaction — mediated entirely by payments.\n"
          "Stochasticity — one seeded NumPy Generator; a fixed seed\n"
          "reproduces a run byte-for-byte.",
          BASE, face="#f7f6f2", fs=7.2, hfs=8.2, pad=3.0)

    save(fig, "d06_odd_overview")


# --------------------------------------------------------------------------- #
# Mermaid source (verbatim from docs/WALKTHROUGH.md for d01-d03; new for d04-d05)
# --------------------------------------------------------------------------- #
MERMAID = {
    "d01_architecture": """classDiagram
    class ItalyModel {
        +date today
        +list~dict~ transactions
        +dict merchants
        +dict income_sources
        +list~Consumer~ consumers
        +DataCollector datacollector
        +step()
        +run()
        +group_balances()
        +debt_by_subtype()
    }
    class Consumer {
        +str macro_area
        +float monthly_income
        +str income_source
        +str income_level
        +bool has_debt
        +str debtor_subtype
        +float debt_balance
        +step()
        +_pay_due_bills()
        +_service_debt()
        +_maybe_buy_from_merchant()
        +_can_afford()
    }
    class Merchant {
        +str category
        +str macro_area
        +step()
    }
    class IncomeSource {
        +str macro_area
        +list served_consumers
        +step()
    }
    class AccountSet {
        +BankAccount current
        +BankAccount savings
        +BankAccount pension
    }
    class BankAccount {
        +float balance
        +list~BankEntry~ entries
        +debit()
        +credit()
    }
    class BankEntry {
        +str date
        +str direction
        +str category
        +float amount_eur
    }
    ItalyModel "1" o-- "*" Consumer
    ItalyModel "1" o-- "*" Merchant
    ItalyModel "1" o-- "*" IncomeSource
    Consumer "1" *-- "1" AccountSet
    AccountSet "1" *-- "3" BankAccount
    Merchant "1" *-- "1" BankAccount
    IncomeSource "1" *-- "1" BankAccount
    BankAccount "1" *-- "*" BankEntry
    IncomeSource ..> Consumer : credits on payday
    Consumer ..> Merchant : _pay()
""",
    "d02_day_step": """sequenceDiagram
    participant M as ItalyModel.step()
    participant I as IncomeSource
    participant C as Consumer
    participant D as DataCollector
    M->>I: do("step")
    Note over I: only on the 27th (payday)
    I->>C: credit monthly income (+Dec tredicesima)
    M->>C: shuffle_do("step")
    Note over C: _month_close (1st) -> _settle_overdue -><br/>_pay_due_bills -> _service_debt (25th) -><br/>_maybe_buy_from_merchant
    C-->>M: append to model.transactions
    M->>M: KPIs + group_balances()
    M->>D: collect(self)
    M->>M: today += 1 day
""",
    "d03_money_flow": """flowchart LR
    I["IncomeSource &#9650;<br/>(per area)"] -- salary --> C["Consumer &#9679;"]
    C -- purchase --> MCh["Merchants<br/>(10 categories)"]
    C -- bill / debt-service --> B["Bills & debt<br/>(utilities/rent/telecom/<br/>mortgage/loan/debt)"]
    C -- "overdraft &euro;30 / late 11%" --> F["Fees &#8594; bank"]
    L["credit_line"] -- borrow (subsister) --> C
    C -. "month-end sweep (internal)" .-> S["savings / pension"]
""",
    "d04_methodology_pipeline": """flowchart LR
    P["1 · Papers<br/>4 Italian + 3 behavioural<br/>+ 1 method"] --> N["2 · numbers.py<br/>every constant,<br/>paper-cited"]
    N --> INIT["3 · Initialise<br/>build agents;<br/>assign bands/debt/savings"]
    INIT --> SIM["4 · Simulate<br/>daily loop:<br/>income&#8594;bills&#8594;debt&#8594;<br/>purchases&#8594;sweep"]
    SIM --> OUT["5 · Outputs<br/>ledger · accounts ·<br/>time series"]
    OUT --> AN["6 · Analysis<br/>clustering · prediction ·<br/>Solara dashboard"]
""",
    "d05_provenance_tiers": """flowchart TB
    subgraph T1["TIER 1 — Italian, calibrated"]
      A["SHIW 2022 · Payment Behaviour Survey · Emiliozzi et al. (2023) · wire-transfer"]
    end
    subgraph T2["TIER 2 — behavioural: shape grounded, magnitude swept"]
      B["Olafsson & Pagel · Stango & Zinman · Dahan & Nisan · Campbell"]
    end
    subgraph T3["TIER 3 — structural modelling choice (flagged, swept)"]
      D["debt-as-stock · debtor archetypes · income dispersion"]
    end
    T1 --> T2 --> T3
""",
}


def write_mermaid():
    for name, src in MERMAID.items():
        (OUT / f"{name}.mmd").write_text(src, encoding="utf-8")
    print(f"  wrote {len(MERMAID)} .mmd sources")


def main():
    d01_architecture()
    d02_day_step()
    d03_money_flow()
    d04_pipeline()
    d05_provenance()
    d06_odd_overview()
    write_mermaid()
    print(f"Done: diagrams in {OUT}")


if __name__ == "__main__":
    main()
