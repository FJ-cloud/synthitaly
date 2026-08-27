# Model reference — consumers, elements, and where every number comes from

This is the single-page reference for **what the simulation contains and which
paper each number traces back to**. It complements [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md)
(a file-by-file code walkthrough); this document is the *data dictionary*.

Every value below lives in [`src/synthitaly/numbers.py`](../src/synthitaly/numbers.py)
with the same source note in a code comment. Nothing here is invented:
empirical figures name their paper and section; deliberate modelling choices and
proxies are **flagged as such** and are meant to be swept.

> **Provenance rule.** The *Italian* numbers come from four Italian sources
> (Emiliozzi et al. 2023 card data; Bank of Italy Payment Behaviour Survey 2023-24;
> SHIW 2022; the wire-transfer / structural-inequalities paper). The
> *behavioural-economics* layer comes from three **non-Italian** papers — there,
> the **shape/existence** of the behaviour is paper-grounded but the **magnitude**
> is a modelling choice (swept), never claimed as an Italian fact.

---

## 1. The bank-eye framing

The whole model is *what a bank would see on its retail customers' accounts*. We
emit only consumer-visible flows — salary in, bills out, purchases, bank fees.
No business-to-business wires, corporate treasury, or taxes are modelled.

### Elements (agents & accounts)

| Element | Count (defaults) | Role |
|---|---|---|
| **Consumer** | `n_consumers` (default 200) | A household. Receives income, pays bills/debt, buys from merchants, sweeps any monthly surplus to savings/pension. The only *active decision-maker*. |
| **Merchant** | 10 categories × 3 areas × 3 each = **90** | A shop in one (category, area). Passive — only receives money. |
| **Bill / fee stand-ins** | per (bill × area) + debt-service + overdraft-fee + credit-line per area | Counterparties so utilities/rent/telecom/mortgage/loan/debt-service/overdraft payments have a payee — and so a subsister's credit draws have a `credit_line` lender to come from. |
| **IncomeSource** | **3** (one per macro-area) | The "employer". On payday it credits every consumer it serves; its own account goes negative by the total paid out. |
| **BankAccount** | **3 per consumer** | `current` (everyday), `savings`, `pension`. Merchants & income sources hold one each. |

### Connections — how money moves

```
                          ┌────────────► Merchants (10 spending categories)
 IncomeSource ──salary──► Consumer ────► Bills & debt (utilities/rent/telecom/
   (▲, per area)          (●)      │       mortgage/consumer-loan/debt-service)
                                   └────► Fees → bank (overdraft €30, late 11%)

           internal, month-end:  Consumer.current ──sweep──► savings / pension
```

- **Income → Consumer**: `kind="salary"` on the 27th (plus a December 13th-month bonus for payroll & pensions).
- **Consumer → Merchant**: `kind="purchase"`, one of 10 categories.
- **Consumer → Bills/Debt**: `kind="bill"` (includes the `debt_service` repayment that pays down the principal).
- **Consumer → Bank**: `kind="fee"` — `overdraft_fee` or `late_payment_fee`.
- **Credit-line → Consumer**: `kind="loan"`, category `credit_draw` — a subsister borrowing to cover a shortfall (raises `debt_balance`; paired, so money is conserved).
- **Consumer.current → savings/pension**: an internal paired debit/credit at month-end. **Money is moved, never created** — every account reconciles and the whole portfolio is conserved.

The live **money-flow arrows** in the dashboard's network panel colour these flows:
green = salary in, blue = purchases, brown = bills/debt, red = fees → bank.

---

## 2. Consumer dimensions — the "types" of consumer

A consumer is not one of a few fixed archetypes; it is a **combination** of the
independent dimensions below. Heterogeneity is emergent from these draws.

