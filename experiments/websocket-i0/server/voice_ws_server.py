"""I0 local-only WebSocket event bridge for the validated H2 voice chain."""
from __future__ import annotations

# Rebuild paths must be configured before third-party imports.
import sys as _rebuild_sys
from pathlib import Path as _RebuildPath
_rebuild_sys.path.insert(0, str(_RebuildPath(__file__).resolve().parents[3]))
from rebuild_config import ROOT as REBUILD_ROOT, owned_path, STT_SNAPSHOT, TTS_MODEL, VAD_REPOSITORY, CPU_PYTHON
from rebuild_config import LLM_BASE_URL as REBUILD_LLM_URL, MODEL_ALIAS as REBUILD_MODEL_ALIAS


import argparse
import asyncio
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import sys
import time
import traceback
from typing import Any
from uuid import uuid4

import psutil
from opencc import OpenCC
from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from bounded_context import (
    HARD_RAW_TURN_CAP,
    RECENT_RAW_TURNS,
    ProtectedMemory,
    apply_summary_result,
    build_llm_history,
    build_summary_request,
    capture_user_facts,
    enforce_hard_raw_turn_cap,
    preserve_protected_summary,
    select_turns_to_compact,
    summary_rejection_reason,
)
from emotion_parser import (
    EMPTY_REPLY_FALLBACK,
    ParsedAssistantReply,
    parse_assistant_reply,
    sanitize_tts_text,
)
from evidence_store import EvidenceStore
from memory_recall_guard import (
    MEMORY_RECALL_REPETITION_RETRY_INSTRUCTION,
    MEMORY_RECALL_RETRY_INSTRUCTION,
    contains_false_unknown_claim,
    is_memory_recall_query,
    is_question_reflection,
    with_memory_recall_instruction,
)
from repetition_guard import assess_recent_repetition, recent_assistant_texts
from reply_quality_guard import choose_retry_candidate
from quality_trace import QualityTrace
from stt_evidence import SttEvidence


PROJECT = REBUILD_ROOT.resolve()
H2_CLIENT = PROJECT / "experiments" / "auto-voice-h2" / "client"
G0_CLIENT = PROJECT / "experiments" / "speech-chain-g0" / "client"
LOG_DIR = PROJECT / "experiments" / "websocket-i0" / "logs"
RUNTIME_DIR = PROJECT / "experiments" / "websocket-i0" / "runtime"
INPUT_WAV = PROJECT / "runtime" / "input" / "i0-vad-utterance.wav"
EVENT_LOG = LOG_DIR / "stage-i0-event-log.jsonl"
HOST = "127.0.0.1"
PORT = 8767
PLAYBACK_MODE_ENV = "CYBER_PLAYBACK_MODE"
PLAYBACK_MODES = {"winsound", "browser", "avatar_webrtc"}
MAX_BROWSER_AUDIO_BYTES = 4 * 1024 * 1024
BROWSER_STARTED_TIMEOUT_SECONDS = 10.0
BROWSER_FINISHED_TIMEOUT_MAX_SECONDS = 120.0
MAX_PARTIAL_RAW_MESSAGES = 8
BROWSER_ERROR_CODES = {
    "decode_failed",
    "audio_context_suspended",
    "binary_size_mismatch",
    "playback_start_failed",
    "unexpected_binary",
}
ANTI_REPETITION_RETRY_INSTRUCTION = "重新回答最新一条用户消息。上一条候选回复与最近几轮助手回复过于相似。不要重复或轻微改写最近几轮助手已经使用过的回复，必须直接回应当前用户最新的问题或含义，使用新的具体措辞，不要复用最近的模板句。用简短自然的中文回答。"
SYSTEM_PROMPT = "你是用户的本地中文聊天伙伴，语气自然、温柔、亲近。尚无正式名字，用户取名前不要自创名字。直接回应用户最新的话，通常用一到三句口语化中文，避免客服套话。历史仅作背景；涉及用户事实时以较新的明确陈述或纠正为准，不要把用户的经历说成自己的。不知道就诚实说明，不编造，也不要重复上一轮回复。"

sys.path.insert(0, str(H2_CLIENT))
sys.path.insert(0, str(G0_CLIENT))

# Import the H2 module first so its verified path setup resolves H0 VAD and G0
# HTTP/playback helpers. Importing it does not construct VAD or open a microphone.
import auto_voice_client as h2_client  # noqa: E402

VadCapture = h2_client.VadCapture
play_sync = h2_client.play_sync
health_checks = h2_client.health_checks
llm_reply = h2_client.llm_reply
nvidia_used_mib = h2_client.nvidia_used_mib
tts_reply = h2_client.tts_reply

from speech_chain_client import llm_reply_raw  # noqa: E402


def prepare_assistant_reply(raw_reply: str) -> ParsedAssistantReply:
    """Keep control metadata separate before text reaches history, events, or TTS."""
    return parse_assistant_reply(raw_reply)


def stt_health() -> dict[str, Any]:
    return h2_client.stt_health()


def stt_transcribe(path: Path) -> dict[str, Any]:
    return h2_client.stt(path)


def check_downstream_services() -> dict[str, str]:
    stt = stt_health()
    if stt.get("status") != "ready":
        raise RuntimeError("H1 STT service is not ready at 127.0.0.1:8766")
    llm, tts = health_checks()
    if llm.get("status") != "ok":
        raise RuntimeError("llama.cpp service is not ready at configured Rebuild LLM")
    if tts.get("status") != "ready":
        raise RuntimeError("E0-E TTS service is not ready at 127.0.0.1:8765")
    return {"stt": "ready", "llm": "ready", "tts": "ready"}


@dataclass
class BrowserPlayback:
    audio_id: str
    turn_id: int
    duration_seconds: float | None
    state: str = "pending_started"
    changed: asyncio.Event = field(default_factory=asyncio.Event)


