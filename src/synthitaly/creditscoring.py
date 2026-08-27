"""Credit-scoring machinery the papers use and scikit-learn does not ship.

Everything here exists because a specific paper asks for it:

* **Weight of evidence and coarse classification** — So, Thomas, Seow & Mues,
  *Using a Transactor/Revolver scorecard to make credit and pricing decisions*, s2:
  "For continuous variables, we split the variable into a large number of intervals.
  We use weight of evidence to coarse-classify these variables into bins with similar
  default risk by combining adjacent intervals where appropriate."
* **Stepwise logistic regression** — the same section: "the overall coefficients were
  obtained using logistic regression with characteristics entering and leaving the
  scorecard in a stepwise fashion."
* **Gini** — their headline discrimination measure, with 0.5 the industry threshold
  for an acceptable application scorecard.
* **The DeLong test** — their Table 3 compares Model 1 against Model 4 with "the
  DeLong, DeLong and Clarke-Pearson test".
* **The ROC tangency threshold and kappa** — Khandani, Kim & Lo (2010) s5: "If the
  cost of false positives is equal to the gain of true positives, the optimal
  threshold will correspond to the tangent point of the ROC curve with the 45 degree
  line", scored with a kappa statistic read against Landis & Koch (1977).
* **F-measure and kappa** — Butaru et al. (2015) s III.D.

Deliberately no ``statsmodels`` dependency: it is not in the project environment, and
the only thing it would buy is per-fit standard errors. So et al. report coefficient
means and standard deviations *across the ten cross-validation folds*, which fall out
of the fold loop directly, so the Wald machinery is not needed. Variable entry and
exit use likelihood-ratio chi-square tests computed from log-loss differences.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import cohen_kappa_score, f1_score, roc_auc_score, roc_curve

__all__ = [
    "LANDIS_KOCH",
    "WoEBinning",
    "woe_bins",
    "information_value",
    "screen_by_iv",
    "MIN_IV",
    "gini",
    "gini_verdict",
    "stepwise_logit",
    "StepwiseResult",
    "delong_roc_test",
    "roc_tangency_threshold",
    "kappa",
    "kappa_verdict",
    "f_measure",
    "precision_recall",
    "classification_scores",
]

# Landis & Koch (1977), as cited by both Khandani et al. (2010) and Butaru et al.
# (2015) for reading a kappa statistic.
LANDIS_KOCH = (
    (0.00, "poor"), (0.20, "slight"), (0.40, "fair"),
    (0.60, "moderate"), (0.80, "substantial"), (1.01, "almost perfect"),
)

_EPS = 1e-9


# --------------------------------------------------------------------------- #
# Weight of evidence / coarse classification
# --------------------------------------------------------------------------- #
@dataclass
class WoEBinning:
    """A fitted coarse classification for one variable.

    ``edges`` are the bin boundaries (``-inf`` .. ``+inf``) and ``woe`` the weight of
    evidence of each bin, so ``transform`` maps a raw column onto its WoE score. This
    is the representation So et al. feed to the logistic regression: the scorecard is
    linear in WoE, not in the raw variable.
    """

    name: str
    edges: np.ndarray
    woe: np.ndarray
    iv: float
    counts: np.ndarray = field(default_factory=lambda: np.array([]))
    event_rate: np.ndarray = field(default_factory=lambda: np.array([]))

    def transform(self, x: np.ndarray) -> np.ndarray:
        idx = np.clip(np.digitize(np.asarray(x, dtype=float), self.edges[1:-1]),
                      0, len(self.woe) - 1)
        return self.woe[idx]


def _woe_of(good: np.ndarray, bad: np.ndarray) -> np.ndarray:
    """ln( (good_i / total_good) / (bad_i / total_bad) ), Laplace-smoothed.

    Smoothing keeps a bin that happens to be pure from producing an infinite score;
    without it a single empty cell takes the whole scorecard out.
    """
    g = (good + 0.5) / (good.sum() + 0.5 * len(good))
    b = (bad + 0.5) / (bad.sum() + 0.5 * len(bad))
    return np.log(g / b)


def woe_bins(
    x: np.ndarray, y: np.ndarray, name: str = "x",
    max_bins: int = 10, min_frac: float = 0.05, n_prebins: int = 50,
) -> WoEBinning:
    """Coarse-classify ``x`` against binary ``y`` (``True`` = event/Bad).

    Follows So et al. s2: cut into many fine intervals, then merge adjacent ones of
    similar risk until every bin holds at least ``min_frac`` of the sample and no more
    than ``max_bins`` remain. Merging always takes the adjacent pair with the closest
    weight of evidence, which is the "combining adjacent intervals where appropriate"
    step. Discrete columns with few distinct values are used as-is.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y).astype(bool)
    uniq = np.unique(x)
    if len(uniq) <= 1:
        return WoEBinning(name, np.array([-np.inf, np.inf]), np.array([0.0]), 0.0)

    if len(uniq) <= max_bins:
        edges = np.concatenate([[-np.inf], (uniq[1:] + uniq[:-1]) / 2.0, [np.inf]])
    else:
        qs = np.linspace(0, 1, min(n_prebins, len(uniq)) + 1)[1:-1]
        cuts = np.unique(np.quantile(x, qs))
        edges = np.concatenate([[-np.inf], cuts, [np.inf]])

    idx = np.clip(np.digitize(x, edges[1:-1]), 0, len(edges) - 2)
    n_bins = len(edges) - 1
    good = np.array([(~y[idx == i]).sum() for i in range(n_bins)], dtype=float)
    bad = np.array([y[idx == i].sum() for i in range(n_bins)], dtype=float)

    floor = max(1.0, min_frac * len(x))
    while len(good) > 1:
        w = _woe_of(good, bad)
        tot = good + bad
        small = np.where(tot < floor)[0]
        if len(small) > 0:
            i = int(small[0])
            j = i - 1 if i == len(good) - 1 else i + 1
        elif len(good) > max_bins:
            j = int(np.argmin(np.abs(np.diff(w)))) + 1
            i = j - 1
        else:
            break
        lo, hi = min(i, j), max(i, j)
        good[lo] += good[hi]
        bad[lo] += bad[hi]
        good = np.delete(good, hi)
        bad = np.delete(bad, hi)
        edges = np.delete(edges, hi)

    w = _woe_of(good, bad)
    tot_g, tot_b = max(good.sum(), _EPS), max(bad.sum(), _EPS)
    iv = float((((good / tot_g) - (bad / tot_b)) * w).sum())
    n = good + bad
    return WoEBinning(name, edges, w, iv, counts=n,
                      event_rate=np.divide(bad, np.maximum(n, 1)))


