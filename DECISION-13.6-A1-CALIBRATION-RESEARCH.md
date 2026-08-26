# Decision 13.6 — A1 threshold calibration research

**Prepared:** 26 August 2026
**Status:** evidence note and calibration proposal; **not a ratification record**
**Scope:** the ten A1 rows in DAMM v1.7, their threshold lineage, Egypt/Nigeria/Bhutan case behavior, official methodological anchors, edge semantics, provenance, and release tests
**Decision affected:** 13.6 remains open. This note changes no threshold, score, model flag, country observation, or Issue 1 file.

## Executive finding

The present A1 cut-points should **not** be ratified as a set. The March 2026 framework workbook establishes a recoverable lineage for all ten rows, but neither it nor the Bhutan delivery records a source, rule, reference distribution, target, or expert rationale for any individual cut. The Bhutan report's general statement that quantitative thresholds were benchmarked against World Bank, ITU, FAO, and GSMA standards is not a cut-level calibration basis.

The recut from the March framework to the v1.7 test values is consequential. Replaying the observed country values changes four levels:

| Country | Row | Observation | March cuts | v1.7 test cuts | Change |
|---|---|---:|---:|---:|---:|
| Egypt | 1.3 Employment in agriculture | 17.5246% in the WDI series; 18.0 stored in the clean final | L4 | L3 | −1 |
| Nigeria | 1.3 Employment in agriculture | 33.5337% | L3 | L2 | −1 |
| Bhutan | 1.7 Agricultural credit access | 12.04% | L1 | L2 | +1 |
| Bhutan | 8.1 Prevalence of undernourishment | 22.7% | L1 | L2 | +1 |

Those are not reasons to choose either set. Egypt, Nigeria, and Bhutan are validation cases, not a population from which to fit global boundaries. The standing requirement for a genuinely unseen, human-shadowed country makes that distinction essential.

What can be approved now is narrower:

1. the calibration contract: an exact construct and unit, explicit score polarity, five exhaustive and non-overlapping intervals, a typed calibration basis, immutable source/snapshot references, approval status, and reproducible tests;
2. the current general boundary mechanic, where it is intended: a higher-is-better row upgrades at an exact cut (`>=`), and a lower-is-better row upgrades at an exact cut (`<=`);
3. the exact official constructs for rows 1.1–1.4 and 8.1, and conditional directionality for most rows;
4. retention of `thresholds_ratified: false` until each row has a signed calibration record and every dependent 13.5 definition is closed.

No current numeric set is ratifiable from the evidence assembled here. Row 8.1 has the strongest external basis for a recut because FAO has published severity categories, but official category vintages differ and their half-open boundaries cannot be represented faithfully by the current bare four-number array. It therefore remains a proposal for method-owner approval, not an automatic correction.

## 1. Evidence base and snapshot

The research used the following first-party and project artifacts.

| Artifact | Role | SHA-256 at research snapshot |
|---|---|---|
| `model/DAMM-v1.7-model.json` | Current canonical draft, v1.7 revision 2; all ten A1 rows have `thresholds_ratified: false` | `057e173496707df78b65df93fe8dd4b1e061fdb29829b51b9a5842235bb94a7f` |
| `model/DAMM-v1.7-model.schema.json` | Current machine schema; a threshold is only four numbers plus direction | `20abd0d06355d7426610158cc5c799b17229e00defff0ebb35044c18c946df93` |
| `gauntlet/loop-1/workbooks-v1.7/DAMM-v1.7-Scoring-Workbook-Blank-Template.xlsx` | Executable spreadsheet boundary logic | `a78c7c15c7b39cc0722054c6fa84f2278c32db11b0517a9bd10ecb96482bca23` |
| `gauntlet/loop-1/EGY_202608260342_clean_v17.json` | Current clean Egypt observation set | `021dff330d2d0b9f351c02ba8b06cda911fe74281cdfdc4feea573179d7f9d7e` |
| `gauntlet/loop-1/NGA_v17.json` | Current verified Nigeria observation set | `637c2fcc87a8bbdfc7be745378dea85f42bf7c03f6b40161f6af77d38d0bbc8c` |
| `Katreyna-Review-Package-2026-08-23/2 Diagnostic reports/Egypt — Digital Agriculture Diagnostic.pdf` | Earlier worked-example report; A1 displayed on physical page 2 | `cfe8af0589cf3b761fae7b9bb40ceee5330d7dd8b3d81d5a4918fe6d04917f76` |
| `Katreyna-Review-Package-2026-08-23/2 Diagnostic reports/Nigeria — Digital Agriculture Diagnostic.pdf` | Worked-example report; A1 displayed on physical page 2 | `fd6c9b1c49dd2f24328876e0fd6821e482ba585800c468b983765e6739b97202` |
| March framework, `.../01 Approach & Methodology/Maturity Model/DAMM Indicator Framework Workbook.xlsx`, sheet `Indicator Framework` | Earliest located explicit A1 threshold set | `38ab37a98d6d34fb295344ed3c4c55a421baa943f8c0371779108839b0022508` |
| Bhutan, `.../03 Country Examples/Bhutan/Final Reports/Bhutan DAR Assessment.xlsx`, sheet `Indicator Data` | Third country/design case using the March cuts | `27e70673d3ac3ec96d7b0f12c11f3499f98d055702b29935c9f0aff0ca4f6182` |
| Bhutan, `.../03 Country Examples/Bhutan/Final Reports/Bhutan DAR Diagnostic.pdf` | Delivered narrative and statistical annex; physical pages 21 and 27 contain the relevant rows | `3c68681a1480e8a86bf91f0d2484e65c52233c182518c8981714e08b00927fc7` |
| `gauntlet/loop-1/CALIBRATION.md` | Pipeline abstention analysis, **not A1 cut-point calibration** | `41501d506c0f71cf6d243bc305aa6ebec1bffabc563f172c74103e933e331808` |

