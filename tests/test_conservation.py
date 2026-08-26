"""Global conservation of money.

``test_smoke.py`` checks that each account reconciles to its own statement.
This adds the *system-wide* invariant the per-account tests don't: across
**every** account in the model — consumers' three accounts, every merchant,
every bill/fee/credit-line stand-in, and every IncomeSource — money is only
ever moved, never created or destroyed. Every flow is a paired debit/credit, so
the total balance must always equal the total of the opening balances.
"""

from __future__ import annotations

from synthitaly.model import ItalyModel


def _all_accounts(model: ItalyModel) -> list:
    """Every BankAccount in the model, across all agent kinds."""
    accts = []
    for c in model.consumers:
        accts.extend(c.accounts.as_dict().values())
    for pool in model.merchants.values():
        accts.extend(m.account for m in pool)
    accts.extend(m.account for m in model._bill_merchants.values())
    accts.extend(src.account for src in model.income_sources.values())
    return accts


def test_global_money_is_conserved():
    """Σ balances across the whole system equals Σ opening balances, after a
    multi-month run with income, bills, purchases, fees, sweeps and borrowing."""
    model = ItalyModel(n_consumers=200, n_merchants_per_category=3, n_days=120, seed=42)
    accts = _all_accounts(model)
    opening_total = sum(a.starting_balance for a in accts)
    model.run()
    closing_total = sum(a.balance for a in _all_accounts(model))
    assert abs(closing_total - opening_total) < 0.01

    # Sanity: the system actually moved money — IncomeSources have paid salaries
    # out (their own accounts run negative), so the test isn't vacuous.
    assert any(src.account.balance < 0 for src in model.income_sources.values())


def test_global_conservation_holds_with_overdraft_and_borrowing():
    """Same invariant on a longer horizon where chronic overdrafts and subsister
    credit-line draws are in play."""
    model = ItalyModel(n_consumers=300, n_merchants_per_category=3, n_days=365, seed=7)
    opening_total = sum(a.starting_balance for a in _all_accounts(model))
    model.run()
    closing_total = sum(a.balance for a in _all_accounts(model))
    assert abs(closing_total - opening_total) < 0.01
