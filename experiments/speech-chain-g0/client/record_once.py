"""G0-A manual short WAV recorder using the existing sounddevice package."""

from __future__ import annotations

# Rebuild paths must be configured before third-party imports.
import sys as _rebuild_sys
from pathlib import Path as _RebuildPath
_rebuild_sys.path.insert(0, str(_RebuildPath(__file__).resolve().parents[3]))
from rebuild_config import ROOT as REBUILD_ROOT, owned_path, STT_SNAPSHOT, TTS_MODEL, VAD_REPOSITORY, CPU_PYTHON
from rebuild_config import LLM_BASE_URL as REBUILD_LLM_URL, MODEL_ALIAS as REBUILD_MODEL_ALIAS


import argparse
import json
from pathlib import Path
import sys
import wave

import numpy as np
import sounddevice as sd


SAMPLE_RATE = 16000


def device_report() -> dict[str, object]:
    devices = sd.query_devices()
    default_input = sd.default.device[0]
    return {
        "ok": True,
        "default_input_device": default_input,
        "devices": [
            {
                "index": index,
                "name": device["name"],
                "max_input_channels": device["max_input_channels"],
                "default_samplerate": device["default_samplerate"],
            }
            for index, device in enumerate(devices)
            if device["max_input_channels"] > 0
        ],
    }


def record(output: Path, device: int | None) -> dict[str, object]:
    output = owned_path(output)
    if not device_report()["devices"]:
        raise RuntimeError("No input audio device is available")
    chunks: list[np.ndarray] = []

    def callback(indata: np.ndarray, frames: int, time_info: object, status: sd.CallbackFlags) -> None:
        if status:
            print(f"audio_callback_status={status}", file=sys.stderr, flush=True)
        chunks.append(indata.copy())

    print("Press Enter to start recording.", flush=True)
    input()
    print("Recording... Press Enter to stop.", flush=True)
    with sd.InputStream(
        samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=callback, device=device,
    ):
        input()
    if not chunks:
        raise RuntimeError("No microphone samples were captured")
    samples = np.concatenate(chunks, axis=0)
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(SAMPLE_RATE)
        audio.writeframes(samples.tobytes())
    return {
        "ok": True, "audio": str(output), "sample_rate": SAMPLE_RATE,
        "channels": 1, "duration_seconds": len(samples) / SAMPLE_RATE,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--device", type=int)
    args = parser.parse_args()
    try:
        if args.list_devices:
            result = device_report()
        elif args.output:
            result = record(args.output, args.device)
        else:
            parser.error("Use --list-devices or --output PATH")
            return 2
        print(json.dumps(result, ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}, ensure_ascii=False), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
