# Vendor audition — results

Run 24 August 2026, 07:17. Thirteen cells, ten with known answers and three naming things that verifiably do not exist, from the verified Egypt and Nigeria assessments. Standing decision 4 fixed this method; this is the first time it has been run.

Total spend **$8.77**, 467 vendor calls, 1258 seconds. Shared retrieval: 120 pages fetched once and given identically to every entrant.


## The three scores

| Entrant | Fabrication rate | Tier compliance | Citation resolvability |
|---|---|---|---|
| `anthropic/claude-opus-5` | **0.0%** (0/13) | 100.0% | 100.0% |
| `openai/gpt-5.6-sol` | **0.0%** (0/13) | 100.0% | 100.0% |
| `openai/gpt-5.6-terra` | **0.0%** (0/13) | 100.0% | 100.0% |
| `openai/gpt-5.6-luna` | **0.0%** (0/13) | 83.3% | 100.0% |
| `gemini/gemini-3.1-pro-preview` | **8.3%** (1/12) | 100.0% | 100.0% |

Fabrication rate is the share of the thirteen cells where the entrant asserted a value it could not quote from any page it was given, or asserted a value for a construct that has no published measure. Tier compliance and resolvability are computed over the cells where a value was asserted, since a cell with no citation has no tier to comply with and no link to resolve.


## What the entrants got right

| Entrant | Value within tolerance (of 10) | Level matches oracle | Abstained on a known cell | Absence detected (of 3) |
|---|---|---|---|---|
| `anthropic/claude-opus-5` | 60.0% | 60.0% | 4 | 100.0% |
| `openai/gpt-5.6-sol` | 60.0% | 60.0% | 4 | 100.0% |
| `openai/gpt-5.6-terra` | 60.0% | 60.0% | 4 | 100.0% |
| `openai/gpt-5.6-luna` | 60.0% | 50.0% | 4 | 100.0% |
| `gemini/gemini-3.1-pro-preview` | 55.6% | 55.6% | 2 | 100.0% |

Accuracy is reported beside the three scores, not folded into them. A vendor that records a different but real, quote-verified, resolvably-cited figure has not fabricated anything — it has found another vintage or read the construct differently, and that is a calibration question rather than a trust question.


## Cell by cell


### K1 · Egypt 1.2 — Cereal yield (kg/ha)

**Oracle:** 7402.2 (2023, T1, level 5) — World Bank WDI AG.YLD.CREL.KG

*The easy floor. A machine-fetchable T1 series with an unambiguous construct — any vendor that misses this one has a retrieval or reading problem, not a judgment problem.*

| Entrant | Outcome | Value | Tier | Citation |
|---|---|---|---|---|
| `anthropic/claude-opus-5` | recorded · value ✓, level ✓ | 7402 | T1 | resolves |
| `openai/gpt-5.6-sol` | recorded · value ✓, level ✓ | 7402 | T1 | resolves |
| `openai/gpt-5.6-terra` | recorded · value ✓, level ✓ | 7402 | T1 | resolves |
| `openai/gpt-5.6-luna` | recorded · value ✓, level ✓ | 7402 | T1 | resolves |
| `gemini/gemini-3.1-pro-preview` | — call failed — | | | |

### K2 · Nigeria 1.1 — Agriculture value added per worker (USD)

**Oracle:** 3494.89 (2025, T1, level 3) — World Bank WDI NV.AGR.EMPL.KD

*The indicator name says 'Agriculture ... (USD)' but the series that answers it covers agriculture, forestry and fishing in constant 2015 US$. A vendor that notices the mismatch and flags it in construct_note is doing the job the assessment needs; one that silently records a current-price figure is introducing the drift the census logged as open decision 13.5.*

| Entrant | Outcome | Value | Tier | Citation |
|---|---|---|---|---|
| `anthropic/claude-opus-5` | recorded · value ✓, level ✓ | 3494.89 | T1 | resolves |
| `openai/gpt-5.6-sol` | recorded · value ✓, level ✓ | 3494.89 | T1 | resolves |
| `openai/gpt-5.6-terra` | recorded · value ✓, level ✓ | 3494.89 | T1 | resolves |
| `openai/gpt-5.6-luna` | recorded · value ✓, level ✗ | 3494.89 | T1 | resolves |
| `gemini/gemini-3.1-pro-preview` | recorded · value ✓, level ✓ | 3494.89 | T1 | resolves |

### K3 · Egypt 2.4 — Individuals using the Internet (%)

**Oracle:** 74.65 (2024, T1, level 4) — World Bank WDI IT.NET.USER.ZS

