# How to use this — the short version

Five things you can do with this folder, in the order you would normally do them.
Everything runs on your own machine; nothing here needs the internet after step 0.

If you only want to *read* the results rather than produce them, skip to step 4.

---

## 0. Set up — once

```bash
uv sync
```

Installs Python 3.13 and the ten libraries the model needs, from `pyproject.toml`.
Takes about 30 seconds the first time and a second or two after that. If it
complains about Python, install Python 3.13 and run it again.

Every command below starts with `uv run`, which just means "run this using the
libraries you installed a moment ago". Run them all from this folder.

---

## 1. Watch the model run — the interactive app

```bash
uv run solara run src/synthitaly/viz.py
```

A web page opens at `http://localhost:8765`. On the left are four sliders — random
seed, number of consumers, merchants, and days to simulate. The workflow is:

> **move a slider → press Reset → press Play**

You get eleven panels, and it is worth scrolling through all of them: spending by
macro-area, the money-flow network (with live arrows for the day being simulated,
width scaled to euros), daily KPIs, behavioural events (overdrafts and late-payment
fees), income composition, balance trajectories, the three debtor archetypes, and an
**account inspector** — pick a cluster, then a consumer, and read their actual
current / savings / pension statements.

Press `Ctrl-C` in the terminal to stop the server.

**One thing it does not do:** the download buttons in the app give you **PNG images
only**. There is no way to get data out of the app. For data, use step 2.

---

## 2. Get the datasets out

```bash
uv run python scripts/export_dataset.py
```

That is the whole thing. It runs the simulation once and writes every table it
produces into a new `exports/` folder:

| File | What it is |
|---|---|
| `transactions.csv` | one row per money movement — salaries in, bills and purchases out, fees |
| `accounts.csv` | one row per (consumer, account) — current / savings / pension balances |
| `features.csv` | one row per consumer — the behavioural features the analysis uses |
| `labels.csv` | one row per consumer — the ground truth, for scoring only |
| `daily_kpis.csv` | one row per simulated day — transaction count and euro total |
| `credit_panel.csv` | one row per (consumer, month), with six months of trailing history |
| `MANIFEST.md` | what settings produced all of the above, and how big each file is |

Open any of them in Excel. `labels.csv` joins to the other per-consumer files on
`consumer_id`.

The defaults are the exact configuration every number in the thesis comes from —
**800 consumers, 720 days, seed 42** — so `features.csv` is the same table as the one
in `runs/latest/`. To generate something else:

```bash
uv run python scripts/export_dataset.py --consumers 2000 --days 1080 --seed 7 --out ~/Desktop/data
```

The model is seeded, so the same settings always produce the same files.

> **What each column means** is documented, column by column with summary statistics,
> in `runs/latest/data_appendix.html` — just open it in a browser.

---

## 3. Run the analysis

```bash
uv run python scripts/run_all.py
```

**About 15 minutes.** It runs thirteen stages — the tests, the validation studies, the
19 figures, the three paper replications, and all four notebooks — and prints one line
per stage so it reads as a checklist. When it finishes, open:

```
runs/latest/results.html
```

That is the front door; the other four pages are linked from the top of it.

| Page | Answers |
|---|---|
| `results.html` | every validation number, with the figures |
| `savers_and_debt.html` | the saver and debtor studies |
| `prediction_and_papers.html` | the So / Khandani / Butaru replications |
| `flows_and_papers.html` | where the money goes, and which paper each number came from |
| `data_appendix.html` | every dataset: schema, dtypes, summary statistics |

**In a hurry?** `uv run python scripts/run_all.py --quick` does the tests, the
validation numbers and three of the pages in about 90 seconds. It skips the figures,
so `results.html` will show placeholders where charts should be.

**Just the tests:** `uv run pytest -q` — 143 tests, about 80 seconds, all should pass.

---

## 4. Read the results without running anything

All of these are already built and sitting in the folder. They are self-contained —
no internet, no server — so you can double-click them, or email the folder to someone.

| Open this | To get |
|---|---|
| `thesis_package/index.html` | the whole hand-off package: results, figures, data, write-up |
| `thesis_package/RESULTS_validation.md` | the written results section |
| `presentation/status_deck.html` | the full status and methodology deck |
| `runs/latest/results.html` | the browsable results page |
| `presentation/figures/` | the 19 charts, as PNG (slides) and SVG (LaTeX) |

---

## 5. Three things not to do

The results in this repo all come from **one** model run, pinned at
`runs/20260822-142420`. `runs/latest` is a shortcut pointing at it. Three commands can
move that shortcut or overwrite the run:

1. **Any `run_all.py` command repoints `runs/latest`** at a new folder — including
   `--only <stage>`, which makes a nearly-empty folder and then points `latest` at
   *that*. Note which folder you care about before running anything partial.
2. **These write straight into `runs/latest`, overwriting it:**
   `validation_report.py`, `build_data_appendix.py`, and the three `replicate_*.py`
   scripts (which have no option to write anywhere else). Give the first two
   `--out somewhere/else` if you just want a copy.
3. **`run_all.py` keeps only the 10 newest run folders** and silently deletes the rest.

None of this applies to `scripts/export_dataset.py` — it only ever writes inside the
folder you give it.

---

## When something goes wrong

| What you see | What to do |
|---|---|
| `uv sync` complains about Python | install Python 3.13, run it again |
| the Solara page is blank | look at the terminal — it prints the reason |
| a stage says FAILED | the full log is in `runs/latest/run_all.log`; re-run just that stage with `--only <name>` |
| `credit_panel.csv` is empty | the run was too short — it needs at least 6 months, so use `--days 720` |
| a number came out different | that should be impossible, everything is seeded. See [`RUNBOOK.md`](RUNBOOK.md) §2 |

---

## Where to go next

This page is the short path. For everything else:

| If you want | Read |
|---|---|
| every run command, and what should come back | [`RUNBOOK.md`](RUNBOOK.md) |
| what was validated, the numbers, and the method sources | [`VALIDATION.md`](VALIDATION.md) |
| why the model exists, and which paper each number came from | [`EXPLANATION.md`](EXPLANATION.md) |
| a plain-language tour of the code files | [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) |
| every model constant and its source | [`MODEL_REFERENCE.md`](MODEL_REFERENCE.md) |
