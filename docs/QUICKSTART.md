# Quickstart

Three commands. Pick whichever way you want to see the simulator working.

> For a fuller plain-language guide — including how to **export the datasets** and how
> to **run the analysis**, neither of which is covered here — see [`USAGE.md`](USAGE.md).

> **Want to run *everything* — tests, validation, all four notebooks, the figures and the
> deck — in one command?** That is [`RUNBOOK.md`](RUNBOOK.md):
> `uv run python scripts/run_all.py`. This page is the short path to seeing the model
> work; the runbook is the full one.

## 0. One-time setup

```bash
uv sync
```

This installs Python 3.13 + Mesa + Solara + the rest. It uses the
`pyproject.toml` in the repo root. Takes ~30 seconds the first time;
seconds thereafter.

## A. The notebook (proven to work, no surprises)

```bash
uv run jupyter lab notebooks/demo.ipynb
```

JupyterLab opens in your browser. Click **Run → Run All Cells**. You will
see, in order:

1. The first ten rows of generated transactions printed as a table.
2. A line chart of how many transactions happen each day, with paydays
   marked.
3. A bar chart comparing the simulated spending mix per category against
   the paper baseline.
4. A bar chart of total spend per macro-area (NORTH / CENTRE / SOUTH).
5. A `demo_transactions.csv` file written next to the notebook — open it
   in Excel if you want.
6. A per-account portfolio table grouped by **cluster** (macro-area |
   income quartile | financial status), plus a `demo_accounts.csv` with
   one row per (consumer, account) — current / savings / pension balances
   you can pivot or cluster offline.

If `jupyter lab` is not on your machine, this will still work:

```bash
uv run jupyter nbconvert --to html --execute notebooks/demo.ipynb
```

It produces `notebooks/demo.html`, openable in any browser.

## B. The interactive app

```bash
uv run solara run src/synthitaly/viz.py
```

A web server starts and a browser tab opens at `http://localhost:8765`.
You see three panels:

- **Spending by macro-area** — bar chart, updates as the model steps.
- **Consumers ↔ Merchants** — a small network picture (illustrative).
- **Daily KPIs** — line plot of transaction count + EUR total over time.

On the left you have sliders for the random seed, number of consumers,
merchants per (category × area), and days to run. Move a slider, hit
**Reset**, then **Play** to watch a fresh run.

## C. The tests

```bash
uv run pytest -q
```

You should see a row of dots and a "passed" line in green. There are
~10 tests; total runtime is under three seconds.

## When something is wrong

- If `uv sync` complains about Python, install Python 3.13 first.
- If the Solara page is blank, check the terminal — it logs why.
- If the notebook fails to render plots, re-run the cell — matplotlib
  sometimes needs a second pass on first import.

## Where to read next

Open `docs/RUNBOOK.md` to run the whole suite — including the validation
studies and the other three notebooks — in one command. Open
`docs/VALIDATION.md` for what those studies measured and where the methods
come from. Open `docs/HOW_IT_WORKS.md` for a plain-language walk through the
code files. Open [`REFERENCES.md`](REFERENCES.md) for the sources every number
traces back to.
