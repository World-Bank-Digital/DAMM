#!/usr/bin/env python3
"""Gauntlet loop 1 — machine pass (Step 1, lane 1).

Fetches every machine-readable T1 series a country row can be served from, with full
provenance. Output: machine_pass.json.

Three publishers, because one is not enough. The lane began as the World Bank API alone,
and the cost of that showed up as rows the research lane spent real money abstaining on
while the figure sat in a public database nobody queried. Each publisher is independent:
one being unreachable degrades the lane, it does not stop it.

  World Bank   the WDI and Findex series
  UNESCO UIS   education series the WDI does not carry
  FAOSTAT      the SDG domain, downloaded once per run and read from the archive

The second rule this file keeps is that a series must measure what the indicator names.
Where the nearest published series measures something adjacent — a different population,
a different act — it is marked `corroborate_only` and can never fill a row. A figure that
is right about the wrong thing is worse than a gap, because a gap is visibly a gap.
"""
import csv, io, json, os, urllib.request, time, sys, datetime, zipfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "research_pipeline"))
import country_names

# indicator id -> (WDI code, note) or (WDI code, note, database source id).
# Most series live in the default database; a few, such as ID4D, are published in a
# separate one and need its source id passed or the query returns nothing.
SERIES = {
 "1.1": ("NV.AGR.EMPL.KD", ""),
 "1.2": ("AG.YLD.CREL.KG", ""),
 "1.3": ("SL.AGR.EMPL.ZS", "ILO modelled estimate"),
 "1.4": ("AG.PRD.FOOD.XD", ""),
 "8.1": ("SN.ITK.DEFC.ZS", ""),
 "2.4": ("IT.NET.USER.ZS", ""),
 "2.9": ("EG.ELC.ACCS.RU.ZS", ""),
 "5.2": ("SE.ADT.LITR.ZS", ""),
 "5.3": ("SE.TER.ENRR", "PROXY: total tertiary gross enrollment, not STEM-specific — census defect logged (D3)"),
 "8.2": ("FX.OWN.TOTL.FE.ZS", "Global Findex wave"),
 # Findex carries the headline mobile-money series the research lane was left to hunt for.
 "8.4": ("mobileaccount.t.d", "Global Findex"),
 # 4.7 is a prerequisite, and both countries' verified assessments source it to the
 # ID4D dataset. The automated research lane reached the ID4D landing pages but never a
 # country value, because the figures sit behind a DataBank query form rather than on a
 # page. The series itself is a plain API call once the database id is supplied.
 "4.7": ("ID.OWN.TOTL.ZS", "World Bank Identification for Development (ID4D)", 89),
}
CANDIDATES = {  # spec 13.2 provisional A1 candidates
 "A1-CAND-IRR": ("AG.LND.IRIG.AG.ZS", "PROVISIONAL spec 13.2 candidate: irrigation coverage"),
}
# --- UNESCO UIS -------------------------------------------------------------------
# Free, no key. Education series the WDI either lacks or carries only as an aggregate.
UIS_SERIES = {
 # 5.3 asks for STEM ENROLMENT. UIS publishes STEM GRADUATES and no enrolment series at
 # all, so the nearest figure counts a different act by a different population. It is
 # recorded for corroboration and may never fill the row: scoring a graduates figure
 # against enrolment thresholds would be a measurement error wearing a T1 badge.
 # The real fix is a model one — see the census defect logged against 5.3.
 "5.3": dict(code="FOSGP.5T8.F500600700",
             name="percentage of graduates from STEM programmes in tertiary education",
             corroborate_only=True,
             note=("CONSTRUCT MISMATCH: this series counts STEM GRADUATES; indicator 5.3 "
                   "names STEM ENROLMENT. UIS publishes no enrolment series for STEM. "
                   "Corroboration only — it cannot fill the row.")),
}

# --- FAOSTAT SDG domain -----------------------------------------------------------
# One bulk archive per run rather than a request per row.
FAO_SDG_URL = ("https://bulks-faostat.fao.org/production/"
               "SDG_BulkDownloads_E_All_Data_(Normalized).zip")
FAO_SDG_SERIES = {
 # 24043 is "Share of women among owners or rights-bearers of agricultural land" — the
 # holders denominator indicator 8.5 asks for. Published for 79 countries, so a miss
 # here is an absence of publication and not a failure to look.
 "8.5": dict(item="24043",
             name="SDG 5.a.1 share of women among owners or rights-bearers of agricultural land"),
}

ACCESS = datetime.date.today().isoformat()

def fetch(iso3, code, source=None):
    url = (f"https://api.worldbank.org/v2/country/{iso3}/indicator/{code}"
           f"?format=json&mrnev=1&per_page=5" + (f"&source={source}" if source else ""))
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=25) as r:
                j = json.load(r)
            if len(j) > 1 and j[1]:
                d = j[1][0]
                return dict(value=d["value"], year=int(d["date"]), code=code, url=url)
            return None
        except Exception as e:
            if attempt == 2: return dict(error=str(e), code=code, url=url)
            time.sleep(2)

def fetch_uis(iso3, code):
    """UNESCO UIS. Returns the most recent year carrying a value."""
    url = (f"https://api.uis.unesco.org/api/public/data/indicators"
           f"?indicator={code}&geoUnit={iso3}&start=2015&end={datetime.date.today().year}")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=25) as r:
                j = json.load(r)
            recs = [x for x in (j.get("records") or []) if x.get("value") is not None]
            if not recs:
                return None
            d = max(recs, key=lambda x: x["year"])
            return dict(value=d["value"], year=int(d["year"]), code=code, url=url)
        except Exception as e:
            if attempt == 2:
                return dict(error=str(e), code=code, url=url)
            time.sleep(2)


