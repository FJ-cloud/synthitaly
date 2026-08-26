#!/usr/bin/env python3
"""Build the savers & debt results page.

    uv run python scripts/build_savers_debt_page.py [--out runs/latest]

Reads ``<out>/validation_report.json`` and writes ``<out>/savers_and_debt.html``.

The two labels are deliberately presented together. Read alone, each is a modest
result; read as a pair they make a methodological point that neither makes on its
own — clustering recovers a label only when that label happens to lie along a
dominant axis of variation, while prediction only needs the signal to be present
at all. The debtor label fails the first test and mostly fails the second; the
saver label fails the first and passes the second.

Both halves also carry a leak that had to be found before the honest number could
be quoted, and the two leaks are different in kind. That is worth a section.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "presentation" / "scripts"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from _inline import captions  # noqa: E402
from _report import (  # noqa: E402
    FIG,
    callout,
    cards,
    esc,
    gallery,
    nav,
    num,
    p,
    page,
    pre,
    section,
    src,
    table,
    tiles,
)

from synthitaly import numbers as N  # noqa: E402

DEBT_FIGS = ["f09_debt_stock_by_subtype", "f10_balance_by_subtype",
             "f11_debtor_composition", "f12_still_in_debt"]
STUDY_FIGS = ["f13_clustering_pca", "f14_cluster_recovery", "f15_prediction"]
SAVER_FIGS = ["f16_saver_rate_by_quintile", "f17_saver_balances_by_quintile",
              "f18_saver_prediction", "f19_saver_debtor_confound"]


# --------------------------------------------------------------------------- #
def headline(rep: dict) -> str:
    lab = rep["labels"]
    clus = {c["features"]: c for c in rep["clustering"]}
    pred = {(r["task"], r["estimator"]): r for r in rep["prediction"]}
    spred = {r["estimator"]: r for r in rep["saver_prediction"]}
    sk2 = next(c for c in rep["saver_clustering"]
               if c["features"] == "saver-fair" and c["k"] == 2)
    return tiles([
        ("debtors", num(lab["n_debtors"]),
         " · ".join(f"{k} {v}" for k, v in lab["subtype_mix"].items())),
        ("savers", num(lab["n_savers"]),
         f"of {rep['config']['n_consumers']} households"),
        ("debtor ARI", num(clus["fair"]["ari"], 3),
         f"leaked control {num(clus['naive']['ari'], 3)}"),
        ("is_debtor AUC", num(pred[("is_debtor", "logreg")]["fair_auc"], 3),
         f"leaked control {num(pred[('is_debtor', 'logreg')]['naive_auc'], 3)}"),
        ("saver ARI", num(sk2["ari"], 3), "clustering finds nothing"),
        ("is_saver AUC", num(spred["logreg"]["saver_fair_auc"], 3),
         f"before the leak fix {num(spred['logreg']['debtor_fair_auc'], 3)}"),
    ])


# --------------------------------------------------------------------------- #
def debt_mechanics() -> str:
    opening = N.DEBT_OPENING_MONTHS
    arch = table(
        ["Archetype", "Monthly repayment", "Overdraft floor", "Opening current balance",
         "What the principal does"],
        [
            ["<b>climber</b>",
             f"the full SHIW service (×{N.CLIMBER_REPAYMENT_MULT:g})",
             "€0 — cannot go negative",
             "one month's income",
             "falls to zero, then the household <b>leaves debt permanently</b>"],
            ["<b>chronic</b>",
             "<b>interest only</b> — exactly the month's accrual",
             "−1 month's debt service (the only archetype that may overdraw)",
             "one month's income",
             "flat by construction; drifts up when the interest is unaffordable, "
             "never clears"],
            ["<b>subsister</b>",
             f"a token ×{N.SUBSISTER_REPAYMENT_MULT:g} of the service",
             "€0, but may draw new credit instead",
             "<b>forced to €0</b> — no cushion at all",
             f"drifts up; capped at {N.SUBSISTER_DEBT_CEILING_MULT:g}× the opening "
             f"principal ({N.SUBSISTER_DEBT_CEILING_MULT * opening:.0f} months of service)"],
        ], "lllll",
    )
    return section(
        "debt-mechanics", "Part 1 · Debt", "How the three archetypes are built",
        p("Who holds debt is a <b>SHIW</b> roll on income quartile. What kind of debtor they "
          "are is not in any paper — it is a modelling choice, tilted by SHIW's own "
          "financially-vulnerable definition so that the chronic cohort lands on genuinely "
          "distressed households rather than comfortable high earners."),
        pre(
            "c.has_debt              = numbers.has_debt(rng, c.income_quartile)      # SHIW\n"
            "c._monthly_debt_service = numbers.annual_debt_service(rng, q) / 12.0    # SHIW\n"
            "c.debt_service_ratio    = c._monthly_debt_service / c.monthly_income\n"
            "c.is_financially_vulnerable = (q <= 2 and c.debt_service_ratio > 0.30)  # SHIW\n"
            "c.debtor_subtype        = numbers.sample_debtor_subtype(rng, vulnerable)\n"
            f"c.debt_balance          = monthly_service * {opening:g}   # opening principal"
        ),
        p(f"The tilt: a vulnerable debtor is drawn "
          f"{N.DEBTOR_SUBTYPE_SHARE_VULNERABLE['chronic']:.0%} chronic, a resilient one "
          f"{N.DEBTOR_SUBTYPE_SHARE_RESILIENT['climber']:.0%} climber "
          f"({src('numbers.py:238-247')}). Interest accrues at "
          f"{N.DEBT_MONTHLY_INTEREST_RATE:.1%}/month <b>whether or not the payment is made</b>, "
          f"so a skipped month grows the debt — the realistic direction."),
        arch,
        callout(
            "<b>The whole debt-as-stock layer is a modelling choice, and the code says so.</b> "
            "SHIW gives debt <i>participation</i> and an annual debt-service <i>flow</i>. It "
            "never gives a principal, an interest rate, or a repayment archetype. Only the "
            "<i>direction</i> of the vulnerability tilt is paper-grounded — every magnitude "
            "here is ours, and is swept.", "warn"),
    )


def debt_results(rep: dict, caps: dict) -> str:
    clus = {c["features"]: c for c in rep["clustering"]}
    rows = []
    for feat in ("naive", "fair"):
        c = clus[feat]
        rows.append([
            "<b>naive</b> (with debt mechanics)" if feat == "naive" else "<b>fair</b> only",
            num(c["n_features"]), num(c["ari"], 4), num(c.get("nmi"), 4),
            num(c.get("silhouette"), 4),
        ])
    clus_t = table(["Feature set", "vars", "ARI", "NMI", "silhouette"], rows, "lrrrr")

    prows = []
    for r in rep["prediction"]:
        prows.append([
            f"<code>{esc(r['task'])}</code>", esc(r["estimator"]),
            num(r["naive_auc"], 4), num(r["fair_auc"], 4),
        ])
    pred_t = table(["Target", "estimator", "naive AUC<br>(control)", "fair AUC<br>(honest)"],
                   prows, "llrr")

    return section(
        "debt-results", "Part 1 · Debt", "Can the archetypes be found in the ledger?",
        p("Two ways of asking. <b>Clustering</b> (unsupervised — would an analyst stumble on "
          "these groups?) and <b>prediction</b> (supervised — is the signal there at all, "
          "given the answer to train on?)."),
        "<h3>Study A — clustering the debtor subpopulation</h3>", clus_t,
        "<h3>Study B — predicting who holds debt, and who digs out</h3>", pred_t,
        callout(
            "<b>The ceiling on the debtor task is structural, not a tuning failure.</b> "
            "<code>sample_debtor_subtype()</code> draws the archetype from a random tilt on a "
            "single hidden binary flag. Conditional on vulnerability the label is close to "
            "noise, so no honest behavioural feature can recover it and no amount of tuning "
            "will move it. What separability does exist arrives <i>after</i> assignment, from "
            "the divergent repayment rules — subsisters draw on a credit line, which is a "
            "distinct mechanic and hence nearly perfectly separable; climbers and chronics "
            "differ only in repayment speed and get merged."),
        gallery(DEBT_FIGS, caps),
        gallery(STUDY_FIGS, caps),
    )


# --------------------------------------------------------------------------- #
def saver_mechanics() -> str:
    q = sorted(N.P_NO_SAVING_BY_INCOME_QUINTILE)
    rows = [[f"Q{k}", f"{N.P_NO_SAVING_BY_INCOME_QUINTILE[k]:.3f}",
             f"{1 - N.P_NO_SAVING_BY_INCOME_QUINTILE[k]:.1%}",
             "observed" if k in (1, 5) else "<span class='warn'>interpolated</span>"]
            for k in q]
    return section(
        "saver-mechanics", "Part 2 · Savers", "How saving happens",
        p("There is <b>no savings-rate parameter anywhere in the model</b>. Saving is the "
          "residual of everything else, computed once a month:"),
        pre(
            "residual = self._m_income - self._m_bills - self._m_debt - self._m_disc\n"
            "if self.is_saver and residual > 0:\n"
            "    amount = min(residual, self.account.balance)\n"
            "    target = pension if self.is_pension_saver else savings\n"
            "    self.account.debit(...); target.credit(...)      # paired, money conserved"
        ),
        p("So all the heterogeneity in savings comes from income minus obligations minus "
          "discretionary spend. A richer household with the same bills simply leaves a bigger "
          "residual. <i>Whether</i> a household sweeps at all is the SHIW roll below; "
          "<i>how much</i> is emergent."),
        table(["Income quintile", "P(did not save)", "→ saver rate", "provenance"],
              rows, "lrrl"),
        cards([
            ("The pension split",
             "<p>A saver passes a <b>second independent roll</b> of the same quintile "
             "probability to become a pension-saver. Their residual then goes to the pension "
             "pot <i>instead of</i> savings — never both.</p><p class='note'>Reusing a "
             "saving-participation probability as a pension-participation probability is an "
             "assumption. The code is candid that no contribution rate was invented, but the "
             "reuse itself is unjustified.</p>"),
            ("The forced subsister",
             "<p><code>_assign_savings</code> force-sets <code>is_saver = True</code> for "
             "every subsister, so their surplus leaves the current account and it hugs zero.</p>"
             "<p class='note'>This overrides SHIW for a whole cohort and entangles the two "
             "labels — see the confound section below.</p>"),
        ]),
        callout(
            "Three of the five probabilities above are a linear interpolation, not survey "
            "output — SHIW reports only Q1 (0.70) and Q5 (0.28). The code marks them; the "
            "tier tables in the docs present the whole vector as calibrated."),
    )


def saver_results(rep: dict, caps: dict) -> str:
    srows = []
    for c in rep["saver_clustering"]:
        srows.append([
            esc(c["features"]), num(c["n_features"]), num(c["k"]),
            f"<code>{esc(c['target'])}</code>", num(c["ari"], 4),
            num(c.get("nmi"), 4), num(c.get("silhouette"), 4),
        ])
    sclus_t = table(["Feature set", "vars", "k", "against", "ARI", "NMI", "silhouette"],
                    srows, "lrrlrrr")

    prows = [[esc(r["estimator"]), num(r["naive_auc"], 4), num(r["debtor_fair_auc"], 4),
              f"<b>{num(r['saver_fair_auc'], 4)}</b>"] for r in rep["saver_prediction"]]
    spred_t = table(
        ["estimator", "naive AUC", "“debtor-fair” AUC<br>(still leaks)",
         "saver-fair AUC<br>(honest)"], prows, "lrrr")

    return section(
        "saver-results", "Part 2 · Savers", "Can savers be found in the ledger?",
        "<h3>Study C — clustering saver vs non-saver</h3>", sclus_t,
        callout(
            "<b>Clustering does not find savers, and that is the result.</b> Look at the "
            "naive row: even with the label mechanically present in the features — where "
            "prediction scores 0.9999 — clustering still cannot recover it. Saver status is a "
            "real but <i>low-variance</i> direction in the feature space, and KMeans "
            "partitions on the dominant axes instead: income scale and activity volume. The "
            "healthy silhouette confirms it found <i>a</i> clean structure, just not this one."),
        "<h3>Study D — predicting who saves</h3>", spred_t,
        p("The middle column is the one to read. It is the set this repo calls “fair”, and on "
          "this label it is not — see the next section."),
        gallery(SAVER_FIGS, caps),
    )


# --------------------------------------------------------------------------- #
def leaks_section(rep: dict) -> str:
    audit = rep["saver_leak_audit"]
    quar = table(
        ["Quarantined column", "corr with <code>is_saver</code>", "Why it had to go"],
        [["<code>cur_total_out</code>", num(audit["quarantined"]["cur_total_out"], 4),
          "the month-close sweep is a <b>debit on the current account</b>, so this total "
          "counts a line only savers ever have"],
         ["<code>cur_balance</code>", num(audit["quarantined"]["cur_balance"], 4),
          "what is left after that debit"]],
        "lrl",
    )
    kept = table(
        ["Kept column", "corr with <code>is_saver</code>", "Why it stays"],
        [[f"<code>{esc(k)}</code>", num(v["corr"], 4), esc(v["why"])]
         for k, v in audit["kept_for_contrast"].items()],
        "lrl",
    )
    return section(
        "leaks", "Both", "Two leaks, and why they are different",
        p("Each half of this page carries a column that looked innocent and was not. They "
          "failed in different ways, which is the interesting part."),
        cards([
            ("Leak 1 — the debtor side: <code>cur_n_entries</code>",
             "<p>A raw count of current-account entries. Fair-sounding, and it silently "
             "included the debt-service, credit-draw and overdraft lines — re-importing the "
             "very leakage the <code>LEAK_</code> prefix exists to quarantine.</p>"
             "<p>Regressed on the other fair activity counts (R² = 0.975), its residual "
             "correlates <b>+0.46</b> with the debt-mechanic line count and predicts "
             "<code>is_debtor</code> alone at <b>AUC 0.78</b>. Left in the fair set it "
             "inflated the headline from <b>0.91</b> to what should have been 0.697.</p>"),
            ("Leak 2 — the saver side: <code>LEAK_SAVER</code>",
             "<p>Fairness is <b>relative to the label</b>. The <code>LEAK_</code> prefix "
             "quarantines what encodes <i>debtor</i> status; nothing was quarantining what "
             "encodes <i>saver</i> status.</p>"
             "<p>The month-close sweep is a debit on the current account, so "
             "<code>cur_total_out</code> and <code>cur_balance</code> carry the saver label "
             "directly — worth <b>AUC 0.995</b>, a bigger leak than the first one.</p>"),
        ]),
        "<h3>What was quarantined for the saver label</h3>", quar,
        "<h3>What was kept, despite correlating just as strongly</h3>",
        p("Correlating with the label is <b>not</b> what makes a column unfair; mechanically "
          "encoding it is. These three correlate about as strongly and stay:"),
        kept,
        callout(
            "<b>The generalisable lesson.</b> A feature is not fair because its name is "
            "innocuous — only if the generating process cannot write the label into it. Both "
            "leaks passed a name-based review and failed a mechanism-based one.", "ok"),
        callout(
            f"<code>fair_columns()</code> is deliberately <b>not</b> changed by the saver "
            f"quarantine, so every debtor number on this page, every figure and every pinned "
            f"test bound is exactly what it was. Use "
            f"<code>saver_fair_columns()</code> ({src('features.py:289')}) whenever "
            f"<code>is_saver</code> is the target."),
    )


def confound_section(rep: dict) -> str:
    audit = rep["saver_leak_audit"]
    rows = [[f"<b>{esc(r['subtype'])}</b>", num(r["savers"]), num(r["total"]),
             f"{r['saver_rate']:.0%}"]
            for r in audit["saver_by_debtor_subtype"]]
    return section(
        "confound", "Both", "Where the two labels touch",
        p("The saver and debtor labels are not independent, and the reason is a single line "
          f"in the debt layer ({src('model.py:1092-1096')})."),
        table(["Debtor archetype", "savers", "total", "saver rate"], rows, "lrrr"),
        callout(
            "<b>Subsisters are 100% savers by construction.</b> The forcing exists so a "
            "hand-to-mouth household's surplus leaves the current account and it hugs zero — "
            "a deliberate choice in the debt layer. But it means any analysis of the saver "
            "label is partly reading the debtor layer. Declared rather than corrected: hiding "
            "a known effect on a second label would be worse than reporting it.", "warn"),
        p(f"One more check worth stating: savings balances are exactly zero for "
          f"<b>{audit['savings_balance_zero_among_non_savers']:.0%}</b> of non-savers, which "
          f"is the invariant that makes the sweep mechanic verifiable at all."),
    )


def verdict_section() -> str:
    return section(
        "verdict", "Both", "What the pair says that neither says alone",
        cards([
            ("Debtor", "<p>Clustering: <b>partly</b> (ARI 0.20 fair). "
                       "Prediction: <b>weakly</b> (AUC 0.70 fair).</p>"
                       "<p>The label is drawn from a <i>hidden</i> flag, so behaviour cannot "
                       "carry it. The ceiling is a property of the generator.</p>"),
            ("Saver", "<p>Clustering: <b>no</b> (ARI 0.008). "
                      "Prediction: <b>yes</b> (AUC 0.83 fair).</p>"
                      "<p>The label is drawn from <i>income quintile</i>, which the ledger "
                      "does reveal through income credits. It has an observable cause.</p>"),
        ]),
        callout(
            "<blockquote style='margin:0'><b>Clustering recovers a label only when that label "
            "aligns with a dominant axis of variation. Prediction only needs the signal to be "
            "present at all.</b></blockquote>"
            "<p style='margin:10px 0 0'>That is a statement about method rather than about "
            "this model, and it is the more transferable of the two findings — it is what the "
            "saver study is <i>for</i>, given that on its own it is a null result.</p>", "ok"),
        p("It also explains why honest saver prediction (0.83) beats honest debtor prediction "
          "(0.70) even though the saver study finds nothing by clustering: the saver label has "
          "an observable cause and the debtor subtype does not."),
    )


# --------------------------------------------------------------------------- #
def build(rep: dict, generated: str) -> str:
    caps = captions(FIG)
    cfg = rep["config"]
    links = [
        ("debt-mechanics", "Debt · mechanics"), ("debt-results", "Debt · results"),
        ("saver-mechanics", "Savers · mechanics"), ("saver-results", "Savers · results"),
        ("leaks", "The two leaks"), ("confound", "The confound"), ("verdict", "Verdict"),
    ]
    body = headline(rep) + "".join([
        debt_mechanics(), debt_results(rep, caps),
        saver_mechanics(), saver_results(rep, caps),
        leaks_section(rep), confound_section(rep), verdict_section(),
    ])
    return page(
        title="synthitaly — savers &amp; debt",
        heading="Savers &amp; debt",
        sub="The two household trajectories the model was built to produce — how each is "
            "constructed, and whether either can be recovered from the transaction stream.",
        meta=f"Generated {generated} · pinned config {cfg['n_consumers']} consumers × "
             f"{cfg['n_days']} days, seed {cfg['seed']} · reproduce with "
             f"<code>uv run python scripts/run_all.py</code>",
        navbar=nav(links),
        body=body,
        footer="synthitaly · self-contained, no network requests · companion pages: "
               "<code>flows_and_papers.html</code>, <code>data_appendix.html</code>, "
               "<code>results.html</code> · full method in <code>docs/VALIDATION.md</code>",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=Path("runs/latest"), type=Path)
    args = ap.parse_args()

    src_json = args.out / "validation_report.json"
    if not src_json.exists():
        print(f"error: {src_json} not found — run scripts/validation_report.py first",
              file=sys.stderr)
        return 1
    rep = json.loads(src_json.read_text(encoding="utf-8"))
    out = args.out / "savers_and_debt.html"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    out.write_text(build(rep, esc(stamp)), encoding="utf-8")
    print(f"wrote {out}  ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
