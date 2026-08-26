"""End-to-end smoke test: the model builds, steps, and produces transactions."""

from __future__ import annotations

from datetime import date, timedelta

from synthitaly import ItalyModel, numbers


def test_model_builds_with_defaults():
    model = ItalyModel(n_consumers=30, n_merchants_per_category=2, n_days=5, seed=1)
    assert len(model.consumers) == 30
    # Every consumer belongs to exactly one macro-area.
    for c in model.consumers:
        assert c.macro_area in {"NORTH", "CENTRE", "SOUTH"}


def test_model_runs_and_emits_transactions():
    model = ItalyModel(n_consumers=50, n_merchants_per_category=3, n_days=10, seed=42)
    model.run()
    txns = model.transactions
    assert len(txns) > 0
    # Every transaction has the expected keys.
    for t in txns[:20]:
        assert set(t.keys()) >= {
            "date", "kind", "from", "to", "category", "amount_eur", "macro_area",
        }
        assert t["amount_eur"] > 0
        assert t["macro_area"] in {"NORTH", "CENTRE", "SOUTH"}
        assert t["kind"] in {"salary", "bill", "purchase", "fee"}


def test_income_bands_assigned():
    """Every consumer gets an income quartile in 1..4 and quintile in 1..5,
    and at n=200 every band is populated (the percentile split is total and
    non-degenerate)."""
    model = ItalyModel(n_consumers=200, n_merchants_per_category=2, n_days=1, seed=9)
    quartiles = {c.income_quartile for c in model.consumers}
    quintiles = {c.income_quintile for c in model.consumers}
    for c in model.consumers:
        assert c.income_quartile in {1, 2, 3, 4}
        assert c.income_quintile in {1, 2, 3, 4, 5}
    assert quartiles == {1, 2, 3, 4}
    assert quintiles == {1, 2, 3, 4, 5}


def test_payday_produces_salary_transactions():
    # The simulation starts 2017-01-01; running 30 days reaches 2017-01-27 (payday).
    model = ItalyModel(n_consumers=20, n_merchants_per_category=2, n_days=30, seed=7)
    model.run()
    salary_txns = [t for t in model.transactions if t["kind"] == "salary"]
    assert len(salary_txns) >= 20  # at least one salary per consumer


def test_datacollector_has_recorded_each_day():
    model = ItalyModel(n_consumers=20, n_merchants_per_category=2, n_days=12, seed=3)
    model.run()
    df = model.datacollector.get_model_vars_dataframe()
    assert len(df) == 12
    assert "daily_txn_count" in df.columns
    assert "daily_eur_total" in df.columns


def test_consumer_account_balance_matches_entries():
    """Every consumer's running balance should equal
    starting_balance + sum(credits) - sum(debits) on their statement."""
    model = ItalyModel(n_consumers=40, n_merchants_per_category=2, n_days=30, seed=11)
    model.run()
    # Pick the first consumer that actually had activity.
    active = next(c for c in model.consumers if c.account.entries)
    ins = sum(e.amount_eur for e in active.account.entries if e.direction == "in")
    outs = sum(e.amount_eur for e in active.account.entries if e.direction == "out")
    expected = active.account.starting_balance + ins - outs
    assert abs(active.account.balance - expected) < 1e-6


def test_merchant_entries_are_all_credits():
    """Merchants only receive money — every entry on a merchant account
    should be an 'in', and the balance equals the sum of those credits."""
    model = ItalyModel(n_consumers=50, n_merchants_per_category=3, n_days=30, seed=5)
    model.run()
    # Flatten all merchants in the regular pool.
    every_merchant = [m for pool in model.merchants.values() for m in pool]
    active_merchant = next(m for m in every_merchant if m.account.entries)
    for e in active_merchant.account.entries:
        assert e.direction == "in"
    total_credits = sum(e.amount_eur for e in active_merchant.account.entries)
    assert abs(active_merchant.account.balance - total_credits) < 1e-6


