"""Exact, initialization-only TTS SoX probe attestation. No shell execution."""
import ctypes,hashlib,json,os,sys,time
from ctypes import wintypes as w
from pathlib import Path

SOURCE_SHA256='0c3e15258ce1f95ca050e045af634d1b16956af2b47ff7670f78b08567d19d47'


class HeldProcess:
    def __init__(self,pid):
        self.kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        self.kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];self.kernel.OpenProcess.restype=w.HANDLE
        self.kernel.GetProcessTimes.argtypes=[w.HANDLE,*([ctypes.POINTER(w.FILETIME)]*4)]
        self.kernel.GetExitCodeProcess.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)]
        self.kernel.CloseHandle.argtypes=[w.HANDLE]
        self.handle=self.kernel.OpenProcess(0x1000|0x00100000,False,pid)
        if not self.handle:raise ctypes.WinError(ctypes.get_last_error())
    def ticks(self):
        values=[w.FILETIME() for _ in range(4)]
        if not self.kernel.GetProcessTimes(self.handle,*(ctypes.byref(v) for v in values)):raise ctypes.WinError(ctypes.get_last_error())
        return (values[0].dwHighDateTime<<32)|values[0].dwLowDateTime
    def exit_code(self):
        value=w.DWORD()
        if not self.kernel.GetExitCodeProcess(self.handle,ctypes.byref(value)):raise ctypes.WinError(ctypes.get_last_error())
        return None if value.value==259 else value.value
    def close(self):
        if self.handle:self.kernel.CloseHandle(self.handle);self.handle=None


