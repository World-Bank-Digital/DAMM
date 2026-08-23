# Shadow run against the verified assessment — Egypt

`EGY_shadow` compared row by row with `EGY_v17`, the verified assessment. The verified assessment was not read by the pipeline and has not been modified by this comparison.


## The five questions

**1. How many of the 57 rows land on the same level?** **26 of 57** (46%). Of the 25 rows where both assessments set a level at all, 17 agree exactly (68%) and 22 are within one level (88%).

**2. Do all twelve prerequisites match?** **4 of 12** carry the same status. The divergences are listed below; each one moves at least one column of the readiness matrix.

**3. Gaps.** The verified assessment records **5** (2.1, 5.12, 6.13, 6.3, 8.17). The shadow run records **22**, of which it found **5** of the recorded ones and raised **17** the verified assessment does not carry. It also set **9** ratification holds against the verified assessment's 5.

**4. The 2.1 finding.** **Reproduced.** The shadow run recorded 2.1 as `Gap` at —, gate verdict `gap`. 
  
  On the construct: *The closest quantified evidence in the supplied pages is NATIONAL, not rural, and sits at T5: the USAID-affiliated digitaldevelopment.org Egypt page lists 'Population covered by 3G signal: 0.99' and 'Population covered by 4G signal: 0.61' (i.e. 99% and 61% of the total population), plus '3G Coverage: 99.00'. These are national population-coverage shares of the kind the assessment's indicator cens…*

  
  Recorded value: `DATA GAP — Order of inspection: (1) ITU DataHub 'About' page — confirmed ITU collects 'mobile population coverage (total, 3G, 4G and above)' from regulators, but the page is methodological and carries no Egypt value and no rural/urban split; dead end for a value. (2) ITU Facts and Figures 2025 land…`


**5. Cost and time.** **$15.14** across 1003 vendor calls in 23 minutes, against a $500 country ceiling — 3.0% of it. By vendor: anthropic $11.21, perplexity $2.16, exa $1.18, jina $0.59.


## Prerequisites — the twelve rows that gate the matrix

