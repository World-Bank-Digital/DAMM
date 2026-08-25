# The Digital Agriculture Maturity Model

## Companion Guidebook — lineage, method, and what each stage produces

**Version 1.7 · Draft for review · August 2026**

---

## What this document is

This is a short companion to the *DAMM v1.7 Guidebook*, which remains the reference for the instrument itself — the seven pillars, the fifty-seven indicators, the rules of evidence, and how to read a diagnostic report. Nothing here replaces it.

It exists to answer two questions that the Guidebook does not, and that a reader coming to this work now is entitled to ask.

**Where did this come from?** The model did not begin on a blank page. Its strictest rule was made possible by a country assessment that had already proved the rule could be met, and several of its refusals are refusals of things that assessment did.

**What does the process actually produce?** The model is now the instrument inside an automated pipeline. This sets out every stage of that pipeline, what each one is allowed to spend, what it hands on, and — stated plainly — how far each has actually been run.

A note on the second question. Several stages described here are built and tested but have not yet been run against live data. Each is marked. We would rather a reviewer knew which parts of this are proven than discover it later.

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

The model is the instrument. The pipeline is what carries a country through it. Six stages, each with a fixed share of a country budget ceiling, each checkpointing after every row so that a failure at row fifty of fifty-seven resumes at row fifty-one rather than at zero.

The budget shares are fixed in advance and enforced, rather than drawn from a common pool. This is deliberate: under a shared pool a badly-behaved research stage consumes the whole ceiling and the country ends with no document at all.

| # | Stage | Share of ceiling | What it hands on | How far it has run |
|---|---|---|---|---|
| 1 | **Research** | 40% | Engine input: all 57 rows with value, source, tier, year, level and a per-row argument; plus the full research trail | **Run live.** Egypt, 25 August 2026, 59 rows, $13.46 |
| 2 | **Second review** | 15% | Reviewed engine input; findings per row reopened | **Run in development** on Egypt and Nigeria; not yet through the application |
| 3 | **Scans** | 15% | Country evidence outside the instrument; one international precedent pointer per chapter; the initiative register | Built and tested; **not yet run live** |
| 4 | **Foresight** | 10% | Scenarios, a preferred future, milestones bound to indicators; standalone report | Built and tested; **not yet run live** |
| 5 | **Diagnostic** | 0% | The diagnostic report | **Run live.** Egypt, 25 August 2026 |
| 6 | **Roadmap** | 20% | The eleven-chapter draft DAR | Built and tested; **not yet run live** |

### Stage 1 — Research

Every one of the fifty-seven indicator rows is researched independently. Queries are generated from that row's own construct, so no row inherits another's leads. Retrieval is a discovery engine and a fetch service, with a second discovery vendor as an independent peer. Each row returns a value, a source with its tier, a year, a proposed level, and an argument for that level.

Eight gates sit between what the machine proposes and what is recorded. A quote must be verifiable against the page that was actually fetched. A source about another country cannot support a claim about this one. A level must follow from the argument given for it, not exceed it. Evidence about the presence of something must be current. A row that fails is held or recorded as a gap, with the trail that produced it.

**Output:** the engine input, and a research trail recording every search, fetch, quote and gate decision for every row.

### Stage 2 — Second review

The gaps, the withheld levels and the twelve prerequisite rows are re-researched by **a model from a different vendor**. This is a peer review, and the vendor must differ: a model reviewing its own pass tends to uphold it, and the second review's whole value is that it is not the first one again.

**Output:** a reviewed engine input, and a per-row record of what was upheld, adjusted, filled or withdrawn.

### Stage 3 — Scans

Three things the fifty-seven indicators do not measure but a roadmap needs.

*Country evidence outside the instrument* — the strategies, institutions, legal instruments and programmes a chapter must be written against.

*The initiative register* — the digital agriculture programmes actually operating in the country: who leads each, at what scale, with what independently evaluated results. Here a rule of the source-tier protocol does real work: T4 and T5 sources are admissible for **existence** facts only. An entry resting on a vendor page or a press release may say that a programme exists; it may not carry a tiered claim about that programme's results.

