# DAMM v1.7 — Specification (draft for review)

Digital Agriculture Maturity Model · 21 August 2026 · Status: **draft, pre-decision**
Companion: `DAMM-v1.7-Indicator-Census.csv` (per-indicator disposition of all 102 v1.5 indicators, with the Egypt and Bhutan evidence behind each decision)

> **Normative workflow supersession — 26 August 2026.** This specification remains
> authoritative for the DAMM instrument. For DAR orchestration and artifact lifecycle,
> `workflow/DAR-CANONICAL-WORKFLOW.md` and `workflow/dar-workflow-v1.json` supersede
> conflicting process statements below. The canonical run has eight stages, with separate AI
> and digital-agriculture assessment and investment-options/cost-benefit analysis stages.
> Optional documents must be supplied and frozen before launch; absence invokes autonomous
> fallback. No human confirmation, upload, retry choice, or budget top-up is required during an
> active run. The independent automated challenge remains in Stage 1; G1, G2, and G3 are
> post-completion review/publication controls. Draft generation is allowed before review;
> promotion to Final and publication are not. The four prohibitions in §11 remain unchanged.

---

## 1. What v1.7 is

v1.7 re-founds the model on a single design authority: the **DAR Playbook (World Bank / Gates Foundation / BCG, 2025)**. The Playbook defines the roadmap the model serves — five steps: Diagnostic assessment → Use case prioritization → Vision → Roadmap development → Implementation planning. DAMM's job within it is precise and bounded: it delivers the **desk-assessment core of Step 1** — 1A problem statement, 1B landscape register, 1C ecosystem maturity — and supplies **Step 2B's Digital Readiness and Impact criteria** and **Step 3C's KPI baseline**. Consultation and validation remain the mission's work; the model does not attempt more.

The whole method in five lines:

1. **Every indicator gets a value, a source, and a year — or a recorded gap.** No level may exist without a recorded value.
2. **What was recorded sets the evidence class:** a number → *Measured*; a citable artifact → *Documented*; neither → *Judged*; a looked-for-and-not-found result → *Gap*. The class is derived, never chosen.
3. **Pillars report a band and their evidence composition.** No pillar weights, no read-out arithmetic, no overall score, no stage.
4. **Prerequisites bind on presence only** — a fact, never an opinion. Three are universal; the rest block specific use-case columns.
5. **Every indicator names the use case areas and DAR steps it serves.** 57 of v1.5's 102 survive that test.

## 2. Relation to the source documents

| Source | What v1.7 takes from it |
|---|---|
| **DAR Playbook (2025)** | The output structure. Every diagnostic-package section is named to the Playbook step it feeds (§9). Use-case taxonomy: ADV advisory & extension · SMF smart farming · MKT market linkage & pricing · SCM supply chain · FIN financial services · AGI agricultural intelligence. |
| **DAMM v1.5 workbook** | The indicator stock (pruned 102→57, IDs preserved), non-overlapping bands, the four prohibitions, country data isolation, the Egypt worked example as evidence. |
| **Bhutan DAR Assessment (Mar 2026)** | Proof that 100% value coverage is achievable (97/97 rows carry value+source+year+confidence). The four-layer structure (Foundation / Enablers / Transformation / Outcomes), restored here. The demonstration that "qualitative" indicators can carry recorded evidence. Its single overall score (2.29) is **not** adopted — v1.5's refusal to average across families stands. |
| **BCG/SAID 2.0 (2020)** | The redundancy principle: SAID screened 50+ indicators and found the differentiating ones few and highly correlated. v1.7's merge decisions are evidenced the same way — indicators that move together in both Egypt and Bhutan are one indicator (census, columns G–H). |

## 3. The indicator record

One row per indicator. Fields, in entry order:

