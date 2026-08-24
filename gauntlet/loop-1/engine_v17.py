#!/usr/bin/env python3
"""DAMM v1.7 engine — gauntlet loop 1.
Same scoring mathematics as the v1.6 reference engine (unchanged by design);
generalized to load assessment rows from JSON and pass tier/url provenance through.
Usage: python3 engine_v17.py <input_rows.json> <output.json> <CountryName>
Input rows: {id: {value, cls, level, year, src, note, tier, url, subs?}}
Rows with id starting "A1-CAND-" are spec-13.2 provisional candidates: carried in
output["candidates"], never scored into pillars/layers/matrix.
"""
import json, sys
from decimal import Decimal, ROUND_HALF_UP

def r2(x):
    """Round half away from zero, to match Excel's ROUND() — the workbook is the source of
    truth, and Python's banker's rounding disagrees with it at exact .xx5 boundaries
    (a mean landing on a band edge would otherwise band differently in the two)."""
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


M = [
 ('1.1','Agriculture value added per worker (USD)','A1','Foundation',['NEED'],'','t','H',[1000,2500,5000,10000]),
 ('1.2','Cereal yield (kg/ha)','A1','Foundation',['NEED'],'','t','H',[1500,3000,4500,6000]),
 ('1.3','Employment in agriculture (%)','A1','Foundation',['NEED'],'','t','L',[45,30,15,5]),
 ('1.4','Food production index (2014-16=100)','A1','Foundation',['NEED'],'','t','H',[95,105,115,130]),
 ('1.5','Post-harvest loss rate (%)','A1','Foundation',['NEED'],'','t','L',[30,20,12,5]),
 ('1.6','Smallholder access to formal markets (%)','A1','Foundation',['NEED','MKT'],'','t','H',[20,40,60,80]),
 ('1.7','Agricultural credit access (% farmers)','A1','Foundation',['NEED','FIN'],'','t','H',[10,25,40,60]),
 ('1.8','Farmers using climate-smart practices (%)','A1','Foundation',['NEED','ADV'],'','t','H',[20,40,60,80]),
 ('8.1','Prevalence of undernourishment (%)','A1','Foundation',['NEED'],'','t','L',[25,15,7.5,2.5]),
 ('8.5','Women who own land (% holders)','A1','Foundation',['NEED','EQ'],'','t','H',[10,25,40,50]),
 ('2.1','Rural mobile broadband coverage (3G/4G)','C1','Foundation',['ALL'],'UNIVERSAL','t','H',[20,40,60,80]),
 ('2.4','Individuals using the Internet (%)','C1','Foundation',['ALL'],'','t','H',[20,40,60,80]),
 ('2.5','Mobile broadband price (% GNI pc)','C1','Foundation',['ALL'],'','t','L',[10,5,2,1]),
 ('2.7','Rural smartphone ownership (%)','C1','Foundation',['ALL'],'','t','H',[20,40,60,80]),
 ('2.9','Rural electricity access (%)','C1','Foundation',['ALL'],'UNIVERSAL','t','H',[20,40,60,80]),
 ('2.11','Device financing/subsidy schemes','C1','Foundation',['ALL'],'','l','',[]),
 ('3.1','UN E-Government Development Index','C2','Enablers',['AGI','ALL'],'','t','H',[0.2,0.4,0.6,0.8]),
 ('3.3','National farmer registry','C2','Enablers',['FIN','AGI','ADV'],'UC:FIN,AGI','l','',[]),
 ('3.4','Digital land/plot registration','C2','Enablers',['FIN','AGI'],'','l','',[]),
 ('3.5','Open agricultural data (machine-readable, AI-ready)','C2','Enablers',['AGI','ADV','SMF'],'','l','',[]),
 ('3.6','Weather/climate data infrastructure','C2','Enablers',['ADV','SMF','AGI'],'','l','',[]),
 ('3.7','Satellite/EO data integration','C2','Enablers',['AGI','SMF'],'','l','',[]),
 ('3.8','National soil map/database','C2','Enablers',['ADV','SMF'],'','l','',[]),
 ('3.11','Agricultural data interoperability standards','C2','Enablers',['AGI','ALL'],'UC:AGI','l','',[]),
 ('4.1','Data protection/privacy law','C3','Enablers',['ALL'],'UNIVERSAL','l','',[]),
 ('4.2','Cybersecurity framework (ITU GCI)','C3','Enablers',['ALL'],'','t','H',[0.2,0.4,0.6,0.8]),
 ('4.3','Government AI Readiness Index','C3','Enablers',['AGI','ALL'],'','t','H',[20,40,60,80]),
 ('4.4','National digital agriculture strategy','C3','Enablers',['ALL'],'','l','',[]),
 ('4.5','Agricultural data governance framework','C3','Enablers',['AGI','FIN'],'UC:AGI','l','',[]),
 ('4.6','National AI strategy with agriculture component','C3','Enablers',['AGI','ALL'],'','l','',[]),
 ('4.7','Digital ID coverage (%)','C3','Enablers',['FIN','ALL'],'UC:FIN','t','H',[20,40,60,80]),
 ('4.9','Inter-ministerial coordination mechanism','C3','Enablers',['ALL'],'DELIVERY','l','',[]),
 ('5.2','Adult literacy rate (%)','C4','Enablers',['ALL'],'','t','H',[50,65,80,90]),
 ('5.3','Tertiary STEM enrollment (% gross)','C4','Enablers',['ALL'],'','t','H',[10,20,30,40]),
 ('5.4','Digital literacy among farmers (%)','C4','Enablers',['ALL'],'','t','H',[10,25,50,75]),
 ('5.5','Digital extension capability','C4','Enablers',['ADV'],'UC:ADV','l','',[]),
 ('5.7','MoAg digital/AI unit','C4','Enablers',['ALL'],'DELIVERY','l','',[]),
 ('5.8','Agtech/data-science training pipeline','C4','Enablers',['ALL'],'','l','',[]),
 ('5.12','Gender balance in digital-ag workforce (%)','C4','Enablers',['EQ','ADV'],'','t','H',[20,35,45,50]),
 ('6.1','Global Innovation Index','E1','Enablers',['ALL'],'','t','H',[25,35,45,55]),
 ('6.3','Business Ready (B-READY)','E1','Enablers',['ALL'],'','t','H',[30,45,60,75]),
 ('6.4','Agtech venture ecosystem','E1','Transformation',['ALL'],'','l','',[]),
 ('6.9','Public-private partnerships in digital ag','E1','Transformation',['ADV','AGI','SCM'],'','l','',[]),
 ('6.12','Digital public goods adopted','E1','Transformation',['ALL'],'','l','',[]),
 ('6.13','SME/agribusiness adoption of digital tools (%)','E1','Transformation',['SMF','SCM','MKT'],'','t','H',[10,25,50,75]),
 ('6.14','Agri-fintech rails for smallholders','E1','Transformation',['FIN'],'UC:FIN','l','',[]),
 ('3.9','Digital advisory platforms at scale','E1','Transformation',['ADV'],'','l','',[]),
 ('3.10','Agricultural e-commerce platforms','E1','Transformation',['MKT'],'','l','',[]),
 ('7.2','AI-enabled agricultural solutions deployed','E1','Transformation',['ADV','FIN','SCM','SMF','AGI'],'','l','',[]),
 ('7.12','Responsible-AI safeguards (consent, rights)','E1','Enablers',['AI'],'UC:AI','l','',[]),
 ('8.2','Account ownership, female (%)','O1','Outcomes',['FIN','EQ'],'','t','H',[20,40,60,80]),
 ('8.4','Mobile money account (%)','O1','Outcomes',['FIN'],'','t','H',[10,25,50,75]),
 ('8.6','Gender gap in phone ownership (pp)','O1','Outcomes',['EQ'],'','t','L',[20,10,5,2]),
 ('8.9','Smallholders reached by digital services (%)','O1','Outcomes',['ALL','EQ'],'','t','H',[10,25,50,75]),
 ('8.11','Services in local languages (%)','O1','Outcomes',['ADV','EQ'],'','t','H',[25,50,75,90]),
 ('8.12','Documented impact evidence (yield/income)','O1','Outcomes',['ALL'],'','l','',[]),
 ('8.17','Climate advisory reach (%)','O1','Outcomes',['ADV'],'','t','H',[20,40,60,80]),
]
MODEL = {m[0]: dict(name=m[1],pillar=m[2],layer=m[3],uc=m[4],prereq=m[5],kind=m[6],dir=m[7],th=m[8]) for m in M}
ABSORB = {'2.1':['2.2'],'2.4':['2.3'],'2.7':['2.6'],'3.5':['3.13','3.12'],'4.5':['4.8'],'4.6':['4.13'],
          '5.5':['1.9','5.6'],'5.7':['5.11'],'5.8':['5.9'],'5.12':['5.13'],'6.4':['6.5','6.6','6.10'],
          '6.13':['6.7'],'6.14':['6.11'],'7.2':['7.3','7.4','7.5','7.6','7.7'],'7.12':['7.10','7.11'],
          '8.2':['8.3'],'8.9':['8.7','8.8','8.16'],'8.12':['8.13'],'8.17':['8.14']}

