#!/usr/bin/env python3
"""The validation report — every headline number the thesis quotes, in one run.

    uv run python scripts/validation_report.py [--out runs/latest]

Builds the pinned model once (800 consumers x 720 days, seed 42) and measures three
things on it, using only the shared pipeline in :mod:`synthitaly.features` and the
factorability instruments in :mod:`synthitaly.diagnostics` — nothing is reimplemented
here, so these numbers cannot drift from the notebooks or the pinned test bounds:

  Study 0  factorability   is the feature matrix suitable for component analysis at all?
  Study A  clustering      do the debtor archetypes fall out of the transaction stream?
  Study B  prediction      can debtor / climber status be predicted from behaviour?

Each study is measured twice — once with the ``LEAK_`` debt-mechanic columns (the
control condition: how completely the label is encoded mechanically) and once on fair
behavioural features only (the honest number). See ``docs/VALIDATION.md``.

Writes ``validation_report.json`` (deterministic — no timestamps, so two runs are
byte-identical) and ``validation_report.md`` (the same content, readable). Exit code is
non-zero if any headline number has drifted outside tolerance.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from synthitaly import diagnostics as D
from synthitaly import features as F
from synthitaly.model import ItalyModel

# The pinned configuration. Everything downstream is seeded, so the whole report is
# reproducible byte-for-byte; ``docs/RUNBOOK.md`` tells you to check exactly that.
CONFIG = {"n_consumers": 800, "n_merchants_per_category": 3, "n_days": 720, "seed": 42}

# Headline values measured on this machine at the pinned config, with the tolerance
# each is checked against. Tight but non-zero: the model and the splits are seeded, so
# the only legitimate movement is last-digit BLAS/threading noise. A number outside
# these bounds means something in the model or the pipeline changed — that is a finding
# to investigate, never something to fix by widening the tolerance.
#
# RE-PINNED on the `regional-income` branch. Three changes moved these:
#   (1) the macro-area income gradient (Semeraro et al. 2020: the South sits 44.6%
#       below Centre-North), applied mean-preservingly;
#   (2) MACRO_AREA_WEIGHTS moved from card-spend midpoints to ISTAT population
#       shares (0.50/0.27/0.23 -> 0.46/0.20/0.34);
#   (3) the unsourced secondary property-income credit was removed, which also made
#       `n_income` constant and so dropped it from the analysis column sets.
#
# Attribution, measured by re-running with each change isolated:
#   * (2) ALONE MOVES NOTHING. With no gradient, area is only a label, so
#     re-weighting it leaves income, debt and savings bit-identical.
#   * (3) shifts the RNG stream (one fewer draw per consumer at construction), which
#     re-rolls the debt and saver Bernoullis. n_debtors 157 -> 150 on its own.
#   * (1) is the substantive one. Income dispersion rises — Gini 0.3005 -> 0.3407,
#     sd/mean 0.619 -> 0.714 — while the population mean is preserved (EUR 1899.09 ->
#     1899.95), which is the whole point of the mean-preserving construction.
#
# Why the individual rows moved:
#   n_debtors / n_savers  Both are Bernoulli rolls over EQUAL-SIZED empirical bands
#     (200 per quartile, 160 per quintile), so their expectation is unchanged:
#     200*(0.120+0.192+0.244+0.285) = 168.2 debtors. 157 (old) and 167 (new) are both
#     ordinary sampling noise around that (sd ~ 11.4). Not a structural change.
#   kmo_headline / kaiser_n / bartlett  The headline set lost `n_income` (20 -> 19
#     variables) and the gradient strengthened the dominant component (PC1 38.5% ->
#     41.1% of variance), so fewer components clear Kaiser.
#   ari_naive  0.471 -> 0.301. The gradient introduces a strong income axis, and
#     KMeans partitions on the dominant axis — so it now separates rich from poor
#     rather than climber from chronic. The archetypes did not become less real; they
#     became less dominant.
#   auc_is_climber_* and auc_is_saver_*saverfair  The same dilution. Verified that it
#     is NOT a loss of label information: AUC(is_saver | monthly_income), the label's
#     actual cause, is unchanged at 0.673 -> 0.671. What fell is the signal carried by
#     the behavioural proxies (chiefly `balance_std_proxy`), which now also carry
#     income-dispersion variance that has nothing to do with saving.
#
# RE-PINNED AGAIN on `category-share-units`. A fourth change:
#   (4) sample_category() now derives selection probabilities as share_c/E[ticket_c]
#       instead of using CATEGORY_SHARES directly. The shares are EURO shares in
#       Emiliozzi et al. (2023) §2.1 Fig. 4/6, and the model drew the ticket
#       independently of the category, so the realised euro mix was wrong by up to
#       10.8pp (travel 19.8% against the paper's 9.0%). It is now exact.
#
# What (4) does mechanically: selection mass moves off the expensive, high-variance
# categories onto the cheap ones. The three categories with sigma >= 1.0 (travel,
# home, repairs) go from 21.0% to 10.4% of draws, so the marginal ticket
# distribution has mean 45.53 -> 38.06 and CV 1.583 -> 1.381. Euro throughput per
# transaction falls ~16% and per-consumer spend DISPERSION falls with it.
#
# Why the individual rows moved under (4):
#   kmo_headline / bartlett_chi2  Down slightly (0.7639 -> 0.7430, 14941 -> 14555).
#     Less spend dispersion means the behavioural columns share less common variance.
#   ari_naive 0.3013 -> 0.3636 and ari_fair 0.1548 -> 0.2126, i.e. UP. The high-sigma
#     categories were injecting consumer-level spend noise unrelated to debtor
#     subtype; removing half of it lets KMeans see the subtype axis more clearly. Note
#     this is the OPPOSITE of what was predicted before the run — the prediction was
#     that income would dominate further. It did not.
#   auc_is_climber_rf_fair 0.8090 -> 0.7857 and auc_is_saver_logreg_saverfair
#     0.7841 -> 0.7467. Both are carried chiefly by `balance_std_proxy`, a DISPERSION
#     feature, so a 13% cut in ticket CV takes signal out of them directly. The
#     saver-fair figure fell just under the 0.75 floor in test_analysis_pipeline.py,
#     which was re-baselined to 0.70 with the cause recorded there. The claim that
#     test defends is unchanged; only its margin is.
#   n_debtors 167 and n_savers 442 are UNCHANGED, as they must be: consumers are
#     constructed before any purchase is drawn and the fix adds no RNG draw. That is
#     the free correctness check on the implementation.
EXPECTED: dict[str, tuple[float, float]] = {
    "n_debtors":                 (167,    0),
    "kmo_headline":              (0.7430, 0.010),
    "kaiser_n_headline":         (5,      0),
    "bartlett_chi2_headline":    (14555,  150),
    "ari_naive":                 (0.3636, 0.050),
    "ari_fair":                  (0.2126, 0.050),
    "auc_is_debtor_logreg_naive": (1.0000, 0.010),
    "auc_is_debtor_logreg_fair":  (0.6783, 0.020),
    "auc_is_debtor_rf_fair":      (0.7646, 0.020),
    "auc_is_climber_logreg_fair": (0.8043, 0.020),
    "auc_is_climber_rf_fair":     (0.7857, 0.020),
    # --- Studies C & D (saver / non-saver) ---
    "n_savers":                      (442,    0),
    # Clustering does not recover saver status at all, with or without the leak. The
    # bound is two-sided on purpose: a sudden JUMP would be as interesting as a drop.
    "ari_saver_naive_k2":            (0.0212, 0.030),
    "ari_saver_fair_k2":             (0.0182, 0.030),
    "ari_finstatus_naive_k4":        (0.1070, 0.040),
    "ari_finstatus_fair_k4":         (0.0381, 0.040),
    # Prediction does. The debtorfair rows pin the LEAK ITSELF: if someone quietly
    # cleans cur_total_out globally these go DRIFT, which is the intended alarm.
    "auc_is_saver_logreg_naive":     (1.0000, 0.010),
    "auc_is_saver_logreg_debtorfair": (0.9956, 0.015),
    "auc_is_saver_rf_debtorfair":     (0.9920, 0.015),
    "auc_is_saver_logreg_saverfair":  (0.7467, 0.020),
    "auc_is_saver_rf_saverfair":      (0.7971, 0.020),
}


# --------------------------------------------------------------------------- #
# Study 0 — factorability
# --------------------------------------------------------------------------- #
def _treatment(name: str, note: str, frame: pd.DataFrame, cols: list[str]) -> dict:
    """One row of the factorability table: KMO, Bartlett, Kaiser count, conditioning.

    ``kmo`` is ``None`` when the correlation matrix is too ill-conditioned to invert —
    :func:`synthitaly.diagnostics.kmo` raises rather than pseudo-inverting, which is the
    whole reason that module exists. A refusal is a result, not an error.
    """
    R = D.correlation_matrix(frame, cols)
    # A zero-variance column leaves NaNs in R, and then even cond() and eigvalsh()
    # fail — cond's SVD does not converge. That is the same class of refusal as
    # the KMO one below, so it is reported the same way rather than crashing.
    finite = bool(np.all(np.isfinite(R)))
    row: dict = {
        "treatment": name,
        "note": note,
        "n_vars": len(cols),
        "condition_number": float(np.linalg.cond(R)) if finite else None,
        "kaiser_n": int(D.eigen_spectrum(R)["kaiser"].sum()) if finite else None,
    }
    if not finite:
        row["degenerate"] = (
            "correlation matrix contains non-finite entries — at least one column "
            "has zero variance, so cond() and the eigen-spectrum are undefined"
        )
    try:
        overall, msa = D.kmo(R)
        row["kmo"] = round(float(overall), 4)
        row["verdict"] = D.kmo_verdict(overall)
        row["msa_min"] = round(float(msa.min()), 4)
        row["lowest_msa_vars"] = [cols[i] for i in np.argsort(msa)[:3]]
    except D.SingularMatrixError as exc:
        row["kmo"] = None
        row["verdict"] = "singular — refused"
        row["refusal"] = str(exc)
    try:
        chi2, dof, p = D.bartlett_sphericity(R, len(frame))
        row["bartlett"] = {"chi2": round(chi2, 1), "dof": dof, "p": p}
    except D.SingularMatrixError as exc:
        row["bartlett"] = {"refused": str(exc)}
    return row


def factorability(frame: pd.DataFrame, fair: list[str]) -> tuple[list[dict], pd.DataFrame]:
    """The four treatments, escalating from the raw fair set to the sensitivity bound."""
    shares = [c for c in fair if c.startswith(D.COMPOSITIONAL_PREFIX)]
    headline = D.factorable_columns(fair)

    rows = [_treatment(
        "full fair set", "every fair feature, untouched", frame, fair)]

    # Dropping a single share breaks the exact sum-to-one dependency without removing
    # the compositional block. It is reported to show that one column is not enough —
    # WHICH share is dropped moves the KMO, which is itself the argument for dropping
    # the whole block rather than picking a victim.
    one_share = [c for c in fair
                 if c not in D.DUPLICATE_AGGREGATES and c != shares[0]]
    rows.append(_treatment(
        "drop 1 share + duplicate aggregates",
        f"drops {shares[0]} only, plus the reconstructible aggregates",
        frame, one_share))

    rows.append(_treatment(
        "drop all shares + duplicates  [HEADLINE]",
        "synthitaly.diagnostics.factorable_columns() — structural drops only",
        frame, headline))

    # Sensitivity bound, NOT a result: this prunes variables *because* their measured
    # MSA was low, which raises KMO by construction. Reported so the reader can see how
    # much of the headline is method rather than data.
    stragglers = rows[-1].get("lowest_msa_vars", [])
    rows.append(_treatment(
        "also drop 3 low-MSA stragglers  (sensitivity bound)",
        f"drops {', '.join(stragglers)} — circular by construction, not a result",
        frame, [c for c in headline if c not in stragglers]))

    spectrum = D.eigen_spectrum(D.correlation_matrix(frame, headline)).head(10).reset_index()
    return rows, spectrum


# --------------------------------------------------------------------------- #
# Study A — clustering
# --------------------------------------------------------------------------- #
def clustering(debtors: pd.DataFrame, fair: list[str], leak: list[str]) -> list[dict]:
    """Recover the three debtor archetypes with KMeans(k=3), naive vs fair features."""
    from sklearn.cluster import KMeans
    from sklearn.metrics import (
        adjusted_rand_score,
        normalized_mutual_info_score,
        silhouette_score,
    )

    truth = debtors["debtor_subtype"]
    out = []
    for tag, cols in (("naive", fair + leak), ("fair", fair)):
        X = F.design_matrix(debtors, cols)
        pred = KMeans(n_clusters=3, n_init=10, random_state=0).fit_predict(X)
        out.append({
            "features": tag,
            "n_features": len(cols),
            "ari": round(float(adjusted_rand_score(truth, pred)), 4),
            "nmi": round(float(normalized_mutual_info_score(truth, pred)), 4),
            "silhouette": round(float(silhouette_score(X, pred)), 4),
            "confusion": pd.crosstab(truth, pred).to_dict(),
        })
    return out


# --------------------------------------------------------------------------- #
# Study B — prediction
# --------------------------------------------------------------------------- #
def _auc(frame: pd.DataFrame, cols: list[str], y: pd.Series, estimator: str) -> float:
    """5-fold cross-validated ROC-AUC, on the same transform the rest of the suite uses."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    # log1p only: it is parameter-free, so applying it before the split leaks nothing.
    # Standardisation DOES estimate from the data, so it goes inside the Pipeline and is
    # refit on each training fold — ESL 2nd ed. §7.10.2, scikit-learn user guide §12.2.
    # (The random forest needs no scaler; trees are scale-invariant.)
    X = F.money_log1p(frame, cols)
    clf = (
        make_pipeline(StandardScaler(),
                      LogisticRegression(max_iter=2000, class_weight="balanced"))
        if estimator == "logreg"
        else RandomForestClassifier(n_estimators=300, random_state=0, class_weight="balanced")
    )
    # cv=5 with a classifier and an integer resolves to StratifiedKFold(5, shuffle=False),
    # so each fold holds the population's class balance. The score is the MEAN OF THE FIVE
    # PER-FOLD AUCs — a point estimate.
    #
    # f15 and f18 report this same quantity, on the same splitter, and agree with it to
    # every digit. They used to pool the out-of-fold probabilities into one ranking
    # instead (Airola et al. 2011, Comp. Stat. & Data Analysis 55(4):1828-1844), which is
    # a defensible way to get a single ROC curve but a different estimator — so the chart
    # and this table disagreed in the last digit with nothing on either telling a reader
    # which was which. They now draw the five fold curves and average them vertically for
    # the line, while annotating this number for the value.
    return float(cross_val_score(clf, X, y, cv=5, scoring="roc_auc").mean())


