# DAMM v1.7 — Global Practice Library (schema)

One page · 22 August 2026 · Companion to `DAMM-v1.7-Specification.md` §9 context rules · Review items in spec §13.7

**What it is.** A standing, country-agnostic register of digital-agriculture practices with evidence — the reusable asset behind (i) the one-line **precedent pointers** on a diagnostic's strategic questions and (ii) the **Precedents note** produced at Playbook Step 2 (≤10 entries, 3–5 pages, in the Step 2 pack — never a chapter of the diagnostic). Roughly 80% of practice evidence is country-invariant; writing it once and joining it per country beats rewriting it per DAR and drifting.

**What it is not.** Not benchmarking. Entries describe what happened somewhere, with tiered evidence; the library never scores, ranks, or compares countries (prohibition 1 applies to it in full).

## Entry schema (one row per practice/program)

| Field | Content |
|---|---|
| id, name, geography | Stable id · program name · country/region |
| Use-case areas | ADV / SMF / MKT / SCM / FIN / AGI (≥1) |
| Constraint tags | The A1-type problems it addresses: yield · post-harvest loss · market access · credit · climate · inclusion |
| Intervention type | registry · advisory · index insurance · e-subsidy · mechanization marketplace · traceability · market platform · data governance · … |
| **Prerequisite pattern** | Which of the 12 DAMM prerequisites it needed to work (e.g. e-subsidy → 3.3 + 4.7; USSD advisory → 2.1 only). **This is the join key.** |
| Scale achieved | Number + unit, source-tiered; vendor-reported figures marked as claims |
| Results evidence | Effect sizes with citation, **T1–T2 only**; "no independent evaluation located" is a recordable value |
| Failure modes | Documented problems (elite capture, payout delays, network failure) — closures and failures are entries, not exclusions; GES belongs here as much as AgriStack |
| Cost data | Where public, with tier |
| Status | Operating / Closed (+ year) |
| Context tags | smallholder share band · rainfed vs irrigated · connectivity band · federal/unitary |
| Sources | Deep links + access dates + tiers; T4–T5 archived |
| Last verified | Date; re-verify at 12 months or on use, whichever first |

**Evidence rules (stricter than the diagnostic's register, because the library is reused and errors compound):** results claims T1–T2 only · existence and scale T3–T4 · **T5 excluded entirely**.

## The relevance join (Step 2)

Candidates = entries whose use-case areas intersect the country's **Ready/Partial columns**, and whose prerequisite pattern either (a) fits within the country's Present (+narrow) prerequisites — *adoptable now* — or (b) contains exactly the country's **named blockers** — *what-it-took precedents* for clearing them. Rank by context-tag overlap; the TTL curates to ≤10 for the Precedents note. The matrix selects; narrative never does.

**Diagnostic hook:** a strategic question may carry at most one pointer, drawn only from entries meeting the evidence rules, framed as an existence proof.

## Seeding and storage

Seed with 25–30 entries from the DARs in hand (Egypt, Nigeria, Bhutan research trails) plus the canonical cases: India AgriStack · Kenya DigiFarm / Kilimo Salama · Rwanda Smart Nkunganire · Ethiopia 8028 hotline · Digital Green (evaluated, T2) · ACRE Africa · Hello Tractor · EMBRAPA digital · and Nigeria's own GES/ABP as domestic failure-mode evidence. Each subsequent DAR contributes one pass. Storage: `practice-library.json` beside the model (columns = this schema); per-country Precedents notes render from it.