| Dimension | Values | Distribution / shares | Source |
|---|---|---|---|
| **macro_area** | NORTH / CENTRE / SOUTH | **0.46 / 0.20 / 0.34** | **ISTAT** resident population by macro-area (2022). Replaces 0.50/0.27/0.23, which was cited to "Emiliozzi et al. §6" — a section that does not exist — and was in fact card-**spend** midpoints, not people |
| ↳ **relative income level by area** | per area | NORTH ×1.00 · CENTRE ×1.00 · **SOUTH ×0.554** (mean-preserving) | **Semeraro et al. (2020) p. 5** — ISTAT 2017 regional accounts: South GDP per capita €18,500, **45% below Centre-North**; corroborated **p. 27** (wire transfers received by natural persons in the South −44.6%). The paper treats Centre-North as one bloc, so North and Centre are **not** separated — a North>Centre tilt would be an invented number |
| **monthly_income** (€, net) | continuous, > 0 | drawn **per source × per area** (each carries its own mean-preserving multiplier, so the population mean stays ≈ €1,900 and the SHIW bands are undisturbed; what changes is dispersion — Gini 0.30 → 0.34) | **SHIW 2022** (source) + **Semeraro et al. (2020)** (area) |
| **income_source** | payroll / self-employed / pension / transfers / **unemployed** | **shares** 0.52 / 0.20 / 0.20 / 0.03 / 0.05 | ⚠ **flagged ISTAT proxy** (SHIW gives levels, not headcounts) — sweepable. `transfers` = broad social support; `unemployed` = benefit-reliant jobless |
| ↳ relative income level | per source | ×1.08 / ×1.49 / ×0.82 / ×0.50 / ×0.40 (mean-preserving) | payroll/self-emp/pension = **SHIW 2022 §2B**; transfers ×0.50 & unemployed ×0.40 = ⚠ proxies |
| ↳ income **dispersion** (σ) | per source | payroll 0.45 · self-emp 0.70 (widest) · pension 0.35 (tightest) · transfers 0.40 · unemployed 0.30 | ⚠ **flagged proxy** — SHIW gives the relative *mean*, not the spread; only the shape is assumed (cf. debt-service σ) |
| **income_level** | low / middle / high | **absolute euro bands**: ≤ €1,000 / €1,000–€4,000 / > €4,000 per month | **Bank of Italy Payment Behaviour Survey 2023-24** income groups (4 survey bands collapsed 4→3 — the only modelling choice) |
| **income_quartile** | 1–4 | empirical 25/50/75 percentiles of *this run's* incomes | SHIW reports **debt** by income quartile |
| **income_quintile** | 1–5 | empirical 20/40/60/80 percentiles of *this run's* incomes | SHIW reports **savings** by income quintile |
| **has_debt** | true / false | P by quartile: Q1 0.120 · Q2 0.192 · Q3 0.244 · Q4 0.285 | **SHIW 2022 §3** |
| **monthly_debt_service** (€) | 0 or > 0 | annual mean by quartile €3,754 / 4,763 / 5,576 / 8,718, drawn lognormal(σ=0.5), ÷12; serviced day 25 | mean = **SHIW 2022 §3**; σ-shape & day-25 = modelling choice |
| **is_financially_vulnerable** | true / false | a debtor with income below median (quartile ≤ 2) **and** debt-service ratio > 30% | **SHIW 2022 §3** definition of a financially-vulnerable household |
| **debtor_subtype** | climber / chronic / subsister / None | split of the SHIW debtors, **tilted by vulnerability**: vulnerable → chronic-heavy (0.10 / 0.60 / 0.30), resilient → climber-heavy (0.60 / 0.15 / 0.25); sets the repayment & borrowing rule | ⚠ **flagged choice** for the *magnitudes*; the **direction** of the tilt is grounded in the SHIW §3 vulnerability definition — sweepable |
| **debt_balance** (€) | ≥ 0 | opening principal = monthly service × `DEBT_OPENING_MONTHS` (12); accrues `DEBT_MONTHLY_INTEREST_RATE` (0.005/mo); climber repays it to 0 & exits, chronic pays *at most the interest* so the principal is non-decreasing (held ≈flat, drifting up when interest is unaffordable — it never clears), subsister drifts up & borrows | ⚠ **flagged choice** (SHIW gives the service *flow*, not a stock/rate) — sweepable |
| **overdraft_allowed / floor** | true/false; €0 or −1 month debt-service | only **chronic** debtors overdraw (floor = −monthly service); climbers defer, subsisters borrow on a `credit_line` | *who has debt* = SHIW-driven; subtype split & floor = ⚠ flagged choice |
| **is_saver** | true / false | saver rate by quintile ≈ 30% / 40.5% / 51% / 61.5% / 72% (from P(not saving) 0.70 / 0.595* / 0.490* / 0.385* / 0.28; * = interpolated) | **SHIW 2022 §2F** |
| **is_pension_saver** | true / false | a saver who passes a 2nd independent roll of the same quintile probability | **SHIW 2022 §2F** (no contribution rate invented) |
| **accounts** | current / savings / pension | current starts at **one month's income**; savings & pension start **€0** | modelling choice (starting buffer) |

**Savings are emergent, not a rate.** Each consumer tracks monthly income, bills,
debt and discretionary spend. At month-end `residual = income − bills − debt −
discretionary`; if the consumer is a saver and the residual is positive, it is
swept (capped at the current balance) into savings — or pension for a
pension-saver. There is **no savings-rate parameter**; richer / lower-bill
consumers simply leave larger residuals, which is where most heterogeneity arises.

