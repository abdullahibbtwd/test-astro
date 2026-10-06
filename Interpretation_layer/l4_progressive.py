"""Deterministic progressive reading plans and one-section L4 generation (ONB_01)."""
from __future__ import annotations
from dataclasses import asdict
from l4_routing import route, section_houses
from l4_sections import MOVEMENT, SECTION_ORDER, RoutedPrinciple
from l4_render import section_title
from l4_generate import SECTION_SCHEMA, DEFAULT_SECTION_SYNTHESIS_MAX_TOKENS
from l4_prompts import build_progressive_finalize_prompt
from l4_validate import validate, SCHEMA_VERSION, PRECISION_TIER

PROMPT_VERSION = 'l4p.v2'
CONTEXT_CHARS = 18000  # Conservative ~6k-token bound for Turkish prose.


def prepare(chart: dict, kept: list[dict], *, chart_key: str = '', routing=None) -> dict:
    """The caller supplies the app identity; this module never invents a chart key."""
    routing = routing or route(kept, chart)
    sections = routing.non_empty()
    houses = section_houses(chart)
    primary = {}
    records = {record['principle_id']: record for record in kept}
    for key, principles in sections.items():
        for principle in principles:
            if any(' occupancy: ' not in reason and ' rulership: ' not in reason
                   for reason in principle.reasons):
                primary.setdefault(principle.principle_id, []).append(key)
    owners = {}
    for pid in {p.principle_id for rows in sections.values() for p in rows}:
        candidates = primary.get(pid)
        if not candidates:
            raise ValueError('Routed principle has no primary ownership reason')
        factor = (records[pid].get('about') or {}).get('factor_type')
        movement_two = [key for key in candidates if MOVEMENT[key] == 2]
        house_fact = factor in {'planet_in_house', 'planet_in_sign_and_house', 'house_ruler', 'house_lord_relative'} or (
            factor in {'house_domain', 'node'} and bool(movement_two))
        owners[pid] = movement_two[0] if house_fact and movement_two else next(
            (key for key in candidates if key not in {'sun_house', 'moon_house'}), candidates[0])
    titles = {key: {lang: section_title(key, lang, houses.get(key)) for lang in ('tr', 'en')}
              for key in sections}
    routed_ids = {key: sorted(p.principle_id for p in rows) for key, rows in sections.items()}
    own, elsewhere = {}, {}
    for key, ids in routed_ids.items():
        own[key] = [pid for pid in ids if key in {'sun_house', 'moon_house'} or owners[pid] == key]
        elsewhere[key] = [{'id': pid, 'owner': owners[pid], 'owner_title_tr': titles[owners[pid]]['tr']}
                          for pid in ids if pid not in own[key]]
    return {'chart_key': chart_key, 'order': list(sections),
            'movement': {key: MOVEMENT[key] for key in sections},
            'house': {key: houses.get(key) for key in sections}, 'titles': titles,
            'routed_ids': routed_ids, 'own': own, 'elsewhere': elsewhere,
            'owners': dict(sorted(owners.items())), 'low_salience_ids': sorted(routing.low_salience_ids()),
            'routed': {key: [asdict(p) for p in rows] for key, rows in sections.items()}}


def routed_for(plan: dict, key: str) -> list[RoutedPrinciple]:
    return [RoutedPrinciple(**row) for row in plan['routed'][key]]


def written_context(plan: dict, key: str, written: list[dict]) -> list[dict]:
    preceding = plan['order'][:plan['order'].index(key)]
    available = {s['key']: s for s in written if s.get('key') in preceding and s.get('text_tr')}
    keys = []
    if 'core_identity' in available:
        keys.append('core_identity')
    nearest = next((k for k in reversed(preceding) if k in available), None)
    if nearest and nearest not in keys:
        keys.append(nearest)
    budget = CONTEXT_CHARS
    result = []
    for context_key in keys:
        text = available[context_key]['text_tr'][:budget]
        budget -= len(text)
        if text:
            result.append({'key': context_key, 'title': plan['titles'][context_key]['tr'], 'text_tr': text})
    return result


def section_output(plan: dict, key: str, **texts) -> dict:
    return {'schema_version': SCHEMA_VERSION, 'precision_tier': PRECISION_TIER,
            'sections': [{'key': key, 'movement': plan['movement'][key], 'house': plan['house'][key],
                          'principle_ids': plan['routed_ids'][key], **texts}]}


def usage_delta(gen, before):
    return {key: value - before.get(key, 0) for key, value in getattr(gen, 'usage', {}).items()}


def generate_section(plan, key, chart, routed, written, gen, *, on_stage=lambda stage: None):
    if key not in plan['order']:
        raise ValueError('Section not in reading plan')
    usage = {}
    on_stage('reading')
    before = dict(getattr(gen, 'usage', {}))
    draft = getattr(gen, 'progressive_section', gen.section)(key, routed, chart)
    if draft.key != key or not draft.text_tr.strip():
        raise ValueError('Invalid section draft')
    usage['draft'] = usage_delta(gen, before)
    context = written_context(plan, key, written)
    by_id = {p.principle_id: p for p in routed}
    elsewhere = [{'principle_id': row['id'], 'rule': (by_id[row['id']].rule or '')[:160],
                  'owner_title': row['owner_title_tr']} for row in plan['elsewhere'][key]]
    system, user = build_progressive_finalize_prompt(
        key, draft.text_tr, [{'title': r['title'], 'text_tr': r['text_tr']} for r in context],
        plan['own'][key], elsewhere, chart, plan['low_salience_ids'])
    on_stage('synthesis')
    before = dict(getattr(gen, 'usage', {}))
    result = gen._call_json(gen.synthesis_model, system, user, temperature=gen.synthesis_temperature,
                            max_tokens=DEFAULT_SECTION_SYNTHESIS_MAX_TOKENS,
                            label=f'progressive_finalize[{key}]', schema=SECTION_SCHEMA)
    usage['finalize'] = usage_delta(gen, before)
    if result.get('key') != key or not isinstance(result.get('text_tr'), str):
        raise ValueError('Invalid finalized section')
    on_stage('validate')
    before = dict(getattr(gen, 'usage', {}))
    text = gen._detox_text(key, result['text_tr'], 'tr')
    usage['detox'] = usage_delta(gen, before)
    errors = validate(section_output(plan, key, text_tr=text),
                      {key: set(plan['routed_ids'][key])}, langs=('tr',))
    if errors:
        raise ValueError('Progressive section failed validation')
    return {'key': key, 'movement': plan['movement'][key], 'house': plan['house'][key],
            'text_tr': text, 'principle_ids': plan['routed_ids'][key], 'draft_tr': draft.text_tr,
            'usage': usage, 'prompt_version': PROMPT_VERSION, 'context_keys': [r['key'] for r in context]}


def translate_section(key, text_tr, gen) -> str:
    if not text_tr.strip():
        raise ValueError('Translation requires a finalized Turkish section')
    translated = gen._detox_text(key, gen.translate(key, text_tr), 'en')
    # Grounding belongs to the immutable TR source; caller revalidates its real ids.
    output = {'schema_version': SCHEMA_VERSION, 'precision_tier': PRECISION_TIER,
              'sections': [{'key': key, 'movement': MOVEMENT[key], 'text_en': translated,
                            'principle_ids': ['source-section']}]}
    if validate(output, {key: {'source-section'}}, langs=('en',)):
        raise ValueError('Progressive translation failed validation')
    return translated
