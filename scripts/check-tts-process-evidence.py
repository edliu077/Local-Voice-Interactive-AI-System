"""No models. Real immediately exiting helpers and unchanged rejection suite."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runtime/repair-tts-launch-race-20261026/offline'
OUT.mkdir(parents=True,exist_ok=True)
spec=importlib.util.spec_from_file_location('creation_test',ROOT/'scripts/tts-process-evidence.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
run=os.urandom(16).hex();previous=os.environ.get('REBUILD_STACK_RUN_ID')
os.environ['REBUILD_STACK_RUN_ID']=run
restore=m.install(ROOT)
checks=[]
try:
    # No sleep: child may have exited before CreateProcess evidence is read.
    p=subprocess.Popen([sys.executable,'-B','-s','-c','pass'],creationflags=subprocess.CREATE_NO_WINDOW)
    assert p.wait(timeout=10)==0
    folder=ROOT/'runtime/tts-service/process-evidence'/run
    deadline=time.monotonic()+10
    while not list(folder.glob(f'{p.pid}-*.exit.json')):
        assert time.monotonic()<deadline
        time.sleep(.01)
    candidates=m.candidates(ROOT,run,p.pid)
    assert len(candidates)==1 and candidates[0]['trusted'] is False
    observation=candidates[0]['observation']
    end=json.loads(next(folder.glob(f'{p.pid}-*.exit.json')).read_text(encoding='utf-8'))
    assert observation['identity']['pid']==p.pid and observation['identity']['creation_filetime_ticks']>0
    assert observation['identity']['creation_filetime_ticks']==end['identity']['creation_filetime_ticks']
    assert observation['identity']['exe']==end['identity']['exe']
    assert end['identity']['raw_exit_code']==0 and end['signaled']
    assert observation['parent']['pid']==os.getpid() and observation['caller_stack']
    assert not m.candidates(ROOT,'f'*32,p.pid) and not m.candidates(ROOT,run,p.pid+1)
    checks.append('immediate real helper: original native creation handle supplies PID/FILETIME/exe, exact CreateProcess argv, parent and signaled exit after delayed polling; observation grants no trust')
    # Commands not in a service allowlist remain only diagnostic observations.
    cmd=str(Path(os.environ['SystemRoot'])/'System32/cmd.exe')
    q=subprocess.Popen([cmd,'/d','/c','exit','9'],creationflags=subprocess.CREATE_NO_WINDOW)
    assert q.wait(timeout=10)==9
    assert m.candidates(ROOT,run,q.pid)[0]['observation']['grants_trust'] is False
    checks.append('unknown cmd command observed without adoption or permission')
finally:
    restore()
    if previous is None:os.environ.pop('REBUILD_STACK_RUN_ID',None)
    else:os.environ['REBUILD_STACK_RUN_ID']=previous
# Existing suite includes native helper, PID reuse, FILETIME, parent, unknown
# descendants, abnormal rollback and Stage7H resource regression. Keep old logs.
source=(ROOT/'scripts/check-tts-startup-repair.py').read_text(encoding='utf-8').replace("OUT=ROOT/'runtime/repair-20261026-tts-owner/offline'",'OUT=Path('+repr(str(OUT/'prior'))+')')
exec(compile(source,str(ROOT/'scripts/check-tts-startup-repair.py'),'exec'),{'__file__':str(ROOT/'scripts/check-tts-startup-repair.py'),'__name__':'prior_evidence_regression'})
checks.append('all prior strict owner / SoX / parent / FILETIME / PID reuse / transient-exit rejection / cleanup / RAM / Commit / paging / GPU contracts PASS')
for path in ['scripts/tts-process-evidence.py','scripts/tts-run.py','scripts/tts-service.py','scripts/livetalking-service.py','scripts/check-tts-process-evidence.py']:
    ast.parse((ROOT/path).read_text(encoding='utf-8'))
assert not any(x in sys.modules for x in ['torch','qwen_tts','faster_qwen3_tts','transformers'])
(OUT/'result.json').write_text(json.dumps(dict(status='PASS',checks=checks,run_id=run,models_loaded=0),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS',checks=checks),ensure_ascii=False,indent=2))
