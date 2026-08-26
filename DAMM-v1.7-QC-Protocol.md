# DAMM v1.7 — Quality Control Protocol

One page · 22 August 2026 · Companion to `DAMM-v1.7-Specification.md` §9 · Review items in spec §13.8

> **Normative workflow supersession — 26 August 2026.** For orchestration and lifecycle,
> `workflow/DAR-CANONICAL-WORKFLOW.md` and `workflow/dar-workflow-v1.json` supersede
> conflicting timing in this protocol. The eight-stage run requires no human action or budget
> top-up after launch. Optional documents are frozen before launch and otherwise use autonomous
> fallback. Stage 1 retains an independent automated challenge. G1, G2, and G3 occur only after
> Stage 8: they may revise a Draft and control promotion to Final or publication, but they are
> not prerequisites for Draft generation. The four prohibitions remain unchanged.

**Design stance.** Quality control is layered into the instrument, the autonomous eight-stage
run, and post-completion sign-off — it is not a stage appended at the end. Machines enforce
active-run checks; humans review judgment after the Draft package exists; the report itself
states which checks ran.

## Layer 1 — Structural (by construction; runs on every assessment, cannot be skipped)

The rules of evidence are the first QC layer: a level cannot exist without a recorded value, source, and year; the evidence class is derived from the value and cannot be chosen; a gap must be searched and named to be recorded; staleness derives from the observation year; prerequisites bind on presence only and show **Unverified** when unevidenced; weak-evidence bands render parenthesized by majority rule; source tiers are reported, never weighted; and no narrative claim can set a level. Each rule removes a class of error rather than detecting it.

## Layer 2 — Automated (every render; emit-blocking)

The renderer runs these checks and **refuses to emit a report on any failure**; the result is stated in the report footer. Stage 1 also runs the independent automated evidence challenge before scoring and rendering. That challenge is part of Draft generation and is distinct from post-completion human G2.

| # | Check |
|---|---|
| A1 | Every row with a level carries value + source + year; no level on a gap |
| A2 | Class↔value consistency: numeric → Measured · citation → Documented · statement → Judged · "DATA GAP" → Gap |
| A3 | Every Gap row carries its search trail |
| A4 | Staleness flag matches the 3-year rule for every non-Gap row |
| A5 | Reconciliation: class counts, pillar n's, and layer n's sum to 57; matrix has exactly the six columns |
| A6 | Prerequisite and matrix statuses draw only from their defined vocabularies |
| A7 | Tier lookup applied to every machine-fetched row; register rows all carry a tier; T5 rows carry no results tier |
| A8 | Engine↔workbook parity suite (60 checks) passes at workbook migration and after any formula change |
| A9 | Presentation: acronyms and codes explained at point of use (never tooltip-only); both themes render; palette validation on any new chart colors; print CSS present; no horizontal page overflow |
| A10 | Citations: Documented rows carry resolvable deep links with access dates; ≥10 links spot-resolved per assessment; T4–T5 links archived |

## Layer 3 — Post-completion human review and publication controls

**G1 — Machine-pass confirmation** (assessor, after Stage 8): review every machine-filled row in the completed Draft package; confirm or correct value, source, year, and tier; accept each recorded gap or re-search it. Output: a versioned review record and, where changed, a revised Draft. G1 never pauses the active run.

**G2 — Peer review** (a second reviewer, not the assessor, after G1 and after Stage 8): re-check **100% of prerequisite rows and 100% of Judged rows**, plus a **15% sample of the remainder** — does the source resolve, is the class correctly derived, is the ladder level justified at the quality/scale rungs? Disagreements are logged and resolved by evidence, not seniority; an unresolvable row honestly reverts to Judged or Gap. This human control must not be confused with Stage 1's automated challenge. (Proportionality: on the Nigeria pass this is 12 prerequisite + 8 Judged rows plus ~6 sampled — hours, not days.)

**G3 — TTL sign-off** (before promotion to Final or publication): a recorded checklist — the four prohibitions hold; parenthesized bands are acknowledged in the transmittal; register rows are verified to the Source-Tier Protocol or explicitly marked illustrative; the QC footer line is accurate. Sign-off (name, date) is recorded in the review record. This control operationalizes prohibition 4: *no public claim before human review*. It does not block creation or internal review of the Draft package.

## The issues log

Every QC finding — automated failure, G2 disagreement, G3 exception — is appended to an **Issues sheet** (finding · row · action · resolver · date). Fixes change **entries** (value, source, year); derived fields are never edited directly. The log ships inside the workbook, not beside it.

## Cadence

Automated checks and the independent challenge run during Draft generation · G1 once after each completed Draft package · G2 after G1 and after any batch of reviewed entry changes · G3 before Final promotion or publication, repeated on material revision.
