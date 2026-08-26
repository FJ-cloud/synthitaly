# Results — validation of the synthetic transaction stream

This section reports what the synthetic data can and cannot support. It covers five
internal studies (0, A, B, C, D) and three external replications of published
consumer-credit models. The organising question throughout is not *how well can a
classifier score this data* but *what does a good score mean here* — because in a
synthetic dataset a high score is as likely to indicate a leaked label as a real
regularity, and separating the two is the whole exercise.

Every number below is reproducible: `scripts/validation_report.py` writes a
byte-deterministic JSON for a fixed seed, and 21 headline values are pinned as tests
that fail the build on drift.

> **Measured on run `20260822-142420`** — 800 consumers x 720 days, seed 42 — the single
> run every figure and table in this document is drawn from. Written 2026-08-22, figure
> cross-references added 2026-08-23. The machine-readable source is
> `data/validation_report.json` in the hand-off package, or `runs/20260822-142420/` in the
> repository. Figures are named as they appear in `figures/CAPTIONS.md`.

---

## 1. Setup

All internal studies use a single configuration: **800 consumers × 720 simulated
days, seed 42**, with three merchants per spending category per macro-area. The
run yields a per-consumer feature frame of **44 columns**.

Income is drawn per source **and** per macro-area: Southern households sit at
0.554× the Centre-North level (Semeraro et al. 2020 p. 5 / p. 27), applied
mean-preservingly so the population mean is unchanged at ≈ €1,900 while the Gini
of income rises from 0.30 to 0.34.

| Population | n |
|---|---:|
| Consumers | 800 |
| Debtors | 167 — climber 86, chronic 44, subsister 37 |
| Savers | 442 |
| Macro-areas | NORTH 356 · CENTRE 159 · SOUTH 285 (ISTAT weights 0.46 / 0.20 / 0.34) |

The raw output stream is `f01_txn_volume` (daily counts and euro throughput) and
`f04_payday_spike` (the post-payday bunching); `f05_behavioural_events` shows the overdraft
and late-payment fee events. Income structure is `f06_income_composition`,
`f07_balance_by_source` and `f08_income_distribution`; the macro-area split is
`f03_spend_by_area`. The debt layer these
studies are about is `f09_debt_stock_by_subtype`, `f10_balance_by_subtype`,
`f11_debtor_composition` and `f12_still_in_debt`.

### 1.1 The `fair` / `LEAK_` distinction

The 44 columns split into **34 `fair`** columns and **10 `LEAK_`** columns. A
`LEAK_` column is one that encodes the label by construction rather than by
behaviour — `LEAK_savings_balance`, for instance, is exactly zero for 100% of
non-savers, so it *is* the saver label wearing a different name.

Throughout, the **`naive`** column of every table means *fair features plus the
`LEAK_` columns*. It is a **control condition, not a result.** It measures how
completely the label is mechanically recoverable; the `fair` number beside it
measures what ordinary observable behaviour actually carries. The interesting
quantity is always the gap between them.

This distinction turns out to be sharper than a single split allows, and §5 is
about where the repository's own definition of "fair" fails.

---

## 2. Study 0 — is the feature matrix factorable?

Before asking what can be predicted, we ask whether the feature space has usable
structure at all.

| Treatment | vars | KMO | Kaiser's verdict | eigen > 1 | Bartlett χ² (df) | cond(R) |
|---|---:|---:|---|---:|---:|---:|
| full fair set | 34 | — | singular — refused | 10 | 77,942 (561) | 6.64 × 10¹⁶ |
| drop 1 share + duplicate aggregates | 28 | 0.729 | middling | 10 | 16,661 (378) | 328 |
| **drop all shares + duplicates — headline** | **19** | **0.743** | **middling** | **5** | **14,555 (171)** | **291** |
| also drop 3 low-MSA stragglers — *sensitivity bound* | 16 | 0.795 | middling | 3 | 13,551 (120) | 289 |

