"""H1 local persistent Faster-Whisper CPU service; loopback only."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import gc
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import wave

import psutil
from faster_whisper import WhisperModel

COMMON_DIR = Path(__file__).resolve().parents[1] / "common"
sys.path.insert(0, str(COMMON_DIR))
from lviai_config import configured_path, loopback_host, port, project_root  # noqa: E402


PROJECT = project_root(__file__)
RUNTIME_ROOT = configured_path("LVIAI_RUNTIME_ROOT", PROJECT / "runtime")
MODEL_ROOT = configured_path("LVIAI_STT_MODEL_ROOT", PROJECT / "models" / "faster-whisper")
WARMUP_WAV = configured_path("LVIAI_STT_WARMUP_WAV", PROJECT / "assets" / "stt" / "warmup-16khz-mono.wav")
HOST = loopback_host("LVIAI_STT_HOST")
PORT = port("LVIAI_STT_PORT", 8766)


def gpu_mib() -> int | None:
    try:
        run = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=10)
        return int(run.stdout.strip().splitlines()[0]) if run.returncode == 0 and run.stdout.strip() else None
    except Exception: return None


def wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) != (1, 2, 16000):
            raise ValueError("audio_path must be mono, 16-bit, 16000 Hz PCM WAV")
        return audio.getnframes() / 16000.0


def safe_audio_path(raw: object) -> Path:
    if not isinstance(raw, str) or not raw.strip(): raise ValueError("audio_path is required")
    if raw.startswith("\\\\") or raw.startswith("//"): raise ValueError("UNC/network paths are not allowed")
    path = Path(raw).resolve()
    try: path.relative_to(RUNTIME_ROOT)
    except ValueError as exc: raise ValueError(f"audio_path must remain under {RUNTIME_ROOT}") from exc
    if not path.is_file(): raise FileNotFoundError(f"audio_path does not exist: {path}")
    return path


class State:
    def __init__(self) -> None:
        self.status = "starting"; self.error: str | None = None; self.model: WhisperModel | None = None
        self.model_load_count = 0; self.warmup_count = 0; self.request_count = 0; self.model_load_seconds: float | None = None
        self.lock = threading.Lock(); self.rss_before_model = psutil.Process().memory_info().rss; self.rss_after_model: int | None = None
        self.available_before = psutil.virtual_memory().available; self.available_after_ready: int | None = None; self.gpu_before = gpu_mib(); self.gpu_after_ready: int | None = None

    def health(self) -> dict[str, object]:
        return {"status": self.status, "error": self.error, "model": "Systran/faster-whisper-small", "device": "cpu", "compute_type": "int8", "model_path": str(MODEL_ROOT), "backend": "CTranslate2 CPU", "model_load_count": self.model_load_count, "warmup_count": self.warmup_count, "request_count": self.request_count, "model_load_seconds": self.model_load_seconds, "rss_before_model_bytes": self.rss_before_model, "rss_current_bytes": psutil.Process().memory_info().rss, "rss_after_model_bytes": self.rss_after_model, "available_ram_before_bytes": self.available_before, "available_ram_after_ready_bytes": self.available_after_ready, "gpu_before_mib": self.gpu_before, "gpu_current_mib": gpu_mib()}

    def initialize(self) -> None:
        os.environ["HF_HUB_OFFLINE"] = "1"
        if not MODEL_ROOT.is_dir(): raise FileNotFoundError(f"Local Faster-Whisper cache is missing: {MODEL_ROOT}")
        started = time.perf_counter()
        self.model = WhisperModel("small", device="cpu", compute_type="int8", download_root=str(MODEL_ROOT), local_files_only=True)
        self.model_load_seconds = time.perf_counter() - started; self.model_load_count = 1; self.rss_after_model = psutil.Process().memory_info().rss
        if self.rss_after_model > 1024 ** 3: raise RuntimeError("Persistent STT RSS exceeds 1 GiB")
        if not WARMUP_WAV.is_file(): raise FileNotFoundError(f"Warmup WAV is missing: {WARMUP_WAV}")
        self._transcribe(WARMUP_WAV, count_request=False); self.warmup_count = 1
        self.available_after_ready = psutil.virtual_memory().available; self.gpu_after_ready = gpu_mib(); self.status = "ready"

    def _transcribe(self, path: Path, *, count_request: bool) -> dict[str, object]:
        if self.model is None: raise RuntimeError("STT model is not ready")
        duration = wav_duration(path); request_started = time.perf_counter(); before = psutil.Process().memory_info().rss
        started = time.perf_counter()
        segments_iter, info = self.model.transcribe(str(path), language="zh", beam_size=1, vad_filter=False, condition_on_previous_text=False)
        segments = [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments_iter if s.text.strip()]
        transcription = time.perf_counter() - started
        if count_request: self.request_count += 1
        return {"ok": True, "text": " ".join(item["text"] for item in segments), "language": info.language, "language_probability": info.language_probability, "audio_duration_seconds": duration, "transcription_seconds": transcription, "rtf": transcription / duration if duration else None, "request_total_seconds": time.perf_counter() - request_started, "request_count": self.request_count, "model_load_count": self.model_load_count, "warmup_count": self.warmup_count, "rss_before_bytes": before, "rss_after_bytes": psutil.Process().memory_info().rss, "available_ram_bytes": psutil.virtual_memory().available, "gpu_used_mib": gpu_mib(), "device": "cpu", "compute_type": "int8", "segments": segments}

    def transcribe(self, path: Path) -> dict[str, object]:
        with self.lock: return self._transcribe(path, count_request=True)


STATE = State()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    def log_message(self, format: str, *args: object) -> None: return
    def send_json(self, code: int, body: dict[str, object]) -> None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8"); self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def do_GET(self) -> None:
        if self.path == "/health": self.send_json(200, STATE.health())
        else: self.send_json(404, {"ok": False, "error": "not found"})
    def do_POST(self) -> None:
        if self.path != "/transcribe": self.send_json(404, {"ok": False, "error": "not found"}); return
        try:
            length = int(self.headers.get("Content-Length", "0"));
            if length <= 0 or length > 16384: raise ValueError("invalid request body size")
            payload = json.loads(self.rfile.read(length).decode("utf-8")); result = STATE.transcribe(safe_audio_path(payload.get("audio_path")))
            self.send_json(200, result)
        except Exception as exc: self.send_json(400, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})


def main() -> int:
    try: STATE.initialize()
    except Exception: STATE.error = traceback.format_exc(); STATE.status = "error"; print(STATE.error, flush=True); return 1
    print(json.dumps({"event": "ready", **STATE.health()}, ensure_ascii=False), flush=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close(); STATE.model = None; gc.collect()
    return 0


if __name__ == "__main__": raise SystemExit(main())
