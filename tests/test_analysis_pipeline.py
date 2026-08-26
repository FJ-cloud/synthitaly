"""Regression guards for the clustering / prediction analysis suite.

The feature pipeline itself lives in :mod:`synthitaly.features` — one implementation
shared by this module, the two analysis notebooks and
``presentation/scripts/generate_figures.py``. This module pins the headline results
against silent drift:

* the feature frame is well-formed and deterministic for a fixed seed;
* with the debt-mechanic ("LEAK_") features, clustering the debtor subpopulation
  recovers the climber/chronic/subsister archetypes (ARI above a floor);
* a classifier predicts debtor status near-perfectly with those proxies (they
  mechanically encode the label) and still beats the baseline using *fair*
  behavioural features only — but only barely, which is itself the finding.

The metrics below are measured on the **compact** column subset
(:data:`synthitaly.features.FAIR_COMPACT` / ``LEAK_COMPACT``), not the full frame, so
the pinned numbers stay comparable to the validation figures. Bounds are deliberately
loose floors, not targets. The heavy 800x720 fits are marked ``slow``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from synthitaly import features as F
from synthitaly.features import (
    LEAK_SAVER,
    build_features,
    fair_columns,
    leak_columns,
    money_columns,
    saver_fair_columns,
)
from synthitaly.model import ItalyModel

# Short local names for the things used on almost every line below. Kept as module-level
# aliases rather than `import ... as` so isort leaves the block as one readable unit.
FAIR = F.FAIR_COMPACT
LEAK = F.LEAK_COMPACT
_design_matrix = F.design_matrix
labels = F.label_frame

# ---------------------------------------------------------------------------
# Fast tests — shape + determinism (small model)
# ---------------------------------------------------------------------------

def test_feature_frame_is_wellformed():
    model = ItalyModel(n_consumers=200, n_merchants_per_category=2, n_days=180, seed=7)
    model.run()
    feats = build_features(model)
    assert len(feats) == len(model.consumers)          # one row per consumer
    assert feats["consumer_id"].is_unique
    for col in FAIR + LEAK:
        assert col in feats.columns, f"missing feature {col}"
    assert feats.drop(columns="consumer_id").isna().sum().sum() == 0   # no NaNs
    assert np.isfinite(feats.drop(columns="consumer_id").to_numpy()).all()


def test_features_are_deterministic_for_a_seed():
    a = ItalyModel(n_consumers=150, n_merchants_per_category=2, n_days=120, seed=11)
    b = ItalyModel(n_consumers=150, n_merchants_per_category=2, n_days=120, seed=11)
    a.run()
    b.run()
    fa = build_features(a).set_index("consumer_id").sort_index()
    fb = build_features(b).set_index("consumer_id").sort_index()
    pd.testing.assert_frame_equal(fa, fb)


def test_leak_columns_are_label_proxies():
    """Sanity-check the leakage claim: only subsisters draw credit; debt-service
    lines imply debt. This is *why* the naive models are near-perfect."""
    model = ItalyModel(n_consumers=300, n_merchants_per_category=2, n_days=365, seed=3)
    model.run()
    df = build_features(model).merge(labels(model), on="consumer_id")
    # credit draws occur only for subsisters
    drew = df[df["LEAK_credit_draw_n"] > 0]
    if len(drew):
        subtypes = set(drew["debtor_subtype"])
        assert subtypes <= {"subsister"}, f"non-subsisters drew credit: {subtypes}"
    # a debt-service line only exists for debtors
    serviced = df[df["LEAK_debt_service_n"] > 0]
    assert serviced["is_debtor"].all()


def test_saver_fair_drops_exactly_the_sweep_contaminated_columns():
    """``saver_fair_columns`` is ``fair_columns`` minus ``LEAK_SAVER`` — no more, no less.

    Guards the label-specific quarantine against drifting into a general-purpose filter.
    """
    model = ItalyModel(n_consumers=120, n_merchants_per_category=2, n_days=120, seed=5)
    model.run()
    feats = build_features(model)
    fair, saver_fair = fair_columns(feats), saver_fair_columns(feats)

    assert set(LEAK_SAVER) <= set(fair), "LEAK_SAVER columns must start out inside fair"
    assert set(fair) - set(saver_fair) == set(LEAK_SAVER)
    # The debtor-facing view is untouched — this is what keeps the pinned debtor numbers put.
    assert not any(c.startswith("LEAK_") for c in fair)


# ---------------------------------------------------------------------------
# Slow tests — the headline metric bounds at the pinned config (800 x 720)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def big_data() -> pd.DataFrame:
    model = ItalyModel(n_consumers=800, n_merchants_per_category=3, n_days=720, seed=42)
    model.run()
    return build_features(model).merge(labels(model), on="consumer_id")


@pytest.fixture(scope="module")
def big_cols(big_data) -> dict[str, list[str]]:
    """Feature-column groups recovered from the merged frame.

    ``big_data`` is features + labels, so the label names have to come back out before
    ``fair_columns`` and friends can be applied — otherwise ``is_saver`` itself would be
    counted as a fair feature, which would make the saver tests meaningless.
    """
    tiny = ItalyModel(n_consumers=20, n_merchants_per_category=2, n_days=40, seed=1)
    tiny.run()
    label_names = set(labels(tiny).columns)
    feats_only = big_data.drop(columns=[c for c in label_names if c != "consumer_id"])
    return {
        "fair": fair_columns(feats_only),
        "leak": leak_columns(feats_only),
        "saver_fair": saver_fair_columns(feats_only),
    }


def _auc(frame: pd.DataFrame, cols: list[str], y, estimator: str = "logreg") -> float:
    """5-fold CV ROC-AUC under the suite's standard log1p-then-standardise transform."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    X = frame[cols].copy()
    for c in money_columns(cols):
        X[c] = np.log1p(X[c].clip(lower=0))
    clf = (
        make_pipeline(StandardScaler(),
                      LogisticRegression(max_iter=2000, class_weight="balanced"))
        if estimator == "logreg"
        else RandomForestClassifier(n_estimators=200, random_state=0, class_weight="balanced")
    )
    return float(cross_val_score(clf, X, y, cv=5, scoring="roc_auc").mean())