The first row is the point of the exercise. The untouched fair set is **singular**
— a condition number of 6.6 × 10¹⁶ — and the KMO routine refuses to
pseudo-invert it rather than return a number that would look like a measurement.
The singularity is structural: category share columns sum to one, and several
aggregates are exact linear combinations of their parts.

The headline row removes those redundancies on **structural grounds only** and
recovers a factorable matrix: KMO 0.743, Bartlett strongly rejects sphericity, and
five components clear Kaiser's criterion, together carrying **71.7%** of variance.
One of the drops is new: `n_income` is now constant for every consumer — every
consumer receives exactly one income credit per payday — so it has zero variance
and cannot enter a correlation matrix at all.

| PC | eigenvalue | % variance | cumulative % |
|---:|---:|---:|---:|
| 1 | 7.556 | 39.8 | 39.8 |
| 2 | 2.189 | 11.5 | 51.3 |
| 3 | 1.652 | 8.7 | 60.0 |
| 4 | 1.198 | 6.3 | 66.3 |
| 5 | 1.035 | 5.4 | 71.7 |

The fourth row must not be read as a better result. It drops three variables
*because their MSA was low*, which raises KMO by construction; it is reported as a
sensitivity bound on how far the statistic can be pushed, not as a finding.

---

## 3. Study A — clustering the debtor subpopulation

KMeans with k = 3 against the true `debtor_subtype` label (climber / chronic /
subsister), on the 167 debtors.

| Features | n cols | ARI | NMI | silhouette |
|---|---:|---:|---:|---:|
| naive | 44 | 0.3636 | 0.3846 | 0.2080 |
| fair | 34 | 0.2126 | 0.1944 | 0.1336 |

`f13_clustering_pca` shows the debtors in the plane of their first two principal
components, KMeans clusters against true archetypes; `f14_cluster_recovery` carries these
scores and the confusion matrix discussed below.

Unsupervised recovery of the debtor archetypes is **modest when the debt mechanics
are visible and weak when they are not**. ARI falls by roughly 40% once the
`LEAK_` columns are removed. The archetypes are genuinely present in observable
behaviour — 0.213 is well above chance — but they are not the dominant axis of
variation.

Both figures have moved twice, in opposite directions, and the pair is worth reading
together. The macro-area income gradient took naive ARI **0.471 → 0.301**: it makes
income the strongest axis in the feature space, and KMeans partitions on the
strongest axis, so it began separating rich from poor rather than climber from
chronic. The category-share units fix then took it **0.301 → 0.364**, because moving
selection mass off the high-variance categories (travel, home, repairs: 21.0% → 10.4%
of draws) removed per-consumer spend noise that had nothing to do with subtype. Less
noise, clearer subtype axis. The archetypes did not become more or less real at any
point — what changed is how much competing variance sits on top of them.

The confusion matrix says where the ceiling is. Subsisters separate cleanly (37 of 37
in one cluster on the naive set); climbers and chronics are merged, with 71 climbers
and 31 chronics landing in the same cluster. That is the whole gap between 0.36 and
1.0, and it is structural — see §7.4.

---

## 4. Study B — predicting debtor status and archetype

Five-fold cross-validated ROC-AUC.

| Task | population | n (positives) | estimator | naive AUC | fair AUC |
|---|---|---:|---|---:|---:|
| `is_debtor` | all consumers | 800 (167) | logistic | 1.0000 | 0.6738 |
| `is_debtor` | all consumers | 800 (167) | random forest | 1.0000 | 0.7736 |
| `is_climber` | debtors only | 167 (86) | logistic | 0.9882 | 0.8173 |
| `is_climber` | debtors only | 167 (86) | random forest | 0.9979 | 0.7857 |

`f15_prediction` plots these as ROC curves — the five folds under their vertical average,
with the coefficient panel beside them.

Two things stand out.

**Debtor status is only weakly observable.** The naive AUC of exactly 1.0000
confirms the `LEAK_` columns encode the label perfectly — as designed. The honest
figure is **0.674–0.774**, a ceiling that recurs throughout this work. Debt
participation is assigned by a SHIW roll on income quartile and then expressed
through a fixed monthly service payment; a consumer's ledger shows that payment,
but little else distinguishes a debtor from a non-debtor of similar income.

