"""Guards for the consumer x month panel in :mod:`synthitaly.panel`.

The panel exists so the rolling-window designs of Khandani, Kim & Lo (2010) and Butaru
et al. (2015) can be run at all, and both designs rest on one property: **no row may
contain information from after its own ``as_of`` month**. Several tests here exist only
to hold that line, because a leak of that kind produces beautiful numbers and is
invisible in the output.

The rest check the trailing-window arithmetic against values recomputed the slow,
obvious way, and pin the two structural facts about this model that the write-up turns
on — that the delinquency label is a persistent liquidity state rather than an event,
and that Transactor/Revolver status genuinely moves over the run.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from synthitaly import panel as P
from synthitaly.model import ItalyModel


@pytest.fixture(scope="module")
def model() -> ItalyModel:
    """720 days, matching the pinned analysis configuration.

    The run length is not arbitrary: a climber repays its principal over roughly two
    years, so a shorter run contains no Revolver -> Transactor migration at all and
    ``test_revolver_status_moves_over_the_run`` has nothing to find. 540 days yields
    exactly zero movers; 720 yields ~8%.
    """
    m = ItalyModel(n_consumers=200, n_merchants_per_category=2, n_days=720, seed=7)
    m.run()
    return m


@pytest.fixture(scope="module")
def delin(model: ItalyModel) -> pd.DataFrame:
    return P.delinquency_frame(model)


@pytest.fixture(scope="module")
def pan(model: ItalyModel, delin: pd.DataFrame) -> pd.DataFrame:
    return P.add_forward_labels(P.build_panel(model), delin, horizons=(3, 6))


# ---------------------------------------------------------------------------
# Shape and wellformedness
# ---------------------------------------------------------------------------

def test_month_end_history_is_one_row_per_consumer_per_closed_month(model, delin):
    counts = delin.groupby("consumer_id").size()
    assert counts.nunique() == 1, "consumers disagree on how many months closed"
    assert set(delin["consumer_id"]) == {c.unique_id for c in model.consumers}
    assert delin["month_idx"].min() == 0
    assert (delin.groupby("consumer_id")["month_idx"].apply(
        lambda s: s.is_monotonic_increasing)).all()


def test_panel_is_wellformed(pan):
    assert not pan.isna().to_numpy().any(), "panel must be free of NaN"
    assert np.isfinite(pan.select_dtypes(float).to_numpy()).all()
    assert not pan.duplicated(["consumer_id", "month_idx"]).any()


def test_panel_drops_rows_without_a_full_trailing_window(pan):
    """A 3-month average and a 6-month average are different variables; the early
    months are dropped rather than silently computed on a short window."""
    assert pan["month_idx"].min() == P.LOOKBACK_MONTHS - 1


def test_column_sets_are_nested_and_derived(pan):
    all_c = set(P.panel_feature_columns(pan))
    fair = set(P.panel_fair_columns(pan))
    leak = set(P.panel_leak_columns(pan))
    behav = set(P.panel_behaviour_columns(pan))
    assert leak | fair == all_c and not (leak & fair)
    assert behav < fair, "Set C must be a strict subset of Set B"
    assert fair - behav == set(P.ARREARS_STATE)
    assert all(c.startswith("LEAK_") for c in leak)
    # keys and labels must never be offered as predictors
    assert not any(c.startswith("y_") or c.startswith("horizon_complete_") for c in all_c)
    for key in ("consumer_id", "month", "month_idx", "was_current"):
        assert key not in all_c


# ---------------------------------------------------------------------------
# The trailing window says what it claims
# ---------------------------------------------------------------------------

def test_trailing_sums_match_a_direct_recomputation(model, pan):
    """``total_spend`` on a row must equal the purchase euros of exactly the six
    months ending at that row's ``as_of``, recomputed straight off the ledger."""
    tx = pd.DataFrame(model.transactions)
    tx = tx[tx["kind"] == "purchase"].copy()
    tx["cid"] = tx["from"].astype(int)
    tx["month"] = pd.to_datetime(tx["date"]).dt.strftime("%Y-%m")
    months = sorted(P.delinquency_frame(model)["month"].unique())

    checked = 0
    for _, row in pan.sample(12, random_state=0).iterrows():
        hi = int(row["month_idx"])
        window = set(months[hi - P.LOOKBACK_MONTHS + 1: hi + 1])
        assert len(window) == P.LOOKBACK_MONTHS
        want = tx[(tx["cid"] == row["consumer_id"]) & (tx["month"].isin(window))]["amount_eur"].sum()
        assert row["total_spend"] == pytest.approx(want, rel=1e-9, abs=1e-6)
        checked += 1
    assert checked == 12


def test_category_shares_sum_to_one_where_there_was_spending(pan):
    shares = [c for c in pan.columns if c.startswith("share_")]
    tot = pan[shares].sum(axis=1)
    spent = pan["total_spend"] > 0
    assert tot[spent].to_numpy() == pytest.approx(1.0, abs=1e-9)


def test_mean_ticket_is_total_over_count(pan):
    have = pan["n_purchases"] > 0
    lhs = pan.loc[have, "mean_ticket"].to_numpy()
    rhs = (pan.loc[have, "total_spend"] / pan.loc[have, "n_purchases"]).to_numpy()
    assert lhs == pytest.approx(rhs, rel=1e-9)


def test_trailing_features_ignore_the_future(model, delin):
    """Truncating the run must not change the features of any month that both runs
    share. This is the strongest available check that no row reads past its ``as_of``:
    the later data simply does not exist in the truncated model."""
    short = ItalyModel(n_consumers=200, n_merchants_per_category=2, n_days=540, seed=7)
    short.run()
    a = P.build_panel(model).set_index(["consumer_id", "month"])
    b = P.build_panel(short).set_index(["consumer_id", "month"])
    shared = a.index.intersection(b.index)
    assert len(shared) > 0
    cols = P.panel_feature_columns(a.reset_index())
    pd.testing.assert_frame_equal(
        a.loc[shared, cols].sort_index(), b.loc[shared, cols].sort_index()
    )