The three external artifacts were inspected from byte-local XLSX/PDF copies. Full
workstation paths and connected-Drive object identifiers are intentionally omitted; the
stable artifact names, sheet or page locations, and SHA-256 digests above are the
provenance record needed for this note.

The Bhutan PDF says the quantitative thresholds are benchmarked against international standards and names World Bank WDI, ITU, FAO, and GSMA. It does not identify which source supports which row or cut. The March workbook says numerical scoring is mechanical once thresholds exist, but it does not document how those thresholds were selected.

The abstention calibration note should not be cited as support for A1 boundaries. It asks whether the research pipeline should assign a level when evidence is thin. Its main result—that four of six rows withheld in both countries were never reached—shows that loosening an evidence threshold cannot cure construct or retrieval gaps in rows such as 1.6 and 1.7. It says nothing about whether 20%, 40%, 60%, and 80% are valid maturity cuts.

## 2. Complete threshold lineage

All arrows below run from the March 2026 framework to the current v1.7 test values.

| ID | Indicator | Direction | March framework | v1.7 test values | Documented reason for recut |
|---|---|---|---|---|---|
| 1.1 | Agriculture value added per worker | Higher | `[1000, 3000, 8000, 15000]` | `[1000, 2500, 5000, 10000]` | None located |
| 1.2 | Cereal yield | Higher | `[1500, 3000, 5000, 7000]` | `[1500, 3000, 4500, 6000]` | None located |
| 1.3 | Employment in agriculture | Lower | `[60, 40, 20, 5]` | `[45, 30, 15, 5]` | None located |
| 1.4 | Food production index | Higher | `[80, 95, 110, 130]` | `[95, 105, 115, 130]` | None located |
| 1.5 | Post-harvest loss rate | Lower | `[30, 20, 10, 5]` | `[30, 20, 12, 5]` | None located |
| 1.6 | Smallholder access to formal markets | Higher | `[20, 40, 65, 85]` | `[20, 40, 60, 80]` | None located |
| 1.7 | Agricultural credit access | Higher | `[15, 35, 60, 80]` | `[10, 25, 40, 60]` | None located |
| 1.8 | Farmers using climate-smart practices | Higher | `[10, 30, 55, 80]` | `[20, 40, 60, 80]` | None located |
| 8.1 | Prevalence of undernourishment | Lower | `[20, 10, 5, 2.5]` | `[25, 15, 7.5, 2.5]` | None located |
| 8.5 | Women who own land | Higher | `[15, 25, 40, 50]` | `[10, 25, 40, 50]` | None located |

There is no cut-level provenance in either set. “Benchmarking” is therefore a claim to be substantiated, not itself a calibration method. A complete calibration record must answer at least: benchmarked to what construct, publisher, version, country universe, reference year, statistical transformation, target or category, and boundary convention?

## 3. Country replay and sensitivity

### 3.1 All ten rows

The table distinguishes threshold-derived values from assessor-held or documented rows. `Gap` means the current clean artifact does not contain an admissible measurement of the named construct. `Hold` means evidence exists but no level is currently authorized.

| ID | Egypt, current clean final | Nigeria, current verified | Bhutan, delivered case | March→v1.7 effect |
|---|---|---|---|---|
| 1.1 | 8,942.42; L4 | 3,494.89; L3 | 1,837.80; L2 | No level change |
| 1.2 | 7,402.0; L5 | 1,558; L2 | 3,463.8; L3 | No level change |
| 1.3 | 18.0 stored (WDI 17.5246); L4→L3 | 33.5337; L3→L2 | 42.37; L2 | Egypt −1; Nigeria −1 |
| 1.4 | 109.1; L3 | 119.85; L4 | 77.75; L1 | No level change |
| 1.5 | Gap | Cereals-only range 9.5–17.4%; Documented L3 | 32%; L1 | No comparable mechanical change; Nigeria is not a single all-crop measurement |
| 1.6 | Gap | About 0% formal-channel participation; Documented L1 | 10.3%; L1 | No level change on the recorded cases |
| 1.7 | Gap | 7% credit beneficiaries; Documented L1 | 12.04%; L1→L2 | Bhutan +1 |
| 1.8 | Gap | 87.2% in two zones; Hold because it is not national | About 75%; L4 | No comparable level change |
| 8.1 | 9.0 stored (fine source value 9.4); L3 | 19.9; L2 | 22.7; L1→L2 | Bhutan +1 |
| 8.5 | Gap | 31.6; Hold pending construct decision | 45.98%; L4 | No comparable level change |

