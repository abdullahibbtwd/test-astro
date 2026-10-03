"""Map the approved grounding plan to immediate place facts, without generating prose."""
def place_reports(data):
    from run_acg import build_chart_products, Stages
    import acg_goals as ag
    import acg_locate as al
    import ground_acg as ga
    import ar_routing
    from ar_sections import FOOTER, CARDS
    from ar_generate import _card_output
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    products = build_chart_products(data['chart'], str(root / 'FE/.local-data/map-products'), stages=Stages(), with_goal_scan=False)
    place = data['place']
    location = {**place, 'name_tr': place['name'], 'source': 'gazetteer' if place['place_id'] else 'manual'}
    loc, relocated = al.build_locate(products['acg'], data['chart'], location, parans=products['parans'])
    ok, _ = ga.corpus_ok()
    payload, _ = ga.ground_acg(data['chart'], relocated, loc,
        ga.load_json(ga.ACG_CORPUS_PATH) if ok else None, ga.load_json(ga.MAIN_CORPUS_PATH),
        acg=products['acg'], affinity=ag.load_affinity(), parans=products['parans'])
    if payload['status'] != 'ok':
        raise RuntimeError('Place grounding unavailable')
    plan = ar_routing.build_plan(payload, focus_goal=data.get('focus_goal'))
    cards = next(s['cards'] for s in plan['sections'] if s['key'] == 'suitability')
    reports = {}
    for lang in ('en', 'tr'):
        reports[lang] = {
            'place': place, 'status': loc['status'],
            'relocation': {'status': loc['relocation']['status'], **({'absence': {'reason': loc['relocation']['absence']['reason']}} if loc['relocation'].get('absence') else {})},
            'focus_goal': data.get('focus_goal'),
            'lines_display': [{'body': l['body'], 'angle': l['angle'], 'planet_label': l['planet_' + lang],
                'angle_label': l['angle_label_' + lang], 'distance_km_rounded': l['distance_km_rounded'],
                'tier': l['tier'], 'tier_label': l['tier_label_' + lang], 'read_in_prose': l['read_in_prose']} for l in plan['lines_display']],
            'parans_display': [{'id': p['id'], 'bodies': p.get('bodies', p.get('planets', [x.lower() for x in p['planets_en']])),
                'planet_labels': p['planets_' + lang], 'north_south': p['north_south'],
                'distance_km_rounded': p['distance_km_rounded'], 'label': p['label_' + lang]} for p in plan['parans_display']],
            'goal_scores': {g: {'band': s['band'], 'label': s['band_label_' + lang]} for g, s in plan['goal_scores'].items()},
            'cards': [{'card': c['card'] if c['card'] in CARDS else 'focus', 'goal': c['goal'],
                'title': c['title_' + lang], 'band': c['band'], 'band_label': c['band_label_' + lang],
                'text': _card_output(c, {}, {})['text_' + lang] if c['template'] else None} for c in cards],
            'reading': {'status': 'absent', 'absence': {'reason': 'not_generated'}}, 'footer': FOOTER[lang]}
    return {'reports': reports}
