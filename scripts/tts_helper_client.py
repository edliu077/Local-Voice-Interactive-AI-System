"""Creation guard: only the fixed telemetry API may request a helper.

The server is an authenticated per-run native pipe. It pins its actual client
PID, duplicates the original handle and commits owner before the child runs.
"""
import ctypes,hashlib,inspect,json,os,subprocess,threading
from ctypes import wintypes as w
from pathlib import Path
from multiprocessing.connection import Client
import _winapi
from tts_helper_lifecycle import send,receive,handle_identity

_local=threading.local()
_installed=False


def install(root):
    global _installed
    root=Path(root).resolve();original=_winapi.CreateProcess
    expected=(root/'scripts/tts_gpu_monitor.py').read_bytes()
    # Compile once so a matching filename or function name alone cannot grant
    # creation privileges. No third-party/model module is executed here.
    compiled=compile(expected,str(root/'scripts/tts_gpu_monitor.py'),'exec')
    def codes(code):
        yield code
        for item in code.co_consts:
            if inspect.iscode(item):yield from codes(item)
    allowed={code.co_name:code for code in codes(compiled) if code.co_name in ('_start_loop','_one_shot')}
    source_hash=hashlib.sha256(expected).hexdigest()
    # Policy is immutable and shared; per-thread transaction is separate.
    launch.policy=(root,source_hash,allowed)
    def guarded(*args,**kwargs):
        transaction=getattr(_local,'transaction',None)
        if transaction is None:
            caller=inspect.currentframe().f_back
            print(json.dumps(dict(event='tts_external_creation_denied',application=args[0] if args else None,
                  command_sha256=hashlib.sha256(str(args[1] if len(args)>1 else '').encode()).hexdigest(),
                  source=caller.f_code.co_filename,line=caller.f_lineno,external_process_created=False)),flush=True)
            raise RuntimeError('Unregistered TTS external creation refused before CreateProcess')
        args=list(args)
        if len(args)!=9 or kwargs or args[0]!=transaction['argv'][0] or args[1]!=subprocess.list2cmdline(transaction['argv']) or args[5]!=subprocess.DETACHED_PROCESS:
            raise RuntimeError('Helper CreateProcess arguments changed')
        args[5]|=4 # Detached + suspended: no code/console before attestation.
        hp,ht,pid,tid=original(*args)
        try:
            native=handle_identity(hp)
            send(transaction['connection'],dict(action='created',run_id=transaction['run_id'],handle=int(hp),native=native))
            answer=receive(transaction['connection'])
            if answer!={'ok':True,'registered':native}:raise RuntimeError('Manager did not attest original helper handle')
            k=ctypes.WinDLL('kernel32',use_last_error=True)
            k.ResumeThread.argtypes=[w.HANDLE];k.ResumeThread.restype=w.DWORD
            if k.ResumeThread(ht)!=1:raise RuntimeError('Helper thread was not suspended exactly once')
            return hp,ht,pid,tid
        except BaseException:
            # These are the original handles returned by this call, never a PID
            # lookup. No other process can be targeted by this abort path.
            _winapi.TerminateProcess(hp,1);_winapi.WaitForSingleObject(hp,5000)
            _winapi.CloseHandle(ht);_winapi.CloseHandle(hp)
            raise
    _winapi.CreateProcess=guarded;_installed=True
    def restore():
        global _installed
        if _winapi.CreateProcess is guarded:_winapi.CreateProcess=original
        _installed=False
    return restore


def launch(kind):
    if not _installed or getattr(_local,'transaction',None) is not None:raise RuntimeError('Helper client not ready/reentrant')
    root,sha,codes=launch.policy
    caller=inspect.currentframe().f_back
    expected=codes.get(caller.f_code.co_name)
    if (expected is None or caller.f_globals.get('__name__')!='tts_gpu_monitor'
        or caller.f_code.co_filename!=str(root/'scripts/tts_gpu_monitor.py')
        or caller.f_code.co_code!=expected.co_code or caller.f_code.co_consts!=expected.co_consts
        or caller.f_code.co_names!=expected.co_names
        or hashlib.sha256((root/'scripts/tts_gpu_monitor.py').read_bytes()).hexdigest()!=sha):
        raise RuntimeError('Untrusted helper creation source')
    if (caller.f_code.co_name,kind) not in {('_start_loop','loop'),('_one_shot','query')}:
        raise RuntimeError('Helper operation/source mismatch')
    run=os.environ['REBUILD_STACK_RUN_ID']
    connection=Client(os.environ['REBUILD_TTS_HELPER_PIPE'],family='AF_PIPE',authkey=bytes.fromhex(os.environ['REBUILD_TTS_HELPER_AUTH']))
    try:
        send(connection,dict(action='prepare',run_id=run,kind=kind));answer=receive(connection)
        if not answer.get('ok'):raise RuntimeError('Manager refused helper preparation')
        from tts_helper_lifecycle import exact_argv
        argv=exact_argv(os.environ['REBUILD_TTS_GPU_SMI'],os.environ['REBUILD_TTS_GPU_UUID'],kind)
        if answer.get('argv')!=argv:raise RuntimeError('Helper policy differs from manager')
        _local.transaction=dict(argv=argv,run_id=run,connection=connection)
        return subprocess.Popen(argv,executable=argv[0],cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                text=True,encoding='utf-8',creationflags=subprocess.DETACHED_PROCESS)
    finally:
        _local.transaction=None;connection.close()