| Field | Rule |
|---|---|
| **Value** | Mandatory. A number, a citation ("PDPL Law 151/2020, in force"), or a recorded gap ("DATA GAP — searched FAO, MoA, NSO 2026-08"). A blank Value voids the row: **no level without a recorded value.** |
| **Source, Year** | Mandatory with the value. Provenance and vintage are entry-time fields, not audit-time discoveries. |
| **Source tier** | **Derived where machine-fetched (domain lookup), recorded otherwise.** T1 official statistics & IO databases · T2 peer-reviewed & IO flagship reports · T3 government legal/policy/budget artifacts · T4 reputable grey literature (GSMA, GIZ, donor evaluations) · T5 news, vendor and market material. **Reported, never weighted** — the tier appears in the evidence panel and ledger ("Documented · T4") and never enters arithmetic; weighting tiers would rebuild the confidence weights v1.7 removed. T5 is admissible only in the initiative register (§9), for existence facts. Full rules: `DAMM-v1.7-Source-Tier-Protocol.md`. |
| **Evidence class** | **Derived, not entered.** Numeric value → `Measured` · citation from an admissible source (T1–T4) → `Documented` · assessor statement without artifact → `Judged` · recorded gap → `Gap`. Replaces the High/Medium/Low confidence tag and its 1.0/0.6/0.3/0 weights entirely — the class cannot contradict the value because it comes from the value. A citation whose only source is T5 derives `Judged`, not `Documented` — admissibility is part of the rule, since T5 may never carry a scored value (loop-1 ruling). |
| **Level (1–5)** | From the numeric threshold (Measured) or the shared ladder (§6). **A level is withheld where the recorded evidence measures a materially different construct from the one the indicator names and the level would turn on that difference.** The row keeps its value, source and tier and carries its open question; it asserts no score. A withheld level is not an absence: a prerequisite so recorded reads `Unverified`, never `Absent`. Sub-readings (absorbed indicators, disaggregations) are recorded beneath the level, not averaged into it. |
| **Staleness** | Derived: observation year older than **3 years → Stale** (one rule for all indicators; replaces the per-indicator 2/3-year table — Egypt's 16 "stale" readings said more about the limits than the country). |
| **Use-case areas · DAR steps · Prerequisite flag · Layer** | Fixed per indicator in the census; not per-assessment entries. |

## 4. Structure: 7 pillars × 4 layers

**Pillars (57 indicators).** C0 is promoted to a scored pillar and E2 dissolves into E1 (AI is a lens on solutions, not a sector of its own — in both worked examples it mostly measured absence):

| Pillar | n | Was |
|---|---|---|
| A1 Agriculture & need | 10 | C0 (8, unscored) + 8.1, 8.5 moved in |
| C1 Connectivity & access | 6 | 11 |
| C2 Data & DPI | 8 | 13 (3.9, 3.10 moved to E1) |
| C3 Policy & safeguards | 8 | 13 |
| C4 People & institutions | 7 | 14 |
| E1 Innovation, solutions & emerging tech | 11 | E1 (14) + E2 (12) + 3.9, 3.10 |
| O1 Outcomes & inclusion | 7 | 17 |

**A1 is scored but interpreted as need, not digital maturity.** It writes the roadmap's "why digital, here" chapter (Playbook 1A) and the impact side of use-case prioritization (2B). A low A1 is a large opportunity, not a poor performance.

**Layers (restored from Bhutan/v1.1):** Foundation 16 · Enablers 26 · Transformation 8 · Outcomes 7. Layers are a reading lens — a profile, never an aggregation with weights.

**The leapfrog flag, finally defined** (v1.5 carried the constant but no computation): `gap = mean level(Foundation) − mean level(Transformation)`. **|gap| > 1.5** raises a flag; the sign is the finding. Positive (Foundation ahead): *unrealized foundations — ecosystem investment can move fast.* Negative (Transformation ahead): *leapfrog fragility — services are running ahead of the rails they stand on.* Bhutan computes +1.26 (no flag, foundations ahead); Egypt +0.92 (no flag).

## 5. Pillar bands and the evidence panel

- **Pillar band** = unweighted mean of its indicators' levels, banded on the v1.5 half-open edges (stated, per the v1.5 lesson that bare numbers get misread): Nascent [1, 1.8) · Emerging [1.8, 2.6) · Established [2.6, 3.4) · Advanced [3.4, 4.2) · Transformative [4.2, 5].
- **Evidence panel**, always beside the band: *n Measured / Documented / Judged / Gap · n Stale*. 
- **Low-evidence rendering:** when Judged + Gap outnumber Measured + Documented, the band renders parenthesized — e.g. "(Emerging)". A majority rule, not a tuned threshold. This **replaces** the 60% coverage gate, the 70%/60% CMS/EMS gates, and the 0.5 adequacy floor. The v1.5 distinction it preserved — *a low score is a finding about the country; weak evidence is a finding about the assessment* — survives in the rendering, with the arithmetic gone.
- **Rounding is half-up**, to two decimals, matching the workbook (which is the source of truth). Banker's rounding disagrees with it at exact `.xx5` values, and a pillar mean landing on a band edge would otherwise band differently in the instrument and the report.
- **Removed entirely:** CMS/EMS/OES (and the unresolved Effectiveness-vs-Equity naming), pillar weights (25/30/25/20, 70/30), stage floors (S2–S5), the non-compensatory cascade, the overall stage. The executive read-out is the pillar profile in prose: *"Foundations Established; outcomes Emerging; evidence thin in E1."*

## 6. Scoring non-measured indicators: one shared ladder

v1.5's 44 qualitative indicators carried five anchor paragraphs each; **35 of the 44 were the same template with the indicator name substituted in** (grammar breaking on substitution). v1.7 formalizes what was actually there — one ladder, asked in stages:

1. **Presence** — Absent / Announced / Adopted / Operating. Factual, citable, always answerable.
2. **Quality** — asked only if Adopted or Operating: governance, funding, institutionalization. *(Absorbed indicators land here: responsible-AI practice is the quality rung of 4.6; interoperability quality of 3.5; agency maturity of 5.7.)*
3. **Scale** — asked only if Operating: coverage and reach, with the indicator's own scale metric. *(6.14 keeps its bespoke thresholds: ≥15% L4, ≥40% L5 of farming households.)*

Level derivation, stated: Absent → 1 · Announced → 2 · Adopted → 3 · Operating + quality → 4 · Operating + quality + scale + evidence of use → 5.

The **9 bespoke anchor sets** (3.6, 6.14, 7.9→4.2 note, 7.10/7.11→7.12, 7.12, 8.12/8.13, 8.16→8.9) are retained as indicator-specific quality/scale guidance — the layer the boilerplate never had. Writing more of them, prerequisites first, is the standing improvement path.

## 7. Prerequisites (replaces the 14 core gates)

Gate power without evidence was v1.5's inversion: 10 of its 14 gates carried no recorded value in Egypt. v1.7 narrows the power and demands the evidence:

- **Universal (3):** 2.1 rural coverage · 2.9 rural electricity · 4.1 data protection law. Absence blocks every use-case column.
- **Use-case prerequisites (7):** 3.3 farmer registry → FIN, AGI · 3.11 interoperability → AGI · 4.5 ag data governance → AGI · 4.7 digital ID → FIN · 5.5 digital extension → ADV · 6.14 agri-fintech rails → FIN · 7.12 consent & data rights → all AI-enabled services.
- **Delivery-risk flags (2):** 4.9 coordination mechanism · 5.7 MoAg digital unit — flagged on the package cover, blocking nothing.

**Two binding rules, ratified in the loop-1 gauntlet and open for confirmation (§13.9):** (i) **7.12 binds AGI** — the consent-and-rights prerequisite is written "all AI-enabled services", which named no column and therefore bound nothing; it now gates the agricultural-intelligence column. (ii) **A universal prerequisite at `Present (narrow)` caps every column at `Partial`** — absence blocks, but narrow presence must not read as ready: Nigeria otherwise showed advisory and smart-farming *Ready* on 23.5% rural electricity.

A **universal prerequisite recorded as `Unverified`** returns every use-case column as `Unverified` — the symmetric treatment already given to use-case prerequisites. A *known* blocker outranks an unknown one, so a column with a named absent prerequisite still reads `Blocked`.

**Binding is on presence only** (rung 1 of the ladder) — "there is no data protection law" is a fact that can cap ambition; "the law is quality 2" is an opinion that must not. A prerequisite whose presence is unevidenced shows **Unverified** in the matrix — it cannot silently pass or fail. Nothing caps a global stage, because there is no stage to cap: a failed prerequisite blocks its column in the readiness matrix, which is where sequencing decisions actually live.

## 8. What was removed, and what answers its question now

| v1.5 mechanism | Its question | v1.7 answer |
|---|---|---|
| CMS / EMS / OES + weights | Where is capability concentrated? | Pillar profile with bands |
| Stage floors + cascade + provisional stage | How mature overall? | The pillar profile sentence; no integer |
| 14 core gates capping the stage | What must exist first? | §7 prerequisites per use-case column |
| Confidence tags + weights + adequacy ≥ 0.5 | Do I trust this? | Derived evidence class + panel + majority rendering |
| Coverage gates 60/70/60% | Is the pillar rateable? | Evidence panel + parenthesized band |
| Per-indicator max-age 2/3 yrs | Is it current? | One rule: stale beyond 3 years |
| Leapfrog constant (uncomputed) | Is progress fragile? | §4 gap, computed, both directions |

Five mechanisms deleted, none of their questions orphaned.

## 9. The Diagnostic Package, restructured to feed the Playbook

The package renders as a single per-country report in **two registers, visibly distinct**: *scored rows* (levels from recorded values only) and *researched narrative* (prose with tier-badged citations, drawn from the tiered search protocol). **The firewall between them is one rule: no narrative claim ever sets a level.** Narrative cites the scored rows; the scored rows never cite the narrative. This is the discipline that separates the package from fluent-but-unverifiable AI desk reports (see the August 2026 ARI comparison — the failure mode is prose resting on sources that do not resolve).

| § | Section | Feeds |
|---|---|---|
| 1 | **Country problem statement** — A1 profile: the agricultural constraints digital must answer | Playbook 1A |
| 2 | **Initiative & solutions register** — the landscape, structured (below) | **1B landscape** |
| 3 | **Pillar profile** — 7 bands + evidence panels | 1C |
| 4 | **Layer profile** — 4 layers + leapfrog/unrealized flag | 1C |
| 5 | **Use-case readiness matrix** — rows: prerequisites & key enablers; columns: ADV SMF MKT SCM FIN AGI; cells: Ready / Partial / **Blocked (named blocker)** / Unverified | **2B Digital Readiness** — the criterion the Playbook names |
| 6 | **Impact side** — A1 constraints × use-case areas that address them | 2B Impact |
| 7 | **Binding constraints** — indicators ascending by level, prerequisite-flagged | 2B, 4A |
| 8 | **Strategic questions** — derived, not authored (below) | Step 2 agenda |
| 9 | **Evidence ledger** — refresh list (Stale), verify list (Judged + Gap prerequisites) | mission planning |
| 10 | **KPI baseline** — every Measured A1/O1 row with value, source, year | **3C results framework** |

§5 is the capability v1.5 could not produce at all, and it is the view Step 2 consumes. §10 makes the diagnostic the DAR's M&E baseline for free.

**§2 The initiative & solutions register.** One row per initiative, government or private: *Initiative · Lead & partners · Use-case areas (ADV/SMF/MKT/SCM/FIN/AGI) · Status on the presence ladder (Announced / Adopted / Operating) · Scale (reach, in the initiative's own unit) · Funding & model · Results evidence (with tier) · Overlap flags · Source (tier, access date).* Rules: (i) status uses §6's presence rung — the register is the presence ladder applied to the landscape; (ii) T4–T5 sources are admissible for **existence facts only** — that an initiative exists, launched, or closed; results and impact claims require T1–T3; (iii) register rows may serve as the Documented evidence behind E1/C4 indicator values — cite the row. The register is where the worked examples were thinnest (Nigeria machine pass: E1/C4 heavy in Judged and Gap), and it is the section that converts them.

**§8 Strategic questions.** Derived mechanically, then curated by the TTL (cap ~12): every **Blocked** cell → *what would it take to clear [named blocker] for [use case]?* · every **Unverified** prerequisite → a verification question for the mission · each prerequisite-flagged binding constraint → a sequencing question · a raised leapfrog flag → the fragility (or unrealized-foundations) question. Authored additions are permitted but marked as such.

**The report is a standalone document.** It carries no process history — no prior passes, no internal cross-references (section numbers, method filenames), no assessment archaeology of any kind. A counterpart reads one document, and the pipeline runs one pass. Text authored by research agents (register entries, notes, search trails) is sanitized before it reaches the page, because that text will always carry such traces.

**Context rules (bounded).** Two kinds of outside context may appear in the report, both tightly bounded. (i) Measured threshold indicators render with **reference values** — the same T1 series read for the world and the peer set — beside the country value: context, never scored, never averaged, carrying their own source and year. (ii) A strategic question may carry at most one **precedent pointer**: a tier-badged citation showing that its blocker has been cleared elsewhere — an existence proof, marked as a pointer, never an endorsement and never a comparison of countries. Pointers draw on the **Global Practice Library** (`DAMM-v1.7-Practice-Library-Schema.md`), the standing, country-agnostic companion; per-country relevance is a join on the readiness matrix and prerequisite patterns, not authored benchmarking. The full practice review is a Step 2 product (the Precedents note, ≤10 entries, 3–5 pages), deliberately outside the diagnostic.

**Quality control.** Three layers, specified in `DAMM-v1.7-QC-Protocol.md`: **structural** — the §3–§7 rules, enforced by construction; **automated** — Stage 1's independent evidence challenge plus render-time checks on consistency, provenance, reconciliation and presentation, where the renderer refuses to emit on failure and states the result in the report footer; and **post-completion human controls** — G1 assessor review of the completed Draft package · G2 peer review of every prerequisite row and every Judged row · G3 TTL sign-off before Final promotion or publication. None of G1–G3 is an active-run dependency or a prerequisite for Draft generation.

## 10. Disposition of the v1.5 handoff defects

1. OES naming (Effectiveness vs Equity) — **moot**, OES removed. 2. Qual/quant count discrepancy — **superseded** by derived classes; the census is the count. 3. Egypt sheet titled v1.4 — **workbook fix at migration**. 4. `leapfrog_gap` uncomputed — **defined and computed** (§4). 5. Numbers without semantics — every constant in this spec carries its meaning inline; the config must too.

And the six handoff questions: 102 right-sized? → 57. Qualitative half proportionate? → class is derived; the ladder cuts assessor cost for weak countries. E1/E2 70/30 validated? → moot, weights removed. 14 gates non-compensatory in spirit? → 3+7+2, presence-only. Staleness limits realistic? → one 3-year rule. Narrative values scoreable? → the ladder scores them; the ratio-style prose case (5.6) is now a scale rung, not an orphan.

## 11. Constraints that survive unchanged

The four prohibitions (no cross-country ranking; no stage — now no *band* — as PDO/DLI/disbursement condition; no automatic financing decisions; no public claim before human review). Country data isolation. *A gap that has been looked for and named is not a blank* — Gap is a recorded class. Coverage suppression **changes mechanism** (§5) but keeps its meaning; this is the one deliberate departure from the handoff's must-survive list, flagged for review.

## 12. Application ripple (dar-studio-v2)

| Change | Touches |
|---|---|
| 45 indicators removed/merged; A1 scored; 4 moves | `model_v1_5.json` → `model_v1_6.json` via extractor; `sources.ts`; fixtures |
| Classes replace confidence | Entry UI, `scoring.ts`, adequacy code deleted |
| Readiness matrix + layer profile + leapfrog | New engine outputs (leapfrog was already typed, never computed) |
| Stages/read-outs/weights/coverage gates deleted | `scoring.test.ts` re-pinned; Diagnostic Package sheet re-rendered |
| Shared ladder | `Qualitative Anchors` sheet becomes ladder + bespoke guidance; `researchableRubrics()` filter strings |
| Source tier field | Workbook Scoring sheet gains a Tier column at migration (derived for machine rows via domain lookup; recorded otherwise); evidence ledger and panel render it |
| Initiative register + strategic questions | New renderer sections (register store per country; questions derived from matrix + constraints at render time); report template `v1.6-report-template/` is the reference rendering |
| Reference values + precedent pointers | REFS map for T-indicators and per-question pointer field in the renderer; `practice-library.json` store joins on the matrix at Step 2 |
| Automated QC | Stage 1 independent challenge plus `qc_checks()` in the renderer — emit-blocking; result stated in the report footer; post-completion G1/G2/G3 review records bind any revised Draft, Final promotion, or publication |
| Workbooks rebuilt at v1.7 | Three files (blank template, Egypt, Nigeria): Source URL and Tier entry columns, Tiers and Issues sheets, gate sign-off block, both matrix rulings in formula. Verified 512/512 against the engine, zero formula errors. The v1.6 workbooks are superseded and must not ship. |

Workbook remains source of truth for DAMM scoring. The canonical DAR workflow is: **1** DAMM diagnostic, including tiered research, automated challenge, engine and report → **2** country research/source inventory → **3** AI in digital agriculture assessment → **4** international strategies/lessons → **5** strategic foresight → **6** investment options and cost-benefit analysis → **7** integrated Draft DAR → **8** export package. Optional documents are immutable pre-launch inputs and otherwise trigger autonomous research. The active run never waits for G1/G2/G3 or a budget top-up; reviewed corrections create a new post-completion version.

## 13. Open for review (Katreyna + Randeep)

Everything that could be corrected without a design ruling **has been corrected** and is recorded in §14. What remains below are design choices — the places where the model rests on judgment rather than on evidence, and where an outside reading is worth more than another internal one.

1. **Band edges** kept at 1.8 / 2.6 / 3.4 / 4.2 — recut now that nothing downstream consumes them, or keep for continuity?
2. **A1 additions.** Both candidates were fetched as unscored rows and now sit visibly beneath the register in each workbook: cereal import dependency **42.8%** (Egypt) against **16.3%** (Nigeria), and irrigation **94.2%** of cultivated area against **0.3%** of agricultural land (Nigeria's stale at 2017). Add both and hold A1 at 12, or hold at 10? The irrigation denominator needs fixing either way (item 5).
3. **The per-use-case prerequisite mapping (§7)** — still the substantive judgment most worth external eyes.
4. **The three binding rules now in force**, each settled during testing and each material: 7.12 gating the agricultural-intelligence column; a universal prerequisite at narrow presence capping every column at `Partial`; a universal prerequisite at `Unverified` returning every column `Unverified`. Ratify, or vary.
5. **Indicator definitions — the largest item.** An audit of all 57 rows found **44 of them carrying an open definitional question**, with one further question on the irrigation candidate row — 45 questions in all, but 44 of the 57. By the instrument's own classification: 6 name a construct their evidence does not measure, 30 record a defensible but measurably different proxy, and 9 leave a unit or denominator unfixed. Every one is attached to its own row in the scoring workbook, in the column *Open definition question*, so each can be ruled in place. **8 of the 12 prerequisites are among them.**
6. **A1 thresholds** are still carried as test values. Both worked examples are scored against them; ratify or recut.
7. **Sub-readings display**: beneath the level (proposed) or as separate rows.
8. **The source-tier lookup and register field set** — confirm the tier assignments, in particular where a national statistical office with known quality issues sits, and whether a donor project completion report is T2 or T4.
9. **The QC Protocol** — confirm the post-completion placement and scope of human G1/G2/G3, and note the amendment §14 records: peer review must ask whether evidence answers *this* indicator, not only whether the source states the number. Stage 1's automated challenge remains part of Draft generation and is not human G2.
10. **The Practice Library schema** — entry fields, the prerequisite-pattern join, and the ≤10-entry cap on the Step 2 Precedents note.
11. Bhutan is out of scope for this release (that assessment served a delivered project). Its role as a design *source* in §2 stands; no re-render ships.
12. **Whether need and outcome indicators belong in a use-case readiness mean.** Each use-case column averages every indicator mapped to it, and that set is not purely enabling: it carries A1 rows, which measure the *severity of the agricultural problem*, and O1 rows, which measure *achieved outcomes*. Usually the effect is small. In one place it is decisive: Nigeria's market-linkage column reads **2.58** with them and **2.64** without — either side of the 2.6 readiness threshold — and it is the only column in either worked example whose status turns on the mean rather than on a prerequisite. On the current mapping, a country with a *worse* agricultural problem reads as *less* digitally ready, which inverts the intended meaning. Split the mapping into readiness, impact and KPI roles, or keep one bearing set and accept the coupling? Nothing has been changed pending the ruling; both means are now printed in the readiness matrix so the difference is visible, and the three A1 rows that carry a use-case tag are recorded as such in the census.

## 14. Corrections applied before release

These were defects, not decisions, and were fixed rather than referred. Each is reproducible from source: the corrections are input files, not edits to generated artifacts.

| # | What was wrong | What was done |
|---|---|---|
| 1 | Egypt's **2.1** recorded the ITU *national* coverage figure against an indicator naming *rural* coverage, scored Measured at level 5. It is a universal prerequisite, so five columns read `Ready` on evidence that did not measure the thing named — and the caveat sat in a note the engine never reads | Recorded as the gap it is, with the national figure retained as context. Egypt's five columns now read `Unverified`, which is what the evidence supports |
| 2 | **Six rows named a construct their evidence did not measure** (2.1, 3.5, 4.7, 5.3, 5.7, 8.5) | Levels withheld where the level turned on the difference; evidence and source retained; the open question attached to the row |
| 3 | **4.7** recorded Egypt on ID ownership among adults and Nigeria on registrations over total population — two denominators in one instrument | Both re-sourced onto the same ID4D series and denominator (Egypt 98.8%, Nigeria 79.1%, adults 15+, 2024) |
| 4 | An **`Unverified` universal prerequisite passed silently**, contradicting §7's own words | Engine and workbook both now return every column `Unverified`, with a known blocker outranking an unknown one |
| 5 | An **unrated prerequisite fell through to `Absent`** in the engine — asserting absence where nothing was asserted (the workbook was already correct) | Engine aligned to the workbook and to §7 |
| 6 | Engine and workbook **rounded differently at exact `.xx5`**, so a mean on a band edge could band differently in instrument and report | Engine rounds half-up, matching the workbook |
| 7 | The scoring sheet could not express *measured but deliberately unrated* | A **Ratification hold** column; the level formula honours it |
| 8 | The **QC review lens** verified that a source states a number but never that the number answers the indicator — which is how defect 1 passed peer review | Recorded as an amendment to the QC Protocol (§13.9) |
| 9 | A **pillar mean was published against the pillar's full indicator count**, while the mean itself averaged only the rated rows. Rows on ratification hold stayed inside their evidence class in the composition figures but contributed no level, so Egypt's C4 read `3.33` over an apparent seven rows when three produced it, and Nigeria's O1 read `3.25` on four of seven | Engine, workbook and report now publish **Rated** and **Held** beside `n`, and the count of rated rows travels with every mean |
| 10 | The **weak-evidence flag could not fire on a pillar hollowed out by holds** — it compared judged and gap rows against measured and documented ones, and a held row counted on the strong side | Recut: judged, gap *and* held rows are weighed against the levelled measured and documented ones. Egypt's C4 now renders parenthesized, which is what its evidence supports |
| 11 | The **PDF cropped the two rightmost columns off the initiative register** — Overlaps and Source, the register's entire provenance — because the on-screen horizontal scroll has nothing to scroll into on paper. The caption beneath still promised a deep link per entry | Print stylesheet lays wide tables out to the page and wraps instead of overflowing; a build-time check now fails the package if any register column is missing from the PDF text |
| 12 | The **Verify-first list carried a Judged row only when that row was a prerequisite**, so a country with a non-prerequisite Judged row published a list shorter than its own caption ("Judged rows and recorded gaps") — Nigeria showed 4 where 5 qualified | Every Judged row and every recorded gap is listed; an invariant checks the count against the class totals |
| 13 | **"45 of 57" overstated the definitional audit.** 44 of the 57 scored rows carry an open question; the 45th sits on the irrigation candidate row, which is not one of the 57 | Corrected here, in the transmittal and in the census; the classification is now restated from the instrument's own severity field |
| 14 | Two **stale version labels** survived the v1.6→v1.7 relabel inside the report itself — the impact-crosswalk caption and the method box | Both now read v1.7 |
| 15 | The **standalone-text sanitizer reached only top-level string fields**, leaving the register's use-case tags, the narrative blocks and indicator value prose unsanitized — which is why British spellings survived in a document whose invariant is American spelling. Separately, the spelling rules ran over **URLs**, where two live citations contain the very strings the rules rewrite | Sanitizer now walks lists and nested values; URLs and proper names are shielded before any rule runs, so a citation can no longer be silently rewritten |


---

*Version history: v1.6 (Aug 2026, never circulated) — indicator census 102→57 with two-country evidence per decision; Playbook made design authority; A1 scored; layers restored and leapfrog defined; stages, read-outs, weights, confidence weights, coverage arithmetic and per-indicator staleness removed; evidence classes derived from mandatory values; shared qualitative ladder; prerequisites per use case, presence-only. Revised after the ARI desk-report comparison: Diagnostic Package extended 8→10 sections (initiative register feeding Playbook 1B; derived strategic questions feeding Step 2); two-register report with the narrative firewall; source tiers on the record; bounded context rules; layered quality control. **v1.7 (this draft)** — the version that survived the loop-1 gauntlet, a clean-slate re-assessment of Egypt and Nigeria under one process, with historical G1 and G2 review passes executed and twenty-eight defects logged before the canonical post-completion sequence was adopted. Changes: evidence class made tier-aware; 7.12 bound to AGI; universal prerequisites at narrow presence capping columns at Partial; half-up rounding to match the workbook; the standalone-report rule; workbooks rebuilt with Source URL, Tier, Tiers and Issues sheets and the gate sign-off block. Scoring machinery otherwise untouched. Released after an all-row indicator audit: six rows whose names outran their evidence corrected, 45 open definitional questions attached row-by-row to the instrument (44 of them on the 57 scored rows), and five engine or workbook defects fixed. Revised again after external design review: the mean's own denominator published beside it, the weak-evidence flag recut to count withheld levels, the print layout repaired so no table loses columns on paper, the Verify-first list aligned to its caption, the text sanitizer extended to nested values with URLs shielded, and a twelfth decision opened on whether need and outcome indicators belong in a readiness mean (§13.12, §14). Prior history in DAMM-v1.5-Process-Guide.md.*
