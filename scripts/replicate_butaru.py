#!/usr/bin/env python3
"""Replication of Butaru, Chen, Clark, Das, Lo & Siddique (2015) — the horse race.

    uv run python scripts/replicate_butaru.py

*Risk and Risk Management in the Credit Card Industry.* NBER Working Paper 21305.
See ``docs/REFERENCES.md`` §④ for the full citation.

What the paper does
-------------------
Three classifiers, the same 87 attributes, run against one another on 5.7-6.6 million
credit-card accounts from six anonymous banks (their section III):

===================================  ======================================
Paper                                Here
===================================  ======================================
Weka J48, the C4.5 algorithm         ``DecisionTreeClassifier(criterion="entropy")``
Ridge logistic (Cessie & van         ``LogisticRegression(C=1.0)`` — its default
Houwelingen 1992), quadratic         penalty is the quadratic one they write out,
penalty, quasi-Newton                ``l(beta) - lambda ||beta||^2``
Random forest, **20 trees**          ``RandomForestClassifier(n_estimators=20)``
===================================  ======================================

The tree is the one real substitution and it is a partial one. Entropy splitting is
C4.5's splitting rule, so that half matches; C4.5's error-based pruning and its
handling of multi-way splits have no scikit-learn equivalent, and ``min_samples_leaf``
stands in for them. This is flagged wherever a tree number is reported.

The dependent variable is an account 90 or more days past due (section III.B), forecast
"over three different time horizons — two, three, and four quarters out". Models are
re-estimated over rolling windows and never see future data (section III.C).
Performance is precision, recall, the F-measure and the kappa statistic (section
III.D), and their appendix sweeps the acceptance threshold to check the optimum is flat.

Their headline: the C4.5 and random-forest models beat logistic regression, with
accuracy ranging "from 63.8% at the worst performing bank to 81.6% at the best".

Portfolios
----------
The paper's six banks are six genuinely different populations. This model has one, so
the six portfolios here are **six seeds**. The spread between them is Monte-Carlo error
and nothing else — a materially weaker claim than theirs, and labelled as such in every
table.

Run length
----------
This script runs 1,440 simulated days rather than the 720 used everywhere else in the
repo, because the paper's own design demands it. A forecast at horizon *h* needs both a
trailing window behind the origination month and a full *h* ahead of it, and the
training rows need their labels already realised — at 720 days the three- and
four-quarter horizons have **no** evaluable origination month at all. Extending the
simulation is the honest fix; truncating the design would not be a replication.

What is not replicated
----------------------
* **Macroeconomic attributes.** They merge ZIP-level HPI, employment and wage series.
  This model has three macro-areas and no time-varying macroeconomy.
* **The value-added / cost-savings analysis** (their section V), which prices a
  credit-line cut. No balance run-up or recovery rate exists here to price.
* **Credit-bureau attributes**, for the same reason as in the Khandani replication.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _papers as PP  # noqa: E402

from synthitaly import creditscoring as CS  # noqa: E402

N_DAYS = PP.LONG_DAYS
QUARTER_MONTHS = 3

# Their re-estimation cadence, section III.C: "we estimate separate machine-learning
# model every six months starting with the period ending 2010Q4", which gives them six
# models per horizon. Scoring at every origination month instead would be *more*
# evaluation than the paper performs, and costs roughly six times as much.
REESTIMATE_EVERY_MONTHS = 6

PAPER_RESULTS = {
    "accuracy_range": (0.638, 0.816),
    "kappa_substantial": 0.60,
    "n_banks": 6,
    "n_accounts": "5.7-6.6 million",
    "finding": "C4.5 and random-forest models outperform logistic regression",
    "rf_trees": 20,
}


def models() -> dict:
    """The three classifiers. Kept in one place so every table is built from the
    same definitions, and so the RF tree count stays at the paper's 20."""
    return {
        "C4.5-style tree": lambda m: DecisionTreeClassifier(
            criterion="entropy", min_samples_leaf=m, random_state=0),
        # Ridge logistic. scikit-learn's default penalty is already the quadratic one
        # the paper writes out — l(beta) - lambda ||beta||^2 — so it is not passed
        # explicitly; the `penalty=` argument is deprecated as of scikit-learn 1.8.
        # C is the inverse of their lambda.
        "ridge logistic": lambda m: make_pipeline(
            StandardScaler(),
            LogisticRegression(C=1.0, max_iter=2000, class_weight="balanced")),
        "random forest (20)": lambda m: RandomForestClassifier(
            n_estimators=PAPER_RESULTS["rf_trees"], min_samples_leaf=m,
            random_state=0, n_jobs=-1),
    }


_bundle_long = PP.bundle_long