| id | prerequisite | verified | shadow | levels | why the shadow run differs |
|---|---|---|---|---|---|
| 2.1 | Rural mobile broadband coverage (3 | Unverified | Unverified | — → — |  |
| 2.9 | Rural electricity access (%) | Present | Present | L5 → L5 |  |
| 3.3 | National farmer registry | Present | **Unverified** | L4 → — |  |
| 3.11 | Agricultural data interoperability | Absent | **Unverified** | L1 → — |  |
| 4.1 | Data protection/privacy law | Present | Present | L3 → L3 |  |
| 4.5 | Agricultural data governance frame | Absent | **Unverified** | L1 → — |  |
| 4.7 | Digital ID coverage (%) | Present | **Unverified** | L5 → — |  |
| 4.9 | Inter-ministerial coordination mec | Present | **Unverified** | L4 → — |  |
| 5.5 | Digital extension capability | Present | Present | L4 → L3 |  |
| 5.7 | MoAg digital/AI unit | Unverified | **Present** | — → L3 |  |
| 6.14 | Agri-fintech rails for smallholder | Present | **Unverified** | L4 → — | The quoted CBE text names smallholder farmers specifically (a project titled "Transformin… |
| 7.12 | Responsible-AI safeguards (consent | Absent | **Present** | L1 → L3 |  |

## Readiness matrix

| use case | verified | shadow | |
|---|---|---|---|
| ADV | Unverified | Unverified | match |
| SMF | Unverified | Unverified | match |
| MKT | Unverified | Unverified | match |
| SCM | Unverified | Unverified | match |
| FIN | Unverified | Unverified | match |
| AGI | Blocked | Unverified | **differs** |

## Pillars

| pillar | verified mean (band) | rated/held | shadow mean (band) | rated/held |
|---|---|---|---|---|
| A1 | 3.0 (Established) | 8/2 | 3.6 (Advanced) | 5/2 |
| C1 | 3.8 (Advanced) | 5/0 | 4.0 (Advanced) | 4/0 |
| C2 | 2.88 (Established) | 8/0 | 3.33 (Established) | 3/2 |
| C3 | 3.25 (Established) | 8/0 | 3.5 (Advanced) | 4/1 |
| C4 | 3.33 (Established) | 3/3 | 3.0 (Established) | 3/0 |
| E1 | 3.11 (Established) | 9/0 | 2.5 (Emerging) | 4/4 |
| O1 | 2.67 (Established) | 6/0 | 2.0 (Emerging) | 3/0 |

## Where the shadow run withheld a level

Each gate below is a design decision doing its job. A row that reaches a gate keeps its evidence; what it loses is the level, and with it its place in every mean.

| gate | rows |
|---|---|
| construct (hold) | 4 |
| tier (hold) | 4 |
| coherence (hold) | 1 |

## Independent corroboration

11 rows are also covered by a machine-fetchable T1 series, fetched separately and never substituted for the research lane's own answer. **7 of 11** research values agree with the independent series within 2%.


## Every row

| id | indicator | verified | shadow | | note |
|---|---|---|---|---|---|
| 1.1 | Agriculture value added per worker ( | Measured L4 | Measured L4 | match |  |
| 1.2 | Cereal yield (kg/ha) | Measured L5 | Measured L5 | match |  |
| 1.3 | Employment in agriculture (%) | Measured L3 | Measured L3 | match |  |
| 1.4 | Food production index (2014-16=100) | Measured L3 | Measured L3 | match |  |
| 1.5 | Post-harvest loss rate (%) | Documented L4 | Documented — | **differs** | The indicator name asserts an all-crop NATIONAL POST-HARVEST loss rate. The bes… |
| 1.6 | Smallholder access to formal markets | Documented L1 | Gap — | **differs** | gap |
| 1.7 | Agricultural credit access (% farmer | Documented L1 | Gap — | **differs** | gap |
| 1.8 | Farmers using climate-smart practice | Documented — | Gap — | match |  |
| 8.1 | Prevalence of undernourishment (%) | Measured L3 | Measured L3 | match |  |
| 8.5 | Women who own land (% holders) | Measured — | Documented — | match |  |
| 2.1 ⚑ | Rural mobile broadband coverage (3G/ | Gap — | Gap — | match |  |
| 2.4 | Individuals using the Internet (%) | Measured L4 | Measured L4 | match |  |
| 2.5 | Mobile broadband price (% GNI pc) | Measured L5 | Measured L4 | **differs** | pass |
| 2.7 | Rural smartphone ownership (%) | Measured L4 | Gap — | **differs** | gap |
| 2.9 ⚑ | Rural electricity access (%) | Measured L5 | Measured L5 | match |  |
| 2.11 | Device financing/subsidy schemes | Documented L1 | Documented L3 | **differs** | pass |
| 3.1 | UN E-Government Development Index | Measured L4 | Measured L4 | match |  |
| 3.3 ⚑ | National farmer registry | Documented L4 | Gap — | **differs** | gap |
| 3.4 | Digital land/plot registration | Documented L3 | Documented L3 | match |  |
| 3.5 | Open agricultural data (machine-read | Documented L2 | Gap — | **differs** | gap |
| 3.6 | Weather/climate data infrastructure | Documented L4 | Documented — | **differs** | the row contradicts itself: the recorded rung and evidence fields derive level … |
| 3.7 | Satellite/EO data integration | Documented L4 | Judged — | **differs** | the only source is T5 news, vendor or market material, which carries existence … |
| 3.8 | National soil map/database | Documented L1 | Documented L3 | **differs** | pass |
| 3.11 ⚑ | Agricultural data interoperability s | Documented L1 | Gap — | **differs** | gap |
| 4.1 ⚑ | Data protection/privacy law | Documented L3 | Documented L3 | match |  |
| 4.2 | Cybersecurity framework (ITU GCI) | Measured L5 | Measured L5 | match |  |
| 4.3 | Government AI Readiness Index | Measured L3 | Measured L3 | match |  |
| 4.4 | National digital agriculture strateg | Documented L1 | Documented — | **differs** | The indicator names a 'National digital agriculture strategy'. No dedicated, st… |
| 4.5 ⚑ | Agricultural data governance framewo | Documented L1 | Gap — | **differs** | gap |
| 4.6 | National AI strategy with agricultur | Documented L4 | Documented L3 | **differs** | pass |
| 4.7 ⚑ | Digital ID coverage (%) | Measured L5 | Gap — | **differs** | gap |
| 4.9 ⚑ | Inter-ministerial coordination mecha | Documented L4 | Gap — | **differs** | gap |
| 5.2 | Adult literacy rate (%) | Measured L3 | Measured L3 | match |  |
| 5.3 | Tertiary STEM enrollment (% gross) | Measured — | Gap — | match |  |
| 5.4 | Digital literacy among farmers (%) | Documented — | Gap — | match |  |
| 5.5 ⚑ | Digital extension capability | Documented L4 | Documented L3 | **differs** | pass |
| 5.7 ⚑ | MoAg digital/AI unit | Documented — | Documented L3 | **differs** | pass |
| 5.8 | Agtech/data-science training pipelin | Documented L3 | Gap — | **differs** | gap |
| 5.12 | Gender balance in digital-ag workfor | Gap — | Gap — | match |  |
| 6.1 | Global Innovation Index | Measured L1 | Documented L1 | match |  |
| 6.3 | Business Ready (B-READY) | Gap — | Gap — | match |  |
| 6.4 | Agtech venture ecosystem | Documented L3 | Judged — | **differs** | the only source is T5 news, vendor or market material, which carries existence … |
| 6.9 | Public-private partnerships in digit | Documented L4 | Gap — | **differs** | gap |
| 6.12 | Digital public goods adopted | Documented L4 | Judged — | **differs** | the only source is T5 news, vendor or market material, which carries existence … |
| 6.13 | SME/agribusiness adoption of digital | Gap — | Gap — | match |  |
| 6.14 ⚑ | Agri-fintech rails for smallholders | Documented L4 | Documented — | **differs** | The quoted CBE text names smallholder farmers specifically (a project titled "T… |
| 3.9 | Digital advisory platforms at scale | Documented L4 | Documented L3 | **differs** | pass |
| 3.10 | Agricultural e-commerce platforms | Documented L4 | Documented L3 | **differs** | pass |
| 7.2 | AI-enabled agricultural solutions de | Documented L3 | Judged — | **differs** | the only source is T5 news, vendor or market material, which carries existence … |
| 7.12 ⚑ | Responsible-AI safeguards (consent,  | Documented L1 | Documented L3 | **differs** | pass |
| 8.2 | Account ownership, female (%) | Measured L3 | Measured L3 | match |  |
| 8.4 | Mobile money account (%) | Measured L2 | Gap — | **differs** | gap |
| 8.6 | Gender gap in phone ownership (pp) | Measured L2 | Documented L2 | match |  |
| 8.9 | Smallholders reached by digital serv | Documented L1 | Documented L1 | match |  |
| 8.11 | Services in local languages (%) | Documented L5 | Gap — | **differs** | gap |
| 8.12 | Documented impact evidence (yield/in | Documented L3 | Gap — | **differs** | gap |
| 8.17 | Climate advisory reach (%) | Gap — | Gap — | match |  |

⚑ marks a prerequisite.


## Reading this

Divergence here is the expected result. The verified assessments came from sustained human-directed searching under the full tiered protocol — Nigeria went from 21 recorded gaps to 4 that way — and this pass runs once, on a budget, without the Gate 2 refutation round that found four of those gap refutations. More gaps and more holds are the honest output of a first automated pass, not a regression.

The number to act on is the **abstention rate**: 9 holds and 22 gaps against the verified 5 and 5. Too loose and everything reads Ready; too tight and everything reads Unverified. These figures are what that threshold should be tuned against, and they should be kept — when automated Gate 2 arrives, re-running this comparison is what tells you whether it earns its 15% of the budget.