The current clean Egypt final appropriately retracts 1.5–1.8 and 8.5 as scored proxies. Its A1 mean is 3.60 on five rated rows under the v1.7 cuts; replaying row 1.3 under the March cuts would make it 3.80, still Advanced under the ruled midpoint bands. The earlier Egypt reviewer PDF shows A1 at 3.00 on eight rated rows because it predates those clean-slate withdrawals; it should not be treated as the authoritative calibration case.

Nigeria's current A1 mean is 2.25 on eight rated rows. Replaying only the numeric 1.3 change under the March cuts produces 2.38; both remain Emerging. Documented rows 1.5–1.7 use assessor levels and are not mechanically relevelled from prose strings.

Bhutan's delivered P1 score is not directly comparable because its report used a different pillar topology. Crosswalking the same ten A1 rows produces a sensitivity mean of 2.00 under the March levels and 2.20 under the v1.7 cuts. This is a diagnostic replay, not a revision to the delivered Bhutan assessment.

### 3.2 What the cases can and cannot establish

The three cases are useful for:

- detecting whether a recut changes a level, mean, band, or margin;
- checking construct availability and whether a supposed national statistic is actually local, commodity-specific, or a proxy;
- exposing exact edge and stale-level propagation defects;
- generating regression fixtures after a method decision is made.

They cannot establish the cut-points. Two cases were already used during pipeline development, and Bhutan is an inherited design case. Fitting thresholds to preserve their historical scores would be circular and would compromise the unseen-country validation condition.

## 4. Official methodological anchors, row by row

### 4.1 Rows with an official international series

