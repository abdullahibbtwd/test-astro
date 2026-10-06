"""Adapter for the approved relationship pipeline; no new interpretation rules."""
import contextlib
import json
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for folder in ('', 'd_layer', 'principles_grounding', 'synastry_reading', 'Interpretation_layer'):
    sys.path.insert(0, str(ROOT / folder))
from budget import install_guard


def generate(data):
    import llm_client
    context = data['context']
    reading_type = {'love': 'personal', 'work': 'professional'}[context['type']]
    dry = data.get('dry_run', False)
    if not dry and os.environ.get('ASTRO_ALLOW_PAID') != '1':
        raise RuntimeError('Paid generation disabled')
    if dry:
        def no_models(*args, **kwargs):
            raise RuntimeError('Dry-run must not call models')
        llm_client.complete = no_models
    budget = None if dry else install_guard(llm_client, str(ROOT / 'FE/.local-data/ai-budget.sqlite'))
    from ground_relationship import ground_relationship
    corpus = json.loads((ROOT / 'principles_grounding/combined_relationship_principles_tagged.json').read_text(encoding='utf-8'))
    for record in corpus:
        contexts = (record.get('synastry') or {}).get('contexts')
        if not isinstance(contexts, list) or not contexts or not set(contexts) <= {'universal', 'personal', 'professional'}:
            raise ValueError('Untagged relationship corpus')
    a, b = data['charts']
    payload = ground_relationship(corpus, a, b).payload()
    houses_valid = all((chart.get('meta') or {}).get('time_precision') == 'exact' for chart in (a, b))
    if dry:
        from s3_profiles import get_profile
        from s3_routing import route
        routing = route(payload, get_profile(reading_type), houses_valid=houses_valid)
        return {'context': context, 'counts': payload['counts'], 'reading_type': reading_type,
                'section_keys': list(routing.non_empty())}
    from read_relationship import read_relationship
    from s3_profiles import get_profile
    output, _, _, errors = read_relationship(payload, reading_type=reading_type,
        label_a=context['people'][0]['label'], label_b=context['people'][1]['label'],
        houses_valid=houses_valid, model=llm_client.DEFAULT_MODEL,
        synthesis_model=llm_client.DEFAULT_MODEL, statements_model=llm_client.DEFAULT_CHEAP_MODEL,
        translation_model=llm_client.DEFAULT_CHEAP_MODEL)
    if errors:
        raise RuntimeError('Relationship validation failed')
    profile = get_profile(reading_type)
    sections = {s['key']: s for s in output['sections']}
    readings = {}
    for lang in ('en', 'tr'):
        rendered = []
        for key in profile.section_order:
            section = sections.get(key)
            if not section or not (section.get('text_' + lang) or '').strip():
                raise RuntimeError('Incomplete relationship reading')
            rendered.append({'key': key, 'movement': profile.movement[key],
                             'title': profile.titles[key][lang], 'text': section['text_' + lang]})
        readings[lang] = {'title': profile.doc_title[lang], 'sections': rendered}
    return {'context': context, 'readings': readings, 'budget_reserved_or_spent_usd': budget.total()}


if __name__ == '__main__':
    try:
        data = json.load(sys.stdin)
        with contextlib.redirect_stdout(sys.stderr):
            result = generate(data)
        print(json.dumps(result, ensure_ascii=True))
    except Exception as error:
        print(json.dumps({'error': type(error).__name__}))
        sys.exit(1)
