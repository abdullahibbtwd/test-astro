"""Private progressive section bridge; public API filters internal provenance."""
import contextlib
import json
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / 'astrologist')]
import _paths
from profile_dossier import Dossier, DEFAULT_ROOT
from l4_progressive import generate_section, translate_section, routed_for, section_output
from l4_validate import validate
import l4_render


def run(data, *, dossier=None, generator=None):
    def stage(name):
        print('ONB_STAGE:' + name, file=sys.stderr, flush=True)
    dossier = dossier or Dossier(data.get('dossier_root', DEFAULT_ROOT))
    key, op = data['chart_key'], data['op']
    if op in ('retain', 'release'):
        return {'removed': getattr(dossier, op)(key, data['reference_id'])}
    if op == 'prepare':
        products = dossier.build_a0(key, data['chart'], data.get('birth'))
        return {'plan': products['natal_plan'], 'titles': l4_render._DOC_TITLE,
                'parts': {lang: [{'movement': m, 'title': l4_render.MOVEMENT_TITLES[lang][m]} for m in (1, 2)] for lang in ('tr', 'en')}}
    if op == 'export':
        return {'manifest': dossier.manifest(key), 'chart': dossier.get(key, 'chart'),
                'grounded_principle_ids': [p['principle_id'] for p in dossier.get(key, 'natal_grounding')['principles']]}
    plan = dossier.get(key, 'natal_plan')
    section = data['section_key']
    if section not in plan['order']:
        raise ValueError('Unknown section')
    existing = dossier.readings(key).get(section)
    if op == 'publish':
        value = data['section']
        if value.get('key') != section:
            raise ValueError('Section mismatch')
        return dossier.publish_section(key, value)
    if op not in ('section', 'translate'):
        raise ValueError('Unknown operation')
    if existing and existing.get('text_tr') and (op == 'section' or existing.get('text_en')):
        return existing
    if generator is None:
        if os.environ.get('ASTRO_ALLOW_PAID') != '1':
            raise RuntimeError('Paid generation is disabled')
        import llm_client
        from budget import install_guard
        install_guard(llm_client, str(Path(os.environ.get('DATA_DIR', str(ROOT / 'backend' / '.local-data'))) / 'ai-budget.sqlite'))
        from l4_generate import LLMGenerator
        generator = LLMGenerator()
    if op == 'section':
        value = generate_section(plan, section, dossier.get(key, 'chart'), routed_for(plan, section),
                                 list(dossier.readings(key).values()), generator, on_stage=stage)
    else:
        if not existing or not existing.get('text_tr'):
            raise ValueError('Translation requires a ready source')
        stage('translation')
        value = {**existing, 'text_en': translate_section(section, existing['text_tr'], generator)}
        if validate(section_output(plan, section, text_en=value['text_en']),
                    {section: set(plan['routed_ids'][section])}, langs=('en',)):
            raise ValueError('Translation validation failed')
    return dossier.publish_section(key, value)


if __name__ == '__main__':
    try:
        data = json.load(sys.stdin)
        with contextlib.redirect_stdout(sys.stderr):
            result = run(data)
        print(json.dumps(result, ensure_ascii=True))
    except Exception as error:
        print(json.dumps({'error': type(error).__name__}))
        sys.exit(1)
