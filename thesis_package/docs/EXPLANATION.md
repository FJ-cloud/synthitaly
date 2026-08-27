# Explanation & reference — what this model is, and why

This is the **connective** document: it explains *why* `synthitaly` exists, how the
source papers fit together, and where calibrated fact ends and modelling choice begins.
It does **not** re-walk the code (see [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md)) or re-table
every constant (see [`MODEL_REFERENCE.md`](MODEL_REFERENCE.md)); it ties those together for
a reader — an examiner, a new contributor, or future-you — who wants the whole picture in
one read. The formal agent-based specification is in [`ODD.md`](ODD.md).

---

## 1. The question

Realistic, account-level financial transaction data is almost impossible to obtain: real
bank ledgers are private, and the few public payment datasets are aggregated past the point
where individual behaviour is visible. Yet that account-level view — *a salary lands, bills
go out, a card is tapped, an overdraft bites* — is exactly what you need to study consumer
financial behaviour, to teach data analysis, or to prototype a tool before it ever touches
real customer data.

`synthitaly` answers a narrow version of that need: **can a small, fully transparent
agent-based model, calibrated to public Italian statistics, generate a synthetic
transaction stream that is realistic where it has been calibrated and honest about where it
has not?** Every number is either traceable to a published source or explicitly flagged as a
modelling choice — there is no hidden tuning.

## 2. Why a *bank-eye* view

The model emits only what a bank would see on its retail customers' accounts: income in,
bills out, purchases at merchants, and the bank's own fees. It deliberately models **nothing
else** — no business-to-business wires, no corporate treasury, no taxes. This framing keeps
the scope tractable and the output legible: every row of the dataset is a transaction a real
statement would show. It is the same metaphor that opens every other doc in this repo, and it
is load-bearing — it is *why* the entity set is as small as it is.

## 3. Why Italy

Italy has an unusually rich set of *public* household-finance statistics that line up neatly
with the bank-eye view, and they were the practical anchor for calibration:

- the **Bank of Italy Survey on Household Income and Wealth (SHIW 2022)** — income by source,
  debt participation and service by income band, and saving behaviour;
- the **Bank of Italy Payment Behaviour Survey 2023-24** — recurring bills and the income
  brackets used for the low/middle/high levels;
- **Emiliozzi et al. (2023)**, Italian credit-card consumption data — the spending categories,
  ticket sizes, and the seasonal/weekday calendar;
- the **structural-inequalities / wire-transfer** paper (Semeraro et al. 2020) — the payday
  calendar (end-of-month salaries, the December *tredicesima*) and the North–South income
  gradient.

Italy also has strong, well-documented regional inequality, and the model now carries it: the
three macro-areas (NORTH / CENTRE / SOUTH, ISTAT population weights 0.46 / 0.20 / 0.34) differ
in income, not just in label. Southern households are drawn at **0.554×** the Centre-North
level — Semeraro et al. (2020) p. 5, quoting ISTAT's 2017 regional accounts (South GDP per
capita €18,500, 45% below Centre-North), corroborated at p. 27 (wire transfers received by
natural persons in the South are 44.6% lower). The paper treats "Centre-North" as one bloc and
never separates North from Centre, so neither does the model.

The multiplier is applied *mean-preservingly*, so the population mean income is unchanged and
the SHIW quartile calibration still lands on the aggregate it was calibrated against; what
changes is the dispersion (Gini 0.30 → 0.34) and the composition of the income bands, which is
what then drives area differences in debt, saving and vulnerability.

Until this was implemented, five documents — including this one — claimed the gradient while
`sample_income_for_source()` took no area argument at all. It does now.

## 4. Why an agent-based model

The phenomena of interest are **emergent and heterogeneous**: the savings rate is not a
parameter but the residual of each household's own income, bills, and spending; fees fall on
whoever happens to be liquidity-constrained on a given day; the same payday spike re-times
spending differently for a pensioner and a self-employed earner. An ABM lets these patterns
*fall out* of simple per-agent rules and a shared calendar, rather than being imposed. Three
agent types carry the whole model — `Consumer` (a household, the only decision-maker),
`Merchant` (a passive payee), and `IncomeSource` (the per-area "employer") — orchestrated by
`ItalyModel` over a daily clock. The full specification is in [`ODD.md`](ODD.md).

