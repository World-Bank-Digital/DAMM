# Thread 2 — research pipeline · handoff

*Written 24 August 2026. Read this, then `DAR-Studio-Automation-Design.md`. Between them they
carry everything: what is already built and verified, the twenty-seven design decisions settled
by interview, your scope, your acceptance test, and the traps that cost real time.*

---

## Status in one paragraph

DAMM v1.7 is built and verified (72 checks). A 24-file review package for Katreyna Schroeder is
finished and **being sent** — it is not yours to touch. DAR Studio has been rebuilt on v1.7: the
v1.5 domain layer is retired (−23,399 lines), and the app now carries a zod-validated model
loader and a scorer held figure-for-figure to the assessment pipeline's own Egypt and Nigeria
outputs. A design interview then settled **27 decisions** for an automated research-and-drafting
pipeline; they are recorded in `DAR-Studio-Automation-Design.md` and **are not to be
relitigated**. Vendor API keys are now in place. Your job is the first build phase: the model
file changes, the vendor audition, and the research orchestrator — proven by a shadow run of
Egypt against the verified assessment.

---

## Where things are

| What | Path |
|---|---|
| **Model repo** (this one) | `~/DAR/Claude/DAMM` — git repo, remote `pcloud`, `main` tracks it |
| **App repo** | `~/Projects/dar-studio-v2` — separate git repo |
| **Design record — read this** | `DAR-Studio-Automation-Design.md` (27 decisions) |
| **Model handoff** | `DAMM-v1.7-HANDOFF.md` (state, standing decisions, invariants) |
| **Specification** | `DAMM-v1.7-Specification.md` — §13 = the twelve open decisions |
| **Canonical model** | `model/DAMM-v1.7-model.json` + `export_model.py` + parity test (293 checks) |
| **DAR chapter bindings** | `dar_outline` in the model file — what each chapter may cite |
| **Pipeline** | `gauntlet/loop-1/` — engine, renderer, workbook builder, verifier |
| **Verified assessments** | `gauntlet/loop-1/{EGY,NGA}_v17.json` — **the test oracle. Do not overwrite.** |
| **Vendor keys** | `.env` (gitignored). Six keys, all set. Never print them, never put them in chat. |
| **Review package** | `Katreyna-Review-Package-2026-08-23/` — finished, being sent. Do not modify. |

Commit and push after every verified state: `git add -A && git commit && git push pcloud main`.
There is **no Time Machine on this Mac** — git is the only backup.

---

## What is already built — do not rebuild it

- **The model is canonical and machine-readable.** `model/export_model.py` generates
  `DAMM-v1.7-model.json` from the engine; `reference_scorer.py` scores from that file alone and
  `test_model_parity.py` proves it reproduces every engine figure (276 checks). Verifier stage 8
  keeps it from drifting.
- **The diagnostic report renderer works.** `render_v17.py` emits ten Playbook-tagged sections,
  four chart types, standalone, with an **emit-blocking QC gate**. It survived a gauntlet and an
  external review. Decision E1: **use it as-is.** Do not rewrite it.
- **The app's domain layer is v1.7.** `src/lib/damm-v17/` — validated loader, scorer, evidence
  bridge, server actions, workspace UI. 123 tests pass; typecheck and lint clean.
- **`verify_end_to_end.py` regenerates and checks everything** — 8 stages, 72 checks. Run it
  before and after your changes; it must stay green.

---

## Your scope

### Task 0 — model file changes — **DONE, do not redo**

Completed 24 August 2026 (decisions E4, F1, F3, F4). What exists now:

- **`dar_outline`** — the 11 chapters, each with a `binding` naming the pillars, indicators,
  use cases, prerequisites and derived sources it may cite, plus `kind`
  (diagnostic / prescriptive) and a `note`. Chapter 2's description was rewritten: the v1.5
  original named CMS/EMS/OES, stages and core gates, none of which exist any more.
  **Chapter 5 (Costs and financing) binds no pillar at all**, and its note states in capitals
  that the model carries no cost, budget or financing data of any kind — the only quantities
  available are initiatives' own reported scale figures from the register.
- **`derived_sources`** — the closed vocabulary a binding may draw on.
- **`foresight`** — method, three named steps, `ratified: false`, and `milestone_binding`
  (indicator_id · target_level · target_year) with the candidate fallback.
- **`candidate_indicators`** — id pattern, required fields, and the `never` list barring a
  candidate from every mean, every prerequisite and the readiness matrix.

Enforced in three places: `test_model_parity.py` (**293 checks**, up from 276), the app's zod
loader (an unresolvable binding is a build error, not a silent hole), and 10 new app tests.
**The invariants were negative-controlled** — five deliberate violations injected, all five
caught. Verification is **76 checks, all passing**; the app is **133 tests**, typecheck and lint
clean. The model has been copied to the app; both repos are committed and pushed.

### Task 1 — vendor audition (decision B2) — **start here**

Standing decision 4 fixes the method and **it has never been run**: 13 cells — 10 with known
answers, 3 naming things that verifiably do not exist — scored on **fabrication rate, tier
compliance and citation resolvability**. Six keys are available (Exa, Jina, Perplexity,
Anthropic, OpenAI, Gemini).

Output: a primary vendor and an independent second for G2, chosen on measurement, not
preference. Record the results in the repo — the fabrication-rate baseline is the number a
reviewer of a machine-drafted roadmap will ask for, and it cannot currently be stated.

