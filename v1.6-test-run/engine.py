import openpyxl, json, re

# ---------- v1.6 model: 57 indicators ----------
# (id, name, pillar, layer, usecases, prereq, kind, dir, thresholds L2..L5)
# A1 thresholds are TEST values pending ratification (spec open item)
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

# ---------- Egypt: map v1.5 workbook through the census ----------
wb = openpyxl.load_workbook('/Users/randeepsudan/pCloud Drive/02 World Bank/Projects/DAR/DAMM/DAMM v1.5 Scoring Workbook — Egypt worked example.xlsx', data_only=True)
raw = {}
for r in wb['Egypt (worked)'].iter_rows(min_row=8, max_row=109, values_only=True):
    if r[1]: raw[str(r[1])] = dict(val=r[8], eff=r[11], year=r[13], src=str(r[15] or ''), note=str(r[17] or ''))
def isnum(x): return isinstance(x,(int,float))
egy = {}
for i in MODEL:
    r = raw.get(i, {})
    v, eff, yr, src = r.get('val'), r.get('eff'), r.get('year'), r.get('src','')
    if isnum(v): cls='Measured'; value=v
    elif v not in (None,''): cls='Documented'; value=str(v)
    elif src and src not in ('','None'): cls='Documented'; value=src[:90]   # citation-as-value migration
    elif eff is not None: cls='Judged'; value='(assessor judgement, no artefact recorded)'
    else: cls='Gap'; value='DATA GAP — not populated in v1.5 assessment'
    subs = [(a, raw.get(a,{}).get('eff')) for a in ABSORB.get(i,[]) if raw.get(a,{}).get('eff') is not None]
    m = MODEL[i]
    if cls=='Measured' and eff is None and m['kind']=='t':
        eff = tlevel(v, m['dir'], m['th'])   # migration rule: Measured => threshold-scored (A1 context rows)
    egy[i] = dict(value=value, cls=cls, level=eff, year=(int(yr) if yr else None), src=src[:80], note=r.get('note','')[:150], subs=subs)

# ---------- Nigeria: machine-first run, session-verified only ----------
def R(value, cls, level, year, src, note='', subs=None):
    return dict(value=value, cls=cls, level=level, year=year, src=src, note=note, subs=subs or [])
