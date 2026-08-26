#!/usr/bin/env python3
"""Build the money-flow and paper-provenance reference page.

    uv run python scripts/build_flows_page.py [--out runs/latest]

Writes ``<out>/flows_and_papers.html`` — a self-contained page answering three
questions that are otherwise scattered across six documents and two source files:

  1. What income can a household receive, and when?
  2. Where does the money go, in what order, and what happens when it runs out?
  3. Which paper justifies which effect — and, crucially, **where the mapping has
     holes in both directions**.

Section F (the gap audit) is the reason this page exists. It is deliberately
uncomfortable reading: it lists the paper-backed material the model does not use,
*and* the mechanisms in the model that no paper backs. Both lists are needed
before anyone can claim the model is "calibrated to four Italian papers".

Every row names the file and line it came from. Values that can be read off
``synthitaly.numbers`` are read from there rather than retyped, so this page
cannot drift from the constants it documents — the one class of error the repo
has already made once.
"""
from __future__ import annotations

import argparse
import math
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "presentation" / "scripts"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from _report import (  # noqa: E402
    callout,
    esc,
    eur,
    nav,
    p,
    page,
    pre,
    section,
    src,
    steps,
    table,
    tiles,
)

from synthitaly import numbers as N  # noqa: E402

TIER1 = '<span class="tier tier1">Italian · calibrated</span>'
TIER2 = '<span class="tier tier2">behavioural · magnitude swept</span>'
TIER3 = '<span class="tier tier3">modelling choice</span>'
TIERM = '<span class="tier tierM">method</span>'


# --------------------------------------------------------------------------- #
# A — income
# --------------------------------------------------------------------------- #
def income_section() -> str:
    base_mean = math.exp(N.INCOME_LOGNORMAL[0] + N.INCOME_LOGNORMAL[1] ** 2 / 2)
    rows = []
    for s in ("payroll", "self_employed", "pension", "transfers", "unemployed"):
        share = N.INCOME_SOURCE_SHARE[s]
        rel = N.INCOME_SOURCE_RELATIVE[s]
        sig = N.INCOME_SOURCE_SIGMA[s]
        mult = N.income_source_multiplier(s)
        tier = TIER1 if s in ("payroll", "self_employed", "pension") else TIER3
        rows.append([
            f"<b>{esc(s)}</b><br><span class='note'>category "
            f"<code>{esc(N.INCOME_SOURCE_CATEGORY[s])}</code></span>",
            f"{share:.2f}",
            f"×{rel:.2f}",
            f"{sig:.2f}",
            eur(base_mean * mult, 0),
            tier,
        ])
    src_table = table(
        ["Primary income source", "share of<br>consumers", "level vs<br>mean (SHIW)",
         "σ (log)", "mean draw<br>per month", "provenance"],
        rows, "lrrrrl",
    )

    extra = table(
        ["Additional inflow", "Rule", "Value", "Where", "Provenance"],
        [
            ["<b>Tredicesima</b><br><span class='note'>13th-month bonus</span>",
             "December only, payroll &amp; pension recipients only — the month's credit doubles",
             "×2.0 in December",
             src("numbers.py:584-589"), TIER1],
            ["<b>Credit draw</b><br><span class='note'>borrowing, not earnings</span>",
             "subsisters only, when a bill is otherwise unaffordable; raises the debt principal "
             "by the same amount",
             f"ceiling {N.SUBSISTER_DEBT_CEILING_MULT:.0f}× the opening principal",
             src("model.py:566-595"), TIER3],
            ["<b>Opening buffer</b><br><span class='note'>a stock, not a flow</span>",
             "the current account starts with one month of income — <b>except subsisters</b>, "
             "who start at zero",
             "1.0 × monthly income", src("model.py:754-755"), TIER3],
        ], "lllll",
    )

    return section(
        "income", "Section A", "Where the money comes in",
        p("A household's income is drawn once, at construction, and then paid on "
          "<b>one day a month — the 27th</b> "
          f"({src('numbers.py:158')}, a stand-in for the last business day). There is no "
          "weekly or biweekly pay, no mid-month top-up, and no income shock during a run: "
          "employment status is fixed for the whole simulation."),
        p("Each source has its own mean <i>and</i> its own spread. The multipliers are "
          "<b>mean-preserving</b> — they are rescaled so the share-weighted population mean "
          "stays at the SHIW figure, which is what keeps the income quartile and quintile "
          f"bands (and therefore all the debt and savings calibration) undisturbed "
          f"({src('numbers.py:568-581')}, asserted at import)."),
        src_table,
        callout(
            "<b>The σ column is not from SHIW.</b> The survey gives each source's relative "
            "<i>mean</i>, never its dispersion. The spreads above are an assumed shape — "
            "self-employed widest, pensions tightest — and they drive how much overlap there "
            "is between sources in the realised population. They are swept, but they are not "
            "facts."),
        "<h3>Inflows that are not a primary salary</h3>",
        extra,
        callout(
            "<b>No taxes, no VAT, no social-security contributions, and no household-to-"
            "household transfers exist anywhere in the model.</b> SHIW incomes are already net "
            "of contributions, and the bank-eye framing puts tax out of scope. This is a scope "
            "decision, not an omission — but it means the model cannot say anything about "
            "fiscal policy, and the word 'income' here always means take-home.",
            "warn"),
    )


