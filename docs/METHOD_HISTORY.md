# Method history — how this model was actually built

This document answers a twelve-part questionnaire about the *development process* behind
`synthitaly`, for the methodology chapter. It is reconstructed from evidence in and around
the repository, not from memory, so that the account can be checked rather than trusted.

Every factual claim carries an evidence tag in brackets: a commit hash (`8ded2d0`), a
`file:line`, or a dated note. Where nothing supports a claim, it says so.

> **Reading this in the public repository.** Two things the evidence tags below point at are
> deliberately not published here. The commit hashes refer to the **private development
> repository** — this public repository was published as a single squashed commit, precisely
> because the third-party PDFs were tracked in its history from the first commit. And the two
> earlier directions the narrative is largely *about* — `abandoned/moneyviz-baseline/` (the UK
> MoneyViz baseline) and `italy_further_work/` (the parked larger Italian prototype) — are also
> private. Path citations to either are historical evidence tags, not links to follow. The
> account is still checkable, but against the private repository rather than this one.

---

## Provenance — three tiers of evidence

| Tier | Source | What it can prove |
|---|---|---|
| **Committed** | the 8 commits in the development repository | exact content and exact date |
| **Reconstructed** | file modification times, `runs/*/run_meta.json`, dated development notes in `~/.claude/projects/…/memory/`, and 17 archived plan files in `~/.claude/plans/` | dated, but not version-controlled — a file can be touched without being changed |
| **Recalled** | neither of the above | flagged explicitly wherever used |

One structural caveat governs the whole document. **The commit history is coarse.** Eight
commits span roughly fifteen weeks, and one of them (`11a03f3`, 21 May) imports **87,793
lines across 146 files** — three separate codebases that were built over the preceding four
weeks and committed together. Git alone therefore compresses the first month of work into a
single day. The reconstructed tier exists to recover that month, and is labelled as such
wherever it is used.

A second caveat: **the most recent phase of work is uncommitted.** As of writing, the
August validation work — `src/synthitaly/features.py`, `src/synthitaly/diagnostics.py`,
`tests/test_diagnostics.py`, `docs/VALIDATION.md`, `docs/RUNBOOK.md`, `scripts/run_all.py`,
`scripts/validation_report.py`, `scripts/build_results_page.py` and the whole
`presentation/` package — exists only in the working tree.

---

## Q1 — What was genuinely uncertain when development began?

Four things were open, and they were not resolved in the order the question implies.

**(a) The baseline dataset — the largest uncertainty, and the one that broke.** The thesis
opened on the MoneyViz / MoneyData dataset (Firat et al., EuroVis 2023; Mendeley
`dnxtg6n4rv`), and a complete Stage-1 analysis was built on it: a 2,460-line `synthtxn`
package, 27 figures, 23 tests, five written deliverables
[`abandoned/moneyviz-baseline/docs/00_stage1_plan.md`]. It was abandoned on **2026-05-13**
[`abandoned/moneyviz-baseline/ABANDONED.md`].

**(b) Whether the data could support the intended analysis at all.** The planning document
records the discovery in its own words: the CSV is *"one UK current account's 7-year ledger…
no user/account/household/merchant ID columns and no demographics"*, so *"the requested
'persona clustering' must be reframed honestly: we cannot cluster people"*
[`00_stage1_plan.md`]. This is the first documented instance of a pattern that recurs
throughout — **reframing the question rather than forcing the answer.**

**(c) Model size and scope.** This was resolved twice, in opposite directions (see Q7). The
first Italian prototype targeted 10,000 consumers and ~6,000 merchants across 25 modules
[`memory/project-overview.md`, 2026-05-13]; the version that survives runs ~150–800
consumers and was rewritten explicitly to be readable.

**(d) The validation strategy — unresolved longest.** Nothing in the record settles *how the
model would be judged* until August 2026. `docs/VALIDATION.md` opens by naming the problem
directly: *"Nobody can check the output against a real Italian bank's ledger, because that
ledger is exactly what does not exist."*

### What was *not* uncertain

Three commitments were fixed early and never revisited:

- **Agent-based modelling as the method**, and Mesa 3.x as the framework — both stated in the
  Stage-1 plan while the UK dataset was still the baseline, i.e. before any Italian work
  [`00_stage1_plan.md`: *"the eventual Mesa ABM"*].
- **The bank-eye framing** — the simulation shows what a bank sees on consumer accounts;
  business-to-business flows are out of scope. Fixed 2026-05-13 and described in the notes as
  *"load-bearing"* [`memory/bank-eye-view.md`].
- **The gap the thesis addresses** — prior generators are either model-only (GANs, which
  reproduce a transactions *table* but not the process behind it) or fraud/AML-oriented agent
  simulators (PaySim, BankSim, RetSim, AMLSim). This framing predates all code
  [`abandoned/moneyviz-baseline/README.md`].

---

## Q2 — Actual chronology: what happened first in practice?

**The short answer: the four phases did not run in sequence, and one of them ran twice.**
A dataset was chosen, analysed for three weeks, and discarded — which forced a *second*
literature search after the first prototype already existed. Method selection came before
dataset selection, not after.

