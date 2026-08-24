# Vendor decision — primary and independent second

*24 August 2026. Taken from the audition in `AUDITION-RESULTS.md`, which is the
measurement; this file is the judgment made on it. The audition can be re-scored and
re-run without disturbing this record, and this record should be re-taken if it is.*

---

## The decision

| Role | Vendor | Why |
|---|---|---|
| **Primary research vendor** | `anthropic/claude-opus-5` | Tied at the top on all three governing scores; widest discovery, surfacing 64 pages of which 46 were T1–T3, and an admissible page in 12 of 13 cells |
| **Independent second, for Gate 2** | `openai/gpt-5.6-terra` | A genuinely different vendor, tied with the primary on all three scores, and the strongest of the three gpt-5.6 siblings on level accuracy and tier compliance |
| **Discovery peer** | `perplexity/sonar-pro` | Confirmed in the role decision C6 assigns it and no other — see below |
| **Not selected** | `gemini/gemini-3.1-pro-preview` | The only entrant that fabricated, and the only one that recorded two figures measuring something other than what the indicator names |

**The primary is a near-tie, and should be recorded as one.** `anthropic/claude-opus-5`,
`openai/gpt-5.6-terra` and `openai/gpt-5.6-sol` returned identical figures on
fabrication (0%), tier compliance (100%) and citation resolvability (100%), and
identical value and level accuracy (60%). Nothing in the three governing scores
separates them. Discovery breadth is the tie-breaker, and it is a weaker measurement
than the three — so if the primary needs to be swapped later, this decision should not
be treated as an obstacle.

**Cost was deliberately not used as a tie-breaker.** The Anthropic rates in
`prices.json` are published; the OpenAI and Gemini rates are placeholders set at
Opus-tier so the counter cannot read low. Comparing a real price against a placeholder
would be a measurement of the placeholder. The recorded token counts make the
comparison exact the moment the real rates are entered.

**The one tier failure left standing is real, and it errs safely.** After the two
scoring corrections, a single non-compliance survives: `gpt-5.6-luna` cited the UN
E-Government Knowledgebase — the correct source, correctly quoted, correctly valued —
and proposed **T5** for it. That is an official UN statistical database being filed as
news and vendor material. Under-tiering never inflates a claim; what it does under this
pipeline's own rules is worse than harmless and better than the alternative — a T5
citation cannot yield `Documented`, so the row would fall to `Judged`, and on a
prerequisite it would fail the C4 bar and be held. The failure mode is lost coverage,
not false confidence. It is still the reason terra and sol are preferred within the
family.

**Independence is by vendor, not by model.** The three gpt-5.6 siblings behaved almost
identically across all thirteen cells — they abstained on the same four known cells and
detected all three absences — which is what one would expect of models sharing a
lineage. A Gate 2 run on a sibling of the primary would refute very little, so the
second is drawn from a different vendor even though a sibling scored the same.

---

## What the audition established

**A fabrication baseline now exists, and it is zero.** Four of the five entrants
asserted no value across thirteen cells that they could not quote verbatim from a page
they had been given. This is the number a reviewer of a machine-drafted roadmap will
ask for and which could not be stated before today. It is a baseline *under quote
verification against a known page set*, which is the condition the pipeline itself
enforces — not a claim about unconstrained generation.

**All five entrants detected all three non-existent constructs.** Including **N1** —
recording Egypt's national 99.8% mobile broadband coverage against an indicator naming
*rural* coverage. That error passed a hand assessor gate and an initial peer review in
the verified Egypt assessment before an audit caught it; it is defect #1 in the issues
log. No entrant repeated it. Every one of them reported the national figure as context
and refused it as an answer.

**The binding constraint is retrieval depth, not judgment.** On four of the ten known
cells (K6, K8, K9, K10) every entrant abstained, and in each case the reason was that
the page carrying the answer was not among the ten they were given:

- **K6** — the ITU price basket lives behind a JavaScript dashboard that returned
  navigation text and no values.
- **K8** — the supplied pages carried absolute NIN enrolment counts with no population
  denominator, so a percentage could not be quote-verified.
- **K9** — the rural smartphone figure sits in a national household survey; the
  supplied pages offered national ownership and rural mobile-internet *use*, neither of
  which is the named construct.
- **K10** — no supplied page carried a published population estimate.

So the measured picture is a fabrication rate near zero and an abstention rate on
known-answer cells of 40%. That asymmetry is the one to act on: the system's error mode
is silence, not invention, and more retrieval depth buys more than more model.

**Quote verification catches invention. It does not catch construct substitution.**
This is the sharpest finding for the pipeline's design. On K10 the supplied Findex page
carried the number 47.1 — an unweighted frequency from a 1,000-case microdata file,
beside the page's own warning that such counts "cannot be interpreted as summary
statistics". Four entrants named that warning and abstained. One recorded 47.1 as
Nigeria's mobile money account rate, fully quote-verified. On K8 the same entrant
recorded 121,191,781 — a raw enrolment count — against an indicator whose name ends in
"(%)", again fully quote-verified.

Neither would have been caught by the quote gate, because neither was invented. Both
are exactly what decisions **C3** (abstain where the evidence measures a different
construct) and **C4** (prerequisites need T1–T3 quote-verified evidence) exist to stop,
and they are the reason those gates cannot be simplified away into quote verification
alone.

**Perplexity earned its assigned role and no more.** Its citations were the most
efficient of any proposer — 25 of 29 pages it surfaced were T1–T3, the highest ratio in
the audition — but it reached an admissible page in only 10 of 13 cells against 12 for
the leading entrants. That is a good peer and a poor primary, which is precisely the
position decision C6 assigns it: its citations are re-fetched through Jina and
quote-verified, and its prose never becomes a source of record.

---

## What this decision does not settle

- **Whether Gate 2 earns its 15%.** That needs the second vendor actually running a
  refutation pass, which is Thread 3. The shadow-run figures recorded now are the
  before-measurement for that comparison.
- **The abstention threshold.** The audition measures abstention against thirteen cells
  where the answer is known. The shadow run measures it against fifty-seven where the
  whole assessment is known, and that is the calibration that matters.
- **Real cost ranking.** Pending the OpenAI and Gemini rates in `prices.json`.
