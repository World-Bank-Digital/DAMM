# Shadow run against the verified assessment — Egypt

`EGY_shadow_g2` compared row by row with `EGY_v17`, the verified assessment. The verified assessment was not read by the pipeline and has not been modified by this comparison.


## The five questions

**1. How many of the 57 rows land on the same level?** **29 of 57** (51%). Of the 32 rows where both assessments set a level at all, 20 agree exactly (62%) and 27 are within one level (84%).

**2. Do all twelve prerequisites match?** **8 of 12** carry the same status. The divergences are listed below; each one moves at least one column of the readiness matrix.

**3. Gaps.** The verified assessment records **5** (2.1, 5.12, 6.3, 6.13, 8.17). The shadow run records **14**, of which it found **5** of the recorded ones and raised **9** the verified assessment does not carry. It also set **10** ratification holds against the verified assessment's 5.

**4. The rural/national trap at 2.1.** **Avoided.** The shadow run recorded 2.1 as `Gap` with no level; gate verdict `gap`. It did not record a national coverage figure against an indicator naming rural coverage — the error that passed an assessor gate and an initial peer review before an audit caught it.
  
  This country's verified assessment records 2.1 as `Gap` at no level, so the two agree.
  
  On the construct: *The indicator names RURAL mobile broadband coverage. The best available Egypt-specific evidence in the retrieved pages is NATIONAL: ITU's Digital Development Dashboard for Egypt reports population covered by at least a 3G mobile network (2022) = 100% and at least a 4G mobile network (2022) = 98%. These are total-population figures with no urban/rural split. The only rural-disaggregated Egyptian f…*
  
  Recorded value: `DATA GAP — 1) ITU Statistics landing page — confirms ITU publishes population covered by mobile-broadband network 'total and by urban/rural area', but only as global/regional/development-group aggregates, not per-country. 2) ITU DataHub home and About pages — confirm the World Telecommunication Ind…`


**5. Cost and time.** **$6.62** across 629 vendor calls in 15 minutes, against a $500 country ceiling — 1.3% of it, across 2 passes (EGY_shadow, EGY_shadow_g2). By vendor: openai $3.92, perplexity $1.42, exa $0.74, jina $0.37, anthropic $0.17.


## Prerequisites — the twelve rows that gate the matrix

