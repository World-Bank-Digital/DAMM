# Thread 4 — closing the rulings, then the worker · handoff

*Written 25 August 2026. Read this, then `DECISIONS-13.md` (the twelve rulings and their
reasoning), then `gauntlet/loop-1/research_pipeline/README.md` (how the pipeline runs and
what will bite you). `THREAD-3-HANDOFF.md` is the previous brief and is now history.*

---

## Status in one paragraph

The pipeline is built, measured and run on both countries with an automated second review.
**Seven of the twelve section 13 rulings are applied**; three are open with their closing
work specified, and two were confirmed unchanged. The model is at **revision 2**,
verification is green at **75 checks**, parity at **320**, the pipeline's own rule tests at
**75**, and DAR Studio is synced and green at **135 tests**. What remains before anything
can be called production-validated is not engineering: three closing artifacts, a re-run
from a frozen configuration, and one unseen country.

---

## Where things are

| What | Path |
|---|---|
| **Model repo** | `~/DAR/Claude/DAMM` — git, remote `pcloud`, `main` tracks it |
| **App repo** | `~/Projects/dar-studio-v2` — its own git repo, **no remote configured** |
| **The rulings** | `DECISIONS-13.md` — read before touching the model |
| **Design record** | `DAR-Studio-Automation-Design.md` — 27 decisions + build status |
| **Specification** | `DAMM-v1.7-Specification.md` — §13 is the twelve |
| **Canonical model** | `model/DAMM-v1.7-model.json`, revision 2 |
| **Pipeline** | `gauntlet/loop-1/` — engine, renderer, workbook, verifier |
| **Research pipeline** | `gauntlet/loop-1/research_pipeline/` — read its README first |
| **Verified assessments** | `gauntlet/loop-1/{EGY,NGA}_v17.json` — the oracle. Derived; regenerate, never hand-edit. |
| **Automated runs** | `{EGY,NGA}_shadow*` + their comparisons + `CALIBRATION.md` |
| **Evidence package** | `Katreyna-Pipeline-Evidence-2026-08-24/` — current, **not yet sent** |
| **Vendor keys** | `.env`, gitignored. Six keys. Never printed. |
| **Vendor SDKs** | `.venv`, gitignored. The rest of the pipeline runs on system `python3`. |

Commit and push after every verified state. **There is no Time Machine on this Mac**, and
the app repo has no remote, so its commits are local only.

---

## The rulings, and what is left of them

Taken 25 August 2026 in a **simulated review exchange**, recorded as working rulings.
They should be confirmed against Katreyna's actual response before anything built on them
is described as ratified. §13 is jointly held, so the direction is proper; the
confirmation is what is outstanding.

**Applied and verified.** 13.1 bands recut to midpoint boundaries with a signed margin ·
13.2 A1 held at ten · 13.4 the 7.12 rebinding · 13.7 sub-readings nested with names
recovered from the v1.5 workbook · 13.8, 13.9, 13.10 approved with qualifications ·
13.11 confirmed · 13.12 need, readiness and outcome separated. The readiness threshold
moved to 2.5 with them and is now *derived* from the Established band edge rather than
duplicated beside it.

**Open, with the closing work named by the reviewer:**

| # | What is needed |
|---|---|
| **13.3** | An **edge-level mapping table**: which use case binds which prerequisite, edge by edge. Carries the largest open consequence in the system, below. |
| **13.6** | A **documented calibration basis** for the A1 thresholds, which are still test values. |
| **13.5** | A **row-level definition dictionary** for the 44 open definitions. The long pole, and the one every other ruling narrows. |

**The largest thing riding on 13.3.** Ruling 13.4 says 7.12 follows the use of personal or
farm-level data. *Which* columns those are is a mapping question and is not ratified. The
set carried in the model — ADV, SMF, FIN, AGI — is a **proposal**, marked as such in the
model, the engine, the workbook and the app. It is doing a great deal of work: Egypt
records 7.12 as Absent, so that one row now blocks four columns instead of one.

---

## What the two countries now show

| | Egypt | Nigeria |
|---|---|---|
| rows at the verified level (of 57) | 29 | 33 |
| prerequisites matching (of 12) | 8 | 8 |
| rows read **above** the verified assessment | 3 | 5 |
| recorded gaps (verified) | 14 (5) | 17 (4) |
| cost, both passes | about $22 | about $21 |

