# DAMM v1.5 — Process Guide

Digital Agriculture Maturity Model · Diagnostic package workflow · Companion to the DAMM-v1.5-Scoring-Workbook

August 2026

---

## What this guide is for

DAMM v1.5 produces a **diagnostic package** — a standardised evidence pack that the Task Team Leader (TTL) and team use as input to offline DAR drafting. The workbook does not attempt to draft the DAR. The workflow has four steps: three automated, one offline.

This guide walks through those four steps, explains what each artefact is for, and specifies what is handed to the TTL at the end.

---

## What changed from v1.4

Three structural changes and one naming change.

**Naming**
- "Anchored rubric" → "Qualitative indicator." The two variants become "Qualitative (capability)" and "Qualitative (evidence quality)."
- "Level Anchors" sheet → "Qualitative Anchors."
- Column labels: "Machine L (auto)" → "Machine level (proposed)"; "Assessor L" → "Assessor level"; "Effective L" → "Effective level."

**Process**
- The 8-rung Decision Ladder (T0 → D6) is retired. It is replaced by a 4-step Process Ladder.
- The government mandate no longer gates the workbook. It gates the DAR. Steps 1–3 run on public evidence at any time and produce an internal Bank diagnostic package. The DAR proper is drafted offline after the mandate.
- The workbook produces a single output artefact — the Diagnostic Package — which is handed to the TTL for offline DAR drafting.

**Structure**
- A new **Diagnostic Package** sheet renders the output the TTL actually reads: three read-outs, provisional stage, core-gate audit, pillar snapshot, evidence quality index, top 15 binding constraints, refresh list, verify list, TTL guidance.
- The pillar count stays at 8. Pillar codes (C0/C1/C2/C3/C4/E1/E2/O1) remain internally; plain-language pillar names ("Connectivity & access", "Data & DPI", "Policy & safeguards", "People & institutions", "Innovation ecosystem", "AI & emerging tech", "Outcomes & inclusion", plus the C0 context profile) appear on the Diagnostic Package.

Everything else — 102 indicators, 14 core gates, CMS/EMS/OES read-outs, non-compensatory cascade, coverage suppression, confidence weighting, staleness flagging, non-overlapping bands — is preserved.

---

## The four-step process

### Step 1 — Populate indicators

**Executor:** Machine, with assessor input on qualitative indicators.
**Output:** A populated country sheet — 102 indicators with value, source name, source URL, observation year.

Populate all 102 indicators in the country sheet (duplicate `Blank Template` and rename to the country name).

For each row, record:

- **Value.** The observed data point (numeric for quantitative indicators; narrative for qualitative indicators).
- **Machine level (proposed).** For quantitative indicators, this is set automatically by the numeric threshold rule on the `Indicators` sheet. For qualitative indicators, the machine may propose a level from public documents; the assessor level always wins.
- **Assessor level.** For qualitative indicators, the assessor reads the L1–L5 anchor on the `Qualitative Anchors` sheet and picks the level that best matches the evidence. Leave blank to mark a Data Gap.
- **Confidence.** High / Medium / Low / Data Gap. Weighting: High=1.0, Medium=0.6, Low=0.3, Data Gap=0.
- **Observation year.** The year the underlying data point refers to.
- **Source name and URL.** Every reading must be traceable to a specific document.

**Rule.** Quantitative indicators are cheap — a lookup. Qualitative indicators are the slow ones — they require judgement. The workbook contains 52 qualitative indicators and 50 quantitative indicators; expect the qualitative rubrics to consume more than half of Step 1 time.

**Convention on qualitative indicators.** The machine may propose a level from public evidence, but it does not have enough context to score qualitative indicators reliably. Every qualitative reading is treated as *requires validation* by default. The assessor must confirm it during Step 1 before it lands on the Diagnostic Package.

### Step 2 — Score evidence quality

**Executor:** Machine (automated). No human input.
**Output:** Evidence Quality Index per pillar; Refresh list; Verify list.

Once Step 1 is complete, the workbook automatically computes evidence quality across five underlying concepts, rolled up into one index:

1. **Confidence.** Per-reading tag (High/Medium/Low/Data Gap), weighted in the adequacy calculation.
2. **Staleness.** Automatic flag if the observation year is older than the indicator's max-age limit (2 or 3 years depending on the indicator).
3. **Coverage.** Share of indicators in a pillar that carry an effective level. Must clear 60% for pillar to be rated. CMS needs 70%; EMS needs 60%.
4. **Weighted evidence adequacy.** A single number combining confidence and coverage across a read-out. Must clear 0.5 for the read-out to stand.
5. **Core-gate audit.** How many of the 14 prerequisite indicators are at Level 1 (caps stage at 1) or unmeasured (suppresses stage).

