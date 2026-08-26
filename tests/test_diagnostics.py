"""Guards for the factorability diagnostics in :mod:`synthitaly.diagnostics`.

Two jobs. The first is that the estimators are *correct* — KMO and Bartlett are easy to
write plausibly and wrongly, so they are checked against cases whose answer is known from
construction (independent columns, a one-factor block, an identity matrix). The second is
that :func:`~synthitaly.diagnostics.kmo` keeps refusing to invert a singular matrix: the
real fair frame is rank-deficient, and a silent ``pinv`` there would hand the write-up a
confident number computed from floating-point noise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from synthitaly import diagnostics as D
from synthitaly import features as F
from synthitaly.model import ItalyModel


@pytest.fixture(scope="module")
def frame() -> pd.DataFrame:
    """A feature frame big enough for the correlation structure to be stable."""
    model = ItalyModel(n_consumers=300, n_merchants_per_category=2, n_days=365, seed=42)
    model.run()
    return F.build_features(model)


# ---------------------------------------------------------------------------
# Estimator correctness — cases with a known answer
# ---------------------------------------------------------------------------

def test_kmo_is_near_half_for_independent_variables():
    """Independent columns share nothing, so partial and raw correlations are both
    small noise of the same order and KMO sits near 0.5 — Kaiser's 'unacceptable'."""
    rng = np.random.default_rng(0)
    R = np.corrcoef(rng.standard_normal((4000, 12)), rowvar=False)
    overall, _ = D.kmo(R)
    assert 0.35 < overall < 0.65, f"independent data gave KMO={overall:.3f}"
    assert D.kmo_verdict(overall) in {"unacceptable", "miserable"}


def test_kmo_is_high_when_one_common_factor_drives_everything():
    """With a single latent factor behind every column the correlations are common, not
    pairwise, so KMO should be high — the case factor analysis is designed for."""
    rng = np.random.default_rng(1)
    factor = rng.standard_normal((4000, 1))
    X = factor @ np.full((1, 10), 0.9) + 0.3 * rng.standard_normal((4000, 10))
    overall, msa = D.kmo(np.corrcoef(X, rowvar=False))
    assert overall > 0.85, f"one-factor data gave KMO={overall:.3f}"
    assert D.kmo_verdict(overall) in {"meritorious", "marvellous"}
    assert msa.min() > 0.5          # no variable is adrift


def test_kmo_outputs_are_bounded_and_shaped(frame):
    cols = D.factorable_columns(F.fair_columns(frame))
    overall, msa = D.kmo(D.correlation_matrix(frame, cols))
    assert 0.0 <= overall <= 1.0
    assert msa.shape == (len(cols),)
    assert np.all((msa >= 0.0) & (msa <= 1.0))


def test_bartlett_is_calibrated_under_sphericity():
    """Sphericity holds by construction, so the test must not systematically reject.

    Asserted over many seeds rather than one: under H0 the p-value is uniform, so any
    single draw can land low by luck (seed 2 alone gives p = 0.005). What must hold is
    *calibration* — E[chi2] ~ df, and rejections at 5% stay near 5%.
    """
    stats, ps = [], []
    for seed in range(40):
        rng = np.random.default_rng(seed)
        X = rng.standard_normal((3000, 8))
        chi2_stat, df, p = D.bartlett_sphericity(np.corrcoef(X, rowvar=False), len(X))
        assert df == 8 * 7 // 2
        stats.append(chi2_stat)
        ps.append(p)

    assert np.mean(stats) == pytest.approx(28, rel=0.35), (
        f"mean chi2={np.mean(stats):.1f}, expected ~df=28 under sphericity"
    )
    reject_rate = np.mean(np.asarray(ps) < 0.05)
    assert reject_rate < 0.25, f"over-rejecting under H0: {reject_rate:.0%} at alpha=5%"


def test_bartlett_rejects_on_the_real_frame(frame):
    """The features are emphatically correlated — sphericity must be rejected."""
    cols = D.factorable_columns(F.fair_columns(frame))
    chi2_stat, df, p = D.bartlett_sphericity(D.correlation_matrix(frame, cols), len(frame))
    assert chi2_stat > 0
    assert df == len(cols) * (len(cols) - 1) // 2
    assert p < 1e-6, f"failed to reject sphericity on real features (p={p:.3g})"


def test_eigen_spectrum_sums_to_the_variable_count(frame):
    """Eigenvalues of a correlation matrix sum to p; the shares must follow."""
    cols = D.factorable_columns(F.fair_columns(frame))
    spec = D.eigen_spectrum(D.correlation_matrix(frame, cols))
    assert len(spec) == len(cols)
    assert spec["eigenvalue"].sum() == pytest.approx(len(cols), rel=1e-9)
    assert spec["cum_pct_variance"].iloc[-1] == pytest.approx(100.0, rel=1e-9)
    assert spec["eigenvalue"].is_monotonic_decreasing
    # the Kaiser flag is exactly "eigenvalue > 1"
    assert (spec["kaiser"] == (spec["eigenvalue"] > 1.0)).all()


# ---------------------------------------------------------------------------
# The refusal — the point of the module
# ---------------------------------------------------------------------------

def test_kmo_refuses_an_exactly_singular_matrix():
    """A duplicated column makes R singular; kmo must raise, not pseudo-invert."""
    rng = np.random.default_rng(3)
    X = rng.standard_normal((500, 5))
    X = np.column_stack([X, X[:, 0]])          # exact duplicate -> rank deficient
    with pytest.raises(D.SingularMatrixError):
        D.kmo(np.corrcoef(X, rowvar=False))


def test_full_fair_set_is_singular_and_is_rejected(frame):
    """The real frame is rank-deficient: the share_* block sums to 1 for every consumer.
    This is the case the module exists to catch."""
    fair = F.fair_columns(frame)
    shares = [c for c in fair if c.startswith(D.COMPOSITIONAL_PREFIX)]
    assert len(shares) > 1
    row_sums = frame[shares].sum(axis=1)
    assert row_sums.min() == pytest.approx(1.0, abs=1e-9)
    assert row_sums.max() == pytest.approx(1.0, abs=1e-9)

    with pytest.raises(D.SingularMatrixError):
        D.kmo(D.correlation_matrix(frame, fair))


def test_the_reduction_restores_full_rank(frame):
    """factorable_columns must produce a set the diagnostics can actually accept."""
    fair = F.fair_columns(frame)
    cols = D.factorable_columns(fair)
    assert set(cols) < set(fair)                                   # strictly smaller
    assert not any(c.startswith(D.COMPOSITIONAL_PREFIX) for c in cols)
    assert not (set(cols) & set(D.DUPLICATE_AGGREGATES))

    X = F.design_matrix(frame, cols)
    assert np.linalg.matrix_rank(X) == len(cols)
    # and the diagnostics run without raising
    R = D.correlation_matrix(frame, cols)
    assert np.linalg.cond(R) < 1e6
    overall, _ = D.kmo(R)
    assert overall > 0.5, f"reduced set still unacceptable (KMO={overall:.3f})"


def test_kmo_verdict_covers_kaiser_scale():
    assert D.kmo_verdict(0.42) == "unacceptable"
    assert D.kmo_verdict(0.55) == "miserable"
    assert D.kmo_verdict(0.65) == "mediocre"
    assert D.kmo_verdict(0.72) == "middling"
    assert D.kmo_verdict(0.85) == "meritorious"
    assert D.kmo_verdict(0.95) == "marvellous"
