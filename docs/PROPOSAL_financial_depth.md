# Proposal — adding financial depth to the generator

**Status:** conceptual. This document proposes *what* to add and *why*, and points
to **candidate sources to read** before any numbers are fixed. It does **not**
change code and does **not** lock in any constant. Read it next to
`docs/HOW_IT_WORKS.md`.

The goal is to make a simulated consumer behave less like a flat 30-day spending
machine and more like a real bank customer watched over months and years:
someone who occasionally dips into overdraft, quietly builds a pension, and every
few years makes a large, financed purchase like a car or a home.

Three things to keep in mind throughout:

- **Bank-eye view.** We only model what a bank would see on a consumer account.
  An overdraft, a pension contribution, a mortgage draw-down and the repayments
  that follow are all account-visible, so they fit.
- **Two kinds of number.** Some values are *paper-grounded* (traceable to one of
  the four Italian papers). Others are unavoidably *modelling choices*. This
  proposal keeps that line bright and never hides a choice as a fact.
- **Sources first, numbers later.** Per the brief, the gaps below are filled with
  *candidate readings* (general and foundational, not Italy-deep). You read them,
  then decide the numbers — see **Part D**.

---

## Part A — What exists today (an honest audit)

The active prototype is three files: `numbers.py` (every empirical constant),
`model.py` (agents + engine), `viz.py` (the Solara app). Each consumer already
owns **three accounts** — `current`, `savings`, `pension` (`AccountSet` in
`model.py`) — and the engine ticks one calendar day at a time.

What a consumer does today:

| Behaviour | How it works now | Grounding |
|---|---|---|
| Income | One flat salary on the 27th (`PAYDAY_DAY_OF_MONTH`) | SHIW income lognormal (~€2,000/mo net); payday is a simplification |
| Bills | A random subset of **4–5** bill types, fixed due-days | BoI Payment Survey §8 (shares, mean €) |
| Discretionary spend | Daily coin-flip × seasonal intensity, small lognormal tickets | Emiliozzi et al. (2023) category shares & ticket sizes |
| Debt | Flag rolled by income quartile; monthly debt-service line | SHIW §3 (participation + mean service by quartile) |
| Overdraft | `_overdraft_floor` lets **every** debt-holder dip to −(1 month of their own debt service) | *Who* = SHIW; *size* = flagged modelling choice |
| Savings / pension | `_month_close()` sweeps the positive monthly *residual* into savings, or retags it `pension` for a pension-saver | Saver flag = SHIW saving probability by quintile |

### Limitations this proposal targets

1. **Horizon.** The default run is **30 days**. Houses and cars are multi-year
   events — they simply cannot appear in a one-month window. Long-run behaviour
   is currently untested.
2. **Overdraft is shallow.** It applies to *all* debt-holders (not the much
   smaller slice that actually revolves), and there is **no interest, no fee, and
   no arrears** — going negative is free and has no consequence.
3. **Pension is not a contribution.** Nothing is *contributed*. The pension
   account only ever receives the leftover monthly residual under a different
   label. There is no rate, no employer/TFR component, no participation logic.
4. **No durable or big-ticket purchases.** Tickets are small. A mortgage exists
   only as a *pre-existing* recurring bill (€489/mo, 19% of households) — it is
   never *originated*, and there is no asset behind it. Nothing accumulates
   toward, or finances, a large purchase.
5. **Trimmed breadth.** Only 4–5 of **9** bill types are used; income is a single
   flat payday with no source heterogeneity, no payment-method layer, and no
   household structure. The fuller parked version already has these — they are
   low-risk wins (Part C).

---

## Part B — The three requested deepenings

Each is framed the same way: the idea, what the papers already give us, what is
missing, and which readings would close the gap.

### B1 — Overdraft

**Idea.** Make overdraft a genuine, consequential behaviour rather than a free
floor. Three layers, in increasing realism:
- *Participation:* only a realistic slice of consumers actually uses an overdraft.
- *Cost:* a negative balance accrues interest and/or a monthly fee — an
  account-visible debit, so it stays bank-eye.
- *Escalation:* persistent overdrawing leads to arrears behaviour (a missed bill,
  a hard limit, or a flag) instead of dipping forever.

**What the papers already give.** SHIW reports that **4.6%** of households hold
overdraft / revolving credit-card debt, **26%** hold any debt, and gives debt
participation and mean debt service by income quartile (Q1 12.0% … Q4 28.5%;
service €3,754 … €8,718). That is enough to decide *who* overdraws and to size a
floor from a consumer's own debt burden — the current model already does the
latter.

**What is missing.** The overdraft **limit size**, the **interest rate**, and any
**fee schedule** or arrears rule. No Italian paper here provides these.

**Candidate readings.** Household-debt overviews (Zinman, *Household Debt: Facts,
Puzzles, Theories*) and the consumer-credit/overdraft literature (e.g. Stango &
Zinman and Agarwal et al. on overdraft fees and behaviour; Gross & Souleles on
revolving credit-card debt). For Italian sizing later: SHIW debt detail you
already cite.

### B2 — Pension contributions

**Idea.** Replace the "retag the residual" placeholder with a real **monthly
contribution**: a share of salary moved from `current` into `pension` on payday,
optionally with an employer / severance (TFR) component. This is a small, regular,
account-visible internal transfer — a natural extension of the existing sweep.

**What the papers already give.** Pension already appears as an **income source**
in SHIW (≈20% of households; pensioner income ≈0.82× the mean), and the engine
already has a dedicated `pension` account and a paired internal-transfer
mechanism. So the *plumbing* exists; only the *contribution* is absent.

**What is missing.** The **contribution rate**, **participation** (who pays into a
supplementary scheme vs only the public system), and any **employer/TFR** split.
The four papers do not cover supplementary pensions.