class SoxIdentity:
    def __init__(self,manager):
        self.m=manager;self.initializing=False;self.run_id=None;self.handles={}
    def source(self):
        path=self.m.ROOT/'.venv-tts/Lib/site-packages/sox/__init__.py'
        if hashlib.sha256(path.read_bytes()).hexdigest()!=SOURCE_SHA256:raise RuntimeError('SoX import source changed; auxiliary exception refused')
        return dict(path=str(path),sha256=SOURCE_SHA256)
    def begin(self,owner):
        self.source();self.initializing=True;self.run_id=owner['StackRunId']
        owner['tts_initialization']=dict(phase='INITIALIZING',run_id=self.run_id,source=self.source())
        self.m.write('owner.json',owner)
    def context(self,owner):
        m=self.m
        if (m.ENTRY!=m.ROOT/'scripts/tts-run.py' or m.PYTHON!=m.ROOT/'.venv-tts/Scripts/python.exe'
            or m.PORT!=8765 or owner['root']!=str(m.ROOT) or owner['entry']!=str(m.ENTRY)):
            raise RuntimeError('SoX exception is restricted to the exact TTS service')
        tag=owner.get('tts_initialization',{})
        disk=json.loads(m.OWNER.read_text(encoding='utf-8'))
        run=owner.get('StackRunId')
        if (not isinstance(run,str) or len(run)!=32 or tag.get('run_id')!=run
            or disk.get('StackRunId')!=run or disk['processes'][0]!=owner['processes'][0]
            or (self.run_id is not None and self.run_id!=run)):
            raise RuntimeError('SoX StackRunId/root baseline conflict')
        m.verified(owner['processes'][0])
        if tag.get('source')!=self.source():raise RuntimeError('SoX source identity conflict')
    def exact_command(self,item):
        cmd=Path(os.environ['SystemRoot'])/'System32/cmd.exe'
        return (Path(item['exe']).resolve()==cmd.resolve() and len(item['cmdline'])==3
                and Path(item['cmdline'][0]).resolve()==cmd.resolve()
                and item['cmdline'][1:]==['/c','sox -h'])
    def parent(self,process,owner):
        m=self.m;root=m.verified(owner['processes'][0]);parent=process.parent()
        if parent is None:raise RuntimeError('SoX parent unavailable')
        baseline=next((p for p in owner['processes'] if p['pid']==parent.pid),None)
        if baseline is None:raise RuntimeError('SoX direct parent is not already registered')
        m.verified(baseline,owner)
        current=m.identity(parent)
        allowed={m.PYTHON.resolve(),Path(sys._base_executable).resolve()}
        argv=current['cmdline']
        if (Path(current['exe']).resolve() not in allowed or len(argv)!=4
            or Path(argv[0]).resolve()!=Path(current['exe']).resolve()
            or argv[1:]!=['-B','-s',str(m.ENTRY)] or current!=baseline):
            raise RuntimeError('SoX direct parent is not the exact TTS Python invocation')
        if process.ppid()!=parent.pid or process.pid not in {p.pid for p in root.children(recursive=True)}:
            raise RuntimeError('SoX parent/tree mismatch')
        if process.children(recursive=True):raise RuntimeError('Unknown descendant under SoX probe')
        return current
    def verify(self,process,owner,register=False):
        m=self.m;item=m.identity(process)
        if not self.exact_command(item):return False
        self.context(owner)
        proofs=owner.setdefault('tts_initialization_auxiliaries',[])
        proof=next((p for p in proofs if p['identity']['pid']==item['pid']),None)
        if proof is None:
            if not register or not self.initializing or owner['tts_initialization']['phase']!='INITIALIZING':
                raise RuntimeError('New SoX probe outside this initialization is forbidden')
            handle=HeldProcess(item['pid'])
            try:
                if handle.ticks()!=item['creation_filetime_ticks']:raise RuntimeError('SoX held-handle FILETIME mismatch')
                parent=self.parent(process,owner)
                if (m.identity(process)!=item or process.ppid()!=parent['pid']
                    or handle.exit_code() is not None or item['creation_filetime_ticks']<parent['creation_filetime_ticks']):
                    raise RuntimeError('SoX changed/exited before complete attestation')
                proof=dict(identity=item.copy(),parent=parent,root=owner['processes'][0].copy(),
                           run_id=owner['StackRunId'],source=self.source(),observed_time_ns=time.time_ns(),exit=None)
                self.handles[item['pid']]=(handle,json.loads(json.dumps(proof)))
                proofs.append(proof)
                owner['processes'].append(item.copy())
                m.write('owner.json',owner)
            except BaseException:
                handle.close();raise
        else:
            if (item!=proof['identity'] or proof['run_id']!=owner['StackRunId']
                or proof['root']!=owner['processes'][0] or proof['source']!=self.source()
                or proof['exit'] is not None):raise RuntimeError('SoX identity/PID reuse/proof conflict')
            if self.parent(process,owner)!=proof['parent']:raise RuntimeError('SoX direct parent identity changed')
        return True
    def refresh(self,owner):
        proofs=owner.get('tts_initialization_auxiliaries',[])
        if not proofs:return
        self.context(owner)
        for proof in proofs:
            held=self.handles.get(proof['identity']['pid'])
            if not held:continue # A later manager never invents an exit code for an old PID.
            handle,baseline=held
            if ({k:v for k,v in proof.items() if k!='exit'}!={k:v for k,v in baseline.items() if k!='exit'}
                or handle.ticks()!=proof['identity']['creation_filetime_ticks']):raise RuntimeError('SoX retained evidence changed')
            code=handle.exit_code()
            if code is not None and proof['exit'] is None:
                proof['exit']=dict(code=code,observed_time_ns=time.time_ns(),creation_filetime_ticks=handle.ticks(),method='retained original process handle')
                self.m.write('owner.json',owner)
    def finish(self,owner):
        self.refresh(owner)
        if any(p['exit'] is None for p in owner.get('tts_initialization_auxiliaries',[])):
            raise RuntimeError('SoX probe exit is not attested; refuse final TTS READY')
        owner['tts_initialization']['phase']='READY';self.initializing=False
        self.m.write('owner.json',owner)
        for handle,_ in self.handles.values():handle.close()
        self.handles.clear()
