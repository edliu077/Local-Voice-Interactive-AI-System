"""Independent Stage 4 service owner; never manages the LLM or old projects."""
from __future__ import annotations
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request
import psutil
import importlib.util

_resource_spec=importlib.util.spec_from_file_location('rebuild_resource_policy',Path(__file__).with_name('resource-policy.py'))
resource_policy=importlib.util.module_from_spec(_resource_spec);_resource_spec.loader.exec_module(resource_policy)

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "third_party/LiveTalking"
RUNTIME = ROOT / "runtime/livetalking"
OWNER = RUNTIME / "owner.json"
ENTRY = ROOT / "scripts/livetalking-run.py"
PYTHON = ROOT / ".venv-livetalking/Scripts/python.exe"
PORT = 8010
MINIMUM_GPU_FREE_MIB = 2048
MINIMUM_RAM_BYTES = resource_policy.POLICY['startup_ram_bytes']['livetalking']
REQUIRED_INPUTS = (REPO / 'models/wav2lip.pth', REPO / 'data/avatars/cybergirlfriend_avatar_v1/coords.pkl')
HEALTH_PATH = '/index.html'
HEALTH_STATUS = None
SERVICE_NAME = 'LiveTalking'
ALLOWED_AUXILIARY = {}
INITIALIZATION_AUXILIARY = None # Installed only by the TTS initialization manager.
CREATED_HELPER_VERIFY = None # TTS creation authority only; other services unchanged.
TTS_STOP_EXIT_CHECK = None # Optional native-handle check before owner archival.


def assert_listener():
    record = json.loads(OWNER.read_text(encoding='utf-8'))
    if record['root'] != str(ROOT) or record['entry'] != str(ENTRY):
        raise RuntimeError('Foreign service record')
    root_process = verified(record['processes'][0])
    register_children(root_process, record)
    processes = []
    for item in record['processes']:
        try:
            processes.append(verified(item, record))
        except psutil.NoSuchProcess:
            pass
    binding = listeners()
    if not binding or any(c.pid not in {p.pid for p in processes} or c.laddr.ip != '127.0.0.1' for c in binding):
        raise RuntimeError('Expected owned loopback listener missing')
    return record


def write(name, value):
    RUNTIME.mkdir(parents=True, exist_ok=True)
    path = RUNTIME / name
    if not path.resolve().is_relative_to(ROOT):
        raise RuntimeError("Output path escaped Rebuild")
    if name == 'owner.json' and os.environ.get('REBUILD_STACK_RUN_ID'):
        value = dict(value, StackRunId=os.environ['REBUILD_STACK_RUN_ID'])
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def ticks(pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        values = [wintypes.FILETIME() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(v) for v in values)):
            raise ctypes.WinError(ctypes.get_last_error())
        return (values[0].dwHighDateTime << 32) | values[0].dwLowDateTime
    finally:
        kernel.CloseHandle(handle)


def identity(process):
    return {"pid": process.pid, "creation_filetime_ticks": ticks(process.pid), "exe": process.exe(), "cmdline": process.cmdline()}


def is_console_identity(item):
    return Path(item['exe']).resolve() == Path(os.environ['SystemRoot'], 'System32', 'conhost.exe').resolve()


def is_console_transition(before, after):
    # Full executable spelling and argv[0] must remain unchanged as well as
    # PID/FILETIME. Only these two exact argument tuples may exchange places.
    if (not is_console_identity(before) or not is_console_identity(after)
            or after != dict(before, cmdline=after['cmdline'])
            or not before['cmdline'] or not after['cmdline']
            or before['cmdline'][0] != after['cmdline'][0]):
        return False
    return (tuple(before['cmdline'][1:]), tuple(after['cmdline'][1:])) in {
        (('0x4',), ('0xffffffff', '-ForceV1')),
        (('0xffffffff', '-ForceV1'), ('0x4',)),
    }


