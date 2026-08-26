# References

Every empirical number in this model traces to a source below. The PDFs themselves are
**not redistributed here** — they are publisher copyright — so this page is the
provenance record in their place. Where a source note in the code says "see
`docs/REFERENCES.md`", this is the page it means.

The per-constant mapping lives in [`MODEL_REFERENCE.md`](MODEL_REFERENCE.md) (the data
dictionary, §6 of which this page expands) and in the source comments in
[`src/synthitaly/numbers.py`](../src/synthitaly/numbers.py). Reading notes on the four
Italian sources are kept in `italy_papers/notes on each paper/`.

**The tiers matter, and they are not interchangeable:**

| Tier | What it licenses the model to claim |
|---|---|
| ① **Italian, calibrated** | The number *is* an Italian empirical figure. Quotable as such. |
| ② **Behavioural overlay** | The **existence and direction** of the behaviour is paper-grounded; the **magnitude** is a modelling choice, swept rather than claimed. All three sources are non-Italian. |
| ③ **Method** | Governs how the model is built, described, and validated — not what any number is. |
| ④ **Replication target** | A published result the model is scored *against* in `scripts/replicate_*.py`. Not an input. |

> **DOI column.** Entries marked `—` are ones whose identifier is not recorded anywhere in
> this repository; the venue is as the code and docs state it. Check those against the
> publisher before quoting one in print. The rest are unambiguous (several are recoverable
> from the publisher's own filename).

---

## ① Italian sources — the calibrated layer

| Source | Reference | Used for | DOI / locator |
|---|---|---|---|
| **SHIW 2022** | Banca d'Italia (2024). *Survey on Household Income and Wealth — Year 2022.* | Income levels and dispersion by source; debt incidence and debt service by income quartile; the financial-vulnerability definition; saving rates by income quintile | Banca d'Italia *Statistics* series |
| **Payment Behaviour Survey 2023-24** | Banca d'Italia. *Report on the payment attitudes of consumers in Italy.* ECB SPACE 2024 survey; fieldwork Sep 2023 – Jun 2024. | The bill table; the three absolute income bands (four survey bands collapsed to three) | — |
| **Emiliozzi et al. (2023)** | Emiliozzi, S., Rondinelli, C. & Villa, S. (2023). *Consumption during the Covid-19 pandemic: evidence from Italian credit cards.* Banca d'Italia, Questioni di Economia e Finanza (Occasional Papers) No. 769, May 2023. | Spending-category shares (§2.1, Figs. 4 and 6); weekday and month seasonality (direction only — the paper reports no coefficients) | QEF No. 769 |
| **Semeraro et al. (2020)** | Semeraro, A. et al. (2020). *Structural inequalities emerging from a large wire transfers network.* Applied Network Science 5:76. | The South × 0.554 mean-preserving income multiplier (p. 5, corroborated p. 27); the payday date and the December bonus | Appl. Netw. Sci. 5:76 |
| **ISTAT** | Istituto Nazionale di Statistica. Resident population by macro-area (2022); regional economic accounts (2017). | `MACRO_AREA_WEIGHTS` 0.46 / 0.20 / 0.34; the South vs Centre-North GDP-per-capita gap, quoted via Semeraro et al. p. 5 | istat.it |

## ② Behavioural-economics overlay — shape grounded, magnitude swept

| Source | Reference | Used for | DOI / locator |
|---|---|---|---|
| **Olafsson & Pagel (2018)** | Olafsson, A. & Pagel, M. (2018). *The Liquid Hand-to-Mouth: Evidence from Personal Finance Management Software.* Review of Financial Studies 31(11). | That low-liquidity households spend against the payday cycle — the mechanism behind the payday spike | — |
| **Stango & Zinman (2014)** | Stango, V. & Zinman, J. (2014). *Limited and Varying Consumer Attention: Evidence from Shocks to the Salience of Bank Overdraft Fees.* Review of Financial Studies 27(4). | That overdraft incidence responds to salience — the existence of the overdraft-fee event | — |
| **Dahan & Nisan (2020)** | Dahan, M. & Nisan, U. (2020). *Late Payments, Liquidity Constraints and the Mismatch between Due Dates and Paydays.* CESifo Working Paper 8733. | That late payment is driven by due-date/payday mismatch rather than by preference — the late-fee rule | CESifo WP 8733 |
| **Campbell (2006)** | Campbell, J. Y. (2006). *Household Finance.* Journal of Finance 61(4). | Framing for the household-finance layer as a whole | — |

**Read but deliberately not implemented** — recorded here because the model would otherwise
look as though it used them:

| Source | Why not wired in |
|---|---|
| Prelec & Simester (2001), on the credit-card willingness-to-pay premium | Requires a payment-instrument layer, which this model does not have |
| Le Blanc et al., on euro-area household saving behaviour | Saving here is emergent and SHIW-calibrated, so the paper had nothing left to set |

## ③ Method

| Source | Reference | Used for | DOI / locator |
|---|---|---|---|
| **Grimm et al. (2010)** | Grimm, V. et al. (2010). *A standard protocol for describing individual-based and agent-based models: ODD.* Ecological Modelling 221(23). | The specification format of [`ODD.md`](ODD.md) and diagram `d06_odd_overview` | — |
| **Jiang et al. (2022)** | Jiang, N., Crooks, A. T., Kavak, H., Burger, A. & Kennedy, W. G. (2022). *A method to create a synthetic population with social networks for geographically-explicit agent-based models.* Computational Urban Science 2:7. | The thesis method paper. **Note:** the social-network half is not implemented in the shipped model — `_build_visual_graph()` draws a graph for the dashboard that no agent reads | Comput. Urban Sci. 2:7 |
| **Fagiolo, Moneta & Windrum (2007)** | Fagiolo, G., Moneta, A. & Windrum, P. (2007). *A Critical Guide to Empirical Validation of Agent-Based Models in Economics.* Computational Economics 30, 195–226. | The validation framing the replication chapter is organised around | 10.1007/s10614-007-9104-4 |
| **Mesa 3** | The Mesa developers. *Mesa 3: Agent-based modeling with Python.* Journal of Open Source Software (2025). | The simulation framework the model is built on | 10.21105/joss.07668 |

## ④ Replication targets — published results the model is scored against

Each is reproduced by a script that states in its own docstring what it replicates, what it
substitutes, and where it disagrees. The disagreements are the finding, not a bug.

| Source | Reference | Script | DOI / locator |
|---|---|---|---|
| **So, Thomas, Seow & Mues** | *Using a Transactor/Revolver scorecard to make credit and pricing decisions.* Southampton Management School / Nottingham University Business School Malaysia. (No year recorded in this repository.) | [`scripts/replicate_so.py`](../scripts/replicate_so.py) | — |
| **Khandani, Kim & Lo (2010)** | Khandani, A. E., Kim, A. J. & Lo, A. W. (2010). *Consumer credit-risk models via machine-learning algorithms.* Journal of Banking & Finance 34, 2767–2787. | [`scripts/replicate_khandani.py`](../scripts/replicate_khandani.py) | 10.1016/j.jbankfin.2010.06.001 |
| **Butaru, Chen, Clark, Das, Lo & Siddique (2015)** | *Risk and Risk Management in the Credit Card Industry.* NBER Working Paper 21305. | [`scripts/replicate_butaru.py`](../scripts/replicate_butaru.py) | nber.org/papers/w21305 |

---

## Supporting statistical method

Cited in the code where the technique is applied rather than as model inputs:

- **Breiman et al. (1984)** — CART, the estimator family in Khandani et al.
- **Landis & Koch (1977)** — the kappa interpretation bands used in the replications.
- **DeLong, DeLong & Clarke-Pearson (1988)** — the correlated-ROC test So et al. use to
  compare their Models 1 and 4.
- **Cessie & van Houwelingen (1992)** — the ridge logistic penalty Butaru et al. specify.
