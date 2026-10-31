"""Model-free conhost identity and cleanup contracts; no real process operations."""
import copy,importlib.util,json,os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runtime/stage7b-conhost'
s=importlib.util.spec_from_file_location('tts_contract',ROOT/'scripts/tts-service.py');tts=importlib.util.module_from_spec(s);s.loader.exec_module(tts);m=tts.manager
console=str(Path(os.environ['SystemRoot'],'System32','conhost.exe'))
checks=[]
def rejects(call):
    try:call()
    except RuntimeError:pass
    else:raise AssertionError('Identity conflict was accepted')
class Process:
    def __init__(self,pid,exe,cmd,parent=None):
        self.pid=pid;self.executable=exe;self.command=cmd;self.parent_id=parent;self.created=pid*1000;self.alive=True
    def exe(self):return self.executable
    def cmdline(self):return self.command.copy()
    def ppid(self):return self.parent_id
    def parent(self):return lookup(self.parent_id) if self.parent_id else None
    def children(self,recursive=False):
        direct=[p for p in processes.values() if p.alive and p.parent_id==self.pid]
        return direct+([c for p in direct for c in p.children(True)] if recursive else [])
    def terminate(self):terminated.append(self.pid);self.alive=False
def identity(p):return dict(pid=p.pid,creation_filetime_ticks=p.created,exe=p.exe(),cmdline=p.cmdline())
def lookup(pid):
    if pid not in processes or not processes[pid].alive:raise m.psutil.NoSuchProcess(pid)
    return processes[pid]
def fixture():
    global processes,terminated
    terminated=[]
    root=Process(100,str(m.PYTHON),[str(m.PYTHON),'-B','-s',str(m.ENTRY)])
    host=Process(101,console,[console,'0xffffffff','-ForceV1'],100)
    python=Process(102,str(Path(sys._base_executable)),[str(Path(sys._base_executable)),'-B','-s',str(m.ENTRY)],100)
    processes={p.pid:p for p in [root,host,python]}
    record=dict(root=str(ROOT),entry=str(m.ENTRY),processes=[identity(root)])
    m.write('owner.json',record);m.register_children(root,record)
    return root,host,python,record
with tempfile.TemporaryDirectory(dir=OUT) as folder:
    temp=Path(folder).resolve();assert temp.is_relative_to(OUT)
    m.RUNTIME=temp;m.OWNER=temp/'owner.json'
    with patch.object(m,'identity',side_effect=identity),patch.object(m.psutil,'Process',side_effect=lookup),patch.object(m.psutil,'pid_exists',side_effect=lambda pid:pid in processes and processes[pid].alive),patch.object(m.psutil,'wait_procs',side_effect=lambda procs,timeout:([p for p in procs if not p.alive],[p for p in procs if p.alive])),patch.object(m,'resources',return_value=dict(mock=True)),patch.object(m,'listeners',return_value=[]):
        root,host,python,record=fixture()
        host.command=[console,'0x4'];m.register_children(root,record)
        host.command=[console,'0xffffffff','-ForceV1'];m.verified(record['processes'][1],record)
        assert len(record['console_startup_transitions'])==2
        assert all(all(e['checks'].values()) for e in record['console_startup_transitions'])
        audit=copy.deepcopy(record['console_startup_transitions'])
        host.command=[console,'0x4'];m.stop()
        assert not m.OWNER.exists() and set(terminated)=={100,101,102}
        checks.append('both exact transitions accepted with complete identity/parent/tree audit; normal stop uses same rules')
        for field,value in [('pid',999),('creation_filetime_ticks',123),('exe',str(ROOT/'conhost.exe')),('cmdline',[str(ROOT/'other.exe'),'0x4']),('cmdline',[console,'0x8']),('cmdline',[console,'0x4','extra'])]:
            before=dict(pid=101,creation_filetime_ticks=101000,exe=console,cmdline=[console,'0xffffffff','-ForceV1'])
            after=dict(before,cmdline=[console,'0x4']);after[field]=value
            assert not m.is_console_transition(before,after),(field,value)
        checks.append('changed PID/FILETIME/exe/argv0 and unknown/extra arguments rejected')
        root,host,python,record=fixture();saved=copy.deepcopy(record)
        host.command=[console,'0x4'];host.created+=1
        rejects(lambda:m.register_children(root,record));assert record==saved and not terminated and m.OWNER.exists()
        checks.append('PID reuse/creation conflict preserves original owner and rejection evidence')
        root,host,python,record=fixture();root.created+=1
        rejects(m.stop);assert not terminated and m.OWNER.exists()
        root,host,python,record=fixture();host.executable=str(ROOT/'conhost.exe')
        rejects(m.stop);assert not terminated and m.OWNER.exists()
        checks.append('root creation conflict or non-System32 lookalike blocks stop without killing or replacing owner')
        root,host,python,record=fixture();host.command=[console,'0x4'];host.parent_id=102
        rejects(lambda:m.register_children(root,record));assert not terminated and m.OWNER.exists()
        checks.append('changed parent inside same root tree remains rejected')
        root,host,python,record=fixture();host.command=[console,'0x4'];host.parent_id=999
        rejects(lambda:m.verified(record['processes'][1],record));assert not terminated
        checks.append('leaving owned tree rejected even when process name/PID/exe match')
        for exe,cmd in [(str(ROOT/'unknown.exe'),['unknown']), (str(Path(sys._base_executable)),[str(Path(sys._base_executable)),'-c','unknown'])]:
            root,host,python,record=fixture()
            processes[999]=Process(999,exe,cmd,100)
            rejects(m.stop)
            assert not terminated and m.OWNER.exists()
            assert len(json.loads(m.OWNER.read_text())['processes'])==3
        checks.append('unknown executable or Python command blocks cleanup, is not adopted, and causes no termination')
        root,host,python,record=fixture();host.command=[console,'0x4']
        try:raise RuntimeError('simulated startup failure')
        except RuntimeError:m.stop()
        assert not m.OWNER.exists() and set(terminated)=={100,101,102}
        checks.append('startup exception cleanup accepts legal reverse transition and reclaims only owned tree')
        root,host,python,record=fixture();record.pop('console_parents');host.command=[console,'0x4']
        rejects(lambda:m.register_children(root,record));assert not terminated
        checks.append('legacy/missing parent baseline cannot authorize a transition')
        # Python/Node/llama identities do not receive the conhost exception.
        root,host,python,record=fixture();python.command.append('--changed')
        rejects(lambda:m.verified(record['processes'][2],record));assert not terminated
        for name in ['node.exe','llama-server.exe']:
            before=dict(pid=300,creation_filetime_ticks=300000,exe=str(ROOT/name),cmdline=[name,'0x4'])
            assert not m.is_console_transition(before,dict(before,cmdline=[name,'0xffffffff','-ForceV1']))
        checks.append('Python, Node and llama command identity exceptions remain forbidden')
before=(OUT/'livetalking-service.before.py').read_text(encoding='utf-8-sig')
after=(ROOT/'scripts/livetalking-service.py').read_text(encoding='utf-8-sig')
assert before[before.index('def start():'):]==after[after.index('def start():'):]
assert before[before.index('def preflight():'):before.index('def stop():')]==after[after.index('def preflight():'):after.index('def stop():')]
checks.append('shared start timing/preflight and RAM/VRAM gates remain byte-for-byte unchanged')
(OUT/'conhost-contracts.json').write_text(json.dumps(dict(status='PASS',model_loads=0,real_process_operations=0,checks=checks,example_audit=audit),indent=2),encoding='utf-8')
print('Conhost deterministic contracts PASS:',len(checks))
