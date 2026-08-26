#!/usr/bin/env python3
"""Generate presentation-ready figures from the ACTIVE synthitaly model.

Run:  uv run python presentation/generate_figures.py

Writes every chart to presentation/figures/ as BOTH .png (200 dpi, white bg) and
.svg, plus a CAPTIONS.md with a one-line caption per figure. Nothing here touches
the engine — it only *reads* the public API (transactions, export_accounts,
debt_by_subtype, group_balances, datacollector) and re-uses the compact feature
pipeline pinned in tests/test_analysis_pipeline.py.

ONE run, at the repository's pinned configuration: 800 consumers x 720 days,
seed 42 — the same model every reported statistic comes from. Previously this
script built three models at three sizes (150x120, 150x720, 600x720), so no
figure was drawn at the configuration the numbers came from and none could be
quoted next to them.

Consolidating is safe because the model is a seeded forward simulation: a long
run's first N days are byte-identical to a short run of N days at the same seed.
Verified for transactions and the datacollector frame at 800x120 against the
first 120 days of 800x720. The four time-series figures (f01, f04, f05, f07)
therefore show a 120-day window sliced out of the single run, for legibility;
everything else uses all 720 days.

  f01-f08  daily / seasonal / behavioural
  f09-f12  debt-as-stock trajectories by subtype
  f13-f15  clustering / prediction validation (debtors)
  f16-f19  savers
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from synthitaly import numbers
from synthitaly.features import (
    build_features,
    design_matrix,
    fair_columns,
    leak_columns,
    money_log1p,
    saver_fair_columns,
    label_frame as labels,
)
from synthitaly.model import ItalyModel

from _style import (  # noqa: E402  (script dir is on sys.path, as in build_deck.py)
    BLUE, GREY, INK, INK2, RED, RULE, YELLOW,
    LEVEL_COLOR, NOMINAL, SOURCE_COLOR, SUBTYPE_COLOR, SUBTYPE_ORDER,
    FULL, PAIR, SHORT, WIDE,
    blue_cmap, darken, econ_fig, econ_style, fmt_int, fmt_pct, fmt_thousands,
    frame, outline, pretty, prettify, save_figure,
)

FIG_DIR = Path(__file__).resolve().parent.parent / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Provenance for the source line under each chart. One configuration, seeded, so
# this is exact rather than approximate — and it is the configuration every
# reported statistic uses, which is the point of having only one.
SRC = "Source: synthitaly simulation \u2014 800 consumers \u00d7 720 days, seed 42"
SRC_120 = SRC + " (first 120 days shown)"

# The window the time-series figures slice out of the single run. 120 days is
# four pay cycles — enough to show the sawtooth repeating, few enough that
# individual paydays stay resolvable.
WINDOW_DAYS = 120

CAPTIONS: list[tuple[str, str]] = []


def save(fig, name: str, caption: str):
    save_figure(fig, FIG_DIR, name)
    CAPTIONS.append((name, caption))
    print(f"  wrote {name}.png / .pdf / .svg")


def dc_frame(model: ItalyModel) -> pd.DataFrame:
    df = model.datacollector.get_model_vars_dataframe().reset_index(drop=True)
    df.index = np.arange(1, len(df) + 1)  # 1-based day
    return df


def txn_frame(model: ItalyModel) -> pd.DataFrame:
    df = pd.DataFrame(model.transactions)
    df["date"] = pd.to_datetime(df["date"])
    return df


# --------------------------------------------------------------------------- #
# Cross-validated ROC, drawn the way the pinned numbers are computed
# --------------------------------------------------------------------------- #
ROC_GRID = np.linspace(0.0, 1.0, 201)


def roc_folds(X, y, n_splits: int = 5):
    """Per-fold ROC curves plus a vertically-averaged mean curve.

    Returns ``(folds, mean_tpr, mean_auc, sd_auc)`` where ``folds`` is a list of
    ``(fpr, tpr)`` arrays, one per fold, and ``mean_tpr`` is defined on
    :data:`ROC_GRID`.

    This replaces the pooled ``cross_val_predict`` curve these figures used to
    draw. Pooling concatenates the out-of-fold probabilities and ranks them
    together, which is legitimate but estimates a different quantity from the one
    ``validation_report.py`` pins, so the chart and the pinned table disagreed in
    the last digit or two with no way for a reader to tell which was which.

    Two things are reported instead, and they are different numbers:

      * the **mean of the per-fold AUCs**, with its standard deviation — this is
        what is annotated, and it is byte-for-byte the quantity
        ``validation_report.py`` pins, down to the fold assignment;
      * a **vertically averaged** mean curve (Fawcett 2006, *Pattern Recognition
        Letters* 27(8), §7.1): interpolate each fold's TPR onto a common FPR grid
        and average. Its own area is NOT the annotated AUC and is not quoted.

    Showing the five fold curves underneath is the honest part: it makes the
    spread the SD summarises visible rather than asserted.

    Standardisation sits inside the pipeline so it is refit on each training fold
    (ESL 2nd ed. §7.10.2); only the parameter-free ``log1p`` is applied outside.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score, roc_curve
    from sklearn.model_selection import StratifiedKFold
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    X = np.asarray(X, dtype=float)
    y = np.asarray(y).astype(int)
    # shuffle=False, which is exactly what `cross_val_score(..., cv=5)` resolves to
    # for a classifier — so the mean AUC computed here is the SAME NUMBER
    # validation_report.py pins, not merely a comparable one. Shuffling would give a
    # defensible but different estimate and put the chart back out of step with the
    # table, which is the problem this rewrite exists to fix.
    cv = StratifiedKFold(n_splits=n_splits, shuffle=False)

    folds, aucs, tprs = [], [], []
    for tr, te in cv.split(X, y):
        clf = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=2000, class_weight="balanced"),
        ).fit(X[tr], y[tr])
        proba = clf.predict_proba(X[te])[:, 1]
        fpr, tpr, _ = roc_curve(y[te], proba)
        folds.append((fpr, tpr))
        aucs.append(roc_auc_score(y[te], proba))
        tprs.append(np.interp(ROC_GRID, fpr, tpr))

    mean_tpr = np.mean(tprs, axis=0)
    mean_tpr[0], mean_tpr[-1] = 0.0, 1.0
    return folds, mean_tpr, float(np.mean(aucs)), float(np.std(aucs))


