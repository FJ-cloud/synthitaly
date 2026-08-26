"""
numbers.py — every Italy-specific number in one place.

This file is the *only* place where empirical constants from the source papers
live. The model in ``model.py`` reads them; the notebook reads them; the
Solara app reads them. Nothing is computed here — these are values you can
trace back to a paper PDF in ``italy_papers/``.

Three things live in this file:
    1. CONSTANTS  — dicts of numbers, with the paper + section they came from
    2. CALENDAR HELPERS  — small functions (is_payday, is_holiday, etc.)
    3. SAMPLERS  — three tiny functions that draw a category, a ticket size,
                   and a daily intensity multiplier

If you change a number here, the new value flows through to the whole model.

SOURCE KEY — the short names used in the comments below, in full:

    Emiliozzi et al. (2023)
        Emiliozzi, S., Rondinelli, C. & Villa, S. (2023). "Consumption during
        the Covid-19 pandemic: evidence from Italian credit cards." Banca
        d'Italia, Questioni di Economia e Finanza (Occasional Papers) No. 769,
        May 2023.  ``italy_papers/Consumption during the Covid-19 pandemic…pdf``
    SHIW 2022
        Banca d'Italia (2024). "Survey on Household Income and Wealth — 2022."
    Payment Behaviour Survey 2023-24
        Banca d'Italia. "Report on the payment attitudes of consumers in Italy"
        (ECB SPACE 2024 survey; fieldwork Sep 2023 – Jun 2024).
    structural-inequalities paper
        Semeraro, A. et al. (2020). "Structural inequalities emerging from a
        large wire transfers network." Applied Network Science 5:76.

SECTION ANCHORS FOR EMILIOZZI ET AL., VERIFIED against the PDF in
``italy_papers/``. The structure is:

    1 Introduction
    2 Credit-cards transaction data
      2.1 A preliminary look at the data      <- Figures 1-7 are discussed here
    3 The event study approach
    4 The effects of the COVID-19 pandemic on credit-card transactions
      4.1 Exploring the expenditure categories
      4.2 Exploring the regional dimension
    5 Conclusions
    References, Appendix A, Appendix B

There is no §6, §9 or §11. Anchors pointing at those were carried over from an
earlier draft that also misnamed the paper; each one has now been either
re-anchored or removed, and the constant it labelled reattributed to whatever
actually supports it. Where nothing does, the comment says so.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np

# ============================================================================
# 1. CONSTANTS
# ============================================================================

# ---- Macro-area population weights ----------------------------------------
# Source: ISTAT resident population by macro-area (2022). Same values the parked
# population-synthesis module already uses (MACRO_AREA_POPULATION_SHARES there).
# These are the share of *people*.
#
# CORRECTION (was 0.50 / 0.27 / 0.23, cited as "Emiliozzi et al. (2023) §6"):
# that citation was wrong twice over. The paper has no §6 — it runs §1-5 plus
# appendices A-B — and its only regional table, B.2, is a cumulative-COVID-loss
# share which rolls up to 54.7 / 25.5 / 19.8, not 50 / 27 / 23. The old numbers
# were midpoints of the paper's card-SPEND heatmap bands, mislabelled as
# population. Card spend per area is a different quantity from people per area
# (Emiliozzi's own notes warn against the substitution: spend ~ population x
# income x tourism x card adoption), and the substitution put CENTRE above
# SOUTH, which is the reverse of the real population ordering.
#
# Card-spend intensity by macro-area is not modelled. If it is added later it
# needs its own constant, not this one.
MACRO_AREA_WEIGHTS: dict[str, float] = {
    "NORTH":  0.46,
    "CENTRE": 0.20,
    "SOUTH":  0.34,
}

# ---- Spending categories ---------------------------------------------------
# Source: Emiliozzi et al. (2023) §2.1, Figures 4 and 6 — "Average shares of
# expenditure categories", 2015-2019 baseline, before COVID. Figure 6 compares
# these against COICOP national-accounts expenditure, so they are shares of
# EUROS SPENT, not of transaction counts. sample_category() converts them to
# selection probabilities; see the note there.
#
# The paper's Figure 4 has nine bands; `home` and `repairs` are merged there and
# are split here by hand. `repairs`, `cash_advance` and `services` therefore have
# no directly traceable source value.
CATEGORY_SHARES: dict[str, float] = {
    "retail":       0.26,
    "food":         0.20,
    "hotels_rest":  0.11,
    "travel":       0.09,
    "clothing":     0.08,
    "home":         0.07,
    "phones_web":   0.05,
    "repairs":      0.05,
    "cash_advance": 0.05,
    "services":     0.04,
}

# ---- Ticket sizes per category --------------------------------------------
# Source: BoI POS averages. Each pair is (mu, sigma) of a lognormal distribution;
# expected EUR ticket is exp(mu + sigma^2 / 2). e.g. retail (3.0, 0.9) -> ~€30.
#
# These were previously attributed to Emiliozzi et al. (2023) §9 as an "overall
# mean €28". The paper has no §9 — it runs §1-§5 plus appendices — and no such
# euro figure appears anywhere in it. The share-weighted mean ticket implied by
# CATEGORY_SHARES and these parameters is ~€38.
CATEGORY_TICKET_LOGNORMAL: dict[str, tuple[float, float]] = {
    "retail":       (3.0, 0.9),
    "food":         (3.2, 0.6),
    "hotels_rest":  (3.4, 0.7),
    "travel":       (4.0, 1.1),
    "clothing":     (3.6, 0.8),
    "home":         (3.5, 1.0),
    "phones_web":   (3.0, 0.7),
    "repairs":      (3.8, 1.2),
    "cash_advance": (4.0, 0.5),
    "services":     (3.4, 0.9),
}

# ---- Seasonality multipliers ----------------------------------------------
# Direction from Emiliozzi et al. (2023); MAGNITUDES ARE THIS MODEL'S OWN.
#
# These used to be cited to "§3 + §11". The paper has neither a §11 nor any table
# of weekday or month multipliers. What it actually supports:
#   * §2 — "a clear seasonal pattern emerges with the week including Christmas
#     being the one" with the highest transaction volume. That grounds the sign
#     of CHRISTMAS_WINDOW_MULTIPLIER and the December peak, not their size.
#   * §3 — the event-study specification "includes weekday fixed effects", which
#     establishes that a day-of-week effect exists and is large enough to control
#     for. It reports no coefficients, so the Fri/Sat values below are a choice.
# The August dip has no support in this paper at all; it is the standard Italian
# summer shutdown, asserted here without a citation.
#
# All of these are swept in the sensitivity analysis for exactly this reason.
WEEKDAY_MULTIPLIER: dict[int, float] = {
    0: 0.95,  # Mon
    1: 0.95,  # Tue
    2: 0.95,  # Wed
    3: 1.00,  # Thu
    4: 1.10,  # Fri
    5: 1.20,  # Sat
    6: 1.00,  # Sun
}

MONTH_MULTIPLIER: dict[int, float] = {
    1: 0.95, 2: 0.92, 3: 0.98, 4: 1.02, 5: 1.00, 6: 1.02,
    7: 1.08, 8: 0.85, 9: 0.95, 10: 1.00, 11: 1.05, 12: 1.25,
}

HOLIDAY_MULTIPLIER: float = 1.15           # generic public-holiday bump
CHRISTMAS_WINDOW_MULTIPLIER: float = 1.40  # Dec 20–31 extra peak

# ---- Recurring bills -------------------------------------------------------
# Source: Bank of Italy 2023-24 Payment Behaviour Survey §8 (30-day diary).
# (share-of-households, mean-amount-EUR, day-of-month-due) per bill type.
# Only the four most common bills are kept — the full nine live in the parked
# prototype, which is not published here.
BILL_TYPES: dict[str, dict[str, float | int]] = {
    "utilities":     {"share": 0.73, "mean_eur": 124.0, "day": 10},
    "telecom":       {"share": 0.70, "mean_eur":  40.0, "day": 15},
    "rent":          {"share": 0.24, "mean_eur": 440.0, "day":  1},
    "mortgage":      {"share": 0.19, "mean_eur": 489.0, "day":  5},
    # consumer_loan = "paying back debt / consumer loans" line of the same
    # survey (§8). Its day-of-month is not in any paper — kept distinct from
    # the others as a modelling choice.
    "consumer_loan": {"share": 0.14, "mean_eur": 198.0, "day": 20},
}

# ---- Income -----------------------------------------------------------------
# Source: SHIW 2022 — Italian net household monthly income, very simplified.
# We use a single lognormal for adult monthly net income (mu, sigma on log
# scale). exp(mu + sigma^2/2) ~ €2,000.
INCOME_LOGNORMAL: tuple[float, float] = (7.4, 0.55)

# ---- Income LEVEL bands (low / middle / high) ------------------------------
# Source: Bank of Italy 2023-24 Payment Behaviour Survey — the survey groups
# respondents into four MONTHLY net-income bands (≤€1,000 / €1,001–€2,500 /
# €2,501–€4,000 / >€4,000) and conditions payment behaviour on them. We collapse
# those four survey bands into three presentation levels — the only modelling
# choice here is the 4→3 collapse:
#     low    ≤ €1,000 / month   (the survey's lowest band, its "low income" group)
#     middle   €1,000 – €4,000  (the two middle survey bands merged)
#     high   > €4,000 / month   (the survey's top band)
# These are ABSOLUTE euro cut-points (not percentiles of the realised run), so a
# household is "low income" in the survey's own absolute sense. Distinct from the
# empirical income_quartile/quintile bands, which stay SHIW-percentile-based.
INCOME_LEVEL_BANDS_EUR: dict[str, float] = {
    "low_max":  1_000.0,   # ≤ this monthly net income → "low"
    "high_min": 4_000.0,   # > this monthly net income → "high"
}

# Italian "payday" rule:
# Salaries are paid on the last business day of the month (structural-
# inequalities paper §9). To keep this prototype simple, we use the 27th
# of the month — close enough to end-of-month for visualization purposes.
PAYDAY_DAY_OF_MONTH: int = 27

# ---- Debt ------------------------------------------------------------------
# Source: SHIW 2022 §3 (debt and financial vulnerability) — share of
# households with any debt, and mean annual debt service, by equivalized-
# income quartile (Q1 = poorest .. Q4 = richest). See
# ``italy_papers/notes on each paper/household_income_survey_notes.txt``.
DEBT_PROBABILITY_BY_INCOME_QUARTILE: dict[int, float] = {
    1: 0.120,
    2: 0.192,
    3: 0.244,
    4: 0.285,
}
DEBT_SERVICE_MEAN_BY_QUARTILE_EUR: dict[int, float] = {
    1: 3_754.0,
    2: 4_763.0,
    3: 5_576.0,
    4: 8_718.0,
}

# Share paid by direct debit for the two debt-repayment bills.
# Source: BoI 2023-24 Payment Behaviour Survey §8.2 (recurring-bill method
# by bill type). Reference figures used by the reference card / docs; the
# prototype does not yet route by payment instrument.
DEBT_PAYMENT_DIRECT_DEBIT: dict[str, float] = {
    "mortgage":      0.571,
    "consumer_loan": 0.650,
}

# No paper gives a day-of-month for aggregate debt service; like PAYDAY this
# is a modelling choice, kept clear of the bill days (rent 1, mortgage 5,
# utilities 10, telecom 15, consumer_loan 20).
DEBT_SERVICE_DAY_OF_MONTH: int = 25

# ---- Savings ---------------------------------------------------------------
# Source: SHIW 2022 §2F — probability a household *did not save* during the
# year, by income quintile. SHIW reports only Q1 (0.70) and Q5 (0.28)
# directly; Q2–Q4 are a documented linear interpolation between them.
P_NO_SAVING_BY_INCOME_QUINTILE: dict[int, float] = {
    1: 0.70,
    2: 0.595,   # interpolated
    3: 0.490,   # interpolated
    4: 0.385,   # interpolated
    5: 0.28,
}
# Spread of the per-household debt-service draw around the SHIW quartile mean.
# Only the *shape* is assumed (right-skewed); the mean is the SHIW figure.
# Matches the lognormal-shape convention already used for ticket sizes.
DEBT_SERVICE_LOGNORMAL_SIGMA: float = 0.5

# ---- Debtor subtypes (debt as a stock) -------------------------------------
# BRIGHT LINE: SHIW gives debt *participation* and annual debt *service* (a flow)
# — never a principal stock, an interest rate, or behavioural repayment
# archetypes. Everything in this block is a MODELLING CHOICE: the *shape* is
# grounded in the supervisor's three requested debtor trajectories, the
# *magnitude* is ours and is meant to be swept (see scripts/sweep_behavioural.py).
# None of it is an Italian fact.
#
#   climber   — digs out: repays more than the interest, principal falls to
#               zero, then leaves debt.
#   chronic   — always in debt: repays roughly the interest, principal stays
#               flat, runs a standing overdraft.
#   subsister — ekes out at ~0: borrows small amounts to cover shortfalls so
#               the current account hugs zero; principal drifts up slowly.
DEBTOR_SUBTYPES: tuple[str, ...] = ("climber", "chronic", "subsister")

# Split of the SHIW-flagged debtor population into the three archetypes. This
# does NOT change who holds debt (that stays the SHIW quartile roll) — it only
# partitions the debtors that roll already produces.
#
# GROUNDING (the one thing here that *is* anchored to SHIW): the split is tilted
# by SHIW 2022 §3's own "financially vulnerable" definition — equivalized income
# *below median* AND debt-service ratio *> 30%*. Vulnerable debtors are drawn
# chronic-heavy (they get stuck: interest-only, standing overdraft, never dig
# out); resilient debtors are drawn climber-heavy (they repay and leave debt).
# This concentrates the chronic cohort among low-income, high-burden households
# (Campbell 2006: fees/mistakes concentrate there; Olafsson & Pagel 2018:
# liquid hand-to-mouth) so "chronically indebted" actually *looks* distressed,
# rather than landing on comfortable high-earners. The magnitudes below are a
# MODELLING CHOICE (sweepable); only the *direction* of the tilt is SHIW-grounded.
DEBTOR_SUBTYPE_SHARE_VULNERABLE: dict[str, float] = {
    "climber":   0.10,
    "chronic":   0.60,
    "subsister": 0.30,
}
DEBTOR_SUBTYPE_SHARE_RESILIENT: dict[str, float] = {
    "climber":   0.60,
    "chronic":   0.15,
    "subsister": 0.25,
}
# Kept for reference / the reference card: the blended population target if the
# two groups were equally sized. Not used to draw subtypes anymore.
DEBTOR_SUBTYPE_SHARE: dict[str, float] = {
    "climber":   0.35,
    "chronic":   0.375,
    "subsister": 0.275,
}

# Monthly interest accrued on the outstanding principal (~6.2%/yr consumer
# credit). A modelling choice — no Italian paper gives a household debt rate.
DEBT_MONTHLY_INTEREST_RATE: float = 0.005

# Opening principal = the consumer's monthly scheduled service × this many
# months. A debtor who pays exactly the SHIW service then clears in roughly this
# many months (a little longer, because of interest).
DEBT_OPENING_MONTHS: float = 12.0

# Per-subtype monthly repayment, as a multiple of the SHIW monthly service.
# The climber pays the full scheduled service (principal falls); the subsister
# pays only a token amount and must borrow to get by. The chronic debtor is
# handled separately as interest-only, which keeps the principal flat exactly.
CLIMBER_REPAYMENT_MULT: float = 1.0
SUBSISTER_REPAYMENT_MULT: float = 0.25

# Subsister borrowing ceiling, as a multiple of the opening principal, so the
# credit line cannot grow without bound.
SUBSISTER_DEBT_CEILING_MULT: float = 2.0

# ---- Behavioural-economics layer ------------------------------------------
# IMPORTANT — different provenance from everything above. The constants in this
# file so far are *Italian* (SHIW / Bank of Italy / Emiliozzi et al.). The
# three below come from non-Italian behavioural-finance papers, so the
# SHAPE/EXISTENCE of each behaviour is paper-grounded but the MAGNITUDE is a
# deliberate modelling choice, NOT an Italian fact. Each is meant to be swept
# (see ``scripts/sweep_behavioural.py``) so no result hangs on one foreign
# number. Keep this line bright.

# Payday spending spike — Olafsson & Pagel (2018), "The Liquid Hand-to-Mouth",
# Review of Financial Studies 31(11). Iceland personal-finance-app data:
# discretionary spending bunches ~40-60% above the non-payday average in the
# days right after income arrives and decays across the pay cycle, an effect
# that is homogeneous across the income distribution. We model it as a
# *mean-neutral* multiplier on daily spending intensity (peak just after payday,
# trough before the next), so monthly totals — and thus the SHIW-grounded
# emergent savings residual — are unchanged; only the within-cycle *timing* of
# spend moves. PEAK is the payday-day multiplier; 1.5 ≈ +50% (mid-range of
# O&P). The exact figure is a non-Italian modelling choice.
PAYDAY_SPIKE_PEAK: float = 1.5

# Overdraft fee — Stango & Zinman (2014), "Limited and Varying Consumer
# Attention: Evidence from Shocks to the Salience of Bank Overdraft Fees",
# Review of Financial Studies 27(4). US checking accounts: a flat per-event fee
# (~$20-35, ≈$150/yr per account), with incidence concentrated among lower-
# income / lower-literacy holders. We charge a flat fee the moment a payment
# pushes the current account below zero. €30 ≈ the US per-event figure; the euro
# amount is a non-Italian modelling choice.
OVERDRAFT_FEE_EUR: float = 30.0

# Late-payment fee — Dahan & Nisan (2020), "Late Payments, Liquidity
# Constraints and the Mismatch between Due Dates and Paydays", CESifo WP 8733.
# Israeli utility bills: when a bill falls due before payday a liquidity-
# constrained household pays *late with a penalty* rather than not at all;
# accumulated late charges reach ~11% of the bill. We add this fraction of the
# bill when an overdue bill is finally settled. 0.11 from the paper (Israel); a
# non-Italian modelling choice.
LATE_PAYMENT_FEE_FRACTION: float = 0.11

# Write-off horizon — how long an unpaid bill is retried before it is dropped
# (service cut / write-off). 90 days is the standard industry cutoff for
# treating an account as defaulted: Butaru et al. (2015), NBER WP 21305 p.12,
# "we define delinquency as a credit-card account greater than or equal to 90
# days past due ... it is rare for an account that is 90 days past due to be
# recovered, and is therefore common practice within the industry to use 90
# days past due as a conservative definition of default"; likewise Khandani,
# Kim & Lo (2010), JBF 34, who forecast "90-days-or-more delinquency". This was
# already the hard-coded bound in ``Consumer._settle_overdue_bills``; naming it
# here is what lets the delinquency label cite a source.
WRITE_OFF_DAYS_PAST_DUE: int = 90

# ---- Income-source heterogeneity ------------------------------------------
# SHIW reports the mean income of each *primary income source* relative to the
# overall mean. payroll/self-employed/pension are SHIW facts; transfers and
# unemployed are flagged proxies (SHIW says only that transfers are "low and
# worsening"). SHIW income is already net of social-security contributions, so
# these are take-home figures.
#
# A "property" key used to sit here at 0.05. It was dead — nothing ever called
# income_source_multiplier("property"), and the property credit was computed
# from its own constant — and the mechanism it belonged to has been removed.
INCOME_SOURCE_RELATIVE: dict[str, float] = {
    "payroll":       1.08,   # SHIW 2022 §2B
    "self_employed": 1.49,   # SHIW 2022 §2B
    "pension":       0.82,   # SHIW 2022 §2B
    "transfers":     0.50,   # PROXY — SHIW says only "low and worsening"
    "unemployed":    0.40,   # PROXY — benefit-reliant jobless (NASpI: partial,
                             # time-limited replacement → below the transfers level)
}

# Population SHARE of each primary source. NOT in the five papers (SHIW gives
# relative levels, not headcounts) — a flagged ISTAT-proxy modelling choice,
# meant to be swept (esp. the pension and unemployed shares). Must sum to 1.0.
# `transfers` is the broad social-support / other-transfers bucket; `unemployed`
# is split out as the benefit-reliant jobless (Italy unemployment ~7-8% of the
# labour force, lower as a *household primary* income source → 5% proxy).
INCOME_SOURCE_SHARE: dict[str, float] = {
    "payroll":       0.52,
    "self_employed": 0.20,
    "pension":       0.20,
    "transfers":     0.03,
    "unemployed":    0.05,
}

# Per-source dispersion (sigma of the source's income lognormal). SHIW gives the
# relative *mean* of each source (INCOME_SOURCE_RELATIVE) but not its spread, so
# only the SHAPE here is assumed — a flagged proxy, mirroring the
# DEBT_SERVICE_LOGNORMAL_SIGMA convention. Pensions are formula-driven (tight);
# self-employment earnings vary widely; benefits are capped (tight). Used by
# ``sample_income_for_source`` to give each source its own scale while keeping
# each source's MEAN at the mean-preserving target (so the population mean — and
# the SHIW quartile/quintile bands — are undisturbed).
INCOME_SOURCE_SIGMA: dict[str, float] = {
    "payroll":       0.45,
    "self_employed": 0.70,   # widest — variable earnings
    "pension":       0.35,   # tightest — pension formula
    "transfers":     0.40,
    "unemployed":    0.30,   # tight — benefit caps
}

# ---- Macro-area income gradient --------------------------------------------
# Source: Semeraro, A., Tambuscio, M., Ronchiadin, S., Li Puma, L. & Ruffo, G.
# (2020), "Structural inequalities emerging from a large wire transfers
# network", Applied Network Science 5:76.
#
#   p. 5  — quoting ISTAT's 2017 regional-economy report: the GDP per capita of
#           the whole South is €18,500, **45% lower than Centre-North**.
#   p. 27 — the total amount of wire transfers *received by natural persons* in
#           Southern regions is **44.6% lower** than in Centre-North.
#   p. 9  — regional wire-transfer totals correlate with regional GDP at
#           r = 0.97, p = 4.1e-13.
#
# WHICH NUMBER AND WHY. We use 0.554 = 1 - 0.446. The two figures agree to
# within 0.4pp, but they are not the same quantity: the authors state on p. 27
# that they deliberately did NOT normalise transfer amounts by regional
# population, so -44.6% is a *total-flow* gap. The per-capita anchor is the 45%
# GDP-per-capita figure, and a per-household income multiplier is a per-capita
# quantity — so the GDP figure is the primary citation and the transfer figure
# is corroboration. They round to the same multiplier either way.
#
# TWO-WAY ONLY. The paper never separates North from Centre — "Centre-North" is
# a single bloc in both the GDP and the transfer statement. So NORTH and CENTRE
# carry the same level here. Giving the North a tilt over the Centre would be an
# invented number with no source, and is deliberately not done. (The parked
# prototype does apply a NORTH 1.10 / CENTRE 1.00 tilt; that tilt is not in the
# paper.)
#
# Applied mean-preservingly — see ``macro_area_income_multiplier``.
MACRO_AREA_INCOME_RELATIVE: dict[str, float] = {
    "NORTH":  1.00,   # Semeraro et al. p.5 — "Centre-North" is one bloc
    "CENTRE": 1.00,   # idem — the paper does not separate Centre from North
    "SOUTH":  0.554,  # 1 - 0.446 (p.27), consistent with -45% GDP/capita (p.5)
}

# Transaction category (the bank-statement label) per income source. The txn
# ``kind`` stays "salary" for every scheduled income credit; the *category*
# carries the source so income can be broken down per source.
INCOME_SOURCE_CATEGORY: dict[str, str] = {
    "payroll":       "salary",
    "self_employed": "self_employ_income",
    "pension":       "pension",
    "transfers":     "transfers",
    "unemployed":    "unemployment_benefit",
}

# Thirteenth-month bonus (the Italian "tredicesima"): payroll and pension
# recipients receive an extra month's income in December. The wire-transfer
# paper §9 documents June & December payment peaks ("probably bonus salaries");
# we model the clearest one (December) for payroll+pension. The month set is a
# flagged choice — add 6 for a June "quattordicesima" if desired.
THIRTEENTH_MONTH_MONTHS: frozenset[int] = frozenset({12})
THIRTEENTH_MONTH_SOURCES: frozenset[str] = frozenset({"payroll", "pension"})


# ============================================================================
# 2. CALENDAR HELPERS
# ============================================================================

# Italian fixed national holidays (Easter + Pasquetta are computed below).
FIXED_HOLIDAYS: set[tuple[int, int]] = {
    (1, 1),   # Capodanno
    (1, 6),   # Epifania
    (4, 25),  # Festa della Liberazione
    (5, 1),   # Festa del Lavoro
    (6, 2),   # Festa della Repubblica
    (8, 15),  # Ferragosto
    (11, 1),  # Ognissanti
    (12, 8),  # Immacolata
    (12, 25), # Natale
    (12, 26), # Santo Stefano
}


def _easter_sunday(year: int) -> date:
    """Compute Easter Sunday using the standard Gregorian algorithm."""
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    L = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * L) // 451
    month = (h + L - 7 * m + 114) // 31
    day = ((h + L - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def is_holiday(d: date) -> bool:
    """True if d is an Italian national public holiday (incl. Easter Monday)."""
    if (d.month, d.day) in FIXED_HOLIDAYS:
        return True
    easter = _easter_sunday(d.year)
    return d in (easter, easter + timedelta(days=1))


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def is_christmas_window(d: date) -> bool:
    """Dec 20–31 retail peak window."""
    return d.month == 12 and d.day >= 20


def is_payday(d: date) -> bool:
    """Salary lands on the 27th of every month in this simplified prototype."""
    return d.day == PAYDAY_DAY_OF_MONTH


def _payday_cycle_bounds(d: date) -> tuple[date, date]:
    """Return ``(last_payday, next_payday)`` bracketing the date ``d``.

    Paydays fall on ``PAYDAY_DAY_OF_MONTH`` every month, so the pay cycle that
    contains ``d`` runs from the most recent 27th up to (but not including) the
    next 27th. Used by ``pay_cycle_multiplier``.
    """
    if d.day >= PAYDAY_DAY_OF_MONTH:
        last = date(d.year, d.month, PAYDAY_DAY_OF_MONTH)
    elif d.month == 1:
        last = date(d.year - 1, 12, PAYDAY_DAY_OF_MONTH)
    else:
        last = date(d.year, d.month - 1, PAYDAY_DAY_OF_MONTH)
    if last.month == 12:
        nxt = date(last.year + 1, 1, PAYDAY_DAY_OF_MONTH)
    else:
        nxt = date(last.year, last.month + 1, PAYDAY_DAY_OF_MONTH)
    return last, nxt


def pay_cycle_multiplier(d: date) -> float:
    """Within-pay-cycle spending multiplier — Olafsson & Pagel (2018).

    Peaks at ``PAYDAY_SPIKE_PEAK`` on payday and falls linearly to
    ``2 - PAYDAY_SPIKE_PEAK`` the day before the next payday. It is
    *mean-neutral*: averaged over the days of a cycle it is exactly 1.0, so it
    re-times discretionary spend toward the days just after income arrives
    without changing the monthly total. With ``PAYDAY_SPIKE_PEAK == 1.0`` it is
    a flat 1.0 (the spike switched off).
    """
    last, nxt = _payday_cycle_bounds(d)
    cycle_len = (nxt - last).days          # 28..31
    if cycle_len <= 1:
        return 1.0
    t = (d - last).days                     # 0 on payday .. cycle_len-1
    slope = (PAYDAY_SPIKE_PEAK - 1.0) * 2.0 / (cycle_len - 1)
    return PAYDAY_SPIKE_PEAK - slope * t


# ============================================================================
# 3. SAMPLERS — three tiny functions that drive the model
# ============================================================================


def _category_selection_probs() -> tuple[list[str], np.ndarray]:
    """Selection probabilities that reproduce CATEGORY_SHARES *in euros*.

    CATEGORY_SHARES are shares of euros spent (Emiliozzi et al. 2023, §2.1,
    Figures 4 and 6). The model draws a category and then draws the ticket size
    independently from that category's lognormal, so using the shares directly
    as selection probabilities reproduces them in transaction COUNTS and misses
    on euros — by up to 10.8 percentage points, travel landing at a 19.8% euro
    share against the paper's 9.0%.

    Expected euro share of category c is p_c * E[ticket_c] / sum_k p_k *
    E[ticket_k], so setting p_c proportional to share_c / E[ticket_c] makes the
    realised euro shares equal CATEGORY_SHARES exactly, by construction. The
    price is that the constant no longer doubles as the count distribution:
    cheap categories are selected more often than their euro share (retail
    0.26 -> 0.33) and expensive ones less (travel 0.09 -> 0.034).

    Consequence for the model as a whole: the share-weighted mean ticket falls
    from ~€45.5 to ~€38.1, so euro throughput per transaction drops ~16%.
    """
    keys = list(CATEGORY_SHARES.keys())
    mean_ticket = np.array(
        [np.exp(mu + sigma ** 2 / 2) for mu, sigma in
         (CATEGORY_TICKET_LOGNORMAL[k] for k in keys)],
        dtype=float,
    )
    probs = np.array([CATEGORY_SHARES[k] for k in keys], dtype=float) / mean_ticket
    return keys, probs / probs.sum()


_CATEGORY_KEYS, _CATEGORY_PROBS = _category_selection_probs()


def sample_category(rng: np.random.Generator) -> str:
    """Pick a spending category. Draws so that the euro shares of the resulting
    spend match CATEGORY_SHARES; see _category_selection_probs()."""
    return str(rng.choice(_CATEGORY_KEYS, p=_CATEGORY_PROBS))


def sample_ticket(rng: np.random.Generator, category: str) -> float:
    """Draw a ticket size in EUR from the category's lognormal distribution."""
    mu, sigma = CATEGORY_TICKET_LOGNORMAL[category]
    return float(rng.lognormal(mu, sigma))


