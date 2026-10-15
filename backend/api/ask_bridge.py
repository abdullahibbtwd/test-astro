"""Run the separately supplied PA bridge behind the existing shared spending cap."""
from pathlib import Path
import contextlib
import json
import os
import runpy
import sys


def main():
    if os.environ.get('ASTRO_ALLOW_PAID') != '1' or os.environ.get('ASTRO_ASK_ENABLED') != '1':
        raise RuntimeError('PA generation disabled')
    root = Path(os.environ.get('ASTRO_PA_ROOT', Path(__file__).resolve().parents[1] / 'engine')).resolve()
    bridge = root / 'ask_bridge.py'
    if not bridge.is_file() or not (root / 'astrologist/pa_engine.py').is_file():
        raise RuntimeError('PA backend incomplete')
    sys.path.insert(0, str(root))
    with contextlib.redirect_stdout(sys.stderr):
        import llm_client
        from budget import install_guard
        data = Path(os.environ['DATA_DIR']) if os.environ.get('DATA_DIR') else Path(__file__).resolve().parents[1] / '.local-data'
        install_guard(llm_client, str(data / 'ai-budget.sqlite'))
    # The backend owns the PA_04 stdin/JSONL protocol; providers are already guarded.
    runpy.run_path(str(bridge), run_name='__main__')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print(json.dumps({'event': 'error', 'data': {
            'type': 'about:blank', 'title': 'Conversation unavailable',
            'status': 503, 'code': 'upstream_unavailable',
        }}), flush=True)
