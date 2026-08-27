"""make_reference_card.py — build the printable model reference card (PDF).

A self-contained, look-it-up-in-ten-seconds handout for the colloquium: every
consumer type and sub-type, the general calibration, the behavioural-economics
layer and how each effect is mapped into code, and the script map (what controls
what). Nothing here is invented — every figure traces to ``src/synthitaly/numbers.py``
(and through it to a paper) or to observed output of the reference run.

The "observed" column figures come from the reference run 800 consumers ×
720 days, seed 42 (the same Run B that produced presentation/figures/f09-f12).
They are recomputed live unless ``--no-run`` is passed, in which case the cached
values below are used.

Run:  uv run python presentation/scripts/make_reference_card.py
Out:  presentation/MODEL_REFERENCE_CARD.pdf
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "presentation" / "MODEL_REFERENCE_CARD.pdf"

# ---------------------------------------------------------------------------
# Palette & type
# ---------------------------------------------------------------------------

INK = colors.HexColor("#16202B")
INK2 = colors.HexColor("#4A5866")
MUTED = colors.HexColor("#77848F")
RULE = colors.HexColor("#D7DEE5")
BAND = colors.HexColor("#F1F5F9")
ACCENT = colors.HexColor("#1F5C8B")   # calibrated / structural blue
GREEN = colors.HexColor("#2E7D5B")    # Italian, calibrated
ORANGE = colors.HexColor("#B4531F")   # modelling choice
PURPLE = colors.HexColor("#6A4C93")   # behavioural layer
PAPER = colors.HexColor("#FFFFFF")

PAGE_W, PAGE_H = A4
MARGIN = 15 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


def _p(name: str, size: float, leading: float, colour=INK, **kw) -> ParagraphStyle:
    return ParagraphStyle(
        name, fontName=kw.pop("font", "Helvetica"), fontSize=size, leading=leading,
        textColor=colour, alignment=kw.pop("align", TA_LEFT), **kw,
    )


S = {
    "title":   _p("title", 21, 24, INK, font="Helvetica-Bold"),
    "subtitle": _p("subtitle", 10, 13.5, INK2),
    "h1":      _p("h1", 13.5, 16, PAPER, font="Helvetica-Bold"),
    "h2":      _p("h2", 10.5, 13, ACCENT, font="Helvetica-Bold", spaceBefore=6, spaceAfter=2),
    "body":    _p("body", 8.6, 11.6, INK2, spaceAfter=3),
    "lead":    _p("lead", 9.4, 13, INK, spaceAfter=4),
    "th":      _p("th", 7.6, 9.6, PAPER, font="Helvetica-Bold"),
    "td":      _p("td", 7.6, 9.7, INK2),
    "tdb":     _p("tdb", 7.6, 9.7, INK, font="Helvetica-Bold"),
    "tdm":     _p("tdm", 7.0, 9.2, MUTED, font="Courier"),
    "note":    _p("note", 7.4, 9.8, MUTED, spaceAfter=2),
    "kicker":  _p("kicker", 7.6, 10, MUTED, font="Helvetica-Bold"),
}


def para(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, S[style])


def mono(text: str) -> str:
    """Inline monospace + accent for a code identifier."""
    return f'<font face="Courier" color="#1F5C8B">{text}</font>'


def tag(kind: str) -> str:
    """Provenance badge: ITA (Italian, calibrated) / BEH / MOD."""
    c = {"ITA": "#2E7D5B", "BEH": "#6A4C93", "MOD": "#B4531F"}[kind]
    return f'<font color="{c}" size="6.6"><b>{kind}</b></font>'


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def section(title: str, kicker: str = "") -> Table:
    """A full-width dark section bar."""
    right = Paragraph(f'<font color="#C8D6E2">{kicker}</font>', S["th"]) if kicker else ""
    t = Table([[Paragraph(title, S["h1"]), right]],
              colWidths=[CONTENT_W * 0.68, CONTENT_W * 0.32])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (0, 0), 8), ("RIGHTPADDING", (1, 0), (1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def table(rows: list[list], widths: list[float], header: bool = True,
          head_colour=ACCENT, zebra: bool = True, extra: list | None = None) -> Table:
    """Standard data table: coloured header row, hairline rules, zebra bands."""
    data = []
    for r, row in enumerate(rows):
        out = []
        for cell in row:
            if isinstance(cell, Paragraph):
                out.append(cell)
            else:
                st = "th" if (header and r == 0) else "td"
                out.append(Paragraph(str(cell), S[st]))
        data.append(out)
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.4), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.4),
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, RULE),
        ("BOX", (0, 0), (-1, -1), 0.5, RULE),
    ]
    if header:
        style += [("BACKGROUND", (0, 0), (-1, 0), head_colour),
                  ("LINEBELOW", (0, 0), (-1, 0), 0.5, head_colour)]
    if zebra:
        start = 1 if header else 0
        for i in range(start, len(data)):
            if (i - start) % 2 == 1:
                style.append(("BACKGROUND", (0, i), (-1, i), BAND))
    if extra:
        style += extra
    t.setStyle(TableStyle(style))
    return t


def callout(title: str, body: str, colour=ACCENT) -> Table:
    """A tinted box with a coloured left edge — used for the 'top 3 scripts'."""
    inner = [[Paragraph(title, _p("cot", 9, 11.5, colour, font="Helvetica-Bold"))],
             [Paragraph(body, S["body"])]]
    t = Table(inner, colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BAND),
        ("LINEBEFORE", (0, 0), (0, -1), 2.4, colour),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 5), ("BOTTOMPADDING", (0, 0), (-1, 0), 1),
        ("TOPPADDING", (0, 1), (-1, 1), 0), ("BOTTOMPADDING", (0, 1), (-1, 1), 5),
    ]))
    return t


def gap(h: float = 5) -> Spacer:
    return Spacer(1, h)


# ---------------------------------------------------------------------------
# Observed figures from the reference run (800 consumers × 720 days, seed 42) —
# the repository's pinned configuration, the one every reported statistic and
# every figure now uses. This block is only the --no-run fallback; the numbers in
# the PDF are recomputed live by default.
# ---------------------------------------------------------------------------

CACHED = {
    "n_txns": 377227,
    "by_source": {
        "payroll": (435, 1919), "self_employed": (151, 2772), "pension": (156, 1428),
        "transfers": (24, 951), "unemployed": (34, 624),
    },
    "mean_income": 1900, "median_income": 1575,
    "by_level": {"low": 194, "middle": 550, "high": 56},
    "by_area": {"NORTH": 356, "CENTRE": 159, "SOUTH": 285},
    "n_debtors": 167, "n_vulnerable": 33, "n_savers": 442, "n_pension_savers": 228,
    "by_subtype": {
        "climber":   {"n": 86, "still": 19, "dsr": 0.261, "bal": 11008, "debt": 1036, "inc": 2511, "vuln": 7},
        "chronic":   {"n": 44, "still": 44, "dsr": 0.448, "bal": 4376,  "debt": 6299, "inc": 1613, "vuln": 17},
        "subsister": {"n": 37, "still": 37, "dsr": 0.303, "bal": 38,    "debt": 8631, "inc": 2303, "vuln": 9},
    },
    "overdraft_events": 284, "overdraft_eur": 8520,
    "late_events": 6608, "late_eur": 137948,
    "credit_draws": 528, "credit_draw_eur": 36670,
    "fees_by_level": {"low": 4785, "middle": 2107, "high": 0},
    "fees_by_subtype": {"no_debt": 5920, "chronic": 584, "climber": 388, "subsister": 0},
    "mean_ticket": 36.73,
}


def observed(live: bool) -> dict:
    """Recompute the headline run statistics, or fall back to the cached ones."""
    if not live:
        return CACHED
    sys.path.insert(0, str(ROOT / "src"))
    import numpy as np

    from synthitaly.model import ItalyModel

    m = ItalyModel(n_consumers=800, n_merchants_per_category=3, n_days=720, seed=42)
    m.run()
    cons = m.consumers
    o: dict = {"n_txns": len(m.transactions)}

    src = defaultdict(list)
    for c in cons:
        src[c.income_source].append(c.monthly_income)
    o["by_source"] = {k: (len(v), round(float(np.mean(v)))) for k, v in src.items()}
    o["mean_income"] = round(float(np.mean([c.monthly_income for c in cons])))
    o["median_income"] = round(float(np.median([c.monthly_income for c in cons])))
    o["by_level"] = dict(Counter(c.income_level for c in cons))
    o["by_area"] = dict(Counter(c.macro_area for c in cons))

    debtors = [c for c in cons if c.debtor_subtype is not None]
    o["n_debtors"] = len(debtors)
    o["n_vulnerable"] = sum(1 for c in debtors if c.is_financially_vulnerable)
    o["n_savers"] = sum(1 for c in cons if c.is_saver)
    o["n_pension_savers"] = sum(1 for c in cons if c.is_pension_saver)
    sub = defaultdict(list)
    for c in debtors:
        sub[c.debtor_subtype].append(c)
    o["by_subtype"] = {
        k: {
            "n": len(v),
            "still": sum(1 for c in v if c.has_debt),
            "vuln": sum(1 for c in v if c.is_financially_vulnerable),
            "dsr": round(float(np.mean([c.debt_service_ratio for c in v])), 3),
            "bal": round(float(np.mean([c.accounts.current.balance for c in v]))),
            "debt": round(float(np.mean([c.debt_balance for c in v]))),
            "inc": round(float(np.mean([c.monthly_income for c in v]))),
        }
        for k, v in sub.items()
    }

    cats = Counter(t["category"] for t in m.transactions)
    eur: dict[str, float] = defaultdict(float)
    for t in m.transactions:
        eur[t["category"]] += t["amount_eur"]
    o["overdraft_events"] = cats.get("overdraft_fee", 0)
    o["overdraft_eur"] = round(eur.get("overdraft_fee", 0.0))
    o["late_events"] = cats.get("late_payment_fee", 0)
    o["late_eur"] = round(eur.get("late_payment_fee", 0.0))
    o["credit_draws"] = cats.get("credit_draw", 0)
    o["credit_draw_eur"] = round(eur.get("credit_draw", 0.0))

    ids = {str(c.unique_id): c for c in cons}
    lvl, st = Counter(), Counter()
    for t in m.transactions:
        if t["category"] in ("overdraft_fee", "late_payment_fee"):
            c = ids.get(t["from"])
            if c is not None:
                lvl[c.income_level] += 1
                st[c.debtor_subtype or "no_debt"] += 1
    o["fees_by_level"] = dict(lvl)
    o["fees_by_subtype"] = dict(st)
    pur = [t for t in m.transactions if t["kind"] == "purchase"]
    o["mean_ticket"] = round(sum(t["amount_eur"] for t in pur) / max(len(pur), 1), 2)
    return o


# ---------------------------------------------------------------------------
# Page furniture
# ---------------------------------------------------------------------------


def furniture(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 10 * mm,
                      "SynthItaly — model reference card · Frederick Erleigh · Master's thesis colloquium")
    canvas.drawRightString(PAGE_W - MARGIN, 10 * mm, f"{canvas.getPageNumber()}")
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN, 12.5 * mm, PAGE_W - MARGIN, 12.5 * mm)
    canvas.restoreState()


# ---------------------------------------------------------------------------
# The document
# ---------------------------------------------------------------------------


def build(o: dict) -> None:
    doc = BaseDocTemplate(
        str(OUT), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=13 * mm, bottomMargin=16 * mm,
        title="SynthItaly — model reference card",
        author="Frederick Erleigh",
        subject="Consumer types, sub-types, calibration, behavioural mapping, script map",
    )
    frame = Frame(MARGIN, 16 * mm, CONTENT_W, PAGE_H - 13 * mm - 16 * mm, id="body",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="std", frames=[frame], onPage=furniture)])

    f = []
    W = CONTENT_W

    # =====================================================================
    # PAGE 1 — the whole model on one page
    # =====================================================================
    f.append(para("SynthItaly — model reference card", "title"))
    f.append(para(
        "A bank-eye agent-based simulation of Italian consumer accounts. "
        "Everything below is either traceable to a named paper and section, or explicitly "
        "flagged as a modelling choice. Reference run for all observed figures: "
        "<b>800 consumers × 720 days, seed 42</b> "
        f"(≈{o['n_txns']:,} transactions).", "subtitle"))
    f.append(gap(8))

    f.append(section("1 · The whole model in one box", "read this first"))
    f.append(gap(4))
    f.append(table([
        ["Element", "Count (defaults)", "What it does"],
        [para("<b>Consumer</b>", "tdb"), "800 (slider)",
         "A household — the <b>only active decision-maker</b>. Receives income, pays bills and debt, "
         "buys from merchants, sweeps any monthly surplus to savings/pension."],
        [para("<b>Merchant</b>", "tdb"), "10 categories × 3 areas × 3 = 90",
         "A shop in one (category, area). Passive — only receives money."],
        [para("<b>IncomeSource</b>", "tdb"), "3 (one per macro-area)",
         "The 'employer'. On payday credits every consumer it serves; its own account runs negative "
         "by the total paid out."],
        [para("<b>Stand-in payees</b>", "tdb"), "24 (per bill × area + 3 special × area)",
         "Counterparties so bills, " + mono("debt_service") + ", " + mono("overdraft_fee") +
         " and the " + mono("credit_line") + " lender have somewhere to send/draw money."],
        [para("<b>BankAccount</b>", "tdb"), "3 per consumer",
         mono("current") + " (everyday) · " + mono("savings") + " · " + mono("pension") +
         ". Merchants and income sources hold one each."],
    ], [W * 0.19, W * 0.24, W * 0.57]))
    f.append(gap(7))

    f.append(para("One simulated day — " + mono("ItalyModel.step()"), "h2"))
    f.append(table([
        ["1 · Income", "2 · Month close", "3 · Overdue", "4 · Bills", "5 · Debt", "6 · Purchases"],
        [
            "Every " + mono("IncomeSource") + " runs first, so a consumer paid today can spend today. "
            "Salary on the <b>27th</b>; December pays double for payroll & pensions.",
            "On the 1st: " + mono("residual = income − bills − debt − discretionary") +
            ". Savers sweep a positive residual into savings/pension (internal paired transfer).",
            "Retry any bill carried over from an earlier month; settle it with the <b>11 % late fee</b> "
            "once cash allows. Written off after 90 days.",
            "Bills due today are paid. If unaffordable: subsisters borrow, everyone else defers "
            "(the bill becomes overdue).",
            "On the <b>25th</b>: interest accrues on the principal, then the archetype's repayment is made. "
            "See page 4.",
            "With probability " + mono("0.6 × daily_intensity(d)") + " pick a category, draw a ticket, "
            "pay a merchant in the same macro-area.",
        ],
    ], [W / 6] * 6, head_colour=INK2))
    f.append(gap(7))

    f.append(para("Provenance tiers — the bright line of the thesis", "h2"))
    f.append(table([
        ["Tier", "Meaning", "Examples", "How it is defended"],
        [para(tag("ITA") + " <b>Italian, calibrated</b>", "td"),
         "Taken directly from one of the four Italian sources, paper + section named.",
         "Macro-area weights · category shares · bill amounts · debt participation by quartile · saving by quintile.",
         "Cited at point of use in " + mono("numbers.py") + " and in the data dictionary."],
        [para(tag("BEH") + " <b>Behavioural: shape grounded, magnitude modelled</b>", "td"),
         "The literature says the mechanism exists; its euro/percentage size is our choice.",
         "Payday spike ×1.5 · overdraft €30 · late fee 11 %.",
         "<b>Swept</b> in " + mono("scripts/sweep_behavioural.py") + " so no conclusion rests on a foreign number."],
        [para(tag("MOD") + " <b>Structural modelling choice</b>", "td"),
         "No paper at all — a construction needed to make the model run.",
         "Debt as a <i>stock</i> · the three debtor archetypes · per-source income dispersion · income-source headcounts.",
         "Flagged in code and docs; swept where it matters; direction grounded where possible."],
    ], [W * 0.20, W * 0.24, W * 0.30, W * 0.26], head_colour=INK2))
    f.append(gap(7))

    f.append(para("The reference run at a glance", "h2"))
    lv, ar, bs = o["by_level"], o["by_area"], o["by_subtype"]
    f.append(table([
        ["Population", "Income", "Debt", "Savings", "Behavioural events"],
        [
            f"{ar.get('NORTH',0)} North · {ar.get('CENTRE',0)} Centre · {ar.get('SOUTH',0)} South<br/>"
            f"{lv.get('low',0)} low · {lv.get('middle',0)} middle · {lv.get('high',0)} high income",
            f"mean €{o['mean_income']:,}/mo<br/>median €{o['median_income']:,}/mo<br/>"
            f"mean ticket €{o['mean_ticket']}",
            f"{o['n_debtors']} debtors ({o['n_debtors']/150:.0%})<br/>"
            f"{bs.get('climber',{}).get('n',0)} climber · {bs.get('chronic',{}).get('n',0)} chronic · "
            f"{bs.get('subsister',{}).get('n',0)} subsister<br/>"
            f"{o['n_vulnerable']} SHIW-vulnerable",
            f"{o['n_savers']} savers ({o['n_savers']/150:.0%})<br/>"
            f"{o['n_pension_savers']} of them pension-savers",
            f"{o['overdraft_events']} overdraft fees (€{o['overdraft_eur']:,})<br/>"
            f"{o['late_events']:,} late fees (€{o['late_eur']:,})<br/>"
            f"{o['credit_draws']} credit draws (€{o['credit_draw_eur']:,})",
        ],
    ], [W * 0.21, W * 0.16, W * 0.22, W * 0.17, W * 0.24], head_colour=INK2))
    f.append(gap(7))

    f.append(para("Run it yourself", "h2"))
    f.append(table([
        ["<b>Tests</b><br/>" + mono("uv run pytest -q"),
         "<b>The live app</b><br/>" + mono("uv run solara run src/synthitaly/viz.py"),
         "<b>The notebook</b><br/>" + mono("uv run jupyter lab notebooks/demo.ipynb"),
         "<b>The sensitivity sweep</b><br/>" + mono("uv run python scripts/sweep_behavioural.py")],
    ], [W * 0.19, W * 0.28, W * 0.28, W * 0.25], header=False, zebra=False))

    # =====================================================================
    # PAGE 2 — consumer types: the dimension stack
    # =====================================================================
    f.append(PageBreak())
    f.append(section("2 · Consumer types — the dimension stack", "a consumer is a combination, not an archetype"))
    f.append(gap(4))
    f.append(para(
        "There is no fixed list of consumer personas. Each household is drawn independently on the "
        "dimensions below, so heterogeneity is <b>emergent</b> from the draws rather than imposed by a "
        "persona table. The two dimensions that <i>do</i> carry named types are the <b>income source</b> "
        "(page 3) and the <b>debtor sub-type</b> (page 4).", "lead"))
    f.append(gap(4))

    f.append(table([
        ["Dimension", "Values", "Distribution / rule", "Source", "Tier"],
        ["<b>macro_area</b>", "NORTH / CENTRE / SOUTH", "0.46 / 0.20 / 0.34",
         "ISTAT resident population 2022 (replaces card-spend midpoints mis-cited to a nonexistent Emiliozzi §6)", para(tag("ITA"), "td")],
        ["<b>area income level</b>", "NORTH / CENTRE / SOUTH", "×1.00 / ×1.00 / ×0.554, mean-preserving",
         "Semeraro et al. (2020) p.5 (South GDP/capita 45% below Centre-North) and p.27 (−44.6% transfers received); Centre-North is one bloc in the paper", para(tag("ITA"), "td")],
        ["<b>monthly_income</b>", "continuous € > 0",
         "Lognormal(7.4, 0.55) ≈ €2,000 mean, drawn <i>per source</i> with that source's own spread; "
         "then by the macro-area multiplier; both mean-preserving, so the population mean and the SHIW bands are undisturbed",
         "SHIW 2022", para(tag("ITA"), "td")],
        ["<b>income_source</b>", "payroll · self-employed · pension · transfers · unemployed",
         "shares 0.52 / 0.20 / 0.20 / 0.03 / 0.05 — see page 3",
         "levels from SHIW §2B; <i>headcount shares</i> are an ISTAT-style proxy",
         para(tag("ITA") + " " + tag("MOD"), "td")],
        ["<b>income_level</b>", "low / middle / high",
         "<b>absolute euro bands</b>: ≤ €1,000 · €1,000–4,000 · > €4,000 per month",
         "BoI Payment Behaviour Survey 2023-24 income groups (4 survey bands collapsed to 3)",
         para(tag("ITA"), "td")],
        ["<b>income_quartile</b>", "1–4",
         "empirical 25/50/75 percentiles <i>of this run's</i> incomes",
         "SHIW reports <b>debt</b> by income quartile", para(tag("ITA"), "td")],
        ["<b>income_quintile</b>", "1–5",
         "empirical 20/40/60/80 percentiles of this run's incomes",
         "SHIW reports <b>savings</b> by income quintile", para(tag("ITA"), "td")],
        ["<b>has_debt</b>", "true / false",
         "P by quartile: Q1 0.120 · Q2 0.192 · Q3 0.244 · Q4 0.285",
         "SHIW 2022 §3", para(tag("ITA"), "td")],
        ["<b>monthly_debt_<br/>service</b>", "0 or € > 0",
         "annual mean by quartile €3,754 / 4,763 / 5,576 / 8,718, drawn lognormal(σ=0.5), ÷ 12; "
         "serviced on day 25",
         "mean = SHIW 2022 §3; the σ-shape and day-25 are choices", para(tag("ITA") + " " + tag("MOD"), "td")],
        ["<b>is_financially_<br/>vulnerable</b>", "true / false",
         "a debtor with income below median (quartile ≤ 2) <b>and</b> debt-service ratio > 30 %",
         "SHIW 2022 §3 — the survey's own definition", para(tag("ITA"), "td")],
        ["<b>debtor_subtype</b>", "climber · chronic · subsister · None",
         "splits the SHIW debtors, tilted by vulnerability — see page 4",
         "direction grounded in SHIW §3; magnitudes are ours", para(tag("MOD"), "td")],
        ["<b>debt_balance</b>", "€ ≥ 0",
         "opening principal = monthly service × 12; accrues 0.5 %/month interest",
         "SHIW gives the service <i>flow</i>, never a stock or a rate", para(tag("MOD"), "td")],
        ["<b>overdraft floor</b>", "€0 or −1 month of service",
         "<b>only chronic debtors overdraw</b>; climbers defer, subsisters borrow",
         "<i>who</i> holds debt is SHIW-driven; the floor size is a choice", para(tag("MOD"), "td")],
        ["<b>is_saver</b>", "true / false",
         "saver rate by quintile ≈ 30 / 40.5 / 51 / 61.5 / 72 % "
         "(from P(not saving) 0.70 / 0.595* / 0.490* / 0.385* / 0.28; * interpolated)",
         "SHIW 2022 §2F", para(tag("ITA"), "td")],
        ["<b>is_pension_saver</b>", "true / false",
         "a saver who passes a second, independent roll of the same quintile probability",
         "SHIW 2022 §2F — no contribution rate is invented", para(tag("ITA"), "td")],
        ["<b>accounts</b>", "current / savings / pension",
         "current starts at one month's income (subsisters: €0); savings and pension start at €0",
         "starting buffer is a modelling choice", para(tag("MOD"), "td")],
    ], [W * 0.155, W * 0.145, W * 0.34, W * 0.295, W * 0.065]))
    f.append(gap(6))

    f.append(callout(
        "Savings are emergent, not a rate — the single most-asked-about design decision",
        "There is <b>no savings-rate parameter anywhere</b>. Each consumer tracks four monthly "
        "accumulators (income, bills, debt service, discretionary spend). At month close "
        + mono("residual = income − bills − debt − discretionary") + "; if the consumer is a saver and "
        "the residual is positive, it is swept (capped at the current balance) into savings — or into "
        "pension for a pension-saver. Richer and lower-bill households simply leave larger residuals. "
        "The sweep is an internal paired debit/credit, so money is <b>moved, never created</b>: every "
        "account reconciles and the whole portfolio is conserved (" + mono("tests/test_conservation.py") + ").",
        GREEN))

    # =====================================================================
    # PAGE 3 — income source types
    # =====================================================================
    f.append(PageBreak())
    f.append(section("3 · Consumer type A — the five income sources", "who pays this household, and how much"))
    f.append(gap(4))
    f.append(para(
        "The primary income source is the household's economic identity: it sets the <i>level</i> and the "
        "<i>spread</i> of income, the statement label the credit carries, and whether a December "
        "thirteenth-month bonus arrives. SHIW gives the relative <b>level</b> of each source — the "
        "<b>headcount share</b> and the <b>dispersion</b> are flagged proxies and are swept.", "lead"))
    f.append(gap(4))

    src = o["by_source"]
    rows = [["Source", "Pop. share", "Rel. level", "σ", "Statement category",
             "13th mo.", "Observed in run", "Reading"]]
    src_meta = [
        ("payroll", "0.52", "×1.08", "0.45", "salary", "yes",
         "the salaried mainstream — a clean payday sawtooth"),
        ("self_employed", "0.20", "×1.49", "0.70", "self_employ_<br/>income", "no",
         "highest and <b>widest</b> — the top tail of the income distribution"),
        ("pension", "0.20", "×0.82", "0.35", "pension", "yes",
         "<b>tightest</b> spread (formula-driven); balances glide rather than saw"),
        ("transfers", "0.03", "×0.50", "0.40", "transfers", "no",
         "broad social support — low and, per SHIW, worsening"),
        ("unemployed", "0.05", "×0.40", "0.30", "unemployment_<br/>benefit", "no",
         "benefit-reliant jobless (NASpI: partial, time-limited) — hugs a low level"),
    ]
    for name, share, rel, sig, cat, thm, note in src_meta:
        n, mean = src.get(name, (0, 0))
        rows.append([f"<b>{name}</b>", share, rel, sig, mono(cat), thm,
                     f"n = {n} ({n/150:.0%})<br/>mean €{mean:,}/mo", note])
    f.append(table(rows, [W * 0.135, W * 0.065, W * 0.06, W * 0.05, W * 0.16,
                          W * 0.06, W * 0.135, W * 0.335]))
    f.append(gap(6))

    f.append(para("How the source is turned into euros — " + mono("numbers.sample_income_for_source()"), "h2"))
    f.append(table([
        ["Step", "What happens", "Why it is built this way"],
        ["1 · draw the source", mono("sample_income_source(rng)") + " picks from " + mono("INCOME_SOURCE_SHARE") + ".",
         "Headcounts are not in any of the five papers — flagged proxy, swept in the sensitivity study."],
        ["2 · mean-preserving multiplier",
         mono("income_source_multiplier(s)") + " = the source's relative level ÷ the share-weighted mean of all levels.",
         "Keeps the <b>population</b> mean income exactly where the SHIW lognormal put it, so the "
         "quartile/quintile bands — and every debt and savings probability hanging off them — are undisturbed."],
        ["3 · per-source lognormal",
         mono("mu = log(target_mean) − σ²/2") + " with the source's own " + mono("σ") + ".",
         "Gives each source its own spread <i>without</i> moving its mean. Only the shape is assumed; "
         "the enforcement is asserted at import time."],
        ["4 · the macro-area income gradient",
         "Every income draw is scaled by its area multiplier as well as its source multiplier: "
         "NORTH and CENTRE ×1.00, SOUTH ×0.554. Both are mean-preserving, so the population "
         "mean is untouched and only the dispersion changes.",
         "Semeraro et al. (2020) p.5/p.27. The paper treats Centre-North as one bloc, so North "
         "and Centre are not separated. Replaces a secondary property-income credit that was "
         "removed — no source gives its incidence or its size."],
        ["5 · the calendar",
         "Payday = the <b>27th</b>. In December, payroll and pension recipients are credited <b>×2</b> (tredicesima).",
         "Payday is a simplification of 'last business day' (structural-inequalities §9); the wire-transfer "
         "paper §9 documents the December peak. The month set is a flagged choice."],
    ], [W * 0.20, W * 0.40, W * 0.40], head_colour=INK2))
    f.append(gap(6))

    f.append(callout(
        "If asked: why does income-source heterogeneity matter at all?",
        "Because it is what makes the <b>balance trajectories</b> differ in kind rather than only in level "
        "(figure f07). A payroll household shows the classic payday sawtooth; a pensioner glides on a tight, "
        "formula-driven income; a self-employed household swings widely; the unemployed hug a low floor and "
        "are the ones that meet a bill due-date before cash arrives — which is exactly where the "
        "late-payment mechanism (page 5) bites. None of that is scripted: it falls out of the level, the "
        "spread, and the shared calendar.",
        ACCENT))

    # =====================================================================
    # PAGE 4 — debtor sub-types
    # =====================================================================
    f.append(PageBreak())
    f.append(section("4 · Consumer sub-type — the three debtor archetypes",
                     "climber · chronic · subsister"))
    f.append(gap(4))
    f.append(para(
        "SHIW decides <b>who</b> holds debt (a quartile roll) and <b>how much</b> they service each month. "
        "The archetype only <b>partitions the debtors that roll already produced</b> — it never changes the "
        "debt participation rate. What it does change is the <i>repayment rule</i>, and that is what makes "
        "the three balance trajectories diverge.", "lead"))
    f.append(gap(4))

    bs = o["by_subtype"]

    def col(k: str, key: str, fmt=str) -> str:
        return fmt(bs.get(k, {}).get(key, 0))

    f.append(table([
        [para("Attribute", "th"),
         para('<font color="#FFFFFF"><b>CLIMBER</b> — digs out</font>', "th"),
         para('<font color="#FFFFFF"><b>CHRONIC</b> — never escapes</font>', "th"),
         para('<font color="#FFFFFF"><b>SUBSISTER</b> — ekes out at zero</font>', "th")],
        ["<b>The story</b>",
         "Repays more than the interest, principal falls to zero, then <b>leaves debt for good</b>.",
         "Repays roughly the interest, principal stays flat, runs a <b>standing overdraft</b>.",
         "Borrows small amounts to cover shortfalls so the current account <b>hugs zero</b>; principal drifts up."],
        ["<b>Monthly repayment</b> (day 25)",
         "full SHIW scheduled service (×1.0) → principal falls",
         "<b>interest only</b> → principal exactly flat (drifts up when even the interest is unaffordable)",
         "token 0.25 × service → principal drifts up"],
        ["<b>Overdraft</b>",
         "not allowed (floor €0) — an unaffordable bill is <b>deferred</b>",
         "<b>allowed</b>, floor = −1 month of their own service — <i>the only subtype that goes into the red</i>",
         "not allowed (floor €0) — borrows instead"],
        ["<b>Borrowing</b>",
         "never",
         "never",
         "draws on a per-area " + mono("credit_line") + " stand-in (logged " + mono('kind="loan"') +
         "), capped at 2 × the opening principal"],
        ["<b>Starting cash</b>",
         "one month's income",
         "one month's income",
         "<b>€0</b> — hand-to-mouth; the month-end sweep is forced on so no buffer accumulates"],
        ["<b>Exit</b>",
         "principal ≤ 0 → " + mono("has_debt=False") + ", overdraft withdrawn; the <i>label</i> is kept so you can "
         "still show 'a climber who made it out'",
         "never — by construction",
         "never — the ceiling bounds the debt, it does not clear it"],
        ["<b>Who becomes one</b>",
         "resilient debtors, drawn <b>climber-heavy</b> (0.60)",
         "vulnerable debtors, drawn <b>chronic-heavy</b> (0.60)",
         "0.25 resilient / 0.30 vulnerable — present in both groups"],
        [f"<b>Observed</b><br/>({o['n_debtors']} debtors)",
         f"<b>n = {col('climber','n')}</b> · still in debt {col('climber','still')}<br/>"
         f"mean income €{bs.get('climber',{}).get('inc',0):,} · DSR {bs.get('climber',{}).get('dsr',0):.0%}<br/>"
         f"end balance €{bs.get('climber',{}).get('bal',0):,} · debt €{bs.get('climber',{}).get('debt',0):,}",
         f"<b>n = {col('chronic','n')}</b> · still in debt {col('chronic','still')}<br/>"
         f"mean income €{bs.get('chronic',{}).get('inc',0):,} · DSR {bs.get('chronic',{}).get('dsr',0):.0%}<br/>"
         f"end balance €{bs.get('chronic',{}).get('bal',0):,} · debt €{bs.get('chronic',{}).get('debt',0):,}",
         f"<b>n = {col('subsister','n')}</b> · still in debt {col('subsister','still')}<br/>"
         f"mean income €{bs.get('subsister',{}).get('inc',0):,} · DSR {bs.get('subsister',{}).get('dsr',0):.0%}<br/>"
         f"end balance €{bs.get('subsister',{}).get('bal',0):,} · debt €{bs.get('subsister',{}).get('debt',0):,}"],
        ["<b>Where in the code</b>",
         para(mono("model.Consumer._service_debt()") + " — the branch on " + mono("debtor_subtype") +
              " is the whole mechanism; assignment (including the opening stock and the overdraft floor) in "
              + mono("model.ItalyModel._assign_debt()") + "; constants in " + mono("numbers.py") +
              " under 'Debtor subtypes'.", "td"),
         "", ""],
    ], [W * 0.155, W * 0.28, W * 0.28, W * 0.285], head_colour=INK2,
       extra=[("SPAN", (1, 9), (3, 9))]))
    f.append(gap(6))

    f.append(para("The one thing here that <i>is</i> grounded: the vulnerability tilt", "h2"))
    f.append(table([
        ["Debtor group", "Definition", "climber", "chronic", "subsister", "Why"],
        ["<b>financially vulnerable</b>",
         "SHIW 2022 §3: equivalized income <b>below median</b> (quartile ≤ 2) <b>and</b> debt-service ratio <b>> 30 %</b>",
         "0.10", "<b>0.60</b>", "0.30",
         "Concentrates the chronic cohort among low-income, high-burden households, so 'chronically indebted' "
         "actually looks distressed. Campbell (2006): financial mistakes and fees concentrate exactly there."],
        ["<b>resilient</b>", "any other debtor", "<b>0.60</b>", "0.15", "0.25",
         "Households with room to repay do repay, and leave debt."],
    ], [W * 0.15, W * 0.27, W * 0.08, W * 0.08, W * 0.095, W * 0.325]))
    f.append(gap(4))
    f.append(para(
        "<b>Say this out loud if challenged:</b> the <i>magnitudes</i> (0.60/0.15/0.25 etc.) are a modelling "
        "choice and are swept; the <i>direction</i> of the tilt is not — it uses SHIW's own definition of a "
        "financially vulnerable household. Without the tilt, 'chronic debtor' would land on comfortable "
        "high-earners, which would be an artefact, not a finding.", "note"))
    f.append(gap(6))

    f.append(callout(
        "The flow→stock step — the biggest single modelling choice in the model",
        "SHIW reports debt <b>participation</b> and annual debt <b>service</b> — a flow. It never reports a "
        "principal stock, an interest rate, or behavioural repayment archetypes. To show trajectories at all "
        "we needed a stock, so: opening principal = monthly service × <b>12 months</b>, accruing "
        "<b>0.5 %/month</b> (≈6.2 %/yr consumer credit). Interest accrues even in a month the household "
        "cannot pay, so missed payments make debt grow — the realistic direction. Both constants are swept.",
        ORANGE))

    # =====================================================================
    # PAGE 5 — behavioural-economics layer
    # =====================================================================
    f.append(PageBreak())
    f.append(section("5 · The behavioural-economics layer", "the thesis contribution — and its honest caveat"))
    f.append(gap(4))
    f.append(para(
        "<b>Different provenance from everything else.</b> These mechanisms come from three non-Italian "
        "papers. The behaviour's <i>existence and shape</i> is paper-grounded; the <i>euro or percentage "
        "magnitude</i> is a deliberate modelling choice and is <b>swept</b>, so no result depends on a single "
        "foreign number. Keep this line bright when presenting.", "lead"))
    f.append(gap(4))

    f.append(table([
        ["Mechanism", "Paper & evidence", "How it is mapped into the model", "Magnitude", "Where"],
        [para("<b>Payday spending spike</b>", "tdb"),
         "<b>Olafsson & Pagel (2018)</b>, <i>The Liquid Hand-to-Mouth</i>, RFS 31(11). Icelandic "
         "personal-finance-app data: discretionary spending bunches ~40–60 % above the non-payday average "
         "right after income arrives, then decays across the cycle — homogeneously across the income distribution.",
         "A <b>mean-neutral multiplier on daily spending intensity</b>: peaks on payday, falls linearly to "
         "(2 − peak) the day before the next. Averaged over a cycle it is exactly 1.0 — asserted at import — "
         "so monthly totals and the emergent savings residual are <b>unchanged</b>; only the <i>timing</i> "
         "of spend inside the cycle moves.",
         "peak <b>×1.5</b><br/>(≈ +50 %)",
         mono("numbers.pay_cycle_multiplier()") + " → " + mono("daily_intensity()") + " → " +
         mono("Consumer._maybe_buy_from_merchant()")],
        [para("<b>Overdraft fee</b>", "tdb"),
         "<b>Stango & Zinman (2014)</b>, RFS 27(4). US checking accounts: a flat per-event fee (~$20–35, "
         "≈$150/yr per account), incidence concentrated among lower-income / lower-literacy holders.",
         "A flat fee charged <b>the moment a payment pushes the current account from ≥ 0 to below 0</b>. "
         + mono("_can_afford()") + " reserves room for the fee, so the overdraft floor stays a hard limit "
         "<i>including</i> fees. Only chronic debtors have a negative floor, so only they can trigger it.",
         "<b>€30</b> flat<br/>per event",
         mono("numbers.OVERDRAFT_FEE_EUR") + " → " + mono("Consumer._pay()") + " → " +
         mono("Consumer._charge_overdraft_fee()")],
        [para("<b>Late-payment fee</b>", "tdb"),
         "<b>Dahan & Nisan (2020)</b>, CESifo WP 8733. Israeli utility bills: when a bill falls due before "
         "payday, a liquidity-constrained household pays <b>late with a penalty</b> rather than not at all; "
         "accumulated late charges reach ~11 % of the bill.",
         "An unaffordable bill is <b>no longer silently skipped</b> — it is carried on an overdue queue and "
         "retried every day. When the account can cover principal + fee, both are paid to the original "
         "biller. Still unpaid after 90 days → written off (service cut), so the queue cannot grow forever.",
         "<b>11 %</b> of<br/>the bill",
         mono("numbers.LATE_PAYMENT_FEE_FRACTION") + " → " + mono("Consumer._pay_due_bills()") + " → " +
         mono("Consumer._settle_overdue_bills()")],
        [para("<b>Fee incidence</b><br/>(conceptual)", "tdb"),
         "<b>Campbell (2006)</b>, <i>Household Finance</i>. Financial mistakes — and the fees they generate — "
         "concentrate among lower-income, lower-literacy households.",
         "Not a constant: an <b>outcome</b>. Because fees are triggered by liquidity constraints, they land "
         "on whoever is short of cash on a given day. This is also the grounding for tilting the chronic "
         "archetype toward the SHIW-vulnerable cohort (page 4).",
         "emergent",
         "verified in output, not parameterised"],
    ], [W * 0.125, W * 0.245, W * 0.305, W * 0.095, W * 0.23], head_colour=PURPLE))
    f.append(gap(6))

    f.append(para("Does Campbell's prediction actually hold in the output? — observed in the reference run", "h2"))
    fl, fs = o["fees_by_level"], o["fees_by_subtype"]
    tot_fees = sum(fl.values()) or 1
    f.append(table([
        ["Fee events by income level", "Fee events by debtor sub-type", "Totals", "The honest reading"],
        [f"low <b>{fl.get('low',0):,}</b> ({fl.get('low',0)/tot_fees:.0%})<br/>"
         f"middle {fl.get('middle',0):,} ({fl.get('middle',0)/tot_fees:.0%})<br/>"
         f"high {fl.get('high',0):,}",
         f"no debt <b>{fs.get('no_debt',0):,}</b><br/>chronic {fs.get('chronic',0)}<br/>"
         f"climber {fs.get('climber',0)}<br/>subsister {fs.get('subsister',0)}",
         f"overdraft: {o['overdraft_events']} events, €{o['overdraft_eur']:,}<br/>"
         f"late payment: {o['late_events']:,} events, €{o['late_eur']:,}<br/>"
         f"credit draws: {o['credit_draws']} , €{o['credit_draw_eur']:,}",
         "<b>Yes on income</b> — roughly four in five fee events fall on low-income households, with none at "
         "all in the high band: exactly Campbell's concentration, and it was never coded in.<br/>"
         "<b>But note</b>: most fee-payers are <i>not</i> debtors. Late fees are driven by the "
         "<b>due-date-before-payday mismatch</b> (Dahan & Nisan's actual mechanism), which hits any "
         "cash-poor household. Debt is not a prerequisite for financial distress in this model — say this "
         "before someone else spots it."],
    ], [W * 0.18, W * 0.17, W * 0.22, W * 0.43], head_colour=INK2))
    f.append(gap(6))

    f.append(callout(
        "The sweep — your answer to 'but those numbers are not Italian'",
        mono("scripts/sweep_behavioural.py") + " varies one parameter at a time around the defaults and "
        "reports how the KPIs move: <b>payday peak</b>, <b>overdraft fee</b>, <b>late-fee fraction</b>, the "
        "<b>pension</b> and <b>unemployed</b> headcount shares, the <b>debt interest rate</b>, and how "
        "<b>chronic-heavy</b> the vulnerable split is drawn. The debt sweeps run on a 720-day horizon so "
        "climbers have time to dig out. The point is not that the defaults are right — it is that the "
        "qualitative conclusions do not turn on them.",
        PURPLE))

    # =====================================================================
    # PAGE 6 — general calibration
    # =====================================================================
    f.append(PageBreak())
    f.append(section("6 · General calibration", "every Italian number, and the paper it came from"))
    f.append(gap(4))
    f.append(para(
        "All of the below lives in " + mono("src/synthitaly/numbers.py") + " with the same source note in a "
        "code comment, and is asserted for consistency at import time (shares sum to 1, the pay-cycle "
        "multiplier is mean-neutral, the income multipliers are mean-preserving). Change a number there and "
        "it flows through the model, the notebooks, and the dashboard.", "lead"))
    f.append(gap(4))

    f.append(para("Spending — 10 card-visible categories · <i>Emiliozzi et al. (2023) §2.1, Fig. 4/6</i> "
                  + tag("ITA"), "h2"))
    # The paper share is a share of EUROS, so it is not the probability of picking
    # the category. sample_category() draws with p ∝ share / E[ticket]; both columns
    # are shown because showing only one invites the reader to assume they are the
    # same number, which is the bug this table used to describe.
    cat_rows = [["Category", "Paper € share", "Draw p", "Ticket (μ, σ)", "Mean ≈"],
                ["retail", "0.26", "0.329", "(3.0, 0.9)", "€30"],
                ["food", "0.20", "0.259", "(3.2, 0.6)", "€29"],
                ["hotels_rest", "0.11", "0.109", "(3.4, 0.7)", "€38"],
                ["travel", "0.09", "0.034", "(4.0, 1.1)", "€100"],
                ["clothing", "0.08", "0.060", "(3.6, 0.8)", "€50"],
                ["home", "0.07", "0.049", "(3.5, 1.0)", "€55"],
                ["phones_web", "0.05", "0.074", "(3.0, 0.7)", "€26"],
                ["repairs", "0.05", "0.021", "(3.8, 1.2)", "€92"],
                ["cash_advance", "0.05", "0.031", "(4.0, 0.5)", "€62"],
                ["services", "0.04", "0.034", "(3.4, 0.9)", "€45"]]
    left = table(cat_rows, [W * 0.13, W * 0.09, W * 0.07, W * 0.12, W * 0.08])
    right_rows = [
        ["Bill", "Share of h.h.", "Mean €", "Day"],
        ["utilities", "0.73", "124", "10"],
        ["telecom", "0.70", "40", "15"],
        ["rent", "0.24", "440", "1"],
        ["mortgage", "0.19", "489", "5"],
        ["consumer_loan", "0.14", "198", "20"],
        [para("<b>debt_service</b> (SHIW aggregate)", "tdb"), "debtors only",
         "quartile mean ÷ 12", "25"],
    ]
    right = table(right_rows, [W * 0.145, W * 0.10, W * 0.11, W * 0.055])
    combo = Table([[left, right]], colWidths=[W * 0.50, W * 0.50])
    combo.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("RIGHTPADDING", (0, 0), (0, 0), 8)]))
    f.append(combo)
    f.append(para(
        "Right-hand table: recurring bills — <i>Bank of Italy Payment Behaviour Survey 2023-24 §8</i> "
        + tag("ITA") + ". A consumer subscribes to each bill independently with its share.", "note"))
    f.append(gap(6))

    f.append(para("Calendar — <i>Emiliozzi et al. (2023) §3, direction only</i> + <i>structural-inequalities</i> " + tag("ITA"), "h2"))
    f.append(table([
        ["Weekday", "Month", "Special days", "Payday", "Bonus"],
        ["Mon–Wed ×0.95<br/>Thu ×1.00<br/><b>Fri ×1.10</b><br/><b>Sat ×1.20</b><br/>Sun ×1.00",
         "<b>Dec ×1.25</b> (peak)<br/>Jul ×1.08 · Nov ×1.05<br/>Apr/Jun ×1.02 · May ×1.00<br/>"
         "Jan/Mar/Sep ×0.95 · Feb ×0.92<br/><b>Aug ×0.85</b> (trough)",
         "public holiday <b>×1.15</b><br/>(10 fixed + Easter &amp; Easter Monday, computed)<br/>"
         "Christmas window Dec 20–31 <b>×1.40</b>",
         "the <b>27th</b> of every month — a simplification of 'last business day of the month'",
         "<b>tredicesima</b>: an extra month's income in <b>December</b> for payroll &amp; pension recipients"],
    ], [W * 0.17, W * 0.24, W * 0.23, W * 0.17, W * 0.19], head_colour=INK2))
    f.append(gap(6))

    f.append(para("Income, debt and savings calibration", "h2"))
    f.append(table([
        ["Block", "Values", "Source", "Tier"],
        ["Income distribution", "lognormal(μ=7.4, σ=0.55) → mean ≈ €2,000/month net",
         "SHIW 2022", para(tag("ITA"), "td")],
        ["Income level bands", "low ≤ €1,000 · middle €1,000–4,000 · high > €4,000 (absolute euro, not percentiles)",
         "BoI Payment Behaviour Survey 2023-24 (4 survey bands collapsed to 3)", para(tag("ITA"), "td")],
        ["Debt participation", "Q1 12.0 % · Q2 19.2 % · Q3 24.4 % · Q4 28.5 %",
         "SHIW 2022 §3", para(tag("ITA"), "td")],
        ["Debt service (annual mean)", "Q1 €3,754 · Q2 €4,763 · Q3 €5,576 · Q4 €8,718 — lognormal σ=0.5, ÷12",
         "SHIW 2022 §3 (mean); σ-shape is a choice", para(tag("ITA") + " " + tag("MOD"), "td")],
        ["Saving probability", "P(did not save) by quintile 0.70 / 0.595* / 0.490* / 0.385* / 0.28 (* interpolated)",
         "SHIW 2022 §2F", para(tag("ITA"), "td")],
        ["Debt stock layer", "opening = 12 × monthly service · interest 0.5 %/month · subsister ceiling 2× opening",
         "no paper — SHIW gives only the flow", para(tag("MOD"), "td")],
        ["Behavioural magnitudes", "payday peak ×1.5 · overdraft €30 · late fee 11 %",
         "Olafsson &amp; Pagel · Stango &amp; Zinman · Dahan &amp; Nisan (non-Italian)", para(tag("BEH"), "td")],
        ["Purchase base rate", mono("base_prob = 0.6") + " per consumer per day, scaled by " + mono("daily_intensity(d)"),
         "a tuning knob chosen for ~0.5–1 transactions/consumer/day", para(tag("MOD"), "td")],
    ], [W * 0.16, W * 0.42, W * 0.35, W * 0.07]))
    f.append(gap(5))
    f.append(para(
        "<b>Known overlap, deliberately not reconciled:</b> the model keeps two paper-faithful but "
        "overlapping views of debt — the recurring " + mono("mortgage") + " (€489, 19 %) and "
        + mono("consumer_loan") + " (€198, 14 %) bills <b>and</b> the SHIW aggregate " + mono("debt_service") +
        " line. They come from different surveys; merging them would require a number neither survey gives. "
        "Documented as a teaching-prototype simplification, not an invented figure.", "note"))

    # =====================================================================
    # PAGE 7 — the script map
    # =====================================================================
    f.append(PageBreak())
    f.append(section("7 · The script map", "what controls what"))
    f.append(gap(4))
    f.append(para(
        "The active model is <b>three files, ~2,900 lines</b>, deliberately small enough to be read "
        "top-to-bottom. Everything else in the repository is scaffolding around those three.", "lead"))
    f.append(gap(4))

    f.append(callout(
        "① src/synthitaly/numbers.py — 692 lines · every empirical constant, one place",
        "<b>Controls: all of the data.</b> Macro-area weights, category shares and ticket distributions, "
        "bills, calendar multipliers, income distribution and per-source levels/spreads, debt participation "
        "and service, saving probabilities, the debtor-subtype splits, and the three behavioural magnitudes. "
        "Also holds the calendar helpers (" + mono("is_payday") + ", " + mono("is_holiday") + ", "
        + mono("pay_cycle_multiplier") + ") and the samplers (" + mono("sample_category") + ", "
        + mono("sample_ticket") + ", " + mono("daily_intensity") + ", " + mono("sample_income_for_source") +
        ", " + mono("sample_debtor_subtype") + "). Every constant carries its paper and section in a comment, "
        "and the file asserts its own consistency at import. <b>Change a number here and it flows through the "
        "model, the notebooks and the dashboard — nothing else hard-codes an Italian value.</b>",
        GREEN))
    f.append(gap(5))
    f.append(callout(
        "② src/synthitaly/model.py — 1,143 lines · the simulation engine",
        "<b>Controls: all of the behaviour.</b> " + mono("BankAccount") + "/" + mono("BankEntry") +
        " (the double-entry bookkeeping), the three agent classes — " + mono("Consumer") + " (the only "
        "decision-maker), " + mono("Merchant") + ", " + mono("IncomeSource") + " — and " + mono("ItalyModel") +
        ", which builds the population and drives the daily clock. The methods that carry the thesis: "
        + mono("_assign_debt()") + " (SHIW roll → archetype → opening stock → overdraft floor), "
        + mono("_service_debt()") + " (the three repayment rules), " + mono("_settle_overdue_bills()") +
        " (late fees), " + mono("_charge_overdraft_fee()") + ", " + mono("_borrow()") + " (subsister credit "
        "line), and " + mono("_month_close()") + " (the emergent savings sweep). Reads " + mono("numbers.py") +
        "; writes nothing to disk.",
        ACCENT))
    f.append(gap(5))
    f.append(callout(
        "③ src/synthitaly/viz.py — 1,083 lines · the live Solara dashboard (the showpiece)",
        "<b>Controls: what you can show live.</b> Eleven panels: spending by area · network panel with live "
        "money-flow arrows (green salary, blue purchases, brown bills/debt, red fees) · KPI plot · "
        "<b>behavioural-events panel</b> (overdraft/late-fee counts + payday markers) · income composition · "
        "balance trajectories by source · <b>debtor composition</b> · <b>debt trajectory by archetype</b> · "
        "<b>chronic-debtor panel</b> · account inspector (pick a cluster → a consumer → read their three "
        "statements) · a static archetype reference card. Sliders set seed, consumers, merchants and days. "
        "Run: " + mono("uv run solara run src/synthitaly/viz.py"),
        PURPLE))
    f.append(gap(7))

    f.append(para("Everything else — where to point if asked", "h2"))
    f.append(table([
        ["Path", "Controls / contains", "When you would open it"],
        [mono("scripts/sweep_behavioural.py"),
         "One-at-a-time sensitivity sweep over every non-Italian or non-paper magnitude "
         "(payday peak, overdraft fee, late fee, pension &amp; unemployed shares, debt interest, chronic tilt).",
         "'Your behavioural numbers aren't Italian' → this is the answer."],
        [mono("tests/") + " (8 files)",
         mono("test_conservation.py") + " money is conserved system-wide · " + mono("test_debt_vulnerability.py") +
         " the subtype rules hold · " + mono("test_income.py") + " · " + mono("test_balances.py") + " · "
         + mono("test_numbers.py") + " · " + mono("test_schema.py") + " · " + mono("test_smoke.py") + " · "
         + mono("test_analysis_pipeline.py") + " pins the feature pipeline the figures reuse.",
         "'How do you know the accounting is right?' → " + mono("uv run pytest -q") + "."],
        [mono("notebooks/demo.ipynb"),
         "Runs the model, plots the output, writes the transaction CSV and the per-account portfolio table.",
         "The safety-net path if the live app misbehaves."],
        [mono("notebooks/clustering.ipynb") + "<br/>" + mono("notebooks/prediction.ipynb"),
         "The two validation studies: unsupervised recovery of the debtor archetypes (PCA + KMeans) and "
         "supervised debtor prediction — including the <b>deliberate leakage demonstration</b> (honest "
         "behavioural features reach AUC 0.68; adding debt-mechanic proxies leaks the label to AUC 1.00).",
         "'Can you get the types back out of the data?' → figures f13–f15."],
        [mono("presentation/scripts/"),
         mono("generate_figures.py") + " regenerates all 19 figures from ONE live model run at the pinned "
         "800×720d, seed 42 — the time-series charts slice its first 120 days, "
         "Run B (150×720d), Run C (600×720d) · " + mono("make_diagrams.py") + " the 5 Mermaid diagrams "
         "(architecture, day-step, money flow, methodology pipeline, provenance tiers) · "
         + mono("build_deck.py") + " the self-contained " + mono("status_deck.html") + " · "
         + mono("make_reference_card.py") + " <b>this PDF</b> — re-run it after changing any constant and "
         "the observed figures update.",
         "Every figure in the deck is reproducible from seed 42; the deck is the backup for showing the "
         "architecture without opening the code."],
        [mono("docs/"),
         mono("MODEL_REFERENCE.md") + " the data dictionary · " + mono("EXPLANATION.md") + " why it exists and "
         "the paper map · " + mono("ODD.md") + " the formal Grimm et al. ABM specification · "
         + mono("HOW_IT_WORKS.md") + " file-by-file walkthrough · " + mono("WALKTHROUGH.md") + " · "
         + mono("QUICKSTART.md") + ".",
         "The written back-up for every claim on this card."],
        ["The parked prototype",
         "The earlier, larger version (3,165 lines, nine bill types, per-paper modules). <b>Parked, not active.</b>",
         "'What did you cut, and why?' → readability over scale."],
    ], [W * 0.26, W * 0.45, W * 0.29]))

    # =====================================================================
    # PAGE 8 — likely questions
    # =====================================================================
    f.append(PageBreak())
    f.append(section("8 · Likely questions — and the honest answer", "the ones worth rehearsing"))
    f.append(gap(4))

    qa = [
        ("Is this real Italian data?",
         "No — and it is not meant to be. It is <b>synthetic transaction data generated by rules calibrated "
         "to public Italian statistics</b>. Real account-level ledgers are private; the public payment "
         "datasets are aggregated past the point where individual behaviour is visible. The contribution is "
         "a model whose every number is either cited or flagged."),
        ("Why an agent-based model rather than a statistical generator?",
         "Because the phenomena of interest are <b>emergent</b>. The savings rate is not a parameter but a "
         "residual; fees land on whoever happens to be cash-poor on a given day; the same payday spike "
         "re-times spending differently for a pensioner and a self-employed household. Three agent rules and "
         "a shared calendar produce all of that; a statistical generator would have to be told each pattern."),
        ("Your behavioural magnitudes come from Iceland, the US and Israel.",
         "Correct, and it is stated everywhere in the code and docs. The <i>shape</i> of each mechanism is "
         "paper-grounded; the <i>magnitude</i> is a modelling choice, and each one is swept in "
         + mono("scripts/sweep_behavioural.py") + ". No qualitative conclusion depends on the default value. "
         "Using a foreign magnitude and saying so is more defensible than inventing an Italian-sounding one."),
        ("The three debtor archetypes — where are they in SHIW?",
         "They are not, and I do not claim they are. SHIW gives debt participation and the annual service "
         "flow. The archetypes are a <b>modelling choice</b> that partitions the debtors SHIW already "
         "produced — participation is untouched. The one grounded element is the <b>direction of the tilt</b>: "
         "vulnerable debtors (SHIW §3: below-median income <i>and</i> DSR > 30 %) are drawn chronic-heavy, so "
         "the chronic cohort lands on distressed households rather than comfortable ones."),
        ("Are the income-source shares Italian?",
         "The <b>levels</b> are (SHIW §2B: payroll ×1.08, self-employed ×1.49, pension ×0.82). The "
         "<b>headcount shares</b> and the per-source <b>dispersion</b> are not — SHIW reports levels, not "
         "headcounts or spreads. Both are flagged proxies and both are swept. The multiplier is "
         "mean-preserving, so adding source heterogeneity does not move the population mean or disturb the "
         "SHIW quartile bands that debt and savings hang off."),
        ("Does the payday spike inflate total spending?",
         "No — it is <b>mean-neutral by construction</b>, and the model asserts it at import: averaged over a "
         "pay cycle the multiplier is exactly 1.0. It moves <i>when</i> money is spent inside the cycle, not "
         "how much. That is deliberate: it keeps the SHIW-grounded savings residual intact while still "
         "reproducing Olafsson &amp; Pagel's bunching."),
        ("Are the paper's category shares shares of euros or of transactions?",
         "<b>Euros.</b> Emiliozzi et al. Figure 4 is titled <i>Average shares of expenditure categories</i> "
         "and Figure 6 benchmarks it against COICOP national-accounts expenditure. This matters because the "
         "model draws the category and the ticket size independently, so using the shares directly as "
         "selection probabilities reproduces them in <b>counts</b> and misses on euros — travel landed at "
         "19.8 % of euros against the paper's 9.0 %, a 10.8pp error that f02 spent months displaying as if it "
         "were a calibration imperfection. "
         + mono("sample_category()") + " now draws with p ∝ share ÷ E[ticket], which makes the realised euro "
         "shares equal the paper's exactly by construction; the residual in f02 is finite-sample noise from "
         "the lognormals, worst case 0.6pp. The cost is that the constant no longer doubles as the count "
         "distribution — cheap categories are picked more often than their euro share, expensive ones less."),
        ("Most of your fee-payers aren't even debtors.",
         "True, and it is the more interesting result. Dahan &amp; Nisan's mechanism is a <b>due-date-before-"
         "payday mismatch</b>, not a debt mechanism — so it hits any cash-poor household. In the reference run "
         f"{o['fees_by_level'].get('low',0)/max(sum(o['fees_by_level'].values()),1):.0%} of fee events fall on "
         "low-income households and none at all on high-income ones. That reproduces Campbell's concentration "
         "result without it being coded in anywhere."),
        ("What are the limitations?",
         "Stated up front: behavioural magnitudes are non-Italian (mitigated by sweeping, not removed); two "
         "overlapping debt views deliberately not reconciled; income-source headcounts are proxies; <b>no "
         "life-cycle or macro dynamics</b> — employment status is static, no inflation, no ageing, no "
         "migration, horizon is months to a few years; and the model is small by design (800 households at "
         "the pinned configuration, "
         "three source files) because it is built to be <i>read</i>."),
        ("Can I trust the accounting?",
         "Every movement is a <b>paired debit/credit</b> through a real counterparty — including fees, credit "
         "draws, and the internal savings sweep — so money is moved, never created. "
         + mono("tests/test_conservation.py") + " checks system-wide conservation; runs are deterministic for "
         "a given seed, so every figure in the deck reproduces exactly."),
    ]
    rows = [["Question", "Answer"]]
    rows += [[para(f"<b>{q}</b>", "tdb"), a] for q, a in qa]
    f.append(table(rows, [W * 0.27, W * 0.73], head_colour=INK2))
    f.append(gap(6))
    f.append(para(
        "Sources: SHIW 2022 (Bank of Italy) · Payment Behaviour Survey 2023-24 (Bank of Italy) · "
        "Emiliozzi et al. (2023), Italian card data · structural-inequalities / wire-transfer paper · "
        "Olafsson &amp; Pagel (2018) RFS 31(11) · Stango &amp; Zinman (2014) RFS 27(4) · Dahan &amp; Nisan "
        "(2020) CESifo WP 8733 · Campbell (2006) <i>Household Finance</i> · Jiang et al. (2022) synthetic "
        "population method. Full citations in " + mono("docs/REFERENCES.md") + ".", "note"))

    doc.build(f)


def main() -> None:
    live = "--no-run" not in sys.argv
    if live:
        print("running the reference model (800 consumers × 720 days, seed 42) …")
    o = observed(live)
    build(o)
    print(f"wrote {OUT.relative_to(ROOT)}  ({OUT.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
