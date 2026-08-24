# Evidence for the Twelve Decisions

DAMM v1.7 · 24 August 2026 · Randeep Sudan

---

## 1. What Was Run, and How

Three exercises were carried out between 23 and 24 August 2026, none of which existed
when the review package was assembled.

**The vendor audition.** Standing decision 4 fixed a method for choosing a research model
and the method had never been run. Thirteen cells: ten whose answers are recorded in the
Egypt and Nigeria assessments, and three naming statistics those assessments record as
data gaps after a documented tier-ordered search. Five models from three vendors were
given an identical set of fetched pages for each cell and scored on fabrication rate,
tier compliance, and citation resolvability. The exercise cost $8.77 and fetched 120
pages.

**Two automated country assessments.** The pipeline researches all fifty-seven indicator
rows and the two carried candidates for one country, proposes a source and a tier for
each, sets a level, and records a rung-by-rung argument including the negative finding
for every level below five. It then runs a second review on the rows where being wrong
costs the most, using a different vendor, and applies whatever survives. A first pass
costs about $15.50 and takes about 25 minutes; the second review costs about $6.20 and
takes about 13 minutes. Both countries were assessed for roughly $22 each.

**A comparison against the verified assessments.** Every automated row was compared with
its counterpart in your assessments. The pipeline did not read those assessments at any
point, and the comparison does not write to them.

It is important to point out what these figures do not establish. Two countries is a
small base, one vendor did the first pass in both, and each country was assessed once.
Two independent runs of the Egypt first pass agree on 53 of 57 rows, so a difference of
one or two rows anywhere below is inside the noise and only larger patterns should be
read as findings.

### Results in Summary

| | Egypt | Nigeria |
|---|---|---|
| Rows at the level your assessment records (of 57) | 29 | 33 |
| Prerequisites at the same status (of 12) | 8 | 8 |
| Rows read **above** your assessment | 3 | 5 |
| Levels withheld where your assessment set one | 15 | 15 |
| Recorded gaps (your assessment) | 14 (5) | 17 (4) |
| Cost, both passes | about $22 | about $21 |

---

## 2. Indicator Definitions (Decision 13.5)

Section 13 calls this the largest item, with 44 of 57 rows carrying an open definitional
question and 8 of the 12 prerequisites among them. The automated runs give that item a
measurable consequence, and it is the finding in this package most worth your time.

The case for leaving the definitions as they are is real and should be stated first. Each
of the 44 questions was raised by the instrument's own audit rather than by a reader, the
proxies chosen are defensible, and the two hand assessments were completed without any
of them being resolved. An assessor who knows the sector applies a sensible reading and
moves on, and thirty of the forty-four are recorded as a defensible but measurably
different proxy rather than as a construct error.

A machine does not have that judgment, and this is where the cost becomes visible.
**Every one of the eight rows where the automated pipeline read above your assessment, in
both countries, carries an open definitional question, and the instrument's own audit
classifies all eight as construct drift.** Not one of them is a case of the machine
misreading a source. In each, the machine took the name as written and read it
permissively, and the assessors read the same name restrictively.

**Device financing and subsidy schemes (Egypt, 2.11).** Your assessment records level 1
and states that no government or telecommunications operator scheme targeting low-income
or rural users was found. The machine recorded level 3, citing the ProGIG initiative run
by Egypt's National Telecommunication Institute with Nasser Social Bank, which offers
soft loans for the purchase of laptops. The name fixes neither a targeting test nor
whether a subsidy is required. The assessor applied a targeting test and found nothing;
the machine applied none and found something.

**Responsible-AI safeguards, consent and rights (Egypt, 7.12).** Your assessment records
level 1 and states that no agriculture-specific consent or farmer-data-rights safeguards
exist beyond the general regime. The machine recorded level 3, citing the Egyptian
Charter for Responsible AI issued by the National Council for Artificial Intelligence in
2023. The assessor required the safeguards the name specifies; the machine accepted a
general instrument that does not use the words consent or rights.

**Inter-ministerial coordination mechanism (Nigeria, 4.9).** Your assessment records
level 1. The machine recorded level 3 on a United Nations record of a Nigerian
inter-ministerial committee, reading the name as satisfied by a committee that exists and
meets. The assessor read it as requiring a mechanism that coordinates.

