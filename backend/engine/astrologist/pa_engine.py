"""PA_04: bounded orchestration and validated JSONL event stream."""
from __future__ import annotations
import json
import re
import time
from datetime import date
from threading import Event
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import _paths
import pa_constants as K
from pa_context import TurnContext
from pa_planner import make_plan
from pa_tools import run_tool, apply_caps, SOURCE_KIND
from pa_compose import compose, template

SOURCE_LABELS = {'en':dict(zip(['chart','natal_reading','forecast','calendar','best_days','acg','compatibility'], ['Looking at your chart…','Reading your birth chart report…','Checking your forecast…','Checking your calendar…','Checking your best days…','Looking at your map…','Looking at your compatibility…'])), 'tr':dict(zip(['chart','natal_reading','forecast','calendar','best_days','acg','compatibility'], ['Haritanıza bakılıyor…','Doğum haritası yorumunuz okunuyor…','Öngörünüz kontrol ediliyor…','Takviminiz kontrol ediliyor…','En iyi günleriniz kontrol ediliyor…','Haritanızın dünya üzerindeki izlerine bakılıyor…','Uyumunuz inceleniyor…']))}

class Cancelled(Exception): pass

def _template_for(plan,packs):
    if plan['intent']=='out_of_scope': return {'crisis':'crisis_support','financial_decision':'decline_financial'}.get(plan['scope_class'],'decline_'+plan['scope_class']),{}
    if plan['intent']=='smalltalk': return 'ai_identity' if plan['smalltalk']=='ai_identity' else 'smalltalk_'+(plan['smalltalk'] or 'hello'),{}
    if plan['intent']=='clarify': return {'person':'clarify_person','place':'clarify_place_missing'}.get(plan['clarify'],'clarify_rephrase'),{}
    for p in packs:
        if p['status']=='needs_input':
            need=p['needs_input'] or {}; kind=need.get('kind')
            if kind=='place_ambiguous': return 'clarify_place',{'options':', '.join(x.get('label') or x.get('name') or '' for x in need.get('options',[]))}
            return ('clarify_place_not_found' if kind=='place_not_found' else 'clarify_person'),{}
    if not any(p[k] for p in packs for k in ('facts','records','items','prose')):
        if any(p['status']=='not_ready' for p in packs): return 'not_ready',{}
        if any(p['status']=='out_of_range' for p in packs): return 'out_of_range_future',{}
        return 'no_data',{}
    return None,{}

def safe_args(args):
    # Free text from a question or a place name is deliberately excluded from audit.
    return {k:v for k,v in args.items() if k not in ('place_text','label','name')}

