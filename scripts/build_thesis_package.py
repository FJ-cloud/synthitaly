#!/usr/bin/env python3
"""Collect everything a writer needs into one hand-off directory.

The analysis pipeline scatters its output across three places — ``runs/<stamp>/``
for the generated pages and data, ``presentation/`` for the figures and diagrams,
and ``docs/`` for the prose. That is the right layout for running the pipeline and
the wrong one for handing the work to someone who has to write with it.

This script copies the three into a single tree and writes an ``index.html`` over
the top. It copies rather than symlinks, so the directory can be zipped and sent.

Run:  uv run python scripts/build_thesis_package.py
      uv run python scripts/build_thesis_package.py --out thesis_package --run runs/latest

Provenance is the point of the README it writes: the figure layer and the model
outputs are generally built at different times, and a package that hides that is
worse than no package.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import shutil
from pathlib import Path

from _report import esc, nav, page, section

ROOT = Path(__file__).resolve().parent.parent
FIGURES = ROOT / "presentation" / "figures"
DIAGRAMS = ROOT / "presentation" / "diagrams"
DOCS = ROOT / "docs"

# (filename in the run dir, label, one-line description)
RESULT_PAGES = [
    ("results.html", "Results",
     "the browsable results page — start here; every study, with its figures"),
    ("flows_and_papers.html", "Flows & papers",
     "the money-flow map, the paper→code mapping, and the 22-item gap audit"),
    ("savers_and_debt.html", "Savers & debt",
     "the saver and debtor studies, with figures f09–f19"),
    ("data_appendix.html", "Data appendix",
     "dataset schemas and summary statistics for every exported frame"),
    ("prediction_and_papers.html", "Prediction & papers",
     "the So / Khandani / Butaru replications against the model"),
]

DATA_FILES = [
    ("features.csv",
     "the per-consumer feature frame: consumer_id + 45 features. The analysis uses 44 "
     "of them (34 fair + 10 LEAK_); n_income is constant and excluded as degenerate"),
    ("validation_report.json", "every validation number, machine-readable"),
    ("replicate_so.json", "So, Thomas, Seow & Mues — transactor/revolver scorecard"),
    ("replicate_khandani.json", "Khandani, Kim & Lo (2010) — CART, rolling windows"),
    ("replicate_butaru.json", "Butaru et al. (2015) — C4.5 vs ridge logit vs RF"),
]

REPORT_FILES = [
    ("validation_report.md", "every validation number, as text"),
    ("run_all.log", "the pipeline log for the run this package was built from"),
]

DOC_FILES = [
    ("USAGE.md", "the one-page run guide — set up, export the data, run the analysis"),
    ("ODD.md", "the ODD protocol (Grimm et al. 2020) — see diagrams/d06_odd_overview"),
    ("VALIDATION.md", "the long-form validation write-up"),
    ("METHOD_HISTORY.md", "the Q1–Q12 methodological narrative"),
    ("RUNBOOK.md", "how to reproduce every number"),
    ("MODEL_REFERENCE.md", "the data dictionary and parameter value tables"),
    ("EXPLANATION.md", "why the model is built the way it is"),
]


def _copy_tree(src: Path, dst: Path, pattern: str = "*") -> int:
    if not src.is_dir():
        return 0
    dst.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted(src.glob(pattern)):
        if f.is_file():
            shutil.copy2(f, dst / f.name)
            n += 1
    return n


def _copy_listed(src: Path, dst: Path, items) -> tuple[list, list]:
    dst.mkdir(parents=True, exist_ok=True)
    got, missing = [], []
    for name, *rest in items:
        f = src / name
        if f.is_file():
            shutil.copy2(f, dst / name)
            got.append((name, *rest))
        else:
            missing.append(name)
    return got, missing


def _index_html(run_dir: Path, counts: dict, pages, stamp: str) -> str:
    def links(items, prefix):
        return ("<ul class='steps'>" + "".join(
            f"<li><a href='{prefix}/{esc(n)}'><b>{esc(n)}</b></a> — {esc(d)}</li>"
            for n, *rest in items for d in [rest[-1]]) + "</ul>")

    body = "".join([
        section("start", "start here", "The five generated pages",
                "<ul class='steps'>" + "".join(
                    f"<li><a href='results/{esc(n)}'><b>{esc(lbl)}</b></a> — {esc(d)}</li>"
                    for n, lbl, d in pages) + "</ul>"),
        section("odd", "the model", "The ODD figure",
                "<p>A single composite schematic of the whole protocol — entities and state "
                "variables, the within-day scheduling loop, and the submodels with their "
                "sources. It is generated from <code>docs/ODD.md</code> by "
                "<code>presentation/scripts/make_diagrams.py</code>.</p>"
                "<p><a href='diagrams/d06_odd_overview.png'>d06_odd_overview.png</a> · "
                "<a href='diagrams/d06_odd_overview.svg'>.svg</a> (vector, for print)</p>"
                "<p><img src='diagrams/d06_odd_overview.svg' "
                "style='width:100%;border:1px solid #d8d7d0;border-radius:6px'></p>"
                "<p><a href='ODD_protocol.html'><b>ODD_protocol.html</b></a> — the same "
                "figure with the protocol written out around it: entities, scheduling, "
                "design concepts, and every submodel tagged with its source and its "
                "&#9888; modelling-choice flag.</p>"),
        section("writeup", "the prose", "The written results section",
                "<p><a href='RESULTS_validation.md'><b>RESULTS_validation.md</b></a> — a "
                "thesis-ready results section covering Studies 0/A/B/C/D and the three "
                "paper replications, with the limitations carried forward.</p>"),
        section("figures", "assets", f"Figures ({counts['figures']} files)",
                "<p><b>f00_overview</b> and <b>f00_overview_v2</b> — what enters the "
                "model, what happens, what comes out. Two variants under comparison: v2 "
                "draws the daily events as categories on one row rather than as a chain, "
                "because they fire on different scheduled dates. Then 19 result figures, "
                "each as PNG, SVG and PDF, plus <code>CAPTIONS.md</code> (which covers "
                "f01–f19; the f00 captions live in the thesis). "
                "Use the SVG or the PDF for print.</p>"
                "<p><a href='figures/'>browse figures/</a></p>"),
        section("diagrams", "assets", f"Diagrams ({counts['diagrams']} files)",
                "<p>d01 architecture · d02 day-step · d03 money-flow · d04 methodology "
                "pipeline · d05 provenance tiers · <b>d06 ODD overview</b>. "
                "PNG + SVG, with Mermaid source for d01–d05.</p>"
                "<p><a href='diagrams/'>browse diagrams/</a></p>"),
        section("data", "data", "Data and machine-readable results",
                links(DATA_FILES, "data")),
        section("reports", "data", "Text reports", links(REPORT_FILES, "reports")),
        section("notebooks", "notebooks", f"Executed notebooks ({counts['notebooks']})",
                "<p>demo · analysis · clustering · prediction, executed headless.</p>"
                "<p><a href='notebooks/'>browse notebooks/</a></p>"),
        section("docs", "prose", "Repository documentation", links(DOC_FILES, "docs")),
        section("evidence", "data", "Evidence pack",
                "<p>The provenance layer, written by <code>scripts/build_evidence_pack.py</code> "
                "after this script runs. It holds the result JSONs and "
                "<code>features.csv</code> again alongside five caveated figures, plus two "
                "listings that are <i>generated from the code itself</i> rather than "
                "maintained by hand: <code>feature_sets.md</code> (the fair / leak / "
                "saver-fair column sets, read off the real frame) and "
                "<code>run_configurations.md</code> (every <code>ItalyModel(...)</code> "
                "construction in the repository, found by parsing the source, which is what "
                "establishes that every figure and number comes from the same 800 × 720 "
                "configuration).</p>"
                "<p><a href='evidence/'>browse evidence/</a> · "
                "<a href='evidence/README.md'>evidence/README.md</a></p>"),
    ])
    return page(
        title="synthitaly — thesis package",
        heading="synthitaly — thesis package",
        sub="Everything from the analysis pipeline, the figure layer and the docs, "
            "collected into one directory.",
        meta=f"Built {esc(stamp)} · model outputs from <code>{esc(run_dir.name)}</code> · "
             "800 consumers × 720 days, seed 42",
        navbar=nav([("start", "Pages"), ("odd", "ODD figure"), ("writeup", "Write-up"),
                    ("figures", "Figures"), ("diagrams", "Diagrams"), ("data", "Data"),
                    ("reports", "Reports"), ("notebooks", "Notebooks"), ("docs", "Docs"),
                    ("evidence", "Evidence")]),
        body=body,
        footer="Generated by <code>scripts/build_thesis_package.py</code>, which copies "
               "rather than rebuilds. Re-run it to refresh; do <b>not</b> pass "
               "<code>--clean</code> unless you also re-run "
               "<code>build_evidence_pack.py</code> afterwards, because "
               "<code>--clean</code> deletes <code>evidence/</code>.",
    )


def _readme(run_dir: Path, counts: dict, missing: list[str], stamp: str) -> str:
    miss = ("\n".join(f"- `{m}`" for m in missing) if missing
            else "- none — every expected artefact was present.")
    return f"""# synthitaly — thesis package

