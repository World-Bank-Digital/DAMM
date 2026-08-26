# The Digital Agriculture Maturity Model

## Companion Guidebook — lineage, method, and what each stage produces

**Version 1.7 · Draft for review · August 2026**

> **Normative workflow supersession — 26 August 2026.** The instrument history and scoring
> guidance in this companion remain unchanged. For process orchestration and artifact
> lifecycle, `workflow/DAR-CANONICAL-WORKFLOW.md` and
> `workflow/dar-workflow-v1.json` supersede conflicting statements below. The canonical
> workflow has eight stages, including separate AI and digital-agriculture assessment and
> investment-options/cost-benefit analysis stages. Optional documents are frozen before launch
> and absent documents trigger autonomous fallback. No human action or budget top-up is required
> during an active run. The independent automated challenge remains in Stage 1; G1, G2, and G3
> are post-completion review/publication controls. A Draft may be generated before review; Final
> promotion and publication may not. The four prohibitions remain unchanged.

---

## What this document is

This is a short companion to the *DAMM v1.7 Guidebook*, which remains the reference for the instrument itself — the seven pillars, the fifty-seven indicators, the rules of evidence, and how to read a diagnostic report. Nothing here replaces it.

It exists to answer two questions that the Guidebook does not, and that a reader coming to this work now is entitled to ask.

**Where did this come from?** The model did not begin on a blank page. Its strictest rule was made possible by a country assessment that had already proved the rule could be met, and several of its refusals are refusals of things that assessment did.

**What does the process actually produce?** The model is now the instrument inside an automated pipeline. This sets out every stage of that pipeline, what it hands on, the execution controls that govern it, and — stated plainly — how far the components have actually been run.

A note on the second question. Several components are built and tested but have not yet been run as one canonical eight-stage workflow. The limits are stated under *What is not yet proven*. We would rather a reviewer knew which parts of this are proven than discover it later.

---

# Part one — the line from Bhutan

## What the Bhutan assessment established

The Bhutan Digital Agriculture Maturity Assessment (March 2026) is the most complete country application of this model's earlier versions, and it is the proof of feasibility behind the strictest rule DAMM now carries.

Its register holds **97 indicators. Every one of them carries a value, a source, a year and a confidence rating. There are no blanks** — not one row without a value, not one without a year, not one without a level.

That matters more than it might appear. The rule at the centre of DAMM v1.7 — that no indicator may be assigned a maturity level unless a value, a source and a year are recorded against it — asks a future assessor for nothing that has not already been done once, by hand, for a whole country. Bhutan is the reason that rule is a requirement rather than an aspiration.

Bhutan established three further things that v1.7 carries directly:

**Indicators labelled "qualitative" can carry recorded evidence.** Bhutan scored numeric values on twenty of forty-two such indicators. That pointed toward deriving the evidence class from what is on the record, rather than asking an assessor for an opinion about how good their own evidence is.

**The four-layer structure works.** Foundation, Enablers, Transformation, Outcomes — restored in v1.7, and with it the structural gap between what a country has built and what it has built on top, which earlier versions defined but could not compute.

**Agriculture belongs in the scoring.** Bhutan scored the agriculture pillar and let it drive investment priorities. Earlier DAMM versions collected the agricultural context and then excluded it from every calculation. Pillar A1 exists because Bhutan showed what including it is for.

## What v1.7 declined, and why

Bhutan also did three things that v1.7 deliberately does not do. Its own figures are the argument.

**A single overall maturity score.** Bhutan reports 2.29 out of 5.00, "Emerging". To produce it, the four layers were weighted — Foundation 0.20, Enablers 0.35, Transformation 0.25, Outcomes 0.20 — and averaged into one number. DAMM v1.7 declines to produce that number. A single figure averaged across families invites exactly the cross-country comparison the model's first prohibition forbids, and the weights that produce it are a judgement about what matters that no evidence in the assessment supports.

