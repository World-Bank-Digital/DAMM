# DAR Studio — automated pipeline design record

*Drafted 24 August 2026 from a structured design interview. Twenty-seven decisions, each
settled deliberately; this record exists so they can be reviewed as a set, and so the
reasoning survives into the next session the way the specification and handoff do.*

*The first build phase landed the same day — see **Build status** at the foot of this
record for which decisions now have code behind them. The historical rationale remains;
the orchestration clauses superseded below no longer govern the active workflow.*

> **Normative workflow supersession — 26 August 2026.** For orchestration and artifact
> lifecycle, `workflow/DAR-CANONICAL-WORKFLOW.md` and
> `workflow/dar-workflow-v1.json` supersede every conflicting statement in this record.
> The canonical workflow has eight stages, including separate AI and digital-agriculture
> assessment and investment-options/cost-benefit analysis stages. Optional documents are
> frozen into the input snapshot before launch; an absent optional document triggers the
> declared autonomous fallback. After launch, no human confirmation, upload, retry choice,
> or budget top-up is required or permitted as a condition of normal completion. The
> independent automated challenge remains inside Stage 1; G1, G2, and G3 are
> post-completion review and publication controls. The system may generate and export a
> Draft before human review, but only a reviewed version may become Final or be published.
> The four DAMM prohibitions remain unchanged.

---

## What is being built

An automated workflow that takes a country name plus any optional pre-launch documents and
produces a versioned Draft DAR package. It runs through all eight stages without requiring a
person after launch; post-completion review may revise the Draft and authorize Final or public
use.

| # | Canonical stage | Required product |
|---:|---|---|
| 1 | DAMM diagnostic | Researched and independently challenged observations, scored assessment, diagnostic report |
| 2 | Country research and source inventory | Country evidence beyond DAMM and a consolidated credible-source inventory |
| 3 | AI in digital agriculture assessment | As-is AI position, peer experience, and recommended national AI agenda |
| 4 | International strategies and lessons | Relevant strategies, transferable lessons, rationale, and limitations |
| 5 | Strategic foresight | Scenarios, preferred future, and backcast milestones |
| 6 | Investment options and cost-benefit analysis | Prioritized options, appraisal ranges, assumptions, sensitivity, risks, and gaps |
| 7 | Integrated Draft DAR | One traceable Draft synthesizing Stages 1–6 |
| 8 | Export package | Required formats, structured data, source inventories, frozen original uploads and extracted text, manifest, and ZIP bundle |

---

## A. Status and governance of the output

**A1. Everything the pipeline produces is a pre-review draft.** Review happens once, at the
end, on the completed end-to-end set — not per artifact. Artifacts carry provenance; the
engagement carries the review state.

**A2. The fourth prohibition is retained, not removed.** It governs *publication*, not
*generation*: "no public claim before human review." The flow — generate draft → human review
→ stakeholder engagement → validation — is that prohibition working as designed. Keeping it is
what licenses the automation, because it is the standing declaration that machine output is
not yet a claim. Removing it would make every generated artifact an assertion at the moment of
creation, which is a worse position for an automated pipeline, not a better one. It is also
inherited from v1.3, printed on every report footer, and wired into the G3 gate.

*Note the distinction that was almost conflated:* stakeholder engagement, investment cases and
governance are **not** prohibitions. They are DAR chapters. The pipeline drafts them; humans
validate them afterwards. That is scope, not governance.

**A3. Unratified dependencies are marked where the reader meets them.** A standing section plus
per-chapter markers, generated mechanically from the model file's `open_decisions[].governs`.
A chapter resting on unratified band edges or A1 test thresholds says so on the page. This is
nearly free — the mapping already exists — and it is what keeps a long, fluent, machine-drafted
document from reading as more settled than it is. Ratification later upgrades the document
mechanically rather than requiring a re-read.

**A4. "150 pages" is a stand-in for comprehensive, not a target.** A page count is an active
incentive to pad. The target is completeness against the 11-chapter outline with every claim
traceable.

---

## B. Sequencing

**B1. Build the machinery now; gate its use.** The pipeline is built and regression-tested
against Egypt and Nigeria, where figure-for-figure expected output already exists. New-country
auto-population waits on the twelve §13 rulings — 44 of 57 definitions are open, and 8 of the
12 prerequisites are among them. Automating research against unratified definitions
industrialises defect #1, where a national coverage figure recorded against an indicator naming
*rural* flipped five columns to Ready.

