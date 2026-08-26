# Answers to `debugging_summary1.odt`

Answers to the five questions you wrote (with screenshots) in `debugging_summary1.odt`,
at the conceptual **and** code level. All citations are `file:line` in `src/synthitaly/`.
The chronic/subsister labelling was reviewed and **kept as-is** (it is a naming choice,
not a bug — see Q2); this document is the explanation to present and defend it.

---

## Q1 — Where do the overdraft and late-payment numbers come from?

Both are the **behavioural-economics layer** added on top of the original sim. Neither is
random: each is one constant + one trigger, grounded in a named non-Italian paper, with
the magnitude flagged as a sweepable modelling choice (not an Italian fact).

### Overdraft fee — €30 flat per event (Stango & Zinman 2014)
- **Concept:** the bank charges a fixed amount the moment a payment pushes the current
  account below zero. Per the paper this cost is regressive — concentrated among
  lower-income / lower-attention account holders.
- **Constant:** `OVERDRAFT_FEE_EUR = 30.0` — `numbers.py:282`.
- **Trigger:** `_pay()` charges it when a debit moves the balance from ≥0 to <0 —
  `model.py:365-366` → `_charge_overdraft_fee()` `model.py:368-396`. `_can_afford()`
  pre-reserves the €30 so the overdraft floor stays a hard limit — `model.py:330-333`.
- **Recorded as:** `kind="fee"`, `category="overdraft_fee"`.
- **Why only chronic debtors show it:** the default overdraft floor is `0.0`, so most
  consumers can never cross zero and never trip the fee. Only the **chronic** archetype
  gets a negative floor (`-monthly_service`, `model.py:1070`). That is why the
  "Chronic fee burden" panel attributes overdraft fees almost entirely to chronics
  (€240 in your screenshot = 8 events × €30).

### Late-payment fee — 11% of the bill (Dahan & Nisan 2020)
- **Concept:** a bill falls due *before* payday; a cash-short household pays it **late,
  with a penalty**, rather than defaulting outright (the due-date/payday mismatch).
- **Constant:** `LATE_PAYMENT_FEE_FRACTION = 0.11` — `numbers.py:291`.
- **Trigger (two stages):** an unaffordable bill is not skipped — it is queued as overdue
  (`model.py:469-473`); later it is settled as `principal + 0.11·principal` once cash
  exists (`_settle_overdue_bills()` `model.py:493-507`). Unpaid > 90 days ⇒ written off.
- **Recorded as:** `kind="fee"`, `category="late_payment_fee"` (paid to the original
  biller, not a separate account).

**"Out of nowhere":** they appear only because the behavioural layer was added on top of
the original transaction sim. They signify the **account-visible cost of liquidity
stress** — overdraft = a balance breaching zero; late fee = a bill calendar misaligned
with the 27th payday.

To pull them from a transaction export: filter `kind == "fee"`, then split on `category`
(`overdraft_fee` vs `late_payment_fee`).

---

## Q4 — Why do late payments behave the way they do?

Same mechanism as Q1, viewed over time:

- **Why monthly spikes:** bills are due on fixed days 1/5/10/15/20 (`BILL_TYPES`,
  `numbers.py:98-107`) but salary lands only on the **27th** (`PAYDAY_DAY_OF_MONTH`,
  `numbers.py:136`). Every bill day precedes payday, so a household that ends a cycle
  short defers its early-month bills and clears the backlog in a batch once the 27th
  salary arrives ⇒ one spike per pay cycle.
- **Why the ramp-up (24 → 52 → 66 → 78 … then plateau):** every consumer starts with a
  one-month income buffer (`starting_balance = income`, `model.py:755`). Early on few
  defer; as bills + discretionary spend erode the buffer, the share hitting a pre-payday
  shortfall rises and settles into a steady state.
- **Why late dominates overdraft in the "events/day" chart but not in "fee burden":** the
  events chart is the **whole population** — many consumers defer a bill (common), but
  only chronics can overdraft (rare). The fee-burden chart is the **chronic cohort only**,
  where standing overdrafts recur, so there overdraft € > late €.

---

## Q3 — Where are the income sources defined? (for the write-up)

All in `numbers.py`, consumed by the `IncomeSource` agent (`model.py:134-208`) and
assigned in `ItalyModel.__init__` (`model.py:748-752`). Income is drawn **once at
construction**, not re-rolled each payday.

