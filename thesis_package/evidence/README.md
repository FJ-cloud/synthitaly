# Evidence pack

Everything behind the answers to the twelve methodology points, so each one is
checkable rather than trusted.

Rebuild with `uv run python scripts/build_evidence_pack.py` — run it **after**
`build_thesis_package.py`, whose `--clean` deletes anything it did not create.

## Machine-readable results — the source of truth

| File | What it pins |
|---|---|
| `validation_report.json` | The 21 pinned checks, all PASS. Config, label counts, factorability, eigenvalues, clustering, prediction, the saver leak audit. |
| `validation_report.md` | The same numbers as prose. |
| `replicate_so.json` | So et al. — 10 cascade runs, DeLong tests, per-fold Ginis, IV maps. |
| `replicate_khandani.json` | Khandani et al. — 18 result keys, stratification lifts, the straight-roller block, CART importances. |
| `replicate_butaru.json` | Butaru et al. — 6 seeds x 3 horizons x 3 models, cross-seed spread, threshold and overfitting sweeps. |
| `features.csv` | The per-consumer feature frame: 800 rows x 46 columns. |

## Generated listings — never transcribed by hand

| File | How it is produced |
|---|---|
| `feature_sets.md` | Calls `fair_columns()`, `leak_columns()`, `saver_fair_columns()` and `factorable_columns()` on `features.csv`, plus the panel set rules. Cannot drift from the code. |
| `run_configurations.md` | Parses the AST of every `.py` and `.ipynb` in the repo and lists every `ItalyModel(...)` with file:line and kwargs. |
| `README.md` | This file, from `build_evidence_pack.py`. |

## Figures

`f02` (spending calibration), `f04` (payday spike), `f09` / `f10` / `f12` (debt
trajectories), as 300 dpi PNG and vector PDF.

All five come from the pinned **800 x 720, seed 42** configuration — the same one
every reported statistic uses. `f04` shows its first 120 days, which the seeding
makes byte-identical to a 120-day run. See `run_configurations.md`.

Note what each one plots: `f02` and `f04` are **euro**, not transaction counts;
`f09` is a **total** across the subtype; `f10` is a **mean** within it; `f12` is a
**count** of households.

## Three corrections worth knowing about before quoting anything

These were all open questions in the previous version of this pack. All three are
now fixed, and the fixes moved published numbers.

1. **`CATEGORY_SHARES` are euro shares and were used as selection probabilities.**
   The paper's Figure 4 (§2.1) is titled *Average shares of expenditure categories*
   and Figure 6 benchmarks it against COICOP national-accounts expenditure — they
   are shares of euros. `sample_category()` used them directly as the probability of
   picking a category, then drew the ticket independently, so the model matched the
   paper in transaction **counts** and missed on euros: travel took 19.8% of euros
   against the paper's 9.0%. Selection is now `p ∝ share / E[ticket]`; the residual
   error on a real run is 0.6pp, all sampling noise. **This changed every
   transaction in the model**, so every number in this pack moved with it. The
   attribution block above `EXPECTED` in `scripts/validation_report.py` names the
   cause of each moved row.

2. **`replicate_so.json` was not reproducible across processes.** The script seeded
   each cascade with `hash(key) % 1000`, and Python salts string hashing per
   process. Over four runs the six late-fee DeLong comparisons were stable but the
   four 90-DPD ones flipped verdict in three runs of ten. The seed is now
   `blake2b(key)` (`replicate_so.py:_stable_seed`), verified identical across fresh
   interpreters. Combined with the units fix, **eight of ten comparisons now reject,
   not six**; `docs/RESULTS_validation.md` §7.1 carries the full table and records
   both earlier counts.

3. **Kappa and F used a threshold chosen on the test labels.** Khandani and Butaru
   called `classification_scores` without a threshold, so it took the ROC tangency
   point of the scores being evaluated. Both now take it from the training fold.
   AUC is threshold-free and did not move; kappa and F did, most visibly for the
   ridge logit on Butaru's behavioural-only set C (kappa 0.501 -> 0.395), which had
   been benefiting the most.

## Regenerating the numbers themselves

```bash
uv run python scripts/validation_report.py      # the 21 pinned checks, ~30s
uv run pytest -m slow                           # the loose regression floors
uv run python scripts/replicate_so.py           # ~2 min, reproducible
```
