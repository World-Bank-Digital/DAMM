# The twelve section 13 decisions — working record

*Opened 24 August 2026. Section 13 is headed "Open for review (Katreyna + Randeep)", so
these are rulings to be taken jointly rather than requested. This file records each one
as it is settled: the question, the evidence, the options with their consequences, the
ruling, and what changes in the model when the ruling lands.*

*A ruling here is a data change. Every value the twelve decisions can move is data in
`model/DAMM-v1.7-model.json`, so ratifying one edits the model and bumps `revision`.
Nothing is rebuilt.*

**Order of work.** 13.11, 13.1, 13.6, 13.2, 13.12, 13.3, 13.4, 13.8, 13.7, 13.9, 13.10,
13.5. Quick and structural first; 13.5 last, because it is 44 sub-items and every other
ruling narrows it.

| # | Title | Status |
|---|---|---|
| 13.11 | Bhutan out of scope | **Confirmed**, no change |
| 13.1 | Band edges | Put for ruling — recut to 1.5/2.5/3.5/4.5 recommended |
| 13.6 | A1 thresholds | Not yet opened |
| 13.2 | A1 additions | Not yet opened |
| 13.12 | Need and outcome in the readiness mean | Not yet opened — carries evidence from 13.1 |
| 13.3 | Per-use-case prerequisite mapping | Not yet opened |
| 13.4 | The three binding rules | Not yet opened |
| 13.8 | Source-tier lookup | Not yet opened |
| 13.7 | Sub-readings display | Not yet opened |
| 13.9 | QC gate scope | Not yet opened |
| 13.10 | Practice Library schema | Not yet opened |
| 13.5 | Indicator definitions | Not yet opened |

---

## Continuous scoring, and what the Bhutan assessment settles

*Opened 25 August 2026, from a proposal to score every indicator on a continuous 0 to 5
scale by ratio to the cut points, so that Egypt's innovation index of 24.7 against a cut
of 25 would record as 0.988 rather than as level 1. Not one of the twelve, but it bears
on 13.1 and 13.6 and is recorded here so the reasoning survives.*

### The proposal is coherent, and compatible with the levels

On a piecewise-linear reading the continuous score and the discrete level agree exactly:
level equals the integer part plus one. Egypt's 24.7 gives 0.988 and level 1; Nigeria's
cereal yield of 1558 gives 1.039 and level 2; Egypt's rural electricity of 100 gives 5.000
and level 5. So a 0 to 5 continuous axis and 1 to 5 level labels are not in conflict, and a
mean built from continuous values would move smoothly rather than jumping by a whole level
when one row is re-read, which would dissolve much of the band-edge fragility recorded
under 13.1.

### Three things stop it becoming the scored quantity

**It reaches about a third of the register.** Egypt has 20 of 57 rows carrying a number,
Nigeria 19. The remainder are 25 ladder indicators, where Absent, Announced, Adopted and
Operating are discrete states with nothing to interpolate between, and 12 or 13 threshold
rows carrying an assessor level and no number. A pillar mean would average a precise third
against a discrete two-thirds.

**Its precision comes from cut points that are not ratified.** Egypt's innovation index of
24.7 scores 0.988 on the current cuts, 1.313 if the first cut were 20, and 0.823 if it were
30. The discrete level is 1 in all three. The added resolution is more sensitive to the
unsettled parameter than the thing it refines, and 13.6 records the A1 thresholds as test
values while 13.5 leaves 44 definitions open.

**It asserts linearity inside a band.** Interpolating between cuts claims that rural
electricity rising from 20 to 40 percent is the same increment of readiness as 60 to 80.
Banding exists to decline that claim.

### What the Bhutan assessment shows

Bhutan (March 2025) is out of scope as an assessment and stands as a design source under
13.11. It resolved this exact question the same way: all 97 indicators carry a whole-number
level with the measured value recorded beside it, and there is not one fractional level in
the register. It also used the same band edges, 1.8 / 2.6 / 3.4 / 4.2, which confirms the
specification's note that they are inherited from v1.5 and were never justified.

