# DAMM v1.7 — evidence from two automated runs

To: Katreyna · From: Randeep Sudan · 24 August 2026 · Digital Agriculture Maturity Model

## What this is, and what is being asked

The package sent on 23 August 2026 carried the instrument and two country assessments
produced by hand. This one is smaller and carries something different: what happened
when the same instrument was run end to end by machine, on the same two countries, with
no person in the loop between the country name and the finished assessment.

The ask has not changed. It is still the twelve decisions in section 13 of the
specification. What this package adds is evidence about four of them, gathered by
accident rather than by design, because building the automated pipeline required the
machine to apply rules that section 13 leaves open, and the places where it applied them
differently from the assessors are visible and countable.

Nothing here asks for a change to the instrument, and nothing here is a defect report.
The automated assessments are not being proposed as replacements for the two you have.
They exist to test the pipeline, and the verified assessments were used as the answer
key: the pipeline never read them, and the comparison never wrote to them.

The fourth prohibition stands over all of it. Nothing the machine produced is a claim,
and none of it has been shown to anyone outside the team.

## Where to start

| Read | Document | Why |
|---|---|---|
| 1 | This note | Two pages. The ask, and the three findings that bear on it. |
| 2 | Evidence for the twelve decisions | The substance. Section 2 is the one that matters most. |
| 3 | Appendix | The machine-generated records behind every figure quoted, unedited. |

## The three findings, before the detail

**Machine-drafted evidence can now be given a fabrication rate, and it is zero.** A
thirteen-cell test put five models from three vendors against ten questions whose answers
are recorded in your two assessments, and three questions naming statistics those
assessments record as data gaps. Four of the five asserted nothing they could not quote
from a page they had been given. All five reported all three non-existent statistics as
absent, including the one that names rural mobile broadband coverage for Egypt. That is
the error that passed an assessor gate and an initial peer review in the Egypt assessment
before an audit caught it in August 2026, and no model repeated it.

**The machine's error runs toward saying too little, not too much.** Across both
countries the automated pipeline read three rows (Egypt) and five rows (Nigeria) above
the level your assessments record, and withheld a level on fifteen rows per country where
your assessments set one. That asymmetry is deliberate and it is the safer of the
two failures, but it means an automated assessment will look thinner than a hand one, and
the thinness is the honest output rather than a fault to be tuned away.

**Almost every disagreement is definitional rather than evidential.** Of the eight rows
where the machine read higher than the assessors, every one turns on which reading of an
unratified indicator name is taken. The machine reads a name as written and reads it
permissively. The assessors read the same names restrictively. Both readings are
defensible, which is what an unratified definition means. This is why section 13.5 has
become the binding constraint on everything downstream, and why more engineering will not
move it.

## What a ruling releases

The pipeline is built, measured, and idle. A full automated assessment of one country
costs about $22 and takes about 40 minutes, against a per-country ceiling of $500 that
was set before any of it had been measured. It is not being run on any new country,
because researching against unratified definitions would industrialize the exact error
described above, at scale and at speed. The rulings in section 13 are what release it.