# --------------------------------------------------------------------------- #
# B — outflows
# --------------------------------------------------------------------------- #
def outflow_section() -> str:
    bill_rows = [
        [f"<b>{esc(b)}</b>", f"{spec['share']:.0%}", eur(spec["mean_eur"], 0),
         f"day {spec['day']}"]
        for b, spec in N.BILL_TYPES.items()
    ]
    bills = table(
        ["Recurring bill", "households<br>subscribing", "amount", "due"],
        bill_rows, "lrrr",
    )

    out_rows = [
        ["<b>Recurring bills</b>", "<code>bill</code>",
         "five types, each an independent coin-flip at construction",
         src("model.py:457-479"), TIER1],
        ["<b>Discretionary purchases</b>", "<code>purchase</code>",
         "a daily coin-flip scaled by the calendar; 10 categories, lognormal ticket",
         src("model.py:609-636"), TIER1],
        ["<b>Debt service</b>", "<code>bill</code>",
         f"once a month on day {N.DEBT_SERVICE_DAY_OF_MONTH}; the amount depends on the "
         "debtor archetype",
         src("model.py:516-562"), TIER3],
        ["<b>Overdraft fee</b>", "<code>fee</code>",
         f"flat {eur(N.OVERDRAFT_FEE_EUR, 0)} the moment a payment takes the balance below "
         "zero — paid to the bank",
         src("model.py:368-396"), TIER2],
        ["<b>Late-payment fee</b>", "<code>fee</code>",
         f"{N.LATE_PAYMENT_FEE_FRACTION:.0%} of the bill, added when an overdue bill is "
         "finally settled — paid to the original biller",
         src("model.py:483-512"), TIER2],
        ["<b>Savings sweep</b>", "<i>internal</i>",
         "month-end; the positive residual moves current → savings",
         src("model.py:416-453"), TIER3],
        ["<b>Pension sweep</b>", "<i>internal</i>",
         "the same amount, routed to the pension account instead",
         src("model.py:430-435"), TIER3],
        ["<b>Interest accrual</b>", "<i>none</i>",
         f"{N.DEBT_MONTHLY_INTEREST_RATE:.1%}/month on the outstanding principal — "
         "<b>the only flow that changes a stock without writing a transaction</b>",
         src("model.py:533-534"), TIER3],
    ]
    outs = table(
        ["Outflow", "ledger <code>kind</code>", "Rule", "Where", "Provenance"],
        out_rows, "lllll",
    )

    return section(
        "outflows", "Section B", "Where the money goes",
        p("Eight distinct outflows. Seven of them write a row to the transaction ledger; "
          "the eighth — interest — does not, which is why the money-conservation test still "
          "passes even though debt grows."),
        outs,
        "<h3>The five recurring bills</h3>",
        p("Subscription is an <b>independent</b> draw per bill, so a household can hold rent "
          "and a mortgage at once, or neither. The survey gives only the marginal shares; the "
          "independence is an assumption."),
        bills,
        callout(
            "<b>Bill amounts carry no dispersion.</b> Every utilities bill in the model is "
            f"exactly {eur(N.BILL_TYPES['utilities']['mean_eur'], 0)}, every month, for every "
            "household. Purchase tickets get a lognormal spread; bills get a point mass. "
            "Nothing in the survey requires this — it is a simplification, and it makes the "
            "monthly obligation far more predictable than a real one."),
        "<h3>Two overlapping views of debt</h3>",
        p("The model carries <b>both</b> the <code>mortgage</code> / "
          "<code>consumer_loan</code> recurring bills (Payment Behaviour Survey) <b>and</b> a "
          "separate aggregate <code>debt_service</code> line (SHIW). They come from different "
          "surveys, measure overlapping things, and are deliberately not reconciled. A "
          "household can pay both. This is documented as a teaching-prototype simplification, "
          "but it does mean total debt burden is overstated for anyone holding both."),
    )


