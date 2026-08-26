"""
model.py — the simulation, end to end, in one readable file.

THE BANK-EYE VIEW
-----------------
Picture you are a bank looking at your consumer customers' accounts.
Every day:
  - Some customers get paid (salary credited).
  - Some customers pay scheduled bills (utilities, rent, mortgage, telecom).
  - Some customers spend money at merchants (groceries, restaurants, ...).
What this simulation produces is the list of transactions that bank would see.

THE BUILDING BLOCKS (Mesa 3.x agents)
-------------------------------------
- Consumer       — a household member with a bank account, a macro-area
                   (NORTH/CENTRE/SOUTH), and a monthly income.
- Merchant       — a shop or service provider, sits in one category and one
                   macro-area, receives payments into its own account.
- IncomeSource   — a passive "employer" — once a month it pays every consumer
                   it serves (debits its own account, credits theirs).

Every agent owns a ``BankAccount`` (see below) so the bookkeeping is visible:
you can ask any consumer for ``c.account.entries`` and see their statement.

The model runs day-by-day. The "calendar" is just a Python date that ticks
forward in ``ItalyModel.step()``.

ALL EMPIRICAL NUMBERS LIVE IN ``numbers.py`` — this file does not hard-code
constants. If you want to change Italy's payday or the share of restaurant
spending, edit ``numbers.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import mesa
import networkx as nx
import numpy as np

from . import numbers

# ============================================================================
# BANK ACCOUNT — the smallest piece of bookkeeping
# ============================================================================


@dataclass
class BankEntry:
    """A single line on a bank statement."""

    date: str           # ISO date string e.g. "2017-01-27"
    direction: str      # "in" or "out"
    counterparty: str   # who the money came from / went to (their unique_id)
    category: str       # "salary" | "utilities" | "retail" | ...
    amount_eur: float


@dataclass
class BankAccount:
    """A bank account. Owns a list of statement entries and a balance.

    The balance is updated on every debit/credit so reading it is O(1),
    while the entry list is the audit trail (and what you'd put in a CSV).
    """

    owner_id: str
    starting_balance: float
    entries: list[BankEntry] = field(default_factory=list)
    _cached_balance: float = field(init=False)

    def __post_init__(self) -> None:
        self._cached_balance = float(self.starting_balance)

    @property
    def balance(self) -> float:
        return self._cached_balance

    def debit(self, *, counterparty: str, category: str, amount: float, date_iso: str) -> None:
        """Money leaves the account."""
        self.entries.append(BankEntry(date_iso, "out", counterparty, category, amount))
        self._cached_balance -= amount

    def credit(self, *, counterparty: str, category: str, amount: float, date_iso: str) -> None:
        """Money arrives at the account."""
        self.entries.append(BankEntry(date_iso, "in", counterparty, category, amount))
        self._cached_balance += amount


@dataclass
class AccountSet:
    """The three accounts a consumer holds.

    ``current`` is the everyday account: salary in, bills / debt service /
    purchases out. ``savings`` and ``pension`` only ever receive the monthly
    residual sweep (an *internal* transfer out of ``current``), so money is
    moved between a consumer's own accounts, never created or destroyed.
    """

    current: BankAccount
    savings: BankAccount
    pension: BankAccount

    def as_dict(self) -> dict[str, BankAccount]:
        return {"current": self.current, "savings": self.savings, "pension": self.pension}


# ============================================================================
# AGENT 1 — Merchant
# ============================================================================


class Merchant(mesa.Agent):
    """A shop in one category and one macro-area. Receives spending from
    consumers into its own bank account; does nothing on its own."""

    def __init__(self, model: mesa.Model, category: str, macro_area: str):
        super().__init__(model)
        self.category = category
        self.macro_area = macro_area
        self.account = BankAccount(owner_id=str(self.unique_id), starting_balance=0.0)

    def step(self) -> None:
        """Merchants are passive — they just sit there."""
        return


# ============================================================================
# AGENT 2 — IncomeSource
# ============================================================================


class IncomeSource(mesa.Agent):
    """One symbolic employer per macro-area. Once a month, on payday, it
    credits every consumer it serves with that consumer's monthly income.

    The income source has its own account too. We start it at zero and let
    it go negative as it pays out — useful for sanity-checking the books
    (total paid out should equal the sum of consumer salary credits)."""

    def __init__(self, model: mesa.Model, macro_area: str):
        super().__init__(model)
        self.macro_area = macro_area
        self.served_consumers: list[Consumer] = []
        # The income-source's "wallet" — we don't model where its money
        # actually comes from. The balance running negative just reflects
        # cumulative salaries paid out.
        self.account = BankAccount(
            owner_id=f"income_{macro_area}",
            starting_balance=0.0,
        )

    def attach(self, consumer: Consumer) -> None:
        self.served_consumers.append(consumer)

    def step(self) -> None:
        """If today is payday, credit every consumer's income.

        Each consumer is paid according to their income source (payroll /
        pension / self-employed / transfers / unemployed), with a December
        thirteenth-month bonus for payroll & pension (tredicesima). Every credit
        is ``kind="salary"`` (a scheduled income credit); the *category* carries
        the source.

        Each consumer has exactly one income stream. A secondary property-income
        credit used to be paid here to a flat 10% of consumers; it was removed
        because no source in the literature set gives either its incidence or
        its size — see the note in ``numbers.py``.
        """
        if not numbers.is_payday(self.model.today):
            return
        date_iso = self.model.today.isoformat()
        my_id = f"income_{self.macro_area}"
        today = self.model.today
        for c in self.served_consumers:
            category = numbers.INCOME_SOURCE_CATEGORY[c.income_source]
            amount = c.monthly_income * numbers.income_calendar_multiplier(
                today, c.income_source
            )
            self._credit_income(c, amount=amount, category=category, my_id=my_id, date_iso=date_iso)

    def _credit_income(
        self, c: Consumer, *, amount: float, category: str, my_id: str, date_iso: str
    ) -> None:
        """Pay one income credit to consumer ``c`` (paired debit/credit, logged)."""
        if amount <= 0:
            return
        self.account.debit(
            counterparty=str(c.unique_id), category=category, amount=amount, date_iso=date_iso
        )
        c.account.credit(
            counterparty=my_id, category=category, amount=amount, date_iso=date_iso
        )
        c._m_income += amount
        self.model._log_txn(
            kind="salary",
            from_party=my_id,
            to_party=c.unique_id,
            category=category,
            amount=amount,
            macro_area=self.macro_area,
        )


# ============================================================================
# AGENT 3 — Consumer
# ============================================================================


class Consumer(mesa.Agent):
    """A person with a bank account. Each simulated day they may:
      1. Pay a recurring bill (utilities/rent/telecom/mortgage on its due day).
      2. Make a discretionary purchase at a merchant (probability driven by
         the day's intensity multiplier from ``numbers.daily_intensity``).
    """

    def __init__(
        self,
        model: mesa.Model,
        macro_area: str,
        monthly_income: float,
        starting_balance: float,
        bills_subscribed: dict[str, dict],
        income_source: str = "payroll",
    ):
        super().__init__(model)
        self.macro_area = macro_area
        self.monthly_income = monthly_income
        # Primary income source (payroll / self_employed / pension / transfers),
        # drawn from INCOME_SOURCE_SHARE; ``monthly_income`` is already scaled by
        # the mean-preserving income_source_multiplier for this source. NOTE:
        # this "pension" is an income *source* (a pensioner being paid) and is
        # unrelated to the ``pension`` savings *account* / ``is_pension_saver``
        # below (a tagged destination for the monthly residual sweep). A
        # consumer can be both a pensioner and a pension-saver.
        self.income_source = income_source
        uid = str(self.unique_id)
        self.accounts = AccountSet(
            current=BankAccount(owner_id=uid, starting_balance=starting_balance),
            savings=BankAccount(owner_id=f"{uid}_savings", starting_balance=0.0),
            pension=BankAccount(owner_id=f"{uid}_pension", starting_balance=0.0),
        )
        # which bills this consumer is liable for (a subset of BILL_TYPES)
        self.bills_subscribed = bills_subscribed
        # Income bands — filled in by ItalyModel once every consumer's income
        # has been drawn (they are empirical percentiles of the realised
        # population, not a per-agent constant). 1..4 / 1..5.
        self.income_quartile: int | None = None
        self.income_quintile: int | None = None
        # Income LEVEL — "low" / "middle" / "high" from the absolute euro bands of
        # the Bank of Italy Payment Behaviour Survey (numbers.income_level). Unlike
        # the empirical quartile/quintile bands above, these are fixed euro
        # cut-points. Filled in by ItalyModel._assign_income_bands.
        self.income_level: str | None = None
        # Debt — filled in by ItalyModel once income bands exist. A consumer
        # who holds debt pays a monthly debt-service line and is allowed to
        # overdraw their account (see _overdraft_floor, Increment 3).
        self.has_debt: bool = False
        self.overdraft_allowed: bool = False
        self._monthly_debt_service: float = 0.0
        # Debtor archetype (None for non-debtors). Set by ItalyModel._assign_debt
        # to one of numbers.DEBTOR_SUBTYPES. Governs the monthly repayment /
        # borrowing rule in _service_debt — and hence the balance trajectory:
        # climber digs out, chronic stays in debt, subsister ekes out near zero.
        self.debtor_subtype: str | None = None
        # SHIW 2022 §3 financial-vulnerability flag, set by _assign_debt for
        # debt-holders: equivalized income below median (income_quartile <= 2) AND
        # debt-service ratio > 30%. ``debt_service_ratio`` is the monthly scheduled
        # service over monthly income. Both drive the chronic-archetype tilt and
        # the chronic-debtor analysis panel.
        self.debt_service_ratio: float = 0.0
        self.is_financially_vulnerable: bool = False
        # Outstanding debt principal (a *stock*). SHIW gives only the service
        # *flow*; the opening stock and its monthly interest are modelling
        # choices (numbers.opening_debt_principal / DEBT_MONTHLY_INTEREST_RATE).
        self.debt_balance: float = 0.0
        # Outstanding principal after each monthly debt-service event, in order.
        # Appended by _service_debt so the Solara inspector can draw a real
        # debt-balance sparkline; ends at 0.0 on the month a debtor digs out.
        self._debt_history: list[float] = []
        # Lowest balance this consumer may reach. 0.0 = the original
        # "never overdraw, skip if you can't afford it" rule; a negative
        # value (debt-holders only) lets them go into the red. No paper
        # gives an overdraft limit — its size is a modelling choice tied to
        # the consumer's own SHIW debt-service burden.
        self._overdraft_floor: float = 0.0
        # Savings / pension — filled in by ItalyModel from the SHIW saving
        # probability for this consumer's income quintile. A saver sweeps the
        # month's positive residual; a pension-saver tags that sweep
        # "pension" instead of "savings".
        self.is_saver: bool = False
        self.is_pension_saver: bool = False
        # Running monthly cash-flow accumulators, reset at each month close.
        self._m_income: float = 0.0
        self._m_bills: float = 0.0
        self._m_debt: float = 0.0
        self._m_disc: float = 0.0
        # Bills that fell due while the account couldn't cover them. The old
        # prototype silently skipped these; instead we carry them here and
        # retry, settling with a late fee once cash is available (Dahan &
        # Nisan 2020). Each item: {"bill_name", "amount", "due_iso"}.
        self._overdue_bills: list[dict] = []
        # Month-end credit-file snapshot, one row per closed month, appended by
        # ``_month_close``. This is pure observation — it draws no random number
        # and changes no branch, so a seeded run is bit-identical with or
        # without it. Consumed by ``synthitaly.panel`` to build the
        # consumer x month frame the rolling-window papers need (Khandani, Kim
        # & Lo 2010; Butaru et al. 2015), which report monthly/quarterly
        # snapshots exactly as a credit file does.
        self.dpd_history: list[dict] = []
        # Within-month delinquency counters, reset with the cash-flow ones.
        self._m_late_fee_n: int = 0
        self._m_late_fee_eur: float = 0.0
        self._m_writeoff_n: int = 0
        self._m_writeoff_eur: float = 0.0

    # -- the everyday account (kept as ``.account`` for back-compat) ---------

    @property
    def account(self) -> BankAccount:
        """The current account. Existing code and tests use ``c.account``;
        it now points at ``c.accounts.current``."""
        return self.accounts.current

    # -- affordability ------------------------------------------------------

    def _can_afford(self, amount: float) -> bool:
        """A payment is allowed if it would not push the balance below this
        consumer's overdraft floor. A payment that moves the balance from
        non-negative to negative also incurs a flat overdraft fee (Stango &
        Zinman 2014), so we reserve room for that fee too — this keeps the floor
        a hard limit *including* fees. With the default floor of 0.0 the balance
        can never cross zero, so the fee never applies and this is exactly the
        old ``balance >= amount`` rule."""
        projected = self.account.balance - amount
        if self.account.balance >= 0 and projected < 0:
            projected -= numbers.OVERDRAFT_FEE_EUR
        return projected >= self._overdraft_floor

    # -- making a payment (with overdraft fee) ------------------------------

    def _pay(
        self, *, merchant: Merchant, category: str, amount: float, kind: str, date_iso: str
    ) -> None:
        """Move ``amount`` from this consumer's current account to ``merchant``
        as a paired debit/credit (money is conserved), log the transaction, and
        — if the debit pushed the balance from non-negative to negative — charge
        a flat overdraft fee. Callers must have checked ``_can_afford`` first."""
        balance_before = self.account.balance
        self.account.debit(
            counterparty=str(merchant.unique_id),
            category=category,
            amount=amount,
            date_iso=date_iso,
        )
        merchant.account.credit(
            counterparty=str(self.unique_id),
            category=category,
            amount=amount,
            date_iso=date_iso,
        )
        self.model._log_txn(
            kind=kind,
            from_party=self.unique_id,
            to_party=merchant.unique_id,
            category=category,
            amount=amount,
            macro_area=self.macro_area,
        )
        if balance_before >= 0 and self.account.balance < 0:
            self._charge_overdraft_fee(date_iso)

    def _charge_overdraft_fee(self, date_iso: str) -> None:
        """Debit the flat overdraft fee to the per-area overdraft-fee stand-in
        (Stango & Zinman 2014). Called only when a payment has just taken the
        balance negative; ``_can_afford`` has already reserved room for it, so
        the floor still holds afterwards."""
        fee = numbers.OVERDRAFT_FEE_EUR
        if fee <= 0:
            return
        stand_in = self.model._bill_merchant("overdraft_fee", self.macro_area)
        self.account.debit(
            counterparty=str(stand_in.unique_id),
            category="overdraft_fee",
            amount=fee,
            date_iso=date_iso,
        )
        stand_in.account.credit(
            counterparty=str(self.unique_id),
            category="overdraft_fee",
            amount=fee,
            date_iso=date_iso,
        )
        self.model._log_txn(
            kind="fee",
            from_party=self.unique_id,
            to_party=stand_in.unique_id,
            category="overdraft_fee",
            amount=fee,
            macro_area=self.macro_area,
        )

    # -- daily routine ------------------------------------------------------

    def step(self) -> None:
        today = self.model.today
        # Close the previous month on the 1st (never on the very first
        # simulated day, which has no month behind it). Done *before* bills
        # so a day-1 bill like rent counts toward the new month.
        if today.day == 1 and today != self.model.start_date:
            self._month_close(today)
        # Clear any carried-over bills first (today's salary, if it is payday,
        # is already credited because IncomeSource runs before Consumer).
        self._settle_overdue_bills(today)
        self._pay_due_bills(today)
        self._service_debt(today)
        self._maybe_buy_from_merchant(today)

    # -- monthly residual sweep --------------------------------------------

    def _month_close(self, today: date) -> None:
        """Sweep the month's positive residual into savings (or pension).

        The residual is emergent — income minus bills, debt service and
        discretionary spend over the month just ended. No savings *rate* is
        assumed; savers simply keep what is left. The sweep is an internal
        paired debit/credit so total money across the consumer's accounts is
        unchanged. Capped at the current balance so neither account goes
        negative from the sweep itself.
        """
        residual = self._m_income - self._m_bills - self._m_debt - self._m_disc
        if self.is_saver and residual > 0:
            amount = min(residual, self.account.balance)
            if amount > 0:
                tag = "pension_sweep" if self.is_pension_saver else "savings_sweep"
                target = (
                    self.accounts.pension
                    if self.is_pension_saver
                    else self.accounts.savings
                )
                date_iso = today.isoformat()
                self.account.debit(
                    counterparty=target.owner_id,
                    category=tag,
                    amount=amount,
                    date_iso=date_iso,
                )
                target.credit(
                    counterparty=self.account.owner_id,
                    category=tag,
                    amount=amount,
                    date_iso=date_iso,
                )
        self._record_month_end(today)
        # Start the new month's accounting from zero regardless of outcome.
        self._m_income = 0.0
        self._m_bills = 0.0
        self._m_debt = 0.0
        self._m_disc = 0.0
        self._m_late_fee_n = 0
        self._m_late_fee_eur = 0.0
        self._m_writeoff_n = 0
        self._m_writeoff_eur = 0.0

    # -- month-end credit-file snapshot -------------------------------------

    def _record_month_end(self, today: date) -> None:
        """Append one row to ``dpd_history`` for the month that just closed.

        ``_month_close`` fires on the 1st, so the month being closed ends the
        day before; days-past-due are measured against that statement date
        rather than against ``today``.

        Days-past-due is bucketed the way a credit file reports it — current /
        30 / 60 / 90 — which is the same stratification Khandani, Kim & Lo
        (2010) use to colour their Fig. 13. ``writeoff_n`` counts bills that
        crossed ``numbers.WRITE_OFF_DAYS_PAST_DUE``, and is the event the
        90-days-or-more delinquency label is built from.

        Purely observational: no RNG draw, no branch change, so a seeded run
        stays bit-identical.
        """
        as_of = today - timedelta(days=1)
        dpd = [(as_of - date.fromisoformat(od["due_iso"])).days for od in self._overdue_bills]
        max_dpd = max(dpd) if dpd else 0
        if max_dpd >= 90:
            bucket = 90
        elif max_dpd >= 60:
            bucket = 60
        elif max_dpd >= 30:
            bucket = 30
        else:
            bucket = 0
        self.dpd_history.append({
            "consumer_id": self.unique_id,
            "month": as_of.strftime("%Y-%m"),
            "as_of": as_of.isoformat(),
            # delinquency state
            "max_dpd": max_dpd,
            "dpd_bucket": bucket,
            "n_overdue": len(self._overdue_bills),
            "overdue_eur": round(sum(float(od["amount"]) for od in self._overdue_bills), 2),
            "late_fee_n": self._m_late_fee_n,
            "late_fee_eur": round(self._m_late_fee_eur, 2),
            "writeoff_n": self._m_writeoff_n,
            "writeoff_eur": round(self._m_writeoff_eur, 2),
            # the month's cash flow, already accumulated for the sweep
            "income_eur": round(self._m_income, 2),
            "bills_eur": round(self._m_bills, 2),
            "debt_service_eur": round(self._m_debt, 2),
            "discretionary_eur": round(self._m_disc, 2),
            # balances as of the statement date
            "cur_balance": round(self.accounts.current.balance, 2),
            "savings_balance": round(self.accounts.savings.balance, 2),
            "pension_balance": round(self.accounts.pension.balance, 2),
            "debt_balance": round(self.debt_balance, 2),
            "has_debt": bool(self.has_debt),
        })

    # -- recurring bills ----------------------------------------------------

    def _pay_due_bills(self, today: date) -> None:
        """If a bill's day-of-month equals today, pay it. A bill the account
        can't cover is *not* skipped — it is carried as overdue and later
        settled with a late fee (see ``_settle_overdue_bills``)."""
        date_iso = today.isoformat()
        for bill_name, spec in self.bills_subscribed.items():
            if today.day != spec["day"]:
                continue
            amount = float(spec["mean_eur"])
            # If the account can't cover the bill, subsisters draw on a credit
            # line to close the gap (so the current account hugs zero); everyone
            # else defers it — the due-date/payday mismatch of Dahan & Nisan 2020.
            if not self._can_afford(amount) and not self._try_borrow_to_afford(amount, today):
                self._overdue_bills.append(
                    {"bill_name": bill_name, "amount": amount, "due_iso": date_iso}
                )
                continue
            merchant = self.model._bill_merchant(bill_name, self.macro_area)
            self._pay(
                merchant=merchant, category=bill_name, amount=amount,
                kind="bill", date_iso=date_iso,
            )
            self._m_bills += amount

    # -- overdue bills (late payment) ---------------------------------------

    def _settle_overdue_bills(self, today: date) -> None:
        """Retry any carried-over bills. When the account can cover the bill
        *plus* a late fee, pay both to the original biller (Dahan & Nisan 2020).
        A bill still unaffordable after ``numbers.WRITE_OFF_DAYS_PAST_DUE`` is
        dropped (service cut / write-off) so the queue can't grow without
        bound. That drop is counted, because crossing 90 days past due is the
        delinquency event the credit-risk literature forecasts."""
        if not self._overdue_bills:
            return
        date_iso = today.isoformat()
        still: list[dict] = []
        for od in self._overdue_bills:
            principal = float(od["amount"])
            fee = principal * numbers.LATE_PAYMENT_FEE_FRACTION
            if self._can_afford(principal + fee):
                merchant = self.model._bill_merchant(od["bill_name"], self.macro_area)
                self._pay(
                    merchant=merchant, category=od["bill_name"], amount=principal,
                    kind="bill", date_iso=date_iso,
                )
                self._m_bills += principal
                if fee > 0:
                    self._pay(
                        merchant=merchant, category="late_payment_fee", amount=fee,
                        kind="fee", date_iso=date_iso,
                    )
                    self._m_bills += fee
                    self._m_late_fee_n += 1
                    self._m_late_fee_eur += fee
            else:
                due = date.fromisoformat(od["due_iso"])
                if (today - due).days <= numbers.WRITE_OFF_DAYS_PAST_DUE:
                    still.append(od)  # keep retrying; otherwise write it off
                else:
                    # Past the write-off horizon: the bill is dropped. Counting
                    # it here is what makes "90 days or more past due" — the
                    # target variable of Khandani, Kim & Lo (2010) and Butaru
                    # et al. (2015) — observable in this model.
                    self._m_writeoff_n += 1
                    self._m_writeoff_eur += principal
        self._overdue_bills = still

    # -- monthly debt service (debt as a stock) -----------------------------

    def _service_debt(self, today: date) -> None:
        """Once a month, accrue interest on the debt principal and make the
        archetype's repayment. The repayment rule is what makes the three
        trajectories diverge:
          • climber   — pays the full scheduled service, so the principal falls;
                        when it reaches zero the consumer *leaves debt for good*.
          • chronic   — pays interest only, so the principal stays flat.
          • subsister — pays a token amount (and borrows elsewhere to get by),
                        so the principal drifts up slowly.

        Interest accrues even in a month the consumer cannot afford to pay, so
        skipped payments make the debt grow — the realistic direction.
        """
        if not self.has_debt or today.day != numbers.DEBT_SERVICE_DAY_OF_MONTH:
            return
        date_iso = today.isoformat()
        # 1. Interest accrues on the outstanding principal.
        interest = self.debt_balance * numbers.DEBT_MONTHLY_INTEREST_RATE
        self.debt_balance += interest
        # 2. The scheduled repayment depends on the archetype.
        if self.debtor_subtype == "chronic":
            scheduled = interest  # interest-only keeps the principal flat
        elif self.debtor_subtype == "subsister":
            scheduled = self._monthly_debt_service * numbers.SUBSISTER_REPAYMENT_MULT
        else:  # climber (and any plain debtor) repays the full SHIW service
            scheduled = self._monthly_debt_service * numbers.CLIMBER_REPAYMENT_MULT
        scheduled = min(scheduled, self.debt_balance)  # never overpay the principal
        # 3. Pay what we can afford to the per-area debt-service stand-in.
        if scheduled > 0 and self._can_afford(scheduled):
            merchant = self.model._bill_merchant("debt_service", self.macro_area)
            self._pay(
                merchant=merchant, category="debt_service", amount=scheduled,
                kind="bill", date_iso=date_iso,
            )
            self._m_debt += scheduled
            self.debt_balance -= scheduled
        # 4. Dig-out: a debtor whose principal reaches zero exits debt for good
        #    (flag cleared, overdraft permission withdrawn). The subtype *label*
        #    is kept so the output can still show "a climber who made it out".
        if self.debt_balance <= 1e-6:
            self.debt_balance = 0.0
            self.has_debt = False
            self.overdraft_allowed = False
            self._overdraft_floor = 0.0
        # 5. Record the post-service principal so the UI can plot the
        #    trajectory; the final entry is the 0.0 left by a dig-out.
        self._debt_history.append(self.debt_balance)

    # -- borrowing (credit line) --------------------------------------------

    def _borrow(self, amount: float, today: date) -> float:
        """Draw new credit: the per-area ``credit_line`` stand-in pays cash into
        this consumer's current account and the debt principal grows by the same
        amount (money is conserved — a paired credit/debit). Bounded by a ceiling
        on the principal so the credit line cannot grow without limit. Returns
        the amount actually drawn."""
        if amount <= 0:
            return 0.0
        ceiling = numbers.SUBSISTER_DEBT_CEILING_MULT * numbers.opening_debt_principal(
            self._monthly_debt_service
        )
        draw = min(amount, max(0.0, ceiling - self.debt_balance))
        if draw <= 0:
            return 0.0
        date_iso = today.isoformat()
        lender = self.model._bill_merchant("credit_line", self.macro_area)
        lender.account.debit(
            counterparty=str(self.unique_id), category="credit_draw",
            amount=draw, date_iso=date_iso,
        )
        self.account.credit(
            counterparty=str(lender.unique_id), category="credit_draw",
            amount=draw, date_iso=date_iso,
        )
        self.debt_balance += draw
        self.model._log_txn(
            kind="loan", from_party=lender.unique_id, to_party=self.unique_id,
            category="credit_draw", amount=draw, macro_area=self.macro_area,
        )
        return draw

    def _try_borrow_to_afford(self, amount: float, today: date) -> bool:
        """Subsisters borrow just enough to make ``amount`` affordable, then
        report whether it now is. Non-subsisters never borrow (return False so
        the caller defers the bill instead)."""
        if self.debtor_subtype != "subsister":
            return False
        need = amount - (self.account.balance - self._overdraft_floor)
        self._borrow(need, today)
        return self._can_afford(amount)

    # -- discretionary spending --------------------------------------------

    def _maybe_buy_from_merchant(self, today: date) -> None:
        """With some probability (scaled by today's intensity), pick a
        category, pick a merchant in our macro-area, draw a ticket size,
        and pay."""
        # Base probability of buying something on a normal Thursday in May.
        # This is a *tuning knob* — pick something that gives roughly
        # 0.5–1 transactions per consumer per day. 0.6 works for a small
        # population over 30 days.
        base_prob = 0.6
        prob = base_prob * numbers.daily_intensity(today)
        if self.model.rng.random() > prob:
            return

        category = numbers.sample_category(self.model.rng)
        amount = numbers.sample_ticket(self.model.rng, category)

        if not self._can_afford(amount):
            return  # past the overdraft floor; skip this purchase

        merchant = self.model._pick_merchant(category, self.macro_area)
        if merchant is None:
            return  # no merchant for this (category, area) — shouldn't happen

        self._pay(
            merchant=merchant, category=category, amount=amount,
            kind="purchase", date_iso=today.isoformat(),
        )
        self._m_disc += amount


# ============================================================================
# THE MODEL
# ============================================================================


class ItalyModel(mesa.Model):
    """Run with ``model = ItalyModel(...); model.run()`` and then read the
    transactions off ``model.transactions`` (a list of dicts).

    Each agent additionally holds a ``BankAccount`` (``agent.account``) — the
    per-agent statement is useful for inspecting individual customers.
    """

    def __init__(
        self,
        n_consumers: int = 200,
        n_merchants_per_category: int = 3,
        start_date: date = date(2017, 1, 1),
        n_days: int = 30,
        seed: int = 42,
    ):
        # Mesa 3.x: ``rng`` is the new keyword; ``seed`` is deprecated but
        # still works. We pass a numpy Generator so ``numbers.sample_*``
        # functions can use it directly.
        super().__init__(rng=np.random.default_rng(seed))

        self.n_consumers = n_consumers
        self.n_merchants_per_category = n_merchants_per_category
        self.start_date = start_date
        self.n_days = n_days
        self.today: date = start_date

        # In-memory transaction log. Each entry is a dict — easy to drop
        # straight into pandas with ``pd.DataFrame(model.transactions)``.
        self.transactions: list[dict] = []

        # ----------------------------------------------------------------
        # 1. MERCHANTS — one pool per (category, macro_area).
        #
        # Why 3 merchants per (category, area)? With 10 categories × 3
        # macro-areas, that's 90 merchants total. The choice is a balance:
        #   - large enough that each consumer can plausibly repeat-visit
        #     several shops without one dominating the category traffic,
        #   - small enough to keep the picture in the network panel
        #     readable and the per-merchant revenue meaningful.
        # If you want a single-shop-per-(category,area) world for clarity,
        # drop the Solara slider to 1.
        # ----------------------------------------------------------------
        self.merchants: dict[tuple[str, str], list[Merchant]] = {}
        for cat in numbers.CATEGORY_SHARES:
            for area in numbers.MACRO_AREA_WEIGHTS:
                pool = [
                    Merchant(self, category=cat, macro_area=area)
                    for _ in range(n_merchants_per_category)
                ]
                self.merchants[(cat, area)] = pool

        # Stand-in merchants for bills (one per (bill_type, area)).
        # Bills always flow to a single utility/landlord/telecom counterparty
        # per area — there's no point in having multiple stand-ins per bill.
        self._bill_merchants: dict[tuple[str, str], Merchant] = {}
        for bill_name in numbers.BILL_TYPES:
            for area in numbers.MACRO_AREA_WEIGHTS:
                self._bill_merchants[(bill_name, area)] = Merchant(
                    self, category=bill_name, macro_area=area
                )
        # Aggregate SHIW debt-service line gets its own stand-in counterparty
        # per area. It is *not* a BILL_TYPE: only debt-flagged consumers pay
        # it, and the amount is the SHIW quartile figure, not a survey mean.
        for area in numbers.MACRO_AREA_WEIGHTS:
            self._bill_merchants[("debt_service", area)] = Merchant(
                self, category="debt_service", macro_area=area
            )
        # Per-area "overdraft_fee" stand-in — the bank's overdraft charge.
        # A flat fee (numbers.OVERDRAFT_FEE_EUR) is debited here the moment a
        # consumer payment pushes the current account below zero (Stango &
        # Zinman 2014). Like debt_service it is a credit-only counterparty.
        for area in numbers.MACRO_AREA_WEIGHTS:
            self._bill_merchants[("overdraft_fee", area)] = Merchant(
                self, category="overdraft_fee", macro_area=area
            )
        # Per-area "credit_line" stand-in — the lender a subsister draws new
        # credit from when it can't cover a bill (logged kind="loan"). It is the
        # mirror of debt_service: this counterparty only ever *pays out* (debits
        # itself, credits the consumer), so its balance runs negative.
        for area in numbers.MACRO_AREA_WEIGHTS:
            self._bill_merchants[("credit_line", area)] = Merchant(
                self, category="credit_line", macro_area=area
            )

        # 2. INCOME SOURCES — one per macro-area
        self.income_sources: dict[str, IncomeSource] = {
            area: IncomeSource(self, macro_area=area)
            for area in numbers.MACRO_AREA_WEIGHTS
        }

        # 3. CONSUMERS — assign macro-area by the population weights, then
        # give each one an income, a starting deposit, and a set of bills.
        areas = list(numbers.MACRO_AREA_WEIGHTS.keys())
        area_probs = np.array(
            [numbers.MACRO_AREA_WEIGHTS[a] for a in areas], dtype=float
        )
        area_probs /= area_probs.sum()

        self.consumers: list[Consumer] = []
        for _ in range(n_consumers):
            area = str(self.rng.choice(areas, p=area_probs))
            # Primary income source, then scale the SHIW draw by the mean-
            # preserving source multiplier (population mean income unchanged).
            source = numbers.sample_income_source(self.rng)
            # Draw from the source's own lognormal (its own spread), centred on the
            # mean-preserving target for this source AND this macro-area, so the
            # population mean — and the SHIW bands — stay put while the South sits
            # below Centre-North (Semeraro et al. 2020). Both multipliers are
            # mean-preserving; see numbers.sample_income_for_source.
            income = numbers.sample_income_for_source(self.rng, source, area)
            # Start each consumer with one month of income as buffer.
            starting_balance = income * 1.0
            # Decide which bills this consumer is subscribed to.
            subscribed: dict[str, dict] = {}
            for bill_name, spec in numbers.BILL_TYPES.items():
                if self.rng.random() < spec["share"]:
                    subscribed[bill_name] = spec
            c = Consumer(
                self,
                macro_area=area,
                monthly_income=income,
                starting_balance=starting_balance,
                bills_subscribed=subscribed,
                income_source=source,
            )
            self.consumers.append(c)
            self.income_sources[area].attach(c)

        # 3b. INCOME BANDS — SHIW reports debt by income *quartile* and
        # savings by income *quintile*. We don't have a paper cut-point table,
        # so the bands are the empirical percentiles of the incomes we just
        # drew (the SHIW lognormal at numbers.INCOME_LOGNORMAL). This keeps
        # every consumer comparable to the realised population, not to an
        # invented threshold.
        self._assign_income_bands()

        # 3c. DEBT — roll each consumer's debt flag from the SHIW debt-
        # participation probability for their income quartile; debt-holders
        # get a monthly debt-service amount and overdraft permission.
        self._assign_debt()

        # 3d. SAVINGS — roll the saver flag from the SHIW saving probability
        # for the income quintile; an independent second roll marks some
        # savers as pension-savers (their sweep is tagged "pension").
        self._assign_savings()

        # 4. A small graph for the Solara network panel. Includes consumer
        # nodes, a handful of merchant nodes, and one IncomeSource node per
        # macro-area so it's visually clear where money enters the system.
        # Topology is built once and not mutated during the run.
        self.graph: nx.Graph = self._build_visual_graph()

        # 5. DataCollector — Mesa hook the Solara plot component reads.
        self._last_day_count: int = 0
        self._last_day_eur: float = 0.0
        self._balance_snapshot: dict[str, dict[str, float]] = self.group_balances()
        model_reporters: dict = {
            "daily_txn_count": lambda m: m._last_day_count,
            "daily_eur_total": lambda m: m._last_day_eur,
        }
        # Per-debtor-subtype reporters for the debt-trajectory panel: total
        # outstanding principal and count still in debt, per archetype per day.
        # ``st=st`` binds the loop variable so each lambda keeps its own subtype.
        for st in numbers.DEBTOR_SUBTYPES:
            model_reporters[f"debt_total_{st}"] = (
                lambda m, st=st: m.debt_by_subtype()[st]["total_debt"]
            )
            model_reporters[f"debt_indebt_{st}"] = (
                lambda m, st=st: m.debt_by_subtype()[st]["n_in_debt"]
            )
        # Balance-trajectory reporters: mean current-account balance per day,
        # grouped by income source, income level, and debtor subtype. Each reads
        # the once-per-step snapshot (``_balance_snapshot``). Missing groups (no
        # members) report 0.0. ``key=key``/``dim=dim`` bind the loop variables.
        _balance_groups = [
            ("src", list(numbers.INCOME_SOURCE_SHARE.keys())),
            ("lvl", ["low", "middle", "high"]),
            ("dst", list(numbers.DEBTOR_SUBTYPES)),
        ]
        for dim, keys in _balance_groups:
            for key in keys:
                model_reporters[f"bal_cur_{dim}_{key}"] = (
                    lambda m, dim=dim, key=key: m._balance_snapshot[dim].get(key, 0.0)
                )
        self.datacollector = mesa.DataCollector(model_reporters=model_reporters)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def step(self) -> None:
        """Advance the calendar by one day, run income sources, then run
        every consumer in a shuffled order."""
        txn_count_before = len(self.transactions)
        eur_before = sum(t["amount_eur"] for t in self.transactions)

        # Income first (so a consumer paid today can spend today), then
        # consumers in random order so no one always goes first.
        self.agents_by_type[IncomeSource].do("step")
        self.agents_by_type[Consumer].shuffle_do("step")

        # KPIs for this day (used by the Solara plot panel + the DataCollector).
        self._last_day_count = len(self.transactions) - txn_count_before
        self._last_day_eur = (
            sum(t["amount_eur"] for t in self.transactions) - eur_before
        )
        # Snapshot grouped mean balances once, so the (many) balance reporters
        # below each read a cached dict instead of re-walking every consumer.
        self._balance_snapshot = self.group_balances()
        self.datacollector.collect(self)

        # Advance the model clock.
        self.today = self.today + timedelta(days=1)

    def run(self) -> None:
        """Step the model ``n_days`` times in a row."""
        for _ in range(self.n_days):
            self.step()

    # ------------------------------------------------------------------
    # Clustering + per-account export (read-only; no disk I/O here)
    # ------------------------------------------------------------------

    @staticmethod
    def _financial_status(c: Consumer) -> str:
        base = "saver" if c.is_saver else "non_saver"
        return base + ("+debt" if c.has_debt else "")

    def cluster_of(self, c: Consumer) -> tuple[str, str, str]:
        """The cluster a consumer belongs to: macro-area × income band
        (income *quartile*, the debt dimension) × financial status."""
        return (c.macro_area, f"Q{c.income_quartile}", self._financial_status(c))

    def clusters(self) -> dict[tuple[str, str, str], list[Consumer]]:
        """Group every consumer by ``cluster_of``. Single source of truth —
        the notebook and the Solara inspector both call this."""
        out: dict[tuple[str, str, str], list[Consumer]] = {}
        for c in self.consumers:
            out.setdefault(self.cluster_of(c), []).append(c)
        return out

    def debt_by_subtype(self) -> dict[str, dict[str, float]]:
        """Per-archetype debt aggregate, read-only::

            {subtype: {"total_debt": €outstanding, "n_in_debt": count}}

        Keyed by ``numbers.DEBTOR_SUBTYPES``. Used by the DataCollector
        reporters (for the trajectory plot) and the composition panel."""
        out = {
            st: {"total_debt": 0.0, "n_in_debt": 0}
            for st in numbers.DEBTOR_SUBTYPES
        }
        for c in self.consumers:
            st = c.debtor_subtype
            if st is None or st not in out:
                continue
            out[st]["total_debt"] += c.debt_balance
            if c.has_debt:
                out[st]["n_in_debt"] += 1
        return out

    def group_balances(self) -> dict[str, dict[str, float]]:
        """Mean **current-account** balance grouped three ways — by income source,
        by income level, and by debtor subtype. This is the per-day snapshot the
        balance-trajectory reporters read::

            {"src": {source: mean_balance},
             "lvl": {level:  mean_balance},
             "dst": {subtype: mean_balance}}

        The current account is the most dynamic (payday sawtooth, overdraft dips),
        so it is the one we track over time. A consumer with no debtor subtype
        (never in debt) is simply absent from the ``dst`` grouping.
        """
        dims = ("src", "lvl", "dst")
        sums: dict[str, dict[str, float]] = {d: {} for d in dims}
        counts: dict[str, dict[str, int]] = {d: {} for d in dims}
        for c in self.consumers:
            bal = c.accounts.current.balance
            keyed = {"src": c.income_source, "lvl": c.income_level, "dst": c.debtor_subtype}
            for dim, key in keyed.items():
                if key is None:
                    continue
                sums[dim][key] = sums[dim].get(key, 0.0) + bal
                counts[dim][key] = counts[dim].get(key, 0) + 1
        return {
            dim: {k: sums[dim][k] / counts[dim][k] for k in sums[dim]}
            for dim in dims
        }

    def export_dpd_history(self) -> list[dict]:
        """One row per (consumer, closed month) — the month-end credit-file
        snapshot assembled by ``Consumer._record_month_end``.

        This is the only agent x time table the model exports; the
        ``DataCollector`` series are group means, not per-agent. It is what
        ``synthitaly.panel`` builds the rolling-window designs of Khandani, Kim
        & Lo (2010) and Butaru et al. (2015) on top of. The final partial month
        has no row, because it never closed."""
        return [row for c in self.consumers for row in c.dpd_history]

    def export_accounts(self) -> list[dict]:
        """One row per (consumer, account_type) — flat enough to drop into a
        DataFrame or CSV. The model itself writes nothing to disk; callers
        decide whether to persist it."""
        rows: list[dict] = []
        for c in self.consumers:
            area, band, status = self.cluster_of(c)
            for acct_type, acct in c.accounts.as_dict().items():
                total_in = sum(e.amount_eur for e in acct.entries if e.direction == "in")
                total_out = sum(e.amount_eur for e in acct.entries if e.direction == "out")
                rows.append({
                    "owner_id": acct.owner_id,
                    "consumer_id": c.unique_id,
                    "macro_area": area,
                    "income_source": c.income_source,
                    "income_level": c.income_level,
                    "income_quartile": c.income_quartile,
                    "income_quintile": c.income_quintile,
                    "financial_status": status,
                    "debtor_subtype": c.debtor_subtype,
                    "debt_balance": round(c.debt_balance, 2),
                    "cluster": f"{area} | {band} | {status}",
                    "account_type": acct_type,
                    "starting_balance": round(acct.starting_balance, 2),
                    "balance": round(acct.balance, 2),
                    "n_entries": len(acct.entries),
                    "total_in": round(total_in, 2),
                    "total_out": round(total_out, 2),
                })
        return rows

    # ------------------------------------------------------------------
    # Internal helpers (used by the agent classes above)
    # ------------------------------------------------------------------

    def _log_txn(
        self,
        *,
        kind: str,
        from_party: int | str,
        to_party: int | str,
        category: str,
        amount: float,
        macro_area: str,
    ) -> None:
        """Append a transaction dict to the in-memory ledger.

        This is *additional* to the per-agent BankAccount entries — it gives
        a flat, model-level list that the notebook can dump straight into
        pandas without walking every agent.
        """
        self.transactions.append({
            "date": self.today.isoformat(),
            "kind": kind,           # "salary" | "bill" | "purchase" | "fee" | "loan"
            "from": str(from_party),
            "to": str(to_party),
            "category": category,
            "amount_eur": round(float(amount), 2),
            "macro_area": macro_area,
        })

    def _pick_merchant(self, category: str, macro_area: str) -> Merchant | None:
        """Pick a random merchant in (category, macro_area). Returns None
        if the pool is empty (shouldn't happen with default parameters)."""
        pool = self.merchants.get((category, macro_area), [])
        if not pool:
            return None
        idx = int(self.rng.integers(0, len(pool)))
        return pool[idx]

    def _bill_merchant(self, bill_name: str, macro_area: str) -> Merchant:
        """Lookup the stand-in merchant used for a given bill type."""
        return self._bill_merchants[(bill_name, macro_area)]

    def _assign_income_bands(self) -> None:
        """Tag every consumer with an income quartile (1..4), quintile (1..5), and
        a low/middle/high level.

        Quartiles/quintiles are empirical percentiles of the realised incomes
        (``np.searchsorted`` on the cut-points, shifted to 1-based) — these drive
        the SHIW debt/savings calibration. The *level* is independent: it uses the
        absolute euro bands of the Bank of Italy Payment Behaviour Survey
        (``numbers.income_level``), so "low income" means the survey's ≤€1,000/month
        in absolute terms, not a percentile of this particular run.
        """
        incomes = np.array([c.monthly_income for c in self.consumers], dtype=float)
        if incomes.size == 0:
            return
        q_cuts = np.quantile(incomes, [0.25, 0.50, 0.75])
        p_cuts = np.quantile(incomes, [0.20, 0.40, 0.60, 0.80])
        for c in self.consumers:
            c.income_quartile = int(np.searchsorted(q_cuts, c.monthly_income, side="right")) + 1
            c.income_quintile = int(np.searchsorted(p_cuts, c.monthly_income, side="right")) + 1
            c.income_level = numbers.income_level(c.monthly_income)

    def _assign_debt(self) -> None:
        """Roll the debt flag per consumer from the SHIW quartile probability,
        then split the flagged debtors into the three behavioural archetypes
        (climber / chronic / subsister). The SHIW roll is unchanged — subtypes
        only *partition* the debtors it already produces.

        Each debtor gets an opening principal (a stock) and a monthly scheduled
        service; the archetype then sets how it overdraws / borrows:
          • chronic   — runs a standing overdraft (floor = one month's service),
                        repays interest only, so the principal stays flat;
          • climber   — no overdraft (floor 0); repays the full service, so the
                        principal falls and it eventually leaves debt;
          • subsister — no overdraft (floor 0) but borrows on a credit line to
                        cover shortfalls, so the current account hugs zero.
        """
        for c in self.consumers:
            c.has_debt = numbers.has_debt(self.rng, c.income_quartile)
            if c.has_debt:
                c._monthly_debt_service = (
                    numbers.annual_debt_service(self.rng, c.income_quartile) / 12.0
                )
                # SHIW 2022 §3 financial vulnerability: equivalized income below
                # median (lower two quartiles) AND debt-service ratio > 30%. This
                # tilts the archetype draw so the chronic cohort concentrates among
                # vulnerable households (see numbers.sample_debtor_subtype).
                c.debt_service_ratio = (
                    c._monthly_debt_service / c.monthly_income
                    if c.monthly_income > 0 else 0.0
                )
                c.is_financially_vulnerable = (
                    c.income_quartile <= 2 and c.debt_service_ratio > 0.30
                )
                c.debtor_subtype = numbers.sample_debtor_subtype(
                    self.rng, c.is_financially_vulnerable
                )
                c.debt_balance = numbers.opening_debt_principal(c._monthly_debt_service)
                if c.debtor_subtype == "chronic":
                    c.overdraft_allowed = True
                    # Run as far negative as one month of their own service —
                    # enough to keep paying (and stay in the red) when tight.
                    c._overdraft_floor = -c._monthly_debt_service
                else:
                    # Climbers and subsisters never overdraw: climbers defer an
                    # unaffordable bill, subsisters borrow to cover it.
                    c.overdraft_allowed = False
                    c._overdraft_floor = 0.0
                if c.debtor_subtype == "subsister":
                    # Hand-to-mouth: no cash cushion to start with (the monthly
                    # surplus is swept out in _assign_savings), so the current
                    # account hugs zero and shortfalls are met by borrowing.
                    c.accounts.current.starting_balance = 0.0
                    c.accounts.current._cached_balance = 0.0

    def _assign_savings(self) -> None:
        """Roll the saver flag per consumer from the SHIW quintile saving
        probability. A second independent roll (same probability) decides
        whether a saver is also a pension-saver — only the SHIW probability
        is reused, no contribution rate is invented."""
        for c in self.consumers:
            c.is_saver = numbers.is_saver(self.rng, c.income_quintile)
            if c.is_saver:
                c.is_pension_saver = numbers.is_saver(self.rng, c.income_quintile)
            # Subsisters are hand-to-mouth: force the month-close sweep on so any
            # surplus leaves the current account (it hugs zero) and lands in the
            # savings pot rather than building a current-account buffer.
            if c.debtor_subtype == "subsister":
                c.is_saver = True

    def _build_visual_graph(self) -> nx.Graph:
        """The graph that the Solara NetworkPanel draws.

        Three node kinds:
          - "consumer": one per Consumer, coloured by macro-area
          - "merchant": one per merchant in the top-3 spending categories
                        (retail/food/hotels_rest), so the picture stays
                        readable even with 90 merchants in the model
          - "income_source": one per macro-area, connected to every
                             consumer in that area — visually anchors
                             where money enters the system
        """
        g = nx.Graph()

        # Consumer nodes
        for c in self.consumers:
            g.add_node(c.unique_id, kind="consumer", macro_area=c.macro_area)

        # Merchant nodes — only the first 3 merchants per (category, area)
        # to avoid clutter; the simulation itself uses all of them.
        for (cat, area), pool in self.merchants.items():
            for m in pool[:3]:
                g.add_node(
                    m.unique_id, kind="merchant", macro_area=area, category=cat
                )

        # Connect each consumer to one merchant per top-3 category in
        # their area (deterministic — first merchant in the pool).
        top_cats = ["retail", "food", "hotels_rest"]
        for c in self.consumers:
            for cat in top_cats:
                pool = self.merchants.get((cat, c.macro_area), [])
                if pool:
                    m = pool[0]
                    g.add_edge(c.unique_id, m.unique_id)

        # Income-source nodes — one per macro-area, connected to every
        # consumer they pay. Use a string id so they don't collide with
        # Mesa agent unique_ids (which are integers).
        for area, src in self.income_sources.items():
            src_node_id = f"income_{area}"
            g.add_node(src_node_id, kind="income_source", macro_area=area)
            for c in src.served_consumers:
                g.add_edge(src_node_id, c.unique_id)

        return g
