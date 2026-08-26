"""Factorability diagnostics — is the feature matrix suitable for component analysis?

`clustering.ipynb` runs PCA and KMeans over the per-consumer feature frame built by
:mod:`synthitaly.features`. Both assume the correlation matrix carries *common* structure
worth extracting. This module tests that assumption instead of taking it on faith, with
the three standard instruments:

* **Bartlett's test of sphericity** — is R distinguishable from the identity at all? If
  not, there is nothing to factor.
* **Kaiser-Meyer-Olkin (KMO)** — of the correlation between two variables, how much is
  *shared* with the rest of the set rather than pairwise-specific? Kaiser's own verdict
  scale runs unacceptable (<0.50) / miserable / mediocre / middling / meritorious /
  marvellous (>=0.90).
* **The eigenvalue spectrum** — how many components clear the Kaiser criterion
  (eigenvalue > 1, i.e. explaining more than a single standardised variable), and how much
  variance they carry.

**The reason this module exists as more than a wrapper.** The full 34-column fair frame is
*singular*: rank 33 of 34, condition number ~2e17, and a determinant whose computed sign is
negative — numerical nonsense. The cause is exact and structural: the ten ``share_*``
columns are proportions of one total and sum to 1.000000 for every consumer. Near-exact log
identities compound it (``log total_spend ~ log mean_ticket + log n_purchases``;
``total_income`` vs ``cur_total_in`` at r = 0.9997).

KMO requires ``inv(R)``. On a singular matrix that is meaningless, and the tempting fix —
reaching for ``pinv`` — silently returns a plausible-looking number computed from noise.
:func:`kmo` therefore *raises* rather than pseudo-inverting. Use
:func:`factorable_columns` to get a defensible reduction first.

Measured at the pinned config (800 consumers x 720 days, seed 42):

===========================================  =====  =======  ==============
Treatment                                     vars     KMO   eigenvalues >1
===========================================  =====  =======  ==============
full fair set                                   34  singular             10
drop 1 share + 5 duplicate aggregates           28    0.719             10
**drop all shares + duplicates** (headline)     19  **0.764**            5
also drop low-MSA stragglers                    16    0.823              4
===========================================  =====  =======  ==============

Each count is one lower than it used to be because ``n_income`` left the analysis sets:
with the secondary property-income credit removed, every consumer receives exactly one
income credit per payday, so the column is constant and has no correlation with anything
(see :data:`DEGENERATE_COLUMNS`). The KMO improvement and the drop from 7 Kaiser
components to 5 are the macro-area income gradient, which concentrates more variance in
the first component (PC1 38.5% -> 41.1%).

The last row is a *sensitivity bound, not a result*: it prunes variables because their MSA
was low, which raises KMO by construction. Bartlett rejects sphericity in every case
(p ~ 0), so structure certainly exists — the middling KMO says that structure is only
partly common-factor shaped, which is consistent with a generator whose latent labels are
drawn rather than caused (see ``docs/EXPLANATION.md`` §8a).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import chi2 as _chi2

from synthitaly import features as _F

__all__ = [
    "KAISER_LABELS",
    "SingularMatrixError",
    "correlation_matrix",
    "kmo",
    "kmo_verdict",
    "bartlett_sphericity",
    "eigen_spectrum",
    "COMPOSITIONAL_PREFIX",
    "DUPLICATE_AGGREGATES",
    "DEGENERATE_COLUMNS",
    "factorable_columns",
]

# Kaiser's verdict scale for the overall measure of sampling adequacy.
KAISER_LABELS: tuple[tuple[float, str], ...] = (
    (0.50, "unacceptable"),
    (0.60, "miserable"),
    (0.70, "mediocre"),
    (0.80, "middling"),
    (0.90, "meritorious"),
    (np.inf, "marvellous"),
)

# Reciprocal condition number below which we refuse to invert. 1e-12 is far looser than
# the observed failure (the full fair set sits near 2e-18) but still well inside the range
# where inv() output is dominated by floating-point noise.
_RCOND_FLOOR = 1e-12


class SingularMatrixError(ValueError):
    """Raised when a correlation matrix is too ill-conditioned to invert honestly."""


def correlation_matrix(frame: pd.DataFrame, cols: list[str]) -> np.ndarray:
    """Correlation matrix of ``cols``, on the same scale the analysis uses.

    Applies the module-standard log1p-then-standardise transform via
    :func:`synthitaly.features.design_matrix`, so the diagnostics describe the matrix that
    PCA and KMeans actually see — not the raw columns.
    """
    return np.corrcoef(_F.design_matrix(frame, cols), rowvar=False)


def _check_invertible(R: np.ndarray) -> None:
    # A zero-variance column makes np.corrcoef divide by zero, so R arrives with
    # NaNs. Left alone, the SVD inside np.linalg.cond raises LinAlgError("SVD did
    # not converge") — a numerical error that says nothing useful. Catch it here
    # and report it as the singularity it is, naming the offending columns.
    if not np.all(np.isfinite(R)):
        bad = np.flatnonzero(~np.isfinite(R).all(axis=0))
        raise SingularMatrixError(
            f"correlation matrix has non-finite entries in {len(bad)} column(s) "
            f"(indices {bad.tolist()[:10]}). This means at least one column has zero "
            f"variance, so its correlation with anything is undefined. Reduce the "
            f"column set first — see factorable_columns() and DEGENERATE_COLUMNS."
        )
    rcond = 1.0 / np.linalg.cond(R)
    if not np.isfinite(rcond) or rcond < _RCOND_FLOOR:
        rank = np.linalg.matrix_rank(R)
        raise SingularMatrixError(
            f"correlation matrix is singular (rank {rank} of {R.shape[0]}, "
            f"reciprocal condition {rcond:.2e}). KMO needs inv(R); pseudo-inverting here "
            f"would return a number computed from numerical noise. Reduce the column set "
            f"first — see factorable_columns()."
        )


def kmo(R: np.ndarray) -> tuple[float, np.ndarray]:
    """Kaiser-Meyer-Olkin measure of sampling adequacy.

    Returns ``(overall, per_variable_msa)``. Raises :class:`SingularMatrixError` if ``R``
    cannot be inverted honestly — deliberately, rather than falling back to ``pinv``.
    """
    R = np.asarray(R, dtype=float)
    _check_invertible(R)

    R_inv = np.linalg.inv(R)
    d = np.sqrt(np.diag(R_inv))
    partial = -R_inv / np.outer(d, d)      # anti-image correlation
    np.fill_diagonal(partial, 0.0)

    corr = R.copy()
    np.fill_diagonal(corr, 0.0)

    corr_ss = (corr**2).sum(axis=0)
    partial_ss = (partial**2).sum(axis=0)
    per_variable = corr_ss / (corr_ss + partial_ss)
    overall = (corr**2).sum() / ((corr**2).sum() + (partial**2).sum())
    return float(overall), per_variable


def kmo_verdict(overall: float) -> str:
    """Kaiser's word for a KMO value ('miserable', 'middling', ...)."""
    for cut, label in KAISER_LABELS:
        if overall < cut:
            return label
    return KAISER_LABELS[-1][1]