# --------------------------------------------------------------------------- #
# C — the tick
# --------------------------------------------------------------------------- #
def tick_section() -> str:
    day = steps([
        "<b>Income sources run first</b>, so a household paid today can spend today. "
        f"{src('model.py:843')}",
        "<b>Consumers run in shuffled order</b>, so nobody is permanently first in the queue. "
        f"{src('model.py:844')}",
        "Daily KPIs and grouped mean balances are snapshotted, then the DataCollector reads "
        f"them. {src('model.py:847-854')}",
        f"The calendar advances one day. {src('model.py:857')}",
    ])
    consumer = steps([
        "<b>Month-close</b> — on day 1 only, sweep last month's residual into savings or "
        "pension, then zero the accumulators. Runs <i>before</i> bills so a day-1 bill like "
        f"rent counts toward the new month. {src('model.py:405-406')}",
        "<b>Settle overdue bills</b> — retry anything carried over, paying the bill plus the "
        f"late fee if it is now affordable. {src('model.py:409')}",
        f"<b>Pay today's due bills</b> — whichever bills fall on this day-of-month. "
        f"{src('model.py:410')}",
        f"<b>Service the debt</b> — on day {N.DEBT_SERVICE_DAY_OF_MONTH} only. "
        f"{src('model.py:411')}",
        "<b>Maybe buy something</b> — a single discretionary purchase, at most one per day. "
        f"{src('model.py:412')}",
    ])

    shortfall = table(
        ["When this cannot be afforded…", "…this happens", "Consequence"],
        [
            ["a <b>recurring bill</b>",
             "a subsister draws credit to close the gap; everyone else defers it to an "
             "overdue queue",
             "the deferred bill later costs "
             f"{N.LATE_PAYMENT_FEE_FRACTION:.0%} more"],
            ["an <b>overdue bill</b>, still",
             "it keeps being retried daily, and is written off after 90 days",
             "the queue cannot grow without bound; the debt silently disappears"],
            ["the <b>monthly debt service</b>",
             "the payment is skipped entirely — there is no partial payment",
             "<b>but interest has already accrued</b>, so the principal grows"],
            ["a <b>discretionary purchase</b>",
             "it is silently skipped",
             "no fee, no queue, no trace in the ledger"],
        ], "lll",
    )

    return section(
        "tick", "Section C", "The order things happen in",
        p("Order matters here more than it looks. Obligations are always settled before "
          "discretionary spending, and the month closes before the first bill of the new "
          "month — both are behavioural claims baked into the loop, and neither is cited."),
        "<h3>A model day</h3>", day,
        "<h3>A household's day</h3>", consumer,
        "<h3>The affordability gate</h3>",
        p(f"Every outflow passes one test, {src('model.py:322-333')}. It reserves room for "
          "the overdraft fee <i>before</i> allowing the payment, so the floor holds including "
          "fees:"),
        pre(
            "projected = self.account.balance - amount\n"
            "if self.account.balance >= 0 and projected < 0:\n"
            "    projected -= numbers.OVERDRAFT_FEE_EUR   # reserve room for the fee\n"
            "return projected >= self._overdraft_floor"
        ),
        p("The floor is <code>0.0</code> for everyone except chronic debtors, who may go one "
          "month's debt service negative. So only chronics can ever pay an overdraft fee — "
          "for everyone else the balance simply cannot cross zero."),
        "<h3>What happens on a shortfall</h3>", shortfall,
    )