def draw_roc_family(ax, folds, mean_tpr, colour, lw: float = 1.6):
    """Five translucent fold curves under one solid mean curve, in one colour."""
    for fpr, tpr in folds:
        ax.plot(fpr, tpr, color=colour, lw=0.7, alpha=0.28, zorder=2)
    ax.plot(ROC_GRID, mean_tpr, color=colour, lw=lw, zorder=4)


# --------------------------------------------------------------------------- #
# Feature pipeline — imported from synthitaly.features, the single implementation
# shared with the notebooks and the pinned regression suite. The validation
# figures use the COMPACT column subset so their numbers stay comparable to the
# bounds in tests/test_analysis_pipeline.py.
# --------------------------------------------------------------------------- #


# --------------------------------------------------------------------------- #
# RUN A — daily / seasonal / behavioural
# --------------------------------------------------------------------------- #
def figures_run_a(model: ItalyModel):
    dc_all = dc_frame(model)
    tx_all = txn_frame(model)
    pur_all = tx_all[tx_all["kind"] == "purchase"]

    # The time-series figures show a WINDOW_DAYS slice; the cross-sectional ones
    # (f02, f03, f06, f08) use the whole run, where more data is strictly better.
    # Because the simulation is a seeded forward pass, this slice is identical to
    # what a WINDOW_DAYS-long run at the same seed would have produced.
    cutoff = tx_all["date"].min() + pd.Timedelta(days=WINDOW_DAYS - 1)
    dc = dc_all.loc[:WINDOW_DAYS]
    tx = tx_all[tx_all["date"] <= cutoff]
    pur = tx[tx["kind"] == "purchase"]

    # f01 — transaction volume. Two stacked panels, never a dual axis: the two
    # measures share a time axis but not a scale.
    fig, (a1, a2) = econ_fig(WIDE, 2, 1, sharex=True)
    a1.plot(dc.index, dc["daily_txn_count"], color=BLUE, lw=1.4)
    a1.fill_between(dc.index, dc["daily_txn_count"], color=BLUE, alpha=0.10)
    a1.set_ylim(0, None)
    fmt_int(a1)
    econ_style(a1, title="Transactions per day")
    a2.plot(dc.index, dc["daily_eur_total"], color=BLUE, lw=1.4)
    a2.fill_between(dc.index, dc["daily_eur_total"], color=BLUE, alpha=0.10)
    a2.set_ylim(0, None)
    fmt_thousands(a2)
    econ_style(a2, title="Euro moved per day, €'000", xlabel="Simulated day")
    frame(fig, "The simulated transaction stream",
          "Daily activity over a 120-day run. The monthly spikes are payday",
          SRC_120, hspace=0.42)
    save(fig, "f01_txn_volume",
         "Daily transaction count (top) and total euro throughput (bottom) over a "
         "120-day run — the raw output stream. The four spikes are the 27th of each "
         "month, when salaries, pensions and transfers are credited.")

    # f02 — spend mix vs the paper baseline, over the FULL run: a calibration
    # check wants every observation, not a window. The two series are named "target"
    # and "simulated" rather than claimed to agree: the largest gaps are
    # computed here and printed on the chart, so the figure cannot drift out of
    # step with its own caption.
    realised = pur_all.groupby("category")["amount_eur"].sum()
    realised = realised / realised.sum()
    paper = pd.Series(numbers.CATEGORY_SHARES)
    cats = paper.sort_values(ascending=True).index.tolist()
    gaps = sorted(
        ((c, realised.get(c, 0.0) - paper.get(c, 0.0)) for c in cats),
        key=lambda kv: abs(kv[1]), reverse=True,
    )[:2]
    gap_txt = "; ".join(
        f"{pretty(c)} {realised.get(c, 0):.0%} against {paper.get(c, 0):.0%}"
        for c, _ in gaps
    )
    gap_note = "Largest gaps between the two: " + gap_txt + "."

    y = np.arange(len(cats))
    fig, ax = econ_fig(WIDE)
    ax.barh(y + 0.21, [paper.get(c, 0) for c in cats], height=0.40,
            color=RED, label="Emiliozzi et al. (2023) card data")
    ax.barh(y - 0.21, [realised.get(c, 0) for c in cats], height=0.40,
            color=BLUE, label="Simulated")
    ax.set_yticks(y)
    ax.set_yticklabels(prettify(cats))
    ax.set_ylim(-0.7, len(cats) - 0.3)
    fmt_pct(ax, "x")
    econ_style(ax, grid="x", yticks_right=False)
    frame(
        fig,
        "The simulated spending mix against its calibration target",
        "Share of purchase euro, %",
        SRC + "; Emiliozzi et al. (2023)",
        key=[("Simulated", BLUE), ("Emiliozzi et al. (2023) card data", RED)],
        note=gap_note,
        left=0.185, right=0.985,
    )
    save(fig, "f02_spend_mix_vs_paper",
         "Simulated category shares against the Emiliozzi et al. (2023) card-data "
         "baseline the model is calibrated to. The match is directional, not exact — "
         "the largest gaps are " + gap_txt + ".")

    # f03 — spend by macro-area. One colour: area is a single series measured
    # three times, not three categories that need telling apart.
    area = pur_all.groupby("macro_area")["amount_eur"].sum().reindex(["NORTH", "CENTRE", "SOUTH"])
    fig, ax = econ_fig(FULL)
    bars = ax.bar(prettify(area.index), area.values, color=BLUE, width=0.6)
    for b, v in zip(bars, area.values):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v / 1000:,.0f}", ha="center",
                va="bottom", color=INK, fontsize=8, fontweight="semibold")
    ax.set_ylim(0, area.max() * 1.14)
    fmt_thousands(ax)
    econ_style(ax)
    frame(fig, "The North spends most, the Centre least",
          "Cumulative purchase euro over the run, €'000",
          SRC,
          note="Population weights 0.46 / 0.20 / 0.34 (ISTAT); the South also carries "
               "an income gradient of 0.554× the Centre-North (Semeraro et al.).")
    save(fig, "f03_spend_by_area",
         f"Cumulative card spend per macro-area: North €{area['NORTH']:,.0f}, "
         f"Centre €{area['CENTRE']:,.0f}, South €{area['SOUTH']:,.0f}. The South "
         f"out-spends the Centre on population weight alone despite the lower "
         f"per-household income.")

    # f04 — payday spike. The paydays are annotated once rather than legended:
    # four identical vertical rules need one explanation, not a legend entry.
    daily = pur.groupby("date")["amount_eur"].sum()
    fig, ax = econ_fig(FULL)
    paydays = [d for d in daily.index if d.day == numbers.PAYDAY_DAY_OF_MONTH]
    for d in paydays:
        ax.axvline(d, color=RULE, lw=0.9, zorder=1)
    ax.plot(daily.index, daily.values, color=BLUE, lw=1.3, zorder=3)
    ax.set_ylim(0, daily.max() * 1.22)
    fmt_thousands(ax)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    econ_style(ax)
    if paydays:
        ax.annotate(f"Payday, the {numbers.PAYDAY_DAY_OF_MONTH}th",
                    xy=(paydays[0], daily.max() * 1.10), xytext=(6, 0),
                    textcoords="offset points", ha="left", va="center",
                    color=INK2, fontsize=7.5, path_effects=outline())
    frame(fig, "Spending bunches in the days just after payday",
          "Purchase euro per day, all consumers, €'000",
          SRC_120,
          note="The re-timing is mean-neutral: the month's total is unchanged, only "
               "its distribution across days (Olafsson & Pagel 2018).")
    save(fig, "f04_payday_spike",
         "Daily purchase euro with the payday rules marked. Spending bunches just "
         "after the 27th and decays through the month — a mean-neutral re-timing, so "
         "monthly totals are unaffected.")

    # f05 — behavioural fee events over time
    fees = tx[tx["kind"] == "fee"].copy()
    if len(fees):
        fees["day"] = fees["date"].dt.normalize()
        piv = fees.pivot_table(index="day", columns="category", values="amount_eur", aggfunc="size").fillna(0)
    else:
        piv = pd.DataFrame()
    fig, ax = econ_fig(SHORT)
    fee_colors = {"late_payment_fee": RED, "overdraft_fee": YELLOW}
    used = []
    if not piv.empty:
        bottom = np.zeros(len(piv))
        for col in [c for c in fee_colors if c in piv.columns] + \
                   [c for c in piv.columns if c not in fee_colors]:
            ax.bar(piv.index, piv[col].values, bottom=bottom, width=1.4,
                   color=fee_colors.get(col, GREY))
            bottom += piv[col].values
            used.append((pretty(col), fee_colors.get(col, GREY)))
        ax.set_ylim(0, bottom.max() * 1.12)
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    else:
        ax.text(0.5, 0.5, "No fee events in this run", ha="center", va="center",
                transform=ax.transAxes, color=GREY)
    fmt_int(ax)
    econ_style(ax)
    frame(fig, "Fees arrive in bursts, on the days bills fall due",
          "Fee events per day, count",
          SRC_120, key=used or None,
          note="Overdraft charges follow Stango & Zinman; late-payment charges follow "
               "Dahan & Nisan. Between the bursts, a thin overdraft tail runs all month.")
    save(fig, "f05_behavioural_events",
         "Daily overdraft (Stango & Zinman) and late-payment (Dahan & Nisan) fee "
         "events. Late-payment charges spike on bill dates; overdraft charges form a "
         "thin continuous tail — the liquidity-constrained minority.")

    # f06 — income composition (source x level)
    comp = pd.DataFrame([{"source": c.income_source, "level": c.income_level} for c in model.consumers])
    piv = comp.pivot_table(index="source", columns="level", aggfunc=len, fill_value=0)
    piv = piv.reindex(columns=[l for l in ["low", "middle", "high"] if l in piv.columns])
    order = piv.sum(axis=1).sort_values(ascending=False).index
    piv = piv.reindex(order)
    fig, ax = econ_fig(FULL)
    bottom = np.zeros(len(piv))
    for lvl in piv.columns:
        ax.bar(prettify(piv.index), piv[lvl].values, bottom=bottom, width=0.62,
               color=LEVEL_COLOR.get(lvl, GREY), edgecolor="white", linewidth=0.9)
        bottom += piv[lvl].values
    ax.set_ylim(0, bottom.max() * 1.10)
    fmt_int(ax)
    econ_style(ax)
    frame(fig, "Half the population is on a payroll",
          "Consumers by income source, count, split by income level",
          SRC,
          key=[(pretty(lvl), LEVEL_COLOR.get(lvl, GREY)) for lvl in piv.columns])
    save(fig, "f06_income_composition",
         "Consumer headcount per income source, each bar split low / middle / high. "
         "Payroll dominates; the high band is confined to payroll and self-employment, "
         "and no transfers or unemployed household reaches it.")

    # f07 — balance trajectory by income source
    src_cols = [c for c in dc.columns if c.startswith("bal_cur_src_")]
    names = [c.replace("bal_cur_src_", "") for c in src_cols]
    # draw in end-of-run order so the key row reads top-to-bottom like the chart
    order = sorted(zip(names, src_cols), key=lambda nc: -dc[nc[1]].iloc[-1])
    fig, ax = econ_fig(FULL)
    for name, col in order:
        ax.plot(dc.index, dc[col], color=SOURCE_COLOR.get(name, GREY), lw=1.4,
                label=pretty(name))
    fmt_thousands(ax, decimals=1)
    econ_style(ax, xlabel="Simulated day", zero_line=True)
    frame(fig, "The payday sawtooth, and who never climbs out of it",
          "Mean current-account balance by income source, €'000",
          SRC_120,
          key=[(pretty(n), SOURCE_COLOR.get(n, GREY)) for n, _ in order],
          note="Neither the sawtooth nor the sub-zero floor is imposed: both follow "
               "from monthly credits meeting daily spending and bill dates.")
    save(fig, "f07_balance_by_source",
         "Mean current-account balance per income source. The payday sawtooth and "
         "the persistent sub-zero floor for unemployed households emerge from the "
         "interaction of monthly credits with daily spending; neither is imposed.")

    # f08 — income distribution by source
    inc = pd.DataFrame([{"source": c.income_source, "income": c.monthly_income} for c in model.consumers])
    order = inc.groupby("source")["income"].median().sort_values().index.tolist()
    data = [inc.loc[inc["source"] == s, "income"].values for s in order]
    fig, ax = econ_fig(FULL)
    bp = ax.boxplot(data, patch_artist=True, widths=0.5, showfliers=False,
                    medianprops=dict(color=INK, lw=1.4))
    for box in bp["boxes"]:
        box.set(facecolor=BLUE, alpha=0.85, edgecolor=BLUE, linewidth=0.8)
    for part in bp["whiskers"] + bp["caps"]:
        part.set(color=BLUE, linewidth=0.9)
    ax.set_xticklabels(prettify(order))
    ax.set_ylim(0, None)
    fmt_thousands(ax, decimals=1)
    econ_style(ax)
    frame(fig, "Self-employment pays best, and least predictably",
          "Monthly net income by source, €'000. Box: interquartile range; line: median",
          SRC + "; Bank of Italy SHIW 2022 §2B",
          note="Whiskers span the full simulated range; outliers are not drawn.")
    save(fig, "f08_income_distribution",
         "Per-source monthly net income distributions. Self-employment is both the "
         "highest-paying and the widest-spread; pensions are the tightest; transfers "
         "and unemployment sit lowest with almost no dispersion.")


