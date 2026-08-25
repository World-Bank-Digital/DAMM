#!/usr/bin/env python3
"""Gauntlet loop 1 — the national survey lane (Step 1, lane 3).

What this lane is, and what it is not.

Five indicator rows defeated every assessment of Egypt and Nigeria attempted so far, by
machine and by hand: farmer digital literacy, climate-smart practice adoption, gender
balance in the digital-agriculture workforce, agri-SME digital adoption, and climate
advisory reach. They were treated as unmeasurable. They are not. Four of the five are
measured directly by the national household survey — Nigeria's GHS-Panel asks "Does
[NAME] have access to the internet?" and "What type of information did you receive?:
WEATHER INFORMATION" — and the reason the pipeline never found them is that it was
searching the open web for a published percentage instead of the survey that collects it.

So this lane reports WHERE A FIGURE LIVES. It never reports a figure.

That distinction is the whole design. Computing "% of farmers with digital literacy" from
a household survey means downloading microdata and running a weighted tabulation against
a definition someone has to choose. This lane does none of that. It names the survey, the
variables that carry the construct, and the landing page, and hands them to the research
lane as targeted retrieval — and where no published tabulation exists, it lets a row
record a far more useful gap than "searched, found nothing": the national survey measures
this, in these variables, and nobody has published the cut we need.

A variable label is evidence about a questionnaire. It is not evidence about a country.

    python3 survey_pass.py NGA Nigeria
"""
import json, re, sys, urllib.parse, urllib.request

API = "https://microdata.worldbank.org/index.php/api/catalog"

# Survey families worth asking, most informative first. LSMS-ISA carries the agricultural
# modules; the general household survey carries the connectivity and literacy ones.
FAMILIES = (
    ("GHS-Panel / LSMS-ISA", r"general household survey|LSMS|living standards|integrated survey"),
    ("Agricultural census or survey", r"agricultur\w*\s+(census|survey)|farm\w*\s+survey"),
    ("Household or living conditions survey", r"household survey|living conditions|budget survey"),
    # Firm-side surveys. The Enterprise Survey asks every country's firms about internet
    # and website use, which is the construct behind agri-SME digital adoption, and it
    # runs in countries that have no LSMS-ISA at all.
    ("Enterprise survey", r"enterprise survey"),
    # Last resort for the person-level connectivity rows where nothing better exists. It
    # is old in most countries, which the staleness rule will catch on the row.
    ("Demographic and health survey", r"demographic and health survey"),
)

# What each row would be measured by, as a probe over variable labels, and — just as
# importantly — WHICH SURVEY FAMILY may answer it.
#
# The family scoping is not tidiness. Without it a farmer-literacy probe matched a 2007
# enterprise survey's "spending on information technology" line, and a workforce-gender
# probe matched "% women employees who received formal training". Both are firm
# expenditure and training questions standing in for household and workforce constructs.
# A located row that points at the wrong question is worse than an unlocated one, because
# it sends the research lane somewhere confidently wrong.
HH = "household"      # LSMS-ISA, GHS-Panel, living-conditions, DHS
FIRM = "firm"         # enterprise surveys

PROBES = {
 "1.8":  (r"irrigat|conservation agric|agroforest|drought.tolerant|cover crop|minimum tillage",
          "climate-smart or conservation practice adoption", HH),
 "5.4":  (r"access to the internet|use the internet|type of mobile phone|smartphone|digital skill",
          "internet and device access among farming households", HH),
 "5.12": (r"(number|how many).*(female|women) (employee|worker)|sex of (the )?(owner|manager)",
          "sex composition of the workforce", FIRM),
 "6.13": (r"(enterprise|establishment|firm|business).*(internet|website|e.?mail|computer)|"
          r"(internet|website|e.?mail).*(purchas|sale|transaction)",
          "digital tool use by firms", FIRM),
 "8.17": (r"weather (information|related)|extension service|agricultural advis|forecast",
          "receipt of weather or advisory information", HH),
 "8.9":  (r"mobile money|digital (service|platform)|information from agent",
          "reach of digital services to farming households", HH),
 "1.6":  (r"sold .*(crop|produce)|to whom .*(sell|sold)|buyer",
          "market participation by smallholders", HH),
}

FAMILY_KIND = {
 "GHS-Panel / LSMS-ISA": HH,
 "Agricultural census or survey": HH,
 "Household or living conditions survey": HH,
 "Demographic and health survey": HH,
 "Enterprise survey": FIRM,
}

