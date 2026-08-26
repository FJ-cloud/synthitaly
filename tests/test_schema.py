"""Output-schema lock and run determinism.

Freezing the exact column sets of the two exported tables guards against silent
schema drift — exactly the failure that left the committed ``demo_accounts.csv``
missing the ``income_level`` column. The determinism test underwrites any claim
that a fixed seed reproduces the same dataset.
"""

from __future__ import annotations

from synthitaly.model import ItalyModel

# The frozen contracts. Update these deliberately (and the data docs) when a
# column is added or removed — that is the point: the change can't be silent.
TRANSACTION_KEYS = {
    "date", "kind", "from", "to", "category", "amount_eur", "macro_area",
}
ACCOUNT_KEYS = {
    "owner_id", "consumer_id", "macro_area", "income_source", "income_level",
    "income_quartile", "income_quintile", "financial_status", "debtor_subtype",
    "debt_balance", "cluster", "account_type", "starting_balance", "balance",
    "n_entries", "total_in", "total_out",
}


def test_transaction_schema_is_frozen():
    model = ItalyModel(n_consumers=60, n_merchants_per_category=2, n_days=30, seed=6)
    model.run()
    assert model.transactions
    for t in model.transactions:
        assert set(t.keys()) == TRANSACTION_KEYS


def test_account_export_schema_is_frozen():
    model = ItalyModel(n_consumers=60, n_merchants_per_category=2, n_days=30, seed=6)
    model.run()
    rows = model.export_accounts()
    assert rows
    for r in rows:
        assert set(r.keys()) == ACCOUNT_KEYS


def _run():
    model = ItalyModel(n_consumers=100, n_merchants_per_category=3, n_days=60, seed=123)
    model.run()
    return model


def test_same_seed_reproduces_identical_outputs():
    """Two runs with the same seed produce byte-identical transactions and
    account exports — the reproducibility guarantee."""
    a, b = _run(), _run()
    assert a.transactions == b.transactions
    assert a.export_accounts() == b.export_accounts()


def test_different_seed_changes_outputs():
    a = _run()
    other = ItalyModel(n_consumers=100, n_merchants_per_category=3, n_days=60, seed=999)
    other.run()
    assert a.transactions != other.transactions


# --------------------------------------------------------------------------- #
# The dataset exporter
# --------------------------------------------------------------------------- #
# ``scripts/export_dataset.py`` is the one-command way to get data out of the
# model, so the guide in ``docs/USAGE.md`` points at it. It reuses the same public
# API the analysis uses, which means a rename in ``features``/``panel`` would break
# the documented workflow silently. This pins the contract: the files it promises,
# and that its feature frame is the same 46-column frame as
# ``runs/latest/features.csv``.
EXPORT_FILES = {
    "transactions", "accounts", "features", "labels", "daily_kpis", "credit_panel",
}


def test_export_dataset_writes_every_promised_file(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "export_dataset.py"),
         "--consumers", "40", "--days", "40", "--out", str(tmp_path)],
        capture_output=True, text=True, cwd=root,
    )
    assert result.returncode == 0, result.stderr

    for name in EXPORT_FILES:
        assert (tmp_path / f"{name}.csv").exists(), f"{name}.csv was not written"
    assert (tmp_path / "MANIFEST.md").exists()


def test_exported_feature_frame_matches_the_analysis_frame(tmp_path):
    """The exporter's ``features.csv`` is the analysis frame, not a lookalike."""
    import pandas as pd

    from synthitaly import features as F

    model = ItalyModel(n_consumers=40, n_merchants_per_category=2, n_days=40, seed=42)
    model.run()

    # ``scripts/`` is not a package, so load the module by path the way the
    # report builders load their own shared helpers.
    import importlib.util
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    spec = importlib.util.spec_from_file_location(
        "export_dataset", root / "scripts" / "export_dataset.py"
    )
    X = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(X)

    frames = X.build_frames(model)
    assert set(frames) == EXPORT_FILES

    feats = frames["features"]
    pd.testing.assert_frame_equal(feats, F.build_features(model))
    # 46 columns: consumer_id + 34 fair + 10 LEAK_ + n_income (degenerate, excluded
    # from every analysis but still exported so the frame matches runs/latest.
    assert feats.shape[1] == 46
    assert len(F.fair_columns(feats)) == 34
    assert len(F.leak_columns(feats)) == 10