*International precedent* — one pointer per prescriptive chapter, drawn from another country's published strategy. This feeds the roadmap only. It never enters the diagnostic, it is never an endorsement, and it is never a comparison of countries. The pointer count is capped for a reason: an uncapped scan produces a league table, and a league table is a ranking whatever the surrounding prose calls it.

**Output:** country findings, international pointers, and the initiative register.

### Stage 4 — Foresight

Scenarios, then a preferred future, then backcasting to milestones. The method is declared in the model file so that it is ratifiable like every other rule; an unnamed method would be the one part of this system nobody could review.

Three things the output states rather than implies. Scenarios bound uncertainty and are **not forecasts**. The preferred future is **a claim about values, not a finding from evidence** — the single normative act in the whole pipeline, and marked as such. And every milestone must bind to an indicator or prerequisite with a target level and a target year, so that progress is measurable against the same instrument that produced the diagnostic. A milestone that cannot be measured against the instrument is refused and recorded as refused; a milestone reduced to prose is exactly what the binding rule exists to prevent.

Where nothing in the model measures what a milestone needs, it proposes a **candidate indicator** — recorded, carried, and outside every mean, prerequisite and readiness column, exactly as the existing candidate mechanism provides.

**Output:** scenarios, the preferred future, bound milestones, proposed candidates, and a standalone foresight report.

### Stage 5 — Diagnostic

The assessment is scored by the engine and rendered by the report renderer. This stage makes no vendor call and has a zero budget share: the evidence has already been paid for. Where the second review has run, its output supersedes the first pass.

The renderer carries an emit-blocking quality gate — a report that fails its own checks is not written. That gate is much of why the diagnostic has survived review.

**Output:** the diagnostic report.

### Stage 6 — Roadmap

Eleven chapters of prose. Chapters three to ten are prescriptive and are marked *proposed, not evidenced* — on the page, in the record, and in the gate.

Prose invites one particular failure: a paragraph that reads perfectly and carries a figure the evidence never produced. Three mechanisms stand against it.

**Each chapter sees only what it may cite.** Every chapter's evidence binding — which pillars, indicators, use-case columns and prerequisites it may draw on — is declared in the model file, and the pack assembled for that chapter contains that and nothing else. A financing chapter reaching for connectivity indicators reads perfectly fluently and is wrong; withholding the material is what prevents it.

**Every figure is checked against the engine.** The claimed figures are matched against the numbers the assessment actually produced, and the prose is separately swept for numbers that were never declared. The resulting fidelity rate is printed on the document's own face.

**The gate blocks the emit.** A missing provenance banner, a citation outside a binding, a prescriptive chapter presented as evidenced, or fidelity below the floor, and no document is written.

**Output:** the eleven-chapter draft roadmap.

---

# Part three — the three documents

The pipeline exists to produce three documents. They are reviewed **once, at the end, on the completed set** — not one at a time. Each is a pre-review draft and says so.

**The diagnostic report.** Where the country stands, on the evidence recorded. Ten sections, its own emit-blocking gate. Its international content is deliberately bounded; free-form comparison has no place in it.

**The strategic foresight report.** Scenarios, a preferred future offered for decision, and milestones bound to the instrument.

**The draft Digital Agriculture Roadmap.** Eleven chapters, with the prescriptive ones marked as proposals rather than findings.

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

**Three of the six stages have never run against live data.** Scans, foresight and roadmap generation are built, and their gates are covered by automated checks that require no network. Tested is not the same as run, and we are not presenting them as run.

**Two definition questions remain open.** The A1 threshold calibration lacks a documented basis, and forty-four indicator rows carry an open definition question. Rows affected by an unsettled definition carry a ratification hold rather than a level.

---

# What we are asking for

Two things, in order of usefulness.

**First, on the instrument:** whether the rules of evidence are the right ones — in particular whether abstention and the ratification hold are set where a reviewer would set them, given that the alternative visible in Bhutan is a complete register in which a third of the evidence was acknowledged weak and every row was scored anyway.

**Second, on the process:** whether the six stages produce what a roadmap engagement actually needs, and whether anything in the outputs described here would be unusable, unwelcome, or missing.

The attached scoring workbook is the instrument itself, and is the quickest way to see the rules operating: six entry columns, everything else derived.

---

*Prepared as a companion to the DAMM v1.7 Guidebook and the DAR Playbook.*
