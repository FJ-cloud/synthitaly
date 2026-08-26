"""Per-consumer feature pipeline — the single source of truth for the analysis suite.

Everything that turns a finished :class:`~synthitaly.model.ItalyModel` into a
one-row-per-consumer table lives here. It used to be copy-pasted into four places
(``notebooks/clustering.ipynb``, ``notebooks/prediction.ipynb``,
``tests/test_analysis_pipeline.py`` and ``presentation/scripts/generate_figures.py``),
and the copies had drifted apart — the notebooks built a 45-column frame while the
tests and the figure script built a compact 19-column one. That divergence is why the
numbers quoted in the notebook prose, the figure captions and the pinned test bounds
all disagreed with each other. There is now one implementation and one set of names.

The vocabulary matters for the write-up:

``FAIR`` features
    Ordinary activity a bank can observe without knowing the answer — purchase counts
    and tickets, category mix, bill payments, credited income, current-account
    aggregates, balance volatility.

``LEAK_`` features
    Debt-mechanic proxies that *mechanically* encode the label. A ``debt_service``
    line only exists for a debtor; ``credit_draw`` only for a subsister; an
    ``overdraft_fee`` only for a chronic. Keeping them behind a prefix is what makes
    an honest fair-only analysis possible — see ``docs/EXPLANATION.md``.

    ``LEAK_cur_n_entries`` is in this block for a less obvious reason: a raw count of
    current-account entries silently includes the debt-service, credit-draw and
    overdraft lines, so it re-imports the leak under a fair-sounding name. It was
    classified fair until it was audited, and it alone was carrying the difference
    between a fair AUC of 0.91 and the honest ~0.69.

``LEAK_SAVER``
    Fair is *relative to the label*. The ``LEAK_`` prefix quarantines what encodes
    **debtor** status; :data:`LEAK_SAVER` names the two further columns that encode
    **saver** status via the month-close sweep. Use :func:`saver_fair_columns` whenever
    ``is_saver`` is the target — see the comment block on :data:`LEAK_SAVER`.

The full column set is canonical. ``FAIR_COMPACT`` / ``LEAK_COMPACT`` name the small
subset used by the regression tests and the validation figures, where the point is a
stable pinned number rather than maximum signal.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from synthitaly import numbers
from synthitaly.model import ItalyModel

__all__ = [
    "FAIR_COMPACT",
    "LEAK_COMPACT",
    "COMPACT",
    "MONEY_KEYS",
    "build_features",
    "label_frame",
    "feature_columns",
    "fair_columns",
    "leak_columns",
    "money_columns",
    "money_log1p",
    "design_matrix",
    "LEAK_SAVER",
    "saver_fair_columns",
]

# Substrings marking a column as a euro/count magnitude that gets log1p'd before
# scaling, so heavy right tails do not dominate the distance metric.
MONEY_KEYS = ("spend", "ticket", "bills", "income", "balance", "sum", "total")

# The compact subset — pinned by tests/test_analysis_pipeline.py and used for the
# validation figures. A strict subset of the full frame's columns.
FAIR_COMPACT = [
    "n_purchases", "total_spend", "mean_ticket", "n_bills", "total_bills",
    "total_income", "mean_income_credit", "cur_balance", "cur_total_in",
    "cur_total_out", "balance_std_proxy",
]
LEAK_COMPACT = [
    "LEAK_debt_service_n", "LEAK_debt_service_sum", "LEAK_overdraft_n",
    "LEAK_credit_draw_n", "LEAK_savings_balance", "LEAK_pension_balance",
    "LEAK_debt_balance", "LEAK_min_balance_proxy",
]
COMPACT = FAIR_COMPACT + LEAK_COMPACT

_PAYDAY = numbers.PAYDAY_DAY_OF_MONTH
_SPEND_CATS = list(numbers.CATEGORY_SHARES.keys())
_BILL_TYPES = list(numbers.BILL_TYPES.keys())


def _last_payday(d: pd.Timestamp) -> pd.Timestamp:
    """The most recent payday on or before ``d``."""
    if d.day >= _PAYDAY:
        return pd.Timestamp(d.year, d.month, _PAYDAY)
    m = d.month - 1 or 12
    y = d.year if d.month > 1 else d.year - 1
    return pd.Timestamp(y, m, _PAYDAY)


def _concentration(counts: np.ndarray, k: int) -> float:
    """1 - normalised entropy: 0 = spread evenly over the k bins, ->1 = concentrated."""
    tot = counts.sum()
    if tot == 0:
        return 0.0
    p = counts[counts > 0] / tot
    return float(1.0 - (-(p * np.log2(p)).sum()) / math.log2(k)) if k > 1 else 0.0


def build_features(model: ItalyModel) -> pd.DataFrame:
    """One row per consumer, derived only from the two exported tables.

    Nothing here reads agent internals that a bank could not see, with the deliberate
    exception of the ``LEAK_`` block (and ``debt_balance``, which is the label in all
    but name). Returns a frame with a ``consumer_id`` column and no NaNs.
    """
    df = pd.DataFrame(model.transactions)
    df["date"] = pd.to_datetime(df["date"])
    acc = pd.DataFrame(model.export_accounts())
    base = pd.DataFrame(
        {"consumer_id": [c.unique_id for c in model.consumers]}
    ).set_index("consumer_id")

    out = df[df["kind"].isin(["purchase", "bill", "fee"])].copy()
    out["cid"] = out["from"].astype(int)
    inflow = df[df["kind"].isin(["salary", "loan"])].copy()
    inflow["cid"] = inflow["to"].astype(int)

    # --- discretionary spending ---
    pur = out[out["kind"] == "purchase"].copy()
    g = pur.groupby("cid")["amount_eur"]
    base["n_purchases"] = g.size()
    base["total_spend"] = g.sum()
    base["mean_ticket"] = g.mean()
    base["median_ticket"] = g.median()
    base["ticket_cv"] = g.std() / g.mean()
    cat = pur.pivot_table(
        index="cid", columns="category", values="amount_eur", aggfunc="sum", fill_value=0.0
    )
    cat_tot = cat.sum(axis=1)
    for sc in _SPEND_CATS:
        base[f"share_{sc}"] = (cat[sc] / cat_tot) if sc in cat else 0.0
    pur["wd"] = pur["date"].dt.weekday
    wd = pur.pivot_table(index="cid", columns="wd", values="amount_eur", aggfunc="size", fill_value=0)
    base["weekday_concentration"] = wd.apply(lambda r: _concentration(r.to_numpy(), 7), axis=1)
    pur["ym"] = pur["date"].dt.to_period("M")
    base["active_months"] = pur.groupby("cid")["ym"].nunique()
    base["spend_per_active_month"] = base["n_purchases"] / base["active_months"]
    # Share of purchase euros falling in the week after payday — the behavioural
    # spike, expressed per consumer. Computed with two grouped sums rather than a
    # groupby.apply so it is independent of pandas' apply/include_groups semantics.
    dsp = (pur["date"] - pur["date"].map(_last_payday)).dt.days
    pur["post_amt"] = np.where(dsp.between(0, 7), pur["amount_eur"], 0.0)
    gp = pur.groupby("cid")
    base["post_payday_share"] = gp["post_amt"].sum() / gp["amount_eur"].sum()

    # --- recurring bills (excluding the SHIW debt-service line) ---
    bills = out[(out["kind"] == "bill") & (out["category"] != "debt_service")]
    base["n_bills"] = bills.groupby("cid").size()
    base["total_bills"] = bills.groupby("cid")["amount_eur"].sum()
    btype = bills.pivot_table(
        index="cid", columns="category", values="amount_eur", aggfunc="size", fill_value=0
    )
    for b in _BILL_TYPES:
        base[f"bill_{b}_n"] = btype[b] if b in btype else 0.0
    late = out[out["category"] == "late_payment_fee"]
    base["late_fee_n"] = late.groupby("cid").size()
    base["late_fee_sum"] = late.groupby("cid")["amount_eur"].sum()

    # --- income (what the bank sees credited) ---
    sal = inflow[inflow["kind"] == "salary"]
    base["total_income"] = sal.groupby("cid")["amount_eur"].sum()
    base["mean_income_credit"] = sal.groupby("cid")["amount_eur"].mean()
    base["n_income"] = sal.groupby("cid").size()

    # --- current-account activity ---
    cur = acc[acc["account_type"] == "current"].set_index("consumer_id")
    base["cur_balance"] = cur["balance"]
    base["cur_total_in"] = cur["total_in"]
    base["cur_total_out"] = cur["total_out"]
    # LEAK_, despite the innocuous name: this counts *every* entry on the current
    # account, and that includes the monthly debt-service bill, credit draws and
    # overdraft fees — the very lines the LEAK_ block exists to quarantine. It looks
    # fair and is not. Regressed on the other fair activity counts (n_purchases,
    # n_bills, n_income; R^2 = 0.975), the leftover part correlates +0.46 with the
    # debt-mechanic line count and predicts is_debtor on its own at AUC 0.78 — mean
    # residual by subtype: none -2.8, climber +10.8, subsister +6.0, chronic +18.5,
    # tracking the extra entries the debt machinery actually writes. Left in the fair
    # set it inflated the headline fair AUC from ~0.69 to 0.91. See docs/EXPLANATION.md.
    base["LEAK_cur_n_entries"] = cur["n_entries"]
    # approximate current-balance path (ignores internal sweeps) -> volatility
    sign = df.assign(
        cid=np.where(df["kind"].isin(["salary", "loan"]), df["to"], df["from"]).astype(int),
        signed=np.where(df["kind"].isin(["salary", "loan"]), df["amount_eur"], -df["amount_eur"]),
    )
    start = {c.unique_id: c.accounts.current.starting_balance for c in model.consumers}
    mins, stds = {}, {}
    for cid, grp in sign.sort_values("date").groupby("cid"):
        path = start.get(cid, 0.0) + grp["signed"].cumsum()
        mins[cid], stds[cid] = path.min(), path.std()
    base["balance_std_proxy"] = pd.Series(stds)

    # --- LEAK_*: debt-mechanic proxies (excluded from the "fair" analysis) ---
    ds = out[out["category"] == "debt_service"]
    base["LEAK_debt_service_n"] = ds.groupby("cid").size()
    base["LEAK_debt_service_sum"] = ds.groupby("cid")["amount_eur"].sum()
    base["LEAK_overdraft_n"] = out[out["category"] == "overdraft_fee"].groupby("cid").size()
    cd = inflow[inflow["category"] == "credit_draw"]
    base["LEAK_credit_draw_n"] = cd.groupby("cid").size()
    base["LEAK_credit_draw_sum"] = cd.groupby("cid")["amount_eur"].sum()
    base["LEAK_savings_balance"] = acc[acc["account_type"] == "savings"].set_index("consumer_id")["balance"]
    base["LEAK_pension_balance"] = acc[acc["account_type"] == "pension"].set_index("consumer_id")["balance"]
    base["LEAK_debt_balance"] = pd.Series({c.unique_id: c.debt_balance for c in model.consumers})
    base["LEAK_min_balance_proxy"] = pd.Series(mins)  # < 0 reveals a chronic overdraft

    # Consumers with no activity in a given block leave NaNs; 0 is the right reading
    # (no purchases => no spend). Ratios of two absent quantities land here too.
    base = base.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    return base.reset_index()


def label_frame(model: ItalyModel) -> pd.DataFrame:
    """Ground-truth labels — the things a bank does *not* see, used only for scoring."""
    return pd.DataFrame([{
        "consumer_id": c.unique_id,
        "debtor_subtype": c.debtor_subtype or "none",
        "is_debtor": c.debtor_subtype is not None,
        "is_climber": c.debtor_subtype == "climber",
        "income_source": c.income_source,
        "income_level": c.income_level,
        "financial_status": ("saver" if c.is_saver else "non_saver") + ("+debt" if c.has_debt else ""),
        "is_saver": c.is_saver,
        "macro_area": c.macro_area,
    } for c in model.consumers])


def feature_columns(frame: pd.DataFrame) -> list[str]:
    """Every feature column in ``frame`` (i.e. everything but ``consumer_id``)."""
    return [c for c in frame.columns if c != "consumer_id"]


def leak_columns(frame: pd.DataFrame) -> list[str]:
    return [c for c in feature_columns(frame) if c.startswith("LEAK_")]


# Columns that are constant for every consumer, so they carry no information and
# cannot be correlated with anything. They stay in the frame — they are honest
# descriptive counts, and the data appendix reports them — but they are excluded
# from every analysis column set below, because a zero-variance column puts NaNs
# into a correlation matrix and takes the factorability tests down with it.
#
#   n_income — one income credit per payday per consumer, so this is just the
#     number of paydays in the run. It varied only while the secondary
#     property-income credit existed (that gave ~10% of consumers a second
#     credit per payday); removing that mechanism made it degenerate. Note the
#     per-month ``n_income`` in ``panel.py`` is NOT degenerate — there it is 0 or
#     1 depending on whether the month contained a payday.
DEGENERATE_COLUMNS = ("n_income",)


def fair_columns(frame: pd.DataFrame) -> list[str]:
    return [
        c for c in feature_columns(frame)
        if not c.startswith("LEAK_") and c not in DEGENERATE_COLUMNS
    ]


def money_columns(cols: list[str]) -> list[str]:
    return [c for c in cols if any(k in c for k in MONEY_KEYS)]


def money_log1p(frame: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    """``log1p`` the money magnitudes in ``cols``. Returns a new DataFrame.

    The compressive half of :func:`design_matrix`, split out because the two halves
    have *different cross-validation status* and conflating them invites the classic
    mistake:

    * This step is **parameter-free** — ``clip`` and ``log1p`` are fixed row-wise maps
      that estimate nothing from the sample — so applying it before a train/test split
      leaks nothing, and it is safe to hand the result straight to ``cross_val_*``.
    * Standardisation is **not** parameter-free: it estimates a mean and a variance.
      Fitting it on the full sample before cross-validating is the error set out in
      Hastie, Tibshirani & Friedman, *The Elements of Statistical Learning* (2nd ed.)
      §7.10.2, "The Wrong and Right Way to Do Cross-validation". It belongs inside a
      ``Pipeline`` so it is refit on each training fold — see the scikit-learn user
      guide, "Common pitfalls and recommended practices" §12.2.

    So: supervised code calls ``money_log1p`` and puts ``StandardScaler`` in its
    pipeline; unsupervised code (KMeans, the correlation matrix), where no folds
    exist, calls :func:`design_matrix` and gets both halves at once.

    Two known distortions, documented rather than fixed (they would re-pin every
    validation number for a cosmetic gain — see ``docs/RESULTS_validation.md`` §8):
    ``clip(lower=0)`` destroys the sign of the columns where negativity *is* the
    signal (``cur_balance``, ``LEAK_min_balance_proxy``), and :data:`MONEY_KEYS`
    matches by substring, so the ratio ``ticket_cv`` and the counts ``n_bills`` /
    ``n_income`` are log-transformed as though they were euro magnitudes.
    """
    X = frame[cols].copy()
    for c in money_columns(cols):
        X[c] = np.log1p(X[c].clip(lower=0))
    return X


# ``cur_total_in`` (every euro credited to the current account) and ``total_income``
# (the sum of salary credits) measure almost the same thing — r = 0.9997 at the pinned
# 800x720 config. Both stay in the frame because they are genuinely different
# quantities, but a linear model splits the income signal between them arbitrarily:
# with ``cur_total_in`` present the coefficients read +1.36 / +0.27, without it they
# consolidate to a sensible +0.98 / +0.83. The predictive cost of dropping it is
# negligible (fair AUC 0.6965 -> 0.6944), so drop it whenever COEFFICIENTS are being
# read as "which behaviours predict debt", and keep it when accuracy is being measured.
COLLINEAR_DUPLICATES = ("cur_total_in",)


def interpretable_columns(cols: list[str]) -> list[str]:
    """``cols`` minus the near-duplicates that make linear coefficients unstable."""
    return [c for c in cols if c not in COLLINEAR_DUPLICATES]


# ``fair`` is not an absolute property of a column — it is relative to the label being
# predicted. The ``LEAK_`` prefix above quarantines what mechanically encodes *debtor*
# status. These two columns are fair for that label and leak the *saver* label:
#
#   ``Consumer._month_close`` sweeps the month's positive residual into savings (or
#   pension), and that sweep is a DEBIT ON THE CURRENT ACCOUNT. ``export_accounts()``
#   sums every entry, so ``cur_total_out`` includes a line that exists only for savers,
#   and ``cur_balance`` is the balance left *after* it. Measured at the pinned 800x720
#   config: cur_total_out correlates +0.556 with is_saver, cur_balance -0.339, and
#   is_saver reads AUC 0.995 on the unmodified fair set against 0.827 with these two
#   quarantined. That is a larger leak than the cur_n_entries one.
#
# Note what is NOT here: ``balance_std_proxy`` (+0.303 with is_saver) is built from the
# transaction stream, and sweeps are never written to ``model.transactions`` — its kinds
# are purchase/bill/salary/fee/loan only. So that correlation is genuine behavioural
# signal and the column stays. ``cur_total_in`` is clean for the same reason the sweep
# cannot reach it: the credit lands on savings/pension, not on the current account.
LEAK_SAVER = ("cur_total_out", "cur_balance")


def saver_fair_columns(frame: pd.DataFrame) -> list[str]:
    """Fair features for the *saver* label: :func:`fair_columns` minus :data:`LEAK_SAVER`.

    Use this wherever ``is_saver`` is the target. ``fair_columns`` is deliberately left
    alone so every pinned debtor number stays exactly where it is.
    """
    return [c for c in fair_columns(frame) if c not in LEAK_SAVER]


def design_matrix(frame: pd.DataFrame, cols: list[str]) -> np.ndarray:
    """log1p the money magnitudes, then standardise. Returns a plain ndarray.

    For **unsupervised** use — KMeans and the correlation matrix — where there is no
    train/test split and fitting the scaler on everything is the intended behaviour.

    Do not feed the output to ``cross_val_*``: standardising on the full sample first
    is the ESL §7.10.2 error. Use :func:`money_log1p` plus a ``Pipeline`` there
    instead. (In practice the outer scaling is *cancelled* by an inner one — restandardising
    is invariant to a prior per-column affine map, so the two give bit-identical
    results — but code that relies on that accident silently becomes a real leak the
    moment the inner scaler is removed.)
    """
    from sklearn.preprocessing import StandardScaler

    return StandardScaler().fit_transform(money_log1p(frame, cols))
