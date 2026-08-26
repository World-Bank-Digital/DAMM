# Decision 13.5 research: proposed indicator-definition dictionary

**Status:** Research proposal for Issue 2 of the final-DAR review. **Nothing in this note ratifies a definition, changes a score, or closes Decision 13.5.**

**Scope:** The 44 scored indicators in DAMM v1.7 whose canonical model record contains `ratification.open_question`. The additional unit question reported in the evidence package belongs to unscored irrigation candidate `A1-CAND-IRR`; it is outside this 44-row scored dictionary and should be handled before that candidate is ever promoted.

**Prepared:** 2026-08-26

## Executive finding

The review correctly identified a model-definition problem rather than a country-research problem. The canonical model contains thresholds and generic ladder anchors, but not a complete operational definition for each indicator. Assessors therefore supplied different populations, units, periods, constructs, and evidence tests while appearing to score the same row.

The 44 open scored rows divide as follows:

| Open-question class | Rows | Meaning |
|---|---:|---|
| `asserts-falsehood` | 6 | The displayed indicator or scored interpretation makes a claim the cited evidence does not establish. |
| `construct-drift` | 30 | Countries or sources measure materially different constructs under one label. |
| `unit-ambiguity` | 8 | The unit, scale, population, denominator, or rung meaning is not fixed. |
| **Total** | **44** | The ninth unit issue in the review is the unscored irrigation candidate. |

Only **five** rows can be closed principally by binding the existing named measure to first-party metadata: **1.1, 1.3, 2.5, 4.2, and 4.3**. The other **39** require a substantive reviewer choice, even where an external standard informs that choice. Evidence can constrain a definition; it cannot decide, for example, whether DAMM intends rural households or rural individuals, foundational ID or remotely usable digital ID, holder or owner, or registered versus active users.

Eight of the 12 prerequisites are among the open rows: 2.1 (universal); 3.3 (FIN, AGI); 3.11 (AGI); 4.7 (FIN); 4.9 (delivery); 5.7 (delivery); 6.14 (FIN); and 7.12 (ADV, SMF, FIN, AGI). These cannot safely remain implicit because their ambiguity can suppress or admit downstream use-case scores.

All eight upward automated-versus-verified disagreements in the two sample assessments sit on open construct-drift rows: Egypt 2.11, 3.8, and 7.12; Nigeria 4.9, 6.4, 6.12, 7.2, and 8.12. Freezing the dictionary is therefore a prerequisite to treating the workbook's automated result as authoritative.

## Local evidence reviewed

The inventory and the implementation recommendations below were checked against:

- the [canonical model](model/DAMM-v1.7-model.json) and its [schema](model/DAMM-v1.7-model.schema.json);
- the [v1.7 specification](DAMM-v1.7-Specification.md), including shared ladder semantics and source tiers;
- the [Decision 13 record](DECISIONS-13.md) and [Thread 4 handoff](THREAD-4-HANDOFF.md);
- the [final-DAR evidence package](Katreyna-Pipeline-Evidence-2026-08-24/01%20Evidence%20for%20the%20twelve%20decisions.md);
- the [definition notes](gauntlet/loop-1/definition_notes.json), [Egypt definition corrections](gauntlet/loop-1/definition_corrections_egy.json), and [Nigeria definition corrections](gauntlet/loop-1/definition_corrections_nga.json);
- the [indicator census](DAMM-v1.7-Indicator-Census.csv);
- the [workbook builder](gauntlet/loop-1/build_workbook_v17.py), [scoring engine](gauntlet/loop-1/engine_v17.py), and model-export logic; and
- the [Egypt](gauntlet/loop-1/EGY_v17.json) and [Nigeria](gauntlet/loop-1/NGA_v17.json) sample assessments, including their cited values and sources.

Two implementation facts are especially important:

1. The workbook derives `Measured`, `Documented`, `Judged`, or `Gap` primarily from cell shape and source tier. Numeric input becomes `Measured` even when the number is a proxy or a modeled estimate. A definition mismatch must therefore be a separate validation failure; evidence class alone cannot catch it.
2. The blank template does not populate the open-definition question from the canonical model. The builder copies a `defnote` only when one exists in a country row. A future definition catalog must be joined from the model for blank and country workbooks alike, rather than duplicated in assessment JSON.

The six falsehood rows remain correctly held or corrected in the sample work: 2.1, 3.5, 4.7, 5.3, 5.7, and 8.5. This proposal does not undo those holds.

## First-party metadata and standards register

The following sources establish definitions or transformations used below. They do not by themselves ratify DAMM's choice of construct.