**Archetype is more observable than participation** (0.786–0.817 vs 0.674–0.774).
Once you know somebody is a debtor, their trajectory — whether the principal falls,
holds, or drifts up — is legible in the transaction stream. Whether they are a
debtor at all is much less so.

---

## 5. Studies C and D — the saver label, and a leakage result

### 5.1 Study C — clustering does not recover saver status

| Features | n cols | k | against | ARI | NMI | silhouette |
|---|---:|---:|---|---:|---:|---:|
| naive | 44 | 2 | `is_saver` | 0.0222 | 0.0130 | 0.2996 |
| naive | 44 | 4 | `financial_status` | 0.1056 | 0.1493 | 0.1563 |
| saver-fair | 32 | 2 | `is_saver` | 0.0180 | 0.0107 | 0.3620 |
| saver-fair | 32 | 4 | `financial_status` | 0.0323 | 0.0274 | 0.1493 |

Clustering **fails to recover saver status**, at ARI ≈ 0.02 — and it fails *even
in the naive condition*, where the label is mechanically present and supervised
prediction (§5.2) is essentially perfect. This is not a failure of the data but a
property of the method: the silhouette of 0.30–0.36 is healthy, so KMeans found *a*
clean partition — just not this one. Saver status is a real but low-variance
direction, and KMeans partitions on the dominant axes instead.

The contrast with Study A is the finding worth stating: debtor archetypes reach
ARI 0.364 under the same procedure. **Unsupervised structure and supervised
learnability are different questions, and this dataset separates them cleanly.**

### 5.2 Study D — "fair" is relative to the label you are predicting

`f18_saver_prediction` is the figure for this section, and it needs three curves rather
than two for exactly the reason the section describes.

| Task | n (positives) | estimator | naive | debtor-fair | saver-fair |
|---|---:|---|---:|---:|---:|
| `is_saver` | 800 (442) | logistic | 1.0000 | 0.9917 | 0.7467 |
| `is_saver` | 800 (442) | random forest | 0.9999 | 0.9917 | 0.7811 |

**The `debtor-fair` column is the point of this study.** That set is what the
repository calls "fair" — the 34 columns with the debt-mechanic leaks removed. On
the saver label it is *not* fair, and it scores 0.992: almost indistinguishable
from the naive control.

The mechanism is specific and worth stating precisely. `Consumer._month_close`
sweeps a saver's positive monthly residual into savings or pension, and that sweep
is executed as a **debit on the current account**. So `cur_total_out` contains a
line item that only savers ever have, and `cur_balance` is what remains after it.
Neither column looks like a leak by name.

Quarantining exactly those two as `LEAK_SAVER` gives the saver-fair set of 32
columns, and takes the honest figure from ~0.992 to **0.75–0.78**.

| Column | corr with `is_saver` | disposition |
|---|---:|---|
| `cur_total_out` | +0.612 | **quarantined** — the sweep debit lands in it |
| `cur_balance` | −0.235 | **quarantined** — the sweep debit lands in it |
| `balance_std_proxy` | +0.351 | kept — transaction-derived; sweeps are never written to `model.transactions` |
| `cur_total_in` | +0.294 | kept — account-derived but unreachable: the sweep credits savings/pension, never the current account |
| `mean_income_credit` | +0.292 | kept — salary credits only; income quintile is the label's actual cause |

Note that correlation alone does not decide the question: `balance_std_proxy`
correlates *more strongly* with the label (+0.351) than `cur_balance` does
(−0.235), yet is kept, because the sweep cannot reach it. **Leakage is a question
about the generating mechanism, not about correlation magnitude.**

### 5.3 A known confound

Subsisters are force-set `is_saver = True` in `ItalyModel._assign_savings`, so
saver status is entangled with debtor subtype:

