"""Sanity tests for the empirical constants in ``numbers.py``."""

from __future__ import annotations

from datetime import date

import numpy as np

from synthitaly import numbers


def test_macro_area_weights_sum_to_one():
    assert abs(sum(numbers.MACRO_AREA_WEIGHTS.values()) - 1.0) < 0.01


def test_category_shares_sum_to_one():
    assert abs(sum(numbers.CATEGORY_SHARES.values()) - 1.0) < 0.01


def test_every_category_has_a_lognormal_parameter_pair():
    assert set(numbers.CATEGORY_SHARES) == set(numbers.CATEGORY_TICKET_LOGNORMAL)


def test_sample_ticket_is_positive():
    rng = np.random.default_rng(0)
    for cat in numbers.CATEGORY_SHARES:
        for _ in range(20):
            assert numbers.sample_ticket(rng, cat) > 0


def test_sample_category_returns_known_label():
    rng = np.random.default_rng(0)
    valid = set(numbers.CATEGORY_SHARES)
    for _ in range(50):
        assert numbers.sample_category(rng) in valid


def test_selection_probs_reproduce_category_shares_in_euros():
    """CATEGORY_SHARES are shares of EUROS (Emiliozzi et al. 2023 §2.1, Fig. 4/6),
    but the model picks a category and then draws the ticket independently. So
    the euro share a category actually receives is p_c * E[ticket_c], normalised
    — not p_c. This asserts the two agree, which is the regression guard for the
    whole units fix: reverting sample_category() to weight directly by the
    shares puts travel at a 19.8% euro share against the paper's 9.0%.

    Pure arithmetic on the constants — no model run.
    """
    keys, probs = numbers._category_selection_probs()
    mean_ticket = np.array(
        [np.exp(mu + sigma ** 2 / 2) for mu, sigma in
         (numbers.CATEGORY_TICKET_LOGNORMAL[k] for k in keys)]
    )
    euro = probs * mean_ticket
    euro = euro / euro.sum()
    for k, got in zip(keys, euro, strict=True):
        assert abs(got - numbers.CATEGORY_SHARES[k]) < 1e-12, (
            f"{k}: realised euro share {got:.4f} != paper share "
            f"{numbers.CATEGORY_SHARES[k]:.4f}"
        )


def test_sample_category_draws_match_the_selection_probabilities():
    """The empirical counterpart of the test above: draw, and check the realised
    euro mix converges on CATEGORY_SHARES rather than on the count mix."""
    # Credit each draw with its category's EXPECTED ticket rather than a drawn
    # one: the question is whether the selection probabilities are right, and a
    # lognormal draw would add variance that has nothing to do with that.
    expected_ticket = {
        cat: float(np.exp(mu + sigma ** 2 / 2))
        for cat, (mu, sigma) in numbers.CATEGORY_TICKET_LOGNORMAL.items()
    }
    rng = np.random.default_rng(0)
    spend = dict.fromkeys(numbers.CATEGORY_SHARES, 0.0)
    for _ in range(200_000):
        cat = numbers.sample_category(rng)
        spend[cat] += expected_ticket[cat]
    total = sum(spend.values())
    for k, share in numbers.CATEGORY_SHARES.items():
        assert abs(spend[k] / total - share) < 0.01, (
            f"{k}: realised euro share {spend[k] / total:.4f} vs {share:.4f}"
        )


def test_daily_intensity_is_higher_in_december_than_february():
    feb_mon = date(2020, 2, 17)   # ordinary Monday
    dec_mon = date(2020, 12, 14)  # ordinary Monday in December
    assert numbers.daily_intensity(dec_mon) > numbers.daily_intensity(feb_mon)


def test_is_payday_fires_on_the_27th():
    assert numbers.is_payday(date(2020, 3, 27))
    assert not numbers.is_payday(date(2020, 3, 26))