Bhutan then did three things v1.6 and v1.7 deliberately removed, and continuous scoring
would make all three easy again: an overall maturity score of 2.29 out of 5, layer weights
of 0.20 / 0.35 / 0.25 / 0.20 to produce it, and a Data Confidence rating. Its own figures
show the cost. Thirty-two of its 97 indicators were rated Low or Estimated, and every one
of them still received a level that fed the headline number. Nothing was withheld: zero
gaps, zero holds, in a register where a third of the evidence was acknowledged weak. That
is the failure the ratification hold and the abstention rule were built to prevent.

**Position: keep the whole-number level as the scored quantity, and carry the continuous
value as recorded data and optional display.** Revisit promoting it only after 13.5 and
13.6 land, since ratified cut points are what the added precision would have to rest on.

### One thing to adopt from Bhutan: an indicator scope tag

Bhutan tags every indicator **Global** or **Local**, according to whether an international
body publishes it for every country or it has to be found nationally. This register carries
no equivalent: `method` says how a row is scored and the tier says what a source turned out
to be, but nothing says in advance where the data should live.

| Bhutan rows | n | rated Low or Estimated |
|---|---|---|
| Global | 27 | 0 (0 percent) |
| Local | 70 | 32 (46 percent) |

All seven rows that both automated country runs failed to reach are tagged Local: 1.6, 1.7,
2.7, 3.11, 4.5, 4.7 and 6.9. Seven of seven is suggestive rather than decisive on its own,
since 72 percent of Bhutan's register is Local; the confidence split is the stronger and
independent signal.

The tag would earn its place twice. The research pipeline currently searches Global and
Local rows identically, when it should go to the international database first for one and
to the national statistical office and the responsible ministry first for the other. And on
the page it tells a reader that a thin Local row is structurally thin rather than the
product of a lazy search.

**Proposal: add `scope: global | local` to the 57 indicators in v1.8, alongside the band
recut.** It changes no score, it is a property of the indicator rather than of the country
so it is set once, and it is the first change identified that would improve retrieval on
the rows the pipeline reaches least well.

---

## 13.11 Bhutan out of scope

**The question.** Section 13 records this as a statement rather than a question: Bhutan
is out of scope for this release, its role as a design source in section 2 stands, and no
re-render ships.

**Ruling: confirmed, no change to the model.** It duplicates standing decision 1 and
governs no field (`governs` is empty in the model file). It is carried in section 13 for
completeness of the record, not because anything turns on it.

---

## 13.1 Band edges

**The question.** The five bands are cut at 1.8 / 2.6 / 3.4 / 4.2. Recut them now that
nothing downstream consumes them, or keep them for continuity?

### Why the edges are where they are

The scale runs 1 to 5, so its range is 4.0, and five equal bands make each 0.8 wide. The
specification carries them "on the v1.5 half-open edges": they are inherited from the
previous version of the instrument, and no rationale for them is recorded anywhere in the
repository. 0.8 was not chosen. It is what splitting the range evenly produces.

### What equal fifths implies

The levels are the maturity scale, and equal-fifths bands do not line up with them.

| Level | Band named for it | Where the level sits inside that band |
|---|---|---|
| 1 | Nascent [1, 1.8) | at the floor |
| 2 | Emerging [1.8, 2.6) | 25 percent across |
| 3 | Established [2.6, 3.4) | at the centre |
| 4 | Advanced [3.4, 4.2) | 75 percent across |
| 5 | Transformative [4.2, 5] | at the ceiling |

Only level 3 sits in the middle of the band named after it, because the scheme is
symmetric about the midpoint of the whole scale rather than about each level.

**This builds in a generosity gradient.** Established is reached at 2.6, which is 0.4
below level 3. Advanced is reached at 3.4, which is 0.6 below level 4. Transformative is
reached at 4.2, which is 0.8 below level 5. A pillar may therefore be labelled
Transformative while averaging 4.2, closer to level 4 than to level 5, and the higher the
band the further below its namesake level a pillar is allowed to sit.

### The bands are also fragile at any cut

Four of the fourteen pillar means in the two verified assessments sit within 0.10 of a
band edge: Nigeria C2 at 2.57 (0.03), Nigeria E1 at 2.56 (0.04), Egypt C4 at 3.33 (0.07),
and Egypt O1 at 2.67 (0.07). A pillar carries roughly seven rows, so one row moving by one
level shifts its mean by about 0.14. Each of those four bands would flip on a single row
being read differently, and decision 13.5 leaves 44 rows whose reading is unsettled.
Moving the edges does not cure this; only showing the margin does.

