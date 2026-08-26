#!/usr/bin/env python3
"""Regression tests for the evidence rules — no keys, no network, no cost.

`smoke_vendors.py` proves the vendor paths work and needs six keys to do it. This file
proves the *rules* are right and needs nothing, so it can run on every change. Everything
here is a rule that was once wrong: each test names the defect it exists to prevent.

    python3 test_gates.py
"""

import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..")))

import vendors as V
import gates as G
import gate2
from build_inputs import ladder_level

FAIL = []
N = [0]


def check(label, got, want):
    N[0] += 1
    if got != want:
        FAIL.append(f"{label}: got {got!r}, wanted {want!r}")


def section(t):
    print(f"\n## {t}")


# ---------------------------------------------------------------- quote verification
section("Quote verification is script-blind")
# The alphanumeric fold once kept only [a-z0-9], so a quote in any non-Latin script
# reduced to the empty string — and the empty string is a substring of every page. An
# entirely invented Arabic quote verified as genuine. Egypt publishes in Arabic.
SCRIPTS = [
    ("Arabic", "The platform serves citizens. مرحبا بكم في مصر الرقمية اليوم.",
     "هذه جملة عربية مختلقة تماما لا توجد", "مرحبا بكم في مصر الرقمية"),
    ("Chinese", "Report text 中国农业农村部发布了最新的统计数据资料。",
     "这是完全捏造的一句中文引文内容", "中国农业农村部发布了最新的统计"),
    ("Cyrillic", "Source: Министерство сельского хозяйства опубликовало данные.",
     "Это полностью выдуманная цитата которой нет", "Министерство сельского хозяйства"),
    ("Greek", "Text: Το Υπουργείο Γεωργίας δημοσίευσε τα στοιχεία.",
     "Αυτή είναι μια εντελώς κατασκευασμένη φράση", "Το Υπουργείο Γεωργίας δημοσίευσε"),
    ("Latin", "Rural electricity access in Egypt reached 100.0 percent in 2024.",
     "Rural electricity access in Egypt reached 62.4 percent", "reached 100.0 percent"),
]
for name, page, fake, real in SCRIPTS:
    check(f"{name}: invented quote rejected", V.quote_verify(fake, page), False)
    check(f"{name}: genuine quote accepted", V.quote_verify(real, page), True)
check("a quote of pure punctuation is rejected",
      V.quote_verify("··· —— ,,,,,,", "any page text here"), False)
check("a changed number is not a quote",
      V.quote_verify("reached 100.1 percent", SCRIPTS[4][1]), False)
check("markup between words is tolerated",
      V.quote_verify("reached 100.0 percent", "…reached **100.0** percent in 2024…"), True)

# ---------------------------------------------------------------- tiers
section("Tier lookup takes the most specific domain")
# `openknowledge.worldbank.org` is the World Bank's repository of analytical reports (T2)
# and once matched the shorter `worldbank.org` needle, filing a flagship as an official
# statistic. And the UN's statistical hosts are T1 while its newswire is not.
for url, want in [
    ("https://data.worldbank.org/indicator/X", "T1"),
    ("https://openknowledge.worldbank.org/handle/1", "T2"),
    ("https://publicadministration.un.org/egovkb/en-us/Data/Country-Information/id/53", "T1"),
    ("https://news.un.org/en/story/2026/01/1234", "T5"),
    ("https://www.ncc.gov.ng/docs/report.pdf", "T3"),
    ("https://www.gsma.com/r/report.pdf", "T4"),
    ("https://agritechblog.example.com/post", "T5"),
]:
    check(f"tier {url[:52]}", V.tier_for_url(url), want)


section("A country's own statistics office is T1, in every country")

import nso_registry as NSO

# The table named Egypt's and Nigeria's offices because those were the countries that had
# been assessed. Everywhere else the body that produces the statistics tiered below a
# World Bank re-publication of the same number, and Kenya's bureau — knbs.or.ke, not a
# .gov domain at all — tiered T5, with the newswires.
for url, country, want in [
    ("https://www.knbs.or.ke/reports/x.pdf", "Kenya", "T1"),
    ("https://mospi.gov.in/publication/y", "India", "T1"),
    ("https://nsb.gov.bt/statistics", "Bhutan", "T1"),
    ("https://www.capmas.gov.eg/z", "Egypt", "T1"),
    ("https://www.nigerianstat.gov.ng/z", "Nigeria", "T1"),
]:
    check(f"{country}'s office is T1", V.tier_for_url(url, country), want)

