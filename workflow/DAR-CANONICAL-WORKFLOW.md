# Canonical workflow for generating a Digital Agriculture Report

**Contract:** `damm.dar-workflow/v1`
**Workflow:** `dar-canonical-v1`
**Status:** normative
**Machine-readable source:** `dar-workflow-v1.json`

This document defines the one canonical workflow that DAMM and DAR Studio must execute to
produce a comprehensive Draft Digital Agriculture Report (DAR). The JSON contract beside this
document is the executable source of truth. Product code must read the exported contract rather
than maintain a second, hard-coded stage list.

## Operating rule

After launch, the workflow runs end to end without requiring a person to confirm evidence,
approve a stage, import a result, upload another document, choose a retry, or increase a budget.
The system may retry, use a declared autonomous fallback, or end in a terminal failure; it must
never wait for human input while presenting the DAR as in progress.

The required launch input is the country under review. A TTL may optionally add relevant
documents and structured inputs before launch. Launch freezes those inputs, their provenance,
and their hashes into an immutable input snapshot. A later upload belongs to a new workflow
version and never changes an active or completed run.

Human review begins only after the eight stages have completed and the Draft DAR package has
been created. That review may correct the evidence, validate recommendations, and promote a
later version to Final. It is not a prerequisite for generating the Draft package. No Draft is a
public claim, financing decision, or authority to publish.

## The eight stages

| # | Stage | Required product |
|---:|---|---|
| 1 | **DAMM diagnostic** | DAMM v1.7 observations, independent automated challenge, scored assessment, and diagnostic report |
| 2 | **Country research and source inventory** | Country-specific evidence beyond DAMM, a consolidated inventory of credible sources, and any pre-launch TTL documents with provenance |
| 3 | **AI in digital agriculture assessment** | Separate assessment of the country's as-is AI position, peer-country experience, and a recommended national AI agenda |
| 4 | **International strategies and lessons** | Recent, relevant country strategies and transferable lessons, with selection rationale and limitations |
| 5 | **Strategic foresight** | Country-specific scenarios, preferred future, and backcast milestones; optional documents are synthesized when present and autonomous research is used when absent |
| 6 | **Investment options and cost-benefit analysis** | Prioritized options with baseline, counterfactual, cost and benefit ranges, assumptions, sensitivity, risks, distributional effects, and evidence gaps |
| 7 | **Integrated Draft DAR** | One comprehensive Draft DAR synthesizing every prior stage, with claim-level provenance and explicit epistemic status |
| 8 | **Export package** | Downloadable stage products, structured data, source inventories, a manifest, and a complete ZIP bundle |

The order is strict. A stage may begin only when every declared dependency is complete. Stage 1
includes automatic import of machine-produced evidence into the run snapshot; there is no
separate human import step. Stage 7 must consume the recorded outputs of stages 1–6 from the
same workflow version. Stage 8 must export only artifacts bound to that version.

## Optional pre-launch inputs

DAR Studio may accept country-context, AI, international-strategy, foresight, and
investment-cost/benefit documents before launch. The workflow records original filename, media
type, byte size or object reference, SHA-256 digest, uploader, upload time, extraction status,
and category. Supported files are declared in the JSON contract.

An optional document changes the evidence available to a stage; it does not replace the stage.
When documents exist, the stage must synthesize them, check their provenance, and supplement
them where needed. When none exist, the stage conducts its own research. Missing optional input
is therefore an automatic branch, never an error and never a request to the TTL during the run.

## Completion and failure

Every stage writes a manifest containing its contract version, input hashes, output hashes,
source inventory, quality-check results, spend, execution mode, and completion status. A stage
is complete only when all required artifacts exist and its blocking checks pass. A transparent
`degraded` flag is allowed only when the minimum completion criteria still pass; it may never be
used to relabel an incomplete diagnostic or missing required product as complete.

Transient failures receive bounded automatic retries. Vendor or retrieval unavailability uses
the declared fallback where one exists. Budget is authorized at launch and enforced through
fixed, protected stage allocations that reserve capacity for every required product, including
Draft generation. No stage can borrow another stage's allocation and no person can increase the
ceiling during a run. Exhaustion that still prevents a required product after retry/fallback is a
terminal failure, not an `awaiting human`, `paused for input`, or budget top-up state.

The protected shares of the launch ceiling are: DAMM diagnostic 45%; country research 7.5%; AI
assessment 10%; international lessons 7.5%; strategic foresight 10%; investment appraisal 5%;
Draft DAR generation 15%; and deterministic export 0%. Stage 1 internally reserves 35% for
evidence research and 10% for its challenge pass. These shares sum to the full ceiling and are
enforced by named ledgers rather than reallocated at runtime.

The workflow states are `queued`, `running`, `retrying`, `complete`, `failed`, and
`cancelled`. The first three are active and the last three are terminal. Cancellation may be offered as an operator safety
control, but no operator action is required for normal completion.

## Required exports

Narrative products are exported as Markdown, DOCX, PDF, and HTML. Structured products and
source inventories are exported as XLSX, CSV, and JSON where tabular representation is
meaningful. When documents were supplied before launch, the package also carries every frozen
original byte stream, every verified extracted-text file, and the upload provenance envelope;
none may be omitted or reconstructed. Stage 8 produces a ZIP bundle and a SHA-256 manifest that
relates every file to its stage or input, workflow version, input snapshot, and generating code
version.

If a format converter is unavailable, Stage 8 fails rather than silently declaring an omitted
required format complete. Downloads are served from the artifact manifest, not reconstructed
from unversioned filenames or a particular worker's local directory.

## Governance after completion

The completed bundle has lifecycle state `draft`. A separate, recorded post-completion review
may create a revised Draft and, after the applicable TTL/stakeholder controls, promote a version
to `final`. The following DAMM prohibitions remain unchanged:

1. no cross-country ranking;
2. no DAMM band as a PDO, DLI, or disbursement condition;
3. no automatic financing decision; and
4. no public claim before human review.

These controls govern use and publication. They do not insert a human gate into Draft DAR
generation.

## Conformance

DAMM owns this contract. `model/export_app_fixtures.py` copies the JSON contract and schema into
DAR Studio and records their SHA-256 digests. DAMM tests validate its structure and invariants;
DAR Studio tests validate the exported hash, render the same eight stages in the same order,
and refuse any contract that introduces a required human gate during active execution.

A workflow implementation conforms only if a user can provide the country and any optional
inputs, launch once, take no further action, and receive either the complete Draft DAR package
or an honest terminal failure.
