#!/usr/bin/env python3
"""Build the dataset appendix — schema + summary statistics for every table the model makes.

    uv run python scripts/build_data_appendix.py [--out runs/latest] [--consumers 800] [--days 720]

Runs the model once at the pinned configuration, then documents each dataset it
produces: what it is, what produces it, one row per column with dtype / unit /
domain / provenance, and the summary statistics an appendix needs — five-number
summaries for numeric columns, level counts and shares for categorical ones.

Everything is *measured*, not transcribed. The column lists come from the frames
themselves, so a column added to the model shows up here without anyone
remembering to write it down. That matters: the hand-maintained data dictionary in
``notebooks/analysis.ipynb`` cell 6 had drifted from the code — it listed
``savings_sweep``/``pension_sweep`` as ledger categories (false, and precisely the
fact the saver-leak argument turns on) and omitted ``income_level`` from the
accounts export. Both are now corrected there; a generated table cannot drift
that way in the first place.

Side effect, deliberate: writes the per-consumer feature frame to CSV. It is the
richest table in the project — 46 columns — and until now it was rebuilt in memory
four separate times and never persisted.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "presentation" / "scripts"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "src"))

from _report import (  # noqa: E402
    callout,
    esc,
    nav,
    p,
    page,
    section,
    src,
    table,
    tiles,
)

from synthitaly import features as F  # noqa: E402
from synthitaly import numbers as N  # noqa: E402
from synthitaly.model import ItalyModel  # noqa: E402

MAX_LEVELS = 30  # categorical columns with more levels than this are summarised, not listed


# --------------------------------------------------------------------------- #
# Summary statistics
# --------------------------------------------------------------------------- #
def numeric_summary(df: pd.DataFrame, cols: list[str]) -> str:
    """Five-number summary plus mean/std/zeros for every numeric column."""
    rows = []
    for c in cols:
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        if s.empty:
            continue
        rows.append([
            f"<code>{esc(c)}</code>", f"{len(s):,}",
            f"{s.mean():,.2f}", f"{s.std():,.2f}", f"{s.min():,.2f}",
            f"{s.quantile(.25):,.2f}", f"{s.median():,.2f}", f"{s.quantile(.75):,.2f}",
            f"{s.max():,.2f}", f"{(s == 0).mean():.0%}",
        ])
    return table(
        ["column", "n", "mean", "std", "min", "q25", "median", "q75", "max", "zeros"],
        rows, "lrrrrrrrrr",
    )


def categorical_summary(df: pd.DataFrame, cols: list[str]) -> str:
    """Level counts and shares. Wide columns are truncated with the remainder named."""
    blocks = []
    for c in cols:
        vc = df[c].astype("object").where(df[c].notna(), "∅ (none)").value_counts(dropna=False)
        shown = vc.head(MAX_LEVELS)
        rows = [[f"<code>{esc(k)}</code>", f"{v:,}", f"{v / len(df):.1%}"]
                for k, v in shown.items()]
        extra = ""
        if len(vc) > MAX_LEVELS:
            extra = (f"<p class='note'>{len(vc) - MAX_LEVELS} further level(s) not shown, "
                     f"covering {vc.iloc[MAX_LEVELS:].sum() / len(df):.1%} of rows.</p>")
        blocks.append(
            f"<h4><code>{esc(c)}</code> — {len(vc)} distinct level(s)</h4>"
            + table(["level", "count", "share"], rows, "lrr") + extra
        )
    return "".join(blocks)


def schema_table(df: pd.DataFrame, notes: dict[str, tuple[str, str]]) -> str:
    """One row per column: dtype, unit/domain, meaning, provenance.

    ``notes`` maps column name -> (unit or domain, description). A column with no
    entry still appears — with its description blank — so an undocumented new
    column is visible rather than silently omitted.
    """
    rows = []
    for c in df.columns:
        unit, desc = notes.get(c, ("", "<span class='warn'>undocumented</span>"))
        rows.append([f"<code>{esc(c)}</code>", f"<code>{df[c].dtype}</code>", unit, desc])
    return table(["column", "dtype", "unit / domain", "meaning"], rows, "llll")


def split_cols(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    num_cols, cat_cols = [], []
    for c in df.columns:
        if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c]):
            num_cols.append(c)
        else:
            cat_cols.append(c)
    return num_cols, cat_cols


# --------------------------------------------------------------------------- #
# Per-dataset column documentation
# --------------------------------------------------------------------------- #
TXN_NOTES = {
    "date": ("ISO date", "the simulated day the movement happened"),
    "kind": ("salary · bill · purchase · fee · loan",
             "the coarse class of movement — this is the field every downstream "
             "aggregation groups on"),
    "from": ("agent id", "payer. A consumer id for purchases/bills/fees; a stand-in id for "
                         "salaries and credit draws"),
    "to": ("agent id", "payee"),
    "category": ("see levels below",
                 "the specific reason: one of 10 spend categories, 5 bill types, a fee type, "
                 "<code>credit_draw</code>, or an income category"),
    "amount_eur": ("€, 2 dp", "always positive — direction is carried by <code>kind</code> "
                              "and the from/to pair, never by the sign"),
    "macro_area": ("NORTH · CENTRE · SOUTH", "the payer's macro-area"),
}

ACC_NOTES = {
    "owner_id": ("string", "account owner — <code>&lt;id&gt;</code>, "
                           "<code>&lt;id&gt;_savings</code> or <code>&lt;id&gt;_pension</code>"),
    "consumer_id": ("int", "the household this account belongs to"),
    "macro_area": ("NORTH · CENTRE · SOUTH", "geography"),
    "income_source": ("payroll · self_employed · pension · transfers · unemployed",
                      "primary income source"),
    "income_level": ("low · middle · high",
                     "<b>absolute</b> euro bands (≤€1,000 / €1,000–4,000 / &gt;€4,000) from "
                     "the Payment Behaviour Survey — not percentiles"),
    "income_quartile": ("1–4", "<b>empirical</b> quartile of this run's realised incomes; "
                               "SHIW reports debt by quartile"),
    "income_quintile": ("1–5", "<b>empirical</b> quintile; SHIW reports saving by quintile"),
    "financial_status": ("saver · non_saver ± +debt", "the 2×2 of saving and debt"),
    "debtor_subtype": ("climber · chronic · subsister · ∅",
                       "the debt archetype; ∅ for households that never held debt"),
    "debt_balance": ("€", "outstanding principal at end of run — <b>a stock</b>, repeated on "
                          "all three account rows of the same household"),
    "cluster": ("string", "<code>AREA | Qn | status</code> — the composite grouping key"),
    "account_type": ("current · savings · pension", "which of the household's three accounts"),
    "starting_balance": ("€", "opening balance: one month's income for current (zero for "
                              "subsisters), zero for savings and pension"),
    "balance": ("€", "closing balance; can be negative on current for chronic debtors only"),
    "n_entries": ("count", "statement lines on this account"),
    "total_in": ("€", "sum of credits"),
    "total_out": ("€", "sum of debits"),
}

LABEL_NOTES = {
    "consumer_id": ("int", "join key"),
    "debtor_subtype": ("climber · chronic · subsister · none", "ground-truth archetype"),
    "is_debtor": ("bool", "held debt at construction"),
    "is_climber": ("bool", "archetype is climber"),
    "income_source": ("category", "ground-truth income source"),
    "income_level": ("low · middle · high", "ground-truth absolute income band"),
    "financial_status": ("category", "the 2×2 of saving and debt"),
    "is_saver": ("bool", "sweeps a positive month-end residual"),
    "macro_area": ("category", "geography"),
}


def feature_notes(frame: pd.DataFrame) -> dict[str, tuple[str, str]]:
    """Classify every feature column as fair / LEAK_ / LEAK_SAVER, with the reason."""
    fair = set(F.fair_columns(frame))
    leak = set(F.leak_columns(frame))
    saver_fair = set(F.saver_fair_columns(frame))
    notes: dict[str, tuple[str, str]] = {
        "consumer_id": ("int", "join key — not a feature"),
    }
    for c in frame.columns:
        if c == "consumer_id":
            continue
        if c in leak:
            tag = ('<span class="tier tier3">LEAK_</span> ',
                   "mechanically encodes the <b>debtor</b> label — a "
                   "<code>debt_service</code> line exists only for a debtor, a "
                   "<code>credit_draw</code> only for a subsister, an "
                   "<code>overdraft_fee</code> only for a chronic")
        elif c in fair and c not in saver_fair:
            tag = ('<span class="tier tier2">LEAK_SAVER</span> ',
                   "fair for the debtor label but <b>not</b> for the saver label — the "
                   "month-close sweep is a debit on the current account, so this column "
                   "carries <code>is_saver</code> directly")
        else:
            tag = ('<span class="tier tier1">fair</span> ',
                   "ordinary activity a bank could observe without knowing the answer")
        notes[c] = ("float64", tag[0] + tag[1])
    # A few columns deserve their own line rather than the generic class description.
    notes["LEAK_cur_n_entries"] = (
        "float64",
        '<span class="tier tier3">LEAK_</span> <b>the one that hid.</b> A raw count of '
        "current-account entries — fair-sounding, but it includes the debt-service, "
        "credit-draw and overdraft lines. Left in the fair set it inflated the headline "
        "debtor AUC from 0.697 to 0.91.")
    notes["post_payday_share"] = (
        "float64",
        '<span class="tier tier1">fair</span> share of purchase euros falling in the week '
        "after payday — the behavioural spike, per household")
    notes["balance_std_proxy"] = (
        "float64",
        '<span class="tier tier1">fair</span> volatility of a reconstructed balance path. '
        "Correlates +0.40 with <code>is_saver</code> and still stays: it is "
        "transaction-derived, and sweeps are never written to the ledger")
    return notes


# --------------------------------------------------------------------------- #
def dataset_section(sid: str, kicker: str, title: str, *, intro: str, produced_by: str,
                    grain: str, persisted: str, df: pd.DataFrame,
                    notes: dict, extra: str = "") -> str:
    num_cols, cat_cols = split_cols(df)
    facts = table(
        ["", ""],
        [["<b>Produced by</b>", produced_by],
         ["<b>Row grain</b>", grain],
         ["<b>Shape</b>", f"{len(df):,} rows × {len(df.columns)} columns"],
         ["<b>Persisted to disk?</b>", persisted]],
        "ll",
    )
    blocks = [p(intro), facts, "<h3>Schema</h3>", schema_table(df, notes)]
    if num_cols:
        blocks += ["<h3>Numeric summary</h3>", numeric_summary(df, num_cols)]
    if cat_cols:
        blocks += ["<h3>Categorical levels</h3>", categorical_summary(df, cat_cols)]
    if extra:
        blocks.append(extra)
    return section(sid, kicker, title, *blocks)


def build(model: ItalyModel, out_dir: Path, generated: str) -> str:
    tx = pd.DataFrame(model.transactions)
    acc = pd.DataFrame(model.export_accounts())
    dc = model.datacollector.get_model_vars_dataframe()
    feats = F.build_features(model)
    labs = F.label_frame(model)

    # Persist the feature frame — the richest table here and the only one that was
    # being rebuilt from scratch by four separate callers and never written.
    feat_csv = out_dir / "features.csv"
    feats.to_csv(feat_csv, index=False)

    cfg_tiles = tiles([
        ("consumers", f"{len(model.consumers):,}", "households"),
        ("days", f"{model.n_days:,}", f"seed {model.seed_value}"),
        ("ledger rows", f"{len(tx):,}", "one per money movement"),
        ("account rows", f"{len(acc):,}", "3 per household"),
        ("feature columns", f"{feats.shape[1] - 1}",
         f"{len(F.fair_columns(feats))} fair · {len(F.leak_columns(feats))} leak"),
        ("datasets", "6", "documented below"),
    ])

    intro = section(
        "about", "Appendix", "What this document is",
        p("Every table the simulation produces, with its schema and its summary statistics, "
          "at the pinned configuration used for every number in the thesis. Written to be "
          "lifted into an appendix."),
        cfg_tiles,
        callout(
            "<b>The model writes nothing to disk on its own.</b> "
            f"{src('model.py:936-938')} is explicit about it — callers decide what to "
            "persist. So “dataset” here means a table the model <i>hands you</i>; where it "
            "ends up is a choice made by a notebook or a script. The persistence status of "
            "each is stated in its section."),
        callout(
            "<b>There are no input datasets.</b> The active model reads no external file at "
            "all — every empirical figure is a paper-cited constant in "
            "<code>src/synthitaly/numbers.py</code>. That is unusual enough to state "
            "plainly: reproducing these tables needs the code and a seed, nothing else.",
            "ok"),
    )

    s_txn = dataset_section(
        "ledger", "Dataset 1", "Transaction ledger",
        intro="The flat, bank-statement-style record — one row per money movement, and the "
              "table most downstream analysis starts from.",
        produced_by=f"<code>ItalyModel._log_txn()</code> · {src('model.py:970-994')}, "
                    "accumulated on <code>model.transactions</code>",
        grain="one row per money movement",
        persisted="written by <code>notebooks/analysis.ipynb</code> to "
                  "<code>notebooks/demo_transactions.csv</code> (gitignored)",
        df=tx, notes=TXN_NOTES,
        extra=callout(
            "<b>The month-end savings and pension sweeps are deliberately absent from this "
            "table.</b> They exist only on the per-account statement (Dataset 6). This is not "
            "an oversight and it is load-bearing: it is exactly why "
            "<code>balance_std_proxy</code> — which is derived from this ledger — stays in "
            "the fair feature set for the saver label. The data dictionary in "
            "<code>notebooks/analysis.ipynb</code> used to claim a <code>savings_sweep</code> "
            "category here; it was wrong, and has been corrected.", "warn"),
    )

    s_acc = dataset_section(
        "accounts", "Dataset 2", "Accounts snapshot",
        intro="End-of-run state, one row per (household, account). Carries the ground-truth "
              "labels alongside the balances, which is convenient and also why it must never "
              "be fed to a model wholesale.",
        produced_by=f"<code>ItalyModel.export_accounts()</code> · {src('model.py:935-964')}",
        grain="one row per (household, account type) — three per household",
        persisted="written by <code>notebooks/analysis.ipynb</code> to "
                  "<code>notebooks/demo_accounts.csv</code> (gitignored)",
        df=acc, notes=ACC_NOTES,
    )

    dc_notes = {c: ("float", "") for c in dc.columns}
    dc_notes.update({
        "daily_txn_count": ("count", "transactions written that day"),
        "daily_eur_total": ("€", "total euro moved that day"),
    })
    for st in N.DEBTOR_SUBTYPES:
        dc_notes[f"debt_total_{st}"] = ("€", f"total outstanding principal held by {st}s")
        dc_notes[f"debt_indebt_{st}"] = ("count", f"{st}s still in debt that day")
    for k in N.INCOME_SOURCE_SHARE:
        dc_notes[f"bal_cur_src_{k}"] = ("€", f"mean current balance, {k} households")
    for k in ("low", "middle", "high"):
        dc_notes[f"bal_cur_lvl_{k}"] = ("€", f"mean current balance, {k}-income households")
    for st in N.DEBTOR_SUBTYPES:
        dc_notes[f"bal_cur_dst_{st}"] = ("€", f"mean current balance, {st}s")

    s_dc = dataset_section(
        "timeseries", "Dataset 3", "Per-day model time series",
        intro="The daily panel — what makes trajectories visible rather than just endpoints. "
              "Every balance series here is a <b>mean over a group</b>, so it smooths the "
              "individual payday sawtooth into the group's.",
        produced_by=f"Mesa <code>DataCollector</code> reporters · {src('model.py:801-829')}, "
                    f"reading <code>group_balances()</code> {src('model.py:906-933')}",
        grain="one row per simulated day",
        persisted="<b>never</b> — read live from the model by the figure script and the "
                  "dashboard",
        df=dc, notes=dc_notes,
        extra=callout(
            "A household with no debtor subtype is simply absent from the <code>dst</code> "
            "grouping rather than counted as zero, so <code>bal_cur_dst_*</code> means "
            "“mean among that archetype”, not “mean over everyone”. Groups with no members "
            "report 0.0, which is indistinguishable from a real zero mean — worth knowing "
            "before plotting the first few days of a small run."),
    )

    s_feat = dataset_section(
        "features", "Dataset 4", "Per-consumer feature frame",
        intro="The analysis table: one row per household, derived <b>only</b> from the two "
              "exported tables above, so nothing enters it that a bank could not observe — "
              "with the deliberate exception of the quarantined blocks.",
        produced_by=f"<code>synthitaly.features.build_features()</code> · "
                    f"{src('features.py:109-218')}",
        grain="one row per household",
        persisted=f"<b>written by this script</b> to <code>{esc(feat_csv.name)}</code>",
        df=feats, notes=feature_notes(feats),
        extra=callout(
            "<b>Fair is relative to the label, not a property of the column.</b> The three "
            "classes above are: <span class='tier tier1'>fair</span> for both labels; "
            "<span class='tier tier2'>LEAK_SAVER</span> — fair for the debtor label only; "
            "<span class='tier tier3'>LEAK_</span> — encodes the debtor label mechanically. "
            "Use <code>fair_columns()</code> when the target is <code>is_debtor</code> and "
            "<code>saver_fair_columns()</code> when it is <code>is_saver</code>."),
    )

    s_lab = dataset_section(
        "labels", "Dataset 5", "Label frame (ground truth)",
        intro="The things a bank does <b>not</b> see. Used only for scoring — never as model "
              "input. Kept in a separate frame from the features precisely so the two cannot "
              "be mixed by accident.",
        produced_by=f"<code>synthitaly.features.label_frame()</code> · "
                    f"{src('features.py:221-233')}",
        grain="one row per household",
        persisted="<b>never</b> — rebuilt on demand",
        df=labs, notes=LABEL_NOTES,
    )

    # Dataset 6 — the statement view. Materialised here for documentation; the
    # model exposes it only through the per-account entry lists.
    entries = pd.DataFrame([
        {"consumer_id": c.unique_id, "account_type": name, "date": e.date,
         "direction": e.direction, "counterparty": e.counterparty,
         "category": e.category, "amount_eur": e.amount_eur}
        for c in model.consumers
        for name, a in c.accounts.as_dict().items()
        for e in a.entries
    ])
    ent_notes = {
        "consumer_id": ("int", "the household"),
        "account_type": ("current · savings · pension", "which account the line is on"),
        "date": ("ISO date", "the simulated day"),
        "direction": ("in · out", "credit or debit — here direction <i>is</i> explicit, "
                                  "unlike the ledger"),
        "counterparty": ("agent id", "the other side of the movement"),
        "category": ("see levels below",
                     "as the ledger, <b>plus</b> <code>savings_sweep</code> and "
                     "<code>pension_sweep</code>, which appear nowhere else"),
        "amount_eur": ("€", "always positive"),
    }
    s_ent = dataset_section(
        "statements", "Dataset 6", "Per-account statement entries",
        intro="The per-account view. This is the only place the month-end sweeps are visible, "
              "which makes it the reference for reconciling any balance by hand.",
        produced_by=f"<code>BankEntry</code> records on each account · {src('model.py:49-57')}, "
                    "surfaced in the dashboard's account inspector",
        grain="one row per statement line, per account",
        persisted="<b>never</b> — materialised here for documentation only",
        df=entries, notes=ent_notes,
        extra=callout(
            "Compare the <code>category</code> levels here with Dataset 1: "
            "<code>savings_sweep</code> and <code>pension_sweep</code> are present here and "
            "absent there. That difference is the mechanism behind the "
            "<code>LEAK_SAVER</code> quarantine.", "ok"),
    )

    recon = section(
        "reconcile", "Appendix", "How the tables reconcile",
        p("Four independent views of the same run. They agree, and the agreement is tested:"),
        table(
            ["Identity", "Meaning", "Tested by"],
            [["Σ all balances = Σ all opening balances",
              "money is conserved system-wide — every movement is a paired debit and credit",
              "<code>tests/test_conservation.py</code>"],
             ["account <code>balance</code> = <code>starting_balance</code> + "
              "<code>total_in</code> − <code>total_out</code>",
              "each account reconciles against its own statement lines",
              "<code>tests/test_smoke.py</code>"],
             ["Σ ledger <code>amount_eur</code> by household ≈ statement lines minus sweeps",
              "the ledger is the statement without the internal transfers",
              "by construction — see Dataset 1"],
             ["feature frame ⊂ ledger + accounts",
              "no feature reads agent internals except the quarantined blocks",
              "<code>tests/test_analysis_pipeline.py</code>"]],
            "lll",
        ),
        callout(
            "<b>Interest is the one movement with no row anywhere.</b> It increments "
            "<code>debt_balance</code> directly. That is what lets debt grow while money still "
            "conserves — the principal is a claim, not cash, and no cash moves when it "
            "accrues."),
    )

    links = [("about", "About"), ("ledger", "1 · Ledger"), ("accounts", "2 · Accounts"),
             ("timeseries", "3 · Time series"), ("features", "4 · Features"),
             ("labels", "5 · Labels"), ("statements", "6 · Statements"),
             ("reconcile", "Reconciliation")]
    body = "".join([intro, s_txn, s_acc, s_dc, s_feat, s_lab, s_ent, recon])
    return page(
        title="synthitaly — dataset appendix",
        heading="Dataset appendix",
        sub="Every table the model produces — schema, data types, domains and summary "
            "statistics.",
        meta=f"Generated {generated} · measured at {len(model.consumers):,} consumers × "
             f"{model.n_days:,} days, seed {model.seed_value} · reproduce with "
             f"<code>uv run python scripts/build_data_appendix.py</code>",
        navbar=nav(links),
        body=body,
        footer="synthitaly · self-contained, no network requests · companion pages: "
               "<code>flows_and_papers.html</code>, <code>savers_and_debt.html</code>, "
               "<code>results.html</code>",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=Path("runs/latest"), type=Path)
    ap.add_argument("--consumers", type=int, default=800)
    ap.add_argument("--days", type=int, default=720)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    print(f"building model — {args.consumers} consumers × {args.days} days, seed {args.seed}")
    model = ItalyModel(n_consumers=args.consumers, n_merchants_per_category=3,
                       n_days=args.days, seed=args.seed)
    model.seed_value = args.seed          # for display; Mesa does not keep it
    model.run()

    out = args.out / "data_appendix.html"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    out.write_text(build(model, args.out, esc(stamp)), encoding="utf-8")
    print(f"wrote {out}  ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