# ---------------------------------------------------------------------------
# Forward labels
# ---------------------------------------------------------------------------

def test_forward_labels_cover_the_window_after_as_of(pan, delin):
    """Recompute ``y_90dpd_3m`` the slow way for a sample of rows."""
    wide = delin.pivot(index="consumer_id", columns="month_idx", values="writeoff_n").fillna(0.0)
    last = int(delin["month_idx"].max())
    for _, row in pan.sample(25, random_state=1).iterrows():
        t = int(row["month_idx"])
        cols = [k for k in range(t + 1, min(t + 3, last) + 1)]
        want = bool(wide.loc[row["consumer_id"], cols].sum() > 0) if cols else False
        assert bool(row["y_90dpd_3m"]) is want


def test_horizon_completeness_flag_marks_truncated_windows(pan, delin):
    last = int(delin["month_idx"].max())
    for h in (3, 6):
        flag = pan[f"horizon_complete_{h}m"]
        assert (pan.loc[flag, "month_idx"] + h <= last).all()
        assert (pan.loc[~flag, "month_idx"] + h > last).all()


def test_was_current_agrees_with_the_arrears_counter(pan):
    assert (pan["was_current"] == (pan["max_dpd"] == 0)).all()


def test_a_label_shifted_into_the_past_destroys_the_signal(pan):
    """Sanity tripwire on the evaluation set-up itself. Predicting a row's label from
    another consumer's features must be no better than chance; if a shuffled target
    still scores well, the split or the join is wrong rather than the model good."""
    from sklearn.metrics import roc_auc_score
    from sklearn.tree import DecisionTreeClassifier

    d = pan[pan["horizon_complete_3m"]]
    cols = P.panel_behaviour_columns(pan)
    y = d["y_90dpd_3m"].to_numpy()
    rng = np.random.default_rng(0)
    shuffled = rng.permutation(y)
    mo = sorted(d["month_idx"].unique())
    cut = mo[len(mo) // 2]
    tr, te = d["month_idx"] < cut, d["month_idx"] >= cut
    if shuffled[tr.to_numpy()].sum() == 0 or shuffled[te.to_numpy()].sum() == 0:
        pytest.skip("too few positives to shuffle meaningfully")
    clf = DecisionTreeClassifier(min_samples_leaf=50, random_state=0)
    clf.fit(d.loc[tr, cols], shuffled[tr.to_numpy()])
    auc = roc_auc_score(shuffled[te.to_numpy()], clf.predict_proba(d.loc[te, cols])[:, 1])
    assert 0.35 < auc < 0.65, f"shuffled label still scored AUC {auc:.3f}"


# ---------------------------------------------------------------------------
# Two structural facts the write-up rests on
# ---------------------------------------------------------------------------

def test_delinquency_is_a_persistent_state_not_an_event(pan):
    """Almost no consumer goes from a clean account to written-off inside a horizon.

    This is why Khandani et al.'s "straight-rollers" test (their Table 8) is degenerate
    on this model, and it is a finding about the model rather than a defect in the
    panel: arrears here are a standing liquidity condition. If this ever starts
    failing, the model has gained a genuine default *shock* and the write-up's central
    caveat needs revisiting.
    """
    d = pan[pan["horizon_complete_3m"]]
    clean = d[d["was_current"]]
    assert len(clean) > 100
    assert clean["y_90dpd_3m"].mean() < 0.01


def test_arrears_state_nearly_determines_the_forward_label(pan):
    """``max_dpd`` alone separates the 90-DPD label almost perfectly, which is the
    reason Set C exists at all."""
    from sklearn.metrics import roc_auc_score

    d = pan[pan["horizon_complete_3m"]]
    if d["y_90dpd_3m"].nunique() < 2:
        pytest.skip("no positives at this configuration")
    auc = roc_auc_score(d["y_90dpd_3m"].astype(int), d["max_dpd"])
    assert auc > 0.90, f"expected near-deterministic arrears signal, got AUC {auc:.3f}"


def test_revolver_status_moves_over_the_run(model):
    """So et al.'s definition is behavioural and time-varying. Climbers clear their
    principal and convert Revolver -> Transactor, which the static ``is_debtor``
    attribute cannot express — the whole reason both definitions are reported."""
    rev = P.revolver_state(model)
    assert rev["is_revolver"].any() and rev["is_transactor"].any()
    assert (rev["is_revolver"] == ~rev["is_transactor"]).all()
    movers = rev.groupby("consumer_id")["is_revolver"].nunique().gt(1).mean()
    assert movers > 0.01, f"only {movers:.1%} of consumers changed T/R state"


def test_revolver_implies_a_debt_balance_somewhere_in_the_window(model):
    rev = P.revolver_state(model)
    ever = rev.groupby("consumer_id")["is_revolver"].any()
    debt = rev.groupby("consumer_id")["debt_balance"].max()
    assert (debt[ever[ever].index] > 0).all()
    assert (debt[ever[~ever].index] == 0).all()


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_panel_is_deterministic_for_a_seed():
    a = ItalyModel(n_consumers=120, n_merchants_per_category=2, n_days=400, seed=3)
    b = ItalyModel(n_consumers=120, n_merchants_per_category=2, n_days=400, seed=3)
    a.run()
    b.run()
    pd.testing.assert_frame_equal(P.build_panel(a), P.build_panel(b))
    assert a.export_dpd_history() == b.export_dpd_history()