def daily_intensity(d: date) -> float:
    """Multiplier on a typical day's spending. Combines weekday, month,
    holiday and Christmas effects, plus the post-payday spending spike. 1.0 = a
    normal Thursday in May at mid-cycle.

    Used by the model to scale the per-consumer probability of buying something
    on a given day. The pay-cycle term (Olafsson & Pagel 2018) is mean-neutral
    over a cycle, so it re-times spend without changing the monthly total.
    """
    mult = WEEKDAY_MULTIPLIER[d.weekday()] * MONTH_MULTIPLIER[d.month]
    if is_holiday(d):
        mult *= HOLIDAY_MULTIPLIER
    if is_christmas_window(d):
        mult *= CHRISTMAS_WINDOW_MULTIPLIER
    mult *= pay_cycle_multiplier(d)
    return mult


def sample_income(rng: np.random.Generator) -> float:
    """Draw a monthly net income in EUR from the SHIW-fitted lognormal."""
    mu, sigma = INCOME_LOGNORMAL
    return float(rng.lognormal(mu, sigma))


def sample_income_source(rng: np.random.Generator) -> str:
    """Pick a primary income source, weighted by INCOME_SOURCE_SHARE."""
    keys = list(INCOME_SOURCE_SHARE.keys())
    probs = np.array(list(INCOME_SOURCE_SHARE.values()), dtype=float)
    probs = probs / probs.sum()
    return str(rng.choice(keys, p=probs))