| Debtor subtype | savers | total | saver rate |
|---|---:|---:|---:|
| chronic | 26 | 44 | 59% |
| climber | 50 | 86 | 58% |
| none | 329 | 633 | 52% |
| subsister | 37 | 37 | **100%** |

This is a modelling artefact and should be treated as one when interpreting §5.2.
`f19_saver_debtor_confound` plots it.

### 5.4 Why honest saver prediction beats honest debtor prediction

Saver-fair AUC exceeds the `is_debtor` fair AUC, which is initially counter-intuitive. The
explanation is in how each label is drawn. `f16_saver_rate_by_quintile` shows the realised
saver rate against the SHIW probability it was drawn from, and
`f17_saver_balances_by_quintile` the resulting balances. `is_saver` is rolled on
**`income_quintile`**, and income is visible in the ledger as salary credits — the
label has an *observable cause*. The debtor subtype is drawn on a **hidden binary
flag** with no ledger signature. A label is learnable to the extent its cause is
observable, and these two labels differ precisely there.

**The margin has narrowed to the point where the estimator matters, and that should
be said rather than averaged away.** On logistic regression the comparison is clean:
0.747 saver-fair against 0.674 on `is_debtor`. On the random forest the two are now
almost tied — 0.781 against 0.774 — so the claim rests on the like-for-like linear
comparison, not on the pair of ranges.

Both honest figures have moved twice. The macro-area income gradient took saver-fair
0.827 → 0.784 and `is_debtor` fair 0.697 → 0.678; the category-share units fix then took
saver-fair to 0.747 while the `is_debtor` random forest rose to 0.774. Neither move is a
loss of label information: the AUC obtainable from the label's actual cause,
`AUC(is_saver | monthly_income)`, was unchanged at 0.673 → 0.671 across the gradient.
What moves is the signal carried by the behavioural proxies — chiefly
`balance_std_proxy`, a **dispersion** feature. The gradient loaded it with
income-dispersion variance unrelated to saving; the units fix then cut the spend
dispersion it measures (marginal ticket CV 1.583 → 1.381), removing signal directly.
The data is harder on both counts, which given §7.4's "near-noise or near-certainty"
critique is an improvement rather than a regression.

---

## 6. Headline checks

**21/21 PASS.** Twenty-one values are pinned with a tolerance, and every one of them
falls inside its band. `scripts/validation_report.py` exits non-zero on any drift, so
this is enforced rather than asserted.

**A known issue, declared rather than resolved.** Eleven of the twenty-one reproduce
their pinned value *exactly*; the other ten pass on tolerance rather than on equality.
The pinned expectations in `scripts/validation_report.py` were set before the
category-share units fix of 2026-08-22 — which changed every transaction in the model —
and were never refreshed afterwards. The largest divergence is
`auc_is_saver_rf_saverfair`, measured **0.7811** against a pinned **0.7971**, consuming
80% of its ±0.02 band.

The distinction that matters here is between a stale expectation and a failure to
reproduce, and this is the former. The pipeline is deterministic: two consecutive runs of
`scripts/validation_report.py` produce byte-identical JSON, and that JSON is in turn
byte-identical to the stored output of the run this document reports. The measurement is
stable; the number it is being compared against is out of date. The remedy is to re-pin
the twenty-one expected values against the current run. That has not been done here, and
until it is, those ten rows should be read as tolerance passes and not as exact
reproductions.

---

## 7. External replication — three consumer-credit papers

The internal studies establish what the data supports on its own terms. The
replications ask a harder question: **do published consumer-credit models behave on
this synthetic data the way they behave on real data?** Where they do not, the
disagreement is diagnostic of the model, not of the papers.

Configuration: 800 consumers, seed 42, 720 days, extended to **1,440 days** for the
12-month horizons, which are not evaluable on a 720-day run. Butaru additionally
uses six simulated portfolios (seeds 42–47).

### 7.1 So, Thomas, Seow & Mues — transactor/revolver scorecard

The paper's premise is stated plainly: *"Since transactors pay off all their balance
each period, they cannot default and so all Transactors must be Goods."*

