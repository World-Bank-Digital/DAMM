# Shadow run against the verified assessment — Nigeria

`NGA_shadow_g2` compared row by row with `NGA_v17`, the verified assessment. The verified assessment was not read by the pipeline and has not been modified by this comparison.


## The five questions

**1. How many of the 57 rows land on the same level?** **30 of 57** (53%). Of the 27 rows where both assessments set a level at all, 20 agree exactly (74%) and 25 are within one level (93%).

**2. Do all twelve prerequisites match?** **5 of 12** carry the same status. The divergences are listed below; each one moves at least one column of the readiness matrix.

**3. Gaps.** The verified assessment records **4** (5.12, 6.3, 8.11, 8.17). The shadow run records **22**, of which it found **4** of the recorded ones and raised **18** the verified assessment does not carry. It also set **7** ratification holds against the verified assessment's 7.

**4. The rural/national trap at 2.1.** **Avoided.** The shadow run recorded 2.1 as `Gap` with no level; gate verdict `gap`. It did not record a national coverage figure against an indicator naming rural coverage — the error that passed an assessor gate and an initial peer review before an audit caught it.
  
  This country's verified assessment records 2.1 as `Documented` at L3 on a T4 source, so the two differ — avoiding the trap and matching the verified conclusion are separate questions.
  
  **The verified level here could not have been reproduced at any depth of searching.** It rests on a T4 source, and decision C4 requires T1–T3 quote-verified evidence for a prerequisite. The bar would have withheld this level even had the pipeline found the same document. That is a fact about the rule rather than about the run, and it is a genuine question for the §13 rulings: either the bar is right and this row should read Unverified, or the bar is too high for an indicator whose only published estimate is modelled.
  
  On the construct: *The indicator names RURAL mobile broadband coverage. The best T1 evidence in the supplied pages is national: ITU's Nigeria dashboard reports population covered by at least a 3G mobile network (2022) at 87% and population covered by at least a 4G mobile network (2022) at 81%, plus mobile-cellular network coverage of 94%. These are whole-population figures with no urban/rural split, so they cannot …*
  
  Recorded value: `DATA GAP — 1) ITU Digital Development Dashboard for Nigeria (ddd_NGA.pdf, T1) — found national coverage: 94% mobile-cellular, 87% at-least-3G, 81% at-least-4G (2022); the only rural-tagged row is households with Internet access at home, rural (2017) 2%, a different construct. No rural coverage spli…`


**5. Cost and time.** **$21.47** across 1616 vendor calls in 37 minutes, against a $500 country ceiling — 4.3% of it, across 2 passes (NGA_shadow, NGA_shadow_g2). By vendor: anthropic $11.39, openai $3.70, perplexity $3.54, exa $1.90, jina $0.95.


## Prerequisites — the twelve rows that gate the matrix

