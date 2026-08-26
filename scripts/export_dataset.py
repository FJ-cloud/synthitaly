#!/usr/bin/env python3
"""Export every dataset the model produces, as CSV, in one command.

    uv run python scripts/export_dataset.py                      # pinned config -> exports/
    uv run python scripts/export_dataset.py --consumers 2000 --days 1080 --seed 7 --out ~/data

Runs the simulation once and writes each table it produces to its own CSV, plus a
MANIFEST.md recording the configuration and the shape of every file. The defaults
reproduce the configuration every number in the thesis comes from — 800 consumers
x 720 days, seed 42 — so ``features.csv`` written here is the same frame as
``runs/latest/features.csv``.

This exists because getting data out used to mean opening a notebook. The two
account/ledger CSVs were only written by ``notebooks/analysis.ipynb`` (at 300 x 365,
into ``notebooks/``), the feature frame only fell out of ``build_data_appendix.py``
as a side effect, and the month-end credit panel was reachable only from inside the
three replication scripts. Nothing produced them together, at a chosen size, in a
chosen folder.

Writes only inside ``--out``. Nothing here touches ``runs/``, so exporting can never
disturb the pinned run. What each column means is documented in
``runs/latest/data_appendix.html``.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from synthitaly import ItalyModel  # noqa: E402
from synthitaly import features as F  # noqa: E402
from synthitaly import panel as P  # noqa: E402


def build_frames(model: ItalyModel) -> dict[str, pd.DataFrame]:
    """Every table the model produces, keyed by the filename it should get.

    Each one comes from the same single run, so the ledger, the accounts and the
    derived frames are guaranteed to correspond — which is the whole point of
    exporting them together rather than a notebook at a time.
    """
    return {
        "transactions": pd.DataFrame(model.transactions),
        "accounts": pd.DataFrame(model.export_accounts()),
        "features": F.build_features(model),
        "labels": F.label_frame(model),
        "daily_kpis": model.datacollector.get_model_vars_dataframe(),
        "credit_panel": P.build_panel(model),
    }


# What each file is, in one line — used for the manifest and the console output.
DESCRIPTIONS: dict[str, str] = {
    "transactions": "one row per money movement: salaries in, bills and purchases out, fees",
    "accounts": "one row per (consumer, account) — current / savings / pension balances",
    "features": "one row per consumer: the behavioural feature frame the analysis uses",
    "labels": "one row per consumer: the ground truth a bank does NOT see, for scoring only",
    "daily_kpis": "one row per simulated day: transaction count and EUR total",
    "credit_panel": "one row per (consumer, month) with trailing 6-month history",
}


def manifest(frames: dict[str, pd.DataFrame], args: argparse.Namespace, stamp: str) -> str:
    """A README for the export, with the shapes read off the frames rather than typed."""
    rows = "\n".join(
        f"| `{name}.csv` | {len(df):,} | {df.shape[1]} | {DESCRIPTIONS[name]} |"
        for name, df in frames.items()
    )
    feats = frames["features"]
    pinned = (args.consumers, args.days, args.seed, args.merchants) == (800, 720, 42, 3)
    pinned_note = (
        "This is the **pinned thesis configuration**, so `features.csv` here is the same\n"
        "frame as `runs/latest/features.csv`.\n"
        if pinned
        else "This is **not** the pinned thesis configuration (800 x 720, seed 42), so these\n"
        "numbers will not match the ones reported in the thesis.\n"
    )
    return f"""# Dataset export

Generated {stamp} by `scripts/export_dataset.py`.

## Configuration

| | |
|---|---|
| consumers | {args.consumers:,} |
| days | {args.days:,} |
| merchants per category per macro-area | {args.merchants} |
| seed | {args.seed} |

{pinned_note}
The model is seeded, so re-running this command with the same flags reproduces
every file below byte-for-byte.

## Files

| File | Rows | Columns | What it is |
|---|---:|---:|---|
{rows}

## Notes

- `features.csv` carries {len(F.fair_columns(feats))} *fair* columns (things a bank could
  actually observe) and {len(F.leak_columns(feats))} `LEAK_` columns. The `LEAK_` prefix marks
  features the debt machinery writes the label into — they are the control condition,
  not features to model with. See `docs/VALIDATION.md`.
- `labels.csv` joins to every other per-consumer file on `consumer_id`. Keep it out of
  any feature set: it is the answer key.
- Column-by-column definitions, dtypes and summary statistics for all of these are in
  `runs/latest/data_appendix.html`.
"""


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Export every dataset the model produces, as CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--out", default=Path("exports"), type=Path,
                    help="directory to write into (default: exports/)")
    ap.add_argument("--consumers", type=int, default=800, help="households to simulate")
    ap.add_argument("--days", type=int, default=720, help="days to simulate")
    ap.add_argument("--merchants", type=int, default=3,
                    help="merchants per category per macro-area")
    ap.add_argument("--seed", type=int, default=42, help="random seed")
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    print(f"running the model — {args.consumers:,} consumers x {args.days:,} days, "
          f"seed {args.seed} (this takes a moment)")
    model = ItalyModel(
        n_consumers=args.consumers,
        n_merchants_per_category=args.merchants,
        n_days=args.days,
        seed=args.seed,
    )
    model.run()

    frames = build_frames(model)
    for name, df in frames.items():
        path = args.out / f"{name}.csv"
        # daily_kpis is indexed by step; every other frame has a meaningful default index.
        df.to_csv(path, index=(name == "daily_kpis"))
        print(f"  wrote {path}  ({len(df):,} rows x {df.shape[1]} cols)")

    # The panel drops every row before a full trailing window has accrued, so a short
    # run yields a header and nothing else. Say so rather than leaving an empty file.
    if frames["credit_panel"].empty:
        print(f"\nnote: credit_panel.csv is empty. It needs {P.LOOKBACK_MONTHS} months of "
              f"history per row, and {args.days} days does not cover that.\n"
              f"      Re-run with --days 720 (the thesis configuration) or more.")

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    man = args.out / "MANIFEST.md"
    man.write_text(manifest(frames, args, stamp), encoding="utf-8")
    print(f"  wrote {man}")

    print(f"\ndone — {len(frames) + 1} files in {args.out}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
