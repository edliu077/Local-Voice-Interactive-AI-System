"""No models: exact TTS shell probe, short exits, PID reuse and existing guards."""
import ast,copy,importlib.util,json,os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runtime/stage7i/offline';OUT.mkdir(parents=True,exist_ok=True)
sys.stdout.reconfigure(encoding='utf-8')
def module(name,path):
    s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
tts=module('tts_contract_i','scripts/tts-service.py');m=tts.manager;aux=tts.sox_module
checks=[];terminated=[]
class Process:
    def __init__(self,pid,exe,args,parent=None):self.pid=pid;self.executable=exe;self.args=args;self.parent_id=parent;self.created=pid*10000;self.alive=True
    def exe(self):return self.executable
    def cmdline(self):return self.args.copy()
    def ppid(self):return self.parent_id
    def parent(self):return lookup(self.parent_id) if self.parent_id else None
    def children(self,recursive=False):
        direct=[p for p in procs.values() if p.alive and p.parent_id==self.pid]
        return direct+([c for p in direct for c in p.children(True)] if recursive else [])
    def terminate(self):terminated.append(self.pid);self.alive=False
def lookup(pid):
    if pid not in procs or not procs[pid].alive:raise m.psutil.NoSuchProcess(pid)
    return procs[pid]
def identity(p):return dict(pid=p.pid,creation_filetime_ticks=p.created,exe=p.exe(),cmdline=p.cmdline())
class Handle:
    def __init__(self,pid):self.p=lookup(pid);self.closed=False
    def ticks(self):return self.p.created
    def exit_code(self):return None if self.p.alive else 1
    def close(self):self.closed=True
def rejects(call):
    try:call()
    except RuntimeError:pass
    else:raise AssertionError('Unsafe identity accepted')
def fixture():
    global procs,terminated
    terminated=[]
    root=Process(100,str(m.PYTHON),[str(m.PYTHON),'-B','-s',str(m.ENTRY)])
    python=Process(101,str(Path(sys._base_executable)),[str(Path(sys._base_executable)),'-B','-s',str(m.ENTRY)],100)
    cmd=str(Path(os.environ['SystemRoot'])/'System32/cmd.exe')
    child=Process(102,cmd,[cmd,'/c','sox -h'],101)
    procs={p.pid:p for p in [root,python,child]}
    owner=dict(root=str(ROOT),entry=str(m.ENTRY),StackRunId='a'*32,processes=[identity(root),identity(python)])
    guard=aux.SoxIdentity(m);m.INITIALIZATION_AUXILIARY=guard;m.write('owner.json',owner);guard.begin(owner)
    return root,python,child,owner,guard
