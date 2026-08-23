# DAR Studio — automated pipeline design record

*Drafted 24 August 2026 from a structured design interview. **Not yet approved and not yet
built.** Twenty-seven decisions, each settled deliberately; this record exists so they can be
reviewed as a set before any code is written, and so the reasoning survives into the next
session the way the specification and handoff do.*

---

## What is being built

An automated pipeline that takes a country name and produces three documents: a **diagnostic
report**, a **strategic foresight report**, and a **draft Digital Agriculture Roadmap**. Every
step between those two points runs without a human. A single human review sits at the end, on
the completed set.

The nine steps as requested, mapped to what they actually mean against DAMM v1.7:

| # | Requested | What it is in practice |
|---|---|---|
| 1 | Web-populate all indicators | Research all 57 rows: value, source, tier, year, level, per-row argument |
| 2 | Broader roadmap research | Country evidence outside the indicator set |
| 3 | International strategies scan | Free-form scan, feeding the **DAR only** (the diagnostic stays bounded) |
| 4 | Diagnostic report | **Already exists** — `render_v17.py`, ten sections, four chart types, QC-gated |
| 5 | Exa / Jina / Perplexity | Exa + Jina as retrieval; Perplexity for discovery, its citations re-fetched |
| 6 | Foresight document upload | Ingestion path (partly recoverable from v1.5 git history) |
| 7–8 | Machine-run foresight | Scenarios → preferred future → backcasting to milestones, standalone report |
| 9 | Draft DAR | 11-chapter outline, full prose, prescriptive chapters marked *proposed, not evidenced* |

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
independent one for G2. Thirteen cells is cheap; choosing wrong costs $500 per country in
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

**C5. G2 runs automatically, with a second vendor.** Scoped to prerequisites, held rows and
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

## D. Where humans touch it

**D1. An edit supersedes, visibly.** The machine's original value, source and argument are kept
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
standalone document already verified and about to be reviewed; the DAR is a different document
with a human process in front of it.

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

**F2. Uploaded document takes precedence.** Where one is supplied, it is ingested and the
machine-run exercise is skipped.

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

**G1. A durable worker runs the Python pipeline; the app orchestrates.** Per-item checkpointing
and resumability — a failure at indicator 50 of 57 must not restart from zero. The v1.5
in-process lock and tick-polling arrangement was fragile and lost work on restart. Keeping the
pipeline in Python is also the fastest route to a working end-to-end system, since it already
runs and is verified.

**G2. $500 per country, with human top-up on exhaustion.** The run stops and reports what it
has; a person decides whether to add budget. A live spend counter is visible throughout.
Exhaustion must be *visible*, because a budget-induced gap is indistinguishable from a real one
in the output — which is how Nigeria's 21 phantom gaps happened.

**G3. Fixed per-pass allocation, with generation reserved.** Roughly: indicator research 40%,
G2 15%, scans 15%, foresight 10%, document generation 20%. Under a shared pool a pathological
research pass consumes the budget and produces no document at all — $500 spent with nothing to
review.

---

## What changes where

| Layer | Work |
|---|---|
| **Model file** (`model/export_model.py`) | Per-chapter DAR bindings (E4); foresight method declaration (F1); candidate-indicator carry for milestones (F4). No ratifiable value changes. |
| **Pipeline** (Python) | Research orchestrator with per-pass budget; abstention rule (C3); prerequisite bar (C4); automated G2 (C5); Perplexity discovery + re-fetch (C6); isolation and bleed rejection (C7); foresight generator; DAR generator; QC gates for both. `render_v17.py` untouched. |
| **App** (`dar-studio-v2`) | Durable job queue and worker (G1); run orchestration, progress, spend counter (G2); evidence edit semantics (D1); version history (D2); document viewing and export; Perplexity added to the search provider set. |

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

4. **At $500 the budget is probably no longer the binding constraint.** The apportionment gives
   roughly $200 to indicator research alone — what the entire run was budgeted at a revision
   ago — with ~$75 for G2, ~$75 for the scans, ~$50 for foresight and ~$100 reserved for
   document generation. The limiting factor moves to the abstention threshold (risk 1) and the
   open definitions (risk 3): more searching does not rescue a row whose construct is unsettled.
   The first Egypt re-run replaces this estimate with a measurement; if it lands well under the
   ceiling, the surplus buys more from widening G2 than from deepening pass one.

5. **Comprehensiveness carries most of its weight in chapters with no evidence base.** Chapters
   3–10 rest on judgment the pipeline does not have. The *proposed, not evidenced* marking (E3)
   is doing a great deal of work and should be visually unmistakable.

---

*Nothing in this record is built. It awaits confirmation.*
