"""Rebuild-owned paths and read-only model inputs; no model loading here."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "config" / "rebuild.json").read_text(encoding="utf-8"))
PROFILE = os.environ.get("REBUILD_LLM_PROFILE", CONFIG["default_llm_profile"])
if PROFILE not in CONFIG["llm_profiles"]:
    raise ValueError("Unknown REBUILD_LLM_PROFILE")
if PROFILE != CONFIG['default_llm_profile']:
    raise ValueError('Retired LLM profile refused by the active voice system')
LLM = CONFIG["llm_profiles"][PROFILE]
LLM_BASE_URL = f"http://127.0.0.1:{LLM['port']}"
MODEL_ALIAS = LLM["alias"]
STT_SNAPSHOT = Path(CONFIG["stt_snapshot"])
TTS_MODEL = Path(CONFIG["tts_model"])
VAD_REPOSITORY = Path(CONFIG["vad_repository"])
# Existing project environments are deliberately not used as launch targets.
CPU_PYTHON = ROOT / ".venv-cpu" / "Scripts" / "python.exe"
TTS_PYTHON = ROOT / ".venv-tts" / "Scripts" / "python.exe"


def owned_path(raw: str | Path) -> Path:
    """Resolve first, rejecting UNC, traversal and links escaping this checkout."""
    text = str(raw)
    if text.startswith(("\\\\", "//")):
        raise ValueError("Network paths are forbidden")
    path = Path(raw).resolve()
    if not path.is_relative_to(ROOT) or path == ROOT:
        raise ValueError(f"Path must remain inside Rebuild: {path}")
    return path


def require_owned_service(service: str, port: int) -> None:
    """Never submit audio/text to a legacy service merely sharing its port."""
    from datetime import datetime
    import psutil

    if service in ('tts','stt','ws'):
        if port != {'tts':8765,'stt':8766,'ws':8767}[service]:
            raise RuntimeError('Unexpected service port')
        import importlib.util
        spec = importlib.util.spec_from_file_location('rebuild_owned_manager', ROOT / f'scripts/{service}-service.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.manager.assert_listener()
        return

    key = f"llm-{PROFILE}" if service == "llm" else service
    record_path = owned_path(ROOT / "runtime" / "services-live" / key / "owner.json")
    if not record_path.is_file():
        raise RuntimeError(f"No Rebuild-owned {service} record; request refused")
    record = json.loads(record_path.read_text(encoding="utf-8-sig"))
    if record["Workspace"] != str(ROOT) or record["Key"] != key:
        raise RuntimeError("Foreign service record")
    expected_exe = Path(CONFIG["llama_server"]) if service == "llm" else (TTS_PYTHON if service == "tts" else CPU_PYTHON)
    if Path(record["Executable"]).resolve() != expected_exe.resolve():
        raise RuntimeError("Unexpected service executable")
    process = psutil.Process(int(record["ProcessId"]))
    created = datetime.fromisoformat(record["CreatedUtc"].replace("Z", "+00:00")).timestamp()
    if abs(process.create_time() - created) > 0.01 or Path(process.exe()).resolve() != expected_exe.resolve():
        raise RuntimeError("Service PID identity changed")
    if process.cmdline()[1:] != record["Arguments"].split("\n"):
        raise RuntimeError("Service arguments changed")
    if service == 'llm':
        expected_args=['-m',LLM['model'],'--host','127.0.0.1','--port',str(LLM['port']),
                       '-ngl','0','-c','4096','-t','10','-tb','12','-np','1',
                       '--alias',MODEL_ALIAS,'--reasoning','off']
        if port != LLM['port'] or record['Arguments'].splitlines()!=expected_args:
            raise RuntimeError('LLM model/profile/port arguments differ from the active CPU configuration')
        if (record.get('Profile')!=PROFILE or record.get('ModelPath')!=LLM['model']
                or record.get('ModelAlias')!=MODEL_ALIAS or record.get('ModelSHA256')!=LLM.get('model_sha256')):
            raise RuntimeError('Active LLM owner metadata mismatch')
        import importlib.util
        spec=importlib.util.spec_from_file_location('llm_native_identity',ROOT/'scripts/livetalking-service.py')
        native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
        identity=record.get('ConsoleRootIdentity',{})
        if (identity.get('Pid')!=process.pid or identity.get('ParentPid')!=process.ppid()
                or identity.get('CreationFiletime')!=native.ticks(process.pid)
                or identity.get('CommandLine')!=record['CommandLine']
                or Path(identity.get('Exe','')).resolve()!=expected_exe.resolve()):
            raise RuntimeError('Active LLM native FILETIME/tree identity changed')
    if not any(c.status == psutil.CONN_LISTEN and c.laddr.ip == "127.0.0.1" and c.laddr.port == port for c in process.net_connections(kind="tcp")):
        raise RuntimeError("Expected Rebuild service does not own the loopback port")


def configure_environment() -> None:
    """Set before importing torch/transformers; override inherited old caches."""
    sys.dont_write_bytecode = True
    values = {
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1",
        "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8",
        "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "HF_HOME": str(ROOT / "cache" / "hf"),
        "HUGGINGFACE_HUB_CACHE": str(ROOT / "cache" / "hf" / "hub"),
        "HF_HUB_CACHE": str(ROOT / "cache" / "hf" / "hub"),
        "TRANSFORMERS_CACHE": str(ROOT / "cache" / "hf" / "transformers"),
        "TORCH_HOME": str(ROOT / "cache" / "torch"),
        "TORCHINDUCTOR_CACHE_DIR": str(ROOT / "cache" / "torchinductor"),
        "TRITON_CACHE_DIR": str(ROOT / "cache" / "triton"),
        "CUDA_CACHE_PATH": str(ROOT / "cache" / "cuda"),
        "XDG_CACHE_HOME": str(ROOT / "cache"),
        "NUMBA_CACHE_DIR": str(ROOT / "cache" / "numba"),
        "PYTHONPYCACHEPREFIX": str(ROOT / "cache" / "pycache"),
        "TEMP": str(ROOT / "runtime" / "tmp"),
        "TMP": str(ROOT / "runtime" / "tmp"),
    }
    os.environ.update(values)
    # Reject accidental old source imports, while retaining normal stdlib/site packages.
    old_root = Path(r"D:\CyberGirlfriend")
    for entry in sys.path:
        if entry and Path(entry).resolve().is_relative_to(old_root):
            raise RuntimeError("Original project must not be on the Python source path")


configure_environment()
