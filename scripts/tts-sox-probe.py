"""Avoid one optional import availability shell probe when SoX is absent.

The installed package is unchanged. Its verified top-level os.popen('sox -h')
receives the same empty output/NO_SOX=True result as the observed missing tool.
Every other popen call is delegated; unknown children retain strict rejection.
"""
import hashlib,inspect,io,json,os,shutil,sys,time
from pathlib import Path

EXPECTED_SHA256='0c3e15258ce1f95ca050e045af634d1b16956af2b47ff7670f78b08567d19d47'

def install(root):
    root=Path(root).resolve()
    if Path(sys.prefix).resolve()!=root/'.venv-tts':raise RuntimeError('Optional SoX probe policy is TTS-environment only')
    source=root/'.venv-tts/Lib/site-packages/sox/__init__.py'
    raw=source.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=EXPECTED_SHA256:raise RuntimeError('SoX import source changed; no probe interception')
    if 'sox' in sys.modules:raise RuntimeError('SoX imported before TTS probe policy; no retrospective trust')
    if shutil.which('sox') is not None:raise RuntimeError('Unexpected SoX executable present; do not override its availability')
    compiled=compile(raw,str(source),'exec');original=os.popen;consumed=False
    def popen(command,*args,**kwargs):
        nonlocal consumed
        caller=inspect.currentframe().f_back
        known=(caller.f_globals.get('__name__')=='sox'
               and Path(caller.f_code.co_filename).resolve()==source.resolve()
               and caller.f_code.co_code==compiled.co_code
               and caller.f_code.co_consts==compiled.co_consts
               and caller.f_code.co_names==compiled.co_names
               and caller.f_lineno==8)
        if not known:return original(command,*args,**kwargs)
        if consumed or command!='sox -h' or args or kwargs:raise RuntimeError('Unexpected known-source SoX probe invocation')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=EXPECTED_SHA256 or shutil.which('sox') is not None:
            raise RuntimeError('SoX source/environment changed during import')
        consumed=True;os.popen=original
        event=dict(event='optional_sox_probe_not_spawned',time=time.time(),source=str(source),source_sha256=EXPECTED_SHA256,
                   command='sox -h',result='empty output; package retains NO_SOX=True',external_process_created=False)
        print(json.dumps(event),flush=True)
        return io.StringIO('')
    os.popen=popen
    def restore():
        if os.popen is popen:os.popen=original
    return restore
