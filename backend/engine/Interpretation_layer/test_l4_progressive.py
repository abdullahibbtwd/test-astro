import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'astrologist'), str(ROOT / 'astrologist/fixtures')]
import _paths
from subjects import SUBJECT, PARTNER, COLLEAGUE
from pa_context import chart_of
from pa_dossier import ground_chart
from l4_progressive import prepare, generate_section, routed_for, written_context, section_output, translate_section, CONTEXT_CHARS
from l4_sections import SECTION_ORDER
from l4_validate import validate


@pytest.fixture(scope='module')
def fixtures():
    return [(c, prepare(c, ground_chart(c)['principles'], chart_key='fixture'))
            for c in [chart_of(s['birth']) for s in (PARTNER, COLLEAGUE, SUBJECT)]]


def test_plan_determinism_and_ownership(fixtures):
    for chart, plan in fixtures:
        assert plan == prepare(chart, ground_chart(chart)['principles'], chart_key='fixture')
        assert plan['order'] == list(SECTION_ORDER)
        assert len(plan['own']['core_identity']) >= 20
        assert len(plan['own']['inner_drives']) >= 10
        assert set(plan['owners']) == set().union(*map(set, plan['routed_ids'].values()))
        for key in plan['order']:
            assert set(plan['own'][key]).isdisjoint(row['id'] for row in plan['elsewhere'][key])
            assert set(plan['own'][key]) | {r['id'] for r in plan['elsewhere'][key]} == set(plan['routed_ids'][key])
        for key in ('sun_house', 'moon_house'):
            assert plan['own'][key] == plan['routed_ids'][key]
        for pid, owner in plan['owners'].items():
            rows = [r for r in plan['routed'][owner] if r['principle_id'] == pid]
            assert rows
            assert any(' occupancy: ' not in r and ' rulership: ' not in r for r in rows[0]['reasons'])


def test_language_validation_remains_strict(fixtures):
    _, plan = fixtures[0]
    out = section_output(plan, 'core_identity', text_tr='Kendini anlamak için zaman ayırabilirsin.')
    allowed = {'core_identity': set(plan['routed_ids']['core_identity'])}
    assert not validate(out, allowed, langs=('tr',))
    assert any('text_en is empty' in e for e in validate(out, allowed))
    out['sections'][0]['principle_ids'] = ['invented']
    assert any('not routed' in e for e in validate(out, allowed, langs=('tr',)))


class FakeGenerator:
    synthesis_model = 'fake'
    synthesis_temperature = 0

    def __init__(self):
        self.usage = {'calls': 0, 'input_tokens': 0, 'output_tokens': 0}
        self.translations = 0

    def section(self, key, routed, chart):
        self.usage['calls'] += 1
        return SimpleNamespace(key=key, text_tr='Kendini anlamak için zaman ayırabilirsin.')

    def _call_json(self, model, system, user, **kwargs):
        self.usage['calls'] += 1
        payload = json.loads(user.split('\nReturn only')[0])
        assert "THIS SECTION'S DRAFT" in payload
        assert 'EXCEPTION:' in system
        return {'key': payload['SECTION'], 'text_tr': 'İç dünyanı tanımaya zaman ayırabilirsin.'}

    def _detox_text(self, key, text, lang):
        return text

    def translate(self, key, text):
        self.translations += 1
        return 'You can take time to understand your inner world.'


def test_two_calls_and_lazy_translation(fixtures):
    chart, plan = fixtures[0]
    gen = FakeGenerator()
    stages = []
    result = generate_section(plan, 'core_identity', chart, routed_for(plan, 'core_identity'), [], gen, on_stage=stages.append)
    assert gen.usage['calls'] == 2
    assert gen.translations == 0
    assert stages == ['reading', 'synthesis', 'validate']
    assert result['context_keys'] == []
    assert result['usage']['draft']['calls'] == result['usage']['finalize']['calls'] == 1
    assert translate_section('core_identity', result['text_tr'], gen)
    assert gen.translations == 1


def test_context_only_previous_core_and_nearest(fixtures):
    _, plan = fixtures[0]
    written = [{'key': k, 'text_tr': k} for k in plan['order']]
    result = written_context(plan, 'inner_drives', written)
    assert [r['key'] for r in result] == ['core_identity', 'moon_house']
    assert written_context(plan, 'core_identity', written) == []
    for r in written:
        r['text_tr'] = 'x' * CONTEXT_CHARS
    assert sum(len(r['text_tr']) for r in written_context(plan, 'inner_drives', written)) <= CONTEXT_CHARS


def test_opening_length_instruction_is_progressive_only(fixtures):
    from l4_generate import LLMGenerator
    from unittest.mock import patch
    chart, plan = fixtures[0]
    generator = LLMGenerator()
    with patch.object(generator, '_call_json', return_value={'key': 'core_identity', 'text_tr': 'text'}) as call:
        generator.progressive_section('core_identity', routed_for(plan, 'core_identity'), chart)
        assert '400-500' in call.call_args.args[1]
        generator.section('core_identity', routed_for(plan, 'core_identity'), chart)
        assert 'ONBOARDING LENGTH' not in call.call_args.args[1]