| id | prerequisite | verified | shadow | levels | why the shadow run differs |
|---|---|---|---|---|---|
| 2.1 | Rural mobile broadband coverage (3 | Present | **Unverified** | L3 → no level | 1) ITU Digital Development Dashboard for Nigeria (ddd_NGA.pdf, T1) — found national coverage: 94% mobile-cell… |
| 2.9 | Rural electricity access (%) | Present (narrow) | Present (narrow) | L2 → L2 |  |
| 3.3 | National farmer registry | Present (narrow) | Present (narrow) | L2 → L2 |  |
| 3.11 | Agricultural data interoperability | Absent | **Unverified** | L1 → no level | Order of inspection: (1) NITDA 'DATA INTEROPERABILITY STANDARDS, 2016' PDF — read preliminaries, arrangement … |
| 4.1 | Data protection/privacy law | Present | Present | L4 → L3 |  |
| 4.5 | Agricultural data governance frame | Absent | **Unverified** | L1 → no level | 1) FAO Global Strategy to Improve Agricultural and Rural Statistics country page for Nigeria (T1) — checked f… |
| 4.7 | Digital ID coverage (%) | Present | **Unverified** | L4 → no level | Started with ID4D as the canonical publisher: id4d.worldbank.org/global-dataset (T1) — describes the 2025 dat… |
| 4.9 | Inter-ministerial coordination mec | Absent | **Present** | L1 → L3 | The National Authority organizes meetings of the Inter-Ministerial Committee on Chemical and Biological Weapo… |
| 5.5 | Digital extension capability | Present | Present | L3 → L3 |  |
| 5.7 | MoAg digital/AI unit | Absent | **Unverified** | L1 → no level | 1) Checked the two Nigeria government-domain sources first, as the only T3 candidates that could carry an org… |
| 6.14 | Agri-fintech rails for smallholder | Present | **Unverified** | L3 → no level | The ABP is explicitly and exclusively addressed to smallholders ('Create an Ecosystem to link out-growers (Sm… |
| 7.12 | Responsible-AI safeguards (consent | Present | Present | L3 → L3 |  |

## Readiness matrix

| use case | verified | shadow | |
|---|---|---|---|
| ADV | Partial | Unverified | **differs** |
| SMF | Partial | Unverified | **differs** |
| MKT | Partial | Unverified | **differs** |
| SCM | Partial | Unverified | **differs** |
| FIN | Partial | Unverified | **differs** |
| AGI | Blocked | Unverified | **differs** |

## Pillars

| pillar | verified mean (band) | rated/held | shadow mean (band) | rated/held |
|---|---|---|---|---|
| A1 | 2.25 (Emerging) | 8/2 | 2.33 (Emerging) | 6/0 |
| C1 | 2.83 (Established) | 6/0 | 3.0 (Established) | 3/1 |
| C2 | 2.57 (Emerging) | 7/1 | 2.8 (Established) | 5/2 |
| C3 | 2.88 (Established) | 8/0 | 2.75 (Established) | 4/0 |
| C4 | 2.5 (Emerging) | 4/2 | 3.0 (Established) | 2/1 |
| E1 | 2.56 (Emerging) | 9/1 | 3.0 (Established) | 6/3 |
| O1 | 3.25 (Established) | 4/1 | 3.5 (Advanced) | 2/0 |

## Which direction the divergences run

This is the part to read first. A shadow run that withholds a level where the verified assessment set one costs coverage; a shadow run that sets a level *higher* than the verified assessment is claiming readiness the evidence may not carry, and that is the failure that matters.

- **4 rows read higher** than the verified assessment.
  - **4.9 Inter-ministerial coordination mechanism** — L1 to L3. The National Authority organizes meetings of the Inter-Ministerial Committee on Chemical and Biological Weapons Conventions quarterly or bi-annually, and its membership includes the Federal Ministry …
  - **6.4 Agtech venture ecosystem** — L3 to L4. Nigeria has an operating agritech venture ecosystem of digital solution providers for smallholder farmers, supported by incubators, accelerators, angel investors and donors, but only a handful of sta…
  - **7.2 AI-enabled agricultural solutions deployed** — L2 to L3. FAO's Science, Technology and Innovation Portal records the AKILIMO Nigeria Integrated Digital Agronomic Solution — classified as an artificial intelligence (AI) digital technology — as adopted in Ni…
  - **8.12 Documented impact evidence (yield/income)** — L3 to L4. A randomized controlled trial of the RiceAdvice digital personalized-extension app in Nigeria found that farm households receiving personalized advice increased their yield by 7% and their profit by …
- **3 rows read lower.** 1.5 (L3→L1), 3.6 (L4→L3), 4.1 (L4→L3)
- **19 rows withheld a level** the verified assessment set: 1.1, 1.6, 1.7, 2.1, 2.7, 2.11, 3.4, 3.11, 4.2, 4.3, 4.5, 4.7, 5.7, 5.8, 6.9, 6.12, 6.14, 8.4, 8.6.
- **1 row set a level** the verified assessment withheld: 8.5.

The asymmetry between the last two is the abstention threshold, stated as a number. It is the figure to tune, and tuning it in either direction moves the first bullet — which is the one that decides whether a machine-set readiness matrix can be trusted.


## Where the shadow run withheld a level

Each gate below is a design decision doing its job. A row that reaches a gate keeps its evidence; what it loses is the level, and with it its place in every mean.

| gate | rows |
|---|---|
| construct (hold) | 5 |
| tier (hold) | 1 |
| coherence (hold) | 1 |

## Independent corroboration

11 rows are also covered by a machine-fetchable T1 series, fetched separately and never substituted for the research lane's own answer. **7 of 11** research values agree with the independent series within 2%.


## Every row

| id | indicator | verified | shadow | | note |
|---|---|---|---|---|---|
| 1.1 | Agriculture value added per worker ( | Measured L3 | Gap no level | **differs** | 1) data.worldbank.org/indicator/NV.AGR.EMPL.KD (T1) — indicator landing page, no country values in … |
| 1.2 | Cereal yield (kg/ha) | Measured L2 | Measured L2 | match |  |
| 1.3 | Employment in agriculture (%) | Measured L2 | Measured L2 | match |  |
| 1.4 | Food production index (2014-16=100) | Measured L4 | Measured L4 | match |  |
| 1.5 | Post-harvest loss rate (%) | Documented L3 | Documented L1 | **differs** | Nigeria has no single published national all-crop post-harvest loss rate; a Nigerian government cou… |
| 1.6 | Smallholder access to formal markets | Documented L1 | Gap no level | **differs** | 1) Checked the two World Bank Microdata data-dictionary pages (sect11h_plantingw2 marketing module;… |
| 1.7 | Agricultural credit access (% farmer | Documented L1 | Gap no level | **differs** | Order of examination: (1) IFPRI NSSP Brief 25 'Review of small farmer access to agricultural credit… |
| 1.8 | Farmers using climate-smart practice | Documented no level | Gap no level | match |  |
| 8.1 | Prevalence of undernourishment (%) | Measured L2 | Measured L2 | match |  |
| 8.5 | Women who own land (% holders) | Documented no level | Documented L3 | **differs** | FAO's RuLIS country brief for Nigeria (General Household Survey 2018-2019) finds that among owners … |
| 2.1 ⚑ | Rural mobile broadband coverage (3G/ | Documented L3 | Gap no level | **differs** | 1) ITU Digital Development Dashboard for Nigeria (ddd_NGA.pdf, T1) — found national coverage: 94% m… |
| 2.4 | Individuals using the Internet (%) | Measured L3 | Measured L3 | match |  |
| 2.5 | Mobile broadband price (% GNI pc) | Measured L4 | Measured L4 | match |  |
| 2.7 | Rural smartphone ownership (%) | Measured L2 | Gap no level | **differs** | 1) NBS elibrary 2021 MICS key messages (T1) — has urban/rural mobile phone ownership (95%/81%) but … |
| 2.9 ⚑ | Rural electricity access (%) | Measured L2 | Measured L2 | match |  |
| 2.11 | Device financing/subsidy schemes | Documented L3 | Judged no level | **differs** | the only source is T5 news, vendor or market material, which carries existence facts but never a st… |
| 3.1 | UN E-Government Development Index | Measured L3 | Measured L3 | match |  |
| 3.3 ⚑ | National farmer registry | Documented L2 | Documented L2 | match |  |
| 3.4 | Digital land/plot registration | Documented L2 | Documented no level | **differs** | the row contradicts itself: the recorded rung and evidence fields derive level 3, while the row arg… |
| 3.5 | Open agricultural data (machine-read | Documented no level | Documented no level | match |  |
| 3.6 | Weather/climate data infrastructure | Documented L4 | Documented L3 | **differs** | 88 |
| 3.7 | Satellite/EO data integration | Documented L3 | Documented L3 | match |  |
| 3.8 | National soil map/database | Documented L3 | Documented L3 | match |  |
| 3.11 ⚑ | Agricultural data interoperability s | Documented L1 | Gap no level | **differs** | Order of inspection: (1) NITDA 'DATA INTEROPERABILITY STANDARDS, 2016' PDF — read preliminaries, ar… |
| 4.1 ⚑ | Data protection/privacy law | Documented L4 | Documented L3 | **differs** | Nigeria has a comprehensive data protection law, the Nigeria Data Protection Act (NDP Act) 2023, wh… |
| 4.2 | Cybersecurity framework (ITU GCI) | Measured L5 | Gap no level | **differs** | 1) ITU GCI 2024 e-publication (English and Chinese-interface renderings, Sources 1 and 5) — read fo… |
| 4.3 | Government AI Readiness Index | Measured L3 | Gap no level | **differs** | 1) Oxford Insights 2025 index page (primary publisher) - Nigeria appears only in the country-select… |
| 4.4 | National digital agriculture strateg | Documented L2 | Documented L2 | match |  |
| 4.5 ⚑ | Agricultural data governance framewo | Documented L1 | Gap no level | **differs** | 1) FAO Global Strategy to Improve Agricultural and Rural Statistics country page for Nigeria (T1) —… |
| 4.6 | National AI strategy with agricultur | Documented L3 | Documented L3 | match |  |
| 4.7 ⚑ | Digital ID coverage (%) | Measured L4 | Gap no level | **differs** | Started with ID4D as the canonical publisher: id4d.worldbank.org/global-dataset (T1) — describes th… |
| 4.9 ⚑ | Inter-ministerial coordination mecha | Documented L1 | Documented L3 | **differs** | The National Authority organizes meetings of the Inter-Ministerial Committee on Chemical and Biolog… |
| 5.2 | Adult literacy rate (%) | Measured L3 | Measured L3 | match |  |
| 5.3 | Tertiary STEM enrollment (% gross) | Measured no level | Gap no level | match |  |
| 5.4 | Digital literacy among farmers (%) | Documented no level | Gap no level | match |  |
| 5.5 ⚑ | Digital extension capability | Documented L3 | Documented L3 | match |  |
| 5.7 ⚑ | MoAg digital/AI unit | Documented L1 | Gap no level | **differs** | 1) Checked the two Nigeria government-domain sources first, as the only T3 candidates that could ca… |
| 5.8 | Agtech/data-science training pipelin | Documented L3 | Documented no level | **differs** | The indicator names an 'Agtech/data-science' pipeline. The evidence quoted (3MTT, and its DeepTech_… |
| 5.12 | Gender balance in digital-ag workfor | Gap no level | Gap no level | match |  |
| 6.1 | Global Innovation Index | Measured L1 | Documented L1 | match |  |
| 6.3 | Business Ready (B-READY) | Gap no level | Gap no level | match |  |
| 6.4 | Agtech venture ecosystem | Documented L3 | Documented L4 | **differs** | Nigeria has an operating agritech venture ecosystem of digital solution providers for smallholder f… |
| 6.9 | Public-private partnerships in digit | Documented L3 | Gap no level | **differs** | Order of examination: (1) NITDA Nigeria Digital Agriculture Strategy 2020-2030 draft (T3, nitda.gov… |
| 6.12 | Digital public goods adopted | Documented L1 | Documented no level | **differs** | The indicator name ("Digital public goods adopted") is ambiguous per the census note. The best avai… |
| 6.13 | SME/agribusiness adoption of digital | Documented no level | Documented no level | match |  |
| 6.14 ⚑ | Agri-fintech rails for smallholders | Documented L3 | Documented no level | **differs** | The ABP is explicitly and exclusively addressed to smallholders ('Create an Ecosystem to link out-g… |
| 3.9 | Digital advisory platforms at scale | Documented L4 | Documented L4 | match |  |
| 3.10 | Agricultural e-commerce platforms | Documented L3 | Documented L3 | match |  |
| 7.2 | AI-enabled agricultural solutions de | Judged L2 | Documented L3 | **differs** | FAO's Science, Technology and Innovation Portal records the AKILIMO Nigeria Integrated Digital Agro… |
| 7.12 ⚑ | Responsible-AI safeguards (consent,  | Documented L3 | Documented L3 | match |  |
| 8.2 | Account ownership, female (%) | Measured L3 | Measured L3 | match |  |
| 8.4 | Mobile money account (%) | Measured L3 | Gap no level | **differs** | Checked, in order: (1) WDI indicator page FX.OWN.TOTL.ZS — has Nigeria 2024 = 63.26 but the series … |
| 8.6 | Gender gap in phone ownership (pp) | Measured L4 | Gap no level | **differs** | 1) Checked the three World Bank Findex 2025 Nigeria microdata pages (catalog/7957 variable F1/V145 … |
| 8.9 | Smallholders reached by digital serv | Documented no level | Gap no level | match |  |
| 8.11 | Services in local languages (%) | Gap no level | Gap no level | match |  |
| 8.12 | Documented impact evidence (yield/in | Documented L3 | Documented L4 | **differs** | A randomized controlled trial of the RiceAdvice digital personalized-extension app in Nigeria found… |
| 8.17 | Climate advisory reach (%) | Gap no level | Gap no level | match |  |

⚑ marks a prerequisite.


## Reading this

Divergence here is the expected result. The verified assessments came from sustained human-directed searching under the full tiered protocol — Nigeria went from 21 recorded gaps to 4 that way — and this pass runs once, on a budget, without the Gate 2 refutation round that found four of those gap refutations. More gaps and more holds are the honest output of a first automated pass, not a regression.

The number to act on is the **abstention rate**: 7 holds and 22 gaps against the verified 7 and 4. Too loose and everything reads Ready; too tight and everything reads Unverified. These figures are what that threshold should be tuned against, and they should be kept — when automated Gate 2 arrives, re-running this comparison is what tells you whether it earns its 15% of the budget.

