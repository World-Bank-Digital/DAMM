# DAMM refinement — handoff note

*Written 2026-08-20 to open a new thread focused on refining the maturity
model itself, not the application that runs it. Read this first; it carries
the current state, the defects already found, and the questions worth
deciding.*

## Where DAMM lives

| Artefact | Path | Role |
|---|---|---|
| **Scoring workbook (source of truth)** | `DAMM/DAMM v1.5 Scoring Workbook — Egypt worked example.xlsx` | The methodology. Live formulas, Egypt worked example, Blank Template. |
| **Process guide** | `DAMM/DAMM-v1.5-Process-Guide.md` | The four-step workflow and vocabulary. |
| **App configuration** | `~/Projects/dar-studio-v2/src/data/model_v1_5.json` | What the software scores against. **Generated, never hand-edited.** |
| **Extractor** | `~/Projects/dar-studio-v2/scripts/extract-damm.py` | Workbook → config. A version bump is a re-run of this. |
| **Guidebook + workbook builders** | `~/Projects/dar-studio-v2/scripts/build-damm-guidebook.js`, `build-damm-workbook.py` | Regenerate the review documents from the config. |
| **Review documents** | `~/Projects/dar-studio-v2/exports/DAMM-v1.5-Guidebook.docx`, `DAMM_v1.5_as_implemented.xlsx` | Sent to Katreyna Schroeder for feedback. |

**The rule that keeps these honest:** every downstream artefact is generated
from the config, and the config is generated from the workbook. Change the
workbook, re-run `extract-damm.py`, re-run the two builders. Never edit the
JSON by hand — it will silently diverge from the methodology.

```
python3 scripts/extract-damm.py "<workbook.xlsx>" src/data/model_v1_5.json
python3 scripts/build-damm-workbook.py
node scripts/build-damm-guidebook.js
```

## What v1.5 is, in numbers

- **102 indicators**, 8 pillars, **14 core gates**, 3 read-outs (CMS/EMS/OES), 5 levels, 4 process steps.
- **Methods:** 50 quantitative thresholds · 42 qualitative (capability) · 2 qualitative (evidence quality) · 8 context profiles.
- **Sourcing:** 27 Global (an API can fetch them) · **75 Local** (no global series exists).
- **Staleness limits:** 63 indicators at 2 years · 39 at 3 years.
- **Pillar sizes:** C0 8 · C1 11 · C2 13 · C3 13 · C4 14 · E1 14 · E2 12 · O1 17.
- **Weights:** capability C1 25 / C2 30 / C3 25 / C4 20 · ecosystem E1 70 / E2 30 · outcome O1 100. Each family sums to 1.
- **Stage floors:** S2 CMS 2.6 · S3 CMS 3.4 + EMS 2.6 · S4 CMS 4.2 + EMS 3.4 + OES 2.6 · S5 CMS 4.5 + EMS 4.2 + OES 3.4.
- **Coverage gates:** pillar 60% · CMS 70% · EMS 60% · evidence adequacy 0.5.
- **Confidence weights:** High 1.0 · Medium 0.6 · Low 0.3 · Data Gap 0.

v1.5 is a clean **superset of v1.3**: all 97 v1.3 indicators retained, five
added (3.13 open ag data, 5.13 extension gender parity, **6.14 agri-fintech
rails — a new core gate**, 8.16 gender-disaggregated adoption, 8.17 climate
advisory reach), none removed or renumbered.

## Defects already found — fix these in the workbook

1. **OES is named two different things.** The Process Guide says "Outcome
   **Effectiveness** Score"; the workbook's own Glossary says "Outcome &
   **Equity** Score". The guidebook follows the workbook. Pick one.
2. **The qualitative/quantitative count in the guide is wrong.** The guide
   says "52 qualitative / 50 quantitative", which only reconciles if the 8
   context profiles are counted as qualitative. The workbook's own Indicators
   sheet says 44 qualitative + 8 context. This matters because it inflates the
   assessor-effort estimate by about a fifth.
3. **The Egypt sheet is still titled "Egypt — DAMM v1.4 assessment."** Cosmetic
   but it will be circulated.
4. **`leapfrog_gap` (1.5) is defined but never computed.** It is in the config
   and typed in the application, but nothing calculates the foundation-minus-
   transformation gap or raises the flag. Either specify how it is computed —
   which pillars constitute "foundation" and which "transformation" — or drop it.
