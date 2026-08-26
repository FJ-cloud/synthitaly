"""Per-day balance-over-time collection: the ``bal_cur_*`` DataCollector
reporters and the ``group_balances()`` snapshot that feeds them."""

from __future__ import annotations

from synthitaly import numbers
from synthitaly.model import ItalyModel


def _expected_bal_columns() -> list[str]:
    cols = [f"bal_cur_src_{s}" for s in numbers.INCOME_SOURCE_SHARE]
    cols += [f"bal_cur_lvl_{lv}" for lv in ("low", "middle", "high")]
    cols += [f"bal_cur_dst_{st}" for st in numbers.DEBTOR_SUBTYPES]
    return cols


def test_balance_reporter_columns_present(seeded_model):
    df = seeded_model.datacollector.get_model_vars_dataframe()
    for col in _expected_bal_columns():
        assert col in df.columns
    assert len(df) == seeded_model.n_days


def test_group_balances_matches_hand_computed_means():
    """The grouped means equal a direct recomputation from the live accounts."""
    model = ItalyModel(n_consumers=80, n_merchants_per_category=2, n_days=20, seed=3)
    model.run()
    gb = model.group_balances()
    assert set(gb) == {"src", "lvl", "dst"}
    for s in numbers.INCOME_SOURCE_SHARE:
        grp = [c.accounts.current.balance for c in model.consumers if c.income_source == s]
        if grp:
            assert abs(gb["src"][s] - sum(grp) / len(grp)) < 1e-6
    for lv in ("low", "middle", "high"):
        grp = [c.accounts.current.balance for c in model.consumers if c.income_level == lv]
        if grp:
            assert abs(gb["lvl"][lv] - sum(grp) / len(grp)) < 1e-6


def test_last_collected_row_equals_current_snapshot(seeded_model):
    """After the run, the last collected day equals the model's live
    ``group_balances()`` (nothing has moved since the final step)."""
    df = seeded_model.datacollector.get_model_vars_dataframe()
    gb = seeded_model.group_balances()
    for s in numbers.INCOME_SOURCE_SHARE:
        assert abs(df[f"bal_cur_src_{s}"].iloc[-1] - gb["src"].get(s, 0.0)) < 1e-6


def test_balances_are_a_real_trajectory(seeded_model):
    """The series is a genuine per-day trajectory, not a constant (payday inflow
    and daily spend move the mean payroll balance around)."""
    df = seeded_model.datacollector.get_model_vars_dataframe()
    assert df["bal_cur_src_payroll"].nunique() > 1