The eight are 2.11, 3.8 and 7.12 in Egypt, and 4.9, 6.4, 6.12, 7.2 and 8.12 in Nigeria.
Three are set out below.

The second review does not correct this class of error, and it is worth being clear about
why. On Nigeria's farmer registry (3.3) it did: the first pass recorded level 3 and the
review returned it to your level 2, after reading the Ministry's own description of a
November 2025 event as a stakeholder workshop written in prospective language. But 4.9
above was created by that same review, which filled a gap the first pass had left. The
reviewer reads sources more carefully than the first pass. It reads the same unratified
names, and gains nothing on them.

The pattern is consistent across both countries and points in one direction. A permissive
reading of an unratified name produces a higher level, higher levels move prerequisites,
and prerequisites move whole columns of the readiness matrix. In this sense the
definitions are not a documentation item. They are the mechanism by which an automated
assessment becomes either conservative or generous, and at present the model does not
specify which.

---

## 3. The Binding Rules and the Tier Bar (Decisions 13.4 and 13.8)

One row moved every column of Nigeria's readiness matrix, and the ruling that would
prevent it sits across two of the twelve items.

Your Nigeria assessment reads Partial on five use-case columns and Blocked on the sixth.
The automated assessment reads **Unverified on all six**. The cause is a single row: rural
mobile broadband coverage (2.1), which your assessment records as Present at level 3 and
the machine withheld. Binding rule *universal-unverified* then returns every column
Unverified, on the stated ground that a known blocker outranks an unknown one. The rule
did exactly what it says. The question is whether what it says is what you want when the
levels are machine-set.

The reason the machine withheld 2.1 is the more consequential half. Your assessment
records rural 4G population coverage at 48 percent for 2024, sourced to GSMA geospatial
analysis, at tier 4. The pipeline requires tier 1 to tier 3 quote-verified evidence for a
prerequisite, on the ground that a one-level error in a prerequisite propagates to six
columns. **The automated pipeline therefore could not have reproduced your Nigeria 2.1
level at any depth of searching.** The bar would have withheld it whatever the machine
found, because the only published estimate is modelled and modelled estimates sit at tier
4.

Two readings are available and the choice is yours. Either the bar is right and a
universal prerequisite resting on a modelled tier 4 estimate should read Unverified, in
which case Nigeria's matrix reading is a correction rather than a loss. Or the bar is too
high for an indicator that no one measures directly, in which case the tier assignment in
decision 13.8 needs to say so explicitly, because a general rule that tier 4 cannot carry
a prerequisite will keep producing this result in every country where rural coverage is
modelled rather than measured. That is most of them.

Egypt is the control, and it now reads well. Its 2.1 is a recorded gap in both
assessments, so the rule has nothing to bite on, and **the automated Egypt matrix
reproduces your Egypt matrix cell for cell**: Unverified on five columns and Blocked on
agricultural intelligence, exactly as your assessment records it. The same machinery that
turns every Nigerian column Unverified leaves every Egyptian column where you put it.

That contrast is the useful part. The rule is not new and it is not misfiring. What is new
is that an automated pass reaches the withheld state far more often than a hand pass does,
so a rule that rarely fired now fires whenever a single universal prerequisite rests on
evidence the tier bar will not take. In Egypt no universal prerequisite does. In Nigeria
one does, and six columns follow it.

---

## 4. Quality Control and the Scope of Gate 2 (Decision 13.9)

Section 14 records an amendment to the QC Protocol: peer review must ask whether the
evidence answers *this* indicator, not only whether the source states the number. The
audition provides direct evidence for that amendment, and the evidence is stronger than
expected.

Quote verification, which checks that every recorded value appears verbatim in the page
cited, caught invention completely. Across thirteen cells and five models there was one
fabricated citation, from a single model, and four of the five models produced none.

Quote verification did not catch construct substitution at all. On the Nigeria digital ID
row, one model recorded 121,191,781, a raw count of National Identification Number
enrolments, against an indicator whose name ends in "(%)". On the Nigeria mobile money
row, the same model recorded 47.1, an unweighted frequency drawn from a thousand-case
microdata file, from a page that carries an explicit warning that such counts cannot be
interpreted as summary statistics. Both figures were verbatim on the pages cited, and
both passed quote verification without difficulty. Four of the five models named the
warning and declined to record a value.

In short, the check that stops fabrication and the check that stops the wrong number
being recorded are different checks, and only the second is a construct test. The section
14 amendment is what closes that gap, and the audition suggests it should be ratified as
written rather than softened.