check("another country's office is not T1 here",
      # Kenya's bureau is a fine publisher and still says nothing about Nigeria. The
      # isolation gate is what should catch that, not a tier that quietly promotes it.
      V.tier_for_url("https://www.knbs.or.ke/x", "Nigeria"), "T5")

check("with no country named, nothing is promoted",
      V.tier_for_url("https://www.knbs.or.ke/x"), "T5")

check("the longest-needle rule still wins over the promotion",
      V.tier_for_url("https://openknowledge.worldbank.org/r", "Kenya"), "T2")

check("the registry covers most of the world", len(NSO.load()) > 150, True)
check("and resolves the model's own country wording",
      NSO.domains_for("Egypt, Arab Rep."), ["capmas.gov.eg"])


section("Citation resolvability distinguishes a bad link from a bad day")
check("a domain root is not a citation", V.url_resolves("https://www.example.com/")[0], False)
check("a non-URL is not a citation", V.url_resolves("see the annex")[0], False)

# ---------------------------------------------------------------- country isolation
section("Country isolation rejects attribution, not mention")
check("a fact about another country is rejected",
      G.foreign_attribution("Nigeria's rural electrification reached 23.5 percent.", "Egypt"),
      ["Nigeria"])
check("a multi-country table naming the target is evidence",
      G.foreign_attribution("Egypt 100.0, Nigeria 23.5, Kenya 71.4", "Egypt"), [])
check("Niger never matches inside Nigeria",
      "Niger" in G.foreign_attribution("Nigeria published the figure.", "Egypt"), False)
check("adjectival forms are caught",
      G.foreign_attribution("The Nigerian regulator published it.", "Egypt"), ["Nigeria"])
check("an ISO3 in a citation path is caught",
      G.foreign_url("https://api.worldbank.org/v2/country/NGA/indicator/X", "Egypt"), "Nigeria")
check("the target's own ISO3 is fine",
      G.foreign_url("https://api.worldbank.org/v2/country/EGY/indicator/X", "Egypt"), None)

# ---------------------------------------------------------------- the ladder
section("The shared ladder")
check("Absent", ladder_level("Absent")[0], 1)
check("Announced", ladder_level("Announced")[0], 2)
check("Adopted", ladder_level("Adopted")[0], 3)
check("Operating with no evidence of quality stays at 3",
      ladder_level("Operating", "", "")[0], 3)
check("Operating + quality", ladder_level("Operating", "x" * 60, "")[0], 4)
check("Operating + quality + scale", ladder_level("Operating", "x" * 60, "y" * 60)[0], 5)
check("scale without quality does not skip a rung",
      ladder_level("Operating", "", "y" * 60)[0], 3)
check("a missing rung yields no level", ladder_level("")[0], None)

# ---------------------------------------------------------------- the gates
section("The gates")
BASE = dict(found=True, value_kind="statement", value="A national soil database exists.",
            quote="A national soil database exists.", proposed_tier="T3",
            construct_match="measures the named construct", presence_rung="Adopted",
            year=2024, proposed_level=3, negative_finding="x" * 40, construct_note="",
            abstain=False, source_url="https://x.gov.eg/a")
PAGES = {"https://x.gov.eg/a"}


def gates(**over):
    a = dict(BASE, **over)
    g = G.run_gates(a, country="Egypt", indicator_id="3.8",
                    is_prerequisite=over.pop("_prereq", False),
                    quote_ok=over.get("_quote_ok", True),
                    quote_page_tier=over.get("_page_tier", "T3"),
                    cited_url=a["source_url"], page_urls=PAGES,
                    derived_level=over.get("_derived", 3), is_ladder=True,
                    assessment_year=2026)
    return G.verdict_of(g)[0]


check("a clean row passes", gates(), "pass")
check("an unverifiable quote is rejected", gates(_quote_ok=False), "reject")
check("a T5-only source holds", gates(proposed_tier="T5", _page_tier="T5"), "hold")
check("a construct mismatch holds",
      gates(construct_match="measures a different construct"), "hold")
check("an unclear construct holds", gates(construct_match="unclear"), "hold")
check("a prerequisite on T4 holds",
      gates(_prereq=True, proposed_tier="T4", _page_tier="T4"), "hold")