def answer_turn(req,cancel=None,*,complete=None,tool_runner=run_tool,context_factory=TurnContext):
    cancel=cancel or Event(); started=time.monotonic(); deadline=started+K.PA_TURN_TIMEOUT_S
    def check():
        if cancel.is_set(): raise Cancelled()
        if time.monotonic()>=deadline: raise TimeoutError('turn_timeout')
    def remaining():
        check(); return max(.1,deadline-time.monotonic())
    def event(kind,data): return {'event':kind,'data':data}
    stage='input'; executor=ThreadPoolExecutor(max_workers=1)
    # One worker avoids races in Swiss Ephemeris and shared lazy caches. Timeout/cancel
    # are enforced on the caller; the frontend also owns the process lifetime.
    def bounded(fn,*args,limit=None,**kwargs):
        future=executor.submit(fn,*args,**kwargs); end=time.monotonic()+min(limit or remaining(),remaining())
        while True:
            check()
            try: return future.result(timeout=min(.1,max(.001,end-time.monotonic())))
            except FutureTimeout:
                if time.monotonic()>=end: future.cancel(); raise TimeoutError('stage_timeout')
    try:
        check()
        if not isinstance(req,dict) or req.get('lang','tr') not in ('tr','en') or not isinstance(req.get('text'),str) or not 1<=len(req['text'].strip())<=K.QUESTION_MAX_CHARS: raise ValueError('invalid_request')
        ctx=context_factory(req['subject'],profiles=req.get('profiles',[]),compatibilities=req.get('compatibilities',[]),lang=req.get('lang','tr'),today=date.fromisoformat(req['today']))
        if complete is None:
            from llm_client import complete
        yield event('status',{'phase':'understanding'})
        stage='provider'
        plan,drops,responses=bounded(make_plan,req,ctx,complete,timeout_s=min(30,remaining()))
        planner_count=len(responses)
        audit={'schema_version':K.AUDIT_SCHEMA,'lang':ctx.lang,'today':ctx.today.isoformat(),'tz':ctx.tz,'plan':{**plan,'calls':[{**c,'args':safe_args(c['args'])} for c in plan['calls']]},'plan_drops':drops,'calls':[],'validation':{},'models':{'planner':K.PA_MODEL,'composer':K.PA_MODEL},'versions':{'prompt':K.PROMPT_VERSION,'dossier':K.DOSSIER_SCHEMA,'pack':K.PACK_SCHEMA}}
        packs=[]
        if plan['calls']:
            yield event('status',{'phase':'computing','sources':[{'kind':kind,'label':SOURCE_LABELS[ctx.lang][kind]} for kind in dict.fromkeys(s for c in plan['calls'] for s in SOURCE_KIND[c['tool']])]})
        stage='tools'
        for i,c in enumerate(plan['calls']):
            check(); then=time.monotonic()
            p=bounded(tool_runner,ctx,f'c{i+1}',c['tool'],c['args'],forced=c['forced'],limit=K.PA_TOOL_TIMEOUT_S)
            packs.append(p)
            audit['calls'].append({'call_id':p['call_id'],'tool':c['tool'],'args_resolved':safe_args(c['args']),'forced':c['forced'],'status':p['status'],'cache_hit':p.get('cache_hit'),'ms':round((time.monotonic()-then)*1000)})
        apply_caps(packs)
        key,slots=_template_for(plan,packs)
        if key:
            message=template(key,ctx.lang,packs,slots); audit['template_id']=key
        else:
            yield event('status',{'phase':'writing'})
            stage='provider'
            message,validation,extra=bounded(compose,req,ctx,plan,packs,complete,timeout_s=min(30,remaining()),check=check)
            responses+=extra; audit['validation']=validation
        check()
        audit['answer_kind']=message['answer_kind']
        audit['evidence_ids']={k:list(dict.fromkeys(x['id'] for p in packs for x in p[k])) for k in ('facts','records','items','prose')}
        audit['usage']=[]
        price=K.PRICE.get(K.PA_MODEL,{})
        pin,pout=float(price.get('input',0)),float(price.get('output',0))
        for index,response in enumerate(responses):
            usage=response.usage or {}
            inp=usage.get('input_tokens',0) or 0; cached=usage.get('cache_read_input_tokens',0) or 0; output=usage.get('output_tokens',0) or 0
            audit['usage'].append({'step':'planner' if index<planner_count else 'composer' if index==planner_count else 'repair','input_tokens':inp,'cached_tokens':cached,'output_tokens':output,'cost_usd_est':((inp+cached)*pin+output*pout)/1000000})
        # Hash identifiers are safe to retain; labels and birth inputs are not.
        audit['chart_key']=ctx.chart_key() if packs else None
        audit['other_chart_keys']=[]
        audit['template_id']=audit.get('template_id')
        audit['latency_ms']={'total':round((time.monotonic()-started)*1000)}
        validation=audit['validation']
        for field,default in [('repair',False),('dropped_segments',[]),('fallback',False),('notes',[])]: audit[field]=validation.get(field,default)
        audit['validation']=[{'attempt':index+1,'violations':violations} for index,violations in enumerate(validation.get('attempts',[]))]
        tokens=re.findall(r'\S+\s*',message['text'])
        for i in range(0,len(tokens),K.DELTA_WORDS):
            check(); yield event('delta',{'text':''.join(tokens[i:i+K.DELTA_WORDS])})
        for card in message['cards']: check(); yield event('card',card)
        for link in message['links']: check(); yield event('link',link)
        check(); yield event('final',{'message':message,'audit':audit})
    except Cancelled: return
    except TimeoutError:
        if not cancel.is_set(): yield event('error',{'code':'generation_failed'})
    except Exception:
        if not cancel.is_set(): yield event('error',{'code':'upstream_unavailable' if stage=='provider' and time.monotonic()<deadline else 'generation_failed'})
    finally:
        executor.shutdown(wait=False,cancel_futures=True)

def prewarm(subject,*,lang='tr',today=None):
    ctx=TurnContext(subject,lang=lang,today=today)
    report={}
    for name,fn in [('dossier',ctx.dossier),('calendar',ctx.calendar),('best_days',ctx.best),('acg',ctx.acg)]:
        then=time.monotonic(); fn(); report[name]={'ready':True,'ms':round((time.monotonic()-then)*1000)}
    return report