# --------------------------------------------------------------------------- #
# D — stocks vs flows
# --------------------------------------------------------------------------- #
def stock_flow_section() -> str:
    t = table(
        ["", "Variable", "Where", "Note"],
        [
            ["<b>Stock</b>", "<code>BankAccount.balance</code> × 3 per household",
             src("model.py:63-78"), "current, savings, pension"],
            ["<b>Stock</b>", "<code>Consumer.debt_balance</code>", src("model.py:284"),
             "the outstanding principal — <b>a modelling construct</b>, see Section F"],
            ["<b>Stock</b>", "<code>_overdue_bills</code>", src("model.py:310"),
             "the arrears queue"],
            ["<b>Stock</b>", "<code>_overdraft_floor</code>", src("model.py:294"),
             "how far below zero this household may go"],
            ["<b>Flow</b>", "<code>_m_income / _m_bills / _m_debt / _m_disc</code>",
             src("model.py:302-305"), "monthly accumulators, reset at month-close"],
            ["<b>Flow</b>", "<code>model.transactions</code>", src("model.py:970-994"),
             "the flat ledger — one row per money movement"],
        ], "llll",
    )
    return section(
        "stocks", "Section D", "Stocks, flows, and what conserves",
        t,
        callout(
            "<b>Money is conserved system-wide.</b> Every movement is a paired debit and "
            "credit — including the savings sweep (internal, same owner) and the credit draw "
            "(lender → household). The sum of all balances equals the sum of all opening "
            "balances, tested in <code>tests/test_conservation.py</code>. Interest is the one "
            "exception, and it conserves precisely <i>because</i> it writes no transaction: "
            "it moves a number, not money.", "ok"),
        callout(
            "<b>An accounting asymmetry worth knowing about.</b> The month-end residual is "
            "<code>income − bills − debt − discretionary</code> "
            f"({src('model.py:426')}). Overdraft fees are <i>not</i> subtracted, and credit "
            "draws are <i>not</i> added to income. So a household that paid fees all month "
            "computes a residual slightly larger than what actually happened. The "
            "<code>min(residual, balance)</code> cap is what stops this over-sweeping in "
            "practice — it is a guard, not a correction.", "warn"),
    )