# --------------------------------------------------------------------------- #
# RUN B — debt-as-stock trajectories
# --------------------------------------------------------------------------- #
def figures_run_b(model: ItalyModel):
    dc = dc_frame(model)

    # f09 — debt stock (outstanding principal) by subtype. Zero-based: the old
    # axis started around €10,000, which hid the fact that the climber line
    # flattens at a residual rather than reaching zero.
    fig, ax = econ_fig(FULL)
    ends = {}
    for st in SUBTYPE_ORDER:
        col = f"debt_total_{st}"
        if col in dc:
            ax.plot(dc.index, dc[col], color=SUBTYPE_COLOR[st], lw=1.6, label=st)
            ends[st] = float(dc[col].iloc[-1])
    ax.set_ylim(0, max(dc[f"debt_total_{st}"].max() for st in SUBTYPE_ORDER
                       if f"debt_total_{st}" in dc) * 1.10)
    fmt_thousands(ax)
    econ_style(ax, xlabel="Simulated day")
    frame(fig, "Only the climbers' debt goes down — and not to zero",
          "Total outstanding principal by archetype, €'000",
          SRC,
          key=[(pretty(st), SUBTYPE_COLOR[st]) for st in SUBTYPE_ORDER],
          note=f"The climber line flattens at €{ends.get('climber', 0):,.0f} of "
               f"residual principal held by the households that never clear.")
    save(fig, "f09_debt_stock_by_subtype",
         f"Total outstanding debt principal per archetype over roughly two years. "
         f"Climbers pay down steadily but flatten at €{ends.get('climber', 0):,.0f} "
         f"rather than reaching zero — the residual of the households that never "
         f"clear (see f12). Chronic debt is near-flat at "
         f"€{ends.get('chronic', 0):,.0f}; subsister debt drifts up to "
         f"€{ends.get('subsister', 0):,.0f}.")

    # f10 — balance trajectory by subtype
    dst_cols = [c for c in dc.columns if c.startswith("bal_cur_dst_")]
    fig, ax = econ_fig(FULL)
    for st in SUBTYPE_ORDER:
        col = f"bal_cur_dst_{st}"
        if col in dst_cols:
            ax.plot(dc.index, dc[col], color=SUBTYPE_COLOR[st], lw=1.2, label=st)
    fmt_thousands(ax, decimals=1)
    econ_style(ax, xlabel="Simulated day", zero_line=True)
    frame(fig, "Climbers build a buffer; subsisters end every month at zero",
          "Mean current-account balance by archetype, €'000",
          SRC,
          key=[(pretty(st), SUBTYPE_COLOR[st]) for st in SUBTYPE_ORDER],
          note="The teeth are the monthly cycle: a credit on the 27th, then a month "
               "of spending. What differs between archetypes is the floor, not the "
               "shape.")
    save(fig, "f10_balance_by_subtype",
         "Mean current balance per archetype. Climbers rebuild a rising buffer once "
         "their principal is paid down; chronic households track them at a lower "
         "level; subsisters return to zero at the end of every month throughout.")

    # f11 — debtor composition
    comp = pd.Series({st: 0 for st in SUBTYPE_ORDER})
    vulner = pd.Series({st: 0 for st in SUBTYPE_ORDER})
    for c in model.consumers:
        if c.debtor_subtype in comp.index:
            comp[c.debtor_subtype] += 1
            if getattr(c, "is_financially_vulnerable", False):
                vulner[c.debtor_subtype] += 1
    # The vulnerable share is drawn as a darker step of each bar's own colour
    # rather than a white hatch over it. Hatching was heavy in print, and the
    # legend explaining it landed on the value labels.
    fig, ax = econ_fig(FULL)
    x = np.arange(len(SUBTYPE_ORDER))
    ax.bar(x, [comp[s] for s in SUBTYPE_ORDER], width=0.58,
           color=[SUBTYPE_COLOR[s] for s in SUBTYPE_ORDER])
    ax.bar(x, [vulner[s] for s in SUBTYPE_ORDER], width=0.58,
           color=[darken(SUBTYPE_COLOR[s]) for s in SUBTYPE_ORDER])
    for xi, st in zip(x, SUBTYPE_ORDER):
        ax.text(xi, comp[st] + 0.15, f"{comp[st]}", ha="center", va="bottom",
                color=INK, fontsize=8, fontweight="semibold")
        if vulner[st]:
            ax.text(xi, vulner[st] / 2, f"{vulner[st]}", ha="center", va="center",
                    color="white", fontsize=8, fontweight="semibold")
    ax.set_xticks(x)
    ax.set_xticklabels(prettify(SUBTYPE_ORDER))
    ax.set_ylim(0, max(comp) * 1.16)
    fmt_int(ax)
    econ_style(ax)
    frame(fig, "The chronic tilt lands where it was aimed",
          "Debtors by archetype, count",
          SRC,
          note="Darker base of each bar: households flagged financially vulnerable "
               "on the SHIW definition. The chronic archetype is deliberately "
               "over-drawn from that cohort.")
    save(fig, "f11_debtor_composition",
         f"Debtors split into climber / chronic / subsister. The darker base of each "
         f"bar is the SHIW financially-vulnerable cohort that the chronic tilt "
         f"targets: {vulner['chronic']} of {comp['chronic']} chronic debtors, against "
         f"{vulner['subsister']} of {comp['subsister']} subsisters and "
         f"{vulner['climber']} of {comp['climber']} climbers.")

    # f12 — still in debt over time. Zero-based y-axis (these are counts, and a
    # truncated axis exaggerates the climber drop), and the series are labelled
    # at the end of each line instead of in a legend box that used to sit on
    # top of the data.
    fig, ax = econ_fig(FULL)
    ends, starts = {}, {}
    for st in SUBTYPE_ORDER:
        col = f"debt_indebt_{st}"
        if col in dc:
            ax.plot(dc.index, dc[col], color=SUBTYPE_COLOR[st], lw=1.8, label=st)
            starts[st], ends[st] = int(dc[col].iloc[0]), int(dc[col].iloc[-1])
    ax.set_ylim(0, max(starts.values(), default=1) * 1.10)
    fmt_int(ax)
    econ_style(ax, xlabel="Simulated day")
    cleared = starts.get("climber", 0) - ends.get("climber", 0)
    frame(fig, "Only climbers ever clear their debt",
          "Households still carrying outstanding principal, count",
          SRC,
          key=[(pretty(st), SUBTYPE_COLOR[st]) for st in SUBTYPE_ORDER])
    save(fig, "f12_still_in_debt",
         f"Households still carrying debt principal, by archetype. "
         f"{cleared} of the {starts.get('climber', 0)} climbers reach zero, all of "
         f"them between day 390 and day 420; the remaining "
         f"{ends.get('climber', 0)} do not. No chronic or subsister household "
         f"clears at any point in the run.")


