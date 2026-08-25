#!/usr/bin/env python3
"""Checks for the national survey lane. No keys, no network.

The lane's one job is to say where a figure lives without ever saying what it is, so what
is worth testing is the boundary it must not cross and the scoping that keeps it pointing
at the right question.

    python3 test_survey_pass.py
"""
import sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import survey_pass as S

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


def stub(surveys, varmap):
    S.find_surveys = lambda iso, limit=60: (surveys, None)
    S.variables = lambda idno: varmap.get(idno, [])


HH_SURVEY = dict(idno="NGA_GHSP", title="General Household Survey, Panel 2023-2024",
                 family="GHS-Panel / LSMS-ISA", year_start=2023, year_end=2024,
                 url="https://microdata/1")
OLD_FIRM = dict(idno="EGY_ES08", title="Enterprise Survey 2008", family="Enterprise survey",
                year_start=2008, year_end=2008, url="https://microdata/2")
NEW_FIRM = dict(idno="EGY_ES25", title="World Bank Enterprise Survey 2025",
                family="Enterprise survey", year_start=2025, year_end=2026,
                url="https://microdata/3")

VARS = {
 "NGA_GHSP": [dict(name="s5bq14", labl="Does [NAME] have access to the internet?"),
              dict(name="s12q8__1", labl="What type of information did you receive?: WEATHER INFORMATION")],
 "EGY_ES08": [dict(name="q107d", labl="Number of female workers in 2007"),
              dict(name="q65c", labl="spending on information technology, computers")],
 "EGY_ES25": [dict(name="c22b", labl="Establishment Has Its Own Website")],
}


section("It says where a figure lives and never what it is")

stub([HH_SURVEY], VARS)
found, _, _ = S.match("NGA", assessment_year=2026)
check("a located row has no value", found["5.4"].get("value"), None)
check("its status is not the machine lane's 'ok'", found["5.4"]["status"], "located")
check("it names the survey", found["5.4"]["survey"], "General Household Survey")
check("it names the variable that carries the construct", found["5.4"]["variables"][0]["name"], "s5bq14")
check("it says a label is not a measurement", found["5.4"]["note"], "not a country")
check("the advisory row finds the weather question", found["8.17"]["variables"][0]["name"], "s12q8__1")


section("A probe may only match the survey family that could answer it")

# Without family scoping, a farmer-literacy probe matched an enterprise survey's IT
# spending line and a workforce-gender probe matched women's training receipt. Both are
# firm questions standing in for household constructs.
stub([OLD_FIRM], VARS)
found, _, _ = S.match("EGY", assessment_year=2026)
check("a household construct is not answered by a firm survey", found.get("5.4"), None)
check("a household construct is not answered by a firm survey (advisory)", found.get("8.17"), None)
check("the firm workforce construct is answered", found["5.12"]["variables"][0]["name"], "q107d")
check("and it is not the IT-spending line", str(found["5.12"]["variables"]), "female workers")


section("An old survey is reported and marked, not silently used")

check("a 2008 survey against a 2026 assessment is stale", found["5.12"]["stale"], "True")
check("and the row says so first", found["5.12"]["note"], "STALE")

stub([NEW_FIRM], VARS)
found, _, _ = S.match("EGY", assessment_year=2026)
check("a current survey is not marked stale", found["6.13"]["stale"], "False")
check("and it locates the website question", found["6.13"]["variables"][0]["name"], "c22b")


section("Nothing found is reported as nothing found")

stub([], {})
found, surveys, err = S.match("XXX", assessment_year=2026)
check("no surveys means no locations", len(found), "0")
check("and no error is invented", err, None)

print()
if FAILED:
    print(f"{len(FAILED)} of {COUNT} checks FAILED\n")
    for f in FAILED:
        print(" ", f)
    sys.exit(1)
print(f"all {COUNT} checks pass")
