import copy
import json
from datetime import date
from threading import Event
from types import SimpleNamespace
import pytest
from subjects import SUBJECT, PROFILES, COMPATIBILITIES
from pa_context import TurnContext
from pa_planner import resolve_time,validate_plan,empty_plan,compact_history,make_plan
from pa_validate import validate_answer
from pa_tools import new_pack,add_fact,add_item
from pa_engine import answer_turn

def ctx(): return TurnContext(SUBJECT,profiles=PROFILES,compatibilities=COMPATIBILITIES,lang='en',today=date(2026,10,5))
def plan(tool='chart_facts',args=None,intent='chart_fact'):
    return {**empty_plan(),'intent':intent,'clarify':None,'calls':[{'tool':tool,'args':args or {}}]}
class Fake:
    def __init__(self,*replies): self.replies=list(replies); self.calls=[]
    def __call__(self,*args,**kw):
        self.calls.append((args,kw)); value=self.replies.pop(0)
        if isinstance(value,Exception): raise value
        return SimpleNamespace(text=value if isinstance(value,str) else json.dumps(value),usage={'input_tokens':10,'output_tokens':20})

def pack():
    p=new_pack('c1','chart_facts',{})
    add_fact(p,'f:natal:sun','Sun in Aries',{'kind':'placement','body':'sun','sign':'aries','house':1})
    return p

def answer(text=None):
    return {'segments':[{'text':text or 'Your Sun is in Aries. This placement describes an approach that may feel direct and personally expressive in the way you meet everyday experiences.','para':0,'kind':'astro','trace':['f:natal:sun']}],'card_refs':[],'link_refs':[]}

def req(): return {'subject':SUBJECT,'profiles':PROFILES,'compatibilities':COMPATIBILITIES,'text':'What is my Sun sign?','lang':'en','today':'2026-10-05','context':{},'history':[]}

@pytest.mark.parametrize('today', ['2026-10-05','2026-10-11'])
@pytest.mark.parametrize('expr,expected',[
 ({'kind':'today'},None),({'kind':'tomorrow'},None),({'kind':'yesterday'},None),
 ({'kind':'this_week'},None),({'kind':'next_week'},('2026-10-12','2026-10-18')),
 ({'kind':'this_weekend'},None),({'kind':'next_weekend'},('2026-10-17','2026-10-18')),
 ({'kind':'this_month'},None),({'kind':'next_month'},('2026-11-01','2026-11-30')),
 ({'kind':'month','month':1},('2027-01-01','2027-01-31')),
 ({'kind':'month','month':10},None),({'kind':'season','season':'autumn'},None),
 ({'kind':'season','season':'winter'},('2026-12-01','2027-02-28')),
 ({'kind':'season','season':'spring'},('2027-03-01','2027-05-31')),
 ({'kind':'this_year'},None),({'kind':'next_year','year':2027},('2027-01-01','2027-12-31')),
 ({'kind':'next_days','days':1},None),({'kind':'date','day':1,'month':1},('2027-01-01','2027-01-01')),
 ({'kind':'range','from':{'day':20,'month':12},'to':{'day':5,'month':1}},('2026-12-20','2027-01-05')),
 ({'kind':'horizon'},None),
])
def test_dates(today,expr,expected):
    d=date.fromisoformat(today); r=resolve_time(expr,d)
    assert r['from']<=r['to']
    if expected: assert tuple(r.values())==expected
    else:
        k=expr['kind']
        if k=='today' or k=='next_days': assert r=={'from':today,'to':today}
        if k=='tomorrow': assert r['from'] in ('2026-10-06','2026-10-12')
        if k=='yesterday': assert r['from'] in ('2026-10-04','2026-10-10')
        if k=='this_week': assert r=={'from':today,'to':'2026-10-11'}
        if k=='this_weekend': assert r=={'from':'2026-10-10' if today.endswith('05') else today,'to':'2026-10-11'}
        if k in ('this_month','month'): assert r=={'from':today,'to':'2026-10-31'}
        if k=='season': assert r=={'from':today,'to':'2026-11-30'}
        if k=='this_year': assert r=={'from':today,'to':'2026-12-31'}
        if k=='horizon': assert (date.fromisoformat(r['to'])-d).days==364