def income_level(monthly_income: float) -> str:
    """Bin a monthly net income into "low" / "middle" / "high" using the absolute
    euro cut-points from the Bank of Italy Payment Behaviour Survey
    (``INCOME_LEVEL_BANDS_EUR``)."""
    if monthly_income <= INCOME_LEVEL_BANDS_EUR["low_max"]:
        return "low"
    if monthly_income > INCOME_LEVEL_BANDS_EUR["high_min"]:
        return "high"
    return "middle"


def sample_income_for_source(
    rng: np.random.Generator, source: str, macro_area: str
) -> float:
    """Draw a monthly net income for a consumer of a given source and macro-area.

    Each source has its own spread (``INCOME_SOURCE_SIGMA``) but its lognormal is
    centred so its *mean* equals the mean-preserving target
    ``base_mean * income_source_multiplier(source) *
    macro_area_income_multiplier(macro_area)``. Both multipliers are
    mean-preserving in their own dimension — the share-weighted source targets
    sum back to the base mean, and so do the population-weighted area targets —
    so the population mean income, and thus the empirical SHIW quartile/quintile
    bands and all downstream debt/savings calibration, is undisturbed. Only the
    location and spread *within* the population change. Construction mirrors
    ``annual_debt_service`` (``mu = log(mean) - sigma**2 / 2``).

    Note the two dimensions compose multiplicatively and independently: a
    Southern pensioner is scaled by both the pension factor and the Southern
    factor. The paper gives no source x area interaction, so none is modelled.
    """
    base_mu, base_sigma = INCOME_LOGNORMAL
    base_mean = math.exp(base_mu + base_sigma**2 / 2)
    target_mean = (
        base_mean
        * income_source_multiplier(source)
        * macro_area_income_multiplier(macro_area)
    )
    sigma = INCOME_SOURCE_SIGMA[source]
    mu = math.log(target_mean) - 0.5 * sigma**2
    return float(rng.lognormal(mu, sigma))