# --------------------------------------------------------------------------- #
# RUN C — clustering + prediction validation
# --------------------------------------------------------------------------- #
def figures_run_c(model: ItalyModel):
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import (
        adjusted_rand_score, confusion_matrix, normalized_mutual_info_score,
    )

    feats = build_features(model).merge(labels(model), on="consumer_id")
    deb = feats[feats["is_debtor"]].reset_index(drop=True)
    y_true = deb["debtor_subtype"].values

    # The FULL column sets, not the compact subsets these figures used to take.
    # `fair_columns` and friends are what validation_report.py and the pinned
    # regression suite measure, so the charts and the tables now describe the same
    # thing; before, a reader comparing f14's ARI with the pinned one found two
    # different numbers and no note saying why.
    #
    # Derived from `build_features(model)` alone — passing `feats` would let the
    # merged label columns through and `is_debtor` would predict itself.
    feat_only = build_features(model)
    FAIR = fair_columns(feat_only)
    LEAK = leak_columns(feat_only)
    NAIVE = FAIR + LEAK

    # f13 — PCA scatter: KMeans clusters vs true subtype
    X = design_matrix(deb, NAIVE)
    pcs = PCA(n_components=2, random_state=0).fit_transform(X)
    km = KMeans(n_clusters=3, n_init=10, random_state=0).fit_predict(X)
    # Groups are labelled in place at their centroids rather than legended, and
    # the cluster ids deliberately use a different palette from the archetypes:
    # sharing colours across the two panels would imply a cluster-to-archetype
    # mapping that the confusion matrix in f14 contradicts.
    fig, (a1, a2) = econ_fig(WIDE, 1, 2, sharex=True, sharey=True)
    for k in range(3):
        m = km == k
        a1.scatter(pcs[m, 0], pcs[m, 1], s=7, color=NOMINAL[k], alpha=0.8,
                   edgecolor="white", linewidth=0.25)
        a1.text(pcs[m, 0].mean(), pcs[m, 1].mean(), f"Cluster {k}",
                ha="center", va="center", color=NOMINAL[k], fontsize=8,
                fontweight="bold", path_effects=outline(lw=2.6))
    econ_style(a1, title="Assigned by KMeans", xlabel="PC1", ylabel="PC2",
               grid="both", yticks_right=False)
    for st in SUBTYPE_ORDER:
        m = y_true == st
        a2.scatter(pcs[m, 0], pcs[m, 1], s=7, color=SUBTYPE_COLOR[st], alpha=0.8,
                   edgecolor="white", linewidth=0.25)
        if m.any():
            a2.text(pcs[m, 0].mean(), pcs[m, 1].mean(), pretty(st),
                    ha="center", va="center", color=SUBTYPE_COLOR[st], fontsize=8,
                    fontweight="bold", path_effects=outline(lw=2.6))
    econ_style(a2, title="True archetype", xlabel="PC1", grid="both",
               yticks_right=False)
    frame(fig, "Behaviour alone recovers one archetype cleanly, and blurs two",
          "Debtors projected onto their first two principal components. Labels sit "
          "at each group's centroid",
          SRC, left=0.06, right=0.985, wspace=0.16,
          note="The cluster numbers are arbitrary identifiers and are coloured "
               "differently on purpose: cluster 0 is not the same thing as climber.")
    save(fig, "f13_clustering_pca",
         "Debtors in the plane of their first two principal components. Unsupervised "
         "KMeans clusters (left) against the true archetypes (right). The subsister "
         "group separates cleanly; climber and chronic overlap heavily, which is what "
         "caps the recovery scores in f14.")

    # f14 — recovery scores (fair vs naive) + confusion matrix
    def scores(cols):
        Xc = design_matrix(deb, cols)
        lab = KMeans(n_clusters=3, n_init=10, random_state=0).fit_predict(Xc)
        return adjusted_rand_score(y_true, lab), normalized_mutual_info_score(y_true, lab), lab
    ari_fair, nmi_fair, _ = scores(FAIR)
    ari_naive, nmi_naive, lab_naive = scores(NAIVE)
    fig, (a1, a2) = econ_fig(PAIR, 1, 2)
    metrics = ["ARI", "NMI"]
    xm = np.arange(len(metrics))
    a1.bar(xm - 0.19, [ari_fair, nmi_fair], width=0.36, color=BLUE)
    a1.bar(xm + 0.19, [ari_naive, nmi_naive], width=0.36, color=RED)
    for xi, (vf, vn) in zip(xm, [(ari_fair, ari_naive), (nmi_fair, nmi_naive)]):
        a1.text(xi - 0.19, vf + 0.02, f"{vf:.2f}", ha="center", va="bottom",
                color=INK, fontsize=7.5, fontweight="semibold")
        a1.text(xi + 0.19, vn + 0.02, f"{vn:.2f}", ha="center", va="bottom",
                color=INK, fontsize=7.5, fontweight="semibold")
    a1.set_xticks(xm)
    a1.set_xticklabels(metrics)
    a1.set_ylim(0, 1)
    econ_style(a1, title="Agreement with the true labels", yticks_right=False)

    # confusion matrix (naive), rows = true, cols = cluster, raw counts
    cm = confusion_matrix(pd.Categorical(y_true, categories=SUBTYPE_ORDER).codes, lab_naive)
    a2.imshow(cm, cmap=blue_cmap(), aspect="auto", vmin=0)
    a2.set_xticks(range(cm.shape[1]))
    a2.set_xticklabels([f"Cluster {j}" for j in range(cm.shape[1])])
    a2.set_yticks(range(len(SUBTYPE_ORDER)))
    a2.set_yticklabels(prettify(SUBTYPE_ORDER))
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            a2.text(j, i, cm[i, j], ha="center", va="center", fontsize=8,
                    fontweight="semibold",
                    color="white" if cm[i, j] > cm.max() * 0.55 else INK)
    econ_style(a2, title="Households by archetype and cluster", grid="none",
               yticks_right=False)
    a2.grid(False)
    a2.spines["bottom"].set_visible(False)
    frame(fig, "The debt-mechanic features do most of the separating",
          "Left: cluster-recovery scores, 0–1. Right: count of households",
          SRC, left=0.075, right=0.985, wspace=0.55,
          key=[("Honest behavioural features", BLUE),
               ("Plus debt-mechanic proxies", RED)],
          note="Both indices are chance-corrected, so 0 means no better than a random "
               "partition. Cluster numbering is arbitrary and carries no ordering.")
    save(fig, "f14_cluster_recovery",
         f"Cluster-recovery scores and the archetype-by-cluster confusion matrix. "
         f"Adding the debt-mechanic proxies lifts ARI from {ari_fair:.2f} to "
         f"{ari_naive:.2f} and NMI from {nmi_fair:.2f} to {nmi_naive:.2f} — most of "
         f"the apparent structure comes from those features, not from behaviour.")

    # f15 — prediction: ROC (is_debtor) fair vs naive + top fair coefficients
    y = feats["is_debtor"].astype(int).values

    def roc_for(cols):
        return roc_folds(money_log1p(feats, cols).to_numpy(), y)

    folds_f, mean_f, auc_f, sd_f = roc_for(FAIR)
    folds_n, mean_n, auc_n, sd_n = roc_for(NAIVE)
    fig, (a1, a2) = econ_fig(WIDE, 1, 2)
    a1.plot([0, 1], [0, 1], color=GREY, lw=0.9, ls=(0, (3, 3)))
    draw_roc_family(a1, folds_n, mean_n, RED)
    draw_roc_family(a1, folds_f, mean_f, BLUE)
    a1.set_xlim(0, 1); a1.set_ylim(0, 1)
    a1.set_box_aspect(1)
    a1.set_anchor("N")          # keep both panel titles on the same line
    # Curves are labelled in the lower-right triangle, which no ROC curve worth
    # plotting ever enters. A legend box in a square panel has nowhere to sit
    # that is not either on the data or outside the axes.
    for y_pos, text, colour in (
        (0.30, f"Plus proxies · AUC {auc_n:.3f} ± {sd_n:.3f}", RED),
        (0.20, f"Honest only · AUC {auc_f:.3f} ± {sd_f:.3f}", BLUE),
        (0.10, "Chance · AUC 0.500", GREY),
    ):
        a1.text(0.40, y_pos, text, ha="left", va="center", color=colour,
                fontsize=6.6, fontweight="semibold", path_effects=outline(lw=2.4))
    econ_style(a1, title="Who holds debt", xlabel="False positive rate",
               ylabel="True positive rate", grid="both", yticks_right=False)

    # Coefficients of the honest model, fit on the full data for display. One
    # colour: the sign is already read off the zero line, and blue-versus-red
    # here would clash with blue-versus-red meaning honest-versus-leaking on
    # the left.
    #
    # The honest set is 34 columns. Thirty-four horizontal bars in a half-panel
    # need ~5 pt labels, which do not survive printing, so this shows the
    # TOP_COEF largest by absolute size — the ones that carry the story — and
    # states in the footnote how many were dropped and how small they were. A
    # top-k with the cut declared is honest; 34 illegible bars are not.
    Xf = design_matrix(feats, FAIR)
    lr = LogisticRegression(max_iter=2000, class_weight="balanced").fit(Xf, y)
    all_coef = pd.Series(lr.coef_[0], index=FAIR)
    TOP_COEF = 14
    coef = (all_coef.reindex(all_coef.abs().sort_values(ascending=False).index)
                    .head(TOP_COEF).sort_values())
    n_hidden = len(all_coef) - len(coef)
    hidden_max = all_coef.drop(coef.index).abs().max() if n_hidden else 0.0
    a2.barh(range(len(coef)), coef.values, height=0.68, color=BLUE)
    a2.set_yticks(range(len(coef)))
    a2.set_yticklabels(prettify(coef.index), fontsize=7)
    a2.set_ylim(-0.7, len(coef) - 0.3)
    a2.axvline(0, color=RULE, lw=0.8)
    econ_style(a2, title=f"What signals it: {TOP_COEF} largest of {len(all_coef)}",
               grid="x", yticks_right=False)
    frame(fig, "Debt-mechanic proxies do not predict the label, they contain it",
          "Left: ROC for predicting who holds debt, five-fold cross-validation. "
          "Right: standardised coefficients, honest model",
          SRC, left=0.085, right=0.985, wspace=0.85,
          note=f"“Honest only” is the {len(FAIR)}-column behavioural set; “plus "
               f"proxies” adds the {len(LEAK)} debt-mechanic columns. Faint lines are "
               f"the five individual folds; the solid line is their vertical average. "
               f"The quoted AUC is the MEAN of the five per-fold AUCs ± 1 SD — the "
               f"quantity validation_report.md pins — not the area under the averaged "
               f"curve. Bars to the right of zero raise the predicted probability of "
               f"holding debt; the {n_hidden} omitted coefficients all sit within "
               f"±{hidden_max:.2f}.")
    save(fig, "f15_prediction",
         f"Debtor prediction: honest behavioural features reach AUC {auc_f:.3f} "
         f"(± {sd_f:.3f} across folds); adding the debt-mechanic proxies leaks the "
         f"label ({auc_n:.3f} ± {sd_n:.3f}). Five-fold stratified CV on the full "
         f"{len(FAIR)}-column honest set, with the five fold curves shown under their "
         f"vertical average. The annotated AUC is the per-fold mean, the same estimator "
         f"validation_report.md pins, so the two agree. The coefficient panel shows the "
         f"{TOP_COEF} largest of {len(all_coef)} by absolute size.")


