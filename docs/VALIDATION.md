# Validation — what was tested, what the number was, and where the method comes from

This model *generates* data. Nobody can check the output against a real Italian bank's
ledger, because that ledger is exactly what does not exist. So "is it right?" has to be
replaced by questions that can actually be answered:

1. **Does it hold together?** Money conserves, balances reconcile, the schema is stable,
   the same seed gives the same run. → `tests/`, 143 tests.
2. **Does it match the papers where it claims to?** Category shares, income bands,
   macro-area weights, the payday calendar. → `docs/MODEL_REFERENCE.md`, and figures
   f02/f03/f06 in the results page.
3. **Does the structure it claims to contain survive being looked for?** If the generator
   really produces distinguishable household archetypes, an analyst who did not build it
   should be able to find them in the transaction stream alone. → **this document.**

Question 3 is the one worth a chapter, because it is the only one that can come back
negative — and partly does. That is a finding, not a failure.

### Where each study lives

| This document | What it measures | Code | Notebook |
|---|---|---|---|
| **Study 0** | factorability of the feature matrix | `synthitaly/diagnostics.py` | `clustering.ipynb` §2b |
| **Study A** | recovering the debtor archetypes by clustering | `scripts/validation_report.py` | `clustering.ipynb` §4 |
| **Study B** | predicting `is_debtor` / `is_climber` | `scripts/validation_report.py` | `prediction.ipynb` §3, §4 |
| **Study C** | recovering saver status by clustering | `scripts/validation_report.py` | `clustering.ipynb` §5b |
| **Study D** | predicting `is_saver` | `scripts/validation_report.py` | `prediction.ipynb` §4b |

> **A naming collision to be aware of.** `clustering.ipynb` uses its own "Study A / A2 / B"
> labels *internally*, for three different clusterings: §3 the whole population, §4 the
> debtor subpopulation, §5 the accounts within each consumer. This document's **Study B**
> is the *prediction* work in the other notebook, and this document's **Study A** is only
> the notebook's §4. The two exploratory clusterings (§3 and §5) are not summarised here —
> open the notebook for those.

**Reproduce everything here in one command:**

```bash
uv run python scripts/run_all.py
```

Then open `runs/latest/results.html`. Every number below is measured at the pinned
configuration: **800 consumers × 720 days, seed 42**, on the shared pipeline in
`src/synthitaly/features.py`. See [`RUNBOOK.md`](RUNBOOK.md) for the operating
instructions.

> **Every number in this document moved on 2026-08-22.** `CATEGORY_SHARES` are shares of
> *euros* (Emiliozzi et al. §2.1, Fig. 4/6), but `sample_category()` had been using them
> directly as the probability of *picking* a category while drawing the ticket size
> independently — so the model reproduced the paper in transaction counts and missed on
> euros by up to 10.8 percentage points. Fixing it changed every transaction in the model,
> and therefore every figure downstream. The attribution block above `EXPECTED` in
> `scripts/validation_report.py` names the cause of each moved row, and
> `archive/2026-08-17_pre-category-fix/` holds the previous outputs for comparison.

---

## The vocabulary: fair vs `LEAK_`

Everything below is measured twice, and the pair is the point.

| | what it is | what it measures |
|---|---|---|
| **fair** | ordinary activity a bank can observe — purchase counts and tickets, category mix, bills paid, income credited, balance volatility | the honest result |
| **naive** | fair **plus** the `LEAK_` block: debt-service lines, credit draws, overdraft fees, the debt balance itself | the **control condition** — how completely the label is written into the ledger by construction |

A `debt_service` line only exists for a debtor; a `credit_draw` only for a subsister; an
`overdraft_fee` only for a chronic. Keeping them behind a prefix is what makes an honest
fair-only analysis possible at all. The naive number is not a result to be proud of — it
is the ceiling that says "if the label were mechanically encoded, this is what perfect
recovery would look like", against which the fair number is read.

