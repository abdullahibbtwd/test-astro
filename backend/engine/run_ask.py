"""Private local runner for the Personal Astrologist. Live calls share the FE budget."""
import argparse
import contextlib
from datetime import date,datetime,timezone
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'astrologist'))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--subject-json',help='Saved frontend Subject JSON; birth data never enters prompts')
    ap.add_argument('--birth-date');ap.add_argument('--birth-time');ap.add_argument('--lat',type=float);ap.add_argument('--lon',type=float);ap.add_argument('--timezone',default='Europe/Sofia');ap.add_argument('--place',default='')
    ap.add_argument('--label',default='You');ap.add_argument('--relation',default='self')
    ap.add_argument('--others-json');ap.add_argument('--context',default='{}');ap.add_argument('--lang',choices=['tr','en'],default='tr');ap.add_argument('--today',default=date.today().isoformat());ap.add_argument('--question')
    ap.add_argument('--plan-only',action='store_true');ap.add_argument('--dry-run',action='store_true');ap.add_argument('--plan-json');ap.add_argument('--fake-llm');ap.add_argument('--prewarm',action='store_true')
    a=ap.parse_args()
    read=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
    if a.subject_json: subject=read(a.subject_json)
    else:
        if not a.birth_date or a.lat is None or a.lon is None: ap.error('Supply --subject-json or --birth-date, --lat, --lon (and --birth-time if known).')
        subject={'label':a.label,'relation':a.relation,'is_self':a.relation=='self','effective_tz':a.timezone,'birth':{'date':a.birth_date,'time':a.birth_time,'place':{'name':a.place,'lat':a.lat,'lon':a.lon,'tz':a.timezone}}}
    from pa_context import TurnContext
    from pa_engine import answer_turn,prewarm
    from pa_planner import make_plan,validate_plan
    from pa_tools import run_tool,apply_caps,model_view
    from pa_compose import SYSTEM
    out=ROOT/'ask_run'/(datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'_'+uuid4().hex[:3]);out.mkdir(parents=True)
    (out/'manifest.json').write_text(json.dumps({'layer':'astrologist','mode':'dry' if a.dry_run else 'fake' if a.fake_llm else 'live'}),encoding='utf-8')
    if a.prewarm:
        with contextlib.redirect_stdout(io.StringIO()): report=prewarm(subject,lang=a.lang,today=date.fromisoformat(a.today))
        print(json.dumps(report));return
    if a.dry_run and not a.plan_json: ap.error('--dry-run requires --plan-json')
    if a.fake_llm:
        replies=iter(read(a.fake_llm))
        def complete(*args,**kwargs):
            value=next(replies);return SimpleNamespace(text=json.dumps(value),usage={})
    elif not a.dry_run:
        import llm_client
        import os
        sys.path.insert(0,str(ROOT.parent/'api'))
        from budget import install_guard
        data = Path(os.environ['DATA_DIR']) if os.environ.get('DATA_DIR') else ROOT.parent/'.local-data'
        install_guard(llm_client,str(data/'ai-budget.sqlite'))
        complete=llm_client.complete
    history=[];context=json.loads(a.context);last_audit={};number=0
    while True:
        text=a.question or input('> ')
        if text=='/quit':break
        if text=='/new':history=[];continue
        if text=='/audit':print(json.dumps(last_audit,ensure_ascii=False,indent=2));continue
        if text.startswith('/context '):context=json.loads(text[9:]);continue
        number+=1;req={'subject':subject,'profiles':read(a.others_json) if a.others_json else [],'compatibilities':[],'context':context,'text':text,'lang':a.lang,'today':a.today,'history':history}
        ctx=TurnContext(subject,profiles=req['profiles'],lang=a.lang,today=date.fromisoformat(a.today))
        with contextlib.redirect_stdout(io.StringIO()):
            if a.dry_run:
                plan,drops=validate_plan(read(a.plan_json),ctx,context)
                packs=apply_caps([run_tool(ctx,f'c{i+1}',c['tool'],c['args'],c['forced']) for i,c in enumerate(plan['calls'])])
                data={'system':SYSTEM,'plan':plan,'drops':drops,'evidence':[model_view(p) for p in packs]}
                (out/f'dry_run_prompt_{number}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
                events=[]
            elif a.plan_only:
                plan,drops,_=make_plan(req,ctx,complete);events=[]
            else: events=list(answer_turn(req,complete=complete))
        if a.dry_run or a.plan_only:print(json.dumps(plan,ensure_ascii=False,indent=2))
        else:
            with (out/'transcript.jsonl').open('a',encoding='utf-8') as f:
                for event in events:f.write(json.dumps(event,ensure_ascii=False)+'\n')
            final=next((e['data'] for e in events if e['event']=='final'),None)
            if final:
                m=final['message'];print(m['text']);print(json.dumps({'cards':m['cards'],'links':m['links']},ensure_ascii=False))
                last_audit=final['audit'];(out/f'audit_{number}.json').write_text(json.dumps(last_audit,ensure_ascii=False,indent=2),encoding='utf-8')
                history.extend([{'role':'user','text':text},{'role':'assistant','text':m['text'],'calls':last_audit['calls']}])
            else: print('Conversation unavailable.')
        if a.question:break
    print('Saved privately:',out)

if __name__=='__main__':main()
