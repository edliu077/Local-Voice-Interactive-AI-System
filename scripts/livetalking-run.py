"""Windows entry point for the pinned, external-audio-only LiveTalking service."""
from pathlib import Path
import os
import runpy
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "third_party/LiveTalking"
sys.path.insert(0, str(REPO))
sys.dont_write_bytecode = True
os.chdir(REPO)
# Local media only: bind ICE sockets to loopback as well as HTTP.
import aioice.ice
aioice.ice.get_host_addresses = lambda use_ipv4, use_ipv6: ["127.0.0.1"] if use_ipv4 else []
# Pinned aiortc 1.14 H264Encoder reads these module constants at construction
# and in its bitrate setter. No installed package or GPU codec is changed.
from aiortc.codecs import h264
h264.DEFAULT_BITRATE = 5_000_000
h264.MIN_BITRATE = 1_000_000
h264.MAX_BITRATE = 8_000_000
# Historical Stage6 evidence must never be a production output directory.
# Optional capture remains explicitly configured and boundary checked by avatar.
# Resolve lazy librosa/numba work before declaring HTTP readiness.
import numpy as np
from avatars.wav2lip import audio as wav2lip_audio
_started = time.perf_counter()
wav2lip_audio.melspectrogram(np.zeros(10240, dtype=np.float32))
print('Rebuild mel prewarm seconds:', time.perf_counter() - _started, flush=True)
sys.argv = [str(REPO / "app.py"), "--config", str(ROOT / "config/livetalking-stage4.yaml")]
runpy.run_path(str(REPO / "app.py"), run_name="__main__")
