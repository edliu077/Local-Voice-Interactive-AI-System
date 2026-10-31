"""Pure immediate-coroutine client checks: no sockets, TTS or model loading."""
import asyncio
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import bridge as b


def run_immediate(coroutine):
    try:
        coroutine.send(None)
    except StopIteration as done:
        return done.value
    finally:
        coroutine.close()
    raise AssertionError('An offline mock unexpectedly scheduled I/O')


class Peer:
    def __init__(self):self.closes=0
    async def close(self):self.closes+=1


class Response:
    def __init__(self,http,url):self.http=http;self.url=url
    async def __aenter__(self):
        bridge=self.http.bridge
        assert bridge.lock.locked()
        if self.url.endswith('/humanaudio'):
            assert bridge.generation is None
            self.http.uploads+=1
            # Exercise an event arriving before the upload acknowledgement.
            assert bridge.accept_event(dict(sessionid='s',turn_id=bridge.active,generation=self.http.uploads,status='start'))
        else:
            assert bridge.invalid
        return self
    async def __aexit__(self,*args):pass
    def raise_for_status(self):pass
    async def json(self):
        if self.url.endswith('/humanaudio'):
            return dict(code=0,data=dict(turn_id=self.http.bridge.active,generation=self.http.uploads,duplicate=False))
        return dict(code=0,data=dict(session_invalidated=True,reconnect_required=True,playback_immediately_stopped=False))


class HTTP:
    uploads=0
    def post(self,url,**kwargs):return Response(self,url)


with tempfile.TemporaryDirectory(dir=b.OUT) as temp:
    root=Path(temp);wav=root/'audio.wav';wav.write_bytes(b'mocked WAV upload only')
    http=HTTP();peer=Peer();client=b.AudioBridge(http,peer,'s');http.bridge=client
    with patch.object(b,'ROOT',root),patch.object(b,'normalize',lambda _:dict(output=str(wav),source_sample_rate=24000)),patch.object(b,'manager',lambda _:type('Owner',(),{'assert_listener':lambda _:None})()):
        first=dict(turn_id='t1',audio_path=str(wav),sample_rate=24000)
        assert run_immediate(client.upload(first))['upload']['code']==0
        assert not client.accept_event(dict(sessionid='other',turn_id='t1',generation=1,status='end'))
        assert not client.accept_event(dict(sessionid='s',turn_id='t1',generation=9,status='end'))
        assert client.accept_event(dict(sessionid='s',turn_id='t1',generation=1,status='end'))
        try:run_immediate(client.upload(first))
        except RuntimeError:pass
        else:raise AssertionError('Client duplicated a completed turn')
        second=dict(first,turn_id='t2');run_immediate(client.upload(second));assert client.generation==2
        assert run_immediate(client.cancel())['data']['reconnect_required']
        assert peer.closes==1 and client.invalid
        assert not client.accept_event(dict(sessionid='s',turn_id='t2',generation=2,status='end'))
        assert http.uploads==2  # Both are mocks; no server request is made.
(b.OUT/'bridge-state-checks.json').write_text(json.dumps(dict(status='PASS',checks=['early-event','stale-session','stale-generation','duplicate-refused','next-turn-generation-reset','cancel-submit-lock','cancel-invalidates-and-closes-peer','late-event-refused'],real_tts_requests=0,real_uploads=0),indent=2),encoding='utf-8')
print('Offline bridge state checks PASS; no network/model/TTS')
