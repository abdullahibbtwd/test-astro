import os
"""No-model adapter for the approved astrocartography geometry and city scan."""
import contextlib
import json
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
ENGINE = Path(__file__).resolve().parents[1] / 'engine'
ROOT = ENGINE  # engines + PA live under backend/engine
for folder in ('', 'd_layer', 'Astrocartography'):
    sys.path.insert(0, str(ROOT / folder))


def calculate(data):
    import llm_client
    def no_models(*args, **kwargs):
        raise RuntimeError('Map facts must not call models')
    llm_client.complete = no_models
    if data.get('mode') == 'place':
        import run_acg  # initializes the approved grounding and reading module paths
        from map_place import place_reports
        return place_reports(data)
    if data.get('mode') == 'recommend':
        from run_acg import build_chart_products, Stages
        import acg_goals as ag
        import acg_geodata as geo
        import acg_recommend as rec
        import acg_destinations as dst
        goal, scope = data['request']['goal'], data['request'].get('scope') or 'world'
        if scope != 'world' and not geo.country(scope):
            return {'invalid_scope': True}
        products = build_chart_products(data['chart'], str(Path(os.environ.get('DATA_DIR', str(REPO / 'backend' / '.local-data'))) / 'map-products'), stages=Stages())
        rec.set_parans(products['parans'])
        aff = ag.load_affinity()
        f = data['request'].get('filters') or {}
        filters = dst.resolve_filters('love' if goal == 'overall' else goal,
            regions=f.get('regions'), city_size=f.get('city_size'), max_distance_km=f.get('max_distance_km'),
            home_latlon=data['home'], climate=f.get('climate'), purpose=f.get('purpose') or ('both' if goal == 'overall' else None))
        if goal == 'overall':
            import acg_overall
            import ar_overall
            raw = ar_overall.assemble(acg_overall.recommend_overall(products['acg'], aff, filters, scope), {}, {})
        else:
            import acg_line_first
            import ar_recommend
            ranking = acg_line_first.rank_line_first(goal, scope, products['acg'], products['goal_scan'], aff, filters)
            ar_recommend.template_texts(ranking)
            raw = ar_recommend.assemble(ranking, {}, {})
        return {'raw': raw}
    if data.get('mode') == 'area':
        from run_acg import build_chart_products, Stages
        import acg_goals as ag
        import acg_geodata as geo
        import acg_recommend as rec
        from ar_sections import FOOTER
        kind, code = data['kind'], data['code']
        meta = geo.country(code) if kind == 'country' else geo.region(code)
        if not meta:
            return {'missing': True}
        products = build_chart_products(data['chart'], str(Path(os.environ.get('DATA_DIR', str(REPO / 'backend' / '.local-data'))) / 'map-products'), stages=Stages())
        rec.set_parans(products['parans'])
        area = rec.area_view(kind, code, products['acg'], products['goal_scan'], ag.load_affinity())
        return {'area': area, 'regions': [r for r in geo.load_regions() if r['iso_a2'] == area.get('iso_a2')], 'footer': FOOTER}
    if data.get('mode') == 'heat':
        from run_acg import build_chart_products, Stages
        import acg_goals
        goal = data['goal']
        if goal not in acg_goals.GOAL_ORDER:
            raise ValueError('Unknown goal')
        products = build_chart_products(data['chart'], str(Path(os.environ.get('DATA_DIR', str(REPO / 'backend' / '.local-data'))) / 'map-products'), stages=Stages())
        if products['goal_scan'] is None:
            raise RuntimeError('Heat calculation unavailable')
        geo = acg_goals.heat_geojson(products['goal_scan'], goal)
        levels = {'strongly_supportive': 2, 'supportive': 1, 'mixed': 0, 'challenging': -1}
        return {'goal': goal, 'grid_step_deg': 0.5,
                'points': [f['geometry']['coordinates'] + [levels[f['properties']['band']]] for f in geo['features']],
                'cache_key': products['key']}
    import compute_acg
    import compute_parans
    import acg_locate
    acg = compute_acg.compute_acg(data['chart'])
    if acg['status'] != 'ok':
        raise ValueError('Map calculation unavailable')
    parans = compute_parans.compute_parans(acg)
    cities = acg_locate.load_gazetteer()
    scan = acg_locate.city_scan(acg, cities)
    lookup = {c['id']: c for c in cities}
    by_line = {}
    for key, values in scan['by_line'].items():
        by_line[key] = [{
            'place_id': v['city_id'], 'name': lookup[v['city_id']]['name'],
            'name_tr': lookup[v['city_id']]['name_tr'],
            'country_code': lookup[v['city_id']]['country_code'],
            'distance_km_rounded': '<10' if v['distance_km'] < 10 else round(v['distance_km'] / 10) * 10,
            'tier': acg_locate.tier_for(v['distance_km'])
        } for v in values]
    return {'lines': compute_acg.to_geojson(acg), 'parans': compute_parans.to_geojson(parans), 'by_line': by_line}


if __name__ == '__main__':
    try:
        data = json.load(sys.stdin)
        with contextlib.redirect_stdout(sys.stderr):
            result = calculate(data)
        print(json.dumps(result, ensure_ascii=True, separators=(',', ':')))
    except Exception as error:
        print(json.dumps({'error': type(error).__name__}))
        sys.exit(1)