> **One leak hid inside the fair set.** The fair debtor AUC read **0.91** until the
> feature set was audited. `cur_n_entries` — a raw count of current-account entries —
> silently included the debt-service, credit-draw and overdraft lines, re-importing the
> very leakage the prefix exists to quarantine. Regressed on the other fair activity
> counts (R² = 0.975) its residual correlates **+0.46** with the debt-mechanic line count
> and predicts `is_debtor` alone at **AUC 0.78**. It is now `LEAK_cur_n_entries`, and the
> honest number is **0.674**. Full audit in [`EXPLANATION.md`](EXPLANATION.md) §8a.
>
> The generalisable lesson: **a feature is not fair because its name is innocuous** — only
> if the generating process cannot write the label into it.

---

## Study 0 — is the feature matrix factorable at all?

PCA and KMeans both assume the correlation matrix carries *common* structure worth
extracting. Study 0 tests that assumption instead of taking it on faith, using the three
standard instruments implemented in `src/synthitaly/diagnostics.py`:

- **Bartlett's test of sphericity** — is **R** distinguishable from the identity at all?
  If not, there is nothing to factor.
- **KMO / measure of sampling adequacy** — of the correlation between two variables, how
  much is *shared* with the rest of the set rather than pairwise-specific?
- **The eigenvalue spectrum** — how many components clear the Kaiser criterion
  (eigenvalue > 1) and how much variance they carry.

### The result

| Treatment | vars | KMO | verdict | eigen>1 | Bartlett χ² (dof) | cond(**R**) |
|---|---:|---:|---|---:|---:|---:|
| full fair set | 34 | **singular — refused** | — | 10 | 77,942 (561) | 6.6 × 10¹⁶ |
| drop 1 share + duplicate aggregates | 28 | 0.729 | middling | 10 | 16,661 (378) | 328 |
| **drop all shares + duplicates** | **19** | **0.743** | **middling** | **5** | **14,555 (171)** | **291** |
| also drop 3 low-MSA stragglers | 16 | 0.795 | middling | 3 | 13,551 (120) | 289 |

**Row 1 is the finding.** The untouched fair set is singular — rank 33 of 34, condition
number ~6.6 × 10¹⁶, and a determinant whose computed *sign* comes out negative, which is
numerical nonsense. The cause is exact and structural: the ten `share_*` columns are
proportions of one total and sum to 1.000000 for every consumer. Near-exact log identities
compound it (`log total_spend ≈ log mean_ticket + log n_purchases`; `total_income` vs
`cur_total_in` at r = 0.9997).

KMO requires `inv(R)`. On a singular matrix that is meaningless, and the tempting fix —
reaching for `pinv` — silently returns a plausible-looking number computed from noise.
**`diagnostics.kmo` therefore raises `SingularMatrixError` rather than pseudo-inverting.**
That refusal is the reason the module exists as more than a wrapper around numpy.

**Row 3 is the headline.** `diagnostics.factorable_columns()` drops only what is
*structurally* redundant — verifiable from the frame itself, not tuning:

1. the compositional `share_*` block (proportions of one total; compositional data needs a
   log-ratio transform before it can enter a factor model, and none is implemented yet);
2. the five aggregates reconstructible from columns that stay (`total_spend`,
   `total_income`, `cur_total_in`, `spend_per_active_month`, `total_bills`).

**Row 4 is a sensitivity bound, not a result.** It prunes variables *because* their
measured MSA was low, which raises KMO by construction. It is reported so a reader can see
how much of any KMO improvement is method rather than data — never quoted as the headline.

**Row 2 is deliberately unstable.** Dropping a *single* share breaks the exact
sum-to-one dependency without removing the compositional block; which share you pick moves
the KMO. That instability is itself the argument for dropping the whole block rather than
picking a victim, which is why the row is shown at all.

### How to read it

Bartlett rejects sphericity in every non-singular case at p ≈ 0, so structure certainly
exists. The **middling** KMO says that structure is only partly common-factor shaped. That
is exactly what you would expect from a generator whose latent labels are *drawn* rather
than caused — see Study B. **Five** components clear the Kaiser criterion, the first
carrying 39.8 % of variance and all five together 71.7 %.

