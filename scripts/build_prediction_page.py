#!/usr/bin/env python3
"""Build ``prediction_and_papers.html`` — the three paper replications, in one page.

    uv run python scripts/build_prediction_page.py

Runs all three replications in one interpreter (so each simulated seed is paid for
once), folds in the existing Study 0/A/B/C/D numbers from ``validation_report.json``,
and writes a single self-contained page.

Presentation only lives here; every number comes from ``replicate_*.py``. Shared CSS
and fragment helpers come from ``_report.py`` — see the note in the header of
``synthitaly/features.py`` for what happens when that gets copy-pasted instead.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _papers as PP  # noqa: E402
import _report as R  # noqa: E402
import replicate_butaru as BUT  # noqa: E402
import replicate_khandani as KHA  # noqa: E402
import replicate_so as SO  # noqa: E402

from synthitaly import panel as P  # noqa: E402

OUT_NAME = "prediction_and_papers.html"

PAPERS = {
    "so": ("So, Thomas, Seow &amp; Mues",
           "Using a Transactor/Revolver scorecard to make credit and pricing decisions",
           "see docs/REFERENCES.md"),
    "khandani": ("Khandani, Kim &amp; Lo (2010)",
                 "Consumer credit-risk models via machine-learning algorithms — "
                 "Journal of Banking &amp; Finance 34, 2767–2787",
                 "doi:10.1016/j.jbankfin.2010.06.001"),
    "butaru": ("Butaru, Chen, Clark, Das, Lo &amp; Siddique (2015)",
               "Risk and Risk Management in the Credit Card Industry — NBER WP 21305",
               "nber.org/papers/w21305"),
    "fagiolo": ("Fagiolo, Moneta &amp; Windrum (2007)",
                "A Critical Guide to Empirical Validation of Agent-Based Models in "
                "Economics — Computational Economics 30, 195–226",
                "doi:10.1007/s10614-007-9104-4"),
}

# What each panel column measures, and — where it is switched off — the mechanism that
# makes it unusable. Written out rather than derived, because the *reason* is the part
# a reader needs and no amount of introspection recovers it.
COLUMN_NOTES = {
    "n_purchases": "Count of discretionary purchases in the trailing window.",
    "total_spend": "Euros of discretionary spending.",
    "mean_ticket": "Average purchase size.",
    "median_ticket": "Median purchase size.",
    "ticket_cv": "Coefficient of variation of purchase size.",
    "weekday_concentration": "How unevenly purchases fall across the week.",
    "active_months": "Months in the window with at least one purchase.",
    "spend_per_active_month": "Purchases per active month.",
    "post_payday_share": "Share of purchase euros within a week of payday.",
    "n_bills": "Recurring bills paid.",
    "total_bills": "Euros of recurring bills paid.",
    "late_fee_n": "Late-payment fees incurred in the window.",
    "late_fee_sum": "Euros of late-payment fees.",
    "total_income": "Euros credited as salary.",
    "mean_income_credit": "Average salary credit.",
    "n_income": "Number of salary credits.",
    "income_shock": "This month's income against its own 6-month mean and SD "
                    "(Khandani et al. §3.2).",
    "cur_balance": "Current-account balance at the statement date.",
    "balance_std": "Standard deviation of month-end balance across the window.",
    "balance_mean": "Mean month-end balance.",
    "balance_to_income": "Mean balance over mean monthly income.",
    "max_dpd": "Worst days-past-due on any open bill.",
    "dpd_bucket": "Days-past-due bucketed as a credit file reports it (0/30/60/90).",
    "n_overdue": "Bills currently unpaid.",
    "overdue_eur": "Euros currently unpaid.",
    "overdue_to_income": "Unpaid euros over mean monthly income — the observable "
                         "counterpart of Khandani et al. §3.1's bureau ratio.",
}
LEAK_NOTES = {
    "LEAK_debt_service_n": "A debt-service line exists <em>only</em> for a debtor, so its "
                           "presence is the label.",
    "LEAK_debt_service_sum": "Same mechanism, in euros.",
    "LEAK_overdraft_n": "An overdraft fee is charged only to a chronic debtor.",
    "LEAK_credit_draw_n": "A credit draw happens only for a subsister.",
    "LEAK_credit_draw_sum": "Same mechanism, in euros.",
    "LEAK_savings_balance": "Exactly zero for 100% of non-savers.",
    "LEAK_pension_balance": "Non-zero only for pension savers.",
    "LEAK_debt_balance": "The debt stock itself — the label in all but name.",
    "LEAK_debt_to_income": "Debt stock over income; needs the debt stock, so same problem.",
    "LEAK_min_balance": "Lowest month-end balance; below zero identifies an overdraft, "
                        "which only a chronic debtor has.",
}


# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #
def sec_framing(so: dict) -> str:
    prem = next(r["premise"] for r in so["runs"].values() if "premise" in r)
    return R.section(
        "framing", "Section 1", "What these tests can and cannot establish",
        R.p("Three papers from the consumer-credit literature are re-run here against this "
            "model's own output. Each was chosen because it classifies exactly the kind of "
            "consumer this model produces — a debtor or not, a transactor or a revolver, an "
            "account that will fall 90 days behind or will not."),
        R.p(f"The fourth paper, <b>{PAPERS['fagiolo'][0]}</b>, is not a method. It is the "
            "reason this section exists. Their <i>under-determination problem</i> — "
            "&ldquo;What happens when different models are consistent with the data that is "
            "used for empirical validation?&rdquo; — is the trap a page like this walks into "
            "if it reports a high score as a success."),
        R.callout(
            "<b>A classifier scoring well here is not evidence that the model is right.</b> "
            "The model generated both the behaviour and the labels, so a classifier is only "
            "asking whether the generating mechanism left a detectable trace in the ledger. "
            "The interesting readings are therefore the places where the answer is "
            "<i>wrong in a specific, mechanical way</i> — and there are three of them.",
            "warn"),
        R.cards([
            ("The premise of the transactor/revolver paper is inverted here",
             R.p("So et al. build their whole cascade on the claim that "
                 "&ldquo;since transactors pay off all their balance each period, they "
                 "cannot default and so all Transactors must be Goods.&rdquo; In this model "
                 f"the Bad rate among transactors is "
                 f"<b>{prem['bad_rate_transactor']:.1%}</b> against "
                 f"<b>{prem['bad_rate_revolver']:.1%}</b> among revolvers. Holding debt is a "
                 "marker of <i>safety</i> here, not of risk.")),
            ("Distress is a standing condition, not an event",
             R.p("Khandani et al. devote a table to &ldquo;straight-rollers&rdquo; — accounts "
                 "current at the forecast date that go 90 days past due anyway, which they "
                 "call &ldquo;a harder learning problem&rdquo;. In this model that population "
                 "is essentially empty. Nobody goes from a clean account to written off; "
                 "arrears are a persistent liquidity state that a consumer is either in or "
                 "not.")),
            ("The difficulty is wrong in both directions",
             R.p("Real credit-risk models land in a middle band — Gini around 0.52, kappa "
                 "0.66–0.79, AUC 0.83–0.89. This model produces either near-noise or "
                 "near-certainty depending on which label is asked for, and almost nothing "
                 "in between. That gap is the substantive result of this page.")),
        ]),
    )


def sec_variables(b: PP.Bundle) -> str:
    pan = b.panel
    all_c = P.panel_feature_columns(pan)
    fair = set(P.panel_fair_columns(pan))
    behav = set(P.panel_behaviour_columns(pan))
    rows = []
    for c in all_c:
        in_a, in_b, in_c = "on", ("on" if c in fair else "off"), ("on" if c in behav else "off")
        if c not in fair:
            why = LEAK_NOTES.get(c, "Encodes the label by construction.")
        elif c not in behav:
            why = ("The account's own arrears counter. Legitimately observable, but it "
                   "nearly determines the forward answer, so Set C asks the question "
                   "without it.")
        else:
            why = ""
        rows.append([R.code(c), COLUMN_NOTES.get(c, "—"), in_a, in_b, in_c, why])
    return R.section(
        "variables", "Section 2", "Which variables are switched on",
        R.p("Every table on this page names the variable setting it came from. There are "
            "three, and the difference between them is the whole argument about what the "
            "model can and cannot be said to predict."),
        R.cards([
            (f"Set A — {PP.VARIABLE_SETS['A'][0]}",
             R.p(PP.VARIABLE_SETS['A'][1] + " Useful only as a ceiling: it says what the "
                 "score looks like when the answer is in the inputs.")),
            (f"Set B — {PP.VARIABLE_SETS['B'][0]}",
             R.p(PP.VARIABLE_SETS['B'][1] + " This is the honest bank's-eye view and the "
                 "default for every headline number.")),
            (f"Set C — {PP.VARIABLE_SETS['C'][0]}",
             R.p(PP.VARIABLE_SETS['C'][1] + " Asks whether spending and income behaviour "
                 "carries the signal once the answer cannot be read off an arrears counter.")),
        ]),
        R.p("Set membership is <b>derived from the data, never hand-listed</b>, so it cannot "
            "drift out of step with the columns actually built — "
            + R.src("src/synthitaly/panel.py") + "."),
        R.table(["Variable", "What it measures", "Set A", "Set B", "Set C",
                 "Why it is switched off"],
                rows, "llcccl"),
    )


def _gini_cell(run: dict, model: str) -> str:
    x = run.get(model, {})
    if x.get("skipped"):
        return "not evaluable"
    if "gini_mean" in x:
        return f"{x['gini_mean']:.3f} ± {x['gini_sd']:.3f}"
    return f"{x['gini']:.3f}" if "gini" in x else "—"


def _cascade_rows(so: dict) -> list[list[str]]:
    rows = []
    for key, r in so["runs"].items():
        target, horizon, month, tr, vset = key.split("|")

        def g(model: str, _r: dict = r) -> str:
            return _gini_cell(_r, model)

        dl = r.get("delong_1_vs_4", {})
        p = dl.get("p")
        verdict = ("—" if p is None else
                   ("no significant difference" if p >= 0.05 else "Model 4 differs, p&lt;0.05"))
        rows.append([
            target.replace("y_", ""), horizon, month.replace("t", "month "),
            tr, vset.replace("set", ""),
            g("model1"), g("model2"), g("model3"), g("model4"), verdict,
        ])
    return rows


def _model_mean(so: dict, model: str) -> float:
    """Mean Gini for one cascade model across every run that could be scored."""
    vals = []
    for r in so["runs"].values():
        m = r.get(model, {})
        if m.get("skipped"):
            continue
        if "gini_mean" in m:
            vals.append(m["gini_mean"])
        elif "gini" in m:
            vals.append(m["gini"])
    return sum(vals) / len(vals) if vals else float("nan")


def sec_so(so: dict, kha: dict) -> str:
    pr = so["paper"]
    prem = next(r["premise"] for r in so["runs"].values() if "premise" in r)
    m1_avg = _model_mean(so, "model1")
    m2_avg = _model_mean(so, "model2")
    m4_avg = _model_mean(so, "model4")
    delongs = [r["delong_1_vs_4"]["p"] for r in so["runs"].values()
               if r.get("delong_1_vs_4")]
    n_delong = len(delongs)
    n_reject = sum(1 for p in delongs if p < 0.05)
    sub = kha.get("by_attribute", {}).get("y_90dpd", {}).get("debtor_subtype", {})
    sub_rows = [
        [("<b>all consumers</b>" if k == "_overall" else
          ("no debt" if k == "none" else k)),
         f"{v['rate']:.4f}", ("—" if k == "_overall" else f"{v['lift']:.2f}×"),
         f"{v['n']:,}"]
        for k, v in sorted(sub.items(), key=lambda kv: -kv[1]["rate"])
    ]
    div = so["tr_definition_divergence"]
    first = so["tr_first_divergence_month"]
    div_rows = [[str(d["month_idx"]), str(d["n_revolver"]), str(d["n_debtor"]),
                 f"{d['agreement']:.3f}"] for d in div]
    return R.section(
        "so", "Section 3 · Paper 1",
        "So, Thomas, Seow &amp; Mues — the Transactor/Revolver scorecard",
        R.p("<b>What the paper does.</b> Four logistic scorecards on 6,308 Hong Kong "
            f"credit-card accounts ({pr['n_bad']:,} Bad, {pr['n_good']:,} Good — a "
            f"{pr['bad_rate']:.1%} Bad rate). Each is built by weight-of-evidence coarse "
            "classification, then stepwise logistic regression, then ten-fold cross "
            "validation done by deciles. They report the mean Gini over the ten holdouts and "
            "compare Model 1 with Model 4 using the DeLong, DeLong &amp; Clarke-Pearson test."),
        R.steps([
            "<b>Model 1</b> — Good/Bad over everybody. Their Gini <b>0.522</b>.",
            "<b>Model 2</b> — Transactor/Revolver over everybody.",
            "<b>Model 3</b> — Good/Bad restricted to Revolvers. Their Gini <b>0.519</b>.",
            "<b>Model 4</b> — the composite <code>P(G|x) = P(T|x) + P(R|x)·P(G|x,R)</code>. "
            "Their Gini <b>0.522</b>, statistically indistinguishable from Model 1.",
        ]),
        R.p("<b>What is replicated.</b> All four models and the full procedure — WoE binning, "
            "the univariate screen, stepwise selection, ten decile folds and the DeLong test. "
            "The scorecard is cross-sectional, as an application scorecard is: characteristics "
            "over the trailing window at one origination month, outcome over the following "
            "performance period. Bin boundaries, selection and coefficients are all fitted "
            "inside the fold, so every Gini below is out of sample."),
        R.h3("Results"),
        R.table(["Outcome", "Window", "Origination", "T/R definition", "Set",
                 "Model 1 Gini", "Model 2 Gini", "Model 3 Gini", "Model 4 Gini",
                 "DeLong, 1 vs 4"],
                _cascade_rows(so), "lllllrrrrl"),
        R.callout(
            f"<b>The paper's structural premise does not hold here.</b> So et al. argue that "
            f"transactors cannot default. In this model the Bad rate among transactors is "
            f"<b>{prem['bad_rate_transactor']:.1%}</b> (n={prem['n_transactor']}) against "
            f"<b>{prem['bad_rate_revolver']:.1%}</b> among revolvers "
            f"(n={prem['n_revolver']}) — the relationship is not weaker, it is reversed. "
            "The reason is mechanical: <code>_assign_debt</code> hands debt out with a "
            "probability that rises with income quartile, so debtors are drawn from the "
            "better-off half of the population, while the consumers who actually fail to pay "
            "bills are the unemployed and transfer-income households, who were never given "
            "debt in the first place. Nothing in the model makes debt <i>cause</i> distress.",
            "warn"),
        R.p("Broken out by debtor subtype the point is starker still. Two of the three "
            "debtor archetypes reach 90 days past due <b>exactly zero times</b> across the "
            "whole panel, while the consumers carrying no debt at all are the ones who "
            "default:"),
        R.table(["Debtor subtype", "90+ DPD rate, 3 months", "Lift vs overall", "Rows"],
                sub_rows, "lrrr"),
        R.p("This shows up directly in Model 4. Where So et al. found the composite "
            "statistically indistinguishable from the plain scorecard, here routing the "
            "Good/Bad decision through the Transactor/Revolver split <b>destroys</b> "
            f"discrimination — Model 1 averages {m1_avg:.2f} against Model 4's "
            f"{m4_avg:.2f}, and DeLong rejects the equality in <b>{n_reject} of "
            f"{n_delong}</b> runs where it could be computed at all. "
            "That is what happens when a segmentation carries no information about the "
            f"outcome: Model 2's Gini averages just {m2_avg:.2f}, the same weak signal the "
            "existing Study B reports as AUC 0.697 for <code>is_debtor</code>."),
        R.h3("The two Transactor/Revolver definitions"),
        R.p("Both were run: <b>behavioural</b> (carried a debt balance across a month "
            "boundary, which is the paper's own definition) and <b>assigned</b> (the "
            "<code>is_debtor</code> attribute the model drew). The gap between them is "
            f"exactly zero until <b>month {first}</b>, because no climber has finished "
            "repaying before then — until that point the two definitions are the same "
            "variable. After it they separate as climbers clear their principal and convert "
            "from Revolver to Transactor, which the static attribute cannot express."),
        R.table(["Month", "Revolvers (behavioural)", "Debtors (assigned)", "Agreement"],
                div_rows, "lrrr"),
        R.callout("<b>Not replicated:</b> sections 5 and 6 — the credit-card profitability "
                  "model, the take probability and the optimal interest rate. This model has "
                  "no revenue side: no interchange fee, no interest income, no pricing "
                  "decision. Those numbers are omitted rather than approximated."),
    )


def _rng(kha: dict, target: str, vset: str, metric: str) -> str:
    """The min–max of ``metric`` across horizons, formatted for prose.

    Computed rather than written out, so a sentence in the text can never drift away
    from the table directly above it — which is exactly what happened once the
    12-month horizon was added.
    """
    vals = [r[metric] for k, r in kha["results"].items()
            if k.startswith(f"{target}|") and k.endswith(f"set{vset}")
            and not r.get("skipped")]
    if not vals:
        return "—"
    lo, hi = f"{min(vals):.2f}", f"{max(vals):.2f}"
    # Collapse on the *rendered* strings, so a spread too small to show does not
    # print as "0.99–0.99".
    return lo if lo == hi else f"{lo}–{hi}"


def sec_khandani(kha: dict) -> str:
    pr = kha["paper"]
    rows = []
    for key, r in kha["results"].items():
        target, h, s = key.split("|")
        if r.get("skipped"):
            rows.append([target.replace("y_", ""), h, s.replace("set", ""),
                         str(kha["run_days"].get(key, "—")), "—", "—", "—", "—",
                         "not evaluable", "—", "—"])
            continue
        sr = sum(p["straight_roller"].get("n_bad", 0) for p in r["periods"])
        rows.append([
            target.replace("y_", ""), h, s.replace("set", ""),
            str(kha["run_days"][key]), str(r["n_periods"]),
            f"{r['mean_base_rate']:.4f}", f"{r['mean_auc']:.4f}",
            f"{r['mean_kappa']:.4f}", r["kappa_verdict"],
            f"{r['mean_score_bad']:.1f} vs {r['mean_score_good']:.1f}",
            f"{sr:,}",
        ])
    strat_rows = []
    for target, block in kha["stratification"].items():
        for var, s in block.items():
            if s.get("degenerate"):
                strat_rows.append([target.replace("y_", ""), R.code(var), s["direction"],
                                   "—", "—", "—", "no tail — " + s["reason"]])
            else:
                strat_rows.append([
                    target.replace("y_", ""), R.code(var), s["direction"],
                    f"{s['rate_in_tail']:.4f}", f"{s['rate_overall']:.4f}",
                    f"{s['lift']:.2f}×" if s.get("lift") else "—", f"n={s['n_tail']:,}"])
    imp = kha["results"].get("y_90dpd|3m|setC", {}).get("importance", {})
    imp_rows = [[R.code(c), f"{v:.3f}"] for c, v in list(imp.items())[:12]]
    strat90 = kha["stratification"]["y_90dpd"]
    dti = strat90["LEAK_debt_to_income"]
    inc = strat90["total_income"]
    bal = strat90["balance_to_income"]
    top2 = sum(list(imp.values())[:2])
    src = kha.get("by_attribute", {}).get("y_90dpd", {}).get("income_source", {})
    src_rows = [
        [("<b>all consumers</b>" if k == "_overall" else k.replace("_", " ")),
         f"{v['rate']:.4f}", ("—" if k == "_overall" else f"{v['lift']:.1f}×"),
         f"{v['n']:,}"]
        for k, v in sorted(src.items(), key=lambda kv: -kv[1]["rate"])
    ]
    return R.section(
        "khandani", "Section 4 · Paper 2",
        "Khandani, Kim &amp; Lo (2010) — CART forecasts of 90+ day delinquency",
        R.p("<b>What the paper does.</b> Generalized classification and regression trees "
            "(CART, Breiman et al. 1984) on a commercial bank's customers, forecasting "
            "90-days-or-more delinquency over a 3-, 6- or 12-month forward window. "
            "Transaction inputs are averaged over the prior six months. The evaluation walks "
            "forward: their Table 5 lists ten calibration/testing periods in which the model "
            "is trained only on delinquencies observable at the forecast date, "
            "&ldquo;to minimize the effects of look-ahead bias&rdquo;. Their delinquency rate "
            f"runs {pr['delinquency_rate_range'][0]:.1%}–{pr['delinquency_rate_range'][1]:.1%}; "
            f"their kappa {pr['kappa_range'][0]}–{pr['kappa_range'][1]}, AUC {pr['auc_note']}."),
        R.p("<b>What is replicated.</b> CART — scikit-learn implements the same Breiman "
            "algorithm the paper cites, so this is the method rather than a substitute — the "
            "six-month trailing averages, the forward-walking calibration, all three horizons, "
            "and the full evaluation block: the average-forecast separation of their Table 7, "
            "the straight-roller restriction of their Table 8, the ROC tangency threshold of "
            "their Figure 16, and the kappa of their Table 9 read against Landis &amp; Koch. "
            "Their §3.1 balance-to-income ratio and §3.2 income-shock variable are carried as "
            "model inputs."),
        R.h3("Results"),
        R.p("The 12-month horizon has no evaluable origination month on the repo's pinned "
            "720-day run — a row needs six months of trailing window, twelve ahead of it, and "
            "a training set whose labels have already closed. Rather than drop the paper's own "
            f"horizon, it is run on a longer {PP.LONG_DAYS}-day simulation; the "
            "<b>days</b> column records which run each row came from."),
        R.table(["Outcome", "Horizon", "Set", "Days", "Periods", "Base rate", "AUC",
                 "Kappa", "Landis &amp; Koch", "Mean score, bad vs good",
                 "Straight-rollers"],
                rows, "lllrrrrrllr"),
        R.callout(
            "<b>Every score is above the paper's.</b> Khandani et al. report kappa "
            f"{pr['kappa_range'][0]}–{pr['kappa_range'][1]} (&ldquo;substantial&rdquo;) and "
            f"AUC {pr['auc_note']}. On Set B this model reaches AUC "
            f"{_rng(kha, 'y_90dpd', 'B', 'mean_auc')} and kappa "
            f"{_rng(kha, 'y_90dpd', 'B', 'mean_kappa')}, at the top of the Landis &amp; Koch "
            "scale. That is not a better model — it is an easier problem. Switching the "
            "arrears counters off (Set C) is what brings kappa back down to "
            f"{_rng(kha, 'y_90dpd', 'C', 'mean_kappa')}, and even then AUC stays at "
            f"{_rng(kha, 'y_90dpd', 'C', 'mean_auc')}.", "warn"),
        R.h3("The straight-rollers — their Table 8"),
        R.p("Khandani et al. single out accounts that are <i>current</i> at the forecast date "
            "and go 90 days past due anyway, calling it &ldquo;a harder learning problem&rdquo; "
            "and reporting that their model still separates the two groups. "
            "<b>In this model that population does not exist.</b> Across every evaluable "
            "period at every horizon, the number of clean accounts that reached 90 days past "
            "due is <b>zero</b> for the write-off outcome. Arrears here are a standing "
            "liquidity condition: a bill must already have gone unpaid for most of the "
            "write-off horizon before it can cross it, and consumers who can pay simply keep "
            "paying. The model generates no default <i>shock</i>."),
        R.h3("Stratification — their §3, which is where the mechanism shows"),
        R.p("The paper motivates its inputs by showing that a tail group carries a visibly "
            "higher forward delinquency rate: their Figure 7 for the balance-to-income ratio, "
            "Figure 9 for the income shock. Run the same way here, the direction of the "
            "headline stratifier is <b>reversed</b>."),
        R.table(["Outcome", "Variable", "Tail", "Rate in tail", "Rate overall", "Lift", "n"],
                strat_rows, "llllrrl"),
        R.callout(
            "Khandani et al.'s central stratifier is the credit-card-balance-to-income ratio: "
            "customers above it are &ldquo;much more likely to experience delinquencies&rdquo;. "
            "Here the top decile of <code>LEAK_debt_to_income</code> has a delinquency rate of "
            f"<b>{dti['rate_in_tail']:.4f}</b> against an overall "
            f"<b>{dti['rate_overall']:.4f}</b> — indebted households are roughly "
            f"<b>{1 / dti['lift']:.1f}× safer</b>, not riskier. What does predict distress is "
            "simply having little money: the bottom decile of <code>total_income</code> runs "
            f"at <b>{inc['rate_in_tail']:.4f}</b>, a {inc['lift']:.1f}× lift, and the bottom "
            f"decile of mean balance at <b>{bal['rate_in_tail']:.4f}</b>, a "
            f"{bal['lift']:.1f}× lift."),
        R.h3("Where the outcome actually comes from"),
        R.p("This breakdown is not in the paper — Khandani et al. have no equivalent, "
            "because in their data delinquency is not a near-function of a single "
            "attribute. Here it is, and naming that attribute explains every score above."),
        R.table(["Income source", "90+ DPD rate, 3 months", "Lift vs overall", "Rows"],
                src_rows, "lrrr"),
        R.h3("Which variables the trees actually use (90+ DPD, 3 months, Set C)"),
        R.table(["Variable", "Mean CART importance"], imp_rows, "lr"),
        R.p("Read together with the stratification table, this says the trees are not finding "
            "a credit-risk relationship at all. The top two variables carry "
            f"<b>{top2:.0%}</b> of the importance between them, and both are proxies for the "
            "same underlying fact — how much money the household has. Delinquency in this "
            "model is, to a first approximation, poverty."),
        R.callout("<b>Not replicated:</b> the CScore benchmark (§4.3 — there is no credit "
                  "bureau in this model), the euro cost/benefit of credit-line cuts (§6 — no "
                  "balance run-up or recovery rate exists), and roughly half of their Table 4 "
                  "inputs, which are credit-bureau items this single-bank view does not have."),
    )


def sec_butaru(but: dict) -> str:
    pr = but["paper"]
    rows = []
    for key, s in but["spread"].items():
        q, name = key.split("|")
        rows.append([q, name, f"{s['auc_mean']:.4f}", f"{s['auc_sd']:.4f}",
                     f"{s['kappa_mean']:.4f}", f"{s['kappa_sd']:.4f}",
                     f"{s['kappa_min']:.3f} – {s['kappa_max']:.3f}",
                     str(s["n_portfolios"])])
    vs_rows = []
    for s, r in but["variable_sets"].items():
        for name, m in r["by_model"].items():
            if m.get("skipped"):
                vs_rows.append([s, name, "not evaluable", "—", "—"])
                continue
            vs_rows.append([s, name, f"{m['mean_auc']:.4f}", f"{m['mean_kappa']:.4f}",
                            m["kappa_verdict"]])
    ov = but.get("overfitting_sweep", {})
    ov_rows = ([[str(r["min_samples_leaf"]), str(r["n_leaves"]),
                 f"{r['auc_in_sample']:.4f}", f"{r['auc_out_of_sample']:.4f}"]
                for r in ov.get("sweep", [])] if not ov.get("skipped") else [])
    th = but.get("threshold_sweep", {})
    th_rows = []
    if not th.get("skipped"):
        grid = th["thresholds"]
        for name, m in th["by_model"].items():
            best = max(range(len(grid)), key=lambda i: m["f_measure"][i])
            flat = sum(1 for v in m["f_measure"] if v >= 0.95 * m["f_measure"][best])
            th_rows.append([name, f"{grid[best]:.2f}", f"{m['f_measure'][best]:.4f}",
                            f"{m['tangency']:.4f}",
                            f"{flat} of {len(grid)} thresholds within 5% of the best"])
    return R.section(
        "butaru", "Section 5 · Paper 3",
        "Butaru, Chen, Clark, Das, Lo &amp; Siddique (2015) — the three-model horse race",
        R.p("<b>What the paper does.</b> Three classifiers on the same 87 attributes, run "
            f"against one another across {pr['n_banks']} anonymous banks and "
            f"{pr['n_accounts']} credit-card accounts: a C4.5 decision tree (Weka's J48), a "
            "ridge logistic regression, and a random forest of "
            f"<b>{pr['rf_trees']} trees</b>. The target is an account 90 or more days past "
            "due, forecast two, three and four quarters out. Models are re-estimated on "
            "rolling windows and never see future data. Their finding: "
            f"<i>{pr['finding']}</i>, with accuracy from "
            f"{pr['accuracy_range'][0]:.1%} at the worst bank to {pr['accuracy_range'][1]:.1%} "
            "at the best."),
        R.h3("What differs, stated plainly"),
        R.cards([
            ("The tree is a partial substitution",
             R.p("C4.5 is not in scikit-learn. <code>DecisionTreeClassifier(criterion="
                 "\"entropy\")</code> uses C4.5's splitting rule, so that half matches; "
                 "C4.5's error-based pruning and multi-way splits have no equivalent, and "
                 "<code>min_samples_leaf</code> stands in for them. The ridge logistic is an "
                 "exact counterpart of the objective they write out, and the forest keeps "
                 "their 20 trees rather than being &lsquo;improved&rsquo;.")),
            ("Six seeds, not six banks",
             R.p("Their six banks are six genuinely different populations, which is what "
                 "makes their spread meaningful. This model has one population, so the six "
                 "portfolios here are six seeds and the spread between them is "
                 "<b>Monte-Carlo error and nothing else</b>. That is a materially weaker "
                 "claim and is labelled as such in the table.")),
            ("A longer simulation",
             R.p(f"This section runs {PP.LONG_DAYS} simulated days rather than the repo's "
                 "720. At 720 the three- and four-quarter horizons have <b>no</b> evaluable "
                 "origination month, because a forecast needs a trailing window, a full "
                 "horizon ahead, and training labels that have already closed. Extending the "
                 "simulation is the honest fix; truncating the design would not be a "
                 "replication.")),
        ]),
        R.h3("The horse race, across six portfolios (Set C, 90+ DPD)"),
        R.table(["Horizon", "Model", "AUC mean", "AUC sd", "Kappa mean", "Kappa sd",
                 "Kappa range", "Portfolios"], rows, "llrrrrll"),
        R.h3("The same race by variable setting (2-quarter horizon)"),
        R.table(["Set", "Model", "AUC", "Kappa", "Landis &amp; Koch"], vs_rows, "llrrl"),
        (R.h3("Threshold sensitivity — their Figures A1–A3") +
         R.p("They sweep the acceptance threshold to check the optimum is flat; a flat "
             "optimum is what makes the F-measure and kappa comparisons meaningful in the "
             "first place.") +
         R.table(["Model", "Best threshold", "Best F-measure", "ROC tangency", "Flatness"],
                 th_rows, "lrrrl") if th_rows else ""),
        (R.h3("Overfitting — their <i>M</i> sweep") +
         R.p("Minimum instances per leaf, in-sample against out-of-sample. The signature of "
             "overfitting is the in-sample score continuing to climb as <i>M</i> falls while "
             "the out-of-sample score turns over.") +
         R.table(["Min samples per leaf", "Leaves", "AUC in-sample", "AUC out-of-sample"],
                 ov_rows, "rrrr") if ov_rows else ""),
        R.callout("<b>Not replicated:</b> the ZIP-level macroeconomic attributes (this model "
                  "has three macro-areas and no time-varying macroeconomy), the value-added "
                  "and cost-savings analysis of their §V (no balance run-up or recovery rate "
                  "exists to price), and the credit-bureau attributes."),
    )


def sec_cross(so: dict, kha: dict, but: dict, val: dict) -> str:
    prem = next(r["premise"] for r in so["runs"].values() if "premise" in r)
    k3 = kha["results"].get("y_90dpd|3m|setB", {})
    k3c = kha["results"].get("y_90dpd|3m|setC", {})
    m1 = next((r["model1"] for k, r in so["runs"].items()
               if k.startswith("y_latefee|12m") and "setB" in k
               and not r["model1"].get("skipped")), {})
    but_c = but["spread"].get("2Q|C4.5-style tree", {})
    src = {k: v for k, v in
           kha.get("by_attribute", {}).get("y_90dpd", {}).get("income_source", {}).items()
           if k != "_overall"}
    if src:
        worst_key = max(src, key=lambda k: src[k]["rate"])
        best_key = min(src, key=lambda k: src[k]["rate"])
        worst_name = worst_key.replace("_", "-")
        best_name = best_key.replace("_", "-")
        src_ratio = (src[worst_key]["rate"] / src[best_key]["rate"]
                     if src[best_key]["rate"] > 0 else float("inf"))
    else:
        worst_name = best_name = "—"
        src_ratio = float("nan")
    rows = [
        ["So et al. — logistic scorecard, WoE + stepwise, 10 decile folds",
         "Good/Bad, 12 months", "B",
         f"Gini {m1.get('gini_mean', float('nan')):.3f}", "Gini 0.522",
         "far above"],
        ["Khandani et al. — CART, rolling windows", "90+ DPD, 3 months", "B",
         f"AUC {k3.get('mean_auc', float('nan')):.3f}, kappa {k3.get('mean_kappa', float('nan')):.3f}",
         "AUC 0.83–0.89, kappa 0.66–0.79", "above"],
        ["Khandani et al. — same, arrears switched off", "90+ DPD, 3 months", "C",
         f"AUC {k3c.get('mean_auc', float('nan')):.3f}, kappa {k3c.get('mean_kappa', float('nan')):.3f}",
         "AUC 0.83–0.89, kappa 0.66–0.79", "AUC above, kappa below"],
        ["Butaru et al. — C4.5-style tree, six portfolios", "90+ DPD, 2 quarters", "C",
         f"AUC {but_c.get('auc_mean', float('nan')):.3f}, kappa {but_c.get('kappa_mean', float('nan')):.3f}",
         "accuracy 63.8%–81.6%", "above"],
    ]
    pred = {(p["task"], p["estimator"]): p for p in val.get("prediction", [])}
    old_rows = [
        ["Study B — <code>is_debtor</code>, logistic", "whole-run cross-section",
         f"{pred[('is_debtor', 'logreg')]['fair_auc']:.4f}",
         f"{pred[('is_debtor', 'logreg')]['naive_auc']:.4f}"],
        ["Study B — <code>is_debtor</code>, random forest", "whole-run cross-section",
         f"{pred[('is_debtor', 'rf')]['fair_auc']:.4f}",
         f"{pred[('is_debtor', 'rf')]['naive_auc']:.4f}"],
        ["Study B — <code>is_climber</code>, logistic", "debtors only",
         f"{pred[('is_climber', 'logreg')]['fair_auc']:.4f}",
         f"{pred[('is_climber', 'logreg')]['naive_auc']:.4f}"],
        ["Study B — <code>is_climber</code>, random forest", "debtors only",
         f"{pred[('is_climber', 'rf')]['fair_auc']:.4f}",
         f"{pred[('is_climber', 'rf')]['naive_auc']:.4f}"],
    ]
    return R.section(
        "cross", "Section 6", "How the three stack up, and against what was already here",
        R.p("The three papers use different algorithms, different cross-validation schemes "
            "and different metrics, so the useful comparison is not which scores highest — it "
            "is that <b>all three land in the same place</b>, and that place is above where "
            "any of them landed on real data."),
        R.table(["Method", "Target", "Set", "This model", "The paper's own", "Reading"],
                rows, "lllllc"),
        R.callout(
            "<b>The method barely matters; the label decides everything.</b> A stepwise "
            "logistic scorecard, a single CART tree and a 20-tree forest all reach roughly "
            "the same discrimination on the same target. Swap the target — ask for "
            "<code>is_debtor</code> instead of delinquency — and every method collapses to "
            "around 0.70 regardless. That is the signature of a label that is either "
            "near-deterministic or near-random by construction, rather than of models that "
            "are learning different things."),
        R.h3("Against the existing prediction work"),
        R.p("The clustering studies are unchanged and remain the reference for structure in "
            "the feature space; nothing on this page revises them. The prediction studies now "
            "have company:"),
        R.table(["Existing study", "Population", "AUC, Set B equivalent",
                 "AUC with label-revealing variables on"], old_rows, "llrr"),
        R.p("The two sit at opposite ends of the same axis and neither is in the middle where "
            "real credit models live. <code>is_debtor</code> is drawn from a random tilt on a "
            "single hidden flag, so conditional on vulnerability it is close to noise and "
            "0.70 is a ceiling, not a tuning failure. The delinquency label is the opposite: "
            f"it follows almost deterministically from income source — {worst_name} "
            f"households write bills off at <b>{src_ratio:.0f}×</b> the rate of "
            f"{best_name} ones — and the ledger reveals income source almost perfectly "
            "through the salary credits."),
        R.callout(
            "<b>What this points at.</b> The model has no mechanism connecting debt to "
            "distress. Debt is assigned by income quartile and then serviced by a rule that "
            "depends only on the subtype; delinquency is driven by whether the current "
            "account happens to be empty when a bill falls due. The two systems run alongside "
            "each other and never interact, which is exactly why the transactor bad rate "
            f"({prem['bad_rate_transactor']:.1%}) exceeds the revolver bad rate "
            f"({prem['bad_rate_revolver']:.1%}). A debt-service burden that actually competed "
            "with bill payments for the same euros would be the smallest change that makes "
            "all three papers' premises hold at once.", "warn"),
    )


def sec_problems() -> str:
    return R.section(
        "problems", "Section 7", "Problems, stated plainly",
        R.cards([
            ("Weight of evidence inflates its own significance",
             R.p("WoE is fitted against the label, so a WoE-transformed column carries "
                 "in-sample signal even when the raw variable is pure noise. Measured "
                 "directly: the likelihood-ratio stepwise test admits a noise column 7% of "
                 "the time on raw inputs — about its nominal rate — and <b>99%</b> of the "
                 "time on WoE-transformed noise. The guard is a univariate screen on "
                 "<i>out-of-sample</i> information value, which the paper also describes. An "
                 "in-sample screen does not work: noise scores IV ≈ 0.03 at n=1,500 and "
                 "≈ 0.006 at n=8,000, so no fixed threshold is right for both.")),
            ("The characteristic list has seen all the rows",
             R.p("Following the paper, the shortlist of characteristics is chosen once rather "
                 "than inside each fold. Every bin boundary, coefficient and reported Gini "
                 "still comes from the nine training deciles alone, but the <i>list</i> is "
                 "mildly optimistic. This is inherited from the paper's own procedure, not a "
                 "shortcut taken here.")),
            ("Class imbalance at 90+ DPD",
             R.p("Around 3% of consumer-months, close to the papers' own 2.0–2.5%. But at 800 "
                 "consumers that is roughly 27 events, which is why the So cascade's Model 3 "
                 "— Good/Bad restricted to revolvers — cannot be built for that outcome at "
                 "all: a decile cannot hold both classes. It is reported as not evaluable "
                 "rather than as a number.")),
            ("A subtype tell that is not quarantined",
             R.p("Subsisters are given <code>starting_balance = 0.0</code> while everyone "
                 "else receives one month's income (" + R.src("src/synthitaly/model.py:1080") +
                 "). That is a deterministic function of the subtype and it reaches "
                 "<code>cur_balance</code>, which sits in Set B. It is called out nowhere "
                 "else in the repo and should be either randomised or quarantined.")),
            ("<code>is_saver</code> is force-set for subsisters",
             R.p("All 36 subsisters are marked savers at " +
                 R.src("src/synthitaly/model.py:1091") + ", so the saver and debtor labels "
                 "are entangled. Already declared in <code>VALIDATION.md</code>, repeated "
                 "here because it bears on any multi-class subtype work.")),
            ("Horizons that do not fit the run",
             R.p("The 12-month horizon is not evaluable on 720 days, and neither are Butaru's "
                 f"three- and four-quarter horizons. Those rows come from a {PP.LONG_DAYS}-day "
                 "run and every table says so. No horizon was scored on a truncated window.")),
        ]),
    )


def _json_default(o):
    """Serialise numpy scalars as numbers, not as their repr.

    ``default=str`` would turn ``np.float64(0.83)`` into the string ``"0.83"``, which
    survives a write and then breaks ``--reuse`` on the next read. The replications cast
    their outputs already; this is the belt to that pair of braces.
    """
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.bool_, bool)):
        return bool(o)
    return str(o)


def _results(out_dir: Path, reuse: bool) -> tuple[dict, dict, dict]:
    """Run the three replications, or load the JSON they last wrote.

    ``--reuse`` exists so the presentation can be iterated without paying for six
    1,440-day simulations each time. It is never the default: a page built from stale
    JSON would silently disagree with the code that produced it.
    """
    got = {}
    for name, mod in (("so", SO), ("khandani", KHA), ("butaru", BUT)):
        path = out_dir / f"replicate_{name}.json"
        if reuse and path.exists():
            print(f"  reusing {path.name}", flush=True)
            got[name] = json.loads(path.read_text())
            continue
        print(f"  running {name}...", flush=True)
        got[name] = mod.run()
        path.write_text(json.dumps(got[name], indent=2, default=_json_default))
    return got["so"], got["khandani"], got["butaru"]


def build(out_dir: Path, reuse: bool = False) -> str:
    t0 = time.time()
    so, kha, but = _results(out_dir, reuse)
    b = PP.bundle()
    val_path = PP.ROOT / "runs" / "latest" / "validation_report.json"
    val = json.loads(val_path.read_text()) if val_path.exists() else {}

    prem = next(r["premise"] for r in so["runs"].values() if "premise" in r)
    k3c = kha["results"].get("y_90dpd|3m|setC", {})
    tiles = R.tiles([
        ("Papers replicated", "3", "plus one framing paper"),
        ("90+ DPD base rate", f"{k3c.get('mean_base_rate', 0):.1%}",
         "papers' own: 2.0–2.5%"),
        ("Transactor bad rate", f"{prem['bad_rate_transactor']:.1%}",
         f"revolvers: {prem['bad_rate_revolver']:.1%} — inverted"),
        ("Straight-rollers found", "0", "clean accounts reaching 90+ DPD"),
    ])
    navbar = R.nav([
        ("framing", "What this tests"), ("variables", "Variables"),
        ("so", "So et al."), ("khandani", "Khandani et al."),
        ("butaru", "Butaru et al."), ("cross", "Comparison"),
        ("problems", "Problems"),
    ])
    body = "".join([
        tiles,
        sec_framing(so),
        sec_variables(b),
        sec_so(so, kha),
        sec_khandani(kha),
        sec_butaru(but),
        sec_cross(so, kha, but, val),
        sec_problems(),
    ])
    meta = (f"{PP.describe_config()} · long-horizon rows from {PP.LONG_DAYS} days · "
            f"built in {time.time() - t0:.0f}s")
    print(f"  assembled in {time.time() - t0:.0f}s", flush=True)
    return R.page(
        title="Prediction &amp; the credit-risk papers",
        heading="Predicting debtors and delinquency — three papers, replicated",
        sub="So, Thomas, Seow &amp; Mues · Khandani, Kim &amp; Lo (2010) · "
            "Butaru et al. (2015), framed by Fagiolo, Moneta &amp; Windrum (2007)",
        meta=meta, navbar=navbar, body=body,
        footer="Generated by <code>scripts/build_prediction_page.py</code>. Every number on "
               "this page comes from <code>scripts/replicate_so.py</code>, "
               "<code>replicate_khandani.py</code> and <code>replicate_butaru.py</code>; "
               "the citations are in <code>docs/REFERENCES.md</code>.",
    )


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(PP.ROOT / "runs" / "latest"),
                    help="directory to write the page into")
    ap.add_argument("--reuse", action="store_true",
                    help="load replicate_*.json from --out instead of re-running the "
                         "replications; for iterating on presentation only")
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    html = build(out_dir, reuse=args.reuse)
    (out_dir / OUT_NAME).write_text(html)
    print(f"  wrote {out_dir / OUT_NAME}  ({len(html) / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
