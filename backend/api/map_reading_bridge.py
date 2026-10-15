"""Supervised, budget-guarded adapter for the existing validated map reading pipelines."""
import contextlib
import json
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import run_acg  # approved module search paths
from budget import install_guard


def generate(data):
    dry_run = data.get('dry_run') is True
    if not dry_run and os.environ.get('ASTRO_ALLOW_PAID') != '1':
        raise RuntimeError('Paid generation is disabled')
    import llm_client
    if dry_run:
        def no_models(*args, **kwargs):
            raise RuntimeError('Dry-run must not call models')
        llm_client.complete = no_models
    else:
        install_guard(llm_client, str(Path(os.environ.get('DATA_DIR', str(ROOT / 'backend' / '.local-data'))) / 'ai-budget.sqlite'))
    from ar_generate import DEFAULT_MODEL, DEFAULT_TRANSLATION_MODEL
    models = {'model': DEFAULT_MODEL, 'synthesis': DEFAULT_MODEL, 'translation': DEFAULT_TRANSLATION_MODEL}
    context, chart = data['context'], data['chart']
    kind, request = context['kind'], context['input']
    if kind == 'place':
        import ar_generate
        import ar_render
        import ar_routing
        import ground_acg as ga
        from map_place import prepare_place
        _, plan = prepare_place({'chart': chart, **request})
        if dry_run:
            return {'context': context, 'dry_run': True, 'sections': len(plan['sections'])}
        allowed = {r['principle_id'] for r in ga.load_json(ga.ACG_CORPUS_PATH)} | set(ar_routing.traced_ids(plan))
        reading, errors = ar_generate.generate(plan, run_acg.make_generator(models), allowed)
        if errors:
            raise RuntimeError('Map reading validation failed')
        values = {}
        for lang in ('en', 'tr'):
            doc = ar_render.reading_json(reading, plan, lang)
            sections = [{'key': s['key'], 'title': s['title'],
                         'paragraphs': [{'slot_id': p['slot_id'], 'text': p['text']} for p in s['paragraphs']]}
                        for s in doc['sections'] if 'paragraphs' in s]
            cards = next((s['cards'] for s in doc['sections'] if s['key'] == 'suitability'), [])
            values[lang] = {'reading': {'status': 'ready', 'sections': sections},
                            'card_texts': {c['goal']: c['text'] for c in cards}}
        return {'context': context, 'readings': values}
    import acg_goals as ag
    import acg_views as views
    import ar_recommend
    import ar_overall
    products = run_acg.build_chart_products(chart, str(Path(os.environ.get('DATA_DIR', str(ROOT / 'backend' / '.local-data'))) / 'map-products'), stages=run_acg.Stages())
    products['natal'] = chart
    saved = {}
    def write(name, obj, **kwargs):
        if name.endswith('.json'):
            saved[name] = obj
    common = dict(dry_run=dry_run, models=models, make_generator=run_acg.make_generator)
    args = (products['acg'], ag.load_affinity(), products, run_acg.Stages(), {}, write, lambda status: status)
    if kind == 'area':
        status = views.run_area(request['kind'], {request['kind']: request['code']}, *args, **common)
        if status != 'ok':
            raise RuntimeError('Area reading validation failed')
        result = saved[f"{request['kind']}_{request['code']}.json"]
        if dry_run:
            return {'context': context, 'dry_run': True, 'units': len(result['dry_run_units'])}
        return {'context': context, 'readings': {lang: {'overview': {'status': 'ready', 'text': result['place_overview'][lang]}} for lang in ('en', 'tr')}}
    payload = {**request['request'], 'birth': {}, 'home_latlon': request['home']}
    goal, scope = payload['goal'], payload.get('scope') or 'world'
    if goal == 'overall':
        status = ar_overall.run(payload, *args, **common, scope=scope)
    else:
        status = ar_recommend.run(payload, *args, **common, goal=goal, scope=scope)
    if status != 'ok':
        raise RuntimeError('Recommendation reading validation failed')
    result = saved[f'recommend_{goal}_{scope}.json']
    if dry_run:
        return {'context': context, 'dry_run': True, 'units': len(result['dry_run_units'])}
    return {'context': context, 'raw': result}


if __name__ == '__main__':
    try:
        data = json.load(sys.stdin)
        with contextlib.redirect_stdout(sys.stderr):
            result = generate(data)
        print(json.dumps(result, ensure_ascii=True, separators=(',', ':')))
    except Exception as error:
        print(json.dumps({'error': type(error).__name__}))
        sys.exit(1)
