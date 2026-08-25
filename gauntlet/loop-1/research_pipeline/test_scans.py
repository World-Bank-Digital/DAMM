#!/usr/bin/env python3
"""Checks for the scans pass. No keys, no network.

What is worth testing here is the pair of gates that keep the two lanes apart. The scans
are the only place in the pipeline where material about other countries is gathered on
purpose, and the whole safety of that rests on it being unable to arrive anywhere it
would be read as evidence about the country being assessed.

    python3 test_scans.py
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gates as G
import scans as S

FAILED = []
COUNT = 0


def check(label, got, want):
    global COUNT
    COUNT += 1
    ok = (got is None) == (want is None) if want in (None,) else (want in str(got))
    if not ok:
        FAILED.append(f"{label}\n    got:  {got}\n    want: {want}")


def section(t):
    print(f"\n## {t}")


section("A country finding must be about this country")

check("a quote naming the country passes",
      S.country_lane_gate("Egypt published its strategy in 2023", "https://mala.gov.eg/x", "Egypt"),
      None)

check("a quote about another country is refused",
      S.country_lane_gate("Kenya published its strategy in 2023", "https://x.org/doc", "Egypt"),
      "about Kenya")

check("a multi-country table that includes this country is ordinary evidence",
      # Mention is not attribution. Rejecting these would manufacture gaps out of the
      # ITU and FAO tables that are often the best source a row has.
      S.country_lane_gate("Egypt 45%, Kenya 38%, Morocco 41%", "https://itu.int/table", "Egypt"),
      None)

check("a citation carrying another country's ISO3 is refused",
      S.country_lane_gate("The strategy was published", "https://worldbank.org/KEN/report", "Egypt"),
      "belongs to Kenya")


section("An international pointer must come from somewhere else")

check("a pointer at another country passes",
      S.international_lane_gate("Kenya", "Kenya digital agriculture strategy",
                                "https://kilimo.go.ke/strategy", "Egypt"),
      None)

check("a pointer at the assessed country is refused",
      # This is the one that matters. Country evidence wearing a precedent label would
      # reach the DAR without passing the standards the country lane is held to.
      S.international_lane_gate("Egypt", "Egypt strategy", "https://x/doc", "Egypt"),
      "not a precedent")

check("the adjectival form is caught too",
      S.international_lane_gate("Egyptian Republic", "t", "https://x/doc", "Egypt"),
      "not a precedent")

check("a pointer that names no country is refused",
      S.international_lane_gate("", "t", "https://x/doc", "Egypt"),
      "does not say which country")

check("a pointer whose citation is a page about this country is refused",
      S.international_lane_gate("Kenya", "Egypt national strategy", "https://x/doc", "Egypt"),
      "not another country's")


section("The matcher behind both gates")

check("the adjectival form names the country", G.names_country("Egyptian ministry", "Egypt"), "True")
check("another country does not", G.names_country("Kenya ministry", "Egypt"), "False")
check("empty text names nobody", G.names_country("", "Egypt"), "False")


section("The register obeys the source-tier protocol")

ok = dict(name="Farmer Card", lead="MALR", status="Operating", results_tier="")

check("an entry with no results tier is fine at any source tier",
      S.register_gate(ok, "T5", "Egypt"), None)

check("a tiered results claim on a T1 source is fine",
      S.register_gate(dict(ok, results_tier="T2"), "T1", "Egypt"), None)

check("a results claim on a T5 source cannot be tiered",
      # T4-T5 are admissible for existence facts only. A vendor figure badged as though
      # it were evaluated is the most plausible-looking wrong thing this lane could
      # produce, and render_v17's own QC refuses to emit a report containing one.
      S.register_gate(dict(ok, results_tier="T2"), "T5", "Egypt"),
      "admissible for existence only")

check("a T4 source is refused the same way",
      S.register_gate(dict(ok, results_tier="T3"), "T4", "Egypt"),
      "admissible for existence only")

check("a results tier outside T1-T3 is refused outright",
      S.register_gate(dict(ok, results_tier="T5"), "T1", "Egypt"),
      "only be tiered T1-T3")

check("an entry with no name is refused", S.register_gate(dict(ok, name=""), "T1", "Egypt"),
      "no name")
check("an entry naming nobody who runs it is refused",
      S.register_gate(dict(ok, lead=""), "T1", "Egypt"), "names nobody who runs it")
check("a status outside the vocabulary is refused",
      S.register_gate(dict(ok, status="Live"), "T1", "Egypt"), "is not one of")


section("One programme is entered once")

check("a name with its sponsor attached is the same programme",
      # The hand-built register's own issues list records this failure: 'Al Mufeed' and
      # 'FAO El-Mufeed' were one app entered twice.
      S.is_duplicate("Al Mufeed", "FAO El-Mufeed app"), "True")
check("a name and its fuller form are the same programme",
      S.is_duplicate("Farmer Card (Kart el-Fallah) smart card programme", "Farmer Card"),
      "True")
check("two different programmes are not merged",
      S.is_duplicate("Hudhud advisory app", "Zr3i"), "False")
check("an acronym is not merged with an unrelated expansion",
      S.is_duplicate("DAIRS", "Digital Agriculture Information System"), "False")
check("a short fragment cannot swallow another entry",
      S.is_duplicate("AIP", "Agricultural Innovation Platform"), "False")


section("Every international record carries its restriction")

check("the schema requires a country to be named",
      "about_country" in S.FINDING_SCHEMA["required"], "True")

check("prescriptive chapters are read from the model, not listed in code",
      all(c["kind"] == "prescriptive" for c in S.prescriptive_chapters()), "True")

check("there are prescriptive chapters to scan for",
      len(S.prescriptive_chapters()) >= 8, "True")


print()
if FAILED:
    print(f"{len(FAILED)} of {COUNT} checks FAILED\n")
    for f in FAILED:
        print("  " + f)
    sys.exit(1)
print(f"all {COUNT} checks pass")