def prediction(data: pd.DataFrame, debtors: pd.DataFrame,
               fair: list[str], leak: list[str]) -> list[dict]:
    """Two tasks x two estimators x {naive, fair}. Naive is the leakage control."""
    out = []
    for task, frame in (("is_debtor", data), ("is_climber", debtors)):
        y = frame[task].astype(int)
        for est in ("logreg", "rf"):
            out.append({
                "task": task,
                "estimator": est,
                "population": "all consumers" if task == "is_debtor" else "debtors only",
                "n": int(len(frame)),
                "positives": int(y.sum()),
                "naive_auc": round(_auc(frame, fair + leak, y, est), 4),
                "fair_auc": round(_auc(frame, fair, y, est), 4),
            })
    return out


# --------------------------------------------------------------------------- #
# Study C — saver clustering
# --------------------------------------------------------------------------- #
# Deliberately written as separate functions rather than by generalising the debtor
# ones: the Study A / B code paths stay byte-for-byte identical, which is what lets the
# debtor numbers be quoted unchanged.
def saver_clustering(data: pd.DataFrame, fair: list[str], leak: list[str],
                     saver_fair: list[str]) -> list[dict]:
    """Can unsupervised clustering find saver status? Two targets, two feature sets.

    k=2 against ``is_saver`` is the direct analogue of Study A. k=4 against
    ``financial_status`` (saver / non_saver, each x debt) asks the richer question.
    """
    from sklearn.cluster import KMeans
    from sklearn.metrics import (
        adjusted_rand_score,
        normalized_mutual_info_score,
        silhouette_score,
    )

    out = []
    for tag, cols in (("naive", fair + leak), ("saver-fair", saver_fair)):
        X = F.design_matrix(data, cols)
        for k, target in ((2, "is_saver"), (4, "financial_status")):
            truth = data[target]
            pred = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(X)
            out.append({
                "features": tag,
                "n_features": len(cols),
                "k": k,
                "target": target,
                "ari": round(float(adjusted_rand_score(truth, pred)), 4),
                "nmi": round(float(normalized_mutual_info_score(truth, pred)), 4),
                "silhouette": round(float(silhouette_score(X, pred)), 4),
                "confusion": pd.crosstab(truth, pred).to_dict(),
            })
    return out


