import sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'astrologist'),str(ROOT/'astrologist/fixtures')]
import _paths
from subjects import PARTNER
from pa_context import chart_of
from profile_dossier import Dossier


def test_static_products_reuse_computation_and_match_producers(tmp_path):
    import compute_acg,compute_parans,acg_locate
    chart=chart_of(PARTNER['birth']);d=Dossier(tmp_path);d.register('fixture',chart)
    for name in ('acg','acg_geojson','parans','parans_geojson','city_scan'):
        d.get('fixture',name)
    assert d.get('fixture','acg') == compute_acg.compute_acg(chart)
    with patch('compute_acg.compute_acg',side_effect=AssertionError('warm compute')),patch('compute_parans.compute_parans',side_effect=AssertionError('warm parans')),patch('acg_locate.city_scan',side_effect=AssertionError('warm scan')):
        for name in ('acg','acg_geojson','parans','parans_geojson','city_scan'):
            assert d.get('fixture',name)

def test_rolling_dates_and_forecast_location_are_scoped(tmp_path):
    import compute_forecast
    d=Dossier(tmp_path);d.register('fixture',chart_of(PARTNER['birth']))
    first={'date':'2026-10-06','tz':'Europe/Sofia','lat':42.7,'lon':23.3}
    second={**first,'date':'2026-10-07'}
    with patch('llm_client.complete',side_effect=AssertionError('CPU products must not call models')):
        month=d.get('fixture','forecast_month',first)
        assert month == d.get('fixture','forecast_month',second)
        day=d.get('fixture','forecast_day',first)
        with patch('compute_forecast.compute_forecast',side_effect=AssertionError('Warm forecast')):
            assert day==d.get('fixture','forecast_day',first)
            assert month==d.get('fixture','forecast_month',{**first,'lat':40,'lon':25})
        d.get('fixture','forecast_day',{**first,'lat':40,'lon':25})
    products=d.manifest('fixture')['products']
    assert len([p for p in products.values() if p['name']=='forecast_day'])==2
    assert len([p for p in products.values() if p['name']=='forecast_month'])==1


def test_calendar_and_pair_products_are_shared_on_warm_access(tmp_path):
    from subjects import SUBJECT
    d=Dossier(tmp_path);d.register('fixture',chart_of(PARTNER['birth']));d.register('other',chart_of(SUBJECT['birth']))
    anchor={'date':'2026-10-06','tz':'Europe/Sofia'}
    with patch('llm_client.complete',side_effect=AssertionError('No LLM')):
        calendar=d.get('fixture','calendar',anchor)
        best=d.get('fixture','best_days',anchor)
        pair=d.get('fixture','relationship_grounding',{'other_chart_key':'other'})
        assert calendar['events']['horizon']['from_local']=='2026-09-29'
        with patch('personal_events.build_personal_events',side_effect=AssertionError('Warm events')),patch('cal_scoring.day_scores',side_effect=AssertionError('Warm scores')),patch('best_days.build_best_days',side_effect=AssertionError('Warm best')),patch('ground_relationship.ground_relationship',side_effect=AssertionError('Warm pair')):
            assert calendar==d.get('fixture','calendar',anchor)
            assert best==d.get('fixture','best_days',anchor)
            assert pair==d.get('fixture','relationship_grounding',{'other_chart_key':'other'})


def test_build_and_last_reference_deletion_are_serialized(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    d = Dossier(tmp_path)
    d.register('fixture', {'meta': {}})
    d.retain('fixture', 'a' * 64)
    entered, finish = Event(), Event()
    def build():
        entered.set()
        assert finish.wait(5)
        return {'value': 1}
    with ThreadPoolExecutor(max_workers=2) as pool:
        producer = pool.submit(d.memo, 'fixture', 'test_product', None, {}, build)
        assert entered.wait(5)
        deletion = pool.submit(d.release, 'fixture', 'a' * 64)
        finish.set()
        assert producer.result() == {'value': 1}
        assert deletion.result()
    assert not d.folder('fixture').exists()


def test_failed_product_records_status_and_can_retry(tmp_path):
    import pytest
    d = Dossier(tmp_path)
    d.register('fixture', {'meta': {}})
    def fail():
        raise ValueError('private input must not enter manifest')
    with pytest.raises(ValueError):
        d.memo('fixture', 'test_product', None, {}, fail)
    entry = d.manifest('fixture')['products']['test_product']
    assert entry['status'] == 'failed'
    assert entry['error_type'] == 'ValueError'
    assert 'private input' not in str(entry)
    assert d.memo('fixture', 'test_product', None, {}, lambda: {'ok': True}) == {'ok': True}
    assert d.manifest('fixture')['products']['test_product']['status'] == 'ok'


def test_calendar_computes_internal_scores_once(tmp_path):
    import cal_scoring
    d = Dossier(tmp_path)
    d.register('fixture', chart_of(PARTNER['birth']))
    with patch('cal_scoring.day_scores', wraps=cal_scoring.day_scores) as scores:
        d.get('fixture', 'calendar', {'date': '2026-10-06', 'tz': 'Europe/Sofia'})
    assert scores.call_count == 1


def test_goal_scan_npz_and_wheel_cache(tmp_path):
    import numpy as np
    d = Dossier(tmp_path)
    d.register('fixture', chart_of(PARTNER['birth']))
    with patch('llm_client.complete', side_effect=AssertionError('No LLM')):
        scan = d.get('fixture', 'goal_scan')
        wheels = d.get('fixture', 'wheel_svg')
        assert set(wheels) == {'light', 'dark'}
        assert all('<svg' in svg for svg in wheels.values())
        with patch('acg_goals.goal_scan', side_effect=AssertionError('Warm scan')), patch('run.render_chart_wheels', side_effect=AssertionError('Warm wheels')):
            restored = d.get('fixture', 'goal_scan')
            assert set(scan) == set(restored)
            for key in scan:
                np.testing.assert_array_equal(scan[key], restored[key])
            assert d.get('fixture', 'wheel_svg') == wheels
