"""No models: actual WS transport, controller access, file scope and mouth mask."""
import asyncio
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import types
from unittest.mock import patch, AsyncMock
from aiohttp.test_utils import TestClient, TestServer

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runtime/stage7'
sys.path[:0]=[str(ROOT),str(ROOT/'experiments/avatar-bridge'),str(ROOT/'experiments/websocket-i0/server')]
checks=[]

def forbidden(*args,**kwargs):raise AssertionError('Real hardware/model operation attempted')

async def ws_checks():
    stubs={name:types.ModuleType(name) for name in ('opencc','websockets','websockets.asyncio','websockets.asyncio.server','websockets.exceptions','auto_voice_client')}
    stubs['opencc'].OpenCC=forbidden
    stubs['websockets.asyncio.server'].ServerConnection=object;stubs['websockets.asyncio.server'].serve=forbidden
    stubs['websockets.exceptions'].ConnectionClosed=type('ConnectionClosed',(Exception,),{})
    for name in ('VadCapture','play_sync','health_checks','llm_reply','nvidia_used_mib','tts_reply','stt','stt_health'):setattr(stubs['auto_voice_client'],name,forbidden)
    with patch.dict(sys.modules,stubs):
        ws=importlib.import_module('voice_ws_server')
        bridge=ws.VoiceBridge('avatar_webrtc')
        events=[];binary=[];uploads=[];tts_calls=[];model_calls=[]
        class Socket:
            async def send(self,value):
                if isinstance(value,bytes):binary.append(value);return
                event=json.loads(value);events.append(event)
                if event['type']=='audio_ready':
                    meta=event['data']
                    command=dict(meta,type='avatar_playback_started')
                    await bridge.handle_avatar_playback_control(context,command)
                    async def finish():
                        await asyncio.sleep(.01)
                        await bridge.handle_avatar_playback_control(context,dict(meta,type='avatar_playback_estimated_finished',completion_semantics='bounded_media_estimate'))
                    asyncio.create_task(finish())
        context=ws.SessionContext(Socket(),'contract-session-123')
        context.playback_mode='avatar_webrtc';context.max_turns=1
        context.avatar_binding=dict(control_id='control123',client_id='client123',sessionid='rtc123')
        bridge.opencc=types.SimpleNamespace(convert=lambda value:value)
        async def append(_):pass
        bridge.append_event_log=append
        async def capture(_):return dict(status='OK',speech_end_clock=0)
        bridge.capture_once=capture
        ws.stt_transcribe=lambda _:dict(text='测试一下')
        def llm(_):model_calls.append(1);return '这是一条自然中文回复。',.01,None
        def tts(text):tts_calls.append(text);return dict(audio_path=str(ROOT/'runtime/tts/contract.wav'),sample_rate=24000,duration_seconds=.04),.01
        ws.llm_reply_raw=llm;ws.tts_reply=tts;ws.nvidia_used_mib=lambda:None;ws.play_sync=forbidden
        async def avatar(action,data):
            assert action=='audio';uploads.append(data)
            return dict(code=0,data=dict(control_id='control123',sessionid='rtc123',bridge_turn_id=context.session_id+':1',generation=1,ws_session_id=context.session_id,turn_id=1,audio_id=data['audio_id'],transport='avatar_webrtc',duration_seconds=.04,sample_rate=16000))
        bridge.avatar_request=avatar
        await asyncio.wait_for(bridge.run_conversation(context),3)
        assert len(tts_calls)==len(model_calls)==len(uploads)==1 and not binary
        assert [m['role'] for m in context.history]==['system','user','assistant']
        assert next(e['data'] for e in events if e['type']=='assistant_text')['emotion']=='neutral'
        ready=next(e['data'] for e in events if e['type']=='audio_ready')
        assert ready['transport']=='avatar_webrtc' and 'audio_path' not in ready
        assert next(e['data'] for e in events if e['type']=='playback_finished')['completion_semantics']=='bounded_media_estimate'
        assert events[-1]['data']['reason']=='max_turns'
        # Stale-generation feedback must not change a pending turn.
        context.browser_playback=ws.BrowserPlayback('audio123',2,.04)
        context.avatar_metadata=dict(sessionid='rtc123',bridge_turn_id=context.session_id+':2',generation=2)
        await bridge.handle_avatar_playback_control(context,dict(type='avatar_playback_started',turn_id=2,audio_id='audio123',sessionid='rtc123',bridge_turn_id=context.session_id+':2',generation=1))
        assert context.browser_playback.state=='pending_started'
        cancellations=[]
        async def cancel(action,data):cancellations.append((action,data));return dict(code=0)
        bridge.avatar_request=cancel
        await bridge.close_avatar(context);await bridge.close_avatar(context)
        assert len(cancellations)==1 and cancellations[0][0]=='cancel' and cancellations[0][1]['ws_session_id']==context.session_id
        try:await bridge.send_browser_audio(context,2,dict(audio_path='must-not-read'))
        except RuntimeError:pass
        else:raise AssertionError('Avatar sent old WAV')
    checks.extend(['actual WS orchestration: one TTS, one upload, zero binary, no winsound','neutral/body/history order preserved','one-turn control and bounded estimate feedback','stale generation rejected; old WAV forbidden'])

