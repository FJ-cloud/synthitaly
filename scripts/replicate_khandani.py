#!/usr/bin/env python3
"""Replication of Khandani, Kim & Lo (2010) — CART forecasts of consumer credit risk.

    uv run python scripts/replicate_khandani.py

*Consumer credit-risk models via machine-learning algorithms.* Journal of Banking &
Finance 34, 2767-2787, doi:10.1016/j.jbankfin.2010.06.001.
See ``docs/REFERENCES.md`` §④.

What the paper does
-------------------
Generalized classification and regression trees (CART, Breiman et al. 1984) on a major
commercial bank's customers, combining transaction, credit-bureau and deposit data
(their Table 4). The target is 90-days-or-more delinquency within a 3-, 6- or 12-month
forward window. Transaction inputs are averaged over the prior six months (their
section 4.2). The evaluation is strictly forward-walking: their Table 5 lists ten
calibration/testing periods in which the model is trained on delinquencies observable
at the forecast date and then applied to a *later* window, "to minimize the effects of
look-ahead bias".

They report:

* **Table 7** — the average forecast among accounts that did go 90+ delinquent against
  those that did not (61.2 vs 1.0 in their May-July 2008 window).
* **Table 8** — the same, restricted to accounts *current* at the forecast date. These
  are the "straight-rollers", and they call it "a harder learning problem".
* **Figure 16** — the ROC curve with the classification threshold traced along it, and
  the 45-degree tangency rule for the equal-cost optimum.
* **Table 9** — the kappa statistic at that threshold, read against Landis & Koch
  (1977), together with the area under the ROC curve.

Two of their exploratory stratifications (their section 3) are also carried here as
model inputs: the credit-card-balance-to-income ratio and the income-shock variable,
"the difference between the current month's income and the 6-month moving-average of
the income, ... divided by the standard deviation of income over the same window".

What is not replicated
----------------------
* **The CScore benchmark** (their section 4.3). There is no credit bureau in this
  model, so there is no external score to compare against.
* **The credit-line-cut cost/benefit in euros** (their section 6). That calculation
  needs a run-up-to-default balance and a recovery assumption, neither of which this
  model carries.
* **Credit-bureau inputs** — roughly half of their Table 4. This model has one bank's
  view, so only the transaction and deposit halves have counterparts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _papers as PP  # noqa: E402

from synthitaly import creditscoring as CS  # noqa: E402

# Their reported figures, quoted next to ours.
PAPER_RESULTS = {
    "delinquency_rate_range": (0.020, 0.025),
    "mean_forecast_bad_example": 61.2,
    "mean_forecast_good_example": 1.0,
    "kappa_range": (0.66, 0.79),
    "auc_note": "0.83-0.89 across their ten evaluation windows",
    "n_periods": 10,
    "r2_delinquency": 0.85,
}

# CART. The paper cites Breiman et al. (1984), which is the algorithm scikit-learn
# implements, so this is the same method rather than a substitute. min_samples_leaf
# stands in for their pruning; it is swept in replicate_butaru.py.
TREE = dict(min_samples_leaf=50, random_state=0)


def _fit_predict(tr: pd.DataFrame, te: pd.DataFrame, cols: list[str], target: str):
    """Fit on ``tr``, score ``te``, and return the cut chosen on ``tr`` alone.

    The threshold matters. ``classification_scores`` defaults to the ROC tangency
    point of whatever scores it is handed, so calling it on the test scores picks
    the cut using the test labels — the very thing being forecast. AUC is
    threshold-free and unaffected, but kappa, F, precision and recall are then
    optimistic by construction. Taking the tangency point from the *training*
    scores keeps the paper's decision rule (Khandani et al. §5) while using only
    information available at origination.

    The tree is regularised (min_samples_leaf=50), so its in-sample scores are
    graded rather than the degenerate 0/1 an unconstrained tree would give, and
    the tangency point is well defined.
    """
    clf = DecisionTreeClassifier(**TREE).fit(tr[cols], tr[target])
    train_score = clf.predict_proba(tr[cols])[:, 1]
    thr = CS.roc_tangency_threshold(tr[target].to_numpy().astype(bool), train_score)
    return clf, clf.predict_proba(te[cols])[:, 1], thr


def rolling_evaluation(
    b: PP.Bundle, cols: list[str], target: str, horizon: int
) -> dict:
    """The paper's Table 5 design: calibrate on what was observable, forecast forward.

    At each origination month ``t`` the model is trained on the rows whose *entire*
    label window closed on or before ``t`` — so the training labels were realised
    facts at the time — and then applied to the rows originated at ``t``, whose labels
    lie strictly in the future. Nothing in the training set postdates the forecast.
    """
    pan = b.panel
    col = f"{target}_{horizon}m"
    usable = pan[pan[f"horizon_complete_{horizon}m"]]
    months = sorted(usable["month_idx"].unique())

    periods: list[dict] = []
    for t in months:
        # a row originated at u has its label window closed by u + horizon
        train = usable[usable["month_idx"] + horizon <= t]
        test = usable[usable["month_idx"] == t]
        if len(train) < 200 or train[col].nunique() < 2 or test[col].nunique() < 2:
            continue
        clf, score, thr = _fit_predict(train, test, cols, col)
        y = test[col].to_numpy().astype(bool)
        rec = CS.classification_scores(y, score, threshold=thr)
        rec.update({
            "origination_month": int(t),
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
            "importance": dict(sorted(
                ((c, float(v)) for c, v in zip(cols, clf.feature_importances_, strict=True) if v > 0),
                key=lambda kv: -kv[1])[:15]),
        })
        # Table 8 — the straight-roller restriction
        cur = test["was_current"].to_numpy().astype(bool)
        if cur.sum() > 20 and len(np.unique(y[cur])) > 1:
            rec["straight_roller"] = {
                "n": int(cur.sum()),
                "n_bad": int(y[cur].sum()),
                "mean_score_bad": float(score[cur][y[cur]].mean() * 100),
                "mean_score_good": float(score[cur][~y[cur]].mean() * 100),
                "auc": float(CS.gini(y[cur], score[cur]) / 2 + 0.5),
            }
        else:
            rec["straight_roller"] = {
                "n": int(cur.sum()), "n_bad": int(y[cur].sum()), "degenerate": True,
                "reason": "no clean account reached 90+ DPD inside the horizon",
            }
        periods.append(rec)

    if not periods:
        return {"skipped": True, "reason": f"no evaluable period at {horizon}m"}

    def avg(k: str) -> float:
        vals = [p[k] for p in periods if isinstance(p.get(k), (int, float))
                and np.isfinite(p[k])]
        return float(np.mean(vals)) if vals else float("nan")

    imp: dict[str, float] = {}
    for p in periods:
        for c, v in p["importance"].items():
            imp[c] = imp.get(c, 0.0) + v / len(periods)

    return {
        "n_periods": len(periods),
        "periods": periods,
        "mean_auc": avg("auc"), "mean_kappa": avg("kappa"),
        "mean_f_measure": avg("f_measure"), "mean_precision": avg("precision"),
        "mean_recall": avg("recall"), "mean_base_rate": avg("base_rate"),
        "mean_score_bad": avg("mean_score_bad"), "mean_score_good": avg("mean_score_good"),
        "kappa_verdict": CS.kappa_verdict(avg("kappa")),
        "importance": dict(sorted(imp.items(), key=lambda kv: -kv[1])[:15]),
    }


def stratification(b: PP.Bundle, target: str, horizon: int) -> dict:
    """Their section 3 in miniature: does the top decile of a candidate variable carry
    a visibly higher forward delinquency rate than everybody else?

    This is how the paper motivates its inputs — Figure 7 for balance-to-income,
    Figure 9 for the income shock — and it shows an input as a mechanism rather than
    as a bar on an importance chart.
    """
    col = f"{target}_{horizon}m"
    d = b.panel[b.panel[f"horizon_complete_{horizon}m"]]
    out = {}
    for var, direction in (("balance_to_income", "low"), ("income_shock", "low"),
                           ("overdue_to_income", "high"), ("total_income", "low"),
                           ("LEAK_debt_to_income", "high")):
        if var not in d.columns:
            continue
        x = d[var].to_numpy(float)
        q = float(np.quantile(x, 0.10 if direction == "low" else 0.90))
        grp = x <= q if direction == "low" else x >= q
        rec = {
            "direction": direction,
            "cutoff": q,
            "rate_in_tail": float(d[col].to_numpy()[grp].mean()),
            "rate_overall": float(d[col].mean()),
            "n_tail": int(grp.sum()),
        }
        # A variable that is zero for most rows has a degenerate decile: the cutoff
        # lands on the mode and the "tail" swallows the sample. Say so rather than
        # printing a tail rate equal to the overall rate as though it were a finding.
        if grp.mean() > 0.5:
            rec["degenerate"] = True
            rec["reason"] = (f"the {'10th' if direction == 'low' else '90th'} percentile "
                             f"is {q:g}, which {grp.mean():.0%} of rows share — this "
                             "variable is zero for most of the panel, so it has no tail")
        else:
            rec["lift"] = (rec["rate_in_tail"] / rec["rate_overall"]
                           if rec["rate_overall"] > 0 else None)
        out[var] = rec
    return out


def by_attribute(b: PP.Bundle, target: str, horizon: int) -> dict:
    """Forward outcome rate broken down by each ground-truth attribute.

    Not part of the paper — this is the diagnostic that explains its results. Khandani
    et al. have no equivalent because in their data the answer is not a near-function of
    one attribute; here it is, and naming that attribute is the point.
    """
    col = f"{target}_{horizon}m"
    d = b.panel[b.panel[f"horizon_complete_{horizon}m"]].merge(
        b.labels, on="consumer_id", how="left")
    out = {}
    for attr in ("income_source", "income_level", "debtor_subtype", "macro_area",
                 "is_saver"):
        g = d.groupby(attr)[col].agg(["mean", "size"])
        overall = float(d[col].mean())
        out[attr] = {
            str(k): {"rate": float(v["mean"]), "n": int(v["size"]),
                     "lift": float(v["mean"] / overall) if overall > 0 else None}
            for k, v in g.iterrows()
        }
        out[attr]["_overall"] = {"rate": overall, "n": int(len(d)), "lift": 1.0}
    return out


def run(seed: int = PP.PRIMARY_SEED) -> dict:
    b = PP.bundle(seed)
    res: dict = {
        "paper": PAPER_RESULTS,
        "config": {"seed": seed, **PP.CONFIG, "tree": TREE,
                   "long_run_days": PP.LONG_DAYS},
        "results": {},
        "stratification": {},
        "run_days": {},
    }
    long_b = None
    for target in ("y_90dpd", "y_latefee"):
        for horizon in PP.KHANDANI_HORIZONS:
            # The 12-month horizon has no evaluable origination month on a 720-day
            # run — a row needs six months of trailing window, twelve ahead, and a
            # training set whose labels have already closed. The paper forecasts at
            # twelve months, so that horizon is run on the longer simulation instead
            # of being dropped. Every table records which run it came from.
            use = b
            if horizon >= 9:
                long_b = long_b or PP.bundle_long(seed)
                use = long_b
            for set_name in ("A", "B", "C"):
                key = f"{target}|{horizon}m|set{set_name}"
                res["results"][key] = rolling_evaluation(
                    use, use.columns(set_name), target, horizon
                )
                res["run_days"][key] = use.n_days
        res["stratification"][target] = stratification(b, target, 3)
        res.setdefault("by_attribute", {})[target] = by_attribute(b, target, 3)
    return res


def main() -> int:
    res = run()
    print("Khandani, Kim & Lo (2010) — CART forecasts of 90+ day delinquency")
    print(f"  config: {PP.describe_config()}")
    print(f"  paper's own delinquency rate: {PAPER_RESULTS['delinquency_rate_range'][0]:.1%}"
          f"-{PAPER_RESULTS['delinquency_rate_range'][1]:.1%} of accounts")
    print()
    hdr = (f"  {'target':10s} {'h':>4s} {'set':>4s} {'days':>5s} {'per':>4s} {'base':>7s} "
           f"{'AUC':>7s} {'kappa':>7s} {'verdict':>14s} {'sc_bad':>7s} {'sc_good':>8s} "
           f"{'SR bad':>7s}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for key, r in res["results"].items():
        if r.get("skipped"):
            print(f"  {key:24s} skipped — {r['reason']}")
            continue
        target, h, s = key.split("|")
        sr = sum(p["straight_roller"].get("n_bad", 0) for p in r["periods"])
        print(f"  {target:10s} {h:>4s} {s[-1]:>4s} {res['run_days'][key]:>5d} "
              f"{r['n_periods']:>4d} {r['mean_base_rate']:>7.4f} {r['mean_auc']:>7.4f} "
              f"{r['mean_kappa']:>7.4f} {r['kappa_verdict']:>14s} {r['mean_score_bad']:>7.1f} "
              f"{r['mean_score_good']:>8.1f} {sr:>7d}")
    print()
    print("  Top variables by mean CART importance (y_90dpd, 3m, Set C):")
    r = res["results"].get("y_90dpd|3m|setC", {})
    for c, v in list(r.get("importance", {}).items())[:8]:
        print(f"    {v:6.3f}  {c}")
    print()
    print("  Section-3 style stratification (y_90dpd, 3m):")
    for var, s in res["stratification"]["y_90dpd"].items():
        if s.get("degenerate"):
            print(f"    {var:22s} no tail — {s['reason']}")
            continue
        print(f"    {var:22s} {s['direction']:>5s} tail rate {s['rate_in_tail']:.4f} "
              f"vs overall {s['rate_overall']:.4f}  lift {s['lift']:5.2f}x  (n={s['n_tail']})")
    out = Path(PP.ROOT) / "runs" / "latest"
    if out.exists():
        (out / "replicate_khandani.json").write_text(json.dumps(res, indent=2, default=str))
        print(f"\n  wrote {out / 'replicate_khandani.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