| Date | Event | Tier |
|---|---|---|
| 2026-04-23 | Repository initialised — README plus four empty directories | committed `8ded2d0` |
| late Apr – 2026-05-12 | **MoneyViz baseline built**: `synthtxn` package (2,460 LOC), EDA notebook, figures F01–F27, 23 tests, docs 00–04 | reconstructed (mtimes to 2026-05-12 16:53) |
| **2026-05-13** | **Baseline abandoned.** Italian direction locked the same day: four empirical Italian papers + Jiang et al. 2022 as the synthetic-population method; bank-eye framing fixed; package renamed `synthtxn` → `synthitaly` | `ABANDONED.md`; `memory/stage1-plan.md`; `memory/project-overview.md`; `memory/bank-eye-view.md` |
| 2026-05-14 | **Italian prototype 1 running** — simulation outputs written to disk | reconstructed (`italy_further_work/runs/run_*/run_meta.json`) |
| ~2026-05-15–17 | Prototype 1 **set aside** as too large to read or demonstrate (3,440 LOC / 25 modules); the small prototype written to replace it | `italy_further_work/FURTHER_WORK.md` |
| 2026-05-18 | Financial depth: debt, overdraft floor, three accounts per consumer, emergent savings sweep, account clustering, account inspector | `memory/active-prototype-financial-depth.md` |
| 2026-05-21 | **All three codebases committed at once** (+87,793 lines); `docs/PROPOSAL_financial_depth.md` written | committed `11a03f3` |
| 2026-05-25 | Behavioural-economics layer (payday spike, overdraft fee, late-payment fee) **and** income-source heterogeneity | committed `9dac04d`; `memory/behavioural-econ-layer.md` |
| 2026-05-29 | Visualisation rewritten to make the behavioural layer inspectable | committed `3c07e88` |
| 2026-06-04 | Behavioural-events panel, live flow arrows; `MODEL_REFERENCE.md` data dictionary | committed `2b12fe4` |
| 2026-06-16 | Debt as a **stock**; climber / chronic / subsister subtypes | committed `6777720`; `memory/debtor-subtypes.md` (2026-06-15) |
| 2026-06-30 | Income differentiation (supervisor request); `ODD.md`, `WALKTHROUGH.md`, `EXPLANATION.md`; test suite expanded to 8 files | committed `f56b8b7` |
| 2026-07-16 | Repository pushed to GitHub (private); clustering + prediction notebooks added | committed `e8e3fc4`; plan `purrfect-swinging-graham.md` |
| 2026-07-27 | Colloquium / defence | presentation files, dated in filename |
| 2026-08-03 – 08-06 | **Post-defence validation phase**: the ML honesty audit, factorability diagnostics, saver studies, the one-command `run_all.py` harness | plan archive (03/04/06 Aug); uncommitted working tree |

### Did the phases overlap?

Yes, and increasingly so. The distinction worth making in the write-up:

- **April–mid-May was sequential and it failed that way.** Dataset first, three weeks of
  analysis, then the realisation that the dataset could not carry the thesis.
- **From 13 May onward the phases interleave deliberately.** The clearest single example is
  2026-05-25: reading three behavioural-finance papers, changing already-working code,
  writing tests, and running a sensitivity sweep over the new constants — all one unit of
  work [`memory/behavioural-econ-layer.md`].
- **Empirical calibration was never a separate phase at all.** It is distributed across every
  increment, enforced by a rule rather than a stage: every constant in `numbers.py` carries an
  inline `# Source:` comment [`memory/active-prototype-financial-depth.md`].

---

## Q3 — Development timeframe

Coding began in **late April 2026** (repository initialised 23 April `8ded2d0`; the earliest
surviving artefact of real work is dated 2026-05-12). The model as it now stands represents
roughly **fifteen weeks** of work, to early August 2026.

The number that matters more than the duration: **three distinct codebases were written in
that window**, not one iterated version.

| Codebase | Size | Fate |
|---|---:|---|
| `abandoned/moneyviz-baseline/synthtxn/` (UK) | 2,460 LOC + 23 tests | abandoned 2026-05-13 |
| `italy_further_work/src/synthitaly/` (Italy, prototype 1) | 3,440 LOC, 25 modules, 85 tests | parked ~2026-05-17 |
| `src/synthitaly/` (Italy, active) | 3,466 LOC, 6 files, 96 tests | current |

An honest observation worth including: the active version was written *because* 3,440 lines
were unreadable, and has since grown to 3,466 — but across **six files instead of
twenty-five**, of which 527 lines are analysis tooling (`features.py`, `diagnostics.py`)
added after the model itself was finished. The `README.md` still describes it as *"~600
lines of code across four files"*, which was true in May and is now stale. The size reduction
that mattered was structural, not numerical.

---

## Q4 — Methodological structure: was a named approach followed?

**No named methodology was consciously adopted while the work was being done.** There is no
document in the repository that says "we are following design science" or "we are doing
Scrum", and the write-up should not claim one retrospectively.

What the record *does* show is a consistent, documented working pattern with three
distinguishing properties:

1. **A plan gate.** Substantial work was preceded by a written plan that the author approved
   before any code was written. Seventeen such plans survive in `~/.claude/plans/`, and two
   are referenced from inside the repository itself
   [`italy_further_work/docs/KNOWN_ISSUES.md` §7 cites an approved plan file by path;
   `memory/active-prototype-financial-depth.md` and `memory/behavioural-econ-layer.md` each
   name theirs].
