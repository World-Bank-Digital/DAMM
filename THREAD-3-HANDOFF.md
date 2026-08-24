# Thread 3 — Gate 2, the scans, and the worker · handoff

*Written 24 August 2026, at the close of Thread 2. Read this, then
`DAR-Studio-Automation-Design.md` (the twenty-seven decisions, with a build-status
section now at its foot), then `gauntlet/loop-1/research_pipeline/README.md` (how the
machinery runs and what will bite you). `THREAD-2-HANDOFF.md` is the previous thread's
brief and is now history — everything from it that still matters is repeated here.*

---

## Status in one paragraph

DAMM v1.7 remains built and verified: **75 checks, all passing**, and the model file
still reproduces every engine figure across **293 parity checks**. Thread 2 built the
first phase of the automated pipeline. The **vendor audition has been run** for the first
time and produced a fabrication-rate baseline of **zero**; a primary and an independent
second are chosen on measurement and recorded. The **research orchestrator** researches
all 57 rows plus the two carried candidates for one country, sets levels, and abstains
where it cannot cite rung-specific quote-verified evidence at an admissible tier. Its
acceptance test — a full shadow run of Egypt compared row by row against the verified
assessment — has been run twice: **$15, 24 minutes, 3% of the country ceiling**, and it
**reproduced the 2.1 finding**, the defect that passed a human assessor gate and an
initial peer review. Your job is what Thread 2 did not build: automated Gate 2, the two
scans, and the durable worker.

---

## Where things are

| What | Path |
|---|---|
| **Model repo** (this one) | `~/DAR/Claude/DAMM` — git repo, remote `pcloud`, `main` tracks it |
| **App repo** | `~/Projects/dar-studio-v2` — separate git repo |
| **Design record — 27 decisions + build status** | `DAR-Studio-Automation-Design.md` |
| **Model handoff** | `DAMM-v1.7-HANDOFF.md` (state, standing decisions, invariants) |
| **Specification** | `DAMM-v1.7-Specification.md` — §13 = the twelve open decisions |
| **Canonical model** | `model/DAMM-v1.7-model.json` + `export_model.py` + parity test |
| **Pipeline** | `gauntlet/loop-1/` — engine, renderer, workbook builder, verifier |
| **The new subsystem** | `gauntlet/loop-1/research_pipeline/` — read its `README.md` first |
| **Verified assessments** | `gauntlet/loop-1/{EGY,NGA}_v17.json` — **the test oracle. Do not overwrite.** |
| **The shadow run** | `gauntlet/loop-1/EGY_shadow*.json` + `SHADOW-COMPARISON-EGY_shadow.md` |
| **Vendor keys** | `.env` (gitignored). Six keys. Never print them, never put them in chat. |
| **Vendor SDKs** | `.venv` (gitignored). The rest of the pipeline still runs on system `python3`. |

Commit and push after every verified state: `git add -A && git commit && git push pcloud main`.
There is **no Time Machine on this Mac** — git is the only backup.

---

## What Thread 2 built — do not rebuild it

- **`research_pipeline/vendors.py`** — the only place an outside call is made. Keys,
  metering, pricing, the domain→tier lookup, quote verification, and a budget ceiling
  that raises rather than degrading. Nine live checks in `smoke_vendors.py`.
- **`research_pipeline/gates.py`** — seven gates in order: isolation (C7), quote (C6),
  tier (C1), construct (C3), prerequisite (C4), coherence, currency, argument. Each one
  withholds a *level* and records why; none deletes evidence.
- **`research_pipeline/research_orchestrator.py`** — per-indicator research for one
  country, checkpointed per row, resumable, producing an engine input directly.
- **`research_pipeline/run_audition.py`** + `audition_cells.json` — the thirteen-cell
  audition, with `--rescore` to re-apply a corrected rule to saved evidence for free.
- **`research_pipeline/compare_shadow.py`** — the acceptance test, including a
  `--prior` mode that measures run-to-run variance.