def console_parent_identity(process, owner):
    root = verified(owner['processes'][0])
    descendants = {p.pid for p in root.children(recursive=True)}
    parent_pid = process.ppid()
    if (process.pid == root.pid or process.pid not in descendants
            or parent_pid not in descendants | {root.pid}):
        write('identity-conflict.json', {'reason':'Console left the owned process tree','pid':process.pid})
        raise RuntimeError('Console parent/tree identity mismatch')
    try:parent = process.parent()
    except psutil.NoSuchProcess as exc:
        if not psutil.pid_exists(process.pid):raise
        raise RuntimeError('Console parent disappeared during verification') from exc
    if parent is None or parent.pid != parent_pid:
        raise RuntimeError('Console parent changed during verification')
    result = identity(parent)
    if process.ppid() != result['pid']:
        raise RuntimeError('Console parent changed during verification')
    return result


def check_console_parent(process, owner):
    current = console_parent_identity(process, owner)
    expected = owner.get('console_parents', {}).get(str(process.pid))
    if expected != current:
        write('identity-conflict.json', {'reason':'Console parent identity changed or baseline missing',
                                      'pid':process.pid,'expected_parent':expected,'current_parent':current})
        raise RuntimeError('Console recorded parent identity mismatch')
    return current


def accept_console_transition(process, before, after, owner):
    if not is_console_transition(before, after):
        return False
    parent = check_console_parent(process, owner)
    owner.setdefault('console_startup_transitions', []).append({
        'time_unix_ns':time.time_ns(), 'before':before.copy(), 'after':after.copy(),
        'parent_before':owner['console_parents'][str(process.pid)].copy(), 'parent_after':parent,
        'root_identity':owner['processes'][0].copy(),
        'checks':{'same_pid':True,'same_creation_filetime':True,'same_exe':True,'same_argv0':True,
                  'same_parent_identity':True,'in_owned_tree':True,'exact_known_argument_pair':True},
    })
    before.update(after)
    write('owner.json', owner)
    return True


def verified(record, owner=None):
    process = psutil.Process(record["pid"])
    item = identity(process)
    if item != record and (owner is None or not accept_console_transition(process, record, item, owner)):
        write('identity-conflict.json', {'reason':'Process identity changed','before':record,'after':item})
        raise RuntimeError("Process identity mismatch; refusing operation")
    if is_console_identity(item):
        if owner is None:raise RuntimeError('Console owner context required')
        check_console_parent(process, owner)
    if not (owner is not None and CREATED_HELPER_VERIFY is not None and CREATED_HELPER_VERIFY(process,owner)) and not allowed_process(process) and not (owner is not None and INITIALIZATION_AUXILIARY is not None
                                           and INITIALIZATION_AUXILIARY.verify(process,owner)):
        raise RuntimeError("Process command rejected; refusing operation")
    return process


def allowed_process(process):
    command = process.cmdline()
    if tuple(command[1:]) in ALLOWED_AUXILIARY.get(str(Path(process.exe()).resolve()).lower(), ()):
        return True
    if str(ENTRY) in command:
        return Path(process.exe()).resolve() in {PYTHON.resolve(), Path(sys._base_executable).resolve()}
    # Windows venv launcher creates this exact console host under CREATE_NO_WINDOW.
    return (Path(process.exe()).resolve() == Path(os.environ['SystemRoot'], 'System32', 'conhost.exe').resolve()
            and tuple(command[1:]) in {('0x4',), ('0xffffffff', '-ForceV1')})