Built **{stamp}** by `scripts/build_thesis_package.py`.
Open **`index.html`** for the linked entry point.

## What this is

One directory holding every result, figure and document produced by the project,
copied out of the three places the pipeline normally scatters them across
(`runs/`, `presentation/`, `docs/`). It is a copy, not a set of symlinks, so it
can be zipped and sent as-is.

## Provenance — read this before quoting a number

All model output in this package comes from the run directory
**`{run_dir.name}`**, configured as **800 consumers × 720 days, seed 42**
(3 merchants per category per area). The Butaru replication additionally uses
1,440-day runs across seeds 42–47, because a 6- or 12-month forecast horizon is
not evaluable on a 720-day run.

Two layers are built at different times, and the distinction matters:

- **Model outputs** (`data/`, `reports/`, and the five pages in `results/`) come
  from the pipeline run recorded in `reports/run_all.log`.
- **The figure layer** (`figures/`, `diagrams/`) is whatever
  `presentation/scripts/generate_figures.py` and `make_diagrams.py` last wrote.
  This script does not rebuild it.

Both layers were written by the same `run_all.py` invocation — the model outputs by
stage 3, the figures by stage 4, minutes apart — so they are the same code by
construction rather than by coincidence. That code is the 2026-08-22 chain, which
includes the category-share units fix (`e018b21`), the So-cascade seeding fix
(`0bbfd61`), the training-fold threshold fix (`755a504`) and the commit that pinned
every figure to this single run (`a3ef57a`). The units fix changed every transaction
in the model, so nothing built before 2026-08-22 is comparable with this package.