# --------------------------------------------------------------------------- #
# Study D — saver prediction
# --------------------------------------------------------------------------- #
def saver_prediction(data: pd.DataFrame, fair: list[str], leak: list[str],
                     saver_fair: list[str]) -> list[dict]:
    """``is_saver`` under three feature sets.

    ``naive`` and ``saver_fair`` are the usual control/honest pair. ``debtor_fair`` is
    the middle column and the point of the study: it is the set this repo calls "fair",
    and on this label it is not — it still carries the month-close sweep.
    """
    y = data["is_saver"].astype(int)
    out = []
    for est in ("logreg", "rf"):
        out.append({
            "task": "is_saver",
            "estimator": est,
            "population": "all consumers",
            "n": int(len(data)),
            "positives": int(y.sum()),
            "naive_auc": round(_auc(data, fair + leak, y, est), 4),
            "debtor_fair_auc": round(_auc(data, fair, y, est), 4),
            "saver_fair_auc": round(_auc(data, saver_fair, y, est), 4),
        })
    return out


def saver_leak_audit(data: pd.DataFrame) -> dict:
    """The evidence that ``LEAK_SAVER`` earns its quarantine, and the known confound."""
    y = data["is_saver"].astype(int)

    def corr(col: str) -> float:
        v = data[col]
        if col in F.money_columns([col]):
            v = np.log1p(v.clip(lower=0))
        return round(float(np.corrcoef(v, y)[0, 1]), 4)

    non_savers = data[~data["is_saver"]]
    return {
        # Quarantined because the month-close sweep is a current-account debit.
        "quarantined": {c: corr(c) for c in F.LEAK_SAVER},
        # Kept despite correlating — each for its own reason, which is the whole point:
        # correlation with the label is not what makes a column unfair, mechanical
        # encoding of it is.
        "kept_for_contrast": {
            "balance_std_proxy": {
                "corr": corr("balance_std_proxy"),
                "why": "transaction-derived; sweeps are never written to model.transactions",
            },
            "cur_total_in": {
                "corr": corr("cur_total_in"),
                "why": "account-derived but unreachable: the sweep credits savings/pension, "
                       "never the current account",
            },
            "mean_income_credit": {
                "corr": corr("mean_income_credit"),
                "why": "salary credits only — genuine signal, and income quintile is the "
                       "label's actual cause",
            },
        },
        "savings_balance_zero_among_non_savers": round(
            float((non_savers["LEAK_savings_balance"] == 0).mean()), 4),
        # Subsisters are force-set is_saver=True in ItalyModel._assign_savings, so the
        # two labels are entangled. Declared, not hidden. Emitted as an explicit list
        # rather than a raw crosstab dict, whose {column: {index: n}} orientation is
        # easy to read the wrong way round downstream.
        "saver_by_debtor_subtype": [
            {"subtype": str(sub), "savers": int(grp["is_saver"].sum()),
             "total": int(len(grp)),
             "saver_rate": round(float(grp["is_saver"].mean()), 4)}
            for sub, grp in data.groupby("debtor_subtype")
        ],
    }