**B2. Run the vendor audition first.** Standing decision 4 fixes the method — 13 cells, 10
known answers and 3 verifiable non-existent, scored on fabrication rate, tier compliance and
citation resolvability — but **it has never been run**. Two vendors are needed: a primary and an
independent one for the automated Stage 1 challenge. Thirteen cells is cheap; choosing wrong costs $500 per country in
re-runs. It also yields a measured fabrication-rate baseline, which is the number a reviewer of
a machine-drafted roadmap will ask for and which cannot currently be stated.

---

## C. Evidence acquisition

**C1. Source quality is a tier, not a score.** The machine proposes a **T1–T5 tier**; a
non-numeric data-quality flag is available alongside it (e.g. a statistical office with known
issues stays T1 and carries the flag). No separate credibility number: v1.6 removed confidence
weights deliberately, and anything numeric will eventually be averaged by someone.

**C2. The machine sets levels; no human confirmation step.** It records value, source, tier and
year, plus a rung-by-rung argument and the negative finding (why the next level up was not
proposed). Levels flow into pillar means, bands, prerequisites and the readiness matrix.
*Consequence accepted:* the readiness matrix of a fresh country is machine-set. C3 and C4 are
what keep that honest.

**C3. The machine may abstain.** Where it cannot cite rung-specific, quote-verified evidence at
an admissible tier, it sets a **ratification hold**: the level is withheld, the row leaves every
mean, and the report says so. The model already distinguishes "no level because nothing was
found" (Gap) from "no level because the evidence measures a different construct" (hold), and an
automated pipeline can set both. Abstention is what prevents uncertainty from disappearing into
adjectives.

**C4. Prerequisites face a higher bar.** The twelve prerequisite rows require **T1–T3
quote-verified** evidence or the machine holds. Their leverage is disproportionate: rural
electricity at level 2 rather than 3 flips every Nigerian column from Ready to Partial. This
stays fully automated while raising the bar precisely where a one-level error propagates to six
columns.

**C5. The Stage 1 challenge runs automatically, with a second vendor.** Scoped to prerequisites, held rows and
recorded gaps — roughly 20 rows, not 57 — prompted to refute. In the gauntlet this earned its
keep: 24 of 24 prerequisites survived attack, 12 provenance adjustments landed, and **4 gap
refutations** found what the first pass missed.

**C6. Perplexity is a discovery peer; its citations become the evidence.** Perplexity's returned
citations are re-fetched through Jina, quote-verified against page text, and tiered. Perplexity
itself never appears as a source of record, because a synthesised answer has neither a publisher
nor an archivable document, and the tier protocol requires both. This preserves the
quote-verification that caught a fabricated pilot in the gauntlet.

**C7. Country isolation is enforced, not merely intended.** Every research task carries exactly
one country context; prompts are generated per country with no shared lead lists; results
naming another country's entities are rejected automatically, as part of the emit-blocking QC
gate. This closes issues-log defect #11 ("Egypt bundle-C prompt carried Nigeria leads"), which
is still open and deferred to loop 2. Bleed is silent — a plausible Nigerian fact in an Egyptian
report looks exactly like a real one — and the gauntlet caught it only because an agent noticed.

---

## D. Where humans touch it after completion

**D1. A post-completion edit supersedes, visibly.** After Stage 8, the machine's original value, source and argument are kept
in history; provenance flips to assessor; the assessment rescores; an audit entry records it.
**The count of human-touched rows appears on the report's face** — in a fully automated pipeline
that number is the most informative quality signal a reviewer has.

**D2. A re-run versions; it never overwrites.** Human-edited rows carry forward by default and
are flagged where the machine now disagrees. The previous version stays readable. Discarding
edits on re-run would destroy exactly the rows someone bothered to correct, and versioning
delivers the source-refresh queue the external review asked for.

---

## E. The documents

**E1. The diagnostic uses `render_v17.py` as-is.** Ten Playbook-tagged sections, four chart
types, standalone, emit-blocking QC gate. It survived a gauntlet and an external review; a
rewrite would re-earn its defects. The worker calls it; a TypeScript port is optional later and
must reproduce the Egypt and Nigeria HTML before replacing anything.