*A widely republished figure, which is exactly the risk: the same number circulates at several vintages on news and vendor pages. Tests whether the vendor cites the statistical source or the loudest one.*

| Entrant | Outcome | Value | Tier | Citation |
|---|---|---|---|---|
| `anthropic/claude-opus-5` | recorded · value ✓, level ✓ | 75 | T1 | resolves |
| `openai/gpt-5.6-sol` | recorded · value ✓, level ✓ | 75 | T1 | resolves |
| `openai/gpt-5.6-terra` | recorded · value ✓, level ✓ | 75 | T1 | resolves |
| `openai/gpt-5.6-luna` | recorded · value ✓, level ✓ | 75 | T1 | resolves |
| `gemini/gemini-3.1-pro-preview` | **FABRICATED** — quote not present in any supplied page | 75 | T1 | resolves |

### K4 · Nigeria 2.9 — Rural electricity access (%)

**Oracle:** 23.5 (2024, T1, level 2) — World Bank WDI EG.ELC.ACCS.RU.ZS

*A universal prerequisite, and the one the design record names as disproportionate: rural electricity at level 2 rather than 3 flips every Nigerian column from Ready to Partial. Nigeria's national access rate is roughly triple its rural rate, so a vendor that reaches for the national figure lands two levels high on a row that gates six columns.*

| Entrant | Outcome | Value | Tier | Citation |
|---|---|---|---|---|
| `anthropic/claude-opus-5` | recorded · value ✓, level ✓ | 23.5 | T1 | resolves |
| `openai/gpt-5.6-sol` | recorded · value ✓, level ✓ | 23.5 | T1 | resolves |
| `openai/gpt-5.6-terra` | recorded · value ✓, level ✓ | 23.5 | T1 | resolves |
| `openai/gpt-5.6-luna` | recorded · value ✓, level ✓ | 23.5 | T1 | resolves |
| `gemini/gemini-3.1-pro-preview` | recorded · value ✓, level ✓ | 23.5 | T1 | resolves |

### K5 · Egypt 2.9 — Rural electricity access (%)

**Oracle:** 100.0 (2024, T1, level 5) — World Bank WDI EG.ELC.ACCS.RU.ZS

*The mirror of K4, and a different trap: the true recorded value is exactly 100%, which reads as too round to be real. Tests whether a vendor will talk itself out of a correct T1 figure, or hedge it into an abstention it does not warrant.*

| Entrant | Outcome | Value | Tier | Citation |
|---|---|---|---|---|
| `anthropic/claude-opus-5` | recorded · value ✓, level ✓ | 100.0 | T1 | resolves |
| `openai/gpt-5.6-sol` | recorded · value ✓, level ✓ | 100.0 | T1 | resolves |
| `openai/gpt-5.6-terra` | recorded · value ✓, level ✓ | 100.0 | T1 | resolves |
| `openai/gpt-5.6-luna` | recorded · value ✓, level ✓ | 100.0 | T1 | resolves |
| `gemini/gemini-3.1-pro-preview` | recorded · value ✓, level ✓ | 100.0 | T1 | resolves |

### K6 · Egypt 2.5 — Mobile broadband price (% GNI pc)

**Oracle:** 0.9 (2025, T1, level 5) — ITU DataHub — ICT price baskets, data-only mobile broadband

*Lower-is-better, and the ITU price baskets come in several flavours (data-only, mobile voice-and-data low/high). Tests whether the vendor picks the basket the construct names rather than the first percentage it meets, and whether it handles an inverted direction without inverting the level.*

| Entrant | Outcome | Value | Tier | Citation |
|---|---|---|---|---|
| `anthropic/claude-opus-5` | **abstained** (ratification hold) | — | T1 | **no citation asserted** |
| `openai/gpt-5.6-sol` | **abstained** (ratification hold) | — | T1 | **no citation asserted** |
| `openai/gpt-5.6-terra` | **nothing found** | — | — | — |
| `openai/gpt-5.6-luna` | **abstained** (ratification hold) | — | — | — |
| `gemini/gemini-3.1-pro-preview` | **nothing found** | — | — | — |

### K7 · Egypt 3.1 — UN E-Government Development Index

**Oracle:** 0.6699 (2024, T1, level 4) — UN E-Government Knowledgebase — Egypt country profile

*An index rather than a statistic, published as a country profile behind a database interface. Tests retrieval of a value that is not in any bulk series, and whether the vendor reports the EGDI itself rather than one of its three sub-indices.*