# --------------------------------------------------------------------------- #
# E — paper map
# --------------------------------------------------------------------------- #
def paper_map_section() -> str:
    rows = [
        ["<b>ISTAT</b><br><span class='note'>resident population 2022</span>",
         "macro-area population weights",
         " / ".join(f"{v:.2f}" for v in N.MACRO_AREA_WEIGHTS.values()),
         src("numbers.py MACRO_AREA_WEIGHTS"), TIER1],
        ["<b>Semeraro et al. (2020)</b><br><span class='note'>wire-transfer network</span>",
         "macro-area income gradient",
         " / ".join(f"{v:.3f}" for v in N.MACRO_AREA_INCOME_RELATIVE.values())
         + " (South &minus;44.6% vs Centre-North, p.5/p.27)",
         src("numbers.py MACRO_AREA_INCOME_RELATIVE"), TIER1],
        ["<b>Emiliozzi et al. (2023)</b><br><span class='note'>Italian credit-card data</span>",
         "10 spending category shares", "retail .26 … services .04",
         src("numbers.py:64"), TIER1],
        ["", "ticket-size distributions", "10 lognormal (μ, σ) pairs",
         src("numbers.py:81"), TIER1],
        ["", "weekday / month / holiday calendar",
         "Sat ×1.20 · Dec ×1.25 · Aug ×0.85 · Christmas ×1.40",
         src("numbers.py:97-113"), TIER1],
        ["<b>SHIW 2022</b><br><span class='note'>Survey on Household Income &amp; Wealth</span>",
         "income level by source", "×1.08 / ×1.49 / ×0.82", src("numbers.py:322-324"), TIER1],
        ["", "debt participation by quartile", "12.0% / 19.2% / 24.4% / 28.5%",
         src("numbers.py:165"), TIER1],
        ["", "annual debt service by quartile", "€3,754 / 4,763 / 5,576 / 8,718",
         src("numbers.py:171"), TIER1],
        ["", "probability of not saving, by quintile", "0.70 / .595 / .490 / .385 / 0.28",
         src("numbers.py:196"), TIER1],
        ["", "the financial-vulnerability definition",
         "income below median <b>and</b> debt-service ratio &gt; 30%",
         src("model.py:1055-1061"), TIER1],
        ["<b>Payment Behaviour Survey</b><br><span class='note'>Bank of Italy / ECB SPACE</span>",
         "the five recurring bills", "share, amount and due-day each",
         src("numbers.py:120"), TIER1],
        ["", "absolute income bands", "≤€1,000 / €1,000–4,000 / &gt;€4,000",
         src("numbers.py:149"), TIER1],
        ["<b>Structural inequalities</b><br><span class='note'>wire-transfer network</span>",
         "the payday rule", "the 27th", src("numbers.py:158"), TIER1],
        ["", "the December <i>tredicesima</i>", "×2.0, payroll &amp; pension",
         src("numbers.py:383-384"), TIER1],
        ["<b>Olafsson &amp; Pagel (2018)</b>", "post-payday spending spike",
         f"peak ×{N.PAYDAY_SPIKE_PEAK}, mean-neutral", src("numbers.py:295"), TIER2],
        ["<b>Stango &amp; Zinman (2014)</b>", "flat overdraft fee",
         eur(N.OVERDRAFT_FEE_EUR, 0) + " per event", src("numbers.py:304"), TIER2],
        ["<b>Dahan &amp; Nisan (2020)</b>", "late-payment penalty",
         f"{N.LATE_PAYMENT_FEE_FRACTION:.0%} of the bill", src("numbers.py:313"), TIER2],
        ["<b>Campbell (2006)</b>", "fees concentrate among the vulnerable",
         "<i>direction of the chronic tilt only — no magnitude</i>",
         src("numbers.py:234"), TIER2],
        ["<b>Jiang et al. (2022)</b>", "synthetic-population method",
         "<i>not implemented in the active model</i>", "—", TIERM],
        ["<b>Grimm et al. (2010)</b>", "the ODD documentation protocol",
         "<i>documentation format; adopted after the model was built</i>", "—", TIERM],
    ]
    return section(
        "papers", "Section E", "Which paper justifies which effect",
        p("Read this next to Section F. This table is what the model <i>does</i> take from "
          "the literature; the next section is what it does not."),
        table(["Paper", "Effect in the model", "Value", "Where", "Tier"], rows, "lllll"),
        callout(
            "<b>Three of the five saver probabilities are interpolated, not observed.</b> "
            "SHIW reports the first and fifth quintiles (0.70 and 0.28); Q2–Q4 are a straight "
            "linear fill between them. The code marks them; the tier tables in the docs list "
            "the whole vector as calibrated. Worth one honest sentence in the thesis."),
    )


# --------------------------------------------------------------------------- #
# F — the gap audit
# --------------------------------------------------------------------------- #
SEV = {
    "must": '<span class="pill warn">must fix</span>',
    "sentence": '<span class="pill">needs a sentence</span>',
    "ok": '<span class="pill mute">defensible</span>',
}