**A Data Confidence rating supplied alongside the score.** This is the consequential one, and the cost is visible in Bhutan's own register:

| Data Confidence | Indicators | Still assigned a level |
|---|---|---|
| High | 27 | 27 |
| Medium | 38 | 38 |
| **Low / Estimated** | **32** | **32** |
| **Total** | **97** | **97** |

**Thirty-two of ninety-seven indicators — a third of the register — were rated Low or Estimated, and every single one of them still received a maturity level that fed the headline number.** Nothing was withheld. There are zero gaps and zero holds in a register where a third of the evidence was acknowledged, by its own authors, to be weak.

That is not a criticism of the assessors, who recorded their uncertainty honestly and visibly. It is a criticism of a design in which recording uncertainty and acting on it are separate steps, so that the second one never has to happen. DAMM v1.7 closes that gap with two mechanisms:

- **Abstention is an answer.** Where the evidence does not establish a level, the row records a gap — with the search trail that produced it — and enters no mean. It is not scored low. It is not scored at all.
- **A ratification hold withholds a level** pending a decision about the indicator's definition or cut points. A withheld level is an absence of a claim, never a claim of absence.

**Expert scores on a 0–100 scale.** These dress judgement in the costume of measurement. The derived evidence classes prevent it: what class a row belongs to follows from what was recorded, and is not available to be asserted.

## What Bhutan still does better

One thing, and it is not a small thing.

**Bhutan achieved complete coverage. DAMM's automated pipeline has not.** Ninety-seven of ninety-seven rows populated by hand, against a best live machine run that reached nine of fifty-seven. The gap is retrieval: finding the published figure for a specific construct in a specific country is the binding constraint on the whole method, and a careful human analyst is still markedly better at it than the pipeline is.

Bhutan's own register shows where the difficulty lies. It tags every indicator **Global** — an international body publishes it for every country — or **Local** — it must be found nationally:

| Scope | Indicators | Rated Low / Estimated |
|---|---|---|
| Global | 27 | 0 (0%) |
| Local | 70 | 32 (46%) |

Not one Global row was weak. Nearly half the Local ones were. The difficulty is not spread evenly across the register; it is concentrated entirely in the rows that require a national source. All seven rows that both automated DAMM country runs failed to reach are Local rows.

So the honest summary of the comparison is this. **Bhutan proved the discipline is achievable. DAMM v1.7 makes that same discipline explicit, machine-checkable and repeatable — and adds abstention, source tiers and recorded search trails where Bhutan's confidence ratings carried the judgement implicitly. What DAMM has not yet matched is Bhutan's completeness.** Both statements are true and both belong in any account of this work.

## The question Bhutan settled

A proposal was considered during this round: score every indicator on a continuous 0-to-5 scale by its ratio to the cut points, so that Egypt's innovation index of 24.7 against a cut-off of 25 would record as 0.988 rather than falling to the level below.

Bhutan had already answered it. **All ninety-seven of its indicators carry a whole-number level with the measured value recorded beside it. There is not one fractional level in the register.** And the three things v1.7 removed — the overall score, the layer weights, the confidence rating — are all things continuous scoring would make easy to reintroduce.

**Position: the whole number stays the scored quantity, and the continuous value is carried as recorded data and optional display.** Interpolating between cut points asserts that maturity increases smoothly inside a band, which is a claim about the world that banding exists precisely to decline. This is revisited only once the open definition questions and the calibration basis are settled, since ratified cut points are what any added precision would have to rest on.

One Bhutan device *is* proposed for adoption in v1.8: the **Global / Local scope tag**. It changes no score. It is a property of the indicator rather than of the country, so it is set once. And it would earn its place twice over — the pipeline currently searches Global and Local rows identically, when it should go to the international database first for one and to the national statistical office for the other; and on the page it tells a reader that a thin Local row is structurally thin rather than the product of a lazy search.

---

# Part two — the process, stage by stage