**In this model the premise is false, and inverted.**

| Group | n | bad rate (12-month late-fee label) | bad rate (12-month 90-DPD) |
|---|---:|---:|---:|
| Transactor | 633 | **28.0%** | **4.3%** |
| Revolver | 167 | **15.6%** | **2.4%** |

Transactors are **1.8× more likely** to go bad than revolvers. The ratio holds at
**1.78–1.85×** wherever the transactor/revolver split is the assigned one, across both
labels and both horizons. On the *behavioural* split at the 3-month horizon it narrows to
**1.08×** — climbers who have cleared their principal reclassify as transactors, which
dilutes the contrast. The inversion itself survives in every cell; only its magnitude
depends on how the split is drawn.

The consequence propagates into the scorecards. So et al.'s Model 4 — the composite
that segments transactors from revolvers — should improve on the single Model 1.
Instead it is worse in every one of the ten evaluable configurations, and
significantly worse in eight:

| Configuration | Model 1 AUC | Model 4 AUC | Δ | z | p |
|---|---:|---:|---:|---:|---:|
| late-fee, 12m, behavioural, set B | 0.9857 | 0.9520 | 0.0337 | 5.37 | 7.8 × 10⁻⁸ |
| late-fee, 12m, behavioural, set C | 0.9805 | 0.8057 | 0.1749 | 10.60 | 3.1 × 10⁻²⁶ |
| late-fee, 12m, assigned, set B | 0.9845 | 0.9452 | 0.0393 | 5.35 | 8.8 × 10⁻⁸ |
| late-fee, 12m, assigned, set C | 0.9781 | 0.8073 | 0.1709 | 10.31 | 6.4 × 10⁻²⁵ |
| late-fee, 3m, behavioural, set B | 0.9893 | 0.9771 | 0.0122 | 2.50 | 0.012 |
| late-fee, 3m, assigned, set B | 0.9893 | 0.9540 | 0.0353 | 4.23 | 2.3 × 10⁻⁵ |
| 90-DPD, 12m, behavioural, set C | 0.9462 | 0.8688 | 0.0774 | 2.15 | 0.032 |
| 90-DPD, 12m, assigned, set C | 0.9581 | 0.8696 | 0.0884 | 2.50 | 0.013 |
| 90-DPD, 12m, behavioural, set B | 0.9560 | 0.9449 | 0.0111 | 0.57 | 0.572 |
| 90-DPD, 12m, assigned, set B | 0.9340 | 0.9280 | 0.0060 | 0.15 | 0.881 |

Segmenting on a distinction that runs backwards makes the model **significantly
worse**. This is the expected behaviour of a correct implementation applied to data
whose premise does not hold.

**Eight of ten evaluable configurations reject at p < 0.05**: all six late-fee rows,
and the two 90-DPD rows built on characteristic set C. The two that do not reject are
both 90-DPD on set B, where the composite is worse by 0.006–0.011 AUC — worse in
direction, within noise in magnitude. On the rarer label the sample supports the
claim that segmenting does not help, but only sometimes supports the stronger claim
that it measurably hurts.

> **Two corrections to earlier versions of this section.** It reported six rejections,
> then seven. Neither was reproducible: the cascades were seeded with
> `hash(key) % 1000`, and Python salts string hashing per process unless
> `PYTHONHASHSEED` is set, which nothing here does. Over four runs the six late-fee
> comparisons rejected every time, but the 90-DPD verdicts flipped in three runs of
> ten. The seed is now `blake2b(key)` (`replicate_so.py:_stable_seed`), verified
> identical across fresh interpreters. The move from seven to eight is a separate
> cause: the category-share units fix changed every transaction in the model.

### 7.2 Khandani, Kim & Lo (2010) — CART on trailing behaviour