These five feed two output lists:

- **Refresh list.** Every reading that is Stale, or at Low confidence. Drives desk-research and mission-verification planning.
- **Verify list.** Every reading that is a Data Gap, and every unmeasured core gate. Must be resolved before the DAR is finalised.

Both lists are rendered on the Diagnostic Package sheet.

### Step 3 — Compile diagnostic package

**Executor:** Machine (automated).
**Output:** The Diagnostic Package (PDF, single artefact handed to the TTL).

The `Diagnostic Package` sheet renders live from the country sheet. It contains, in order:

1. **Headline read-outs.** CMS, EMS, OES with coverage, score, band.
2. **Provisional stage.** Overall stage from the non-compensatory cascade, with the provisional-and-may-be-overridden caveat.
3. **Core-gate audit.** Count of core gates at L1, unmeasured, and ≥L3.
4. **Pillar snapshot.** Per-pillar coverage, mean level, and band.
5. **Evidence Quality Index.** Weighted evidence adequacy, overall coverage, stale readings count, data gaps count, foundation-vs-ecosystem gap.
6. **Top binding constraints.** Auto-ranked top 15 indicators by ascending level with core-gate flag.
7. **Refresh list.** All stale and low-confidence readings.
8. **Verify list.** All data gaps and unmeasured core gates.
9. **Guidance for the TTL.** Short standing notes on how to use the package.

Export the sheet to PDF. This is the single artefact handed to the TTL.

### Step 4 — Draft the DAR offline

**Executor:** TTL and team, post-mandate.
**Output:** The DAR.

The TTL and team draft the DAR offline, after the government mandate, drawing on the Diagnostic Package as evidence. This workbook is an input to that process, not part of it.

Under this framing:

- The Diagnostic Package is watermarked "Provisional — pre-mandate, for TTL and team use."
- The stage on the package is provisional. The TTL may accept or override it during offline drafting. If overridden, the override rationale goes into the DAR methodology chapter.
- The government engages with the DAR when the DAR is a DAR — after adoption. What the government sees before adoption is the DAR draft under the standard DAR methodology, not the Diagnostic Package.

---

## What the Diagnostic Package tells the TTL

The Diagnostic Package answers seven questions in a single document:

| Question | Where it's answered |
|---|---|
| What is this country's provisional maturity? | Sections 1–2 (Headline read-outs, Provisional stage) |
| Are the prerequisites in place? | Section 3 (Core-gate audit) |
| Where is capability concentrated? | Section 4 (Pillar snapshot) |
| How much do I trust the evidence? | Section 5 (Evidence Quality Index) |
| What are the binding constraints? | Section 6 (Top 15 auto-ranked) |
| What must I refresh before finalising? | Section 7 (Refresh list) |
| What data gaps must I close? | Section 8 (Verify list) |

Section 9 restates the TTL's brief in one page: this is an input, not the DAR; qualitative indicators require validation; the stage is provisional; the mandate gates the DAR, not the diagnostic.

---

## Naming and vocabulary

**Qualitative indicators.** Indicators scored 1–5 against a written anchor paragraph per level rather than a numeric threshold. The `Qualitative Anchors` sheet contains the anchor text. Roughly 52 of the 102 indicators are qualitative.

**Quantitative indicators.** Indicators scored 1–5 against a numeric threshold (higher-is-better or lower-is-better). The threshold values live on the `Indicators` sheet. Roughly 50 of the 102.

**Core gates.** 14 prerequisite indicators that behave non-compensatively. If any core gate is at Level 1, the overall stage is capped at Stage 1 regardless of scores elsewhere. If any core gate is unmeasured, the overall stage is suppressed entirely.

**Coverage.** Share of a pillar's indicators that carry an effective level. Below the pillar-specific coverage gate, the pillar reads "Not rated."

**Confidence.** Per-reading tag (High / Medium / Low / Data Gap) with weights 1.0 / 0.6 / 0.3 / 0.

**Staleness.** A reading is stale if its observation year is older than the indicator's max age (2 or 3 years).

**CMS / EMS / OES.** Capability Maturity Score (weighted mean of pillars C1–C4), Ecosystem Maturity Score (weighted mean of E1–E2, weights 70/30), Outcome Effectiveness Score (mean of O1). Never averaged into a single number.

**Provisional stage.** The stage computed by the non-compensatory cascade. Provisional because the TTL may accept or override it during offline DAR drafting.