| id | prerequisite | verified | shadow | levels | why the shadow run differs |
|---|---|---|---|---|---|
| 2.1 | Rural mobile broadband coverage (3 | Unverified | Unverified | no level → no level |  |
| 2.9 | Rural electricity access (%) | Present | Present | L5 → L5 |  |
| 3.3 | National farmer registry | Present | **Unverified** | L4 → no level | The indicator names a registry of FARMERS (individuals). The only national instrument evidenced in the retrie… |
| 3.11 | Agricultural data interoperability | Absent | Absent | L1 → L1 |  |
| 4.1 | Data protection/privacy law | Present | Present | L3 → L3 |  |
| 4.5 | Agricultural data governance frame | Absent | Absent | L1 → L1 |  |
| 4.7 | Digital ID coverage (%) | Present | Present | L5 → L5 |  |
| 4.9 | Inter-ministerial coordination mec | Present | Present | L4 → L3 |  |
| 5.5 | Digital extension capability | Present | Present | L4 → L3 |  |
| 5.7 | MoAg digital/AI unit | Unverified | **Present** | no level → L3 | A Digital Transformation Unit (AG-DTU) was ordered established inside Egypt's Ministry of Agriculture and Lan… |
| 6.14 | Agri-fintech rails for smallholder | Present | **Unverified** | L4 → no level | The indicator names AGRI-FINTECH RAILS for SMALLHOLDERS. The quoted T3 page sits under a heading covering 'NG… |
| 7.12 | Responsible-AI safeguards (consent | Absent | **Present** | L1 → L3 | Egypt adopted a cross-sector Egyptian Charter for Responsible AI, launched by the National Council for Artifi… |

## Readiness matrix

| use case | verified | shadow | |
|---|---|---|---|
| ADV | Blocked | Unverified | **differs** |
| SMF | Blocked | Unverified | **differs** |
| MKT | Unverified | Unverified | match |
| SCM | Unverified | Unverified | match |
| FIN | Blocked | Unverified | **differs** |
| AGI | Blocked | Blocked | match |

## Pillars

| pillar | verified mean (band) | rated/held | shadow mean (band) | rated/held |
|---|---|---|---|---|
| A1 | 3.0 (Established) | 8/2 | 3.6 (Advanced) | 5/2 |
| C1 | 3.8 (Advanced) | 5/0 | 4.0 (Advanced) | 4/0 |
| C2 | 2.88 (Established) | 8/0 | 2.8 (Established) | 5/3 |
| C3 | 3.25 (Established) | 8/0 | 3.29 (Established) | 7/1 |
| C4 | 3.33 (Established) | 3/3 | 3.0 (Established) | 3/1 |
| E1 | 3.11 (Established) | 9/0 | 2.33 (Emerging) | 6/3 |
| O1 | 2.67 (Established) | 6/0 | 2.0 (Emerging) | 3/0 |

## Which direction the divergences run

This is the part to read first. A shadow run that withholds a level where the verified assessment set one costs coverage; a shadow run that sets a level *higher* than the verified assessment is claiming readiness the evidence may not carry, and that is the failure that matters.

- **3 rows read higher** than the verified assessment.
  - **2.11 Device financing/subsidy schemes** — L1 to L3. Egypt's Ministry of Communications and Information Technology operates ProGIG, a joint initiative of the National Telecommunication Institute and Nasser Social Bank offering soft loans of up to EGP 6…
  - **3.8 National soil map/database** — L1 to L3. The indicator names a 'National soil map/database'. The best available evidence describes (a) national digital soil and terrain data of Egypt produced by NARSS with FAO/European Soil Bureau, and (b) …
  - **7.12 Responsible-AI safeguards (consent, rights)** — L1 to L3. Egypt adopted a cross-sector Egyptian Charter for Responsible AI, launched by the National Council for Artificial Intelligence in April 2023, built on five values (Human-Centeredness, Transparency an…
- **9 rows read lower.** 2.5 (L5→L4), 3.6 (L4→L3), 4.6 (L4→L3), 4.9 (L4→L3), 5.5 (L4→L3), 6.9 (L4→L1), 3.9 (L4→L3), 3.10 (L4→L3), 8.12 (L3→L1)
- **15 rows withheld a level** the verified assessment set: 1.5, 1.6, 1.7, 2.7, 3.3, 3.5, 3.7, 4.4, 5.8, 6.4, 6.12, 6.14, 8.4, 8.9, 8.11.
- **1 row set a level** the verified assessment withheld: 5.7.

The asymmetry between the last two is the abstention threshold, stated as a number. It is the figure to tune, and tuning it in either direction moves the first bullet — which is the one that decides whether a machine-set readiness matrix can be trusted.


## Where the shadow run withheld a level

Each gate below is a design decision doing its job. A row that reaches a gate keeps its evidence; what it loses is the level, and with it its place in every mean.

| gate | rows |
|---|---|
| construct (hold) | 10 |
| tier (hold) | 3 |

## Independent corroboration

12 rows are also covered by a machine-fetchable T1 series, fetched separately and never substituted for the research lane's own answer. **7 of 12** research values agree with the independent series within 2%.


## Every row

| id | indicator | verified | shadow | | note |
|---|---|---|---|---|---|
| 1.1 | Agriculture value added per worker ( | Measured L4 | Measured L4 | match |  |
| 1.2 | Cereal yield (kg/ha) | Measured L5 | Measured L5 | match |  |
| 1.3 | Employment in agriculture (%) | Measured L3 | Measured L3 | match |  |
| 1.4 | Food production index (2014-16=100) | Measured L3 | Measured L3 | match |  |
| 1.5 | Post-harvest loss rate (%) | Documented L4 | Documented no level | **differs** | The indicator name asserts a single all-crop NATIONAL post-harvest loss rate for Egypt. No such fig… |
| 1.6 | Smallholder access to formal markets | Documented L1 | Gap no level | **differs** | Worked through the ten supplied pages in order. Sources 1, 2, 3 and 4 (IFAD, T1): the 2017 CSPE, th… |
| 1.7 | Agricultural credit access (% farmer | Documented L1 | Gap no level | **differs** | 1) FAO Statistics highlight 'Credit to agriculture. Global and regional trends 2014-2023' — checked… |
| 1.8 | Farmers using climate-smart practice | Documented no level | Gap no level | match |  |
| 8.1 | Prevalence of undernourishment (%) | Measured L3 | Measured L3 | match |  |
| 8.5 | Women who own land (% holders) | Measured no level | Documented no level | match |  |
| 2.1 ⚑ | Rural mobile broadband coverage (3G/ | Gap no level | Gap no level | match |  |
| 2.4 | Individuals using the Internet (%) | Measured L4 | Measured L4 | match |  |
| 2.5 | Mobile broadband price (% GNI pc) | Measured L5 | Measured L4 | **differs** | 1.58 |
| 2.7 | Rural smartphone ownership (%) | Measured L4 | Gap no level | **differs** | 1) ITU DataHub Egypt page for household indicators with Location disaggregation — only 'Households … |
| 2.9 ⚑ | Rural electricity access (%) | Measured L5 | Measured L5 | match |  |
| 2.11 | Device financing/subsidy schemes | Documented L1 | Documented L3 | **differs** | Egypt's Ministry of Communications and Information Technology operates ProGIG, a joint initiative o… |
| 3.1 | UN E-Government Development Index | Measured L4 | Measured L4 | match |  |
| 3.3 ⚑ | National farmer registry | Documented L4 | Documented no level | **differs** | The indicator names a registry of FARMERS (individuals). The only national instrument evidenced in … |
| 3.4 | Digital land/plot registration | Documented L3 | Documented L3 | match |  |
| 3.5 | Open agricultural data (machine-read | Documented L2 | Documented no level | **differs** | The indicator names OPEN + MACHINE-READABLE + AI-READY AGRICULTURAL data. The strongest artifact fo… |
| 3.6 | Weather/climate data infrastructure | Documented L4 | Documented L3 | **differs** | The Egyptian Meteorological Authority operates 28 synoptic stations (all shared on the WMO Global T… |
| 3.7 | Satellite/EO data integration | Documented L4 | Documented no level | **differs** | The indicator name, 'Satellite/EO data integration', fixes neither the object (integration into wha… |
| 3.8 | National soil map/database | Documented L1 | Documented L3 | **differs** | The indicator names a 'National soil map/database'. The best available evidence describes (a) natio… |
| 3.11 ⚑ | Agricultural data interoperability s | Documented L1 | Documented L1 | match |  |
| 4.1 ⚑ | Data protection/privacy law | Documented L3 | Documented L3 | match |  |
| 4.2 | Cybersecurity framework (ITU GCI) | Measured L5 | Measured L5 | match |  |
| 4.3 | Government AI Readiness Index | Measured L3 | Measured L3 | match |  |
| 4.4 | National digital agriculture strateg | Documented L1 | Documented no level | **differs** | The indicator names a 'National digital agriculture strategy'. The best evidence retrieved is for a… |
| 4.5 ⚑ | Agricultural data governance framewo | Documented L1 | Documented L1 | match |  |
| 4.6 | National AI strategy with agricultur | Documented L4 | Documented L3 | **differs** | Egypt's National AI Strategy contains a dedicated agriculture component: Section 7.1 'Agriculture, … |
| 4.7 ⚑ | Digital ID coverage (%) | Measured L5 | Measured L5 | match |  |
| 4.9 ⚑ | Inter-ministerial coordination mecha | Documented L4 | Documented L3 | **differs** | Under the guidance of the Inter-Ministerial Steering Committee, UELDP enhanced Local economic devel… |
| 5.2 | Adult literacy rate (%) | Measured L3 | Measured L3 | match |  |
| 5.3 | Tertiary STEM enrollment (% gross) | Measured no level | Gap no level | match |  |
| 5.4 | Digital literacy among farmers (%) | Documented no level | Gap no level | match |  |
| 5.5 ⚑ | Digital extension capability | Documented L4 | Documented L3 | **differs** | In July 2019 FAO and Egypt's Ministry of Agriculture and Land Reclamation launched a digital model … |
| 5.7 ⚑ | MoAg digital/AI unit | Documented no level | Documented L3 | **differs** | A Digital Transformation Unit (AG-DTU) was ordered established inside Egypt's Ministry of Agricultu… |
| 5.8 | Agtech/data-science training pipelin | Documented L3 | Judged no level | **differs** | the only source is T5 news, vendor or market material, which carries existence facts but never a st… |
| 5.12 | Gender balance in digital-ag workfor | Gap no level | Gap no level | match |  |
| 6.1 | Global Innovation Index | Measured L1 | Documented L1 | match |  |
| 6.3 | Business Ready (B-READY) | Gap no level | Gap no level | match |  |
| 6.4 | Agtech venture ecosystem | Documented L3 | Judged no level | **differs** | the only source is T5 news, vendor or market material, which carries existence facts but never a st… |
| 6.9 | Public-private partnerships in digit | Documented L4 | Documented L1 | **differs** | Across the pages retrieved for Egypt I found digital-agriculture collaborations that are public-pub… |
| 6.12 | Digital public goods adopted | Documented L4 | Judged no level | **differs** | the only source is T5 news, vendor or market material, which carries existence facts but never a st… |
| 6.13 | SME/agribusiness adoption of digital | Gap no level | Gap no level | match |  |
| 6.14 ⚑ | Agri-fintech rails for smallholders | Documented L4 | Documented no level | **differs** | The indicator names AGRI-FINTECH RAILS for SMALLHOLDERS. The quoted T3 page sits under a heading co… |
| 3.9 | Digital advisory platforms at scale | Documented L4 | Documented L3 | **differs** | Digital agricultural advisory apps, websites, call centers and SMS platforms (e.g. Hodhod, Mahsooly… |
| 3.10 | Agricultural e-commerce platforms | Documented L4 | Documented L3 | **differs** | Farmer-facing agricultural e-commerce/online marketplace platforms are operating in Egypt, includin… |
| 7.2 | AI-enabled agricultural solutions de | Documented L3 | Documented L3 | match |  |
| 7.12 ⚑ | Responsible-AI safeguards (consent,  | Documented L1 | Documented L3 | **differs** | Egypt adopted a cross-sector Egyptian Charter for Responsible AI, launched by the National Council … |
| 8.2 | Account ownership, female (%) | Measured L3 | Measured L3 | match |  |
| 8.4 | Mobile money account (%) | Measured L2 | Gap no level | **differs** | 1) Checked Source 1 (data.worldbank.org, Egypt) first as the canonical T1 route — found only FX.OWN… |
| 8.6 | Gender gap in phone ownership (pp) | Measured L2 | Documented L2 | match |  |
| 8.9 | Smallholders reached by digital serv | Documented L1 | Gap no level | **differs** | Reviewed all ten supplied pages in order of likely relevance to a national smallholder reach figure… |
| 8.11 | Services in local languages (%) | Documented L5 | Gap no level | **differs** | 1) Checked MCIT press release 'ICT Sector Achievements in 2025' (T3) — the most granular Egyptian g… |
| 8.12 | Documented impact evidence (yield/in | Documented L3 | Documented L1 | **differs** | Across the retrieved Egypt evidence base — IFAD's three country strategy and programme evaluations … |
| 8.17 | Climate advisory reach (%) | Gap no level | Gap no level | match |  |

⚑ marks a prerequisite.


## Reading this

Divergence here is the expected result. The verified assessments came from sustained human-directed searching under the full tiered protocol — Nigeria went from 21 recorded gaps to 4 that way — and this pass runs once, on a budget, without the Gate 2 refutation round that found four of those gap refutations. More gaps and more holds are the honest output of a first automated pass, not a regression.

The number to act on is the **abstention rate**: 10 holds and 14 gaps against the verified 5 and 5. Too loose and everything reads Ready; too tight and everything reads Unverified. These figures are what that threshold should be tuned against, and they should be kept — when automated Gate 2 arrives, re-running this comparison is what tells you whether it earns its 15% of the budget.

