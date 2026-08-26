# How it works — a walkthrough

The whole prototype is three Python files under `src/synthitaly/`. This
document explains each one in plain English. Read it next to the files —
each section names exactly the file it describes.

## The bank-eye framing

Imagine you are a bank looking at your retail customers' accounts. Every
day, on each customer's account, you might see:

- A **salary** lands on payday.
- A **bill** goes out (utilities, rent, mortgage, telecom).
- One or several **purchases** at merchants.

That is everything this simulator emits. We do not model anything the bank
would not see — no manufacturer-to-distributor wires, no corporate
treasury flows, no taxes. The four Italian source papers contain a lot
more than that. This prototype uses only the consumer-visible numbers.

---

## File 1 — `numbers.py`

Every empirical Italian constant lives in this one file. Three sections:

### Constants (the numbers themselves)

| Name | What it is | From which paper |
|---|---|---|
| `MACRO_AREA_WEIGHTS` | NORTH / CENTRE / SOUTH population shares (0.46, 0.20, 0.34) | ISTAT resident population (was mis-cited to a nonexistent Emiliozzi §6) |
| `CATEGORY_SHARES` | Share of card **euros** in each of 10 categories | Emiliozzi et al. (2023) §2.1, Figures 4 and 6 |
| `CATEGORY_TICKET_LOGNORMAL` | (mu, sigma) of the ticket-size distribution per category | BoI POS averages (the "§9 overall mean €28" it used to cite is not in the paper) |
| `WEEKDAY_MULTIPLIER` | Mon–Sun multipliers on a normal day's spend | Direction only: Emiliozzi §3 includes weekday fixed effects but reports no coefficients. **Magnitudes are this model's own** |
| `MONTH_MULTIPLIER` | January–December multipliers | Direction only: Emiliozzi §2 notes Christmas week is the annual peak. The August dip and all magnitudes are **unsourced** |
| `HOLIDAY_MULTIPLIER`, `CHRISTMAS_WINDOW_MULTIPLIER` | Bumps on national holidays and Dec 20–31 | Emiliozzi §2 (Christmas peak); magnitudes are this model's own |
| `BILL_TYPES` | Utilities / telecom / rent / mortgage / consumer_loan: share of households, mean EUR, day-of-month due | BoI Payment Behaviour Survey 2023-24 §4 "Recurring payments", print p. 16 / fig. A4.1 (was cited as §8; the report has only 7 sections) |
| `INCOME_LOGNORMAL` | Distribution of monthly net income in EUR | SHIW 2022 |
| `PAYDAY_DAY_OF_MONTH` | The 27th — when salaries arrive | Distilled from structural-inequalities §9 (end-of-month spike) |
| `DEBT_PROBABILITY_BY_INCOME_QUARTILE` | P(holds debt) by income quartile | SHIW 2022 §3 |
| `DEBT_SERVICE_MEAN_BY_QUARTILE_EUR` | Mean annual debt service by income quartile | SHIW 2022 §3 |
| `DEBT_PAYMENT_DIRECT_DEBIT` | Direct-debit share for mortgage / consumer_loan (reference only) | BoI Payment Behaviour Survey 2023-24 §8.2 |

### Calendar helpers

Small functions on `datetime.date`:
- `is_holiday(d)` — true on Italian public holidays (including Easter Monday).
- `is_weekend(d)` — Saturday or Sunday.
- `is_christmas_window(d)` — Dec 20–31.
- `is_payday(d)` — the 27th of any month.

### Samplers

Three functions the model uses on every step:
- `sample_category(rng)` — pick a category. **Not** weighted by `CATEGORY_SHARES` directly: those are shares of *euros*, and the ticket is drawn separately, so the draw probability is `share / E[ticket]` normalised. That makes the realised euro mix match the paper exactly; it also means cheap categories come up more often than their euro share (retail 0.26 → 0.33) and expensive ones less (travel 0.09 → 0.034).
- `sample_ticket(rng, category)` — draw a EUR amount from that category's lognormal.
- `daily_intensity(d)` — combine weekday × month × holiday into one number; the higher this is, the more likely each consumer is to buy something on day `d`.
- `sample_income(rng)` — pull a monthly net income from the SHIW lognormal.

