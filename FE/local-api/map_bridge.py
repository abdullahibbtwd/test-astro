"""No-model adapter for the approved astrocartography geometry and city scan."""
import contextlib
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
for folder in ('', 'd_layer', 'Astrocartography'):
    sys.path.insert(0, str(ROOT / folder))


def calculate(data):
    import llm_client
    def no_models(*args, **kwargs):
        raise RuntimeError('Map facts must not call models')
    llm_client.complete = no_models
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