@dataclass
class SessionContext:
    websocket: ServerConnection
    session_id: str
    history: list[dict[str, str]] = field(default_factory=lambda: [{"role": "system", "content": SYSTEM_PROMPT}])
    conversation_summary: str = ""
    summary_revision: int = 0
    summary_source_turn_count: int = 0
    protected_memory: ProtectedMemory = field(default_factory=ProtectedMemory)
    evidence_store: EvidenceStore = field(init=False)
    evidence_history_ids: list[str] = field(default_factory=list)
    evidence_history_turn_ids: list[int] = field(default_factory=list)
    completed_turn_ids: set[int] = field(default_factory=set)
    turn_id: int = 0
    stop_requested: asyncio.Event = field(default_factory=asyncio.Event)
    conversation_task: asyncio.Task[None] | None = None
    browser_playback: BrowserPlayback | None = None
    playback_mode: str = 'browser'
    avatar_binding: dict[str, Any] | None = None
    avatar_metadata: dict[str, Any] | None = None
    max_turns: int | None = None
    stop_reason: str | None = None
    quality_trace: QualityTrace | None = None

    def __post_init__(self) -> None:
        self.evidence_store = EvidenceStore(self.session_id)


class VoiceBridge:
    def __init__(self, playback_mode: str) -> None:
        if playback_mode not in PLAYBACK_MODES:
            raise ValueError(f"Unsupported playback mode: {playback_mode}")
        self.playback_mode = playback_mode
        self.vad: VadCapture | None = None
        self.opencc: OpenCC | None = None
        self.service_health: dict[str, str] | None = None
        self.active: SessionContext | None = None
        self.connection_lock = asyncio.Lock()
        self.event_log_lock = asyncio.Lock()
        self.stt_evidence = SttEvidence.from_environment(PROJECT)

    def startup(self) -> None:
        """Validate loopback dependencies first, then load only CPU Silero VAD."""
        self.service_health = check_downstream_services()
        self.opencc = OpenCC("t2s")
        self.vad = VadCapture()
        rss = psutil.Process().memory_info().rss
        if rss > 1024 * 1024 * 1024:
            raise RuntimeError("I0 server RSS exceeds 1 GiB after VAD startup")
        if rss > 700 * 1024 * 1024:
            print(f"WARNING: I0 server RSS after VAD startup is {rss} bytes", flush=True)
        print(json.dumps({"event": "i0_ready", "host": HOST, "port": PORT, "rss_bytes": rss}, ensure_ascii=False), flush=True)

    async def append_event_log(self, event: dict[str, Any]) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
        async with self.event_log_lock:
            with EVENT_LOG.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())

    async def emit(self, context: SessionContext, event_type: str, data: dict[str, Any] | None = None, *, turn_id: int | None = None) -> bool:
        event = {
            "type": event_type,
            "timestamp": time.time(),
            "session_id": context.session_id,
            "turn_id": context.turn_id if turn_id is None else turn_id,
            "data": data or {},
        }
        await self.append_event_log(event)
        try:
            await context.websocket.send(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
            return True
        except ConnectionClosed:
            context.stop_reason = "disconnect"
            context.stop_requested.set()
            return False

    async def set_state(self, context: SessionContext, state: str, *, turn_id: int | None = None) -> bool:
        return await self.emit(context, "state", {"state": state}, turn_id=turn_id)

    async def protocol_warning(self, context: SessionContext, message: str) -> None:
        await self.append_event_log({
            "type": "protocol_warning",
            "timestamp": time.time(),
            "session_id": context.session_id,
            "turn_id": context.turn_id,
            "data": {"message": message, "recoverable": True},
        })

    @staticmethod
    def completed_pair_starts(context: SessionContext) -> list[int]:
        """Only playback-completed turns are eligible; evidence metadata may age out."""
        if len(context.evidence_history_ids) != len(context.history) - 1 or len(context.evidence_history_turn_ids) != len(context.evidence_history_ids):
            raise RuntimeError("evidence/history alignment lost")
        starts: list[int] = []
        index = 1
        while index + 1 < len(context.history):
            turn_index = index - 1
            turn_id = context.evidence_history_turn_ids[turn_index]
            if (context.history[index].get("role") == "user"
                    and context.history[index + 1].get("role") == "assistant"
                    and context.evidence_history_turn_ids[turn_index + 1] == turn_id
                    and turn_id in context.completed_turn_ids):
                starts.append(index)
                index += 2
            else:
                index += 1
        return starts

    @staticmethod
    def remove_sidecar_positions(context: SessionContext, positions: set[int]) -> tuple[str, ...]:
        """Positions are history indices; update both aligned raw sidecars together."""
        if len(context.evidence_history_ids) != len(context.history) - 1 or len(context.evidence_history_turn_ids) != len(context.evidence_history_ids):
            raise RuntimeError("evidence/history alignment lost before removal")
        removed_ids = tuple(context.evidence_history_ids[index - 1] for index in sorted(positions))
        context.evidence_history_ids = [item for index, item in enumerate(context.evidence_history_ids, 1) if index not in positions]
        context.evidence_history_turn_ids = [item for index, item in enumerate(context.evidence_history_turn_ids, 1) if index not in positions]
        context.completed_turn_ids.intersection_update(context.evidence_history_turn_ids)
        return removed_ids

    async def bound_partial_history(self, context: SessionContext) -> None:
        """Bound incomplete raw turns; source loss is explicit, never called summary."""
        if len(context.evidence_history_ids) != len(context.history) - 1 or len(context.evidence_history_turn_ids) != len(context.evidence_history_ids):
            raise RuntimeError("evidence/history alignment lost before partial cap")
        partial_turns = list(dict.fromkeys(
            turn_id for turn_id in context.evidence_history_turn_ids
            if turn_id not in context.completed_turn_ids
        ))
        partial_count = sum(turn_id not in context.completed_turn_ids for turn_id in context.evidence_history_turn_ids)
        while partial_count > MAX_PARTIAL_RAW_MESSAGES:
            oldest_turn = partial_turns.pop(0)
            positions = {index for index, turn_id in enumerate(context.evidence_history_turn_ids, 1)
                         if turn_id == oldest_turn}
            removed_messages = tuple(context.history[index] for index in sorted(positions))
            removed_evidence_ids = self.remove_sidecar_positions(context, positions)
            context.history = [message for index, message in enumerate(context.history) if index not in positions]
            context.evidence_store.mark_raw_removed(removed_evidence_ids, "interrupted_cap", None)
            availability = [context.evidence_store.availability(item, context.evidence_history_ids)
                            for item in removed_evidence_ids]
            await self.append_event_log({
                "type": "interrupted_history_cap_applied", "timestamp": time.time(),
                "session_id": context.session_id, "turn_id": oldest_turn,
                "data": {"evidence_ids": removed_evidence_ids,
                         "message_roles": [message["role"] for message in removed_messages],
                         "availability": availability, "summary_claimed": False},
            })
            partial_count -= len(positions)

    async def compact_history_if_needed(self, context: SessionContext) -> None:
        completed_starts = self.completed_pair_starts(context)
        selected_messages, compressed_turns = select_turns_to_compact(
            context.history,
            RECENT_RAW_TURNS,
            completed_starts=completed_starts,
        )
        if compressed_turns == 0:
            return

        try:
            summary_request = build_summary_request(context.conversation_summary, selected_messages)
            if context.quality_trace is not None:
                context.quality_trace.record("summary_request", context.turn_id, {
                    "summary_revision_before": context.summary_revision,
                    "summary_text_before": context.conversation_summary,
                    "history_before": context.history,
                    "selected_raw_messages": selected_messages,
                    "compressed_turns": compressed_turns,
                    "request_messages": summary_request,
                    "protected_user_facts": context.protected_memory.lines(),
                    "superseded_fruits": context.protected_memory.superseded_fruits,
                })
            raw_summary, _summary_latency, _summary_tokens_per_second = await asyncio.to_thread(
                llm_reply_raw,
                summary_request,
            )
            if context.quality_trace is not None:
                context.quality_trace.record("summary_candidate", context.turn_id, {
                    "raw_candidate": raw_summary,
                })
            updated_history, updated_summary, applied = apply_summary_result(
                context.history,
                context.conversation_summary,
                raw_summary,
                compressed_turns,
                protected_memory=context.protected_memory,
                completed_starts=completed_starts,
            )
            if not applied:
                rejection_reason = summary_rejection_reason(
                    raw_summary, compressed_turns, context.protected_memory,
                )
                raise ValueError(f"summary rejected: {rejection_reason}")
            if len(context.evidence_history_ids) != len(context.history) - 1:
                raise RuntimeError("evidence/history alignment lost before summary commit")
            removed_positions = {index for start in completed_starts[:compressed_turns]
                                 for index in (start, start + 1)}
            removed_evidence_ids = self.remove_sidecar_positions(context, removed_positions)
            context.history = updated_history
            context.conversation_summary = updated_summary
            context.summary_revision += 1
            context.summary_source_turn_count += compressed_turns
            context.evidence_store.mark_raw_removed(
                removed_evidence_ids, "summary", context.summary_revision,
            )
            if context.quality_trace is not None:
                context.quality_trace.record("evidence_source_transition", context.turn_id, {
                    "reason": "summary", "summary_revision": context.summary_revision,
                    "evidence_ids": removed_evidence_ids,
                    "availability": [context.evidence_store.availability(item, context.evidence_history_ids)
                                     for item in removed_evidence_ids],
                })
            if context.quality_trace is not None:
                context.quality_trace.record("summary_accepted", context.turn_id, {
                    "summary_revision_after": context.summary_revision,
                    "accepted_summary": context.conversation_summary,
                    "removed_raw_messages": selected_messages,
                    "history_after": context.history,
                    "protected_user_facts": context.protected_memory.lines(),
                    "superseded_fruits": context.protected_memory.superseded_fruits,
                })
            await self.append_event_log({
                "type": "conversation_summary_updated",
                "timestamp": time.time(),
                "session_id": context.session_id,
                "turn_id": context.turn_id,
                "data": {
                    "revision": context.summary_revision,
                    "compressed_turns": compressed_turns,
                    "summary_chars": len(updated_summary),
                    "summary_source_turn_count": context.summary_source_turn_count,
                },
            })
        except Exception as exc:
            context.evidence_store.note_summary_rejected()
            if context.quality_trace is not None:
                context.quality_trace.record("summary_failed", context.turn_id, {
                    "error_type": type(exc).__name__,
                    "reason": str(exc) if isinstance(exc, ValueError) and str(exc).startswith("summary rejected: ") else "summary_call_or_apply_failed",
                    "pending_turns": compressed_turns,
                })
            await self.append_event_log({
                "type": "conversation_summary_failed",
                "timestamp": time.time(),
                "session_id": context.session_id,
                "turn_id": context.turn_id,
                "data": {
                    "error_type": type(exc).__name__,
                    "pending_turns": compressed_turns,
                },
            })
            capped_history, dropped_turns = enforce_hard_raw_turn_cap(
                context.history,
                HARD_RAW_TURN_CAP,
                completed_starts=completed_starts,
            )
            if dropped_turns:
                if len(context.evidence_history_ids) != len(context.history) - 1:
                    raise RuntimeError("evidence/history alignment lost before hard-cap commit")
                removed_positions = {index for start in completed_starts[:dropped_turns]
                                     for index in (start, start + 1)}
                removed_evidence_ids = tuple(context.evidence_history_ids[index - 1]
                                             for index in sorted(removed_positions))
                protected_summary = preserve_protected_summary(
                    context.conversation_summary, context.protected_memory,
                )
                if protected_summary != context.conversation_summary:
                    context.conversation_summary = protected_summary
                    context.summary_revision += 1
                removed_raw_messages = [context.history[index] for index in sorted(removed_positions)]
                self.remove_sidecar_positions(context, removed_positions)
                context.history = capped_history
                context.evidence_store.mark_raw_removed(removed_evidence_ids, "hard_cap", None)
                if context.quality_trace is not None:
                    context.quality_trace.record("evidence_source_transition", context.turn_id, {
                        "reason": "hard_cap", "summary_revision": None,
                        "evidence_ids": removed_evidence_ids,
                        "availability": [context.evidence_store.availability(item, context.evidence_history_ids)
                                         for item in removed_evidence_ids],
                    })
                if context.quality_trace is not None:
                    context.quality_trace.record("hard_cap_applied", context.turn_id, {
                        "dropped_turns": dropped_turns,
                        "removed_raw_messages": removed_raw_messages,
                        "history_after": context.history,
                        "protected_summary": context.conversation_summary,
                        "summary_revision_after": context.summary_revision,
                    })
                await self.append_event_log({
                    "type": "conversation_history_hard_cap_applied",
                    "timestamp": time.time(),
                    "session_id": context.session_id,
                    "turn_id": context.turn_id,
                    "data": {
                        "dropped_turns": dropped_turns,
                        "hard_raw_turn_cap": HARD_RAW_TURN_CAP,
                    },
                })

    @staticmethod
    def safe_browser_wav_bytes(audio_path: str) -> bytes:
        root = (PROJECT / "runtime" / "tts").resolve()
        candidate = Path(audio_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise RuntimeError("TTS audio path is outside the approved runtime directory") from exc
        if not candidate.is_file():
            raise FileNotFoundError("TTS audio output is missing")
        size = candidate.stat().st_size
        if size <= 0:
            raise RuntimeError("TTS audio output is empty")
        if size > MAX_BROWSER_AUDIO_BYTES:
            raise RuntimeError(f"audio_too_large: {size} bytes exceeds {MAX_BROWSER_AUDIO_BYTES} bytes")
        return candidate.read_bytes()

    async def send_browser_audio(self, context: SessionContext, turn_id: int, tts: dict[str, Any]) -> BrowserPlayback:
        if context.playback_mode == 'avatar_webrtc':
            raise RuntimeError('Old WAV delivery forbidden for avatar_webrtc')
        audio_bytes = await asyncio.to_thread(self.safe_browser_wav_bytes, str(tts["audio_path"]))
        playback = BrowserPlayback(
            audio_id=uuid4().hex,
            turn_id=turn_id,
            duration_seconds=float(tts["duration_seconds"]) if isinstance(tts.get("duration_seconds"), (int, float)) else None,
        )
        context.browser_playback = playback
        delivered = await self.emit(
            context,
            "audio_ready",
            {
                "transport": "websocket_binary",
                "audio_id": playback.audio_id,
                "byte_length": len(audio_bytes),
                "content_type": "audio/wav",
                "duration_seconds": tts.get("duration_seconds"),
                "sample_rate": tts.get("sample_rate"),
            },
            turn_id=turn_id,
        )
        if not delivered:
            raise RuntimeError("browser disconnected before audio delivery")
        try:
            await context.websocket.send(audio_bytes)
        except ConnectionClosed as exc:
            context.stop_requested.set()
            raise RuntimeError("browser disconnected during binary audio delivery") from exc
        return playback

    async def avatar_request(self, action: str, data: dict[str, Any]) -> dict[str, Any]:
        import importlib.util
        path = PROJECT / 'experiments/avatar-bridge/production_client.py'
        spec = importlib.util.spec_from_file_location('ws_avatar_control', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return await asyncio.to_thread(module.control_request, action, data)

    async def send_avatar_audio(self, context: SessionContext, turn_id: int, tts: dict[str, Any]) -> BrowserPlayback:
        binding = context.avatar_binding
        if not binding or context.playback_mode != 'avatar_webrtc':
            raise RuntimeError('No bound avatar session')
        playback = BrowserPlayback(uuid4().hex, turn_id, tts.get('duration_seconds'))
        context.browser_playback = playback
        metadata = dict(control_id=binding['control_id'], sessionid=binding['sessionid'],
                        bridge_turn_id=context.session_id+':'+str(turn_id), ws_session_id=context.session_id,
                        turn_id=turn_id, audio_id=playback.audio_id,
                        duration_seconds=tts.get('duration_seconds'), transport='avatar_webrtc')
        if not await self.emit(context, 'avatar_audio_pending', metadata, turn_id=turn_id):
            raise RuntimeError('Browser disconnected before avatar submission')
        result = await self.avatar_request('audio', dict(control_id=binding['control_id'],
            ws_session_id=context.session_id, turn_id=turn_id, audio_id=playback.audio_id, tts=tts))
        metadata = result['data']
        context.avatar_metadata = metadata
        playback.duration_seconds = metadata['duration_seconds']
        if not await self.emit(context, 'audio_ready', metadata, turn_id=turn_id):
            raise RuntimeError('Browser disconnected during avatar acknowledgement')
        return playback

    async def handle_avatar_playback_control(self, context: SessionContext, command: dict[str, Any]) -> None:
        metadata = context.avatar_metadata
        if (not metadata or any(command.get(k) != metadata.get(k) for k in ('sessionid','bridge_turn_id','generation'))):
            await self.protocol_warning(context, 'ignored stale avatar identity or generation')
            return
        mapping = {'avatar_playback_started':'browser_playback_started',
                   'avatar_playback_estimated_finished':'browser_playback_finished',
                   'avatar_playback_cancelled':'browser_playback_cancelled',
                   'avatar_playback_error':'audio_playback_error'}
        kind = command.get('type')
        if kind == 'avatar_playback_estimated_finished' and command.get('completion_semantics') != 'bounded_media_estimate':
            await self.protocol_warning(context, 'avatar completion semantics missing')
            return
        if kind not in mapping:return
        # Reuse bounded half-duplex acknowledgement state; the wire event is
        # distinct, and never claims an exact browser/speaker end signal.
        await self.handle_browser_playback_control(context, dict(command, type=mapping[kind]))

    async def wait_for_browser_state(
        self,
        context: SessionContext,
        playback: BrowserPlayback,
        expected_state: str,
        timeout_seconds: float,
    ) -> None:
        deadline = time.monotonic() + timeout_seconds
        while playback.state != expected_state:
            if context.stop_requested.is_set():
                raise RuntimeError("browser playback stopped or disconnected")
            if playback.state in {"error", "cancelled"}:
                raise RuntimeError(f"browser playback {playback.state}")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(f"browser playback {expected_state} acknowledgement timed out")
            await asyncio.wait_for(playback.changed.wait(), timeout=remaining)
            playback.changed.clear()

    async def handle_browser_playback_control(self, context: SessionContext, command: dict[str, Any]) -> None:
        command_type = command.get("type")
        playback = context.browser_playback
        turn_id = command.get("turn_id")
        audio_id = command.get("audio_id")
        if playback is None or turn_id != playback.turn_id or audio_id != playback.audio_id:
            await self.protocol_warning(context, f"ignored stale or malformed {command_type}")
            return
        if command_type == "browser_playback_started":
            if playback.state != "pending_started":
                await self.protocol_warning(context, "ignored duplicate or out-of-order browser_playback_started")
                return
            playback.state = "started"
        elif command_type == "browser_playback_finished":
            if playback.state != "started":
                await self.protocol_warning(context, "ignored browser_playback_finished before started or after completion")
                return
            playback.state = "finished"
        elif command_type == "browser_playback_cancelled":
            if playback.state not in {"pending_started", "started"}:
                await self.protocol_warning(context, "ignored duplicate browser_playback_cancelled")
                return
            playback.state = "cancelled"
            context.stop_requested.set()
        elif command_type == "audio_playback_error":
            code = command.get("code")
            if not isinstance(code, str) or code not in BROWSER_ERROR_CODES:
                await self.protocol_warning(context, "ignored audio_playback_error with unsupported code")
                return
            if playback.state not in {"pending_started", "started"}:
                await self.protocol_warning(context, "ignored audio_playback_error after playback completion")
                return
            playback.state = "error"
        else:
            await self.protocol_warning(context, f"ignored unsupported browser playback control: {command_type}")
            return
        playback.changed.set()

    async def reject_second_connection(self, websocket: ServerConnection) -> None:
        event = {
            "type": "error",
            "timestamp": time.time(),
            "session_id": str(uuid4()),
            "turn_id": 0,
            "data": {"message": "another active session already exists", "recoverable": True},
        }
        await self.append_event_log(event)
        await websocket.send(json.dumps(event, ensure_ascii=False, separators=(",", ":")))
        await websocket.close(code=4001, reason="one active conversation client")

    async def handler(self, websocket: ServerConnection) -> None:
        context: SessionContext | None = None
        reject = False
        async with self.connection_lock:
            if self.active is not None:
                reject = True
            else:
                context = SessionContext(websocket=websocket, session_id=str(uuid4()))
                context.playback_mode = self.playback_mode
                self.active = context

        if reject:
            await self.reject_second_connection(websocket)
            return
        if context is None:
            raise RuntimeError("I0 active-session initialization failed")

        context.quality_trace = QualityTrace.for_session(
            context.session_id, Path(__file__).resolve(), SYSTEM_PROMPT,
        )

        try:
            health = await asyncio.to_thread(check_downstream_services)
            health["vad"] = "ready"
            health["playback_mode"] = self.playback_mode
            health['supported_playback_modes'] = sorted(PLAYBACK_MODES)
            if not await self.emit(context, "session_ready", health, turn_id=0):
                return

            async for raw_message in websocket:
                if not isinstance(raw_message, str):
                    await self.protocol_warning(context, "ignored unexpected binary control frame")
                    continue
                try:
                    command = json.loads(raw_message)
                except json.JSONDecodeError:
                    await self.emit(context, "error", {"message": "invalid JSON control message", "recoverable": True}, turn_id=0)
                    continue
                command_type = command.get("type") if isinstance(command, dict) else None
                if command_type == "start":
                    if context.conversation_task is not None and not context.conversation_task.done():
                        await self.emit(context, "error", {"message": "conversation is already active", "recoverable": True}, turn_id=context.turn_id)
                        continue
                    requested = command.get('playback_mode',self.playback_mode)
                    rounds = command.get('max_turns') if command.get('development_test') is True else None
                    if requested not in PLAYBACK_MODES or (rounds is not None and (type(rounds) is not int or rounds not in (1,2,6))):
                        await self.emit(context,'error',dict(message='invalid playback mode or turn count',recoverable=True))
                        continue
                    if requested == 'avatar_webrtc':
                        binding = command.get('avatar_binding')
                        if not isinstance(binding,dict):
                            await self.emit(context,'error',dict(message='avatar binding required',recoverable=True));continue
                        try:
                            await self.avatar_request('bind',dict(binding,ws_session_id=context.session_id))
                        except Exception:
                            await self.emit(context,'error',dict(message='avatar binding rejected',recoverable=True));continue
                        context.avatar_binding=binding
                    else:context.avatar_binding=None
                    context.playback_mode=requested;context.max_turns=rounds
                    context.stop_requested.clear()
                    context.stop_reason = None
                    context.conversation_task = asyncio.create_task(self.run_conversation(context))
                elif command_type == "stop":
                    context.stop_reason = "client_stop"
                    context.stop_requested.set()
                    await self.close_avatar(context)
                    if context.browser_playback is not None and context.browser_playback.state in {"pending_started", "started"}:
                        context.browser_playback.state = "cancelled"
                        context.browser_playback.changed.set()
                    if context.conversation_task is None or context.conversation_task.done():
                        await self.set_state(context, "IDLE", turn_id=context.turn_id)
                        await self.emit(context, "session_stopped", {"reason": "client_stop"}, turn_id=context.turn_id)
                        return
                elif command_type in {
                    "browser_playback_started",
                    "browser_playback_finished",
                    "browser_playback_cancelled",
                    "audio_playback_error",
                }:
                    if context.playback_mode != "browser":
                        await self.protocol_warning(context, f"ignored {command_type} outside browser playback mode")
                    else:
                        await self.handle_browser_playback_control(context, command)
                elif command_type in {'avatar_playback_started','avatar_playback_estimated_finished','avatar_playback_cancelled','avatar_playback_error'}:
                    if context.playback_mode == 'avatar_webrtc':
                        await self.handle_avatar_playback_control(context,command)
                    else:await self.protocol_warning(context,'avatar feedback outside avatar mode')
                else:
                    await self.emit(context, "error", {"message": "unsupported control message", "recoverable": True}, turn_id=0)
        except ConnectionClosed:
            context.stop_reason = "disconnect"
            context.stop_requested.set()
        finally:
            if context.stop_reason is None:
                context.stop_reason = "disconnect"
            context.stop_requested.set()
            await self.close_avatar(context)
            if context.browser_playback is not None and context.browser_playback.state in {"pending_started", "started"}:
                context.browser_playback.state = "cancelled"
                context.browser_playback.changed.set()
            if context.conversation_task is not None and not context.conversation_task.done():
                # Blocking H2 calls may finish first; the task checks this flag before
                # another turn. Keep the single active-session reservation until then.
                await context.conversation_task
            async with self.connection_lock:
                if self.active is context:
                    self.active = None

    async def close_avatar(self, context: SessionContext) -> None:
        binding=context.avatar_binding
        if context.playback_mode!='avatar_webrtc' or not binding:return
        context.avatar_binding=None
        try:
            await self.avatar_request('cancel',dict(control_id=binding['control_id'],ws_session_id=context.session_id))
        except Exception as exc:
            # Keep the original failure visible; never reconnect or resynthesize.
            print('Avatar binding cleanup:',type(exc).__name__,str(exc),file=sys.stderr,flush=True)

    async def capture_once(self, context: SessionContext) -> dict[str, Any]:
        if self.vad is None:
            raise RuntimeError("VAD is not initialized")
        loop = asyncio.get_running_loop()
        status_queue: asyncio.Queue[str] = asyncio.Queue()

        def status_callback(message: str) -> None:
            loop.call_soon_threadsafe(status_queue.put_nowait, message)

        capture_task = asyncio.create_task(asyncio.to_thread(self.vad.capture_once, INPUT_WAV, status_callback, context.stop_requested))
        speech_started_sent = False
        while not capture_task.done():
            try:
                status = await asyncio.wait_for(status_queue.get(), timeout=0.2)
            except asyncio.TimeoutError:
                continue
            if status == "Speech started." and not speech_started_sent:
                speech_started_sent = True
                await self.emit(context, "speech_started", {}, turn_id=context.turn_id + 1)
        capture = await capture_task
        if capture.get("status") == "OK":
            if not speech_started_sent:
                await self.emit(context, "speech_started", {}, turn_id=context.turn_id + 1)
            await self.emit(
                context,
                "speech_ended",
                {"utterance_duration_seconds": capture.get("utterance_duration_seconds")},
                turn_id=context.turn_id + 1,
            )
        return capture

    async def run_conversation(self, context: SessionContext) -> None:
        try:
            first_turn = context.turn_id
            while not context.stop_requested.is_set() and (context.max_turns is None or context.turn_id-first_turn < context.max_turns):
                await self.set_state(context, "LISTENING", turn_id=context.turn_id + 1)
                capture = await self.capture_once(context)
                if context.stop_requested.is_set():
                    break
                if capture.get("status") == "NO_SPEECH":
                    await self.emit(context, "no_speech", {"wait_seconds": capture.get("wait_seconds")}, turn_id=context.turn_id)
                    await self.set_state(context, "LISTENING", turn_id=context.turn_id + 1)
                    continue

                context.turn_id += 1
                turn_id = context.turn_id
                await self.set_state(context, "TRANSCRIBING", turn_id=turn_id)
                evidence = self.stt_evidence
                ticket = (await asyncio.to_thread(evidence.begin, context.session_id, turn_id,
                          INPUT_WAV, context.stop_requested.is_set)
                          if evidence is not None and capture.get('status') == 'OK' else None)
                stt_started = time.perf_counter()
                try:
                    stt = await asyncio.to_thread(stt_transcribe, INPUT_WAV)
                except Exception as exc:
                    if evidence is not None:
                        await asyncio.to_thread(evidence.fail, ticket, 'stt_request_failed', exc)
                    raise
                stt_http_seconds = time.perf_counter() - stt_started
                if evidence is not None:
                    await asyncio.to_thread(evidence.response, ticket, stt, context.stop_requested.is_set)
                if context.stop_requested.is_set():
                    break
                try:
                    raw_transcript = str(stt.get("text", "")).strip()
                    if not raw_transcript:
                        raise RuntimeError("STT returned an empty transcript")
                    if self.opencc is None:
                        raise RuntimeError("OpenCC t2s converter is not initialized")
                    user_text = self.opencc.convert(raw_transcript).strip()
                    if not user_text:
                        raise RuntimeError("OpenCC normalization returned an empty transcript")
                except Exception as exc:
                    if evidence is not None:
                        await asyncio.to_thread(evidence.fail, ticket, 'normalization_failed', exc)
                    raise
                if evidence is not None:
                    await asyncio.to_thread(evidence.finish, ticket, user_text, context.stop_requested.is_set)
                context.protected_memory = capture_user_facts(
                    context.protected_memory, {"role": "user", "content": user_text},
                )
                if context.quality_trace is not None:
                    context.quality_trace.record("normalized_user_message", turn_id, {
                        "normalized_stt_text": user_text,
                    })
                context.history.append({"role": "user", "content": user_text})
                user_evidence = context.evidence_store.record_message(
                    turn_id, "user", user_text, "stt_opencc", "opencc_t2s",
                )
                context.evidence_history_ids.append(user_evidence.evidence_id)
                context.evidence_history_turn_ids.append(turn_id)
                await self.bound_partial_history(context)
                if context.quality_trace is not None:
                    context.quality_trace.record("evidence_recorded", turn_id, {
                        "evidence_id": user_evidence.evidence_id, "role": "user",
                        "turn_state": "partial", "exact_copy": user_evidence.text is not None,
                    })
                await self.emit(context, "user_transcript", {"text": user_text}, turn_id=turn_id)

                await self.set_state(context, "THINKING", turn_id=turn_id)
                previous_assistant_texts = recent_assistant_texts(context.history)
                base_llm_history = build_llm_history(context.history, context.conversation_summary)
                memory_recall = is_memory_recall_query(user_text)
                generation_history = [dict(message) for message in base_llm_history]
                if memory_recall:
                    generation_history = with_memory_recall_instruction(base_llm_history)
                    await self.append_event_log({
                        "type": "memory_recall_context_applied",
                        "timestamp": time.time(),
                        "session_id": context.session_id,
                        "turn_id": turn_id,
                        "data": {"turn_id": turn_id},
                    })
                if context.quality_trace is not None:
                    context.quality_trace.record("first_request", turn_id, {
                        "history_before_request": context.history,
                        "summary_revision": context.summary_revision,
                        "summary_text_used": context.conversation_summary,
                        "base_messages": base_llm_history,
                        "memory_recall": memory_recall,
                        "request_messages": generation_history,
                        "candidate_id": f"{turn_id}:1",
                    })
                raw_reply, llm_latency, _tokens_per_second = await asyncio.to_thread(llm_reply_raw, generation_history)
                if context.quality_trace is not None:
                    context.quality_trace.record("candidate_raw", turn_id, {
                        "candidate_id": f"{turn_id}:1", "raw_text": raw_reply,
                    })
                if context.stop_requested.is_set():
                    break
                parsed_reply = prepare_assistant_reply(raw_reply)
                if context.quality_trace is not None:
                    context.quality_trace.record("candidate_parsed", turn_id, {
                        "candidate_id": f"{turn_id}:1", "text": parsed_reply.text,
                        "emotion": parsed_reply.emotion,
                    })
                repetition = assess_recent_repetition(parsed_reply.text, previous_assistant_texts, user_text)
                false_unknown = memory_recall and contains_false_unknown_claim(parsed_reply.text)
                question_reflection = memory_recall and is_question_reflection(parsed_reply.text, user_text)
                if false_unknown:
                    retry_reason = "memory_recall_false_unknown"
                elif question_reflection:
                    retry_reason = "memory_recall_question_reflection"
                elif memory_recall and repetition.suspicious:
                    retry_reason = "memory_recall_repetition"
                elif repetition.suspicious:
                    retry_reason = "anti_repetition"
                else:
                    retry_reason = None
                if context.quality_trace is not None:
                    context.quality_trace.record("retry_decision", turn_id, {
                        "triggered": retry_reason is not None, "reason": retry_reason,
                        "memory_recall": memory_recall,
                        "false_unknown": false_unknown,
                        "question_reflection": question_reflection,
                        "repetition_suspicious": repetition.suspicious,
                        "repetition_similarity": repetition.similarity,
                    })
                first_reply = parsed_reply
                selected_candidate_id = f"{turn_id}:1"
                selection_reason = "first_candidate_no_retry"
                if retry_reason is not None:
                    if retry_reason == "memory_recall_false_unknown":
                        await self.append_event_log({
                            "type": "memory_recall_retry",
                            "timestamp": time.time(),
                            "session_id": context.session_id,
                            "turn_id": turn_id,
                            "data": {"triggered": True},
                        })
                        retry_instruction = MEMORY_RECALL_RETRY_INSTRUCTION
                    elif retry_reason == "memory_recall_question_reflection":
                        await self.append_event_log({
                            "type": "memory_recall_question_reflection_retry",
                            "timestamp": time.time(),
                            "session_id": context.session_id,
                            "turn_id": turn_id,
                            "data": {"triggered": True},
                        })
                        retry_instruction = MEMORY_RECALL_RETRY_INSTRUCTION
                    elif retry_reason == "memory_recall_repetition":
                        await self.append_event_log({
                            "type": "memory_recall_repetition_retry",
                            "timestamp": time.time(),
                            "session_id": context.session_id,
                            "turn_id": turn_id,
                            "data": {
                                "triggered": True,
                                "similarity": round(repetition.similarity, 4),
                            },
                        })
                        retry_instruction = MEMORY_RECALL_REPETITION_RETRY_INSTRUCTION
                    else:
                        await self.append_event_log({
                            "type": "anti_repetition_retry",
                            "timestamp": time.time(),
                            "session_id": context.session_id,
                            "turn_id": turn_id,
                            "data": {
                                "triggered": True,
                                "similarity": round(repetition.similarity, 4),
                            },
                        })
                        retry_instruction = ANTI_REPETITION_RETRY_INSTRUCTION
                    retry_history = [dict(message) for message in generation_history]
                    retry_history.insert(len(retry_history) - 1, {
                        "role": "system",
                        "content": retry_instruction,
                    })
                    if context.quality_trace is not None:
                        context.quality_trace.record("retry_request", turn_id, {
                            "candidate_id": f"{turn_id}:2", "reason": retry_reason,
                            "request_messages": retry_history,
                        })
                    raw_retry, retry_latency, _retry_tokens_per_second = await asyncio.to_thread(
                        llm_reply_raw,
                        retry_history,
                    )
                    if context.quality_trace is not None:
                        context.quality_trace.record("candidate_raw", turn_id, {
                            "candidate_id": f"{turn_id}:2", "raw_text": raw_retry,
                        })
                    llm_latency += retry_latency
                    if context.stop_requested.is_set():
                        break
                    try:
                        retry_reply = prepare_assistant_reply(raw_retry)
                    except ValueError:
                        # A bad optional retry cannot discard a usable first reply.
                        retry_reply = first_reply
                    if context.quality_trace is not None:
                        context.quality_trace.record("candidate_parsed", turn_id, {
                            "candidate_id": f"{turn_id}:2", "text": retry_reply.text,
                            "emotion": retry_reply.emotion,
                        })
                    parsed_reply, selection_reason = choose_retry_candidate(
                        first_reply, retry_reply, user_text, previous_assistant_texts, memory_recall,
                    )
                    if parsed_reply is retry_reply:
                        selected_candidate_id = f"{turn_id}:2"
                assistant_text = parsed_reply.text
                emotion = parsed_reply.emotion
                if context.quality_trace is not None:
                    context.quality_trace.record("candidate_selected", turn_id, {
                        "candidate_id": selected_candidate_id,
                        "reason": selection_reason,
                        "retry_reason": retry_reason,
                        "final_text": assistant_text, "final_emotion": emotion,
                    })
                context.history.append({"role": "assistant", "content": assistant_text})
                assistant_evidence = context.evidence_store.record_message(
                    turn_id, "assistant", assistant_text, "selected_reply", "parser_cleaned",
                )
                context.evidence_history_ids.append(assistant_evidence.evidence_id)
                context.evidence_history_turn_ids.append(turn_id)
                await self.bound_partial_history(context)
                if context.quality_trace is not None:
                    context.quality_trace.record("evidence_recorded", turn_id, {
                        "evidence_id": assistant_evidence.evidence_id, "role": "assistant",
                        "turn_state": "partial", "exact_copy": assistant_evidence.text is not None,
                    })
                if await self.emit(context, "assistant_text", {"text": assistant_text, "emotion": emotion}, turn_id=turn_id):
                    context.evidence_store.mark_turn_phase(turn_id, "assistant_text_sent")

                await self.set_state(context, "SYNTHESIZING", turn_id=turn_id)
                tts_text = sanitize_tts_text(assistant_text) or EMPTY_REPLY_FALLBACK
                if context.quality_trace is not None:
                    context.quality_trace.record("final_output", turn_id, {
                        "stored_assistant_text": context.history[-1]["content"],
                        "final_text": assistant_text, "emotion": emotion,
                        "tts_text": tts_text,
                    })
                tts, _tts_http_seconds = await asyncio.to_thread(tts_reply, tts_text)
                if context.stop_requested.is_set():
                    break
                playback_start = time.perf_counter()
                if context.playback_mode in {"browser",'avatar_webrtc'}:
                    playback_wait = (await self.send_avatar_audio(context,turn_id,tts) if context.playback_mode == 'avatar_webrtc'
                                     else await self.send_browser_audio(context, turn_id, tts))
                    try:
                        await self.wait_for_browser_state(
                            context, playback_wait, "started", BROWSER_STARTED_TIMEOUT_SECONDS,
                        )
                    except RuntimeError:
                        if context.stop_requested.is_set() or playback_wait.state == "cancelled":
                            break
                        raise
                    await self.set_state(context, "SPEAKING", turn_id=turn_id)
                    await self.emit(context, "playback_started", {'mode':context.playback_mode,'semantics':'media_flow' if context.playback_mode=='avatar_webrtc' else 'web_audio'}, turn_id=turn_id)
                    context.evidence_store.mark_turn_phase(turn_id, "playback_started")
                    duration = playback_wait.duration_seconds or 0.0
                    finished_timeout = min(
                        BROWSER_FINISHED_TIMEOUT_MAX_SECONDS,
                        max(15.0, duration + 10.0),
                    )
                    try:
                        await self.wait_for_browser_state(context, playback_wait, "finished", finished_timeout)
                    except RuntimeError:
                        if context.stop_requested.is_set() or playback_wait.state == "cancelled":
                            break
                        raise
                    playback = {
                        "backend": "avatar_webrtc" if context.playback_mode=='avatar_webrtc' else "browser_web_audio",
                        "playback_seconds": duration,
                        "mode": context.playback_mode,
                        'completion_semantics':'bounded_media_estimate' if context.playback_mode=='avatar_webrtc' else 'web_audio_onended',
                    }
                    await self.emit(context, "playback_finished", playback, turn_id=turn_id)
                    context.evidence_store.mark_turn_phase(turn_id, "playback_finished")
                    context.browser_playback = None
                    context.avatar_metadata = None
                else:
                    audio_path = str(tts["audio_path"])
                    await self.emit(
                        context,
                        "audio_ready",
                        {
                            "audio_path": audio_path,
                            "duration_seconds": tts.get("duration_seconds"),
                            "sample_rate": tts.get("sample_rate"),
                        },
                        turn_id=turn_id,
                    )
                    await self.set_state(context, "SPEAKING", turn_id=turn_id)
                    await self.emit(context, "playback_started", {}, turn_id=turn_id)
                    context.evidence_store.mark_turn_phase(turn_id, "playback_started")
                    playback = await asyncio.to_thread(play_sync, audio_path)
                    await self.emit(context, "playback_finished", playback, turn_id=turn_id)
                    context.evidence_store.mark_turn_phase(turn_id, "playback_finished")
                await self.emit(
                    context,
                    "turn_complete",
                    {
                        "stt_http_seconds": stt_http_seconds,
                        "llm_latency_seconds": llm_latency,
                        "tts_synthesis_seconds": tts.get("synthesis_seconds"),
                        "speech_end_to_playback_start_seconds": playback_start - float(capture["speech_end_clock"]),
                        "playback_duration_seconds": playback.get("playback_seconds"),
                        "gpu_used_mib": nvidia_used_mib(),
                    },
                    turn_id=turn_id,
                )
                context.evidence_store.mark_turn_completed(turn_id)
                context.completed_turn_ids.add(turn_id)
                if context.quality_trace is not None:
                    context.quality_trace.record("evidence_turn_completed", turn_id, {
                        "evidence_ids": context.evidence_history_ids[-2:],
                    })
                await self.compact_history_if_needed(context)

            if context.max_turns is not None and context.turn_id-first_turn >= context.max_turns and not context.stop_reason:context.stop_reason='max_turns'
            await self.set_state(context, "IDLE", turn_id=context.turn_id)
            await self.emit(
                context,
                "session_stopped",
                {"reason": context.stop_reason or "client_stop"},
                turn_id=context.turn_id,
            )
        except Exception as exc:
            context.stop_reason = "error"
            print(traceback.format_exc(), file=sys.stderr, flush=True)
            await self.set_state(context, "ERROR", turn_id=context.turn_id)
            await self.emit(context, "error", {"message": f"{type(exc).__name__}: {exc}", "recoverable": False}, turn_id=context.turn_id)
            await self.emit(context, "session_stopped", {"reason": "error"}, turn_id=context.turn_id)


async def run_server(host: str, port: int, playback_mode: str) -> None:
    bridge = VoiceBridge(playback_mode)
    await asyncio.to_thread(bridge.startup)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    async def health_response(connection, request):
        if request.path == '/health':
            from http import HTTPStatus
            return connection.respond(HTTPStatus.OK, json.dumps({'status':'ready','services':bridge.service_health,'vad':'cpu','microphone':'windows-default-input'}))
        return None
    async with serve(bridge.handler, host, port, origins=['http://127.0.0.1:3000',None], process_request=health_response, ping_interval=20, ping_timeout=20, max_size=64 * 1024):
        print(f"I0 WebSocket event bridge listening at ws://{host}:{port} ({playback_mode} playback)", flush=True)
        await asyncio.Future()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=HOST, choices=[HOST])
    parser.add_argument("--port", type=int, default=PORT, choices=[PORT])
    args = parser.parse_args()
    playback_mode = os.environ.get(PLAYBACK_MODE_ENV, "winsound").strip().lower()
    if playback_mode not in PLAYBACK_MODES:
        print(f"{PLAYBACK_MODE_ENV} must be one of: {', '.join(sorted(PLAYBACK_MODES))}", file=sys.stderr, flush=True)
        return 1
    try:
        asyncio.run(run_server(args.host, args.port, playback_mode))
    except KeyboardInterrupt:
        return 0
    except Exception:
        print(traceback.format_exc(), file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