- **S01 — WDI agricultural value added per worker.** The World Bank series is explicitly “Agriculture, forestry, and fishing, value added per worker (constant 2015 US$),” series `NV.AGR.EMPL.KD`: [official indicator page](https://data.worldbank.org/indicator/NV.AGR.EMPL.KD).
- **S02 — WDI agricultural employment.** Series `SL.AGR.EMPL.ZS` is employment in agriculture as a percentage of total employment and is a modeled ILO estimate: [official indicator page](https://data.worldbank.org/indicator/SL.AGR.EMPL.ZS).
- **S03 — WDI tertiary gross enrollment.** Series `SE.TER.ENRR` measures gross tertiary enrollment across fields, not STEM participation: [official indicator page](https://data.worldbank.org/indicator/SE.TER.ENRR).
- **S04 — Global Findex account definition.** Current WDI series `FX.OWN.TOTL.FE.ZS` counts women age 15+ with an account at a financial institution **or** personal use of a mobile-money service in the preceding 12 months: [WDI metadata glossary](https://databank.worldbank.org/metadataglossary/world-development-indicators/series/FX.OWN.TOTL.FE.ZS). Findex publishes country, gender, and rural disaggregations with questionnaires and glossaries: [official download page](https://www.worldbank.org/en/publication/globalfindex/download-data).
- **S05 — Separate financial-institution and mobile-money accounts.** The World Bank Gender Statistics catalog exposes separate financial-institution account series `fiaccount.t.d.1` and mobile-money account series `mobileaccount.t.d.1`: [financial-institution-account metadata](https://databank.worldbank.org/metadataglossary/gender-statistics/series/fiaccount.t.d.1) and [mobile-account metadata](https://databank.worldbank.org/metadataglossary/gender-statistics/series/mobileaccount.t.d.1).
- **S06 — ID4D terminology and data.** ID4D distinguishes a digital ID system, which uses digital technology throughout the identity lifecycle and can support remote transactions, from foundational identification more generally: [ID4D glossary](https://id4d.worldbank.org/guide/glossary). The 2025 dataset separates demand-side ownership and use of foundational and digital ID from supply-side system availability: [ID4D global dataset](https://id4d.worldbank.org/global-dataset) and [data catalog record](https://datacatalog.worldbank.org/search/dataset/0040787/identification-for-development-id4d-global-dataset).
- **S07 — ITU “at least 3G” coverage.** Coverage is the share of inhabitants within range of a mobile-cellular signal using at least 3G technology, irrespective of subscription or use; higher generations count and 2G does not. The published core indicator is national, so a rural adaptation must use rural covered inhabitants over all rural inhabitants: [ITU telecommunications administrative-data handbook](https://www.itu.int/en/ITU-D/Statistics/Documents/publications/handbook/2020/ITUHandbookTelecomAdminData2020_E.pdf).
- **S08 — ITU mobile-data price basket.** For 2025, the data-only mobile-broadband basket is the cheapest domestic plan providing at least 5 GB per month over 3G or higher; the headline affordability unit is a percentage of GNI per capita. The prior 2 GB basket is a comparability break: [2025 methodology](https://www.itu.int/itu-d/reports/statistics/2025/10/15/ff25-methodology/) and [ITU price-data portal](https://www.itu.int/en/ITU-D/Statistics/Pages/ICTprices/default.aspx).
- **S09 — ITU Global Cybersecurity Index.** The 2024 GCI is reported on a 0–100 scale, with five pillars worth 20 points each: [official GCI 2024 publication](https://www.itu.int/epublications/publication/global-cybersecurity-index-2024).
- **S10 — Government AI Readiness Index.** Oxford Insights' 2025 edition covers 195 governments and uses an updated methodology: [official 2025 index page](https://oxfordinsights.com/ai-readiness/government-ai-readiness-index-2025/). The 2024 methodology documents a 0–100 total score formed from pillar and dimension scores: [official 2024 report](https://oxfordinsights.com/wp-content/uploads/2024/12/2024-Government-AI-Readiness-Index-2.pdf).
- **S11 — APHLIS postharvest loss.** APHLIS estimates cumulative dry-weight loss from harvesting through drying, handling, storage, transport, and market storage by crop, location, and year: [official data table](https://www.aphlis.net/en/data/tables/dry-weight-losses/XAF/wheat/2021) and [loss-assessment manual](https://www.aphlis.net/downloads/APHLIS%20Loss%20Assessment%20Manual.pdf).
- **S12 — Agricultural holding and holder.** FAO defines an agricultural holding as an economic unit under single management and the holder as the person or entity making major decisions: [FAO agricultural-census concepts](https://www.fao.org/4/a0135e/a0135e04.htm).
- **S13 — Small-scale food producer.** The SDG 2.3 methodology operationalizes small scale with relative physical and economic size, while FAO notes that no universal smallholder definition exists: [SDG 2.3 methodology](https://www.fao.org/fileadmin/user_upload/sustainable_development_goals/docs/Methodology_for_SDG_Indicators_2.3.1_and_2.3.2_rev_Feb_2018.pdf) and [FAO smallholder discussion](https://www.fao.org/family-farming/detail/en/c/471178/).
- **S14 — Women and agricultural land.** SDG 5.a.1(b) is the share of women among owners or secure-rights bearers of agricultural land; ownership/secure rights are distinct from operating a holding: [FAO indicator page](https://www.fao.org/sustainable-development-goals-data-portal/data/indicators/5a1-women-ownership-of-agricultural-land/sdg-5-indicators-of-women-s-ownership-of-agricultural-land/) and [UN metadata](https://unstats.un.org/sdgs/metadata/files/Metadata-05-0a-01.pdf).
- **S15 — Phone-ownership gender gap.** GSMA defines its published gender gap as `(male rate − female rate) / male rate`, a relative percentage, not percentage points; phone ownership is sole or main use at least monthly: [official report](https://www.gsma.com/wp-content/uploads/2025/12/The-Mobile-Gender-Gap-Report-2024.pdf) and [methodology page](https://www.gsma.com/solutions-and-impact/connectivity-for-good/mobile-for-development/gsma_resources/methodology-the-mobile-gender-gap-report-2024/).
- **S16 — Digital skills.** ITU measures activities performed in the prior three months across five skill areas; “basic” requires at least one activity in every available area, rather than self-rated literacy: [ITU household manual](https://www.itu.int/en/ITU-D/Statistics/Documents/publications/manual/ITU_HHManual_ICTskills_rev2025.pdf), [2025 skills note](https://www.itu.int/itu-d/reports/statistics/2025/10/15/ff25-ict-skills/), and [SDG 4.4.1 metadata](https://unstats.un.org/sdgs/metadata/files/Metadata-04-04-01.pdf).
- **S17 — Digital public goods.** A DPG is open software, data, AI model, standard, or content that meets the DPG Standard; registered goods undergo review and annual renewal: [DPG Standard](https://github.com/DPGAlliance/DPG-Standard), [DPGA FAQ](https://www.digitalpublicgoods.net/digital-public-goods/faqs), and [registry API](https://github.com/DPGAlliance/dpg-api).
- **S18 — Agricultural data interoperability.** FAO's AGROVOC is a structured linked-open-data vocabulary intended to support semantic interoperability in food and agriculture: [AGROVOC](https://www.fao.org/agrovoc/) and [FAO interoperability publication](https://www.fao.org/agrovoc/publications/agrovoc-semantic-data-interoperability-food-and-agriculture).
- **S19 — Climate-data infrastructure.** WMO's climate-services information system centers on routinely produced, archived, analyzed, exchanged, quality-controlled, and disseminated climate data and products: [WMO CSIS](https://public.wmo.int/activities/csis) and [WMO capacity guidelines](https://etrp.wmo.int/pluginfile.php/25833/mod_resource/content/1/Guidelines%20for%20NMHSs%20on%20Capacity%20Development%20for%20Climate%20Services.pdf).
- **S20 — Agrifoodtech scope.** AgFunder's own taxonomy includes consumer-facing downstream categories such as e-grocery and restaurant technology, which are broader than farmer-serving agtech: [AgFunder taxonomy discussion](https://agfundernews.com/data-snapshot-downstream-investment-grew-124-in-2021-but-upstream-saw-more-deals).
- **S21 — PPP test.** The World Bank PPP Reference Guide describes a PPP as a long-term government–private contract for a public asset or service in which the private party bears significant risk and management responsibility and remuneration is linked to performance: [official definition](https://ppp.worldbank.org/what-ppp-defining-public-private-partnership). A memorandum or ordinary vendor arrangement is therefore not automatically a PPP.
- **S22 — Climate-smart practice components.** FAO defines conservation agriculture through minimum soil disturbance, permanent soil cover, and crop diversification, and identifies integrated pest, nutrient, weed, and water management as complementary practices: [official conservation-agriculture definition](https://www.fao.org/conservation-agriculture/overview/what-is-conservation-agriculture/en/). FAO also treats agroforestry and integrated land/water management as resilience practices: [official sustainable-land-management page](https://www.fao.org/land-water/Land/sustainable-land-management/en).

## Dictionary conventions

Every row below is a **proposed** record. `Evidence-backed metadata binding` means the named DAMM measure maps cleanly to a first-party series or index definition; it does **not** mean the row is already ratified. `Substantive reviewer choice` means at least one plausible interpretation would change the eligible evidence, score, or prerequisite result.

For threshold rows, “current cuts” means the four cuts already in the canonical model. Higher-is-better maps values below the first cut to L1 and values at or above successive cuts to L2–L5. Lower-is-better maps values above the first cut to L1 and values at or below successive cuts to L2–L5. These cuts remain provisional wherever Decision 13.6 governs thresholds or this proposal changes the construct.

For ladder rows, the proposed anchors specialize the shared semantics: L1 absent after documented search; L2 announced, planned, or draft; L3 adopted or operating narrowly; L4 operating with governance, funding, quality, and institutionalization; L5 operating at scale with independent evidence of use. An L5 source should not be solely the operator whose scale claim is being assessed.

Source tiers retain the v1.7 rules: T1 official statistics/databases; T2 peer-reviewed research or international-organization flagships; T3 laws, policies, budgets, and official program records for presence; T4 grey literature; T5 news/vendor material only for initiative existence. Load-bearing numbers require two independent T1–T2 confirmations or the model's single-source flag. Impact requires T2.

## Proposed row-level dictionary

### 1.1 — Agriculture value added per worker (USD)

- **Question class / resolution basis:** `construct-drift`; **evidence-backed metadata binding** to WDI `NV.AGR.EMPL.KD` (S01).
- **Construct:** Labor productivity in agriculture, forestry, and fishing at constant prices.
- **Operational definition:** Use the WDI series exactly as published; display the full sector scope and price basis in the indicator name.
- **Unit / population / period:** Constant 2015 US dollars per worker; national workers in ISIC section A; latest available calendar year, with source year stored.
- **Numerator / denominator:** Constant-2015-US-dollar value added of agriculture, forestry, and fishing / employment in those activities.
- **Admissible sources:** Preferred and ordinarily exclusive source is WDI `NV.AGR.EMPL.KD` (T1). A national-statistics reconstruction is admissible only if it matches sector boundary, constant-price base, employment concept, and year and documents the conversion.
- **Scoring semantics:** Higher is better; current cuts 1,000 / 2,500 / 5,000 / 10,000 map to L2–L5. Cuts remain subject to Decision 13.6.
- **Inclusions / exclusions:** Include forestry and fishing because the series does. Exclude current-US-dollar values, agriculture-only series, GDP per agricultural worker, and values with an undisclosed price base.
- **Ambiguity resolution:** A bare “USD” is invalid. The workbook must show `constant 2015 US$/worker`; rebasing requires an explicit transform and definition-version change.

### 1.3 — Employment in agriculture (%)

- **Question class / resolution basis:** `construct-drift`; **evidence-backed metadata binding** to WDI `SL.AGR.EMPL.ZS` (S02).
- **Construct:** Agriculture, forestry, and fishing employment as a share of total employment.
- **Operational definition:** Use the modeled ILO estimate published through WDI and identify it as modeled rather than a direct survey observation.
- **Unit / population / period:** Percentage of total employed persons; national working-age employed population; latest available calendar year, with source year stored.
- **Numerator / denominator:** Persons employed in ISIC section A / all employed persons × 100.
- **Admissible sources:** Preferred WDI `SL.AGR.EMPL.ZS` (T1). A direct ILOSTAT extract of the same modeled series is equivalent. National survey data are not interchangeable unless the model explicitly changes series and documents classification, age, and year.
- **Scoring semantics:** Lower is better; current cuts 45 / 30 / 15 / 5 map to L2–L5. Cuts remain subject to Decision 13.6.
- **Inclusions / exclusions:** Include forestry and fishing. Exclude the rural-population share, labor-force share, agriculture's GDP share, and a survey estimate silently mixed with the modeled series.
- **Ambiguity resolution:** `Measured` may describe a numeric observation in the engine, but provenance must also record `modeled_estimate`; the evidence class must not imply direct enumeration.

### 1.5 — Post-harvest loss rate (%)

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** between all-crop, cereal-basket, and single-crop constructs.
- **Construct:** Production-weighted postharvest dry-matter loss for a fixed national cereal basket.
- **Operational definition:** Estimate cumulative physical dry-weight loss from harvest through drying, handling, storage, transport, and market storage for this proposed fixed cereal basket: maize, rice, wheat, sorghum, millet, and barley. A crop absent from national production receives zero weight. Use APHLIS-compatible stage definitions (S11).
- **Unit / population / period:** Percent of harvested dry-matter production; national production of basket cereals; latest common crop year or three-year centered average if annual volatility is material.
- **Numerator / denominator:** Sum across basket crops of estimated postharvest dry-matter quantity lost / sum of harvested dry-matter production × 100, using production weights.
- **Admissible sources:** APHLIS/FAO or national loss assessments with documented stage, crop, location, and year (T1–T2). A modeled series must be labeled modeled and retain its uncertainty metadata.
- **Scoring semantics:** Lower is better; current cuts 30 / 20 / 12 / 5 are provisional and require Decision 13.6 validation against the selected basket.
- **Inclusions / exclusions:** Include physical loss in the defined postharvest chain. Exclude preharvest loss, moisture change, quality or price loss without physical loss, horticulture unless added to the basket, and a single-crop estimate presented as national all-crop loss.
- **Ambiguity resolution:** Store `crop_basket_version`, crop-level losses and production weights, `loss_stages`, weighting method, and reference year; if any differ, the value is a proxy and remains held. Reviewers must affirm that a cereal basket, rather than all crops, is DAMM's intended construct.

### 1.6 — Smallholder access to formal markets (%)

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** because access, participation, and channel-of-sale are different measures.
- **Construct:** Small-scale food-producer participation in a formal output market.
- **Operational definition:** Rename to **“Small-scale food producers participating in formal output markets (%)”**. Count a holding only when it completed at least one output sale through a registered buyer, licensed marketplace, formal contract, regulated exchange, or documented producer organization during the reference period. Use the shared FAO/SDG small-scale-producer rule (S12–S13).
- **Unit / population / period:** Percent of small-scale food-producing holdings nationally; prior 12 months or completed crop year.
- **Numerator / denominator:** Small-scale holdings with at least one qualifying completed formal sale / all small-scale food-producing holdings with output in the period × 100.
- **Admissible sources:** Nationally representative agricultural or household-enterprise survey, agricultural census module, or reconciled T1 administrative and census data; T2 survey analysis is admissible when nationally representative.
- **Scoring semantics:** Higher is better; current cuts 20 / 40 / 60 / 80 are provisional pending construct and threshold ratification.
- **Inclusions / exclusions:** Include completed formal transactions. Exclude mere physical/digital access, awareness, informal sales, a regional contract-farming sample, and share of sales by channel unless convertible to the holding-level numerator.
- **Ambiguity resolution:** “Access” is not inferred from infrastructure. The record must state the producer definition, formal-market test, geographic coverage, and whether the unit is holdings or transactions.

### 1.7 — Agricultural credit access (% farmers)

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** between eligibility, application, approval, and actual use.
- **Construct:** Receipt of formal agricultural credit by small-scale food producers.
- **Operational definition:** Rename to **“Small-scale food producers receiving formal agricultural credit (%)”**. Count credit received for an agricultural purpose from a regulated financial institution, licensed microfinance or digital lender, or formally registered cooperative in the prior 12 months.
- **Unit / population / period:** Percent of nationally defined small-scale food-producing holdings; prior 12 months.
- **Numerator / denominator:** Qualifying holdings that received formal agricultural credit / all qualifying small-scale food-producing holdings × 100.
- **Admissible sources:** Nationally representative demand-side survey or T1 lender/registry data reconciled to the national small-scale-producer denominator; T2 nationally representative analysis is admissible.
- **Scoring semantics:** Higher is better; current cuts 10 / 25 / 40 / 60 are provisional pending construct and threshold ratification.
- **Inclusions / exclusions:** Include disbursed formal loans, input credit, and regulated digital credit for agriculture. Exclude rural non-farm adults, application or eligibility without receipt, informal family/moneylender borrowing, and all-purpose household borrowing whose agricultural purpose is unknown.
- **Ambiguity resolution:** “Access” is operationalized as receipt/use, not theoretical availability; alternate access constructs require a new indicator version.

### 1.8 — Farmers using climate-smart practices (%)

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** because farmer, area, crop trait, and practice-basket measures are not interchangeable.
- **Construct:** Adoption by agricultural holdings of practices from a ratified climate-smart-agriculture basket.
- **Operational definition:** A holding qualifies if it used at least one practice from this proposed version-1 basket during the crop year: minimum/reduced tillage; permanent soil cover/cover cropping; crop rotation or intercropping; agroforestry; integrated soil-fertility/nutrient management; integrated pest management; water harvesting or soil/water conservation; efficient irrigation; a stress-tolerant crop variety formally released for the locally relevant climate risk; or an improved livestock heat/drought/disease-resilience practice. Each survey item must include the practice-specific minimum test; generic “climate-smart” self-identification does not qualify. The conservation, water, and agroforestry components are consistent with FAO practice descriptions (S22).
- **Unit / population / period:** Percent of agricultural holdings nationally; latest completed crop year.
- **Numerator / denominator:** Holdings adopting at least one listed practice / all agricultural holdings × 100.
- **Admissible sources:** National agricultural survey/census or nationally representative T2 adoption study using the same basket and holding unit.
- **Scoring semantics:** Higher is better; current cuts 20 / 40 / 60 / 80 are provisional pending basket and threshold ratification.
- **Inclusions / exclusions:** Include listed practices only. Exclude share of crop area, adoption of an unlisted crop trait, project or two-zone samples, intentions, and climate awareness.
- **Ambiguity resolution:** The workbook must expose `practice_basket_version`, holding definition, geographic coverage, and whether adoption is self-reported or observed; no conversion from area share to farmer share.

### 2.1 — Rural mobile broadband coverage (3G/4G)

- **Question class / resolution basis:** `asserts-falsehood`; **substantive reviewer choice** whether DAMM truly requires rural coverage rather than the readily available national ITU series. This proposal retains rural.
- **Construct:** Rural population covered by at least a 3G mobile-cellular signal.
- **Operational definition:** Adapt the ITU at-least-3G coverage definition (S07) to a rural population frame. Coverage means residence within signal range irrespective of subscription or use; 4G and 5G count, 2G does not.
- **Unit / population / period:** Percent of rural residents under the country's documented official rural classification; end-year or stated measurement date, latest available.
- **Numerator / denominator:** Rural inhabitants within at-least-3G signal range / all rural inhabitants × 100.
- **Admissible sources:** T1 regulator/operator submissions validated by the regulator, official coverage maps combined with T1 population grids, or a transparently modeled T2/T4 geospatial estimate allowed by the eventual Decision 13.8 source rule. The national ITU figure is context only.
- **Scoring semantics:** Higher is better; current cuts 20 / 40 / 60 / 80. This is the universal prerequisite, so a national substitute or a 4G-only estimate cannot silently unlock the model.
- **Inclusions / exclusions:** Include all technologies at 3G or higher. Exclude national coverage, subscriber penetration, internet use, 2G, and 4G-only coverage when the intended measure is at least 3G.
- **Ambiguity resolution:** Require `rural_definition`, technology floor, population raster/census year, and modeling method. If only national coverage exists, score `DATA GAP`, not a proxy value.

### 2.5 — Mobile broadband price (% GNI pc)

- **Question class / resolution basis:** `unit-ambiguity`; **evidence-backed metadata binding** to the current ITU data-only mobile-broadband basket (S08).
- **Construct:** Affordability of a minimum-use mobile data plan relative to average monthly income.
- **Operational definition:** From the 2025 methodology onward, use the cheapest domestic data-only mobile-broadband plan on at least 3G providing at least 5 GB per month. Version-lock the basket; do not splice it to the retired 2 GB series.
- **Unit / population / period:** Monthly plan price as percent of monthly GNI per capita; national retail market; ITU price-collection reference month/year.
- **Numerator / denominator:** Monthly retail basket price, including applicable taxes / (annual GNI per capita ÷ 12) × 100.
- **Admissible sources:** Preferred ITU ICT price-basket series (T1). A national reconstruction is admissible only if plan allowance, technology, taxes, promotional treatment, reference month, and GNI denominator match ITU.
- **Scoring semantics:** Lower is better; current cuts 10 / 5 / 2 / 1 map to L2–L5.
- **Inclusions / exclusions:** Include data-only 5 GB plans under the current method. Exclude voice-and-data baskets, annual GNI used without dividing by 12, legacy 2 GB values treated as current, and unadjusted promotional prices.
- **Ambiguity resolution:** Store `basket_version`, allowance, basket type, reference month, currency, tax treatment, and GNI vintage. A method break is not a trend.

### 2.7 — Rural smartphone ownership (%)

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** between individual and household ownership. This proposal aligns the definition to the available household evidence and renames the row.
- **Construct:** Availability of at least one smartphone to a rural household.
- **Operational definition:** Rename to **“Rural households with at least one smartphone (%)”**. A smartphone must support installation and use of internet applications, not merely data-capable feature-phone functions.
- **Unit / population / period:** Percent of rural households; nationally representative survey reference date/year.
- **Numerator / denominator:** Rural households owning or having the regular use of at least one smartphone / all rural households × 100.
- **Admissible sources:** National household ICT survey, census, or Findex-like nationally representative household instrument that explicitly identifies smartphones (T1–T2).
- **Scoring semantics:** Higher is better; current cuts 20 / 40 / 60 / 80 require revalidation after the unit is ratified.
- **Inclusions / exclusions:** Include household-owned or regularly available devices under the survey definition. Exclude individual ownership rates, all-mobile-phone ownership, national/urban rates, and occasional borrowed devices.
- **Ambiguity resolution:** Never compare or substitute household and individual percentages. If reviewers prefer individuals, rename and rebuild the source/threshold rule rather than mixing units.

### 2.11 — Device financing/subsidy schemes

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** on targeting and whether commercial installments qualify.
- **Construct:** An operating affordability intervention that reduces the upfront device barrier for underserved users.
- **Operational definition:** A qualifying scheme offers a subsidy, concessional finance, guarantee, pay-as-you-go arrangement, or other documented price relief and has explicit low-income, rural, farmer, female, disabled, or otherwise underserved eligibility or delivery design.
- **Unit / population / period:** Institutional maturity; schemes available nationally or in documented subnational areas; current status with activity in the latest 12 months.
- **Numerator / denominator:** Not applicable; ladder indicator. Beneficiary and geographic denominators are required for L5 scale evidence.
- **Admissible sources:** T1–T3 policy, budget, regulator, program, or audited provider records for design/operation; T2/T4 independent evaluation for use and scale. T5/vendor evidence can establish existence only.
- **Scoring semantics:** L1 no qualifying scheme after documented search; L2 officially announced/designed or funded; L3 operating narrowly with published terms and verified enrollments; L4 sustained, governed, funded operation in at least three first-order administrative regions; L5 independently verified active beneficiaries equal to at least 10% of the documented eligible population and scheme availability in at least 80% of first-order regions. These L4/L5 bars are proposed and require ratification.
- **Inclusions / exclusions:** Include targeted public, nonprofit, or regulated public–private affordability schemes. Exclude ordinary premium handset installments, cash purchase discounts, generic student laptop finance with no qualifying target, and an announcement with no operating channel.
- **Ambiguity resolution:** Both financing and subsidy may qualify, but explicit underserved targeting is mandatory. Store instrument type, eligibility, effective price relief, active beneficiaries, geography, and year.

### 3.3 — National farmer registry

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** between individual farmers, agricultural holdings, beneficiaries, and mixed card/plot units. This proposal uses the holding as the primary unit.
- **Construct:** A national master register of agricultural holdings and their responsible holder or holders.
- **Operational definition:** Rename to **“National agricultural holding/producer registry.”** A qualifying registry assigns a persistent unique record to a holding, links its holder(s) and relevant parcels or enterprises, has a named public steward, deduplication rules, and an update process consistent with FAO holding concepts (S12).
- **Unit / population / period:** Institutional maturity plus coverage of the current national agricultural-holding universe; status during the latest 12 months.
- **Numerator / denominator:** Ladder indicator; for coverage, active deduplicated registered holdings / estimated total agricultural holdings from the latest census or survey.
- **Admissible sources:** T1–T3 law, administrative instrument, data dictionary, registry documentation, budget, and official operating statistics; T2/T4 independent audit may establish quality or use. Printed-card totals alone are insufficient.
- **Scoring semantics:** L1 no register; L2 approved design or funded build; L3 live registry in limited geography/population with unique records; L4 routinely updated national system with stewardship, deduplication, security, and interoperability; L5 independently verified active records for at least 80% of census-estimated holdings and production use by at least three national agricultural programs. The 80%/three-program bar is proposed.
- **Inclusions / exclusions:** Include records for holdings with linked responsible persons. Exclude a one-off beneficiary list, unlinked farmer cards, plot counts treated as farmer counts, and aggregate census tables.
- **Ambiguity resolution:** Store primary unit, relationship among person/holding/parcel, active-record rule, coverage numerator, census denominator, and last update. Mixed units cannot be added without a crosswalk.

### 3.4 — Digital land/plot registration

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** between title registries, all-property identifiers, agricultural holdings, and use rights.
- **Construct:** A digital, georeferenced register of agricultural parcels and legally recognized tenure or use rights.
- **Operational definition:** A qualifying system represents agricultural parcels as digital geospatial records and links each to a documented ownership, lease, customary, usufruct, or other recognized right, with an updating authority and transaction history.
- **Unit / population / period:** Institutional maturity and share of agricultural parcels/area covered; current operation in the latest 12 months.
- **Numerator / denominator:** Ladder indicator; L5 coverage uses registered agricultural parcels or area / national agricultural-parcel or agricultural-land denominator, with the unit fixed in advance.
- **Admissible sources:** T1–T3 land law, cadastre/registry technical documentation, administrative statistics, budgets, and audit records; T2 independent evaluation for national use/quality.
- **Scoring semantics:** L1 no qualifying system; L2 approved plan/legal basis or funded digitization; L3 operating in limited jurisdictions; L4 routine national operation with governance, update, and data-quality controls; L5 independently verified current records covering at least 80% of national agricultural land area and evidence of registrations/updates/transfers during the latest 12 months. The 80% bar and area denominator are proposed.
- **Inclusions / exclusions:** Include recognized ownership and nonownership rights when explicitly represented. Exclude urban-only property identifiers, scanned/static maps, subsidy plot lists with no tenure field, and claimed national coverage with an unknown denominator.
- **Ambiguity resolution:** Store parcel-versus-area unit, right types, agricultural filter, geography, denominator vintage, and whether the record supports legal transactions or only administrative reference.

### 3.5 — Open agricultural data (machine-readable, AI-ready)

- **Question class / resolution basis:** `asserts-falsehood`; **substantive reviewer choice** because “open,” “machine-readable,” and “AI-ready” are separate tests. This proposal drops the undefined “AI-ready” claim.
- **Construct:** Public availability of reusable, machine-readable priority agricultural datasets.
- **Operational definition:** Rename to **“Open machine-readable agricultural data service.”** A dataset must have nondiscriminatory access, an explicit open license or equivalent legal permission, machine-readable bulk download or API, metadata, and a stated update/vintage. The proposed priority universe has six dataset families: agricultural production/holdings; market and input prices; land/parcel or land use; soils; weather/climate; and pests/disease. Quality fields may be recorded separately rather than called “AI-ready.”
- **Unit / population / period:** Institutional maturity of the national agricultural-data service; current availability and update status.
- **Numerator / denominator:** Not applicable; ladder indicator. A versioned priority-dataset list is the universe for L4–L5 completeness evidence.
- **Admissible sources:** T1–T3 data catalog, license, API/bulk endpoint, metadata, policy, and operating records; independent reuse/uptime studies for L5. A live endpoint check is corroboration, not a substitute for license and metadata.
- **Scoring semantics:** L1 no qualifying dataset after documented search; L2 open-data commitment/draft catalog; L3 at least one priority family passes all access/license/format/metadata tests; L4 at least four of six families are versioned, quality-controlled, and updated on their stated schedule; L5 all six pass and an independent source evidences sustained access and reuse in at least three user organizations outside the publishing ministry. The six-family universe is proposed and requires ratification.
- **Inclusions / exclusions:** Include CSV/JSON/GeoJSON/RDF or documented APIs with open legal terms. Exclude PDF-only tables, dashboards with no export, approval-gated access, missing reuse rights, stale one-off dumps, and a portal announcement without data.
- **Ambiguity resolution:** Score each required test separately. Registration or API keys may be allowed if nondiscriminatory and free, but individualized approval is not open. “AI-ready” cannot be inferred from file format.

### 3.6 — Weather/climate data infrastructure

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** between upstream infrastructure and downstream advisory products. This proposal measures infrastructure.
- **Construct:** The national operational chain for observing, quality-controlling, archiving, exchanging, and disseminating weather and climate data.
- **Operational definition:** A qualifying system has maintained observation assets, calibrated instruments, reliable data flow, quality control, an electronic climate database/archive, processing capability, and documented access/exchange arrangements consistent with WMO's CSIS functions (S19).
- **Unit / population / period:** Institutional maturity and national system coverage; sustained current operation over at least the latest 12 months.
- **Numerator / denominator:** Not applicable; ladder indicator. Network coverage and uptime may support L4–L5 but must state station and geography denominators.
- **Admissible sources:** T1–T3 meteorological-service plans, network inventories, WMO assessments, budgets, technical audits, data-access records; T2/T4 independent quality or use studies for higher rungs.
- **Scoring semantics:** L1 core chain absent/unverified; L2 funded modernization plan; L3 partial operational chain or limited coverage; L4 nationally operational system with QA, archive, governance, funding, and access; L5 independent assessment verifies at least 90% capture/availability against the published schedule for the defined core observation/product set over 12 months and routine use by at least three external organizations. The 90%/three-user bar is proposed.
- **Inclusions / exclusions:** Include physical and digital upstream data infrastructure. Exclude an advisory app, forecast bulletin, warning campaign, or project station network with no national archive/QA chain.
- **Ambiguity resolution:** 8.17 measures receipt of advisories; evidence used there cannot establish 3.6 unless it separately proves the upstream infrastructure components.

### 3.7 — Satellite/EO data integration

- **Question class / resolution basis:** `unit-ambiguity`; **substantive reviewer choice** on what system receives EO data and when a pilot becomes operational integration.
- **Construct:** Routine integration of satellite/earth-observation data into a public agricultural decision or service workflow.
- **Operational definition:** EO data must be ingested on a repeated schedule into a named production workflow—such as crop monitoring, yield estimation, insurance, extension targeting, water management, or disaster response—and materially affect an output or decision.
- **Unit / population / period:** Institutional maturity of each qualifying workflow; repeated operation during at least one completed agricultural cycle.
- **Numerator / denominator:** Not applicable; ladder indicator. L5 may report share of relevant geography, holdings, or decisions covered, with the denominator named.
- **Admissible sources:** T1–T3 technical architecture, procurement/contract, operating records, published outputs, budgets, and agency methods; T2/T4 independent validation or user evidence for scale.
- **Scoring semantics:** L1 no verified integration; L2 funded plan, announcement, or controlled prototype; L3 verified live pilot/narrow production workflow; L4 repeated operational cycles with QA, ownership, and recurring resources; L5 independent review verifies at least two completed cycles and coverage of at least 80% of the workflow's national target agricultural area/population/decisions. The 80%/two-cycle bar is proposed.
- **Inclusions / exclusions:** Include a production workflow even if EO inputs are procured externally. Exclude a research map, hackathon, MOU, one-off analysis, or future-use statement.
- **Ambiguity resolution:** Store integration target, EO products, refresh frequency, decision/output changed, production start date, coverage unit, and last successful run.

### 3.8 — National soil map/database

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** between a digitized legacy map and an operating soil-information service.
- **Construct:** A national digital soil-information service that exposes georeferenced soil properties with documented methods and vintage.
- **Operational definition:** The service must provide queryable or downloadable geospatial soil data, coverage metadata, property definitions, sampling/model methods, vintage, quality/uncertainty information, and a responsible updating institution.
- **Unit / population / period:** Institutional maturity and geographic/agricultural-land coverage; current service status and dataset vintage.
- **Numerator / denominator:** Not applicable; ladder indicator. L5 coverage should use mapped agricultural land / total agricultural land, or another ratified spatial denominator.
- **Admissible sources:** T1–T3 soil agency/database records, metadata, technical reports, budgets, update logs, and live services; T2 independent accuracy/use studies for L5.
- **Scoring semantics:** L1 no accessible national digital resource; L2 funded digitization/update plan; L3 legacy or new data are digitally queryable for limited coverage; L4 governed national service with documented QA and update process; L5 independently evidenced routine use by at least three external user organizations and mapped coverage of at least 80% of national agricultural land. The 80%/three-user bar is proposed.
- **Inclusions / exclusions:** Include legacy observations when digitized with usable metadata. Exclude a scanned map, an image with no queryable attributes, local project maps presented as national, and an announcement without a service.
- **Ambiguity resolution:** “Database” requires queryable data; “national” requires an explicit coverage denominator. Legacy age is recorded and cannot be hidden by a recent portal date.

### 3.9 — Digital advisory platforms at scale

- **Question class / resolution basis:** `unit-ambiguity`; **substantive reviewer choice** because scale and “user” are undefined. This proposal uses active holdings and an explicit provisional bar.
- **Construct:** Sustained farmer-facing delivery of actionable digital agricultural advice.
- **Operational definition:** A platform qualifies when it delivers crop, livestock, market, weather, pest, or management recommendations through a digital channel to identifiable farmers/holdings. An active user is a unique farmer/holding that received or used advice during the prior 12 months, not a historical registration.
- **Unit / population / period:** Institutional maturity plus deduplicated active holdings; latest 12 months and at least one completed agricultural cycle.
- **Numerator / denominator:** Ladder indicator; scale evidence uses active recipient holdings / all national agricultural holdings × 100.
- **Admissible sources:** T1–T3 program design, message/usage logs, privacy-preserving deduplication method, budgets, and official monitoring; T2/T4 independent use survey or audit for L5. Operator totals alone cannot establish L5.
- **Scoring semantics:** L1 absent; L2 announced/designed; L3 operating narrowly with verified active recipients; L4 sustained service with governance, content QA, recurring funding, and active-use reporting; L5 independently verified active reach of at least 10% of national holdings over two cycles. The 10% bar is proposed and requires ratification.
- **Inclusions / exclusions:** Include SMS/USSD/IVR/apps and hybrid digital delivery when advice is actionable. Exclude portals with no delivery, registered-user totals, message sends without a recipient rule, and a temporary project pilot claimed as national scale.
- **Ambiguity resolution:** Store unique-user rule, activity window, deduplication, national denominator, channel, and coverage. If scale cannot be calculated, L5 is unavailable.

### 3.10 — Agricultural e-commerce platforms

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** between farmer-facing agricultural commerce and broader consumer agrifood commerce.
- **Construct:** A digital marketplace through which agricultural producers buy inputs or sell farm output.
- **Operational definition:** A qualifying platform supports producer onboarding and at least one substantive commercial function—buyer/seller matching, order placement, contracting, payment, or transaction recording—for farm inputs or primary agricultural output.
- **Unit / population / period:** Institutional maturity and active producer participation; activity in the latest 12 months.
- **Numerator / denominator:** Not applicable for L1–L4; L5 scale uses deduplicated active producer holdings / all agricultural holdings, or an explicitly ratified transaction denominator.
- **Admissible sources:** T1–T3 platform rules, official registries, contracts, transaction/usage records, and program documents; T2/T4 independent user or market evidence for L5. Vendor claims alone establish existence only.
- **Scoring semantics:** L1 none; L2 announced/prototype; L3 live farmer-facing transactions in limited scope; L4 sustained operation with governance, payments/logistics or dispute processes, and verified active producers; L5 independently verified transactions by at least 10% of national agricultural holdings during the latest 12 months and availability in at least 80% of first-order regions. These scale bars are proposed.
- **Inclusions / exclusions:** Include input and output marketplaces with direct producer participation. Exclude restaurant tech, consumer food delivery, e-grocery, and wholesale platforms that cannot evidence a producer-facing function.
- **Ambiguity resolution:** “Agricultural” is determined by the transacting producer and primary-output/input function, not by a generic food-sector label. Store active-producer and transaction definitions.

### 3.11 — Agricultural data interoperability standards

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** on whether a general government standard qualifies. This proposal requires an agricultural application profile or implementation.
- **Construct:** Formally governed semantic and/or technical rules that allow agricultural data exchange across institutions.
- **Operational definition:** A qualifying standard is formally adopted, agriculture-specific or has a documented agricultural profile, specifies data concepts/formats/interfaces or identifiers, and is implemented by at least two independent institutions. AGROVOC illustrates a sector-specific semantic resource (S18).
- **Unit / population / period:** Institutional maturity and production adoption across the agricultural-data ecosystem; current use in the latest 12 months.
- **Numerator / denominator:** Not applicable; ladder indicator. L5 may report conformant institutions/systems over the identified exchange ecosystem.
- **Admissible sources:** T1–T3 standards, schemas, API specifications, governance decisions, conformance tests, system documentation, and operating records; T2/T4 independent interoperability assessment for L5.
- **Scoring semantics:** L1 none; L2 draft/mandate or working group; L3 formally adopted agricultural standard/profile; L4 production implementation by at least two independent institutions with governance and conformance process; L5 independently verified conformance and repeated exchange across at least five production systems owned by at least three institutions. The five-system/three-institution bar is proposed.
- **Inclusions / exclusions:** Include semantic vocabularies, exchange schemas, APIs, and identifier profiles when governed and implemented. Exclude a generic e-government interoperability framework with no agricultural profile or use, a data-sharing MOU without technical rules, and a single-system internal schema.
- **Ambiguity resolution:** General standards count only through documented agricultural implementation. Store standard/version, governance body, conformant systems, exchange transactions, and test evidence.

### 4.2 — Cybersecurity framework (ITU GCI)

- **Question class / resolution basis:** `unit-ambiguity`; **evidence-backed metadata binding** to the ITU GCI overall score (S09).
- **Construct:** National cybersecurity commitment and capacity as represented by the ITU Global Cybersecurity Index.
- **Operational definition:** Use the country's published ITU GCI overall score for the selected edition and normalize it from 0–100 to 0–1 solely for DAMM's current cuts.
- **Unit / population / period:** Dimensionless score on 0–1 after normalization; national government; latest published GCI edition, with edition stored.
- **Numerator / denominator:** Published overall score, or the sum of the five published pillar scores / 100. This is a scale conversion, not a population ratio.
- **Admissible sources:** ITU country profile, report, or official downloadable data (T1). A government press release is admissible only as a pointer and cannot replace a reconcilable ITU score.
- **Scoring semantics:** Higher is better; current normalized cuts 0.2 / 0.4 / 0.6 / 0.8 correspond to 20 / 40 / 60 / 80 on ITU's scale.
- **Inclusions / exclusions:** Include the overall GCI only. Exclude rank, tier label, a single pillar, values such as 82.4 entered as 82.4 against 0–1 cuts, and an unverified self-reported national score.
- **Ambiguity resolution:** The stored raw value remains 0–100; the scoring transform is `raw / 100`. Record edition and transform. Do not average pillars again when an official overall score exists.

### 4.3 — Government AI Readiness Index

- **Question class / resolution basis:** `unit-ambiguity`; **evidence-backed metadata binding** to the Oxford Insights total score (S10).
- **Construct:** Government readiness to implement AI, as operationalized by the named Oxford Insights index.
- **Operational definition:** Use the publicly available country **total score** on the 0–100 scale from the latest edition that publishes a numeric total. Store edition and methodology version because the 2025 methodology changed.
- **Unit / population / period:** Index points, 0–100; national government; named annual edition.
- **Numerator / denominator:** Not a population ratio; use the publisher's total-score aggregation. No local reconstruction from rank or selected pillars.
- **Admissible sources:** Oxford Insights official report, data download, or country table. Under DAMM's generic taxonomy this publisher source is T4, so the definition catalog must record a narrow named-index exception that permits the publisher-primary total score for this row; it does not promote other T4 claims. A secondary index aggregator may corroborate but not supply the load-bearing value.
- **Scoring semantics:** Higher is better; current cuts 20 / 40 / 60 / 80.
- **Inclusions / exclusions:** Include only total score. Exclude country rank, pillar/dimension score, percentile, media summary, or prior-edition value labeled as current.
- **Ambiguity resolution:** If the newest edition makes no numeric total available, use the most recent edition that does and show its year; do not substitute rank. Treat methodology changes as comparability breaks.

### 4.4 — National digital agriculture strategy

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** whether a broader national strategy or a collection of programs qualifies. This proposal requires a dedicated final strategy for L3 or higher.
- **Construct:** An adopted, implemented national strategy dedicated to digital transformation of agriculture.
- **Operational definition:** A qualifying strategy is a final official national document whose primary scope is digital agriculture, with objectives, institutional owner, implementation arrangements, and time horizon.
- **Unit / population / period:** Policy and implementation maturity; national scope; current strategy period.
- **Numerator / denominator:** Not applicable; ladder indicator.
- **Admissible sources:** T1–T3 government publication/gazette, cabinet decision, budget, implementation plan, monitoring report; T2/T4 independent implementation evaluation for L5.
- **Scoring semantics:** L1 no dedicated strategy after documented search; L2 official commitment or draft; L3 final official publication/adoption; L4 funded implementation with accountable governance and annual output reporting; L5 an independent review verifies completion or on-track delivery of at least 50% of time-due actions across two reporting cycles. The 50%/two-cycle test is proposed.
- **Inclusions / exclusions:** Include a dedicated national strategy even if nested under a broader policy framework. Exclude a broadband/AI/agriculture strategy with scattered digital-ag references, a donor project, a program list, and a draft treated as adopted.
- **Ambiguity resolution:** “National” means formally applicable nationwide; “strategy” requires a final document. Broader-strategy components may support L2 context but not L3.

### 4.6 — National AI strategy with agriculture component

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** on the meaning of “adopted” and how explicit the agriculture component must be.
- **Construct:** An adopted national AI strategy that explicitly governs or programs AI use in agriculture.
- **Operational definition:** A final government AI strategy must expressly identify agriculture, farming, food production, livestock, fisheries, forestry, or a clearly equivalent sector as an application area, with at least an objective, action, program, or governance commitment.
- **Unit / population / period:** Policy and implementation maturity; national scope; current strategy period.
- **Numerator / denominator:** Not applicable; ladder indicator.
- **Admissible sources:** T1–T3 final official strategy, gazette/cabinet approval where used, implementation plan, budget, and monitoring record; T2/T4 independent implementation evidence for L5.
- **Scoring semantics:** L1 no qualifying strategy; L2 draft or official announcement; L3 final official publication or formal approval with explicit agriculture component; L4 assigned owner, budget, plan, and at least one operating agriculture action; L5 an independent review verifies delivery of at least 50% of time-due agriculture actions across two reporting cycles. The 50%/two-cycle test is proposed.
- **Inclusions / exclusions:** Include official final publication where publication itself is the jurisdiction's adoption act. Exclude drafts, speeches, generic “all sectors” language with no agriculture reference, and an agriculture AI pilot unconnected to a national strategy.
- **Ambiguity resolution:** Record the adoption act and exact agriculture provision. Publication and formal cabinet approval are alternative valid adoption routes only when jurisdictional practice supports them.

### 4.7 — Digital ID coverage (%)

- **Question class / resolution basis:** `asserts-falsehood`; **substantive reviewer choice** between foundational-ID ownership and a remotely usable digital credential. This proposal retains the stronger digital-ID construct.
- **Construct:** Adult ownership or effective access to a government-recognized digital credential capable of digital authentication.
- **Operational definition:** Count adults age 15+ who possess or can activate/use a recognized digital credential issued within a digital ID system, including a credential that enables remote online authentication. Apply the ID4D distinction between foundational and digital ID (S06).
- **Unit / population / period:** Percent of resident adults age 15+; national demand-side population; latest comparable survey year.
- **Numerator / denominator:** Adults age 15+ possessing or effectively accessing the qualifying digital credential / all resident adults age 15+ × 100.
- **Admissible sources:** Preferred ID4D/Findex demand-side digital-ID ownership/use series or a nationally representative T1 survey using the same test. Supply-side system availability and administrative cards issued may corroborate but not replace coverage.
- **Scoring semantics:** Higher is better; current cuts 20 / 40 / 60 / 80. This is a FIN prerequisite, so foundational-ID ownership cannot silently unlock it.
- **Inclusions / exclusions:** Include a physical credential only if it has a usable digital authentication capability and the person can access it. Exclude foundational ID ownership alone, birth registration, IDs issued rather than held/usable, and a live system with no population coverage measure.
- **Ambiguity resolution:** The current ID4D `ID.OWN.TOTL.ZS` foundational-ID measure is not automatically admissible. Store credential type, authentication capability, age frame, ownership/use question, and survey year.

### 4.9 — Inter-ministerial coordination mechanism

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** between a standing institution, recurring coordination, and project meetings. This proposal requires a standing or demonstrably recurring mechanism.
- **Construct:** An operating cross-government mechanism that coordinates digital-agriculture decisions and delivery.
- **Operational definition:** The mechanism must have an explicit digital-agriculture mandate, named participation by the agriculture ministry and at least one digital/ICT/data/AI authority, defined membership or terms of reference, and evidence of recurring decisions or meetings.
- **Unit / population / period:** Institutional maturity; national government; current activity within the latest 12 months.
- **Numerator / denominator:** Not applicable; ladder indicator.
- **Admissible sources:** T1–T3 law, cabinet/ministerial order, terms of reference, membership, secretariat budget, agendas/minutes, decisions, and implementation reports; T2/T4 independent governance review for L5.
- **Scoring semantics:** L1 no mechanism; L2 announced or terms of reference drafted; L3 at least two evidenced meetings/decisions in 12 months with both required ministry types; L4 formal standing body with secretariat, resources, accountability, and executed decisions; L5 independent review verifies executed joint actions involving at least three ministries across two successive annual work cycles. The meeting/action bars are proposed.
- **Inclusions / exclusions:** Include a recurring mechanism without a separate legal entity if mandate and evidence trail are strong. Exclude a one-off workshop, bilateral MOU, donor project steering meeting, and general digital committee with no agriculture mandate.
- **Ambiguity resolution:** Store mandate, members, meeting/decision dates, secretariat, funding, and actions executed. “Inter-ministerial” cannot be inferred from program partners.

### 5.3 — Tertiary STEM enrollment (% gross)

- **Question class / resolution basis:** `asserts-falsehood`; **substantive reviewer choice** because “STEM share of students” and “gross enrollment ratio in STEM” have different denominators, while the cited WDI series is all-field tertiary GER (S03). This proposal uses a field share.
- **Construct:** STEM students as a share of all tertiary students.
- **Operational definition:** Rename to **“Tertiary students enrolled in STEM fields (% of tertiary enrollment).”** STEM comprises the ratified ISCED-F field codes for natural sciences, mathematics and statistics; ICT; and engineering, manufacturing, and construction.
- **Unit / population / period:** Percent of enrolled tertiary students; national recognized tertiary institutions; academic year.
- **Numerator / denominator:** Students enrolled in the ratified STEM fields / all tertiary students in the same institutions and year × 100.
- **Admissible sources:** UNESCO UIS or T1 national education statistics with matching ISCED level, field classification, headcount/full-time-equivalent rule, and year.
- **Scoring semantics:** Higher is better. The current cuts 10 / 20 / 30 / 40 were attached to an incoherent label and **must be recalibrated before scoring this construct**; the row remains held.
- **Inclusions / exclusions:** Include only ratified ISCED-F fields. Exclude all-field tertiary gross enrollment, STEM graduates unless the indicator changes, upper-secondary students, and a numerator divided by the tertiary-age population.
- **Ambiguity resolution:** Store field codes, enrollment status, headcount/FTE, ISCED levels, and denominator. The term “gross” should be removed unless reviewers instead choose a population-based GER and define its age denominator.

### 5.4 — Digital literacy among farmers (%)

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** among self-rated literacy, task performance, rural proxies, and farmer/holder populations. This proposal adapts ITU's task-based basic-skills method.
- **Construct:** Basic ICT skills among agricultural holders or day-to-day managers.
- **Operational definition:** A respondent qualifies by reporting at least one specified activity in each of the five ITU skill areas during the prior three months, with all five areas present in the instrument (S16).
- **Unit / population / period:** Percent of agricultural holders/managers nationally; activities in the prior three months, survey year stored.
- **Numerator / denominator:** Holders/managers meeting the basic threshold across all five areas / all interviewed holders/managers with complete skill-area data × 100.
- **Admissible sources:** Nationally representative agricultural/ICT survey using the complete task module (T1–T2). A validated module embedded in a farm survey is admissible.
- **Scoring semantics:** Higher is better; current cuts 10 / 25 / 50 / 75 require revalidation for the adapted population and full-five-area rule.
- **Inclusions / exclusions:** Include activity-based responses under the common window. Exclude self-rated “digital literacy,” general rural-population results, regional training samples, device ownership, and `100 − illiteracy` unless the original instrument is definitionally identical.
- **Ambiguity resolution:** Store exact activities, skill areas, missing-item handling, respondent role, age frame, and weights. If any skill area is absent, do not label the result overall basic digital literacy.

### 5.7 — MoAg digital/AI unit

- **Question class / resolution basis:** `asserts-falsehood`; **substantive reviewer choice** between an organizational unit and a temporary program. This proposal requires a standing unit.
- **Construct:** Permanent organizational capability for digital, data, and/or AI functions inside the national ministry responsible for agriculture.
- **Operational definition:** A qualifying unit is established by an administrative/legal instrument or approved organization chart and has a defined mandate, accountable head, assigned staff, and organizational placement. L4 additionally requires recurring budget/workplan and delivered outputs.
- **Unit / population / period:** Institutional maturity; national agriculture ministry; current fiscal/organizational year.
- **Numerator / denominator:** Not applicable; ladder indicator.
- **Admissible sources:** T1–T3 organization chart, establishment instrument, mandate, staffing table, budget, workplan, and output report; T2/T4 independent capacity review for L5.
- **Scoring semantics:** L1 no unit; L2 approved establishment or funded design; L3 formally established with an accountable head and at least one assigned FTE; L4 recurring budget, annual workplan, at least three FTEs, and delivered outputs; L5 independent review verifies the unit's material role in at least three national ministry workflows across two annual cycles. The staffing/workflow bars are proposed.
- **Inclusions / exclusions:** Include a combined ICT/data/digital unit if its mandate substantively covers digital agriculture or AI. Exclude a donor project team, time-bound implementation unit, committee without staff, individual focal point, and a proposed unit treated as operating.
- **Ambiguity resolution:** Store establishment authority, permanence, reporting line, head, staff FTE, recurring budget, mandate, and outputs. A project can support the unit but cannot substitute for it.

### 5.8 — Agtech/data-science training pipeline

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** because a generic ICT course and an agriculture–data bridge are different pipelines.
- **Construct:** A recurring national education or workforce pipeline that combines agriculture with digital, data-science, or AI capabilities.
- **Operational definition:** A qualifying program has an explicit curriculum joining an agricultural domain with software, data, remote sensing, automation, digital finance, or AI; admits cohorts on a recurring basis; and records completion or placement outcomes.
- **Unit / population / period:** Institutional maturity and annual learners/completers; current academic or training year, with at least two cohorts for sustained claims.
- **Numerator / denominator:** Not applicable; ladder indicator. L5 outcome rates require completers placed in relevant roles / traceable completers.
- **Admissible sources:** T1–T3 accredited curricula, ministry/university records, budgets, enrollment/completion data, qualification registers; T2/T4 tracer or labor-market study for outcomes.
- **Scoring semantics:** L1 none; L2 approved/announced curriculum or funded pilot; L3 at least one operating cohort; L4 at least two completed cohorts with quality assurance and completion data; L5 operation in at least three accredited institutions or one nationally administered program, plus an independent tracer covering at least 70% of completers and reporting relevant placement/capability outcomes. These bars are proposed.
- **Inclusions / exclusions:** Include agriculture programs with substantive digital/data content and digital programs with substantive agricultural application. Exclude generic ICT bootcamps, ordinary agriculture degrees, one-off workshops, and planned curricula with no learners.
- **Ambiguity resolution:** Interpret the slash as an agriculture **and** digital/data bridge, not “agtech or any data-science training.” Store curriculum hours, agriculture content, credential, cohorts, and outcomes.

### 5.12 — Gender balance in digital-ag workforce (%)

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** because “digital-ag workforce” has no population boundary. This proposal uses a bounded public-sector job family.
- **Construct:** Women's representation among professional staff performing digital-agriculture functions in the agriculture ministry and public extension system.
- **Operational definition:** Establish a model-owned job-family crosswalk covering digital product/service, ICT, data, analytics, GIS/EO, automation, AI, and digital-extension roles whose primary duty supports agriculture; count filled professional positions.
- **Unit / population / period:** Percent women; national agriculture ministry and public extension organizations; payroll/reference date or annual average.
- **Numerator / denominator:** Women in qualifying filled positions / all people in qualifying filled positions × 100.
- **Admissible sources:** T1/T3 official HR/payroll or audited workforce return with sex and job-family mapping; T2 independent workforce study using the same institutional boundary.
- **Scoring semantics:** Higher is better; current cuts 20 / 35 / 45 / 50 require validation against this selected population.
- **Inclusions / exclusions:** Include employees mapped to the qualifying job family. Exclude the entire extension workforce, the whole national ICT sector, students, contractors unless explicitly included for all genders, and private agtech staff under this proposed public-sector scope.
- **Ambiguity resolution:** Reviewers must choose public sector versus whole ecosystem. Store organizations, job codes, employment status, sex-variable treatment, vacancy rule, and reference date; do not combine incompatible populations.

### 6.4 — Agtech venture ecosystem

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** between farmer-serving agtech and the broader agrifoodtech investment universe. This proposal uses a farm-proximate scope.
- **Construct:** A sustained ecosystem of active digital ventures serving primary producers or agricultural production and supply-chain operations.
- **Operational definition:** A qualifying venture has a material digital/technology product used in primary production, input delivery, farm management, extension, agricultural finance/insurance, traceability, logistics from farmgate, or producer-to-market exchange. The ecosystem includes multiple active ventures plus enabling finance, support, talent, or market institutions.
- **Unit / population / period:** Institutional maturity and qualifying active ventures/deals; current status with a rolling three-year activity window for sustained claims.
- **Numerator / denominator:** Not applicable; ladder indicator. Counts must use a deduplicated national venture universe and disclosed taxonomy.
- **Admissible sources:** T1–T3 company/registry, investment, accelerator, procurement, and official ecosystem records; T2/T4 independent deal databases and ecosystem studies. AgFunder data require category-level filtering because its downstream categories are broader (S20).
- **Scoring semantics:** L1 no verified ecosystem activity; L2 public/private support announced or first qualifying cohort; L3 at least three active qualifying ventures and one operating support/finance channel; L4 at least five active ventures, two support/finance channels, and qualifying activity in each of the last three years; L5 independent evidence verifies at least 10 active ventures plus follow-on finance, sustained producer use, or an exit during the three-year window. These count bars are proposed.
- **Inclusions / exclusions:** Include farm-proximate upstream and enabling technologies. Exclude restaurant tech, consumer food delivery, e-grocery, alternative protein, and downstream food brands unless their qualifying direct producer service is separately evidenced.
- **Ambiguity resolution:** Store venture taxonomy, inclusion decision, headquarters-versus-operation rule, active-status test, deal window, and source. A broad “agrifoodtech investment” total cannot be scored without filtering.

### 6.9 — Public-private partnerships in digital ag

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** between a formal risk-bearing PPP and looser collaboration. This proposal uses the World Bank PPP test (S21).
- **Construct:** A long-term contractual public–private arrangement delivering a digital-agriculture public asset or service with material private responsibility and risk.
- **Operational definition:** A government entity and legally independent private party must have an executed contract for a public digital-ag asset/service; the private party bears significant management responsibility and performance risk, and remuneration or benefit is linked materially to performance.
- **Unit / population / period:** Institutional maturity of qualifying contracts; current contract term and performance in the latest 12 months.
- **Numerator / denominator:** Not applicable; ladder indicator. Contract portfolio counts require a defined active-contract denominator.
- **Admissible sources:** T1–T3 executed contract or redacted contract summary, procurement/PPP register, allocation of responsibilities/risk, performance reports, and budget/payment records; T2/T4 independent performance evaluation for L5.
- **Scoring semantics:** L1 no qualifying arrangement; L2 planned procurement, approved business case, or nonbinding MOU; L3 executed and operating qualifying contract; L4 at least 12 months of operation with contract governance, funding, risk allocation, and performance monitoring; L5 independent review verifies performance targets over two reporting cycles and service coverage of at least 50% of the contract's nationally approved target population or geography. The duration/coverage bars are proposed.
- **Inclusions / exclusions:** Include performance-linked long-term contracts and concessions meeting the test. Exclude an MOU, sponsorship, grant, ordinary short-term vendor purchase, privatization with no continuing public role, and partnership solely with a state-owned entity treated as private.
- **Ambiguity resolution:** If reviewers intend a broader collaborative-partnership construct, rename the row and define it separately. Under this proposal, “PPP” is not inferred from mixed funding or a public announcement.

### 6.12 — Digital public goods adopted

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** between a country's product being listed as a DPG and the country actually deploying a DPG.
- **Construct:** Live national public-sector agricultural deployment of a verified digital public good.
- **Operational definition:** A qualifying good is current on the DPGA registry at the assessment date, or independently demonstrates conformance to the then-current DPG Standard (S17), and is deployed in production by a national or subnational public agricultural institution.
- **Unit / population / period:** Institutional maturity and deployment scope; registry status and live use during the latest 12 months.
- **Numerator / denominator:** Not applicable; ladder indicator. Active users, transactions, agencies, or geographic coverage support L5 only with an explicit denominator.
- **Admissible sources:** DPGA registry/API plus T1–T3 government architecture, deployment, maintenance, budget, and usage records; T2/T4 independent adoption/use evidence for L5.
- **Scoring semantics:** L1 no verified DPG deployment; L2 planned selection, localization, or pilot announcement; L3 live narrow public agricultural deployment; L4 at least 12 months of maintained and integrated production use with governance and recurring resources; L5 independent review verifies use across at least 50% of the nationally approved target population/geography and reuse by at least two public institutions. These duration/scale bars are proposed.
- **Inclusions / exclusions:** Include registered/open goods actually deployed. Exclude a national product's registry listing with no domestic deployment, an open-source policy, a prototype, and a proprietary product labeled a public good without Standard evidence.
- **Ambiguity resolution:** Verify both halves—DPG status and domestic production use—at a recorded date. Annual registry expiry or withdrawal changes eligibility prospectively and must be versioned.

### 6.13 — SME/agribusiness adoption of digital tools (%)

- **Question class / resolution basis:** `unit-ambiguity`; **substantive reviewer choice** because the enterprise universe and qualifying tools are undefined.
- **Construct:** Operational use of defined digital business tools by agribusiness micro, small, and medium enterprises.
- **Operational definition:** Use the country's official MSME size taxonomy and a model-owned agribusiness industry-code crosswalk. An enterprise qualifies if it used at least one listed operational or transactional tool—such as e-commerce, digital payments, accounting/ERP, inventory, traceability, logistics, farm-management, or production-control software—in the prior 12 months.
- **Unit / population / period:** Percent of active agribusiness MSMEs nationally; prior 12 months.
- **Numerator / denominator:** Active agribusiness MSMEs using at least one qualifying tool / all active agribusiness MSMEs in the sampling frame × 100.
- **Admissible sources:** Nationally representative enterprise/ICT survey or T1 business-register-linked administrative data with industry, size, and tool-use fields; T2 nationally representative research using the same frame.
- **Scoring semantics:** Higher is better; current cuts 10 / 25 / 50 / 75 require validation after the enterprise and tool universes are frozen.
- **Inclusions / exclusions:** Include actual business use. Exclude mere internet/smartphone ownership, planned adoption, all-sector SME rates, large enterprises, farm households unless legally in the MSME frame, and a vendor's customer count without the national denominator.
- **Ambiguity resolution:** Store national SME rule, industry codes, active-enterprise rule, tool basket/version, survey mode, weights, and year. Cross-country comparability depends on exposing national taxonomy rather than pretending it is uniform.

### 6.14 — Agri-fintech rails for smallholders

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** between underlying interoperable rails, a single product, cards issued, and active smallholder use.
- **Construct:** Interoperable digital identity, payment, data, or credit infrastructure actively used to deliver agricultural finance to small-scale food producers.
- **Operational definition:** A qualifying rail supports origination, eligibility/underwriting, disbursement, repayment, insurance settlement, or payment for agricultural finance across more than one participating institution or program. Beneficiaries must meet the shared small-scale-producer definition (S13).
- **Unit / population / period:** Institutional maturity and active small-scale users/transactions; activity during the latest 12 months or agricultural cycle.
- **Numerator / denominator:** Ladder indicator; L5 scale uses deduplicated active small-scale users / estimated national small-scale food producers × 100.
- **Admissible sources:** T1–T3 system architecture, interoperability rules, regulated-participant list, transaction logs, program records, and official denominator; T2/T4 independent audit or demand-side survey for L5. Provider reach claims alone are insufficient.
- **Scoring semantics:** L1 none; L2 designed/announced or sandboxed; L3 live narrow transactions for verified small-scale users; L4 at least 12 months of governed interoperable operation with two or more independent financial/service providers and recurring transactions; L5 independently verified active reach of at least 10% of the national small-scale population. The participant/duration/10% bars are proposed.
- **Inclusions / exclusions:** Include reusable multi-participant rails and services demonstrably built on them. Exclude cards/accounts issued, general landholder products, a single lender's closed app, registered users without transactions, and products whose smallholder status is not tested.
- **Ambiguity resolution:** Store rail components, participants, interoperability, qualifying transaction, active window, deduplication, small-scale test, and denominator. Product availability alone cannot satisfy operation or scale.

### 7.2 — AI-enabled agricultural solutions deployed

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** on the minimum AI test and when a prototype becomes deployment.
- **Construct:** Production use of an agricultural service in which AI/ML is a material functional component.
- **Operational definition:** The service must use a documented model or algorithm that learns, predicts, classifies, recommends, generates, or optimizes; it must deliver a live agricultural function to users or operational decision-makers outside a controlled research test.
- **Unit / population / period:** Institutional maturity and active production use; latest 12 months and at least one completed agricultural cycle where seasonality matters.
- **Numerator / denominator:** Not applicable; ladder indicator. L5 scale requires active users, decisions, transactions, area, or another ratified denominator.
- **Admissible sources:** T1–T3 technical documentation, procurement/contract, model card or system description, deployment/usage logs, governance and monitoring records; T2/T4 independent performance/use assessment for L5. Vendor marketing can establish a claim, not operation.
- **Scoring semantics:** L1 none; L2 announcement, research prototype, or funded build; L3 verified live pilot/narrow production users; L4 at least one completed agricultural cycle in production with accountable owner, monitoring, resources, and repeated use; L5 independent review verifies use covering at least 10% of the national target population/area/decisions across two cycles plus performance or outcome evidence. The 10%/two-cycle bar is proposed.
- **Inclusions / exclusions:** Include ML-enabled diagnosis, forecasting, advisory, risk, automation, and decision support when AI is material. Exclude rule-only digitization mislabeled AI, future announcements, demos, unpublished research, and a pilot with no live user/decision.
- **Ambiguity resolution:** Store AI function, model type/version, deployment environment, live-user/decision evidence, monitoring, geography, and active period. “AI-enabled” cannot be established by branding alone.

### 7.12 — Responsible-AI safeguards (consent, rights)

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** whether a generally applicable legal regime can satisfy the row and which rights are mandatory. This proposal allows a general enforceable regime at L3 and requires agricultural implementation for L4–L5.
- **Construct:** Enforceable rights, remedies, and oversight for people affected by agricultural AI and data-driven automated decisions.
- **Operational definition:** The applicable framework must cover agricultural systems and specify lawful data processing; consent where consent is the lawful basis; access and correction; objection/contestability or meaningful review for consequential automated decisions; complaint/redress; and an accountable oversight authority. Sector implementation must show how farmer, worker, land, and producer data are protected.
- **Unit / population / period:** Legal and implementation maturity; people affected by agricultural AI nationally; currently enforceable regime and latest 12-month implementation evidence.
- **Numerator / denominator:** Not applicable; ladder indicator.
- **Admissible sources:** T1–T3 enacted law/regulation, binding code, regulator guidance/decisions, system impact assessments, procurement safeguards, complaint/remedy records; T2/T4 independent legal or compliance audit for L5.
- **Scoring semantics:** L1 no applicable enforceable safeguards; L2 draft, strategy, or nonbinding principles; L3 general enforceable regime applies to agricultural AI/data and contains the mandatory rights/oversight set; L4 all inventoried high-impact public agricultural AI systems have a documented impact assessment and named oversight route; L5 independent audit covers that complete inventory and verifies compliance, accessible remedy, and at least one completed oversight/enforcement cycle. The system-inventory test is proposed.
- **Inclusions / exclusions:** Include general laws when legally applicable and complete at L3. Exclude aspirational ethics charters, consent-only notices with no rights/redress, generic cybersecurity controls, and an agriculture project policy with no enforcement route.
- **Ambiguity resolution:** “Consent” is not always the correct lawful basis and is not sufficient alone. Store applicable provisions, rights matrix, oversight body, agricultural implementation artifact, decisions/complaints, and audit period.

### 8.2 — Account ownership, female (%)

- **Question class / resolution basis:** `unit-ambiguity`; **substantive reviewer choice** because the current Findex combined account series includes mobile money and therefore overlaps the separate DAMM mobile-money row. This proposal isolates financial-institution accounts.
- **Construct:** Financial-institution account ownership among women.
- **Operational definition:** Rename to **“Financial-institution account ownership, women (% age 15+).”** Bind to the separate Findex/Gender Statistics financial-institution account variable `fiaccount.t.d.1`, not combined WDI series `FX.OWN.TOTL.FE.ZS` (S04–S05).
- **Unit / population / period:** Percent of resident women age 15+; national survey population; latest Findex wave.
- **Numerator / denominator:** Women age 15+ reporting an account at a bank or other financial institution covered by the Findex question / all surveyed women age 15+ × 100, using survey weights.
- **Admissible sources:** Preferred World Bank Global Findex/Gender Statistics sex-disaggregated series (T1); a nationally representative demand-side financial-inclusion survey is admissible only with a definitionally matched question and age frame.
- **Scoring semantics:** Higher is better; current cuts 20 / 40 / 60 / 80.
- **Inclusions / exclusions:** Include qualifying financial-institution accounts. Exclude mobile-money-only ownership, household account availability, administrative accounts opened, and mixed-age or male/female combined rates.
- **Ambiguity resolution:** If reviewers retain the combined Findex indicator, they must explicitly accept double counting with the separate mobile-money construct or revise that row. Store series code and survey wave.

### 8.5 — Women who own land (% holders)

- **Question class / resolution basis:** `asserts-falsehood`; **substantive reviewer choice** between ownership/secure rights and being the operator or holder. This proposal binds to SDG 5.a.1(b).
- **Construct:** Women's share among people with ownership or secure rights over agricultural land.
- **Operational definition:** Rename to **“Women among owners or secure-rights bearers of agricultural land (%)”** and follow SDG 5.a.1(b) (S14). Recognized proxies for secure rights must meet the UN metadata rules.
- **Unit / population / period:** Percent of individual agricultural-land owners/secure-rights bearers; national population represented in the survey; survey reference year.
- **Numerator / denominator:** Women with ownership or secure rights over agricultural land / all people with ownership or secure rights over agricultural land × 100.
- **Admissible sources:** FAO/UN SDG database, nationally representative agricultural or household survey using the same rights test, or T1 land registry with adequate sex coverage and known missingness.
- **Scoring semantics:** Higher is better; current cuts 10 / 25 / 40 / 50 require validation against the SDG 5.a.1(b) construct.
- **Inclusions / exclusions:** Include documented or legally recognized ownership/secure rights under the SDG method. Exclude agricultural holders/operators/managers with no established rights, share of women who own any land when the indicator is agricultural land, and plot counts substituted for people.
- **Ambiguity resolution:** A holder may rent or manage land and is not necessarily an owner (S12). Store rights test, person/plot unit, sex coverage, joint-ownership treatment, and reference year.

### 8.6 — Gender gap in phone ownership (pp)

- **Question class / resolution basis:** `unit-ambiguity`; **substantive reviewer choice** between signed percentage-point difference, absolute difference, shortfall, and GSMA's relative gap. This proposal uses a nonnegative female shortfall.
- **Construct:** The shortfall in women's mobile-phone ownership relative to men's, measured in percentage points.
- **Operational definition:** Rename to **“Female mobile-phone ownership shortfall (percentage points).”** Calculate from male and female ownership rates measured by the same nationally representative instrument and wave.
- **Unit / population / period:** Percentage points; resident adults age 15+ nationally; same survey wave/reference date for both sexes.
- **Numerator / denominator:** `max(0, male ownership % − female ownership %)`. Underlying sex-specific rates each use owners / surveyed adults of that sex with survey weights.
- **Admissible sources:** Preferred Global Findex same-wave sex-disaggregated mobile-phone ownership (S04); a nationally representative survey with matched questions is admissible. GSMA's published relative gap (S15) is not entered as percentage points without the underlying rates.
- **Scoring semantics:** Lower is better; current cuts 20 / 10 / 5 / 2 map to L2–L5 and require confirmation that a shortfall, rather than signed or absolute difference, is intended.
- **Inclusions / exclusions:** Include personal phone ownership under one instrument. Exclude household access, smartphone-only rates unless renamed, rates from different years/sources, and the relative gap percentage entered as points.
- **Ambiguity resolution:** Store both raw sex-specific rates, instrument, wave, and transform. If women exceed men, the shortfall is zero; a signed advantage may be retained separately for analysis.

### 8.9 — Smallholders reached by digital services (%)

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** between registration, messages sent, receipt, use, and benefit. This proposal requires verified active receipt/use.
- **Construct:** Active receipt or use of at least one qualifying digital agricultural service by small-scale food producers.
- **Operational definition:** A small-scale holding qualifies if a deduplicated farmer/holder received or used a substantive advisory, market, finance, insurance, traceability, input, or public agricultural service through a digital channel during the prior 12 months. Apply the common small-scale definition (S13).
- **Unit / population / period:** Percent of national small-scale food-producing holdings; prior 12 months.
- **Numerator / denominator:** Deduplicated small-scale holdings with verified active receipt/use / all national small-scale food-producing holdings × 100.
- **Admissible sources:** Nationally representative demand-side survey or privacy-preserving reconciliation of T1 service logs to a T1/T2 national denominator; independent T2 validation for operator claims.
- **Scoring semantics:** Higher is better; current cuts 10 / 25 / 50 / 75 require validation after the qualifying-service and active-use rules are frozen.
- **Inclusions / exclusions:** Include active receipt/use during the window. Exclude registrations, accounts/cards issued, messages sent without delivery/recipient evidence, cumulative operator “reach,” regional project samples, and nonagricultural digital services.
- **Ambiguity resolution:** Store service basket/version, active event, window, person-to-holding deduplication, small-scale test, geography, and national denominator. Do not add service counts without cross-service deduplication.

### 8.11 — Services in local languages (%)

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** because neither the service universe nor “local language” is defined.
- **Construct:** Availability of the core function of active farmer-facing digital agricultural services in languages used by their intended population.
- **Operational definition:** First create a dated national register of qualifying active farmer-facing services. A service passes if its core content and interaction—not merely marketing or navigation—are available in at least one official/national language other than a default international language, or a language spoken by at least 5% of the intended rural/agricultural population. The 5% rule is proposed.
- **Unit / population / period:** Percent of qualifying active services; national service universe at a fixed annual cutoff.
- **Numerator / denominator:** Qualifying active services passing the local-language test / all qualifying active services in the dated register × 100. Count each service once.
- **Admissible sources:** T1–T3 service register, operating documentation, language inventory, and direct functional test; T1 census/language statistics for the 5% test; T2/T4 user-accessibility audit for corroboration.
- **Scoring semantics:** Higher is better; current cuts 25 / 50 / 75 / 90. If the denominator cannot be enumerated and independently checked, the row must remain a gap or be redesigned as a ladder—never scored from an anecdotal sample.
- **Inclusions / exclusions:** Include translated core advisory/transaction functions across text, audio, IVR, or interface. Exclude a translated landing page, browser auto-translation, customer support only, inactive services, and services outside agriculture.
- **Ambiguity resolution:** Store service inclusion rule, register cutoff, language criterion, test procedure, and pass/fail evidence. Country narrative contamination or a copied service list is a validation failure.

### 8.12 — Documented impact evidence (yield/income)

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** on whether adoption/diffusion evidence counts as impact. This proposal requires a yield or net-farm-income outcome.
- **Construct:** Credible evidence that a digital-agriculture intervention caused or materially contributed to improved agricultural yield or net farm income.
- **Operational definition:** A completed independent causal or credible quasi-experimental evaluation must report a yield and/or net-farm-income outcome, comparator/counterfactual, sample, method, uncertainty, intervention exposure, and reference period. A transparent contribution design may qualify only if causal attribution limits are explicit.
- **Unit / population / period:** Evidence maturity; evaluated producers/holdings and intervention context; study period and publication year stored.
- **Numerator / denominator:** Not applicable; ladder indicator. Effect sizes retain their study-specific units and denominators.
- **Admissible sources:** T2 peer-reviewed study or international-organization flagship/evaluation. T1 program monitoring may identify a study but cannot alone establish impact; T5 is inadmissible for impact.
- **Scoring semantics:** L1 no qualifying evidence after documented search; L2 preregistered protocol or credible evaluation underway; L3 one completed credible outcome study; L4 at least two independent studies or one preregistered multi-region study with transparent methods and consistent outcome evidence; L5 at least three independent studies in two or more regions/interventions plus independently verified scaled implementation and material outcomes. These evidence-count bars are proposed.
- **Inclusions / exclusions:** Include crop/livestock productivity and net farm income when attributable to the digital intervention. Exclude adoption, awareness, diffusion, registrations, user satisfaction, gross revenue without costs when labeled income, simulations, and a vendor testimonial.
- **Ambiguity resolution:** Store intervention, outcome definition, estimator, counterfactual, sample, geography, dates, effect and uncertainty, independence, and publication status. Adoption evidence belongs elsewhere and cannot advance this ladder.

### 8.17 — Climate advisory reach (%)

- **Question class / resolution basis:** `construct-drift`; **substantive reviewer choice** between advisories issued, people registered, messages delivered, and farmers receiving actionable advice. This proposal measures receipt.
- **Construct:** Receipt by agricultural holdings of actionable weather or climate advisories.
- **Operational definition:** A holding qualifies when its holder/manager received at least one timely, location- or crop/livestock-relevant recommendation based on weather or climate information during the prior 12 months. Mere availability or a generic warning is insufficient.
- **Unit / population / period:** Percent of agricultural holdings nationally; prior 12 months or completed agricultural cycle.
- **Numerator / denominator:** Agricultural holdings whose holder/manager received at least one qualifying advisory / all agricultural holdings × 100.
- **Admissible sources:** Nationally representative agricultural/household survey or deduplicated T1 delivery logs reconciled to the national holding denominator; T2 independent reach/use assessment is admissible.
- **Scoring semantics:** Higher is better; current cuts 20 / 40 / 60 / 80 require validation after receipt and advisory-content rules are frozen.
- **Inclusions / exclusions:** Include delivered SMS/USSD/IVR/app/radio or extension-mediated advice when receipt and actionable content are demonstrated. Exclude forecasts or alerts issued, platform availability, registrations, raw weather data, general disaster warnings, and project reach without a national denominator.
- **Ambiguity resolution:** Store advisory test, channel, receipt event, activity window, deduplication, holding denominator, and geography. 3.6 measures upstream infrastructure and cannot substitute for recipient reach.

## What can be resolved mechanically, and what cannot

This distinction should be represented as data, not left in prose:

| Resolution route | Count | Indicator IDs | Required action |
|---|---:|---|---|
| Evidence-backed metadata binding | 5 | 1.1, 1.3, 2.5, 4.2, 4.3 | Confirm the exact publisher series/edition and transformation; then implement and test the binding. No new construct choice is needed. |
| Substantive joint reviewer choice | 39 | 1.5, 1.6, 1.7, 1.8; 2.1, 2.7, 2.11; 3.3–3.11; 4.4, 4.6, 4.7, 4.9; 5.3, 5.4, 5.7, 5.8, 5.12; 6.4, 6.9, 6.12, 6.13, 6.14; 7.2, 7.12; 8.2, 8.5, 8.6, 8.9, 8.11, 8.12, 8.17 | Reviewers must accept, amend, or reject the proposed construct and boundary. Thresholds or ladder anchors must then be confirmed against that choice. |

The range notation `3.3–3.11` in the table means the nine open IDs present in this note (3.3 through 3.11), not every decimal number in an arithmetic sequence.

Reviewer choices should be taken in dependency order:

1. Ratify cross-cutting units first: agricultural holding/holder (S12), small-scale food producer (S13), active user/receipt, and national-versus-subnational evidence.
2. Decide the eight prerequisite rows before any dependent use-case result is accepted.
3. Decide each threshold row's population, denominator, period, and transform before Decision 13.6 calibrates or confirms cuts.
4. Decide each ladder's qualifying object and L3/L5 operating/scale tests before rerunning country assessments.

## Recommended canonical file and schema

Create a model-owned catalog and schema:

- `model/DAMM-v1.7-indicator-definitions.json`
- `model/DAMM-v1.7-indicator-definitions.schema.json`

The definition catalog should be the single home for operational definitions. The canonical model should contain only a stable `definition_ref` for each indicator plus a top-level catalog version and SHA-256 digest. Release/build logic must refuse a missing or mismatched digest. Do not copy definitions into country assessment JSON as editable text.

For Decision 13.5, the first catalog can contain these 44 proposed records. Before a subsequent model release, the same schema should cover all 57 scored indicators so that “closed” rows are not left with a weaker implicit standard.

Recommended shape:

```json
{
  "$schema": "DAMM-v1.7-indicator-definitions.schema.json",
  "catalog_version": "13.5-proposal.1",
  "model_version": "1.7",
  "catalog_status": "proposal",
  "entries": {
    "1.1": {
      "definition_version": "1.1-proposal.1",
      "status": "proposed",
      "question_class": "construct-drift",
      "resolution_basis": "metadata-binding",
      "construct": "Labor productivity in agriculture, forestry, and fishing at constant prices",
      "display_name": "Agriculture, forestry, and fishing value added per worker (constant 2015 US$)",
      "measure": {
        "operational_definition": "Use WDI NV.AGR.EMPL.KD exactly as published",
        "unit": "constant-2015-USD-per-worker",
        "population_scope": "national; ISIC section A workers",
        "reference_period": "latest available calendar year",
        "numerator": "constant-price sector value added",
        "denominator": "sector employment"
      },
      "source_policy": {
        "preferred_series": ["WDI:NV.AGR.EMPL.KD"],
        "allowed_tiers": ["T1"],
        "fallback_rule": "definitionally matched reconstruction only",
        "minimum_confirmation": "model-default"
      },
      "scoring": {
        "method": "threshold",
        "direction": "higher-is-better",
        "cuts": [1000, 2500, 5000, 10000],
        "cuts_status": "pending-13.6",
        "missing_rule": "DATA GAP",
        "mismatch_rule": "HOLD"
      },
      "inclusions": ["forestry", "fishing"],
      "exclusions": ["current USD", "agriculture-only series"],
      "ambiguity_rule": "A bare USD value is inadmissible",
      "comparability_breaks": [],
      "decision": {
        "decision_id": "13.5",
        "ratified_by": null,
        "ratified_on": null,
        "rationale": "proposal only"
      },
      "citations": ["S01"]
    }
  }
}
```

Required schema behavior:

- Enumerate `status` as `proposed`, `ratified`, or `superseded`; only `ratified` may remove a scoring hold.
- Enumerate `resolution_basis` as `metadata-binding` or `reviewer-choice`.
- Require nonempty construct, operational definition, unit, population/scope, reference period, admissible-source policy, scoring semantics, inclusions, exclusions, ambiguity rule, decision record, and citations.
- Require numerator and denominator for rates, shares, per-capita/per-worker measures, and derived gaps; permit explicit `not_applicable` only for ladders and indices.
- For `threshold`, require numeric cuts, direction, unit compatibility, and strictly ordered cuts in the direction of improvement.
- For `ladder`, require explicit L1–L5 anchors, a qualifying-object test, an operating test, and an independently verifiable scale test.
- Require a `transform` whenever publisher and DAMM units differ, such as ITU GCI `/ 100` or the phone-gap subtraction.
- Require `comparability_breaks` for method/edition changes, including the ITU 2 GB→5 GB basket and Oxford Insights methodology changes.
- Require exact dataset identifiers where a named series exists; a title or homepage alone is not a binding.
- Preserve the original open question and its resolution rationale in provenance even after ratification.

## Workbook and build integration

The build should join the catalog by indicator ID and definition version. Recommended workbook behavior:

1. Add a generated **Definitions** sheet containing every scored indicator's ID, definition version/status, construct, operational definition, unit, scope, period, formula, source policy, scoring semantics, inclusion/exclusion, ambiguity rule, and citation links.
2. In **Scoring**, retain the open-question visibility but populate it from the catalog for blank and country workbooks. Add generated `Definition version`, `Definition status`, and `Definition match` fields; do not rely on country-level `defnote` text.
3. Derive the ratification hold from catalog status and definition match. A row with `status != ratified`, missing required fields, or mismatched unit/population/period must remain held even when its value is numeric.
4. Capture assessment metadata structurally: raw value, unit, numerator, denominator, population, geography, reference period, source series/edition, transform, source tier, and proxy flag. Narrative notes are not a substitute.
5. Have the export path use the same joined structure as the workbook. No definition, threshold, or ladder string should be retyped in builder code.
6. Make definition records read-only/protected in generated workbooks. Country researchers may record a proposed proxy, but cannot redefine the indicator locally.

## Validation strategy

Validation should fail closed and run in the following layers:

1. **JSON Schema:** validate types, enums, required fields, conditionals by method/unit, URL shape, and decision provenance.
2. **Inventory parity:** assert exactly one catalog entry for each model indicator, no orphan IDs, no duplicates, and—during Decision 13.5—exact agreement between the 44 `ratification.open_question` IDs and the 44 proposal records.
3. **Semantic completeness:** reject blank/generic population, period, unit, denominator, inclusion/exclusion, or ambiguity fields. Flag forbidden placeholders such as “national where available,” “at scale,” or “appropriate source” unless operationalized.
4. **Mathematical consistency:** check unit/formula compatibility, denominator nonzero, percentages in 0–100, normalized indices in 0–1, gap transform sign, and threshold monotonicity.
5. **Named-series contracts:** regression-test exact codes and transforms for the five mechanical rows: `NV.AGR.EMPL.KD`, `SL.AGR.EMPL.ZS`, the versioned ITU 5 GB data-only basket, ITU GCI `/ 100`, and Oxford Insights total score. Reject ranks, pillars, legacy baskets, or label-only matches.
6. **Assessment admissibility:** compare a country value's unit, population, geography, period, numerator/denominator, series/edition, and transform with the ratified record. Any mismatch becomes `HOLD` or `DATA GAP`; it never silently becomes `Measured`.
7. **Prerequisite safety:** require a ratified definition and an admissible source before any prerequisite can unlock dependent rows. Emit the affected use cases in the error.
8. **Workbook/model parity:** verify the model, definitions sheet, Scoring rows, formulas, and export all carry the same ID, definition version, status, method, cuts/anchors, and digest. Verify the blank workbook displays all definition records.
9. **Country regression fixtures:** rerun Egypt and Nigeria. The six falsehood corrections must remain held/corrected, and none of the eight upward automated-versus-verified rows may rise until its reviewer-choice definition is ratified and its evidence passes.
10. **Adversarial fixtures:** include national-versus-rural, household-versus-individual, foundational-versus-digital ID, holder-versus-owner, active-versus-registered, issued-versus-received, general-versus-agriculture-specific, and operator-versus-independent evidence cases.
11. **Source/citation integrity:** require first-party metadata for named series/standards, validate citation resolution in CI, record access/edition dates, and flag source-tier violations or expired registry status.
12. **Version and change control:** any change to construct, unit, population, period, denominator, transform, qualifying object, or ladder anchor bumps the definition version and catalog digest, records a decision, and invalidates or explicitly migrates derived assessments.

## Ratification workflow proposed for Decision 13.5

1. Accept the five metadata bindings as a batch only after a reviewer confirms that the named external measures are indeed DAMM's intended constructs.
2. Review the 39 choices in small construct families: agricultural units; connectivity/affordability; registries/data infrastructure; strategies/institutions; skills/workforce; ecosystem/deployment; inclusion/outcomes.
3. For each accepted row, record the reviewer, date, rationale, definition version, and any threshold/ladder follow-up. “Accepted subject to later definition” is not closed.
4. Keep the canonical `ratification.open_question` and workbook hold until the structured record is `ratified` and validation passes.
5. Run Decision 13.6 only against frozen constructs. A threshold calibrated before its denominator or unit is fixed is not portable.
6. Rebuild the blank workbook and both sample assessments, review the eight discrepancy rows manually, and publish a change report before declaring Issue 2 closed.

## Completeness check

The proposed dictionary contains one record for every scored canonical open-definition ID:

| Numeric group | Count | IDs |
|---|---:|---|
| 1.x | 6 | 1.1, 1.3, 1.5, 1.6, 1.7, 1.8 |
| 2.x | 4 | 2.1, 2.5, 2.7, 2.11 |
| 3.x | 9 | 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10, 3.11 |
| 4.x | 6 | 4.2, 4.3, 4.4, 4.6, 4.7, 4.9 |
| 5.x | 5 | 5.3, 5.4, 5.7, 5.8, 5.12 |
| 6.x | 5 | 6.4, 6.9, 6.12, 6.13, 6.14 |
| 7.x | 2 | 7.2, 7.12 |
| 8.x | 7 | 8.2, 8.5, 8.6, 8.9, 8.11, 8.12, 8.17 |
| **Total** | **44** | **Exact parity with scored canonical open-question rows** |

Automated parity should remain the acceptance criterion; this table is a human-readable audit aid. The unscored `A1-CAND-IRR` question is intentionally excluded.

## Bottom line

Decision 13.5 should not be ratified as a blanket “definitions fixed” decision from this note. The defensible closure is row-level: five metadata bindings can be confirmed mechanically; 39 boundaries need joint reviewer judgment; and every accepted definition must enter the canonical, versioned catalog before it can affect a workbook or country score. This preserves the Issue 1 corrections and turns future disagreements into explicit validation failures rather than silent scoring drift.
