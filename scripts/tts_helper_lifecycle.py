"""TTS creation-time authority. Authenticated pipe + duplicated native handles.

JSON diagnostic records are not authority. The manager owns live handles and
private baselines, and takes its identity lock before granting any creation.
"""
import copy,ctypes,hashlib,json,os,secrets,threading,time,uuid
from ctypes import wintypes as w
from pathlib import Path
from multiprocessing.connection import Listener
from multiprocessing import AuthenticationError
import _winapi
from tts_nvml import NVML


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def send(connection,value):connection.send_bytes(json.dumps(value).encode())
def receive(connection):
    if not connection.poll(10):raise RuntimeError('Helper protocol deadline exceeded')
    return json.loads(connection.recv_bytes(16384))


def handle_identity(handle):
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.GetProcessTimes.argtypes=[w.HANDLE,*([ctypes.POINTER(w.FILETIME)]*4)]
    k.GetProcessId.argtypes=[w.HANDLE];k.GetProcessId.restype=w.DWORD
    values=[w.FILETIME() for _ in range(4)]
    if not k.GetProcessTimes(handle,*(ctypes.byref(v) for v in values)):raise ctypes.WinError(ctypes.get_last_error())
    return dict(pid=k.GetProcessId(handle),creation_filetime_ticks=(values[0].dwHighDateTime<<32)|values[0].dwLowDateTime)


def client_pid(connection):
    k=ctypes.WinDLL('kernel32',use_last_error=True);pid=w.ULONG()
    k.GetNamedPipeClientProcessId.argtypes=[w.HANDLE,ctypes.POINTER(w.ULONG)]
    if not k.GetNamedPipeClientProcessId(connection.fileno(),ctypes.byref(pid)):raise ctypes.WinError(ctypes.get_last_error())
    return pid.value


def exact_argv(smi,gpu,kind):
    base=[str(smi),'--query-gpu=memory.used','--format=csv,noheader,nounits','--id='+gpu]
    if kind=='query':return base
    if kind=='loop':return base+['--loop-ms=200']
    raise RuntimeError('Unknown helper operation')


def verify_live(m,process,owner):
    proof=next((p for p in owner.get('tts_created_auxiliaries',[]) if p['identity']['pid']==process.pid),None)
    if proof is None:return False
    if m.ENTRY!=m.ROOT/'scripts/tts-run.py' or m.PORT!=8765:raise RuntimeError('Foreign helper context')
    if set(proof['sources'])!={'tts_gpu_monitor.py','tts_helper_client.py','tts_helper_lifecycle.py','tts_nvml.py'}:
        raise RuntimeError('Incomplete helper source baseline')
    parent=next((p for p in owner['processes'] if p['pid']==proof['parent']['pid']),None)
    if (proof['run_id']!=owner.get('StackRunId') or proof['root']!=owner['processes'][0]
            or parent!=proof['parent'] or m.identity(process)!=proof['identity']
            or proof['identity']['cmdline']!=exact_argv(proof['smi'],proof['gpu_uuid'],proof['kind'])
            or Path(proof['smi']).resolve()!=Path(os.environ['SystemRoot'],'System32/nvidia-smi.exe').resolve()
            or process.ppid()!=parent['pid']):raise RuntimeError('TTS helper identity/parent/run conflict')
    m.verified(parent,owner)
    for name,sha in proof['sources'].items():
        if digest(m.ROOT/'scripts'/name)!=sha:raise RuntimeError('TTS helper trusted source changed')
    # The approved helper is detached at creation; it needs no console host.
    # Therefore ALL descendants remain forbidden, including a surprise conhost.
    if process.children(recursive=True):raise RuntimeError('Unknown grandchild under TTS helper')
    return True


