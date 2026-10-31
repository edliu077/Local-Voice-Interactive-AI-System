"""Stage 5 isolated TTS manager; shares exact owner validation, not LLM control."""
import argparse
import importlib.util
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import os
import uuid
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('tts_owner_manager',ROOT/'scripts/livetalking-service.py')
manager=importlib.util.module_from_spec(spec);spec.loader.exec_module(manager)
manager.REPO=ROOT
manager.RUNTIME=ROOT/'runtime/tts-service'
manager.OWNER=manager.RUNTIME/'owner.json'
manager.ENTRY=ROOT/'scripts/tts-run.py'
manager.PYTHON=ROOT/'.venv-tts/Scripts/python.exe'
manager.PORT=8765
manager.MINIMUM_GPU_FREE_MIB=5120
manager.MINIMUM_RAM_BYTES=manager.resource_policy.POLICY['startup_ram_bytes']['tts']
manager.HEALTH_PATH='/health'
manager.HEALTH_STATUS='ready'
manager.SERVICE_NAME='Rebuild Qwen3-TTS'
_smi=shutil.which('nvidia-smi')
if not _smi:raise RuntimeError('nvidia-smi missing')
# GPU auxiliaries require creation-time authority, not a command-only whitelist.
manager.ALLOWED_AUXILIARY={}
import tts_helper_lifecycle as helper_lifecycle
manager.CREATED_HELPER_VERIFY=lambda process,owner:helper_lifecycle.verify_live(manager,process,owner)
_original_stop=manager.stop
manager.stop=lambda:helper_lifecycle.stop_with_handles(manager,_original_stop)
config=json.loads((ROOT/'config/rebuild.json').read_text())
manager.REQUIRED_INPUTS=(Path(config['tts_model'])/'model.safetensors',ROOT/'assets/voice-clone/reference-short.wav',ROOT/'assets/voice-clone/reference-short.txt')
sox_spec=importlib.util.spec_from_file_location('tts_sox_identity',ROOT/'scripts/tts-sox-identity.py')
sox_module=importlib.util.module_from_spec(sox_spec);sox_spec.loader.exec_module(sox_module)
manager.INITIALIZATION_AUXILIARY=sox_module.SoxIdentity(manager)

policy_spec=importlib.util.spec_from_file_location('tts_startup_policy',ROOT/'scripts/tts-startup-policy.py')
policy_module=importlib.util.module_from_spec(policy_spec);policy_spec.loader.exec_module(policy_module)

def validate_ready(body):
    expected={'status':'ready','model':'Qwen/Qwen3-TTS-12Hz-0.6B-Base','device':'cuda',
              'voice_clone_prompt_ready':True,'model_load_count':1,'voice_clone_prompt_create_count':1,
              'warmup_count':1,'request_count':0}
    if any(body.get(k)!=v for k,v in expected.items()):raise RuntimeError('TTS READY health contract mismatch: '+str(body))

def sample_resources():
    # Sampling during the extended wait is itself bounded; no model API calls.
    gpu=subprocess.check_output([_smi,'--query-gpu=memory.total,memory.used,memory.free','--format=csv,noheader,nounits'],text=True,timeout=5)
    total,used,free=(int(x.strip()) for x in gpu.splitlines()[0].split(','))
    return dict(available_ram_bytes=manager.psutil.virtual_memory().available,gpu_total_mib=total,gpu_used_mib=used,gpu_free_mib=free)

def wait_for_tts(process,root_process,record,started):
    policy=policy_module.StartupPolicy(started)
    offset=0;pending=b'';last_sample=started-5;last_phase=None
    stdout=manager.RUNTIME/'stdout.log'
    while True:
        if process.poll() is not None:raise RuntimeError(f'TTS exited {process.returncode}; see logs')
        current=manager.register_children(root_process,record)
        with stdout.open('rb') as source:
            source.seek(offset);chunk=source.read(65536);offset=source.tell()
        pending+=chunk
        if len(pending)>262144:raise RuntimeError('TTS startup log line exceeded diagnostic limit')
        while b'\n' in pending:
            line,pending=pending.split(b'\n',1)
            try:data=json.loads(line.decode('utf-8'))
            except (ValueError,UnicodeError):continue  # ordinary framework output, not a failure event
            if isinstance(data,dict):policy.event(data,time.perf_counter())
        now=time.perf_counter();policy.check(now)
        if policy.phase!=last_phase:
            print('TTS startup phase:',policy.phase,flush=True);last_phase=policy.phase
        manager.write('startup-progress.json',policy.snapshot(now))
        if now-last_sample>=5:
            rss=[]
            for p in current:
                try:rss.append(dict(pid=p.pid,rss_bytes=p.memory_info().rss))
                except manager.psutil.NoSuchProcess:pass
            with (manager.RUNTIME/'startup-resources.jsonl').open('a',encoding='utf-8') as f:
                f.write(json.dumps(dict(time=time.time(),**policy.snapshot(now),processes=rss,**sample_resources()))+'\n')
            last_sample=now
        binding=manager.listeners()
        if binding:
            if any(c.pid not in {p.pid for p in current} or c.laddr.ip!='127.0.0.1' for c in binding):
                raise RuntimeError('Unexpected TTS listener owner or address')
            try:
                with urllib.request.urlopen('http://127.0.0.1:8765/health',timeout=2) as response:
                    body=json.load(response)
                    if body.get('status')=='error':raise RuntimeError('TTS initialization error: '+str(body))
                    if response.status!=200:raise RuntimeError('TTS health HTTP failure')
                    if body.get('status')=='ready':
                        validate_ready(body)
                        manager.INITIALIZATION_AUXILIARY.finish(record)
                        manager.write('startup.json',dict(status='READY',startup_seconds=time.perf_counter()-started,
                                      processes=record['processes'],health=body,policy=policy.snapshot(time.perf_counter()),**sample_resources()))
                        print('Rebuild Qwen3-TTS ready at http://127.0.0.1:8765/health',flush=True)
                        return
                    if body.get('status')!='starting':raise RuntimeError('Unexpected TTS health status: '+str(body))
            except urllib.error.HTTPError as exc:
                raise RuntimeError(f'TTS health HTTP {exc.code}') from exc
            except urllib.error.URLError:
                pass  # transport may not be ready yet; finite phase/absolute deadlines still apply
        time.sleep(.5)

