"""Guards for the credit-scoring machinery in :mod:`synthitaly.creditscoring`.

Weight of evidence, stepwise selection and the DeLong test are all easy to write
plausibly and wrongly, and all three feed numbers straight into the write-up. Each is
checked against a case whose answer is known by construction rather than against a
previously observed output.

The most important test here is the pair on :func:`~synthitaly.creditscoring.screen_by_iv`.
Weight of evidence is fitted against the label, so a WoE-transformed column carries
in-sample signal even when the raw variable is pure noise — measured, that pushes a
noise column into the stepwise scorecard 99% of the time. The screen is what stops it,
and it only works because the information value is scored out of sample. If someone
"simplifies" it back to an in-sample IV these tests fail.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

from synthitaly import creditscoring as CS


def _logistic_sample(n: int, seed: int, beta: float = 0.8):
    """``x`` drives the event, ``z`` is pure noise of the same shape."""
    rng = np.random.default_rng(seed)
    x = rng.normal(size=n)
    z = rng.normal(size=n)
    y = rng.random(n) < 1.0 / (1.0 + np.exp(-(beta * x - 0.3)))
    return x, z, y


# ---------------------------------------------------------------------------
# Weight of evidence
# ---------------------------------------------------------------------------

def test_woe_preserves_the_ranking_information_of_a_monotone_variable():
    """WoE is a Good/Bad log-odds, so it runs *against* the event: a variable that
    raises the event rate gets a falling WoE. The magnitude of the discrimination must
    survive the transform, which is what AUC reflected about 0.5 measures."""
    x, _, y = _logistic_sample(8000, 0)
    b = CS.woe_bins(x, y, "x")
    raw = roc_auc_score(y.astype(int), x)
    woe = roc_auc_score(y.astype(int), b.transform(x))
    assert woe < 0.5 < raw, "WoE should be oriented towards Good, i.e. against the event"
    assert abs((1 - woe) - raw) < 0.02, f"transform lost discrimination: {1 - woe:.3f} vs {raw:.3f}"


def test_woe_bins_respect_the_size_floor_and_bin_cap():
    x, _, y = _logistic_sample(4000, 1)
    b = CS.woe_bins(x, y, "x", max_bins=6, min_frac=0.10)
    assert len(b.woe) <= 6
    assert b.counts.min() >= 0.10 * len(x) * 0.5, "a bin fell far below the size floor"
    assert np.isfinite(b.woe).all(), "smoothing should keep every WoE finite"


def test_woe_handles_a_constant_column_without_blowing_up():
    _, _, y = _logistic_sample(500, 2)
    b = CS.woe_bins(np.ones(500), y, "const")
    assert b.iv == 0.0
    assert np.allclose(b.transform(np.ones(10)), 0.0)


def test_information_value_ranks_a_strong_variable_above_a_weak_one():
    rng = np.random.default_rng(3)
    n = 6000
    strong = rng.normal(size=n)
    weak = rng.normal(size=n)
    y = rng.random(n) < 1.0 / (1.0 + np.exp(-(1.5 * strong + 0.15 * weak)))
    assert CS.woe_bins(strong, y).iv > CS.woe_bins(weak, y).iv


# ---------------------------------------------------------------------------
# The IV screen — the guard on WoE's in-sample bias
# ---------------------------------------------------------------------------

def test_out_of_sample_iv_of_pure_noise_is_centred_on_zero():
    """The whole point of scoring IV out of sample. An in-sample IV of noise is
    positive and grows as bins/n grows, so no fixed threshold can filter it; the
    out-of-sample version has expectation zero at any sample size."""
    ivs = []
    for s in range(30):
        _, z, y = _logistic_sample(3000, 100 + s)
        _, m = CS.screen_by_iv(pd.DataFrame({"z": z}), ["z"], y, seed=s)
        ivs.append(m["z"])
    mean_iv = float(np.mean(ivs))
    assert abs(mean_iv) < 0.01, f"noise IV should centre on 0, got {mean_iv:+.4f}"


def test_iv_screen_keeps_signal_and_mostly_rejects_noise():
    kept_signal = kept_noise = 0
    trials = 20
    for s in range(trials):
        x, z, y = _logistic_sample(4000, 200 + s)
        keep, _ = CS.screen_by_iv(pd.DataFrame({"x": x, "z": z}), ["x", "z"], y, seed=s)
        kept_signal += "x" in keep
        kept_noise += "z" in keep
    assert kept_signal == trials, "the screen dropped a genuinely predictive variable"
    assert kept_noise <= trials * 0.25, f"noise survived {kept_noise}/{trials} times"


# ---------------------------------------------------------------------------
# Stepwise logistic regression
# ---------------------------------------------------------------------------

def test_stepwise_is_calibrated_on_raw_variables():
    """On un-binned inputs the likelihood-ratio test should admit a noise column at
    roughly its nominal rate. This is the baseline that isolates the WoE bias: when
    this passes and the WoE version does not, the binning is the culprit."""
    entered = 0
    trials = 60
    for s in range(trials):
        x, z, y = _logistic_sample(1500, 300 + s)
        r = CS.stepwise_logit(pd.DataFrame({"x": x, "z": z}), ["x", "z"], y)
        entered += "z" in r.selected
    assert entered <= trials * 0.25, f"noise entered {entered}/{trials}, test is too liberal"


def test_stepwise_selects_the_driver_and_reports_its_direction():
    x, z, y = _logistic_sample(6000, 7)
    r = CS.stepwise_logit(pd.DataFrame({"x": x, "z": z}), ["x", "z"], y)
    assert "x" in r.selected
    assert r.coef["x"] > 0, "coefficient should be positive for an event-raising variable"
    assert any(step == "enter" and name == "x" for step, name, _ in r.history)


def test_stepwise_never_returns_an_empty_scorecard():
    """With no usable signal it must still hand back something fittable, otherwise the
    fold loop in the So replication has nothing to score."""
    rng = np.random.default_rng(11)
    n = 400
    y = rng.random(n) < 0.5
    f = pd.DataFrame({"a": rng.normal(size=n), "b": rng.normal(size=n)})
    r = CS.stepwise_logit(f, ["a", "b"], y)
    assert len(r.selected) >= 1


# ---------------------------------------------------------------------------
# Gini and the DeLong test
# ---------------------------------------------------------------------------

def test_gini_is_twice_auc_minus_one():
    x, _, y = _logistic_sample(3000, 12)
    assert np.isclose(CS.gini(y, x), 2 * roc_auc_score(y.astype(int), x) - 1)


def test_gini_verdict_uses_the_industry_half():
    assert "acceptable" in CS.gini_verdict(0.52)
    assert "below" in CS.gini_verdict(0.49)


def test_delong_finds_no_difference_between_a_score_and_itself():
    x, _, y = _logistic_sample(2000, 13)
    out = CS.delong_roc_test(y, x, x)
    assert out["diff"] == pytest.approx(0.0, abs=1e-12)
    assert out["p"] == pytest.approx(1.0)


def test_delong_rejects_when_one_score_is_genuinely_better():
    x, z, y = _logistic_sample(3000, 14)
    out = CS.delong_roc_test(y, x, z)
    assert out["diff"] > 0.1
    assert out["p"] < 1e-6


def test_delong_is_symmetric_up_to_sign():
    x, z, y = _logistic_sample(2000, 15)
    a = CS.delong_roc_test(y, x, z)
    b = CS.delong_roc_test(y, z, x)
    assert a["diff"] == pytest.approx(-b["diff"])
    assert a["p"] == pytest.approx(b["p"])


def test_delong_matches_the_auc_it_reports():
    x, z, y = _logistic_sample(2000, 16)
    out = CS.delong_roc_test(y, x, z)
    assert out["auc_a"] == pytest.approx(roc_auc_score(y.astype(int), x), abs=1e-9)
    assert out["auc_b"] == pytest.approx(roc_auc_score(y.astype(int), z), abs=1e-9)


def test_delong_needs_both_classes():
    with pytest.raises(ValueError):
        CS.delong_roc_test(np.ones(50, dtype=bool), np.arange(50.0), np.arange(50.0))


# ---------------------------------------------------------------------------
# Thresholds and confusion-matrix scores
# ---------------------------------------------------------------------------

def test_tangency_threshold_maximises_tpr_minus_fpr():
    x, _, y = _logistic_sample(3000, 17)
    s = 1.0 / (1.0 + np.exp(-x))
    thr = CS.roc_tangency_threshold(y, s)
    best = ((s >= thr) & y).sum() / y.sum() - ((s >= thr) & ~y).sum() / (~y).sum()
    for alt in np.quantile(s, np.linspace(0.05, 0.95, 25)):
        j = ((s >= alt) & y).sum() / y.sum() - ((s >= alt) & ~y).sum() / (~y).sum()
        assert j <= best + 1e-9


def test_classification_scores_confusion_counts_are_consistent():
    x, _, y = _logistic_sample(2000, 18)
    s = 1.0 / (1.0 + np.exp(-x))
    out = CS.classification_scores(y, s)
    assert out["tp"] + out["fp"] + out["fn"] + out["tn"] == out["n"] == len(y)
    assert out["tp"] + out["fn"] == int(y.sum())
    assert out["base_rate"] == pytest.approx(y.mean())
    assert out["gini"] == pytest.approx(2 * out["auc"] - 1)


def test_mean_score_separation_favours_the_bad_group():
    """Khandani et al. Table 7 reads exactly this way: the average forecast among
    accounts that went bad against those that did not."""
    x, _, y = _logistic_sample(4000, 19)
    out = CS.classification_scores(y, 1.0 / (1.0 + np.exp(-x)))
    assert out["mean_score_bad"] > out["mean_score_good"]


def test_kappa_verdict_walks_the_landis_koch_scale():
    """Landis & Koch (1977): below zero poor, 0.00-0.20 slight, 0.21-0.40 fair,
    0.41-0.60 moderate, 0.61-0.80 substantial, 0.81-1.00 almost perfect. Both Lo
    papers read their kappas off this scale, so the boundaries matter."""
    assert CS.kappa_verdict(-0.05) == "poor"
    assert CS.kappa_verdict(0.05) == "slight"
    assert CS.kappa_verdict(0.3) == "fair"
    assert CS.kappa_verdict(0.5) == "moderate"
    assert CS.kappa_verdict(0.7) == "substantial"
    assert CS.kappa_verdict(0.95) == "almost perfect"


def test_f_measure_is_zero_when_nothing_is_flagged():
    y = np.array([True, False, True, False])
    assert CS.f_measure(y, np.zeros(4, dtype=bool)) == 0.0