The model is the instrument. The workflow is what carries a country through it. The country is
required at launch; country-context, AI, international-strategy, foresight, and investment/CBA
documents are optional pre-launch inputs. Launch freezes their provenance and hashes. A missing
optional document starts the declared autonomous research fallback and never pauses the run.

The budget ceiling is also authorized before launch. The system may retry and automatically
reallocate within that ceiling, but it never waits for a human decision or top-up. If a required
product remains impossible after bounded retry and fallback, the run fails transparently.

| # | Canonical stage | What it hands on |
|---:|---|---|
| 1 | **DAMM diagnostic** | DAMM observations, independent automated challenge, scored assessment, diagnostic report, source inventory |
| 2 | **Country research and source inventory** | Country evidence beyond DAMM and a consolidated inventory of credible sources and pre-launch materials |
| 3 | **AI in digital agriculture assessment** | As-is AI position, peer-country experience, and a recommended national AI agenda |
| 4 | **International strategies and lessons** | Relevant recent strategies, transferable lessons, selection rationale, and limitations |
| 5 | **Strategic foresight** | Scenarios, preferred future, and backcast milestones |
| 6 | **Investment options and cost-benefit analysis** | Prioritized options with baselines, counterfactuals, cost/benefit ranges, sensitivity, risks, distributional effects, and evidence gaps |
| 7 | **Integrated Draft DAR** | One comprehensive Draft with claim-level provenance and explicit epistemic status |
| 8 | **Export package** | Required narrative and structured formats, source inventories, manifest, and complete ZIP bundle |

### Stage 1 — DAMM diagnostic

Every one of the fifty-seven indicator rows is researched independently. Queries are generated
from that row's own construct, so no row inherits another's leads. Each row returns a value, a
source with its tier, a year, a proposed level, and an argument for that level. The gaps,
withheld levels, and prerequisite rows are then challenged automatically by an independent
vendor. This is the Stage 1 automated challenge, not human G2.

Evidence gates verify quotation, country isolation, tier, construct, prerequisite, coherence,
currency, and argument. The engine scores only accepted observations, and the renderer refuses
to emit a diagnostic that fails its automated checks.

**Output:** observations, automated challenge, scored assessment, diagnostic report, source
inventory, and stage manifest.

### Stage 2 — Country research and source inventory

This stage researches the strategies, institutions, legal instruments, programmes, and
initiative register that the fifty-seven indicators do not cover. Pre-launch country documents
are synthesized when present; autonomous country research fills the branch when absent.

**Output:** country research report, country evidence data, consolidated source inventory, and
stage manifest.

### Stage 3 — AI in digital agriculture assessment

AI is a separate required analytical product: the country's as-is AI position, peer-country
experience, and a recommended national AI agenda for digital agriculture. Optional AI documents
supplement the analysis; their absence triggers autonomous country and peer research.

**Output:** AI assessment report, AI evidence data, source inventory, and stage manifest.

### Stage 4 — International strategies and lessons

Recent, relevant country strategies are selected with an explicit rationale, and their
transferable lessons and limits are recorded. This is neither an endorsement nor a country
ranking. Optional strategy documents supplement rather than replace the stage.

**Output:** international lessons report, strategy-comparison data, source inventory, and stage
manifest.

### Stage 5 — Strategic foresight

Scenarios bound uncertainty and are **not forecasts**. The preferred future is a claim about
values, not an evidence finding. Backcast milestones bind to indicators or prerequisites with a
target level and year. Optional foresight materials are synthesized when present; autonomous
research and the declared method run when absent.

**Output:** foresight report, foresight data, source inventory, and stage manifest.

### Stage 6 — Investment options and cost-benefit analysis

Potential investments are appraised through explicit baselines, counterfactuals, cost and
benefit ranges, assumptions, sensitivity, risks, distributional effects, and evidence gaps.
Where optional appraisal material is absent, preliminary ranges come from cited benchmarks and
unsupported values are marked for post-completion validation. This stage recommends and
appraises; it never makes an automatic financing decision.

