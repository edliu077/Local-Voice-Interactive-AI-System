"""One-shot, owned TTS -> normalized WAV -> owned LiveTalking. No implicit retry."""
import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import re
from uuid import uuid4
import aiohttp
from audio_adapter import normalize, owned

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
OUT=ROOT/'runtime/stage5'


def manager(name):
    spec=importlib.util.spec_from_file_location('bridge_'+name,ROOT/'scripts'/f'{name}-service.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.manager if name=='tts' else module


async def generate_tts(text, turn_id=None):
    turn_id=turn_id or uuid4().hex
    result_path=OUT/'tts-result.json'
    attempt=OUT/'tts-attempt.json'
    if result_path.exists() or attempt.exists():
        raise RuntimeError('TTS request already attempted; refusing implicit regeneration')
    manager('tts').assert_listener()
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=180)) as http:
        async with http.get('http://127.0.0.1:8765/health') as r: before=await r.json()
        if before.get('status')!='ready' or not before.get('voice_clone_prompt_ready'):
            raise RuntimeError('Owned TTS is not clone-ready')
        attempt.write_text(json.dumps(dict(turn_id=turn_id,text=text,status='attempting')),encoding='utf-8')
        async with http.post('http://127.0.0.1:8765/tts',json={'text':text}) as r:
            r.raise_for_status();result=await r.json()
        async with http.get('http://127.0.0.1:8765/health') as r: after=await r.json()
    wav=owned(result['audio_path'])
    if not wav.is_relative_to(ROOT/'runtime/tts') or not result.get('ok'):
        raise RuntimeError('Invalid TTS output path/result')
    assert after['request_count']==before['request_count']+1
    result.update(turn_id=turn_id,health_before=before,health_after=after)
    result_path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return result


class AudioBridge:
    def __init__(self,http,pc,sessionid):
        self.http,self.pc,self.sessionid=http,pc,sessionid
        self.active=None
        self.generation=None
        self.invalid=False
        self.events=[]
        self.ignored_events=[]
        self.seen=set()
        self.lock=asyncio.Lock()

    async def upload(self,tts_result):
        async with self.lock:
            turn=str(tts_result['turn_id'])
            if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,96}',turn):
                raise ValueError('Invalid turn_id')
            if self.invalid or self.active or turn in self.seen:
                raise RuntimeError('Invalid, busy or duplicate bridge turn')
            manager('livetalking').assert_listener()
            converted=normalize(tts_result['audio_path'])
            if converted['source_sample_rate']!=tts_result['sample_rate']:
                raise RuntimeError('TTS-reported sample rate differs from WAV')
            self.active=turn;self.generation=None;self.seen.add(turn)
            ledger_dir=ROOT/'runtime/avatar-bridge/turns'
            ledger_dir.mkdir(parents=True,exist_ok=True)
            # Windows filenames cannot contain colon, though the wire ID can.
            ledger=ledger_dir/(hashlib.sha256(turn.encode()).hexdigest()+'.json')
            with ledger.open('x',encoding='utf-8') as f:
                json.dump(dict(sessionid=self.sessionid,turn_id=turn,conversion=converted,status='submitting_no_automatic_retry'),f,indent=2)
            form=aiohttp.FormData()
            form.add_field('sessionid',self.sessionid)
            form.add_field('turn_id',turn)
            form.add_field('file',Path(converted['output']).read_bytes(),filename=Path(converted['output']).name,content_type='audio/wav')
            try:
                async with self.http.post('http://127.0.0.1:8010/humanaudio',data=form) as r:
                    r.raise_for_status();body=await r.json()
                if body.get('code')!=0:
                    raise RuntimeError(str(body))
                data=body['data']
                if data['turn_id']!=turn or data['duplicate']:
                    raise RuntimeError('Unexpected upload acknowledgement')
                self.generation=data['generation']
                return dict(conversion=converted,upload=body,sessionid=self.sessionid,turn_id=turn)
            except BaseException:
                self.invalid=True
                await self.pc.close()
                raise

    def accept_event(self,event):
        # End signals server processing, never the browser speaker's actual end.
        if (self.invalid or event.get('sessionid')!=self.sessionid or event.get('turn_id')!=self.active
                or (self.generation is not None and event.get('generation')!=self.generation)):
            self.ignored_events.append(event);return False
        self.events.append(event)
        if event.get('status')=='end':
            self.active=None
        return True

    async def cancel(self):
        async with self.lock:
            self.invalid=True
            try:
                async with self.http.post('http://127.0.0.1:8010/interrupt_talk',json={'sessionid':self.sessionid,'turn_id':self.active}) as r:
                    result=await r.json()
                    if result.get('code')!=0:raise RuntimeError(str(result))
                    return result
            finally:
                await self.pc.close()


if __name__=='__main__':
    print(json.dumps(asyncio.run(generate_tts('你好，这是数字人语音接入测试。')),ensure_ascii=False,indent=2))
