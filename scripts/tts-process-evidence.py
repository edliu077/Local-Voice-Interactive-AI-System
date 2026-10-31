"""TTS-only Windows creation-handle evidence. Evidence grants no permission.

Capture before subprocess.Popen receives CreateProcess's result, so even a
child which has already exited retains its original kernel identity. No PATH,
command, creation flags, model settings or process lifetime is changed.
Native/third-party launches bypassing Python's _winapi are outside this hook.
"""
import ctypes
from ctypes import wintypes as w
import inspect
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import uuid


def native(handle, query_image=True):
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.GetProcessTimes.argtypes = [w.HANDLE, *([ctypes.POINTER(w.FILETIME)] * 4)]
    k.GetProcessId.argtypes = [w.HANDLE]; k.GetProcessId.restype = w.DWORD
    k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, ctypes.POINTER(w.DWORD)]
    k.GetExitCodeProcess.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
    values = [w.FILETIME() for _ in range(4)]
    if not k.GetProcessTimes(handle, *(ctypes.byref(v) for v in values)):
        raise ctypes.WinError(ctypes.get_last_error())
    size = w.DWORD(32768); image = ctypes.create_unicode_buffer(size.value)
    image_error = None
    if query_image and not k.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
        # Some exited Windows launcher images cannot be queried even with the
        # original handle. Preserve FILETIME/exit evidence without inventing exe.
        image_error = repr(ctypes.WinError(ctypes.get_last_error()))
    code = w.DWORD()
    if not k.GetExitCodeProcess(handle, ctypes.byref(code)):
        raise ctypes.WinError(ctypes.get_last_error())
    return dict(pid=k.GetProcessId(handle), creation_filetime_ticks=(values[0].dwHighDateTime << 32) | values[0].dwLowDateTime,
                exe=image.value if query_image and not image_error else None,
                image_error=image_error, raw_exit_code=code.value)


def install(root):
    import _winapi
    import psutil
    root = Path(root).resolve()
    if Path(sys.prefix).resolve() != root / '.venv-tts':
        raise RuntimeError('Creation evidence is restricted to the TTS environment')
    run = os.environ.get('REBUILD_STACK_RUN_ID', '')
    if len(run) != 32 or any(c not in '0123456789abcdef' for c in run):
        raise RuntimeError('TTS creation evidence requires an explicit run identity')
    folder = root / 'runtime/tts-service/process-evidence' / run
    folder.mkdir(parents=True, exist_ok=True)
    original = _winapi.CreateProcess
    parent = psutil.Process()
    parent_handle = _winapi.OpenProcess(0x1000, False, parent.pid)
    try:
        parent_identity = native(parent_handle)
    finally:
        _winapi.CloseHandle(parent_handle)
    parent_identity.pop('raw_exit_code')
    parent_identity['cmdline'] = parent.cmdline()
    parent_identity['parent_pid'] = parent.ppid()

    def save(path, data):
        temp = path.with_suffix('.tmp')
        temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        temp.replace(path)

    def created(*args, **kwargs):
        # This is the exact CPython positional CreateProcess interface.
        frames = []
        frame = inspect.currentframe().f_back
        while frame is not None and len(frames) < 24:
            location=dict(file=frame.f_code.co_filename, function=frame.f_code.co_name, line=frame.f_lineno)
            caller_path=Path(frame.f_code.co_filename)
            if caller_path.is_absolute() and caller_path.is_relative_to(root) and caller_path.suffix=='.py':
                try: location['source_sha256']=hashlib.sha256(caller_path.read_bytes()).hexdigest()
                except OSError as exc: location['source_error']=repr(exc)
            frames.append(location)
            frame = frame.f_back
        del frame
        result = original(*args, **kwargs)
        hp, ht, pid, tid = result
        token = f'{pid}-{time.time_ns()}-{uuid.uuid4().hex}'
        path = folder / (token + '.json')
        evidence = dict(kind='python_createprocess_observation', StackRunId=run, time_ns=time.time_ns(),
                        pid=pid, thread_id=tid, parent=parent_identity, caller_stack=frames,
                        application=args[0] if len(args)>0 else kwargs.get('application_name'),
                        command_line=args[1] if len(args)>1 else kwargs.get('command_line'),
                        creation_flags=args[5] if len(args)>5 else None,
                        grants_trust=False)
        duplicate = None
        try:
            evidence['identity'] = native(hp)
            current = _winapi.GetCurrentProcess()
            duplicate = _winapi.DuplicateHandle(current, hp, current, 0, False, _winapi.DUPLICATE_SAME_ACCESS)
            save(path, evidence)
            def observe_exit():
                try:
                    # Does not hold Popen's output pipe handles or delay its return.
                    # Polling only waits on the duplicated original kernel object.
                    while _winapi.WaitForSingleObject(duplicate, 1000) == _winapi.WAIT_TIMEOUT:
                        pass
                    exit_identity=native(duplicate, query_image=False)
                    exit_identity['exe']=evidence['identity']['exe']
                    exit_identity['exe_source']='creation_handle_snapshot; not re-read after exit'
                    save(folder / (token + '.exit.json'), dict(StackRunId=run, identity=exit_identity,
                         signaled=True, time_ns=time.time_ns(), creation_record=path.name, grants_trust=False))
                except BaseException as exc:
                    save(folder / (token + '.exit-error.json'), dict(error=repr(exc), grants_trust=False))
                finally:
                    _winapi.CloseHandle(duplicate)
            threading.Thread(target=observe_exit, daemon=True).start()
        except BaseException as exc:
            if duplicate is not None: _winapi.CloseHandle(duplicate)
            evidence['capture_error'] = repr(exc)
            # A diagnostic failure is visible; it cannot convert an unknown child
            # into an allowed one. Return original handles to their Popen owner.
            try: save(path, evidence)
            except OSError as write_error:
                print('TTS process creation evidence unavailable: '+repr(write_error), file=sys.stderr, flush=True)
        return result

    _winapi.CreateProcess = created
    def restore():
        if _winapi.CreateProcess is created: _winapi.CreateProcess = original
    return restore


def candidates(root, run, pid):
    """Diagnostic correlation only: a PID match is NEVER an attestation."""
    if not isinstance(run, str) or len(run) != 32 or any(c not in '0123456789abcdef' for c in run):
        return []
    result = []
    for path in (Path(root)/'runtime/tts-service/process-evidence'/run).glob(f'{int(pid)}-*.json'):
        if path.name.endswith(('.exit.json', '.exit-error.json')): continue
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if data.get('StackRunId') == run and data.get('pid') == pid:
                result.append(dict(path=str(path), observation=data, trusted=False))
        except (OSError, ValueError): pass
    return result