**Diagnostic package.** The single output artefact of this workbook, handed to the TTL as input to offline DAR drafting.

**Requires validation.** The default tag on every qualitative indicator until the assessor has confirmed the level.

---

## The Egypt worked example

The Egypt sheet in the workbook is a complete worked example. Key figures from the current populated draft (August 2026, pre-mandate):

**Read-outs**
- CMS = 3.07 (Established), coverage 98%
- EMS = 2.90 (Established), coverage 96%
- OES = 2.41 (Emerging), coverage 100%

**Provisional stage:** Stage 2 — Capability building.

**Core gates:** 0 at Level 1; 0 unmeasured; 12 of 14 at ≥ Level 3.

**Evidence quality**
- Weighted evidence adequacy: 0.57 (just clears the 0.5 floor)
- Stale readings: 16
- Data gaps: 2
- Foundation-vs-Ecosystem gap: 0.92 (below the 1.5 leapfrog-fragility threshold — no flag)

**The story the Diagnostic Package tells the TTL for Egypt.** Capability and ecosystem sit at Established; outcomes lag at Emerging. Foundations are laid — rural coverage, cybersecurity legal framework, data protection law, digital ID, inter-ministerial coordination, national AI strategy with ag component, agri-fintech rails accessible to smallholders. The binding constraints are concentrated in People & institutions (C4) — digital literacy among farmers, gender balance in the digital-agriculture workforce, extension training reach — and in Outcomes & inclusion (O1) — women's land ownership, climate advisory reach, gender-disaggregated adoption.

Before drafting, the TTL should refresh the 16 stale readings (several are 2015–2022 rural-connectivity, gender, and land-ownership figures), close the 2 data gaps, and validate the qualitative readings that currently sit at Low confidence.

---

## What the workbook explicitly refuses to do

The prohibitions from v1.3 and v1.4 stand:

- No cross-country ranking. The bands and stages are diagnostic categories, not league-table positions.
- No DAMM stage used as PDO indicator, DLI, or disbursement condition.
- No automatic financing, procurement, vendor, or technology decisions from the diagnostic.
- No stage claimed publicly before human review by the TTL and steering committee.

---

## Handoff to the TTL

At the end of Step 3, the deliverable to the TTL is a single PDF export of the `Diagnostic Package` sheet, plus the workbook itself as the auditable artefact. The DAR is drafted under separate methodology.

The TTL's checklist on receiving the package:

1. Read the headline read-outs and provisional stage. Sanity-check against country knowledge.
2. Read the core-gate audit. Any core gate at Level 1 or unmeasured is a red flag that must be addressed before the DAR is drafted.
3. Scan the pillar snapshot. Identify the two or three lowest-scoring pillars — these are the DAR's strategic priorities.
4. Read the binding constraints list. Filter by pillar to build chapter-specific weakness sections.
5. Read the Refresh list. Plan desk research and mission verification against it.
6. Read the Verify list. Data gaps must be closed before the DAR is finalised.
7. Read the qualitative indicators marked "requires validation." These are the readings that need a human eye before they land in the DAR narrative.

Everything else in the workbook — Config, Qualitative Anchors, Core Gates methodology, Indicators census — is back-office plumbing that the TTL consults only when they want to audit a specific score.

---

## Version history

- **v1.0 (2026).** Initial framework. 8 pillars, 97 indicators, 4 layers, 5 levels. Overlapping bands. Hardcoded scores.
- **v1.1 (July 2026).** Red-team corrections. Live formulas throughout. Non-overlapping bands. Data Confidence Index. Data Gap vs Nascent distinction. Rebuilt investment matrix.
- **v1.3 (August 2026).** Restructured as config file for external app. Role families (C0 context, C1–C4 capability, E1–E2 ecosystem, O1 outcome). Three read-outs introduced. Core-gate cap and coverage suppression. Evidence staleness. Decision ladder. Prohibitions wired in. Removed live scoring.
- **v1.4 (August 2026).** Restored live-scoring workbook. 102 indicators. E1/E2 weights rebalanced to 70/30. New E1 core gate. Egypt worked example. Blank Template. Full dashboard.
- **v1.5 (August 2026, this version).** Simplified process, clearer language. Anchored rubrics → qualitative indicators. Level Anchors → Qualitative Anchors. 8-rung Decision Ladder → 4-step Process Ladder. New Diagnostic Package sheet as single TTL-facing output. Column labels rewritten for readability. Scoring engine, 102 indicators, 14 core gates, CMS/EMS/OES, coverage suppression, staleness flagging, non-compensatory cascade all unchanged.
