# Final-DAR review Issue 2 — ratification disposition

**Date:** 26 August 2026
**Outcome:** **Contained, review-ready, and not yet closed.**
**Canonical state:** DAMM v1.7 revision 2 remains `status: "draft for review"` and
`ratified: false`.

Issue 2 cannot be closed by changing a label. The repository says section 13 is jointly
held by Katreyna + Randeep, but the recorded working rulings came from a simulated review
exchange. No actual joint confirmation is present in the repository or connected Drive
material inspected for this work. The remaining decisions are also substantive: 39
indicator definitions need a reviewer choice, and neither available A1 threshold set has
a documented cut-level calibration basis.

This disposition therefore does two things:

1. blocks the repository generator from accidentally presenting an unratified method as
   a Final DAR; and
2. supplies the research, proposals, calibration contract, and exact missing-record
   checklist needed to conduct an honest ratification review.

## Engineering containment completed

### Final-publication gate

`gauntlet/loop-1/research_pipeline/generate_dar.py` now treats narrative review and method
ratification as independent requirements. A DAR may carry the Final label only when all of
the following are true:

- the exact inputs and exact narrative replay are reviewed;
- the root model has `ratified: true` and exact `status: "ratified"`;
- `open_decisions` is present, well formed, and empty;
- the complete expected binding-rule set is present and every rule is affirmatively
  ratified;
- the complete 57-indicator inventory is present;
- no indicator carries an unresolved definition question;
- every one of the 32 threshold rows is affirmatively marked
  `thresholds_ratified: true`;
- the foresight method is affirmatively ratified.

Those state assertions are necessary but not sufficient. The model must also carry a
durable `ratification_evidence` bundle. Every reference must resolve to a repository-local
archive whose bytes match the declared SHA-256 digest and whose content binds to the
current model revision. The two approval-source records must also bind the exact digest
of the complete non-joint evidence manifest, so an artifact cannot be swapped after the
recorded approval. Required content comprises two distinct, validly dated Katreyna and
Randeep approvals with immutable external provenance; 72 accepted 13.3 cells; the 44
accepted 13.5 decisions plus a full 57-row release definition catalog; ten accepted 13.6
A1 calibrations; a method-owned 32-row threshold catalog; a full foresight-method record;
accepted Egypt and Nigeria migration snapshots and diffs; independent human-shadow
evidence for a real third ISO-alpha3 country other than Egypt, Nigeria, or Bhutan,
including all 57 human, automated, and comparison rows; and a release-verification record
covering the revision bump, schema- and content-validated artifact bytes, structured test
results, single-source parity, full build, replayed application tests, implementation
digest, and a tag that points to the current release commit and evidence tree.

The gate also checks that the approved 13.3 mapping is installed at the model root and is
actually exercised by the engine, that every model row carries the accepted definition
version, and that every threshold row points to the accepted calibration. The 44-row
13.5 decision artifact must agree exactly with the corresponding rows in the full
57-entry release catalog; the ten 13.6 records must agree with the corresponding rows in
the complete 32-calibration catalog.

The evidence is executable where software can make it so. Each ratified observation must
name its actual geography, observation period, edition, proxy status, source-record
digest, numerator/denominator treatment, source series, exact definition digest, and
calibration reference. Its tier must be allowed by the ratified source policy, its
load-bearing source must have a construct-review digest, and the catalog's missing- and
mismatch-handling rules must be exact. For a Measured row, the declared transform is
recomputed from archived transform inputs and compared with the scored value. A non-null
threshold score must be Measured; a ladder row cannot masquerade as Measured; and a
definition mismatch may remain Documented only with its level explicitly held. The
engine and independent reference scorer reject a ratified row that does not satisfy that
contract. Egypt and Nigeria migrations bind the old snapshot to an archived revision-2
model digest, source commit, historical implementation digest, and historical release
tag. The tag or its target commit must pass Git's cryptographic verification, and the
baseline record binds the verification-transcript digest. Each old country snapshot must
be byte-identical to a file in that tag; its complete engine and independent-reference
outputs are then semantically reproduced by projecting the archived draft model through
the compatibility runner. The new snapshot is replayed under the candidate ratified
model, and typed diffs are derived from those outputs rather than trusted as
reviewer-entered counts. Each new migration row also resolves its source and
construct-review digests to archived, model-bound records. The unseen country archives 57
indicator-level source captures and construct reviews. Each source record binds the raw
capture bytes and locator, tier, URL, series, edition, geography, transform inputs, raw
value, unit, period, and evidence excerpt. Each construct review additionally binds the
complete human assessment-row digest. A full 57-row input exercises all 32 threshold rows
as Measured and archives the reference year, intervention profiles, complete engine
output, implementation digest, and provenance-backed human comparison. Accepted
human/automation differences need a specific resolution; unresolved rejected automation
cannot pass. The gate replays the output and rejects even a fully rehashed fabricated
score set, substituted human levels, or a valid HOLD substituted for one of the required
calibration exercises.