2. **Small verified increments.** `memory/active-prototype-financial-depth.md` records six
   numbered increments delivered in one day, each with the same verification step:
   *"`uv run pytest -q` (29 tests), `ruff`, `python -c "import synthitaly.viz"`,
   nbconvert-execute the demo notebook."*
3. **Sources-first for anything unfunded by the papers.** When a feature needed a number no
   paper supplied, the response was a written proposal of *candidate sources to read* rather
   than a value — `docs/PROPOSAL_financial_depth.md` is 217 lines that fix no constant and
   change no code, by design [`memory/working-style-scoped-and-sources-first.md`, 2026-05-21].

Two formal frameworks *were* adopted, but **for documentation, after the modelling**, and the
distinction is worth stating precisely:

- The **ODD protocol** (Grimm et al. 2010) — `docs/ODD.md`, written 2026-06-30 `f56b8b7`,
  roughly six weeks after the model first ran.
- **Edmonds' parsimony/purpose argument**, adopted at direction-lock as the justification for
  a deliberately small model [`memory/project-overview.md`, 2026-05-13].

**Suggested framing for the thesis:** *iterative, evidence-driven prototyping with
documentation-by-protocol* — described accurately rather than mapped onto design science or
agile after the fact. If a named comparison is wanted, note the resemblance to
**evolutionary prototyping** (three prototypes, two discarded, each informing the next) while
being explicit that the label is applied by the author in retrospect, not followed at the
time.

---

## Q5 — The typical iteration cycle

The proposed cycle is close, but the record shows two steps it omits — one at the front, one
at the back:

```
paper / evidence / supervisor request
      ↓
  WRITTEN PLAN, approved before any code            ← the front gate
      ↓
  implement ONE increment
      ↓
  pytest + ruff + import check + notebook execution
      ↓
  visual inspection of charts and CSVs
      ↓
  revise  ─── OR ───  document the limitation       ← a legitimate terminal state
      ↓
  dated note recording the decision and its rationale
```

Two features distinguish this from the generic loop:

**The plan gate.** Nothing substantial was implemented unplanned. The plan documents record
not just what to build but what was explicitly ruled out — `KNOWN_ISSUES.md` §7 lists six
features as *"deliberate scope deferral in the approved plan"* rather than as oversights.

**"Document the limitation" as a valid exit.** Several iterations ended without a code
change, on purpose:

- The chronic/subsister labelling was reviewed against the code, the colour legend and three
  tests, and **kept as-is** with a written defence rather than renamed
  [`debugging/debugging_answers1.md` Q2].
- The self-employed balance divergence was traced to a missing consumption function and
  written up as a *"known modelling limitation worth a sentence in the thesis"* — explicitly
  *"not done here"* [`debugging/debugging_answers1.md` Q5].
- The overlap between the survey-derived `mortgage`/`consumer_loan` bills and the SHIW
  aggregate `debt_service` line is *"a documented teaching simplification, flagged in
  HOW_IT_WORKS.md, not hidden — do not silently reconcile it"*
  [`memory/active-prototype-financial-depth.md`].

---

## Q6 — Important changes caused by testing

Four, in the requested *initial → observed problem → change → improvement* form. The first
two came from behavioural inspection; the last two from analytical testing after the defence.

### 1. Bills — silent skip → deferred payment with a penalty

- **Initial version.** A bill the household could not afford was simply **skipped**. No
  record, no consequence.
- **Observed problem.** The household escaped the obligation entirely. Liquidity stress —
  the thing the model exists to show — left no trace in the ledger, and the mismatch between
  fixed bill dates (1st, 5th, 10th, 15th, 20th) and the 27th payday was invisible.
- **Change (2026-05-25).** The skip was replaced with an overdue queue: an unaffordable bill
  goes to `Consumer._overdue_bills` [`model.py:470`] and is later settled at principal +
  11% [`model.py:483-512`], with a 90-day write-off bounding the queue. Grounded in Dahan &
  Nisan (2020) on the due-date/payday mismatch; the 11% is flagged as a modelling choice and
  swept [`numbers.py:291`].
- **Improvement.** Late fees became an observable, explicable output — the monthly spike and
  its ramp-up (24 → 52 → 66 → 78, then plateau) were later diagnosed from first principles as
  buffer erosion against a fixed calendar [`debugging/debugging_answers1.md` Q4].

### 2. Debt — flag → stock

- **Initial version.** Debt was a boolean flag plus a fixed monthly outflow. No principal.
- **Observed problem.** *"Every debtor behaved identically, so no trajectories were
  possible"* [`memory/debtor-subtypes.md`, 2026-06-15]. When the supervisor asked for three
  debtor archetypes — those who dig out, those permanently indebted, those subsisting near
  zero — the existing representation could not express them.
- **Change (2026-06-16, `6777720`).** Debt became a stock (`Consumer.debt_balance`) with
  monthly interest and a per-subtype repayment rule [`model.py:516`]: climber pays the full
  service and exits at zero; chronic pays interest only and runs a standing overdraft;
  subsister pays a token 0.25× and borrows on a credit line. "Method B" (explicit stock) was
  chosen by the author over a lighter emergent-steering alternative.
