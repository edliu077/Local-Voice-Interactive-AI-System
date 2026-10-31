"""Seven-service Windows coordinator. No takeover, gate bypass or model swapping."""
import argparse,ctypes,importlib.util,json,os,shutil,subprocess,sys,time,uuid
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parents[1];RUNTIME=ROOT/'runtime/stack';OWNER=RUNTIME/'owner.json'
DEFAULT_LLM_PROFILE=json.loads((ROOT/'config/rebuild.json').read_text(encoding='utf-8'))['default_llm_profile']
ORDER=['frontend','avatar-control','tts','livetalking','llm','stt','ws']
PORTS=dict(zip(ORDER,[3000,8011,8765,8010,8081,8766,8767]))
RECORDS={n:ROOT/f'runtime/{n}-service/owner.json' for n in ORDER}
RECORDS['livetalking']=ROOT/'runtime/livetalking/owner.json';RECORDS['llm']=ROOT/f'runtime/services-live/llm-{DEFAULT_LLM_PROFILE}/owner.json'
_resource_spec=importlib.util.spec_from_file_location('stack_resource_policy',ROOT/'scripts/resource-policy.py')
resource_policy=importlib.util.module_from_spec(_resource_spec);_resource_spec.loader.exec_module(resource_policy)
_receipt_spec=importlib.util.spec_from_file_location('stack_stop_receipts',ROOT/'scripts/stack-stop-receipts.py')
stop_receipts=importlib.util.module_from_spec(_receipt_spec);_receipt_spec.loader.exec_module(stop_receipts)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def fingerprint(r):
    if 'processes' in r:return {'root':r['root'],'entry':r['entry'],'process':r['processes'][0]}
    return {k:r[k] for k in ['Workspace','Key','ProcessId','Executable','Arguments','CommandLine','CreatedUtc']}
def resources():
    gpu=subprocess.check_output(['nvidia-smi','--query-gpu=memory.total,memory.used,memory.free','--format=csv,noheader,nounits'],text=True).strip()
    processes=[]
    for name,path in RECORDS.items():
        if not path.exists():continue
        record=read(path)
        ids=[x['pid'] for x in record['processes']] if 'processes' in record else [record['ProcessId']]
        for pid in ids:
            try:
                p=psutil.Process(pid)
                memory=p.memory_info()
                processes.append(dict(service=name,pid=pid,rss_bytes=memory.rss,private_bytes=memory.private,exe=p.exe(),command=p.cmdline(),created_unix=p.create_time(),parent_pid=p.ppid()))
            except psutil.NoSuchProcess:pass
    vm=psutil.virtual_memory()
    return dict(**resource_policy.snapshot(),total_ram_bytes=vm.total,gpu_total_used_free_mib=gpu,owned_process_samples=processes)
