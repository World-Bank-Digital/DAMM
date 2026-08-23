# DAMM v1.7 — handoff note

*Written 23 August 2026 to open a new thread. Read this first: it carries the current
state, what is decided, what is deliberately still open, and the conventions that must
not be broken. It supersedes `superseded/DAMM-REFINEMENT-HANDOFF.md` (the v1.5→v1.6
note), which is kept only as history.*

---

## Status in one paragraph

**v1.7 is built, verified end to end, and packaged for external review.** It was hardened
by a "gauntlet" — a clean-slate re-assessment of Egypt and Nigeria under one identical
process, with two of three quality gates executed and 38 defects logged and fixed at
root, then by an **external design review of the assembled package (23 Aug 2026)** which
found 8 more defects (39–46) and raised one design question. All 8 are fixed at root and
the package is rebuilt; verification now runs **72 checks, all passing** (was 63).
Nothing has been sent yet. **The next moves are: send the package → receive her rulings on
twelve design decisions → run loop 2 as the exit gate → stamp v1.7 with Randeep's G3
sign-off → rebuild DAR Studio against the ratified model.**

---

## Where everything lives

All paths relative to **`~/DAR/Claude/DAMM/`** — the project moved off pCloud to local disk on
23 August 2026 and is now a **git repository**. pCloud is a *publish target* for finished
packages, not the working tree: `~/pCloud Drive/02 World Bank/Projects/DAR/DAMM/` receives a
copy of the review package and nothing else. Work, build and verify locally; commit as you go.

| Artifact | Path | Role |
|---|---|---|
| **Specification** | `DAMM-v1.7-Specification.md` | The design record. §13 = the eleven open decisions. §14 = corrections applied before release. |
| **Guidebook** | `DAMM-v1.7-Guidebook.docx` | The method in prose, 24 pp. First document any reviewer sees. |
| **Indicator census** | `DAMM-v1.7-Indicator-Census.csv` | Per-indicator disposition of all 102 v1.5 indicators → 57. |
| **Method companions** | `DAMM-v1.7-Source-Tier-Protocol.md`, `DAMM-v1.7-QC-Protocol.md`, `DAMM-v1.7-Practice-Library-Schema.md` | Source tiers T1–T5; the three quality gates; the standing practice library (schema only — not yet seeded). |
| **Workbooks** | `gauntlet/loop-1/workbooks-v1.7/` (3 files) | The instrument: blank template + Egypt + Nigeria. **Source of truth for scoring.** |
| **Reports** | `gauntlet/loop-1/{Egypt,Nigeria}-DAR-Diagnostic.html` | The deliverable. Ten sections, standalone. |
| **Review package** | `Katreyna-Review-Package-2026-08-23/` | 24 files, assembled and integrity-checked. Ready to send. |
| **Transmittal source** | `transmittal/note.docx` | The cover note. Moved into the project — it used to live in a session scratchpad, so the package could not rebuild from the repo alone. |
| **Issues log** | `gauntlet/loop-1/issues-log.md` | 38 defects with root-cause fixes. The gauntlet's real product. |
| **Verification record** | `gauntlet/loop-1/VERIFICATION-RECORD.md` | The end-to-end run: 63 checks, all passing. |
| **Old app (frozen)** | `~/Projects/dar-studio-v2/` | Still runs the v1.3 model. To be overhauled, not patched. |
| **Published copy** | `~/pCloud Drive/02 World Bank/Projects/DAR/DAMM/Katreyna-Review-Package-2026-08-23/` | The review package only, byte-identical to the local build. Written by `build_package.sh`; never edited there. |

---

## The pipeline — how to reproduce everything

Everything downstream regenerates from the **sources of record**. Nothing is hand-edited
between generation and verification; corrections are input files, not edits to outputs.

