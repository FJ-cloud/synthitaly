# Run configurations

Every `ItalyModel(...)` construction in the repository, found by parsing
the AST of every `.py` and `.ipynb` outside `.venv/`, `abandoned/` and
`italy_further_work/`. Generated, not transcribed.

The pinned configuration behind every reported statistic is **800
consumers x 720 days, seed 42, 3 merchants per category per area**
(`scripts/validation_report.py:40`). The simulation start date is **1
January 2017** (`src/synthitaly/model.py:733`) — a constructor keyword
that no caller anywhere in the repo overrides.

## What produces what

| Artefact | Configuration |
|---|---|
| Validation report, internal studies 0/A/B/C/D | 800 x 720, seed 42 |
| Data appendix (ledger counts, schemas) | 800 x 720, seed 42 |
| Notebooks `clustering.ipynb`, `prediction.ipynb` | 800 x 720, seed 42 |
| So et al.; Khandani 3m and 6m horizons | 800 x 720, seed 42 |
| Khandani 12m horizon; Butaru, all horizons | 800 x **1,440**, seeds 42-47 |
| **Figures f01-f19** | **800 x 720**, seed 42 |
| Behavioural sensitivity sweep | 300 x 150 (720 for debt), seed 42 |

**Every figure is now produced at the pinned 800 x 720 configuration** — the same
one every reported statistic comes from. `generate_figures.py` builds one model and
draws all nineteen from it; f01, f04, f05 and f07 show its first 120 days, which is
byte-identical to a 120-day run at the same seed (verified for both the transaction
log and the datacollector frame). Until 22 Aug 2026 the figures came from three
separate runs at 150 x 120, 150 x 720 and 600 x 720, and none could be quoted
alongside the numbers.

The 1,440-day runs exist because a 9- or 12-month forecast horizon has no evaluable
origination month on a 720-day run (`scripts/_papers.py:111-116`).

## Every construction

