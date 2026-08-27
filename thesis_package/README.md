# synthitaly — thesis package

Built **2026-08-24 17:59** by `scripts/build_thesis_package.py`.
Open **`index.html`** for the linked entry point.

## What this is

One directory holding every result, figure and document produced by the project,
copied out of the three places the pipeline normally scatters them across
(`runs/`, `presentation/`, `docs/`). It is a copy, not a set of symlinks, so it
can be zipped and sent as-is.

## Provenance — read this before quoting a number

All model output in this package comes from the run directory
**`20260822-142420`**, configured as **800 consumers × 720 days, seed 42**
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
| `results/` | the five generated HTML pages (5) |
| `figures/` | 64 files — `f00_overview` + `f00_overview_v2` (two variants under comparison) plus 19 result figures as PNG + SVG + PDF, and `CAPTIONS.md` (f01–f19) |
| `diagrams/` | 17 files — d01–d06 as PNG + SVG, `.mmd` source for d01–d05 |
| `data/` | `features.csv` and the four machine-readable result JSONs |
| `reports/` | `validation_report.md` and the pipeline log |
| `notebooks/` | 4 executed notebooks as HTML |
| `docs/` | the repository's prose documentation |
| `evidence/` | the provenance pack — result JSONs, `features.csv`, five caveated figures, and two listings generated from the code itself. Written separately by `scripts/build_evidence_pack.py`, which must run *after* this script. **`--clean` deletes it.** |

## The ODD figure

`diagrams/d06_odd_overview.{png,svg}` is a single composite schematic of the
whole ODD protocol, laid out in ODD order: **A** entities and state variables
(§1.2), **B** process overview and scheduling (§1.3) with the month calendar, and
**C** submodels (§3.3) each tagged with its source, over the design concepts of
§2. The ⚠ glyph marks a parameter that `docs/ODD.md` flags as a modelling choice
rather than a calibrated value. Use the SVG for print.

## Missing artefacts at build time

- none — every expected artefact was present.

## Rebuilding

```bash
uv run python scripts/run_all.py                       # the full 13-stage pipeline
uv run python scripts/build_thesis_package.py          # then re-collect
```