def _reconciles(acct) -> bool:
    ins = sum(e.amount_eur for e in acct.entries if e.direction == "in")
    outs = sum(e.amount_eur for e in acct.entries if e.direction == "out")
    return abs(acct.balance - (acct.starting_balance + ins - outs)) < 1e-6


def test_each_account_reconciles_independently():
    """Current, savings and pension each satisfy start + Σin − Σout = balance,
    even though savings/pension are fed by internal sweeps."""
    model = ItalyModel(n_consumers=120, n_merchants_per_category=2, n_days=95, seed=8)
    model.run()
    for c in model.consumers:
        for acct in c.accounts.as_dict().values():
            assert _reconciles(acct)


def test_savings_sweep_conserves_money():
    """The sweep moves money between a consumer's own accounts — it never
    creates or destroys any. Whole-portfolio total must equal the current
    account's starting balance plus its *external* (non-sweep) flows."""
    model = ItalyModel(n_consumers=120, n_merchants_per_category=2, n_days=95, seed=8)
    model.run()
    swept = [
        c for c in model.consumers
        if c.accounts.savings.entries or c.accounts.pension.entries
    ]
    assert len(swept) >= 1  # the sweep actually fires for someone
    for c in swept:
        cur = c.accounts.current
        total = cur.balance + c.accounts.savings.balance + c.accounts.pension.balance
        ext_in = sum(
            e.amount_eur for e in cur.entries
            if e.direction == "in" and e.category not in ("savings_sweep", "pension_sweep")
        )
        ext_out = sum(
            e.amount_eur for e in cur.entries
            if e.direction == "out" and e.category not in ("savings_sweep", "pension_sweep")
        )
        assert abs(total - (cur.starting_balance + ext_in - ext_out)) < 1e-6


def test_pension_pot_nonempty_for_some():
    """Over three months at least one pension-saver builds a positive pot."""
    model = ItalyModel(n_consumers=200, n_merchants_per_category=2, n_days=95, seed=8)
    model.run()
    assert any(c.accounts.pension.balance > 0 for c in model.consumers)


def test_overdraft_floor_respected_and_reconciles():
    """Only overdraft-allowed debt-holders may go negative, never past their
    floor; the balance still reconciles to the statement when negative."""
    model = ItalyModel(n_consumers=300, n_merchants_per_category=3, n_days=90, seed=42)
    model.run()
    negatives = [c for c in model.consumers if c.account.balance < -1e-9]
    # Hard invariant: a consumer without overdraft permission is never negative.
    for c in model.consumers:
        if not c.overdraft_allowed:
            assert c.account.balance >= -1e-9
    # Anyone in the red is an overdraft-allowed debt-holder, above their floor.
    for c in negatives:
        assert c.overdraft_allowed and c.has_debt
        assert c.account.balance >= c._overdraft_floor - 1e-6
    # Overdraft actually bites — some debt-holder ends in the red.
    assert len(negatives) >= 1
    # Reconciliation holds even with a negative balance.
    for c in negatives:
        ins = sum(e.amount_eur for e in c.account.entries if e.direction == "in")
        outs = sum(e.amount_eur for e in c.account.entries if e.direction == "out")
        expected = c.account.starting_balance + ins - outs
        assert abs(c.account.balance - expected) < 1e-6


def test_debt_service_transactions_emitted():
    """With a sizeable population some consumers hold debt; running past the
    debt-service day produces at least one debt_service bill, and it flows to
    a credit-only stand-in merchant."""
    model = ItalyModel(n_consumers=200, n_merchants_per_category=2, n_days=30, seed=13)
    assert any(c.has_debt for c in model.consumers)
    model.run()
    ds = [t for t in model.transactions if t["category"] == "debt_service"]
    assert len(ds) >= 1
    assert all(t["kind"] == "bill" for t in ds)
    # The debt-service stand-in only ever receives money.
    for area in ("NORTH", "CENTRE", "SOUTH"):
        m = model._bill_merchant("debt_service", area)
        for e in m.account.entries:
            assert e.direction == "in"


