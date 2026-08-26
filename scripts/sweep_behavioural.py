"""Sensitivity sweep over the behavioural / non-Italian-magnitude parameters.

Several magnitudes in the model come from non-Italian papers or are not in the
source papers at all (see the "Behavioural-economics layer" and
"Income-source heterogeneity" blocks in ``synthitaly/numbers.py``), so the
honest way to use them is to show how the model's KPIs move as they vary —
results are never hostage to a single number.

This sweep varies one parameter at a time around the defaults:

    PAYDAY_SPIKE_PEAK         Olafsson & Pagel (2018) — post-payday spending spike
    OVERDRAFT_FEE_EUR         Stango & Zinman (2014)  — flat per-event overdraft fee
    LATE_PAYMENT_FEE_FRACTION Dahan & Nisan (2020)    — late-payment penalty
    pension SHARE             not in the 5 papers (ISTAT-proxy) — pensioner headcount
    unemployed SHARE          not in the 5 papers (ISTAT-proxy) — jobless headcount
    DEBT_MONTHLY_INTEREST_RATE  debt-stock layer (modelling choice) — interest on principal
    vulnerable-chronic SHARE    debt-stock layer (modelling choice) — how chronic-heavy the
                                SHIW financially-vulnerable debtors are drawn

The debt-stock sweeps run on a longer horizon (N_DAYS_DEBT) so climbers have
time to pay their principal down to zero and leave debt.

Run:  uv run python scripts/sweep_behavioural.py
"""

from __future__ import annotations

from synthitaly import numbers
from synthitaly.model import ItalyModel

# Defaults mirror numbers.py; the sweep restores them when it finishes.
DEFAULTS = {
    "peak": numbers.PAYDAY_SPIKE_PEAK,
    "fee": numbers.OVERDRAFT_FEE_EUR,
    "late_frac": numbers.LATE_PAYMENT_FEE_FRACTION,
}
DEFAULT_SHARE = dict(numbers.INCOME_SOURCE_SHARE)

N_CONSUMERS = 300
N_DAYS = 150
N_DAYS_DEBT = 720  # ~24 months — long enough for climbers to dig out
SEED = 42


def _kpis() -> dict:
    """Run one model at the current numbers.* settings and return summary KPIs."""
    m = ItalyModel(n_consumers=N_CONSUMERS, n_days=N_DAYS, seed=SEED)
    m.run()
    txns = m.transactions

    od = [t for t in txns if t["category"] == "overdraft_fee"]
    lf = [t for t in txns if t["category"] == "late_payment_fee"]
    purchases = [t for t in txns if t["kind"] == "purchase"]
    pension_inc = [t for t in txns if t["kind"] == "salary" and t["category"] == "pension"]
    n_pensioners = sum(1 for c in m.consumers if c.income_source == "pension")
    return {
        "overdraft_fee_eur": round(sum(t["amount_eur"] for t in od)),
        "late_payments": len(lf),
        "late_fee_eur": round(sum(t["amount_eur"] for t in lf)),
        "purchase_eur": round(sum(t["amount_eur"] for t in purchases)),
        "pensioners": n_pensioners,
        "pension_inc_eur": round(sum(t["amount_eur"] for t in pension_inc)),
    }


def _kpis_behavioural(*, peak: float, fee: float, late_frac: float) -> dict:
    numbers.PAYDAY_SPIKE_PEAK = peak
    numbers.OVERDRAFT_FEE_EUR = fee
    numbers.LATE_PAYMENT_FEE_FRACTION = late_frac
    return _kpis()


def _kpis_source_share(source: str, share: float) -> dict:
    """Set one income source's headcount share (renormalising the other sources
    to keep the mix summing to 1.0) and report KPIs."""
    others = {k: v for k, v in DEFAULT_SHARE.items() if k != source}
    scale = (1.0 - share) / sum(others.values())
    numbers.INCOME_SOURCE_SHARE = {
        **{k: v * scale for k, v in others.items()},
        source: share,
    }
    try:
        return _kpis()
    finally:
        numbers.INCOME_SOURCE_SHARE = dict(DEFAULT_SHARE)


def _debt_kpis() -> dict:
    """Run one long-horizon model and report, per debtor archetype, the mean
    outstanding debt balance and how many of that archetype have dug out
    (principal paid to zero → has_debt cleared)."""
    m = ItalyModel(n_consumers=N_CONSUMERS, n_days=N_DAYS_DEBT, seed=SEED)
    m.run()
    deb = [c for c in m.consumers if c.debtor_subtype]
    out: dict = {}
    for st in numbers.DEBTOR_SUBTYPES:
        grp = [c for c in deb if c.debtor_subtype == st]
        n = len(grp)
        out[f"{st[:4]}_debt"] = round(sum(c.debt_balance for c in grp) / n) if n else 0
        out[f"{st[:4]}_out"] = sum(1 for c in grp if not c.has_debt)
    return out