## 5. The papers, and how each one is used

| Paper | Role in the model | Provenance |
|---|---|---|
| **SHIW 2022** (Bank of Italy) | income by source & relative level; debt participation & service by income quartile; saving probability by quintile; the *financial-vulnerability* definition behind the chronic-debtor tilt | **Italian — calibrated** |
| **Payment Behaviour Survey 2023-24** (Bank of Italy) | the five recurring bills; the absolute-euro income-level bands (≤€1,000 / €1,000–€4,000 / >€4,000) | **Italian — calibrated** |
| **Emiliozzi et al. (2023)** (Italian card data) | 10 spending categories + shares; ticket-size distributions; weekday / month / holiday / Christmas multipliers | **Italian — calibrated** |
| **ISTAT** resident population by macro-area (2022) | `MACRO_AREA_WEIGHTS` 0.46 / 0.20 / 0.34. Replaces an earlier 0.50 / 0.27 / 0.23 that was mis-cited to Emiliozzi §6 — that paper has no §6, and the figures were card-*spend* midpoints, not people | **Italian — calibrated** |
| **Structural-inequalities / wire transfers** (Semeraro et al. 2020) | the payday rule (end-of-month, modelled on the 27th); the December 13th-month bonus; the **North–South income gradient** — `MACRO_AREA_INCOME_RELATIVE`, South = 0.554 × Centre-North (p. 5 / p. 27) | **Italian — calibrated** |
| **Olafsson & Pagel (2018)**, *The Liquid Hand-to-Mouth* | the post-payday spending spike (re-timing only, mean-neutral) | **behavioural — shape grounded, magnitude swept** |
| **Stango & Zinman (2014)** | the flat overdraft fee charged when an account crosses below zero | **behavioural — shape grounded, magnitude swept** |
| **Dahan & Nisan (2020)** | late-payment penalties when a bill falls due before payday | **behavioural — shape grounded, magnitude swept** |
| **Campbell (2006)**, *Household Finance* | the principle that fees/mistakes concentrate among lower-income households — the rationale for tilting the chronic cohort toward the vulnerable | **behavioural — conceptual grounding** |
| **Jiang et al. (2022)** | the synthetic-population method (used in the parked fuller version; conceptual ancestor here) | **method paper** |

### Full references for the four Italian sources

- **SHIW 2022** — Banca d'Italia (2024). *Survey on Household Income and Wealth — Year 2022.*
- **Payment Behaviour Survey 2023-24** — Banca d'Italia. *Report on the payment attitudes of
  consumers in Italy* (ECB SPACE 2024 survey; fieldwork September 2023 – June 2024).
- **Emiliozzi et al. (2023)** — Emiliozzi, S., Rondinelli, C. & Villa, S. (2023).
  *Consumption during the Covid-19 pandemic: evidence from Italian credit cards.*
  Banca d'Italia, Questioni di Economia e Finanza (Occasional Papers) No. 769, May 2023.
- **Structural inequalities / wire transfers** — Semeraro, A. et al. (2020). *Structural
  inequalities emerging from a large wire transfers network.* Applied Network Science 5:76.

> **Two caveats on the card-data citation.** This paper was cited throughout an earlier draft
> of the repo as "Carlsen-Riccaboni" — a name that appears nowhere in the document. The
> attribution is now correct, but **the `§n` section anchors attached to it were inherited
> from that draft and have not been re-verified** against the published paper; they point at
> the working notes in `italy_papers/notes on each paper/`, not at checked section numbers.
> Verify them by hand before quoting a section in the thesis.

## 6. Calibrated vs modelled — the bright line

