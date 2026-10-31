"""Import only the installed SoX Python package; no AI modules/models."""
import importlib.util,io,json,os,sys
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('probe_test',ROOT/'scripts/tts-sox-probe.py');p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
checks=[]
def reject(call):
    try:call()
    except RuntimeError:pass
    else:raise AssertionError('Invalid source/environment accepted')
with patch.object(sys,'prefix',str(ROOT/'.venv-livetalking')):reject(lambda:p.install(ROOT))
with patch.object(p,'EXPECTED_SHA256','0'*64):reject(lambda:p.install(ROOT))
with patch.object(p.shutil,'which',lambda name:'C:/unexpected/sox.exe'):reject(lambda:p.install(ROOT))
checks.append('non-TTS environment, changed source and unexpected executable refuse interception')
calls=[]
def delegate(command,*args,**kwargs):calls.append((command,args,kwargs));return io.StringIO('delegated')
with patch.object(os,'popen',delegate):
    restore=p.install(ROOT)
    try:
        os.popen('sox -h')
        exec(compile("import os\nos.popen('sox -h & extra')",str(ROOT/'.venv-tts/Lib/site-packages/sox/__init__.py'),'exec'),{'__name__':'sox'})
        assert calls==[('sox -h',(),{}),('sox -h & extra',(),{})]
    finally:restore()
checks.append('same command from wrong caller and forged/extra-shell source are not trusted; original popen semantics delegated')
spawned=[]
def audit(event,args):
    if event=='subprocess.Popen':spawned.append(str(args[0]));raise AssertionError('Import unexpectedly spawned an external process')
sys.addaudithook(audit)
restore=p.install(ROOT)
try:
    import sox
    assert sox.NO_SOX is True and not spawned
    assert not any(n in sys.modules for n in ['torch','qwen_tts','faster_qwen3_tts','transformers'])
finally:restore()
checks.append('real installed SoX import retains NO_SOX=True with zero external process and zero AI imports')
print(json.dumps(dict(status='PASS',checks=checks,model_loads=0,external_processes=spawned),ensure_ascii=False))