_FAO_CACHE = {}


def _fao_sdg_rows():
    """The SDG archive, downloaded once per process.

    Cached because the alternative is a 4.7 MB download per row per country, which would
    make the cheapest lane in the pipeline the slowest.
    """
    if "rows" in _FAO_CACHE:
        return _FAO_CACHE["rows"]
    try:
        with urllib.request.urlopen(FAO_SDG_URL, timeout=180) as r:
            blob = r.read()
        z = zipfile.ZipFile(io.BytesIO(blob))
        name = next(n for n in z.namelist() if n.endswith("_All_Data_(Normalized).csv"))
        rows = list(csv.DictReader(io.TextIOWrapper(z.open(name), "utf-8-sig")))
        _FAO_CACHE["rows"] = rows
    except Exception as e:
        _FAO_CACHE["rows"] = []
        _FAO_CACHE["error"] = str(e)
    return _FAO_CACHE["rows"]


def _fao_areas():
    """Every area FAOSTAT publishes, from the archive's own list.

    Read from the same download as the data, so the two can never drift, and so a
    country's area name is never a thing somebody has to remember to add. This began as
    a two-entry map of the countries that had been assessed, which meant a third country
    resolved to nothing and the lane produced no row without saying why.
    """
    if "areas" in _FAO_CACHE:
        return _FAO_CACHE["areas"]
    rows = _fao_sdg_rows()
    _FAO_CACHE["areas"] = sorted({r.get("Area") for r in rows if r.get("Area")})
    return _FAO_CACHE["areas"]


def fetch_fao_sdg(iso3, item, country=None):
    rows = _fao_sdg_rows()
    if not rows:
        return dict(error=_FAO_CACHE.get("error", "the SDG archive could not be read"),
                    code=item, url=FAO_SDG_URL)
    area = country_names.resolve(country, _fao_areas()) if country else None
    if not area:
        return dict(error=(f"{country!r} does not resolve to an area FAOSTAT publishes"
                           if country else "no country name was supplied"),
                    code=item, url=FAO_SDG_URL)
    got = [r for r in rows
           if r.get("Area") == area and r.get("Item Code") == item
           and str(r.get("Value", "")).strip()]
    if not got:
        return None
    d = max(got, key=lambda r: int(r["Year"]))
    return dict(value=float(d["Value"]), year=int(d["Year"]), code=item, url=FAO_SDG_URL)


# Guarded so the SERIES map can be imported as the one source of truth for which
# indicators have a machine-fetchable T1 series, without refetching both countries as
# a side effect of the import. The automated pipeline reuses this map to corroborate
# its own research on those rows.
def fetch_country(iso3, country=None):
    rows = {}

    # --- UNESCO UIS
    for ind, spec in UIS_SERIES.items():
        r = fetch_uis(iso3, spec["code"])
        base = dict(note=spec["note"], access=ACCESS,
                    corroborate_only=spec.get("corroborate_only", False))
        if r is None:
            rows[ind] = dict(status="no_data", code=spec["code"], **base)
        elif "error" in r:
            rows[ind] = dict(status="error", **r, **base)
        else:
            rows[ind] = dict(status="ok", value=r["value"], year=r["year"],
                             src=f"UNESCO Institute for Statistics — {spec['name']} ({r['code']})",
                             url=r["url"], tier="T1", **base)

    # --- FAOSTAT SDG
    for ind, spec in FAO_SDG_SERIES.items():
        r = fetch_fao_sdg(iso3, spec["item"], country)
        base = dict(note=spec.get("note", ""), access=ACCESS,
                    corroborate_only=spec.get("corroborate_only", False))
        if r is None:
            rows[ind] = dict(status="no_data", code=spec["item"], **base)
        elif "error" in r:
            rows[ind] = dict(status="error", **r, **base)
        else:
            rows[ind] = dict(status="ok", value=r["value"], year=r["year"],
                             src=f"FAOSTAT — {spec['name']} (item {r['code']})",
                             url=r["url"], tier="T1", **base)

    # --- World Bank, last and never overwriting. A row already served by a publisher
    # above keeps it, because those entries were chosen for construct fit and carry the
    # flags that say when a figure may not fill a row. Letting the WDI pass overwrite them
    # silently discarded both — it replaced the flagged STEM-graduates series with an
    # unflagged total-tertiary proxy, which `--t1-fill` would then have written into a
    # STEM indicator as a measurement.
    for ind, spec in list(SERIES.items()) + list(CANDIDATES.items()):
        code, note, source = (list(spec) + [None])[:3]
        r = fetch(iso3, code, source)
        if r is None:
            rows.setdefault(ind, dict(status="no_data", code=code, note=note,
                                      access=ACCESS, corroborate_only=False))
        elif "error" in r:
            rows.setdefault(ind, dict(status="error", **r, note=note, access=ACCESS,
                                      corroborate_only=False))
        else:
            rows.setdefault(ind, dict(status="ok", value=r["value"], year=r["year"],
                             corroborate_only=False,
                             src=f"World Bank WDI {code}" + (f" ({note})" if note and "PROXY" not in note and "PROVISIONAL" not in note else ""),
                             url=r["url"], tier="T1", note=note, access=ACCESS))
    return rows


if __name__ == "__main__":
    out = {}
    for iso3, cname in [("EGY", "Egypt"), ("NGA", "Nigeria")]:
        rows = fetch_country(iso3, cname)
        for ind in rows:
            print(f"{cname} {ind}: {rows[ind].get('value','—')} ({rows[ind].get('year','—')})")
        out[cname] = rows
    json.dump(out, open("machine_pass.json", "w"), indent=1)
    print("wrote machine_pass.json")