**E2. The diagnostic keeps its bounded international content.** At most one tier-badged
precedent pointer per strategic question — "never an endorsement and never a comparison of
countries." The free-form international scan feeds the **DAR only**. The diagnostic is a
standalone document already verified and about to be reviewed; the DAR Draft is generated by
the same autonomous workflow and enters human review only after the export package completes.

**E3. The DAR is full prose, with epistemic status on the page.** All 11 chapters get prose.
Prescriptive chapters (3–10: vision, investment programme, costs and financing, policy, delivery
and governance, climate, results, risks) are explicitly marked *proposed, not evidenced*, with
their own visual treatment. **The fidelity checker returns and is non-optional** — it discarded
model prose carrying figures the engine never produced, and it is recoverable from git.

**E4. Each chapter declares the evidence it may cite.** Per-chapter bindings in the model file:
the pillars, indicators and matrix cells a chapter may draw on. This upgrades the fidelity
checker from "did it invent a number" to "did it use the right number" — a financing chapter
citing connectivity indicators reads perfectly fluently and is wrong.

**E5. Every document gets an emit-blocking QC gate.** The diagnostic already has one and it is
much of why the diagnostic survived review. The DAR's gate checks that every chapter carries a
provenance banner, that no chapter cites outside its binding, that no prescriptive chapter
renders as evidenced, and that the fidelity pass rate is recorded on the document's face. The
gates are the compensation for having removed the human from every step before final review.

---

## F. Foresight

**F1. Method: scenarios → preferred future → backcasting to milestones**, declared in the model
file so it is ratifiable like every other rule. An unnamed method would be the one part of the
system nobody could review. (A pre-mortem and stakeholder wind-tunnel remain available as
additions.)

**F2. Optional documents are pre-launch inputs, not stage replacements.** A supplied document
is frozen into the launch snapshot, provenance-checked, synthesized, and supplemented where
needed. When none is supplied, the stage runs its declared autonomous research fallback; it
never pauses an active run to request an upload.

**F3. Milestones bind to the instrument.** Each milestone attaches to one or more indicators or
prerequisites with a target level and year — *"2.1 rural mobile broadband to L3 by 2029"* — so
progress is measurable against the same instrument that produced the diagnostic, and DAR
chapter 9 has something concrete to measure.

**F4. Where no indicator fits, foresight proposes a candidate indicator.** Recorded and carried,
**outside every aggregate**, flagged as a ratification item — the existing mechanism used by
`A1-CAND-IMP` and `A1-CAND-IRR`. Foresight can define what it needs to measure without silently
expanding the scored model. A target level on an unratified threshold inherits that
provisionality and is marked accordingly (A3).

---

## G. Execution and cost

**Execution 1. A durable worker runs the Python pipeline; the app orchestrates.** Per-item checkpointing
and resumability — a failure at indicator 50 of 57 must not restart from zero. The v1.5
in-process lock and tick-polling arrangement was fragile and lost work on restart. Keeping the
pipeline in Python is also the fastest route to a working end-to-end system, since it already
runs and is verified.

**Execution 2. The budget ceiling is authorized before launch; there is no active-run top-up.** A live
spend counter remains visible. The system may retry within fixed, protected stage allocations
under the frozen ceiling. If a required product still cannot be completed, the run ends in an
honest terminal failure rather than pausing for a person or emitting budget-induced gaps as
findings.

**Execution 3. Stage budgets are controlled within the preauthorized ceiling.** The declared per-pass
shares are fixed and protected so an expensive early stage cannot consume the allocation reserved
for a later required product, especially Draft generation. They are not human checkpoints;
exhaustion after bounded retry and fallback is terminal. The stage shares are 45% diagnostic
(35% research plus 10% challenge), 7.5% country research, 10% AI assessment, 7.5% international
lessons, 10% foresight, 5% investment appraisal, 15% Draft generation, and 0% deterministic export.

---

## What changes where

