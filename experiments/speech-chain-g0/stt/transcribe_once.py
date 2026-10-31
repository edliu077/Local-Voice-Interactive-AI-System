"""G0-A one-shot local Faster-Whisper transcription worker.

This worker is intentionally CPU-only and offline. It never starts VAD, LLM,
TTS, a service, a microphone, or any browser component. Stdout is exactly one
UTF-8 JSON object; stderr is reserved for diagnostics.
"""

from __future__ import annotations

# Rebuild paths must be configured before third-party imports.
import sys as _rebuild_sys
from pathlib import Path as _RebuildPath
_rebuild_sys.path.insert(0, str(_RebuildPath(__file__).resolve().parents[3]))
from rebuild_config import ROOT as REBUILD_ROOT, owned_path, STT_SNAPSHOT, TTS_MODEL, VAD_REPOSITORY, CPU_PYTHON
from rebuild_config import LLM_BASE_URL as REBUILD_LLM_URL, MODEL_ALIAS as REBUILD_MODEL_ALIAS


import argparse
import gc
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import wave

import psutil
from faster_whisper import WhisperModel


DEFAULT_MODEL_ROOT = STT_SNAPSHOT


def gpu_used_mib() -> int | None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip().splitlines()[0])
    except Exception:
        pass
    return None


def wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        if audio.getnchannels() != 1 or audio.getframerate() != 16000 or audio.getsampwidth() != 2:
            raise ValueError("Input must be mono, 16 kHz, 16-bit PCM WAV")
        return audio.getnframes() / float(audio.getframerate())


def transcribe(audio: Path, model_root: Path) -> dict[str, object]:
    if not audio.is_file():
        raise FileNotFoundError(f"Audio file does not exist: {audio}")
    if not model_root.is_dir():
        raise FileNotFoundError(f"Faster-Whisper model root does not exist: {model_root}")

    # Prevent a missing cache entry from silently downloading a model.
    os.environ["HF_HUB_OFFLINE"] = "1"
    duration = wav_duration_seconds(audio)
    process = psutil.Process()
    available_before = psutil.virtual_memory().available
    gpu_before = gpu_used_mib()
    rss_before = process.memory_info().rss

    load_started = time.perf_counter()
    model = WhisperModel(
        str(model_root), device="cpu", compute_type="int8",
        local_files_only=True,
    )
    load_seconds = time.perf_counter() - load_started
    rss_after_load = process.memory_info().rss
    available_after_load = psutil.virtual_memory().available

    started = time.perf_counter()
    segments_iter, info = model.transcribe(
        str(audio), language="zh", beam_size=1, vad_filter=False,
        condition_on_previous_text=False,
    )
    segments = [
        {"start": segment.start, "end": segment.end, "text": segment.text.strip()}
        for segment in segments_iter
        if segment.text.strip()
    ]
    transcription_seconds = time.perf_counter() - started
    text = " ".join(segment["text"] for segment in segments)
    rss_after_transcription = process.memory_info().rss
    available_after_transcription = psutil.virtual_memory().available
    gpu_after = gpu_used_mib()

    result: dict[str, object] = {
        "ok": True,
        "model": "Systran/faster-whisper-small",
        "device": "cpu",
        "compute_type": "int8",
        "faster_whisper_version": importlib.metadata.version("faster-whisper"),
        "ctranslate2_version": importlib.metadata.version("ctranslate2"),
        "audio": str(audio),
        "audio_duration_seconds": duration,
        "text": text,
        "language": info.language,
        "language_probability": info.language_probability,
        "segments": segments,
        "model_load_seconds": load_seconds,
        "transcription_seconds": transcription_seconds,
        "rtf": transcription_seconds / duration if duration else None,
        "stt_rss_before_bytes": rss_before,
        "stt_rss_after_load_bytes": rss_after_load,
        "stt_rss_after_transcription_bytes": rss_after_transcription,
        "stt_rss_peak_observed_bytes": max(rss_before, rss_after_load, rss_after_transcription),
        "available_ram_before_bytes": available_before,
        "available_ram_after_load_bytes": available_after_load,
        "available_ram_after_transcription_bytes": available_after_transcription,
        "minimum_available_ram_observed_bytes": min(
            available_before, available_after_load, available_after_transcription
        ),
        "gpu_used_before_mib": gpu_before,
        "gpu_used_after_mib": gpu_after,
    }
    del model
    gc.collect()
    result["available_ram_after_model_release_bytes"] = psutil.virtual_memory().available
    result["gpu_used_after_model_release_mib"] = gpu_used_mib()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, default=DEFAULT_MODEL_ROOT)
    args = parser.parse_args()
    try:
        print(json.dumps(transcribe(args.audio, args.model_root), ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), flush=True)
        traceback.print_exc(file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
