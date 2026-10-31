"""Stage 5 one generated WAV, one upload, one recorded local WebRTC session."""
import asyncio
import json
from pathlib import Path
import sys
import time
import subprocess
import aiohttp
import aioice.ice
import cv2
import numpy as np
import psutil
from aiortc import RTCPeerConnection, RTCConfiguration, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaRecorder
from bridge import AudioBridge, manager, generate_tts

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'runtime/stage5'
aioice.ice.get_host_addresses=lambda use_ipv4,use_ipv6:['127.0.0.1'] if use_ipv4 else []


async def main():
    if (OUT/'runtime-attempt.json').exists():raise RuntimeError('Runtime attempt exists; inspect instead of automatic replay')
    manager('livetalking').assert_listener()
    tts=json.loads((OUT/'tts-result.json').read_text(encoding='utf-8')) if (OUT/'tts-result.json').exists() else None
    (OUT/'runtime-attempt.json').write_text(json.dumps(dict(attempts=1)),encoding='utf-8')
    pc=RTCPeerConnection(RTCConfiguration(iceServers=[]))
    recorder=MediaRecorder(str(OUT/'qwen-tts-avatar-webrtc.mp4'))
    counts=dict(audio=0,video=0)
    video_times=[];resources=[];states=[];rms=[];tasks=[]
    result=dict(status='STARTING',mode='serial' if tts else 'concurrent',browser_playback_confirmed=False)
    bridge=None
    class Measured(MediaStreamTrack):
        def __init__(self,track):super().__init__();self.track=track;self.kind=track.kind
        async def recv(self):
            frame=await self.track.recv();counts[self.kind]+=1
            if self.kind=='video':
                video_times.append(time.perf_counter())
                if counts['video'] in (1,70,100):cv2.imwrite(str(OUT/f"frame-{counts['video']:03d}.png"),frame.to_ndarray(format='bgr24'))
            elif counts['audio']%10==0:
                a=frame.to_ndarray().astype(np.float64);rms.append(float(np.sqrt(np.mean(a*a))))
            return frame
    @pc.on('track')
    def on_track(track):recorder.addTrack(Measured(track))
    @pc.on('connectionstatechange')
    async def on_state():states.append(dict(time=time.time(),state=pc.connectionState))

    async def sample():
        ids=[v['pid'] for v in manager('livetalking').assert_listener()['processes']]
        if result['mode']=='concurrent':ids += [v['pid'] for v in manager('tts').assert_listener()['processes']]
        while True:
            gpu=await asyncio.to_thread(subprocess.check_output,['nvidia-smi','--query-gpu=memory.used,memory.free','--format=csv,noheader,nounits'],text=True)
            resources.append(dict(time=time.time(),available_ram_bytes=psutil.virtual_memory().available,
                                  rss_bytes=sum(psutil.Process(pid).memory_info().rss for pid in ids if psutil.pid_exists(pid)),gpu_used_free_mib=gpu.strip()))
            await asyncio.sleep(1)
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=90)) as http:
            # Same-origin preflight verifies the CORS change dynamically.
            async with http.options('http://127.0.0.1:8010/humanaudio',headers={'Origin':'http://127.0.0.1:8010','Access-Control-Request-Method':'POST'}) as r:
                result['cors']=dict(status=r.status,allow_origin=r.headers.get('Access-Control-Allow-Origin'))
                assert r.status==200 and result['cors']['allow_origin']=='http://127.0.0.1:8010'
            async with http.options('http://127.0.0.1:8010/humanaudio',headers={'Origin':'https://untrusted.invalid','Access-Control-Request-Method':'POST'}) as r:
                result['cors_disallowed_status']=r.status
                assert r.status==403
            pc.addTransceiver('audio',direction='recvonly');pc.addTransceiver('video',direction='recvonly')
            await pc.setLocalDescription(await pc.createOffer())
            started=time.perf_counter()
            async with http.post('http://127.0.0.1:8010/offer',json={'sdp':pc.localDescription.sdp,'type':'offer','avatar':'cybergirlfriend_avatar_v1'}) as r:answer=await r.json()
            if 'sessionid' not in answer:raise RuntimeError(str(answer))
            result['sessionid']=answer['sessionid']
            bridge=AudioBridge(http,pc,answer['sessionid'])
            await pc.setRemoteDescription(RTCSessionDescription(sdp=answer['sdp'],type=answer['type']))
            await recorder.start();tasks.append(asyncio.create_task(sample()))
            ready=asyncio.Event()
            async def sse():
                async with http.get('http://127.0.0.1:8010/sse',params={'sessionid':answer['sessionid']}) as r:
                    assert r.status==200;ready.set()
                    async for line in r.content:
                        if line.startswith(b'data: '):bridge.accept_event(json.loads(line[6:]))
            tasks.append(asyncio.create_task(sse()))
            await asyncio.wait_for(ready.wait(),10)
            deadline=time.perf_counter()+60
            while counts['video']<30:
                if time.perf_counter()>deadline:raise TimeoutError('Connected but first idle media not ready; no automatic retry')
                await asyncio.sleep(.1)
            result['first_media_ready_seconds']=time.perf_counter()-started
            if tts is None:
                tts=await generate_tts('你好，这是数字人语音接入测试。')
            result['turn_id']=tts['turn_id']
            result['upload']=await bridge.upload(tts)
            deadline=time.perf_counter()+45
            while not any(e.get('status')=='end' for e in bridge.events):
                if time.perf_counter()>deadline:raise TimeoutError('No matching server media-end event')
                await asyncio.sleep(.1)
            await asyncio.sleep(1)
            result['events']=bridge.events;result['ignored_events']=bridge.ignored_events
            assert any(e.get('status')=='start' for e in bridge.events)
            async with http.post('http://127.0.0.1:8010/is_speaking',json={'sessionid':answer['sessionid']}) as r:result['speaking_after']=await r.json()
            result['invalidation_after_end']=await bridge.cancel()
            result['status']='PASS'
    except Exception as exc:
        result.update(status='FAILED',error=f'{type(exc).__name__}: {exc}')
        raise
    finally:
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        await recorder.stop();await pc.close()
        result.update(counts=counts,connection_states=states,resources=resources,max_audio_rms=max(rms,default=0))
        if len(video_times)>1:result['received_video_fps']=(len(video_times)-1)/(video_times[-1]-video_times[0])
        (OUT/'runtime-result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='resources'},ensure_ascii=False,indent=2))

asyncio.run(main())
