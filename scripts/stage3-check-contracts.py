"""Deterministic contract checks: fake hardware/services; no sockets or models."""
from __future__ import annotations
import ast
import asyncio
import contextlib
import importlib
import io
import faulthandler
import json
from pathlib import Path
import sys
import time
import types

ROOT = Path(__file__).resolve().parents[1]
faulthandler.dump_traceback_later(15, exit=True)
SERVER = ROOT / "experiments/websocket-i0/server"
sys.path[:0] = [str(ROOT), str(SERVER)]
from reply_text import clean_reply_text
from emotion_parser import parse_assistant_reply, sanitize_tts_text
from memory_recall_guard import with_memory_recall_instruction
from bounded_context import build_llm_history
from reply_quality_guard import choose_retry_candidate
from repetition_guard import assess_recent_repetition

checks = []
cases = [
    ("你好。", "你好。"),
    ("<think>私有推理</think>你好。", "你好。"),
    ("前文<think>甲<think>乙</think>丙</think>后文", "前文后文"),
    ("<THINK>内部</THINK>正文。", "正文。"),
    ("</think>保留正文。", "保留正文。"),
    ("<think>未配对但需保留的正文。", "未配对但需保留的正文。"),
    ("正文。<think>", "正文。"),
    ("<emotion:love>我喜欢你。</emotion:love>", "我喜欢你。"),
    ("前文<emotion:sad>后文", "前文后文"),
    ("emotion:love>你好。", "你好。"),
    ("<emotion:unknown>正文", "正文"),
    ("love\nemotion 是一个英文词。", "love\nemotion 是一个英文词。"),
    ("<think>推理</think>\n<emotion:excited>\n今天挺顺利。", "今天挺顺利。"),
]
for raw, expected in cases:
    assert clean_reply_text(raw) == expected, (raw, clean_reply_text(raw))
    reply = parse_assistant_reply(raw)
    assert reply.text == expected and reply.emotion == "neutral"
checks.append(f"{len(cases)} cleanup fixtures preserve body and always return neutral")
for raw in ("", "<think>仅思考</think>", "<emotion:love></emotion:love>"):
    try:
        parse_assistant_reply(raw)
    except ValueError:
        pass
    else:
        raise AssertionError("Empty/metadata-only output accepted")
assert len(parse_assistant_reply("中" * 350).text) == 300
assert sanitize_tts_text("<emotion:love>你好❤️。") == "你好。"
checks.append("Empty replies reject; 300-char bound and TTS emoji cleanup retained")
repeated = "今天我们可以慢慢聊，你想说什么我都会认真听。"
assert assess_recent_repetition(repeated, [repeated], "聊点什么").suspicious
assert not assess_recent_repetition(repeated, [repeated], "请重复刚才的话").suspicious
first = parse_assistant_reply(repeated)
second = parse_assistant_reply("我们换个话题，聊聊你今天最开心的事吧。")
selected, _ = choose_retry_candidate(first, second, "聊点什么", [repeated], False)
assert selected is second
checks.append("Repetition detection, explicit repeat exception and text-only candidate selection retained")

# Import actual WS orchestration with external dependencies replaced. Every
# hardware/network/model hook raises unless the individual fixture replaces it.
def forbidden(*args, **kwargs):
    raise AssertionError("Real model/hardware/network operation attempted")

for name in ("psutil", "opencc", "websockets", "websockets.asyncio", "websockets.asyncio.server", "websockets.exceptions", "auto_voice_client"):
    sys.modules[name] = types.ModuleType(name)
sys.modules["psutil"].Process = forbidden
sys.modules["opencc"].OpenCC = forbidden
sys.modules["websockets.asyncio.server"].ServerConnection = object
sys.modules["websockets.asyncio.server"].serve = forbidden
sys.modules["websockets.exceptions"].ConnectionClosed = type("ConnectionClosed", (Exception,), {})
fake_h2 = sys.modules["auto_voice_client"]
for attr in ("VadCapture", "play_sync", "health_checks", "llm_reply", "nvidia_used_mib", "tts_reply", "stt", "stt_health"):
    setattr(fake_h2, attr, forbidden)
ws = importlib.import_module("voice_ws_server")
g0 = importlib.import_module("speech_chain_client")
assert g0.clean_for_tts("<think>内部</think><emotion:love>你好。") == "你好。"
for instruction in (ws.SYSTEM_PROMPT, ws.ANTI_REPETITION_RETRY_INSTRUCTION,
                    importlib.import_module("memory_recall_guard").MEMORY_RECALL_REPETITION_RETRY_INSTRUCTION):
    assert "emotion" not in instruction and "JSON" not in instruction
checks.append("Main and retry prompts impose no output format; G0 shares text cleanup")

class Socket:
    def __init__(self):
        self.events = []
        self.binary = []
        self.context = None

    async def send(self, data):
        if isinstance(data, bytes):
            self.binary.append(data)
            return
        event = json.loads(data)
        assert set(event) == {"type", "timestamp", "session_id", "turn_id", "data"}
        self.events.append(event)
        if event["type"] == "turn_complete":
            self.context.stop_requested.set()