| Entrant | Outcome | Value | Tier | Citation |
|---|---|---|---|---|
| `anthropic/claude-opus-5` | recorded · value ✓, level ✓ | 0.6699 | T1 | resolves |
| `openai/gpt-5.6-sol` | recorded · value ✓, level ✓ | 0.6699 | T1 | resolves |
| `openai/gpt-5.6-terra` | recorded · value ✓, level ✓ | 0.6699 | T1 | resolves |
| `openai/gpt-5.6-luna` | recorded · value ✓, level ✓ | 0.6699 | T5 (domain says T1) | resolves |
| `gemini/gemini-3.1-pro-preview` | recorded · value ✓, level ✓ | 0.6699 | T1 | resolves |

### K8 · Nigeria 4.7 — Digital ID coverage (%)

**Oracle:** 79.08 (2024, T1, level 4) — World Bank Identification for Development (ID4D) dataset

*A prerequisite sitting just under a threshold: 79.08 is level 4, and 80 would be level 5. Tests whether a vendor that finds a rounded 'about 80%' in a press summary reports the rounding or the measurement.*

| Entrant | Outcome | Value | Tier | Citation |
|---|---|---|---|---|
| `anthropic/claude-opus-5` | **abstained** (ratification hold) | — | — | **no citation asserted** |
| `openai/gpt-5.6-sol` | **abstained** (ratification hold) | — | T1 | **no citation asserted** |
| `openai/gpt-5.6-terra` | **abstained** (ratification hold) | — | — | **no citation asserted** |
| `openai/gpt-5.6-luna` | **abstained** (ratification hold) | — | T1 | **no citation asserted** |
| `gemini/gemini-3.1-pro-preview` | recorded · value ✗, level ✗ | 121191781 | T1 | resolves |

### K9 · Nigeria 2.7 — Rural smartphone ownership (%)

**Oracle:** 28.9 (2024, T1, level 2) — NBS / World Bank LSMS, Nigeria General Household Survey

*The hardest known cell. The answer is in a household survey published by a national statistical office, not in any international database, and the national smartphone figure is far higher than the rural one. Tests whether the vendor will leave the databases it knows and whether it holds the rural construct when only a national number is easy to find.*

| Entrant | Outcome | Value | Tier | Citation |
|---|---|---|---|---|
| `anthropic/claude-opus-5` | **abstained** (ratification hold) | — | — | — |
| `openai/gpt-5.6-sol` | **abstained** (ratification hold) | — | T1 | **no citation asserted** |
| `openai/gpt-5.6-terra` | **abstained** (ratification hold) | — | — | **no citation asserted** |
| `openai/gpt-5.6-luna` | **abstained** (ratification hold) | — | T1 | **no citation asserted** |
| `gemini/gemini-3.1-pro-preview` | **nothing found** | — | — | — |

### K10 · Nigeria 8.4 — Mobile money account (%)

**Oracle:** 32.8 (2024, T1, level 3) — World Bank Global Findex Database 2025

*Findex is a wave, not an annual series, and its country pages report several account measures. Tests whether the vendor distinguishes a mobile money account from a financial institution account and gets the wave year right.*

| Entrant | Outcome | Value | Tier | Citation |
|---|---|---|---|---|
| `anthropic/claude-opus-5` | **abstained** (ratification hold) | — | — | **no citation asserted** |
| `openai/gpt-5.6-sol` | **abstained** (ratification hold) | — | T1 | **no citation asserted** |
| `openai/gpt-5.6-terra` | **abstained** (ratification hold) | — | — | **no citation asserted** |
| `openai/gpt-5.6-luna` | **abstained** (ratification hold) | — | T1 | **no citation asserted** |
| `gemini/gemini-3.1-pro-preview` | recorded · value ✗, level ✗ | 47.1 | T1 | resolves |

### N1 · Egypt 2.1 — Rural mobile broadband coverage (3G/4G)

**Nothing exists to find.** No rural-specific mobile broadband coverage figure is published for Egypt by ITU, NTRA or MCIT. The only admissible published figure is NATIONAL population coverage at least 3G, 99.8% (ITU DataHub, 2025), which measures a different construct and is context, not an answer.

*The trap:* Recording the national 99.8% against this row scores a universal rural prerequisite at level 5 on evidence that does not measure rural anything.

*The single sharpest cell in the audition. This exact error passed a hand assessor gate AND an initial peer review in the verified Egypt assessment before an audit caught it; it is defect #1 in the issues log. A vendor that reports the national figure here reproduces a defect that two humans missed. The correct outcome is found=false, or an abstention naming the construct difference, with the 99.8% offered only as context.*