Derivation rules have one home each: the qualitative ladder is `build_inputs.ladder_level`
and the machine-fetchable T1 series map is `machine_pass.SERIES`. Both files were made
importable so the new pipeline shares them instead of carrying copies that would drift.
Both countries' verified inputs still regenerate **byte-identical**.

---

## What the measurements say

### The audition (`AUDITION-RESULTS.md`, `VENDOR-DECISION.md`)

Thirteen cells, five entrants, **$8.77**. Primary **`anthropic/claude-opus-5`**,
independent second for Gate 2 **`openai/gpt-5.6-terra`** — recorded as the near-tie it
is, since three entrants returned identical figures on all three governing scores.

- **Fabrication rate zero** for four of five entrants. The baseline a reviewer of a
  machine-drafted roadmap asks for now exists.
- **All five entrants detected all three non-existent constructs**, including recording
  Egypt's national coverage figure against an indicator naming *rural* coverage.
- **The binding constraint is retrieval depth, not judgment.** On four of the ten
  known-answer cells every entrant abstained, each time because the page carrying the
  answer was behind a JavaScript dashboard or inside a survey PDF the substrate did not
  deliver.
- **Quote verification catches invention; it does not catch construct substitution.**
  One entrant recorded a raw enrolment count of 121,191,781 against an indicator whose
  name ends in "(%)", and an unweighted microdata frequency as a national rate — both
  fully quote-verified. This is why the construct gate and the prerequisite bar exist
  and why they cannot be collapsed into the quote check.

### The Egypt shadow run (`SHADOW-COMPARISON-EGY_shadow.md`)

| | |
|---|---|
| Rows at the same level | **24 of 57**; of the 23 both assessments levelled, 15 exact and 21 within one |
| Prerequisites matching | **4 of 12** |
| Gaps | found **all 5** the verified assessment records; raised **17** more |
| Holds | **11**, against the verified assessment's 5 |
| **The 2.1 finding** | **Reproduced** — recorded as a gap, with the national figure named as context and refused as an answer |
| Cost and time | **$15.49**, 24 minutes, 1005 vendor calls — **3.1%** of the $500 ceiling |
| Repeatability | two independent runs agree on **53 of 57** rows (93%) |

**Read the direction of the divergences, not the headline.** Only **two** rows read
*higher* than the verified assessment, and neither is a fabrication: both turn on which
side of an unratified definitional question the evidence sits — a device financing
scheme judged without a targeting test, and a general-purpose national AI charter
accepted against an agriculture-specific row. That is decision **B1**'s warning arriving
exactly as predicted, and it is an argument for the §13 rulings rather than for more
pipeline. Twenty-four rows withheld a level the verified assessment set; one set a level
it withheld. That asymmetry *is* the abstention threshold, stated as a number.

---

## Your scope

### Task 1 — automated Gate 2 (decision C5)

Scoped to prerequisites, held rows and recorded gaps — roughly 20 rows of 57, not all of
them — prompted to refute, run on the independent second vendor. In the hand gauntlet
this earned its keep: 24 of 24 prerequisites survived attack, 12 provenance adjustments
landed, and **4 gap refutations** found what the first pass missed.

**You have a before-measurement and should use it.** Re-run `compare_shadow.py` after
Gate 2 and the delta tells you whether it earns its 15% of budget. Given the shadow run's
17 new gaps and 11 holds, the specific question is how many of those a refutation pass
converts back into evidenced rows.

### Task 2 — the broad and international scans (steps 2 and 3)

Country evidence outside the indicator set, and a free-form international strategies
scan. Note decision **E2**: the international scan feeds the **DAR only**. The diagnostic
keeps its bounded international content — at most one tier-badged precedent pointer per
strategic question, never an endorsement and never a comparison of countries.

### Task 3 — the durable worker and the app's job queue (decision G1)

Per-item checkpointing and resumability; a failure at indicator 50 of 57 must not restart
from zero. The Python side already checkpoints per row and resumes with `--resume`; what
is missing is the app-side queue, the run orchestration, the progress display and the
live spend counter (G2), plus adding Perplexity to the app's provider set.

---