**Candidate readings.** Life-cycle / permanent-income saving theory (Modigliani &
Brumberg; Friedman) and retirement-saving evidence (OECD *Pensions at a Glance*
for a general overview; Poterba–Venti–Wise on retirement-saving vehicles; Madrian
& Shea on enrolment inertia / defaults, which is directly about *participation*).
For Italian rates later: the COVIP supplementary-pension reports.

### B3 — Big-ticket purchases over long horizons (houses, cars)

**Idea.** Let a consumer, over years rather than days, **save toward** and then
**make** a large purchase: accumulate a deposit, put down a down-payment, and
finance the rest — after which a **stream of repayments** appears on the account
(for a home, this should reconcile with the mortgage bill that already exists).
This is the most ambitious change and the one that *requires* multi-year runs.

**What the papers already give.** A mortgage *repayment* already exists as a
recurring bill (€489/mo, 19% of households) — an originated home loan can be made
to flow into exactly that line. SHIW net-wealth figures (mean €296k, median
€152k; real assets dominate household wealth) can anchor a plausible dwelling
value. The existing emergent savings sweep is the natural deposit-accumulation
engine.

**What is missing.** **Purchase prices** (homes, cars), **loan-to-value** and loan
terms, and how a durable's value **decays** over time. None of this is in the four
papers.

**Candidate readings.** Durable-goods purchase-timing theory — why big buys are
lumpy and infrequent — via the (S,s) durables literature (Mankiw; Eberly's
automobile-purchase study; Bar-Ilan & Blinder; Grossman & Laroque on an illiquid
durable). Housing-and-mortgage life-cycle work (Cocco, *Portfolio Choice in the
Presence of Housing*; Campbell & Cocco on mortgage choice). The liquidity angle
(Kaplan–Violante–Weidner, *The Wealthy Hand-to-Mouth*) is useful because it
explains why people with illiquid wealth still run thin current accounts — which
ties B3 back to B1. For Italian prices later: ISTAT house-price index / Agenzia
delle Entrate (OMI) for property, and ISTAT/ACI vehicle data for cars.

---

## Part C — Lower-risk additions already backed by the four papers

These need **no new sources** — the numbers are already in the papers (and mostly
already coded in the parked version). They make the world richer at low risk
and are good to do first.

| Addition | What it adds | Already in a paper? |
|---|---|---|
| **Full 9 bill types** | Add subscriptions (€32), insurance (€244), taxes (€151), school (€121) | BoI Payment Survey §8 |
| **Income-source heterogeneity** | Payroll / self-employed / pension / transfers, each with its own relative income level (1.08× / 1.49× / 0.82× / low) | SHIW §2B |
| **Calendar income effects** | End-of-month payday spike, June & December extra salaries, August lull | Structural-inequalities §9 |
| **Realistic starting balances** | Set opening balance from SHIW deposit-share-by-wealth-decile rather than a flat one month of income | SHIW §2D |
| **Payment-method layer (optional)** | Cash vs card vs mobile by amount and demographics — the bank only "sees" the card-visible part | BoI Payment Survey §3 |
| **Household structure** | Generate households (not lone individuals) with the OECD-modified equivalence scale | SHIW (equivalence scale) |

---

## Part D — Candidate sources to read (general & foundational)

Grouped by the concept they support. These are **starting points to read**, not
endorsed numbers — pick what fits after reading. Italian data sources are listed
separately and only matter once you move from concept to calibration.

**Saving & the life cycle** (underpins B2 pensions and B3 deposit accumulation)
- Modigliani & Brumberg — life-cycle hypothesis.
- Friedman — permanent-income hypothesis.
- Deaton — *Saving and Liquidity Constraints*; Carroll — *Buffer-Stock Saving*.

**Household finance overview** (overdraft, debt, housing, portfolios — B1 & B3)
- Campbell — *Household Finance*.
- Zinman — *Household Debt: Facts, Puzzles, Theories*.

**Consumer credit & overdraft** (B1)
- Gross & Souleles — revolving credit-card debt.
- Stango & Zinman; Agarwal et al. — overdraft fees and behaviour.

**Pensions & retirement saving** (B2)
- OECD — *Pensions at a Glance* (general overview).
- Poterba, Venti & Wise — retirement-saving vehicles.
- Madrian & Shea — enrolment inertia / default participation.

**Durable goods & big-ticket timing** (B3)
- Mankiw; Eberly (automobile purchases); Bar-Ilan & Blinder — (S,s) durables.
- Grossman & Laroque — illiquid durable goods and portfolio choice.

**Housing & mortgages** (B3)
- Cocco — *Portfolio Choice in the Presence of Housing*.
- Campbell & Cocco — optimal mortgage choice.
- Kaplan, Violante & Weidner — *The Wealthy Hand-to-Mouth* (liquidity link to B1).

**Secondary — for later Italian calibration only** (not needed at this stage)
- COVIP — supplementary-pension (fondi pensione / TFR) reports → B2 rates.
- ISTAT house-price index / Agenzia delle Entrate (OMI) → B3 property values.
- ISTAT / ACI vehicle registrations → B3 car prices.
- SHIW — real-asset detail not yet used in the prototype.

---

## Part E — Suggested sequencing

1. **Part C first.** Cheapest and fully paper-backed; immediately makes agents
   more distinct.
2. **B1 then B2.** Both extend scaffolding that already exists (the overdraft
   floor; the pension account and sweep), so they are incremental.
3. **B3 last.** It needs multi-year horizons *and* the most new sources, so it is
   the largest single step — best attempted once the run engine is exercised over
   long horizons and Part C/D groundwork is in place.