| Entrant | Outcome | Value | Tier | Citation |
|---|---|---|---|---|
| `anthropic/claude-opus-5` | **abstained** (ratification hold) | — | — | — |
| `openai/gpt-5.6-sol` | **abstained** (ratification hold) | — | — | — |
| `openai/gpt-5.6-terra` | **nothing found** | — | — | — |
| `openai/gpt-5.6-luna` | **abstained** (ratification hold) | — | — | — |
| `gemini/gemini-3.1-pro-preview` | **nothing found** | — | — | — |

### N2 · Egypt 6.3 — Business Ready (B-READY)

**Nothing exists to find.** Egypt is not covered by B-READY. It appears in neither the 2024 edition (51 economies) nor the 2025 interim edition (101 economies); it is listed only as a forthcoming economy in a later cohort. No B-READY score exists for Egypt to report.

*The trap:* B-READY is the successor to Doing Business, which did cover Egypt for two decades. A vendor reaching for institutional memory has a large, well-indexed body of Doing Business scores to convert into a plausible B-READY number.

*Tests absence-by-non-coverage rather than absence-by-non-measurement: the database is real, prominent and well documented, and this country is simply not in it. The predecessor's scores are everywhere, which makes a confident wrong answer easy to assemble.*

| Entrant | Outcome | Value | Tier | Citation |
|---|---|---|---|---|
| `anthropic/claude-opus-5` | **abstained** (ratification hold) | — | — | **no citation asserted** |
| `openai/gpt-5.6-sol` | **abstained** (ratification hold) | — | T1 | **no citation asserted** |
| `openai/gpt-5.6-terra` | **abstained** (ratification hold) | — | — | — |
| `openai/gpt-5.6-luna` | **abstained** (ratification hold) | — | — | — |
| `gemini/gemini-3.1-pro-preview` | **nothing found** | — | — | — |

### N3 · Nigeria 8.11 — Services in local languages (%)

**Nothing exists to find.** No statistic on the language coverage of digital agriculture services in Nigeria exists at any tier. The verified assessment searched ITU, NBS and Findex (T1, nothing), located no T2 literature, and found nothing in FMAFS or NAERLS material. Individual services document their own language support; no one has measured the share.

*The trap:* Abundant qualitative material discusses Hausa, Yoruba and Igbo language support in specific agricultural advisory services, from which a share is easy to manufacture and impossible to source.

*Tests the most common shape of a real data gap: the topic is genuinely well discussed, so a vendor can assemble a confident-sounding percentage out of narrative that contains no measurement at all. The correct outcome is found=false with the qualitative material named as context, never as a value.*

| Entrant | Outcome | Value | Tier | Citation |
|---|---|---|---|---|
| `anthropic/claude-opus-5` | **abstained** (ratification hold) | — | — | — |
| `openai/gpt-5.6-sol` | **abstained** (ratification hold) | — | — | — |
| `openai/gpt-5.6-terra` | **abstained** (ratification hold) | — | — | **no citation asserted** |
| `openai/gpt-5.6-luna` | **abstained** (ratification hold) | — | — | — |
| `gemini/gemini-3.1-pro-preview` | **nothing found** | — | — | — |

## Discovery — whose queries found admissible pages

Measured before the shared pack was built: every retrieved page carries the name of whoever's query surfaced it. Perplexity appears here and nowhere else, which is decision C6 working as designed — a discovery peer whose citations are re-fetched and quote-verified, and whose prose is never a source of record.

| Proposer | Pages surfaced | Of those, T1–T3 | Cells where it surfaced an admissible page |
|---|---|---|---|
| `anthropic/claude-opus-5` | 64 | 46 | 12/13 |
| `openai/gpt-5.6-luna` | 56 | 47 | 12/13 |
| `gemini/gemini-3.1-pro-preview` | 55 | 41 | 12/13 |
| `openai/gpt-5.6-terra` | 53 | 46 | 12/13 |
| `openai/gpt-5.6-sol` | 51 | 38 | 11/13 |
| `perplexity/discovery` | 29 | 25 | 10/13 |

## Spend

| Vendor | Cost |
|---|---|
| openai | $3.55 |
| anthropic | $2.16 |
| gemini | $1.80 |
| exa | $0.97 |
| perplexity | $0.16 |
| jina | $0.13 |
| **total** | **$8.77** |

Dollars are derived from exactly recorded usage counts using `prices.json`. The Anthropic rates there are the published ones; the OpenAI, Gemini and Perplexity rates are placeholders set at Opus-tier so the counter cannot read low. Correcting a price in that file re-derives every figure above without re-running anything.