def register_children(root_process, record):
    if root_process.pid != record['processes'][0]['pid']:
        raise RuntimeError('Unexpected root process')
    verified(record['processes'][0])
    current = [root_process, *root_process.children(recursive=True)]
    for child in current:
        partial = {}
        try:
            if INITIALIZATION_AUXILIARY is not None:
                # Preserve what can be acquired before touching remote argv/PEB.
                try:
                    partial['creation_filetime_ticks'] = ticks(child.pid)
                    partial['parent_pid'] = child.ppid()
                    partial['exe'] = child.exe()
                except (OSError, psutil.Error) as exc:
                    partial['capture_error'] = repr(exc)
                # Diagnostic failure does not bypass the original checks below.
            if not (CREATED_HELPER_VERIFY is not None and CREATED_HELPER_VERIFY(child,record)) and not allowed_process(child) and not (INITIALIZATION_AUXILIARY is not None
                                                  and INITIALIZATION_AUXILIARY.verify(child,record,register=True)):
                write('unexpected-child.json',identity(child))
                raise RuntimeError('Unexpected child command; exact identity saved')
            item = identity(child)
        except psutil.NoSuchProcess:
            if INITIALIZATION_AUXILIARY is not None and child.pid not in {p['pid'] for p in record['processes']}:
                spec=importlib.util.spec_from_file_location('tts_failure_evidence',ROOT/'scripts/tts-process-evidence.py')
                evidence=importlib.util.module_from_spec(spec);spec.loader.exec_module(evidence)
                write('unattested-child-exit.json',dict(pid=child.pid,StackRunId=record.get('StackRunId'),root_identity=record['processes'][0],observed_time=time.time(),partial_identity=partial,creation_candidates=evidence.candidates(ROOT,record.get('StackRunId'),child.pid),reason='Exited before native identity/parent attestation; creation candidates are diagnostic only'))
                raise RuntimeError('Unregistered TTS descendant exited before trustworthy attestation')
            continue
        existing = next((r for r in record['processes'] if r['pid'] == item['pid']), None)
        if existing and is_console_identity(item):
            check_console_parent(child, record)
        if existing and existing != item:
            if not accept_console_transition(child, existing, item, record):
                write('identity-conflict.json', {'reason':'Recorded descendant identity changed','before':existing,'after':item})
                raise RuntimeError('Recorded descendant identity changed')
        elif not existing:
            if is_console_identity(item):
                record.setdefault('console_parents', {})[str(child.pid)] = console_parent_identity(child, record)
            record['processes'].append(item)
            write('owner.json', record)
    if INITIALIZATION_AUXILIARY is not None:INITIALIZATION_AUXILIARY.refresh(record)
    return current


def listeners():
    return [c for c in psutil.net_connections(kind="tcp") if c.status == "LISTEN" and c.laddr.port == PORT]


def resources():
    gpu = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free", "--format=csv,noheader,nounits"], text=True).strip()
    fields = [int(v.strip()) for v in gpu.splitlines()[0].split(",")]
    return {**resource_policy.snapshot(), "gpu_total_mib": fields[0], "gpu_used_mib": fields[1], "gpu_free_mib": fields[2]}


def preflight():
    for path in (PYTHON, ENTRY, *REQUIRED_INPUTS):
        if not path.is_file():
            raise FileNotFoundError(path)
    result = resources()
    result.update({"port": PORT, "owner_exists": OWNER.exists(), "listeners": [c.pid for c in listeners()], "status": "READY"})
    if result["owner_exists"] or result["listeners"]:
        result["status"] = "BLOCKED_OWNER_OR_PORT"
    result['minimum_ram_bytes']=MINIMUM_RAM_BYTES
    result['minimum_gpu_free_mib']=MINIMUM_GPU_FREE_MIB
    result['resource_errors']=resource_policy.violations(result,minimum=MINIMUM_RAM_BYTES,gpu_minimum=MINIMUM_GPU_FREE_MIB)
    if result['status']=='READY' and result['resource_errors']:
        result["status"] = "BLOCKED_RESOURCES"
    write("preflight.json", result)
    return result