```
cd ~/DAR/Claude/DAMM/gauntlet/loop-1

python3 build_inputs.py        # research + machine pass + 4 correction layers → {ISO}_v17_input.json
python3 engine_v17.py EGY_v17_input.json EGY_v17.json Egypt
python3 engine_v17.py NGA_v17_input.json NGA_v17.json Nigeria
python3 render_v17.py EGY      # → Egypt-DAR-Diagnostic.html  (QC gate BLOCKS emission on failure)
python3 render_v17.py NGA
python3 build_workbook_v17.py  # → workbooks-v1.7/ (3 files)

python3 verify_end_to_end.py   # regenerates ALL of the above and checks 7 stages → VERIFICATION-RECORD.md
cd .. && bash build_package.sh # assembles the package locally, then publishes to pCloud (non-fatal)

git add -A && git commit       # commit every verified state — there is no Time Machine here
```

**Sources of record** (never generated — these are the inputs):

- `machine_pass.json` — World Bank API pass (`machine_pass.py` refetches)
- `research/{EGY,NGA}_{A..G}.json` — tiered source research, 7 pillar bundles per country
- `research/{EGY,NGA}_register.json` — initiative registers
- `g1_overrides_{egy,nga}.json` — assessor confirmations (Gate 1), each with a reason
- `g2_corrections_{egy,nga}.json` — peer-review corrections (Gate 2)
- `definition_corrections_{egy,nga}.json` — the six name-vs-evidence corrections
- `definition_notes.json` — 45 open definitional questions, attached row-by-row to the workbook

**Correction layers apply in order**, and text normalization (standalone-report sanitizer
+ American spelling) runs **last**, so text introduced by any layer is covered.

---

## Current state in numbers

| | Egypt | Nigeria |
|---|---|---|
| Measured / Documented / Judged / Gap | 20 / 32 / 0 / 5 | 19 / 33 / 1 / 4 |
| Pillars | A1 3.00 Est · C1 3.80 **Adv** · C2 2.88 Est · C3 3.25 Est · C4 3.33 **(Est)** · E1 3.11 Est · O1 2.67 Est | A1 2.25 Emg · C1 2.83 Est · C2 2.57 Emg · C3 2.88 Est · C4 2.50 Emg · E1 2.56 Emg · O1 3.25 Est |
| Rated / n per pillar | A1 8/10 · C1 5/6 · C2 8/8 · C3 8/8 · **C4 3/7** · E1 9/11 · O1 6/7 | A1 8/10 · C1 6/6 · C2 7/8 · C3 8/8 · C4 4/7 · E1 9/11 · **O1 4/7** |
| Levels withheld (holds) | 5 | 7 |
| Use-case matrix | 5 **Unverified** + AGI **Blocked** | 5 **Partial** + AGI **Blocked** |
| Why | Rural mobile broadband coverage (2.1), a universal prerequisite, is not published for Egypt at any admissible tier | Rural electricity 23.5% — a universal prerequisite present but narrow — caps every column |
| Stale readings | 11 | 11 |

**Egypt's five Unverified columns are the headline finding and are correct.** The
assessment had recorded ITU's *national* coverage figure (99.8%) against an indicator
named *rural* coverage, scoring a universal prerequisite at level 5 and returning five
"Ready" columns on evidence that did not measure the thing named. It is now recorded as
the gap it is.

---

## Standing decisions (Randeep, this thread — do not relitigate)

1. **Bhutan is out of scope.** That assessment served a delivered project. Its role as a
   design *source* stands; no re-render ships.
2. **v1.7 is the gauntlet's exit stamp.** The document set was relabeled from v1.6 once
   the corrections landed; nothing had circulated externally, so there is no
   reconciliation burden.
3. **Exa (discovery) + Jina (fetch)** for the scripted research pipeline — Exa because the
   tier protocol can be enforced in API parameters. Loop 1 ran on built-in search. Keys go
   in a local `.env`, **never in chat**.