---

## Study A — clustering: do the archetypes fall out of the ledger?

KMeans (k = 3) on the 167 debtors, scored against the true climber / chronic / subsister
labels. Notebook: `notebooks/clustering.ipynb`.

| Features | n | ARI | NMI | silhouette |
|---|---:|---:|---:|---:|
| naive (fair + `LEAK_`) | 44 | **0.364** | 0.385 | 0.208 |
| fair only | 34 | **0.213** | 0.194 | 0.134 |

**What separates and what does not.** Subsisters are recovered completely — all 37 land in
one cluster — because they draw on a **credit line**, a distinct mechanic that writes a
distinct kind of line into the ledger. That cluster also absorbs 5 chronics and 8 climbers.
The other two archetypes are the problem: 71 climbers and 31 chronics land together in a
single cluster, because they differ only in repayment *speed*. So the 0.364 is "one
archetype found cleanly, two conflated", not "a third of each" — and that conflation is the
entire gap between 0.364 and 1.0.

**Both figures have moved twice, in opposite directions, and the pair is worth reading
together.** The macro-area income gradient took naive ARI **0.471 → 0.301**: it makes income
the dominant axis of the feature space, and KMeans partitions on the dominant axis, so it
began separating rich from poor rather than climber from chronic — the same mechanism Study
C describes below. The category-share units fix then took it **0.301 → 0.364**, because
moving selection mass off the high-variance categories (travel, home and repairs fall from
21.0 % to 10.4 % of draws) stripped out per-consumer spend noise that had nothing to do with
subtype. Less competing variance, clearer subtype axis.

The archetypes did not become more or less real at any point. What changed is how much
unrelated variation sits on top of them.

Fair-only recovery at 0.213 is above chance but weak, and the reason is structural
rather than a tuning failure — see the ceiling argument in Study B.

---

## Study B — prediction: can debtors and climbers be spotted?

5-fold cross-validated ROC-AUC. Notebook: `notebooks/prediction.ipynb`.

| Task | population | n (positives) | estimator | naive AUC | fair AUC |
|---|---|---:|---|---:|---:|
| `is_debtor` | all consumers | 800 (167) | LogReg | 1.000 | **0.674** |
| `is_debtor` | all consumers | 800 (167) | RF | 1.000 | **0.774** |
| `is_climber` | debtors only | 167 (86) | LogReg | 0.988 | **0.817** |
| `is_climber` | debtors only | 167 (86) | RF | 0.998 | **0.786** |

### The bound on `is_debtor` is structural — and the fair result clears it

`is_debtor` is `c.debtor_subtype is not None` (`features.py:227`), and a subtype is assigned
if and only if `has_debt` came up true (`model.py:1134-1135`). So the label is drawn by
`numbers.has_debt(rng, income_quartile)` (`numbers.py:755-760`) — a Bernoulli on
`DEBT_PROBABILITY_BY_INCOME_QUARTILE` = `{1: 0.120, 2: 0.192, 3: 0.244, 4: 0.285}`.
(`sample_debtor_subtype` and the vulnerability flag decide *which* archetype a debtor is,
so they bound `is_climber`, not `is_debtor` — see below.)

At assignment time, therefore, the only signal in the label is the income-quartile gradient.
Those four probabilities put a hard ceiling on what any assignment-time feature could
achieve: with equal-sized quartiles the Bayes-optimal AUC from income quartile alone is
**0.603**.

The fair AUCs are **0.674 (LogReg) and 0.774 (RF)** — *above* that bound. The excess is not
noise: separability arrives *after* assignment, from the divergent repayment rules, which
leave a visible trace in the account record. Read this as a positive result rather than a
shortfall. The honest number is well short of the naive 1.000 because the direct proxies
were removed, not because the label is unlearnable.

### `is_climber` does better, and for a good reason