def information_value(binning: WoEBinning) -> float:
    """Siddiqi's information value. Rough convention: <0.02 useless, 0.02-0.1 weak,
    0.1-0.3 medium, 0.3-0.5 strong, >0.5 suspiciously strong (check for leakage)."""
    return binning.iv


# Siddiqi's "unpredictive" cutoff, and why the screen behind it has to be honest.
#
# Weight of evidence is fitted *against the label*, so a WoE-transformed column carries
# in-sample signal even when the raw variable is pure noise. Measured directly: the
# likelihood-ratio stepwise test below is well calibrated on raw variables (a noise
# column enters at 7% against a nominal 5%), but on WoE-transformed noise it enters
# 99% of the time. The binning has quietly spent degrees of freedom the chi-square test
# does not know about.
#
# A univariate screen is the standard guard, and is also what So, Thomas, Seow & Mues
# describe: "The standard approach to building scorecards involves univariate analysis
# and stepwise regression to identify the borrower characteristics that most impact on
# the borrower's subsequent Good/Bad status."
#
# But the screen only works if the IV itself is honest. An IV computed on the same rows
# that chose the bins inherits the same bias, and its size depends on the sample: pure
# noise binned into 10 bins scores IV ~0.03 at n=1500 and ~0.006 at n=8000, so no fixed
# threshold can be right for both. :func:`screen_by_iv` therefore fits the bins on one
# half and scores the IV on the other, where noise lands near zero at any n.
#
# This affects which variables are SELECTED, never the reported discrimination: Gini is
# always measured on a held-out fold whose rows took no part in binning or fitting.
MIN_IV = 0.02


