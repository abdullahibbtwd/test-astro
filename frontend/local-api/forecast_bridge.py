"""Use the approved predictive pipeline for the local app, without changing its rules."""
import contextlib
import json
import os
import sys
from pathlib import Path
from datetime import date
ROOT = Path(__file__).resolve().parents[2]
for folder in ('', 'd_layer', 'Forecast_compute', 'principles_grounding', 'prediction_reading'):
    sys.path.insert(0, str(ROOT / folder))
from budget import install_guard


def prepare(data):
    from compute_forecast import compute_forecast
    from ground_forecast import ground_forecast
    import pr_calendar
    c = data['context']
    if c['horizon'] not in ('day', 'month', 'year') or c['lens'] not in ('general', 'personal', 'professional'):
        raise ValueError('Invalid forecast request')
    target = date.fromisoformat(c['target'])
    if c['horizon'] != 'day' and target.day != 1:
        raise ValueError('Calendar forecasts must start on the first')
    current = c['current']
    forecast = compute_forecast(data['chart'], c['target'], c['horizon'],
        latitude=current['lat'], longitude=current['lon'], window_tz=current['tz'])
    records = json.loads((ROOT / 'principles_grounding/all_principles_grounded.with_predictive.json').read_text(encoding='utf-8'))
    grounded = ground_forecast(forecast, data['chart'], records, cap=6, sim_floor=0.35).forecast
    calendar = pr_calendar.for_forecast(pr_calendar.build(data['chart'], current['tz'], target), grounded)
    return grounded, calendar


def generate(data):
    import llm_client
    dry = data.get('dry_run', False)
    if not dry and os.environ.get('ASTRO_ALLOW_PAID') != '1':
        raise RuntimeError('Paid generation disabled')
    if dry:
        def no_models(*args, **kwargs):
            raise RuntimeError('Dry-run must not call models')
        llm_client.complete = no_models
    budget = None if dry else install_guard(llm_client, str(ROOT / 'frontend/.local-data/ai-budget.sqlite'))
    grounded, calendar = prepare(data)
    import pr_calendar
    result = {'context': data['context'], 'from': str(pr_calendar.window_dates(grounded)[0]),
              'to': str(pr_calendar.window_dates(grounded)[1]),
              'segments': {key: {'from': str(pr_calendar.segment_dates(grounded, key)[0]),
                                 'to': str(pr_calendar.segment_dates(grounded, key)[1])}
                           for key in calendar['segments']}}
    if dry:
        return {**result, 'event_count': len(grounded['events'])}
    from read_forecast import run_reading
    from run_predictive import translate_reading
    from pr_events import HORIZON_KEYS
    reading, errors, report = run_reading(grounded, reading_type=data['context']['lens'],
        model=llm_client.DEFAULT_MODEL, calendar=calendar, max_workers=2)
    if report.get('build_blocking'):
        raise RuntimeError('Forecast validation failed')
    translated = translate_reading(reading, llm_client.DEFAULT_CHEAP_MODEL)
    keys = HORIZON_KEYS[data['context']['horizon']]
    readings = {}
    for lang, source in [('tr', reading), ('en', translated)]:
        if any(not isinstance(source.get(key), str) or not source[key].strip() for key in keys):
            raise RuntimeError('Incomplete forecast translation')
        readings[lang] = {key: source[key] for key in keys}
    return {**result, 'readings': readings, 'validation_warning_count': len(errors),
            'budget_reserved_or_spent_usd': budget.total()}

if __name__ == '__main__':
    try:
        data = json.load(sys.stdin)
        with contextlib.redirect_stdout(sys.stderr):
            result = generate(data)
        print(json.dumps(result, ensure_ascii=True))
    except Exception as error:
        print(json.dumps({'error': type(error).__name__}))
        sys.exit(1)
