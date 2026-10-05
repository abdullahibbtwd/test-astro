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
