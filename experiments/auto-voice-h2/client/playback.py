"""Windows synchronous WAV playback with project-path validation."""
from __future__ import annotations

# Rebuild paths must be configured before third-party imports.
import sys as _rebuild_sys
from pathlib import Path as _RebuildPath
_rebuild_sys.path.insert(0, str(_RebuildPath(__file__).resolve().parents[3]))
from rebuild_config import ROOT as REBUILD_ROOT, owned_path, STT_SNAPSHOT, TTS_MODEL, VAD_REPOSITORY, CPU_PYTHON
from rebuild_config import LLM_BASE_URL as REBUILD_LLM_URL, MODEL_ALIAS as REBUILD_MODEL_ALIAS

from pathlib import Path
import time
import wave
import winsound

PROJECT = REBUILD_ROOT.resolve()

def validate_wav(raw: str | Path) -> tuple[Path, dict[str, float | int]]:
    path = owned_path(raw)
    try: path.relative_to(PROJECT)
    except ValueError as exc: raise ValueError("Playback path must remain under Rebuild") from exc
    if path.suffix.lower() != ".wav" or not path.is_file() or path.stat().st_size == 0: raise ValueError("Playback path must be a non-empty project WAV")
    with wave.open(str(path), "rb") as audio:
        meta={"channels":audio.getnchannels(),"sample_width":audio.getsampwidth(),"sample_rate":audio.getframerate(),"duration_seconds":audio.getnframes()/float(audio.getframerate())}
    return path, meta

def play_sync(raw: str | Path) -> dict[str, object]:
    path, meta = validate_wav(raw); started=time.perf_counter()
    winsound.PlaySound(str(path), winsound.SND_FILENAME)
    elapsed=time.perf_counter()-started
    return {"wav_path":str(path),**meta,"playback_seconds":elapsed,"playback_overhead_seconds":elapsed-float(meta["duration_seconds"]),"backend":"winsound","mode":"synchronous half-duplex"}