The required sequence is also explicit: a separately archived Katreyna + Randeep method
freeze, with immutable approval provenance and UTC timestamps, must precede the Egypt and
Nigeria reruns; both reruns must finish before the unseen-country assessment begins. The
unseen record binds the exact freeze and migration payload digests.

Release workbooks are parsed as OOXML and must carry the ratified status, exact model
version/revision/digest, exact Config constants, all 57 scoring rows, a complete
Definitions sheet, calibration references, and all 72 mapping edges. The gate matches the
complete formula manifest: evidence class, level, staleness and six use-case bearing flags;
pillar, layer and leapfrog calculations; all prerequisite statuses; the mapped readiness
matrix with conditional constraints and delivery risks; and the live Visuals feeds. Each
scoring row carries a canonical contract digest, and every literal dependency and formula
cell is position-sensitive. The workbook must also contain a nondegenerate input case
covering every evidence class, a HOLD, both staleness sides, and true/false/unresolved
profiles. The exact formula-manifest digest and formula count are bound into the release
check. A separate verifier validates that exact workbook first, copies it into an
isolated temporary workspace, recalculates only the copy with LibreOffice, and compares
the cached workbook results with complete engine and independent-reference projections.
Its archived runtime record must bind the exact workbook, canonical-model, observation,
and intervention-profile bytes; the formula-manifest digest and count; all three equal
projection digests; the 57 indicators, seven pillars, four layers, leapfrog outputs,
12 prerequisites, six readiness matrices, and 72 mapping-edge helpers; zero formula,
input-binding, or output mismatches; an unchanged source workbook; and a zero
recalculator exit. The release gate rejects a static-only workbook attestation or a
runtime record whose reference, hash, country, inputs, scope, or result has been changed.
Application evidence is replayed through both the engine and independent
reference scorer across six required cases: unconditional gating, conditional
inactive/active behavior, delivery-risk isolation, threshold-cache recomputation, and
definition-mismatch rejection. Each implementation's complete semantic result—including
all 57 indicator rows, pillar/layer results, leapfrog reading, prerequisite statuses,
matrix reasoning, constraints, KPI/verification/refresh lists, and counts—is
content-addressed and must agree exactly. Definition rejection must identify the same
error on both implementations. Its check log is bound to the fixture digest and exact
case list. Release-check records must declare the exact command, run and attestation
identifiers, timestamps, structured results, content bindings, and immutable external
provenance. The final tag name, signature target, and authorized signer fingerprint are
jointly manifest-bound before tagging. Verification resolves that tag once to an
immutable object, verifies its signature, peels one commit, and reads every model,
implementation, and evidence byte through that commit; it does not embed an impossible
self-referential commit hash in the tagged content. The current draft workbook builder
intentionally cannot satisfy this release contract until the real choices are ratified
and regenerated.