One figure bears on the scope of Gate 2. The design work assumed a second review would
cover roughly twenty rows. Scoped as intended, to prerequisites, withheld levels, and
recorded gaps, it covered 38 rows in Egypt and 36 in Nigeria, because an automated first
pass withholds more often than a hand one. It cost $6.35 in Egypt and $5.99 in Nigeria,
against an allocation of $75, and changed four levels in the first and five in the second.
It is cheap and it earns its place, but its scope is a function of how conservative the
first pass is, and that in turn is a function of section 13.5.

---

## 5. The Source-Tier Lookup (Decision 13.8)

The starter domain-to-tier lookup in the Source-Tier Protocol has been implemented as
code, which means it can now be applied identically to every country and every row rather
than remembered. Implementing it surfaced two assignments the written protocol does not
resolve, both of which produced wrong answers before they were fixed by hand.

The first is the World Bank's own domains. Analytical reports and flagships are published
at `openknowledge.worldbank.org`, which is a subdomain of the same host that serves the
statistical databases. A lookup keyed on the shorter name files a flagship report as an
official statistic. The second is the United Nations. `publicadministration.un.org` serves
the E-Government Knowledgebase, a statistical database, while `news.un.org` serves the
organization's newswire, and the protocol's tiers put those four tiers apart.

Both were resolved provisionally in code, the first as tier 2 and the second as tier 1
with the newswire held at tier 5. Ratifying them, together with the two open judgment
calls the protocol already flags on national statistical offices with documented quality
concerns and on donor project completion reports, would make the lookup deterministic.
The practical value of that is not tidiness. A ratified lookup is executable, and an
executable lookup applies the same tier to the same publisher in Cairo and in Abuja
without an assessor having to remember what was decided last time.

---

## 6. Where the Runs Are Silent

Six of the twelve decisions gained no evidence from this work and should be read as
untouched by it: band edges (13.1), A1 thresholds (13.6), sub-readings display (13.7),
the Practice Library schema (13.10), Bhutan's exclusion (13.11), and the per-use-case
prerequisite mapping (13.3), which the runs applied without testing.

Two gained something slight. On the A1 candidates (13.2), the machine located Egypt's
irrigation figure at 100 percent of cultivated area against the 94.21 percent your
assessment records from AQUASTAT for 2023, and found neither candidate for Nigeria and
neither import-dependency figure for either country. Three of the four candidate cells
came back empty, so the candidates are not reliably findable. On whether need and outcome indicators belong
in a readiness mean (13.12), the automated runs withhold enough levels that use-case means
rest on fewer rows than in your assessments, which makes any status driven by the mean
rather than by a prerequisite thinner than it looks. Neither observation is strong enough
to argue from.

---

## 7. What This Does Not Claim

The automated assessments are test output. They have not been reviewed, they are not
proposed for any use, and they should not be read as second opinions on Egypt or Nigeria.
Where they disagree with your assessments the presumption is that your assessments are
right, and the value of the disagreement is diagnostic.

The verified assessments are the best available answer rather than the truth, and the
comparison is calibrated against them for want of anything better. The pipeline has not
been run on any country outside the two that already have hand assessments, and it will
not be until the section 13 rulings land.

Lastly, it is important to mention that the abstention behaviour described throughout
this note is a design choice and not an accident. The pipeline is built to withhold a
level rather than to guess one, on the ground that a withheld level is visible and a
guessed one is not. Roughly two thirds of the rows that both countries withheld were
rows whose evidence the pipeline never reached, rather than rows it read and declined to
score. Those are a retrieval problem with named sources and a known fix. They are not an
argument for relaxing the rule.

---

## 8. The Decision That Releases the Rest

The engineering is finished and measured. What it is waiting on is not more engineering.

Every automated assessment produced so far rests on 44 indicator definitions that have
not been ratified, and every material disagreement between the machine and your assessors
comes from that fact rather than from the evidence, the vendors, or the cost. A ruling on
section 13.5, taken with the tier assignment in 13.8 and the binding rules in 13.4,
determines whether an automated national assessment reads conservatively or generously,
and it determines it once for every country the instrument is ever applied to. Extensive
commitment at the point of ruling is what converts a working pipeline into one that can
be trusted with a country that has no hand assessment to check it against.
