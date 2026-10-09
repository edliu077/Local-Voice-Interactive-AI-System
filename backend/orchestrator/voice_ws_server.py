"""Demo Stable loopback WebSocket bridge for the validated voice chain."""
from __future__ import annotations

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


BACKEND_DIR = Path(__file__).resolve().parents[1]
COMMON_DIR = BACKEND_DIR / "common"
VAD_DIR = BACKEND_DIR / "vad"
sys.path.insert(0, str(COMMON_DIR))
sys.path.insert(0, str(VAD_DIR))

from lviai_config import (  # noqa: E402
    allowed_frontend_origins,
    configured_path,
    loopback_host,
    port,
    project_root,
)
from vad_capture import VadCapture  # noqa: E402
from backend_client import (  # noqa: E402
    health_checks,
    llm_reply,
    nvidia_used_mib,
    stt_health,
    stt_transcribe,
    tts_reply,
)
from playback import play_sync  # noqa: E402


PROJECT = project_root(__file__)
RUNTIME_ROOT = configured_path("LVIAI_RUNTIME_ROOT", PROJECT / "runtime")
LOG_DIR = RUNTIME_ROOT / "logs"
INPUT_WAV = RUNTIME_ROOT / "input" / "i0-vad-utterance.wav"
EVENT_LOG = LOG_DIR / "demo-ws-event-log.jsonl"
HOST = loopback_host("LVIAI_WS_HOST")
PORT = port("LVIAI_WS_PORT", 8767)
FRONTEND_PORT = port("LVIAI_FRONTEND_PORT", 3000)
ALLOWED_ORIGINS = allowed_frontend_origins(FRONTEND_PORT)
PLAYBACK_MODE_ENV = "LVIAI_PLAYBACK_MODE"
PLAYBACK_MODES = {"winsound", "browser"}
MAX_TURNS_ALLOWED = {1, 2, 6}
MAX_RAW_TURNS = 6
MAX_BROWSER_AUDIO_BYTES = 4 * 1024 * 1024
BROWSER_STARTED_TIMEOUT_SECONDS = 10.0
BROWSER_FINISHED_TIMEOUT_MAX_SECONDS = 120.0
BROWSER_ERROR_CODES = {
    "decode_failed",
    "audio_context_suspended",
    "binary_size_mismatch",
    "playback_start_failed",
    "unexpected_binary",
}
SYSTEM_PROMPT = (
    "你是一个本地运行的语音交互AI助手，语气自然、友好、简洁、专业。"
    "不要主动虚构或声称固定个人名字，不要建立恋爱关系、陪伴型角色绑定或二次元角色设定。"
    "当用户问你是谁、要求自我介绍或询问名字时，优先自然回答："
    "‘我是一个本地运行的语音交互AI助手。’不得给出其他固定名字。"
    "认真参考当前 conversation history，不机械重复上一条回复；"
    "不确定的信息不要编造，不知道时自然承认。"
    "默认用简体中文，回复口语化、简短，通常一到三句话；"
    "不要使用 Markdown、标题或列表，除非用户明确要求。"
)


