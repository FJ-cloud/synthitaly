"""Consumer x month panel — the frame the rolling-window credit-risk papers need.

``synthitaly.features`` collapses a whole run into one row per consumer. That is the
right shape for the clustering studies, and the wrong shape for two of the three
papers replicated here:

* **Khandani, Kim & Lo (2010)**, *Consumer credit-risk models via machine-learning
  algorithms*, JBF 34:2767-2787. Section 4.2: "For all transaction-related items,
  their average values over the prior 6 months, or as many months as available, are
  used." Their Table 5 then calibrates on a window observable at the forecast date and
  applies the fitted model to a later window.
* **Butaru et al. (2015)**, NBER WP 21305. Section III.C: models are estimated "as if
  we were in that time period, i.e., no future data is ever used as inputs to a model".

Both designs need a per-consumer time axis, so this module builds one.

How the trailing window is computed
-----------------------------------
Only **additive** quantities are accumulated per month (counts, euro sums, sums of
squares, weekday tallies). Every ratio, share, mean and standard deviation is then
derived from the trailing *sums*. That is not an approximation: the trailing mean
ticket really is (sum of tickets over the window) / (count over the window), so this
gives values identical to re-slicing the ledger for each origination month, at a
fraction of the cost.

Set A / Set B
-------------
The ``LEAK_`` prefix carries over from :mod:`synthitaly.features` and means the same
thing: the column encodes the answer by construction rather than by behaviour. A
``debt_service`` line exists only for a debtor, a ``credit_draw`` only for a
subsister, an ``overdraft_fee`` only for a chronic. :func:`panel_fair_columns` derives
Set B from the prefix, so membership can never drift out of sync with the data.

One genuinely new judgement call, worth stating plainly. Khandani's headline
stratifier is the credit-card-balance-to-income ratio (their section 3.1), taken from
*credit bureau* data. This model has no bureau, so the observable analogue is narrower:
:data:`overdue_to_income` uses only the biller's own unpaid invoices, which a
counterparty really can see. The bureau-style version is provided as
``LEAK_debt_to_income`` and is Set A only.

Delinquency state (``max_dpd``, ``n_overdue``, ``overdue_eur``) is *fair*: a biller
plainly knows whether it has been paid. It is also strongly autocorrelated with the
forward label, which is a real property of credit risk, not a leak. Khandani handle
exactly this by restricting to accounts current at the forecast date - the
"straight-rollers" test - and :func:`add_forward_labels` emits the ``was_current`` flag
that makes that restriction possible.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from synthitaly import numbers
from synthitaly.features import _last_payday
from synthitaly.model import ItalyModel

__all__ = [
    "LOOKBACK_MONTHS",
    "HORIZONS_MONTHS",
    "monthly_ledger",
    "delinquency_frame",
    "build_panel",
    "add_forward_labels",
    "revolver_state",
    "panel_feature_columns",
    "panel_fair_columns",
    "panel_leak_columns",
    "panel_behaviour_columns",
    "ARREARS_STATE",
    "origination_months",
]

# Khandani, Kim & Lo (2010) s4.2 — six months of trailing history.
LOOKBACK_MONTHS = 6
# Their forecast horizons (s4.4 uses 3-month windows; the paper also reports 6 and 12).
HORIZONS_MONTHS = (3, 6, 12)

_SPEND_CATS = list(numbers.CATEGORY_SHARES.keys())
_BILL_TYPES = list(numbers.BILL_TYPES.keys())


# --------------------------------------------------------------------------- #
# Month-end state
# --------------------------------------------------------------------------- #
def delinquency_frame(model: ItalyModel) -> pd.DataFrame:
    """The month-end credit-file snapshot as a frame, with a ``month_idx``.

    ``month_idx`` is a 0-based integer month counter, which is what all the window
    arithmetic downstream is done in — it avoids period/calendar edge cases when
    forming "the six months up to t" and "the h months after t".
    """
    d = pd.DataFrame(model.export_dpd_history())
    if d.empty:
        raise ValueError(
            "no month-end history — the model has not been run, or ran for less "
            "than one full calendar month"
        )
    months = sorted(d["month"].unique())
    idx = {m: i for i, m in enumerate(months)}
    d["month_idx"] = d["month"].map(idx)
    return d.sort_values(["consumer_id", "month_idx"]).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Monthly additive accumulators from the ledger
# --------------------------------------------------------------------------- #
def monthly_ledger(model: ItalyModel, months: list[str]) -> pd.DataFrame:
    """One row per (consumer, month) of purely **additive** ledger quantities.

    Reindexed onto the full consumer x month grid so months with no activity are
    zeros rather than missing rows — otherwise a trailing window would silently
    average over fewer months than it claims to.
    """
    df = pd.DataFrame(model.transactions)
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.strftime("%Y-%m")

    out = df[df["kind"].isin(["purchase", "bill", "fee"])].copy()
    out["cid"] = out["from"].astype(int)
    inflow = df[df["kind"].isin(["salary", "loan"])].copy()
    inflow["cid"] = inflow["to"].astype(int)

    cids = [c.unique_id for c in model.consumers]
    grid = pd.MultiIndex.from_product([cids, months], names=["consumer_id", "month"])
    base = pd.DataFrame(index=grid)

    def add(name: str, series: pd.Series) -> None:
        series.index.names = ["consumer_id", "month"]
        base[name] = series

    # --- discretionary purchases ---
    pur = out[out["kind"] == "purchase"].copy()
    gk = ["cid", "month"]
    g = pur.groupby(gk)["amount_eur"]
    add("pur_n", g.size())
    add("pur_sum", g.sum())
    add("pur_sumsq", pur.assign(sq=pur["amount_eur"] ** 2).groupby(gk)["sq"].sum())
    # category euros (shares are formed from trailing sums, never averaged)
    catsum = pur.pivot_table(index=gk, columns="category", values="amount_eur",
                             aggfunc="sum", fill_value=0.0)
    for sc in _SPEND_CATS:
        add(f"catsum_{sc}", catsum[sc] if sc in catsum else pd.Series(dtype=float))
    # weekday tallies -> concentration is computed from the summed tallies
    pur["wd"] = pur["date"].dt.weekday
    wd = pur.pivot_table(index=gk, columns="wd", values="amount_eur",
                         aggfunc="size", fill_value=0)
    for w in range(7):
        add(f"wd_{w}", wd[w] if w in wd else pd.Series(dtype=float))
    # euros spent within a week of payday (the behavioural spike)
    dsp = (pur["date"] - pur["date"].map(_last_payday)).dt.days
    pur["post_amt"] = np.where(dsp.between(0, 7), pur["amount_eur"], 0.0)
    add("post_payday_eur", pur.groupby(gk)["post_amt"].sum())

    # --- recurring bills (the SHIW debt-service line is a LEAK_, kept apart) ---
    bills = out[(out["kind"] == "bill") & (out["category"] != "debt_service")]
    add("bill_n", bills.groupby(gk).size())
    add("bill_sum", bills.groupby(gk)["amount_eur"].sum())
    btype = bills.pivot_table(index=gk, columns="category", values="amount_eur",
                              aggfunc="size", fill_value=0)
    for b in _BILL_TYPES:
        add(f"billtype_{b}_n", btype[b] if b in btype else pd.Series(dtype=float))
    late = out[out["category"] == "late_payment_fee"]
    add("latefee_n", late.groupby(gk).size())
    add("latefee_sum", late.groupby(gk)["amount_eur"].sum())

    # --- income credited ---
    sal = inflow[inflow["kind"] == "salary"]
    add("sal_n", sal.groupby(gk).size())
    add("sal_sum", sal.groupby(gk)["amount_eur"].sum())
    add("sal_sumsq", sal.assign(sq=sal["amount_eur"] ** 2).groupby(gk)["sq"].sum())

    # --- LEAK_: debt-mechanic lines ---
    ds = out[out["category"] == "debt_service"]
    add("lk_ds_n", ds.groupby(gk).size())
    add("lk_ds_sum", ds.groupby(gk)["amount_eur"].sum())
    add("lk_od_n", out[out["category"] == "overdraft_fee"].groupby(gk).size())
    cd = inflow[inflow["category"] == "credit_draw"]
    add("lk_cd_n", cd.groupby(gk).size())
    add("lk_cd_sum", cd.groupby(gk)["amount_eur"].sum())

    base = base.fillna(0.0)
    base["has_pur"] = (base["pur_n"] > 0).astype(float)
    return base.reset_index()


# --------------------------------------------------------------------------- #
# The panel
# --------------------------------------------------------------------------- #
def _entropy_concentration(counts: np.ndarray) -> np.ndarray:
    """Row-wise 1 - normalised entropy over 7 weekday bins (vectorised)."""
    tot = counts.sum(axis=1, keepdims=True)
    p = np.divide(counts, tot, out=np.zeros_like(counts, dtype=float), where=tot > 0)
    logp = np.log2(p, out=np.zeros_like(p), where=p > 0)
    ent = -(p * logp).sum(axis=1) / math.log2(7)
    return np.where(tot.ravel() > 0, 1.0 - ent, 0.0)


def _std_from_sums(n: np.ndarray, s: np.ndarray, ss: np.ndarray) -> np.ndarray:
    """Population std from count / sum / sum-of-squares, clipped at zero."""
    with np.errstate(divide="ignore", invalid="ignore"):
        var = np.where(n > 0, ss / n - (s / np.maximum(n, 1)) ** 2, 0.0)
    return np.sqrt(np.clip(var, 0.0, None))


def build_panel(model: ItalyModel, lookback_months: int = LOOKBACK_MONTHS) -> pd.DataFrame:
    """One row per (consumer, ``as_of`` month) with trailing-window features.

    Features describe the ``lookback_months`` ending at and including ``as_of``;
    nothing after ``as_of`` is read. Rows before a full window has accrued are
    dropped, so every row means the same thing — Khandani's "or as many months as
    available" is deliberately not used at the start of the sample, because a
    3-month average and a 6-month average are not the same variable.
    """
    delin = delinquency_frame(model)
    months = sorted(delin["month"].unique())
    ml = monthly_ledger(model, months)

    m = ml.merge(
        delin[["consumer_id", "month", "month_idx", "max_dpd", "dpd_bucket", "n_overdue",
               "overdue_eur", "writeoff_n", "late_fee_n", "cur_balance",
               "savings_balance", "pension_balance", "debt_balance", "has_debt"]],
        on=["consumer_id", "month"], how="left",
    ).sort_values(["consumer_id", "month_idx"]).reset_index(drop=True)

    add_cols = [c for c in ml.columns if c not in ("consumer_id", "month")]
    w = lookback_months
    roll = (m.groupby("consumer_id")[add_cols]
              .rolling(w, min_periods=w).sum()
              .reset_index(drop=True))
    roll.columns = [f"T_{c}" for c in roll.columns]
    # trailing month-end balance statistics (a real volatility measure, not a proxy)
    bal = m.groupby("consumer_id")["cur_balance"]
    roll["T_bal_std"] = bal.rolling(w, min_periods=w).std().reset_index(drop=True)
    roll["T_bal_min"] = bal.rolling(w, min_periods=w).min().reset_index(drop=True)
    roll["T_bal_mean"] = bal.rolling(w, min_periods=w).mean().reset_index(drop=True)
    p = pd.concat([m, roll], axis=1)
    p = p[p["month_idx"] >= w - 1].reset_index(drop=True)

    n_pur = p["T_pur_n"].to_numpy()
    spend = p["T_pur_sum"].to_numpy()
    n_sal = p["T_sal_n"].to_numpy()
    inc = p["T_sal_sum"].to_numpy()
    safe_pur = np.maximum(n_pur, 1)
    safe_spend = np.where(spend > 0, spend, 1.0)
    safe_inc_m = np.where(inc > 0, inc / w, 1.0)   # mean monthly income over the window

    out = pd.DataFrame({"consumer_id": p["consumer_id"], "month": p["month"],
                        "month_idx": p["month_idx"]})

    # --- discretionary spending ---
    out["n_purchases"] = n_pur
    out["total_spend"] = spend
    out["mean_ticket"] = np.where(n_pur > 0, spend / safe_pur, 0.0)
    tstd = _std_from_sums(n_pur, spend, p["T_pur_sumsq"].to_numpy())
    mean_ticket = np.where(n_pur > 0, spend / safe_pur, 0.0)
    out["ticket_cv"] = np.divide(tstd, mean_ticket,
                                 out=np.zeros_like(tstd), where=mean_ticket > 0)
    for sc in _SPEND_CATS:
        out[f"share_{sc}"] = np.where(spend > 0, p[f"T_catsum_{sc}"].to_numpy() / safe_spend, 0.0)
    out["weekday_concentration"] = _entropy_concentration(
        p[[f"T_wd_{i}" for i in range(7)]].to_numpy()
    )
    out["active_months"] = p["T_has_pur"].to_numpy()
    out["spend_per_active_month"] = np.where(
        p["T_has_pur"].to_numpy() > 0, n_pur / np.maximum(p["T_has_pur"].to_numpy(), 1), 0.0
    )
    out["post_payday_share"] = np.where(
        spend > 0, p["T_post_payday_eur"].to_numpy() / safe_spend, 0.0
    )

    # --- bills ---
    out["n_bills"] = p["T_bill_n"].to_numpy()
    out["total_bills"] = p["T_bill_sum"].to_numpy()
    for b in _BILL_TYPES:
        out[f"bill_{b}_n"] = p[f"T_billtype_{b}_n"].to_numpy()
    out["late_fee_n"] = p["T_latefee_n"].to_numpy()
    out["late_fee_sum"] = p["T_latefee_sum"].to_numpy()

    # --- income, and Khandani s3.2's income-shock variable ---
    out["total_income"] = inc
    out["mean_income_credit"] = np.where(n_sal > 0, inc / np.maximum(n_sal, 1), 0.0)
    out["n_income"] = n_sal
    # (this month's income - trailing mean) / trailing sd, per Khandani s3.2: "the
    # difference between the current month's income and the 6-month moving-average of
    # the income, divided by the standard deviation of income over the same window".
    inc_std = _std_from_sums(n_sal, inc, p["T_sal_sumsq"].to_numpy())
    out["income_shock"] = np.where(
        inc_std > 0, (p["sal_sum"].to_numpy() - inc / w) / np.where(inc_std > 0, inc_std, 1.0), 0.0
    )

    # --- current-account state at as_of, and its trailing behaviour ---
    out["cur_balance"] = p["cur_balance"].to_numpy()
    out["balance_std"] = p["T_bal_std"].fillna(0.0).to_numpy()
    out["balance_mean"] = p["T_bal_mean"].to_numpy()
    out["balance_to_income"] = p["T_bal_mean"].to_numpy() / safe_inc_m

    # --- delinquency state at as_of (fair: the biller knows if it was paid) ---
    out["max_dpd"] = p["max_dpd"].to_numpy()
    out["dpd_bucket"] = p["dpd_bucket"].to_numpy()
    out["n_overdue"] = p["n_overdue"].to_numpy()
    out["overdue_eur"] = p["overdue_eur"].to_numpy()
    out["overdue_to_income"] = p["overdue_eur"].to_numpy() / safe_inc_m

    # --- LEAK_: Set A only ---
    out["LEAK_debt_service_n"] = p["T_lk_ds_n"].to_numpy()
    out["LEAK_debt_service_sum"] = p["T_lk_ds_sum"].to_numpy()
    out["LEAK_overdraft_n"] = p["T_lk_od_n"].to_numpy()
    out["LEAK_credit_draw_n"] = p["T_lk_cd_n"].to_numpy()
    out["LEAK_credit_draw_sum"] = p["T_lk_cd_sum"].to_numpy()
    out["LEAK_savings_balance"] = p["savings_balance"].to_numpy()
    out["LEAK_pension_balance"] = p["pension_balance"].to_numpy()
    out["LEAK_debt_balance"] = p["debt_balance"].to_numpy()
    # the bureau-style stratifier of Khandani s3.1; no bureau exists here, so this is
    # Set A only and `overdue_to_income` is its observable counterpart.
    out["LEAK_debt_to_income"] = p["debt_balance"].to_numpy() / safe_inc_m
    out["LEAK_min_balance"] = p["T_bal_min"].to_numpy()

    return out.replace([np.inf, -np.inf], np.nan).fillna(0.0)


def add_forward_labels(
    panel: pd.DataFrame, delin: pd.DataFrame, horizons: tuple[int, ...] = HORIZONS_MONTHS
) -> pd.DataFrame:
    """Attach forward-looking outcome flags to each ``as_of`` row.

    For horizon ``h``, the label covers months strictly after ``as_of`` up to and
    including ``as_of + h``. The trailing features stop at ``as_of``, so feature and
    label windows never overlap.

    ``y_90dpd_{h}m``
        A bill crossed :data:`synthitaly.numbers.WRITE_OFF_DAYS_PAST_DUE` in the
        window — the "90 days or more past due" target of Khandani, Kim & Lo (2010)
        and Butaru et al. (2015).
    ``y_latefee_{h}m``
        A late-payment fee was incurred — a milder, denser distress threshold.
    ``was_current``
        No bill was past due at ``as_of``. Khandani's Table 8 restricts to these to
        isolate "straight-rollers": accounts that look clean and go bad anyway.
    ``horizon_complete_{h}m``
        The full h months exist in the sample. Rows where this is False are excluded
        from evaluation rather than being scored against a truncated window.
    """
    last = int(delin["month_idx"].max())
    p = panel.copy()
    p["was_current"] = (p["max_dpd"].to_numpy() == 0)
    t = p["month_idx"].to_numpy()

    # Cumulative event counts per consumer, with a leading zero column, so the total
    # over the half-open window (t, t+h] is a single subtraction.
    def cumulative(col: str) -> tuple[np.ndarray, dict[int, int]]:
        wide = (delin.pivot(index="consumer_id", columns="month_idx", values=col)
                .reindex(columns=range(last + 1)).fillna(0.0))
        rows = {c: i for i, c in enumerate(wide.index)}
        cum = np.zeros((len(wide), last + 2))
        cum[:, 1:] = wide.to_numpy().cumsum(axis=1)
        return cum, rows

    cum_wo, rows = cumulative("writeoff_n")
    cum_lf, _ = cumulative("late_fee_n")
    r = np.array([rows[c] for c in p["consumer_id"].to_numpy()])

    for h in horizons:
        end = np.minimum(t + h, last)
        # cum[:, k + 1] is the total through month k, so this is months t+1 .. end
        y_wo = cum_wo[r, end + 1] - cum_wo[r, t + 1]
        y_lf = cum_lf[r, end + 1] - cum_lf[r, t + 1]
        p[f"y_90dpd_{h}m"] = y_wo > 0
        p[f"y_latefee_{h}m"] = y_lf > 0
        p[f"horizon_complete_{h}m"] = (t + h) <= last
    return p


def revolver_state(model: ItalyModel, lookback_months: int = LOOKBACK_MONTHS) -> pd.DataFrame:
    """Month-end Transactor/Revolver state, per So, Thomas, Seow & Mues.

    Their section 3 defines a Transactor as "a card holder who pays off the balance
    for at least 12 months before the sampling time, provided the card holder has at
    least one year history, or pays the balance off every period of their history if
    this is less than 12 months". The behavioural translation here: a **Revolver**
    carried a positive debt balance across at least one month boundary in the trailing
    window; a **Transactor** cleared it every month.

    This is genuinely time-varying, which the assigned ``is_debtor`` attribute is not:
    ``Consumer._service_debt`` sets ``has_debt = False`` when a climber's principal
    reaches zero, so a climber really does convert Revolver -> Transactor part-way
    through the run. Roughly 9% of consumers change state at the pinned configuration.
    """
    d = delinquency_frame(model)
    d["revolving"] = (d["debt_balance"] > 0).astype(float)
    w = lookback_months
    d["revolving_trailing"] = (
        d.groupby("consumer_id")["revolving"].rolling(w, min_periods=w).sum()
        .reset_index(drop=True)
    )
    d = d[d["month_idx"] >= w - 1].copy()
    d["is_revolver"] = d["revolving_trailing"] > 0
    d["is_transactor"] = ~d["is_revolver"]
    return d[["consumer_id", "month", "month_idx", "is_revolver", "is_transactor",
              "debt_balance", "has_debt"]].reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Column sets — derived, never hand-listed
# --------------------------------------------------------------------------- #
_NON_FEATURE = ("consumer_id", "month", "month_idx", "was_current")

# The account's own arrears state at ``as_of``. These are entirely fair — a biller
# knows perfectly well whether it has been paid — but they are near-deterministic for
# the forward 90-DPD label, because a bill must already have been overdue for most of
# the write-off horizon before it can cross it. ``max_dpd`` alone scores AUC 0.9999 at
# the pinned configuration.
#
# Set C exists to ask the question that survives that: does *spending and income
# behaviour* predict distress, for an account whose arrears are not being read
# directly? It is the closest thing this model supports to Khandani, Kim & Lo's
# "straight-rollers" test (their Table 8), which is otherwise degenerate here —
# essentially no consumer goes from a clean account to written-off, because arrears in
# this model are a persistent liquidity state rather than a shock.
ARREARS_STATE = (
    "max_dpd", "dpd_bucket", "n_overdue", "overdue_eur", "overdue_to_income",
    "late_fee_n", "late_fee_sum",
)


def panel_feature_columns(frame: pd.DataFrame) -> list[str]:
    """Every predictor column: excludes keys, labels (``y_*``) and window flags."""
    return [
        c for c in frame.columns
        if c not in _NON_FEATURE
        and not c.startswith("y_")
        and not c.startswith("horizon_complete_")
    ]


def panel_leak_columns(frame: pd.DataFrame) -> list[str]:
    """Set A only — columns that encode the answer by construction."""
    return [c for c in panel_feature_columns(frame) if c.startswith("LEAK_")]


def panel_fair_columns(frame: pd.DataFrame) -> list[str]:
    """Set B — what a counterparty could actually observe."""
    return [c for c in panel_feature_columns(frame) if not c.startswith("LEAK_")]


def panel_behaviour_columns(frame: pd.DataFrame) -> list[str]:
    """Set C — Set B minus the account's own arrears state (:data:`ARREARS_STATE`).

    Not a leakage quarantine: these variables are legitimately observable. This set
    isolates whether spending and income *behaviour* carries the signal, once the
    answer cannot be read straight off the arrears counter.
    """
    return [c for c in panel_fair_columns(frame) if c not in ARREARS_STATE]


def origination_months(panel: pd.DataFrame, horizon: int) -> list[int]:
    """The ``month_idx`` values that have both a full trailing window and a full
    forward window at ``horizon``. Returned in order; may be empty, in which case
    the horizon is not evaluable on this run length and should be reported as such
    rather than scored on a truncated window."""
    ok = panel[panel[f"horizon_complete_{horizon}m"]]
    return sorted(ok["month_idx"].unique().tolist())