def bartlett_sphericity(R: np.ndarray, n_obs: int) -> tuple[float, int, float]:
    """Bartlett's test that ``R`` is an identity matrix. Returns ``(chi2, df, p)``.

    A rejection means the variables *are* correlated — a necessary (not sufficient)
    condition for factor analysis to be meaningful.
    """
    R = np.asarray(R, dtype=float)
    p_vars = R.shape[0]
    # Same NaN trap as in _check_invertible, and here it is the more dangerous
    # one: slogdet on a NaN matrix returns sign = nan, and `nan <= 0` is False,
    # so without this the function would sail past the guard below and hand back
    # a nan chi2 that looks like a result.
    if not np.all(np.isfinite(R)):
        raise SingularMatrixError(
            "correlation matrix has non-finite entries — at least one column has "
            "zero variance. See factorable_columns() and DEGENERATE_COLUMNS."
        )
    sign, logdet = np.linalg.slogdet(R)
    if sign <= 0:
        raise SingularMatrixError(
            f"determinant sign is {sign:g}; a genuine correlation matrix is positive "
            f"definite, so this matrix is numerically singular and log|R| is meaningless."
        )
    chi2_stat = -(n_obs - 1 - (2 * p_vars + 5) / 6) * logdet
    df = p_vars * (p_vars - 1) // 2
    return float(chi2_stat), int(df), float(_chi2.sf(chi2_stat, df))


