# Runbook — how to run everything

One command runs the whole thing. Everything else on this page is an optional way to look
at a piece of it more closely.

## 0. One-time setup

```bash
uv sync
```

Installs Python 3.13, Mesa, Solara, scikit-learn and the rest from `pyproject.toml`.
~30 seconds the first time, seconds thereafter. If it complains about Python, install
Python 3.13 first.

---

## 1. The one command

```bash
uv run python scripts/run_all.py
```

**About 17 minutes**, nearly all of it in `prediction-papers`. It runs thirteen
stages and prints one status line for each:

| # | Stage | What it does | ~time |
|---:|---|---|---:|
| 1 | `tests` | 129 unit / conservation / schema / determinism / diagnostics tests | 41 s |
| 2 | `tests-slow` | the pinned validation bounds (ARI and AUC floors) | 32 s |
| 3 | `validation` | builds the 800 × 720 model and measures every headline number | 31 s |
| 4 | `figures` | 19 charts from the live model, PNG + SVG | 25 s |
| 5 | `diagrams` | the 6 architecture / flow / ODD diagrams | 2 s |
| 6 | `deck` | rebuilds `presentation/status_deck.html` | <1 s |
| 7 | `results` | builds the browsable results page | <1 s |
| 8 | `flows` | money flows + paper map + gap audit | <1 s |
| 9 | `savers-debt` | the savers & debt page | <1 s |
| 10 | `data-appendix` | dataset schemas + summary stats (runs its own model) | 30 s |
| 11 | `prediction-papers` | the So / Khandani / Butaru replications (six 1,440-day runs) | 714 s |
| 12 | `notebooks` | executes all four notebooks headless, keeps the HTML | 88 s |
| 13 | `determinism` | compares this run's numbers with the previous run | instant |

`prediction-papers` dominates the wall clock. To rebuild only its page from the
`replicate_*.json` it already wrote, use
`uv run python scripts/build_prediction_page.py --out runs/latest --reuse` — seconds
rather than twelve minutes.

Exit code is the number of failed stages, so it is `0` when everything worked.

### Where the output goes

```
runs/latest/results.html          <- START HERE. The browsable results page.
runs/latest/flows_and_papers.html    income sources, money flows, paper map + gap audit
runs/latest/savers_and_debt.html     the savers & debt studies on one page
runs/latest/data_appendix.html       every dataset: schema, dtypes, summary statistics
runs/latest/prediction_and_papers.html  the So / Khandani / Butaru replications
runs/latest/replicate_*.json         the three replications, machine-readable
runs/latest/features.csv             the 46-column per-consumer feature frame
runs/latest/validation_report.md     every number, as readable text
runs/latest/validation_report.json   the same, machine-readable and deterministic
runs/latest/notebooks/*.html         the four executed notebooks
runs/latest/run_all.log              the full log of the run
presentation/status_deck.html        the full status & methodology deck
presentation/figures/                the 19 charts, PNG (slides) + SVG (LaTeX)
presentation/diagrams/               d01-d06, incl. d06_odd_overview (the ODD figure)
```

To hand all of this to someone who has to *write* with it rather than run it:

```bash
uv run python scripts/build_thesis_package.py    # -> thesis_package/index.html
```

That copies the run outputs, the figure layer and the docs into one directory,
along with `RESULTS_validation.md`, the written results section.

The four reference pages are linked from the top of `results.html`, so start there
and follow the arrows. Each is self-contained — no network requests — so the whole
`runs/<stamp>/` folder can be zipped and read anywhere.

`runs/latest` is a symlink to the newest timestamped run. The last 10 runs are kept;
`runs/` is gitignored, so none of this touches version control.

### Faster variants

```bash
uv run python scripts/run_all.py --quick      # tests + validation + results page, ~60 s
uv run python scripts/run_all.py --list       # show the stage keys
uv run python scripts/run_all.py --only validation results
uv run python scripts/run_all.py --only notebooks
```

---

## 2. Run it a second time — the determinism check

**Do this.** It is the single most informative thing you can do with the harness.

```bash
uv run python scripts/run_all.py --quick      # first run
uv run python scripts/run_all.py --quick      # second run
```

The model and every train/test split are seeded, and `validation_report.json` deliberately
carries **no timestamp**, so two runs must be byte-identical. Stage 12 hashes them and says
so:

```
[12/12] Determinism check — compare with the previous run
    sha256 2a68fa826750cb0f…
    MATCH — byte-identical to runs/20260806-122121. The pipeline is deterministic.
```

If it says **DRIFT**, something is genuinely non-deterministic — that is a bug worth
finding, not noise to ignore. The message prints the `diff` command to run.

### The numbers that must come back

Stage 3 checks each of these against the pinned value and marks it PASS or DRIFT:

