"""Loopback production control: browser sessions, existing WAV bridge, one preview."""
from __future__ import annotations
import asyncio
from collections import deque
from dataclasses import dataclass, field
import hashlib
import hmac
import time
import json
from pathlib import Path
import re
import secrets
import sys
from uuid import uuid4
import aiohttp
from aiohttp import web
from bridge import AudioBridge, manager
from audio_adapter import owned, ROOT

RUNTIME=ROOT/'runtime/avatar-control'
PREVIEW=ROOT/'runtime/avatar-preview'
ORIGIN='http://127.0.0.1:3000'
LT='http://127.0.0.1:8010'
PREVIEW_TEXT='你好，我已经来到这个房间，听见你的声音了。'


def valid_id(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,96}',value):
        raise ValueError('invalid identity')
    return value


class RemotePeer:
    def __init__(self,session):self.session=session
    async def close(self):
        session=self.session
        session.invalid=True
        async with session.http.post(LT+'/session/close',json={'sessionid':session.sessionid}) as response:
            result=await response.json()
            if result.get('code')!=0:
                print('RTC close response:', result.get('code'),flush=True)


@dataclass
class ControlSession:
    http:aiohttp.ClientSession
    client_id:str
    control_id:str
    sessionid:str
    invalid:bool=False
    ready:bool=False
    ws_session_id:str|None=None
    bridge:AudioBridge=field(init=False)
    lock:asyncio.Lock=field(default_factory=asyncio.Lock)
    events:deque=field(default_factory=lambda:deque(maxlen=128))
    subscribers:set=field(default_factory=set)
    sse_task:asyncio.Task|None=None
    telemetry_history:deque=field(default_factory=lambda:deque(maxlen=256))
    last_public:dict|None=None
    def __post_init__(self):self.bridge=AudioBridge(self.http,RemotePeer(self),self.sessionid)


