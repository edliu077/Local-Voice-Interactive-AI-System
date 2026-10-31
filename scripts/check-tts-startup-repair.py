"""Model-free repair regression, with short owned test helpers only."""
import copy,importlib.util,json,os,subprocess,sys,tempfile,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runtime/repair-20261026-tts-owner/offline';OUT.mkdir(parents=True,exist_ok=True)
sys.stdout.reconfigure(encoding='utf-8')
def load(name,path):
    s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def rejected(call):
    try:call()
    except (RuntimeError,FileNotFoundError):pass
    else:raise AssertionError('Unsafe reconciliation accepted')
checks=[];receipts=load('receipt_contract','scripts/stack-stop-receipts.py')
with tempfile.TemporaryDirectory(dir=OUT,prefix='receipts-') as temp:
    root=Path(temp);folder=root/'runtime/tts-service';folder.mkdir(parents=True)
    ident=dict(pid=42424242,creation_filetime_ticks=134373000000000000,exe='C:\\verified\\python.exe',cmdline=['C:\\verified\\python.exe','-B','-s',str(root/'scripts/tts-run.py')])
    owner=dict(root=str(root),entry=str(root/'scripts/tts-run.py'),processes=[ident],StackRunId='f'*32)
    archive=folder/'stopped-test.json';archive.write_text(json.dumps(owner),encoding='utf-8')
    receipt=dict(status='STOPPED',time=time.time(),process_ids=[ident['pid']],owner_archive=str(archive))
    record=dict(run_id='f'*32,before=dict(time=0))
    def save():(folder/'stop-result.json').write_text(json.dumps(receipt),encoding='utf-8')
    save()
    def absent(pid):raise receipts.psutil.NoSuchProcess(pid)
    with patch.object(receipts.psutil,'Process',absent):
        proof=receipts.prove(root,'tts',record,receipts.fingerprint(owner),lambda p:None)
        assert len(proof['exits'])==1
        for field,value in [('StackRunId','x'*32),('root','foreign'),('entry','foreign')]:
            bad=copy.deepcopy(owner);bad[field]=value;archive.write_text(json.dumps(bad),encoding='utf-8')
            rejected(lambda:receipts.prove(root,'tts',record,receipts.fingerprint(owner),lambda p:None))
        archive.write_text(json.dumps(owner),encoding='utf-8')
        for field,value in [('status','STARTING'),('process_ids',[1]),('time',-1)]:
            old=receipt[field];receipt[field]=value;save();rejected(lambda:receipts.prove(root,'tts',record,None,lambda p:None));receipt[field]=old
        save()
        (folder/'owner.json').write_text('{}');rejected(lambda:receipts.prove(root,'tts',record,None,lambda p:None));(folder/'owner.json').unlink()
        bad=copy.deepcopy(receipts.fingerprint(owner));bad['process']['creation_filetime_ticks']+=1
        rejected(lambda:receipts.prove(root,'tts',record,bad,lambda p:None))
    with patch.object(receipts.psutil,'Process',lambda pid:SimpleNamespace(pid=pid)):
        rejected(lambda:receipts.prove(root,'tts',record,None,lambda p:ident))
        result=receipts.prove(root,'tts',record,None,lambda p:dict(ident,creation_filetime_ticks=ident['creation_filetime_ticks']+1))
        assert 'PID_REUSED_UNTOUCHED' in result['exits'][0]['state']
    checks.append('same-run STOPPED receipt + full root/native identity accepted; foreign run/root/entry, malformed PID set/time, active owner, live instance and changed fingerprint rejected; reused PID untouched')
    # Real coordinator partial-start rollback, no real PIDs or ports.
    m=load('receipt_stack','scripts/rebuild-system.py');path=folder/'owner.json'
    calls=[]
    def fake(name,action):
        calls.append((name,action))
        if action=='preflight':return json.dumps(dict(status='READY'))
        if action=='start':
            owner['StackRunId']=stack.run_id;archive.write_text(json.dumps(owner),encoding='utf-8');receipt['time']=time.time();save()
            raise RuntimeError('simulated failed start with completed self-cleanup')
        raise AssertionError('Already-stopped service should not be stopped/adopted again')
    with patch.multiple(m,ROOT=root,RUNTIME=root/'runtime/stack',OWNER=root/'runtime/stack/owner.json',ORDER=['tts'],RECORDS={'tts':path}),patch.object(receipts.psutil,'Process',absent):
        stack=m.Stack(fake,lambda:dict(time=0,available_ram_bytes=9*1024**3,commit_headroom_bytes=20*1024**3,page_size_bytes=4096,pages_output_per_second=0));stack.clean_start=lambda:None
        try:stack.start()
        except RuntimeError:pass
        else:raise AssertionError('Simulated startup succeeded')
        assert not m.OWNER.exists()
        result=json.loads(next((m.RUNTIME/'runs').glob('*.json')).read_text(encoding='utf-8'))
        assert result['status']=='STOPPED' and result['cleanup_errors']==[] and result['validated_stop_receipts']
    checks.append('partial-start self-cleanup receipt reconciles automatically; original error preserved, no duplicate stop or process takeover')
# Preserve the entire prior strict identity/RAM/cleanup suite in this repair folder.
prior=OUT/'prior-regression';prior.mkdir(exist_ok=True)
source=(ROOT/'scripts/stage7i-check-contracts.py').read_text(encoding='utf-8').replace("OUT=ROOT/'runtime/stage7i/offline'",'OUT=Path('+repr(str(prior))+')')
exec(compile(source,str(ROOT/'scripts/stage7i-check-contracts.py'),'exec'),{'__file__':str(ROOT/'scripts/stage7i-check-contracts.py'),'__name__':'repair_regression'})
checks.append('all Stage7I legal/illegal SoX/parent/FILETIME/run/PID-reuse/transient/descendant cases and Stage7H RAM/commit/paging/GPU/cleanup cases PASS')
native=load('native_aux','scripts/tts-sox-identity.py')
process=subprocess.Popen([sys.executable,'-B','-s','-c','import time;time.sleep(.3)'],creationflags=subprocess.CREATE_NO_WINDOW)
handle=native.HeldProcess(process.pid);ticks=handle.ticks();process.wait(timeout=10)
assert handle.exit_code()==0 and handle.ticks()==ticks;handle.close()
checks.append('real short helper exits before first delayed poll; original held handle preserves native creation identity and exit code')
logger=load('manual_log','scripts/manual-rebuild.py')
code=logger.run([sys.executable,'-B','-s','-c',"import sys; print('test-output'); print('test-error',file=sys.stderr);sys.exit(7)"],OUT/'manual-log-test')
assert code==7 and 'test-output' in (OUT/'manual-log-test/stdout.log').read_text() and 'test-error' in (OUT/'manual-log-test/stderr.log').read_text()
assert json.loads((OUT/'manual-log-test/result.json').read_text())['returncode']==7
checks.append('real failing no-model helper retains stdout/stderr/exit code and is echoed to console')
(OUT/'contracts.json').write_text(json.dumps(dict(status='PASS',checks=checks,models_loaded=0,model_requests=0),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS',checks=checks),ensure_ascii=False,indent=2))
