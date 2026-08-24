#!/usr/bin/env python3
"""The research cell — one schema and one prompt, shared by the audition and the
orchestrator so that whatever the audition measured is what the pipeline then runs.

The schema is the design record's evidence decisions made machine-checkable:

  C1  `proposed_tier` is a tier, never a score, and `data_quality_flag` is free text
      beside it — no credibility number, because anything numeric gets averaged.
  C2  the machine sets `proposed_level` itself, with `rung_argument` and
      `negative_finding` recorded, so a level always arrives with its reasoning.
  C3  `abstain` is a first-class answer, not a failure — a withheld level is not
      an absence.
  C6  `quote` must be verbatim from the fetched page, so a synthesised claim cannot
      pass as a source of record.
  C7  `country` is stated once and any other country's entities are a rejection.
"""

CELL_SCHEMA = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean",
                  "description": "True only if an admissible published source states a figure or fact for the named construct, for the named country."},
        "abstain": {"type": "boolean",
                    "description": "True to set a ratification hold: evidence exists but does not measure the named construct, or is not at an admissible tier, or cannot be quote-verified."},
        "abstain_reason": {"type": "string"},
        "value_kind": {"type": "string", "enum": ["number", "statement", "none"]},
        "value": {"type": "string",
                  "description": "The recorded value. A bare number for value_kind=number (no units, no commas, no percent sign). A single factual sentence for value_kind=statement. Empty for none."},
        "unit": {"type": "string"},
        "year": {"type": "integer",
                 "description": "Reference year of the figure itself, not the publication year. 0 if none."},
        "source_title": {"type": "string",
                         "description": "Publisher and document title, as a reader would cite it."},
        "source_url": {"type": "string",
                       "description": "Deep link to the document that carries the value. A domain root is not a citation."},
        "proposed_tier": {"type": "string", "enum": ["T1", "T2", "T3", "T4", "T5", ""]},
        "quote": {"type": "string",
                  "description": "Verbatim text copied from the fetched page, containing the value. Never paraphrased, never reconstructed. Empty if abstaining or not found."},
        "data_quality_flag": {"type": "string",
                              "description": "Non-numeric caveat about the source, e.g. 'modelled estimate' or 'statistical office with documented quality concerns'. Empty if none."},
        "construct_match": {"type": "string",
                            "enum": ["measures the named construct",
                                     "measures a different construct",
                                     "unclear"]},
        "construct_note": {"type": "string",
                           "description": "Where the evidence and the indicator name differ, say exactly how."},
        "presence_rung": {"type": "string",
                          "enum": ["Absent", "Announced", "Adopted", "Operating", ""],
                          "description": "Ladder indicators only. Empty for threshold indicators."},
        "quality_evidence": {"type": "string"},
        "scale_evidence": {"type": "string"},
        "proposed_level": {"type": "integer",
                           "description": "1-5, or 0 to withhold."},
        "rung_argument": {"type": "string",
                          "description": "Rung by rung: what the evidence establishes at each level up to the one proposed."},
        "negative_finding": {"type": "string",
                             "description": "Why the next level up was NOT proposed. Required whenever a level is proposed below 5."},
        "search_trail": {"type": "string",
                         "description": "What was looked at and in what order, including dead ends."},
    },
    "required": ["found", "abstain", "abstain_reason", "value_kind", "value", "unit",
                 "year", "source_title", "source_url", "proposed_tier", "quote",
                 "data_quality_flag", "construct_match", "construct_note",
                 "presence_rung", "quality_evidence", "scale_evidence",
                 "proposed_level", "rung_argument", "negative_finding", "search_trail"],
    "additionalProperties": False,
}

QUERY_SCHEMA = {
    "type": "object",
    "properties": {
        "queries": {"type": "array", "items": {"type": "string"},
                    "description": "Up to three web search queries, most likely to surface the highest-tier source first."},
        "likely_publishers": {"type": "array", "items": {"type": "string"},
                              "description": "Domains most likely to publish this figure, highest tier first."},
    },
    "required": ["queries", "likely_publishers"],
    "additionalProperties": False,
}


SYSTEM = """You are recording evidence for a national digital-agriculture maturity \
assessment. Your output is a source of record that an auditor will check line by line.

The rules that govern you, in order of force:

1. NEVER state a value you cannot copy verbatim out of the page text you were given. \
The `quote` field must be an exact substring of one of the supplied pages; it is \
checked mechanically against them, and a quote that does not appear there is recorded \
as a fabrication. If you believe a figure exists but it is not in the supplied pages, \
set found=false and say so in `search_trail`.

2. A figure that measures something other than the named construct is NOT an answer to \
this cell. If the indicator names RURAL coverage and the only published figure is \
NATIONAL, that is not a rural figure — set abstain=true, put the national figure in \
`construct_note` as context, and explain the difference. This single rule is the one \
most often broken, and breaking it is the most damaging error you can make: it converts \
a data gap into a confident high score.

3. Some cells have no answer. A named statistic that no publisher has produced, a \
country absent from a database, an artifact that does not exist — the correct output is \
found=false with a search trail showing where you looked. Reporting nothing found is a \
successful outcome, not a failure. Never construct a plausible figure to fill a cell.

4. Tier is a property of the publisher, never a judgment of quality:
   T1 official statistics and international databases (FAOSTAT, WDI, ITU, Findex, \
national statistical offices)
   T2 peer-reviewed literature and international-organisation flagship or analytical \
reports (including openknowledge.worldbank.org)
   T3 government legal, policy and budget artifacts, and regulator reports
   T4 reputable grey literature (GSMA, donor reports, established industry analyses)
   T5 news, vendor and market material — existence facts only, never a statistic
   Tier the publisher of the page you actually quote, not the organisation the page \
talks about.

5. You are working on ONE country. Evidence about any other country is not evidence \
about this one, however similar the two are. Do not carry a figure across a border.

6. When you propose a level, argue it rung by rung, and say why the rung above was not \
reached. A level with no negative finding is an assertion, not an assessment."""