# --------------------------------------------------------------------------- #
# Assembly
# --------------------------------------------------------------------------- #
def build_report() -> dict:
    model = ItalyModel(**CONFIG)
    model.run()

    feat = F.build_features(model)
    data = feat.merge(F.label_frame(model), on="consumer_id")
    fair, leak = F.fair_columns(feat), F.leak_columns(feat)
    debtors = data[data["is_debtor"]].reset_index(drop=True)

    saver_fair = F.saver_fair_columns(feat)

    fact_rows, spectrum = factorability(feat, fair)
    clus = clustering(debtors, fair, leak)
    pred = prediction(data, debtors, fair, leak)
    s_clus = saver_clustering(data, fair, leak, saver_fair)
    s_pred = saver_prediction(data, fair, leak, saver_fair)
    s_audit = saver_leak_audit(data)

    def _sc(features: str, k: int) -> float:
        return next(c["ari"] for c in s_clus if c["features"] == features and c["k"] == k)

    headline = next(r for r in fact_rows if "HEADLINE" in r["treatment"])
    measured = {
        "n_debtors": len(debtors),
        "kmo_headline": headline["kmo"],
        "kaiser_n_headline": headline["kaiser_n"],
        "bartlett_chi2_headline": headline["bartlett"]["chi2"],
        "ari_naive": next(c["ari"] for c in clus if c["features"] == "naive"),
        "ari_fair": next(c["ari"] for c in clus if c["features"] == "fair"),
        **{f"auc_{r['task']}_{r['estimator']}_naive": r["naive_auc"] for r in pred},
        **{f"auc_{r['task']}_{r['estimator']}_fair": r["fair_auc"] for r in pred},
        # Studies C & D
        "n_savers": int(data["is_saver"].sum()),
        "ari_saver_naive_k2": _sc("naive", 2),
        "ari_saver_fair_k2": _sc("saver-fair", 2),
        "ari_finstatus_naive_k4": _sc("naive", 4),
        "ari_finstatus_fair_k4": _sc("saver-fair", 4),
        **{f"auc_is_saver_{r['estimator']}_naive": r["naive_auc"] for r in s_pred},
        **{f"auc_is_saver_{r['estimator']}_debtorfair": r["debtor_fair_auc"]
           for r in s_pred},
        **{f"auc_is_saver_{r['estimator']}_saverfair": r["saver_fair_auc"]
           for r in s_pred},
    }

    checks = []
    for name, (want, tol) in EXPECTED.items():
        got = measured.get(name)
        ok = got is not None and abs(got - want) <= tol
        checks.append({"name": name, "measured": got, "expected": want,
                       "tolerance": tol, "status": "PASS" if ok else "DRIFT"})

    return {
        "config": CONFIG,
        "frame": {
            "n_consumers": int(len(feat)),
            "n_features": len(fair) + len(leak),
            "n_fair": len(fair), "n_leak": len(leak),
            "leak_columns": leak,
        },
        "labels": {
            "n_debtors": int(len(debtors)),
            "subtype_mix": debtors["debtor_subtype"].value_counts().to_dict(),
            "n_savers": int(data["is_saver"].sum()),
            "financial_status_mix": data["financial_status"].value_counts().to_dict(),
        },
        "saver_fair_columns": {
            "n": len(saver_fair), "quarantined": list(F.LEAK_SAVER),
        },
        "factorability": fact_rows,
        "eigen_spectrum": spectrum.round(4).to_dict(orient="records"),
        "clustering": clus,
        "prediction": pred,
        "saver_clustering": s_clus,
        "saver_prediction": s_pred,
        "saver_leak_audit": s_audit,
        "checks": checks,
    }


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #
def _fmt(v, nd=4):
    return "—" if v is None else (f"{v:.{nd}f}" if isinstance(v, float) else str(v))