def macro_area_income_multiplier(macro_area: str) -> float:
    """Mean-preserving income multiplier for a macro-area.

    The exact analogue of ``income_source_multiplier``, one dimension over: the
    area's relative level divided by the population-weighted mean of all the
    relative levels. Scaling a draw by this reproduces the Semeraro et al.
    North/Centre-vs-South gap (``MACRO_AREA_INCOME_RELATIVE``) while leaving the
    *population* mean income exactly where it was, so the SHIW quartile and
    quintile calibration still lands on the same aggregate.

    What it does change — deliberately — is the *composition* of those bands.
    Because the South is scaled down, Southern households sort into the lower
    quartiles, which is what then drives area differences in debt participation,
    debt service, saver probability and financial vulnerability. Those follow
    from the income gradient; none of them is calibrated by area directly.
    """
    if macro_area not in MACRO_AREA_INCOME_RELATIVE:
        raise ValueError(
            f"unknown macro_area {macro_area!r}; "
            f"expected one of {sorted(MACRO_AREA_INCOME_RELATIVE)}"
        )
    norm = sum(
        MACRO_AREA_WEIGHTS[a] * MACRO_AREA_INCOME_RELATIVE[a]
        for a in MACRO_AREA_WEIGHTS
    )
    return MACRO_AREA_INCOME_RELATIVE[macro_area] / norm