def test_debt_probability_monotone_in_quartile():
    p = numbers.DEBT_PROBABILITY_BY_INCOME_QUARTILE
    assert set(p) == {1, 2, 3, 4}
    vals = [p[q] for q in (1, 2, 3, 4)]
    assert all(0.0 <= v <= 1.0 for v in vals)
    assert vals == sorted(vals) and vals[0] < vals[-1]  # richer quartile -> more debt


def test_debt_service_mean_monotone():
    m = numbers.DEBT_SERVICE_MEAN_BY_QUARTILE_EUR
    assert set(m) == {1, 2, 3, 4}
    vals = [m[q] for q in (1, 2, 3, 4)]
    assert all(v > 0 for v in vals)
    assert vals == sorted(vals) and vals[0] < vals[-1]


def test_has_debt_and_annual_debt_service_valid():
    rng = np.random.default_rng(0)
    for q in (1, 2, 3, 4):
        assert isinstance(numbers.has_debt(rng, q), bool)
        assert numbers.annual_debt_service(rng, q) > 0
    for bad in (0, 5):
        try:
            numbers.has_debt(rng, bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"has_debt accepted bad quartile {bad}")


def test_debtor_subtype_share_well_formed():
    share = numbers.DEBTOR_SUBTYPE_SHARE
    assert set(share) == set(numbers.DEBTOR_SUBTYPES)
    assert abs(sum(share.values()) - 1.0) < 1e-9
    assert all(0.0 <= v <= 1.0 for v in share.values())


def test_sample_debtor_subtype_covers_all_subtypes():
    rng = np.random.default_rng(0)
    # The draw is tilted by the SHIW financial-vulnerability flag; both tilts
    # keep all three subtypes reachable.
    drawn = set()
    for _ in range(2000):
        drawn.add(numbers.sample_debtor_subtype(rng, True))
        drawn.add(numbers.sample_debtor_subtype(rng, False))
    assert drawn == set(numbers.DEBTOR_SUBTYPES)


def test_vulnerability_tilt_makes_chronic_more_likely():
    """A financially-vulnerable debtor is drawn chronic far more often than a
    resilient one (the SHIW §3 grounding for the chronic cohort)."""
    rng = np.random.default_rng(0)
    n = 4000
    vuln_chronic = sum(numbers.sample_debtor_subtype(rng, True) == "chronic" for _ in range(n))
    resi_chronic = sum(numbers.sample_debtor_subtype(rng, False) == "chronic" for _ in range(n))
    assert vuln_chronic > resi_chronic


def test_opening_debt_principal_scales_with_service():
    a = numbers.opening_debt_principal(100.0)
    b = numbers.opening_debt_principal(200.0)
    assert a > 0 and b > a
    assert abs(a - 100.0 * numbers.DEBT_OPENING_MONTHS) < 1e-9


def test_p_no_saving_monotone_decreasing():
    p = numbers.P_NO_SAVING_BY_INCOME_QUINTILE
    assert set(p) == {1, 2, 3, 4, 5}
    vals = [p[q] for q in (1, 2, 3, 4, 5)]
    assert all(0.0 <= v <= 1.0 for v in vals)
    # Poorer quintiles are likelier NOT to save.
    assert vals == sorted(vals, reverse=True) and vals[0] > vals[-1]


def test_is_saver_valid():
    rng = np.random.default_rng(0)
    for q in (1, 2, 3, 4, 5):
        assert isinstance(numbers.is_saver(rng, q), bool)
    for bad in (0, 6):
        try:
            numbers.is_saver(rng, bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"is_saver accepted bad quintile {bad}")


def test_easter_holiday_is_recognised():
    # Easter 2020 was 12 Apr; Pasquetta 13 Apr.
    assert numbers.is_holiday(date(2020, 4, 12))
    assert numbers.is_holiday(date(2020, 4, 13))
    assert not numbers.is_holiday(date(2020, 4, 14))


# ---- Behavioural-economics layer ------------------------------------------


def test_behavioural_constants_in_range():
    assert numbers.PAYDAY_SPIKE_PEAK >= 1.0
    assert numbers.OVERDRAFT_FEE_EUR >= 0.0
    assert 0.0 <= numbers.LATE_PAYMENT_FEE_FRACTION < 1.0