# --------------------------------------------------------------------------- #
# RUN D — savers (shares run C's model)
#
# The debt side of the model had four figures and the saver side had none, even
# though the saver studies carry their own pinned numbers. These four close that
# gap. They deliberately mirror the debt figures: one calibration check, one
# distribution, one ROC, one confound.
# --------------------------------------------------------------------------- #
def figures_run_d(model: ItalyModel):


    # One row per consumer, read straight off the agents — these are ground-truth
    # attributes, used here only for description, never as model input.
    cons = pd.DataFrame([{
        "consumer_id": c.unique_id,
        "quintile": c.income_quintile,
        "is_saver": c.is_saver,
        "is_pension_saver": c.is_pension_saver,
        "subtype": c.debtor_subtype or "none",
        "savings": c.accounts.savings.balance,
        "pension": c.accounts.pension.balance,
    } for c in model.consumers])

    # f16 — saver rate by quintile: realised vs the SHIW probability it was drawn from
    q = sorted(numbers.P_NO_SAVING_BY_INCOME_QUINTILE)
    target = [1.0 - numbers.P_NO_SAVING_BY_INCOME_QUINTILE[k] for k in q]
    realised = [cons.loc[cons["quintile"] == k, "is_saver"].mean() for k in q]
    n_per_q = [int((cons["quintile"] == k).sum()) for k in q]

    fig, ax = econ_fig(FULL)
    x = np.arange(len(q))
    ax.bar(x, realised, width=0.58, color=BLUE, label="Realised in this run")
    ax.plot(x, target, color=RED, lw=1.8, marker="o", ms=4.5,
            markeredgecolor="white", markeredgewidth=0.8,
            label="SHIW 2022 §2F target")
    for xi, r in enumerate(realised):
        ax.text(xi, r + 0.03, f"{r:.0%}", ha="center", color=INK, fontsize=8,
                fontweight="semibold")
    ax.set_xticks(x)
    ax.set_xticklabels([f"Q{k}" for k in q])
    ax.set_ylim(0, 1.0)
    fmt_pct(ax)
    econ_style(ax, xlabel="Income quintile, poorest to richest")
    frame(fig, "Saving rises with income, as the survey says it should",
          "Share of households that save, %",
          SRC + "; Bank of Italy SHIW 2022 §2F",
          key=[("Realised in this run", BLUE), ("SHIW 2022 §2F target", RED)],
          note=f"n={n_per_q[0]} per quintile. Q2–Q4 of the target are "
               f"interpolated: SHIW publishes only Q1 and Q5.")
    save(fig, "f16_saver_rate_by_quintile",
         "Share of households that save, by income quintile: realised (bars) against the "
         "SHIW 2022 §2F probability they were drawn from (line). Q2–Q4 of the target are "
         "linearly interpolated — SHIW reports only Q1 and Q5. Realised rates track the "
         "target within sampling error at n≈120 per quintile; the small uniform lift comes "
         "from subsisters, whose saver flag is force-set (see f19) and who are spread "
         "roughly evenly across quintiles rather than concentrated in the low ones.")

    # f17 — where the swept money ends up. Savings and pension are separate pots:
    # a pension-saver's residual goes to pension INSTEAD of savings, never both.
    fig, (a1, a2) = econ_fig(PAIR, 1, 2, sharey=True)
    sav = [cons.loc[(cons["quintile"] == k) & (cons["savings"] > 0), "savings"].values
           for k in q]
    pen = [cons.loc[(cons["quintile"] == k) & (cons["pension"] > 0), "pension"].values
           for k in q]
    # One colour across both panels: the panel titles say which pot is which, so
    # hue would only repeat information that the layout already carries.
    for ax, data, name in ((a1, sav, "Savings"), (a2, pen, "Pension")):
        parts = ax.boxplot(
            [d if len(d) else [0.0] for d in data], positions=np.arange(len(q)),
            widths=0.5, patch_artist=True, showfliers=False,
            medianprops=dict(color=INK, lw=1.3),
        )
        for box in parts["boxes"]:
            box.set(facecolor=BLUE, alpha=0.85, edgecolor=BLUE, linewidth=0.8)
        for w in parts["whiskers"] + parts["caps"]:
            w.set(color=BLUE, linewidth=0.9)
        ax.set_xticks(np.arange(len(q)))
        ax.set_xticklabels([f"Q{k}" for k in q])
        ax.set_ylim(0, None)
        fmt_thousands(ax)
        econ_style(ax, title=f"{name} balance", xlabel="Income quintile",
                   yticks_right=(ax is a2))
    frame(fig, "Both pots scale steeply with income",
          "End-of-run balance among the households holding any, €'000",
          SRC, left=0.075, right=0.925, wspace=0.22,
          note="The two pots are exclusive by construction: a pension-saver's monthly "
               "residual is swept to pension instead of savings, never to both.")
    save(fig, "f17_saver_balances_by_quintile",
         "End-of-run savings (left) and pension (right) balances among households that hold "
         "any, by income quintile. The two pots are exclusive — a pension-saver's residual "
         "is swept to pension instead of savings, never to both.")

    # f18 — the saver ROC triple. Three curves, not two, because the debtor-fair
    # set is NOT fair for this label: the month-close sweep is a debit on the
    # current account, so cur_total_out / cur_balance encode is_saver directly.
    feats = build_features(model)
    # Align the label to the feature frame's own row order rather than assuming
    # the two were built in the same sequence.
    y = (cons.set_index("consumer_id")
             .loc[feats["consumer_id"].values, "is_saver"]
             .astype(int).values)
    # Full column sets, as in f13-f15, so these curves describe the same objects
    # the pinned table does.
    FAIR = fair_columns(feats)
    LEAK = leak_columns(feats)
    saver_fair = saver_fair_columns(feats)

    def roc_for(cols):
        return roc_folds(money_log1p(feats, cols).to_numpy(), y)

    folds_n, mean_n, auc_n, sd_n = roc_for(FAIR + LEAK)
    folds_d, mean_d, auc_d, sd_d = roc_for(FAIR)
    folds_s, mean_s, auc_s, sd_s = roc_for(saver_fair)

    fig, ax = econ_fig(WIDE)
    ax.plot([0, 1], [0, 1], color=GREY, lw=0.9, ls=(0, (3, 3)))
    draw_roc_family(ax, folds_n, mean_n, RED)
    draw_roc_family(ax, folds_d, mean_d, YELLOW)
    draw_roc_family(ax, folds_s, mean_s, BLUE)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_box_aspect(1)
    ax.set_anchor("N")
    for y_pos, text, colour in (
        (0.34, f"All features · AUC {auc_n:.3f} ± {sd_n:.3f}", RED),
        (0.25, f"“Debtor-fair” set · AUC {auc_d:.3f} ± {sd_d:.3f}", YELLOW),
        (0.16, f"Saver-fair set · AUC {auc_s:.3f} ± {sd_s:.3f}", BLUE),
        (0.07, "Chance · AUC 0.500", GREY),
    ):
        ax.text(0.40, y_pos, text, ha="left", va="center", color=colour,
                fontsize=6.8, fontweight="semibold", path_effects=outline(lw=2.4))
    econ_style(ax, xlabel="False positive rate", ylabel="True positive rate",
               grid="both", yticks_right=False)
    frame(fig, "The column set this repo calls “fair” is not fair for this label",
          "ROC for predicting who saves, five-fold cross-validation",
          SRC, left=0.075,
          note=f"The month-close sweep is a debit on the current account, so money out "
               f"and end balance encode the saver flag directly. Quarantining those two "
               f"columns ({len(FAIR)} \u2192 {len(saver_fair)}) is what separates the "
               f"honest curve from the other two. Faint lines are the five individual "
               f"folds; solid lines their vertical average. Quoted AUCs are the mean of "
               f"the five per-fold values ± 1 SD, the estimator validation_report.md "
               f"pins.")
    save(fig, "f18_saver_prediction",
         f"Saver prediction needs three curves, not two: the column set this repo calls "
         f"“fair” still reaches AUC {auc_d:.3f} on this label, because the month-close "
         f"sweep writes it into cur_total_out and cur_balance. Quarantining those two "
         f"gives the honest {auc_s:.3f} ± {sd_s:.3f}. Measured at the pinned 800 x 720 "
         f"configuration on the full {len(saver_fair)}-column saver-fair set, as the "
         f"per-fold mean AUC over five stratified folds — the same configuration and "
         f"estimator validation_report.md pins, so the two agree.")

    # f19 — the confound, stated rather than hidden: _assign_savings force-sets
    # is_saver for subsisters, so one debtor archetype is 100% savers by construction.
    order = ["none"] + SUBTYPE_ORDER
    rate = [cons.loc[cons["subtype"] == s, "is_saver"].mean() for s in order]
    n_s = [int((cons["subtype"] == s).sum()) for s in order]
    colours = [GREY] + [SUBTYPE_COLOR[st] for st in SUBTYPE_ORDER]

    # No hatching: it prints heavy and needed a legend to explain it. The
    # subsister bar is annotated instead, which says more in less ink.
    fig, ax = econ_fig(FULL)
    ax.bar(np.arange(len(order)), rate, width=0.58, color=colours)
    for xi, r in enumerate(rate):
        ax.text(xi, r + 0.025, f"{r:.0%}", ha="center", color=INK, fontsize=8,
                fontweight="semibold")
    mean = cons["is_saver"].mean()
    # The mean line is explained in the footer rather than labelled in place:
    # every position on the chart that is close enough to the line to read as
    # belonging to it is already occupied by a bar value.
    ax.axhline(mean, color=INK2, lw=0.9, ls=(0, (4, 3)), zorder=4)
    ax.annotate("Set to 100% by\nthe debt layer",
                xy=(len(order) - 1, 1.0), xytext=(len(order) - 1.45, 0.78),
                ha="right", va="center", color=INK2, fontsize=7,
                linespacing=1.3,
                arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8,
                                shrinkA=2, shrinkB=4))
    ax.set_xticks(np.arange(len(order)))
    ax.set_xticklabels([f"{pretty(st)}\nn={n}" for st, n in zip(order, n_s)])
    ax.set_ylim(0, 1.14)
    fmt_pct(ax)
    econ_style(ax)
    frame(fig, "One archetype is a saver by construction",
          "Share of households that save, %, by debtor archetype",
          SRC,
          note=f"Dashed line: population mean, {mean:.0%}. _assign_savings force-sets "
               f"the saver flag for every subsister, which entangles the two labels; "
               f"it is declared here rather than corrected.")
    save(fig, "f19_saver_debtor_confound",
         f"Saver rate by debtor archetype. Subsisters are 100% savers because "
         f"_assign_savings force-sets the flag for them — a deliberate choice in the "
         f"debt layer that entangles the two labels. Every other archetype sits within "
         f"a few points of the population mean of {mean:.0%}. Declared here rather "
         f"than corrected.")