**A note on overlapping debt views.** The model keeps two paper-faithful but
overlapping debt representations — the recurring `mortgage` (€489, 19%) and
`consumer_loan` (€198, 14%) bills **and** the SHIW aggregate `debt_service`
line. They are from different surveys and deliberately **not** reconciled; this
is a documented teaching-prototype simplification, not an invented number.

**Balances over time, not just at the end.** Alongside the final per-account
export, the `DataCollector` records each simulated day the **mean current-account
balance** grouped by income source (`bal_cur_src_*`), income level
(`bal_cur_lvl_*`), and debtor subtype (`bal_cur_dst_*`). The dashboard's
**Balance-trajectory** panel plots these per source (pensions glide, payroll
shows the payday sawtooth, the unemployed hug a low level), and the
**Chronic-debtor** panel uses the per-subtype series to contrast climbers
rebuilding a buffer against chronic/subsister households staying cash-poor.

---

## 3. Spending, bills, and the calendar

### Spending categories (purchases) — *Emiliozzi et al. (2023) §2.1, Figures 4 and 6*

10 card-visible categories. The shares below are shares of **euros spent** —
Figure 4 is titled "Average shares of expenditure categories" and Figure 6
benchmarks it against COICOP national-accounts expenditure. They are *not* the
probability of picking a category: the model draws the category and then the
ticket independently, so `sample_category()` draws with probability
`share / E[ticket]`, normalised. That makes the realised euro mix equal the
table below by construction.

Ticket size comes from a per-category lognormal (BoI POS averages). The
share-weighted mean is **€38.06**; a real run measures **€36.73**. An earlier
version of this file said "≈ €28" and credited it to the paper's §9 — the paper
has no §9, and no such euro figure appears in it.

| euro share | retail 0.26 · food 0.20 · hotels_rest 0.11 · travel 0.09 · clothing 0.08 · home 0.07 · phones_web 0.05 · repairs 0.05 · cash_advance 0.05 · services 0.04 |
|---|---|
| draw probability | retail 0.329 · food 0.259 · hotels_rest 0.109 · travel 0.034 · clothing 0.060 · home 0.049 · phones_web 0.074 · repairs 0.021 · cash_advance 0.031 · services 0.034 |

The paper's Figure 4 has nine bands; `home` and `repairs` are merged there and
split here by hand, so `repairs`, `cash_advance` and `services` have no directly
traceable source value.

### Recurring bills — *Bank of Italy Payment Behaviour Survey 2023-24 §8*

(share of households, mean €, day of month). A consumer subscribes to each with its share.

| utilities 0.73 / €124 / day 10 · telecom 0.70 / €40 / 15 · rent 0.24 / €440 / 1 · mortgage 0.19 / €489 / 5 · consumer_loan 0.14 / €198 / 20 |
|---|

### Calendar multipliers — *Emiliozzi et al. (2023) §3, direction only*

- **Weekday**: Fri ×1.10, Sat ×1.20, Aug-type weekdays ×0.95, etc.
- **Month**: December ×1.25 (peak), August ×0.85 (trough).
- **Holiday** ×1.15; **Christmas window (Dec 20–31)** ×1.40.
- **Payday**: the **27th** (proxy for last business day — *structural-inequalities paper §9*).
- **13th-month bonus** ("tredicesima"): an extra month's income in **December** for **payroll & pension** recipients (*wire-transfer paper §9* documents the December peak; the month set is a flagged choice).

---

## 4. Behavioural-economics layer (the thesis contribution)

⚠ **Different provenance.** These three come from non-Italian papers: the
behaviour's existence/shape is grounded, the **euro/percentage magnitude is a
deliberate modelling choice and is swept** (`scripts/sweep_behavioural.py`) so no
result depends on a single foreign number.

| Mechanism | Effect in model | Magnitude | Paper |
|---|---|---|---|
| **Payday spike** | mean-neutral multiplier on *daily* spending intensity — peaks just after payday, troughs before the next; monthly totals (and the savings residual) unchanged, only *timing* moves | peak ×1.5 (≈ +50%) | **Olafsson & Pagel (2018)**, *The Liquid Hand-to-Mouth*, RFS 31(11) — Iceland app data |
| **Overdraft fee** | flat fee the moment a payment pushes the current account below €0 | **€30** flat per event | **Stango & Zinman (2014)**, RFS 27(4) — US checking accounts |
| **Late-payment fee** | a liquidity-constrained household pays a bill *late with a penalty* rather than not at all; fee added when the overdue bill is finally settled | **11%** of the bill | **Dahan & Nisan (2020)**, CESifo WP 8733 — Israeli utility bills |