def stop_with_handles(m,original_stop):
    """A later standalone stop also holds native objects across termination."""
    if not m.OWNER.exists():return original_stop()
    owner=json.loads(m.OWNER.read_text(encoding='utf-8'));held=[];exits=[]
    previous_check=m.TTS_STOP_EXIT_CHECK
    try:
        for proof in owner.get('tts_created_auxiliaries',[]):
            item=proof['identity']
            try:
                process=m.verified(item,owner)
                handle=_winapi.OpenProcess(0x1000|0x00100000,False,process.pid)
            except m.psutil.NoSuchProcess:
                exits.append(dict(identity=item,state='previously_registered_instance_absent_at_stop',exit_code=None))
                continue
            if handle_identity(handle)!={k:item[k] for k in ('pid','creation_filetime_ticks')}:
                _winapi.CloseHandle(handle);raise RuntimeError('Stop handle FILETIME/PID conflict')
            held.append((handle,copy.deepcopy(item)))
        def check_exits():
            if previous_check is not None:previous_check()
            for handle,item in held:
                if _winapi.WaitForSingleObject(handle,0)!=_winapi.WAIT_OBJECT_0:
                    raise RuntimeError('Stopped helper native object not signaled; owner retained')
                exits.append(dict(identity=item,state='STOPPED',native=handle_identity(handle),
                                  exit_code=_winapi.GetExitCodeProcess(handle),method='retained native stop handle'))
            if exits:m.write('helper-stop-exits.json',dict(run_id=owner.get('StackRunId'),exits=exits,time=time.time()))
        m.TTS_STOP_EXIT_CHECK=check_exits
        result=original_stop()
        if exits:
            receipt=json.loads((m.RUNTIME/'stop-result.json').read_text(encoding='utf-8'))
            receipt['auxiliary_exits']=exits;m.write('stop-result.json',receipt)
        return result
    finally:
        m.TTS_STOP_EXIT_CHECK=previous_check
        for handle,_ in held:_winapi.CloseHandle(handle)