0.786–0.817 fair-only, because the divergent repayment rules leave an ordinary, visible
trace in the account record — a climber's balance rebuilds, a chronic's does not. Here the
behaviour genuinely carries the signal, which is the positive result of the pair.

---

## "Fair" is relative to the label you are predicting

Studies 0, A and B all ask about **debtors**. Studies C and D ask the same questions of
**savers**, and doing so exposed something the debtor work could not have:

> The `LEAK_` prefix quarantines what mechanically encodes *debtor* status. Two columns
> that are genuinely fair for that label — `cur_total_out` and `cur_balance` — encode
> *saver* status almost completely. **Fairness is a property of a (feature, label) pair,
> not of a feature.**

The mechanism is exact. `Consumer._month_close` sweeps the month's positive residual into
savings or pension, and that sweep is a **debit on the current account**.
`export_accounts()` sums every entry, so `cur_total_out` counts a line that only savers
ever have, and `cur_balance` is what is left after it. On the saver label that is worth
**AUC 0.992** — a bigger leak than the `cur_n_entries` one.

`synthitaly.features` therefore carries a second, label-specific quarantine:

```python
LEAK_SAVER = ("cur_total_out", "cur_balance")
saver_fair_columns(frame)   # fair_columns minus LEAK_SAVER — use when the target is is_saver
```

`fair_columns()` is deliberately **not** changed, so every debtor number in this document,
every figure, and every pinned test bound is exactly what it was.

### What is *not* quarantined, and why

Correlating with the label is not what makes a column unfair; **mechanically encoding it**
is. Three columns correlate about as strongly and stay:

| Column | corr with `is_saver` | why it stays |
|---|---:|---|
| `balance_std_proxy` | +0.351 | transaction-derived — sweeps are never written to `model.transactions` (its kinds are purchase/bill/salary/fee/loan only) |
| `cur_total_in` | +0.294 | account-derived, but the sweep *credits* savings/pension and never touches the current account |
| `mean_income_credit` | +0.292 | salary credits only — genuine signal, and income quintile is the label's actual cause |

---

## Study C — clustering: saver vs non-saver

KMeans on all 800 consumers. k = 2 against `is_saver`, k = 4 against the four-way
`financial_status`.

| Features | n | k | against | ARI | NMI | silhouette |
|---|---:|---:|---|---:|---:|---:|
| naive | 44 | 2 | `is_saver` | **0.0222** | 0.0130 | 0.300 |
| naive | 44 | 4 | `financial_status` | 0.1056 | 0.1493 | 0.156 |
| saver-fair | 32 | 2 | `is_saver` | **0.0180** | 0.0107 | 0.362 |
| saver-fair | 32 | 4 | `financial_status` | 0.0323 | 0.0274 | 0.149 |

**Clustering does not find savers — and that is the result.** Look at the `naive` row: even
with the label mechanically present in the features, where Study D scores **1.0000**,
clustering still cannot recover it. Saver status is a real but *low-variance* direction in
the feature space; KMeans partitions on the dominant axes — income scale, activity volume —
and this split is not one of them. The healthy silhouette (0.300 naive, 0.362 saver-fair)
confirms it found *a* clean structure, just not this one.

The bound here is two-sided on purpose: `ari_saver_*` is pinned at ±0.030, so a sudden
*jump* would be as interesting as a drop. Neither has happened through two substantial
changes to the generator, which is itself evidence the result is about method rather than
about any particular calibration.

Read beside Study A, where the debtor archetypes reach ARI 0.364, the pair makes a point
neither makes alone:

> **Clustering recovers a label only when that label aligns with a dominant axis of
> variation. Prediction only needs the signal to be present at all.**

That is a statement about method, not about this model, and it is the more transferable
finding of the two.

---

## Study D — prediction: who is a saver?