Heterogeneity reference: **Campbell** is cited for the principle that financial
mistakes (fees) concentrate among lower-income / lower-literacy households —
which is why fees here fall disproportionately on low-quartile, debt-holding,
liquidity-constrained consumers. This is also the grounding for the **chronic**
archetype tilt (§2): the chronic, never-escaping debtors concentrate among the
SHIW financially-vulnerable, where Campbell's fee incidence and Olafsson &
Pagel's liquid-hand-to-mouth dynamics bite hardest.

---

## 5. Changing the numbers

- **Every constant** is in [`src/synthitaly/numbers.py`](../src/synthitaly/numbers.py); edit there and it flows through model, notebook, and dashboard.
- **Sweep the behavioural magnitudes** with `scripts/sweep_behavioural.py` to confirm no conclusion hinges on a foreign figure.
- **See it run** with `uv run solara run src/synthitaly/viz.py` — the network panel's live arrows show these flows day by day.

---

## 6. Full references

The tiered version of this list — with what each source licenses the model to claim, and the
replication targets — is [`REFERENCES.md`](REFERENCES.md). The PDFs themselves are publisher
copyright and are not redistributed with this repository.

| Short name used above | Full reference |
|---|---|
| **SHIW 2022** | Banca d'Italia (2024). *Survey on Household Income and Wealth — Year 2022.* |
| **Payment Behaviour Survey 2023-24** | Banca d'Italia. *Report on the payment attitudes of consumers in Italy* (ECB SPACE 2024 survey; fieldwork Sep 2023 – Jun 2024). |
| **Emiliozzi et al. (2023)** | Emiliozzi, S., Rondinelli, C. & Villa, S. (2023). *Consumption during the Covid-19 pandemic: evidence from Italian credit cards.* Banca d'Italia, Questioni di Economia e Finanza (Occasional Papers) No. 769, May 2023. |
| **Structural inequalities / wire transfers** | Semeraro, A. et al. (2020). *Structural inequalities emerging from a large wire transfers network.* Applied Network Science 5:76. |
| **Olafsson & Pagel (2018)** | Olafsson, A. & Pagel, M. (2018). *The Liquid Hand-to-Mouth: Evidence from Personal Finance Management Software.* Review of Financial Studies 31(11). |
| **Stango & Zinman (2014)** | Stango, V. & Zinman, J. (2014). *Limited and Varying Consumer Attention: Evidence from Shocks to the Salience of Bank Overdraft Fees.* Review of Financial Studies 27(4). |
| **Dahan & Nisan (2020)** | Dahan, M. & Nisan, U. (2020). *Late Payments, Liquidity Constraints and the Mismatch between Due Dates and Paydays.* CESifo Working Paper 8733. |
| **Campbell (2006)** | Campbell, J. Y. (2006). *Household Finance.* Journal of Finance 61(4). |
| **Jiang et al. (2022)** | Jiang, N., Crooks, A. T., Kavak, H., Burger, A. & Kennedy, W. G. (2022). *A method to create a synthetic population with social networks for geographically-explicit agent-based models.* Computational Urban Science 2:7. |
| **ISTAT** | Istituto Nazionale di Statistica — resident population by macro-area (2022) for `MACRO_AREA_WEIGHTS`; the 2017 regional-economy report for the South/Centre-North GDP-per-capita gap, quoted in Semeraro et al. (2020) p. 5. |

> **Removed: `has_property_income`.** A flat 10% of consumers used to receive an extra
> payday credit worth 5% of their own income. Neither number came from any source in the
> literature set — SHIW records property income as a category but publishes only "+5.7% on
> average" for 2020-22, with no incidence and no level — and nothing in the model linked the
> `rent` bill to anyone's property income. It was removed rather than left flagged. Side
> effect: `n_income` (the count of income credits) is now constant for every consumer, so it
> is excluded from the analysis column sets (`features.DEGENERATE_COLUMNS`).

> **The `§n` anchors for Emiliozzi et al. have been checked.** They were inherited from an
> earlier draft that misattributed the paper (as "Carlsen-Riccaboni"), and were verified
> against the published document afterwards. The paper runs **§1–§5 plus appendices**: there
> is no §6, §9 or §11, and every anchor that pointed at one of those has been re-anchored or
> removed. `CATEGORY_SHARES` is §2.1 (Figs. 4 and 6); the weekday and month multipliers are
> given as **direction only**, because §3 reports weekday fixed effects without coefficients
> and the magnitudes here are this model's own.
