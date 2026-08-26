#!/usr/bin/env python3
"""Checks for country-name resolution. No keys, no network.

    python3 test_country_names.py
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import country_names as C

FAILED, COUNT = [], [0]


def check(label, got, want):
    COUNT[0] += 1
    if got != want:
        FAILED.append(f"{label}: got {got!r}, wanted {want!r}")


def section(t):
    print(f"\n## {t}")


# The two publishers this pipeline reads, spelled as each of them spells it.
UNSD = ["Egypt", "Nigeria", "Kenya", "Congo", "Turkey", "Korea, Republic of",
        "United Republic of Tanzania", "Viet Nam", "Bolivia (Plurinational State of)"]
FAO = ["Egypt", "Nigeria", "Kenya", "Congo", "Democratic Republic of the Congo",
       "Türkiye", "Republic of Korea", "United Republic of Tanzania", "Viet Nam",
       "Bolivia (Plurinational State of)"]


section("One resolver, publishers that do not agree with each other")

# The UNSD list says "Turkey" and "Korea, Republic of"; FAOSTAT says "Türkiye" and
# "Republic of Korea". A map to one canonical spelling resolves against whichever
# publisher it was written for and fails on the other.
check("World Bank wording against the UNSD list",
      C.resolve("Egypt, Arab Rep.", UNSD), "Egypt")
check("World Bank wording against the FAOSTAT list",
      C.resolve("Egypt, Arab Rep.", FAO), "Egypt")
check("Turkiye finds the UNSD spelling", C.resolve("Turkiye", UNSD), "Turkey")
check("Turkiye finds the FAOSTAT spelling", C.resolve("Turkiye", FAO), "Türkiye")
check("Korea, Rep. finds the UNSD spelling",
      C.resolve("Korea, Rep.", UNSD), "Korea, Republic of")
check("Korea, Rep. finds the FAOSTAT spelling",
      C.resolve("Korea, Rep.", FAO), "Republic of Korea")
check("a bare name reaches a qualified entry",
      C.resolve("Tanzania", FAO), "United Republic of Tanzania")
check("and the reverse", C.resolve("United Republic of Tanzania", UNSD),
      "United Republic of Tanzania")
check("accents are not required", C.resolve("Cote d'Ivoire", ["Côte d'Ivoire"]),
      "Côte d'Ivoire")


section("A qualifier that carries the whole distinction is never dropped")

# cnsee.org is the Republic of Congo's statistical office. Resolving "Congo, Dem. Rep."
# to it by stripping the qualifier would attribute one country's statistics to another,
# silently, and the assessment would carry the wrong country's numbers.
check("the DRC does not resolve to Congo when only Congo is listed",
      C.resolve("Congo, Dem. Rep.", UNSD), None)
check("the DRC resolves where the publisher lists it",
      C.resolve("Congo, Dem. Rep.", FAO), "Democratic Republic of the Congo")
check("Congo still resolves to Congo", C.resolve("Congo", FAO), "Congo")
check("and so does its World Bank wording", C.resolve("Congo, Rep.", FAO), "Congo")


section("Not resolving is an answer")

check("an unknown country resolves to nothing", C.resolve("Wakanda", FAO), None)
check("an empty name resolves to nothing", C.resolve("", FAO), None)
check("no candidates resolves to nothing", C.resolve("Egypt", []), None)


section("Every name a publisher uses resolves to itself")

for lst, who in ((UNSD, "UNSD"), (FAO, "FAOSTAT")):
    unresolved = [n for n in lst if C.resolve(n, lst) != n]
    check(f"{who}: every listed name resolves to itself", unresolved, [])

print()
if FAILED:
    print(f"{len(FAILED)} of {COUNT[0]} checks FAILED\n")
    for f in FAILED:
        print(" ", f)
    sys.exit(1)
print(f"all {COUNT[0]} checks pass")