def stop():
    if not OWNER.exists():
        print("No LiveTalking owner record; no process touched")
        return
    record = json.loads(OWNER.read_text(encoding="utf-8"))
    if record["root"] != str(ROOT) or record["entry"] != str(ENTRY):
        raise RuntimeError("Foreign owner record")
    if psutil.pid_exists(record['processes'][0]['pid']):
        register_children(verified(record['processes'][0]), record)
    alive = []
    for item in record["processes"]:
        try:
            alive.append(verified(item, record))
        except psutil.NoSuchProcess:
            pass
    recorded = {p.pid for p in alive}
    for process in alive:
        try:
            if any(p.pid not in recorded for p in process.children(recursive=True)):
                raise RuntimeError("Unrecorded descendant; stop refused")
        except psutil.NoSuchProcess:
            pass
    for process in reversed(alive):
        try:
            verified(next(r for r in record["processes"] if r["pid"] == process.pid), record).terminate()
        except psutil.NoSuchProcess:
            pass  # An owned console/launcher may exit as its Python child exits.
    _, remaining = psutil.wait_procs(alive, timeout=15)
    if remaining:
        raise RuntimeError("Owned process did not exit; owner retained")
    if TTS_STOP_EXIT_CHECK is not None:TTS_STOP_EXIT_CHECK()
    if listeners():
        raise RuntimeError("Another listener remains; it was not touched")
    archive = RUNTIME / f"stopped-{time.time_ns()}.json"
    OWNER.rename(archive)
    write("stop-result.json", {"status":"STOPPED", "process_ids":[r["pid"] for r in record["processes"]], "owner_archive":str(archive), **resources()})
    print(f"Stopped only verified {SERVICE_NAME} process tree; no port residue")


def start():
    result = preflight()
    if result["status"] != "READY":
        raise RuntimeError(result)
    command = [str(PYTHON), "-B", "-s", str(ENTRY)]
    RUNTIME.mkdir(parents=True, exist_ok=True)
    archive = RUNTIME / ('previous-' + str(time.time_ns()))
    for name in ('stdout.log','stderr.log','startup.json'):
        if (RUNTIME / name).exists():
            archive.mkdir(exist_ok=True)
            (RUNTIME / name).rename(archive / name)
    with (RUNTIME / "stdout.log").open("wb") as out, (RUNTIME / "stderr.log").open("wb") as err:
        process = subprocess.Popen(command, cwd=REPO, stdout=out, stderr=err, creationflags=subprocess.CREATE_NO_WINDOW)
    root_process = psutil.Process(process.pid)
    record = {"root":str(ROOT), "entry":str(ENTRY), "processes":[identity(root_process)]}
    write("owner.json", record)
    started = time.perf_counter()
    try:
        for _ in range(180):
            if process.poll() is not None:
                raise RuntimeError(f"Service exited {process.returncode}; see logs")
            current = register_children(root_process, record)
            binding = listeners()
            if binding:
                if any(c.pid not in {p.pid for p in current} or c.laddr.ip != "127.0.0.1" for c in binding):
                    raise RuntimeError("Unexpected listener owner or address")
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{HEALTH_PATH}", timeout=2) as response:
                        body = json.load(response) if HEALTH_STATUS else {}
                        if body.get('status') == 'error':
                            raise RuntimeError('Service initialization error: ' + str(body))
                        if response.status == 200 and (HEALTH_STATUS is None or body.get('status') == HEALTH_STATUS):
                            write("startup.json", {"status":"READY", "startup_seconds":time.perf_counter()-started,"processes":record["processes"],**resources()})
                            print(f"{SERVICE_NAME} ready at http://127.0.0.1:{PORT}{HEALTH_PATH}")
                            return
                except OSError:
                    pass
            time.sleep(1)
        raise TimeoutError("Startup timed out")
    except BaseException:
        stop()
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["preflight","start","stop","status"])
    action = parser.parse_args().action
    if action == "start": start()
    elif action == "stop": stop()
    elif action == "preflight": print(json.dumps(preflight(),indent=2))
    else: print(OWNER.read_text(encoding="utf-8") if OWNER.exists() else "No owned service")