check("a prerequisite on T1 passes",
      gates(_prereq=True, proposed_tier="T1", _page_tier="T1"), "pass")
check("a row that contradicts its own level holds",
      gates(proposed_level=5, _derived=3), "hold")
# A 2001 workshop report once recorded a national soil database as Adopted today.
check("a 25-year-old document cannot establish a present state",
      gates(year=2001), "hold")
check("a 2019 instrument still can", gates(year=2019), "pass")
check("an announcement is exempt from currency",
      gates(year=2001, presence_rung="Announced", proposed_level=2, _derived=2), "pass")
check("a level below 5 with no negative finding holds",
      gates(negative_finding=""), "hold")
# The ladder's bottom rung was unreachable. An Absent row cites the nearest adjacent
# instrument as evidence of where it searched, so the ordinary construct test held every
# well-evidenced absence: neither automated country run placed a single ladder row at
# level 1, while neither verified assessment recorded a single ladder row as a gap.
check("a well-evidenced absence reaches the bottom rung",
      gates(presence_rung="Absent", proposed_level=1, _derived=1,
            construct_match="measures a different construct"), "pass")
check("an absence on a prerequisite is not blocked by the tier bar",
      gates(presence_rung="Absent", proposed_level=1, _derived=1, _prereq=True,
            proposed_tier="T4", _page_tier="T4",
            construct_match="measures a different construct"), "pass")
check("an absence still has to say what it looked for",
      gates(presence_rung="Absent", proposed_level=1, _derived=1,
            negative_finding=""), "hold")
check("an absence still cannot cite a T5 source",
      gates(presence_rung="Absent", proposed_level=1, _derived=1,
            proposed_tier="T5", _page_tier="T5"), "hold")
check("an absence still cannot carry an unverifiable quote",
      gates(presence_rung="Absent", proposed_level=1, _derived=1, _quote_ok=False), "reject")
check("a foreign attribution is rejected",
      gates(value="Nigeria's registry covers 12 million farmers.",
            quote="Nigeria's registry covers 12 million farmers."), "reject")

# ---------------------------------------------------------------- Gate 2's decisions
section("What a Gate 2 finding does to a row")
SPEC = dict(id="9.9", name="Test", method="ladder", candidate=False, prerequisite=None,
            direction="higher-is-better", thresholds=[], pillar="C1")
ROW = dict(value="v", cls="Documented", level=3, year=2024, src="s", note="", tier="T3",
           tier_detail="", url="u", defnote="an open question", defsev="construct-drift")


def finding(verdict, kind, plevel, gate="pass", quote_verified=True):
    return dict(verdict=verdict, refutation_kind=kind, reason="the evidence shows X",
                gate_verdict=gate, quote_verified=quote_verified,
                proposed_row=dict(ROW, level=plevel, src="new src"))


def decide(*a, **k):
    return gate2.decide(SPEC, ROW, finding(*a, **k))


check("confirmed leaves the row alone", decide("confirmed", "", 5)[0], "upheld")
# Failing to find it again is not a refutation — the hand protocol's own rule.
check("could not locate independently is not a refutation",
      decide("refuted", "could not locate independently", 5)[0], "upheld")
check("an unsupported source withdraws the level",
      decide("refuted", "source does not support the value", None)[0], "withdrawn")
check("a construct mismatch withdraws the level",
      decide("refuted", "construct mismatch", None)[0], "withdrawn")
# A withdrawal is the only path that lowers a row, so it must rest on something the
# reviewer actually read. Both countries' 7.12 withdrawals came from a reviewer that
# asserted no value and verified no quote — an absence filed as a refutation.
check("a withdrawal with nothing quoted is not a withdrawal",
      decide("refuted", "source does not support the value", None,
             quote_verified=False)[0], "upheld")
check("a construct mismatch with nothing quoted is not a withdrawal",
      decide("refuted", "construct mismatch", None, quote_verified=False)[0], "upheld")
check("a proposal that did not clear the gates changes nothing",
      decide("adjust", "better evidence exists", 4, gate="hold")[0], "upheld")
# The schema calls 'adjust' a wrong tier, class, LEVEL or vintage. It once copied only
# the provenance and kept the old level, which made the verdict mean less than it says.
check("an adjustment that changes the level changes the level",
      decide("adjust", "better evidence exists", 4)[0], "relevelled")
check("an adjustment can lower a level too",
      decide("adjust", "better evidence exists", 2)[0], "relevelled")
