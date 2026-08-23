# DAMM v1.7 — Source-Tier Protocol

One page · 22 August 2026 · Companion to `DAMM-v1.7-Specification.md` §3 (tier field) and §9 (two-register report)

**Why it exists.** The August 2026 ARI comparison (Egypt + Nigeria AI desk reports) showed the failure mode this protocol prevents: ~150–200 sources per report with no hierarchy — FAO flagships beside SEO content farms and scraped page code — and citations that do not resolve (domain-root URLs). Breadth without hierarchy is decoration. DAMM's rule is the reverse: **fewer sources, each resolvable, each tiered.**

## The tiers

| Tier | What | Examples | Admissible for |
|---|---|---|---|
| **T1** | Official statistics & IO databases | FAOSTAT, AQUASTAT, WDI, ITU DataHub, Global Findex, ASTI, FSIN/IPC, DHS/LSMS, national statistical office releases | Any claim; the default for every number |
| **T2** | Peer-reviewed literature & IO flagship/analytical reports | Journal articles, systematic reviews, World Bank/FAO/IFPRI/CGIAR flagships, evaluated impact studies | Any claim; **required** for impact and effectiveness claims |
| **T3** | Government legal, policy & budget artifacts | Gazetted laws, adopted strategies, budgets, regulator reports (e.g. NCC), official program documents | Presence facts (the ladder's rung 1), policy intent, program design — *not* outcomes |
| **T4** | Reputable grey literature | GSMA, GIZ/USAID/AGRA/donor reports and evaluations, established industry analyses | Context and sector narrative, flagged as T4; presence facts where T3 is silent |
| **T5** | News, vendor & market material | Press, startup/vendor sites, market-research releases, blogs | **Initiative register only, existence facts only** (an initiative exists, launched, raised, closed). Never statistics, never impact. |

## The rules

1. **Search order per indicator:** API/T1 first (19 of 57 are machine-fetchable), then T2 → T3 → T4, stop when found. A dead end is recorded as the Gap value with its search trail ("DATA GAP — searched FAOSTAT, FMAFS, NBS 2026-08").
2. **Triangulation:** a load-bearing number (anything quoted in the problem statement, matrix, or KPI baseline) needs two independent T1–T2 confirmations, or ships flagged *single-source*.
3. **Resolvability:** every citation is a deep link to the document, with access date. T4–T5 links get an archived copy (Wayback) at capture time. A citation that resolves only to a domain root is not a citation.
4. **Tier is reported, never weighted.** It renders in the evidence panel and ledger ("Documented · T4") and in narrative citation badges. It never enters level or band arithmetic — weighting tiers would rebuild the confidence weights v1.7 removed.
5. **The narrative firewall (spec §9):** researched narrative may cite any tier under these rules; **no narrative claim ever sets a level.** Levels come from recorded values only.
6. **Vintage beats tier at the margin:** a 2024 T2 estimate outranks a 2017 T1 figure for the *narrative*; the *scored row* records the T1 figure and its staleness honestly, and the ledger routes it for refresh.

## Starter domain→tier lookup (machine rows; §13.6 to confirm)

`fao.org / faostat / aquastat / worldbank.org / data.worldbank.org / itu.int / ifad.org / wfp.org / findex` → T1 · `openknowledge.worldbank.org / cgiar.org / ifpri.org / doi.org / nature.com / sciencedirect / springer / frontiersin` → T2 · `*.gov.* / *.go.* / faolex / official gazettes / regulator domains (e.g. ncc.gov.ng)` → T3 · `gsma.com / giz.de / usaid.gov / agra.org / reliefweb.int` → T4 · everything else → T5 until reviewed.

**Open judgment calls (flag for Katreyna, spec §13.6):** national statistical offices with documented quality concerns (row-by-row, not blanket demotion); donor project completion reports (T2 if independently evaluated, T4 otherwise); Wikipedia and encyclopedias (not citable at any tier — follow their references instead).