def eigen_spectrum(R: np.ndarray) -> pd.DataFrame:
    """Eigenvalues of ``R`` with variance shares and the Kaiser (>1) flag.

    Eigenvalues of a correlation matrix sum to the number of variables, so ``pct_variance``
    is ``eigenvalue / p``.
    """
    ev = np.linalg.eigvalsh(np.asarray(R, dtype=float))[::-1]
    total = ev.sum()
    return pd.DataFrame({
        "component": np.arange(1, len(ev) + 1),
        "eigenvalue": ev,
        "pct_variance": 100.0 * ev / total,
        "cum_pct_variance": 100.0 * np.cumsum(ev) / total,
        "kaiser": ev > 1.0,
    }).set_index("component")


# ---------------------------------------------------------------------------
# The reduction
# ---------------------------------------------------------------------------
# BRIGHT LINE: which columns get dropped, and why, is a *methodological* choice —
# not a number from any paper. Both rules below are structural facts about the
# feature construction, verifiable from the frame itself, not tuning:
#
#   1. share_* are proportions of one total and sum to exactly 1.0 for every
#      consumer. That is an exact linear dependency: it alone costs one rank and
#      makes R singular. Compositional data needs a log-ratio transform before it
#      can enter a factor model; raw shares cannot. Dropping the block is the
#      honest option until such a transform is implemented.
#   2. Each aggregate below is reconstructible from columns that stay. In log
#      space total = mean x count is additive, so total_spend duplicates
#      (mean_ticket + n_purchases) and total_income duplicates
#      (mean_income_credit + n_income); cur_total_in is r = 0.9997 with
#      total_income; spend_per_active_month is n_purchases / active_months; and
#      total_bills is r = 0.95 with n_bills.
#
# What is NOT done here: dropping a variable because its measured MSA came out
# low. That raises KMO by construction and is reported only as a sensitivity
# bound in the notebook, never as the headline set.
COMPOSITIONAL_PREFIX = "share_"

DUPLICATE_AGGREGATES = (
    "total_spend",             # = mean_ticket x n_purchases
    "total_income",            # = mean_income_credit x n_income
    "cur_total_in",            # r = 0.9997 with total_income
    "spend_per_active_month",  # = n_purchases / active_months
    "total_bills",             # r = 0.95 with n_bills
)

# Constant-by-construction columns, re-exported from :mod:`synthitaly.features`
# so there is one definition. ``fair_columns`` already drops them, so this is a
# second line of defence for callers that assemble a column list by hand.
DEGENERATE_COLUMNS = _F.DEGENERATE_COLUMNS


def factorable_columns(cols: list[str]) -> list[str]:
    """``cols`` reduced to a full-rank set the factorability tests can accept.

    Drops the compositional ``share_*`` block, the reconstructible aggregates listed in
    :data:`DUPLICATE_AGGREGATES`, and the by-construction constants in
    :data:`DEGENERATE_COLUMNS`.
    """
    return [
        c for c in cols
        if not c.startswith(COMPOSITIONAL_PREFIX)
        and c not in DUPLICATE_AGGREGATES
        and c not in DEGENERATE_COLUMNS
    ]