class Control:
    def __init__(self):
        self.session=None
        self.connect_lock=asyncio.Lock()
        self.preview_lock=asyncio.Lock()
        RUNTIME.mkdir(parents=True,exist_ok=True)
        self.secret_path=RUNTIME/'internal-secret.txt'
        if not self.secret_path.exists():
            with self.secret_path.open('x',encoding='utf-8') as f:f.write(secrets.token_hex(32))
        self.secret=self.secret_path.read_text(encoding='utf-8')

    def find(self,data,internal=False,allow_invalid=False):
        session=self.session
        if not session or (session.invalid and not allow_invalid) or data.get('control_id')!=session.control_id:
            raise ValueError('inactive control session')
        if not internal and data.get('client_id')!=session.client_id:
            raise ValueError('foreign browser session')
        return session

    async def pump(self,session,ready):
        try:
            async with session.http.get(LT+'/sse',params={'sessionid':session.sessionid},timeout=aiohttp.ClientTimeout(total=None)) as response:
                if response.status!=200:raise RuntimeError('SSE refused')
                ready.set()
                async for line in response.content:
                    if line.startswith(b'data: '):
                        event=json.loads(line[6:])
                        if session.bridge.accept_event(event):
                            session.events.append(event)
                            with (RUNTIME/(session.control_id+'-events.jsonl')).open('a',encoding='utf-8') as f:f.write(json.dumps(event)+'\n')
                            for queue in list(session.subscribers):
                                if queue.full():session.invalid=True;continue
                                queue.put_nowait(event)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            session.invalid=True
            print('SSE failure:',type(exc).__name__,flush=True)

    async def connect(self,request):
        data=await request.json();client=valid_id(data.get('client_id'))
        if data.get('type')!='offer' or not isinstance(data.get('sdp'),str) or len(data['sdp'])>100000:
            raise ValueError('invalid SDP')
        async with self.connect_lock:
            if self.session is not None:raise ValueError('another control session exists; disconnect it first')
            manager('livetalking').assert_listener()
            http=aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90))
            session=None
            try:
                async with http.post(LT+'/offer',json={'type':'offer','sdp':data['sdp'],'avatar':'cybergirlfriend_avatar_v1'}) as response:
                    response.raise_for_status();answer=await response.json()
                if 'sessionid' not in answer:raise ValueError('offer refused')
                session=ControlSession(http,client,uuid4().hex,answer['sessionid']);self.session=session
                ready=asyncio.Event();session.sse_task=asyncio.create_task(self.pump(session,ready))
                await asyncio.wait_for(ready.wait(),10)
                return web.json_response(dict(code=0,**answer,control_id=session.control_id))
            except BaseException:
                if session:await self.close(session)
                else:await http.close()
                raise

    async def ready(self,request):
        data=await request.json();session=self.find(data)
        if data.get('first_frame') is not True or data.get('width')!=1278 or data.get('height')!=720:
            raise ValueError('decoded full-size frame required')
        session.ready=True
        (RUNTIME/(session.control_id+'-ready.json')).write_text(json.dumps({k:data.get(k) for k in ('first_frame','width','height','client_kind')},indent=2),encoding='utf-8')
        return web.json_response(dict(code=0,ready=True))

    async def bind(self,request):
        data=await request.json();session=self.find(data,True)
        ws_id=valid_id(data.get('ws_session_id'))
        if session.ws_session_id and session.ws_session_id!=ws_id:raise ValueError('already bound to another conversation')
        if data.get('client_id')!=session.client_id:raise ValueError('browser identity mismatch')
        session.ws_session_id=ws_id
        return web.json_response(dict(code=0))

    async def upload(self,session,tts,ws_id,turn,audio_id):
        diagnostic_started=time.perf_counter()
        if not session.ready or session.invalid:raise ValueError('decoded media not ready')
        if not isinstance(turn,int) or isinstance(turn,bool) or not 1<=turn<=100000:raise ValueError('invalid turn')
        source=owned(tts['audio_path'])
        if not source.is_relative_to(ROOT/'runtime/tts'):raise ValueError('TTS path outside allowlist')
        bridge_turn=ws_id+':'+str(turn)
        result=await session.bridge.upload(dict(audio_path=str(source),sample_rate=tts['sample_rate'],turn_id=bridge_turn))
        converted=result['conversion']
        public=dict(control_id=session.control_id,sessionid=session.sessionid,bridge_turn_id=bridge_turn,
                    generation=result['upload']['data']['generation'],ws_session_id=ws_id,turn_id=turn,audio_id=audio_id,
                    transport='avatar_webrtc',duration_seconds=converted['output_seconds'],sample_rate=16000)
        session.last_public=public
        evidence=dict(public=public,conversion=converted,upload=result['upload'],
                      submit_elapsed_ms=(time.perf_counter()-diagnostic_started)*1000,
                      controller_monotonic_seconds=time.perf_counter(),wall_time=time.time())
        name=hashlib.sha256(bridge_turn.encode()).hexdigest()+'.json'
        (RUNTIME/name).write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        return public

    async def audio(self,request):
        data=await request.json();session=self.find(data,True)
        if session.ws_session_id!=data.get('ws_session_id'):raise ValueError('unbound conversation')
        async with session.lock:
            result=await self.upload(session,data['tts'],session.ws_session_id,data['turn_id'],valid_id(data['audio_id']))
            return web.json_response(dict(code=0,data=result))

    async def preview(self,request):
        data=await request.json()
        if set(data)-{'control_id','client_id','sessionid','turn_id'}:raise ValueError('unexpected preview input')
        session=self.find(data)
        if data.get('sessionid')!=session.sessionid:raise ValueError('foreign media session')
        turn=data.get('turn_id')
        if type(turn) is not int or not 1<=turn<=100000:raise ValueError('invalid preview turn')
        if 'preview-'+session.client_id+':'+str(turn) in session.bridge.seen:raise ValueError('duplicate preview turn')
        if not session.ready or session.bridge.active or session.lock.locked() or session.ws_session_id:
            raise ValueError('preview requires an idle unbound ready session')
        async with session.lock, self.preview_lock:
            PREVIEW.mkdir(parents=True,exist_ok=True)
            result_path=PREVIEW/'preview-tts-result.json'
            attempt_path=PREVIEW/'preview-tts-attempt.json'
            historical=ROOT/'runtime/stage6/preview-tts-result.json'
            if result_path.exists():
                tts=json.loads(result_path.read_text(encoding='utf-8'))
            elif historical.exists():
                tts=json.loads(historical.read_text(encoding='utf-8'))
            else:
                if attempt_path.exists():raise ValueError('previous TTS attempt uncertain; no automatic regeneration')
                manager('tts').assert_listener()
                with attempt_path.open('x',encoding='utf-8') as f:json.dump(dict(text=PREVIEW_TEXT,status='attempting'),f)
                async with session.http.get('http://127.0.0.1:8765/health') as r:before=await r.json()
                if before.get('status')!='ready':raise ValueError('TTS not ready')
                async with session.http.post('http://127.0.0.1:8765/tts',json={'text':PREVIEW_TEXT},timeout=aiohttp.ClientTimeout(total=180)) as r:
                    r.raise_for_status();tts=await r.json()
                if not tts.get('ok'):raise ValueError('TTS failed')
                async with session.http.get('http://127.0.0.1:8765/health') as r:after=await r.json()
                if after['request_count']!=before['request_count']+1:raise ValueError('unexpected TTS count')
                result_path.write_text(json.dumps(dict(tts,health_before=before,health_after=after),ensure_ascii=False,indent=2),encoding='utf-8')
            if session.invalid:raise ValueError('session cancelled during synthesis')
            public=await self.upload(session,tts,'preview-'+session.client_id,data.get('turn_id'),uuid4().hex)
            return web.json_response(dict(code=0,data=dict(public,text=PREVIEW_TEXT)))

    async def events(self,request):
        session=self.find(request.query)
        response=web.StreamResponse(headers={'Content-Type':'text/event-stream','Cache-Control':'no-cache','Access-Control-Allow-Origin':ORIGIN})
        await response.prepare(request)
        queue=asyncio.Queue(maxsize=64);session.subscribers.add(queue)
        try:
            for event in list(session.events):await response.write(('data: '+json.dumps(event)+'\n\n').encode())
            while not session.invalid:
                try:event=await asyncio.wait_for(queue.get(),10)
                except TimeoutError:
                    await response.write(b': keepalive\n\n');continue
                await response.write(('data: '+json.dumps(event)+'\n\n').encode())
        except (ConnectionResetError,asyncio.CancelledError):pass
        finally:session.subscribers.discard(queue)
        return response

    async def close(self,session):
        session.invalid=True
        try:
            await session.bridge.cancel()
        finally:
            if session.sse_task:
                session.sse_task.cancel();await asyncio.gather(session.sse_task,return_exceptions=True)
            await session.http.close()
            if self.session is session:self.session=None

    async def disconnect(self,request):
        data=await request.json();session=self.find(data,allow_invalid=True)
        await self.close(session)
        return web.json_response(dict(code=0,reconnect_required=True,playback_immediately_stopped=False))

    async def cancel_bound(self,request):
        data=await request.json()
        # Closing an already-closed binding is harmless; never close a new one.
        if not self.session:return web.json_response(dict(code=0,already_closed=True))
        session=self.find(data,True,allow_invalid=True)
        if session.ws_session_id!=data.get('ws_session_id'):raise ValueError('foreign conversation')
        await self.close(session)
        return web.json_response(dict(code=0,reconnect_required=True))

    async def telemetry(self,request):
        data=await request.json();session=self.find(data)
        metrics=data.get('metrics',{})
        if not isinstance(metrics,dict) or len(json.dumps(metrics))>24000:raise ValueError('invalid metrics')
        (RUNTIME/(session.control_id+'-browser-stats.json')).write_text(json.dumps(metrics,indent=2),encoding='utf-8')
        async with session.http.get(LT+'/session/stats',params={'sessionid':session.sessionid}) as r:stats=await r.json()
        session.telemetry_history.append(dict(time=time.time(),controller_monotonic_seconds=time.perf_counter(),sessionid=session.sessionid,browser=metrics,server=stats.get('data',[])))
        (RUNTIME/(session.control_id+'-stats-history.json')).write_text(json.dumps(list(session.telemetry_history),indent=2),encoding='utf-8')
        return web.json_response(dict(code=0,server=stats.get('data',[])))

    async def feedback(self,request):
        data=await request.json();session=self.find(data)
        public=session.last_public
        if not public or any(data.get(k)!=public.get(k) for k in ('sessionid','audio_id','bridge_turn_id','generation','turn_id')):
            raise ValueError('stale playback feedback')
        if data.get('kind') not in ('started','estimated_finished','cancelled','error'):raise ValueError('invalid feedback')
        with (RUNTIME/(session.control_id+'-feedback.jsonl')).open('a',encoding='utf-8') as f:
            f.write(json.dumps({k:data.get(k) for k in ('kind','audio_id','turn_id','generation','bridge_turn_id','completion_semantics','completion_margin_ms')})+'\n')
        return web.json_response(dict(code=0))

    async def recording(self,request):
        form=await request.post();session=self.find(form)
        public=session.last_public
        if not public or form.get('audio_id')!=public['audio_id'] or int(form.get('turn_id',0))!=public['turn_id']:
            raise ValueError('stale recording')
        if not hasattr(form.get('file'),'file'):raise ValueError('recording file required')
        payload=form['file'].file.read()
        if not 4<len(payload)<=50*1024**2 or payload[:4]!=bytes.fromhex('1a45dfa3'):
            raise ValueError('invalid bounded WebM recording')
        PREVIEW.mkdir(parents=True,exist_ok=True)
        target=PREVIEW/('browser-recording-'+session.control_id+'.webm')
        with target.open('xb') as f:f.write(payload)
        return web.json_response(dict(code=0,bytes=len(payload)))

    async def frame(self,request):
        import struct
        form=await request.post();session=self.find(form)
        label=form.get('label')
        if label not in ('idle','speaking') or not hasattr(form.get('file'),'file'):raise ValueError('invalid frame')
        if label=='speaking' and (not session.last_public or form.get('audio_id')!=session.last_public['audio_id']):raise ValueError('stale frame')
        payload=form['file'].file.read()
        if not 24<len(payload)<=3*1024**2 or payload[:8]!=b'\x89PNG\r\n\x1a\n' or struct.unpack('>II',payload[16:24])!=(1278,720):raise ValueError('invalid full-size PNG')
        PREVIEW.mkdir(parents=True,exist_ok=True)
        target=PREVIEW/('browser-'+label+'-'+session.control_id+'.png')
        if not target.exists():
            with target.open('xb') as f:f.write(payload)
        return web.json_response(dict(code=0))