**1.1 — Agriculture value added per worker.** The exact WDI construct is “Agriculture, forestry, and fishing, value added per worker (constant 2015 US$),” series `NV.AGR.EMPL.KD`. It covers ISIC Rev. 4 divisions 01–03 and combines national accounts with employment data. WDI warns that definition, coverage, and methodology are not always consistent across countries. A higher value is directionally consistent with greater measured labor productivity, but WDI supplies no five-level maturity categories. The bare-dollar cuts are also price-base dependent and must be versioned if the constant-price reference year changes. [World Bank WDI metadata](https://databank.worldbank.org/metadataglossary/world-development-indicators/series/NV.AGR.EMPL.KD)

**Disposition:** approve the exact series, unit, and conditional higher-is-better polarity after 13.5 renames the row; do not approve either numeric set without choosing and documenting a normative or frozen-distribution method.

**1.2 — Cereal yield.** WDI/FAO series `AG.YLD.CREL.KG` is kilograms per harvested hectare for a dry-grain cereal basket. WDI notes that production depends on soil, rainfall, irrigation, seed quality, and production technique, and that cross-country consistency is incomplete. Higher yield is directionally consistent with this productivity construct, but neither WDI nor FAO provides DAMM maturity categories at 1,500/3,000/4,500/6,000 or at the March values. [World Bank WDI metadata](https://databank.worldbank.org/metadataglossary/world-development-indicators/series/AG.YLD.CREL.KG)

**Disposition:** approve the exact construct and conditional higher-is-better polarity; numeric cuts need method-owner approval, with agroecological and crop-mix sensitivity disclosed.

**1.3 — Employment in agriculture.** WDI/ILO series `SL.AGR.EMPL.ZS` is the modeled share of total employment in agriculture, hunting, forestry, and fishing. WDI describes the textbook development path as labor moving from agriculture to industry and services, but also warns that modeled observations are uncertain and should not be used for country rankings, and that survey scope and treatment of self-employment and unpaid family labor vary. [World Bank WDI metadata](https://databank.worldbank.org/metadataglossary/world-development-indicators/series/SL.AGR.EMPL.ZS)

Lower-is-better is therefore a structural-transformation interpretation, not a universal welfare law. A high agricultural employment share can coexist with productive, resilient agriculture; a falling share can also reflect distress rather than transformation.

**Disposition:** approve the exact series and denominator; retain lower-is-better only with an explicit structural-transformation rationale approved by the domain owner. Neither `[60,40,20,5]` nor `[45,30,15,5]` has an official basis. The change materially downgrades both worked countries.

**1.4 — Food production index.** WDI/FAO series `AG.PRD.FOOD.XD` is a relative Laspeyres volume index with 2014–2016 equal to 100, using price-weighted quantities after seed and feed deductions. It is not an absolute production level or a food-security outcome. A value of 115 means production is 15% above that country's own base-period aggregate, not that the country is 15 points more mature than a country at 100. [World Bank WDI metadata](https://databank.worldbank.org/metadataglossary/world-development-indicators/series/AG.PRD.FOOD.XD)

**Disposition:** the exact construct can be approved. Higher-is-better is defensible only as growth relative to the fixed base, not general maturity. Numeric cuts require an explicit choice about base-period rebasing, volatility, and whether change from a country baseline belongs in a cross-country maturity model.

**8.1 — Prevalence of undernourishment.** FAO defines SDG 2.1.1 as the proportion of the population whose habitual food consumption is insufficient to meet dietary-energy requirements. Lower-is-better is unambiguous for this construct. [Current FAO SDG indicator page](https://www.fao.org/sustainable-development-goals-data-portal/data/indicators/2.1.1-prevalence-of-undernourishment/2/en)

FAO has published more than one category convention. An official five-category presentation used `<2.5`, `2.5–<5`, `5–<20`, `20–<35`, and `>=35`; later Hunger Map material used `<5`, `5–<15`, `15–<25`, `25–<35`, and `>=35`. FAO's 2026 statement still treats 2.5% as a meaningful reporting/Hunger Map threshold. [FAO five-category presentation](https://www.fao.org/4/Y0006E/Y0006E00.htm), [FAO Hunger Map example](https://coin.fao.org/coin-static/cms/media/2/13843839442340/overview_food_security_and_nutrition_in_mexico_2013-prov.pdf), [FAO 2026 statement](https://www.fao.org/director-general/speeches/details/launch-of-the-state-of-food-security-and-nutrition-in-the-world-%28sofi%29-2026-report-statement/en)

Neither the March `[20,10,5,2.5]` set nor the current `[25,15,7.5,2.5]` set matches either published five-category scheme. The current array appears to be a hybrid, but no rationale is recorded.

**Disposition:** approve the construct and lower-is-better polarity. Ask the method owner to select an official category vintage or state a different normative rule. If the older five-category system is selected, the DAMM performance levels would reverse the FAO severity categories: L1 `x >= 35`, L2 `20 <= x < 35`, L3 `5 <= x < 20`, L4 `2.5 <= x < 5`, L5 `x < 2.5`. This is a proposed crosswalk only. It requires interval objects and censored-value support; it cannot be encoded exactly by the current `<=` four-cut mechanic.

### 4.2 Rows without a standardized global percentage construct

**1.5 — Post-harvest loss rate.** FAO's SDG 12.3.1a Food Loss Index covers losses from production/harvest up to but excluding retail and measures change in percentage losses for a country basket relative to a base period. FAO also distinguishes commodity-level loss percentages and warns against simple aggregation across unlike commodities. This is not the same object as a single national “all-crop post-harvest loss rate.” [FAO food-loss measurement methodology](https://www.fao.org/platform-food-loss-waste/food-loss/food-loss-measurement/), [FAO SDG 12.3.1a portal](https://www.fao.org/sustainable-development-goals-data-portal/data/indicators/1231-global-food-losses)

**Disposition:** lower losses are directionally better, but no threshold can be calibrated until 13.5 fixes scope, supply-chain stages, commodity aggregation, denominator, and whether the row is a rate or an index. Current Egypt is a gap and current Nigeria is a cereals-only range, which confirms the construct problem.

**1.6 — Smallholder access to formal markets.** FAO's Smallholder Farmers' Data Portrait distinguishes market location and formal/informal contract or channel characteristics. It does not establish a universal national “access” percentage or five maturity cuts. SDG 2.3 recognizes market and financial-service access as enabling conditions but its official indicators measure productivity and income, not this rate. [FAO Smallholder Farmers' Data Portrait](https://www.fao.org/family-farming/detail/ar/c/1111162/), [FAO SDG 2.3 indicators](https://www.fao.org/sustainable-development-goals-data-portal/data/indicators/average-income-of-small-scale-food-producers-by-sex-and-indigenous-status/sdg-2-indicators-of-productivity-and-income-of-small-scale-food-producers/)

**Disposition:** higher is directionally better only after “access,” “smallholder,” “formal,” denominator, and reference period are fixed. Hold all cuts pending 13.5 and a surveyable national construct.

**1.7 — Agricultural credit access.** The World Bank's Enabling the Business of Agriculture methodology measures laws, regulations, bureaucratic processes, and regulatory good practices for accessing finance. It is a 0–100 regulatory composite, not the percentage of farmers with credit access. [World Bank EBA methodology](https://eba.worldbank.org/en/methodology)

**Disposition:** higher actual farmer access is directionally better, but “access,” “use/borrowing,” “beneficiary,” “formal provider,” farmer versus household denominator, and recall period must be fixed first. No official source found supports either cut set.

**1.8 — Farmers using climate-smart practices.** World Bank/FAO climate-smart agriculture frameworks assess productivity, resilience/adaptation, and mitigation, and emphasize that suitable practices depend on agroecological and socioeconomic context. The World Bank indicator framework separates policy, technology, and results indicators rather than defining a universal percentage of farmers using any practice. [World Bank Climate-Smart Agriculture Indicators](https://documents1.worldbank.org/curated/en/187151469504088937/pdf/105162-WP-P132359-PUBLIC-CSAIndicatorsReportweb.pdf), [World Bank CSA overview](https://www.worldbank.org/en/topic/climate-smart-agriculture)

Counting any named practice makes higher adoption appear better even where the practice basket is not locally appropriate or does not produce the intended triple win. The Egypt proxy was wheat area under one practice, the Nigeria evidence was farmer adoption in two zones, and Bhutan used an estimated broad share.

**Disposition:** do not ratify even the generic higher-is-better direction until the eligible practice basket, qualification test, denominator, and geography are fixed. Then calibrate against a defined adoption construct, not the phrase “climate-smart.”

**8.5 — Women who own land.** Official SDG 5.a.1 contains two different sub-indicators: (a) the share of the agricultural population with ownership or secure rights, by sex; and (b) the share of women among owners or rights-bearers. The current DAMM name combines ownership language with a “% holders” denominator and therefore does not uniquely select either construct. [UN SDG 5.a metadata page](https://unstats.un.org/sdgs/metadata?Goal=5&Target=5.a), [official SDG 5.a.1 metadata PDF](https://unstats.un.org/sdgs/metadata/files/Metadata-05-0a-01.pdf)

**Disposition:** hold direction and thresholds until 13.5 selects 5.a.1(a), 5.a.1(b), or a national agricultural-holder statistic. If 5.a.1(b) is selected, the 50% top anchor can be interpreted as parity/saturation, but the lower 10/25/40 cuts remain unsupported and the reference population must be recorded.

## 5. Distributional stress test for the five global series

To test whether the current cuts silently approximate global quintiles, the most recent non-null 2022–2025 WDI observation was taken for each non-aggregate economy, using the official WDI API. Quantiles are unweighted across economies and linearly interpolated. This is a sensitivity diagnostic, not an endorsed calibration method.

| Row | n | Raw-value q20 / q40 / q60 / q80 | Current L1 / L2 / L3 / L4 / L5 counts |
|---|---:|---:|---:|
| 1.1 value added per worker | 172 | 1,917 / 4,014 / 11,378 / 27,314 | 15 / 29 / 30 / 25 / 73 |
| 1.2 cereal yield | 179 | 1,534 / 2,421 / 3,768 / 5,369 | 35 / 52 / 42 / 23 / 27 |
| 1.3 employment in agriculture | 186 | 2.78 / 9.18 / 23.61 / 41.63 | 29 / 31 / 32 / 39 / 55 |
| 1.4 food production index | 195 | 97.61 / 102.72 / 111.51 / 122.29 | 33 / 55 / 48 / 38 / 21 |
| 8.1 prevalence of undernourishment | 166 | 2.5 / 3.1 / 7.0 / 16.8 | 14 / 23 / 27 / 40 / 62 |

Example API query: [WDI `NV.AGR.EMPL.KD`, 2022–2025](https://api.worldbank.org/v2/country/all/indicator/NV.AGR.EMPL.KD?format=json&date=2022:2025&per_page=20000). The other series use the same query with `AG.YLD.CREL.KG`, `SL.AGR.EMPL.ZS`, `AG.PRD.FOOD.XD`, and `SN.ITK.DEFC.ZS`.

The current cuts do not generate equal-frequency bands. Row 1.1 places 42% of observed economies in L5. Row 8.1 places 37% in L5; all 62 observations in that level are published as 2.5, the numeric representation used for the `<2.5` lower-bound category. That pile-up is censoring, not evidence that all those estimates are exactly 2.5.

If the method owners choose distributional calibration, the record must freeze the series version, country universe, observation-selection rule, date range, weights, missing-data rule, quantile algorithm, outlier treatment, and update cadence. Performance-order quintile cuts for a lower-is-better row must be reversed. A recut must not happen automatically when the live API revises history.

## 6. Score polarity, directionality, and edge behavior

### 6.1 “Need” is not the direction of the level

A1 is described as a need profile, yet its levels run from worse conditions to better conditions: higher productivity, yield, market/credit access, and inclusion, and lower agricultural employment, loss, and hunger produce higher levels. The pillar is therefore an **adequacy / lower-unmet-need score**, not a severity score.

That inversion should be explicit in data, for example:

```json
{
  "reading_role": "need_baseline",
  "score_polarity": "higher_level_means_lower_unmet_need"
}
```

Without it, a consumer can reasonably but incorrectly interpret a high A1 score as high need.

### 6.2 Current numeric boundary semantics

The workbook, `model/reference_scorer.py`, and `gauntlet/loop-1/engine_v17.py` use inclusive upgrades. With higher-is-better cuts `t1 < t2 < t3 < t4`:

- L1: `x < t1`
- L2: `t1 <= x < t2`
- L3: `t2 <= x < t3`
- L4: `t3 <= x < t4`
- L5: `x >= t4`

With lower-is-better cuts `t1 > t2 > t3 > t4`:

- L1: `x > t1`
- L2: `t2 < x <= t1`
- L3: `t3 < x <= t2`
- L4: `t4 < x <= t3`
- L5: `x <= t4`

Thus an observation exactly at any cut upgrades to the higher performance level. This is coherent and monotone, but the current schema description—“level = 1 + how many are met”—does not state the comparison operators or interval closure. It also cannot express an official interval such as PoU L1 `x >= 35` and L2 `20 <= x < 35`, because the lower-is-better `<=35` mechanic promotes exact 35 into L2.

### 6.3 Censored observations

FAO/WDI's displayed `2.5` for PoU can mean `<2.5`, not an exact estimate. The current scorer cannot distinguish those cases. It happens to place numeric 2.5 in L5 under the test cuts, but that coincidence is not sound measurement semantics.

Store the observation as an inequality:

```json
{
  "value": {
    "kind": "upper_bound",
    "bound": 2.5,
    "inclusive": false
  }
}
```

The interval scorer can then conclude that `<2.5` belongs in the best PoU category without claiming the country equals 2.5.

### 6.4 Stored-level bypass and the required regression contract

In the committed baseline inspected during this research, `model/reference_scorer.py` used an explicit observation `level` whenever the key existed, and the engine defined `tlevel()` without applying it in `run()`. Because country observations carry stored levels, changing a cut could therefore leave an old level silently in force. A `level: null` key also bypassed derivation, although null is intentionally used as a construct/ratification hold.

During the Issue 2 engineering containment, both scoring boundaries were changed so
non-null Measured levels are re-derived, null holds remain null, and stale-level/hold
regression cases are enforced. This note does not implement those changes; it records why
Decision 13.6 should make the behavior a permanent cross-implementation release
requirement:

- a non-null stored level on a Measured threshold row is an auditable cache, never an independent input;
- the current value and active calibration always derive the effective level;
- a deliberate null hold remains null until explicitly released;
- any retained cached level that differs from the derived level is surfaced as an error or migration diff, never silently trusted.

The best A1 golden cases are already present in the lineage: Egypt 1.3 must rederive L4→L3, Nigeria 1.3 L3→L2, Bhutan 1.7 L1→L2, and Bhutan 8.1 L1→L2 when the active calibration changes.

## 7. Proposed machine-readable provenance

Bare arrays should become a generated legacy projection, not the canonical calibration. Keep sources normalized in one registry and let each indicator reference one versioned calibration record.

```json
{
  "calibration_sources": {
    "FAO-POU-CATEGORIES-2001": {
      "publisher": "Food and Agriculture Organization of the United Nations",
      "title": "Assessment of the World Food Security Situation",
      "url": "https://www.fao.org/4/Y0006E/Y0006E00.htm",
      "accessed_on": "2026-08-26",
      "content_sha256": null,
      "locator": "Prevalence categories",
      "source_type": "official_classification"
    }
  },
  "threshold_calibrations": {
    "A1-8.1-FAO-POU-CATEGORIES-v1": {
      "indicator_id": "8.1",
      "construct_id": "FAO-SDG-2.1.1-POU",
      "definition_decision": "13.5",
      "calibration_decision": "13.6",
      "status": "proposed",
      "unit": "percent_of_total_population",
      "reading_role": "need_baseline",
      "score_polarity": "higher_level_means_lower_unmet_need",
      "direction": "lower-is-better",
      "intervals": [
        {"level": 1, "lower": {"value": 35, "inclusive": true}, "upper": null},
        {"level": 2, "lower": {"value": 20, "inclusive": true}, "upper": {"value": 35, "inclusive": false}},
        {"level": 3, "lower": {"value": 5, "inclusive": true}, "upper": {"value": 20, "inclusive": false}},
        {"level": 4, "lower": {"value": 2.5, "inclusive": true}, "upper": {"value": 5, "inclusive": false}},
        {"level": 5, "lower": null, "upper": {"value": 2.5, "inclusive": false}}
      ],
      "basis": {
        "kind": "official_classification",
        "source_ids": ["FAO-POU-CATEGORIES-2001"],
        "method": "Reverse official severity categories into DAMM performance levels",
        "reference_universe": null,
        "reference_period": null,
        "snapshot_id": null,
        "quantile_method": null,
        "transform": null,
        "rationale": "Proposed crosswalk; official category vintage still requires approval"
      },
      "supersedes": {
        "calibration_id": null,
        "legacy_thresholds": [25, 15, 7.5, 2.5]
      },
      "validation_fixture_ids": ["EGY-8.1", "NGA-8.1", "BTN-8.1"],
      "approval": {
        "method_owner": null,
        "status": "pending",
        "approved_on": null,
        "record_ref": null
      },
      "created_on": "2026-08-26"
    }
  },
  "indicator_calibration_refs": {
    "8.1": "A1-8.1-FAO-POU-CATEGORIES-v1"
  }
}
```

This 8.1 object illustrates the structure; it is not an instruction to ratify that vintage. Other allowed `basis.kind` values should be constrained to `normative_target`, `distributional`, `expert_judgment`, or `hybrid`. Each type has required fields:

- `official_classification`: publisher, document/version, exact category text, locator;
- `normative_target`: issuing authority, target, target year, and rule translating one target into five levels;
- `distributional`: frozen dataset checksum, universe, period, weights, missing-data and outlier rules, and quantile method;
- `expert_judgment`: named method owner/panel, dated rationale for every cut, conflicts considered, and review date;
- `hybrid`: each component above plus the combination rule.

Country observations must remain outside the model. Calibration records may reference immutable fixture IDs for validation, but must not embed or learn from country assessment data. An approved calibration is immutable; recuts create a new ID and a migration diff.

## 8. Required validation tests

### Schema and governance

1. **Calibration coverage:** every threshold indicator has exactly one calibration reference, construct ID, unit, direction, score polarity, status, and basis.
2. **Source resolution:** every `source_id` resolves; URLs are deep links; accessed date and checksum/snapshot are present where reproducibility requires them.
3. **Definition dependency:** a calibration cannot become `approved` or `ratified` while its governing 13.5 construct decision is open.
4. **Approval dependency:** `thresholds_ratified` must agree with the referenced calibration status and approval record. Production release fails if any A1 row points to a proposed calibration.
5. **Single canonical representation:** interval objects are canonical; any four-number legacy array is generated and parity-tested, never independently edited.

### Mathematical behavior

6. **Partition:** each calibration contains exactly five exhaustive, contiguous, non-overlapping intervals with explicit closures.
7. **Order:** legacy-compatible H cuts are strictly ascending and L cuts strictly descending; duplicate or unsorted cuts fail validation.
8. **Exact edges:** golden tests assert the expected level at every boundary, immediately below, and immediately above using `nextafter` or decimal-safe equivalents.
9. **Monotonicity:** property tests over random finite values prove levels never decrease as H values rise and never decrease as L values fall.
10. **Invalid values:** null, NaN, infinity, malformed strings, and unit-mismatched values never receive a threshold level.
11. **Censoring:** `<2.5`, exact `2.5`, and `>2.5` are distinct observations and exercise the intended intervals.

### Cross-implementation parity and migration

12. **Workbook/scorer/engine parity:** the spreadsheet, reference scorer, engine, and application fixtures produce identical effective levels at all A1 edges.
13. **Explicit-level bypass regression:** for a Measured row, inject a deliberately stale non-null stored level and prove all implementations rederive it. Inject an explicit null hold and prove all preserve the hold.
14. **A1 recut goldens:** assert the four lineage changes exactly: Egypt 1.3 L4→L3, Nigeria 1.3 L3→L2, Bhutan 1.7 L1→L2, Bhutan 8.1 L1→L2.
15. **Full migration diff:** a calibration version change reports every country row, old/new level, pillar mean, band, and margin. No cached level may survive silently.
16. **Construct guards:** series ID, constant-price base, index base period, denominator, geographic scope, and reference population must match the calibration. A proxy or prose range cannot enter the Measured threshold path.
17. **Status/hold behavior:** a Gap or explicit ratification hold always has no effective level, whatever its value or cached level.
18. **Reproducible distribution:** when `basis.kind` is distributional, recomputing from the frozen snapshot must reproduce every cut exactly.
19. **No case fitting:** Egypt, Nigeria, and Bhutan fixtures are evaluated only after cuts are produced. A calibration build must not read them as training inputs.
20. **Unseen-country gate:** after the definition and calibration freeze, rerun Egypt and Nigeria and then validate one genuinely unseen, human-shadowed country before claiming production calibration.

## 9. Ratifiability matrix

| ID | Construct/direction supported now | Current cuts supported | Calibration basis to take forward | Required approval before ratification |
|---|---|---|---|---|
| 1.1 | Exact WDI series and H polarity, conditional on rename/unit | No | Frozen distribution of the exact constant-price series, potentially stratified by income/structure; never a live-API percentile | Method owner selects strata, quantile rule, and base-year policy after comparability review |
| 1.2 | Exact WDI/FAO series and H polarity | No | Prefer an agroecology-normalized/yield-gap construct; if raw yield is retained, use frozen peer strata rather than one global distribution | 13.5 construct choice plus agriculture/statistics review of crop mix and agroecology |
| 1.3 | Exact WDI/ILO series; L only as an explicit structural-transformation interpretation | No | Hybrid of frozen distribution and signed structural-transformation judgment; do not present modeled estimates as a country ranking | Domain owner approves the interpretation, reference universe, and numeric method |
| 1.4 | Exact WDI/FAO relative index; H only as growth from fixed base | No | Normative deviations from the fixed 100 base, with an explicit rebasing and volatility policy; distributional ranks are not substantively meaningful | Method owner decides whether this relative index belongs in maturity scoring and approves the bands |
| 1.5 | Lower loss is directionally desirable | No | Official FLI or harmonized commodity-loss construct first, then frozen distribution/target on that exact measure | 13.5 construct plus food-loss statistician; rate/index, stages, basket, aggregation |
| 1.6 | H conditional on a fixed access construct | No | Harmonized national survey measure, calibrated from a frozen eligible-country distribution and/or explicit policy target | 13.5 definition plus survey/market specialist and national measurement design |
| 1.7 | H conditional on a fixed access construct | No | Harmonized national survey measure, calibrated from a frozen distribution and an explicit formal-access target | 13.5 definition plus rural-finance measurement specialist |
| 1.8 | Not yet; “any CSA practice” is not a stable positive construct | No | Locally qualified practice basket and adoption target; if no comparable global basket exists, keep it local rather than force global cuts | 13.5 practice basket and CSA/domain approval before direction or cuts |
| 8.1 | Exact FAO PoU construct and L polarity | No; official-category recut is the strongest candidate | An approved FAO category vintage, reversed into DAMM performance levels with explicit half-open intervals and censor semantics | Method owner selects the category vintage/crosswalk and approves interval behavior |
| 8.5 | Not until 5.a.1(a), 5.a.1(b), or another holder construct is selected | No | Official SDG construct plus a normative equality/parity or secure-rights target, with saturation stated explicitly | 13.5 decision plus gender-and-land statistician; denominator and parity/saturation rule |

## 10. Recommended decision path

1. **Do not ratify or silently preserve the current arrays.** Keep all ten `thresholds_ratified` flags false.
2. **Approve the calibration contract and tests first.** This is method infrastructure and does not prejudge a numeric answer.
3. **Close 13.5 dependencies before local-row calibration.** Rows 1.5–1.8 and 8.5 cannot be calibrated while their numerator, denominator, geography, or construct is unsettled.
4. **Choose one calibration family per row.** Prefer official classifications where they exactly match; then explicit normative targets; then a frozen, reproducible distribution. Use expert judgment only with named approval and cut-by-cut rationale.
5. **Prepare a one-page calibration card per row.** It should include exact construct, source, direction, five intervals, basis, global distribution diagnostic, the three country sensitivity cases, and proposed review cadence.
6. **Route the ten cards for joint method-owner confirmation.** Domain/statistical specialists should sign the rows identified above; their approval is methodological, not merely editorial.
7. **Version, migrate, and rerun.** Once approved, create immutable calibration IDs, generate the legacy arrays/workbook, report the full score diff, rerun Egypt and Nigeria, and execute the unseen-country gate.

The evidence supports a disciplined route to ratification. It does not support treating inherited round numbers, historical country levels, or a generic claim of international benchmarking as the calibration basis.

## Primary-source register

- World Bank WDI metadata: [`NV.AGR.EMPL.KD`](https://databank.worldbank.org/metadataglossary/world-development-indicators/series/NV.AGR.EMPL.KD), [`AG.YLD.CREL.KG`](https://databank.worldbank.org/metadataglossary/world-development-indicators/series/AG.YLD.CREL.KG), [`SL.AGR.EMPL.ZS`](https://databank.worldbank.org/metadataglossary/world-development-indicators/series/SL.AGR.EMPL.ZS), [`AG.PRD.FOOD.XD`](https://databank.worldbank.org/metadataglossary/world-development-indicators/series/AG.PRD.FOOD.XD).
- FAO: [SDG 2.1.1 PoU](https://www.fao.org/sustainable-development-goals-data-portal/data/indicators/2.1.1-prevalence-of-undernourishment/2/en), [historical PoU prevalence categories](https://www.fao.org/4/Y0006E/Y0006E00.htm), [2026 SOFI launch statement](https://www.fao.org/director-general/speeches/details/launch-of-the-state-of-food-security-and-nutrition-in-the-world-%28sofi%29-2026-report-statement/en), [food-loss measurement](https://www.fao.org/platform-food-loss-waste/food-loss/food-loss-measurement/), [SDG 12.3.1a](https://www.fao.org/sustainable-development-goals-data-portal/data/indicators/1231-global-food-losses), [smallholder data portrait](https://www.fao.org/family-farming/detail/ar/c/1111162/), [SDG 2.3 indicators](https://www.fao.org/sustainable-development-goals-data-portal/data/indicators/average-income-of-small-scale-food-producers-by-sex-and-indigenous-status/sdg-2-indicators-of-productivity-and-income-of-small-scale-food-producers/).
- World Bank: [Enabling the Business of Agriculture methodology](https://eba.worldbank.org/en/methodology), [Climate-Smart Agriculture Indicators](https://documents1.worldbank.org/curated/en/187151469504088937/pdf/105162-WP-P132359-PUBLIC-CSAIndicatorsReportweb.pdf), [CSA overview](https://www.worldbank.org/en/topic/climate-smart-agriculture).
- United Nations Statistics Division: [SDG 5.a metadata page](https://unstats.un.org/sdgs/metadata?Goal=5&Target=5.a), [SDG 5.a.1 metadata PDF](https://unstats.un.org/sdgs/metadata/files/Metadata-05-0a-01.pdf).