def income_source_multiplier(source: str) -> float:
    """Mean-preserving income multiplier for a primary source.

    Scaling the SHIW lognormal draw by this keeps the *population* mean income
    unchanged — so the empirical income quartile/quintile bands and their SHIW
    debt/savings calibration are undisturbed — while spreading incomes across
    sources in the SHIW ratios (payroll 1.08 : self 1.49 : pension 0.82 :
    transfers 0.50). It is the source's relative level divided by the
    share-weighted mean of all relative levels.
    """
    norm = sum(
        INCOME_SOURCE_SHARE[s] * INCOME_SOURCE_RELATIVE[s] for s in INCOME_SOURCE_SHARE
    )
    return INCOME_SOURCE_RELATIVE[source] / norm


def income_calendar_multiplier(d: date, source: str) -> float:
    """Extra income paid on a given payday. 2.0 = a thirteenth-month bonus in
    December for payroll/pension (wire-transfer paper §9); otherwise 1.0."""
    if d.month in THIRTEENTH_MONTH_MONTHS and source in THIRTEENTH_MONTH_SOURCES:
        return 2.0
    return 1.0


def has_debt(rng: np.random.Generator, income_quartile: int) -> bool:
    """True if this consumer holds debt — Bernoulli with the SHIW
    debt-participation probability for their income quartile (1..4)."""
    if income_quartile not in DEBT_PROBABILITY_BY_INCOME_QUARTILE:
        raise ValueError(f"income_quartile must be 1..4, got {income_quartile}")
    return bool(rng.random() < DEBT_PROBABILITY_BY_INCOME_QUARTILE[income_quartile])