**Output:** investment-options report, cost-benefit workbook, appraisal data, source inventory,
and stage manifest.

### Stage 7 — Integrated Draft DAR

The Draft synthesizes the recorded outputs of Stages 1–6 from the same workflow version.
Prescriptive material is marked *proposed, not evidenced*. Chapter bindings and figure checks
prevent a fluent claim from citing the wrong evidence or inventing a number.

**Output:** integrated Draft DAR, source data, claim provenance, and stage manifest.

### Stage 8 — Export package

The workflow exports required narrative formats, meaningful structured formats, source
inventories, a SHA-256 manifest, and a complete ZIP bundle. A missing required converter is a
terminal failure, not a silently omitted format.

**Output:** the complete, version-bound Draft package. Human review begins only now. G1 and G2
may create a revised Draft; G3 controls promotion to Final or publication. None is an active-run
dependency.

---

# Part three — the Draft package

The workflow produces a versioned package and it is reviewed **once, after Stage 8, as a
completed set** — not one artifact at a time. Every narrative product is a pre-review Draft and
says so.

**The diagnostic report.** Where the country stands, on the evidence recorded. Ten sections, its own emit-blocking gate. Its international content is deliberately bounded; free-form comparison has no place in it.

**The country research and source inventory.** Country evidence beyond DAMM, including the
initiative register and the provenance of optional pre-launch materials.

**The AI in digital agriculture assessment.** The country's as-is AI position, peer experience,
and recommended national agenda.

**The international strategies and lessons report.** Relevant strategies, transferable lessons,
and their limitations without ranking countries.

**The strategic foresight report.** Scenarios, a preferred future offered for decision, and milestones bound to the instrument.

**The investment-options report and cost-benefit workbook.** Appraisal ranges and assumptions for
post-completion validation, never an automatic financing decision.

**The integrated Draft Digital Agriculture Roadmap.** The comprehensive synthesis, with
prescriptive material marked as proposals rather than findings.

**The export package.** Required narrative and structured formats, source inventories, a
cryptographic manifest, and the complete ZIP bundle.

---

# What the model will not do

These are prohibitions, not preferences. They are in the model file, and they are printed on every document the pipeline produces.

- No cross-country ranking.
- No band used as a project development objective, a disbursement-linked indicator, or a disbursement condition.
- No automatic financing decisions.
- No public claim before human review.

---

# What is not yet proven

Stated plainly, because a reviewer should not have to discover it.

**The pipeline has not yet produced a complete assessment.** The one full research pass run through the application reached nine of fifty-seven rows with a recorded value. That run was degraded — one of the three retrieval vendors was unavailable for the entire pass, so every row was researched without its discovery peer. The failure was recorded on every affected row rather than hidden, and the run reports it. But the resulting assessment is thin, and the diagnostic rendered from it says so on its face rather than presenting an absence of evidence as a finding about the country.

**The complete eight-stage canonical workflow has not yet been demonstrated live.** Earlier
component runs do not establish end-to-end conformance, especially for the separate AI,
investment/CBA, integration, and export stages. Tested is not the same as run, and we are not
presenting those components as a completed canonical run.

**Two definition questions remain open.** The A1 threshold calibration lacks a documented basis, and forty-four indicator rows carry an open definition question. Rows affected by an unsettled definition carry a ratification hold rather than a level.

---

# What we are asking for

Two things, in order of usefulness.

**First, on the instrument:** whether the rules of evidence are the right ones — in particular whether abstention and the ratification hold are set where a reviewer would set them, given that the alternative visible in Bhutan is a complete register in which a third of the evidence was acknowledged weak and every row was scored anyway.

**Second, on the process:** whether the eight stages produce what a roadmap engagement actually needs, and whether anything in the outputs described here would be unusable, unwelcome, or missing.

The attached scoring workbook is the instrument itself, and is the quickest way to see the rules operating: six entry columns, everything else derived.

---

*Prepared as a companion to the DAMM v1.7 Guidebook and the DAR Playbook.*
