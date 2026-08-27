#!/usr/bin/env python3
"""Assemble the browsable results page from a validation report + the figures.

    uv run python scripts/build_results_page.py [--out runs/latest]

Reads ``<out>/validation_report.json`` (written by ``scripts/validation_report.py``) and
the SVGs in ``presentation/figures/``, and writes a single self-contained
``<out>/results.html`` — every image inlined as a data-URI, so it opens in any browser
with no server and no network. Reuses the inlining helpers in
``presentation/scripts/_inline.py``, the same ones ``build_deck.py`` uses.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "presentation" / "scripts"))

from _inline import captions, data_uri  # noqa: E402

FIG = ROOT / "presentation" / "figures"

# --------------------------------------------------------------------------- #
# Sourcing. Two tables, deliberately kept apart: where the model's NUMBERS come
# from (empirical, Italian, load-bearing for realism) vs where the analysis METHODS
# come from (canonical statistics, load-bearing for defensibility). Blurring the two
# is exactly the error docs/EXPLANATION.md §6 exists to prevent.
# --------------------------------------------------------------------------- #
MODEL_SOURCES = [
    ("Tier 1 — calibrated", "SHIW 2022 (Bank of Italy)",
     "income by source; debt participation &amp; service by quartile; saver probability by "
     "quintile; the financial-vulnerability definition behind the chronic tilt"),
    ("Tier 1 — calibrated", "Payment Behaviour Survey 2023–24",
     "the five recurring bills; the low / middle / high income bands"),
    ("Tier 1 — calibrated", "Emiliozzi et al. (2023) — card data",
     "10 spending categories and their shares; ticket sizes; weekday / month / holiday "
     "multipliers; macro-area population weights"),
    ("Tier 1 — calibrated", "Structural inequalities / wire transfers",
     "end-of-month payday (27th); the December <em>tredicesima</em>; the North–South income "
     "gradient (South = 0.554 &times; Centre-North, Semeraro et al. 2020 p.5/p.27)"),
    ("Tier 2 — behavioural overlay", "Olafsson &amp; Pagel (2018)",
     "the mean-neutral post-payday spending spike (×1.5)"),
    ("Tier 2 — behavioural overlay", "Stango &amp; Zinman (2014)",
     "the flat per-event overdraft fee (€30)"),
    ("Tier 2 — behavioural overlay", "Dahan &amp; Nisan (2020)",
     "the late-payment penalty on overdue bills (11%)"),
    ("Tier 2 — conceptual", "Campbell (2006)",
     "fees concentrate among the vulnerable → the chronic-debtor tilt"),
    ("Method", "Jiang et al. (2022)",
     "the synthetic-population construction (implemented in the parked fuller version)"),
    ("Method", "Grimm et al. (2020)",
     "the ODD protocol the model spec in <code>docs/ODD.md</code> follows"),
]

METHOD_SOURCES = [
    ("<code>diagnostics.bartlett_sphericity</code>", "Test of sphericity",
     "Bartlett, M. S. (1950). Tests of significance in factor analysis. "
     "<em>British Journal of Psychology (Statistical Section)</em> 3(2), 77–85."),
    ("<code>diagnostics.kmo</code>", "KMO / measure of sampling adequacy",
     "Kaiser, H. F. (1970). A second generation little jiffy. "
     "<em>Psychometrika</em> 35(4), 401–415."),
    ("<code>diagnostics.kmo_verdict</code>", "The marvellous→unacceptable scale",
     "Kaiser, H. F. &amp; Rice, J. (1974). Little Jiffy, Mark IV. "
     "<em>Educational and Psychological Measurement</em> 34(1), 111–117."),
    ("<code>diagnostics.eigen_spectrum</code>", "Eigenvalue &gt; 1 retention rule",
     "Kaiser, H. F. (1960). The application of electronic computers to factor analysis. "
     "<em>Educational and Psychological Measurement</em> 20(1), 141–151."),
    ("<code>factorable_columns</code> — the <code>share_*</code> drop",
     "Why proportions summing to 1 cannot enter a factor model untransformed",
     "Aitchison, J. (1982). The statistical analysis of compositional data. "
     "<em>JRSS Series B</em> 44(2), 139–177."),
    ("Study A", "Adjusted Rand index",
     "Hubert, L. &amp; Arabie, P. (1985). Comparing partitions. "
     "<em>Journal of Classification</em> 2(1), 193–218."),
    ("Study A", "Silhouette",
     "Rousseeuw, P. J. (1987). Silhouettes: a graphical aid to the interpretation and "
     "validation of cluster analysis. <em>J. Computational and Applied Mathematics</em> 20, 53–65."),
    ("Study A — <code>clustering.ipynb</code>", "Ward linkage",
     "Ward, J. H. (1963). Hierarchical grouping to optimize an objective function. "
     "<em>JASA</em> 58(301), 236–244."),
    ("Study A", "k-means++ initialisation",
     "Arthur, D. &amp; Vassilvitskii, S. (2007). k-means++: the advantages of careful "
     "seeding. <em>SODA</em>, 1027–1035."),
    ("Study B", "ROC-AUC",
     "Fawcett, T. (2006). An introduction to ROC analysis. "
     "<em>Pattern Recognition Letters</em> 27(8), 861–874."),
    ("The <code>LEAK_</code> design", "Target leakage as a named failure mode",
     "Kaufman, S., Rosset, S., Perlich, C. &amp; Stitelman, O. (2012). Leakage in data "
     "mining: formulation, detection, and avoidance. <em>ACM TKDD</em> 6(4), 1–21."),
    ("<code>scripts/sweep_behavioural.py</code>", "One-at-a-time sensitivity analysis",
     "Saltelli, A. et al. (2008). <em>Global Sensitivity Analysis: The Primer</em>. Wiley."),
]

STUDY_FIGS = ["f13_clustering_pca", "f14_cluster_recovery", "f15_prediction"]
MODEL_FIGS = [
    "f01_txn_volume", "f02_spend_mix_vs_paper", "f03_spend_by_area", "f04_payday_spike",
    "f05_behavioural_events", "f06_income_composition", "f07_balance_by_source",
    "f08_income_distribution", "f09_debt_stock_by_subtype", "f10_balance_by_subtype",
    "f11_debtor_composition", "f12_still_in_debt",
]


# --------------------------------------------------------------------------- #
# Fragments
# --------------------------------------------------------------------------- #
def table(headers: list[str], rows: list[list[str]], aligns: str = "") -> str:
    aligns = aligns or "l" * len(headers)
    cls = {"l": "", "r": ' class="r"', "c": ' class="c"'}
    # strict=True on purpose: a row whose cell count disagrees with the header should be a
    # loud error, not a silently truncated table in a document people read numbers off.
    head = "".join(f"<th{cls[a]}>{h}</th>" for h, a in zip(headers, aligns, strict=True))
    body = "".join(
        "<tr>" + "".join(f"<td{cls[a]}>{c}</td>"
                         for c, a in zip(r, aligns, strict=True)) + "</tr>"
        for r in rows
    )
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def plate(stem: str, caps: dict[str, str]) -> str:
    svg = FIG / f"{stem}.svg"
    if not svg.exists():
        return (f'<figure class="plate missing"><figcaption>{stem} — not generated yet; '
                f'run <code>generate_figures.py</code></figcaption></figure>')
    cap = caps.get(stem, "")
    return (f'<figure class="plate"><img loading="lazy" alt="{stem}" src="{data_uri(svg)}">'
            f'<figcaption><b>{stem.split("_")[0]}</b> — {cap}</figcaption></figure>')


def num(v, nd=4):
    if v is None:
        return "—"
    return f"{v:.{nd}f}" if isinstance(v, float) else f"{v:,}" if isinstance(v, int) else str(v)


def section(sid: str, kicker: str, title: str, *blocks: str) -> str:
    return (f'<section id="{sid}"><div class="kicker">{kicker}</div><h2>{title}</h2>'
            + "".join(blocks) + "</section>")


def p(text: str) -> str:
    return f"<p>{text}</p>"


# --------------------------------------------------------------------------- #
# Page
# --------------------------------------------------------------------------- #
def build(rep: dict, generated: str) -> str:
    caps = captions(FIG)
    cfg, frame, labels = rep["config"], rep["frame"], rep["labels"]

    # --- headline strip -----------------------------------------------------
    head_row = next(r for r in rep["factorability"] if "HEADLINE" in r["treatment"])
    clus = {c["features"]: c for c in rep["clustering"]}
    pred = {(r["task"], r["estimator"]): r for r in rep["prediction"]}
    spred = {r["estimator"]: r for r in rep["saver_prediction"]}
    sclus_k2 = next(c for c in rep["saver_clustering"]
                    if c["features"] == "saver-fair" and c["k"] == 2)
    n_pass = sum(1 for k in rep["checks"] if k["status"] == "PASS")
    n_all = len(rep["checks"])
    tiles = [
        ("KMO", num(head_row["kmo"], 3), head_row["verdict"]),
        ("debtor ARI", num(clus["naive"]["ari"], 3), f"fair-only {num(clus['fair']['ari'], 3)}"),
        ("is_debtor AUC", num(pred[("is_debtor", "logreg")]["fair_auc"], 3),
         f"leaked control {num(pred[('is_debtor', 'logreg')]['naive_auc'], 3)}"),
        ("is_climber AUC", num(pred[("is_climber", "logreg")]["fair_auc"], 3),
         f"leaked control {num(pred[('is_climber', 'logreg')]['naive_auc'], 3)}"),
        ("is_saver AUC", num(spred["logreg"]["saver_fair_auc"], 3),
         f"before the leak fix {num(spred['logreg']['debtor_fair_auc'], 3)}"),
        ("saver ARI", num(sclus_k2["ari"], 3), "clustering finds nothing"),
        ("headline checks", f"{n_pass}/{n_all}",
         "PASS" if n_pass == n_all else "DRIFT — see below"),
    ]
    strip = '<div class="tiles">' + "".join(
        f'<div class="tile"><div class="tl">{a}</div><div class="tv">{b}</div>'
        f'<div class="ts">{c}</div></div>' for a, b, c in tiles) + "</div>"

    # --- study 0 ------------------------------------------------------------
    fact_rows = []
    for r in rep["factorability"]:
        b = r["bartlett"]
        bart = "refused" if "refused" in b else f"{b['chi2']:,.0f} ({b['dof']})"
        mark = ' class="hl"' if "HEADLINE" in r["treatment"] else ""
        name = r["treatment"].replace("[HEADLINE]", '<span class="pill">headline</span>') \
                             .replace("(sensitivity bound)", '<span class="pill warn">sensitivity</span>')
        fact_rows.append([
            f'<span{mark}>{name}</span><br><span class="note">{r["note"]}</span>',
            str(r["n_vars"]),
            num(r["kmo"], 3) if r["kmo"] is not None else "—",
            (r["verdict"] if r["kmo"] is not None
             else f'<span class="warn">{r["verdict"]}</span>'),
            str(r["kaiser_n"]), bart, f'{r["condition_number"]:.3g}',
        ])
    eig_rows = [[str(e["component"]), f'{e["eigenvalue"]:.3f}', f'{e["pct_variance"]:.1f}',
                 f'{e["cum_pct_variance"]:.1f}', "●" if e["kaiser"] else ""]
                for e in rep["eigen_spectrum"]]

    # --- study A / B --------------------------------------------------------
    clus_rows = [[c["features"], str(c["n_features"]), num(c["ari"]), num(c["nmi"]),
                  num(c["silhouette"])] for c in rep["clustering"]]
    pred_rows = [[f'<code>{r["task"]}</code>', r["population"],
                  f'{r["n"]:,} ({r["positives"]})', r["estimator"],
                  num(r["naive_auc"]), f'<b>{num(r["fair_auc"])}</b>']
                 for r in rep["prediction"]]
    check_rows = [[f'<code>{k["name"]}</code>', num(k["measured"]), num(k["expected"]),
                   f'±{k["tolerance"]}',
                   f'<span class="{"ok" if k["status"] == "PASS" else "warn"}">{k["status"]}</span>']
                  for k in rep["checks"]]

    # --- studies C / D (saver) ---------------------------------------------
    sclus_rows = [[r["features"], str(r["n_features"]), str(r["k"]),
                   f'<code>{r["target"]}</code>', num(r["ari"]), num(r["nmi"]),
                   num(r["silhouette"])] for r in rep["saver_clustering"]]
    spred_rows = [[f'<code>{r["task"]}</code>', f'{r["n"]:,} ({r["positives"]})',
                   r["estimator"], num(r["naive_auc"]),
                   f'<span class="warn">{num(r["debtor_fair_auc"])}</span>',
                   f'<b>{num(r["saver_fair_auc"])}</b>']
                  for r in rep["saver_prediction"]]
    audit = rep["saver_leak_audit"]
    audit_rows = (
        [[f'<code>{c}</code>', f'{v:+.3f}',
          '<span class="warn">quarantined</span> — the sweep debit lands in it']
         for c, v in audit["quarantined"].items()]
        + [[f'<code>{c}</code>', f'{d["corr"]:+.3f}', f'kept — {d["why"]}']
           for c, d in audit["kept_for_contrast"].items()]
    )
    confound_bits = [(r["subtype"], f'{r["savers"]}/{r["total"]} savers')
                     for r in audit["saver_by_debtor_subtype"]]

    body = "".join([
        section(
            "overview", "what this is", "Validation results",
            p(f"Every headline number the write-up quotes, measured in one run of "
              f"<code>scripts/validation_report.py</code> at the pinned configuration: "
              f"<b>{cfg['n_consumers']} consumers × {cfg['n_days']} days, seed {cfg['seed']}</b>. "
              f"The feature frame is {frame['n_features']} columns "
              f"({frame['n_fair']} fair, {frame['n_leak']} <code>LEAK_</code>) over "
              f"{frame['n_consumers']} consumers; {labels['n_debtors']} of them are debtors "
              + ", ".join(f"({k} {v}" if i == 0 else f"{k} {v}"
                          for i, (k, v) in enumerate(sorted(labels['subtype_mix'].items())))
              + ")."),
            strip,
            p("The pattern to read across every study: the <b>naive</b> column includes the "
              "<code>LEAK_</code> debt-mechanic features and is the <em>control condition</em> — "
              "it measures how completely the label is written into the ledger by construction. "
              "The <b>fair</b> column is the honest result: what ordinary, bank-observable "
              "behaviour actually carries."),
            p("Studies <b>0, A and B</b> ask about <b>debtors</b>; studies <b>C and D</b> ask the "
              "same questions of <b>savers</b>. Reading them together is what makes each one "
              "mean something — the two labels behave oppositely, and the contrast is the "
              "methodological result."),
            '<div class="callout"><b>&ldquo;Fair&rdquo; is relative to the label you are '
            'predicting.</b> The <code>LEAK_</code> prefix quarantines what mechanically encodes '
            '<em>debtor</em> status. Two columns that are genuinely fair for that label — '
            '<code>cur_total_out</code> and <code>cur_balance</code> — encode <em>saver</em> '
            'status via the month-close sweep, so the saver studies use a separate '
            '<code>LEAK_SAVER</code> quarantine. The debtor feature set is left exactly as it '
            'was, so every debtor number on this page is unchanged. See Study D.</div>',
        ),
        section(
            "study0", "study 0", "Is the feature matrix factorable?",
            p("PCA and KMeans both assume the correlation matrix carries common structure worth "
              "extracting. This tests that assumption instead of taking it on faith. The first "
              "row is the point: the untouched fair set is <b>singular</b> — the ten "
              "<code>share_*</code> columns are proportions of one total and sum to exactly 1.0 "
              "for every consumer — and <code>diagnostics.kmo</code> <b>refuses</b> to "
              "pseudo-invert it rather than returning a plausible number computed from noise."),
            table(["Treatment", "vars", "KMO", "Kaiser's verdict", "eigen&gt;1",
                   "Bartlett χ² (dof)", "cond(R)"],
                  fact_rows, "lrrlrrr"),
            p("Bartlett rejects sphericity in every case (p ≈ 0), so structure certainly exists. "
              "The middling KMO says that structure is only partly common-factor shaped — which "
              "is what you expect from a generator whose latent labels are <em>drawn</em> rather "
              "than caused. The last row is a <b>sensitivity bound, not a result</b>: it prunes "
              "variables because their measured MSA was low, which raises KMO by construction."),
            '<h3>Eigenvalue spectrum of the headline set</h3>',
            table(["PC", "eigenvalue", "% variance", "cumulative %", "Kaiser"],
                  eig_rows, "rrrrc"),
        ),
        section(
            "studyA", "study A", "Clustering — do the archetypes fall out of the ledger?",
            p("KMeans (k = 3) on the debtor subpopulation, scored against the true "
              "climber / chronic / subsister labels."),
            table(["Features", "n", "ARI", "NMI", "silhouette"], clus_rows, "lrrrr"),
            p("Subsisters separate cleanly because they draw on a credit line — a distinct "
              "mechanic that leaves a distinct trace. Climbers and chronics differ only in "
              "repayment <em>speed</em>, so clustering merges them; that is the ceiling, and it "
              "is structural rather than a tuning failure."),
            '<div class="gallery">' + "".join(plate(s, caps) for s in STUDY_FIGS[:2]) + "</div>",
            '<p class="note">The figures quote ARI 0.39 / 0.01 rather than the 0.471 / 0.200 '
            'above — not a contradiction. Figures are generated at <b>600 consumers × 720 '
            'days</b> on the small <code>FAIR_COMPACT</code> / <code>LEAK_COMPACT</code> column '
            'set, where the point is a stable pinned number; the tables here use the full '
            '45-column frame at 800 × 720. Both are correct for their configuration, and the '
            'configuration is stated wherever a number appears.</p>',
        ),
        section(
            "studyB", "study B", "Prediction — can debtors and climbers be spotted?",
            p("5-fold cross-validated ROC-AUC. Two tasks, two estimators, each measured on the "
              "leaked control set and on fair features only."),
            table(["Task", "population", "n (positives)", "estimator", "naive AUC", "fair AUC"],
                  pred_rows, "llrlrr"),
            p("<code>is_debtor</code> is near-perfect with the debt-mechanic columns and modest "
              "without them. The label is <em>drawn</em> by <code>numbers.has_debt</code>, a "
              "Bernoulli on the income-quartile gradient "
              "<code>{1: 0.120, 2: 0.192, 3: 0.244, 4: 0.285}</code>, so at assignment time "
              "income quartile is the only signal in it and bounds the Bayes-optimal AUC at "
              "<b>0.603</b>. The fair scores clear that bound on post-assignment repayment "
              "behaviour. <code>is_climber</code> predicts better fair-only because the divergent "
              "repayment rules leave an ordinary, visible trace in the account record."),
            '<div class="gallery">' + plate(STUDY_FIGS[2], caps) + "</div>",
            '<div class="callout"><b>One leak hid inside the fair set.</b> The fair debtor AUC '
            'read 0.91 until the feature set was audited: <code>cur_n_entries</code>, a raw count '
            'of current-account entries, silently included the debt-service, credit-draw and '
            'overdraft lines. It is now <code>LEAK_cur_n_entries</code> and the honest number is '
            '0.697. A feature is not fair because its <em>name</em> is innocuous — only if the '
            'generating process cannot write the label into it. Full audit in '
            '<code>docs/EXPLANATION.md</code> §8a.</div>',
        ),
        section(
            "studyC", "study C", "Clustering — saver vs non-saver",
            p("The same question as Study A, asked of the other label. KMeans at k = 2 "
              "against <code>is_saver</code>, and at k = 4 against the four-way "
              "<code>financial_status</code> (saver / non-saver, each with and without debt)."),
            table(["Features", "n", "k", "against", "ARI", "NMI", "silhouette"],
                  sclus_rows, "lrrlrrr"),
            '<div class="callout"><b>Clustering does not find savers — and that is the '
            'result.</b> ARI ≈ 0.008 at k = 2. Look at the <code>naive</code> row: even with '
            'the label mechanically present in the features — where prediction below scores '
            '0.9999 — clustering still cannot recover it. Saver status is a real but '
            '<em>low-variance</em> direction in the feature space; KMeans partitions on the '
            'dominant axes (income scale, activity volume) and this split is not one of them. '
            'The healthy silhouette (0.38) confirms it found <em>a</em> clean structure, just '
            'not this one.</div>',
            p("Put beside Study A — where the debtor archetypes reached ARI 0.471 — the pair "
              "makes the methodological point neither makes alone: <b>clustering recovers a "
              "label only when it aligns with a dominant axis of variation; prediction only "
              "needs the signal to be present at all.</b>"),
        ),
        section(
            "studyD", "study D", "Prediction — who is a saver?",
            p("5-fold cross-validated ROC-AUC on <code>is_saver</code>, under three feature "
              "sets. The middle column is the one to read."),
            table(["Task", "n (positives)", "estimator", "naive AUC", "debtor-fair AUC",
                   "saver-fair AUC"], spred_rows, "lrlrrr"),
            '<div class="callout"><b>A second leak, on a different label.</b> The '
            '<code>debtor-fair</code> column is the set this repo calls "fair" — and on the '
            'saver label it is not fair at all, scoring 0.995. <code>Consumer._month_close</code> '
            'sweeps the month\'s positive residual into savings or pension, and that sweep is a '
            '<em>debit on the current account</em>. So <code>cur_total_out</code> counts a line '
            'only savers ever have, and <code>cur_balance</code> is what is left after it. '
            'Quarantining the two as <code>LEAK_SAVER</code> takes the honest number to '
            '<b>0.827</b>. Same class of bug as <code>cur_n_entries</code>, found by asking the '
            'question of a new label.</div>',
            '<h3>The audit — correlation with <code>is_saver</code></h3>',
            p("Correlating with the label is not what makes a column unfair; <em>mechanically "
              "encoding</em> it is. Three columns correlate as strongly and are kept, each for "
              "its own reason:"),
            table(["Column", "corr", "disposition"], audit_rows, "lrl"),
            p(f"<code>LEAK_savings_balance</code> is zero for "
              f"<b>{audit['savings_balance_zero_among_non_savers']:.0%}</b> of non-savers — "
              f"definitionally the label, and already quarantined."),
            '<h3>Why this label is easier, and one confound</h3>',
            p("Honest saver prediction (0.827) beats honest debtor prediction (0.697), and the "
              "reason is structural: <code>is_saver</code> is drawn on <code>income_quintile</code>, "
              "which the ledger <em>does</em> show through the income credits. The debtor subtype "
              "is drawn on a hidden binary flag. The label has an observable cause, so behaviour "
              "carries it."),
            p("<b>Known confound:</b> subsisters are force-set <code>is_saver = True</code> in "
              "<code>ItalyModel._assign_savings</code>, so the two labels are entangled — "
              + ", ".join(f"{k}: {v}" for k, v in confound_bits) + "."),
        ),
        section(
            "checks", "reproducibility", "Headline checks",
            p("Every number above, against the value measured when this harness was pinned. "
              "The model and every split are seeded, so the only legitimate movement is "
              "last-digit numerical noise. A DRIFT row means something in the model or the "
              "pipeline changed — investigate it; never widen the tolerance to make it green."),
            table(["Number", "measured", "expected", "tolerance", ""], check_rows, "lrrrc"),
            p('Reproduce in full: <code>uv run python scripts/run_all.py</code>. Run it twice — '
              '<code>validation_report.json</code> must be byte-identical. See '
              '<code>docs/RUNBOOK.md</code>.'),
        ),
        section(
            "figures", "the model", "What the generator produces",
            p("Generated fresh from the live model by "
              "<code>presentation/scripts/generate_figures.py</code> — runs A (150 × 120 days) "
              "and B (150 × 720 days), seed 42. These are outputs, not validation: they show the "
              "calibrated and behavioural mechanisms falling out of the per-agent rules."),
            '<div class="gallery">' + "".join(plate(s, caps) for s in MODEL_FIGS) + "</div>",
        ),
        section(
            "sources", "provenance", "Where everything comes from",
            p("Two tables, kept apart on purpose. The first is where the model's <b>numbers</b> "
              "come from — empirical, Italian, load-bearing for realism. The second is where the "
              "analysis <b>methods</b> come from — canonical statistics, load-bearing for "
              "defensibility. A method citation is never evidence that a magnitude is real."),
            '<h3>Model calibration — the numbers</h3>',
            table(["Tier", "Source", "What it fixes"],
                  [[a, f"<b>{b}</b>", c] for a, b, c in MODEL_SOURCES]),
            p("Full number-by-number mapping in <code>docs/MODEL_REFERENCE.md</code>; the "
              "calibrated-vs-modelled bright line in <code>docs/EXPLANATION.md</code> §6."),
            '<h3>Statistical method — the instruments</h3>',
            table(["Used in", "Method", "Source"], [list(r) for r in METHOD_SOURCES]),
        ),
    ])

    nav = "".join(
        f'<a href="#{i}">{t}</a>' for i, t in [
            ("overview", "Overview"), ("study0", "Study 0"), ("studyA", "Study A"),
            ("studyB", "Study B"), ("studyC", "Study C"), ("studyD", "Study D"),
            ("checks", "Checks"), ("figures", "Figures"), ("sources", "Sources")])
    # Sibling pages, written into the same run directory by run_all.py. Relative
    # links so the whole runs/<stamp>/ folder stays portable when zipped or moved.
    nav += "".join(
        f'<a href="{f}" style="color:var(--accent)">{t} →</a>' for f, t in [
            ("flows_and_papers.html", "Flows &amp; papers"),
            ("savers_and_debt.html", "Savers &amp; debt"),
            ("data_appendix.html", "Dataset appendix"),
            ("prediction_and_papers.html", "Paper replications")])

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>synthitaly — validation results</title>
<style>
:root {{
  --bg:#fbfbf9; --card:#fff; --ink:#14140f; --ink2:#4b4a44; --muted:#8a887f;
  --line:#e4e3db; --accent:#2a78d6; --ok:#008300; --warn:#c23b3b; --hl:#f5f2e6;
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg:#131311; --card:#1c1c19; --ink:#f0efe9; --ink2:#b8b6ad; --muted:#86847c;
           --line:#33322c; --accent:#6ea8ee; --ok:#4fbb6a; --warn:#e8756f; --hl:#26261f; }}
}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--ink); font:16px/1.65 -apple-system,
  "Segoe UI", system-ui, sans-serif; }}
.wrap {{ max-width:1080px; margin:0 auto; padding:0 24px 80px; }}
header {{ padding:56px 0 8px; }}
h1 {{ font-size:2.4rem; margin:0 0 6px; letter-spacing:-.02em; }}
.sub {{ color:var(--ink2); font-size:1.05rem; margin:0; }}
.meta {{ color:var(--muted); font-size:.85rem; margin-top:10px; }}
nav {{ position:sticky; top:0; background:var(--bg); border-bottom:1px solid var(--line);
  padding:10px 0; margin:24px 0 0; z-index:5; display:flex; gap:18px; flex-wrap:wrap; }}
nav a {{ color:var(--ink2); text-decoration:none; font-size:.86rem; font-weight:600; }}
nav a:hover {{ color:var(--accent); }}
section {{ padding:44px 0 8px; border-bottom:1px solid var(--line); }}
.kicker {{ font-size:.74rem; letter-spacing:.14em; text-transform:uppercase;
  color:var(--muted); font-weight:700; }}
h2 {{ font-size:1.6rem; margin:4px 0 16px; letter-spacing:-.01em; }}
h3 {{ font-size:1.05rem; margin:30px 0 10px; color:var(--ink2); }}
p {{ margin:0 0 14px; max-width:74ch; }}
code {{ font:.88em ui-monospace, "SF Mono", Menlo, monospace; background:var(--hl);
  padding:1px 5px; border-radius:4px; }}
.scroll {{ overflow-x:auto; margin:16px 0 20px; }}
table {{ border-collapse:collapse; width:100%; font-size:.9rem; background:var(--card); }}
th, td {{ text-align:left; padding:9px 12px; border-bottom:1px solid var(--line);
  vertical-align:top; }}
th {{ font-size:.76rem; letter-spacing:.06em; text-transform:uppercase; color:var(--muted);
  border-bottom:2px solid var(--line); white-space:nowrap; }}
td.r, th.r {{ text-align:right; font-variant-numeric:tabular-nums; }}
td.c, th.c {{ text-align:center; }}
tbody tr:hover {{ background:var(--hl); }}
.note {{ color:var(--muted); font-size:.82rem; }}
.hl {{ font-weight:700; }}
.ok {{ color:var(--ok); font-weight:700; }}
.warn {{ color:var(--warn); font-weight:700; }}
.pill {{ background:var(--accent); color:#fff; font-size:.68rem; font-weight:700; padding:2px 7px;
  border-radius:10px; letter-spacing:.05em; text-transform:uppercase; }}
.pill.warn {{ background:var(--warn); color:#fff; }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px;
  margin:22px 0 8px; }}
.tile {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:14px 16px; }}
.tl {{ font-size:.72rem; letter-spacing:.09em; text-transform:uppercase; color:var(--muted);
  font-weight:700; }}
.tv {{ font-size:1.9rem; font-weight:700; letter-spacing:-.02em; font-variant-numeric:tabular-nums;
  line-height:1.2; margin:2px 0; }}
.ts {{ font-size:.78rem; color:var(--ink2); }}
.gallery {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(400px,1fr)); gap:20px;
  margin:20px 0; }}
.plate {{ margin:0; background:var(--card); border:1px solid var(--line); border-radius:10px;
  padding:12px; }}
.plate img {{ width:100%; height:auto; display:block; border-radius:4px; background:#fff; }}
.plate figcaption {{ font-size:.8rem; color:var(--ink2); margin-top:9px; line-height:1.5; }}
.plate.missing {{ border-style:dashed; color:var(--muted); padding:26px; text-align:center; }}
.callout {{ background:var(--hl); border-left:3px solid var(--accent); border-radius:0 8px 8px 0;
  padding:14px 18px; margin:20px 0; font-size:.92rem; max-width:74ch; }}
footer {{ padding:32px 0; color:var(--muted); font-size:.83rem; }}
</style></head>
<body><div class="wrap">
<header>
  <h1>synthitaly — validation results</h1>
  <p class="sub">What was validated, what the number was, and where the method comes from.</p>
  <p class="meta">Generated {generated} · pinned config {cfg['n_consumers']} consumers ×
  {cfg['n_days']} days, seed {cfg['seed']} · reproduce with
  <code>uv run python scripts/run_all.py</code></p>
</header>
<nav>{nav}</nav>
{body}
<footer>synthitaly · every figure generated fresh from the live model · this page is
self-contained (no network requests) · see <code>docs/VALIDATION.md</code> and
<code>docs/RUNBOOK.md</code></footer>
</div></body></html>
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=Path("runs/latest"), type=Path)
    args = ap.parse_args()

    src = args.out / "validation_report.json"
    if not src.exists():
        print(f"error: {src} not found — run scripts/validation_report.py first",
              file=sys.stderr)
        return 1

    rep = json.loads(src.read_text(encoding="utf-8"))
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    out = args.out / "results.html"
    out.write_text(build(rep, html.escape(stamp)), encoding="utf-8")
    print(f"wrote {out}  ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
