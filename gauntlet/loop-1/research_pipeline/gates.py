#!/usr/bin/env python3
"""The gates between a vendor's answer and a recorded row.

Every gate here is one of the design record's evidence decisions, made mechanical.
They run in order and the first one that fires decides the row, because they are
ordered by how badly the failure would mislead a reader:

  1. isolation   (C7) — a fact about another country is not evidence about this one,
                        and bleed is invisible in the finished report.
  2. quote       (C6) — a value that cannot be found in the page it cites is not a
                        value; this is the check that caught a fabricated pilot.
  3. tier        (C1) — T5 yields existence facts only, never a statistic.
  4. construct   (C3) — evidence measuring a different construct sets a hold. This is
                        defect #1: a national figure recorded against a rural indicator.
  5. prerequisite(C4) — the twelve prerequisite rows require T1-T3 quote-verified
                        evidence, because a one-level error there moves six columns.

A gate never deletes evidence. It withholds a *level* and records why, so the row
still carries what was found. A withheld level is not an absence.
"""

import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "countries.json")) as handle:
    _C = json.load(handle)

# Longest first, so "Niger" can never match inside "Nigeria".
_ALL_TERMS = []
for _n in _C["names"]:
    _ALL_TERMS.append((_n, _n))
    for _a in _C["adjectivals"].get(_n, []):
        _ALL_TERMS.append((_n, _a))
_ALL_TERMS.sort(key=lambda t: -len(t[1]))


def _mentions(text, term):
    return re.search(r"(?<![A-Za-z])" + re.escape(term) + r"(?![A-Za-z])", text or "",
                     re.I) is not None


def names_country(text, country):
    """Whether `text` names this country, by name or by its adjectival form.

    "Egyptian" is not "Egypt" to a word-boundary match, and a check that misses the
    adjectival form lets a passage about the assessed country pass as being about
    somewhere else. foreign_attribution has always known this; it is public now because
    the scans pass needs the same judgement in the opposite direction.
    """
    if not text:
        return False
    return any(_mentions(text, t) for t in [country] + _C["adjectivals"].get(country, []))


def foreign_attribution(text, country):
    """Countries named in `text` other than `country`, when `country` is not named.

    Mention is not attribution: a multi-country ITU table that includes the target is
    ordinary evidence, and rejecting it would manufacture gaps. What is rejected is a
    passage that names another country and not this one — which is what carrying a
    lead across a border actually looks like.
    """
    if not text:
        return []
    if names_country(text, country):
        return []
    hits, seen = [], set()
    for name, term in _ALL_TERMS:
        if name == country or name in seen:
            continue
        if _mentions(text, term):
            seen.add(name)
            hits.append(name)
    return hits


def foreign_url(url, country):
    """An ISO3 country code in a citation's path that belongs to a different country."""
    if not url:
        return None
    mine = _C["iso3"].get(country, "")
    for name, code in _C["iso3"].items():
        if name == country or code == mine:
            continue
        if re.search(r"(?<![A-Za-z])" + code + r"(?![A-Za-z])", url):
            return name
    return None


# ------------------------------------------------------------------ the gates

class Gate:
    """A gate outcome. `verdict` is one of pass / hold / reject."""

    def __init__(self, name, verdict, reason=""):
        self.name, self.verdict, self.reason = name, verdict, reason

    def __repr__(self):
        return f"<{self.name}:{self.verdict} {self.reason[:60]}>"

    def as_dict(self):
        return dict(gate=self.name, verdict=self.verdict, reason=self.reason)


