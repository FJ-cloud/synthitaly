# synthitaly — a small Italian consumer-transaction simulator

An agent-based simulation of what an Italian bank would see on its consumer customers'
accounts: salaries arriving, bills going out, purchases at merchants, fees when a balance
runs short. Households differ by **income source** (payroll / self-employed / pension /
transfers / unemployed), by **income level**, and by **macro-area** (North / Centre /
South); account balances are tracked over time; and indebted households fall into three
trajectories — climbers who dig out, the **chronically** stuck, and subsisters hugging
zero on a credit line. Built on Mesa 3.x.

*This is the code accompanying a master's thesis.* The simulator is one half of it; the
other half is the validation — the model is scored against three published consumer-credit
papers, and the interesting result is where it **disagrees** with them.

Every empirical constant lives in one file, [`numbers.py`](src/synthitaly/numbers.py), with
its source in a comment beside it. The Italian numbers are calibrated; the behavioural
overlay is grounded in direction only and swept rather than claimed. See
[`docs/REFERENCES.md`](docs/REFERENCES.md).

## Run it

```bash
uv sync                                            # install dependencies
uv run python scripts/run_all.py                   # EVERYTHING — tests, validation, notebooks, figures
uv run pytest -q                                   # just the tests
uv run python scripts/export_dataset.py            # write the six CSVs to exports/
uv run jupyter lab notebooks/demo.ipynb            # the demo notebook
uv run solara run src/synthitaly/viz.py            # the interactive app
```

**New here?** [`docs/USAGE.md`](docs/USAGE.md) is the one-page guide — how to run it, how to
export the datasets, and how to run the analysis.

`run_all.py` takes about fifteen minutes and leaves a browsable results page at
`runs/latest/results.html` — every validation number, the 19 figures, and the sourcing. Run
it twice and it tells you whether the numbers came back byte-identical. See
[`docs/RUNBOOK.md`](docs/RUNBOOK.md).

The notebook is the safety-net path — it produces the plots, a transaction CSV, and a
per-account portfolio table grouped by cluster. The Solara app is the showpiece — it opens a
browser, has sliders, updates live, and includes an account inspector (pick a cluster → a
consumer → see their current/savings/pension statements).

## Repository layout

```
src/synthitaly/       4,800 lines, eight modules
  numbers.py            every empirical constant, one place, paper-cited
  model.py              Mesa model + Consumer / Merchant / IncomeSource agents
  features.py           per-consumer feature pipeline — one source of truth for the analysis
  panel.py              per-consumer-month panel + Transactor/Revolver states
  creditscoring.py      weight-of-evidence scorecards (So, Thomas, Seow & Mues)
  diagnostics.py        factorability instruments (KMO, Bartlett, Kaiser)
  viz.py                Solara interactive app
notebooks/
  demo.ipynb            runs the model + plots the output
  analysis.ipynb        the dataset tour, with paper→page provenance
  clustering.ipynb      validation study 0 (factorability) + A (clustering)
  prediction.ipynb      validation study B (predicting debtors & climbers)
scripts/
  run_all.py            runs everything; writes runs/latest/
  validation_report.py  the headline numbers, on their own
  export_dataset.py     the six frames as CSV, plus a MANIFEST
  sweep_behavioural.py  sensitivity sweep over the non-Italian magnitudes
  replicate_*.py        the three consumer-credit paper replications
  build_*.py            the generated reference pages under runs/latest/
tests/                143 tests — unit, smoke, conservation, schema, determinism, diagnostics
presentation/scripts/ figure, diagram and deck generators — all output regenerated from the model
italy_papers/         reading notes on the four Italian sources (the PDFs are not redistributed)
docs/                 see the table below
```

## Documentation — where to start

| If you want… | Read |
|---|---|
| a short, plain guide: run it, export the data, run the analysis | [`docs/USAGE.md`](docs/USAGE.md) |
| just the run commands | [`docs/QUICKSTART.md`](docs/QUICKSTART.md) |
| to run everything, and know what should come back | [`docs/RUNBOOK.md`](docs/RUNBOOK.md) |
| the whole picture — why this exists, the papers, what's calibrated vs modelled | [`docs/EXPLANATION.md`](docs/EXPLANATION.md) |
| what was validated, the numbers, and where the methods come from | [`docs/VALIDATION.md`](docs/VALIDATION.md) |
| the thesis-ready results section, study by study | [`docs/RESULTS_validation.md`](docs/RESULTS_validation.md) |
| the data dictionary (every number → its paper) | [`docs/MODEL_REFERENCE.md`](docs/MODEL_REFERENCE.md) |
| every source, tiered by what it licenses the model to claim | [`docs/REFERENCES.md`](docs/REFERENCES.md) |
| the formal agent-based specification | [`docs/ODD.md`](docs/ODD.md) |
| a file-by-file code walkthrough | [`docs/HOW_IT_WORKS.md`](docs/HOW_IT_WORKS.md) |
| a guided tour of the output | [`docs/WALKTHROUGH.md`](docs/WALKTHROUGH.md) |
| how the model was actually built, and what was tried and dropped | [`docs/METHOD_HISTORY.md`](docs/METHOD_HISTORY.md) |
| the deferred deepenings and their candidate sources | [`docs/PROPOSAL_financial_depth.md`](docs/PROPOSAL_financial_depth.md) |

## Where the numbers come from

Four empirical Italian sources shape the model — SHIW 2022, the Bank of Italy Payment
Behaviour Survey 2023-24, Emiliozzi et al. (2023) on Italian card data, and Semeraro et al.
(2020) on the wire-transfer network — with a four-paper behavioural-finance overlay on top.
The distinction between them is load-bearing: the Italian numbers are quotable as Italian
facts, while the behavioural layer is paper-grounded in **direction only**, its magnitudes
treated as modelling choices and swept.

The publisher PDFs are copyright and are **not** redistributed here.
[`docs/REFERENCES.md`](docs/REFERENCES.md) is the provenance record in their place — every
source, its tier, and what it does and does not license the model to claim. Reading notes on
the four Italian sources are kept in `italy_papers/notes on each paper/`.
[`docs/MODEL_REFERENCE.md`](docs/MODEL_REFERENCE.md) has the number → paper mapping and
[`docs/EXPLANATION.md`](docs/EXPLANATION.md) how the papers fit together.

## License

MIT — see [`LICENSE`](LICENSE). The license covers this code. It does not extend to the
third-party papers it cites.