def test_pay_cycle_multiplier_is_mean_neutral_over_a_cycle():
    """Averaged over the days of a pay cycle the multiplier is exactly 1.0, so
    it re-times spend without inflating the monthly total."""
    from datetime import timedelta

    start = date(2017, 3, 27)              # a payday
    nxt = date(2017, 4, 27)               # the next payday
    days = [start + timedelta(days=k) for k in range((nxt - start).days)]
    vals = [numbers.pay_cycle_multiplier(d) for d in days]
    assert abs(sum(vals) / len(vals) - 1.0) < 1e-9
    # Peak on payday, trough the day before the next payday.
    assert vals[0] == max(vals)
    assert vals[-1] == min(vals)


def test_pay_cycle_multiplier_peaks_after_payday():
    """Just after payday spending intensity exceeds that just before the next
    payday."""
    assert numbers.pay_cycle_multiplier(date(2017, 3, 28)) > numbers.pay_cycle_multiplier(
        date(2017, 4, 25)
    )


def test_pay_cycle_multiplier_off_when_peak_is_one():
    original = numbers.PAYDAY_SPIKE_PEAK
    numbers.PAYDAY_SPIKE_PEAK = 1.0
    try:
        from datetime import timedelta

        start = date(2017, 3, 27)
        for k in range(31):
            assert numbers.pay_cycle_multiplier(start + timedelta(days=k)) == 1.0
    finally:
        numbers.PAYDAY_SPIKE_PEAK = original


# ---- Income-source heterogeneity ------------------------------------------


def test_income_source_share_sums_to_one():
    assert abs(sum(numbers.INCOME_SOURCE_SHARE.values()) - 1.0) < 1e-9


def test_income_source_relative_keys_and_order():
    rel = numbers.INCOME_SOURCE_RELATIVE
    assert {"payroll", "self_employed", "pension", "transfers", "unemployed"} <= set(rel)
    assert all(v > 0 for v in rel.values())
    # SHIW ordering: self-employed richest, pension below payroll.
    assert rel["self_employed"] > rel["payroll"] > rel["pension"]


def test_no_property_income_remains():
    """Property income was removed — no source gives its incidence or its size.

    It was a flat 10% Bernoulli paying 5% of the consumer's own income, with no
    paper behind either number, and it is gone from the constants, the ledger
    categories and the agent.
    """
    assert "property" not in numbers.INCOME_SOURCE_RELATIVE
    assert "property" not in numbers.INCOME_SOURCE_CATEGORY
    assert "property_income" not in numbers.INCOME_SOURCE_CATEGORY.values()
    assert not hasattr(numbers, "PROPERTY_INCOME_SECONDARY_RATE")
    assert not hasattr(numbers, "PROPERTY_SECONDARY_FRACTION")


def test_sample_income_source_returns_valid_label():
    rng = np.random.default_rng(0)
    valid = set(numbers.INCOME_SOURCE_SHARE)
    for _ in range(50):
        assert numbers.sample_income_source(rng) in valid


def test_income_source_multiplier_is_mean_preserving():
    """The share-weighted average of the source multipliers is exactly 1.0, so
    introducing sources does not move the population mean income."""
    wt = sum(
        numbers.INCOME_SOURCE_SHARE[s] * numbers.income_source_multiplier(s)
        for s in numbers.INCOME_SOURCE_SHARE
    )
    assert abs(wt - 1.0) < 1e-9
    # Ordering survives the normalisation.
    assert numbers.income_source_multiplier("payroll") > numbers.income_source_multiplier("pension")


def test_income_calendar_multiplier_december_bonus():
    dec = date(2017, 12, 27)
    mar = date(2017, 3, 27)
    assert numbers.income_calendar_multiplier(dec, "payroll") == 2.0
    assert numbers.income_calendar_multiplier(dec, "pension") == 2.0
    assert numbers.income_calendar_multiplier(dec, "transfers") == 1.0  # no tredicesima
    assert numbers.income_calendar_multiplier(mar, "payroll") == 1.0    # not December
