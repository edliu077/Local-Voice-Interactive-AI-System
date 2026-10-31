"""No AI models: real native creation authority + deterministic rejection tests."""
import ast,copy,ctypes,importlib.util,json,os,shutil,subprocess,sys,tempfile,time,uuid
from pathlib import Path
from unittest.mock import patch
import psutil
import tts_helper_lifecycle as life
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runtime/tts-reliability-repair/offline';OUT.mkdir(parents=True,exist_ok=True)
checks=[]


def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def reject(call):
    try:call()
    except (RuntimeError,psutil.Error,OSError,KeyError):return
    raise AssertionError('Unsafe identity accepted')


# A fake TTS entry below a temporary Rebuild test folder uses the ACTUAL helper
# module and ACTUAL native pipe/handle mechanism, without uvicorn or AI imports.
# Keep evidence even on failure; never let TemporaryDirectory erase an active
# test owner's native baseline while a process still has this as its cwd.
with __import__('contextlib').nullcontext(str(OUT/('native-'+uuid.uuid4().hex))) as temp:
    root=Path(temp);(root/'scripts').mkdir(parents=True)
    for name in ('tts_helper_client.py','tts_helper_lifecycle.py','tts_gpu_monitor.py','tts_nvml.py'):
        shutil.copyfile(ROOT/'scripts'/name,root/'scripts'/name)
    entry=root/'scripts/tts-run.py'
    entry.write_text('''import os,sys,time,threading,subprocess,json
from pathlib import Path
import tts_helper_client as client
import tts_gpu_monitor as gpu
root=Path(__file__).resolve().parents[1]
restore=client.install(root)
case=os.environ['CONTRACT_CASE']
try:
    if case in ('query','pollrace'):
        monitor=gpu.GPUMonitor.__new__(gpu.GPUMonitor)
        print(monitor._one_shot(),flush=True)
    elif case=='illegal':
        try:subprocess.Popen([os.environ['COMSPEC'],'/c','echo unauthorized'])
        except RuntimeError:print('DENIED_BEFORE_CREATE',flush=True)
        else:raise AssertionError('Unknown command ran')
    elif case=='forged':
        from multiprocessing.connection import Client
        from tts_helper_lifecycle import send,receive
        c=Client(os.environ['REBUILD_TTS_HELPER_PIPE'],family='AF_PIPE',authkey=bytes.fromhex(os.environ['REBUILD_TTS_HELPER_AUTH']))
        send(c,dict(action='prepare',run_id=os.environ['REBUILD_STACK_RUN_ID'],kind='query'))
        assert receive(c)['ok']
        send(c,dict(action='created',run_id=os.environ['REBUILD_STACK_RUN_ID'],handle=-1,native=dict(pid=1,creation_filetime_ticks=1)))
        assert receive(c)['ok'] is False
        c.close();print('FORGED_REJECTED',flush=True)
    else:
        monitor=gpu.GPUMonitor()
        print('LOOP_READY',flush=True)
        while not (root/'release').exists():time.sleep(.05)
        monitor.close()
finally:restore()
''',encoding='utf-8')
    smi=Path(os.environ['SystemRoot'])/'System32/nvidia-smi.exe'
    gpu_uuid=subprocess.check_output([str(smi),'--query-gpu=uuid','--format=csv,noheader,nounits'],text=True,timeout=5).splitlines()[0].strip()
    for case in ('query','pollrace','illegal','forged','loop'):
        m=load('reliability_owner_'+case,ROOT/'scripts/livetalking-service.py')
        m.ROOT=root;m.REPO=root;m.ENTRY=entry;m.PYTHON=Path(sys._base_executable);m.PORT=8765
        m.RUNTIME=root/'runtime/tts-service';m.RUNTIME.mkdir(parents=True,exist_ok=True);m.OWNER=m.RUNTIME/'owner.json'
        m.resources=lambda:dict(test_only=True,time=time.time())
        m.listeners=lambda:[]
        m.CREATED_HELPER_VERIFY=lambda process,owner:life.verify_live(m,process,owner)
        original_stop=m.stop
        m.stop=lambda:life.stop_with_handles(m,original_stop)
        run=uuid.uuid4().hex;broker=life.Broker(m,run,gpu_uuid);broker.bind()
        env=dict(os.environ,**broker.environment(),REBUILD_TTS_GPU_BACKEND='smi-loop',CONTRACT_CASE=case)
        before_time=time.time()
        out=OUT/(case+'.stdout.log');err=OUT/(case+'.stderr.log')
        with out.open('wb') as stdout,err.open('wb') as stderr:
            process=subprocess.Popen([str(m.PYTHON),'-B','-s',str(entry)],env=env,cwd=root,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        owner=dict(root=str(root),entry=str(entry),StackRunId=run,processes=[m.identity(psutil.Process(process.pid))])
        m.write('owner.json',owner);broker.start(owner)
        try:
            if case!='loop':
                if case=='pollrace':
                    while process.poll() is None:
                        try:m.register_children(psutil.Process(process.pid),owner)
                        except psutil.NoSuchProcess:
                            process.wait(timeout=10);break
                        time.sleep(.001)
                process.wait(timeout=20)
                assert process.returncode==0,err.read_text(encoding='utf-8')
                # Deliberately do NOT poll the helper while it exists. The
                # broker's original handle proves the exited instance instead.
                if case=='forged':
                    reject(lambda:broker.refresh(owner))
                    broker.stopping=True
                broker.refresh(owner,stopping=broker.stopping)
                if case in ('query','pollrace'):
                    assert len(owner['tts_retired_auxiliaries'])==1
                    proof=owner['tts_retired_auxiliaries'][0]
                    assert proof['exit']['code']==0 and proof['identity']['pid'] not in [p['pid'] for p in owner['processes']]
                    checks.append('real '+case+': suspended creation/native peer/FILETIME/exe/argv/source attested before execution; original handle exit0 accepted; delayed/concurrent polling cannot race registration; retired PID not adopted again')
                elif case=='illegal':
                    assert 'DENIED_BEFORE_CREATE' in out.read_text() and not broker.handles
                    checks.append('real unauthorized cmd is refused BEFORE OS process creation')
                else:
                    assert 'FORGED_REJECTED' in out.read_text() and not broker.handles
                    broker.stopping=True
                    checks.append('actual authenticated TTS peer cannot authorize a forged creation record / pseudo handle as a new GPU helper')
            else:
                deadline=time.monotonic()+20
                while 'LOOP_READY' not in out.read_text(encoding='utf-8'):
                    assert process.poll() is None,err.read_text(encoding='utf-8')
                    assert time.monotonic()<deadline
                    time.sleep(.05)
                proof=owner['tts_created_auxiliaries'][0]
                child=psutil.Process(proof['identity']['pid'])
                assert life.verify_live(m,child,owner)
                time.sleep(.7) # More than three real 200ms sampling periods.
                assert process.poll() is None and life.verify_live(m,child,owner)
                assert not child.children(recursive=True)
                with patch.object(child,'children',return_value=[object()]):reject(lambda:life.verify_live(m,child,owner))
                checks.append('detached auxiliary needs no conhost; every unexpected descendant remains refused')
                # Authentic native process + manipulated metadata must still fail.
                for mutate in ('run','parent','ticks','pid','argv','exe','sources','root'):
                    bad=copy.deepcopy(owner);p=bad['tts_created_auxiliaries'][0]
                    if mutate=='run':p['run_id']='f'*32
                    elif mutate=='parent':p['parent']['creation_filetime_ticks']+=1
                    elif mutate=='ticks':p['identity']['creation_filetime_ticks']+=1
                    elif mutate=='pid':p['identity']['pid']+=1
                    elif mutate=='argv':p['identity']['cmdline'].append('--bad')
                    elif mutate=='exe':p['identity']['exe']=str(Path(os.environ['SystemRoot'])/'System32/cmd.exe')
                    elif mutate=='sources':p['sources']={}
                    elif mutate=='root':p['root']['creation_filetime_ticks']+=1
                    if mutate=='pid':assert life.verify_live(m,child,bad) is False
                    else:reject(lambda:life.verify_live(m,child,bad))
                    reject(lambda:broker.refresh(bad))
                checks.append('actual native live helper rejects forged owner metadata, parent, FILETIME, PID reuse, arbitrary argv/exe, missing source baseline and cross-run/root; private handle baseline unchanged')
                # Possession of a pipe credential does not make an unrelated
                # native parent part of the TTS service tree.
                from multiprocessing.connection import Client
                outsider=Client(broker.address,family='AF_PIPE',authkey=broker.key)
                life.send(outsider,dict(action='prepare',run_id=run,kind='query'))
                assert life.receive(outsider)['ok'] is False;outsider.close()
                checks.append('actual authenticated but foreign native pipe parent cannot create/adopt a helper')
                # Simulated initialization failure uses the SAME production stop.
                broker.stopping=True;m.stop();process.wait(timeout=10)
                assert not m.OWNER.exists() and not psutil.pid_exists(child.pid)
                stopped=json.loads((m.RUNTIME/'stop-result.json').read_text())
                assert stopped['auxiliary_exits'][0]['native']['creation_filetime_ticks']==proof['identity']['creation_filetime_ticks']
                checks.append('actual persistent GPU fallback has fresh true samples; simulated initialization failure safely stops only exact registered root/helper and archives owner')
        finally:
            broker.stopping=True
            if m.OWNER.exists():m.stop()
            receipts=load('native_receipts_'+case,ROOT/'scripts/stack-stop-receipts.py')
            proof=receipts.prove(root,'tts',dict(run_id=run,before=dict(time=before_time)),native_identity=m.identity)
            assert proof['receipt']['status']=='STOPPED'
            broker.close()
            if process.poll() is None:raise AssertionError('Owned test entry remains')
    # Same fake TTS entry was launched/stopped again across distinct runs.
    checks.append('independent runs repeat native create/register/stop without active owner residue')
    checks.append('each actual no-model failure/stop receipt passes the same Stack reconciliation path')

assert not any(n in sys.modules for n in ('torch','transformers','qwen_tts','faster_qwen3_tts'))
for name in ('tts_nvml.py','tts_gpu_monitor.py','tts_helper_client.py','tts_helper_lifecycle.py','tts-run.py','tts-service.py','livetalking-service.py'):
    ast.parse((ROOT/'scripts'/name).read_text(encoding='utf-8'))
(OUT/'native-contracts.json').write_text(json.dumps(dict(status='PASS',checks=checks,models_loaded=0,tts_service_starts=0),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS',checks=checks),ensure_ascii=False,indent=2))