| Label | horizon | mean AUC | mean κ | base rate |
|---|---|---:|---:|---:|
| 90+ DPD | 3m | 0.947–0.989 | 0.423–0.813 | 3.0% |
| 90+ DPD | 6m | 0.943–0.958 | 0.405–0.795 | 3.4% |
| 90+ DPD | 12m | 0.966–0.997 | 0.464–0.756 | 3.9% |
| late fee | 3m | 0.978–0.984 | 0.808–0.829 | 21.6% |
| late fee | 6m | 0.937–0.979 | 0.699–0.834 | 23.3% |
| late fee | 12m | 0.971–0.977 | 0.825–0.847 | 26.2% |

> **κ and F are now measured at a threshold chosen on the training fold.** Both this
> section and §7.3 previously called `classification_scores` without a threshold, so
> it took the ROC tangency point of the *test* scores — choosing the cut with the
> labels being forecast. AUC is threshold-free and did not move; κ and F did, and the
> figures above are the honest ones. The decision rule is still the paper's (§5, equal
> cost of a false positive and gain of a true positive); only the information used to
> locate it changed.

The paper reports **AUC 0.83–0.89** across its ten evaluation windows. This model
runs at **0.94–0.997** — not better modelling, but an easier problem. Delinquency
here is **largely determined by income source**:

| Income source | 90+ DPD rate | lift |
|---|---:|---:|
| unemployed | 17.6% | 5.98 |
| transfers | 8.1% | 2.73 |
| pension | 3.5% | 1.19 |
| self-employed | 1.9% | 0.64 |
| payroll | 1.7% | 0.57 |
| *overall* | *2.95%* | *1.00* |

A 10× spread between the worst and best source, and a 0.0% rate for the `high`
income level, means one categorical variable still does most of the work. Real
portfolios do not decompose this cleanly.

**The gradient changed the ordering, which is worth reading.** Before it, the spread
was 38× and pensioners were the safest group in the population (0.6%). Now pensioners
are *third riskiest* at 3.5%, and payroll is the safest. Nothing about pensions
changed — but pensions are a fixed euro amount, so a Southern pensioner scaled to
0.554× is now genuinely close to the bill burden, whereas before the gradient the
same household sat comfortably above it. Regional income and distress are no longer
independent, and the population is less cleanly separable by source alone. The
macro-area lift now runs 0.08 (North) to 2.48 (South) — a 33× spread on a variable
that carried none before.

Two of the paper's constructs also fail structurally:

- **The balance-to-income stratifier runs backwards.** Khandani expects high
  balance-to-income to mark risk. Here the risk concentrates in the **low** tail:
  26.3% in the tail against 2.95% overall, a lift of **8.91** in the wrong
  direction. Debt is assigned by income quartile, so debtors are the better-off
  half of the population.
- **`overdue_to_income` is degenerate** — its 90th percentile is zero, because most
  consumers never carry an overdue bill, so the stratifier selects the entire
  sample.

### 7.3 Butaru et al. (2015) — C4.5 vs ridge logit vs random forest

Two-quarter horizon, primary portfolio (seed 42):

| Variable set | model | AUC | κ | F | verdict |
|---|---|---:|---:|---:|---|
| A (all) | C4.5-style tree | 0.9997 | 0.9731 | 0.9742 | almost perfect |
| A | ridge logistic | 0.8993 | 0.7709 | 0.7866 | substantial |
| A | random forest (20) | 0.9998 | 0.9731 | 0.9742 | almost perfect |
| C (behavioural only) | C4.5-style tree | 0.9544 | 0.5450 | 0.5689 | moderate |
| C | ridge logistic | 0.8824 | 0.3952 | 0.4326 | fair |
| C | random forest (20) | 0.9865 | 0.5036 | 0.5311 | moderate |

> As in §7.2, κ and F are now measured at a threshold taken from the **training**
> fold. They were previously read off the test fold's own labels and were optimistic
> by construction. AUC is threshold-free and is unchanged by the correction.

**This is the one clean positive replication.** Butaru et al.'s central finding —
that C4.5 and random forests outperform logistic regression — reproduces on
synthetic data, in both variable sets, by 7–10 AUC points. On set C the gap is
0.072 AUC (tree) and 0.104 (forest) over the ridge logit, and the κ ordering now
separates them clearly too: 0.545 and 0.504 against 0.395, which is the difference
between *moderate* and *fair* agreement on Landis & Koch.