| Layer | Work |
|---|---|
| **Model file** (`model/export_model.py`) | Per-chapter DAR bindings (E4); foresight method declaration (F1); candidate-indicator carry for milestones (F4). No ratifiable value changes. |
| **Pipeline** (Python) | Research orchestrator with a preauthorized ceiling; abstention rule (C3); prerequisite bar (C4); automated Stage 1 challenge (C5); Perplexity discovery + re-fetch (C6); isolation and bleed rejection (C7); foresight generator; investment/CBA stage; DAR generator; QC gates. `render_v17.py` untouched. |
| **App** (`dar-studio-v2`) | Durable job queue and worker (Execution 1); run orchestration, progress, spend counter (Execution 2); evidence edit semantics (D1); version history (D2); document viewing and export; Perplexity added to the search provider set. |

---

## Risks worth stating before approval

1. **The abstention threshold is the highest-leverage parameter in the system.** Calibrated
   loosely, everything reads Ready; calibrated tightly, everything reads Unverified. It is the
   only thing standing between machine-set levels and a machine-set readiness matrix, and it
   must be tuned against the Egypt and Nigeria known answers before any new country runs.

2. **An automated pass will not reach the hand-run gauntlet's depth.** Nigeria went from 21
   recorded gaps to 4 under the full tiered protocol — that took sustained, effectively
   unbounded searching. Even at $500, an automated pass will likely produce **more gaps and
   more holds** than the
   verified Egypt and Nigeria assessments. That is the honest output, not a regression, but it
   will look worse than the worked examples and expectations should be set accordingly.

3. **The whole chain inherits the diagnostic's provisionality.** The foresight report rests on
   the diagnostic; the DAR rests on both. Until the §13 rulings land, every document in the
   chain is provisional, and A3's marking is what carries that fact forward.

4. **At $500 the budget is probably no longer the binding constraint.** The limiting factor
   moves to the abstention threshold (risk 1) and the open definitions (risk 3): more searching
   does not rescue a row whose construct is unsettled. The ceiling is frozen at launch and split
   into fixed, protected stage allocations; there is no human top-up or active-run choice.

5. **Comprehensiveness carries most of its weight in chapters with no evidence base.** Chapters
   3–10 rest on judgment the pipeline does not have. The *proposed, not evidenced* marking (E3)
   is doing a great deal of work and should be visually unmistakable.

---

## Build status

*Added 24 August 2026. This section records which historical decisions gained code. The
26 August 2026 normative supersession governs wherever those decisions conflict with the
canonical workflow.*

**Built and exercised against Egypt and Nigeria.** B2 (the audition, run for the first
time — `gauntlet/loop-1/research_pipeline/AUDITION-RESULTS.md` and `VENDOR-DECISION.md`).
C1, C2, C3, C4, C6, C7 and the preauthorized budget controls of Execution 2/3, in
`research_pipeline/research_orchestrator.py` with the gates in `gates.py`. E4, F1 and F4
in the model file, enforced by the parity test and the app's loader.

**Not built — later threads.** C5 (the automated Stage 1 challenge), the broad and international scans,
and Execution 1's durable worker are Thread 3. D1 and D2 (edit semantics and versioning) live in
the app. E1's caller, E3 and E5 (the DAR generator and its gate), and F2 are Thread 4.
A1–A4 are governance statements the generators will carry.

**Three gates exist that this record did not name**, each added because the first
automated runs produced the failure it prevents, and each recorded here because it is a
rule about evidence rather than an implementation detail:

- **coherence** — a ladder row whose recorded rung and evidence fields derive a
  different level from the one the row argues for is held. A row contradicting itself
  cannot set a level that enters a pillar mean.
- **currency** — an *Adopted* or *Operating* rung resting on evidence more than ten
  years old is held. The rung asserts a present state; a document establishes only what
  was true when it was written. Ten years is a calibration parameter, not a ruling.
- **argument** — a level below 5 proposed with no negative finding is held. This is this
  record's own standard ("a level with no negative finding is an assertion") made
  mechanical.

**Risk 4 is now measured and was wrong in a useful direction.** A full 57-row Egypt pass
cost **$15**, not the ~$200 the apportionment allowed for indicator research. The
binding constraint is not budget and, on the evidence of the audition, not model
judgment either: it is retrieval depth. Figures that sit behind JavaScript database
front-ends or inside national household-survey PDFs were not reached, and the pipeline
abstained rather than guessing. Risk 1 stands exactly as written — the abstention
threshold remains the highest-leverage parameter, and there is now a measurement to tune
it against.