def start_tts():
    # Only TTS replaces the wait loop. Launch/owner/child/stop helpers are reused
    # unchanged from the verified shared manager; other services call its start().
    result=manager.preflight()
    if result['status']!='READY':raise RuntimeError(result)
    # Same physical first GPU as the existing CLI guards, pinned by UUID rather
    # than assuming CUDA/NVML enumeration order. Never change CUDA selection.
    rows=subprocess.check_output([_smi,'--query-gpu=uuid,memory.used','--format=csv,noheader,nounits'],text=True,timeout=5).strip().splitlines()
    gpu_uuid=rows[0].split(',')[0].strip()
    backend='smi-loop';calibration={'uuid':gpu_uuid,'device_count':len(rows)}
    try:
        nvml=helper_lifecycle.NVML(gpu_uuid);before=nvml.memory()
        cli=int(subprocess.check_output([_smi,'--query-gpu=memory.used','--format=csv,noheader,nounits','--id='+gpu_uuid],text=True,timeout=5).strip())
        after=nvml.memory()
        # Driver semantics differ between v1/v2 and WDDM. Select NVML only when
        # its real whole-device used value brackets this CLI sample (1MiB round).
        if not min(before['used_mib'],after['used_mib'])-1<=cli<=max(before['used_mib'],after['used_mib'])+1:
            raise RuntimeError('NVML/CLI memory.used semantic/sample mismatch')
        backend='nvml';calibration.update(before=before,cli_used_mib=cli,after=after)
    except Exception as exc:calibration['fallback_reason']=repr(exc)
    manager.RUNTIME.mkdir(parents=True,exist_ok=True)
    archive=manager.RUNTIME/('previous-'+str(time.time_ns()))
    for name in ('stdout.log','stderr.log','startup.json','startup-progress.json','startup-resources.jsonl',
                 'gpu-telemetry-selection.json','helper-protocol-failure.json','helper-stop-exits.json',
                 'helper-handle-release.json','startup-cleanup-failure.json','uncommitted-launch-failure.json'):
        if (manager.RUNTIME/name).exists():
            archive.mkdir(exist_ok=True);(manager.RUNTIME/name).rename(archive/name)
    command=[str(manager.PYTHON),'-B','-s',str(manager.ENTRY)]
    run_id=os.environ.get('REBUILD_STACK_RUN_ID') or uuid.uuid4().hex
    broker=helper_lifecycle.Broker(manager,run_id,gpu_uuid)
    child_env=dict(os.environ,**broker.environment(),REBUILD_TTS_GPU_BACKEND=backend,REBUILD_TTS_GPU_COUNT=str(len(rows)))
    manager.write('gpu-telemetry-selection.json',dict(run_id=run_id,backend=backend,calibration=calibration))
    broker.bind()
    process=None;record=None
    try:
        with (manager.RUNTIME/'stdout.log').open('wb') as out,(manager.RUNTIME/'stderr.log').open('wb') as err:
            process=subprocess.Popen(command,cwd=manager.REPO,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW,env=child_env)
        started=time.perf_counter() # original absolute/phase budget starts here
        root_process=manager.psutil.Process(process.pid)
        record={'root':str(ROOT),'entry':str(manager.ENTRY),'processes':[manager.identity(root_process)],'StackRunId':run_id}
        manager.write('owner.json',record)
        manager.INITIALIZATION_AUXILIARY.begin(record)
        broker.start(record)
        wait_for_tts(process,root_process,record,started)
    except BaseException as startup_error:
        broker.stopping=True
        try:
            if record is not None and manager.OWNER.exists():manager.stop()
            else:
                # An uncommitted launch is NOT fabricated as STOPPED. Preserve
                # native evidence for strict reconciliation if identity IO failed.
                manager.write('uncommitted-launch-failure.json',dict(run_id=run_id,error=repr(startup_error),
                    original_command=command,native=helper_lifecycle.handle_identity(process._handle) if process else None,
                    exit_code=process.poll() if process else None,requires_reconciliation=process is not None))
        except BaseException as cleanup_error:
            manager.write('startup-cleanup-failure.json',dict(run_id=run_id,error=repr(cleanup_error),owner_retained=manager.OWNER.exists()))
            raise
        raise
    finally:
        broker.close()
        manager.register_children=broker.register_original

# Public manager interface remains compatible with callers using manager.start().
manager.start=start_tts

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['preflight','start','stop','status']);action=p.parse_args().action
    if action=='preflight':print(json.dumps(manager.preflight(),indent=2))
    elif action=='start':manager.start()
    elif action=='stop':manager.stop()
    elif manager.OWNER.exists():print(json.dumps(manager.assert_listener(),indent=2))
    else:print('No owned TTS service')