G = lambda note: R('DATA GAP — searched, not verified this run','Gap',None,2026,'Machine pass 2026-08-21',note)
nga = {
 '1.1': R(3494.9,'Measured',3,2025,'World Bank WDI NV.AGR.EMPL.KD'),
 '1.2': R(1558,'Measured',2,2024,'World Bank WDI AG.YLD.CREL.KG','Yield less than half of Egypt-scale systems'),
 '1.3': R(33.5,'Measured',2,2025,'World Bank WDI SL.AGR.EMPL.ZS (ILO model)'),
 '1.4': R(119.85,'Measured',4,2022,'World Bank WDI AG.PRD.FOOD.XD','Stale: 2022'),
 '1.5': G('No verified national post-harvest loss rate; APHLIS/FMAFS to confirm'),
 '1.6': G('RNR-style market access survey not found'),
 '1.7': G('EFInA/CBN smallholder credit share to verify'),
 '1.8': G('CSA adoption share unverified'),
 '8.1': R(19.9,'Measured',2,2023,'World Bank WDI SN.ITK.DEFC.ZS'),
 '8.5': G('FAO gender & land rights figure to verify'),
 '2.1': R('~90% pop. 3G; 4G expansion toward 94% target; rural share unpublished','Documented',3,2025,'NCC 2024 Year-End Performance Report; GSMA','Rural-specific coverage not published — level judged from national data'),
 '2.4': R(41.2,'Measured',3,2024,'World Bank WDI IT.NET.USER.ZS'),
 '2.5': R(4.2,'Measured',3,2024,'ITU/A4AI via GSMA: 2GB basket % GNI pc'),
 '2.7': G('GSMA rural smartphone ownership to verify'),
 '2.9': R(23.5,'Measured',2,2024,'World Bank WDI EG.ELC.ACCS.RU.ZS','Near the universal-gate floor — rural power is the fragile foundation'),
 '2.11': G('Device financing schemes not verified'),
 '3.1': R(0.4815,'Measured',3,2024,'UN E-Government Survey 2024 (rank 144/193)'),
 '3.3': R('NIN-enabled National Digital Farmers Registry launched; 279k farmers supported 2024/25 season','Documented',2,2025,'FMAFS & NIMC press releases; TheCable','Operating pilot, <1% of farm households — narrow coverage'),
 '3.4': G('State-level land registries fragmented; national digital cadastre unverified'),
 '3.5': R('(assessor judgement)','Judged',2,2026,'NBS ag statistics exist; no open ag-data portal found'),
 '3.6': R('NiMet Seasonal Climate Prediction, annual national service','Documented',3,2026,'NiMet SCP 2026','Operational; ag-tailored downscaling partial'),
 '3.7': R('(assessor judgement)','Judged',2,2026,'NASRDA EO assets; ag integration ad hoc'),
 '3.8': G('National digital soil information service unverified'),
 '3.11': R('(assessor judgement)','Judged',1,2026,'No ag-data interoperability standards found','PREREQUISITE ABSENT for AGI'),
 '4.1': R('NDPA 2023 in force; NDPC enforcing (1,368 compliance notices, GAID 2025)','Documented',4,2025,'NDPC; Jones Day Aug 2025','Operating with active enforcement'),
 '4.2': R(0.824,'Measured',5,2024,'ITU Global Cybersecurity Index 2024','ITU places Nigeria Tier 3 despite 82.4 score — threshold read with caution'),
 '4.3': G('Oxford Insights AI Readiness score not verified this run'),
 '4.4': R('NDAS 2020-2030 remains a DRAFT; NATIP 2022-27 carries the digital-ag budget line','Documented',2,2020,'NITDA draft NDAS; FMAFS NATIP','Announced, never adopted — stale and unowned'),
 '4.5': R('(assessor judgement)','Judged',1,2026,'No agricultural data governance framework found','PREREQUISITE ABSENT for AGI'),
 '4.6': R('NAIS 2024 adopted; agriculture a named priority sector','Documented',3,2024,'NAIS 2024; OECD.AI'),
 '4.7': R(57.2,'Measured',3,2026,'NIMC: 137.4M NIN Jul 2026 / ~240M pop.','Ward-level drive underway; 2026 full-coverage directive'),
 '4.9': R('FMAFS-NIMC registry partnership; NITDA-FMARD NDAS collaboration; no standing mechanism','Documented',2,2025,'NIMC/FMAFS G2P project','DELIVERY RISK: coordination is project-based'),
 '5.2': R(70.4,'Measured',3,2024,'World Bank WDI SE.ADT.LITR.ZS'),
 '5.3': R(9.7,'Measured',1,2011,'World Bank WDI SE.TER.ENRR','Stale: last national observation 2011'),
 '5.4': G('Farmer digital literacy survey not found'),
 '5.5': R('(assessor judgement)','Judged',2,2026,'NAERLS + e-extension pilots; reach unquantified','ADV prerequisite: present but narrow'),
 '5.7': G('FMAFS digital/AI unit not verified — DELIVERY flag Unverified'),
 '5.8': R('(assessor judgement)','Judged',2,2026,'University agtech programmes present; scale unverified'),
 '5.12': G('Gender balance in digital-ag workforce unmeasured'),
 '6.1': R(21.1,'Measured',1,2025,'WIPO GII 2025 (rank 105/139; top climber)','Score below L2 floor despite momentum'),
 '6.3': G('B-READY coverage of Nigeria unverified'),
 '6.4': R('Dense agtech cohort: ThriveAgric, Crop2Cash, Hello Tractor, Releaf ...; $865M digital lending 2025 (all sectors)','Documented',3,2025,'AgFunder 2025; CBN Fintech Report 2026','Operating and funded; ag-specific capital thin'),
 '6.9': R('BoA-Cellulant; FMAFS-NIMC G2P; LIFE-ND platforms','Documented',3,2025,'BoA; NIMC; LIFE-ND'),
 '6.12': G('DPG adoption in agriculture unverified'),
 '6.13': G('SME digital adoption share unmeasured'),
 '6.14': R('PSBs (MoMo, SmartCash) + agri-fintech rails (Crop2Cash, ThriveAgric); smallholder reach unquantified','Documented',3,2025,'CBN Fintech Report 2026; AgFunder','FIN prerequisite present; scale rung unverified'),
 '3.9': R('Multiple advisory platforms with >10k users (AgFunder-listed cohort)','Documented',3,2025,'AgFunder 2025'),
 '3.10': R('(assessor judgement)','Judged',2,2026,'Ag marketplaces present; verified scale thin'),
 '7.2': R('AI-powered national agro-productivity system launched 2026; isolated private AI deployments','Documented',2,2026,'FMAFS launch (African Sustainability Matters)','Early: announced-to-pilot'),
 '7.12': R('NDPA general consent basis; no ag/AI-specific provisions','Documented',2,2023,'NDPA 2023','AI prerequisite: general law only — Partial'),
 '8.2': R(52.2,'Measured',3,2024,'World Bank WDI FX.OWN.TOTL.FE.ZS (Findex 2025 wave)'),
 '8.4': G('Findex 2025 mobile-money split not retrievable via API this run'),
 '8.6': G('GSMA gender gap figure to verify'),
 '8.9': G('No national figure for smallholder digital reach'),
 '8.11': R('(assessor judgement)','Judged',2,2026,'Major platforms partially in Hausa/Yoruba/Igbo (e.g. USSD advisory)'),
 '8.12': G('No verified impact evaluation retrieved; platform yield claims unaudited'),
 '8.17': G('Climate advisory reach unmeasured'),
}