**This script copies; it does not verify.** It re-runs no model code and re-checks
no number. What underwrites the numbers is elsewhere: `validation_report.json` is
byte-deterministic for a given seed, and 21 headline values are asserted by
`pytest -m slow`, which passed on the run recorded in `reports/run_all.log`.

### Why the determinism line in `reports/run_all.log` says FAILED

It is a stale baseline, not drift. The check compares a run against the *previous*
run directory, and that one — `runs/20260817-145314` — predates the category-share
units fix, which changed every transaction in the model, so the two were expected to
differ. All 21 pinned bounds PASS in the same
log, which is the stronger check. To turn it into a genuine `MATCH`, run
`scripts/run_all.py` twice with no edits in between: it needs two runs of the same
code to have anything to compare.

## Layout

| Path | What |
|---|---|
| `index.html` | linked entry point for everything below |
| `RESULTS_validation.md` | the written results section for the validation set |
| `ODD_protocol.html` | the ODD protocol as a readable page, with the d06 figure |
| `results/` | the five generated HTML pages ({len(RESULT_PAGES)}) |
| `figures/` | {counts['figures']} files — `f00_overview` + `f00_overview_v2` (two variants under comparison) plus 19 result figures as PNG + SVG + PDF, and `CAPTIONS.md` (f01–f19) |
| `diagrams/` | {counts['diagrams']} files — d01–d06 as PNG + SVG, `.mmd` source for d01–d05 |
| `data/` | `features.csv` and the four machine-readable result JSONs |
| `reports/` | `validation_report.md` and the pipeline log |
| `notebooks/` | {counts['notebooks']} executed notebooks as HTML |
| `docs/` | the repository's prose documentation |
| `evidence/` | the provenance pack — result JSONs, `features.csv`, five caveated figures, and two listings generated from the code itself. Written separately by `scripts/build_evidence_pack.py`, which must run *after* this script. **`--clean` deletes it.** |