# (severity, what, detail, where)
PAPER_GAPS = [
    ("ok", "RESOLVED — the North–South income gradient is now implemented",
     "For most of this project's life, <b>five</b> documents (not the four this entry used to "
     "claim) credited the wire-transfer paper with a North–South income gradient that did not "
     "exist: <code>sample_income_for_source()</code> took no area argument, and area affected "
     "headcount and merchant routing only. It is now real — "
     "<code>MACRO_AREA_INCOME_RELATIVE</code> puts the South at 0.554&times; Centre-North "
     "(Semeraro et al. 2020 p.5 / p.27), applied mean-preservingly so the population mean and "
     "the SHIW band calibration are undisturbed. Two things came out of fixing it: the "
     "macro-area weights were card-<i>spend</i> midpoints mis-cited to a nonexistent "
     "Emiliozzi §6, now ISTAT population shares; and the gradient raises income dispersion "
     "(Gini 0.30 &rarr; 0.34), which re-pinned 10 of the 21 headline validation numbers. A "
     "later change — the category-share units fix below — re-pinned six more, so the "
     "attribution block above <code>EXPECTED</code> now carries four named causes.",
     "numbers.py MACRO_AREA_INCOME_RELATIVE · model.py consumer construction"),
    ("sentence", "A calibrated constant that nothing reads",
     "<code>DEBT_PAYMENT_DIRECT_DEBIT</code> holds real Payment Behaviour Survey figures "
     "(mortgage 57.1%, consumer loan 65.0%) and has <b>zero readers</b> across the whole "
     "repo. The comment admits the prototype does not route by payment instrument.",
     "numbers.py:182"),
    ("ok", "A SHIW-cited sampler that is never called",
     "<code>sample_income()</code> draws from the SHIW lognormal and is superseded by "
     "<code>sample_income_for_source()</code>. Dead, but harmless.",
     "numbers.py:523"),
    ("sentence", "The Payment Behaviour Survey's actual subject is unused",
     "The survey is <i>about</i> payment instruments — cash vs card, POS vs online vs P2P, "
     "by age, education, income and region. The model uses its bill table and its income "
     "bands, and nothing else. There is no payment-instrument dimension in the model at all.",
     "italy_papers/notes on each paper/population_behaviours_notes.txt"),
    ("sentence", "Most of the wire-transfer paper is unused",
     "It supplies degree distributions, assortativity, bow-tie structure and sectoral flows. "
     "Two things reach the code: the payday date and the December bonus.",
     "numbers.py:158, 383"),
    ("ok", "Two papers read but never wired in",
     "Prelec &amp; Simester (2001) on the credit-card willingness-to-pay effect needs a "
     "payment-method layer that does not exist. Le Blanc et al. on euro-area household saving "
     "was set aside because saving here is emergent and SHIW-calibrated. Both are recorded as "
     "read-but-not-implemented, so neither looks wired in.",
     "docs/REFERENCES.md"),
    ("sentence", "The method paper is not implemented in the shipped model",
     "Jiang et al. (2022) is the thesis's method paper. <code>_build_visual_graph()</code> "
     "builds a graph for the dashboard only — it is never mutated and no agent reads it. The "
     "real implementation is parked in the private development repository, not published here.",
     "model.py:1098-1143"),
    ("ok", "Mesa 3 (JOSS 2025) now has its citation",
     "It was the framework the model is built on but appeared in no source table. It is now "
     "listed under the method tier, where the tool deserves its citation.",
     "docs/REFERENCES.md"),
    ("sentence", "SHIW figures that exist in the notes but reached no constant",
     "Gini 0.336, bottom/top decile income shares (2.4% / 27.9%), the deposit-share-by-wealth-"
     "decile table, and the OECD-modified equivalence scale. The first two are <b>validation "
     "targets the model could be scored against</b> and currently is not.",
     "italy_papers/notes on each paper/household_income_survey_notes.txt"),
    ("sentence", "The card paper's own validation checklist is never run",
     "Its notes end with a checklist — long-run trend, weekday structure, Christmas peak, "
     "regional concentration, daily-vs-weekly volatility. The repo checks category shares and "
     "area weights; the rest is unchecked.",
     "italy_papers/notes on each paper/consumption-paper-notes.txt"),
]