- **Improvement.** Trajectories diverge measurably and are testable
  (`test_debtor_trajectories_diverge_by_subtype`,
  `test_chronic_principal_non_decreasing_and_never_clears`). Every validation study in
  `VALIDATION.md` measures this divergence — it did not exist to be measured before.

### 3. The hidden leak inside the "fair" feature set

- **Initial version.** Debtor prediction on fair features (ordinary bank-observable activity)
  read **AUC 0.91**, and the notebook prose reported it.
- **Observed problem.** The number contradicted the repository's own pinned figures
  (AUC 0.68). An audit of the feature set found `cur_n_entries` — a raw count of
  current-account entries, innocuous by name — silently counting debt-service, credit-draw
  and overdraft lines. Regressed on the other fair activity counts (R² = 0.975), its residual
  correlates **+0.46** with the debt-mechanic line count and predicts `is_debtor` alone at
  **AUC 0.78**; mean residual by subtype runs none −2.8, climber +10.8, subsister +6.0,
  chronic +18.5.
- **Change.** The column was renamed `LEAK_cur_n_entries` [`features.py:189`], moving it
  behind the quarantine prefix.
- **Improvement.** The honest number fell to **0.697**, and the contradiction resolved in
  favour of the code: the pinned figures had been right all along and the hand-written prose
  wrong. The transferable lesson is stated in both documents: *"a feature is not fair because
  its name is innocuous — only if the generating process cannot write the label into it"*
  [`VALIDATION.md`; `EXPLANATION.md` §8a].

### 4. Factorability — pseudo-inverting a singular matrix → refusing to

- **Initial version.** The KMO / Bartlett factorability check was run on the full 35-column
  fair feature set, as a precondition for PCA and k-means.
- **Observed problem.** The correlation matrix is **singular** — rank 34 of 35, condition
  number ~4.9 × 10¹⁷, and a determinant whose computed sign comes out negative, which is
  numerical nonsense. The cause is exact and structural: the ten `share_*` columns are
  proportions of one total and sum to 1.000000 for every consumer. KMO requires `inv(R)`, and
  the tempting fix — `pinv` — *"silently returns a plausible-looking number computed from
  noise."*
- **Change.** `diagnostics.kmo` **raises `SingularMatrixError` rather than pseudo-inverting**
  [`diagnostics.py:85, 103, 153`], and `factorable_columns()` [`diagnostics.py:212`] drops
  only what is verifiably redundant from the frame itself — the compositional block (per
  Aitchison 1982) and five reconstructible aggregates.
- **Improvement.** A defensible KMO of **0.715** on 20 variables, with the refusal itself
  under test (`test_kmo_refuses_an_exactly_singular_matrix`,
  `test_full_fair_set_is_singular_and_is_rejected`, `test_the_reduction_restores_full_rank`).
  A sensitivity row is reported alongside it *"so a reader can see how much of any KMO
  improvement is method rather than data"* [`VALIDATION.md` Study 0].

### A fifth, if a longer-horizon example is wanted

