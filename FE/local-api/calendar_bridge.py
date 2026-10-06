"""Compute real calendar facts using the existing orchestrator with model calls disabled."""
import json
import sys
import contextlib
from pathlib import Path
from datetime import date
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import run_calendar as calendar
import cr_sections as labels

def compute(data):
    # Fail closed if a future orchestrator change accidentally attempts generation.
    import llm_client
    def no_models(*args, **kwargs): raise RuntimeError('Calendar facts must not call models')
    llm_client.complete = no_models
    profile = data['profile']
    b = profile['birth']
    y,m,d = map(int, b['date'].split('-'))
    h,minute = map(int, b['time'].split(':'))
    current = data.get('current') or b['place']
    def geocoder(query):
        p = b['place'] if query == 'birth' else current
        return {'latitude':p['lat'], 'longitude':p['lon'], 'display_name':p['name']}
    calendar.CAL_RUN = str(ROOT / 'FE/.local-data/calendar')
    result = calendar.run_calendar({'year':y,'month':m,'day':d,'hour':h,'minute':minute,'location':'birth','time_precision':'exact'},
        current_location='current', mode='all', start=date.fromisoformat(data['start']), dry_run=True, geocoder=geocoder)
    folder = Path(result['run_dir'])
    def read(name): return json.loads((folder / f"{name}_{b['date']}.json").read_text(encoding='utf-8'))
    events = read('personal_events')['events']
    periods = read('periods')['periods']
    horizon = read('personal_events')['horizon']
    years = list(range(int(horizon['from_local'][:4])-1,int(horizon['to_local'][:4])+2))
    years = [year for year in years if (ROOT / f'cal_run/_collective/{year}.json').exists()]
    names = {}
    for year in years:
        for event in json.loads((ROOT / f'cal_run/_collective/{year}.json').read_text(encoding='utf-8'))['events']:
            names[event['id']] = dict(zip(('tr','en'), labels.collective_label(event)))
    for event in events: names[event['id']] = dict(zip(('tr','en'), labels.event_label(event)))
    for period in periods: names[period['id']] = dict(zip(('tr','en'), labels.period_label(period['goal'],period['kind'])))
    return {'dir':str(folder), 'birthDate':b['date'], 'years':years, 'labels':{'events':names}}

if __name__ == '__main__':
    try:
        data = json.load(sys.stdin)
        with contextlib.redirect_stdout(sys.stderr):
            result = compute(data)
        print(json.dumps(result,ensure_ascii=True))
    except Exception as error:
        print(json.dumps({'error':type(error).__name__}))
        sys.exit(1)
