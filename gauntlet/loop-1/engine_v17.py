#!/usr/bin/env python3
"""DAMM v1.7 engine — gauntlet loop 1.
Same scoring mathematics as the v1.6 reference engine (unchanged by design);
generalized to load assessment rows from JSON and pass tier/url provenance through.
Usage: python3 engine_v17.py <input_rows.json> <output.json> <CountryName>
Input rows: {id: {value, cls, level, year, src, note, tier, url, subs?}}
Rows with id starting "A1-CAND-" are spec-13.2 provisional candidates: carried in
output["candidates"], never scored into pillars/layers/matrix.
"""
import hashlib, json, math, os, sys
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
 ('7.12','Responsible-AI safeguards (consent, rights)','E1','Enablers',['AI'],'UC:ADV,SMF,FIN,AGI','l','',[]),
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

def evidence_class(r):
    """Derive the canonical evidence class when a ratified input omits it."""
    value = r.get('value')
    if value is None or value == '': return ''
    if isinstance(value, (int, float)): return 'Measured'
    if 'DATA GAP' in str(value).upper(): return 'Gap'
    if r.get('src') and r.get('tier') != 'T5': return 'Documented'
    return 'Judged'

def effective_level(r, m):
    """Apply the current thresholds without overriding an explicit scoring hold.

    Input artifacts carry their last computed level for reviewability.  Once a level is
    present, however, it is a cache rather than an independent scoring input: a threshold
    revision must flow through on the next score.  ``level: null`` is different.  It is
    how construct/ratification review withholds a score, so it must remain null until that
    hold is deliberately released.
    """
    if (r.get('cls') == 'Measured' and m['kind'] == 't'
            and ('level' not in r or r.get('level') is not None)):
        return tlevel(r['value'], m['dir'], m['th'])
    return r.get('level')


# Decision 13.3 compatibility boundary.  The free-form prerequisite strings remain the
# active rule until a complete mapping and its containing model are both ratified.  That
# keeps every current v1.7 output unchanged while allowing a future canonical model to
# switch both scorers to the edge graph without another engine-only constant.
_PREREQUISITE_STATUSES = ('Absent', 'Unverified', 'Present (narrow)', 'Present')
_READINESS_STATUSES = ('Blocked', 'Unverified', 'Partial', 'Ready')
_GATE_OUTCOMES = {
    'Absent': 'Blocked', 'Unverified': 'Unverified',
    'Present (narrow)': 'Partial', 'Present': 'no_change',
}
_DELIVERY_RISK_OUTCOMES = {
    'Absent': 'flag', 'Unverified': 'verify',
    'Present (narrow)': 'flag_narrow', 'Present': 'no_change',
}
_INTERVENTION_PROFILE_FIELDS = frozenset({
    'targeted_farmer_level_delivery',
    'cross_organization_agricultural_data_sharing',
    'cross_ministerial_delivery', 'moag_led_or_owned',
    'uses_personal_data', 'uses_farm_level_data', 'ai_enabled',
})


def _mapping_error(message):
    raise ValueError('invalid ratified prerequisite_mapping: ' + message)


def _valid_predicate(predicate):
    if not isinstance(predicate, dict):
        return False
    if set(predicate) == {'field', 'equals'}:
        return (predicate['field'] in _INTERVENTION_PROFILE_FIELDS
                and type(predicate['equals']) is bool)
    for operator in ('any', 'all'):
        if set(predicate) == {operator}:
            children = predicate[operator]
            return (isinstance(children, list) and bool(children)
                    and all(_valid_predicate(child) for child in children))
    return False


def _predicate_result(predicate, profile):
    """Evaluate a boolean intervention predicate with an explicit unknown state."""
    if 'field' in predicate:
        field = predicate['field']
        if field not in profile:
            return None
        if type(profile[field]) is not bool:
            raise ValueError(
                f'intervention profile field {field!r} must be boolean')
        return profile[field] == predicate['equals']
    operator = 'any' if 'any' in predicate else 'all'
    results = [_predicate_result(child, profile) for child in predicate[operator]]
    if operator == 'any':
        if any(result is True for result in results):
            return True
        return None if any(result is None for result in results) else False
    if any(result is False for result in results):
        return False
    return None if any(result is None for result in results) else True


def _canonical_model_root():
    """Load the optional model root for the CLI; ``run`` itself stays filesystem-pure."""
    path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..', 'model', 'DAMM-v1.7-model.json'))
    try:
        with open(path) as source:
            return json.load(source)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as error:
        raise ValueError('canonical model root cannot be loaded') from error


