#!/usr/bin/env python3
"""Gauntlet loop 1 — machine pass (Step 1, lane 1).
Fetches every API-fetchable indicator for Egypt + Nigeria from the World Bank API
(most recent non-empty value), with full provenance. Output: machine_pass.json.
Includes the two spec-13.2 A1 candidates as PROVISIONAL rows (flagged).
"""
import json, urllib.request, time, sys, datetime

SERIES = {  # indicator id -> (WDI code, note)
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
}
CANDIDATES = {  # spec 13.2 provisional A1 candidates
 "A1-CAND-IRR": ("AG.LND.IRIG.AG.ZS", "PROVISIONAL spec 13.2 candidate: irrigation coverage"),
}
ACCESS = datetime.date.today().isoformat()

def fetch(iso3, code):
    url = f"https://api.worldbank.org/v2/country/{iso3}/indicator/{code}?format=json&mrnev=1&per_page=5"
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

# Guarded so the SERIES map can be imported as the one source of truth for which
# indicators have a machine-fetchable T1 series, without refetching both countries as
# a side effect of the import. The automated pipeline reuses this map to corroborate
# its own research on those rows.
def fetch_country(iso3):
    rows = {}
    for ind, (code, note) in list(SERIES.items()) + list(CANDIDATES.items()):
        r = fetch(iso3, code)
        if r is None:
            rows[ind] = dict(status="no_data", code=code, note=note, access=ACCESS)
        elif "error" in r:
            rows[ind] = dict(status="error", **r, note=note, access=ACCESS)
        else:
            rows[ind] = dict(status="ok", value=r["value"], year=r["year"],
                             src=f"World Bank WDI {code}" + (f" ({note})" if note and "PROXY" not in note and "PROVISIONAL" not in note else ""),
                             url=r["url"], tier="T1", note=note, access=ACCESS)
    return rows


if __name__ == "__main__":
    out = {}
    for iso3, cname in [("EGY", "Egypt"), ("NGA", "Nigeria")]:
        rows = fetch_country(iso3)
        for ind in rows:
            print(f"{cname} {ind}: {rows[ind].get('value','—')} ({rows[ind].get('year','—')})")
        out[cname] = rows
    json.dump(out, open("machine_pass.json", "w"), indent=1)
    print("wrote machine_pass.json")