def is_saver(rng: np.random.Generator, income_quintile: int) -> bool:
    """True if this consumer saves — Bernoulli with one minus the SHIW
    'did not save' probability for their income quintile (1..5)."""
    if income_quintile not in P_NO_SAVING_BY_INCOME_QUINTILE:
        raise ValueError(f"income_quintile must be 1..5, got {income_quintile}")
    return bool(rng.random() >= P_NO_SAVING_BY_INCOME_QUINTILE[income_quintile])


def annual_debt_service(rng: np.random.Generator, income_quartile: int) -> float:
    """Draw an annual debt-service amount in EUR for a debt-holding consumer.

    Lognormal whose *mean* is the SHIW quartile figure; only the spread
    (``DEBT_SERVICE_LOGNORMAL_SIGMA``) is an assumed shape.
    """
    if income_quartile not in DEBT_SERVICE_MEAN_BY_QUARTILE_EUR:
        raise ValueError(f"income_quartile must be 1..4, got {income_quartile}")
    mean = DEBT_SERVICE_MEAN_BY_QUARTILE_EUR[income_quartile]
    sigma = DEBT_SERVICE_LOGNORMAL_SIGMA
    mu = math.log(mean) - 0.5 * sigma**2
    return float(rng.lognormal(mu, sigma))