### Task 2 — research orchestrator

Per-indicator research producing: value, source, source URL, **proposed tier**, year, level, and
a rung-by-rung argument including the **negative finding** (why the next level up was not
proposed). Decisions that govern it:

- **C1** — source quality is a **tier**, never a score. A non-numeric data-quality flag may
  accompany it. No credibility number: v1.6 removed confidence weights deliberately.
- **C2** — the machine sets levels; no human confirmation step.
- **C3** — **the machine may abstain.** Where it cannot cite rung-specific, quote-verified
  evidence at an admissible tier, it sets a **ratification hold**: level withheld, row leaves
  every mean, report says so.
- **C4** — the twelve **prerequisites require T1–T3 quote-verified** evidence or the machine
  holds. Their leverage is disproportionate: rural electricity at level 2 rather than 3 flips
  every Nigerian column from Ready to Partial.
- **C6** — **Perplexity is a discovery peer only.** Its returned citations are re-fetched
  through Jina, quote-verified against page text, and tiered. Perplexity never appears as a
  source of record: a synthesised answer has neither a publisher nor an archivable document,
  and the tier protocol requires both.
- **C7** — **hard country isolation.** One country context per research task; prompts generated
  per country with no shared lead lists; results naming another country's entities rejected
  automatically. This closes issues-log defect **#11** ("Egypt bundle-C prompt carried Nigeria
  leads"), still open.
- **G2/G3** — **$500 per country**, human top-up on exhaustion, live spend counter. Fixed
  per-pass allocation with document generation reserved. Exhaustion must be **visible**: a
  budget-induced gap is indistinguishable from a real one, which is how Nigeria's 21 phantom
  gaps happened.

---

## Your acceptance test — the Egypt shadow run

Run the pipeline on Egypt and write the result to a **separate** assessment. Do **not** overwrite
`EGY_v17.json`. Then produce a comparison report answering:

1. How many of the 57 rows land on the same level as the verified assessment?
2. Do all **twelve prerequisites** match? (This is the one that matters most — they gate the
   whole readiness matrix.)
3. Does it find the five recorded gaps, or manufacture new ones?
4. **Does it reproduce the 2.1 finding** — that no admissible rural mobile-broadband figure is
   published for Egypt — or does it repeat the original defect and record the national 99.8%
   against an indicator naming *rural*?
5. What did it cost, and how long did it take?

Question 4 is the single sharpest test in the project. That defect passed an assessor gate *and*
an initial peer review before an audit caught it; if the automated pipeline reproduces the
finding, it has earned real trust.

**Expect divergence, and do not treat it as failure.** The verified assessments came from
sustained human-directed searching — Nigeria went from 21 recorded gaps to 4 that way. A first
automated pass will produce more gaps and more holds. The useful output of this thread is the
**measured delta**, because it tells you how to calibrate the abstention threshold — which the
design record names as the highest-leverage parameter in the whole system. Too loose and
everything reads Ready; too tight and everything reads Unverified.

Note also that Thread 2 runs **without** automated G2 (that is Thread 3). Keep the shadow-run
numbers: when G2 arrives, re-running the comparison tells you whether it earns its 15% of budget.

---

## What is *not* yours

- **Automated G2, the broad and international scans, the app's job queue and worker** — Thread 3.
- **Foresight generator, DAR generator, their QC gates** — Thread 4.
- **Any new country** — blocked until Katreyna rules on the twelve §13 decisions. 44 of 57
  definitions are open; researching against unratified constructs industrialises the exact
  defect described above (decision **B1**).
- **The review package, and the verified Egypt/Nigeria assessments.** Both are load-bearing.

---

## Traps that cost real time

- **pCloud is a `synchronous` FUSE mount and has dropped four times**, always under sustained
  writes. The project lives on local disk for this reason; pCloud is a publish target only. If
  it drops, zsh cannot spawn while the shell's cwd is on it — `cd ~/DAR/Claude/DAMM` first.
- **Keys live in `.env`, gitignored, and never enter a transcript.** Standing decision 3. Print
  key *names* if you must, never values.
- **Never `pkill` LibreOffice unless you have confirmed it is idle** — killing a conversion
  mid-write leaves a zombie holding a document lock that poisons every later recalculation.
  `verify_end_to_end.py` handles this; do not fight it. A transient recalc timing artifact can
  fail workbook parity once — re-run before investigating.
- **Read the artifact, not the exit code**, when a pipeline is involved: `python3 x.py | tail`
  returns `tail`'s status, which has masked failures.
- **Never let a text rule run over a URL.** Two live citations contain the exact strings the
  American-spelling rules rewrite. The sanitizer shields URLs and proper names; keep it that way.
- **After regenerating the model, re-copy** `model/DAMM-v1.7-model.json` →
  `~/Projects/dar-studio-v2/src/data/model_v1_7.json` and re-run the app tests (123 must pass).

---

## Working rules that hold across every thread

- **Ship finished products.** Fix every defect before handing over; document only genuine design
  choices as open decisions.
- **Fixes land at the root** — spec, model, engine, renderer — never in generated outputs.
- **No level without a recorded value.** The evidence class is *derived* from what was recorded,
  never chosen.
- **A withheld level is not an absence.**
- **A mean never travels without its own denominator.**
- **The report is a standalone document** — no process history, no internal cross-references.