def check_downstream_services() -> dict[str, str]:
    stt = stt_health()
    if stt.get("status") != "ready":
        raise RuntimeError(f"STT service is not ready at 127.0.0.1:{port('LVIAI_STT_PORT', 8766)}")
    llm, tts = health_checks()
    if llm.get("status") != "ok":
        raise RuntimeError(f"llama.cpp is not ready at 127.0.0.1:{port('LVIAI_LLM_PORT', 8080)}")
    if tts.get("status") != "ready":
        raise RuntimeError(f"TTS service is not ready at 127.0.0.1:{port('LVIAI_TTS_PORT', 8765)}")
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
    history: list[dict[str, str]] = field(
        default_factory=lambda: [{"role": "system", "content": SYSTEM_PROMPT}]
    )
    max_turns: int = 6
    turn_id: int = 0
    stop_requested: asyncio.Event = field(default_factory=asyncio.Event)
    conversation_task: asyncio.Task[None] | None = None
    browser_playback: BrowserPlayback | None = None
    stop_reason: str | None = None

    def reset_for_start(self, max_turns: int) -> None:
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.max_turns = max_turns
        self.turn_id = 0
        self.stop_requested.clear()
        self.browser_playback = None
        self.stop_reason = None


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

    def startup(self) -> None:
        self.service_health = check_downstream_services()
        self.opencc = OpenCC("t2s")
        self.vad = VadCapture()
        rss = psutil.Process().memory_info().rss
        if rss > 1024 * 1024 * 1024:
            raise RuntimeError("WebSocket service RSS exceeds 1 GiB after VAD startup")
        if rss > 700 * 1024 * 1024:
            print(f"WARNING: WebSocket service RSS after VAD startup is {rss} bytes", flush=True)
        print(
            json.dumps(
                {"event": "demo_ready", "host": HOST, "port": PORT, "rss_bytes": rss},
                ensure_ascii=False,
            ),
            flush=True,
        )

    async def append_event_log(self, event: dict[str, Any]) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
        async with self.event_log_lock:
            with EVENT_LOG.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())

    async def emit(
        self,
        context: SessionContext,
        event_type: str,
        data: dict[str, Any] | None = None,
        *,
        turn_id: int | None = None,
    ) -> bool:
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

    async def set_state(
        self, context: SessionContext, state: str, *, turn_id: int | None = None
    ) -> bool:
        return await self.emit(context, "state", {"state": state}, turn_id=turn_id)

    async def protocol_warning(self, context: SessionContext, message: str) -> None:
        await self.append_event_log(
            {
                "type": "protocol_warning",
                "timestamp": time.time(),
                "session_id": context.session_id,
                "turn_id": context.turn_id,
                "data": {"message": message, "recoverable": True},
            }
        )

    @staticmethod
    def safe_browser_wav_bytes(audio_path: str) -> bytes:
        root = (RUNTIME_ROOT / "tts").resolve()
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
            raise RuntimeError(
                f"audio_too_large: {size} bytes exceeds {MAX_BROWSER_AUDIO_BYTES} bytes"
            )
        return candidate.read_bytes()

    async def send_browser_audio(
        self, context: SessionContext, turn_id: int, tts: dict[str, Any]
    ) -> BrowserPlayback:
        audio_bytes = await asyncio.to_thread(
            self.safe_browser_wav_bytes, str(tts["audio_path"])
        )
        playback = BrowserPlayback(
            audio_id=uuid4().hex,
            turn_id=turn_id,
            duration_seconds=(
                float(tts["duration_seconds"])
                if isinstance(tts.get("duration_seconds"), (int, float))
                else None
            ),
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
                raise RuntimeError(
                    f"browser playback {expected_state} acknowledgement timed out"
                )
            await asyncio.wait_for(playback.changed.wait(), timeout=remaining)
            playback.changed.clear()

    async def handle_browser_playback_control(
        self, context: SessionContext, command: dict[str, Any]
    ) -> None:
        command_type = command.get("type")
        playback = context.browser_playback
        turn_id = command.get("turn_id")
        audio_id = command.get("audio_id")
        if playback is None or turn_id != playback.turn_id or audio_id != playback.audio_id:
            await self.protocol_warning(context, f"ignored stale or malformed {command_type}")
            return
        if command_type == "browser_playback_started":
            if playback.state != "pending_started":
                await self.protocol_warning(
                    context, "ignored duplicate or out-of-order browser_playback_started"
                )
                return
            playback.state = "started"
        elif command_type == "browser_playback_finished":
            if playback.state != "started":
                await self.protocol_warning(
                    context, "ignored browser_playback_finished before started or after completion"
                )
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
                await self.protocol_warning(
                    context, "ignored audio_playback_error with unsupported code"
                )
                return
            if playback.state not in {"pending_started", "started"}:
                await self.protocol_warning(
                    context, "ignored audio_playback_error after playback completion"
                )
                return
            playback.state = "error"
        else:
            await self.protocol_warning(
                context, f"ignored unsupported browser playback control: {command_type}"
            )
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
                self.active = context

        if reject:
            await self.reject_second_connection(websocket)
            return
        if context is None:
            raise RuntimeError("active-session initialization failed")

        try:
            health = await asyncio.to_thread(check_downstream_services)
            health["vad"] = "ready"
            health["playback_mode"] = self.playback_mode
            if not await self.emit(context, "session_ready", health, turn_id=0):
                return

            async for raw_message in websocket:
                if not isinstance(raw_message, str):
                    await self.protocol_warning(context, "ignored unexpected binary control frame")
                    continue
                try:
                    command = json.loads(raw_message)
                except json.JSONDecodeError:
                    await self.emit(
                        context,
                        "error",
                        {"message": "invalid JSON control message", "recoverable": True},
                        turn_id=0,
                    )
                    continue
                command_type = command.get("type") if isinstance(command, dict) else None
                if command_type == "start":
                    if context.conversation_task is not None and not context.conversation_task.done():
                        await self.emit(
                            context,
                            "error",
                            {"message": "conversation is already active", "recoverable": True},
                            turn_id=context.turn_id,
                        )
                        continue
                    requested_turns = command.get("max_turns", 6)
                    if not isinstance(requested_turns, int) or requested_turns not in MAX_TURNS_ALLOWED:
                        await self.emit(
                            context,
                            "error",
                            {"message": "max_turns must be 1, 2, or 6", "recoverable": True},
                            turn_id=0,
                        )
                        continue
                    context.reset_for_start(requested_turns)
                    context.conversation_task = asyncio.create_task(
                        self.run_conversation(context)
                    )
                elif command_type == "stop":
                    context.stop_reason = "client_stop"
                    context.stop_requested.set()
                    if (
                        context.browser_playback is not None
                        and context.browser_playback.state in {"pending_started", "started"}
                    ):
                        context.browser_playback.state = "cancelled"
                        context.browser_playback.changed.set()
                    if context.conversation_task is None or context.conversation_task.done():
                        await self.set_state(context, "IDLE", turn_id=context.turn_id)
                        await self.emit(
                            context,
                            "session_stopped",
                            {"reason": "client_stop"},
                            turn_id=context.turn_id,
                        )
                elif command_type in {
                    "browser_playback_started",
                    "browser_playback_finished",
                    "browser_playback_cancelled",
                    "audio_playback_error",
                }:
                    if self.playback_mode != "browser":
                        await self.protocol_warning(
                            context, f"ignored {command_type} outside browser playback mode"
                        )
                    else:
                        await self.handle_browser_playback_control(context, command)
                else:
                    await self.emit(
                        context,
                        "error",
                        {"message": "unsupported control message", "recoverable": True},
                        turn_id=0,
                    )
        except ConnectionClosed:
            context.stop_reason = "disconnect"
            context.stop_requested.set()
        finally:
            if context.stop_reason is None:
                context.stop_reason = "disconnect"
            context.stop_requested.set()
            if (
                context.browser_playback is not None
                and context.browser_playback.state in {"pending_started", "started"}
            ):
                context.browser_playback.state = "cancelled"
                context.browser_playback.changed.set()
            if context.conversation_task is not None and not context.conversation_task.done():
                await context.conversation_task
            async with self.connection_lock:
                if self.active is context:
                    self.active = None

    async def capture_once(self, context: SessionContext) -> dict[str, Any]:
        if self.vad is None:
            raise RuntimeError("VAD is not initialized")
        loop = asyncio.get_running_loop()
        status_queue: asyncio.Queue[str] = asyncio.Queue()

        def status_callback(message: str) -> None:
            loop.call_soon_threadsafe(status_queue.put_nowait, message)

        capture_task = asyncio.create_task(
            asyncio.to_thread(self.vad.capture_once, INPUT_WAV, status_callback)
        )
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
            while (
                not context.stop_requested.is_set()
                and context.turn_id < context.max_turns
            ):
                await self.set_state(context, "LISTENING", turn_id=context.turn_id + 1)
                capture = await self.capture_once(context)
                if context.stop_requested.is_set():
                    break
                if capture.get("status") == "NO_SPEECH":
                    await self.emit(
                        context,
                        "no_speech",
                        {"wait_seconds": capture.get("wait_seconds")},
                        turn_id=context.turn_id,
                    )
                    await self.set_state(context, "LISTENING", turn_id=context.turn_id + 1)
                    continue

                context.turn_id += 1
                turn_id = context.turn_id
                await self.set_state(context, "TRANSCRIBING", turn_id=turn_id)
                stt_started = time.perf_counter()
                stt = await asyncio.to_thread(stt_transcribe, INPUT_WAV)
                stt_http_seconds = time.perf_counter() - stt_started
                if context.stop_requested.is_set():
                    break
                raw_transcript = str(stt.get("text", "")).strip()
                if not raw_transcript:
                    raise RuntimeError("STT returned an empty transcript")
                if self.opencc is None:
                    raise RuntimeError("OpenCC t2s converter is not initialized")
                user_text = self.opencc.convert(raw_transcript).strip()
                if not user_text:
                    raise RuntimeError("OpenCC normalization returned an empty transcript")
                context.history.append({"role": "user", "content": user_text})
                await self.emit(
                    context, "user_transcript", {"text": user_text}, turn_id=turn_id
                )

                await self.set_state(context, "THINKING", turn_id=turn_id)
                assistant_text, llm_latency, _tokens_per_second = await asyncio.to_thread(
                    llm_reply, context.history
                )
                if context.stop_requested.is_set():
                    break
                context.history.append({"role": "assistant", "content": assistant_text})
                while len(context.history) > 1 + MAX_RAW_TURNS * 2:
                    del context.history[1:3]
                await self.emit(
                    context, "assistant_text", {"text": assistant_text}, turn_id=turn_id
                )

                await self.set_state(context, "SYNTHESIZING", turn_id=turn_id)
                tts, _tts_http_seconds = await asyncio.to_thread(tts_reply, assistant_text)
                if context.stop_requested.is_set():
                    break
                playback_start = time.perf_counter()
                if self.playback_mode == "browser":
                    playback_wait = await self.send_browser_audio(context, turn_id, tts)
                    try:
                        await self.wait_for_browser_state(
                            context,
                            playback_wait,
                            "started",
                            BROWSER_STARTED_TIMEOUT_SECONDS,
                        )
                    except RuntimeError:
                        if context.stop_requested.is_set() or playback_wait.state == "cancelled":
                            break
                        raise
                    await self.set_state(context, "SPEAKING", turn_id=turn_id)
                    await self.emit(context, "playback_started", {}, turn_id=turn_id)
                    duration = playback_wait.duration_seconds or 0.0
                    finished_timeout = min(
                        BROWSER_FINISHED_TIMEOUT_MAX_SECONDS,
                        max(15.0, duration + 10.0),
                    )
                    try:
                        await self.wait_for_browser_state(
                            context, playback_wait, "finished", finished_timeout
                        )
                    except RuntimeError:
                        if context.stop_requested.is_set() or playback_wait.state == "cancelled":
                            break
                        raise
                    playback = {
                        "backend": "browser_web_audio",
                        "playback_seconds": duration,
                        "mode": "browser",
                    }
                    await self.emit(
                        context, "playback_finished", playback, turn_id=turn_id
                    )
                    context.browser_playback = None
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
                    playback = await asyncio.to_thread(play_sync, audio_path)
                    await self.emit(
                        context, "playback_finished", playback, turn_id=turn_id
                    )
                await self.emit(
                    context,
                    "turn_complete",
                    {
                        "stt_http_seconds": stt_http_seconds,
                        "llm_latency_seconds": llm_latency,
                        "tts_synthesis_seconds": tts.get("synthesis_seconds"),
                        "speech_end_to_playback_start_seconds": playback_start
                        - float(capture["speech_end_clock"]),
                        "playback_duration_seconds": playback.get("playback_seconds"),
                        "gpu_used_mib": nvidia_used_mib(),
                    },
                    turn_id=turn_id,
                )

            await self.set_state(context, "IDLE", turn_id=context.turn_id)
            reason = context.stop_reason or (
                "max_turns" if context.turn_id >= context.max_turns else "client_stop"
            )
            await self.emit(
                context, "session_stopped", {"reason": reason}, turn_id=context.turn_id
            )
        except Exception as exc:
            context.stop_reason = "error"
            print(traceback.format_exc(), file=sys.stderr, flush=True)
            await self.set_state(context, "ERROR", turn_id=context.turn_id)
            await self.emit(
                context,
                "error",
                {"message": f"{type(exc).__name__}: {exc}", "recoverable": False},
                turn_id=context.turn_id,
            )
            await self.emit(
                context,
                "session_stopped",
                {"reason": "error"},
                turn_id=context.turn_id,
            )


async def run_server(host: str, server_port: int, playback_mode: str) -> None:
    bridge = VoiceBridge(playback_mode)
    await asyncio.to_thread(bridge.startup)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (RUNTIME_ROOT / "input").mkdir(parents=True, exist_ok=True)
    async with serve(
        bridge.handler,
        host,
        server_port,
        origins=ALLOWED_ORIGINS,
        ping_interval=20,
        ping_timeout=20,
        max_size=64 * 1024,
    ):
        print(
            f"Demo WebSocket bridge listening at ws://{host}:{server_port} "
            f"({playback_mode} playback; origins={','.join(ALLOWED_ORIGINS)})",
            flush=True,
        )
        await asyncio.Future()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=HOST, choices=[HOST])
    parser.add_argument("--port", type=int, default=PORT, choices=[PORT])
    args = parser.parse_args()
    playback_mode = os.environ.get(PLAYBACK_MODE_ENV, "browser").strip().lower()
    if playback_mode not in PLAYBACK_MODES:
        print(
            f"{PLAYBACK_MODE_ENV} must be one of: {', '.join(sorted(PLAYBACK_MODES))}",
            file=sys.stderr,
            flush=True,
        )
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
