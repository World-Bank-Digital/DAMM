#!/usr/bin/env python3
"""Checks for the machine-readable T1 lane. No keys, no network.

The lane's value is that it is deterministic, so what is worth testing is the two rules
that keep it honest rather than the fetching, which is the publishers' business.

    python3 test_machine_pass.py
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import machine_pass as mp

FAILED = []
COUNT = 0


def check(label, got, want):
    global COUNT
    COUNT += 1
    ok = (got is None) if want is None else (want in str(got))
    if not ok:
        FAILED.append(f"{label}\n    got:  {got}\n    want: {want}")


def section(t):
    print(f"\n## {t}")


# A fetch stub, so the rules can be checked without asking three publishers for
# permission every time the suite runs.
def stub(uis=None, fao=None, wb=None):
    mp.fetch_uis = lambda iso, code: uis
    mp.fetch_fao_sdg = lambda iso, item, area=None: fao
    mp.fetch = lambda iso, code, source=None: wb


_real = (mp.fetch_uis, mp.fetch_fao_sdg, mp.fetch)


section("A construct mismatch may be shown and may never fill a row")

stub(uis=dict(value=14.05, year=2025, code="FOSGP.5T8.F500600700", url="https://uis/x"),
     wb=dict(value=38.0, year=2025, code="SE.TER.ENRR", url="https://wb/x"))
rows = mp.fetch_country("EGY")

check("5.3 is served and carries a value", rows["5.3"]["status"], "ok")
check("5.3 is marked corroborate-only", rows["5.3"]["corroborate_only"], "True")
check("5.3 says why it cannot fill", rows["5.3"]["note"], "CONSTRUCT MISMATCH")
# UIS counts graduates and the WDI series counts all tertiary enrolment. Both are wrong
# for a STEM enrolment indicator, and the WDI one is the more dangerous because nothing
# on its face says so.
check("the flagged series wins over the unflagged proxy", rows["5.3"]["src"], "UNESCO")
check("the proxy did not overwrite it", rows["5.3"]["src"], "graduates")


section("A publisher chosen for construct fit is not overwritten")

stub(fao=dict(value=31.6, year=2019, code="24043", url="https://fao/x"),
     wb=dict(value=99.9, year=2024, code="WB.WRONG", url="https://wb/x"))
rows = mp.fetch_country("NGA")
check("8.5 keeps the FAOSTAT holders series", rows["8.5"]["src"], "FAOSTAT")
check("8.5 keeps the FAOSTAT value", rows["8.5"]["value"], "31.6")
check("8.5 may fill, because the construct matches", rows["8.5"]["corroborate_only"], "False")


section("One publisher failing degrades the lane, it does not stop it")

stub(uis=dict(error="timeout", code="X", url="u"),
     fao=dict(error="archive unreadable", code="Y", url="v"),
     wb=dict(value=3494.89, year=2025, code="NV.AGR.EMPL.KD", url="https://wb/x"))
rows = mp.fetch_country("NGA")
check("the UIS failure is recorded, not raised", rows["5.3"]["status"], "error")
check("the FAOSTAT failure is recorded", rows["8.5"]["status"], "error")
check("World Bank rows still arrive", rows["1.1"]["status"], "ok")
check("a failed row can never fill", rows["5.3"].get("corroborate_only"), "True")


section("A publisher with no value for a country says so")

stub(uis=None, fao=None, wb=None)
rows = mp.fetch_country("EGY")
check("no data is not an error", rows["8.5"]["status"], "no_data")
check("and carries no value", rows["8.5"].get("value"), None)


section("The map stays the single source of truth for what is machine-fetchable")

mp.fetch_uis, mp.fetch_fao_sdg, mp.fetch = _real
served = set(mp.SERIES) | set(mp.UIS_SERIES) | set(mp.FAO_SDG_SERIES)
check("8.4 is now served by Findex", "8.4" in mp.SERIES, "True")
check("8.5 is now served by FAOSTAT", "8.5" in mp.FAO_SDG_SERIES, "True")
check("no row is claimed by two fillable maps",
      len(set(mp.SERIES) & set(mp.FAO_SDG_SERIES)), "0")

print()
if FAILED:
    print(f"{len(FAILED)} of {COUNT} checks FAILED\n")
    for f in FAILED:
        print(" ", f)
    sys.exit(1)
print(f"all {COUNT} checks pass")