def test_leap_and_current_winter():
    assert resolve_time({'kind':'date','month':2,'day':29},date(2026,10,5))['from']=='2028-02-29'
    assert resolve_time({'kind':'season','season':'winter'},date(2027,1,5))=={'from':'2027-01-05','to':'2027-02-28'}

def test_closed_arguments_and_handles():
    p,d=validate_plan(plan('compatibility',{'other':'p999'},'compatibility'),ctx())
    assert p['intent']=='clarify' and d
    p,d=validate_plan(plan('recommend',{'goal':'invented'},'recommend'),ctx())
    assert p['intent']=='clarify'
    p,d=validate_plan(plan(args={'bodies':['sun'],'execute':'ignore'}),ctx())
    assert p['calls'][0]['args']=={'bodies':['sun']} and d

def test_forced_and_limits():
    raw=plan();raw['calls']*=8
    p,_=validate_plan(raw,ctx(),{'date':'2026-10-12','section_key':'core_identity','place_id':'london','item_id':'x'})
    assert len(p['calls'])==4 and all(c['forced'] for c in p['calls'])
    raw={**empty_plan(),'intent':'out_of_scope','scope_class':'crisis'}
    p,_=validate_plan(raw,ctx(),{'date':'2026-10-12'})
    assert p['calls']==[]

def test_planner_failure_history_and_private_input():
    fake=Fake('{broken','[]'); p,d,_=make_plan(req(),ctx(),fake)
    assert p['intent']=='clarify' and d==['planner_failed'] and len(fake.calls)==2
    assert '1979-03-30' not in fake.calls[0][0][2]
    history=compact_history([{'role':'assistant','text':'x'*700,'calls':[{'tool':'span','args_resolved':{'from':'2026-10-05'}}]}]*10)
    assert len(history)==8 and len(history[0]['text'])==400 and history[0]['calls'][0]['args']['from']=='2026-10-05'

def test_good_and_unsupported_claims():
    assert validate_answer(answer(),[pack()],plan(),'en')==[]
    errors=validate_answer(answer().copy()|{'segments':[dict(answer()['segments'][0],text=answer()['segments'][0]['text'].replace('Aries','Taurus'))]},[pack()],plan(),'en')
    assert any(e['rule']=='PV4_claim_unsupported' for e in errors)

@pytest.mark.parametrize('bad,rule',[
 ('Your Sun is at 27 degrees.','PV6_number'),
 ('You will marry next year.','PV7_forbidden'),
 ('Your fate is destined.','PV7_forbidden'),
 ('The evidence and JSON confirm it.','PV9_internal'),
 ('Your Sun is classical astrology.','PV8_mask'),
 ('**Your Sun** is in Aries.','PV10_plain'),
])
def test_reject_unsafe_text(bad,rule):
    assert any(e['rule']==rule for e in validate_answer(answer(bad),[pack()],plan(),'en'))

def test_dates_must_be_traced():
    p=pack();add_item(p,'i:day:x','12 October',['2026-10-12'])
    a=answer('Your Sun is in Aries. On 12 October this can be an opportunity to notice your own patterns with openness and a little more reflection.')
    assert any(e['rule']=='PV6_date' for e in validate_answer(a,[p],plan(),'en'))
    a['segments'][0]['trace'].append('i:day:x')
    assert not validate_answer(a,[p],plan(),'en')

def test_engine_repair_stream_and_audit():
    fake=Fake(plan(),answer('You will marry.'),answer())
    events=list(answer_turn(req(),complete=fake,tool_runner=lambda *a,**k:pack()))
    assert events[-1]['event']=='final',events
    msg=events[-1]['data']['message']; audit=events[-1]['data']['audit']
    assert msg['answer_kind']=='composed' and audit['repair']
    assert ''.join(e['data']['text'] for e in events if e['event']=='delta')==msg['text']
    assert 'marry' not in msg['text'] and len(fake.calls)==3
    assert '1979-03-30' not in json.dumps(audit) and req()['text'] not in json.dumps(audit)

