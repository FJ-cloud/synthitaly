"""Income SOURCE × LEVEL layer: the explicit ``unemployed`` source, per-source
income *scale* (dispersion), and the absolute-euro low/middle/high *level* bands.

Complements the income-source tests already in ``test_smoke.py`` /
``test_numbers.py`` — here we cover the dispersion and level features added on
top of the original source/level-multiplier machinery.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

from synthitaly import numbers
from synthitaly.model import ItalyModel


def test_unemployed_source_present_and_shares_sum_to_one():
    assert "unemployed" in numbers.INCOME_SOURCE_SHARE
    assert abs(sum(numbers.INCOME_SOURCE_SHARE.values()) - 1.0) < 1e-9


def test_income_source_sigma_key_parity():
    """Every primary source carries its own dispersion."""
    assert set(numbers.INCOME_SOURCE_SIGMA) == set(numbers.INCOME_SOURCE_SHARE)
    assert all(v > 0 for v in numbers.INCOME_SOURCE_SIGMA.values())


def test_sample_income_for_source_is_mean_preserving_per_source():
    """Each source's lognormal is centred on the mean-preserving target
    ``base_mean * multiplier``, so per-source sample means track that target.

    The draw now also carries a macro-area factor, so the per-source target is
    only recovered as a population-weighted mixture over the areas — drawing a
    single area would give that area's tilted mean, not the source target.
    """
    rng = np.random.default_rng(0)
    base_mu, base_sigma = numbers.INCOME_LOGNORMAL
    base_mean = math.exp(base_mu + base_sigma**2 / 2)
    areas = list(numbers.MACRO_AREA_WEIGHTS)
    probs = np.array([numbers.MACRO_AREA_WEIGHTS[a] for a in areas], dtype=float)
    probs /= probs.sum()
    for s in numbers.INCOME_SOURCE_SHARE:
        target = base_mean * numbers.income_source_multiplier(s)
        drawn = rng.choice(areas, size=30000, p=probs)
        xs = [numbers.sample_income_for_source(rng, s, a) for a in drawn]
        assert abs(float(np.mean(xs)) / target - 1.0) < 0.05


def test_income_is_mean_preserving_across_macro_areas():
    """The area gradient moves income between areas without moving the mean.

    Holding the source fixed removes the source dimension, so what is left is
    purely the Semeraro et al. tilt: the population-weighted mean of the area
    draws must come back to the source's own target.
    """
    rng = np.random.default_rng(11)
    base_mean = math.exp(numbers.INCOME_LOGNORMAL[0] + numbers.INCOME_LOGNORMAL[1] ** 2 / 2)
    target = base_mean * numbers.income_source_multiplier("payroll")
    per_area = {
        a: float(np.mean([numbers.sample_income_for_source(rng, "payroll", a)
                          for _ in range(40000)]))
        for a in numbers.MACRO_AREA_WEIGHTS
    }
    mixture = sum(numbers.MACRO_AREA_WEIGHTS[a] * m for a, m in per_area.items())
    assert abs(mixture / target - 1.0) < 0.05

    # ... and the gap it produces is the published one: the South sits 44.6%
    # below Centre-North (Semeraro et al. 2020 p.27 / p.5).
    centre_north = (
        numbers.MACRO_AREA_WEIGHTS["NORTH"] * per_area["NORTH"]
        + numbers.MACRO_AREA_WEIGHTS["CENTRE"] * per_area["CENTRE"]
    ) / (numbers.MACRO_AREA_WEIGHTS["NORTH"] + numbers.MACRO_AREA_WEIGHTS["CENTRE"])
    assert per_area["SOUTH"] / centre_north == pytest.approx(0.554, abs=0.03)
    # The paper gives a two-way split only — North and Centre are one bloc.
    assert per_area["NORTH"] / per_area["CENTRE"] == pytest.approx(1.0, abs=0.05)


def test_macro_area_income_multiplier_rejects_unknown_area():
    with pytest.raises(ValueError, match="unknown macro_area"):
        numbers.macro_area_income_multiplier("MIDDLE-EARTH")


def test_self_employed_has_the_widest_spread():
    rng = np.random.default_rng(1)
    stds = {
        s: float(np.std([numbers.sample_income_for_source(rng, s, "NORTH")
                         for _ in range(30000)]))
        for s in numbers.INCOME_SOURCE_SHARE
    }
    assert stds["self_employed"] == max(stds.values())


def test_population_mean_preserved_and_source_order():
    """Per-source scale leaves the population mean ~ the base mean, and the SHIW
    ordering survives into realised incomes."""
    base_mean = math.exp(numbers.INCOME_LOGNORMAL[0] + numbers.INCOME_LOGNORMAL[1] ** 2 / 2)
    model = ItalyModel(n_consumers=600, n_merchants_per_category=2, n_days=1, seed=9)
    incomes = [c.monthly_income for c in model.consumers]
    assert abs(float(np.mean(incomes)) / base_mean - 1.0) < 0.10
    means = {}
    for s in numbers.INCOME_SOURCE_SHARE:
        grp = [c.monthly_income for c in model.consumers if c.income_source == s]
        assert grp, f"no {s} consumers at n=600"
        means[s] = sum(grp) / len(grp)
    assert means["self_employed"] > means["payroll"] > means["pension"]
    assert means["pension"] > means["transfers"]
    assert means["pension"] > means["unemployed"]


def test_realised_area_headcounts_track_the_population_weights():
    """The realised split matches MACRO_AREA_WEIGHTS.

    There was no test on this before, which is part of why the weights sat
    unexamined at card-spend shares (0.50/0.27/0.23) while being documented as
    population shares. They are now ISTAT population shares, and SOUTH is the
    second-largest area rather than the smallest.
    """
    model = ItalyModel(n_consumers=2000, n_merchants_per_category=1, n_days=1, seed=5)
    n = len(model.consumers)
    for area, weight in numbers.MACRO_AREA_WEIGHTS.items():
        share = sum(c.macro_area == area for c in model.consumers) / n
        assert share == pytest.approx(weight, abs=0.03), f"{area}: {share:.3f} vs {weight}"
    assert (
        numbers.MACRO_AREA_WEIGHTS["SOUTH"] > numbers.MACRO_AREA_WEIGHTS["CENTRE"]
    ), "ISTAT population: the South is larger than the Centre"


def test_south_earns_less_than_centre_north_in_a_built_model():
    """The gradient survives into realised incomes, not just the sampler.

    End-to-end version of the sampler test above: build a model and check that
    Southern households really do sit below Centre-North, and that the
    population mean is still the base mean (mean-preservation).
    """
    base_mean = math.exp(numbers.INCOME_LOGNORMAL[0] + numbers.INCOME_LOGNORMAL[1] ** 2 / 2)
    model = ItalyModel(n_consumers=3000, n_merchants_per_category=1, n_days=1, seed=17)
    inc = {a: [] for a in numbers.MACRO_AREA_WEIGHTS}
    for c in model.consumers:
        inc[c.macro_area].append(c.monthly_income)

    overall = float(np.mean([c.monthly_income for c in model.consumers]))
    assert abs(overall / base_mean - 1.0) < 0.10

    south = float(np.mean(inc["SOUTH"]))
    centre_north = float(np.mean(inc["NORTH"] + inc["CENTRE"]))
    assert south < centre_north
    # Semeraro et al. 2020: -44.6%. Loose bound — these are heavy-tailed
    # lognormals, so the realised gap wanders by several points at n=3000.
    assert south / centre_north == pytest.approx(0.554, abs=0.10)


def test_income_level_band_boundaries():
    lo = numbers.INCOME_LEVEL_BANDS_EUR["low_max"]
    hi = numbers.INCOME_LEVEL_BANDS_EUR["high_min"]
    assert numbers.income_level(lo) == "low"           # <= low_max
    assert numbers.income_level(lo + 0.01) == "middle"
    assert numbers.income_level(hi) == "middle"        # not > high_min
    assert numbers.income_level(hi + 0.01) == "high"


def test_every_consumer_gets_a_level_matching_its_income():
    model = ItalyModel(n_consumers=300, n_merchants_per_category=2, n_days=1, seed=9)
    for c in model.consumers:
        assert c.income_level in {"low", "middle", "high"}
        assert c.income_level == numbers.income_level(c.monthly_income)


def test_export_accounts_carries_income_source_and_level():
    model = ItalyModel(n_consumers=60, n_merchants_per_category=2, n_days=5, seed=6)
    model.run()
    for r in model.export_accounts():
        assert r["income_source"] in numbers.INCOME_SOURCE_SHARE
        assert r["income_level"] in {"low", "middle", "high"}
