"""Shared pytest fixtures and configuration.

Two jobs:

1. ``restore_numbers_globals`` (autouse) — several tests poke module-level
   constants in ``synthitaly.numbers`` (e.g. ``PAYDAY_SPIKE_PEAK``,
   ``INCOME_SOURCE_SHARE``, the debtor-subtype splits) and restore them in a
   ``finally``. That is fragile: a crash mid-test leaks the mutated value into
   every later test. This autouse fixture snapshots all mutable module-level
   constants before each test and restores them afterwards, unconditionally.

2. ``seeded_model`` — a single, already-run model shared across the (many)
   read-only assertions so we don't rebuild/run one per test.

Plus a registered ``slow`` marker for the long-horizon debt tests
(``uv run pytest -m "not slow"`` skips them).
"""

from __future__ import annotations

import copy

import pytest

from synthitaly import numbers
from synthitaly.model import ItalyModel

# The mutable constant types we snapshot/restore. Scalars are restored by
# re-binding the name; dicts/tuples/sets by deep-copying the value back.
_SNAPSHOT_TYPES = (int, float, str, bool, dict, tuple, frozenset, set, list)


def _snapshot_numbers() -> dict[str, object]:
    snap: dict[str, object] = {}
    for name, value in vars(numbers).items():
        if name.startswith("__"):
            continue
        if callable(value):
            continue
        if isinstance(value, _SNAPSHOT_TYPES):
            snap[name] = copy.deepcopy(value)
    return snap


@pytest.fixture(autouse=True)
def restore_numbers_globals():
    """Restore every mutable ``numbers`` constant after each test, so tests that
    mutate them (and may crash before their own ``finally``) can't leak state."""
    snap = _snapshot_numbers()
    try:
        yield
    finally:
        for name, value in snap.items():
            setattr(numbers, name, copy.deepcopy(value))


@pytest.fixture(scope="session")
def seeded_model() -> ItalyModel:
    """A representative model, built and run once for read-only assertions.

    90 days reaches three paydays and one savings sweep cycle; 120 consumers is
    enough that every income source and debtor subtype is populated.
    """
    model = ItalyModel(n_consumers=120, n_merchants_per_category=2, n_days=90, seed=42)
    model.run()
    return model


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "slow: long-horizon (multi-year) runs; deselect with -m 'not slow'",
    )