The single most important epistemic commitment of this thesis is that it **never hides a
choice as a fact**. Three tiers, each marked at point of use in
[`numbers.py`](../src/synthitaly/numbers.py) and [`MODEL_REFERENCE.md`](MODEL_REFERENCE.md):

1. **Italian, calibrated.** A value taken directly from one of the four Italian sources, with
   the paper and section named — e.g. payroll earners average 1.08× the mean income (SHIW
   2022 §2B), or 12.0% of the poorest income quartile hold debt (SHIW 2022 §3).
2. **Behavioural, shape-grounded but magnitude-modelled.** The three non-Italian behavioural
   mechanisms exist because the literature says they do, but their euro/percentage size is a
   deliberate choice (payday peak ×1.5, overdraft €30, late fee 11%). These are marked **⚠**
   and are *swept* in [`scripts/sweep_behavioural.py`](../scripts/sweep_behavioural.py) so no
   conclusion rests on one foreign number.
3. **Structural modelling choices** with no paper at all — e.g. the debt *stock* (SHIW gives
   only the service *flow*), the three debtor archetypes, and the per-source income
   *dispersion*. Each is flagged **⚠** and sweepable. Where a choice could be grounded, it is:
   the chronic archetype is tilted toward SHIW's own *financially-vulnerable* definition
   (below-median income **and** debt-service ratio > 30%), so "chronically indebted" lands on
   genuinely distressed households rather than comfortable high-earners.

This is what makes the synthetic data defensible: a reader can audit every number's tier.

## 7. What the model produces

A single run yields three views, all reconcilable to one another (money is conserved
system-wide — see [`tests/test_conservation.py`](../tests/test_conservation.py)):

- a flat **transaction ledger** (`model.transactions`) — one row per money movement;
- a per-account **portfolio snapshot** (`export_accounts()`) — final balances + labels
  (income source, income level, debtor subtype, vulnerability) per household;
- **per-day time series** in the `DataCollector` — transaction volume, debt by subtype, and
  the mean current-account balance by income source / level / debtor subtype, so accounts can
  be watched *moving*, not just at the end.

The interactive Solara app surfaces all of this live across eleven panels (income composition,
balance trajectories, the chronic-debtor view, an account inspector, and more).

## 8. Limitations (an honest audit)

- **Behavioural magnitudes are non-Italian.** Mitigated by sweeping, not removed.
- **Two overlapping debt views.** The recurring `mortgage`/`consumer_loan` bills and the SHIW
  aggregate `debt_service` line come from different surveys and are deliberately not
  reconciled — a documented teaching-prototype simplification.
- **Income shares are proxies.** SHIW gives income *levels* per source, not the *headcount*
  share of each source; the shares (and the `unemployed` split) are flagged ISTAT-style
  proxies, swept.
- **No life-cycle or macro dynamics.** Employment status is static (no job loss/gain during a
  run), there is no inflation, no ageing, no migration. The horizon is months-to-a-few-years.
- **Small by design.** A 200-consumer default and a four-file model core — built to be *read*, not to be
  the largest possible model. The parked earlier version trades readability for scale, and is
  not published here.
- **The debtor subtype is drawn, not caused** — see §8a, which is the main reason the honest
  machine-learning results are as modest as they are.

### 8a. Why the fair ML results are weak — a finding, not a tuning failure

`notebooks/clustering.ipynb` and `notebooks/prediction.ipynb` ask whether the debtor archetypes
can be recovered from the transaction stream. The answer splits in a way worth stating plainly,
because it is a property of the generator rather than of the models. All figures are measured at
800 consumers × 720 days, seed 42, on the shared pipeline in `synthitaly.features`.

| Task | With debt-mechanic (`LEAK_`) features | Fair features only |
|---|---|---|
| Cluster the debtor subpopulation (ARI) | **0.364** | **0.213** |
| Predict `is_debtor` (ROC-AUC, LogReg / RF) | **1.000 / 1.000** | **0.678 / 0.765** |
| Predict `is_climber` among debtors (ROC-AUC) | **0.988 / 0.998** | **0.817 / 0.786** |