def create_app():
    control=Control()
    @web.middleware
    async def access(request,handler):
        if request.remote!='127.0.0.1' or request.host!='127.0.0.1:8011':raise web.HTTPForbidden()
        limit=52*1024**2 if request.path=='/recording' else (4*1024**2 if request.path=='/frame' else 128*1024)
        if request.content_length is not None and request.content_length>limit:raise web.HTTPRequestEntityTooLarge(max_size=limit,actual_size=request.content_length)
        internal=request.path.startswith('/internal/')
        if internal:
            if request.headers.get('Origin') or not hmac.compare_digest(request.headers.get('X-Rebuild-Control',''),control.secret):raise web.HTTPForbidden()
        elif request.path!='/health' and request.headers.get('Origin')!=ORIGIN:
            raise web.HTTPForbidden()
        if request.method=='OPTIONS':
            return web.Response(headers={'Access-Control-Allow-Origin':ORIGIN,'Access-Control-Allow-Methods':'GET, POST, OPTIONS','Access-Control-Allow-Headers':'Content-Type'})
        try:response=await handler(request)
        except (ValueError,KeyError) as exc:
            print('Control rejected:',type(exc).__name__,flush=True)
            response=web.json_response(dict(code=-1,message='会话、轮次或媒体状态无效。请断开后重新连接。'),status=409)
        except Exception as exc:
            print('Control operation failed:',type(exc).__name__,str(exc),flush=True)
            response=web.json_response(dict(code=-1,message='本机音频操作失败，请检查服务日志。'),status=503)
        if not response.prepared:response.headers['Access-Control-Allow-Origin']=ORIGIN
        return response
    app=web.Application(middlewares=[access],client_max_size=52*1024**2)
    app['control']=control
    app.router.add_post('/internal/cancel',control.cancel_bound)
    app.router.add_get('/health',lambda _:web.json_response(dict(status='ok')))
    for path,handler in [('/connect',control.connect),('/ready',control.ready),('/preview',control.preview),('/disconnect',control.disconnect),('/telemetry',control.telemetry),('/feedback',control.feedback),('/recording',control.recording),('/frame',control.frame),('/internal/bind',control.bind),('/internal/audio',control.audio)]:
        app.router.add_post(path,handler)
    app.router.add_get('/events',control.events)
    app.router.add_route('OPTIONS','/{tail:.*}',lambda _:web.Response())
    async def cleanup(_):
        if control.session:await control.close(control.session)
    app.on_cleanup.append(cleanup)
    return app


if __name__=='__main__':web.run_app(create_app(),host='127.0.0.1',port=8011,access_log=None,print=None)