@pytest.mark.slow
def test_naive_clustering_recovers_debtor_subtypes(big_data):
    """Clustering the debtor subpopulation with the debt-mechanic features recovers
    the three archetypes well above chance (observed ARI ~0.36; floor 0.30).

    The observed value was ~0.47 before the macro-area income gradient landed. The
    gradient makes income the dominant axis of the feature space and KMeans partitions
    on the dominant axis, so recovery of the archetypes weakened — see
    ``docs/RESULTS_validation.md`` §3. The floor stays at 0.30: still well above chance,
    and a fall through it would mean the archetypes had stopped being recoverable at
    all, which is the thing worth alarming on."""
    from sklearn.cluster import KMeans
    from sklearn.metrics import adjusted_rand_score

    deb = big_data[big_data["is_debtor"]].reset_index(drop=True)
    assert set(deb["debtor_subtype"]) == {"climber", "chronic", "subsister"}
    X = _design_matrix(deb, FAIR + LEAK)
    labels_ = KMeans(n_clusters=3, n_init=10, random_state=0).fit_predict(X)
    ari = adjusted_rand_score(deb["debtor_subtype"], labels_)
    assert ari > 0.30, f"naive debtor clustering ARI={ari:.3f} (expected ~0.36)"


@pytest.mark.slow
def test_debtor_prediction_naive_perfect_fair_beats_baseline(big_data):
    """Naive features (incl. proxies) predict debtor status almost perfectly; fair
    behavioural features still beat the 0.5 baseline by a clear margin."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    y = big_data["is_debtor"].astype(int)

    def auc(cols):
        X = big_data[cols].copy()
        for m in cols:
            if any(k in m for k in ("spend", "ticket", "bills", "income", "balance", "sum", "total")):
                X[m] = np.log1p(X[m].clip(lower=0))
        clf = make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=2000, class_weight="balanced")
        )
        return cross_val_score(clf, X, y, cv=5, scoring="roc_auc").mean()

    naive_auc = auc(FAIR + LEAK)
    fair_auc = auc(FAIR)
    # Naive ~1.0; fair ~0.66 on this COMPACT set. The notebooks' fuller 45-column
    # frame lands at 0.697 — close, and for the same reason: both exclude
    # LEAK_cur_n_entries. It used to be classified fair, which pushed the notebook
    # number to 0.91; the compact set never contained it, which is why the two
    # disagreed. Both bounds below are loose floors, not targets.
    assert naive_auc > 0.95, f"naive AUC={naive_auc:.3f} (expected ~1.0)"
    assert fair_auc > 0.60, f"fair AUC={fair_auc:.3f} (expected ~0.66, clearly above 0.5 baseline)"
    assert naive_auc >= fair_auc       # proxies can only help


# ---------------------------------------------------------------------------
# Saver label — studies C & D
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_saver_prediction_is_honest_only_after_the_sweep_quarantine(big_data, big_cols):
    """The saver leak, pinned from both sides.

    ``cur_total_out`` and ``cur_balance`` carry the month-close sweep — a current-account
    debit only savers ever have. On the *debtor*-fair set they take ``is_saver`` to ~0.995;
    quarantining them (``LEAK_SAVER``) gives the honest ~0.83.

    The 0.95 floor on ``debtor_fair`` is deliberate and unusual: it pins **the leak
    itself**. If someone cleans ``cur_total_out`` globally, this fails loudly rather than
    letting docs/VALIDATION.md go quietly stale.
    """
    y = big_data["is_saver"].astype(int)
    debtor_fair_auc = _auc(big_data, big_cols["fair"], y)
    saver_fair_auc = _auc(big_data, big_cols["saver_fair"], y)

    assert debtor_fair_auc > 0.95, (
        f"debtor-fair AUC on is_saver={debtor_fair_auc:.3f} (expected ~0.995). If this "
        f"dropped, the sweep leak may have been fixed upstream — update docs/VALIDATION.md."
    )
    # Floor RE-BASELINED 0.75 -> 0.70 on `category-share-units`, with the cause known
    # rather than assumed. Measured 0.8300 originally, 0.7841 after the macro-area
    # income gradient, 0.7467 after the category-units fix in sample_category().
    #
    # The last step is mechanical: the fix moved selection mass off the high-variance
    # categories (travel/home/repairs, sigma >= 1.0, 21.0% -> 10.4% of draws), cutting
    # the marginal ticket CV 1.583 -> 1.381. This AUC is carried by `balance_std_proxy`,
    # a DISPERSION feature, so it loses signal directly — as did auc_is_climber_rf_fair
    # over the same change.
    #
    # What the test defends is unchanged: saver status IS recoverable from honest
    # behavioural features once the sweep leak is quarantined, far above the 0.5
    # baseline and far below the 0.99 the leak buys. 0.70 keeps that claim falsifiable
    # while absorbing a drop with a named cause. If it goes BELOW 0.70, the honest
    # signal has genuinely gone and Study D needs re-reading — do not widen again.
    assert saver_fair_auc > 0.70, (
        f"saver-fair AUC={saver_fair_auc:.3f} (expected ~0.75, clearly above 0.5 baseline)"
    )
    assert debtor_fair_auc > saver_fair_auc, "quarantining a leak cannot raise the score"


@pytest.mark.slow
def test_clustering_does_not_recover_saver_status(big_data, big_cols):
    """Study C's finding, pinned: KMeans does not find savers even with the leak present.

    Saver status is a real but low-variance direction — prediction reaches ~1.0 on the same
    columns where clustering scores ARI ~0.008. The ceiling is two-sided on purpose: a jump
    would be as interesting as a drop, and either means this test's docs need revisiting.
    """
    from sklearn.cluster import KMeans
    from sklearn.metrics import adjusted_rand_score

    for tag, cols in (("naive", big_cols["fair"] + big_cols["leak"]),
                      ("saver-fair", big_cols["saver_fair"])):
        X = _design_matrix(big_data, cols)
        pred = KMeans(n_clusters=2, n_init=10, random_state=0).fit_predict(X)
        ari = adjusted_rand_score(big_data["is_saver"], pred)
        assert ari < 0.15, (
            f"{tag} k=2 saver ARI={ari:.3f} (expected ~0.008). Clustering suddenly finding "
            f"savers would overturn Study C — investigate, do not relax this bound."
        )