4. **Model choice by audition, not spec sheet.** A 13-cell test (10 known answers, 3
   verifiable non-existent) scoring fabrication rate, tier compliance and citation
   resolvability. Output-window size is irrelevant — the pipeline is many small tasks, not
   one long generation. A second vendor is reserved for Gate 2 independence.
5. **DAR Studio gets a complete overhaul**, not a patch: new domain layer on the proven
   chassis (auth, BYOK, engagement lifecycle, audit trail all survive). **After** gauntlet
   exit, so the config is built once.
6. **Ship finished products.** Fix every defect before sending; document only genuine
   design choices as open decisions. A package with known faults flagged as "open items"
   puts the reviewer to work finding what we already know.

---

## Design invariants (breaking these is a defect)

- **No level without a recorded value.** The evidence class is *derived* from what was
  recorded, never chosen. A T5-only citation derives `Judged`, never `Documented`.
- **A mean never travels without its own denominator.** A pillar mean averages rated rows
  only; `Rated` and `Held` print beside `n` everywhere the mean appears. Held rows keep
  their evidence class in the composition figures, so composition alone will overstate the
  base — that is exactly the trap defect 39 fell into.
- **A rendered artifact is checked as a document, not only as data.** `build_package.sh`
  fails the build if any HTML table column is missing from the PDF text. Gate 2 reads the
  evidence; nothing was reading the deliverable, which is how a cropped column shipped.
- **A withheld level is not an absence.** Where evidence measures a different construct
  from the indicator name and the level would turn on that difference, the level is
  withheld; a prerequisite so recorded reads `Unverified`, never `Absent`.
- **The report is a standalone document.** No process history, no prior passes, no
  internal cross-references (section numbers, method filenames). Agent-authored text is
  sanitized before it reaches the page.
- **No narrative claim ever sets a level.** Researched prose cites scored rows; the scored
  rows never cite the prose.
- **Tiers are reported, never weighted.** Weighting them would rebuild the confidence
  weights v1.6 removed.
- **Rounding is half-up**, matching the workbook (which is the source of truth). Python's
  banker's rounding disagrees at exact `.xx5` and would band a mean differently.
- **The four prohibitions:** no cross-country ranking · no band as a PDO/DLI/disbursement
  condition · no automatic financing decisions · no public claim before human review.
- **American spelling**, with quoted labels and proper names protected (e.g. ITU's
  `'Role-modelling'` is a quotation and must not be altered).

---

## What is open

**The twelve decisions** (specification §13) — these are Katreyna's, and loop 2 cannot
close several of them without her answers:

1. Band edges (1.8 / 2.6 / 3.4 / 4.2) — recut or keep
2. A1 additions: cereal import dependency and irrigation coverage (both measured, sitting
   unscored beneath the register in each workbook)
3. The per-use-case prerequisite mapping
4. The three binding rules now in force (7.12 → AGI; universal narrow → Partial; universal
   unverified → Unverified)
5. **Indicator definitions — the largest item.** **44 of the 57** indicators carry an open
   definitional question (a 45th sits on the irrigation candidate row, which is not one of
   the 57), attached to their own rows in the workbook. 8 of the 12 prerequisites are
   among them.
6. A1 thresholds (still test values)
7. Sub-readings display
8. Source-tier lookup and register field set
9. QC gate scope, plus the amendment §14 records
10. Practice Library schema
11. (Statement) Bhutan out of scope
12. **Whether need and outcome indicators belong in a use-case readiness mean** — opened by
    the external review. Each column averages every indicator mapped to it, including A1
    need rows and O1 outcome rows. Nigeria MKT is 2.58 with them, 2.64 without, either side
    of the 2.6 threshold, and the only column in either country whose status turns on the
    mean rather than a prerequisite. Both means now print; nothing changed pending the ruling.

**Then:** loop 2 as the exit gate (re-verification, not re-research) → v1.7 stamped with
G3 sign-off → DAR Studio 2.0.

