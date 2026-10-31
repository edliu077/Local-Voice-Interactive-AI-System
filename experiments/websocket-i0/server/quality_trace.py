"""Opt-in, local conversation-quality trace. Never participates in decisions."""
from __future__ import annotations

# Rebuild paths must be configured before third-party imports.
import sys as _rebuild_sys
from pathlib import Path as _RebuildPath
_rebuild_sys.path.insert(0, str(_RebuildPath(__file__).resolve().parents[3]))
from rebuild_config import ROOT as REBUILD_ROOT, owned_path, STT_SNAPSHOT, TTS_MODEL, VAD_REPOSITORY, CPU_PYTHON
from rebuild_config import LLM_BASE_URL as REBUILD_LLM_URL, MODEL_ALIAS as REBUILD_MODEL_ALIAS


import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any


TRACE_ENV = "CYBER_QUALITY_TRACE"
TRACE_DIR = owned_path(REBUILD_ROOT / "experiments" / "websocket-i0" / "diagnostics" / "quality-traces")
MAX_SESSION_FILES = 8
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_RECORD_BYTES = 512 * 1024
_SAFE_ID = re.compile(r"^[0-9a-f-]{36}$")


class QualityTrace:
    """Append captured values without ever interrupting the voice pipeline."""

    def __init__(self, path: Path, session_id: str, initial_bytes: int) -> None:
        self.path = path
        self.session_id = session_id
        self.bytes_written = initial_bytes
        self.closed_for_limit = False

    @classmethod
    def for_session(
        cls, session_id: str, source_path: Path, system_prompt: str,
        *, directory: Path = TRACE_DIR,
    ) -> QualityTrace | None:
        if os.environ.get(TRACE_ENV) != "1" or not _SAFE_ID.fullmatch(session_id):
            return None
        try:
            directory = owned_path(directory)
            directory.mkdir(parents=True, exist_ok=True)
            # Never remove or overwrite a prior trace. A full directory disables
            # new traces until the user manually removes old files.
            if sum(1 for item in directory.glob("quality-*.jsonl") if item.is_file()) >= MAX_SESSION_FILES:
                return None
            source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
            prompt_hash = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()
            path = directory / f"quality-{session_id}.jsonl"
            header = {
                "label": "CAPTURED", "event": "session_source", "session_id": session_id,
                "turn_id": 0, "timestamp": time.time(),
                "data": {"source_path": str(source_path), "source_sha256": source_hash,
                         "system_prompt_sha256": prompt_hash},
            }
            encoded = (json.dumps(header, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            with path.open("xb") as handle:
                handle.write(encoded)
            return cls(path, session_id, len(encoded))
        except (OSError, ValueError, TypeError):
            return None

    def record(self, event: str, turn_id: int, data: dict[str, Any]) -> None:
        if self.closed_for_limit:
            return
        try:
            entry = {"label": "CAPTURED", "event": event, "session_id": self.session_id,
                     "turn_id": turn_id, "timestamp": time.time(), "data": data}
            encoded = (json.dumps(entry, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            if len(encoded) > MAX_RECORD_BYTES or self.bytes_written + len(encoded) > MAX_FILE_BYTES:
                marker = {"label": "DIAGNOSTIC", "event": "trace_limit_reached",
                          "session_id": self.session_id, "turn_id": turn_id,
                          "timestamp": time.time(),
                          "data": {"omitted_event": event, "reason": "size_limit"}}
                marker_bytes = (json.dumps(marker, separators=(",", ":")) + "\n").encode("utf-8")
                if self.bytes_written + len(marker_bytes) <= MAX_FILE_BYTES:
                    with self.path.open("ab") as handle:
                        handle.write(marker_bytes)
                    self.bytes_written += len(marker_bytes)
                self.closed_for_limit = True
                return
            with self.path.open("ab") as handle:
                handle.write(encoded)
            self.bytes_written += len(encoded)
        except (OSError, ValueError, TypeError):
            # Observability must not change generation, retry, or summary behavior.
            self.closed_for_limit = True