def test_export_accounts_shape():
    """Three rows per consumer (current/savings/pension); each row's cluster
    fields are populated and start + in − out reconciles to balance."""
    model = ItalyModel(n_consumers=60, n_merchants_per_category=2, n_days=40, seed=6)
    model.run()
    rows = model.export_accounts()
    assert len(rows) == 3 * len(model.consumers)
    seen_types: dict[int, set] = {}
    for r in rows:
        assert r["account_type"] in {"current", "savings", "pension"}
        assert r["macro_area"] in {"NORTH", "CENTRE", "SOUTH"}
        assert r["income_quartile"] in {1, 2, 3, 4}
        assert r["financial_status"] in {
            "saver", "non_saver", "saver+debt", "non_saver+debt",
        }
        # Debtor archetype: None for never-indebted consumers, else one of the
        # three subtypes; the debt balance is a non-negative stock.
        assert r["debtor_subtype"] in {None, *numbers.DEBTOR_SUBTYPES}
        assert r["debt_balance"] >= 0.0
        # Each field is rounded to cents independently, so allow a few
        # cents of accumulated rounding noise in the reconciliation.
        assert abs(
            (r["starting_balance"] + r["total_in"] - r["total_out"]) - r["balance"]
        ) < 0.05
        seen_types.setdefault(r["consumer_id"], set()).add(r["account_type"])
    for types in seen_types.values():
        assert types == {"current", "savings", "pension"}


def test_cluster_of_stable():
    model = ItalyModel(n_consumers=40, n_merchants_per_category=2, n_days=1, seed=2)
    grouped = model.clusters()
    assert sum(len(v) for v in grouped.values()) == len(model.consumers)
    for c in model.consumers:
        area, band, status = model.cluster_of(c)
        assert area in {"NORTH", "CENTRE", "SOUTH"}
        assert band in {"Q1", "Q2", "Q3", "Q4"}
        assert status in {"saver", "non_saver", "saver+debt", "non_saver+debt"}
        assert c in grouped[(area, band, status)]


def test_viz_module_imports():
    """Importing the Solara module builds its import-time model and assembles
    the page without disk I/O — a cheap guard against the KNOWN_ISSUES class
    of breakage (eager disk writes / hardcoded model.grid)."""
    import synthitaly.viz as viz

    assert viz.page is not None
    assert callable(viz.AccountInspectorPanel)
    assert isinstance(viz.model, ItalyModel)


# ---------------------------------------------------------------------------
# Behavioural-economics layer: payday spike, overdraft fee, late payment.
# ---------------------------------------------------------------------------


def test_payday_spike_shifts_spending_after_payday():
    """Olafsson & Pagel (2018): discretionary spending bunches in the days
    right after payday. So more purchases land in the first half of the pay
    cycle than the second."""
    model = ItalyModel(n_consumers=150, n_merchants_per_category=2, n_days=120, seed=21)
    model.run()
    early = late = 0
    for t in model.transactions:
        if t["kind"] != "purchase":
            continue
        d = date.fromisoformat(t["date"])
        last, nxt = numbers._payday_cycle_bounds(d)
        cycle_len = (nxt - last).days
        if (d - last).days < cycle_len / 2:
            early += 1
        else:
            late += 1
    assert early > late


def test_payday_spike_does_not_inflate_monthly_spend():
    """The pay-cycle multiplier is mean-neutral, so switching the spike on
    (PEAK=1.5) does not raise total discretionary spend versus off (PEAK=1.0).
    It only re-times it (saturation at one purchase/day can even shave a little
    off, never inflate)."""
    def total_purchase_eur(peak: float) -> float:
        original = numbers.PAYDAY_SPIKE_PEAK
        numbers.PAYDAY_SPIKE_PEAK = peak
        try:
            m = ItalyModel(n_consumers=150, n_merchants_per_category=2, n_days=120, seed=33)
            m.run()
            return sum(t["amount_eur"] for t in m.transactions if t["kind"] == "purchase")
        finally:
            numbers.PAYDAY_SPIKE_PEAK = original

    flat = total_purchase_eur(1.0)   # spike off
    spiked = total_purchase_eur(1.5)  # spike on
    assert spiked <= flat * 1.10  # no inflation beyond RNG noise