check("an adjustment at the same level is provenance only",
      decide("adjust", "tier or class wrong", 3)[0], "adjusted")
for verdict, kind, lvl in [("adjust", "better evidence exists", 4),
                           ("refuted", "source does not support the value", None),
                           ("adjust", "tier or class wrong", 3)]:
    _, applied = decide(verdict, kind, lvl)
    check(f"the ratification note survives '{kind}'",
          (applied or ROW).get("defnote"), "an open question")

# A gap the reviewer also could not fill leaves the gap standing.
GAP = dict(ROW, cls="Gap", level=None)
check("a gap the reviewer could not fill either stays a gap",
      gate2.decide(SPEC, GAP, dict(verdict="refuted", refutation_kind="better evidence exists",
                                   reason="r", gate_verdict="pass",
                                   proposed_row=dict(GAP)))[0], "upheld")
check("a gap the reviewer filled becomes evidence",
      gate2.decide(SPEC, GAP, dict(verdict="refuted", refutation_kind="better evidence exists",
                                   reason="r", gate_verdict="pass",
                                   proposed_row=dict(ROW, level=3)))[0], "filled")

# ---------------------------------------------------------------- the spend counter
section("The spend counter survives a resume")
import json as _json, os as _os, tempfile as _tf

# A resume used to start the counter at zero and overwrite the saved ledger, so a run
# finished in two sittings reported only the second: Egypt's first pass read $0.26 when
# it had cost $15.75. The ceiling stopped binding too, since it could be walked past by
# stopping and starting. And wrapping `save` in a plain Lock deadlocked it against
# `spent`, at the first checkpoint of every run.
_led = V.Ledger(ceiling=500, label="t"); _led.record("exa", "research", searches=3)
_f = _tf.mktemp(suffix=".json"); _led.save(_f)
_l2 = V.Ledger(ceiling=500, label="t")
check("a resume carries the earlier calls", _l2.load(_f), 1)
_l2.record("exa", "research", searches=2)
check("and the counter accumulates", round(_l2.spent(), 6), 0.025)
check("the summary counts both sittings", _l2.summary()["calls"], 2)
_l2.save(_f)
check("saving does not drop the carried calls", len(_json.load(open(_f))["calls"]), 2)

_l3 = V.Ledger(ceiling=0.02, label="t"); _l3.load(_f)
try:
    _l3.check("research")
    check("the ceiling binds across a resume", "no raise", "BudgetExhausted")
except V.BudgetExhausted:
    check("the ceiling binds across a resume", "BudgetExhausted", "BudgetExhausted")
_os.unlink(_f)

# Per-pass caps only bound the total if the allocations exhaust the ceiling (decision G3).
check("the per-pass allocations sum to the whole ceiling",
      round(sum(v for k, v in V.Ledger.ALLOCATION.items() if k != "audition"), 6), 1.0)
check("country research has its own protected share",
      V.Ledger.ALLOCATION["country_research"], 0.075)
check("international lessons has its own protected share",
      V.Ledger.ALLOCATION["international_lessons"], 0.075)
check("the legacy aggregate scan share is not a second canonical allocation",
      "scans" in V.Ledger.ALLOCATION, False)
check("historical all-lane scans retain their old aggregate cap",
      V.Ledger(ceiling=500).cap("scans"), 75.0)

# ---------------------------------------------------------------- report

section("A second review supersedes the first pass, for every document")

import tempfile, pathlib

with tempfile.TemporaryDirectory() as _d:
    pathlib.Path(_d, "X_input.json").write_text("{}")
    p, rev = V.engine_input_for(_d, "X")
    check("with no review, the first pass is read", p.endswith("X_input.json"), True)
    check("and it says it was not reviewed", rev, False)

    pathlib.Path(_d, "X_g2_input.json").write_text("{}")
    p, rev = V.engine_input_for(_d, "X")
    # The rule lived only in the diagnostic. The foresight and roadmap passes read the
    # unreviewed file, so a review could reopen a gap, fill it and withdraw a level, and
    # the roadmap would still be written against the row as the first pass left it.
    check("once reviewed, the reviewed pass is read", p.endswith("X_g2_input.json"), True)
    check("and it says so", rev, True)

print()
if FAIL:
    print(f"FAILED {len(FAIL)} of {N[0]} checks\n")
    for f in FAIL:
        print("  " + f)
    sys.exit(1)
print(f"all {N[0]} checks pass")
