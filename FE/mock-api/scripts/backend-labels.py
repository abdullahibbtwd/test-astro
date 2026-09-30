"""Export the existing backend's deterministic labels. Never calls a model or orchestrator."""
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[3]
for folder in ('Interpretation_layer', 'calendar_reading', 'Calendar', 'Astrocartography'):
    sys.path.insert(0, str(root / folder))
import l4_render as natal
import cr_sections as calendar
from acg_constants import GOALS

cal = root / 'cal_run/20260929-130418_c7m_1979-03-30'
events = json.loads((cal / 'personal_events_1979-03-30.json').read_text(encoding='utf8'))['events']
periods = json.loads((cal / 'periods_1979-03-30.json').read_text(encoding='utf8'))['periods']
labels = {}
for year in (2026, 2027):
    collective = json.loads((root / f'cal_run/_collective/{year}.json').read_text(encoding='utf8'))
    for event in collective['events']:
        labels[event['id']] = dict(zip(('tr', 'en'), calendar.collective_label(event)))
for event in events:
    labels[event['id']] = dict(zip(('tr', 'en'), calendar.event_label(event)))
for period in periods:
    labels[period['id']] = dict(zip(('tr', 'en'), calendar.period_label(period['goal'], period['kind'])))
result = {'events': labels, 'goals': GOALS, 'bodies': {'tr': calendar.PLANET_TR, 'en': calendar.PLANET_EN},
          'signs': {'tr': calendar.SIGN_TR, 'en': {k: k.title() for k in calendar.SIGN_TR}},
          'natal': {lang: {'title': natal._DOC_TITLE[lang], 'parts': natal.MOVEMENT_TITLES[lang],
                    'sections': {key: {str(h): natal.section_title(key, lang, h) for h in range(13)}
                                 for key in natal.SECTION_TITLES}} for lang in ('tr', 'en')}}
print(json.dumps(result, ensure_ascii=False))