The bands also discriminate weakly in the range observed. All fourteen means fall between
2.25 and 3.80, inside three of the five bands, and nine of the fourteen read Established.
Neither Nascent nor Transformative was reached by any pillar in either country.

### The options

The boundaries can sit in three places: between the levels at arbitrary fifths of the
range (the current cut), on the integers, or halfway between the integers. Putting them
on the integers is the natural instinct, since the levels are the maturity scale, but it
forces a choice: a boundary at exactly 2.0 has to send a mean of 2.0 either up or down,
and the two answers are the two extremes.

| | Tolerance: how far below level *k* a pillar may sit and still claim band *k* | Nascent width | Transformative width |
|---|---|---|---|
| **A** current, equal fifths, 1.8 / 2.6 / 3.4 / 4.2 | 0.2, 0.4, 0.6, 0.8 — rising | 0.8 | 0.8 |
| **B** round to nearest level, 1.5 / 2.5 / 3.5 / 4.5 | 0.5, flat | 0.5 | 0.5 |
| **C** ceiling, bands (*k*-1, *k*] | 1.0, flat | **0** | 1.0 |
| **D** floor, bands [*k*, *k*+1) | 0, flat | 1.0 | **0** |

All four agree on the pure case: a pillar whose rows are all at level *k* reads as band
*k* under every scheme. That test does not separate them. Tolerance does.

**C is the most generous scheme available.** A pillar averaging 2.01 reads Established,
the band named for level 3, because any progress past level 2 counts as having arrived at
level 3. Nascent collapses to the single point 1.0: with roughly seven rows in a pillar,
one row above the floor moves the whole pillar to Emerging, so Nascent would in practice
never be used and the five-band scale would become four.

**D is the strictest, with the mirror flaw.** Transformative becomes unreachable except at
a flat 5.0, and a pillar averaging 3.99 reads Established.

On the fourteen real pillar means both integer cuts destroy the discrimination, in
opposite directions. Under C nothing reads below Established: Nigeria's weakest pillar,
A1 at 2.25, reads Established, and five pillars read Advanced. Under D nothing reads above
Established: Egypt's strongest pillar, C1 at 3.80, reads Established as well.

| Scheme | How the fourteen means distribute |
|---|---|
| A | Emerging 4 · Established 9 · Advanced 1 |
| B | Emerging 1 · Established 12 · Advanced 1 |
| C | Established 9 · Advanced 5 |
| D | Emerging 8 · Established 6 |

**E. Recut to fit the observed level distribution.** Rejected. The only distribution
available is 93 rows from two countries assessed by one team, and fitting to it would
encode those two countries into the instrument.

### The secondary value, and why it settles the cut

A second figure beside the band, giving the signed distance of the mean from the middle of
its band, was proposed to carry the nuance without complicating the rule. It should be
adopted. Under equal-width bands it is interconvertible with distance to the nearest
boundary (distance to the edge equals half the band width minus the size of the distance
from the midpoint), so it answers "how close to flipping" as directly, and it reads more
naturally as "how strongly does this pillar hold its band".

It also settles where the boundaries belong, because the two candidate cuts render the
same pillar very differently.

| A pillar whose rows are **all** at level… | Integer cuts | Round to nearest |
|---|---|---|
| all 2 | Emerging −0.50 | Emerging +0.00 |
| all 3 | Established −0.50 | Established +0.00 |
| all 4 | Advanced −0.50 | Advanced +0.00 |

With boundaries on the integers, a pillar in which every row sits at level 3 reads
Established −0.50: the weakest possible position in its band, a hair from dropping out of
it. With boundaries at the midpoints it reads Established +0.00, which is what it is.
Egypt's A1 is exactly 3.00, seven rows averaging precisely level 3, and integer cuts would
render that as −0.50. The nuance layer would report every uniform pillar as barely holding
on, which is the opposite of the clarity it exists to provide.

### Whether the scale should start at 0

Raised as a way to get five integer-bounded bands and a floor that plainly means nothing.
Two findings, and the second settles it.