## What is *not* yours

- **The foresight generator, the DAR generator, and their QC gates** — Thread 4.
- **Any new country** — still blocked until Katreyna rules on the twelve §13 decisions.
  44 of 57 definitions are open and 8 of the 12 prerequisites are among them. The shadow
  run has now demonstrated the cost of ignoring this: both of its upward divergences are
  definitional, not evidential.
- **The review package and the verified Egypt/Nigeria assessments.** Both load-bearing.
- **`render_v17.py`** — decision E1: use it as-is.

---

## Traps that cost real time

- **pCloud is a `synchronous` FUSE mount and has dropped four times**, always under
  sustained writes. The project lives on local disk; pCloud is a publish target only. If
  it drops, zsh cannot spawn while the shell's cwd is on it — `cd ~/DAR/Claude/DAMM` first.
- **Keys live in `.env`, gitignored, and never enter a transcript.** Print key *names* if
  you must, never values.
- **Vendor SDKs live in `.venv`, not in system python.** Run the research pipeline with
  `../../../.venv/bin/python`; everything else still runs on `python3`. The verifier does
  not need the venv and must keep not needing it.
- **Never `pkill` LibreOffice unless you have confirmed it is idle.** `verify_end_to_end.py`
  handles it; do not fight it. A transient recalc timing artifact can fail workbook parity
  once — re-run before investigating.
- **Read the artifact, not the exit code**, when a pipeline is involved: `python3 x.py | tail`
  returns `tail`'s status, which has masked failures.
- **Never let a text rule run over a URL.** Two live citations contain the exact strings
  the American-spelling rules rewrite. `standalone` and `americanize` are applied to
  values, notes and source titles, never to `url`. Keep it that way.
- **Perplexity throttles hardest of the six.** Its calls are serialised behind a minimum
  gap and 429s back off on `Retry-After`. Before that, four concurrent rows rate-limited
  each other and rows silently lost their discovery peer.
- **A reasoning model can spend its whole output allowance thinking and return an empty
  body.** `json_call` retries once with double the room; Gemini additionally carries a
  floor, because its thinking tokens come out of the same allowance.
- **Correcting a scoring rule does not require re-running.** Both the audition and the
  orchestrator checkpoint the retrieved pages beside the answers. Two of the audition's
  own findings were corrections to the scoring rather than to a vendor, and both were
  applied with `--rescore` for free.
- **After regenerating the model, re-copy** `model/DAMM-v1.7-model.json` →
  `~/Projects/dar-studio-v2/src/data/model_v1_7.json` and re-run the app tests.

---

## Open, and genuinely undecided

1. **The abstention threshold.** Still the highest-leverage parameter in the system, and
   now it has a measurement to tune against: 24 rows withheld where the verified
   assessment set a level, 1 the other way. Tune it against Egypt *and* Nigeria before
   any new country runs.
2. **`PRESENCE_EVIDENCE_MAX_AGE`, ten years** (`gates.py`). How old a document may be and
   still establish that something exists *now*. Set generously so it does not fire on a
   2019 act; it is a calibration parameter, not a ruling, and it has not yet fired in a
   full run.
3. **The real cost ranking.** `prices.json` carries published Anthropic rates and
   placeholder rates for OpenAI, Gemini and Perplexity, set at Opus-tier so the counter
   cannot read low. Usage counts are exact, so entering the real rates re-derives every
   past figure without re-running anything.
4. **Whether the primary vendor should stay the primary.** Three entrants tied on all
   three governing scores; the tie was broken on discovery breadth, which is a weaker
   measurement. Do not treat that choice as settled.

---

## Working rules that hold across every thread

- **Ship finished products.** Fix every defect before handing over; document only genuine
  design choices as open decisions.
- **Fixes land at the root** — spec, model, engine, renderer — never in generated outputs.
- **No level without a recorded value.** The evidence class is *derived* from what was
  recorded, never chosen.
- **A withheld level is not an absence.**
- **A mean never travels without its own denominator.**
- **The report is a standalone document** — no process history, no internal cross-references.