# How old a document may be and still, by itself, establish that something exists NOW.
#
# This is a calibration parameter, not a settled rule, and it is set generously on
# purpose: a law, strategy or programme document from within the last decade plausibly
# still describes the current state, so the gate does not fire on the ordinary case of
# a 2019 act or a 2021 strategy. What it stops is the case the first Egypt shadow run
# produced — a national soil database recorded as *Adopted* on the strength of a 2001
# FAO workshop report describing a GIS in use since 1997. That document is real, and it
# was quote-verified; it establishes what existed twenty-five years ago, which is not
# what a presence rung claims. The model's own `staleness_years` is 3, but staleness
# only flags a row, and three years is far too tight to gate a legal instrument on.
PRESENCE_EVIDENCE_MAX_AGE = 10


def run_gates(ans, *, country, indicator_id, is_prerequisite, quote_ok, quote_page_tier,
              cited_url, page_urls, derived_level=None, is_ladder=False,
              assessment_year=None):
    """Return the ordered list of gate outcomes for one answer.

    `quote_ok` is the result of verifying the answer's quote against the page it cited;
    the caller does the verification because only it holds the fetched text.
    `derived_level` is what the shared ladder rule produces from the recorded rung and
    evidence fields, which the coherence gate compares against the level the answer
    argued for.
    """
    out = []
    asserted = bool(ans.get("found")) and ans.get("value_kind") in ("number", "statement") \
        and str(ans.get("value", "")).strip() != ""

    # 1. isolation — C7
    bleed = set(foreign_attribution(str(ans.get("value", "")), country))
    bleed |= set(foreign_attribution(ans.get("quote", ""), country))
    url_bleed = foreign_url(cited_url, country)
    if url_bleed:
        bleed.add(url_bleed)
    if asserted and bleed:
        out.append(Gate("isolation", "reject",
                        f"the recorded evidence attributes its facts to "
                        f"{', '.join(sorted(bleed))} rather than to {country}"))
        return out
    out.append(Gate("isolation", "pass", ""))

    if not asserted:
        out.append(Gate("quote", "pass", "no value asserted"))
        return out

    # 2. quote verification — C6
    if not quote_ok:
        off_pack = cited_url and cited_url.split("#")[0] not in page_urls
        out.append(Gate("quote", "reject",
                        "the citation is not among the pages retrieved for this row"
                        if off_pack else
                        "the quoted text does not appear in the page it cites"))
        return out
    out.append(Gate("quote", "pass", ""))

    # 3. tier admissibility — C1 and the source-tier protocol
    tier = ans.get("proposed_tier") or ""
    effective = quote_page_tier or tier
    if effective == "T5":
        out.append(Gate("tier", "hold",
                        "the only source is T5 news, vendor or market material, which "
                        "carries existence facts but never a statistic"))
        return out
    out.append(Gate("tier", "pass", f"recorded at {effective}"))

    # 4. construct match — C3
    #
    # A row at rung Absent is exempt, and the exemption is not a loophole. Such a row
    # claims that the named instrument does not exist and cites the nearest adjacent one
    # as evidence of where it looked. That citation measures a different construct by
    # design, so the ordinary construct test would hold every well-evidenced absence and
    # the ladder's bottom rung would be unreachable. It was: neither automated country
    # run placed a single ladder row at level 1, while neither verified assessment
    # recorded a single ladder row as a gap. Absent scores 1, the lowest level on the
    # ladder, so the incentive this creates runs toward under-claiming.
    if is_ladder and ans.get("presence_rung") == "Absent":
        out.append(Gate("construct", "pass", "rung Absent: the citation evidences the "
                                             "search, not the construct"))
        out.append(Gate("prerequisite", "pass", "rung Absent"))
        out.append(Gate("coherence", "pass", ""))
        if len((ans.get("negative_finding") or "").strip()) < 20:
            out.append(Gate("argument", "hold",
                            "rung Absent is proposed with no negative finding — nothing "
                            "is recorded about what an Announced instrument would have "
                            "looked like and why none was found"))
            return out
        out.append(Gate("currency", "pass", ""))
        out.append(Gate("argument", "pass", ""))
        return out

    cm = ans.get("construct_match") or "unclear"
    if cm == "measures a different construct":
        out.append(Gate("construct", "hold",
                        ans.get("construct_note")
                        or "the evidence measures a construct other than the one the "
                           "indicator names"))
        return out
    if cm == "unclear":
        out.append(Gate("construct", "hold",
                        ans.get("construct_note")
                        or "it could not be established that the evidence measures the "
                           "construct the indicator names"))
        return out
    out.append(Gate("construct", "pass", ""))

    # 5. the prerequisite bar — C4
    if is_prerequisite and effective not in ("T1", "T2", "T3"):
        out.append(Gate("prerequisite", "hold",
                        f"{indicator_id} is a prerequisite and gates whole columns of "
                        f"the readiness matrix; the best evidence found is {effective}, "
                        f"below the T1-T3 bar such a row requires"))
        return out
    out.append(Gate("prerequisite", "pass", ""))

    # 6. coherence — the row must agree with itself.
    #
    # On a ladder row the machine supplies both the rung and the two evidence fields
    # that raise the level, AND its own argument for a level. When the two disagree,
    # one of them is unsupported and there is no way to tell which. The probe run
    # produced exactly this: a row whose negative finding argued that no independent
    # evidence of delivery quality existed, while its quality and scale fields were
    # filled with the programme's own design description, deriving level 5 from an
    # argument for level 3. A level that the row's own reasoning contradicts is not an
    # assessment, so the row holds.
    #
    # Threshold rows are exempt: there the value is authoritative and the level is
    # arithmetic on cut points, so a slip in the machine's own sum says nothing about
    # the strength of the evidence.
    if is_ladder and derived_level is not None:
        claimed = ans.get("proposed_level")
        if isinstance(claimed, int) and claimed > 0 and claimed != derived_level:
            out.append(Gate("coherence", "hold",
                            f"the row contradicts itself: the recorded rung and evidence "
                            f"fields derive level {derived_level}, while the row argues "
                            f"for level {claimed}"))
            return out
    out.append(Gate("coherence", "pass", ""))

    # 7. currency — a present-tense claim needs evidence from the present.
    #
    # Adopted and Operating assert that something is in place now. A document can only
    # establish what was true when it was written, so past a certain age it stops being
    # evidence for a present-tense claim and becomes evidence for a historical one.
    # Announced and Absent are exempt: an announcement is a dated event, and absence is
    # not established by a document at all.
    rung = ans.get("presence_rung")
    year = ans.get("year") or 0
    if is_ladder and rung in ("Adopted", "Operating") and assessment_year and year:
        age = assessment_year - year
        if age > PRESENCE_EVIDENCE_MAX_AGE:
            out.append(Gate("currency", "hold",
                            f"the rung '{rung}' asserts that this is in place now, but "
                            f"the evidence is from {year} — {age} years old, and it can "
                            f"establish only what was true then"))
            return out
    out.append(Gate("currency", "pass", ""))

    # 8. argument — a level below 5 must say what the level above would have required.
    #
    # This is the design record's own standard, applied mechanically: "A level with no
    # negative finding is an assertion, not an assessment." It matters most exactly
    # where the machine sets a level from non-numeric evidence, because there the
    # argument is the only thing between the evidence and the score.
    claimed = ans.get("proposed_level")
    if isinstance(claimed, int) and 1 <= claimed <= 4 \
            and len((ans.get("negative_finding") or "").strip()) < 20:
        out.append(Gate("argument", "hold",
                        f"level {claimed} is proposed with no negative finding — nothing "
                        f"is recorded about what level {claimed + 1} would have required "
                        f"and the evidence does not show"))
        return out
    out.append(Gate("argument", "pass", ""))
    return out


def verdict_of(gates):
    """reject beats hold beats pass — the worst outcome decides the row."""
    for g in gates:
        if g.verdict == "reject":
            return "reject", g
    for g in gates:
        if g.verdict == "hold":
            return "hold", g
    return "pass", gates[-1] if gates else None


mentions = _mentions
