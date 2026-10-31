"""Exercise the actual conversation loop beyond six turns, without models/hardware."""
import asyncio
import ast
import importlib
import json
from pathlib import Path
import sys
import types
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runtime/pre-freeze-productization'
OUT.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(ROOT), str(ROOT / 'experiments/websocket-i0/server')]


def forbidden(*args, **kwargs):
    raise AssertionError('Real model, microphone or hardware operation attempted')


async def main():
    stubs = {name: types.ModuleType(name) for name in
             ('opencc', 'websockets', 'websockets.asyncio', 'websockets.asyncio.server',
              'websockets.exceptions', 'auto_voice_client')}
    stubs['opencc'].OpenCC = forbidden
    stubs['websockets.asyncio.server'].ServerConnection = object
    stubs['websockets.asyncio.server'].serve = forbidden
    stubs['websockets.exceptions'].ConnectionClosed = type('ConnectionClosed', (Exception,), {})
    for name in ('VadCapture', 'play_sync', 'health_checks', 'llm_reply', 'nvidia_used_mib', 'tts_reply', 'stt', 'stt_health'):
        setattr(stubs['auto_voice_client'], name, forbidden)
    with patch.dict(sys.modules, stubs):
        ws = importlib.import_module('voice_ws_server')
        # Redirect all test evidence to new files; never append to actual session logs.
        # EvidenceStore itself is bounded in-memory; event logging is replaced below.
        bridge = ws.VoiceBridge('avatar_webrtc')
        bridge.opencc = types.SimpleNamespace(convert=lambda value: value)
        events = []
        calls = {'tts': 0, 'reply': 0, 'summary': 0, 'upload': 0}

        class Socket:
            async def send(self, value):
                assert isinstance(value, str), 'Avatar mode must not send browser WAV'
                event = json.loads(value)
                events.append(event)
                if event['type'] == 'audio_ready':
                    meta = event['data']
                    await bridge.handle_avatar_playback_control(context, dict(meta, type='avatar_playback_started'))

                    async def finish():
                        await asyncio.sleep(.001)
                        await bridge.handle_avatar_playback_control(context, dict(
                            meta, type='avatar_playback_estimated_finished', completion_semantics='bounded_media_estimate'))
                    asyncio.create_task(finish())
                if event['type'] == 'turn_complete' and event['turn_id'] == 8:
                    context.stop_reason = 'client_stop'
                    context.stop_requested.set()

        context = ws.SessionContext(Socket(), 'productization-offline-eight-turns')
        assert context.max_turns is None
        context.playback_mode = 'avatar_webrtc'
        context.avatar_binding = dict(control_id='control123', client_id='client123', sessionid='rtc123')

        async def append(_):
            pass
        bridge.append_event_log = append

        async def capture(_):
            return dict(status='OK', speech_end_clock=ws.time.perf_counter())
        bridge.capture_once = capture
        ws.stt_transcribe = lambda _: dict(text=f'请聊聊第{context.turn_id}个话题，今天的云彩真漂亮。')

        def reply(messages):
            if messages[0]['content'] != ws.SYSTEM_PROMPT:
                calls['summary'] += 1
                return '用户在轻松聊天，谈到云彩和不同话题。助手亲切回应了用户。', .001, None
            calls['reply'] += 1
            return f'第{context.turn_id}片云像一朵棉花，我们一起看看吧。', .001, None
        ws.llm_reply_raw = reply

        def tts(text):
            calls['tts'] += 1
            return dict(audio_path=str(OUT / 'not-created.wav'), sample_rate=24000, duration_seconds=.04), .001
        ws.tts_reply = tts
        ws.nvidia_used_mib = lambda: None

        async def avatar(action, data):
            assert action == 'audio'
            calls['upload'] += 1
            return dict(code=0, data=dict(context.avatar_binding,
                bridge_turn_id=f'{context.session_id}:{context.turn_id}', generation=context.turn_id,
                ws_session_id=context.session_id, turn_id=context.turn_id, audio_id=data['audio_id'],
                transport='avatar_webrtc', duration_seconds=.04, sample_rate=16000))
        bridge.avatar_request = avatar
        await asyncio.wait_for(bridge.run_conversation(context), 8)
        completed = [e['turn_id'] for e in events if e['type'] == 'turn_complete']
        assert completed == list(range(1, 9)), completed
        assert events[-1]['type'] == 'session_stopped' and events[-1]['data']['reason'] == 'client_stop'
        assert calls['tts'] == calls['upload'] == 8
        assert len(context.history) <= 1 + 2 * ws.HARD_RAW_TURN_CAP
        assert calls['summary'] > 0 and context.summary_revision > 0
        roles = [m['role'] for m in context.history]
        assert roles[0] == 'system' and roles[1:] == ['user', 'assistant'] * ((len(roles)-1)//2)

        # Evaluate the actual production start-command turn-limit selection.
        tree = ast.parse((ROOT / 'experiments/websocket-i0/server/voice_ws_server.py').read_text(encoding='utf-8'))
        assignment = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                          and any(isinstance(t, ast.Name) and t.id == 'rounds' for t in n.targets))
        expr = compile(ast.Expression(assignment.value), '<actual turn-limit selection>', 'eval')
        for command in ({}, {'max_turns': 6}, {'development_test': False, 'max_turns': 6}):
            assert eval(expr, {'command': command}) is None
        assert eval(expr, {'command': {'development_test': True, 'max_turns': 2}}) == 2
        # Explicit finite development limit still ends deterministically.
        events.clear()
        context = ws.SessionContext(Socket(), 'productization-offline-development')
        context.playback_mode = 'avatar_webrtc'; context.max_turns = 1
        context.avatar_binding = dict(control_id='control123', client_id='client123', sessionid='rtc123')
        await asyncio.wait_for(bridge.run_conversation(context), 3)
        assert context.turn_id == 1 and events[-1]['data']['reason'] == 'max_turns'
        result = dict(status='PASS', real_models=0, real_service_starts=0,
            completed_normal_turns=completed, calls=calls,
            checks=['8 turns without max_turns stop', 'client stop ends session',
                    'actual bounded history and rolling summary retained',
                    'normal command ignores legacy test count', 'finite limit only with development_test=true'])
        (OUT / 'conversation-contracts.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
        print('Productization conversation contracts PASS')


if __name__ == '__main__':
    asyncio.run(main())