def cell_prompt(country, indicator_id, indicator_name, construct, ladder_or_threshold,
                pack, extra_rules=""):
    """Assemble the one user message. `pack` is the list of fetched sources."""
    lines = [f"COUNTRY: {country}",
             f"INDICATOR: {indicator_id} — {indicator_name}",
             f"WHAT THIS INDICATOR MEASURES: {construct}",
             ladder_or_threshold.strip(), ""]
    if extra_rules:
        lines += [extra_rules.strip(), ""]
    lines += ["=" * 68,
              "SOURCE PAGES RETRIEVED FOR THIS CELL",
              "Your `quote` must be an exact substring of one of these pages, and your",
              "`source_url` must be the URL of the page you quoted.",
              "=" * 68, ""]
    for n, s in enumerate(pack, 1):
        lines += [f"--- SOURCE {n} ---",
                  f"title: {s.get('title', '')}",
                  f"url: {s['url']}",
                  f"publisher tier (from the domain): {s.get('tier', '')}",
                  f"surfaced by: {s.get('surfaced_by', 'search')}",
                  "text:",
                  s.get("text", "")[:s.get("cap", 6000)],
                  ""]
    if not pack:
        lines += ["(no pages were retrieved for this cell)", ""]
    lines += ["=" * 68,
              "Record the cell now. If nothing in these pages measures the named",
              "construct for this country, set found=false and say where you looked."]
    return "\n".join(lines)


LADDER_TEXT = """SCORING: this is a LADDER indicator. Set `presence_rung` to one of
Absent / Announced / Adopted / Operating.

ABSENT IS AN ANSWER, NOT A FAILURE TO FIND ONE. This is the rung most often missed. A
ladder indicator asks whether a named instrument exists, and establishing that it does
not is a finding at rung Absent, which scores level 1. It is NOT a data gap. Record it
this way: set found=true, value_kind="statement", presence_rung="Absent", and write in
`value` what you did find in the domain together with the fact that the named instrument
is not among it. Cite the nearest adjacent instrument you examined, and quote it. That
citation is not being offered as a measure of the construct; it is the evidence that you
searched the right place and that the named thing is not there.

Use found=false, and accept a data gap, only when you could not search the domain
effectively at all: the sources were unreachable, or nothing in the field was retrieved.
The difference is real. "I examined the national data policy and the e-government
interoperability framework, and neither covers agricultural data" is Absent. "I could not
reach any relevant document" is a gap. The level derives mechanically from that rung
and from two evidence fields: Absent 1, Announced 2, Adopted 3, Operating 3, then +1 if
`quality_evidence` is filled and +1 more if `scale_evidence` is also filled, capped at 5.

Because those two fields ADD LEVELS, they are claims, not commentary:

  `quality_evidence` — fill it ONLY with independent or official evidence about how well
  the thing works: an evaluation, an audit, a performance report, a service standard
  being met. A programme's own description of what it intends to do is DESIGN, not
  quality. If you have only the implementer's own page, leave this field EMPTY.

  `scale_evidence` — fill it ONLY with figures for reach: users, beneficiaries,
  disbursements, coverage, geographic spread. A stated ambition or target is not scale.
  If no figures are published, leave this field EMPTY.

Leaving a field empty is the normal case and costs nothing. Filling it with the nearest
available text raises the level of this row and every mean it enters, on evidence that
does not support it. Your `proposed_level` must equal the level these rules produce from
the rung and the fields you filled; if it does not, the row is self-contradictory and
will be held."""


def threshold_text(direction, thresholds, unit=""):
    d = "higher is better" if direction == "higher-is-better" else "lower is better"
    cuts = ", ".join(str(t) for t in (thresholds or []))
    return (
        f"SCORING: this is a THRESHOLD indicator ({d}), unit {unit or 'as published'}. "
        f"The cut points are {cuts}: a value below the first cut is level 1, and each cut "
        f"passed raises the level by one, to level 5 above the last cut.\n\n"
        f"There are two ways to answer, and choosing between them matters:\n\n"
        f"  If a source publishes a single figure for this construct, set "
        f"value_kind=\"number\" and record it. The level then follows arithmetically and "
        f"`rung_argument` should justify the VALUE and its construct match, not the sum.\n\n"
        f"  If the construct is real and evidenced but no single figure is published for "
        f"it — the evidence is a range, or several partial measures, or a qualitative "
        f"finding — do NOT invent a representative number, and do NOT treat this as "
        f"nothing found. Set value_kind=\"statement\", record what the sources actually "
        f"establish, and set `proposed_level` yourself by arguing the evidence against "
        f"the cut points above. This is a normal outcome for indicators no one publishes "
        f"a headline number for. Manufacturing a single number from a range would give "
        f"the row a precision its sources do not have.\n\n"
        f"Whichever route you take, if you propose a level below 5 you must give the "
        f"`negative_finding` — the specific thing the evidence does not show that the "
        f"next level up would require. A level with no negative finding is an assertion "
        f"rather than an assessment, and the row will be held.")