# A survey this much older than the assessment cannot carry a current-state claim on its
# own. It is still reported, marked stale, so a row can cite it and say what it is.
STALE_AFTER_YEARS = 6

_VARS = {}


def _get(url, timeout=45):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def find_surveys(iso3, limit=60):
    """The country's surveys, newest first, tagged by family."""
    url = f"{API}/search?country={urllib.parse.quote(iso3)}&ps={limit}&sort_by=year_end&sort_order=desc"
    try:
        rows = _get(url).get("result", {}).get("rows", []) or []
    except Exception as e:
        return [], str(e)
    out = []
    for r in rows:
        title = str(r.get("title", ""))
        fam = next((name for name, pat in FAMILIES if re.search(pat, title, re.I)), None)
        if not fam:
            continue
        out.append(dict(idno=r.get("idno"), title=title, family=fam,
                        year_start=r.get("year_start"), year_end=r.get("year_end"),
                        url=r.get("url") or f"https://microdata.worldbank.org/catalog/{r.get('id')}"))
    # Newest first within the most informative family.
    order = {name: i for i, (name, _) in enumerate(FAMILIES)}
    out.sort(key=lambda s: (order.get(s["family"], 9), -int(s.get("year_end") or 0)))
    return out, None


def variables(idno):
    """A survey's variable list, cached — each is several hundred kilobytes."""
    if idno in _VARS:
        return _VARS[idno]
    try:
        v = _get(f"{API}/{urllib.parse.quote(idno)}/variables").get("variables", []) or []
    except Exception:
        v = []
    _VARS[idno] = v
    return v


def match(iso3, indicators=None, max_surveys=6, assessment_year=None):
    """For each probed row, the survey and variables that would carry it.

    Returns rows in the same shape the machine lane uses, with one difference that
    matters: `value` is never set, and `status` is 'located' rather than 'ok'. Nothing
    downstream can mistake this for a measurement.
    """
    import datetime
    year = assessment_year or datetime.date.today().year
    want = set(indicators or PROBES)
    surveys, err = find_surveys(iso3)
    if err:
        return {}, [], err
    found = {}
    for s in surveys[:max_surveys]:
        kind = FAMILY_KIND.get(s["family"])
        if not any(PROBES[i][2] == kind for i in want if i in PROBES):
            continue
        vs = variables(s["idno"])
        if not vs:
            continue
        ends = int(s.get("year_end") or 0)
        stale = bool(ends) and (year - ends) > STALE_AFTER_YEARS
        for ind in sorted(want):
            if ind in found or ind not in PROBES:
                continue
            pat, construct, need = PROBES[ind]
            if need != kind:
                continue
            hits = [v for v in vs if re.search(pat, str(v.get("labl", "")), re.I)]
            if not hits:
                continue
            found[ind] = dict(
                status="located",
                construct=construct,
                survey=s["title"],
                survey_years=f"{s.get('year_start')}-{s.get('year_end')}",
                idno=s["idno"],
                url=s["url"],
                n_variables=len(hits),
                stale=stale,
                variables=[dict(name=v.get("name"), label=str(v.get("labl", ""))[:120])
                           for v in hits[:6]],
                note=(("STALE: this survey ended more than "
                       f"{STALE_AFTER_YEARS} years before the assessment year, so it "
                       "cannot carry a current-state claim on its own. " if stale else "")
                      + "The national survey collects this. No value is asserted here: a "
                      "variable label describes a questionnaire, not a country. Fetch the "
                      "survey's published report for a tabulation, or record the gap "
                      "naming this survey."),
            )
    return found, surveys[:max_surveys], None


if __name__ == "__main__":
    iso3 = sys.argv[1] if len(sys.argv) > 1 else "NGA"
    found, surveys, err = match(iso3)
    if err:
        print(f"!! the survey catalogue could not be read: {err}")
        sys.exit(1)
    print(f"{iso3} — surveys consulted:")
    for s in surveys:
        print(f"  [{s['family']}] {s['title'][:64]} ({s['year_start']}-{s['year_end']})")
    print()
    for ind in sorted(found):
        f = found[ind]
        flag = "  [STALE]" if f.get("stale") else ""
        print(f"  {ind:<6} located in {f['survey'][:40]} ({f['survey_years']}) — "
              f"{f['n_variables']} variables{flag}")
        for v in f["variables"][:3]:
            print(f"           {v['name']:<14} {v['label'][:66]}")
    missing = sorted(set(PROBES) - set(found))
    print()
    print(f"located {len(found)} of {len(PROBES)} probed rows; not located: {missing}")
