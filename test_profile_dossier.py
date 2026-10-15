from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path
from unittest.mock import patch
import pytest
ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT/'astrologist'), str(ROOT/'astrologist/fixtures')]
import _paths
from subjects import PARTNER
from pa_context import chart_of
from profile_dossier import Dossier

@pytest.fixture
def chart():
    return chart_of(PARTNER['birth'])

def test_a0_shared_single_build_and_warm_zero_compute(tmp_path, chart):
    d = Dossier(tmp_path)
    import pa_dossier
    import profile_dossier
    with patch('pa_dossier.ground_chart', wraps=pa_dossier.ground_chart) as ground, patch('profile_dossier.route', wraps=profile_dossier.route) as route, patch('llm_client.complete', side_effect=AssertionError('No paid calls')):
        with ThreadPoolExecutor(4) as pool:
            results = list(pool.map(lambda _: d.build_a0('same', chart), range(4)))
        assert all(r == results[0] for r in results)
        assert ground.call_count == route.call_count == 1
        assert Dossier(tmp_path).build_a0('same', chart) == results[0]
        assert ground.call_count == route.call_count == 1
    assert all(p['status'] == 'ok' for p in d.manifest('same')['products'].values())

def test_selective_rebuild_and_immutable_readings(tmp_path, chart):
    d = Dossier(tmp_path)
    d.build_a0('same', chart)
    before = d.manifest('same')
    d.publish_section('same', {'key':'core_identity', 'text_tr':'Original', 'prompt_version':'v1'})
    updated = Dossier(tmp_path, {'natal_corpus':'new-version'})
    updated.build_a0('same', chart)
    after = updated.manifest('same')
    assert before['products']['chart'] == after['products']['chart']
    assert before['products']['natal_plan']['depends_on'] != after['products']['natal_plan']['depends_on']
    result = updated.publish_section('same', {'key':'core_identity', 'text_tr':'Rewritten', 'text_en':'Translation', 'prompt_version':'v2'})
    assert result['text_tr'] == 'Original'
    assert result['text_en'] == 'Translation'
    assert result['prompt_version'] == 'v1'

def test_identity_collision_and_path_guard(tmp_path, chart):
    d = Dossier(tmp_path)
    d.register('same', chart)
    with pytest.raises(ValueError):
        d.register('same', {**chart, 'confidence':'unknown'})
    with pytest.raises(ValueError):
        d.folder('../escape')

def test_deletion_requires_known_last_reference(tmp_path, chart):
    d = Dossier(tmp_path)
    d.build_a0('shared', chart)
    d.build_a0('unrelated', chart)
    d.retain('shared', 'a' * 64)
    d.retain('shared', 'b' * 64)
    assert not d.release('shared', 'c' * 64)
    assert not d.release('shared', 'a' * 64)
    assert d.get('shared', 'chart') == chart
    assert d.release('shared', 'b' * 64)
    assert not d.folder('shared').exists()
    assert d.get('unrelated', 'chart') == chart
    assert not d.release('unrelated', 'a' * 64)

def test_pa_reads_app_sections_without_generation_or_regrounding(tmp_path, chart):
    from pa_context import TurnContext
    d = Dossier(tmp_path)
    products = d.build_a0('app-chart', chart)
    plan = products['natal_plan']
    d.publish_section('app-chart', {'key': 'core_identity', 'text_tr': 'Saved app reading', 'principle_ids': plan['routed_ids']['core_identity']})
    subject = {**PARTNER, 'dossier_chart_key': 'app-chart'}
    with patch('pa_context.chart_of', side_effect=AssertionError('No compute')), patch('pa_dossier.ground_chart', side_effect=AssertionError('No grounding')), patch('llm_client.complete', side_effect=AssertionError('No generation')):
        ctx = TurnContext(subject, profile_dossier=d)
        assert ctx.natal() == chart
        dossier = ctx.dossier()
        assert dossier['prose']['p:natal_section:core_identity']['text_tr'] == 'Saved app reading'
        assert 'p:natal_section:inner_drives' not in dossier['prose']
        assert dossier['index']['by_topic']['inner_drives']

def test_section_bridge_offline_roundtrip_is_immutable_and_lazy(tmp_path, chart):
    sys.path.insert(0, str(ROOT/'backend/api'))
    from reading_section_bridge import run
    from test_l4_progressive import FakeGenerator
    d = Dossier(tmp_path)
    prepared = run({'op':'prepare', 'chart_key':'bridge', 'chart':chart}, dossier=d)
    gen = FakeGenerator()
    request = {'op':'section', 'chart_key':'bridge', 'section_key':'core_identity'}
    first = run(request, dossier=d, generator=gen)
    assert gen.usage['calls'] == 2 and gen.translations == 0
    for _ in range(3):
        assert run(request, dossier=d, generator=gen) == first
    translated = run({**request, 'op':'translate'}, dossier=d, generator=gen)
    assert translated['text_tr'] == first['text_tr']
    assert translated['text_en'] and gen.translations == 1
    assert run({**request, 'op':'translate'}, dossier=d, generator=gen) == translated
    assert gen.translations == 1
    assert first['principle_ids'] == prepared['plan']['routed_ids']['core_identity']
    exported = run({'op':'export', 'chart_key':'bridge'}, dossier=d)
    assert exported['grounded_principle_ids']
    assert 'rule' not in exported and 'natal_grounding' not in exported


def test_a0_product_hashes_identical_in_independent_folders(tmp_path, chart):
    left, right = Dossier(tmp_path/'left'), Dossier(tmp_path/'right')
    left.build_a0('same', chart)
    right.build_a0('same', chart)
    l, r = left.manifest('same'), right.manifest('same')
    assert {k:v['sha256'] for k,v in l['products'].items()} == {k:v['sha256'] for k,v in r['products'].items()}
