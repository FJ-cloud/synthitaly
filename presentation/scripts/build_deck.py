#!/usr/bin/env python3
"""Assemble presentation/status_deck.html from the generated figures, diagrams,
and captions. Self-contained: every image is inlined as a base64 SVG data-URI, so
the page has no external dependencies.

Run:  uv run python presentation/build_deck.py   (after generate_figures + make_diagrams)
"""
from __future__ import annotations

from pathlib import Path

from _inline import captions, data_uri  # noqa: F401  (data_uri used by plate())

ROOT = Path(__file__).resolve().parent.parent
FIG, DIA = ROOT / "figures", ROOT / "diagrams"

CAP = captions(FIG)


def plate(stem: str, folder: Path, cap: str | None = None, fig_no: str | None = None) -> str:
    cap = cap if cap is not None else CAP.get(stem, "")
    tag = f'<span class="plate-tag">{fig_no}</span>' if fig_no else ""
    figcap = f'<figcaption>{tag}{cap}</figcaption>' if cap else ""
    return (
        f'<figure class="plate">'
        f'<div class="plate-img"><img loading="lazy" alt="{stem}" src="{data_uri(folder / (stem + ".svg"))}"></div>'
        f'{figcap}</figure>'
    )


PAPER_ROWS = [
    ("SHIW 2022", "①", "income by source; debt participation &amp; service by quartile; saver prob by quintile; the vulnerability definition behind the chronic tilt", "tier1"),
    ("Payment Behaviour Survey 2023-24", "①", "the five recurring bills; the low / middle / high income bands", "tier1"),
    ("Emiliozzi et al. (2023) (card data)", "①", "10 spending categories + shares; ticket sizes; weekday / month / holiday multipliers; macro-area weights", "tier1"),
    ("Structural inequalities / wire transfers", "①", "end-of-month payday (27th); December <em>tredicesima</em>; the North–South income gradient (South = 0.554 &times; Centre-North)", "tier1"),
    ("Olafsson &amp; Pagel (2018)", "②", "the mean-neutral post-payday spending spike &nbsp;<code>×1.5</code>", "tier2"),
    ("Stango &amp; Zinman (2014)", "②", "the flat overdraft fee on crossing €0 &nbsp;<code>€30</code>", "tier2"),
    ("Dahan &amp; Nisan (2020)", "②", "the late-payment penalty on overdue bills &nbsp;<code>11%</code>", "tier2"),
    ("Campbell (2006)", "②", "<em>conceptual</em> — fees concentrate among the vulnerable → the chronic-debtor tilt", "tier2"),
    ("Jiang et al. (2022)", "M", "the synthetic-population method (implemented in the parked fuller version)", "tierM"),
]


def paper_table() -> str:
    rows = "".join(
        f'<tr><td class="pt-name">{n}</td><td><span class="tier-dot {c}">{t}</span></td>'
        f'<td class="pt-use">{u}</td></tr>'
        for n, t, u, c in PAPER_ROWS
    )
    return (
        '<div class="table-wrap"><table class="tbl">'
        '<thead><tr><th>Paper</th><th>Tier</th><th>What it grounds in the engine</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div>'
    )


LEDGER_COLS = [
    ("date", "ISO date"), ("kind", "salary | bill | purchase | fee | loan"),
    ("from", "payer id"), ("to", "payee id"), ("category", "spend / bill / fee type"),
    ("amount_eur", "euro (2 dp)"), ("macro_area", "NORTH | CENTRE | SOUTH"),
]