def tlevel(v, d, th):
    ls = 1
    for i,t in enumerate(th):
        if (d=='H' and v>=t) or (d=='L' and v<=t): ls = i+2
    return ls

# ---------- compute ----------
# Ruling 13.1: the band is the level the pillar rounds to. Cuts sit at the midpoints
# between levels, not at arbitrary fifths of the 1-5 range. The previous edges
# (1.8/2.6/3.4/4.2) were inherited from v1.5 with no rationale on record, and their
# tolerance rose with the band: Established was reachable 0.4 below level 3, Advanced 0.6
# below level 4, Transformative 0.8 below level 5. Midpoint cuts make that a flat 0.5 and
# put every level at the centre of the band that carries its name.
BANDS=[(1,1.5,'Nascent'),(1.5,2.5,'Emerging'),(2.5,3.5,'Established'),(3.5,4.5,'Advanced'),(4.5,5.01,'Transformative')]
# The level each band is named for. The margin is measured from this rather than from the
# interval midpoint: the two end bands are half-width, so their midpoints are 1.25 and
# 4.75, and a pillar with every row at level 1 would read -0.25 instead of the +0.00 that
# makes the figure mean what it looks like it means.
BAND_LEVEL={'Nascent':1,'Emerging':2,'Established':3,'Advanced':4,'Transformative':5}
def band(x):
    for lo,hi,n in BANDS:
        if lo<=x<hi: return n
    return '—'