CODE_GAPS = [
    ("must", "<code>base_prob = 0.6</code> — the biggest uncited number in the model",
     "This single literal sets how often <i>anyone</i> buys anything, so it determines total "
     "transaction volume and therefore every euro aggregate on every figure. Its own comment "
     "calls it “a <i>tuning knob</i>”. It is hard-coded in <code>model.py</code>, which "
     "violates that file's stated contract that <i>all empirical numbers live in "
     "numbers.py</i>; it is absent from every ⚠ table in the docs; and it is not in the "
     "sensitivity sweep. Every category-share and ticket-size calibration is conditional on "
     "it.",
     "model.py:617"),
    ("ok", "RESOLVED — CATEGORY_SHARES were euro shares used as selection probabilities",
     "<b>Fixed.</b> The shares are shares of <i>euros</i> (Emiliozzi et al. §2.1, Fig. 4 — "
     "“Average shares of expenditure categories”, benchmarked in Fig. 6 against COICOP "
     "national-accounts expenditure). <code>sample_category()</code> used them directly as "
     "the probability of picking a category and then drew the ticket independently, so the "
     "model matched the paper on transaction <i>counts</i> and missed on euros: travel took "
     "<b>19.8%</b> of euros against the paper's 9.0%, a 10.8pp error. f02 had been plotting "
     "that gap as a calibration imperfection. Selection is now p ∝ share ÷ E[ticket], which "
     "makes the realised euro shares equal the paper's by construction; the residual on a "
     "real run is 0.6pp, all of it lognormal sampling noise. Cost: the constant no longer "
     "doubles as the count distribution, and euro throughput per transaction fell ~16%.",
     "numbers.py:_category_selection_probs"),
    ("ok", "RESOLVED — the “overall mean €28” attributed to the paper is not in the paper",
     "<b>Fixed.</b> <code>CATEGORY_TICKET_LOGNORMAL</code> cited an “overall mean €28” to "
     "Emiliozzi et al. §9. The paper runs §1–§5 plus appendices — there is no §9 — and no "
     "such euro figure appears anywhere in it. The citation is removed; the parameters are "
     "now attributed to BoI POS averages alone, which is where they actually came from. For "
     "the record the share-weighted mean is <b>€38.06</b> after the units fix (€45.53 "
     "before), and a real run measures <b>€36.73</b>. Neither is €28, and €28 was never "
     "citable.",
     "numbers.py:91-99"),
    ("sentence", "Starting balance = exactly one month's income",
     "It sets how often anyone crosses zero, so it co-determines the overdraft-fee rate and "
     "the late-payment rate — i.e. it silently scales two of the three behavioural results. "
     "SHIW's deposit-share-by-wealth-decile table could ground it and is unused.",
     "model.py:754-755"),
    ("sentence", "Subsisters are forced to be savers",
     "This overrides the SHIW quintile probability for an entire cohort, and it is the "
     "documented cause of a known pathology: over a long run the hand-to-mouth subsisters end "
     "up the <i>richest</i> savers in the model. It also entangles the saver and debtor "
     "labels — subsisters are 100% savers by construction.",
     "model.py:1092-1096"),
    ("sentence", "The 90-day write-off of unpaid bills",
     "A bare literal with no constant name and no source. It decides how much unpaid debt "
     "quietly evaporates. Dahan &amp; Nisan gives the penalty rate, not an arrears horizon.",
     "model.py:509-511"),
    ("sentence", "Debt service is all-or-nothing",
     "If the full scheduled repayment is unaffordable, nothing is paid — no partial payment, "
     "no arrears queue (unlike bills, which do queue). Interest still accrues, so the "
     "principal grows.",
     "model.py:544-551"),
    ("sentence", "Leaving debt is permanent and irreversible",
     "A household whose principal reaches zero has its debt flag and overdraft permission "
     "withdrawn for good and can never borrow again. No re-entry into debt is possible.",
     "model.py:552-559"),
    ("ok", "The chronic overdraft floor",
     "Set to one month's debt service below zero. Self-flagged as having no paper — but "
     "unlike the three behavioural magnitudes it is not in the sweep, and it jointly "
     "determines fee incidence with the €30 fee.",
     "model.py:1066-1070"),
    ("ok", "Spending is independent of who is spending",
     "<code>sample_category()</code> and <code>sample_ticket()</code> take only the random "
     "generator. A low-income pensioner and a high-income self-employed household draw from "
     "the identical category mix and the identical ticket distribution — there is no "
     "consumption function. Recorded as a known limitation.",
     "numbers.py:491-505"),
    ("ok", "Merchant choice is uniform random with no memory",
     "Picked fresh from the pool on every purchase. The pool size of 3 is justified in a "
     "comment as letting households “plausibly repeat-visit several shops”, but nothing "
     "implements loyalty or repeat visits.",
     "model.py:996-1003"),
    ("ok", "Obligations always precede discretionary spending",
     "A behavioural claim — no impulse purchase ever jumps ahead of a due bill — fixed by the "
     "order of the day loop and never cited.",
     "model.py:400-412"),
    ("ok", "Employment is static",
     "No job loss, no job gain, no income shock, no transition between income sources during "
     "a run. Acknowledged in prose, never flagged at the code.",
     "model.py"),
]