def rolling_horse_race(
    b: PP.Bundle, cols: list[str], target: str, quarters: int, min_leaf: int = 50
) -> dict:
    """All three classifiers over the same rolling origination months.

    Training rows are those whose label window has already closed by the origination
    month, so no model ever sees an outcome that had not happened yet — the paper's
    "as if we were in that time period".
    """
    h = quarters * QUARTER_MONTHS
    col = f"{target}_{h}m"
    usable = b.panel[b.panel[f"horizon_complete_{h}m"]]
    out: dict = {"horizon_quarters": quarters, "horizon_months": h, "by_model": {}}

    # Re-estimate on their cadence rather than every month, counting back from the
    # last evaluable origination so the most recent period is always included.
    all_months = sorted(usable["month_idx"].unique())
    schedule = sorted(all_months[::-1][::REESTIMATE_EVERY_MONTHS])
    out["origination_months"] = [int(t) for t in schedule]

    for name, make in models().items():
        periods = []
        for t in schedule:
            train = usable[usable["month_idx"] + h <= t]
            test = usable[usable["month_idx"] == t]
            if len(train) < 300 or train[col].nunique() < 2 or test[col].nunique() < 2:
                continue
            clf = make(min_leaf).fit(train[cols], train[col])
            score = clf.predict_proba(test[cols])[:, 1]
            # Choose the cut on the training fold, not the test fold. Left to its
            # default, classification_scores takes the ROC tangency point of the
            # scores it is given — i.e. using the labels being forecast, which makes
            # kappa and F optimistic. AUC is threshold-free and does not move.
            thr = CS.roc_tangency_threshold(
                train[col].to_numpy().astype(bool),
                clf.predict_proba(train[cols])[:, 1],
            )
            rec = CS.classification_scores(
                test[col].to_numpy().astype(bool), score, threshold=thr)
            rec["origination_month"] = int(t)
            rec["train_rows"] = int(len(train))
            periods.append(rec)
        if not periods:
            out["by_model"][name] = {
                "skipped": True,
                "reason": f"no origination month has both a closed training window and "
                          f"a full {h}-month forward window",
            }
            continue
        agg = {f"mean_{k}": float(np.mean([p[k] for p in periods]))
               for k in ("auc", "kappa", "f_measure", "precision", "recall", "base_rate")}
        agg["kappa_verdict"] = CS.kappa_verdict(agg["mean_kappa"])
        agg["n_periods"] = len(periods)
        agg["periods"] = periods
        out["by_model"][name] = agg
    return out