A 10-year run (300 consumers × 3,650 days, seed 42) showed **hand-to-mouth subsisters ending
as the richest savers in the model** — median savings €59,213, maximum €908,873, against
€0 median for every other subtype. Cause: `is_saver` is force-set `True` for subsisters
[`model.py:1096`], there is no dissaving path, and spending never scales with income, so
balances compound without bound. The finding is declared rather than silently corrected
[plan `alright-um-okay-i-ve-synchronous-pancake.md`, 2026-08-03; `VALIDATION.md` "Known
confound"].

---

## Q7 — Failed or abandoned elements

Three categories, which are not the same thing and should not be merged in the write-up.

### (a) Abandoned outright

- **The MoneyViz / MoneyData UK baseline** and its entire Stage-1 package — 2,460 LOC,
  27 figures, 23 tests, five documents. Abandoned **2026-05-13**; preserved intact under
  `abandoned/moneyviz-baseline/`. The stated reason at the time is candid: *"the MoneyViz
  paper does not work as the thesis baseline. Reason TBD — to be filled in once the user
  decides on the replacement direction"* [`ABANDONED.md`]. The functional reason is visible
  in the Stage-1 plan itself: one account, no IDs, no demographics — the dataset could not
  support a multi-agent, multi-household model.
- **The package name `synthtxn`** — *"burned"* along with the direction
  [`memory/project-overview.md`].

### (b) Built, working, and then parked — the most interesting case

`italy_further_work/` is **not a failure**, and the write-up should be careful about this:
3,440 lines across 25 modules, **85 passing tests**, calibrated to all four Italian papers,
with a working command-line interface, a synthetic-population implementation of Jiang et
al.'s three steps, four network layers, and parquet output. Thirteen simulation runs sit on
disk from 14 May.

It was set aside for reasons that are about **communicability, not correctness**
[`FURTHER_WORK.md`]:

> - The user (business major, learning Python) could not read or operate 3,165 lines of code
>   spread across 25 modules.
> - The interactive SolaraViz app never reached the browser.
> - The thesis presentation needed a prototype someone could **click and run**, not a CLI
>   invocation.

This is a defensible methodological decision for a thesis whose contribution is a
*transparent, re-parameterisable* generator: a model nobody can read fails its own stated
purpose. The four-paper calibration in that folder remains the source of truth for constants
the active version borrows, with citations copied across.

### (c) Considered, sometimes half-built, then declined — with reasons

| Element | Status | Reason |
|---|---|---|
| **Pension contribution rates** (INPS/TFR/COVIP) | declined | No paper in the set provides a rate, participation split, or employer component. Kept instead as a *tagged slice of the savings residual* — honest about being a placeholder [`PROPOSAL_financial_depth.md` B2] |
| **Big-ticket purchases** (houses, cars) | deferred | Needs multi-year horizons *and* the most new sources (prices, LTV, depreciation) — sequenced last on purpose [`PROPOSAL_financial_depth.md` B3, Part E] |
| **Cash-vs-card payment-method layer** | deferred | Listed as a low-risk, paper-backed addition [Part C] but never built |
| **Prelec & Simester (2001) card-payment premium** | declined | Requires the payment-method layer first; *"the user did not select it"* [`memory/behavioural-econ-layer.md`] |
| **Household structure** (multi-person households, OECD equivalence scale) | deferred | Available in the papers and implemented in the parked version; the active model treats a Consumer as a household [Part C] |
| **The household social network** | abandoned as a stub | `italy_further_work/networks/household_net.py` returns an empty graph [`KNOWN_ISSUES.md` §7] |
| **SolaraViz in prototype 1** | failed, never fixed | Never reached the browser — eager model instantiation at import, plus a Mesa API that renders only `model.grid`. Diagnosed, fix path costed at ~50 LOC, deliberately not taken [`KNOWN_ISSUES.md` §1–2] |
| **The animated bow-tie Sankey centrepiece** | dropped | Listed under "what's not in P1 at all (by design, not bugs)" [§7] |
| **B2B / legal-entity flows** | ruled out by scope | The structural-inequalities paper's 100M-edge network is mostly invisible to a bank; excluding it is the bank-eye framing doing its job [`memory/bank-eye-view.md`] |
| **A 20-region Italian geography** | reduced to 3 macro-areas | Decided at direction-lock [`memory/project-overview.md`] |

**Also worth reporting as a near-miss:** in August, a proposal to *replace* the drawn debtor
archetypes with emergent ones was written up with three stances — redesign outright, document
the limitation, or implement emergence as a switchable mode beside the current draw. The
third was recommended precisely because it *"preserves everything already measured"*
[plan `check-the-status-on-humming-eich.md`, 2026-08-04]. That this remained a reviewable
proposal rather than a silent rewrite is itself part of the method.

---

## Q8 — Literature–code feedback: which papers changed *existing* code?

This is the question the record answers most precisely, because the dated notes distinguish
what was planned from what arrived later. Direct answer first:

### Changed code that already existed and worked

| Mechanism | Paper | What it changed |
|---|---|---|
| **Late-payment fees** | Dahan & Nisan (2020) | **The clearest case.** It *replaced* a working mechanism: the silent bill skip became an overdue queue settled at principal + 11% [`model.py:483-512`]. Existing behaviour was deleted, not extended |
| **Overdraft fees** | Stango & Zinman (2014) | Added on top of a working payment path — `_pay()` gained a zero-crossing check [`model.py:366`], and `_can_afford()` had to be changed to *pre-reserve* the €30 so the overdraft floor stayed a hard limit [`model.py:332`] |
| **Payday spending spike** | Olafsson & Pagel (2018) | Folded a multiplier into the existing `daily_intensity`. Deliberately **mean-neutral** over a pay cycle so the already-calibrated SHIW savings residual was left undisturbed — a change constrained by what was already there |
| **Income-source heterogeneity + the December *tredicesima*** | SHIW §2B; structural-inequalities §9 | Changed how income had already been drawn. Made **mean-preserving** (share-weighted multipliers sum to 1.0, asserted at `numbers.py:666-673`) specifically so the existing quartile/quintile debt and savings calibration survived |
| **The debtor archetypes** | SHIW §3 financial-vulnerability definition | Rewrote the existing debt implementation from flag to stock (Q6.2). SHIW supplied only the *service flow*; the *stock* is a flagged modelling choice |
| **The low/middle/high income bands** | Bank of Italy Payment Behaviour Survey | Changed **twice**. Initially realised percentiles of the income draw; re-grounded in the survey's absolute euro bands (≤€1,000 / €1,000–€4,000 / >€4,000) after the author rejected labelling them *"descriptive… not from a paper"* as unacceptable for the thesis [`memory/grounding-in-papers.md`] |
| **Campbell (2006)** | *Household Finance* | Changed no mechanism, but supplied the justification for letting fees fall harder on lower-income households **emergently** (thinner buffers cross zero more often) rather than via a fabricated per-quartile fee schedule |

### Planned from the start (calibration, not feedback)

Recurring bills and their shares, the ten spending categories and ticket sizes, macro-area
weights, the seasonal/weekday/Christmas calendar, the North–South gradient, debt
participation by income quartile, and saving probability by quintile. (The North–South
gradient was planned here but only actually implemented on the `regional-income` branch,
2026-08-17 — for the whole period described below it was documented and absent.) All of
these were fixed
at direction-lock on **2026-05-13**, before the active prototype existed
[`memory/project-overview.md`].

### The pattern worth naming in the thesis

The four Italian papers were **chosen first and shaped the design**; the four behavioural
papers were **encountered later and modified a working model**. That difference is also why
the two groups are handled differently in the code: the Italian constants are calibrated
facts, while the behavioural magnitudes (payday peak ×1.5, overdraft €30, late fee 11%) are
non-Italian, sit in a separately labelled block in `numbers.py`, are marked ⚠, and are
**swept** in `scripts/sweep_behavioural.py` *"so no conclusion rests on one foreign number"*
[`EXPLANATION.md` §6; `memory/behavioural-econ-layer.md`].

---

## Q9 — Testing practices

**All nine listed practices were genuinely used.** Specific checks for each:

| Practice | Used | Specific evidence |
|---|---|---|
| **Automated / unit tests** | yes | **96 tests across 8 files** (`pytest --collect-only`, verified). The docs say 93 — three were added since. Growth is itself documented: 29 tests (18 May) → 39 → 48 (25 May) → 96 |
| **Assertions / consistency checks** | yes | Module-level assertions run at import in `numbers.py`: shares sum to one, the share-weighted income multipliers return exactly 1.0 [`numbers.py:666-673`], fee constants in range [`numbers.py:635-637`] |
| **Manual CSV inspection** | yes | `demo_accounts.csv` / `demo_transactions.csv` written by the notebooks specifically for inspection; a whole session was spent building a data dictionary of the accounts CSV for the colloquium [plan `stateless-waddling-duckling.md`, 2026-07-26] |
| **Summary statistics** | yes | `scripts/validation_report.py` — the headline numbers on their own, ~27 s |
| **Charts / distributions** | yes | 15 figures regenerated from live model runs; 11 live Solara panels; the notebooks' plots. Visual inspection drove real changes — five screenshot-based questions became `debugging/debugging_answers1.md` |
| **Balance / accounting checks** | yes | `test_global_money_is_conserved`, `test_global_conservation_holds_with_overdraft_and_borrowing`, `test_each_account_reconciles_independently`, `test_consumer_account_balance_matches_entries`, `test_savings_sweep_conserves_money` |
| **Repeated simulation runs** | yes | `run_all.py` stage 9 compares each run with the previous one; determinism confirmed MATCH across four runs [plan `plan-to-run-everything-sprightly-hare.md`] |
| **Fixed random seeds** | yes | Seed 42 throughout; `test_same_seed_reproduces_identical_outputs` **and** `test_different_seed_changes_outputs` — both directions |
| **Comparison with published values** | yes | `docs/MODEL_REFERENCE.md` maps every constant to its paper and section; figures f02/f03/f06 compare generated shares against the paper baselines |

### Six checks worth naming individually in the thesis

1. **Frozen schema contracts** — `test_transaction_schema_is_frozen`,
   `test_account_export_schema_is_frozen`. The output format is a tested interface, so
   downstream analysis cannot break silently.
2. **Whole-pipeline determinism, not just seeded tests.** `validation_report.json`
   deliberately carries **no timestamp**, so two runs must be *byte-identical*.
   `run_all.py` hashes them and prints MATCH or DRIFT, with the standing instruction that
   DRIFT *"is a bug worth finding, not noise to ignore"* [`RUNBOOK.md` §2].
3. **Test-isolation hardening.** An autouse fixture snapshots and restores every mutable
   module-level constant after each test, because tests that poke constants and restore them
   in a `finally` leak state when they crash [`tests/conftest.py`].
4. **21 pinned headline numbers with explicit tolerances**, and a written rule:
   *"never widen the tolerance to make it green"* [`RUNBOOK.md`].
5. **Loose floors rather than pinned values in the test suite** — ARI > 0.30, naive
   AUC > 0.95, fair AUC > 0.60, plus the ordering constraint `naive_auc >= fair_auc`. The
   stated reasoning: *"floors catch a broken pipeline without turning a measurement into a
   target"* [`VALIDATION.md`].
6. **A test that pins a known leak in place.** The debtor-fair feature set must still score
   above 0.95 on `is_saver` — so that if someone quietly "cleans" the contaminated column,
   the test fails loudly and the documentation is revisited rather than going silently stale
   [`VALIDATION.md`].

Also: estimators are tested against cases with a **known** answer (KMO ≈ 0.5 under
independence, KMO high under a single common factor, Bartlett calibrated under sphericity)
[`tests/test_diagnostics.py`]; `ruff` runs on every increment with a documented
never-increase baseline; and a one-at-a-time sensitivity sweep covers every non-Italian
magnitude [`scripts/sweep_behavioural.py`, method per Saltelli et al. 2008].

---

## Q10 — Acceptance criterion

Not one criterion but **four, applied in a consistent order**, visible in every increment:

1. **Correctness first — non-negotiable.** Tests pass, money conserves, the schema holds, the
   same seed reproduces the same run. `memory/active-prototype-financial-depth.md` records
   the identical four-step verification after each of six increments.
2. **Provenance second.** Every constant traces to a paper *or* is explicitly flagged as a
   modelling choice. The rule is stated as a hard constraint — *"no invented numbers"* — and
   was enforced by the author against the assistant at least once, when calling income bands
   "not from a paper" was rejected outright [`memory/grounding-in-papers.md`].
3. **Plausibility on inspection third.** Output had to look like a bank statement. Charts and
   CSVs were inspected each cycle, and anomalies were pursued until *explained* — the
   self-employed divergence was traced to a specific missing mechanism (no
   marginal-propensity-to-consume) rather than being tuned away
   [`debugging/debugging_answers1.md` Q5].
4. **Analytical usefulness last — and explicitly not a gate.**

Point 4 is the strongest evidence for the ordering, and the most defensible thing in the
methodology chapter. The honest machine-learning results came back **weak** — fair-feature
clustering ARI **0.200**, fair debtor prediction AUC **0.697** — and they were kept,
published, pinned in tests, and explained rather than improved. `VALIDATION.md` states the
position in its opening: *"Question 3 is the one worth a chapter, because it is the only one
that can come back negative — and partly does. That is a finding, not a failure."* The
mechanism behind the ceiling is named precisely: the debtor subtype is *drawn* from a tilt on
one binary flag, so conditional on vulnerability the label is close to noise and **no fair
feature can recover it** — *"a property of the generator, not of the models"*
[`EXPLANATION.md` §8a].

The clearest single illustration: the fair AUC **fell** from 0.91 to 0.697 as a direct result
of the leak audit (Q6.3), and the *lower* number was adopted. An acceptance criterion driven
by analytical usefulness would have kept 0.91.

---

## Q11 — Documentation and version control

### Is the repository available for inspection?

**Yes.** `https://github.com/FJ-cloud/master-thesis-repo` (private, pushed 2026-07-16
[`e8e3fc4`; plan `purrfect-swinging-graham.md`]). All eight commits and all five branches are
on the remote.

### What exists

| Artefact | Detail |
|---|---|
| **Git** | 8 commits, 23 Apr – 16 Jul 2026; 5 branches, all pushed |
| **README** | project statement, run commands, repository map, documentation index |
| **Documentation** | 9 files in `docs/` (~2,000 lines): `ODD.md` (formal ABM spec), `MODEL_REFERENCE.md` (number → paper), `EXPLANATION.md` (why, and calibrated-vs-modelled), `VALIDATION.md`, `RUNBOOK.md`, `HOW_IT_WORKS.md`, `WALKTHROUGH.md`, `QUICKSTART.md`, `PROPOSAL_financial_depth.md` |
| **Development notes** | 6 dated notes (May) + 5 more (Jun–Aug) in `~/.claude/projects/…/memory/`; 17 archived plan documents in `~/.claude/plans/` — outside the repository, but the reason this reconstruction is possible at all |
| **Configuration** | `pyproject.toml` + `uv.lock` (pinned, Python 3.13); ruff config; pytest config |
| **Notebooks** | 4: `demo`, `analysis`, `clustering`, `prediction` — all executed headless by the harness so none can silently rot |
| **Diagrams** | 5, generated by script; 3 mirror the mermaid diagrams in `WALKTHROUGH.md` |
| **Saved intermediate outputs** | timestamped `runs/` directories with a `latest` symlink, last 10 kept; `runs/latest/results.html`, `validation_report.{md,json}`, executed notebook HTML, full log |
| **Literature** | 4 Italian papers + 6 behavioural papers + the Jiang method paper, each with the author's own reading notes in `italy_papers/notes on each paper/` |

### Three honest caveats to state rather than hide

1. **The commits are coarse.** Eight commits for fifteen weeks, one of them +87,793 lines.
   Git is not the fine-grained record here; the dated notes and plan archive are.
2. **The branches are labels, not parallel development.** `git log --graph` shows a single
   linear chain with no merges — `data-analysis`, `debtor-subtypes`, `final-additions` and
   `validation-&-data_analysis` are checkpoint pointers into it. Earlier notes also reference
   branches (`prototype`, `behavioural-economic-theory-integration`) that no longer exist.
3. **The most recent phase is uncommitted.** The entire August validation layer —
   `features.py`, `diagnostics.py`, `VALIDATION.md`, `RUNBOOK.md`, the three scripts, the
   `presentation/` package — exists only in the working tree. **Commit it before submission**,
   or the thesis will cite work the repository cannot show.

---

## Q12 — AI-assisted work

*This section is written in full detail so it can be trimmed with knowledge of what is being
left out. Check the final wording against your programme's disclosure policy before
submission — see the suggested paragraph at the end.*

### Tool

**Claude Code (Anthropic)** — a command-line coding assistant — used throughout development,
from the first prototype to the final validation work. No other AI tool is evidenced in the
repository. The audit trail is unusually complete: 17 archived plan documents, 11 session
transcripts, and 11 dated development notes.

### Task by task

**Finding literature — assisted, but bounded by an explicit rule.** The assistant produced
*shortlists of candidate sources to read*, never citations to cite. `PROPOSAL_financial_depth.md`
Part D is the clearest artefact: eighteen candidate readings grouped by the concept they
support, with the framing *"These are starting points to read, not endorsed numbers — pick
what fits after reading."* The rule was set by the author and recorded as a standing
instruction: *"for missing numbers propose sources to read, don't invent"*
[`memory/working-style-scoped-and-sources-first.md`, 2026-05-21]. **Every paper used was
selected and read by the author**, whose own notes — 1,729 lines across four files — are in
`italy_papers/notes on each paper/`.

**Explaining concepts — substantial use.** The clearest example is
`debugging/debugging_answers1.md`: the author annotated model output with screenshots and
five questions; the assistant answered each at both the conceptual level and the `file:line`
level. One answer defended the existing design and recommended no change (the chronic /
subsister labelling); another identified a genuine limitation and explicitly did not fix it.

**Generating initial code — extensive.** First drafts of all three codebases were
assistant-generated, always behind a plan the author approved first.

**Debugging — extensive.** The Solara / Starlette / `altair` dependency failures
[`KNOWN_ISSUES.md` §3–5]; the self-employed balance divergence; the late-fee ramp; the leak
audit; the singular correlation matrix.

**Refactoring — the largest single instance** is the 3,440-line, 25-module prototype
reduced to a readable model across six files, and later the consolidation of duplicated
notebook feature code into one shared `features.py` pipeline.

**Writing tests — yes**, assistant-authored and author-run. Test count is tracked in the
notes as a first-class deliverable alongside the code (29 → 39 → 48 → 96).

**Reviewing outputs — yes**, and this produced some of the most consequential changes: the
`cur_n_entries` leak (Q6.3), the factorability refusal (Q6.4), and the 10-year-run finding.

**Documentation — extensive.** The `docs/` set was drafted by the assistant from the code and
checked against it. One such check found and fixed stale line references in the notebook
provenance table [plan `please-list-the-behavioural-crystalline-piglet.md`, 2026-07-27].

### What the author retained

Recorded, not asserted:

- **Which dataset and which papers are the baseline.** The abandonment of MoneyViz and the
  lock on the Italian direction were both author decisions [`memory/stage1-plan.md`].
- **Every model constant.** Enforced by the no-invented-numbers rule, and enforced *against*
  the assistant at least once on the record [`memory/grounding-in-papers.md`].
- **Whether a limitation is fixed or documented** — see Q5, and the "Method B" choice for the
  debt implementation, taken by the author over a lighter alternative
  [`memory/debtor-subtypes.md`].
- **Review before implementation.** A standing instruction from 2026-08-04, in the author's
  own words: *"please make a clear html proposal for the different issues and we can work on
  the code after I have reviewed it and looked into it myself"* [`memory/review-before-code.md`].
- **Scope.** *"Do exactly what's asked and stop; don't add branches/refactors unasked"*
  [`memory/working-style-scoped-and-sources-first.md`].

### Suggested disclosure paragraph — a draft to adapt

> Development of the `synthitaly` prototype was carried out with the assistance of Claude
> Code (Anthropic), an AI coding assistant. It was used for initial code generation,
> refactoring, debugging, test authoring, documentation drafting, and for producing
> shortlists of candidate literature. All empirical sources were selected and read by the
> author, whose reading notes are included in the repository; all model parameters were
> chosen or approved by the author under a standing rule that every constant must trace to a
> published source or be explicitly flagged as a modelling choice. Architectural decisions —
> the choice of baseline dataset, the abandonment of the initial direction, the scope of the
> model, and whether a given limitation was corrected or documented — were made by the
> author. Written plans were approved before implementation, and the plan documents,
> development notes and commit history together form the audit trail on which the
> development account in this chapter is based.

---

## Appendix — commits at a glance

| Hash | Date | Subject | Files | Lines |
|---|---|---|---:|---:|
| `8ded2d0` | 2026-04-23 | Initial thesis repo structure | 5 | +12 |
| `11a03f3` | 2026-05-21 | added prototyping and testing branches | 146 | +87,793 |
| `9dac04d` | 2026-05-25 | behavioural-economics layer + income-source heterogeneity | 13 | +1,127 / −110 |
| `3c07e88` | 2026-05-29 | visualization update for the behavioural layer | 1 | +262 / −59 |
| `2b12fe4` | 2026-06-04 | BehaviouralEventsPanel + MODEL_REFERENCE | 4 | +416 / −130 |
| `6777720` | 2026-06-16 | debt-as-stock with climber/chronic/subsister | 17 | +2,086 / −945 |
| `f56b8b7` | 2026-06-30 | income differentiation; ODD/WALKTHROUGH/EXPLANATION; 8 test files | 21 | +2,027 / −91 |
| `e8e3fc4` | 2026-07-16 | clustering/prediction notebooks; analysis pipeline tests | 10 | +7,169 / −7,612 |

Reproduce with `git log --all --reverse --stat`.

---

## Reading map

| If you want… | Read |
|---|---|
| why the model exists; the paper map; calibrated vs modelled | [`EXPLANATION.md`](EXPLANATION.md) |
| what was validated, the numbers, and the method sources | [`VALIDATION.md`](VALIDATION.md) |
| the formal agent-based specification | [`ODD.md`](ODD.md) |
| every model number → its paper | [`MODEL_REFERENCE.md`](MODEL_REFERENCE.md) |
| the deferred deepenings and their candidate sources | [`PROPOSAL_financial_depth.md`](PROPOSAL_financial_depth.md) |
| what the abandoned and parked versions were | §5 and §7 below — the directories themselves are in the private development repository |
