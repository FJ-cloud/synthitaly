#!/usr/bin/env python3
"""Shared configuration and data assembly for the three paper replications.

``replicate_so.py``, ``replicate_khandani.py`` and ``replicate_butaru.py`` all need
the same starting point: a finished model, its month-end panel, the forward labels and
the Transactor/Revolver state. Building that costs ~20 seconds a seed, so it is done
once here and cached in-process; the page builder runs all three in one interpreter and
pays for each seed only once.

Nothing in this module decides anything about a paper's method — it only assembles the
data those methods run on.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from synthitaly import features as F  # noqa: E402
from synthitaly import panel as P  # noqa: E402
from synthitaly.model import ItalyModel  # noqa: E402

# The pinned analysis configuration, matching scripts/validation_report.py so the new
# numbers sit alongside the existing Study A-D numbers without a caveat about setup.
CONFIG = {"n_consumers": 800, "n_merchants_per_category": 3, "n_days": 720}

# Butaru et al. (2015) run their horse race across six banks. This model has one
# population, so the six portfolios are six seeds: the spread between them is
# Monte-Carlo error and nothing else, which is a weaker claim than theirs and is
# labelled as such wherever it is reported.
SEEDS = (42, 43, 44, 45, 46, 47)
PRIMARY_SEED = SEEDS[0]

# Horizons used across the three scripts. Khandani et al. forecast 3/6/12 months;
# Butaru et al. forecast 2/3/4 quarters, which is 6/9/12 months.
KHANDANI_HORIZONS = (3, 6, 12)
BUTARU_HORIZONS_Q = (2, 3, 4)
ALL_HORIZONS = tuple(sorted({*KHANDANI_HORIZONS, *(q * 3 for q in BUTARU_HORIZONS_Q)}))

# The two outcome definitions, and why both are carried everywhere.
TARGETS = {
    "y_90dpd": (
        "90+ days past due",
        "A bill went unpaid past the write-off horizon. This is the target variable of "
        "both Lo papers, verbatim.",
    ),
    "y_latefee": (
        "late-payment fee",
        "A late fee was incurred — a milder, much denser distress threshold, carried "
        "because the 90-DPD rate is too thin to support a ten-fold scorecard.",
    ),
}

# The three variable settings. Deliberately not called "fair" and "naive": the point
# is to say exactly which columns are switched on, not to grade them.
VARIABLE_SETS = {
    "A": ("Everything the simulator knows",
          "All columns, including those that encode the answer by construction."),
    "B": ("Only what a bank could observe",
          "Columns that reveal the label mechanically are switched off."),
    "C": ("Observable behaviour, arrears switched off",
          "Set B without the account's own arrears counters, which are near-"
          "deterministic for the forward label."),
}


@dataclass
class Bundle:
    """Everything the replications need for one seed."""

    seed: int
    n_days: int
    model: ItalyModel
    panel: pd.DataFrame          # consumer x month, trailing features + forward labels
    delin: pd.DataFrame          # month-end credit-file snapshot
    revolver: pd.DataFrame       # month-end Transactor/Revolver state
    labels: pd.DataFrame         # ground-truth attributes, for scoring only

    @property
    def last_month(self) -> int:
        return int(self.delin["month_idx"].max())

    def columns(self, which: str) -> list[str]:
        return {
            "A": P.panel_feature_columns,
            "B": P.panel_fair_columns,
            "C": P.panel_behaviour_columns,
        }[which](self.panel)

    def cross_section(self, month_idx: int) -> pd.DataFrame:
        """One row per consumer at ``month_idx``, with T/R state and labels joined.

        This is the shape So, Thomas, Seow & Mues work in: an application scorecard is
        cross-sectional, characteristics at one date against an outcome over the
        following performance period.
        """
        d = self.panel[self.panel["month_idx"] == month_idx]
        r = self.revolver[self.revolver["month_idx"] == month_idx][
            ["consumer_id", "is_revolver", "is_transactor"]
        ]
        return d.merge(r, on="consumer_id").merge(self.labels, on="consumer_id")


# A longer run, used only where a paper's own design demands it.
#
# A forecast at horizon h needs a trailing window behind the origination month, a full
# h ahead of it, and training rows whose labels have already been realised. At 720 days
# (23 closed months) that leaves the 9- and 12-month horizons with **no** evaluable
# origination month at all. Khandani, Kim & Lo forecast at 12 months and Butaru et al.
# at three and four quarters, so those horizons need a longer sample. Extending the
# simulation is the honest fix; quietly shortening the burn-in would not be.
LONG_DAYS = 1440

_CACHE: dict[tuple[int, int], Bundle] = {}


def bundle(seed: int = PRIMARY_SEED, n_days: int | None = None) -> Bundle:
    """Build (or return the cached) data bundle for ``seed``.

    ``n_days`` defaults to the repo-wide pinned configuration; pass
    :data:`LONG_DAYS` for the long-horizon analyses. The cache is keyed on both, so a
    process that needs each pays for each once.
    """
    days = n_days or CONFIG["n_days"]
    key = (seed, days)
    if key in _CACHE:
        return _CACHE[key]
    model = ItalyModel(n_consumers=CONFIG["n_consumers"],
                       n_merchants_per_category=CONFIG["n_merchants_per_category"],
                       n_days=days, seed=seed)
    model.run()
    delin = P.delinquency_frame(model)
    pan = P.add_forward_labels(P.build_panel(model), delin, horizons=ALL_HORIZONS)
    _CACHE[key] = Bundle(
        seed=seed,
        n_days=days,
        model=model,
        panel=pan,
        delin=delin,
        revolver=P.revolver_state(model),
        labels=F.label_frame(model),
    )
    return _CACHE[key]


def bundle_long(seed: int = PRIMARY_SEED) -> Bundle:
    """The :data:`LONG_DAYS` bundle for ``seed``."""
    return bundle(seed, n_days=LONG_DAYS)


def latest_origination(b: Bundle, horizon_months: int) -> int:
    """The most recent ``month_idx`` with both a full trailing window and a full
    forward window — the point with the most history behind it that can still be
    scored honestly."""
    ok = P.origination_months(b.panel, horizon_months)
    if not ok:
        raise ValueError(
            f"horizon {horizon_months}m is not evaluable on a {CONFIG['n_days']}-day run"
        )
    return ok[-1]


def describe_config() -> str:
    return (f"{CONFIG['n_consumers']} consumers x {CONFIG['n_days']} days, "
            f"{len(SEEDS)} seeds ({SEEDS[0]}-{SEEDS[-1]}), "
            f"{P.LOOKBACK_MONTHS}-month trailing window")