async def controller_checks():
    import control_service as service
    with tempfile.TemporaryDirectory(dir=OUT) as temp,patch.object(service,'RUNTIME',Path(temp)):
        app=service.create_app();control=app['control']
        client=TestClient(TestServer(app,host='127.0.0.1'))
        await client.start_server()
        good={'Host':'127.0.0.1:8011','Origin':service.ORIGIN}
        try:
            r=await client.get('/health',headers={'Host':'127.0.0.1:8011'});assert r.status==200
            r=await client.post('/connect',json={},headers=dict(good,Origin='https://foreign.invalid'));assert r.status==403
            r=await client.post('/connect',json={},headers=dict(good,Host='foreign.invalid'));assert r.status==403
            r=await client.post('/internal/audio',json={},headers=good);assert r.status==403
            r=await client.post('/internal/audio',json={},headers={'Host':'127.0.0.1:8011'});assert r.status==403
            r=await client.post('/preview',json=dict(audio_path='D:/CyberGirlfriend/private.wav'),headers=good);assert r.status==409
            session=service.ControlSession(None,'client123','control123','rtc123');session.ready=True;control.session=session
            r=await client.post('/preview',json=dict(control_id='other123',client_id='client123',turn_id=1),headers=good);assert r.status==409
            r=await client.post('/preview',json=dict(control_id='control123',client_id='client123',sessionid='rtc123',turn_id='../bad'),headers=good);assert r.status==409
            payload=dict(control_id='control123',client_id='client123',sessionid='other123',turn_id=1)
            r=await client.post('/preview',json=payload,headers=good);assert r.status==409
            # Exercise the real frontend binding shape without synthesizing audio.
            await session.lock.acquire()
            with patch.object(service,'manager',side_effect=AssertionError('must not synthesize')):
                r=await client.post('/preview',json=dict(payload,sessionid='rtc123'),headers=good)
                assert r.status==409
                try:
                    await control.preview(types.SimpleNamespace(json=AsyncMock(return_value=dict(payload,sessionid='rtc123'))))
                except ValueError as error:
                    assert str(error)=='preview requires an idle unbound ready session'
                else:raise AssertionError('Busy preview accepted')
            session.lock.release()
            internal={'Host':'127.0.0.1:8011','X-Rebuild-Control':control.secret}
            bind=dict(control_id='control123',client_id='client123',ws_session_id='conversation123')
            r=await client.post('/internal/bind',json=bind,headers=internal);assert r.status==200
            r=await client.post('/internal/bind',json=dict(bind,ws_session_id='another123'),headers=internal);assert r.status==409 and session.ws_session_id=='conversation123'
            r=await client.post('/internal/audio',json=dict(control_id='control123',ws_session_id='conversation123',turn_id=1,audio_id='audio123',tts=dict(audio_path='D:/CyberGirlfriend/private.wav',sample_rate=24000)),headers=internal);assert r.status==409
            assert session.bridge.active is None and not session.bridge.seen
            r=await client.post('/internal/cancel',json=dict(control_id='control123',ws_session_id='another123'),headers=internal);assert r.status==409
            with patch.object(control,'close',new_callable=AsyncMock) as close:
                r=await client.post('/internal/cancel',json=dict(control_id='control123',ws_session_id='conversation123'),headers=internal)
                assert r.status==200 and close.await_count==1
        finally:
            control.session=None
            await client.close()
    checks.extend(['controller Host and Origin allowlist','internal API requires secret and rejects browser Origin','invalid session, turn and file paths rejected before side effects','cannot rebind another WS conversation'])

def quality_checks():
    import numpy as np
    os.environ['LIVETALKING_LOG']=str(OUT/'quality-test.log')
    os.environ.pop('REBUILD_QUALITY_CAPTURE_DIR',None)
    sys.path.insert(0,str(ROOT/'third_party/LiveTalking'))
    from avatars.wav2lip_avatar import LipReal
    avatar=LipReal.__new__(LipReal)
    source=np.full((720,1278,3),80,np.uint8)
    avatar.frame_list_cycle=[source];avatar.coord_list_cycle=[(160,416,500,756)]
    pred=np.full((256,256,3),180,np.uint8)
    result=avatar.paste_back_frame(pred,0)
    assert result.shape==source.shape and np.array_equal(source,np.full_like(source,80))
    assert np.array_equal(result[:280],source[:280])
    assert np.array_equal(result[:, :500],source[:, :500])
    assert result[354,628,0]>100
    checks.extend(['mouth blend preserves full dimensions and source bytes','upper face/background unmodified; mouth responds'])

async def main():await ws_checks();await controller_checks()
asyncio.run(main())
quality_checks()
(OUT/'contract-checks.json').write_text(json.dumps(dict(status='PASS',checks=checks,models_loaded=0,real_tts_requests=0),indent=2),encoding='utf-8')
print('Stage7 model-free contracts PASS:',len(checks))