def _ratified_engine_projection(model_root):
    """Translate a ratified exported model into the engine's compact row vocabulary.

    Revision pins are meaningful only if the supplied model drives all scoring inputs.
    The v1.7 engine still requires the same indicator inventory, but names, thresholds,
    directions, roles, groupings, bands, and configuration come from ``model_root``.
    """
    indicators = model_root.get('indicators')
    pillars = model_root.get('pillars')
    layers = model_root.get('layers')
    use_cases = model_root.get('use_cases')
    bands = model_root.get('bands')
    config = model_root.get('config')
    if (not isinstance(indicators, list)
            or len(indicators) != len(MODEL)
            or any(not isinstance(row, dict) for row in indicators)
            or not isinstance(pillars, dict) or not pillars
            or not isinstance(layers, list) or not layers
            or any(not isinstance(layer, str) or not layer for layer in layers)
            or len(set(layers)) != len(layers)
            or not isinstance(use_cases, dict) or not use_cases
            or not isinstance(bands, list) or len(bands) != 5
            or any(not isinstance(item, dict) for item in bands)
            or not isinstance(config, dict)):
        raise ValueError('invalid ratified model_spec: scoring catalogs are malformed')

    ids = [row.get('id') for row in indicators]
    if (any(not isinstance(indicator_id, str) for indicator_id in ids)
            or len(set(ids)) != len(ids) or set(ids) != set(MODEL)):
        raise ValueError(
            'invalid ratified model_spec: indicator inventory differs from DAMM v1.7')
    if (any(not isinstance(key, str) or not key for key in pillars)
            or any(not isinstance(key, str) or not key for key in use_cases)):
        raise ValueError('invalid ratified model_spec: catalog ids are malformed')
    if (set(pillars) != {'A1', 'C1', 'C2', 'C3', 'C4', 'E1', 'O1'}
            or set(layers) != {
                'Foundation', 'Enablers', 'Transformation', 'Outcomes'}
            or set(use_cases) != {'ADV', 'SMF', 'MKT', 'SCM', 'FIN', 'AGI'}):
        raise ValueError(
            'invalid ratified model_spec: DAMM v1.7 scoring catalogs differ')

    projection = {}
    for row in indicators:
        method = row.get('method')
        direction = row.get('direction')
        thresholds = row.get('thresholds')
        row_use_cases = row.get('use_cases')
        tags = row.get('tags')
        prerequisite = row.get('prerequisite')
        if (not isinstance(row.get('name'), str) or not row['name'].strip()
                or row.get('pillar') not in pillars
                or row.get('layer') not in layers
                or not isinstance(row_use_cases, list)
                or any(not isinstance(item, str) for item in row_use_cases)
                or not isinstance(tags, list)
                or any(not isinstance(item, str) for item in tags)
                or prerequisite is not None and not isinstance(prerequisite, str)
                or method not in ('threshold', 'ladder')):
            raise ValueError(
                'invalid ratified model_spec: indicator scoring metadata is malformed')
        if method == 'threshold':
            if (direction not in ('higher-is-better', 'lower-is-better')
                    or not isinstance(thresholds, list) or len(thresholds) != 4
                    or any(type(value) not in (int, float) for value in thresholds)):
                raise ValueError(
                    'invalid ratified model_spec: threshold rule is malformed')
            kind = 't'
            compact_direction = 'H' if direction == 'higher-is-better' else 'L'
        else:
            if direction is not None or thresholds not in (None, []):
                raise ValueError(
                    'invalid ratified model_spec: ladder rule is malformed')
            kind, compact_direction, thresholds = 'l', '', []
        projection[row['id']] = {
            'name': row['name'], 'pillar': row['pillar'], 'layer': row['layer'],
            'uc': list(row_use_cases) + list(tags),
            'use_cases': list(row_use_cases), 'tags': list(tags),
            'prereq': prerequisite or '', 'kind': kind,
            'dir': compact_direction, 'th': list(thresholds),
        }

    normalized_bands = []
    for item in bands:
        if (not isinstance(item.get('name'), str) or not item['name'].strip()
                or type(item.get('lo')) not in (int, float)
                or type(item.get('hi')) not in (int, float)
                or item['lo'] >= item['hi']):
            raise ValueError('invalid ratified model_spec: bands are malformed')
        normalized_bands.append((item['lo'], item['hi'], item['name']))
    for key in ('assessment_year', 'readiness_threshold',
                'leapfrog_threshold', 'staleness_years'):
        if type(config.get(key)) not in (int, float):
            raise ValueError(
                'invalid ratified model_spec: scoring configuration is malformed')
    if config.get('rounding') != 'half-up':
        raise ValueError(
            'invalid ratified model_spec: engine supports half-up rounding only')
    return {
        'model': projection,
        'pillars': list(pillars),
        'layers': list(layers),
        'use_cases': list(use_cases),
        'bands': normalized_bands,
        'band_levels': {item[2]: index + 1
                        for index, item in enumerate(normalized_bands)},
        'assessment_year': config['assessment_year'],
        'readiness_threshold': config['readiness_threshold'],
        'leapfrog_threshold': config['leapfrog_threshold'],
        'staleness_years': config['staleness_years'],
    }