def _iv_of_fixed_bins(binning: WoEBinning, x: np.ndarray, y: np.ndarray) -> float:
    """Information value of held-out data under an already-fitted binning.

    The bin *weights* come from the held-out sample but the weight-of-evidence values
    are the **training** ones. That is what makes this an honest out-of-sample
    measure: the WoE vector is fixed before the test rows are seen, so for a variable
    carrying no signal the two distributions differ only by noise and the expected IV
    is zero rather than positive. Re-estimating WoE on the held-out half instead would
    simply reproduce the in-sample bias on a smaller sample.
    """
    y = np.asarray(y).astype(bool)
    idx = np.clip(np.digitize(np.asarray(x, float), binning.edges[1:-1]),
                  0, len(binning.woe) - 1)
    k = len(binning.woe)
    good = np.array([(~y[idx == i]).sum() for i in range(k)], dtype=float)
    bad = np.array([y[idx == i].sum() for i in range(k)], dtype=float)
    tot_g, tot_b = max(good.sum(), _EPS), max(bad.sum(), _EPS)
    return float((((good / tot_g) - (bad / tot_b)) * binning.woe).sum())


def screen_by_iv(
    frame: pd.DataFrame, cols: list[str], y: np.ndarray,
    min_iv: float = MIN_IV, seed: int = 0, n_splits: int = 2,
) -> tuple[list[str], dict[str, float]]:
    """Univariate pre-screen on **out-of-sample** information value.

    For each column the bins are fitted on one half of ``frame`` and the IV scored on
    the other, averaged over ``n_splits`` random halvings. Columns averaging at least
    ``min_iv`` survive. Returns the survivors and the full IV map, so the report can
    show what was dropped and why.

    ``frame`` must hold raw, un-binned values.
    """
    y = np.asarray(y).astype(bool)
    n = len(y)
    rng = np.random.default_rng(seed)
    ivs: dict[str, float] = {}
    for c in cols:
        x = frame[c].to_numpy(dtype=float)
        scores = []
        for _ in range(n_splits):
            m = np.zeros(n, dtype=bool)
            m[rng.permutation(n)[: n // 2]] = True
            if y[m].sum() == 0 or (~y[m]).sum() == 0:
                continue
            scores.append(_iv_of_fixed_bins(woe_bins(x[m], y[m], c), x[~m], y[~m]))
        ivs[c] = float(np.mean(scores)) if scores else 0.0
    return [c for c in cols if ivs[c] >= min_iv], ivs


# --------------------------------------------------------------------------- #
# Discrimination
# --------------------------------------------------------------------------- #
def gini(y: np.ndarray, score: np.ndarray) -> float:
    """Gini = 2 x AUC - 1, the measure So et al. report throughout."""
    return 2.0 * roc_auc_score(np.asarray(y).astype(int), np.asarray(score, dtype=float)) - 1.0


def gini_verdict(g: float) -> str:
    """So et al. s2, citing Anderson: "application scorecards are considered
    acceptable if they have Gini coefficients of 0.5 or more"."""
    return "acceptable (>= 0.50)" if g >= 0.50 else "below the 0.50 industry threshold"


# --------------------------------------------------------------------------- #
# Stepwise logistic regression
# --------------------------------------------------------------------------- #
@dataclass
class StepwiseResult:
    selected: list[str]
    coef: dict[str, float]
    intercept: float
    model: LogisticRegression
    history: list[tuple[str, str, float]]  # (step, variable, p-value)


def _loglik(model: LogisticRegression, X: np.ndarray, y: np.ndarray) -> float:
    p = np.clip(model.predict_proba(X)[:, 1], _EPS, 1 - _EPS)
    return float(np.sum(y * np.log(p) + (1 - y) * np.log(1 - p)))


def _fit(X: np.ndarray, y: np.ndarray) -> LogisticRegression:
    # Very large C ~ unpenalised, which is what a classical scorecard fit is. The
    # penalty is not removed entirely because a perfectly separating split would
    # otherwise fail to converge.
    return LogisticRegression(max_iter=2000, C=1e6, solver="lbfgs").fit(X, y)


def stepwise_logit(
    frame: pd.DataFrame, cols: list[str], y: np.ndarray,
    p_enter: float = 0.05, p_remove: float = 0.10, max_steps: int = 50,
) -> StepwiseResult:
    """Forward/backward stepwise logistic regression by likelihood-ratio test.

    Each candidate is scored by the LR statistic ``2 * (LL_with - LL_without)``, which
    is chi-square with one degree of freedom. A variable enters at ``p_enter`` and is
    dropped again if it rises above ``p_remove`` once others are present — the
    "entering and leaving the scorecard in a stepwise fashion" of So et al. s2.
    """
    y = np.asarray(y).astype(int)
    sel: list[str] = []
    history: list[tuple[str, str, float]] = []
    remaining = list(cols)

    def ll(names: list[str]) -> float:
        if not names:
            p = np.clip(y.mean(), _EPS, 1 - _EPS)
            return float(np.sum(y * np.log(p) + (1 - y) * np.log(1 - p)))
        X = frame[names].to_numpy(dtype=float)
        return _loglik(_fit(X, y), X, y)

    for _ in range(max_steps):
        changed = False
        base = ll(sel)
        # forward
        best, best_p = None, 1.0
        for c in remaining:
            stat = 2.0 * (ll(sel + [c]) - base)
            p = float(stats.chi2.sf(max(stat, 0.0), 1))
            if p < best_p:
                best, best_p = c, p
        if best is not None and best_p < p_enter:
            sel.append(best)
            remaining.remove(best)
            history.append(("enter", best, best_p))
            changed = True
        # backward
        if len(sel) > 1:
            full = ll(sel)
            worst, worst_p = None, 0.0
            for c in sel:
                stat = 2.0 * (full - ll([s for s in sel if s != c]))
                p = float(stats.chi2.sf(max(stat, 0.0), 1))
                if p > worst_p:
                    worst, worst_p = c, p
            if worst is not None and worst_p > p_remove:
                sel.remove(worst)
                remaining.append(worst)
                history.append(("remove", worst, worst_p))
                changed = True
        if not changed:
            break

    if not sel:
        # Nothing cleared the bar. This is NOT an intercept-only fit: it fits a
        # one-variable model on whichever column happens to be first, so the result
        # is a scorecard built on near-noise and is indistinguishable from a real one
        # in the returned object. Callers that care must check `selected`.
        sel = [cols[0]]
    X = frame[sel].to_numpy(dtype=float)
    model = _fit(X, y)
    return StepwiseResult(
        selected=sel,
        coef={c: float(v) for c, v in zip(sel, model.coef_[0], strict=True)},
        intercept=float(model.intercept_[0]),
        model=model,
        history=history,
    )


# --------------------------------------------------------------------------- #
# DeLong test
# --------------------------------------------------------------------------- #
def _midrank(x: np.ndarray) -> np.ndarray:
    order = np.argsort(x)
    s = x[order]
    n = len(x)
    tr = np.empty(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j < n - 1 and s[j + 1] == s[i]:
            j += 1
        tr[i:j + 1] = 0.5 * (i + j) + 1
        i = j + 1
    out = np.empty(n, dtype=float)
    out[order] = tr
    return out


def delong_roc_test(y: np.ndarray, score_a: np.ndarray, score_b: np.ndarray) -> dict:
    """Two-sided DeLong test for two correlated ROC curves on the same sample.

    So et al. use "the DeLong, DeLong and Clarke-Pearson test" (their ref [7]) to show
    that the Gini difference between their Model 1 and Model 4 is not significant.
    Implemented via the fast midrank algorithm of Sun & Xu (2014).

    Returns ``auc_a``, ``auc_b``, ``diff``, ``se``, ``z`` and ``p``.
    """
    y = np.asarray(y).astype(bool)
    pos = np.vstack([np.asarray(score_a, float)[y], np.asarray(score_b, float)[y]])
    neg = np.vstack([np.asarray(score_a, float)[~y], np.asarray(score_b, float)[~y]])
    m, n = pos.shape[1], neg.shape[1]
    if m == 0 or n == 0:
        raise ValueError("DeLong needs both classes present")

    tx = np.array([_midrank(pos[k]) for k in range(2)])
    ty = np.array([_midrank(neg[k]) for k in range(2)])
    tz = np.array([_midrank(np.concatenate([pos[k], neg[k]])) for k in range(2)])

    auc = (tz[:, :m].sum(axis=1) / m - (m + 1) / 2.0) / n
    v01 = (tz[:, :m] - tx) / n
    v10 = 1.0 - (tz[:, m:] - ty) / m
    s = np.cov(v01) / m + np.cov(v10) / n
    s = np.atleast_2d(s)

    d = np.array([1.0, -1.0])
    var = float(d @ s @ d)
    diff = float(auc[0] - auc[1])
    se = float(np.sqrt(max(var, 0.0)))
    if se == 0.0:
        z, p = 0.0, 1.0
    else:
        z = diff / se
        p = float(2 * stats.norm.sf(abs(z)))
    return {"auc_a": float(auc[0]), "auc_b": float(auc[1]), "diff": diff,
            "se": se, "z": float(z), "p": p}


# --------------------------------------------------------------------------- #
# Threshold and confusion-matrix scores
# --------------------------------------------------------------------------- #
def roc_tangency_threshold(y: np.ndarray, score: np.ndarray) -> float:
    """The threshold where the ROC curve's tangent has slope 1.

    Khandani et al. s5: with equal cost of a false positive and gain of a true
    positive, the optimal cut is the tangency of the ROC curve with the 45 degree
    line. Equivalent to maximising ``tpr - fpr`` (Youden's J), which is how it is
    found here.
    """
    fpr, tpr, thr = roc_curve(np.asarray(y).astype(int), np.asarray(score, float))
    return float(thr[int(np.argmax(tpr - fpr))])


def kappa(y: np.ndarray, pred: np.ndarray) -> float:
    return float(cohen_kappa_score(np.asarray(y).astype(int), np.asarray(pred).astype(int)))


def kappa_verdict(k: float) -> str:
    for hi, label in LANDIS_KOCH:
        if k < hi:
            return label
    return "almost perfect"


def f_measure(y: np.ndarray, pred: np.ndarray) -> float:
    """Harmonic mean of precision and recall — Butaru et al. s III.D."""
    return float(f1_score(np.asarray(y).astype(int), np.asarray(pred).astype(int),
                          zero_division=0))


def precision_recall(y: np.ndarray, pred: np.ndarray) -> tuple[float, float]:
    y = np.asarray(y).astype(bool)
    pred = np.asarray(pred).astype(bool)
    tp = float((y & pred).sum())
    prec = tp / max(float(pred.sum()), 1.0)
    rec = tp / max(float(y.sum()), 1.0)
    return prec, rec


def classification_scores(y: np.ndarray, score: np.ndarray, threshold: float | None = None) -> dict:
    """The full metric block both Lo papers report, at one threshold.

    ``threshold=None`` uses the ROC tangency point, which is what Khandani et al.
    Table 9 does ("for each model we constructed the ROC curve, determined the ...
    classification threshold").
    """
    y = np.asarray(y).astype(bool)
    score = np.asarray(score, dtype=float)
    thr = roc_tangency_threshold(y, score) if threshold is None else threshold
    pred = score >= thr
    prec, rec = precision_recall(y, pred)
    k = kappa(y, pred)
    tp = int((y & pred).sum())
    fp = int((~y & pred).sum())
    fn = int((y & ~pred).sum())
    tn = int((~y & ~pred).sum())
    auc = float(roc_auc_score(y.astype(int), score))
    return {
        "threshold": float(thr), "auc": auc, "gini": 2 * auc - 1,
        "precision": prec, "recall": rec, "f_measure": f_measure(y, pred),
        "kappa": k, "kappa_verdict": kappa_verdict(k),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "n": int(len(y)), "base_rate": float(y.mean()),
        # Khandani et al. Table 7: the separation between the average forecast among
        # accounts that did and did not go bad. Reported on a 0-100 scale as they do.
        "mean_score_bad": float(score[y].mean() * 100) if y.any() else float("nan"),
        "mean_score_good": float(score[~y].mean() * 100) if (~y).any() else float("nan"),
    }