async def run_fixture(user_text, candidates, expected, expected_calls, error=False):
    bridge = ws.VoiceBridge("winsound")
    socket = Socket()
    ctx = ws.SessionContext(socket, "mock-session")
    socket.context = ctx
    bridge.opencc = types.SimpleNamespace(convert=lambda value: value)
    logs = []
    requests = []
    spoken = []

    async def log(event):
        logs.append(event)

    async def capture(context):
        return {"status": "OK", "speech_end_clock": time.perf_counter()}

    def model(messages):
        requests.append([dict(item) for item in messages])
        assert messages[-1] == {"role": "user", "content": user_text}
        assert len(requests) <= len(candidates)
        return candidates[len(requests) - 1], 0.01, None

    def tts(text):
        spoken.append(text)
        return {"audio_path": str(ROOT / "runtime/tts/mock.wav"), "duration_seconds": 0.01, "sample_rate": 24000}, 0.01

    bridge.append_event_log = log
    bridge.capture_once = capture
    ws.stt_transcribe = lambda _: {"text": user_text}
    ws.llm_reply_raw = model
    ws.tts_reply = tts
    ws.play_sync = lambda _: {"playback_seconds": 0.01}
    ws.nvidia_used_mib = lambda: None
    with contextlib.redirect_stderr(io.StringIO()):
        await asyncio.wait_for(bridge.run_conversation(ctx), timeout=5)
    assert len(requests) == expected_calls
    assert not any(m["role"] == "system" for m in ctx.history[1:])
    assistant = [m["content"] for m in ctx.history if m["role"] == "assistant"]
    text_events = [e for e in socket.events if e["type"] == "assistant_text"]
    if error:
        assert ctx.history == [{"role":"system", "content":ws.SYSTEM_PROMPT}, {"role":"user", "content":user_text}]
        assert not assistant and not spoken and not text_events
        assert any(e["type"] == "state" and e["data"]["state"] == "ERROR" for e in socket.events)
    else:
        assert [m["role"] for m in ctx.history] == ["system", "user", "assistant"]
        assert assistant == [expected] and spoken == [expected]
        assert len(text_events) == 1 and text_events[0]["data"] == {"text":expected, "emotion":"neutral"}
        assert len(ctx.evidence_history_ids) == len(ctx.history) - 1
        assert all("<think>" not in m["content"] and "<emotion:" not in m["content"] for m in ctx.history)
        states = [e["data"]["state"] for e in socket.events if e["type"] == "state"]
        assert states == ["LISTENING", "TRANSCRIBING", "THINKING", "SYNTHESIZING", "SPEAKING", "IDLE"]
    return {"requests": requests, "history": ctx.history, "events": socket.events, "tts_text": spoken}


async def main():
    print("Running isolated WS contract fixtures", flush=True)
    fixtures = []
    fixtures.append(await run_fixture("今天好吗", ["<think>内部</think><emotion:love>今天挺好，想听你聊聊。"], "今天挺好，想听你聊聊。", 1))
    fixtures.append(await run_fixture("你还记得我喜欢什么吗", ["我不记得你喜欢什么。", "<think>只有思考</think>"], "我不记得你喜欢什么。", 2))
    fixtures.append(await run_fixture("你好", ["<think>只有思考</think>"], None, 1, error=True))
    checks.append("Mock WS: clean history/event/TTS, single commit, retry fallback, empty-reply ERROR; no real voice chain")
    bridge = ws.VoiceBridge("browser")
    socket = Socket()
    ctx = ws.SessionContext(socket,"browser-fixture")
    socket.context = ctx
    ctx.turn_id = 1
    async def no_log(event):
        pass
    bridge.append_event_log = no_log
    bridge.safe_browser_wav_bytes = lambda _: b"RIFF-contract-only"
    playback = await bridge.send_browser_audio(ctx,1,{"audio_path":"mock", "duration_seconds":0.1, "sample_rate":24000})
    ready = socket.events[0]
    assert ready["type"] == "audio_ready" and ready["data"]["transport"] == "websocket_binary"
    assert ready["data"]["byte_length"] == len(socket.binary[0]) and ready["data"]["content_type"] == "audio/wav"
    for kind, state in (("browser_playback_started","started"),("browser_playback_finished","finished")):
        await bridge.handle_browser_playback_control(ctx,{"type":kind,"turn_id":1,"audio_id":playback.audio_id})
        assert playback.state == state
    checks.append("Actual browser audio envelope, binary delivery and started/finished acknowledgements retained (mock bytes only)")
    raw=[{"role":"system","content":"persona"},{"role":"user","content":"事实"}]
    copied=build_llm_history(raw,"历史摘要")
    temporary=with_memory_recall_instruction(copied)
    assert raw == [{"role":"system","content":"persona"},{"role":"user","content":"事实"}]
    assert temporary[-1]["role"] == "user" and all(m["role"] == "system" for m in temporary[:-1])
    checks.append("Summary/recall instructions operate on copies and retain latest user; bounded-context algorithms unchanged")
    python_files = [ROOT / "rebuild_config.py", ROOT / "reply_text.py", *(ROOT / "experiments").rglob("*.py"), *(ROOT / "scripts").glob("*.py")]
    for file in python_files:
        ast.parse(file.read_text(encoding="utf-8-sig"),filename=str(file))
    checks.append(f"Active Python syntax passed: {len(python_files)} files")
    out=ROOT/"runtime/stage3/contract-checks.json"
    out.write_text(json.dumps({"status":"PASS","mock_only":True,"real_model_calls":0,"service_network_calls":0,"checks":checks,"fixtures":fixtures},ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"status":"PASS","checks":checks},ensure_ascii=False,indent=2))
    faulthandler.cancel_dump_traceback_later()

asyncio.run(main())