The `is_debtor` fair column quotes the **pinned** bounds from [`RUNBOOK.md`](RUNBOOK.md);
[`VALIDATION.md`](VALIDATION.md) quotes the **observed** values from the same run (0.674 /
0.774). Both are the pinned 800 x 720 seed-42 run — one is the tolerance anchor, the other
the measurement.

These moved twice since first written. The macro-area income gradient introduced a
strong income axis that KMeans partitions on, taking `ari_naive` 0.471 → 0.301; the
category-share units fix then took it back up to 0.364 by removing spend-variance
noise unrelated to subtype. The attribution block above `EXPECTED` in
`scripts/validation_report.py` records every row and its cause.

The bound on the debtor task is structural. `is_debtor` is `c.debtor_subtype is not None`,
and a subtype is assigned iff `has_debt` came up true — so the label is drawn by
`numbers.has_debt(rng, income_quartile)`, a Bernoulli on
`DEBT_PROBABILITY_BY_INCOME_QUARTILE` = `{1: 0.120, 2: 0.192, 3: 0.244, 4: 0.285}`. At
assignment time the only signal in the label is that income gradient, and it caps the
Bayes-optimal AUC from income quartile alone at **0.603**. The fair AUCs of 0.674 and 0.774
sit *above* that bound. What separability does exist beyond it arrives *after*
assignment, from the divergent repayment rules: subsisters draw on a credit line (a distinct
mechanic, hence near-perfect cluster separation — all 37 of them land together, in a cluster
that also absorbs 5 chronics and 8 climbers), while climbers and chronics differ only in
repayment speed and are merged by clustering. Climber-vs-other predicts better (0.786-0.817)
because those repayment rules leave an ordinary, visible trace in the account record.

The `LEAK_` column is therefore not a bug to be fixed but the control condition: it measures how
completely the label is encoded mechanically (perfectly), against which the fair number measures
what ordinary behaviour actually carries.

**One leak hid inside the fair set.** The fair debtor AUC read **0.91** until the feature set was
audited. A single column — `cur_n_entries`, a raw count of current-account entries — silently
included the debt-service, credit-draw and overdraft lines, re-importing the very leakage the
`LEAK_` prefix exists to quarantine. Regressed on the other fair activity counts (`n_purchases`,
`n_bills`, `n_income`; R² = 0.975) its residual correlates **+0.46** with the debt-mechanic line
count and predicts `is_debtor` alone at **AUC 0.78**, with mean residual by subtype running
none −2.8, climber +10.8, subsister +6.0, chronic +18.5 — tracking the extra entries the debt
machinery writes. It is now `LEAK_cur_n_entries`, and the honest number is 0.674. This also
explains a discrepancy that had stood in the repo: the validation figures
(`presentation/figures/f15_prediction`, AUC 0.68) and the pinned regression bounds never
included that column, so they had been right all along while the notebook prose was not. The
generalisable lesson: a feature is not fair because its *name* is innocuous — only if the
generating process cannot write the label into it.

The full write-up of all three studies — including the factorability diagnostics that sit
in front of them, and the sources for every statistical method used — is in
[`VALIDATION.md`](VALIDATION.md). Reproduce the numbers with
`uv run python scripts/run_all.py`.

## 9. Reading map

| If you want… | Read |
|---|---|
| the whole picture (this) | `EXPLANATION.md` |
| the formal ABM specification | [`ODD.md`](ODD.md) |
| a file-by-file code walkthrough | [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) |
| the data dictionary (every number → its paper) | [`MODEL_REFERENCE.md`](MODEL_REFERENCE.md) |
| what was validated, the numbers, and the method sources | [`VALIDATION.md`](VALIDATION.md) |
| to run everything, and what should come back | [`RUNBOOK.md`](RUNBOOK.md) |
| to just run it | [`QUICKSTART.md`](QUICKSTART.md) |
| the roadmap of deferred deepenings | [`PROPOSAL_financial_depth.md`](PROPOSAL_financial_depth.md) |
