# Calibrating the abstention threshold

Two automated runs, each compared against its own verified assessment. The design record names the abstention threshold as the highest-leverage parameter in the system — too loose and everything reads Ready, too tight and everything reads Unverified — and says it must be tuned against both countries before any new country runs. This is that comparison.


## The two runs side by side

| | Egypt | Nigeria |
|---|---|---|
| rows at the verified level (of 57) | 24 | 30 |
| prerequisites matching (of 12) | 5 | 5 |
| recorded gaps | 20 (verified: 5) | 22 (verified: 4) |
| ratification holds | 10 (verified: 5) | 7 (verified: 7) |
| levels withheld where the verified assessment set one | 21 | 19 |
| **rows read HIGHER than the verified assessment** | **2** | **4** |
| cost | $21.88 | $21.47 |

The row to read is the last but one. The pipeline's error is overwhelmingly in the direction of saying too little, not too much — which is the failure the design record chose when it made abstention a first-class answer.


## Is the abstention the pipeline, or the country?

**11 rows** withheld a level in BOTH countries. Those are the pipeline. Rows withheld in only one are that country's data environment.

| | rows | which |
|---|---|---|
| withheld in both | 11 | 1.6, 1.7, 2.7, 3.4, 3.11, 4.5, 4.7, 5.8, 6.9, 6.12, 6.14 |
| Egypt only | 10 | 1.5, 3.3, 3.5, 3.8, 4.4, 6.4, 7.2, 8.9, 8.11, 8.12 |
| Nigeria only | 8 | 1.1, 2.1, 2.11, 4.2, 4.3, 5.7, 8.4, 8.6 |

## The split that decides which lever to pull

Of the rows withheld in both countries, the ones the pipeline **never reached** need more retrieval, and no threshold change will rescue them. The ones it reached and **declined to level** are the threshold.

| | rows |
|---|---|
| not reached in both | 7 |
| declined in both | 3 |
| mixed | 1 |

**64%** of the rows both countries withheld were never reached at all. 
On this evidence the binding constraint is retrieval, not the abstention threshold — which is what the vendor audition also found, where every entrant abstained on the same four known-answer cells because the page carrying the answer was behind a JavaScript dashboard or inside a survey PDF. Loosening the threshold would not have produced those levels; it would only have produced levels with less behind them.


## Why each country declined, gate by gate

| country | declined: coherence | declined: construct | declined: tier | not reached |
|---|---|---|---|---|
| Egypt | 0 | 7 | 2 | 12 |
| Nigeria | 1 | 3 | 1 | 14 |

## Every row read higher than its verified assessment

The dangerous direction, in full, for both countries.

- **Egypt 2.11 Device financing/subsidy schemes** — verified L1, recorded L3. Egypt's Ministry of Communications and Information Technology operates ProGIG, a joint initiative of the National Telecommunication Institute and Nasser Social Bank offering soft loans of up to EGP 65,000 (with a 50% dis
- **Egypt 7.12 Responsible-AI safeguards (consent, rights)** — verified L1, recorded L3. Egypt adopted a cross-sector Egyptian Charter for Responsible AI, launched by the National Council for Artificial Intelligence in April 2023, built on five values (Human-Centeredness, Transparency and Explainability, Fai
- **Nigeria 4.9 Inter-ministerial coordination mechanism** — verified L1, recorded L3. The National Authority organizes meetings of the Inter-Ministerial Committee on Chemical and Biological Weapons Conventions quarterly or bi-annually, and its membership includes the Federal Ministry of Agriculture and Ru
- **Nigeria 6.4 Agtech venture ecosystem** — verified L3, recorded L4. Nigeria has an operating agritech venture ecosystem of digital solution providers for smallholder farmers, supported by incubators, accelerators, angel investors and donors, but only a handful of start-ups have scaled.
- **Nigeria 7.2 AI-enabled agricultural solutions deployed** — verified L2, recorded L3. FAO's Science, Technology and Innovation Portal records the AKILIMO Nigeria Integrated Digital Agronomic Solution — classified as an artificial intelligence (AI) digital technology — as adopted in Nigeria at the 'Livelih
- **Nigeria 8.12 Documented impact evidence (yield/income)** — verified L3, recorded L4. A randomized controlled trial of the RiceAdvice digital personalized-extension app in Nigeria found that farm households receiving personalized advice increased their yield by 7% and their profit by 10%.

## The cheapest coverage there is

Every run fetches a machine-readable T1 lane separately and reports it beside the research lane's own answer without ever substituting it — a measurement run that quietly swapped in an API figure would be measuring the API. The rows below are ones where the research lane recorded a gap while that independent T1 series had the figure all along. Each one is already visible on its row, which said so in its note; each is also a level available for the price of a decision.

| country | id | indicator | the T1 series had |
|---|---|---|---|
| Egypt | 5.3 | Tertiary STEM enrollment (% gross) | 38.04 (2025) — World Bank WDI SE.TER.ENRR |
| Nigeria | 1.1 | Agriculture value added per worker | 3494.89 (2025) — World Bank WDI NV.AGR.EMPL.KD |
| Nigeria | 5.3 | Tertiary STEM enrollment (% gross) | 9.74 (2011) — World Bank WDI SE.TER.ENRR |

**3 rows** across both countries. Whether the T1 lane should be allowed to fill a gap the research lane could not is a real design question and not one to settle silently: it trades a measurement of what the research lane can do for coverage a reader would rather have. It is recorded here as an open decision.


## Rows to fix by hand before the next country

Withheld in both countries and never reached: these are named sources behind interfaces the Exa/Jina substrate does not open. Each is a targeted retrieval job, not a tuning question, and fixing one fixes it for every country.

- **1.6 Smallholder access to formal markets (%)**
- **1.7 Agricultural credit access (% farmers)**
- **2.7 Rural smartphone ownership (%)**
- **3.11 Agricultural data interoperability standards**  ⚑ prerequisite
- **4.5 Agricultural data governance framework**  ⚑ prerequisite
- **4.7 Digital ID coverage (%)**  ⚑ prerequisite
- **6.9 Public-private partnerships in digital ag**

## What the second review changed, in both countries

| outcome | Egypt | Nigeria |
|---|---|---|
| filled | 3 | 2 |
| withdrawn | 0 | 0 |
| relevelled | 0 | 1 |
| adjusted | 2 | 1 |
| upheld | 33 | 32 |
| cost | $6.39 | $6.14 |