def _ratified_prerequisite_mapping(model_root, use_case_ids, prerequisite_ids):
    """Return a complete active mapping, or None while the model remains legacy."""
    if not isinstance(model_root, dict):
        return None
    mapping = model_root.get('prerequisite_mapping')
    if model_root.get('ratified') is not True:
        return None
    if model_root.get('status') != 'ratified':
        _mapping_error('ratified model root must have status ratified')
    if not isinstance(mapping, dict) or mapping.get('ratified') is not True:
        _mapping_error('ratified model root requires a ratified mapping')

    if mapping.get('decision_id') != '13.3' or mapping.get('status') != 'ratified':
        _mapping_error('decision/status is not ratified 13.3')
    if (type(mapping.get('revision')) is not int or mapping['revision'] < 1
            or not isinstance(model_root.get('version'), str)
            or not model_root['version'].strip()
            or type(model_root.get('revision')) is not int
            or model_root['revision'] < 1):
        _mapping_error('model and mapping revisions must be pinned')
    config = model_root.get('config')
    readiness_threshold = (config.get('readiness_threshold')
                           if isinstance(config, dict) else None)
    if (type(readiness_threshold) not in (int, float)
            or not 0 < readiness_threshold <= 5):
        _mapping_error('model readiness threshold is missing or invalid')
    if (not isinstance(mapping.get('use_case_ids'), list)
            or len(mapping['use_case_ids']) != len(use_case_ids)
            or any(not isinstance(item, str)
                   for item in mapping['use_case_ids'])
            or set(mapping['use_case_ids']) != set(use_case_ids)
            or not isinstance(mapping.get('prerequisite_ids'), list)
            or len(mapping['prerequisite_ids']) != len(prerequisite_ids)
            or any(not isinstance(item, str)
                   for item in mapping['prerequisite_ids'])
            or set(mapping['prerequisite_ids']) != set(prerequisite_ids)):
        _mapping_error('declared use-case/prerequisite inventories do not match')

    precedence = mapping.get('status_precedence')
    if precedence != list(_READINESS_STATUSES):
        _mapping_error('status_precedence does not match the ratified schema')
    if mapping.get('conditional_policy') != {
            'missing_profile': 'report_condition_without_mutating_base_status',
            'true': 'activate_edge',
            'false': 'ignore_edge'}:
        _mapping_error('conditional_policy is missing or unsupported')

    edges = mapping.get('edges')
    expected_pairs = {(prerequisite_id, use_case_id)
                      for prerequisite_id in prerequisite_ids
                      for use_case_id in use_case_ids}
    if not isinstance(edges, list) or len(edges) != 72 or len(expected_pairs) != 72:
        _mapping_error('edges must be the complete 12 x 6 graph')

    actual_pairs = []
    for edge in edges:
        if (not isinstance(edge, dict)
                or not isinstance(edge.get('prerequisite_id'), str)
                or not isinstance(edge.get('use_case_id'), str)):
            _mapping_error('every edge must name string prerequisite/use-case ids')
        actual_pairs.append((edge['prerequisite_id'], edge['use_case_id']))
        if (not isinstance(edge.get('rationale'), str) or not edge['rationale'].strip()
                or not isinstance(edge.get('basis'), list) or not edge['basis']
                or any(not isinstance(item, str) or not item.strip()
                       for item in edge['basis'])
                or edge.get('decision_status') != 'ratified'):
            _mapping_error('every edge needs ratified rationale and basis metadata')

        effect = edge.get('effect')
        applicability = edge.get('applicability')
        mode = applicability.get('mode') if isinstance(applicability, dict) else None
        if effect not in ('gate', 'delivery_risk', 'none'):
            _mapping_error('edge effect is outside gate/delivery_risk/none')
        if effect == 'none':
            if applicability != {'mode': 'never'}:
                _mapping_error('none edges must use exact never applicability')
            if 'on_prerequisite_status' in edge:
                _mapping_error('none edges cannot declare prerequisite outcomes')
            continue
        if mode not in ('always', 'conditional'):
            _mapping_error('positive edges must be always or conditional')
        if mode == 'always':
            if applicability != {'mode': 'always'}:
                _mapping_error('always edges must use exact always applicability')
        elif (set(applicability) != {'mode', 'predicate'}
              or not _valid_predicate(applicability.get('predicate'))):
            _mapping_error('conditional edge predicate is malformed')

        outcomes = edge.get('on_prerequisite_status')
        if not isinstance(outcomes, dict) or set(outcomes) != set(_PREREQUISITE_STATUSES):
            _mapping_error('positive edges must declare all prerequisite outcomes')
        if effect == 'gate' and outcomes != _GATE_OUTCOMES:
            _mapping_error('gate outcomes do not match the ratified schema')
        if effect == 'delivery_risk' and outcomes != _DELIVERY_RISK_OUTCOMES:
            _mapping_error('delivery-risk outcomes do not match the ratified schema')

    if len(set(actual_pairs)) != 72 or set(actual_pairs) != expected_pairs:
        _mapping_error('edge pairs are duplicated or incomplete')
    effects = {edge['effect'] for edge in edges}
    if not {'gate', 'delivery_risk', 'none'} <= effects:
        _mapping_error('mapping must exercise gate, delivery_risk, and none effects')
    if not any(edge['effect'] == 'gate'
               and edge['applicability'] == {'mode': 'always'}
               for edge in edges):
        _mapping_error('mapping must include an always gate')
    return mapping