def test_overdraft_fee_charged_on_crossing_zero():
    """A payment that takes the balance from non-negative to negative incurs
    one flat overdraft fee; a further payment while already negative does not."""
    model = ItalyModel(n_consumers=5, n_merchants_per_category=1, n_days=1, seed=1)
    c = model.consumers[0]
    acct = c.accounts.current               # reset to a clean €50 account
    acct.starting_balance = 50.0
    acct._cached_balance = 50.0
    acct.entries.clear()
    c._overdraft_floor = -500.0  # let this consumer overdraw
    merchant = model._pick_merchant("retail", c.macro_area)
    iso = model.today.isoformat()

    c._pay(merchant=merchant, category="retail", amount=80.0, kind="purchase", date_iso=iso)
    fees = [e for e in c.account.entries if e.category == "overdraft_fee"]
    assert len(fees) == 1
    assert abs(fees[0].amount_eur - numbers.OVERDRAFT_FEE_EUR) < 1e-9
    assert abs(c.account.balance - (50.0 - 80.0 - numbers.OVERDRAFT_FEE_EUR)) < 1e-9

    # Already negative — a second debit must not add another overdraft fee.
    c._pay(merchant=merchant, category="retail", amount=5.0, kind="purchase", date_iso=iso)
    assert len([e for e in c.account.entries if e.category == "overdraft_fee"]) == 1
    assert _reconciles(c.account)


def test_overdraft_fees_emergent_and_standin_credit_only():
    """Over a multi-month run some debt-holders overdraw and pay fees; the fee
    only ever hits overdraft-allowed consumers, and the stand-in is credit-only."""
    model = ItalyModel(n_consumers=300, n_merchants_per_category=3, n_days=120, seed=42)
    model.run()
    fees = [t for t in model.transactions if t["category"] == "overdraft_fee"]
    assert len(fees) >= 1
    assert all(t["kind"] == "fee" for t in fees)
    fee_payers = {t["from"] for t in fees}
    for c in model.consumers:
        if str(c.unique_id) in fee_payers:
            assert c.overdraft_allowed and c.has_debt
    for area in ("NORTH", "CENTRE", "SOUTH"):
        m = model._bill_merchant("overdraft_fee", area)
        for e in m.account.entries:
            assert e.direction == "in"
        assert _reconciles(m.account)


def test_unaffordable_bill_is_deferred_then_paid_late():
    """A bill the account can't cover is carried, not skipped, and is settled
    with a late fee once money arrives (Dahan & Nisan 2020)."""
    model = ItalyModel(n_consumers=5, n_merchants_per_category=1, n_days=1, seed=1)
    c = model.consumers[0]
    acct = c.accounts.current               # reset to a clean €10 account
    acct.starting_balance = 10.0
    acct._cached_balance = 10.0
    acct.entries.clear()
    c._overdraft_floor = 0.0       # no overdraft room
    c.has_debt = False
    c.bills_subscribed = {
        "utilities": {"share": 1.0, "mean_eur": 100.0, "day": model.today.day}
    }

    c._pay_due_bills(model.today)
    assert len(c._overdue_bills) == 1   # deferred, not paid
    assert c.account.balance == 10.0    # nothing left the account

    # Money arrives; settle a few days later.
    c.accounts.current.credit(
        counterparty="payroll", category="salary", amount=1000.0,
        date_iso=model.today.isoformat(),
    )
    c._settle_overdue_bills(model.today + timedelta(days=3))
    assert c._overdue_bills == []
    late = [e for e in c.account.entries if e.category == "late_payment_fee"]
    assert len(late) == 1
    assert abs(late[0].amount_eur - 100.0 * numbers.LATE_PAYMENT_FEE_FRACTION) < 1e-9
    # Principal + late fee both left the account.
    assert abs(c.account.balance - (1010.0 - 100.0 - 100.0 * numbers.LATE_PAYMENT_FEE_FRACTION)) < 1e-9
    assert _reconciles(c.account)