# ---------- compute ----------
BANDS=[(1,1.8,'Nascent'),(1.8,2.6,'Emerging'),(2.6,3.4,'Established'),(3.4,4.2,'Advanced'),(4.2,5.01,'Transformative')]
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
        weak = comp['Judged']+comp['Gap'] > comp['Measured']+comp['Documented']
        mean = round(sum(lv)/len(lv),2) if lv else None
        out['pillars'][P]=dict(n=len(rows), mean=mean, band=(band(mean) if mean else 'Not rated'),
                               weak=weak, comp=comp, stale=sum(1 for r in rows if r['stale']))
    for L in ['Foundation','Enablers','Transformation','Outcomes']:
        lv=[out['indicators'][i]['level'] for i in MODEL if MODEL[i]['layer']==L and out['indicators'][i]['level'] is not None]
        out['layers'][L]=round(sum(lv)/len(lv),2) if lv else None
    F,T=out['layers']['Foundation'],out['layers']['Transformation']
    out['leapfrog']=dict(gap=(round(F-T,2) if F and T else None), flag=(F and T and abs(F-T)>1.5),
                         reading=('Transformation running ahead of foundations — leapfrog fragility' if F and T and T-F>1.5
                                  else 'Foundations ahead of ecosystem — unrealized potential' if F and T and F-T>1.5 else 'No structural flag'))
    for i,m in MODEL.items():
        if not m['prereq']: continue
        r=out['indicators'][i]
        if r['cls']=='Gap': st='Unverified'
        elif r['level'] and r['level']>=3: st='Present'
        elif r['level']==2: st='Present (narrow)'
        else: st='Absent'
        out['prereq'][i]=dict(name=m['name'], kind=m['prereq'], status=st)
    UCS=['ADV','SMF','MKT','SCM','FIN','AGI']
    uni_block=[i for i,p in out['prereq'].items() if p['kind']=='UNIVERSAL' and p['status']=='Absent']
    for uc in UCS:
        pres=[(i,out['prereq'][i]['status']) for i in out['prereq'] if out['prereq'][i]['kind'].startswith('UC:') and uc in out['prereq'][i]['kind']]
        lv=[out['indicators'][i]['level'] for i in MODEL if (uc in MODEL[i]['uc'] or 'ALL' in MODEL[i]['uc']) and out['indicators'][i]['level'] is not None]
        mean=round(sum(lv)/len(lv),2) if lv else None
        if uni_block: st='Blocked'; why='Universal: '+', '.join(uni_block)
        elif any(s=='Absent' for _,s in pres): st='Blocked'; why=', '.join(i for i,s in pres if s=='Absent')
        elif any(s=='Unverified' for _,s in pres): st='Unverified'; why=', '.join(i for i,s in pres if s=='Unverified')
        elif any(s=='Present (narrow)' for _,s in pres) or (mean and mean<2.6): st='Partial'; why=', '.join(i for i,s in pres if 'narrow' in s) or 'thin enablers'
        else: st='Ready'; why=''
        out['matrix'][uc]=dict(status=st, why=why, mean=mean, prereqs=pres)
    rated=[(i,out['indicators'][i]) for i in MODEL if out['indicators'][i]['level'] is not None]
    out['constraints']=[dict(id=i,name=r['name'],level=r['level'],pillar=r['pillar'],prereq=bool(r['prereq'])) for i,r in sorted(rated,key=lambda x:(x[1]['level'],x[0]))[:12]]
    out['kpi']=[dict(id=i,name=r['name'],value=r['value'],year=r['year'],src=r['src']) for i,r in out['indicators'].items() if r['cls']=='Measured' and r['pillar'] in ('A1','O1')]
    out['verify']=[dict(id=i,name=r['name'],cls=r['cls']) for i,r in out['indicators'].items() if r['cls']=='Gap' or (r['cls']=='Judged' and r['prereq'])]
    out['refresh']=[dict(id=i,name=r['name'],year=r['year']) for i,r in out['indicators'].items() if r['stale']]
    out['counts']={c:sum(1 for i in MODEL if out['indicators'][i]['cls']==c) for c in ('Measured','Documented','Judged','Gap')}
    return out

for name,data in [('egypt',egy),('nigeria',nga)]:
    res=run(name.capitalize(),data)
    json.dump(res,open(name+'_v16.json','w'),indent=1,default=str)
    print('===',name.upper(),res['counts'])
    for P,p in res['pillars'].items():
        print(' %s mean=%s band=%s%s comp=%s stale=%d'%(P,p['mean'],('('+p['band']+')') if p['weak'] else p['band'],'',p['comp'],p['stale']))
    print(' layers',res['layers'],'leapfrog',res['leapfrog']['gap'],res['leapfrog']['reading'])
    print(' matrix:',{k:v['status'] for k,v in res['matrix'].items()})
    print(' prereq:',{k:v['status'] for k,v in res['prereq'].items()})
    print(' verify n=%d refresh n=%d'%(len(res['verify']),len(res['refresh'])))
