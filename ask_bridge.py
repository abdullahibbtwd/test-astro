"""One private stdin request; stdout contains only the PA_04 JSONL protocol."""
import contextlib
import io
import json
import os
from pathlib import Path
import signal
import sys
from threading import Event
sys.path.insert(0,str(Path(__file__).resolve().parent/'astrologist'))

def main():
    output=sys.stdout
    cancel=Event()
    def stop(*_): cancel.set(); raise SystemExit(130)
    signal.signal(signal.SIGTERM,stop)
    signal.signal(signal.SIGINT,stop)
    def emit(value): output.write(json.dumps(value,ensure_ascii=False)+'\n'); output.flush()
    try:
        raw=sys.stdin.read(1000001)
        if len(raw)>1000000: raise ValueError('input_limit')
        payload=json.loads(raw)
        # Existing calculation layers may print progress; it must never enter JSONL or logs.
        with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            from pa_engine import answer_turn,prewarm
            if payload.get('op')=='turn':
                sys.path.insert(0,str(Path(__file__).resolve().parent/'FE'/'local-api'))
                import llm_client
                from budget import install_guard
                install_guard(llm_client,str(Path(__file__).resolve().parent/'FE'/'.local-data'/'ai-budget.sqlite'))
                for event in answer_turn(payload['request'],cancel): emit(event)
            elif payload.get('op')=='prewarm': emit({'event':'prewarm','data':prewarm(payload['subject'])})
            else: raise ValueError('invalid_operation')
    except Exception: emit({'event':'error','data':{'code':'generation_failed'}})

if __name__=='__main__': main()
