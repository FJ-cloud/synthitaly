#!/usr/bin/env python3
"""Replication of So, Thomas, Seow & Mues — the Transactor/Revolver scorecard.

    uv run python scripts/replicate_so.py

*Using a Transactor/Revolver scorecard to make credit and pricing decisions.*
Southampton Management School / Nottingham University Business School Malaysia.
See ``docs/REFERENCES.md`` §④ for the full citation.

What the paper does
-------------------
Four logistic scorecards on 6,308 Hong Kong credit-card accounts (1,577 Bad, 4,731
Good), each built the same way (their section 2): weight-of-evidence coarse
classification of every characteristic, stepwise logistic regression, and **ten-fold
cross validation done by deciles** — "we split the dataset into deciles and applied
cross validation, by repeatedly leaving out one decile to test the results and building
a scorecard on the remaining nine deciles". They report mean coefficients with the
standard deviation across the ten scorecards, mean Gini on the ten holdouts, and
compare Model 1 against Model 4 with the DeLong, DeLong & Clarke-Pearson test.

    Model 1  Good/Bad over everybody              (their Gini 0.522)
    Model 2  Transactor/Revolver over everybody
    Model 3  Good/Bad restricted to Revolvers     (their Gini 0.519)
    Model 4  P(G|x) = P(T|x) + P(R|x) P(G|x,R)    (their Gini 0.522, n.s. vs Model 1)

Model 4 exists because of a structural claim: "Since transactors pay off all their
balance each period, they cannot default and so all Transactors must be Goods."

What is replicated here
-----------------------
All four models, the WoE + stepwise + ten-decile-fold procedure, the Gini, and the
DeLong comparison. The scorecard is cross-sectional, as an application scorecard is:
characteristics over the trailing window at one origination month, outcome over the
following performance period.

Two Transactor/Revolver definitions are carried side by side:

  (a) *behavioural* — a Revolver carried a debt balance across a month boundary in the
      trailing window, which is the paper's own definition translated to this ledger;
  (b) *assigned* — the ``is_debtor`` attribute the model itself drew.

What is not replicated
----------------------
Sections 5 and 6 — the credit-card profitability model, the take probability and the
optimal interest rate. This model has no revenue side: no interchange fee, no interest
income, no pricing decision. Nothing in it could produce those numbers, so they are
omitted rather than approximated.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _papers as PP  # noqa: E402

from synthitaly import creditscoring as CS  # noqa: E402

N_FOLDS = 10  # "we split the dataset into deciles"

# The paper works with a fixed list of about ten characteristics (their Table 1),
# chosen before the ten scorecards are built — footnote 1: "We have used characteristic
# selection to come up with this list of variables." The panel offers 33-40 columns, so
# the same step is applied here: screen on out-of-sample information value, then keep
# the strongest MAX_CHARACTERISTICS. Doing it once rather than inside each fold is what
# the paper describes and is also what makes the run tractable; the cost is that the
# characteristic *list* has seen all the rows, while every coefficient, bin boundary and
# reported Gini still comes from the nine training deciles alone.
MAX_CHARACTERISTICS = 12


def _stable_seed(key: str) -> int:
    """A per-run seed derived from the run key, reproducibly.

    This used to be ``hash(key) % 1000``. Python salts string hashing per
    process unless ``PYTHONHASHSEED`` is set, which nothing here does, so every
    Gini and DeLong p-value in the output changed between interpreters — the
    fold assignments and the IV shortlist both depend on this number. Measured
    over four runs, the six late-fee comparisons were stable (all p < 2e-6 every
    time) but the four 90-DPD ones were not: the reject/no-reject verdict flipped
    in three of ten runs. blake2b is stable across processes and versions.
    """
    import hashlib

    return int(hashlib.blake2b(key.encode(), digest_size=4).hexdigest(), 16) % 1000

# Their own results, quoted alongside ours everywhere.
PAPER_RESULTS = {
    "n_accounts": 6308, "n_bad": 1577, "n_good": 4731, "bad_rate": 1577 / 6308,
    "transactor_share": 0.47, "revolver_share": 0.53,
    "gini_model1": 0.522, "gini_model3": 0.519, "gini_model4": 0.522,
    "gini_threshold": 0.50,
}


# --------------------------------------------------------------------------- #
# One scorecard, built exactly the paper's way
# --------------------------------------------------------------------------- #
def _fold_assignments(n: int, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.permutation(n) % N_FOLDS


def characteristics(
    frame: pd.DataFrame, cols: list[str], y: np.ndarray, *, seed: int = 0
) -> tuple[list[str], dict[str, float]]:
    """The paper's characteristic-selection step: screen on out-of-sample information
    value, keep the strongest :data:`MAX_CHARACTERISTICS`. Returns the list and the
    full IV map, so the report can show what was dropped and why."""
    keep, ivs = CS.screen_by_iv(frame[cols], cols, y, seed=seed)
    if not keep:
        keep = [max(cols, key=lambda c: ivs.get(c, 0.0))]
    return sorted(keep, key=lambda c: -ivs[c])[:MAX_CHARACTERISTICS], ivs


def scorecard(
    frame: pd.DataFrame, cols: list[str], y: np.ndarray, *, seed: int = 0
) -> dict:
    """Build a scorecard under ten-fold cross validation and score the holdouts.

    The characteristic list is fixed first, as the paper does. Everything that then
    estimates a number from the label — the WoE bin boundaries, the stepwise selection
    and the coefficients — happens **inside** the fold, on the nine training deciles
    only. The held-out decile contributes to none of it, so the Gini reported here is
    genuinely out of sample.

    Returns the fold Ginis, the mean coefficient and its standard deviation across the
    ten scorecards (the paper's Table 2 layout), and the pooled out-of-fold score
    vector, which is what the DeLong comparison of Model 1 against Model 4 needs.
    """
    y = np.asarray(y).astype(bool)
    n = len(y)
    cand, ivs = characteristics(frame, cols, y, seed=seed)
    folds = _fold_assignments(n, seed)
    oof = np.full(n, np.nan)
    ginis: list[float] = []
    coefs: dict[str, list[float]] = {c: [] for c in cand}
    picked: dict[str, int] = {c: 0 for c in cand}

    for k in range(N_FOLDS):
        te = folds == k
        tr = ~te
        if y[tr].sum() < 2 or (~y[tr]).sum() < 2 or y[te].sum() < 1 or (~y[te]).sum() < 1:
            continue

        keep = cand
        # coarse classification: bins fitted on the training deciles only
        bins = {c: CS.woe_bins(frame.loc[tr, c].to_numpy(float), y[tr], c) for c in keep}
        Xtr = pd.DataFrame({c: b.transform(frame.loc[tr, c].to_numpy(float))
                            for c, b in bins.items()}, index=frame.index[tr])
        Xte = pd.DataFrame({c: b.transform(frame.loc[te, c].to_numpy(float))
                            for c, b in bins.items()}, index=frame.index[te])

        # stepwise logistic regression
        res = CS.stepwise_logit(Xtr, keep, y[tr])
        for c in res.selected:
            coefs[c].append(res.coef[c])
            picked[c] += 1

        # score the held-out decile
        s = res.model.predict_proba(Xte[res.selected].to_numpy(float))[:, 1]
        oof[te] = s
        ginis.append(CS.gini(y[te], s))

    if not ginis:
        # Every fold refused: with a handful of minority-class rows in the whole
        # sample a decile cannot hold both classes. Say so, rather than reporting a
        # NaN Gini that reads like a measurement.
        minority = int(min(y.sum(), (~y).sum()))
        return {
            "skipped": True,
            "reason": f"only {minority} of {n} rows fall in the minority class — a "
                      "decile cannot hold both, so no fold could be scored",
            "n": int(n), "n_minority": minority, "characteristics": cand,
        }
    mean_iv = {c: float(v) for c, v in ivs.items()}
    return {
        "characteristics": cand,
        "gini_mean": float(np.mean(ginis)) if ginis else float("nan"),
        "gini_sd": float(np.std(ginis)) if ginis else float("nan"),
        "gini_folds": ginis,
        "auc_oof": float(CS.gini(y[~np.isnan(oof)], oof[~np.isnan(oof)]) / 2 + 0.5)
        if np.isfinite(oof).any() else float("nan"),
        "oof_score": oof,
        "coefficients": {
            c: {"mean": float(np.mean(v)), "sd": float(np.std(v)), "times_selected": picked[c]}
            for c, v in coefs.items() if v
        },
        "iv_mean": mean_iv,
        "n": int(n),
        "n_bad": int(y.sum()),
        "bad_rate": float(y.mean()),
    }


# --------------------------------------------------------------------------- #
# The four-model cascade
# --------------------------------------------------------------------------- #
def cascade(
    d: pd.DataFrame, cols: list[str], bad: np.ndarray, revolver: np.ndarray, *, seed: int = 0
) -> dict:
    """Models 1-4 of the paper, plus the DeLong comparison of 1 against 4.

    ``bad`` is True for the Bad outcome; the scorecards below are all oriented to
    predict **Good**, matching the paper's ``s(x) = ln(P(G|x) / P(B|x))``.
    """
    good = ~bad
    out: dict = {}

    # Model 1 — Good/Bad over the whole population
    m1 = scorecard(d, cols, good, seed=seed)
    out["model1"] = m1

    # Model 2 — Transactor/Revolver over the whole population
    out["model2"] = scorecard(d, cols, revolver, seed=seed + 1)

    # Model 3 — Good/Bad restricted to Revolvers
    sub = d[revolver].reset_index(drop=True)
    sub_good = good[revolver]
    if len(sub) >= N_FOLDS * 2 and 0 < sub_good.sum() < len(sub):
        out["model3"] = scorecard(sub, cols, sub_good, seed=seed + 2)
    else:
        out["model3"] = {"skipped": True, "reason":
                         f"only {len(sub)} revolvers with {int((~sub_good).sum())} Bads — "
                         "too few to support ten folds"}

    # Model 4 — the composite. P(G|x) = P(T|x) + P(R|x) P(G|x,R).
    # P(T|x) comes from Model 2's out-of-fold score (oriented to Revolver, so it is
    # inverted here); P(G|x,R) from a revolver-only scorecard applied to everyone.
    m2_rev = out["model2"]["oof_score"]
    p_rev = np.where(np.isnan(m2_rev), np.nanmean(m2_rev), m2_rev)
    p_trans = 1.0 - p_rev
    if not out["model3"].get("skipped"):
        keep, _ = characteristics(d, cols, good, seed=seed + 3)
        rev_idx = np.where(revolver)[0]
        bins = {c: CS.woe_bins(d.loc[rev_idx, c].to_numpy(float), good[revolver], c)
                for c in keep}
        Xr = pd.DataFrame({c: b.transform(d.loc[rev_idx, c].to_numpy(float))
                           for c, b in bins.items()})
        res = CS.stepwise_logit(Xr, keep, good[revolver])
        Xall = pd.DataFrame({c: b.transform(d[c].to_numpy(float)) for c, b in bins.items()})
        p_good_given_rev = res.model.predict_proba(Xall[res.selected].to_numpy(float))[:, 1]
        composite = p_trans + p_rev * p_good_given_rev
        out["model4"] = {
            "gini": float(CS.gini(good, composite)),
            "formula": "P(G|x) = P(T|x) + P(R|x) P(G|x,R)",
            "selected": res.selected,
        }
        m1_score = m1["oof_score"]
        ok = ~np.isnan(m1_score)
        if ok.sum() > 10 and 0 < good[ok].sum() < ok.sum():
            out["delong_1_vs_4"] = CS.delong_roc_test(good[ok], m1_score[ok], composite[ok])
    else:
        out["model4"] = {"skipped": True, "reason": "Model 3 was skipped"}

    # The paper's structural premise, checked directly against this model.
    out["premise"] = {
        "claim": "Since transactors pay off all their balance each period, they cannot "
                 "default and so all Transactors must be Goods.",
        "bad_rate_transactor": float(bad[~revolver].mean()) if (~revolver).any() else None,
        "bad_rate_revolver": float(bad[revolver].mean()) if revolver.any() else None,
        "n_transactor": int((~revolver).sum()),
        "n_revolver": int(revolver.sum()),
    }
    return out


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #
def _strip(obj):
    """Drop the raw score vectors before serialising."""
    if isinstance(obj, dict):
        return {k: _strip(v) for k, v in obj.items() if k != "oof_score"}
    if isinstance(obj, list):
        return [_strip(v) for v in obj]
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    return obj


def run(seed: int = PP.PRIMARY_SEED) -> dict:
    b = PP.bundle(seed)
    results: dict = {
        "paper": PAPER_RESULTS,
        "config": {"seed": seed, **PP.CONFIG, "n_folds": N_FOLDS},
        "runs": {},
    }

    # -- main run: a 12-month performance period, as the paper uses ---------------
    t_main = PP.latest_origination(b, 12)
    d = b.cross_section(t_main)
    cols_b = b.columns("B")
    cols_c = b.columns("C")

    for target in ("y_latefee", "y_90dpd"):
        bad = d[f"{target}_12m"].to_numpy().astype(bool)
        for tr_name, rev in (("behavioural", d["is_revolver"].to_numpy().astype(bool)),
                             ("assigned", d["is_debtor"].to_numpy().astype(bool))):
            for set_name, cols in (("B", cols_b), ("C", cols_c)):
                key = f"{target}|12m|t{t_main}|{tr_name}|set{set_name}"
                results["runs"][key] = _strip(
                    cascade(d, cols, bad, rev, seed=_stable_seed(key))
                )

    # -- where the two T/R definitions actually diverge ---------------------------
    # Climbers only clear their principal late in the run, so before that month the
    # behavioural and assigned definitions are the *same variable* and comparing them
    # is vacuous. This records where they separate and by how much.
    div = []
    lab = b.labels.set_index("consumer_id")
    for t, g in b.revolver.groupby("month_idx"):
        assigned = lab.loc[g["consumer_id"], "is_debtor"].to_numpy()
        beh = g["is_revolver"].to_numpy()
        div.append({"month_idx": int(t), "n_revolver": int(beh.sum()),
                    "n_debtor": int(assigned.sum()),
                    "agreement": float((beh == assigned).mean())})
    results["tr_definition_divergence"] = div
    first_div = next((r["month_idx"] for r in div if r["agreement"] < 1.0), None)
    results["tr_first_divergence_month"] = first_div

    # A second cascade at a month where they genuinely differ, on a 3-month window.
    if first_div is not None:
        t_div = PP.latest_origination(b, 3)
        d2 = b.cross_section(t_div)
        bad2 = d2["y_latefee_3m"].to_numpy().astype(bool)
        for tr_name, rev in (("behavioural", d2["is_revolver"].to_numpy().astype(bool)),
                             ("assigned", d2["is_debtor"].to_numpy().astype(bool))):
            key = f"y_latefee|3m|t{t_div}|{tr_name}|setB"
            results["runs"][key] = _strip(cascade(d2, cols_b, bad2, rev, seed=7))
        results["divergence_run"] = {"month_idx": t_div, "horizon_months": 3}

    results["main_origination_month"] = t_main
    return results


def main() -> int:
    res = run()
    out = Path(PP.ROOT) / "runs" / "latest"
    print("So, Thomas, Seow & Mues — Transactor/Revolver scorecard")
    print(f"  config: {PP.describe_config()}")
    print(f"  origination month {res['main_origination_month']}, 12-month performance period")
    print(f"  T/R definitions first diverge at month {res['tr_first_divergence_month']}")
    print()
    def gini_cell(run: dict, model: str) -> str:
        m = run.get(model, {})
        if "gini_mean" in m:
            return f"{m['gini_mean']:.3f}"
        if "gini" in m:
            return f"{m['gini']:.3f}"
        return "—"

    hdr = (f"  {'run':52s} {'M1 Gini':>9s} {'M2 Gini':>9s} {'M3 Gini':>9s} "
           f"{'M4 Gini':>9s} {'DeLong p':>9s}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for key, r in res["runs"].items():
        def g(model: str, _r: dict = r) -> str:
            return gini_cell(_r, model)
        dl = r.get("delong_1_vs_4", {}).get("p")
        print(f"  {key:52s} {g('model1'):>9s} {g('model2'):>9s} {g('model3'):>9s} "
              f"{g('model4'):>9s} {(f'{dl:.3f}' if dl is not None else '—'):>9s}")
    print()
    prem = next(iter(res["runs"].values()))["premise"]
    print("  The paper's premise — 'all Transactors must be Goods':")
    print(f"    Bad rate among Transactors: {prem['bad_rate_transactor']:.4f} "
          f"(n={prem['n_transactor']})")
    print(f"    Bad rate among Revolvers  : {prem['bad_rate_revolver']:.4f} "
          f"(n={prem['n_revolver']})")
    if out.exists():
        (out / "replicate_so.json").write_text(json.dumps(res, indent=2, default=str))
        print(f"\n  wrote {out / 'replicate_so.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