The behavioural-only set C is the honest one, and it has moved twice. Before the
income gradient the three models sat at κ 0.711 / 0.490 / 0.597; after it they were
nearly tied at 0.562 / 0.501 / 0.538; with the threshold now chosen on the training
fold they read 0.545 / 0.395 / 0.504. The narrowing after the gradient was real —
once income varies continuously by region as well as by source, the trees' advantage
at carving axis-aligned regions out of a categorical driver shrinks. The re-widening
is a measurement correction, not a recovery: the ridge logit was benefiting most
from a threshold fitted to the test labels, so it lost the most when that stopped.

Cross-portfolio dispersion over the six seeds is modest — C4.5 at the 2-quarter
horizon: κ mean 0.626, sd 0.045, range 0.545–0.676; AUC mean 0.960, sd 0.006 — so
the ordering is not an artefact of one draw. The random forest is the most stable of
the three (AUC sd 0.003), the ridge logit the least (0.026).

The caveat is that the *levels* remain inflated for the reason in §7.2: with income
source doing most of the work, a tree that splits on it once is already most of the
way to a high score.

### 7.4 What the three replications say together

1. **The debt-to-distress relationship is inverted.** `_assign_debt` allocates debt
   by income quartile, so debtors are the better-off half of the population, while
   the households that fail to pay bills are the unemployed and transfer-income
   consumers who were never given debt in the first place. Nothing in the model
   makes debt *cause* distress.
2. **Delinquency is largely determined by income source**, so classifiers reach
   0.94–0.997 on the Khandani replication (§7.2) where the literature reports
   0.83–0.89. The macro-area gradient narrowed
   the source spread from 38× to 10× and cost the classifiers a few points, but did not
   close the gap.
3. **There are no straight-rollers.** Of the account-months that were current at
   `as_of` — 9,216 at the 3-month horizon, 4,608 at 6 months and 13,824 at 12 months —
   **zero** reach 90+ DPD within the horizon, at any horizon, in any variable set,
   unchanged by the gradient. Arrears are a persistent liquidity state rather than a shock, which makes
   Khandani's Table 8 transition analysis degenerate here.

Taken with the `is_debtor` ceiling from §4 — ~0.67 on logistic regression, 0.77 on
the random forest, the model produces **either
near-noise or near-certainty, and very little in the realistic middle.** The
macro-area income gradient pushes modestly against this — it widens the income
distribution (Gini 0.30 → 0.34) and moves several honest AUCs down toward the
realistic middle — but it does not address the inversion, which is about debt
causation rather than income dispersion.

The smallest change that would make all three papers' premises hold is a
**debt-service burden that competes with bill payments for the same euros** — that
is, making debt a cause of distress rather than a correlate of income. That is a
model change, not an analysis change, and it is not made here.

---

## 8. Limitations

Carried forward from the paper-vs-code gap audit (`flows_and_papers.html` §F) and
the analysis above. Items that have since been closed are kept and marked
**RESOLVED** rather than deleted, so the audit trail survives:

1. **`base_prob = 0.6`** (`model.py`) is a self-described tuning knob that sets how
   often any consumer buys anything. It therefore drives total transaction volume
   and every euro aggregate in this section. It is hard-coded in `model.py`, in
   violation of that file's own contract that empirical constants live in
   `numbers.py`, and it is not swept.
