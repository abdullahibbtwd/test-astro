"""Local development-only Android UI smoke helper."""
import subprocess, sys, xml.etree.ElementTree as ET, re
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parents[2]
adb=root/'.tooling/android/platform-tools/adb.exe'
def run(*args):return subprocess.check_output([str(adb),*args],text=True,encoding='utf-8',errors='replace')
def state():
 run('shell','uiautomator','dump','/sdcard/astrology-ui.xml')
 return ET.fromstring(run('shell','cat','/sdcard/astrology-ui.xml'))
action=sys.argv[1] if len(sys.argv)>1 else 'state'
if action=='tap':
 label=sys.argv[2]; nodes=[n for n in state().iter('node') if n.get('content-desc')==label or n.get('text')==label]
 if not nodes:raise SystemExit('Visible label not found: '+label)
 n=next((n for n in nodes if n.get('content-desc')==label),nodes[0]);x1,y1,x2,y2=map(int,re.findall(r'\d+',n.get('bounds')));run('shell','input','tap',str((x1+x2)//2),str((y1+y2)//2))
elif action=='type':run('shell','input','text',sys.argv[2])
elif action=='back':run('shell','input','keyevent','4')
elif action=='shot':
 state()
 target=root/'FE/artifacts/screenshots'/sys.argv[2];target.parent.mkdir(parents=True,exist_ok=True)
 run('shell','screencap','-p','/sdcard/astrology.png');run('pull','/sdcard/astrology.png',str(target));print(target)
else:
 for n in state().iter('node'):
  if n.get('text') or n.get('content-desc'):print(n.get('text'),n.get('content-desc'),n.get('bounds'))