def ledger_table() -> str:
    rows = "".join(f'<tr><td><code>{c}</code></td><td>{d}</td></tr>' for c, d in LEDGER_COLS)
    return ('<div class="table-wrap"><table class="tbl compact">'
            '<thead><tr><th>column</th><th>meaning</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


LIB_ROWS = [
    ("mesa", "the ABM framework — agents, scheduling, DataCollector"),
    ("numpy", "the single seeded RNG → deterministic runs; all sampling"),
    ("pandas", "ledger &amp; accounts DataFrames, CSV export, analysis"),
    ("matplotlib", "every static plot — panels &amp; these figures"),
    ("networkx", "the who-pays-whom graph behind the network panel"),
    ("solara", "the live 11-panel dashboard (viz.py)"),
    ("scikit-learn", "clustering &amp; prediction validation studies"),
    ("scipy", "hierarchical-clustering dendrograms"),
]


def lib_table() -> str:
    rows = "".join(f'<tr><td class="pt-name"><code>{n}</code></td><td>{d}</td></tr>' for n, d in LIB_ROWS)
    return ('<div class="table-wrap"><table class="tbl">'
            '<thead><tr><th>library</th><th>role</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


STATS = [
    ("3", "agent types", "Consumer · IncomeSource · Merchant"),
    ("4 + 3", "papers", "Italian calibrated + behavioural overlay"),
    ("~150", "consumers", "≈ 3.8k transactions in a demo run"),
    ("15", "figures", "generated fresh from the live model"),
    ("1 seed", "→ identical run", "byte-for-byte reproducible"),
]


def stat_row() -> str:
    tiles = "".join(
        f'<div class="stat"><div class="stat-num">{n}</div>'
        f'<div class="stat-lbl">{l}</div><div class="stat-sub">{s}</div></div>'
        for n, l, s in STATS
    )
    return f'<div class="stats">{tiles}</div>'


SECTIONS = [
    ("s1", "01", "The question"),
    ("s2", "02", "Architecture"),
    ("s3", "03", "Pipeline"),
    ("s4", "04", "One day"),
    ("s5", "05", "Papers &amp; provenance"),
    ("s6", "06", "Datasets"),
    ("s7", "07", "The data in motion"),
    ("s8", "08", "Debt as a stock"),
    ("s9", "09", "Validation"),
    ("s10", "10", "Status &amp; next"),
]


def nav() -> str:
    links = "".join(f'<a href="#{sid}"><span>{no}</span>{name}</a>' for sid, no, name in SECTIONS)
    return f'<nav class="secnav">{links}</nav>'


def section(sid, no, kicker, title, *blocks) -> str:
    body = "".join(blocks)
    return (
        f'<section id="{sid}" class="sec">'
        f'<div class="sec-head"><span class="sec-no">{no}</span>'
        f'<div><p class="kicker">{kicker}</p><h2>{title}</h2></div></div>'
        f'{body}</section>'
    )


def p(text) -> str:
    return f'<p class="prose">{text}</p>'


def gallery(*plates) -> str:
    return f'<div class="gallery">{"".join(plates)}</div>'


HTML = f"""<style>
:root {{
  --paper:#f7f8fa; --surface:#ffffff; --plate:#ffffff;
  --ink:#121820; --ink2:#47505b; --muted:#6b7480; --line:#e4e8ee;
  --accent:#17539e; --accent-soft:#eaf1f9; --accent-ink:#17539e;
  --tier1:#0f7a52; --tier2:#b9761f; --tier3:#c23b3b; --tierM:#5b6470;
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,"Times New Roman",serif;
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,"SF Mono","Cascadia Code",Menlo,Consolas,monospace;
}}
@media (prefers-color-scheme:dark) {{
  :root:where(:not([data-theme="light"])) {{
    --paper:#0f141a; --surface:#161d26; --plate:#f4f5f7;
    --ink:#eef2f7; --ink2:#b3bdc9; --muted:#8894a2; --line:#263041;
    --accent:#5b9be0; --accent-soft:#16233a; --accent-ink:#8fc0f2;
    --tier1:#3fae83; --tier2:#d99b4a; --tier3:#e2716f; --tierM:#8892a0;
  }}
}}
:root[data-theme="dark"] {{
  --paper:#0f141a; --surface:#161d26; --plate:#f4f5f7;
  --ink:#eef2f7; --ink2:#b3bdc9; --muted:#8894a2; --line:#263041;
  --accent:#5b9be0; --accent-soft:#16233a; --accent-ink:#8fc0f2;
  --tier1:#3fae83; --tier2:#d99b4a; --tier3:#e2716f; --tierM:#8892a0;
}}
* {{ box-sizing:border-box; }}
body, .page {{ margin:0; }}
.page {{
  background:var(--paper); color:var(--ink); font-family:var(--sans);
  font-size:17px; line-height:1.65; -webkit-font-smoothing:antialiased;
}}
.wrap {{ max-width:1080px; margin:0 auto; padding:0 28px; }}
a {{ color:var(--accent-ink); text-decoration:none; }}

/* ---- masthead ---- */
.mast {{ border-bottom:1px solid var(--line); padding:64px 0 40px; }}
.mast .eyebrow {{ font-family:var(--mono); font-size:12.5px; letter-spacing:.16em;
  text-transform:uppercase; color:var(--accent-ink); margin:0 0 18px; }}
.mast h1 {{ font-family:var(--serif); font-weight:600; font-size:clamp(34px,6vw,58px);
  line-height:1.04; letter-spacing:-.01em; margin:0 0 18px; text-wrap:balance; }}
.mast h1 em {{ font-style:italic; color:var(--accent-ink); }}
.mast .lede {{ font-size:20px; color:var(--ink2); max-width:64ch; margin:0 0 26px; text-wrap:pretty; }}
.mast .meta {{ display:flex; flex-wrap:wrap; gap:8px 22px; font-size:14px; color:var(--muted);
  font-family:var(--mono); }}
.mast .meta b {{ color:var(--ink2); font-weight:600; }}

/* ---- stat row ---- */
.stats {{ display:grid; grid-template-columns:repeat(5,1fr); gap:14px; margin:34px 0 8px; }}
.stat {{ background:var(--surface); border:1px solid var(--line); border-radius:12px;
  padding:16px 16px 14px; }}
.stat-num {{ font-family:var(--serif); font-size:30px; font-weight:600; line-height:1;
  color:var(--accent-ink); font-variant-numeric:tabular-nums; }}
.stat-lbl {{ font-size:13.5px; font-weight:650; margin-top:8px; letter-spacing:.01em; }}
.stat-sub {{ font-size:12px; color:var(--muted); margin-top:3px; line-height:1.35; }}

/* ---- section nav ---- */
.secnav {{ position:sticky; top:0; z-index:20; display:flex; flex-wrap:wrap; gap:2px;
  background:color-mix(in srgb, var(--paper) 88%, transparent);
  backdrop-filter:blur(8px); border-bottom:1px solid var(--line);
  padding:10px 28px; margin:0 -28px; }}
.secnav a {{ font-size:12.5px; color:var(--ink2); padding:6px 11px; border-radius:7px;
  display:flex; gap:7px; align-items:baseline; white-space:nowrap; }}
.secnav a span {{ font-family:var(--mono); font-size:11px; color:var(--muted); }}
.secnav a:hover {{ background:var(--accent-soft); color:var(--accent-ink); }}

/* ---- sections ---- */
.sec {{ padding:56px 0; border-bottom:1px solid var(--line); scroll-margin-top:56px; }}
.sec-head {{ display:flex; gap:20px; align-items:flex-start; margin-bottom:26px; }}
.sec-no {{ font-family:var(--mono); font-size:14px; color:var(--accent-ink);
  border:1px solid var(--line); border-radius:8px; padding:6px 10px; margin-top:4px; }}
.kicker {{ font-family:var(--mono); font-size:11.5px; letter-spacing:.14em; text-transform:uppercase;
  color:var(--muted); margin:0 0 6px; }}
.sec h2 {{ font-family:var(--serif); font-weight:600; font-size:clamp(24px,3.6vw,34px);
  line-height:1.1; margin:0; letter-spacing:-.01em; text-wrap:balance; }}
.prose {{ max-width:70ch; color:var(--ink2); margin:0 0 18px; }}
.prose strong {{ color:var(--ink); font-weight:650; }}
.prose code, .pt-use code, td code {{ font-family:var(--mono); font-size:.86em;
  background:var(--accent-soft); color:var(--accent-ink); padding:1px 6px; border-radius:5px; }}

/* ---- figure plates ---- */
.gallery {{ display:grid; grid-template-columns:1fr 1fr; gap:22px; margin-top:8px; }}
.gallery.one {{ grid-template-columns:1fr; }}
.plate {{ margin:0; background:var(--surface); border:1px solid var(--line);
  border-radius:14px; overflow:hidden; display:flex; flex-direction:column; }}
.plate.wide {{ grid-column:1 / -1; }}
.plate-img {{ background:var(--plate); padding:14px; }}
.plate-img img {{ display:block; width:100%; height:auto; }}
.plate figcaption {{ font-size:13.5px; color:var(--ink2); padding:13px 17px 15px;
  border-top:1px solid var(--line); line-height:1.5; }}
.plate-tag {{ font-family:var(--mono); font-size:11px; color:var(--accent-ink);
  font-weight:700; margin-right:8px; }}

/* ---- tables ---- */
.table-wrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:12px; margin:6px 0 8px; }}
.tbl {{ width:100%; border-collapse:collapse; font-size:14.5px; background:var(--surface); }}
.tbl th {{ text-align:left; font-size:12px; letter-spacing:.06em; text-transform:uppercase;
  color:var(--muted); font-weight:650; padding:12px 16px; border-bottom:1px solid var(--line); }}
.tbl td {{ padding:11px 16px; border-bottom:1px solid var(--line); color:var(--ink2); vertical-align:top; }}
.tbl tr:last-child td {{ border-bottom:0; }}
.tbl.compact td, .tbl.compact th {{ padding:8px 14px; }}
.pt-name {{ color:var(--ink); font-weight:600; white-space:nowrap; }}
.tier-dot {{ font-family:var(--mono); font-weight:700; font-size:12px; color:#fff;
  width:22px; height:22px; border-radius:50%; display:inline-flex; align-items:center; justify-content:center; }}
.tier1 {{ background:var(--tier1); }} .tier2 {{ background:var(--tier2); }}
.tier3 {{ background:var(--tier3); }} .tierM {{ background:var(--tierM); }}

/* ---- tier legend cards ---- */
.tiers {{ display:grid; grid-template-columns:repeat(3,1fr); gap:14px; margin:8px 0 20px; }}
.tcard {{ border:1px solid var(--line); border-left:4px solid var(--tc); border-radius:11px;
  padding:15px 17px; background:var(--surface); }}
.tcard h4 {{ margin:0 0 6px; font-size:14.5px; color:var(--ink); }}
.tcard p {{ margin:0; font-size:13px; color:var(--ink2); line-height:1.5; }}

/* ---- two-col ---- */
.cols {{ display:grid; grid-template-columns:1fr 1fr; gap:26px; align-items:start; }}
.cols h3, .sub {{ font-family:var(--sans); font-size:15px; font-weight:700; color:var(--ink);
  margin:0 0 8px; }}

/* ---- callout ---- */
.callout {{ background:var(--accent-soft); border:1px solid var(--line); border-radius:12px;
  padding:18px 20px; margin:14px 0; color:var(--ink2); font-size:15px; }}
.callout b {{ color:var(--ink); }}

/* ---- next-steps ---- */
.steps {{ list-style:none; padding:0; margin:8px 0 0; display:grid; gap:10px; max-width:74ch; }}
.steps li {{ background:var(--surface); border:1px solid var(--line); border-radius:10px;
  padding:13px 16px; color:var(--ink2); font-size:15px; }}
.steps li b {{ color:var(--ink); }}

footer {{ padding:40px 0 70px; color:var(--muted); font-size:13.5px; font-family:var(--mono); }}

@media (max-width:860px) {{
  .stats {{ grid-template-columns:repeat(2,1fr); }}
  .gallery, .tiers, .cols {{ grid-template-columns:1fr; }}
  .plate.wide {{ grid-column:auto; }}
}}
@media print {{ .secnav {{ display:none; }} .sec {{ break-inside:avoid; }} }}
</style>

<div class="page">
<header class="mast"><div class="wrap">
  <p class="eyebrow">Master's thesis · status report · July 2026</p>
  <h1><em>synthitaly</em> — a transparent agent-based model of Italian household finance</h1>
  <p class="lede">A Mesa simulation of what a bank sees on its customers' accounts — salaries in,
  bills out, card purchases, fees — calibrated to public Italian statistics, with a
  behavioural-economics overlay. Every number is either traceable to a paper or flagged as a choice.</p>
  <div class="meta">
    <span><b>Engine</b> src/synthitaly · Mesa 3.x · ~3.1k LOC</span>
    <span><b>Runs</b> seed 42 · 150–600 consumers · 120 / 720 days</span>
    <span><b>Output</b> ledger · accounts · time-series</span>
  </div>
  {stat_row()}
</div></header>

<div class="wrap">
{nav()}

{section("s1", "01", "The question", "Realistic account-level data you can actually inspect",
    p("Real bank ledgers are private, and public payment datasets are aggregated past the point "
      "where individual behaviour is visible — yet that account-level view is exactly what you need "
      "to study consumer financial behaviour. <strong>synthitaly</strong> asks a narrow version of the "
      "question: <strong>can a small, fully transparent agent-based model, calibrated to public Italian "
      "statistics, generate a synthetic transaction stream that is realistic where it is calibrated and "
      "honest about where it is not?</strong>"),
    p("The framing is <strong>bank-eye</strong>: the model emits only what a bank would see — income in, "
      "bills out, purchases, and its own fees. No business-to-business wires, no corporate treasury, no "
      "taxes. That keeps the scope tractable and every output row legible."),
    plate("d03_money_flow", DIA, cap="Money flow — the entire scope of the model. Salary in, purchases and bills out, fees to the bank, an internal month-end sweep to savings/pension. Money is conserved system-wide.", fig_no="DIAGRAM"),
)}

{section("s2", "02", "Architecture", "Three agent types over a daily clock",
    p("One <code>ItalyModel</code> orchestrates three agent types. The <strong>Consumer</strong> (a household) "
      "is the only active decision-maker; the <strong>IncomeSource</strong> pays salaries on payday; the "
      "<strong>Merchant</strong> passively receives. Each consumer holds three accounts — current, savings, "
      "pension — and every money movement is a paired debit/credit, so accounts reconcile and money is conserved."),
    plate("d01_architecture", DIA, cap="Class structure — the model, the three agents, and the account/entry bookkeeping that makes every balance auditable.", fig_no="DIAGRAM"),
)}

{section("s3", "03", "Pipeline", "From papers to analysis, six stages",
    p("Empirical evidence enters through <code>numbers.py</code>, where every constant is paper-cited. "
      "Initialisation builds the population and assigns income bands, debt, and savings flags; the daily "
      "loop runs the simulation; outputs are three reconcilable views; analysis and the live dashboard sit "
      "on top. Nothing is written to disk until a caller asks."),
    plate("d04_methodology_pipeline", DIA, cap="The methodology pipeline. A single seeded RNG makes every run byte-for-byte reproducible; the three provenance tiers travel through every stage.", fig_no="DIAGRAM"),
    '<h3 class="sub" style="margin-top:26px">Libraries the system leans on</h3>',
    lib_table(),
)}

{section("s4", "04", "One day", "What happens inside a single step",
    p("Scheduling is <strong>synchronous across days, randomised within a day</strong>. Income sources act "
      "first (so a consumer paid today can spend today), then consumers act in shuffled order: close last "
      "month, settle overdue bills, pay bills due today, service debt on the 25th, and maybe buy. The model "
      "records the day's KPIs and grouped balances, then advances the clock."),
    plate("d02_day_step", DIA, cap="Sequence of one ItalyModel.step(): income → consumers (in randomised order) → data collection → clock advance.", fig_no="DIAGRAM"),
)}

{section("s5", "05", "Papers &amp; provenance", "The calibrated-vs-modelled bright line",
    p("The single most important commitment of the thesis: <strong>it never hides a choice as a fact</strong>. "
      "Every number sits in one of three tiers, marked at the point of use in the code."),
    '<div class="tiers">'
    '<div class="tcard" style="--tc:var(--tier1)"><h4>① Italian, calibrated</h4>'
    '<p>Taken directly from a public Italian source, section-cited — SHIW 2022, the Payment Behaviour Survey, Emiliozzi et al. (2023) card data, the wire-transfer paper.</p></div>'
    '<div class="tcard" style="--tc:var(--tier2)"><h4>② Behavioural — shape grounded</h4>'
    '<p>The behaviour exists because the literature says so; its euro/percentage magnitude is a modelling choice and is <em>swept</em>, never claimed as an Italian fact.</p></div>'
    '<div class="tcard" style="--tc:var(--tier3)"><h4>③ Structural choice</h4>'
    '<p>No paper at all — the debt stock, the three archetypes, per-source dispersion. Flagged at point of use and swept in <code>sweep_behavioural.py</code>.</p></div>'
    '</div>',
    paper_table(),
    plate("d05_provenance_tiers", DIA, cap="The nine papers placed on the three tiers — the audit trail a reader can follow from any number back to its source.", fig_no="DIAGRAM"),
)}

{section("s6", "06", "Datasets", "What the model produces, and its schema",
    p("A single run yields three reconcilable views. The active path writes two CSVs; a parked, more formal "
      "engine writes a 21-column Parquet ledger with a provenance sidecar. All simulation outputs are "
      "regenerated on demand (gitignored) and are deterministic for a fixed seed."),
    '<div class="cols"><div><h3 class="sub">Transaction ledger — 7 columns</h3>'
    '<p class="prose" style="font-size:14.5px">One row per money movement (<code>model.transactions</code>).</p>'
    + ledger_table() +
    '</div><div><h3 class="sub">The other two views</h3>'
    '<div class="callout" style="margin-top:0"><b>Accounts snapshot</b> — one row per (consumer, account), '
    '17 columns: area, income source/level/quartile, financial status, debtor subtype, debt balance, '
    'balances &amp; totals per account.</div>'
    '<div class="callout"><b>Per-day time series</b> — <code>daily_txn_count</code>, <code>daily_eur_total</code>, '
    'debt total &amp; headcount per subtype, and mean balance grouped by income source, level, and subtype. '
    'This is what the trajectory charts read.</div></div></div>',
)}

{section("s7", "07", "The data in motion", "The generated dataset, straight from the live model",
    p("These eight figures come from a fresh 150-consumer, 120-day run (seed 42) — the raw stream, the "
      "calibration checks, the behavioural layer, and the emergent heterogeneity."),
    gallery(
        plate("f01_txn_volume", FIG, fig_no="Fig 1"),
        plate("f04_payday_spike", FIG, fig_no="Fig 2"),
        plate("f02_spend_mix_vs_paper", FIG, fig_no="Fig 3"),
        plate("f03_spend_by_area", FIG, fig_no="Fig 4"),
        plate("f06_income_composition", FIG, fig_no="Fig 5"),
        plate("f08_income_distribution", FIG, fig_no="Fig 6"),
    ),
    gallery(
        plate("f07_balance_by_source", FIG, fig_no="Fig 7"),
        plate("f05_behavioural_events", FIG, fig_no="Fig 8"),
    ),
)}

{section("s8", "08", "Debt as a stock", "Climbers, the chronically stuck, and subsisters",
    p("Debt is modelled as a <strong>stock</strong> — a principal that accrues interest — and debtors split "
      "into three behavioural archetypes with divergent repayment rules. Over a 720-day run the trajectories "
      "separate cleanly: <strong>climbers</strong> repay and leave debt, <strong>chronic</strong> debtors pay "
      "interest only and never escape, <strong>subsisters</strong> borrow to survive and drift up. The tilt "
      "toward the chronic archetype is anchored to SHIW's own financial-vulnerability definition."),
    gallery(
        plate("f09_debt_stock_by_subtype", FIG, fig_no="Fig 9"),
        plate("f10_balance_by_subtype", FIG, fig_no="Fig 10"),
        plate("f12_still_in_debt", FIG, fig_no="Fig 11"),
        plate("f11_debtor_composition", FIG, fig_no="Fig 12"),
    ),
)}

{section("s9", "09", "Validation", "Can the archetypes be recovered from behaviour?",
    p("Two studies test whether the structure the model builds in is recoverable from the output alone "
      "(600 consumers, 720 days). <strong>Unsupervised clustering</strong> of the debtor subpopulation "
      "recovers the three archetypes (ARI ≈ 0.39 with debt-mechanic features). <strong>Prediction</strong> of "
      "who holds debt reaches AUC ≈ 0.68 from honest behavioural features alone — and a near-perfect 1.00 once "
      "debt-mechanic proxies are added, a deliberate demonstration of label leakage."),
    gallery(
        plate("f13_clustering_pca", FIG, fig_no="Fig 13"),
        plate("f14_cluster_recovery", FIG, fig_no="Fig 14"),
    ),
    gallery(plate("f15_prediction", FIG, fig_no="Fig 15")),
)}

{section("s10", "10", "Status &amp; next", "Where the work stands",
    p("The engine runs, the tests pass (including money-conservation and determinism), the datasets and this "
      "figure set regenerate with one command, and the live dashboard shows the model moving. Honest open items:"),
    '<ul class="steps">'
    '<li><b>Behavioural magnitudes are non-Italian.</b> Mitigated by sweeping every one of them, not removed.</li>'
    '<li><b>Two overlapping debt views</b> (recurring mortgage/loan bills vs the SHIW aggregate service line) are deliberately not reconciled — a documented teaching-prototype simplification.</li>'
    '<li><b>Income-source headcounts are proxies.</b> SHIW gives income levels per source, not the share of each source; flagged and swept.</li>'
    '<li><b>No life-cycle or macro dynamics</b> yet — static employment, no inflation, no ageing. Roadmap in <code>PROPOSAL_financial_depth.md</code>: overdraft depth, real pension contributions, multi-year big-ticket purchases.</li>'
    '</ul>',
    '<div class="callout"><b>Bottom line for the defence:</b> a reader can audit every number&rsquo;s tier, '
    'reproduce any run byte-for-byte, and watch the calibrated and behavioural mechanisms fall out of simple '
    'per-agent rules — realistic where calibrated, honest where not.</div>',
)}

<footer>synthitaly · figures &amp; diagrams generated from the live model (seed 42) · regenerate with
<code>generate_figures.py</code> → <code>make_diagrams.py</code> → <code>build_deck.py</code></footer>
</div>
</div>
"""


def main():
    out = ROOT / "status_deck.html"
    out.write_text(HTML, encoding="utf-8")
    kb = out.stat().st_size / 1024
    print(f"wrote {out}  ({kb:.0f} KB)")


if __name__ == "__main__":
    main()
