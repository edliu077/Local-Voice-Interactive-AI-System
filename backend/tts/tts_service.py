"""E0-E local, single-inference Qwen3-TTS service.

Only the E0-C/E0-D proven Base-model torch/eager cloning route is used.  The
model and voice-clone prompt live in this process exactly once.  No endpoint
can select a model, speaker, or reference recording, and this module contains
no model-download operation.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import gc
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback
from typing import Any
from uuid import uuid4

import psutil
import soundfile as sf
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

COMMON_DIR = Path(__file__).resolve().parents[1] / "common"
sys.path.insert(0, str(COMMON_DIR))
from lviai_config import configured_path, project_root  # noqa: E402


MODEL_ID = "Qwen/Qwen3-TTS-12Hz-0.6B-Base"
LANGUAGE = "Chinese"
GPU_LIMIT_MIB = 6656
MAX_TEXT_CHARS = 300
PROJECT_ROOT = project_root(__file__)
RUNTIME_ROOT = configured_path("LVIAI_RUNTIME_ROOT", PROJECT_ROOT / "runtime")
MODEL_ROOT = configured_path("LVIAI_TTS_MODEL_ROOT", PROJECT_ROOT / "models" / "qwen3-tts" / "0.6b-base")
REFERENCE_AUDIO = configured_path("LVIAI_TTS_REFERENCE_AUDIO", PROJECT_ROOT / "assets" / "voice" / "reference-short.wav")
REFERENCE_TEXT = configured_path("LVIAI_TTS_REFERENCE_TEXT", PROJECT_ROOT / "assets" / "voice" / "reference-short.txt")
OUTPUT_DIR = RUNTIME_ROOT / "tts"
REQUIRED_MODEL_PATHS = ("config.json", "model.safetensors", "tokenizer_config.json", "speech_tokenizer")


def log(event: str, **fields: Any) -> None:
    print(json.dumps({"event": event, "timestamp": time.time(), **fields}, ensure_ascii=False), flush=True)


def gpu_used_mib() -> int | None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=False, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().splitlines()[0])
    except Exception:
        pass
    return None


class RequestMonitor:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self.gpu_peak_mib: int | None = None
        self.rss_peak_bytes = 0

    def _sample(self) -> None:
        self.rss_peak_bytes = max(self.rss_peak_bytes, psutil.Process().memory_info().rss)
        gpu = gpu_used_mib()
        if gpu is not None:
            self.gpu_peak_mib = max(self.gpu_peak_mib or 0, gpu)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self._sample()
            self._stop.wait(0.2)

    def start(self) -> None:
        self._sample()
        self._thread.start()

    def finish(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)
        self._sample()


def confirmed_reference_text(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "STATUS: CONFIRMED":
        raise RuntimeError(f"Reference transcript is not confirmed: {path}")
    text_lines = [line.strip() for line in lines[1:] if line.strip() and not line.startswith("裁剪区间")]
    if len(text_lines) != 1:
        raise RuntimeError("Confirmed reference text must have exactly one non-empty transcript line")
    return text_lines[0]


def ensure_local_model_complete() -> None:
    missing = [str(MODEL_ROOT / name) for name in REQUIRED_MODEL_PATHS if not (MODEL_ROOT / name).exists()]
    if missing:
        raise FileNotFoundError("Local Base model is incomplete; downloads are disabled: " + "; ".join(missing))


class TTSState:
    def __init__(self) -> None:
        self.status = "starting"
        self.error: str | None = None
        self.model: Any | None = None
        self.prompt_items: Any | None = None
        self.model_load_count = 0
        self.voice_clone_prompt_create_count = 0
        self.warmup_count = 0
        self.request_count = 0
        self.inference_lock = asyncio.Lock()
        self.overall_gpu_peak_mib: int | None = None
        self.overall_rss_peak_bytes = 0

    def health(self) -> dict[str, Any]:
        return {
            "status": self.status, "model": MODEL_ID, "device": "cuda",
            "voice_clone_prompt_ready": self.prompt_items is not None,
            "model_load_count": self.model_load_count,
            "voice_clone_prompt_create_count": self.voice_clone_prompt_create_count,
            "warmup_count": self.warmup_count, "request_count": self.request_count,
        }

    def initialize(self) -> None:
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable; E0-E intentionally has no CPU fallback")
        if not REFERENCE_AUDIO.is_file():
            raise FileNotFoundError(f"Missing reference WAV: {REFERENCE_AUDIO}")
        if not os.environ.get("HF_HOME") or not os.environ.get("HUGGINGFACE_HUB_CACHE"):
            raise RuntimeError("HF cache environment variables are required")
        ensure_local_model_complete()
        ref_text = confirmed_reference_text(REFERENCE_TEXT)
        from faster_qwen3_tts import FasterQwen3TTS

        load_started = time.perf_counter()
        self.model = FasterQwen3TTS.from_pretrained(
            str(MODEL_ROOT), device="cuda", dtype=torch.bfloat16,
            attn_implementation="eager", backend="torch", local_files_only=True,
        )
        self.model_load_count = 1
        log("model_loaded", seconds=time.perf_counter() - load_started, model_load_count=self.model_load_count)

        prompt_started = time.perf_counter()
        self.prompt_items = self.model.model.create_voice_clone_prompt(
            ref_audio=str(REFERENCE_AUDIO), ref_text=ref_text, x_vector_only_mode=False,
        )
        self.voice_clone_prompt_create_count = 1
        log("voice_clone_prompt_created", seconds=time.perf_counter() - prompt_started,
            voice_clone_prompt_create_count=self.voice_clone_prompt_create_count)

        # This one call performs the known CUDA graph warm-up/capture path.
        self._generate("你好。", OUTPUT_DIR / f"warmup-{uuid4().hex}.wav", count_request=False)
        self.warmup_count = 1
        self.status = "ready"
        log("service_ready", **self.health())

    def _generate(self, text: str, output: Path, *, count_request: bool) -> dict[str, Any]:
        if self.model is None or self.prompt_items is None:
            raise RuntimeError("TTS model or voice-clone prompt is not ready")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        monitor = RequestMonitor()
        monitor.start()
        gpu_before = gpu_used_mib()
        rss_before = psutil.Process().memory_info().rss
        started = time.perf_counter()
        try:
            wavs, sample_rate = self.model.generate_voice_clone(
                text=text, language=LANGUAGE, voice_clone_prompt=self.prompt_items, non_streaming_mode=False,
            )
            synthesis_seconds = time.perf_counter() - started
            if not wavs:
                raise RuntimeError("Voice clone returned no audio")
            sf.write(str(output), wavs[0], sample_rate)
            if not output.is_file() or output.stat().st_size == 0:
                raise RuntimeError("Output WAV is missing or empty")
            info = sf.info(str(output))
            duration_seconds = info.frames / float(info.samplerate)
        finally:
            monitor.finish()

        self.overall_gpu_peak_mib = max(self.overall_gpu_peak_mib or 0, monitor.gpu_peak_mib or 0)
        self.overall_rss_peak_bytes = max(self.overall_rss_peak_bytes, monitor.rss_peak_bytes)
        metrics = {
            "sample_rate": info.samplerate, "channels": info.channels,
            "duration_seconds": duration_seconds, "synthesis_seconds": synthesis_seconds,
            "rtf": synthesis_seconds / duration_seconds if duration_seconds > 0 else None,
            "output_bytes": output.stat().st_size, "gpu_used_before_mib": gpu_before,
            "gpu_used_after_mib": gpu_used_mib(), "request_gpu_peak_mib": monitor.gpu_peak_mib,
            "python_rss_before_bytes": rss_before,
            "python_rss_after_bytes": psutil.Process().memory_info().rss,
            "python_rss_peak_bytes": monitor.rss_peak_bytes,
            "system_available_ram_bytes": psutil.virtual_memory().available,
        }
        if metrics["request_gpu_peak_mib"] is not None and metrics["request_gpu_peak_mib"] > GPU_LIMIT_MIB:
            log("tts_request_gpu_limit_exceeded", output_path=str(output), **metrics)
            raise RuntimeError(f"GPU safety threshold exceeded: {metrics['request_gpu_peak_mib']} MiB > {GPU_LIMIT_MIB} MiB")
        if count_request:
            self.request_count += 1
        return metrics

    def synthesize(self, text: str) -> dict[str, Any]:
        request_id = uuid4().hex
        output = OUTPUT_DIR / f"{request_id}.wav"
        metrics = self._generate(text, output, count_request=True)
        log("tts_request_complete", request_id=request_id, text_length=len(text), request_count=self.request_count, **metrics)
        return {"ok": True, "request_id": request_id, "text": text, "audio_path": str(output), **metrics,
                "model_load_count": self.model_load_count,
                "voice_clone_prompt_create_count": self.voice_clone_prompt_create_count,
                "warmup_count": self.warmup_count, "request_count": self.request_count}


state = TTSState()


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        state.initialize()
    except Exception:
        state.status = "error"
        state.error = traceback.format_exc()
        log("initialization_failed", error=state.error)
    yield
    if state.model is not None:
        del state.model
        state.model = None
        state.prompt_items = None
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        log("service_shutdown")


app = FastAPI(title="Local Voice-Interactive AI System TTS", version="E0-E", lifespan=lifespan)


class TTSRequest(BaseModel):
    text: str


@app.get("/health")
async def health() -> dict[str, Any]:
    response = state.health()
    if state.error:
        response["error"] = state.error.splitlines()[-1] if state.error.splitlines() else "initialization failed"
    return response


@app.post("/tts")
async def tts(request: TTSRequest) -> dict[str, Any]:
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="text must not be empty")
    if len(text) > MAX_TEXT_CHARS:
        raise HTTPException(status_code=400, detail=f"text must be at most {MAX_TEXT_CHARS} characters")
    if state.status != "ready":
        raise HTTPException(status_code=503, detail=f"TTS service is {state.status}")
    async with state.inference_lock:
        try:
            return await asyncio.to_thread(state.synthesize, text)
        except Exception as exc:
            detail = f"TTS synthesis failed: {type(exc).__name__}: {exc}"
            log("tts_request_failed", error=detail, traceback=traceback.format_exc())
            raise HTTPException(status_code=500, detail=detail) from exc