def _mapped_readiness(mapping, edges, prerequisite_statuses, mean_readiness,
                      readiness_threshold, intervention_profile):
    """Evaluate one use-case edge column without letting risks mutate readiness."""
    active_gates, conditional_constraints, delivery_risks = [], [], []
    candidates = []
    for edge in edges:
        if edge['effect'] == 'none':
            continue
        prerequisite_id = edge['prerequisite_id']
        prerequisite_status = prerequisite_statuses[prerequisite_id]['status']
        action = edge['on_prerequisite_status'][prerequisite_status]
        mode = edge['applicability']['mode']
        evaluation = True
        if mode == 'conditional':
            evaluation = _predicate_result(
                edge['applicability']['predicate'], intervention_profile)
            conditional_constraints.append({
                'prerequisite_id': edge['prerequisite_id'],
                'effect': edge['effect'],
                'predicate': edge['applicability']['predicate'],
                'prerequisite_status': prerequisite_status,
                'outcome_if_active': action,
                'evaluation': ('active' if evaluation is True else
                               'inactive' if evaluation is False else 'unresolved'),
            })
        if evaluation is not True:
            continue

        if edge['effect'] == 'gate':
            gate = {
                'prerequisite_id': prerequisite_id,
                'prerequisite_status': prerequisite_status,
                'outcome': action,
                'applicability': mode,
            }
            active_gates.append(gate)
            if action != 'no_change':
                candidates.append((action, {
                    'type': 'gate', 'prerequisite_id': prerequisite_id,
                    'prerequisite_status': prerequisite_status,
                }))
        elif edge['effect'] == 'delivery_risk' and action != 'no_change':
            delivery_risks.append({
                'prerequisite_id': prerequisite_id,
                'prerequisite_status': prerequisite_status,
                'action': action,
                'applicability': mode,
            })

    if mean_readiness is not None and mean_readiness < readiness_threshold:
        candidates.append(('Partial', {
            'type': 'readiness_mean', 'mean_readiness': mean_readiness,
            'threshold': readiness_threshold,
        }))
    rank = {status: index for index, status in enumerate(mapping['status_precedence'])}
    status = min(candidates, key=lambda item: rank[item[0]])[0] if candidates else 'Ready'
    drivers = [driver for outcome, driver in candidates if outcome == status]
    drivers.sort(key=lambda item: (
        0 if item['type'] == 'gate' else 1,
        item.get('prerequisite_id', ''),
    ))

    active_gates.sort(key=lambda item: item['prerequisite_id'])
    conditional_constraints.sort(
        key=lambda item: (item['prerequisite_id'], item['effect']))
    delivery_risks.sort(key=lambda item: item['prerequisite_id'])
    gate_drivers = [driver['prerequisite_id'] for driver in drivers
                    if driver['type'] == 'gate']
    why = (', '.join(gate_drivers) if gate_drivers else
           'thin enablers' if any(driver['type'] == 'readiness_mean'
                                  for driver in drivers) else '')
    return {
        'status': status,
        'why': why,
        'active_gates': active_gates,
        'conditional_constraints': conditional_constraints,
        'delivery_risks': delivery_risks,
        'status_reason': {
            'status': status,
            'status_precedence': list(mapping['status_precedence']),
            'drivers': drivers,
        },
    }

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
# Ready means enablers at least Established, so the threshold IS the Established edge
# rather than a constant that happens to equal it. It was a separate literal, and when
# the bands were recut it stayed at 2.6 while the edge moved to 2.5 — leaving a column
# able to read 'Partial, thin enablers' with enablers the instrument calls Established.
READINESS_THRESHOLD = next(lo for lo, hi, n in BANDS if n == 'Established')


