# DAMM v1.7 — Quality Control Protocol

One page · 22 August 2026 · Companion to `DAMM-v1.7-Specification.md` §9 · Review items in spec §13.8

**Design stance.** Quality control is layered into the instrument, the pipeline, and the sign-off — it is not a stage appended at the end. Machines enforce what can be enforced; humans gate what requires judgment; the report itself states which checks ran.

## Layer 1 — Structural (by construction; runs on every assessment, cannot be skipped)

The rules of evidence are the first QC layer: a level cannot exist without a recorded value, source, and year; the evidence class is derived from the value and cannot be chosen; a gap must be searched and named to be recorded; staleness derives from the observation year; prerequisites bind on presence only and show **Unverified** when unevidenced; weak-evidence bands render parenthesized by majority rule; source tiers are reported, never weighted; and no narrative claim can set a level. Each rule removes a class of error rather than detecting it.

## Layer 2 — Automated (every render; emit-blocking)

The renderer runs these checks and **refuses to emit a report on any failure**; the result is stated in the report footer.

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

## Layer 3 — Human gates

**G1 — Machine-pass confirmation** (assessor, after Step 1's machine pass): review every machine-filled row; confirm or correct value, source, year, tier; accept each recorded gap or re-search it. Output: an initialed workbook.

**G2 — Peer review** (a second reviewer, not the assessor, before the first internally circulated render): re-check **100% of prerequisite rows and 100% of Judged rows**, plus a **15% sample of the remainder** — does the source resolve, is the class correctly derived, is the ladder level justified at the quality/scale rungs? Disagreements are logged and resolved by evidence, not seniority; an unresolvable row honestly reverts to Judged or Gap. (Proportionality: on the Nigeria pass this is 12 prerequisite + 8 Judged rows plus ~6 sampled — hours, not days.)

**G3 — TTL sign-off** (before anything leaves the team): a recorded checklist — the four prohibitions hold; parenthesized bands are acknowledged in the transmittal; register rows are verified to the Source-Tier Protocol or explicitly marked illustrative; the QC footer line is accurate. Sign-off (name, date) is recorded in the workbook Read Me. This gate operationalizes prohibition 4: *no public claim before human review*.

## The issues log

Every QC finding — automated failure, G2 disagreement, G3 exception — is appended to an **Issues sheet** (finding · row · action · resolver · date). Fixes change **entries** (value, source, year); derived fields are never edited directly. The log ships inside the workbook, not beside it.

## Cadence

G1 once per machine pass · automated checks on **every** render (idempotent) · G2 before first internal circulation and after any batch of entry changes · G3 before any external eyes, repeated on material revision.