def test_late_payment_fees_emergent_and_accounts_reconcile():
    """Over a long run some consumers pay bills late; late fees are logged as
    'fee' transactions and every current account still reconciles."""
    model = ItalyModel(n_consumers=400, n_merchants_per_category=3, n_days=150, seed=42)
    model.run()
    late = [t for t in model.transactions if t["category"] == "late_payment_fee"]
    assert len(late) >= 1
    assert all(t["kind"] == "fee" for t in late)
    for c in model.consumers:
        assert _reconciles(c.account)


# ---------------------------------------------------------------------------
# Income-source heterogeneity: payroll / self-employed / pension / transfers.
# ---------------------------------------------------------------------------


def test_every_consumer_has_a_valid_income_source():
    model = ItalyModel(n_consumers=300, n_merchants_per_category=2, n_days=1, seed=9)
    valid = set(numbers.INCOME_SOURCE_SHARE)
    sources = {c.income_source for c in model.consumers}
    for c in model.consumers:
        assert c.income_source in valid
    # At n=300 every source (incl. the rare 3% transfers) should appear.
    assert sources == valid


def test_payroll_income_exceeds_pension_income_on_average():
    """The SHIW relative-income ordering survives into realised incomes."""
    model = ItalyModel(n_consumers=400, n_merchants_per_category=2, n_days=1, seed=9)
    payroll = [c.monthly_income for c in model.consumers if c.income_source == "payroll"]
    pension = [c.monthly_income for c in model.consumers if c.income_source == "pension"]
    assert payroll and pension
    assert sum(payroll) / len(payroll) > sum(pension) / len(pension)


def test_income_credits_carry_the_source_category():
    """Income credits are logged kind='salary' with a per-source category."""
    model = ItalyModel(n_consumers=300, n_merchants_per_category=2, n_days=30, seed=9)
    model.run()
    income_cats = {t["category"] for t in model.transactions if t["kind"] == "salary"}
    # At least the common sources appear as categories.
    assert {"salary", "pension"} <= income_cats


def test_december_thirteenth_month_bonus():
    """December total income exceeds a normal month's (tredicesima for payroll
    and pension)."""
    model = ItalyModel(n_consumers=150, n_merchants_per_category=2, n_days=365, seed=8)
    model.run()
    by_month: dict[int, float] = {}
    for t in model.transactions:
        if t["kind"] == "salary":
            mo = date.fromisoformat(t["date"]).month
            by_month[mo] = by_month.get(mo, 0.0) + t["amount_eur"]
    assert by_month[12] > by_month[11] * 1.10  # clear December bump


# ---------------------------------------------------------------------------
# Debtor subtypes: explicit debt stock + climber / chronic / subsister.
# ---------------------------------------------------------------------------


def test_debtor_subtypes_partition_the_debtors():
    """Before any time passes, the consumers carrying a subtype are exactly the
    consumers flagged with debt (subtypes partition the SHIW debtor roll), and
    each debtor opens with a positive principal."""
    model = ItalyModel(n_consumers=300, n_merchants_per_category=2, n_days=1, seed=13)
    subtyped = {c for c in model.consumers if c.debtor_subtype is not None}
    indebted = {c for c in model.consumers if c.has_debt}
    assert subtyped == indebted
    assert subtyped  # the roll produced some debtors at this size
    for c in subtyped:
        assert c.debtor_subtype in numbers.DEBTOR_SUBTYPES
        assert c.debt_balance > 0.0
    # Non-debtors carry no subtype and no principal.
    for c in model.consumers:
        if not c.has_debt:
            assert c.debtor_subtype is None and c.debt_balance == 0.0


def test_debt_balance_never_negative():
    model = ItalyModel(n_consumers=300, n_merchants_per_category=2, n_days=400, seed=42)
    model.run()
    for c in model.consumers:
        assert c.debt_balance >= -1e-9


