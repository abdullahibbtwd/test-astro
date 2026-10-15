"""Deterministic area facts from the existing scan; no network or language-model calls."""
import sys,json,hashlib
from pathlib import Path
root=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(root/'Astrocartography'))
from acg_recommend import area_view
from acg_goals import load_scan,load_affinity
from acg_geodata import load_regions,load_countries
run=root/'acg_run/20260929-105635_kgc'
cache=root/'frontend/mock-api/fixtures/_area-source.json'
inputs=[run/'acg_1979-03-30.json',run/'goal_scan_1979-03-30.npz',*sorted((root/'Astrocartography').glob('acg_*.py')),Path(__file__)]
key=hashlib.sha256(b''.join(p.read_bytes() for p in inputs)).hexdigest()
if cache.exists():
 old=json.loads(cache.read_text(encoding='utf-8'))
 if old['key']==key:
  print(json.dumps(old['data'],ensure_ascii=False));sys.exit()
acg=json.loads(inputs[0].read_text(encoding='utf-8')); scan=load_scan(str(inputs[1]));aff=load_affinity()
areas=[];regions=load_regions()
for iso in ['TR','BG','DE','GB','ES']:
 view=area_view('country',iso,acg,scan,aff);areas.append(view)
 for code in dict.fromkeys(v['admin1_id'] for v in view.get('varies_highlight',[])):
  areas.append(area_view('region',code,acg,scan,aff))
data={'areas':areas,'countries':load_countries(),'regions':regions}
cache.write_text(json.dumps({'key':key,'data':data},ensure_ascii=False),encoding='utf-8')
print(json.dumps(data,ensure_ascii=False))