**All eight upward rows carry an open definitional question**, and the instrument's own
audit classes all eight as construct drift. Not one is a misread source. That is the
finding the evidence package is built on.

**Both readiness matrices now diverge, for different reasons.** Nigeria's turns on a tier
bar: its only published rural coverage estimate is T4 and the prerequisite bar admits
T1–T3, so the pipeline could not reproduce that row at any depth of searching. Egypt's
turns on a definition: the machine read 7.12 as Present where the assessors read Absent,
and under ruling 13.4 that single disagreement moves four columns. Neither is a retrieval
failure and neither is a fabrication.

**Calibration.** Six rows withheld a level in both countries; four of the six were never
reached at all. The abstention threshold is largely the wrong lever — the binding
constraint is retrieval depth. `CALIBRATION.md` names the rows.

---

## Your scope

### 1. The three closing artifacts

In the reviewer's order of difficulty: the edge-level mapping table (13.3), the
calibration basis (13.6), then the definition dictionary (13.5, 44 rows). Each is a data
artifact that closes a ruling; none is a code change.

### 2. Freeze, then re-run

Once the rules and definitions are frozen, re-run Egypt and Nigeria from the frozen
configuration. **Those runs produce the authoritative figures.** Everything currently
quoted was measured before the rulings landed, and the first-pass ledgers for both
countries were truncated by a resume defect since fixed, so the cost figures are stated as
approximations rather than read from a file.

### 3. The durable worker (app)

Thread 3's Task 3, not started. The job queue, run orchestration, progress display and
live spend counter, so DAR Studio can run the pipeline instead of a terminal. Survey the
chassis first: auth, BYOK, the engagement lifecycle and the audit trail survived the v1.5
demolition, so there may be queue machinery worth building on.

### 4. One unseen, human-shadowed country

The reviewer's condition for calling the pipeline production-validated. Neither Egypt nor
Nigeria can serve: both have hand assessments the pipeline is calibrated against. Note the
ordering — decision **B1** blocks new-country work until the §13 rulings land, so this
becomes possible only after step 2.

### Not yours

The two scans (they feed the DAR, which is Thread 5), and the foresight and DAR
generators.

---

## Traps that cost real time

- **pCloud is a `synchronous` FUSE mount and has dropped four times** under sustained
  writes. The project lives on local disk; pCloud is a publish target only. If it drops,
  zsh cannot spawn while the shell's cwd is on it — `cd ~/DAR/Claude/DAMM` first.
- **One rule, one home.** Every duplicated constant found today had drifted: the readiness
  threshold was a second copy of a band edge, the renderer carried its own band table
  still at the old values, and the engine compared against a literal rather than the
  config. The parity test and the verifier caught all three. When you change a rule, grep
  for its value.
- **Never redefine a key; replace it.** `mean` became three role means rather than being
  silently redefined, so every consumer had to be updated and the typechecker found them.
  A redefinition leaves everyone agreeing on a word and disagreeing on the quantity.
- **The app fixtures are distilled, not copied.** Use `model/export_app_fixtures.py`.
  Copying the raw assessment over them looks right and silently changes the shape.
- **Read the artifact AND the exit code.** The verification record once said "ALL CHECKS
  PASS" while the process exited 1 on a `KeyError` after the record was written.
- **Quote verification must stay script-blind.** The alphanumeric fold once kept only
  `[a-z0-9]`, so an invented Arabic quote verified as genuine. Egypt publishes in Arabic.
  `test_gates.py` checks five scripts.
- **A reviewer cannot classify its own failure.** Gate 2's withdrawal path once fired on a
  reviewer that asserted nothing; a withdrawal now requires a verified quote.
- **Correcting a rule does not require re-running.** The audition, Gate 2 and the
  orchestrator all checkpoint their evidence: `--rescore`, `--reapply`, `--resume`.
- **After changing the model**, run `model/export_model.py`, regenerate both assessments,
  run the parity test, run `verify_end_to_end.py`, then `model/export_app_fixtures.py` and
  the app's `npm test`. All five, in that order.

---

## Working rules that hold across every thread

- **Ship finished products.** Fix every defect before handing over; document only genuine
  design choices as open decisions.
- **Fixes land at the root** — spec, model, engine, renderer — never in generated outputs.
- **No level without a recorded value.** The evidence class is derived, never chosen.
- **A withheld level is not an absence.**
- **A mean never travels without its own denominator.**
- **The report is a standalone document** — no process history, no cross-references.
