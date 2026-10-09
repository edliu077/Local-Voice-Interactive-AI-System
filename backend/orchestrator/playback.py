"""Windows synchronous WAV playback with project-path validation."""
from __future__ import annotations
import sys
from pathlib import Path
import time
import wave
import winsound

COMMON_DIR = Path(__file__).resolve().parents[1] / "common"
sys.path.insert(0, str(COMMON_DIR))
from lviai_config import configured_path, project_root  # noqa: E402

PROJECT = project_root(__file__)
RUNTIME_ROOT = configured_path("LVIAI_RUNTIME_ROOT", PROJECT / "runtime")

def validate_wav(raw: str | Path) -> tuple[Path, dict[str, float | int]]:
    path = Path(raw).resolve()
    try: path.relative_to(RUNTIME_ROOT)
    except ValueError as exc: raise ValueError(f"Playback path must remain under {RUNTIME_ROOT}") from exc
    if path.suffix.lower() != ".wav" or not path.is_file() or path.stat().st_size == 0: raise ValueError("Playback path must be a non-empty project WAV")
    with wave.open(str(path), "rb") as audio:
        meta={"channels":audio.getnchannels(),"sample_width":audio.getsampwidth(),"sample_rate":audio.getframerate(),"duration_seconds":audio.getnframes()/float(audio.getframerate())}
    return path, meta

def play_sync(raw: str | Path) -> dict[str, object]:
    path, meta = validate_wav(raw); started=time.perf_counter()
    winsound.PlaySound(str(path), winsound.SND_FILENAME)
    elapsed=time.perf_counter()-started
    return {"wav_path":str(path),**meta,"playback_seconds":elapsed,"playback_overhead_seconds":elapsed-float(meta["duration_seconds"]),"backend":"winsound","mode":"synchronous half-duplex"}
