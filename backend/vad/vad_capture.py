"""Persistent CPU-only Silero VAD capture for H0; no downstream components."""
from __future__ import annotations

from collections import deque
import os
from pathlib import Path
import queue
import sys
import time
import wave

import numpy as np
import psutil
import sounddevice as sd
import torch
from speech_to_speech.VAD.vad_iterator import VADIterator

COMMON_DIR = Path(__file__).resolve().parents[1] / "common"
sys.path.insert(0, str(COMMON_DIR))
from lviai_config import configured_path, project_root  # noqa: E402


RATE, CHUNK = 16000, 512
PROJECT_ROOT = project_root(__file__)
MODEL_ROOT = configured_path("LVIAI_VAD_MODEL_ROOT", PROJECT_ROOT / "models" / "silero-vad")


def cache_present() -> bool:
    hub = MODEL_ROOT / "hub"
    return hub.is_dir() and any(path.is_dir() and (path / "hubconf.py").is_file() for path in hub.glob("snakers4_silero-vad_*"))


class VadCapture:
    def __init__(self) -> None:
        os.environ["TORCH_HOME"] = str(MODEL_ROOT)
        if torch.cuda.is_available():
            raise RuntimeError("H0 VAD refuses CUDA")
        if not cache_present():
            raise FileNotFoundError(f"Silero VAD cache is missing: {MODEL_ROOT}")
        process = psutil.Process()
        self.rss_before_bytes = process.memory_info().rss
        started = time.perf_counter()
        self.model, _ = torch.hub.load("snakers4/silero-vad", "silero_vad", trust_repo=True, skip_validation=True)
        self.model.eval()
        self.model_load_seconds = time.perf_counter() - started
        self.rss_after_load_bytes = process.memory_info().rss
        if self.rss_after_load_bytes > 1024 ** 3:
            raise RuntimeError("VAD RSS exceeds 1 GiB; H0 is blocked pending a lighter backend assessment")
        self.rss_warning = self.rss_after_load_bytes > 500 * 1024 ** 2
        self.iterator = VADIterator(self.model, threshold=0.5, sampling_rate=RATE, min_silence_duration_ms=800, speech_pad_ms=300)

    def capture_once(self, output: Path, status: callable) -> dict[str, object]:
        self.iterator.reset_states()
        received: queue.Queue[np.ndarray] = queue.Queue()
        pre_roll: deque[np.ndarray] = deque(maxlen=11)  # 352 ms at 512 samples/chunk.
        utterance: list[np.ndarray] = []
        started, speech_started = time.perf_counter(), None
        available_before = psutil.virtual_memory().available
        vad_seconds = 0.0

        def callback(indata: np.ndarray, frames: int, time_info: object, callback_status: sd.CallbackFlags) -> None:
            received.put(indata[:, 0].copy())

        status("Listening...")
        with sd.InputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=CHUNK, callback=callback):
            while True:
                now = time.perf_counter()
                if speech_started is None and now - started >= 20.0:
                    return {"status": "NO_SPEECH", "wait_seconds": now - started, "vad_processing_seconds": vad_seconds, "available_ram_before_vad_bytes": available_before}
                chunk_i16 = received.get(timeout=1.0)
                chunk_float = chunk_i16.astype(np.float32) / 32768.0
                before = self.iterator.triggered
                inference_started = time.perf_counter()
                outcome = self.iterator(torch.from_numpy(chunk_float))
                vad_seconds += time.perf_counter() - inference_started
                if not before and self.iterator.triggered:
                    speech_started = time.perf_counter()
                    utterance = list(pre_roll) + [chunk_i16]
                    status("Speech started.")
                elif speech_started is None:
                    pre_roll.append(chunk_i16)
                else:
                    utterance.append(chunk_i16)
                if speech_started is not None and (outcome is not None or time.perf_counter() - speech_started >= 15.0):
                    audio = np.concatenate(utterance).astype("<i2", copy=False)
                    output.parent.mkdir(parents=True, exist_ok=True)
                    with wave.open(str(output), "wb") as target:
                        target.setnchannels(1); target.setsampwidth(2); target.setframerate(RATE); target.writeframes(audio.tobytes())
                    ended = time.perf_counter()
                    status("Speech ended.")
                    return {
                        "status": "OK", "audio_path": str(output), "wait_seconds": speech_started - started,
                        "utterance_duration_seconds": len(audio) / RATE, "vad_processing_seconds": vad_seconds,
                        "speech_start_clock": speech_started, "speech_end_clock": ended,
                        "vad_rss_steady_bytes": psutil.Process().memory_info().rss,
                        "available_ram_before_vad_bytes": available_before, "available_ram_after_vad_bytes": psutil.virtual_memory().available,
                    }