def run(country, D, refyear=2026):
    out=dict(country=country, indicators={}, pillars={}, layers={}, prereq={}, matrix={})
    for i,m in MODEL.items():
        r=D[i]
        stale = bool(r['year'] and r['cls']!='Gap' and r['year'] < refyear-3)
        out['indicators'][i]=dict(r, stale=stale, **{k:m[k] for k in ('name','pillar','layer','uc','prereq','kind')})
    for P in ['A1','C1','C2','C3','C4','E1','O1']:
        rows=[out['indicators'][i] for i in MODEL if MODEL[i]['pillar']==P]
        lv=[r['level'] for r in rows if r['level'] is not None]
        comp={c:sum(1 for r in rows if r['cls']==c) for c in ('Measured','Documented','Judged','Gap')}
        # comp reports the evidence CLASS of every row, including rows whose level is withheld.
        # The mean is taken over rated rows only, so rated/held must be published beside it: a
        # pillar mean that rests on 3 of 7 rows must not read as though it rests on 7 (defect 39).
        rated=len(lv)
        held=sum(1 for r in rows if r['level'] is None and r['cls']!='Gap')
        judged_rated=sum(1 for r in rows if r['cls']=='Judged' and r['level'] is not None)
        # weak: the band rests more on judgment, recorded gaps and withheld levels than on
        # levelled measured/documented evidence. Withheld levels count against it — before
        # they did not, so a pillar hollowed out by ratification holds could never flag.
        weak = (judged_rated + comp['Gap'] + held) > (rated - judged_rated)
        mean = r2(sum(lv)/len(lv)) if lv else None
        bnd = band(mean) if mean else 'Not rated'
        # Ruling 13.1: the signed distance from the level the band is named for. Zero means
        # the pillar sits squarely at that level; plus or minus 0.5 means it is on the edge
        # of the next one. Four of fourteen pillar bands in the worked examples turned on a
        # margin under 0.10, which the band alone never showed.
        margin = r2(mean - BAND_LEVEL[bnd]) if mean and bnd in BAND_LEVEL else None
        out['pillars'][P]=dict(n=len(rows), rated=rated, held=held, mean=mean,
                               band=bnd, margin=margin,
                               weak=weak, comp=comp, stale=sum(1 for r in rows if r['stale']))
    for L in ['Foundation','Enablers','Transformation','Outcomes']:
        lv=[out['indicators'][i]['level'] for i in MODEL if MODEL[i]['layer']==L and out['indicators'][i]['level'] is not None]
        out['layers'][L]=r2(sum(lv)/len(lv)) if lv else None
    F,T=out['layers']['Foundation'],out['layers']['Transformation']
    out['leapfrog']=dict(gap=(r2(F-T) if F and T else None), flag=(F and T and abs(F-T)>1.5),
                         reading=('Transformation running ahead of foundations — leapfrog fragility' if F and T and T-F>1.5
                                  else 'Foundations ahead of ecosystem — unrealized potential' if F and T and F-T>1.5 else 'No structural flag'))
    for i,m in MODEL.items():
        if not m['prereq']: continue
        r=out['indicators'][i]
        if r['cls']=='Gap' or r['level'] is None: st='Unverified'  # a row with no level asserts nothing: unrated is NOT absent (matches the workbook formula and spec 7)
        elif r['level'] and r['level']>=3: st='Present'
        elif r['level']==2: st='Present (narrow)'
        else: st='Absent'
        out['prereq'][i]=dict(name=m['name'], kind=m['prereq'], status=st)
    UCS=['ADV','SMF','MKT','SCM','FIN','AGI']
    uni_block=[i for i,p in out['prereq'].items() if p['kind']=='UNIVERSAL' and p['status']=='Absent']
    uni_narrow=[i for i,p in out['prereq'].items() if p['kind']=='UNIVERSAL' and p['status']=='Present (narrow)']  # narrow presence caps every column at Partial
    uni_unver=[i for i,p in out['prereq'].items() if p['kind']=='UNIVERSAL' and p['status']=='Unverified']  # spec 7: an unevidenced prerequisite 'cannot silently pass or fail'
    for uc in UCS:
        pres=[(i,out['prereq'][i]['status']) for i in out['prereq'] if out['prereq'][i]['kind'].startswith('UC:') and (uc in out['prereq'][i]['kind'] or (out['prereq'][i]['kind']=='UC:AI' and uc=='AGI'))]  # loop-1 ruling: UC:AI binds AGI pending spec definition of 'all AI-enabled services' (D6)
        bearing=[i for i in MODEL if (uc in MODEL[i]['uc'] or 'ALL' in MODEL[i]['uc']) and out['indicators'][i]['level'] is not None]
        lv=[out['indicators'][i]['level'] for i in bearing]
        mean=r2(sum(lv)/len(lv)) if lv else None
        # The bearing set mixes three roles: A1 rows measure the SEVERITY OF THE PROBLEM, O1 rows
        # measure ACHIEVED OUTCOMES, and the rest measure ENABLING READINESS. Averaging all three
        # into one readiness number is an open design question (spec 13.12), so the split and the
        # enabler-only mean are published beside the mean rather than silently folded into it.
        role={'A1':'need','O1':'outcome'}
        basis={'need':0,'outcome':0,'enabler':0}
        for i in bearing: basis[role.get(MODEL[i]['pillar'],'enabler')]+=1
        enab=[out['indicators'][i]['level'] for i in bearing if MODEL[i]['pillar'] not in ('A1','O1')]
        mean_enabler=r2(sum(enab)/len(enab)) if enab else None
        if uni_block: st='Blocked'; why='Universal: '+', '.join(uni_block)
        elif any(s=='Absent' for _,s in pres): st='Blocked'; why=', '.join(i for i,s in pres if s=='Absent')
        elif uni_unver: st='Unverified'; why='universal unverified: '+', '.join(uni_unver)
        elif any(s=='Unverified' for _,s in pres): st='Unverified'; why=', '.join(i for i,s in pres if s=='Unverified')
        elif any(s=='Present (narrow)' for _,s in pres) or (mean and mean<2.6): st='Partial'; why=', '.join(i for i,s in pres if 'narrow' in s) or 'thin enablers'
        elif uni_narrow: st='Partial'; why='universal narrow: '+', '.join(uni_narrow)
        else: st='Ready'; why=''
        out['matrix'][uc]=dict(status=st, why=why, mean=mean, prereqs=pres,
                               n_bearing=len(bearing), basis=basis, mean_enabler=mean_enabler,
                               mean_driven=(st=='Partial' and why=='thin enablers'))
    rated=[(i,out['indicators'][i]) for i in MODEL if out['indicators'][i]['level'] is not None]
    out['constraints']=[dict(id=i,name=r['name'],level=r['level'],pillar=r['pillar'],prereq=bool(r['prereq'])) for i,r in sorted(rated,key=lambda x:(x[1]['level'],x[0]))[:12]]
    out['kpi']=[dict(id=i,name=r['name'],value=r['value'],year=r['year'],src=r['src']) for i,r in out['indicators'].items() if r['cls']=='Measured' and r['pillar'] in ('A1','O1')]
    # The section states "Judged rows and recorded gaps". It previously carried a Judged row only
    # when that row was a prerequisite, so a country with a non-prerequisite Judged row published
    # a list shorter than its own caption promised (defect 42).
    out['verify']=[dict(id=i,name=r['name'],cls=r['cls']) for i,r in out['indicators'].items() if r['cls'] in ('Gap','Judged')]
    out['refresh']=[dict(id=i,name=r['name'],year=r['year']) for i,r in out['indicators'].items() if r['stale']]
    out['counts']={c:sum(1 for i in MODEL if out['indicators'][i]['cls']==c) for c in ('Measured','Documented','Judged','Gap')}
    out['held']=sum(1 for i in MODEL if out['indicators'][i]['level'] is None and out['indicators'][i]['cls']!='Gap')
    out['rated']=sum(1 for i in MODEL if out['indicators'][i]['level'] is not None)
    return out


def main(inp, outp, country):
    data = json.load(open(inp))
    cand = {k: v for k, v in data.items() if k.startswith("A1-CAND-")}
    rows = {k: v for k, v in data.items() if not k.startswith("A1-CAND-")}
    missing = [i for i in MODEL if i not in rows]
    if missing:
        raise SystemExit(f"input missing {len(missing)} indicator rows: {missing}")
    for k, v in rows.items():
        v.setdefault("note", ""); v.setdefault("subs", []); v.setdefault("tier", ""); v.setdefault("url", "")
    res = run(country, rows)
    for i in res["indicators"]:
        res["indicators"][i]["tier"] = rows[i].get("tier", "")
        res["indicators"][i]["url"] = rows[i].get("url", "")
    res["candidates"] = cand
    json.dump(res, open(outp, "w"), indent=1, default=str)
    print(country, res["counts"])
    print(" pillars:", {p: (("(" + d["band"] + ")") if d["weak"] else d["band"]) for p, d in res["pillars"].items()})
    print(" matrix:", {k: v["status"] for k, v in res["matrix"].items()})
    print(" prereq:", {k: v["status"] for k, v in res["prereq"].items()})

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