class Broker:
    def __init__(self,m,run_id,gpu_uuid):
        if m.ENTRY!=m.ROOT/'scripts/tts-run.py' or m.PORT!=8765:raise RuntimeError('TTS-only broker')
        self.m=m;self.run_id=run_id;self.gpu=gpu_uuid
        self.smi=Path(os.environ['SystemRoot'])/'System32/nvidia-smi.exe'
        self.sources={p:digest(m.ROOT/'scripts'/p) for p in ['tts_gpu_monitor.py','tts_helper_client.py','tts_helper_lifecycle.py','tts_nvml.py']}
        self.lock=threading.RLock();self.handles={};self.error=None;self.owner=None;self.enabled=True
        self.address=r'\\.\pipe\RebuildTTS-'+uuid.uuid4().hex;self.key=secrets.token_bytes(32)
        self.listener=Listener(self.address,family='AF_PIPE',authkey=self.key)
        self.thread=threading.Thread(target=self._serve,daemon=True,name='tts-creation-authority')

    def environment(self):
        return dict(REBUILD_TTS_HELPER_PIPE=self.address,REBUILD_TTS_HELPER_AUTH=self.key.hex(),
                    REBUILD_STACK_RUN_ID=self.run_id,REBUILD_TTS_GPU_UUID=self.gpu,
                    REBUILD_TTS_GPU_SMI=str(self.smi),REBUILD_TTS_HELPER_ROOT=str(self.m.ROOT))

    def start(self,owner):self.owner=owner;self.thread.start()

    def bind(self):
        self.register_original=self.m.register_children;self.stopping=False
        self.m.register_children=self.register

    def register(self,root,owner):
        with self.lock:
            self.refresh(owner,stopping=self.stopping)
            current=self.register_original(root,owner)
            self.refresh(owner,stopping=self.stopping)
            return current

    def _serve(self):
        while self.enabled:
            try:connection=self.listener.accept()
            except AuthenticationError:continue # Not an authenticated service request.
            except (OSError,EOFError):return
            try:
                # Holding this lock across prepare/create/register prevents the
                # polling path from observing an unattested suspended helper.
                with self.lock:self._transaction(connection)
            except Exception as exc:
                self.error=repr(exc)
                self.m.write('helper-protocol-failure.json',dict(run_id=self.run_id,error=self.error,time=time.time()))
                try:send(connection,dict(ok=False,error='Helper attestation rejected'))
                except (OSError,EOFError):pass
            finally:connection.close()

    def _transaction(self,connection):
        m=self.m;owner=self.owner
        if not self.enabled or owner.get('StackRunId')!=self.run_id:raise RuntimeError('Inactive/cross-run helper authority')
        request=receive(connection);pid=client_pid(connection)
        if request!={'action':'prepare','run_id':self.run_id,'kind':request.get('kind')}:
            raise RuntimeError('Unknown helper request')
        kind=request['kind'];argv=exact_argv(self.smi,self.gpu,kind)
        if len(owner.get('tts_created_auxiliaries',[]))+len(owner.get('tts_retired_auxiliaries',[]))>=4:
            raise RuntimeError('Bounded startup helper budget exhausted')
        self.register_original(m.verified(owner['processes'][0]),owner)
        parent=next((p for p in owner['processes'] if p['pid']==pid),None)
        if parent is None:raise RuntimeError('Pipe peer is not a registered TTS parent')
        m.verified(parent,owner)
        if parent['cmdline'][1:]!=['-B','-s',str(m.ENTRY)]:raise RuntimeError('Pipe peer command mismatch')
        if any(digest(m.ROOT/'scripts'/p)!=sha for p,sha in self.sources.items()):raise RuntimeError('Helper source changed')
        send(connection,dict(ok=True,argv=argv))
        not_before_ticks=time.time_ns()//100+116444736000000000
        created=receive(connection)
        if created.get('action')!='created' or created.get('run_id')!=self.run_id:raise RuntimeError('Creation transaction mismatch')
        peer=_winapi.OpenProcess(0x0040|0x1000,False,pid)
        handle=None
        try:
            if handle_identity(peer)!={k:parent[k] for k in ('pid','creation_filetime_ticks')}:raise RuntimeError('Pipe parent FILETIME changed')
            handle=_winapi.DuplicateHandle(peer,int(created['handle']),_winapi.GetCurrentProcess(),0,False,_winapi.DUPLICATE_SAME_ACCESS)
            native=handle_identity(handle)
            if native!=created.get('native'):raise RuntimeError('Forged handle/PID/FILETIME record')
            child=m.psutil.Process(native['pid']);item=m.identity(child)
            if (item['pid']!=native['pid'] or item['creation_filetime_ticks']!=native['creation_filetime_ticks']
                or item['exe'].lower()!=str(self.smi).lower() or item['cmdline']!=argv
                or child.ppid()!=pid or child.children(recursive=True)
                or m.identity(m.psutil.Process(pid))!=parent
                or native['creation_filetime_ticks']<max(parent['creation_filetime_ticks'],not_before_ticks)
                or _winapi.WaitForSingleObject(handle,0)!=_winapi.WAIT_TIMEOUT):
                raise RuntimeError('Native helper executable/argv/parent/lifetime mismatch')
            proof=dict(identity=item,parent=copy.deepcopy(parent),root=copy.deepcopy(owner['processes'][0]),
                       run_id=self.run_id,sources=self.sources.copy(),smi=str(self.smi),gpu_uuid=self.gpu,kind=kind,
                       method='authenticated native pipe peer + duplicated original handle before resume',exit=None)
            self.handles[native['pid']]=(handle,copy.deepcopy(proof));handle=None
            owner.setdefault('tts_created_auxiliaries',[]).append(proof)
            owner['processes'].append(item);m.write('owner.json',owner)
            send(connection,dict(ok=True,registered=native))
        finally:
            if handle is not None:_winapi.CloseHandle(handle)
            _winapi.CloseHandle(peer)

    def refresh(self,owner,stopping=False):
        with self.lock:
            if self.error and not stopping:raise RuntimeError('TTS helper protocol failure: '+self.error)
            if {p['identity']['pid'] for p in owner.get('tts_created_auxiliaries',[])}!=set(self.handles):
                raise RuntimeError('Helper record set differs from private native handle registry')
            for proof in list(owner.get('tts_created_auxiliaries',[])):
                held=self.handles.get(proof['identity']['pid'])
                if held is None:raise RuntimeError('Helper has no original native handle')
                handle,baseline=held
                if proof!=baseline or handle_identity(handle)!={k:proof['identity'][k] for k in ('pid','creation_filetime_ticks')}:
                    raise RuntimeError('Private helper baseline/FILETIME changed')
                if _winapi.WaitForSingleObject(handle,0)==_winapi.WAIT_OBJECT_0:
                    code=_winapi.GetExitCodeProcess(handle)
                    retired=copy.deepcopy(proof);retired['exit']=dict(code=code,signaled=True,method='manager retained original kernel handle',time=time.time())
                    owner.setdefault('tts_retired_auxiliaries',[]).append(retired)
                    owner['tts_created_auxiliaries'].remove(proof)
                    owner['processes']=[p for p in owner['processes'] if p!=proof['identity']]
                    _winapi.CloseHandle(handle);del self.handles[proof['identity']['pid']]
                    self.m.write('owner.json',owner)
                    if code!=0 and not stopping:raise RuntimeError('TTS helper exited with failure: '+str(code))

    def close(self):
        self.enabled=False;self.listener.close()
        released=[]
        for handle,proof in self.handles.values():
            signaled=_winapi.WaitForSingleObject(handle,0)==_winapi.WAIT_OBJECT_0
            released.append(dict(identity=proof['identity'],native=handle_identity(handle),
                state='EXITED' if signaled else 'REGISTERED_RUNNING_HANDOFF',
                exit_code=_winapi.GetExitCodeProcess(handle) if signaled else None))
        try:
            if released:self.m.write('helper-handle-release.json',dict(run_id=self.run_id,processes=released,time=time.time()))
        finally:
            for handle,_ in self.handles.values():_winapi.CloseHandle(handle)
            self.handles.clear()