2. **RESOLVED — the ticket-size mismatch was a units bug, and is fixed.** This item
   used to read "ticket sizes average ≈ €45, not the cited €28", citing a
   share-weighted mean of €45.53 against a measured €43.14. Both figures were
   artefacts of the same error: `CATEGORY_SHARES` are shares of *euros spent*
   (Emiliozzi et al. 2023 §2.1, Fig. 4/6), but `sample_category()` was using them
   directly as the probability of *picking* a category, and weighting the ticket
   means by them compounded the mistake. Categories are now drawn with probability
   `share / E[ticket]`, normalised, so the realised euro mix matches the paper by
   construction (worst category error 10.8 pp → 0.6 pp); `f02_spend_mix_vs_paper`
   plots the corrected mix against the paper baseline. The share-weighted mean is
   now **€38.06** and a real run measures **€36.73** (`docs/MODEL_REFERENCE.md`).
   The "cited €28" half of the claim was also wrong: it was attributed to a §9 of a
   paper that has no §9, and the attribution has been removed rather than repaired.
   Any statement about mean spend should still use the measured value.
3. **The macro-area income gradient rests on a single paper, and on a two-way
   split.** `MACRO_AREA_INCOME_RELATIVE` is anchored on Semeraro et al. (2020) p. 5
   / p. 27 alone — SHIW publishes no geographic breakdown at all, so there is no
   second Italian source to triangulate against. The paper treats "Centre-North" as
   one bloc, so North and Centre are not distinguished; any real North-vs-Centre
   difference is therefore absent by construction. The gradient is also applied to
   income only: spending propensity, bill amounts and debt participation carry no
   area term, so the South is poorer but not otherwise different.
   *(This item previously read "documented but not implemented" — five documents
   claimed a gradient the code did not have. That is now fixed.)*
4. **The saver/subsister confound** of §5.3 is a modelling artefact.
5. **Single-configuration internal studies.** Studies 0/A/B/C/D are reported at one
   seed and one population size. They are deterministic and pinned, but not
   averaged over seeds; the replications in §7 are the only multi-seed evidence.
   Relatedly, each AUC is the mean of five per-fold values from a single unshuffled
   `StratifiedKFold(5)` split; no confidence interval is computed, and the tolerances
   in the pinned table are reproducibility bounds, not sampling error.
6. **The feature transform distorts two things, knowingly.** `features.money_log1p`
   applies `clip(lower=0)` before `log1p`, which destroys the *sign* of the two
   columns where negativity is the signal — `cur_balance` and
   `LEAK_min_balance_proxy`, the latter documented in the code as "`< 0` reveals a
   chronic overdraft". Every overdraft depth is collapsed to exactly 0, turning a
   continuous measure into a partial indicator. Separately, the money-column selector
   matches by substring, so the ratio `ticket_cv` and the counts `n_bills` and
   `n_income` are log-transformed as though they were euro magnitudes. Both were left
   in place deliberately: correcting them would re-pin all 21 headline numbers for a
   change that does not affect any conclusion in this section.
7. **Zero and absent are the same value.** The feature builder fills missing
   aggregates with `0.0`, so "never purchased anything" and "spread spending perfectly
   evenly" both give `weekday_concentration = 0`.
8. **`is_debtor` and the `+debt` suffix are different populations.** `is_debtor` means
   "was ever assigned a debtor subtype"; the `+debt` in `financial_status` means "still
   holds debt at the end of the run", which climbers who clear their principal do not.
   Both appear in the same frame.

---

## 9. Reproduction

```bash
uv sync

# everything, into a fresh timestamped runs/ directory
uv run python scripts/run_all.py

# or the pieces behind this section
uv run python scripts/validation_report.py --out runs/latest   # §2–§6, exits 1 on drift
uv run python scripts/build_prediction_page.py --out runs/latest  # §7 (~12 min)
uv run pytest -q -m slow                                        # 5 long-horizon floor tests

# collect it all for hand-off
uv run python scripts/build_thesis_package.py
```

Machine-readable outputs, as they are named **inside the hand-off package**:
`thesis_package/data/validation_report.json` (§2–§6),
`thesis_package/data/replicate_so.json`, `.../replicate_khandani.json`,
`.../replicate_butaru.json` (§7). The browsable versions with figures are
`thesis_package/results/results.html` and `.../prediction_and_papers.html`. Running the
commands above instead writes them to `runs/<timestamp>/`, flat, without the `data/` and
`results/` split — the package layout is created by `build_thesis_package.py`.