| Thing | Location |
|---|---|
| Five sources + relative levels (payroll 1.08× … self-employed 1.49× … unemployed 0.40×) | `INCOME_SOURCE_RELATIVE` `numbers.py:299-307` |
| Population shares | `INCOME_SOURCE_SHARE` `numbers.py:315-321` |
| Per-source dispersion (self-employed widest, σ 0.70; pension tightest, 0.35) | `INCOME_SOURCE_SIGMA` `numbers.py:331-337` |
| Income-level bands (low ≤ €1,000 / high > €4,000) | `INCOME_LEVEL_BANDS_EUR` `numbers.py:127`, `income_level()` `numbers.py:515` |
| December *tredicesima* (payroll + pension only, ×2) | `THIRTEENTH_MONTH_*` `numbers.py:361-362`, `income_calendar_multiplier()` `numbers.py:562` |
| Statement-label per source | `INCOME_SOURCE_CATEGORY` `numbers.py:347` |
| The actual monthly draw (mean-preserving lognormal) | `sample_income_for_source()` `numbers.py:526`, `income_source_multiplier()` `numbers.py:546` |

The draw is mean-preserving: each source is centred on `base_mean × relative_level`, and
the share-weighted multipliers sum back to 1.0 (asserted at `numbers.py:666-673`), so the
population mean income — and the SHIW quartile/quintile bands — are undisturbed; only the
per-source location and spread change.

---

## Q5 — Why do self-employed balances pull away so massively?

**Structural artifact, not a bug — and fully explainable.** Mechanism:

1. Self-employed have the **highest income** (1.49× mean ⇒ ~€2,723/mo in your plot) and
   the **widest spread** (σ 0.70, the heaviest right tail).
2. **Spending does NOT scale with income.** `_maybe_buy_from_merchant` never reads
   `monthly_income` (`model.py:609-636`): purchase probability is a fixed
   `base_prob = 0.6 × daily_intensity` and ticket sizes are fixed-euro draws from
   `CATEGORY_TICKET_LOGNORMAL` (mean ~€28). Bills are fixed euro amounts too. So a
   consumer's monthly **outflow is roughly constant in euros regardless of income**,
   while **inflow scales with income**.
3. ⇒ High earners run a large monthly surplus. The month-close sweep removes it **only
   for savers** (`_month_close`, `model.py:416-453`); for **non-savers the surplus stays
   in the current account and compounds linearly in time**. Even the top income quintile
   has a 28% non-saver rate (`P_NO_SAVING_BY_INCOME_QUINTILE[5] = 0.28`, `numbers.py:178`),
   so a meaningful fraction of high earners never sweep.

Self-employed, having both the highest level and the heaviest tail, diverge fastest — a
few very high earners dominate the *mean* current balance (~€8,000). Low-income sources
(transfers 0.50×, unemployed 0.40×) have income ≈ spend, so they hug zero; pension (0.82×,
σ 0.35) stays roughly flat — matching the "everyone else is stationary" you observed.

**Known modelling limitation worth a sentence in the thesis:** there is no consumption
function / marginal-propensity-to-consume, so spending doesn't rise with income. If you
want bounded balances across all sources, make discretionary spend a *fraction* of income
rather than a flat absolute amount. (Separate change — not done here.)

---

## Q2 — "Change the labels": chronic flat, subsister rising — are they swapped?

**No — the labels are correct and match the documented design.** Reviewed against the
definitions, the repayment code, the colour legend, the panel docstring, and three tests
(`tests/test_debt_vulnerability.py`, `tests/test_smoke.py`, `tests/test_numbers.py`).
**Decision: kept as-is.**

The taxonomy (`numbers.py:194-199`, `model.py:516-562`):

| Subtype | Rule | Principal | Your plot |
|---|---|---|---|
| **climber** | pays full service (`1.0 × service`), more than interest | **falls to zero**, then leaves debt | green, 115k → 75k |
| **chronic** | pays **interest only** (`scheduled = interest`, `model.py:537`) | **exactly flat**, standing overdraft, *never clears* | red, ~52k flat |
| **subsister** | pays a **token** `0.25 × service` *and borrows* to plug gaps | **drifts up** toward a 2× ceiling | orange, 86k → 96k |

So your expectation "chronic = the stuck one" **is** satisfied — chronic is the flat,
never-digging-out cohort. The confusion is that **subsister also never clears** (it even
rises), so you expected the *rising* line to be chronic. In this model:

- **chronic = stuck-and-flat** — treads water on interest, a permanent stable revolving
  balance; and
- **subsister = slowly-sinking** — borrows to survive, so debt creeps upward.

Both are distressed; only the climber escapes. Nothing is mislabelled in the plot — the
series are correctly mapped (`viz.py:601-603`, colour map `viz.py:151-158`), and the tilt
toward chronic among the financially vulnerable (SHIW 2022 §3) is intentional
(`numbers.py:206-220`).