| Number | Expected | Tolerance |
|---|---:|---:|
| `n_debtors` | 167 | exact |
| `kmo_headline` | 0.7430 | ± 0.010 |
| `kaiser_n_headline` (eigenvalues > 1) | 5 | exact |
| `bartlett_chi2_headline` | 14555 | ± 150 |
| `ari_naive` (debtor clustering, with debt mechanics) | 0.3636 | ± 0.050 |
| `ari_fair` (debtor clustering, fair only) | 0.2126 | ± 0.050 |
| `auc_is_debtor_logreg_naive` | 1.0000 | ± 0.010 |
| `auc_is_debtor_logreg_fair` | 0.6783 | ± 0.020 |
| `auc_is_debtor_rf_fair` | 0.7646 | ± 0.020 |
| `auc_is_climber_logreg_fair` | 0.8043 | ± 0.020 |
| `auc_is_climber_rf_fair` | 0.7857 | ± 0.020 |
| `n_savers` | 442 | exact |
| `ari_saver_naive_k2` (clustering finds no savers) | 0.0212 | ± 0.030 |
| `ari_saver_fair_k2` | 0.0182 | ± 0.030 |
| `ari_finstatus_naive_k4` | 0.1070 | ± 0.040 |
| `ari_finstatus_fair_k4` | 0.0381 | ± 0.040 |
| `auc_is_saver_logreg_naive` | 1.0000 | ± 0.010 |
| `auc_is_saver_logreg_debtorfair` (pins the sweep leak) | 0.9956 | ± 0.015 |
| `auc_is_saver_rf_debtorfair` | 0.9920 | ± 0.015 |
| `auc_is_saver_logreg_saverfair` | 0.7467 | ± 0.020 |
| `auc_is_saver_rf_saverfair` | 0.7971 | ± 0.020 |

A DRIFT row means something in the model or the feature pipeline changed. Find out what —
**never widen the tolerance to make it green.** What each number means is in
[`VALIDATION.md`](VALIDATION.md).

---

## 3. Running the notebooks yourself

Stage 11 already executes all four headless — `runs/latest/notebooks/*.html` has the
rendered output. Open them interactively when you want to poke at something:

```bash
uv run jupyter lab notebooks/clustering.ipynb
```

Then **Run → Run All Cells**. Each notebook generates its own data — there are no input
files to fetch.

| Notebook | Consumers × days | What to look at | ~time |
|---|---|---|---:|
| `demo.ipynb` | several small runs | the basic output: transaction table, daily volume, spend mix vs the paper baseline, the behavioural layer, the chronic-debtor view | 17 s |
| `analysis.ipynb` | 300 × 365 | the dataset tour — data dictionary, savers vs pensions, debtor subtypes, income composition, the December *tredicesima*, paper→page provenance | 11 s |
| `clustering.ipynb` | 800 × 720 | **Studies 0, A, C.** §2b factorability (KMO / Bartlett / eigenvalues); §4 clusters within the debtor subpopulation — dendrogram + confusion matrix are the ones to show; §5b is the saver study, where clustering finds nothing | 45 s |
| `prediction.ipynb` | 800 × 720 | **Studies B, D.** §3 `is_debtor`, §4 `is_climber`, §4b `is_saver` — each with the fair-vs-leaked ROC pair; §4b has three curves because the sweep leak needs its own column | 50 s |

`analysis.ipynb` regenerates its data on every run and writes `demo_accounts.csv` /
`demo_transactions.csv` next to the notebook (both gitignored). Set `REGENERATE = False`
in its first cell to read those CSVs instead of re-running the model.

To render one to HTML without opening Jupyter:

```bash
uv run jupyter nbconvert --to html --execute notebooks/clustering.ipynb
```

---

## 4. Just one piece

```bash
uv run python scripts/validation_report.py      # the numbers, ~25 s, no notebooks or figures
uv run pytest -q                                # all 96 tests, ~72 s
uv run pytest -q -m "not slow"                  # skip the long-horizon runs, ~40 s
uv run pytest -q tests/test_diagnostics.py      # the KMO/Bartlett estimators, ~5 s
uv run python presentation/scripts/generate_figures.py   # figures only
uv run python scripts/sweep_behavioural.py      # sensitivity sweep over the non-Italian magnitudes
```

## 5. The interactive app

```bash
uv run solara run src/synthitaly/viz.py
```

Opens `http://localhost:8765`. Sliders on the left (seed, consumers, merchants, days) —
move one, hit **Reset**, then **Play**. Includes the behavioural-events panel, live flow
arrows, and an account inspector (cluster → consumer → current/savings/pension statements).
This is the showpiece; the notebooks are the safety net.

---

## 6. When something looks wrong

| Symptom | What it means | What to do |
|---|---|---|
| a stage says **FAILED** | its last 12 output lines are printed inline, and the whole log is in `runs/latest/run_all.log` | read the log; re-run just that stage with `--only <key>` |
| a check says **DRIFT** | a headline number moved outside tolerance | something in `model.py`, `numbers.py` or `features.py` changed. `git diff` those, and see [`VALIDATION.md`](VALIDATION.md) for what the number means |
| stage 9 says **DRIFT** | two runs of the *same* code gave different numbers | a real non-determinism bug. Run the printed `diff` to see which field moved |
| `notebooks` stage fails | a notebook does not survive a clean kernel | open it in Jupyter Lab and Run All to see the failing cell — headless execution starts from an empty kernel, so stale state cannot mask a broken cell |
| Solara page is blank | server-side error | check the terminal, it logs why |
| `uv sync` complains about Python | wrong interpreter | install Python 3.13 |

---

## Where to read next

| If you want… | Read |
|---|---|
| what each validation study means, and its sources | [`VALIDATION.md`](VALIDATION.md) |
| why the model exists; the paper map; calibrated vs modelled | [`EXPLANATION.md`](EXPLANATION.md) |
| every model number → its paper | [`MODEL_REFERENCE.md`](MODEL_REFERENCE.md) |
| the formal agent-based spec | [`ODD.md`](ODD.md) |
| a file-by-file code walkthrough | [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) · [`WALKTHROUGH.md`](WALKTHROUGH.md) |