**Also queued:** seed the Practice Library (25–30 entries); Studio v1 freeze; the loop-2
workflow fixes already identified (tier enum in the research schema, per-country lead
injection, FAOSTAT bulk-file route).

---

## Environment gotchas (all cost real time in the last thread)

- **pCloud Drive drops under sustained writes — this is why the project left it.** It failed
  four times on 23 August 2026, always during sustained writes. It is a `synchronous`
  `pcloudfs` FUSE mount, so every write blocks on the network: exactly the wrong shape for a
  pipeline that does thousands of small writes. Symptoms: `Socket is not connected`,
  `Device not configured`, then **zsh cannot spawn at all** because the working directory is
  on the dead mount — recover by moving the shell off it first (`cd ~/DAR/Claude/DAMM`).
  **Fix in place:** the project lives on local disk; `build_package.sh` assembles the package
  locally and only then copies it to pCloud, in one bulk operation, as a **non-fatal** step.
  If the mount is down the build still succeeds and prints the exact re-publish command.
- **There is no Time Machine destination configured on this Mac.** Local disk has no OS-level
  backup, which is why the project is under git. **Commit after every verified state.** The
  pCloud package copy is a convenience for sharing, not a backup of the work.
- **Never `pkill` LibreOffice unless you have confirmed it is idle.** Killing a conversion
  mid-write leaves a zombie holding a document lock that poisons every later recalculation.
  `verify_end_to_end.py` now waits for live conversions and only force-kills a genuine hang.
- **Read the artifact, not the exit code**, when a pipeline is involved: `python3 x.py |
  tail` returns `tail`'s status, which masked three failures once.
- **docx surgery:** `<w:t[^>]*>` also matches `<w:tc>` — use `<w:t(?:\s[^>]*)?>` or you will
  silently delete cell markup. And never anchor a block replacement with a plain
  `find(end)`: the Guidebook's Executive Summary repeats §9's sentences verbatim, so the
  edit lands in the wrong section while the target survives. Anchor on the unique heading,
  then search forward, and probe for **both** old-absent and new-present afterward.
- **pCloud dropped a third time**, again on the final bulk copy of the package. Recovery is
  unchanged and worked: the finished build survives at `/private/tmp/claude-501/pkgbuild/`,
  and the shell must be moved off the dead mount (`cd` elsewhere) before anything else —
  zsh cannot spawn while its cwd is on it. Re-run only the last two lines of the script.
- **Never let a text rule run over a URL.** Two live citations contain the exact strings the
  American-spelling rules rewrite (`...summer-fertiliser-season...`,
  `...silo-modernisation-efforts...`). The sanitizer now shields URLs and proper names before
  any rule runs. Adding a spelling rule without that shield silently breaks citations.
- **Calibri is not installed on this Mac.** Documents specifying it render with silent
  substitutes. The Guidebook now uses Georgia (body) + Arial (headings, tables, furniture),
  both present on macOS and Windows.

---

## Method lessons worth carrying

- **An indicator's name must be held to the evidence recorded against it.** Verifying that
  a source states a number is *not* the same as verifying the number answers the indicator.
  Gate 2 confirmed Egypt's 2.1 on exactly that blind spot; it is now a QC amendment.
- **When generalizing a single-country template, grep for every literal number, id and
  country fact in captions.** Hardcoded prose survives refactors and will state falsehoods
  on the next country — `a1_tiles()` printed "Recorded gaps — 5 of 10" on a country with
  none.
- **Depth of search, not the country, drove most apparent data scarcity.** Nigeria went
  from 21 recorded gaps to 4 under the full tiered protocol; Egypt moved the other way,
  from an apparent zero to an honest 5, once migrated evidence was re-searched rather than
  inherited.
- **The surviving gaps are mostly not country facts.** Three of four are the same
  indicators in both countries — an indicator no country can evidence is a question for the
  register.