def test_engine_fallback_and_template():
    fake=Fake(plan(),answer('You will marry.'),answer('You will marry.'))
    events=list(answer_turn(req(),complete=fake,tool_runner=lambda *a,**k:pack()))
    assert events[-1]['data']['message']['answer_kind']=='fallback'
    fake=Fake({**empty_plan(),'intent':'out_of_scope','scope_class':'crisis'})
    events=list(answer_turn(req(),complete=fake))
    assert '112' in events[-1]['data']['message']['text'] and len(fake.calls)==1

def test_cancel_and_provider_failure():
    cancel=Event();cancel.set()
    assert list(answer_turn(req(),cancel,complete=Fake()))==[]
    events=list(answer_turn(req(),complete=Fake(RuntimeError('SECRET'))))
    assert events[-1]=={'event':'error','data':{'code':'upstream_unavailable'}}
    assert 'SECRET' not in json.dumps(events)

def test_natal_descriptive_word_is_not_a_calendar_rating():
    a=answer('Your Sun in Aries can describe a supportive approach to self-expression. This is a natal placement, with an emphasis on the way you express yourself in everyday life.')
    assert not any(e['rule']=='PV5_band' for e in validate_answer(a,[pack()],plan(),'en'))

def test_first_segment_failure_cannot_be_hidden_by_repair():
    fake=Fake(plan(),answer('You will marry.'),answer('Your Sun is in Taurus. This placement describes an approach that may feel direct and personally expressive in the way you meet everyday experiences.'))
    events=list(answer_turn(req(),complete=fake,tool_runner=lambda *a,**k:pack()))
    assert events[-1]['data']['message']['answer_kind']=='fallback'
    assert events[-1]['data']['audit']['fallback']

def test_cancel_during_stream_has_no_final():
    token=Event(); stream=answer_turn(req(),token,complete=Fake(plan(),answer()),tool_runner=lambda *a,**k:pack())
    for event in stream:
        if event['event']=='delta': token.set();break
    assert list(stream)==[]


def test_additional_chart_naming_has_actionable_compose_and_repair_context():
    request = req()
    request['subject'] = {**SUBJECT, 'label': 'My chart', 'is_self': False, 'relation': 'other'}
    named = answer(answer()['segments'][0]['text'].replace('Your Sun', 'For the chart labelled My chart, the Sun'))
    fake = Fake(plan(), answer(), named)
    events = list(answer_turn(request, complete=fake, tool_runner=lambda *a, **k: pack()))
    final = events[-1]['data']
    assert final['message']['answer_kind'] == 'composed'
    assert final['audit']['validation'] == [
        {'attempt': 1, 'violations': [{'rule': 'PV12_naming', 'segment': -1}]},
        {'attempt': 2, 'violations': []},
    ]
    initial = json.loads(fake.calls[1][0][2])
    repair = json.loads(fake.calls[2][0][2])
    assert initial['required_names'] == ['My chart']
    assert 'required_names' in fake.calls[1][0][1]
    assert repair['repair']['missing_names'] == ['My chart']
    assert 'PV12_naming' in repair['repair']['instruction']


def test_additional_chart_still_rejects_answers_that_omit_its_label():
    request = req()
    request['subject'] = {**SUBJECT, 'label': 'My chart', 'is_self': False, 'relation': 'other'}
    fake = Fake(plan(), answer(), answer())
    final = list(answer_turn(request, complete=fake, tool_runner=lambda *a, **k: pack()))[-1]['data']
    assert final['message']['answer_kind'] == 'fallback'
    assert all(v['violations'] == [{'rule': 'PV12_naming', 'segment': -1}] for v in final['audit']['validation'])