def sample_debtor_subtype(rng: np.random.Generator, financially_vulnerable: bool) -> str:
    """Draw a debtor archetype (climber / chronic / subsister) for a debt-holding
    consumer, tilted by their SHIW financial-vulnerability flag: vulnerable
    debtors draw from ``DEBTOR_SUBTYPE_SHARE_VULNERABLE`` (chronic-heavy),
    resilient debtors from ``DEBTOR_SUBTYPE_SHARE_RESILIENT`` (climber-heavy).
    See the comment on those constants for the SHIW §3 grounding."""
    share = (
        DEBTOR_SUBTYPE_SHARE_VULNERABLE
        if financially_vulnerable
        else DEBTOR_SUBTYPE_SHARE_RESILIENT
    )
    subtypes = list(share.keys())
    probs = np.array([share[s] for s in subtypes], dtype=float)
    probs /= probs.sum()
    return str(rng.choice(subtypes, p=probs))


def opening_debt_principal(monthly_service: float) -> float:
    """Opening debt *stock* for a debtor, from their monthly scheduled service
    and ``DEBT_OPENING_MONTHS``. A flow→stock modelling choice (SHIW gives only
    the flow)."""
    return float(monthly_service) * DEBT_OPENING_MONTHS


# ----------------------------------------------------------------------------
# Sanity check at import: weights sum to ~1.0, and the behavioural constants
# are well-formed (fee fraction a proper fraction; the pay-cycle multiplier is
# mean-neutral over a cycle so it cannot silently inflate monthly spend).
# ----------------------------------------------------------------------------
_macro_sum = sum(MACRO_AREA_WEIGHTS.values())
_cat_sum = sum(CATEGORY_SHARES.values())
assert abs(_macro_sum - 1.0) < 0.01, f"MACRO_AREA_WEIGHTS sums to {_macro_sum}"
assert abs(_cat_sum - 1.0) < 0.01, f"CATEGORY_SHARES sums to {_cat_sum}"

