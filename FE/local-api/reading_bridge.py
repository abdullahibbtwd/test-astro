from pathlib import Path
import sys
import json
import contextlib
from datetime import datetime, timezone
ROOT = Path(__file__).resolve().parents[2]
for folder in ('', 'd_layer', 'principles_grounding', 'Interpretation_layer'):
    sys.path.insert(0, str(ROOT / folder))
from budget import install_guard

def generate(data):
    import llm_client
    import os
    if os.environ.get('ASTRO_ALLOW_PAID') != '1':
        raise RuntimeError('Paid generation is disabled')
    budget = install_guard(llm_client, str(ROOT / 'FE/.local-data/ai-budget.sqlite'))
    from ground import ground
    from l4_interpret import interpret
    import l4_render
    records = json.loads((ROOT / 'principles_grounding/all_principles.grounded.json').read_text(encoding='utf-8'))
    grounded = ground(records, data['chart'], reading='natal', house_policy='placidus')
    output, report, errors = interpret(data['chart'], grounded.kept, max_workers=2)
    if errors:
        raise RuntimeError('Reading failed grounding/structure validation')
    generated = datetime.now(timezone.utc).isoformat()
    readings = {}
    for lang in ('tr', 'en'):
        readings[lang] = {'profile_id': data['profile_id'], 'chart_key': data['chart_key'], 'lang': lang,
            'generated_at': generated, 'title': l4_render._DOC_TITLE[lang],
            'parts': [{'movement': m, 'title': l4_render.MOVEMENT_TITLES[lang][m]} for m in (1,2)],
            'sections': [{'key': s['key'], 'movement': s['movement'], 'house': s.get('house'),
                'title': l4_render.section_title(s['key'], lang, s.get('house') or 0), 'text': s['text_'+lang]}
                for s in output['sections'] if s.get('text_'+lang, '').strip()]}
    return {'readings': readings, 'budget_reserved_or_spent_usd': budget.total()}

if __name__ == '__main__':
    try:
        data = json.load(sys.stdin)
        with contextlib.redirect_stdout(sys.stderr):
            result = generate(data)
        print(json.dumps(result, ensure_ascii=True))
    except Exception as error:
        # Category only: raw exceptions can contain provider responses or personal data.
        print(json.dumps({'error': type(error).__name__}))
        sys.exit(1)