def process_identity(process):
    spec=importlib.util.spec_from_file_location('stack_identity',ROOT/'scripts/livetalking-service.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return dict(module.identity(process),parent_pid=process.ppid())

def terminate_management_call(process,name,action,expected):
    """Terminate only the exact invocation managers, never a service executable."""
    if process.poll() is not None:return
    root=psutil.Process(process.pid)
    if process_identity(root)!=expected:raise RuntimeError('Invocation root identity conflict; left untouched')
    script=str(ROOT/'scripts'/f'{name}-service.py')
    allowed_exes={str(Path(sys._base_executable).resolve()).lower(),
                  str(ROOT/'.venv-livetalking/Scripts/python.exe').lower(),
                  str(ROOT/'.venv-tts/Scripts/python.exe').lower()}
    managers=[]
    for child in root.children(recursive=True):
        try:identity=process_identity(child)
        except psutil.NoSuchProcess:continue
        if identity['exe'].lower() in allowed_exes and identity['cmdline'][1:]==['-B','-s',script,action]:
            managers.append((child,identity))
    # Services can be descendants too; they are reclaimed only by their owner managers.
    for child,identity in reversed(managers):
        try:
            terminate_exact_process(child,identity)
            child.wait(timeout=15)
        except psutil.NoSuchProcess:pass
    if process.poll() is None:terminate_exact_process(root,expected)
    process.wait(timeout=15)

def terminate_exact_process(process,expected):
    from ctypes import wintypes
    if process_identity(process)!=expected:raise RuntimeError('Invocation identity changed; untouched')
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.GetProcessTimes.argtypes=[wintypes.HANDLE,*([ctypes.POINTER(wintypes.FILETIME)]*4)]
    kernel.TerminateProcess.argtypes=[wintypes.HANDLE,wintypes.UINT];kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    handle=kernel.OpenProcess(0x1000|0x0001|0x00100000,False,process.pid)
    if not handle:raise ctypes.WinError(ctypes.get_last_error())
    try:
        values=[wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle,*(ctypes.byref(v) for v in values)):raise ctypes.WinError(ctypes.get_last_error())
        ticks=(values[0].dwHighDateTime<<32)|values[0].dwLowDateTime
        if ticks!=expected['creation_filetime_ticks']:raise RuntimeError('Invocation handle FILETIME changed')
        if not kernel.TerminateProcess(handle,1):raise ctypes.WinError(ctypes.get_last_error())
    finally:kernel.CloseHandle(handle)

def run_logged(args,directory,timeout,env,on_timeout,check=None):
    directory.mkdir(parents=True,exist_ok=False)
    before=time.monotonic()
    with (directory/'stdout.log').open('wb') as out,(directory/'stderr.log').open('wb') as err:
        process=subprocess.Popen(args,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,
                                 close_fds=True,creationflags=subprocess.CREATE_NO_WINDOW)
        try:expected=process_identity(psutil.Process(process.pid))
        except psutil.NoSuchProcess:expected=None # A fast completed invocation needs no timeout termination.
        (directory/'invocation.json').write_text(json.dumps(dict(args=args,identity=expected,timeout_seconds=timeout),indent=2),encoding='utf-8')
        try:
            while process.poll() is None:
                if check:check()
                remaining=timeout-(time.monotonic()-before)
                if remaining<=0:raise subprocess.TimeoutExpired(args,timeout)
                try:process.wait(timeout=min(2,remaining))
                except subprocess.TimeoutExpired:pass
            code=process.returncode
        except subprocess.TimeoutExpired:
            (directory/'timeout.json').write_text(json.dumps(dict(identity=expected,elapsed=time.monotonic()-before)),encoding='utf-8')
            if expected is None:raise RuntimeError('No trustworthy invocation identity; timeout evidence preserved')
            on_timeout(process,expected)
            raise TimeoutError(f'Manager invocation timed out; evidence: {directory}')
        except BaseException:
            # Stop only this invocation manager; service rollback remains owner-checked.
            if process.poll() is None:
                if expected is None:raise RuntimeError('Resource failure without trustworthy invocation identity')
                on_timeout(process,expected)
            raise
    stdout=(directory/'stdout.log').read_text(encoding='utf-8-sig',errors='replace')
    stderr=(directory/'stderr.log').read_text(encoding='utf-8-sig',errors='replace')
    (directory/'result.json').write_text(json.dumps(dict(returncode=code,elapsed_seconds=time.monotonic()-before)),encoding='utf-8')
    if code:raise RuntimeError(f'Manager exited {code}: {stdout}\n{stderr}')
    return stdout.strip()

def invoke(name,action,run_id=None,profile=None,check=None):
    profile=profile or DEFAULT_LLM_PROFILE
    if action in ('start','preflight','help') and profile!=DEFAULT_LLM_PROFILE:
        raise RuntimeError('Retired LLM profile; only the configured default may start')
    settings=read(ROOT/'config/windows-runtime.json')
    shell=Path(settings['powershell'])
    if not shell.is_file():raise RuntimeError('Recorded PowerShell 7 missing; no policy changes attempted')
    args=[str(shell),'-NoProfile','-File',str(ROOT/'scripts'/('rebuild-service.ps1' if name=='llm' else name+'-service.ps1')),'-Action',action]
    if name=='llm':args+=['-Service','llm','-Profile',profile]
    env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',PYTHONUTF8='1',PYTHONIOENCODING='utf-8',REBUILD_LLM_PROFILE=profile,TEMP=str(ROOT/'runtime/tmp'),TMP=str(ROOT/'runtime/tmp'))
    env['PATH']=str(Path(settings['node']).parent)+os.pathsep+env['PATH']
    env.pop('REBUILD_STACK_RUN_ID',None)
    if run_id:env['REBUILD_STACK_RUN_ID']=run_id
    # Outer budgets include independent manager preflight/cleanup overhead.
    # TTS's own 600-second policy remains unchanged and takes precedence.
    budget=(660 if name=='tts' else 240) if action=='start' else (120 if action=='stop' else 60)
    directory=RUNTIME/'invocations'/f'{time.time_ns()}-{name}-{action}-{uuid.uuid4().hex}'
    arguments=(args,directory,budget,env,lambda p,i:terminate_management_call(p,name,action,i))
    return run_logged(*arguments,check=check) if check and action in ('start','status') else run_logged(*arguments)
class Stack:
    def __init__(self,call=None,resource=resources):
        self.run_id=None;self.resource=resource;self.pressure=resource_policy.Pressure()
        self.call=call or (lambda n,a:invoke(n,a,self.run_id,check=self.check_resources))
    def check_resources(self):
        sample=self.resource()
        if self.run_id:
            directory=RUNTIME/'resource-streams';directory.mkdir(parents=True,exist_ok=True)
            with (directory/f'{self.run_id}.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(sample)+'\n')
        return self.pressure.check(sample)
    def save(self,r):
        if not RUNTIME.resolve().is_relative_to(ROOT):raise RuntimeError('Stack output path escaped Rebuild')
        RUNTIME.mkdir(parents=True,exist_ok=True);OWNER.write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
    def clean_start(self):
        if OWNER.exists():raise RuntimeError('Stack owner exists: inspect status/stop; no adoption')
        if any(p.exists() for p in RECORDS.values()):raise RuntimeError('An independent service owner exists; no takeover')
        if list((ROOT/'runtime/services-live').glob('llm-*/owner.json')) or list((ROOT/'runtime/isolated-llm').glob('*/owner.json')):
            raise RuntimeError('An active or retired LLM owner requires inspection; no takeover')
        legacy=ROOT/'runtime/services'
        if legacy.exists() and list(legacy.rglob('owner.json')):raise RuntimeError('Legacy owner requires inspection')
        occupied=[dict(port=c.laddr.port,pid=c.pid,address=c.laddr.ip) for c in psutil.net_connections('tcp') if c.status=='LISTEN' and c.laddr.port in PORTS.values()]
        if occupied:raise RuntimeError(f'Occupied ports; no process touched: {occupied}')
    def preflight_one(self,name):
        text=self.call(name,'preflight');record=json.loads(text)
        if record.get('status',record.get('Status')) not in ['READY','READY_FOR_ISOLATED_START']:
            raise RuntimeError(f'{name} blocked: {json.dumps(record)}')
        return record
    def stop_record(self,r):
        errors=[]
        targets=list(r['started'])+list(r.get('recovered_pending',[]))
        pending=r.get('pending')
        if pending and pending['service'] not in [x['service'] for x in targets]:
            path=RECORDS[pending['service']]
            if path.exists():
                record=read(path)
                if record.get('StackRunId')!=r['run_id']:
                    errors.append('Pending owner token conflict; preserved, no takeover')
                elif pending.get('fingerprint') and fingerprint(record)!=pending['fingerprint']:
                    errors.append('Pending owner identity conflict; preserved')
                else:
                    item=dict(service=pending['service'],fingerprint=fingerprint(record),pending_cleanup=True)
                    r.setdefault('recovered_pending',[]).append(item);targets.append(item);self.save(r)
            else:
                try:
                    proof=stop_receipts.prove(ROOT,pending['service'],r,pending.get('fingerprint'),process_identity)
                    r.setdefault('validated_stop_receipts',[]).append(proof)
                    item=dict(service=pending['service'],fingerprint=fingerprint(proof['owner']),pending_cleanup=True,stopped=True,stop_receipt_verified=True)
                    r.setdefault('recovered_pending',[]).append(item);targets.append(item);self.save(r)
                except Exception as exc:errors.append('Pending owner absent; no trusted same-run stop receipt: '+str(exc))
        for item in reversed(targets):
            if item.get('stopped'):continue
            name=item['service'];path=RECORDS[name]
            try:
                if not path.exists():raise RuntimeError('Service owner missing; cannot prove process exit')
                if fingerprint(read(path))!=item['fingerprint']:raise RuntimeError('Service owner identity changed; untouched')
                print(self.call(name,'stop'),flush=True);item['stopped']=True;self.save(r)
            except Exception as exc:errors.append(f'{name}: {exc}')
        r['cleanup_errors']=errors
        if errors:self.save(r);raise RuntimeError('; '.join(errors))
        r['status']='STOPPED';r['after_stop']=self.resource();self.save(r)
        target=RUNTIME/'runs'/f"{r['run_id']}.json";target.parent.mkdir(exist_ok=True);OWNER.rename(target)
        return target
    def start(self):
        self.clean_start();self.run_id=uuid.uuid4().hex
        r=dict(run_id=self.run_id,status='STARTING',before=self.resource(),steps=[],started=[]);self.save(r)
        try:
            for name in ORDER:
                self.check_resources()
                print(f'[{name}] real preflight...',flush=True)
                step_started=time.monotonic();before=self.resource()
                gate=self.preflight_one(name)
                r['steps'].append(dict(service=name,before=before,preflight=gate));self.save(r)
                r['pending']=dict(service=name,run_id=r['run_id']);self.save(r)
                print(self.call(name,'start'),flush=True)
                record=read(RECORDS[name])
                if record.get('StackRunId')!=r['run_id']:raise RuntimeError('Returned owner token mismatch')
                r['pending']['fingerprint']=fingerprint(record);self.save(r)
                # A READY file alone never authorizes successful registration.
                self.call(name,'status')
                after=self.resource()
                r['started'].append(dict(service=name,fingerprint=fingerprint(record)))
                r['steps'][-1].update(after_ready=after,startup_seconds=time.monotonic()-step_started)
                r.pop('pending',None);self.save(r)
                self.check_resources()
            r['resident_resources']=self.resource()
            r['resource_state']=self.pressure.check(r['resident_resources'])
            r['status']='READY';r['startup_outcome']='READY';self.save(r)
            print('Owned services ready: '+', '.join(ORDER),flush=True)
            if 'frontend' in ORDER:print('http://127.0.0.1:3000/',flush=True)
        except BaseException as exc:
            r['status']='BLOCKED';r['startup_outcome']='BLOCKED';r['blocked_service']=name;r['error']=str(exc);r['at_block']=self.resource();self.save(r)
            print(str(exc),flush=True)
            path=self.stop_record(r)
            raise RuntimeError(f'Start blocked at {name}; owned services reclaimed. Evidence: {path}') from exc
    def stop(self):
        if not OWNER.exists():print('No stack run is owned; independent services untouched');return
        record=read(OWNER);record['status']='STOPPING';self.save(record)
        self.stop_record(record)
    def watch(self):
        """Keep protecting the resident stack until the existing stop entry is used."""
        last_health=time.monotonic()
        try:
            while OWNER.exists():
                record=read(OWNER)
                if record['run_id']!=self.run_id:raise RuntimeError('Supervisor run identity conflict')
                if record['status']!='READY':return
                self.check_resources()
                if time.monotonic()-last_health>=30:
                    for item in record['started']:
                        if not OWNER.exists() or read(OWNER)['status']!='READY':return
                        if fingerprint(read(RECORDS[item['service']]))!=item['fingerprint']:
                            raise RuntimeError('Resident owner fingerprint changed')
                        self.call(item['service'],'status')
                    last_health=time.monotonic()
                time.sleep(2)
        except BaseException as exc:
            if OWNER.exists():
                record=read(OWNER)
                if record['run_id']!=self.run_id or record['status']!='READY':raise
                record.update(status='BLOCKED',runtime_resource_error=str(exc),at_block=self.resource());self.save(record)
                self.stop_record(record)
            raise
def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['preflight','start','stop','status']);a=p.parse_args().action
    stack=Stack()
    if a=='start':stack.start();stack.watch()
    elif a=='stop':stack.stop()
    elif a=='status':
        if not OWNER.exists():print('No stack run owned')
        else:
            r=read(OWNER)
            for x in r['started']:
                if not x.get('stopped'):print(x['service'],stack.call(x['service'],'status'))
            print(r['status'])
    else:
        stack.clean_start();print(json.dumps(dict(system=resources(),isolated_gates={n:stack.preflight_one(n) for n in ORDER},notice='Snapshot gates do not prove simultaneous residency'),indent=2))
if __name__=='__main__':main()