**If you want to change the simulation's behaviour without touching code logic, this is the file to edit.**

---

## File 2 — `model.py`

This is the simulation engine. A tiny `BankAccount` class, three agent classes, and the model class.

### `BankAccount` (and `BankEntry`)

Every Consumer, Merchant, and IncomeSource owns one `BankAccount`. An account holds a list of `BankEntry` records and a balance:

- `account.entries` — the statement: each entry has `date`, `direction` (`"in"` / `"out"`), `counterparty`, `category`, `amount_eur`.
- `account.balance` — the current balance. Maintained on every debit/credit so it's O(1) to read.
- `account.debit(...)` and `account.credit(...)` — append an entry and adjust the balance.

This makes the accounting **visible**: pick any consumer in a REPL and read `c.account.entries` to see their statement; the balance is auditable from those entries alone.

### Agents

| Class | What it is | What it does on `step()` |
|---|---|---|
| `Merchant` | A shop in one (category, macro-area) | Nothing — passive; receives money into `account` |
| `IncomeSource` | One per macro-area | On payday, debits its own account and credits every consumer it serves |
| `Consumer` | A household member | (1) pay any bills due today, (2) maybe buy from a merchant |

### `ItalyModel.__init__`

Builds everything in order:

1. **Merchants** — one pool per (category × macro-area). With defaults: 10 categories × 3 areas × **3 merchants = 90 merchants**. (Why 3 per (category, area)? Large enough that consumers repeat-visit several shops, small enough to keep the picture readable.)
2. **Bill stand-in merchants** — one per (bill_type × macro-area), 5 × 3 = 15, plus a `debt_service`, an `overdraft_fee`, and a `credit_line` stand-in per area (9 more) = 24. They exist so utility / rent / mortgage / telecom / consumer-loan / debt-service / overdraft-fee payments have a counterparty, and so a subsister's credit draws have a lender to come from.
3. **Income sources** — three, one per macro-area.
4. **Consumers** — each gets assigned a macro-area (weighted by `MACRO_AREA_WEIGHTS`), an income (`sample_income`), a starting balance (one month's income), and a random subset of bill types.
5. **Income bands** — once every consumer's income is drawn, `_assign_income_bands()` tags each one with an income **quartile** (1–4) and **quintile** (1–5). These are *empirical percentiles* of the realised population, not hard-coded thresholds: SHIW reports debt by income quartile and savings by income quintile but gives no cut-point table, so we split the population we actually generated. The bands drive debt and savings behaviour (below) and the account-clustering view.
6. **A small network graph** — purely visual, for the Solara network panel. Includes consumer nodes, a handful of merchant nodes, and the 3 IncomeSource nodes so you can see where money enters the system.
7. **A `mesa.DataCollector`** — records `daily_txn_count` and `daily_eur_total` so the line chart has something to plot.

### Debt

`_assign_debt()` rolls a debt flag for every consumer using the SHIW
debt-participation probability for their income quartile (Q1 ≈ 12 % … Q4 ≈
28.5 %). A debt-holder is given a monthly debt-service amount — the SHIW mean
annual figure for their quartile, drawn lognormally and divided by 12 — and an
opening **debt principal** (`debt_balance`): a *stock*, taken as that monthly
service × `DEBT_OPENING_MONTHS`. SHIW gives only the service *flow*, so the
stock and its monthly interest (`DEBT_MONTHLY_INTEREST_RATE`) are flagged
modelling choices, not Italian facts.

### Debtor subtypes — climber / chronic / subsister

The SHIW roll only decides *who* holds debt; `_assign_debt()` then splits those
debtors into three behavioural archetypes (`DEBTOR_SUBTYPE_SHARE`), and
`Consumer._service_debt()` (run once a month, day 25) gives each a different
repayment rule so their balance trajectories diverge:

- **climber** — repays the full scheduled service, so the principal falls; when
  it reaches zero the consumer *leaves debt for good* (flag cleared, overdraft
  permission withdrawn — the subtype *label* is kept so you can still see "a
  climber who made it out"). Floor `0.0`, no overdraft.
- **chronic** — repays interest only, so the principal stays flat and they never
  escape. They run a standing overdraft (floor = −1 month of service), so this
  is the subtype that goes into the red.
- **subsister** — repays only a token amount and instead **borrows** on a
  per-area `credit_line` stand-in (logged `kind="loan"`) to cover any bill the
  account can't otherwise meet. They start with no cash cushion and sweep any
  month-end surplus out, so the current account *hugs zero* ("ekes out").

Interest accrues even in a month a debtor can't afford to pay, so missed
payments make the principal grow — the realistic direction. Every borrow and
repayment is a paired debit/credit through a stand-in counterparty, so money
stays conserved and the per-account reconciliation still holds.

### Overdraft — why agents stopped being identical

Originally *every* consumer skipped a bill or purchase the moment
`balance < amount`. Now affordability goes through `Consumer._can_afford()`:
a payment is allowed unless it would push the balance below that consumer's
`_overdraft_floor`. The floor is `0.0` for everyone without debt — exactly
the old rule — but for a debt-holder it is `−(one month of their own debt
service)`, so they can dip into the red when cash is tight. Because each
debt-holder's floor is derived from their own SHIW-drawn debt burden, the
floors differ from agent to agent: the population is no longer uniform, and
who-skips-what now depends on each consumer's income quartile and debt draw
rather than a single global rule. No paper gives an overdraft limit, so its
*size* is a flagged modelling choice; *who* gets one is paper-driven (SHIW
debt participation).

Note on overlap: the prototype keeps two *paper-faithful but overlapping*
views of debt — the pop_behaviours recurring bills (`mortgage` €489 / 19 %,
`consumer_loan` €198 / 14 %, which a consumer subscribes to like any bill)
**and** the SHIW aggregate debt-service line. They come from different
surveys and are deliberately *not* reconciled into one figure; this is a
documented teaching-prototype simplification, not an invented number.

### Savings and pension — emergent, not a rate

Every consumer now holds **three** accounts (`c.accounts.current` /
`.savings` / `.pension`); `c.account` still points at the current account so
old code and tests are untouched. `_assign_savings()` rolls a saver flag from
the SHIW probability of *not* saving for the consumer's income quintile (Q1
≈ 70 % don't save … Q5 ≈ 28 %). A second, independent roll with the *same*
probability marks some savers as **pension-savers** — that is the only thing
that decides pension vs ordinary savings, so no contribution rate is invented.

The amount saved is **emergent**. The consumer keeps four running monthly
accumulators (income, bills, debt service, discretionary). On the 1st of each
month `_month_close()` settles the month just ended: `residual = income −
bills − debt − discretionary`. If the consumer is a saver and the residual is
positive, that residual (capped at the current balance) is swept into
`savings`, or into `pension` for a pension-saver. The sweep is an **internal
paired debit/credit** between the consumer's own accounts, so money is moved,
never created — every account still reconciles independently and the
whole-portfolio total is conserved. There is no savings-rate parameter
anywhere; richer/lower-bill consumers simply have larger residuals, which is
where most of the agent heterogeneity now comes from.

### `ItalyModel.step()`

One day:

1. Run every `IncomeSource.step()` (so salaries arrive first).
2. Run every `Consumer.step()` in a shuffled order.
3. Compute the two KPIs for the day; the data collector records them.
4. Advance `self.today` by one day.

### `ItalyModel.run()`

A `for` loop that calls `step()` `n_days` times.

### Where the output lives

After `model.run()`:
- `model.transactions` — a list of dicts. Each dict has `date`, `kind` (salary / bill / purchase), `from`, `to`, `category`, `amount_eur`, `macro_area`. Drop straight into pandas.
- `model.datacollector.get_model_vars_dataframe()` — a per-day DataFrame with the two KPIs.
- `model.consumers` — the consumer agents. Each has `c.account.balance` / `c.account.entries` (the current account) plus `c.accounts.savings` and `c.accounts.pension`, and the bands/flags `income_quartile`, `income_quintile`, `has_debt`, `debtor_subtype` (`climber`/`chronic`/`subsister`, or `None`), `debt_balance` (outstanding principal), `is_saver`, `is_pension_saver`.
- `model.merchants` — the merchant pools (`dict[(category, area)] -> list[Merchant]`). Each merchant has `m.account.balance` reflecting cumulative receipts and `m.account.entries` for the full credit list.
- `model.income_sources` — `dict[area] -> IncomeSource`. Each has `src.account` (will be negative — it equals the total salaries paid out).

**Nothing is written to disk** unless you explicitly call `pd.DataFrame(model.transactions).to_csv(...)`. The notebook does that at the end.

---

## File 3 — `viz.py`

The interactive Solara app. **Six** panels, each a small function:

| Panel | Type | What it shows |
|---|---|---|
| `SpendingByArea` | Custom `@solara.component` | Bar chart of cumulative purchase EUR per macro-area. Live — updates each step. |
| `NetworkPanel` | Custom `@solara.component` | A clean **layered** diagram: income sources (▲) → consumers (●, banded by macro-area) → destinations (■: 10 purchase categories + Bills & debt + Fees → bank). **Live money-flow arrows** show where euros moved on the most recent day (green = salary, blue = purchases, brown = bills/debt, red = fees → bank); width ∝ €. Includes a "Download PNG" button. |
| `KPIPanel` | Mesa's `make_plot_component` | Line plot of `daily_txn_count` and `daily_eur_total`. Live. |
| `BehaviouralEventsPanel` | Custom `@solara.component` | Daily overdraft / late-payment fee counts (stacked bars) + daily purchase EUR with payday markers, so the behavioural-economics layer is visible. Live; "Download PNG" button. |
| `AccountInspectorPanel` | Custom `@solara.component` | Pick a **cluster** (macro-area \| income quartile \| financial status), then a consumer, and see their current/savings/pension statements plus a running-balance sparkline. Read-only; reuses `model.clusters()` so the clustering logic lives in one place. |
| `ArchetypesPanel` | Custom `@solara.component` | Static reference card: agent kinds, the 10 spending categories with paper share + average ticket, the 5 bill types with share + amount, the 3 macro-areas with population share. |

Sliders on the left set seed, consumers, merchants per category × area, and days.

> For a full data dictionary of every consumer dimension and its source paper,
> see [`MODEL_REFERENCE.md`](MODEL_REFERENCE.md).

### Why this app works when the old one didn't

Two problems recorded against the earlier, parked version of the app:

1. **The old model wrote to disk during `__init__`.** That fought with the Solara server's startup health check. **Fix here:** the new model writes nothing to disk during construction, so the server starts cleanly.
2. **`make_space_component` was hardcoded to read `model.grid`.** Two calls to it would render the same picture twice. **Fix here:** the network panel is a custom `@solara.component` that computes its own layered layout with matplotlib (no `make_space_component`, and no spring layout — positions are deterministic).

---

## Doing more with this

- **Change a number** → edit `numbers.py`. Nothing in `model.py` should know specific Italian values.
- **Add an agent kind** → put the new class in `model.py` next to the others.
- **Plot something different** → add a new `@solara.component` function in `viz.py` and append it to the `components=[...]` list at the bottom.
- **Calibrate against a paper** → every number and its source is in `numbers.py`, with the full citation list in [`REFERENCES.md`](REFERENCES.md). The parked version carried a module per paper; this one keeps them all in one file on purpose.