5. **v1.3 carried threshold numbers without their meaning, and that caused a
   real bug.** The application read each `stageN` threshold as that stage's
   *ceiling* rather than its *floor* and overstated every country by one stage
   (Egypt would have been Stage 3 against the workbook's Stage 2). v1.5's
   Config sheet states the meanings, which is how it was caught. **Keep stating
   the semantics beside every number** — a bare number in a config is an
   invitation to misread it.

## What the Egypt worked example reveals about the model

This is the most useful empirical input to a refinement discussion.

- **92 of 102** indicators carry an effective level — a well-executed assessment.
- But only **42 carry a numeric value.** The other ~50 levels come from an
  assessor reading anchor text.
- **16 stale readings**, **2 data gaps**, weighted evidence adequacy **0.57** —
  which only just clears the 0.5 floor.
- CMS 3.07 (Established) · EMS 2.90 (Established) · OES 2.41 (Emerging) ·
  **Stage 2**. Verified: the application engine reproduces these figures exactly.

**The implication worth discussing.** Roughly half the model cannot be
populated by machine at all, and 75 of 102 indicators have no global series.
The binding constraint on a country assessment is therefore assessor time on
qualitative indicators, not data availability. Any refinement that adds
qualitative indicators adds directly to that constraint.

## Questions worth deciding in the new thread

1. **Is 102 the right number?** Randeep's own view, in the draft note to
   Katreyna: "I would rather prune it now than later." Candidates for scrutiny
   are indicators that no assessment has ever populated, and pillars that have
   grown (O1 is now 17, the largest).
2. **Is the qualitative half proportionate?** 44 indicators requiring
   judgement is the resourcing constraint. Could some become quantitative with
   a defined proxy, or merge?
3. **Was the E1/E2 rebalance (55/45 → 70/30) validated,** or inherited from
   v1.4? It materially moves EMS.
4. **Are 14 core gates still non-compensatory in spirit?** Each addition makes
   a suppressed stage more likely; 6.14 was added in v1.5.
5. **Do the staleness limits match reality?** 63 indicators demand data under
   two years old. Egypt has 16 stale readings against limits, several from
   2015–2022 — that may say more about the limits than the country.
6. **Should the model say how to score a narrative value?** Egypt has readings
   like "~1 extension worker per 200 families" that carry no level because
   they are prose, not a number and not an anchor judgement.

## Constraints that must survive any refinement

- **The four prohibitions** — no cross-country ranking; no stage as PDO
  indicator, DLI or disbursement condition; no automatic financing or
  procurement decisions; no stage claimed publicly before human review.
- **Country data isolation.** Verified in the application: every read and write
  is country-scoped. Egypt's assessment is an example of *form* for other
  countries and never a source of data. The single deliberate exception is
  practice research, which collects other countries' strategies as labelled
  comparators that can never populate an indicator.
- **A gap that has been looked for and named is not a blank.** Data Gap is a
  recorded state weighted zero, distinct from "not yet assessed".
- **Coverage suppression.** Below the gate a pillar reads *Not rated*, not a
  low score. A low score is a finding about the country; Not rated is a
  finding about the evidence.

## If the refinement changes the model

Anything below will ripple into the application, so flag it when deciding:

| Change | What it touches |
|---|---|
| Add/remove indicators | `sources.ts` needs a source spec per new indicator (global series or named gap + steward); fixtures need rows |
| Add/remove a core gate | Demo fixture must still clear its own readiness gate; gauntlet arithmetic shifts |
| Change weights or floors | `scoring.test.ts` pins the fixture's arithmetic; update the expected values with the reasoning |
| Rename a method or vocabulary | `researchableRubrics()` filters on method strings |
| Add a computed concept (e.g. leapfrog) | Needs an engine implementation, not just a config entry |

Tests derive model counts from the config rather than hardcoding them, so a
version bump should not break test literals — that was fixed during the v1.5
migration.

## State of the application, for reference

Branch `rebuild/byok-delivery-2026-08`, HEAD `74c9fd5`, pushed. 330 tests,
clean typecheck/lint/build. Reads v1.5. The four process decisions taken with
the user (provisional stage shown watermarked; 8-rung ladder retired in favour
of the 4-step process ladder; unattended runs still produce a diagnostic
package with unvalidated rows flagged; Egypt imported for Egypt only) are
recorded as **D5** in `~/Projects/dar-studio-v2/LEARNINGS.md`, and the stage
cascade bug as **L25**. Still to build in the application: the qualitative
validation queue, the Diagnostic Package sheet, and the ladder retirement.