assert PAYDAY_SPIKE_PEAK >= 1.0, f"PAYDAY_SPIKE_PEAK must be >= 1.0, got {PAYDAY_SPIKE_PEAK}"
assert OVERDRAFT_FEE_EUR >= 0.0, f"OVERDRAFT_FEE_EUR must be >= 0, got {OVERDRAFT_FEE_EUR}"
assert 0.0 <= LATE_PAYMENT_FEE_FRACTION < 1.0, (
    f"LATE_PAYMENT_FEE_FRACTION must be in [0, 1), got {LATE_PAYMENT_FEE_FRACTION}"
)

_subtype_sum = sum(DEBTOR_SUBTYPE_SHARE.values())
assert abs(_subtype_sum - 1.0) < 1e-9, f"DEBTOR_SUBTYPE_SHARE sums to {_subtype_sum}"
assert set(DEBTOR_SUBTYPE_SHARE) == set(DEBTOR_SUBTYPES), "DEBTOR_SUBTYPE_SHARE keys must match DEBTOR_SUBTYPES"
for _name, _split in (
    ("DEBTOR_SUBTYPE_SHARE_VULNERABLE", DEBTOR_SUBTYPE_SHARE_VULNERABLE),
    ("DEBTOR_SUBTYPE_SHARE_RESILIENT", DEBTOR_SUBTYPE_SHARE_RESILIENT),
):
    assert set(_split) == set(DEBTOR_SUBTYPES), f"{_name} keys must match DEBTOR_SUBTYPES"
    _s = sum(_split.values())
    assert abs(_s - 1.0) < 1e-9, f"{_name} sums to {_s}"
assert 0.0 <= DEBT_MONTHLY_INTEREST_RATE < 1.0, (
    f"DEBT_MONTHLY_INTEREST_RATE must be in [0, 1), got {DEBT_MONTHLY_INTEREST_RATE}"
)
assert DEBT_OPENING_MONTHS > 0, f"DEBT_OPENING_MONTHS must be > 0, got {DEBT_OPENING_MONTHS}"
assert CLIMBER_REPAYMENT_MULT > 0, f"CLIMBER_REPAYMENT_MULT must be > 0, got {CLIMBER_REPAYMENT_MULT}"
assert SUBSISTER_REPAYMENT_MULT >= 0, f"SUBSISTER_REPAYMENT_MULT must be >= 0, got {SUBSISTER_REPAYMENT_MULT}"
assert SUBSISTER_DEBT_CEILING_MULT >= 1.0, (
    f"SUBSISTER_DEBT_CEILING_MULT must be >= 1, got {SUBSISTER_DEBT_CEILING_MULT}"
)
_cycle = [
    date(2017, 1, 27) + timedelta(days=_k)
    for _k in range((date(2017, 2, 27) - date(2017, 1, 27)).days)
]
_cycle_mean = sum(pay_cycle_multiplier(_d) for _d in _cycle) / len(_cycle)
assert abs(_cycle_mean - 1.0) < 1e-9, f"pay_cycle_multiplier not mean-neutral: {_cycle_mean}"

_src_share_sum = sum(INCOME_SOURCE_SHARE.values())
assert abs(_src_share_sum - 1.0) < 1e-9, f"INCOME_SOURCE_SHARE sums to {_src_share_sum}"
assert set(INCOME_SOURCE_SHARE) <= set(INCOME_SOURCE_RELATIVE)
assert all(v > 0 for v in INCOME_SOURCE_RELATIVE.values())
_wt_mult = sum(
    INCOME_SOURCE_SHARE[_s] * income_source_multiplier(_s) for _s in INCOME_SOURCE_SHARE
)
assert abs(_wt_mult - 1.0) < 1e-9, f"income_source_multiplier not mean-preserving: {_wt_mult}"
assert set(INCOME_SOURCE_SIGMA) == set(INCOME_SOURCE_SHARE), (
    "INCOME_SOURCE_SIGMA keys must match the primary INCOME_SOURCE_SHARE sources"
)
assert all(v > 0 for v in INCOME_SOURCE_SIGMA.values())
assert INCOME_LEVEL_BANDS_EUR["low_max"] < INCOME_LEVEL_BANDS_EUR["high_min"], (
    "INCOME_LEVEL_BANDS_EUR low_max must be below high_min"
)
# sample_income_for_source keeps the population mean at the base mean: the
# share-weighted per-source target means sum back to base_mean (× weighted
# multiplier = 1), so the SHIW income bands are undisturbed.
_base_mean = math.exp(INCOME_LOGNORMAL[0] + INCOME_LOGNORMAL[1] ** 2 / 2)
_wt_target = sum(
    INCOME_SOURCE_SHARE[_s] * _base_mean * income_source_multiplier(_s)
    for _s in INCOME_SOURCE_SHARE
)
assert abs(_wt_target - _base_mean) < 1e-6, (
    f"per-source income targets not mean-preserving: {_wt_target} vs {_base_mean}"
)
# The macro-area gradient obeys the same discipline, one dimension over: the
# population-weighted area multipliers must also average to 1.0, so applying the
# Semeraro et al. South/Centre-North gap moves income *between* areas without
# moving the population mean. If this trips, the SHIW quartile calibration is no
# longer landing on the aggregate it was calibrated against.
assert set(MACRO_AREA_INCOME_RELATIVE) == set(MACRO_AREA_WEIGHTS), (
    "MACRO_AREA_INCOME_RELATIVE keys must match MACRO_AREA_WEIGHTS"
)
assert all(v > 0 for v in MACRO_AREA_INCOME_RELATIVE.values())
_wt_area = sum(
    MACRO_AREA_WEIGHTS[_a] * macro_area_income_multiplier(_a)
    for _a in MACRO_AREA_WEIGHTS
)
assert abs(_wt_area - 1.0) < 1e-9, (
    f"macro_area_income_multiplier not mean-preserving: {_wt_area}"
)