The frozen country-code allow-list comes from the UN Statistics Division's current
[M49 country or area table](https://unstats.un.org/unsd/methodology/m49/), which publishes
the associated ISO-alpha3 codes and excludes ISO's user-assigned `ZZZ` range.

Missing, empty, incomplete, malformed, unapplied, or manifest-unbound attestations fail
closed. HTML displays the specific publication blockers, and contradictory
`final`/status labels are rejected. The currently reviewed Egypt replay therefore
completes as a reviewed **Draft**, never as a Final DAR.

This is an integrity and application gate, not an identity oracle. SHA-256 proves that an
archived record has not changed since capture; it does not prove that Katreyna or Randeep
authored it, nor does a locally archived `passed: true` record prove that its named command
actually ran. The archive must therefore retain an immutable CI/provider revision,
signed record, verified commit, or independently checked physical-record reference, and
the release reviewer must verify that provenance outside the generator. A maintainer with
write access could deliberately forge local JSON or change the gate itself; preventing
that requires repository access controls and signed or external records beyond this
code's trust boundary. The generator authenticates the archived historical outputs and
reproduces their semantics under the archived model; it deliberately does not execute
arbitrary code from an old tag. A sandboxed replay of the historical implementation and
organizational trust in the signing key remain external release checks.

### Threshold-cache bypass closed

Both scoring boundaries now treat a non-null stored level on a Measured threshold row as
an auditable cache, not an independent score. The effective level is re-derived from the
active cut-points in:

- `gauntlet/loop-1/engine_v17.py`; and
- `model/reference_scorer.py`.

An explicit `level: null` remains a deliberate definition/ratification hold. A missing
level key follows the pre-existing threshold derivation behavior. The DAR input validator
separately rejects a non-null cached level that disagrees with the active thresholds, so
publication requires the input artifact to be migrated rather than silently normalized.

## Review artifacts prepared

| Decision | Artifact | Evidence-backed disposition | Approval still needed |
|---|---|---|---|
| 13.3 prerequisite mapping | `DECISION-13.3-PREREQUISITE-MAPPING-PROPOSAL.md` | Complete 12×6 graph: 25 unconditional gates, 8 conditional gates, 12 delivery-risk overlays, 27 explicit no-edges | Accept/amend the edge graph, especially the 7.12, 3.3, and 4.5 predicates |
| 13.5 definitions | `DECISION-13.5-INDICATOR-DEFINITION-RESEARCH.md` | All 44 scored open rows defined; 6 falsehood, 30 construct-drift, 8 unit-ambiguity; 22 numbered source-register entries covering 39 links/documents | Confirm five named-series bindings and decide 39 construct/population/unit/ladder boundaries row by row |
| 13.6 A1 calibration | `DECISION-13.6-A1-CALIBRATION-RESEARCH.md` | Full ten-row lineage; undocumented recut changes four Egypt/Nigeria/Bhutan levels; calibration contract and 20 release tests specified | Choose an approved basis and five explicit intervals for each row after dependent 13.5 definitions freeze |

These are not the ratified machine-readable artifacts required by the publication gate.
In particular, the ten numeric A1 calibration cards and all 22 non-A1 calibration records
still have to be prepared from approved choices.

The 13.3 proposal changes no arithmetic. On the verified country oracles its unconditional
base graph would move Egypt from **4 Blocked / 2 Unverified** to **1 Blocked / 5
Unverified**; Nigeria remains **1 Blocked / 5 Partial**. Intervention predicates can then
activate additional gates. This sensitivity is exactly why the proposal was not applied
without approval.

The 13.6 lineage finds four score movements caused solely by the undocumented March→v1.7
recut:

- Egypt 1.3: L4→L3;
- Nigeria 1.3: L3→L2;
- Bhutan 1.7: L1→L2; and
- Bhutan 8.1: L1→L2.

These cases test a future decision; they are not a defensible sample for fitting one.

## Why the canonical model was not changed

The available evidence does not authorize any of the following:

- representing the simulated review exchange as Katreyna's actual confirmation;
- choosing 39 normative definitions on behalf of the joint reviewers;
- treating inherited or newly recut round numbers as calibrated thresholds;
- regenerating Egypt and Nigeria before rules, definitions, and calibrations are frozen;
  or
- claiming production validation before one genuinely unseen country is independently
  human-shadowed.

Accordingly, this work does **not** set the root or foresight ratification booleans, clear
open decisions, remove definition questions, mark thresholds true, revise country scores,
add a synthetic `ratification_evidence` bundle, or generate a release tag. A future
ratified canonical revision must add that bundle from the real records; the generator's
passing test fixture demonstrates the schema but is not release evidence.

## Ratification record required to proceed

The joint review should create a dated record containing at least:

| Field | Required decision/evidence |
|---|---|
| Reviewers | Katreyna and Randeep named explicitly; approval dates; immutable external provenance; each source record binds both the ratifiable-model digest and exact evidence-manifest digest |
| 13.3 | Accepted mapping revision and every amended edge/predicate |
| 13.5 | Accepted definition version for each of 44 rows; named-series IDs/transforms; rationale for each of the 39 reviewer-choice rows |
| Full definition catalog | One ratified, model-revision-bound record for every one of the 57 scored indicators; the 13 rows not opened by 13.5 remain part of release completeness |
| 13.6 | One typed basis per A1 row (`official_classification`, `normative_target`, frozen `distributional`, `expert_judgment`, or `hybrid`); exact five intervals and boundary closures; method/domain approvers |
| All thresholds | One method-owner-attested 32-row calibration catalog. The 22 non-A1 rows are not covered by 13.6; 15 of them remain definition-dependent under 13.5 |
| Foresight | Explicit method approval or a recorded reason it remains publication-blocking |
| Application | Approved mapping installed and exercised; all 57 model rows point to the accepted definition version; all 32 threshold rows point to the accepted calibration |
| Migration | Jointly evidenced method-freeze timestamp; revision-2 baseline model/implementation bound to its source commit and historical tag; each old country snapshot present byte-for-byte in that tag; old/new 57-row engine and reference outputs replayed under their respective models; current-row source and construct reviews resolved; mechanically derived typed diff accepted for Egypt and Nigeria |
| Validation | Independent human-shadow record for a genuinely unseen country, with 57 indicator-level source and construct-review records, 57 human rows, all 32 threshold rows Measured in the canonical engine input, profiles/output, implementation digest, replay, and row-wise comparison after both reruns |
| Release | Schema/content-validated artifact archives, six engine-and-reference application replays, exact-command structured check results with externally verified run provenance, implementation digest, current release commit, and a tag resolving to that commit and the same evidence tree |

Silence, removal of a hold field, or “approved subject to a later definition” is not an
affirmative ratification.

## Definition of done for Issue 2

1. Obtain and archive the actual joint decision and method-freeze records with externally
   verified immutable provenance; bind final approvals to the ratifiable-model and
   evidence-manifest digests.
2. Convert the accepted 13.3 graph, 13.5 catalog, 13.6 A1 calibration cards, and complete
   32-row threshold calibration catalog into canonical machine-readable artifacts and
   schemas.
3. Install the exact accepted mapping, definition versions, and calibration references in
   the model; make that model the single source for engine, reference scorer, workbook,
   renderer, and application fixtures; remove duplicated rule constants.
4. Bump the model revision and artifact versions; set ratification fields affirmatively
   and clear only decisions that have a durable approval record.
5. Regenerate and review Egypt and Nigeria from the frozen configuration, publishing the
   complete level/mean/band/matrix migration diff.
6. Run one genuinely unseen, independently human-shadowed country.
7. Run the full parity/build/application verification sequence, including the temp-only
   workbook runtime verifier, archive its content-addressed evidence, and create the
   release tag.
8. Only then permit the DAR generator to emit a Final label.

Until those eight steps are complete, Issue 2 is safely contained but the methodology is
not ratified.

## Verification at this disposition

- Model/engine/reference parity: **470/470**.
- DAR generator and evidence-gate checks: **298/298**.
- DAR CLI/replay tests: **37/37**.
- Country-name, foresight, gate, scan, machine-pass, and survey-pass checks:
  **198/198**.
- Workbook runtime-verifier unit tests: **6/6**.
- Total safe checks: **1,009/1,009**.
- Temp-only bundled-LibreOffice smoke on the nondegenerate ratified-model fixture:
  **1,682** output comparisons and **504** input bindings, with zero mismatches or
  formula errors, three equal projection hashes, exit 0, and an unchanged source
  workbook. This is verifier evidence, not evidence that the draft model was ratified.
- Adversarial LibreOffice replays also passed for an activated low gate (**1,692**
  comparisons) and for a simultaneous Partial gate plus below-threshold readiness mean
  (**1,718** comparisons); the latter reproduced `why: "2.1"` and
  `mean_driven: true`, with zero mismatches or formula errors.
- A synthetic complete-map two-driver replay (**1,706** comparisons) reproduced the
  canonical comma-separated reason `2.1, 2.9`, again with zero mismatches or formula
  errors. It tests spreadsheet portability; it does not amend the proposed mapping.
- Python compilation and `git diff --check`: clean.

The pre-existing Issue 1 changes and fixtures were preserved. No commit, push, release,
or external message was made.