def to_markdown(rep: dict) -> str:
    c = rep["config"]
    # Prose figures, read from the measured headlines rather than typed in. These
    # sentences used to carry hard-coded numbers and went stale the moment the model
    # changed — a generated report quoting figures its own tables contradict is worse
    # than no prose at all.
    _h = {k["name"]: k["measured"] for k in rep["checks"]}
    _sk2 = _h["ari_saver_fair_k2"]
    _ari_n = _h["ari_naive"]
    _df_auc = _h["auc_is_saver_logreg_debtorfair"]
    _sf_auc = _h["auc_is_saver_logreg_saverfair"]
    _deb_auc = _h["auc_is_debtor_logreg_fair"]
    L: list[str] = [
        "# Validation report",
        "",
        f"Config: **{c['n_consumers']} consumers x {c['n_days']} days, seed {c['seed']}** "
        f"({c['n_merchants_per_category']} merchants per category x area).",
        f"Feature frame: {rep['frame']['n_features']} columns "
        f"({rep['frame']['n_fair']} fair, {rep['frame']['n_leak']} `LEAK_`) "
        f"over {rep['frame']['n_consumers']} consumers.",
        f"Debtors: {rep['labels']['n_debtors']} — "
        + ", ".join(f"{k} {v}" for k, v in sorted(rep["labels"]["subtype_mix"].items())),
        f"Savers: {rep['labels']['n_savers']} — "
        + ", ".join(f"{k} {v}" for k, v in sorted(rep["labels"]["financial_status_mix"].items())),
        f"Saver-fair set: {rep['saver_fair_columns']['n']} columns "
        f"(fair minus {', '.join('`' + c + '`' for c in rep['saver_fair_columns']['quarantined'])}).",
        "",
        "Generated by `scripts/validation_report.py`. Deterministic: two runs of this file",
        "produce byte-identical JSON.",
        "",
        "## Study 0 — is the feature matrix factorable?",
        "",
        "| Treatment | vars | KMO | Kaiser's verdict | eigen>1 | Bartlett chi2 (dof) | cond(R) |",
        "|---|---:|---:|---|---:|---:|---:|",
    ]
    for r in rep["factorability"]:
        b = r["bartlett"]
        bart = "refused" if "refused" in b else f"{b['chi2']:,.0f} ({b['dof']})"
        cond = "undefined" if r["condition_number"] is None else f"{r['condition_number']:.3g}"
        kaiser = "—" if r["kaiser_n"] is None else str(r["kaiser_n"])
        L.append(
            f"| {r['treatment']} | {r['n_vars']} | {_fmt(r['kmo'], 3)} | {r['verdict']} | "
            f"{kaiser} | {bart} | {cond} |"
        )
    L += [
        "",
        "The first row is the point of the exercise: the untouched fair set is singular, and",
        "`diagnostics.kmo` refuses to pseudo-invert it. The last row is a **sensitivity bound,",
        "not a result** — it drops variables because their MSA was low, which raises KMO by",
        "construction. The headline row uses structural drops only.",
        "",
        "### Eigenvalue spectrum of the headline set",
        "",
        "| PC | eigenvalue | % variance | cumulative % | Kaiser |",
        "|---:|---:|---:|---:|:--:|",
    ]
    for e in rep["eigen_spectrum"]:
        L.append(
            f"| {e['component']} | {e['eigenvalue']:.3f} | {e['pct_variance']:.1f} | "
            f"{e['cum_pct_variance']:.1f} | {'yes' if e['kaiser'] else ''} |"
        )
    L += [
        "",
        "## Study A — clustering the debtor subpopulation (KMeans, k=3)",
        "",
        "| Features | n | ARI | NMI | silhouette |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in rep["clustering"]:
        L.append(f"| {r['features']} | {r['n_features']} | {r['ari']:.4f} | "
                 f"{r['nmi']:.4f} | {r['silhouette']:.4f} |")
    L += [
        "",
        "## Study B — prediction (5-fold CV ROC-AUC)",
        "",
        "| Task | population | n (positives) | estimator | naive AUC | fair AUC |",
        "|---|---|---:|---|---:|---:|",
    ]
    for r in rep["prediction"]:
        L.append(f"| `{r['task']}` | {r['population']} | {r['n']} ({r['positives']}) | "
                 f"{r['estimator']} | {r['naive_auc']:.4f} | {r['fair_auc']:.4f} |")
    L += [
        "",
        "`naive` = fair features **plus** the `LEAK_` debt-mechanic columns. It is the control",
        "condition — it measures how completely the label is encoded mechanically, against which",
        "the fair number measures what ordinary behaviour actually carries.",
        "",
        "## Study C — clustering for saver / non-saver",
        "",
        "| Features | n | k | against | ARI | NMI | silhouette |",
        "|---|---:|---:|---|---:|---:|---:|",
    ]
    for r in rep["saver_clustering"]:
        L.append(f"| {r['features']} | {r['n_features']} | {r['k']} | `{r['target']}` | "
                 f"{r['ari']:.4f} | {r['nmi']:.4f} | {r['silhouette']:.4f} |")
    L += [
        "",
        f"Clustering does **not** recover saver status — ARI {_sk2:.3f} at k=2, and barely",
        "better against the four-way `financial_status`. Note this holds even for `naive`,",
        "where the label is mechanically present and prediction (below) is essentially",
        "perfect: saver status is a real but low-variance direction, and KMeans partitions on",
        "the dominant axes instead. The healthy silhouette says it found *a* clean structure,",
        f"just not this one. Contrast Study A, where the debtor archetypes reach ARI {_ari_n:.3f}.",
        "",
        "## Study D — predicting `is_saver` (5-fold CV ROC-AUC)",
        "",
        "| Task | n (positives) | estimator | naive AUC | debtor-fair AUC | saver-fair AUC |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for r in rep["saver_prediction"]:
        L.append(f"| `{r['task']}` | {r['n']} ({r['positives']}) | {r['estimator']} | "
                 f"{r['naive_auc']:.4f} | {r['debtor_fair_auc']:.4f} | "
                 f"{r['saver_fair_auc']:.4f} |")
    audit = rep["saver_leak_audit"]
    L += [
        "",
        "**`debtor-fair` is the point of this study.** That column is the set this repo calls",
        "\"fair\" — and on the saver label it is not. `Consumer._month_close` sweeps the month's",
        "positive residual into savings or pension, and that sweep is a *debit on the current",
        "account*, so `cur_total_out` counts a line that only savers ever have and `cur_balance`",
        "is what is left after it. Quarantining the two (`LEAK_SAVER`) is what takes the honest",
        f"number from ~{_df_auc:.3f} to ~{_sf_auc:.2f}.",
        "",
        "Correlation with `is_saver` — quarantined vs kept:",
        "",
        "| Column | corr | disposition |",
        "|---|---:|---|",
    ]
    for c, v in audit["quarantined"].items():
        L.append(f"| `{c}` | {v:+.3f} | **quarantined** — the sweep debit lands in it |")
    for c, d in audit["kept_for_contrast"].items():
        L.append(f"| `{c}` | {d['corr']:+.3f} | kept — {d['why']} |")
    L += [
        "",
        f"`LEAK_savings_balance` is zero for **{audit['savings_balance_zero_among_non_savers']:.0%}** "
        "of non-savers — definitionally the label, and already quarantined.",
        "",
        "**Known confound:** subsisters are force-set `is_saver = True` in",
        "`ItalyModel._assign_savings`, so saver status is entangled with debtor subtype:",
        "",
        "| Debtor subtype | savers | total | saver rate |",
        "|---|---:|---:|---:|",
    ]
    for r in audit["saver_by_debtor_subtype"]:
        L.append(f"| {r['subtype']} | {r['savers']} | {r['total']} | {r['saver_rate']:.0%} |")
    L += [
        "",
        "Unlike the debtor subtype — drawn on a *hidden* binary flag — `is_saver` is drawn on",
        "`income_quintile`, which the ledger does show through the income credits. That is why",
        f"honest saver prediction (~{_sf_auc:.2f}) beats honest debtor prediction",
        f"(~{_deb_auc:.2f}): the label has an observable cause.",
        "",
        "## Headline checks",
        "",
        "| Number | measured | expected | tolerance | |",
        "|---|---:|---:|---:|:--|",
    ]
    for k in rep["checks"]:
        L.append(f"| `{k['name']}` | {_fmt(k['measured'])} | {_fmt(k['expected'])} | "
                 f"±{k['tolerance']} | {k['status']} |")
    drift = [k for k in rep["checks"] if k["status"] == "DRIFT"]
    L += ["", f"**{len(rep['checks']) - len(drift)}/{len(rep['checks'])} PASS.**"
          + (" Investigate the DRIFT rows — do not widen the tolerance." if drift else "")]
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="runs/latest", type=Path,
                    help="output directory (default: runs/latest)")
    args = ap.parse_args()

    t0 = time.time()
    print(f"building the pinned model ({CONFIG['n_consumers']} x {CONFIG['n_days']} days, "
          f"seed {CONFIG['seed']}) — about 20 s …", flush=True)
    rep = build_report()

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "validation_report.json").write_text(
        json.dumps(rep, indent=2, default=str), encoding="utf-8")
    (args.out / "validation_report.md").write_text(to_markdown(rep), encoding="utf-8")

    drift = [k for k in rep["checks"] if k["status"] == "DRIFT"]
    print(f"\n{to_markdown(rep).split('## Headline checks')[1]}")
    print(f"wrote {args.out}/validation_report.json + .md   ({time.time() - t0:.1f}s)")
    for k in drift:
        print(f"  DRIFT  {k['name']}: {k['measured']} vs expected {k['expected']} "
              f"±{k['tolerance']}", file=sys.stderr)
    return 1 if drift else 0


if __name__ == "__main__":
    raise SystemExit(main())