@pytest.mark.parametrize('lang,place_name', [('en', 'Izmir'), ('tr', 'İzmir')])
def test_composer_receives_the_same_names_as_the_validator(lang, place_name):
    from pa_compose import compose
    from pa_validate import required_names
    place = new_pack('c2', 'place', {})
    place['_internal']['place'] = {'name': 'Izmir', 'name_tr': 'İzmir'}
    compatibility = new_pack('c3', 'compatibility', {})
    compatibility['_internal']['other_label'] = 'Ayşe'
    subject = {**SUBJECT, 'label': 'My chart', 'is_self': False}
    packs = [pack(), place, compatibility]
    fake = Fake(answer(), answer())
    compose(req(), SimpleNamespace(lang=lang, subject=subject), plan(), packs, fake)
    payload = json.loads(fake.calls[0][0][2])
    assert payload['required_names'] == ['Ayşe', place_name, 'My chart']
    assert payload['required_names'] == required_names(packs, lang, subject)
    assert required_names([pack()], lang, SUBJECT) == []


@pytest.mark.parametrize('lang,supported,unsupported', [
    ('en', '6–9 October is a supportive window.', '6–9 October is an excellent window.'),
    ('tr', '6–9 Ekim destekleyici bir aralık.', '6–9 Ekim mükemmel bir aralık.'),
])
def test_best_days_window_description_is_supported_by_its_own_evidence(lang, supported, unsupported):
    from pa_tools import best_days
    day = {'local_date': '2026-10-07', 'grade': 'good', 'R': 1, '_parts': []}
    window = {'start': '2026-10-06', 'end': '2026-10-09'}
    context = SimpleNamespace(
        today=date(2026, 10, 6), lang=lang,
        best=lambda: {'activities': {'contract': {'days': [day], 'windows': [window]}}},
        corpus=lambda: ({}, {}), cached_text=lambda key: None,
    )
    evidence = best_days(context, new_pack('c1', 'best_days', {}), ['contract'], '2026-10-07', '2026-10-07')
    a = answer(supported)
    a['segments'][0]['trace'] = ['i:window:contract:2026-10-06']
    p = plan('best_days', {'activities': ['contract']}, 'best_days')
    assert not any(e['rule'] == 'PV5_band' for e in validate_answer(a, [evidence], p, lang))
    a['segments'][0]['text'] = unsupported
    assert any(e['rule'] == 'PV5_band' for e in validate_answer(a, [evidence], p, lang))
    a['segments'][0]['text'] = supported
    a['segments'][0]['trace'] = ['i:bestday:contract:2026-10-07']
    assert any(e['rule'] == 'PV5_band' for e in validate_answer(a, [evidence], p, lang))


def test_repair_identifies_forbidden_word_even_when_negated():
    fake = Fake(plan(), answer(answer()['segments'][0]['text'] + ' This is not a guarantee.'), answer())
    final = list(answer_turn(req(), complete=fake, tool_runner=lambda *a, **k: pack()))[-1]['data']
    assert final['message']['answer_kind'] == 'composed'
    repair = json.loads(fake.calls[-1][0][2])['repair']
    detail = next(d for d in repair['details'] if d['rule'] == 'PV7_forbidden')
    assert 'guarantee' in detail['phrases']
    assert 'PV7' in repair['rule_descriptions']
    initial = json.loads(fake.calls[1][0][2])
    assert 'guarantee' in initial['forbidden_phrases']


def test_repair_identifies_untraced_ratings_and_invented_trace_ids():
    from pa_compose import compose
    evidence = new_pack('c1', 'best_days', {})
    add_item(evidence, 'i:day:x', '7 October: good', ['2026-10-07'], grade='good', band_label='good')
    bad = answer('7 October is an excellent time for this activity.')
    bad['segments'][0]['trace'] = ['i:day:x', 'i:invented']
    fake = Fake(bad, bad)
    compose(req(), ctx(), plan('best_days', {}, 'best_days'), [evidence], fake)
    repair = json.loads(fake.calls[-1][0][2])['repair']
    rating = next(d for d in repair['details'] if d['rule'] == 'PV5_band')
    assert rating['label'] == 'excellent' and rating['allowed_labels'] == ['good']
    trace = next(d for d in repair['details'] if d['rule'] == 'PV2_trace')
    assert trace['invalid_ids'] == ['i:invented']