5-fold cross-validated ROC-AUC on `is_saver` (442 of 800 — a far healthier class balance
than the debtor task's 167).

| estimator | naive AUC | debtor-fair AUC | **saver-fair AUC** |
|---|---:|---:|---:|
| LogReg | 1.0000 | 0.9917 | **0.7467** |
| RF | 0.9999 | 0.9917 | **0.7811** |

The middle column is the one to read: it is the set this repo calls "fair", and on this
label it is not — see the section above. Quarantining `LEAK_SAVER` takes the honest number
from ~0.992 to **~0.75–0.78**.

The saver-fair figure has drifted down across both generator changes — 0.830 originally,
0.784 after the income gradient, 0.747 after the category-share units fix — and the last
step has a mechanical cause. The fix moved selection mass off the high-variance spending
categories, cutting the marginal ticket coefficient of variation from 1.583 to 1.381, and
this AUC is carried chiefly by `balance_std_proxy`, a **dispersion** feature. Less spend
dispersion, less signal. The regression floor in
`tests/test_analysis_pipeline.py` was re-baselined 0.75 → 0.70 to match, with the cause
recorded there; below 0.70 the honest signal would have genuinely gone and this study would
need re-reading.

### Why this label is easier than the debtor one

Honest saver prediction (0.747–0.781) still clearly beats honest debtor prediction
(0.674–0.774 — and the LogReg comparison, 0.747 vs 0.674, is the like-for-like one), and the
reason is structural rather than incidental. `numbers.is_saver(rng, income_quintile)` draws
the flag conditional on **income quintile** — which the ledger *does* reveal, through the
income credits. The debtor subtype is drawn on a *hidden* binary vulnerability flag. The
saver label has an observable cause, so ordinary behaviour genuinely carries it; the debtor
subtype does not, so it cannot.

### Known confound

`ItalyModel._assign_savings` force-sets `is_saver = True` for subsisters (hand-to-mouth
households need the sweep on so any surplus leaves the current account). The two labels are
therefore entangled:

| Debtor subtype | savers | total | saver rate |
|---|---:|---:|---:|
| chronic | 26 | 44 | 59 % |
| climber | 50 | 86 | 58 % |
| none | 329 | 633 | 52 % |
| subsister | 37 | 37 | **100 %** |

Declared rather than corrected: the forcing is a deliberate modelling choice in the debt
layer, and hiding its effect on a second label would be worse than reporting it.

---

### A note on the figures

**The figures now agree with this document digit for digit.** Both of the reasons they
previously disagreed have been removed:

- They were drawn at **600 consumers × 720 days** on the small
  `FAIR_COMPACT` / `LEAK_COMPACT` column set, while this document used the full frame at
  800 × 720. All nineteen figures are now generated from a single model run at the pinned
  **800 × 720, seed 42**, on the same full column sets used here — fair 34, naive 44,
  saver-fair 32. f01, f04, f05 and f07 show that run's first 120 days, which the seeding
  makes byte-identical to a 120-day run.
- The ROC figures (f15, f18) quoted a **pooled out-of-fold** AUC — one ranking over all
  observations, which is what a single ROC curve needs (Airola et al. 2011) — whereas this
  document reports the **mean of the five per-fold AUCs**. Two legitimate estimators of the
  same quantity, differing in the last digit or two, with nothing on either telling a reader
  which was which. The figures now draw the five individual fold curves under their vertical
  average (Fawcett 2006 §7.1) and annotate the per-fold mean with its standard deviation, on
  the same `StratifiedKFold(5, shuffle=False)` the pinned table uses. Verified equal to
  machine precision.

So f14 reads ARI 0.21 / 0.36 against this document's 0.213 / 0.364, and f15 reads
0.674 / 1.000. The remaining visible difference is rounding for display, not estimation.

---

## Reproducing every number

| What | Command | Time |
|---|---|---|
| Everything | `uv run python scripts/run_all.py` | ~15 min |
| Just this document's numbers | `uv run python scripts/validation_report.py` | ~27 s |
| The pinned regression bounds | `uv run pytest -q -m slow` | ~32 s |
| The diagnostics estimators | `uv run pytest -q tests/test_diagnostics.py` | ~5 s |
| Studies 0, A, C interactively | `uv run jupyter lab notebooks/clustering.ipynb` → Run All | ~35 s |
| Studies B, D interactively | `uv run jupyter lab notebooks/prediction.ipynb` → Run All | ~35 s |

The full-run figure is measured, not estimated: the pinned run's own
`run_all.log` records **12/13 stages ok in 924.4s**, of which the paper replications
alone take 660 s. An earlier `~3½ min` in this table predated the replication stages
and was wrong.

`runs/latest/validation_report.json` carries no timestamp and the model is seeded, so two
runs are byte-identical — `run_all.py` checks exactly that and reports MATCH or DRIFT.

### What is pinned in tests, and what is not

`tests/test_analysis_pipeline.py` asserts **loose floors**, not the measured values: ARI >
0.30, naive AUC > 0.95, fair AUC > 0.60, and `naive_auc >= fair_auc` (proxies can only
help). Floors catch a broken pipeline without turning a measurement into a target. The
saver tests add one unusual assertion — that the *debtor-fair* set still scores above 0.95
on `is_saver`. That pins **the leak itself**: if someone quietly cleans `cur_total_out`
globally, the test fails loudly and this document gets revisited rather than silently
going stale. The companion floor on the honest saver-fair AUC was re-baselined 0.75 → 0.70
on 2026-08-22, with the mechanism recorded at the assertion; that is the only bound in the
suite that has been widened, and it was widened only after the cause was measured rather
than assumed.
`scripts/validation_report.py` carries the tight expected values with tolerances, so drift
is visible; if a check goes DRIFT the answer is to find out what changed, never to widen
the tolerance.

`tests/test_diagnostics.py` tests the estimators against cases with a *known* answer — KMO
≈ 0.5 for independent variables, KMO high under a single common factor, Bartlett
calibrated under sphericity — plus the refusal itself: that the full fair set is singular
and is rejected, and that the reduction restores full rank.

### Known limits of the replication harness

Three properties of the published-workflow replications (`scripts/replicate_so.py`,
`src/synthitaly/creditscoring.py`) that a reader should know before quoting from them.
None of them changes a reported discrimination figure, and none is hidden — each is
stated on the prediction page too.

1. **A So scorecard's Gini can rest on fewer than ten folds.** `scorecard()` drops any
   decile that does not hold both classes and only marks a run `skipped` when *every*
   decile fails. At the 90+ DPD base rate that bites: 7 of the 30 scorecards in the pinned
   run use fewer than ten folds and one uses a **single** fold, where the reported
   `± 0.000` means n = 1 rather than a precise measurement. Fold counts are carried in
   `gini_folds` in `replicate_so.json` and are now rendered next to every Gini.

2. **A failed stepwise selection still returns a scorecard.** When no characteristic
   clears the likelihood-ratio bar, `stepwise_logit` falls back to a one-variable fit on
   whichever column is first in the list, and the result is shaped like a successful fit.
   Callers that care must inspect `selected`. This is the likely origin of the one
   negative Gini in the cascade.

3. **Model 4 versus Model 1 is not out-of-sample on both sides.** Model 1's score is the
   pooled out-of-fold vector; Model 4's `P(G|x,R)` component is fitted on all revolvers
   without cross-validation and applied to everyone. The DeLong comparison is therefore
   **conservative** — Model 4 holds the in-sample advantage and still loses in all ten
   evaluable configurations, so the direction of the result stands — but it is not the
   symmetric out-of-sample test the phrasing suggests.

Fixing 1 and 2 properly means changing `replicate_so.py` / `creditscoring.py` and
re-running, which would move the pinned run every reported number is traced to. They are
documented rather than fixed, deliberately.

---

## Sources

Two tables, kept apart on purpose. Blurring them is the error
[`EXPLANATION.md`](EXPLANATION.md) §6 exists to prevent: **a method citation is never
evidence that a magnitude is real.**

### Where the model's numbers come from

Unchanged by this document — the number-by-number mapping lives in
[`MODEL_REFERENCE.md`](MODEL_REFERENCE.md), and the calibrated-vs-modelled bright line in
[`EXPLANATION.md`](EXPLANATION.md) §6. In summary: four empirical Italian sources (SHIW
2022; Payment Behaviour Survey 2023–24; Emiliozzi et al. (2023) card data; the structural
inequalities / wire-transfer work) fix the calibrated magnitudes; three behavioural-finance
papers (Olafsson & Pagel 2018; Stango & Zinman 2014; Dahan & Nisan 2020) plus Campbell
(2006) conceptually supply the behavioural overlay; Jiang et al. (2022) supplies the
synthetic-population method and Grimm et al. (2020) the ODD protocol.

### Where the analysis methods come from

Canonical statistics for the instruments the code implements. These are **method
provenance** — they justify the choice of test, not the value of any model parameter.

| Used in | Method | Source |
|---|---|---|
| `diagnostics.bartlett_sphericity` | Test of sphericity | Bartlett, M. S. (1950). Tests of significance in factor analysis. *British Journal of Psychology (Statistical Section)* 3(2), 77–85. |
| `diagnostics.kmo` | KMO / measure of sampling adequacy | Kaiser, H. F. (1970). A second generation little jiffy. *Psychometrika* 35(4), 401–415. |
| `diagnostics.kmo_verdict` | The marvellous→unacceptable verdict scale | Kaiser, H. F. & Rice, J. (1974). Little Jiffy, Mark IV. *Educational and Psychological Measurement* 34(1), 111–117. |
| `diagnostics.eigen_spectrum` | Eigenvalue > 1 retention rule | Kaiser, H. F. (1960). The application of electronic computers to factor analysis. *Educational and Psychological Measurement* 20(1), 141–151. |
| `factorable_columns` — the `share_*` drop | Why proportions summing to 1 cannot enter a factor model untransformed | Aitchison, J. (1982). The statistical analysis of compositional data. *JRSS Series B* 44(2), 139–177. |
| Study A | Adjusted Rand index | Hubert, L. & Arabie, P. (1985). Comparing partitions. *Journal of Classification* 2(1), 193–218. |
| Study A | Silhouette | Rousseeuw, P. J. (1987). Silhouettes: a graphical aid to the interpretation and validation of cluster analysis. *J. Computational and Applied Mathematics* 20, 53–65. |
| Study A — `clustering.ipynb` dendrogram | Ward linkage | Ward, J. H. (1963). Hierarchical grouping to optimize an objective function. *JASA* 58(301), 236–244. |
| Study A | k-means++ initialisation | Arthur, D. & Vassilvitskii, S. (2007). k-means++: the advantages of careful seeding. *SODA*, 1027–1035. |
| Study B | ROC-AUC | Fawcett, T. (2006). An introduction to ROC analysis. *Pattern Recognition Letters* 27(8), 861–874. |
| The `LEAK_` design | Target leakage as a named failure mode | Kaufman, S., Rosset, S., Perlich, C. & Stitelman, O. (2012). Leakage in data mining: formulation, detection, and avoidance. *ACM TKDD* 6(4), 1–21. |
| `scripts/sweep_behavioural.py` | One-at-a-time sensitivity analysis | Saltelli, A. et al. (2008). *Global Sensitivity Analysis: The Primer*. Wiley. |

---

## Reading map

| If you want… | Read |
|---|---|
| how to run all of this | [`RUNBOOK.md`](RUNBOOK.md) |
| why the fair results are weak, in full | [`EXPLANATION.md`](EXPLANATION.md) §8a |
| every model number → its paper | [`MODEL_REFERENCE.md`](MODEL_REFERENCE.md) |
| the formal model spec | [`ODD.md`](ODD.md) |
| the code, file by file | [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md), [`WALKTHROUGH.md`](WALKTHROUGH.md) |