def threshold_sweep(b: PP.Bundle, cols: list[str], target: str, quarters: int) -> dict:
    """Their Figures A1-A3: is the optimum flat in the acceptance threshold?

    A flat optimum means the choice of cut-off is not load-bearing, which is what makes
    the F-measure and kappa comparisons across models meaningful in the first place.
    """
    h = quarters * QUARTER_MONTHS
    col = f"{target}_{h}m"
    usable = b.panel[b.panel[f"horizon_complete_{h}m"]]
    ts = sorted(usable["month_idx"].unique())
    if len(ts) < 2:
        return {"skipped": True}
    t = ts[len(ts) // 2]
    train = usable[usable["month_idx"] + h <= t]
    test = usable[usable["month_idx"] == t]
    if len(train) < 300 or train[col].nunique() < 2 or test[col].nunique() < 2:
        return {"skipped": True}
    y = test[col].to_numpy().astype(bool)
    grid = np.round(np.arange(0.05, 0.96, 0.05), 2)
    out: dict = {"origination_month": int(t), "thresholds": grid.tolist(), "by_model": {}}
    for name, make in models().items():
        clf = make(50).fit(train[cols], train[col])
        s = clf.predict_proba(test[cols])[:, 1]
        out["by_model"][name] = {
            "f_measure": [CS.f_measure(y, s >= g) for g in grid],
            "kappa": [CS.kappa(y, s >= g) for g in grid],
            "tangency": float(CS.roc_tangency_threshold(y, s)),
        }
    return out


def overfitting_sweep(b: PP.Bundle, cols: list[str], target: str, quarters: int) -> dict:
    """Their M sweep: minimum instances per leaf, in-sample against out-of-sample.

    "when M = 2, the algorithm will continue to [split] ... increasing M are
    overfitting the sample." The signature of overfitting is the in-sample score
    continuing to improve as M falls while the out-of-sample score turns over.
    """
    h = quarters * QUARTER_MONTHS
    col = f"{target}_{h}m"
    usable = b.panel[b.panel[f"horizon_complete_{h}m"]]
    ts = sorted(usable["month_idx"].unique())
    if len(ts) < 2:
        return {"skipped": True}
    t = ts[len(ts) // 2]
    train = usable[usable["month_idx"] + h <= t]
    test = usable[usable["month_idx"] == t]
    if len(train) < 300 or train[col].nunique() < 2 or test[col].nunique() < 2:
        return {"skipped": True}
    rows = []
    for m in (2, 5, 10, 25, 50, 100, 200, 400):
        clf = DecisionTreeClassifier(criterion="entropy", min_samples_leaf=m,
                                     random_state=0).fit(train[cols], train[col])
        rows.append({
            "min_samples_leaf": m,
            "n_leaves": int(clf.get_n_leaves()),
            "auc_in_sample": float(CS.gini(train[col], clf.predict_proba(train[cols])[:, 1]) / 2 + 0.5),
            "auc_out_of_sample": float(CS.gini(test[col], clf.predict_proba(test[cols])[:, 1]) / 2 + 0.5),
        })
    return {"origination_month": int(t), "sweep": rows}


def run(seeds: tuple[int, ...] = PP.SEEDS) -> dict:
    res: dict = {
        "paper": PAPER_RESULTS,
        "config": {"n_days": N_DAYS, "seeds": list(seeds),
                   "n_consumers": PP.CONFIG["n_consumers"],
                   "quarters": list(PP.BUTARU_HORIZONS_Q)},
        "portfolios": {},
    }
    primary = None
    for seed in seeds:
        t0 = time.time()
        b = _bundle_long(seed)
        if primary is None:
            primary = b
        cols_c = b.columns("C")
        per_seed: dict = {}
        for q in PP.BUTARU_HORIZONS_Q:
            per_seed[f"{q}Q"] = rolling_horse_race(b, cols_c, "y_90dpd", q)
        res["portfolios"][str(seed)] = per_seed
        print(f"    seed {seed}: {time.time() - t0:5.1f}s", flush=True)

    # Set A / Set B comparison and the two sweeps: primary seed only.
    res["variable_sets"] = {}
    for s in ("A", "B", "C"):
        res["variable_sets"][s] = rolling_horse_race(
            primary, primary.columns(s), "y_90dpd", 2)
    res["threshold_sweep"] = threshold_sweep(primary, primary.columns("C"), "y_90dpd", 2)
    res["overfitting_sweep"] = overfitting_sweep(primary, primary.columns("C"), "y_90dpd", 2)
    res["latefee"] = {f"{q}Q": rolling_horse_race(primary, primary.columns("C"),
                                                  "y_latefee", q)
                      for q in PP.BUTARU_HORIZONS_Q}

    # Cross-portfolio spread, the paper's Table 4 reading.
    spread: dict = {}
    for q in PP.BUTARU_HORIZONS_Q:
        for name in models():
            vals = [res["portfolios"][str(s)][f"{q}Q"]["by_model"][name].get("mean_kappa")
                    for s in seeds]
            vals = [v for v in vals if v is not None and np.isfinite(v)]
            aucs = [res["portfolios"][str(s)][f"{q}Q"]["by_model"][name].get("mean_auc")
                    for s in seeds]
            aucs = [v for v in aucs if v is not None and np.isfinite(v)]
            if vals:
                spread[f"{q}Q|{name}"] = {
                    "kappa_mean": float(np.mean(vals)), "kappa_sd": float(np.std(vals)),
                    "kappa_min": float(np.min(vals)), "kappa_max": float(np.max(vals)),
                    "auc_mean": float(np.mean(aucs)), "auc_sd": float(np.std(aucs)),
                    "n_portfolios": len(vals),
                }
    res["spread"] = spread
    return res


def main() -> int:
    print("Butaru, Chen, Clark, Das, Lo & Siddique (2015) — three-model horse race")
    print(f"  {PP.CONFIG['n_consumers']} consumers x {N_DAYS} days, "
          f"{len(PP.SEEDS)} seeds as portfolios, Set C variables")
    print(f"  paper: {PAPER_RESULTS['finding']}")
    print()
    res = run()
    print()
    hdr = (f"  {'horizon':>8s} {'model':>20s} {'AUC mean':>9s} {'AUC sd':>8s} "
           f"{'kappa mean':>11s} {'kappa sd':>9s} {'min':>7s} {'max':>7s}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for key, s in res["spread"].items():
        q, name = key.split("|")
        print(f"  {q:>8s} {name:>20s} {s['auc_mean']:>9.4f} {s['auc_sd']:>8.4f} "
              f"{s['kappa_mean']:>11.4f} {s['kappa_sd']:>9.4f} "
              f"{s['kappa_min']:>7.4f} {s['kappa_max']:>7.4f}")
    print()
    print("  Variable sets (2Q horizon, primary seed):")
    for s, r in res["variable_sets"].items():
        label, _ = PP.VARIABLE_SETS[s]
        for name, m in r["by_model"].items():
            if m.get("skipped"):
                continue
            print(f"    Set {s} ({label[:34]:34s}) {name:20s} "
                  f"AUC {m['mean_auc']:.4f}  kappa {m['mean_kappa']:.4f}")
    print()
    ov = res["overfitting_sweep"]
    if not ov.get("skipped"):
        print("  Overfitting sweep (their M), C4.5-style tree:")
        print(f"    {'M':>5s} {'leaves':>7s} {'AUC in':>8s} {'AUC out':>8s}")
        for r in ov["sweep"]:
            print(f"    {r['min_samples_leaf']:>5d} {r['n_leaves']:>7d} "
                  f"{r['auc_in_sample']:>8.4f} {r['auc_out_of_sample']:>8.4f}")
    out = Path(PP.ROOT) / "runs" / "latest"
    if out.exists():
        (out / "replicate_butaru.json").write_text(json.dumps(res, indent=2, default=str))
        print(f"\n  wrote {out / 'replicate_butaru.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