## The ODD figure

`diagrams/d06_odd_overview.{{png,svg}}` is a single composite schematic of the
whole ODD protocol, laid out in ODD order: **A** entities and state variables
(§1.2), **B** process overview and scheduling (§1.3) with the month calendar, and
**C** submodels (§3.3) each tagged with its source, over the design concepts of
§2. The ⚠ glyph marks a parameter that `docs/ODD.md` flags as a modelling choice
rather than a calibrated value. Use the SVG for print.

## Missing artefacts at build time

{miss}

## Rebuilding

```bash
uv run python scripts/run_all.py                       # the full 13-stage pipeline
uv run python scripts/build_thesis_package.py          # then re-collect
```
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="thesis_package",
                    help="package directory, relative to the repo root")
    ap.add_argument("--run", default="runs/latest",
                    help="the run directory to take model outputs from")
    ap.add_argument("--clean", action="store_true",
                    help="remove the package directory first")
    args = ap.parse_args()

    run_dir = (ROOT / args.run).resolve()
    out = ROOT / args.out
    if not run_dir.is_dir():
        print(f"error: run directory not found: {run_dir}")
        return 1

    if args.clean and out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"synthitaly — thesis package\n  from: {run_dir}\n  into: {out}\n")

    pages, missing = _copy_listed(run_dir, out / "results", RESULT_PAGES)
    print(f"  results/    {len(pages)} pages")
    data, m2 = _copy_listed(run_dir, out / "data", DATA_FILES)
    print(f"  data/       {len(data)} files")
    reports, m3 = _copy_listed(run_dir, out / "reports", REPORT_FILES)
    print(f"  reports/    {len(reports)} files")
    docs, m4 = _copy_listed(DOCS, out / "docs", DOC_FILES)
    print(f"  docs/       {len(docs)} files")

    # These two are hand-written rather than generated, so they live in docs/ where a
    # --clean rebuild cannot delete them, and are surfaced at the package root because
    # that is where a writer looks.
    for name in ("RESULTS_validation.md", "ODD_protocol.html"):
        src = DOCS / name
        if src.is_file():
            shutil.copy2(src, out / name)
            print(f"  {name}")
        else:
            missing.append(f"docs/{name}")

    n_fig = _copy_tree(FIGURES, out / "figures")
    print(f"  figures/    {n_fig} files")
    n_dia = _copy_tree(DIAGRAMS, out / "diagrams")
    print(f"  diagrams/   {n_dia} files")
    n_nb = _copy_tree(run_dir / "notebooks", out / "notebooks", "*.html")
    print(f"  notebooks/  {n_nb} files")

    missing += m2 + m3 + m4
    if not (DIAGRAMS / "d06_odd_overview.png").is_file():
        missing.append("diagrams/d06_odd_overview.png")

    counts = {"figures": n_fig, "diagrams": n_dia, "notebooks": n_nb}
    (out / "index.html").write_text(
        _index_html(run_dir, counts, pages, stamp), encoding="utf-8")
    (out / "README.md").write_text(
        _readme(run_dir, counts, missing, stamp), encoding="utf-8")

    print(f"\n  wrote index.html + README.md")
    if missing:
        print(f"\n  WARNING — {len(missing)} artefact(s) missing:")
        for m in missing:
            print(f"    - {m}")
    print(f"\nDone: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
