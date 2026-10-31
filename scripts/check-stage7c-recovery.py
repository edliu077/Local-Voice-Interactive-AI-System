"""No models: ownership, coordinator registration/rollback and Windows pipe EOF."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runtime/stage7c-recovery'
spec=importlib.util.spec_from_file_location('coordinator',ROOT/'scripts/rebuild-system.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
checks=[]

def stack_case(directory,mode):
    records={name:directory/name/'owner.json' for name in ['frontend','llm']}
    events=[]
    def fake(name,action):
        events.append((name,action))
        if action=='preflight':return json.dumps(dict(status='READY'))
        path=records[name]
        if action=='start':
            r=json.loads((directory/'stack/owner.json').read_text())
            assert name not in [x['service'] for x in r['started']]
            path.parent.mkdir(exist_ok=True)
            record=dict(root=str(directory),entry='fake-service.py',processes=[dict(pid=1234,exe='fake',creation_filetime_ticks=123)],StackRunId=stack.run_id)
            if mode=='foreign' and name=='llm':record['StackRunId']='foreign-run'
            path.write_text(json.dumps(record))
            if name=='llm' and mode=='missing':
                path.unlink();raise RuntimeError('simulated failure before durable owner')
            if name=='llm' and mode in ['timeout','foreign','cleanupretry']:raise TimeoutError('simulated partial launch timeout')
            return 'READY'
        if action=='status':
            r=json.loads((directory/'stack/owner.json').read_text())
            assert name not in [x['service'] for x in r['started']]
            if mode=='badhealth' and name=='llm':raise RuntimeError('simulated identity/health rejection')
            if mode=='mutated' and name=='llm':
                r=json.loads(path.read_text());r['processes'][0]['pid']=9876;path.write_text(json.dumps(r))
                raise RuntimeError('simulated real identity conflict')
            return 'Owned ready'
        if action=='stop':
            if mode=='cleanupretry' and name=='frontend' and events.count(('frontend','stop'))==1:raise RuntimeError('simulated first cleanup refusal')
            path.unlink();return 'verified fake stop'
        raise AssertionError(action)
    with patch.multiple(m,ROOT=directory,RUNTIME=directory/'stack',OWNER=directory/'stack/owner.json',ORDER=['frontend','llm'],RECORDS=records):
        stack=m.Stack(fake,lambda:dict(available_ram_bytes=9*1024**3))
        stack.clean_start=lambda:None
        try:stack.start()
        except RuntimeError:
            assert mode!='success'
        else:
            assert mode=='success'
            r=m.read(m.OWNER)
            assert [x['service'] for x in r['started']]==['frontend','llm'] and not r.get('pending')
            stack.stop()
        if mode=='cleanupretry':
            assert m.OWNER.exists() and not records['llm'].exists()
            assert m.read(m.OWNER)['recovered_pending'][0]['stopped']
            stack.stop()
            assert not m.OWNER.exists() and not records['frontend'].exists()
            assert events.count(('llm','stop'))==1
        elif mode in ['success','timeout','badhealth']:
            assert not m.OWNER.exists() and not any(p.exists() for p in records.values())
            assert [n for n,a in events if a=='stop']==['llm','frontend']
            archive=m.read(next((directory/'stack/runs').glob('*.json')))
            if mode!='success':assert archive['recovered_pending'][0]['service']=='llm'
        else:
            assert m.OWNER.exists() and (records['llm'].exists() or mode=='missing')
            assert ('llm','stop') not in events
            assert m.read(m.OWNER)['cleanup_errors']
    checks.append('coordinator '+mode)

def pipe_contract(directory):
    settings=m.read(ROOT/'config/windows-runtime.json')
    helper=directory/'sleep-helper.py'
    helper.write_text('import time\nprint("helper",flush=True)\ntime.sleep(3)\n')
    script=directory/'launch-helper.ps1'
    # Match the real native PowerShell launch shape; no model, port or network.
    script.write_text("$ErrorActionPreference='Stop'\n$p=Start-Process -FilePath '"+sys._base_executable+"' -ArgumentList @('-B','-s','\""+str(helper)+"\"') -WindowStyle Hidden -RedirectStandardOutput '"+str(directory/'helper.stdout.log')+"' -RedirectStandardError '"+str(directory/'helper.stderr.log')+"' -PassThru\nWrite-Output $p.Id\nWrite-Output 'READY'\n")
    args=[settings['powershell'],'-NoProfile','-File',str(script)]
    parent=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
    parent.wait(timeout=10)
    held=False
    try:stdout,stderr=parent.communicate(timeout=.2)
    except subprocess.TimeoutExpired:
        held=True;stdout,stderr=parent.communicate(timeout=10)
    assert parent.returncode==0 and b'READY' in stdout,stderr
    # This is a real Windows reproduction, not a mocked assertion about pipes.
    result=dict(powershell_exited=True,pipe_eof_delayed_by_live_helper=held)
    (OUT/'pipe-reproduction.json').write_text(json.dumps(result,indent=2))
    assert held,'Pipe inheritance was not reproduced; do not claim confirmed'
    checks.append('real Windows: exited PowerShell still holds PIPE EOF via live helper')
    begin=time.monotonic()
    text=m.run_logged(args,directory/'file-call',10,os.environ.copy(),lambda p,i:(_ for _ in ()).throw(AssertionError('unexpected timeout')))
    elapsed=time.monotonic()-begin
    child_pid=int(text.splitlines()[0])
    child=m.psutil.Process(child_pid)
    assert child.is_running() and elapsed<3
    result.update(file_call_seconds=elapsed,file_call_returns_while_helper_alive=True)
    (OUT/'pipe-reproduction.json').write_text(json.dumps(result,indent=2))
    child.wait(timeout=10)
    checks.append('real file-backed call returns before inherited-handle helper exits')
    args=[sys._base_executable,'-B','-s','-c','import time; time.sleep(10)']
    terminated=[]
    def on_timeout(process,identity):
        m.terminate_exact_process(m.psutil.Process(process.pid),identity)
        process.wait(timeout=5);terminated.append(process.pid)
    try:m.run_logged(args,directory/'timeout-call',.5,os.environ.copy(),on_timeout)
    except TimeoutError:pass
    else:raise AssertionError('Timeout accepted')
    assert len(terminated)==1 and not m.psutil.pid_exists(terminated[0])
    checks.append('bounded invocation timeout terminates exact native FILETIME dummy only')
    # Real no-model PowerShell -> Python manager timeout, matching wrapper argv.
    fake_root=directory/'fake-root';(fake_root/'scripts').mkdir(parents=True)
    manager=fake_root/'scripts/frontend-service.py';manager.write_text('import time; time.sleep(10)')
    wrapper=fake_root/'wrapper.ps1'
    wrapper.write_text("& '"+sys._base_executable+"' -B -s '"+str(manager)+"' start\n")
    identity_spec=importlib.util.spec_from_file_location('native_identity',ROOT/'scripts/livetalking-service.py')
    native=importlib.util.module_from_spec(identity_spec);identity_spec.loader.exec_module(native)
    def native_identity(p):return dict(native.identity(p),parent_pid=p.ppid())
    timed_ids=[]
    def stop_managers(p,identity):
        timed_ids.extend([p.pid]+[c.pid for c in m.psutil.Process(p.pid).children(recursive=True)])
        m.terminate_management_call(p,'frontend','start',identity)
    with patch.object(m,'ROOT',fake_root),patch.object(m,'process_identity',native_identity):
        try:m.run_logged([settings['powershell'],'-NoProfile','-File',str(wrapper)],directory/'manager-timeout',1.5,os.environ.copy(),stop_managers)
        except TimeoutError:pass
        else:raise AssertionError('Manager timeout accepted')
    assert timed_ids and not any(m.psutil.pid_exists(i) for i in timed_ids)
    checks.append('real exact-identity PowerShell/Python manager timeout reclaimed without model')

def owner_token_contract(directory):
    identity_spec=importlib.util.spec_from_file_location('native_owner',ROOT/'scripts/livetalking-service.py')
    native=importlib.util.module_from_spec(identity_spec);identity_spec.loader.exec_module(native)
    with patch.object(native,'RUNTIME',directory),patch.dict(os.environ,REBUILD_STACK_RUN_ID='contract-token'):
        native.write('owner.json',dict(root=str(ROOT),entry='fake',processes=[]))
    assert json.loads((directory/'owner.json').read_text())['StackRunId']=='contract-token'
    checks.append('shared owner write carries exact stack run token')

with tempfile.TemporaryDirectory(prefix='contracts-',dir=OUT) as temp:
    base=Path(temp)
    for mode in ['success','timeout','badhealth','foreign','mutated','missing','cleanupretry']:
        directory=base/mode;directory.mkdir();stack_case(directory,mode)
    pipe_dir=base/'pipe';pipe_dir.mkdir();pipe_contract(pipe_dir)
    token_dir=base/'token';token_dir.mkdir();owner_token_contract(token_dir)
result=dict(status='PASS',checks=checks,models_loaded=0)
(OUT/'coordinator-contracts.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