def _definition_contract_error(indicator_id, row, model_spec):
    """Return why a ratified observation is not bound to its definition, if any."""
    catalog = model_spec.get('indicator_definitions')
    entries = catalog.get('entries') if isinstance(catalog, dict) else None
    if entries is None:
        return 'missing ratified definition catalog'
    definition = entries.get(indicator_id) if isinstance(entries, dict) else None
    metadata = row.get('definition_metadata') if isinstance(row, dict) else None
    if not isinstance(definition, dict) or not isinstance(metadata, dict):
        return 'missing ratified definition metadata'
    encoded = json.dumps(
        definition, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode('utf-8')
    measure = definition.get('measure')
    policy = definition.get('source_policy')
    scoring = definition.get('scoring')
    model_indicators = model_spec.get('indicators')
    indicator = next((item for item in (
                          model_indicators if isinstance(model_indicators, list) else [])
                      if isinstance(item, dict)
                      and item.get('id') == indicator_id), None)
    expected = {
        'definition_version': definition.get('definition_version'),
        'definition_sha256': hashlib.sha256(encoded).hexdigest(),
        'unit': measure.get('unit') if isinstance(measure, dict) else None,
        'population_scope': (measure.get('population_scope')
                             if isinstance(measure, dict) else None),
        'reference_period_rule': (measure.get('reference_period')
                                  if isinstance(measure, dict) else None),
        'transform': measure.get('transform') if isinstance(measure, dict) else None,
    }
    if any(metadata.get(field) != value for field, value in expected.items()):
        return 'definition metadata differs from the ratified catalog'
    if metadata.get('definition_match') is not True:
        return 'definition match was not affirmed'
    if (not isinstance(policy, dict)
            or not isinstance(policy.get('allowed_tiers'), list)
            or not policy['allowed_tiers']
            or policy.get('minimum_confirmation')
            != 'One load-bearing source plus construct review'
            or not isinstance(scoring, dict)
            or scoring.get('missing_rule') != 'DATA GAP'
            or scoring.get('mismatch_rule') != 'HOLD'):
        return 'ratified definition policy is not executable'
    if row.get('cls') != 'Gap' and row.get('tier') not in policy['allowed_tiers']:
        return 'source tier is not allowed by the ratified definition'
    expected_method = (indicator.get('method')
                       if isinstance(indicator, dict) else None)
    expected_direction = (indicator.get('direction')
                          if isinstance(indicator, dict) else None)
    expected_thresholds = (indicator.get('thresholds')
                           if isinstance(indicator, dict) else None)
    if (not isinstance(scoring, dict)
            or scoring.get('method') != expected_method
            or scoring.get('direction') != expected_direction
            or (expected_method == 'threshold'
                and scoring.get('cuts') != expected_thresholds)
            or (expected_method == 'ladder' and 'cuts' in scoring)):
        return 'definition scoring does not match the runtime model'
    if (expected_method == 'threshold' and row.get('level') is not None
            and row.get('cls') not in ('Measured', 'Gap')):
        return 'threshold score requires a Measured observation'
    if expected_method == 'ladder' and row.get('cls') == 'Measured':
        return 'ladder observation cannot be Measured'
    if any(not isinstance(metadata.get(field), str)
           or not metadata[field].strip()
           for field in ('geography', 'observation_period', 'edition')):
        return 'definition metadata lacks observation identity'
    if type(metadata.get('proxy')) is not bool:
        return 'definition metadata proxy flag is not boolean'
    proxy_reason = metadata.get('proxy_justification')
    if (metadata['proxy']
            and (not isinstance(proxy_reason, str)
                 or len(' '.join(proxy_reason.split()).strip(' .')) < 8)):
        return 'proxy observation lacks a specific justification'
    source_digest = metadata.get('source_record_sha256')
    if (not isinstance(source_digest, str) or len(source_digest) != 64
            or any(character not in '0123456789abcdef'
                   for character in source_digest)):
        return 'definition metadata source record digest is invalid'
    review_digest = metadata.get('construct_review_sha256')
    if (not isinstance(review_digest, str) or len(review_digest) != 64
            or any(character not in '0123456789abcdef'
                   for character in review_digest)):
        return 'definition metadata construct review digest is invalid'
    for field in ('numerator', 'denominator'):
        contract_value = measure.get(field) if isinstance(measure, dict) else None
        actual_value = metadata.get(field)
        if contract_value == 'not_applicable':
            if actual_value != 'not_applicable':
                return f'definition metadata {field} must be not_applicable'
        elif not ((isinstance(actual_value, str) and actual_value.strip())
                  or (type(actual_value) in (int, float)
                      and actual_value == actual_value
                      and actual_value not in (float('inf'), float('-inf')))):
            return f'definition metadata lacks an actual {field}'
    preferred = policy.get('preferred_series') if isinstance(policy, dict) else []
    source_series = metadata.get('source_series')
    if not isinstance(source_series, str) or not source_series.strip():
        return 'definition metadata lacks a source series'
    fallback = metadata.get('fallback_justification')
    if (preferred and source_series not in preferred
            and (not isinstance(fallback, str)
                 or len(' '.join(fallback.split()).strip(' .')) < 8)):
        return 'non-preferred source has no fallback justification'
    calibration_refs = model_spec.get('indicator_calibration_refs')
    expected_calibration = (calibration_refs.get(indicator_id)
                            if isinstance(calibration_refs, dict) else None)
    if expected_method == 'threshold' and expected_calibration is None:
        return 'threshold row has no ratified calibration reference'
    if expected_calibration is not None:
        if metadata.get('calibration_ref') != expected_calibration:
            return 'calibration reference differs from the ratified model'
    elif 'calibration_ref' in metadata:
        return 'ladder row names a threshold calibration'
    if row.get('cls') == 'Measured':
        value = row.get('value')
        inputs = metadata.get('transform_inputs')
        transform = measure.get('transform') if isinstance(measure, dict) else None
        if (type(value) not in (int, float) or not math.isfinite(value)
                or not isinstance(inputs, dict)):
            return 'Measured observation lacks numeric transform inputs'
        try:
            if transform == 'identity' and set(inputs) == {'source_value'}:
                expected_value = inputs['source_value']
            elif transform == 'raw / 100' and set(inputs) == {'source_value'}:
                expected_value = inputs['source_value'] / 100
            elif (transform == 'monthly_price / (annual_GNI_per_capita / 12) * 100'
                  and set(inputs) == {'monthly_price', 'annual_gni_per_capita'}
                  and inputs['annual_gni_per_capita'] != 0):
                expected_value = (inputs['monthly_price']
                                  / (inputs['annual_gni_per_capita'] / 12) * 100)
            elif (transform == 'max(male_rate - female_rate, 0)'
                  and set(inputs) == {'male_rate', 'female_rate'}):
                expected_value = max(
                    inputs['male_rate'] - inputs['female_rate'], 0)
            else:
                return 'Measured observation uses an unsupported transform input contract'
        except (TypeError, ZeroDivisionError):
            return 'Measured observation transform inputs are not numeric'
        if (type(expected_value) not in (int, float)
                or not math.isfinite(expected_value)
                or not math.isclose(
                    value, expected_value, rel_tol=1e-9, abs_tol=1e-9)):
            return 'Measured value does not equal the ratified transform result'
    return None


def run(country, D, refyear=2026, model_spec=None, intervention_profiles=None,
        project_unratified_model=False):
    """Score one assessment.

    ``project_unratified_model`` exists only for authenticated historical replay.  Normal
    callers retain the legacy draft behavior; the release gate opts in when it verifies a
    tagged pre-ratification model and must reproduce that model's exact scoring catalog.
    """
    if type(project_unratified_model) is not bool:
        raise ValueError('project_unratified_model must be boolean')
    if project_unratified_model and not isinstance(model_spec, dict):
        raise ValueError(
            'project_unratified_model requires an explicit model_spec')
    active_model = MODEL
    active_pillars = ['A1','C1','C2','C3','C4','E1','O1']
    active_layers = ['Foundation','Enablers','Transformation','Outcomes']
    active_use_cases = ['ADV','SMF','MKT','SCM','FIN','AGI']
    active_bands = BANDS
    active_band_levels = BAND_LEVEL
    active_readiness_threshold = READINESS_THRESHOLD
    active_leapfrog_threshold = 1.5
    active_staleness_years = 3
    active_assessment_year = refyear
    if (isinstance(model_spec, dict)
            and (model_spec.get('ratified') is True
                 or project_unratified_model)):
        projection = _ratified_engine_projection(model_spec)
        active_model = projection['model']
        active_pillars = projection['pillars']
        active_layers = projection['layers']
        active_use_cases = projection['use_cases']
        active_bands = projection['bands']
        active_band_levels = projection['band_levels']
        active_assessment_year = projection['assessment_year']
        active_readiness_threshold = projection['readiness_threshold']
        active_leapfrog_threshold = projection['leapfrog_threshold']
        active_staleness_years = projection['staleness_years']

    mapping = _ratified_prerequisite_mapping(
        model_spec, active_use_cases,
        [i for i, m in active_model.items() if m['prereq']])
    if mapping is not None:
        if intervention_profiles is None:
            intervention_profiles = {}
        if not isinstance(intervention_profiles, dict):
            raise ValueError('intervention_profiles must be a use-case keyed object')
        if any(use_case_id not in active_use_cases
               for use_case_id in intervention_profiles):
            raise ValueError('intervention_profiles names an unknown use case')
        for use_case_id, profile in intervention_profiles.items():
            if not isinstance(profile, dict):
                raise ValueError(
                    f'intervention profile for {use_case_id} must be an object')
            if (set(profile) - _INTERVENTION_PROFILE_FIELDS
                    or any(type(value) is not bool for value in profile.values())):
                raise ValueError(
                    f'intervention profile for {use_case_id} has invalid facts')
        edges_by_use_case = {
            uc: [edge for edge in mapping['edges'] if edge['use_case_id'] == uc]
            for uc in active_use_cases
        }

    def active_band(value):
        for lo, hi, name in active_bands:
            if lo <= value < hi:
                return name
        return '—'

    out=dict(country=country, indicators={}, pillars={}, layers={}, prereq={}, matrix={})
    for i,m in active_model.items():
        r=dict(D[i])
        if mapping is not None and not r.get('cls'):
            r['cls'] = evidence_class(r)
        if isinstance(model_spec, dict) and model_spec.get('ratified') is True:
            contract_error = _definition_contract_error(i, r, model_spec)
            if contract_error:
                raise ValueError(
                    f'invalid ratified observation {i}: {contract_error}')
        r['level'] = (None if mapping is not None and r['cls'] in ('', 'Gap')
                      else effective_level(r, m))
        stale = bool(r['year'] and r['cls']!='Gap'
                     and r['year']
                     < active_assessment_year-active_staleness_years)
        out['indicators'][i]=dict(r, stale=stale, **{k:m[k] for k in ('name','pillar','layer','uc','prereq','kind')})
    for P in active_pillars:
        rows=[out['indicators'][i] for i in active_model
              if active_model[i]['pillar']==P]
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
        bnd = active_band(mean) if mean else 'Not rated'
        # Ruling 13.1: the signed distance from the level the band is named for. Zero means
        # the pillar sits squarely at that level; plus or minus 0.5 means it is on the edge
        # of the next one. Four of fourteen pillar bands in the worked examples turned on a
        # margin under 0.10, which the band alone never showed.
        margin = (r2(mean - active_band_levels[bnd])
                  if mean and bnd in active_band_levels else None)
        out['pillars'][P]=dict(n=len(rows), rated=rated, held=held, mean=mean,
                               band=bnd, margin=margin,
                               weak=weak, comp=comp, stale=sum(1 for r in rows if r['stale']))
    for L in active_layers:
        lv=[out['indicators'][i]['level'] for i in active_model
            if active_model[i]['layer']==L
            and out['indicators'][i]['level'] is not None]
        out['layers'][L]=r2(sum(lv)/len(lv)) if lv else None
    F,T=out['layers']['Foundation'],out['layers']['Transformation']
    out['leapfrog']=dict(
        gap=(r2(F-T) if F and T else None),
        flag=(F and T and abs(F-T)>active_leapfrog_threshold),
        reading=('Transformation running ahead of foundations — leapfrog fragility'
                 if F and T and T-F>active_leapfrog_threshold
                 else 'Foundations ahead of ecosystem — unrealized potential'
                 if F and T and F-T>active_leapfrog_threshold
                 else 'No structural flag'))
    for i,m in active_model.items():
        if not m['prereq']: continue
        r=out['indicators'][i]
        if r['cls']=='Gap' or r['level'] is None: st='Unverified'  # a row with no level asserts nothing: unrated is NOT absent (matches the workbook formula and spec 7)
        elif r['level'] and r['level']>=3: st='Present'
        elif r['level']==2: st='Present (narrow)'
        else: st='Absent'
        out['prereq'][i]=dict(name=m['name'], kind=m['prereq'], status=st)
    uni_block=[i for i,p in out['prereq'].items() if p['kind']=='UNIVERSAL' and p['status']=='Absent']
    uni_narrow=[i for i,p in out['prereq'].items() if p['kind']=='UNIVERSAL' and p['status']=='Present (narrow)']  # narrow presence caps every column at Partial
    uni_unver=[i for i,p in out['prereq'].items() if p['kind']=='UNIVERSAL' and p['status']=='Unverified']  # spec 7: an unevidenced prerequisite 'cannot silently pass or fail'
    for uc in active_use_cases:
        # Ruling 13.4: 7.12 follows the USE OF PERSONAL OR FARM-LEVEL DATA rather than
        # the agricultural-intelligence column alone, so the binding is read from the
        # model like every other per-use-case prerequisite and there is no longer a
        # special case for it. WHICH columns use such data is a mapping question and
        # belongs to decision 13.3, which is not ratified; the set carried here is a
        # proposal recorded in that decision's mapping table.
        pres=[(i,out['prereq'][i]['status']) for i in out['prereq']
              if out['prereq'][i]['kind'].startswith('UC:')
              and uc in out['prereq'][i]['kind'].split(':',1)[1].split(',')]
        bearing=[i for i in active_model
                 if ((uc in active_model[i].get('use_cases', active_model[i]['uc'])
                      or 'ALL' in active_model[i].get('tags', active_model[i]['uc']))
                 and out['indicators'][i]['level'] is not None)]
        # The bearing set mixes three roles: A1 rows measure the SEVERITY OF THE PROBLEM, O1 rows
        # measure ACHIEVED OUTCOMES, and the rest measure ENABLING READINESS. Averaging all three
        # into one readiness number is an open design question (spec 13.12), so the split and the
        # enabler-only mean are published beside the mean rather than silently folded into it.
        # Ruling 13.12: the three roles are separated. A1 rows measure the SEVERITY OF THE
        # PROBLEM, O1 rows measure ACHIEVED OUTCOMES, and only the rest measure ENABLING
        # READINESS. Averaging all three produced the inversion the specification records:
        # a country with a worse agricultural problem read as less digitally ready. Only
        # the readiness mean decides the column; need and outcome are reported beside it
        # and never scored into it.
        role={'A1':'need','O1':'outcome'}
        basis={'need':0,'outcome':0,'enabler':0}
        for i in bearing:
            basis[role.get(active_model[i]['pillar'],'enabler')]+=1
        def _rolemean(want):
            v=[out['indicators'][i]['level'] for i in bearing
               if role.get(active_model[i]['pillar'],'enabler')==want]
            return r2(sum(v)/len(v)) if v else None
        mean_readiness=_rolemean('enabler')
        mean_need=_rolemean('need')
        mean_outcome=_rolemean('outcome')
        if mapping is None:
            if uni_block: st='Blocked'; why='Universal: '+', '.join(uni_block)
            elif any(s=='Absent' for _,s in pres): st='Blocked'; why=', '.join(i for i,s in pres if s=='Absent')
            elif uni_unver: st='Unverified'; why='universal unverified: '+', '.join(uni_unver)
            elif any(s=='Unverified' for _,s in pres): st='Unverified'; why=', '.join(i for i,s in pres if s=='Unverified')
            elif any(s=='Present (narrow)' for _,s in pres) or (mean_readiness and mean_readiness<active_readiness_threshold): st='Partial'; why=', '.join(i for i,s in pres if 'narrow' in s) or 'thin enablers'
            elif uni_narrow: st='Partial'; why='universal narrow: '+', '.join(uni_narrow)
            else: st='Ready'; why=''
            out['matrix'][uc]=dict(status=st, why=why, prereqs=pres, n_bearing=len(bearing),
                                   basis=basis, mean_readiness=mean_readiness,
                                   mean_need=mean_need, mean_outcome=mean_outcome,
                                   mean_driven=(st=='Partial' and why=='thin enablers'))
        else:
            profile = intervention_profiles.get(uc, {})
            mapped = _mapped_readiness(
                mapping, edges_by_use_case[uc], out['prereq'],
                mean_readiness, active_readiness_threshold, profile)
            mapped_prereqs = [
                (gate['prerequisite_id'], gate['prerequisite_status'])
                for gate in mapped['active_gates']
            ]
            out['matrix'][uc]=dict(
                n_bearing=len(bearing), basis=basis,
                mean_readiness=mean_readiness, mean_need=mean_need,
                mean_outcome=mean_outcome,
                prereqs=mapped_prereqs,
                mean_driven=any(
                    driver['type'] == 'readiness_mean'
                    for driver in mapped['status_reason']['drivers']),
                **mapped)
    rated=[(i,out['indicators'][i]) for i in active_model
           if out['indicators'][i]['level'] is not None]
    out['constraints']=[dict(id=i,name=r['name'],level=r['level'],pillar=r['pillar'],prereq=bool(r['prereq'])) for i,r in sorted(rated,key=lambda x:(x[1]['level'],x[0]))[:12]]
    out['kpi']=[dict(id=i,name=r['name'],value=r['value'],year=r['year'],src=r['src']) for i,r in out['indicators'].items() if r['cls']=='Measured' and r['pillar'] in ('A1','O1')]
    # The section states "Judged rows and recorded gaps". It previously carried a Judged row only
    # when that row was a prerequisite, so a country with a non-prerequisite Judged row published
    # a list shorter than its own caption promised (defect 42).
    out['verify']=[dict(id=i,name=r['name'],cls=r['cls']) for i,r in out['indicators'].items() if r['cls'] in ('Gap','Judged')]
    out['refresh']=[dict(id=i,name=r['name'],year=r['year']) for i,r in out['indicators'].items() if r['stale']]
    out['counts']={c:sum(1 for i in active_model
                         if out['indicators'][i]['cls']==c)
                   for c in ('Measured','Documented','Judged','Gap')}
    out['held']=sum(1 for i in active_model
                    if out['indicators'][i]['level'] is None
                    and out['indicators'][i]['cls']!='Gap')
    out['rated']=sum(1 for i in active_model
                     if out['indicators'][i]['level'] is not None)
    if mapping is not None:
        out['model_version'] = model_spec['version']
        out['model_revision'] = model_spec['revision']
        out['prerequisite_mapping_revision'] = mapping['revision']
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
    res = run(country, rows, model_spec=_canonical_model_root())
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