**It would still be five levels.** 0, 1, 2, 3 and 4 are five distinct values. Renaming the
floor removes no level. It also would not deliver integer-bounded bands: N contiguous
integer levels give N-1 integer-cut intervals whatever the origin, so on 0 to 4 the
collapse simply moves from the bottom of the scale to the top, and Transformative becomes
the single point 4.

**The bottom level is doing two different jobs, and 0 suits only one of them.** Maturity
scales conventionally start at 1 because the bottom rung is a characterisation rather than
an absence; CMMI's level 1, "Initial", describes ad hoc and reactive practice, not nothing
at all. In this register:

- 25 ladder indicators record level 1 as rung *Absent*: the named instrument does not
  exist. A zero would be more honest here.
- 32 threshold indicators record level 1 as a real measured value below the first cut.
  Egypt's Global Innovation Index is 24.7 against a first cut of 25, and Nigeria's is
  21.1. Recording a score that nearly clears the bar as zero would be plainly wrong.

A 0-based scale would therefore repair the semantics of 25 rows and break them for 32.
**Ruling: the levels stay 1 to 5.**

*Carried to 13.12.* The oddity that prompted the question survives the ruling: a pillar in
which every ladder row is Absent still scores 1.00 rather than 0. That is not a property
of the scale and renumbering would not cure it. It is that a pillar mean averages "the
instrument does not exist" and "a real but low measured value" as though they were the
same quantity, which is the question 13.12 asks about indicators playing different roles
in one mean. Recorded there as evidence.

### Why integer boundaries cannot carry five bands

The interval [1, 5] contains three interior integers: 2, 3 and 4. Three cuts make four
intervals, and there are five band names to place. Integer boundaries therefore force one
of three things: run four bands and drop a name, make one band a single point (which is
what the ceiling and floor rules do at opposite ends), or renumber the levels 0 to 4 so
that the scale has four interior integers. The last is arithmetically clean and was raised
as "0-1 for Nascent, 1-2 for Emerging", but it reaches every threshold, every ladder rung,
the workbook, the indicator census and both worked examples, and a level 0 reads oddly in
an assessment that describes what a country has rather than what it lacks.

Midpoint boundaries need no such choice: 1.5, 2.5, 3.5 and 4.5 are four cuts on a scale
with three interior integers, and they place all five names without collapsing any of
them.

### Recommendation

**B, together with the signed distance from the band midpoint.**

An earlier draft of this note recommended keeping the current edges on the ground that
equal fifths was the only distribution-free cut available. That was wrong: every scheme in
the table is distribution-free. The question is where the boundary belongs relative to the
levels, and the current cut answers it worst. Its tolerance rises from 0.2 at the bottom
to 0.8 at the top, so the higher the band the further below its namesake level a pillar
may sit, and no principled alternative has that property.

Anchoring the bands to the levels is right. Anchoring them *on* the integers is what
cannot be done without choosing C or D, and each degenerates at one end: C erases Nascent,
D erases Transformative. Halfway between the integers is the symmetric resolution of the
same instinct. Every level then sits at the centre of the band that carries its name,
tolerance is 0.5 in both directions, and the rule states itself in one sentence: the band
is the level the pillar rounds to.

The three bands that move under B are Nigeria C4 at 2.50, E1 at 2.56, and C2 at 2.57. All
three sit within 0.07 of a boundary under either cut, so what changes is which side of a
coin-toss they fall on, not the reading of the country. That is the argument for doing
both things at once: recut so the band means what it says, and print the margin so a
reader can see when a band rests on 0.03.

*Dependency.* If 13.5 moves a material number of rows, the means move with them and the
three borderline pillars should be re-read before the recut is published.

The distance is reported as a signed two-decimal figure beside the band, so a pillar reads
"Established +0.11" or "Emerging +0.07". Zero means the pillar sits squarely at its level;
plus or minus 0.50 means it is on the edge of flipping.

**Ruling:** *awaiting*

**What changes when it lands (option b):** `bands` in `model/DAMM-v1.7-model.json` and
`BANDS` in `engine_v17.py`, which are the same four numbers in two places; the parity test
holds them together. Three Nigerian pillar bands change and must be named in the revision
note, since that assessment is already with the reviewer. The margin is a further
presentation change in the engine and the renderer, overlapping decision 13.7.