with tempfile.TemporaryDirectory(dir=OUT,prefix='sox-') as temp:
    m.RUNTIME=Path(temp);m.OWNER=m.RUNTIME/'owner.json'
    with patch.object(m,'identity',identity),patch.object(m.psutil,'Process',lookup),patch.object(m.psutil,'pid_exists',lambda pid:pid in procs and procs[pid].alive),patch.object(m.psutil,'wait_procs',lambda ps,timeout:([p for p in ps if not p.alive],[p for p in ps if p.alive])),patch.object(m,'listeners',lambda:[]),patch.object(m,'resources',lambda:dict(mock=True)),patch.object(aux,'HeldProcess',Handle):
        root,python,child,owner,guard=fixture();m.register_children(root,owner)
        assert owner['tts_initialization_auxiliaries'][0]['parent']==identity(python)
        assert len(owner['processes'])==3 and not terminated
        child.alive=False;m.register_children(root,owner);guard.finish(owner)
        assert owner['tts_initialization_auxiliaries'][0]['exit']['code']==1
        assert owner['tts_initialization']['phase']=='READY'
        checks.append('exact System32 cmd /c sox -h with live parent/root/native-time/run attestation accepted; original-handle exit audited')
        for args in [['/c','sox -h & whoami'],['/c','sox -h','extra'],['/c','echo sox'],['/k','sox -h']]:
            root,python,child,owner,guard=fixture();child.args=[child.executable,*args]
            rejects(lambda:m.register_children(root,owner));assert not terminated and len(owner['processes'])==2
        checks.append('different cmd, extra shell command, extra argv and /k rejected without adoption')
        root,python,child,owner,guard=fixture();child.executable=str(ROOT/'cmd.exe');child.args[0]=child.executable
        rejects(lambda:m.register_children(root,owner));assert not terminated
        root,python,child,owner,guard=fixture();m.register_children(root,owner);python.created+=1
        rejects(lambda:m.verified(owner['processes'][-1],owner));assert not terminated
        root,python,child,owner,guard=fixture();m.register_children(root,owner);child.parent_id=100
        rejects(lambda:m.verified(owner['processes'][-1],owner));assert not terminated
        checks.append('lookalike exe, changed direct parent FILETIME or reparenting inside root tree rejected')
        root,python,child,owner,guard=fixture();m.register_children(root,owner);child.created+=1
        rejects(lambda:m.register_children(root,owner));assert not terminated and m.OWNER.exists()
        root,python,child,owner,guard=fixture();m.register_children(root,owner);owner['StackRunId']='b'*32
        rejects(lambda:m.verified(owner['processes'][-1],owner));assert not terminated
        checks.append('child FILETIME/PID reuse and StackRunId mutation rejected, owner preserved')
        root,python,child,owner,guard=fixture()
        with patch.object(Handle,'ticks',lambda self:self.p.created+1):
            rejects(lambda:m.register_children(root,owner))
        assert len(owner['processes'])==2 and not terminated
        checks.append('creation FILETIME from retained native handle must match initial live identity')
        root,python,child,owner,guard=fixture();m.INITIALIZATION_AUXILIARY=None
        rejects(lambda:m.register_children(root,owner));assert not terminated
        root,python,child,owner,guard=fixture()
        with patch.object(m,'ENTRY',ROOT/'scripts/stt-run.py'):rejects(lambda:guard.verify(child,owner,True))
        checks.append('non-TTS service never receives exception')
        root,python,child,owner,guard=fixture();procs[103]=Process(103,'unknown.exe',['unknown.exe'],102)
        rejects(lambda:m.register_children(root,owner));assert not terminated and len(owner['processes'])==2
        checks.append('unregistered grandchild under otherwise exact probe rejected')
        root,python,child,owner,guard=fixture();m.register_children(root,owner);old=child;child.alive=False
        guard.refresh(owner)
        procs[102]=Process(102,old.executable,old.args,101);procs[102].created+=20
        rejects(lambda:m.register_children(root,owner));assert not terminated
        checks.append('original retained handle proves exited instance; reused PID is not trusted')
        root,python,child,owner,guard=fixture()
        original_identity=identity
        def vanished(p):
            if p.pid==102:raise m.psutil.NoSuchProcess(p.pid)
            return original_identity(p)
        with patch.object(m,'identity',vanished):rejects(lambda:m.register_children(root,owner))
        assert not owner.get('tts_initialization_auxiliaries') and not terminated
        checks.append('unattested transient exit rejected, never auto-trusted')
        root,python,child,owner,guard=fixture();m.register_children(root,owner)
        child.alive=False;guard.refresh(owner);guard.finish(owner)
        procs[103]=Process(103,child.executable,child.args,101)
        rejects(lambda:m.register_children(root,owner));assert not terminated
        checks.append('new probe after final READY rejected')
        root,python,child,owner,guard=fixture();m.register_children(root,owner);m.stop()
        assert set(terminated)=={100,101,102} and not m.OWNER.exists()
        checks.append('normal/failed-initialization cleanup uses exact same parent/identity checks and stops only registered tree')
# Existing Stage7H policy/identity/rollback suite, output relocated; source/history untouched.
directory=OUT/'stage7h-regression';directory.mkdir(exist_ok=True)
source=(ROOT/'scripts/stage7h-check-contracts.py').read_text(encoding='utf-8')
source=source.replace("OUT=ROOT/'runtime/stage7h/offline'",'OUT=Path('+repr(str(directory))+')')
exec(compile(source,str(ROOT/'scripts/stage7h-check-contracts.py'),'exec'),{'__file__':str(ROOT/'scripts/stage7h-check-contracts.py'),'__name__':'stage7i_regression'})
checks.append('Stage7H RAM/commit/paging/GPU, conhost, 1.7B, retired profiles and rollback regression PASS')
for path in ['scripts/tts-sox-identity.py','scripts/tts-service.py','scripts/livetalking-service.py','scripts/stage7i-check-contracts.py']:
    ast.parse((ROOT/path).read_text(encoding='utf-8-sig'))
(OUT/'contracts.json').write_text(json.dumps(dict(status='PASS',checks=checks,model_loads=0,real_inference_requests=0),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS',checks=checks),ensure_ascii=False,indent=2))