def _kpis_debt_interest(rate: float) -> dict:
    original = numbers.DEBT_MONTHLY_INTEREST_RATE
    numbers.DEBT_MONTHLY_INTEREST_RATE = rate
    try:
        return _debt_kpis()
    finally:
        numbers.DEBT_MONTHLY_INTEREST_RATE = original


def _kpis_vulnerable_chronic_share(chronic_share: float) -> dict:
    """Shift how chronic-heavy the SHIW financially-vulnerable debtors are drawn
    (splitting the remainder evenly between climber and subsister) and report the
    per-archetype debt KPIs. This is the lever that decides how big and how stuck
    the chronic cohort becomes."""
    original = dict(numbers.DEBTOR_SUBTYPE_SHARE_VULNERABLE)
    rest = (1.0 - chronic_share) / 2.0
    numbers.DEBTOR_SUBTYPE_SHARE_VULNERABLE = {
        "climber": rest, "chronic": chronic_share, "subsister": rest,
    }
    try:
        return _debt_kpis()
    finally:
        numbers.DEBTOR_SUBTYPE_SHARE_VULNERABLE = original


def _print_block(title: str, rows: list[tuple[str, dict]]) -> None:
    print(f"\n== {title} ==")
    cols = list(rows[0][1].keys())
    header = f"{'param':>10} | " + " | ".join(f"{c:>16}" for c in cols)
    print(header)
    print("-" * len(header))
    for label, kpi in rows:
        print(f"{label:>10} | " + " | ".join(f"{kpi[c]:>16}" for c in cols))


def main() -> None:
    print(f"Sweep: n_consumers={N_CONSUMERS}, n_days={N_DAYS}, seed={SEED}")
    print(f"Defaults: {DEFAULTS} | pension share={DEFAULT_SHARE['pension']}")
    try:
        _print_block(
            "PAYDAY_SPIKE_PEAK (Olafsson & Pagel 2018)",
            [(str(p), _kpis_behavioural(**{**DEFAULTS, "peak": p})) for p in (1.0, 1.25, 1.5, 2.0)],
        )
        _print_block(
            "OVERDRAFT_FEE_EUR (Stango & Zinman 2014)",
            [(str(f), _kpis_behavioural(**{**DEFAULTS, "fee": f})) for f in (0.0, 15.0, 30.0, 60.0)],
        )
        _print_block(
            "LATE_PAYMENT_FEE_FRACTION (Dahan & Nisan 2020)",
            [(str(lf), _kpis_behavioural(**{**DEFAULTS, "late_frac": lf})) for lf in (0.0, 0.05, 0.11, 0.25)],
        )
        # Restore behavioural defaults before the share sweep.
        _kpis_behavioural(**DEFAULTS)
        _print_block(
            "pension SHARE (ISTAT-proxy, not in the 5 papers)",
            [(str(p), _kpis_source_share("pension", p)) for p in (0.10, 0.20, 0.30, 0.40)],
        )
        _print_block(
            "unemployed SHARE (ISTAT-proxy, not in the 5 papers)",
            [(str(p), _kpis_source_share("unemployed", p)) for p in (0.02, 0.05, 0.10, 0.15)],
        )
        print(f"\n[debt-stock sweeps use n_days={N_DAYS_DEBT}; "
              f"*_debt = mean principal EUR, *_out = count dug out]")
        _print_block(
            "DEBT_MONTHLY_INTEREST_RATE (modelling choice — debt-stock layer)",
            [(str(r), _kpis_debt_interest(r)) for r in (0.0, 0.005, 0.01, 0.02)],
        )
        _print_block(
            "vulnerable-chronic SHARE (chronic-heaviness of vulnerable debtors)",
            [(str(s), _kpis_vulnerable_chronic_share(s)) for s in (0.30, 0.45, 0.60, 0.80)],
        )
    finally:
        numbers.PAYDAY_SPIKE_PEAK = DEFAULTS["peak"]
        numbers.OVERDRAFT_FEE_EUR = DEFAULTS["fee"]
        numbers.LATE_PAYMENT_FEE_FRACTION = DEFAULTS["late_frac"]
        numbers.INCOME_SOURCE_SHARE = dict(DEFAULT_SHARE)


if __name__ == "__main__":
    main()