def gap_table(items) -> str:
    return table(
        ["Severity", "Gap", "Why it matters", "Where"],
        [[SEV[s], f"<b>{w}</b>", d, src(where)] for s, w, d, where in items],
        "llll",
    )


def gaps_section() -> str:
    n_must = sum(1 for g in PAPER_GAPS + CODE_GAPS if g[0] == "must")
    n_sent = sum(1 for g in PAPER_GAPS + CODE_GAPS if g[0] == "sentence")
    n_ok = sum(1 for g in PAPER_GAPS + CODE_GAPS if g[0] == "ok")
    return section(
        "gaps", "Section F", "The gap audit — both directions",
        p("A model described as “calibrated to four Italian papers” invites two questions. "
          "What do those papers offer that the model doesn't take? And what does the model do "
          "that no paper backs? Both lists are below."),
        tiles([
            ("must fix", str(n_must), "before submission"),
            ("needs a sentence", str(n_sent), "declare and move on"),
            ("defensible", str(n_ok), "already documented, or harmless"),
        ]),
        callout(
            "<b>Severity is about the thesis, not the code.</b> “Must fix” means a reader "
            "could reasonably call the current text wrong. “Needs a sentence” means the "
            "choice is fine but currently invisible — declaring it costs a line and closes "
            "the hole. Nothing here is a bug in the sense of the model misbehaving; the tests "
            "pass and money conserves."),
        "<h3>F1 · What the papers offer that the model does not use</h3>",
        gap_table(PAPER_GAPS),
        "<h3>F2 · What the model does that no paper backs</h3>",
        p("The repo is unusually honest about this already — most of these carry a ⚠ comment "
          "at the point of use. The two marked <b>must fix</b> are the ones that are not "
          "flagged anywhere and that change numbers a reader will see."),
        gap_table(CODE_GAPS),
        callout(
            "<b>What this section is not saying.</b> A modelling choice is not a flaw; every "
            "ABM is mostly choices. The claim is narrower: a choice that is <i>presented as "
            "calibration</i> is a problem, and a choice that drives a headline number while "
            "sitting outside the sweep is a problem. Those are the two marked must-fix. The "
            "rest simply need to be visible."),
    )


# --------------------------------------------------------------------------- #
def build(generated: str) -> str:
    links = [
        ("income", "A · Income"), ("outflows", "B · Outflows"), ("tick", "C · The tick"),
        ("stocks", "D · Stocks & flows"), ("papers", "E · Paper map"),
        ("gaps", "F · Gap audit"),
    ]
    body = "".join([
        income_section(), outflow_section(), tick_section(),
        stock_flow_section(), paper_map_section(), gaps_section(),
    ])
    return page(
        title="synthitaly — money flows &amp; paper provenance",
        heading="Money flows &amp; paper provenance",
        sub="Every income source, every payment, the order they happen in — and an honest "
            "audit of where the papers and the code fail to meet.",
        meta=f"Generated {generated} · values read live from "
             f"<code>src/synthitaly/numbers.py</code> · reproduce with "
             f"<code>uv run python scripts/build_flows_page.py</code>",
        navbar=nav(links),
        body=body,
        footer="synthitaly · this page is self-contained (no network requests) · "
               "companion pages: <code>savers_and_debt.html</code>, "
               "<code>data_appendix.html</code>, <code>results.html</code>",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=Path("runs/latest"), type=Path)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / "flows_and_papers.html"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    out.write_text(build(esc(stamp)), encoding="utf-8")
    print(f"wrote {out}  ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