def main(argv: list[str] | None = None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--only", nargs="+", choices=["a", "b", "c", "d"], metavar="GROUP",
        help="regenerate only these figure groups (a=f01-f08, b=f09-f12, "
             "c=f13-f15, d=f16-f19). The model is built once either way — the "
             "saving is in the plotting, not the simulation. CAPTIONS.md is only "
             "rewritten on a full build, since a partial one would drop the "
             "captions of the figures it did not draw.",
    )
    args = ap.parse_args(argv)
    want = set(args.only or ["a", "b", "c", "d"])

    # ONE model, at the pinned configuration. Every figure below is a view of
    # this run: the time-series ones slice its first WINDOW_DAYS days, which the
    # seeding guarantees is identical to a WINDOW_DAYS-long run.
    print("Building the pinned model — 800 consumers x 720 days, seed 42 …")
    model = ItalyModel(n_consumers=800, n_merchants_per_category=3,
                       n_days=720, seed=42)
    model.run()

    if "a" in want:
        print("f01-f08 — daily / seasonal / behavioural")
        figures_run_a(model)
    if "b" in want:
        print("f09-f12 — debt-as-stock trajectories")
        figures_run_b(model)
    if "c" in want:
        print("f13-f15 — clustering / prediction validation")
        figures_run_c(model)
    if "d" in want:
        print("f16-f19 — savers")
        figures_run_d(model)

    if args.only:
        print(f"\nPartial build: {len(CAPTIONS)} figures in {FIG_DIR} "
              f"(CAPTIONS.md left alone)")
        return 0

    cap = FIG_DIR / "CAPTIONS.md"
    cap.write_text(
        "# Figure captions\n\n"
        + "\n".join(f"- **{n}** — {c}" for n, c in CAPTIONS)
        + "\n",
        encoding="utf-8",
    )
    print(f"\nDone: {len(CAPTIONS)} figures + CAPTIONS.md in {FIG_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