| Where | consumers | days | seed | merchants/cat |
|---|---:|---:|---:|---:|
| `presentation/scripts/generate_figures.py:947` | 800 | 720 | 42 | 3 |
| `presentation/scripts/make_reference_card.py:215` | 800 | 720 | 42 | 3 |
| `presentation/scripts/make_slide_assets.py:304` | 800 | 720 | 42 | 3 |
| `scripts/_papers.py:133` | CONFIG['n_consumers'] | days | seed | CONFIG['n_merchants_per_category'] |
| `scripts/build_data_appendix.py:485` | args.consumers | args.days | args.seed | 3 |
| `scripts/export_dataset.py:138` | args.consumers | args.days | args.seed | args.merchants |
| `scripts/sweep_behavioural.py:47` | N_CONSUMERS | N_DAYS | SEED | 3 (default) |
| `scripts/sweep_behavioural.py:92` | N_CONSUMERS | N_DAYS_DEBT | SEED | 3 (default) |
| `scripts/validation_report.py:426` | — | — | — | 3 (default) |
| `src/synthitaly/viz.py:1065` | 150 | 30 | 42 | 3 |
| `tests/conftest.py:64` | 120 | 90 | 42 | 2 |
| `tests/test_analysis_pipeline.py:50` | 200 | 180 | 7 | 2 |
| `tests/test_analysis_pipeline.py:62` | 150 | 120 | 11 | 2 |
| `tests/test_analysis_pipeline.py:63` | 150 | 120 | 11 | 2 |
| `tests/test_analysis_pipeline.py:74` | 300 | 365 | 3 | 2 |
| `tests/test_analysis_pipeline.py:92` | 120 | 120 | 5 | 2 |
| `tests/test_analysis_pipeline.py:109` | 800 | 720 | 42 | 3 |
| `tests/test_analysis_pipeline.py:122` | 20 | 40 | 1 | 2 |
| `tests/test_balances.py:26` | 80 | 20 | 3 | 2 |
| `tests/test_conservation.py:31` | 200 | 120 | 42 | 3 |
| `tests/test_conservation.py:46` | 300 | 365 | 7 | 3 |
| `tests/test_debt_vulnerability.py:19` | 400 | 1 | 13 | 2 |
| `tests/test_debt_vulnerability.py:31` | 300 | 1 | 5 | 2 |
| `tests/test_debt_vulnerability.py:42` | 600 | 1 | 42 | 2 |
| `tests/test_debt_vulnerability.py:57` | 400 | 720 | 42 | 3 |
| `tests/test_diagnostics.py:25` | 300 | 365 | 42 | 2 |
| `tests/test_income.py:100` | 600 | 1 | 9 | 2 |
| `tests/test_income.py:121` | 2000 | 1 | 5 | 1 |
| `tests/test_income.py:139` | 3000 | 1 | 17 | 1 |
| `tests/test_income.py:165` | 300 | 1 | 9 | 2 |
| `tests/test_income.py:172` | 60 | 5 | 6 | 2 |
| `tests/test_panel.py:34` | 200 | 720 | 7 | 2 |
| `tests/test_panel.py:131` | 200 | 540 | 7 | 2 |
| `tests/test_panel.py:248` | 120 | 400 | 3 | 2 |
| `tests/test_panel.py:249` | 120 | 400 | 3 | 2 |
| `tests/test_schema.py:27` | 60 | 30 | 6 | 2 |
| `tests/test_schema.py:35` | 60 | 30 | 6 | 2 |
| `tests/test_schema.py:44` | 100 | 60 | 123 | 3 |
| `tests/test_schema.py:59` | 100 | 60 | 999 | 3 |
| `tests/test_schema.py:102` | 40 | 40 | 42 | 2 |
| `tests/test_smoke.py:11` | 30 | 5 | 1 | 2 |
| `tests/test_smoke.py:19` | 50 | 10 | 42 | 3 |
| `tests/test_smoke.py:37` | 200 | 1 | 9 | 2 |
| `tests/test_smoke.py:49` | 20 | 30 | 7 | 2 |
| `tests/test_smoke.py:56` | 20 | 12 | 3 | 2 |
| `tests/test_smoke.py:67` | 40 | 30 | 11 | 2 |
| `tests/test_smoke.py:80` | 50 | 30 | 5 | 3 |
| `tests/test_smoke.py:100` | 120 | 95 | 8 | 2 |
| `tests/test_smoke.py:111` | 120 | 95 | 8 | 2 |
| `tests/test_smoke.py:134` | 200 | 95 | 8 | 2 |
| `tests/test_smoke.py:142` | 300 | 90 | 42 | 3 |
| `tests/test_smoke.py:167` | 200 | 30 | 13 | 2 |
| `tests/test_smoke.py:183` | 60 | 40 | 6 | 2 |
| `tests/test_smoke.py:210` | 40 | 1 | 2 | 2 |
| `tests/test_smoke.py:241` | 150 | 120 | 21 | 2 |
| `tests/test_smoke.py:280` | 5 | 1 | 1 | 1 |
| `tests/test_smoke.py:305` | 300 | 120 | 42 | 3 |
| `tests/test_smoke.py:324` | 5 | 1 | 1 | 1 |
| `tests/test_smoke.py:358` | 400 | 150 | 42 | 3 |
| `tests/test_smoke.py:373` | 300 | 1 | 9 | 2 |
| `tests/test_smoke.py:384` | 400 | 1 | 9 | 2 |
| `tests/test_smoke.py:393` | 300 | 30 | 9 | 2 |
| `tests/test_smoke.py:403` | 150 | 365 | 8 | 2 |
| `tests/test_smoke.py:422` | 300 | 1 | 13 | 2 |
| `tests/test_smoke.py:437` | 300 | 400 | 42 | 2 |
| `tests/test_smoke.py:450` | 400 | 720 | 42 | 3 |
| `tests/test_smoke.py:503` | 400 | 720 | 42 | 3 |
| `tests/test_smoke.py:524` | 30 | 1 | 4 | 2 |
| `tests/test_smoke.py:266` | 150 | 120 | 33 | 2 |
| `notebooks/.ipynb_checkpoints/demo-checkpoint.ipynb [cell 2]:9` | 200 | 30 | 42 | 10 |
| `notebooks/.ipynb_checkpoints/demo-checkpoint.ipynb [cell 15]:7` | 300 | 180 | 42 | 5 |
| `notebooks/.ipynb_checkpoints/demo-checkpoint.ipynb [cell 17]:2` | 300 | 365 | 42 | 5 |
| `notebooks/analysis.ipynb [cell 4]:2` | N_CONSUMERS | N_DAYS | SEED | N_MERCH |
| `notebooks/clustering.ipynb [cell 2]:19` | 800 | 720 | RNG_SEED | 3 |
| `notebooks/demo.ipynb [cell 2]:9` | 200 | 30 | 42 | 10 |
| `notebooks/demo.ipynb [cell 15]:7` | 300 | 180 | 42 | 5 |
| `notebooks/demo.ipynb [cell 17]:2` | 300 | 365 | 42 | 5 |
| `notebooks/demo.ipynb [cell 19]:5` | 400 | 720 | 42 | 5 |
| `notebooks/prediction.ipynb [cell 2]:19` | 800 | 720 | RNG_SEED | 3 |