def test_debtor_trajectories_diverge_by_subtype():
    """Over a long horizon the three archetypes behave as intended:
    climbers pay their principal down and some leave debt; chronic debtors
    never leave and keep a positive principal; subsisters keep their current
    account near zero (much lower than the other two)."""
    import statistics

    model = ItalyModel(n_consumers=400, n_merchants_per_category=3, n_days=720, seed=42)
    model.run()
    deb = [c for c in model.consumers if c.debtor_subtype is not None]
    by = {st: [c for c in deb if c.debtor_subtype == st] for st in numbers.DEBTOR_SUBTYPES}
    for st in numbers.DEBTOR_SUBTYPES:
        assert by[st], f"no {st} debtors at this size/seed"

    # Climbers dig out: at least one has cleared its debt entirely, and a
    # cleared climber has its overdraft permission withdrawn but keeps its
    # subtype label.
    cleared = [c for c in by["climber"] if not c.has_debt]
    assert cleared
    for c in cleared:
        assert c.debt_balance == 0.0
        assert not c.overdraft_allowed and c._overdraft_floor == 0.0
        assert c.debtor_subtype == "climber"

    # Chronic debtors never leave and keep a substantial principal.
    assert all(c.has_debt and c.debt_balance > 0.0 for c in by["chronic"])

    # Everyday (current-account) balances separate the three archetypes:
    #   • climbers rebuild a buffer once they dig out — the highest balance;
    #   • subsisters hug zero (sweep surplus out, borrow to cover shortfalls);
    #   • chronic concentrate among the SHIW financially-vulnerable and run a
    #     standing overdraft — they are the only subtype that goes negative.
    med = {st: statistics.median([c.account.balance for c in by[st]]) for st in by}
    assert med["climber"] > med["subsister"]
    assert med["climber"] > med["chronic"]
    assert abs(med["subsister"]) < med["climber"]  # subsister hugs zero

    # Distress is asserted on the overdraft, not on the median. The chronic
    # median is bimodal — a standing overdraft lets some chronic debtors sit
    # deep in the red while others hold a positive buffer — so on ~16 agents it
    # swings either side of zero from seed to seed and says little. What is
    # stable, and is the actual mechanism, is that chronic debtors are the only
    # ones who can overdraw at all, and that some of them do.
    #
    # (This replaced a `med["chronic"] < med["subsister"]` assertion. That held
    # while subsisters hugged zero *from above*; once the macro-area income
    # gradient landed, enough subsisters borrow to exactly zero that their
    # median is 0.00 and the comparison became a coin-flip on the chronic side.)
    below = {st: sum(c.account.balance < 0 for c in by[st]) for st in by}
    assert below["chronic"] > 0, "chronic debtors should be using their overdraft"
    assert below["climber"] == 0 and below["subsister"] == 0, (
        f"only chronic debtors hold an overdraft, but got {below}"
    )
    assert all(c.overdraft_allowed for c in by["chronic"])


def test_subsisters_borrow_and_credit_line_is_payout_only():
    """Subsisters draw on the credit line (logged kind='loan'); the credit_line
    stand-in only ever pays money out, and money stays conserved (every
    consumer current account reconciles)."""
    model = ItalyModel(n_consumers=400, n_merchants_per_category=3, n_days=720, seed=42)
    model.run()
    loans = [t for t in model.transactions if t["kind"] == "loan"]
    assert loans
    assert all(t["category"] == "credit_draw" for t in loans)
    # Only subsisters borrow.
    borrowers = {t["to"] for t in loans}
    for c in model.consumers:
        if str(c.unique_id) in borrowers:
            assert c.debtor_subtype == "subsister"
    # The credit-line stand-in only pays out (debits itself).
    for area in ("NORTH", "CENTRE", "SOUTH"):
        m = model._bill_merchant("credit_line", area)
        for e in m.account.entries:
            assert e.direction == "out"
        assert _reconciles(m.account)
    for c in model.consumers:
        assert _reconciles(c.account)


def test_visual_graph_includes_income_sources():
    model = ItalyModel(n_consumers=30, n_merchants_per_category=2, n_days=1, seed=4)
    income_nodes = [
        n for n, d in model.graph.nodes(data=True)
        if d.get("kind") == "income_source"
    ]
    assert len(income_nodes) == 3
    # Each income node should have at least one edge to a consumer.
    for n in income_nodes:
        assert model.graph.degree(n) >= 1
