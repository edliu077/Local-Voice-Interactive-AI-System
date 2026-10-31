"""Offline A/V queue/PTS/diagnostic contracts. No services or AI imports."""
import ast,asyncio,importlib.util,json,logging,queue,sys,threading,time
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runtime/av-stutter-investigation/offline';OUT.mkdir(parents=True,exist_ok=True)
path=ROOT/'third_party/LiveTalking/utils/realtime_diagnostics.py'
spec=importlib.util.spec_from_file_location('av_diag_test',path)
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
checks=[]
diagnostic=d.Diagnostics(OUT/'bounded-logs')
# No IO on the observing thread; aggregation and memory stay bounded under load.
diagnostic.worker=object()
for i in range(2000):diagnostic.observe('s','stage',{'turn_id':'same','generation':1},cost_ms=2)
assert len(diagnostic.windows)==1 and diagnostic.queue.qsize()<=256
for i in range(300):diagnostic.observe(str(i),'stage',force=True,cost_ms=1)
assert len(diagnostic.windows)<=128 and diagnostic.queue.qsize()<=256 and diagnostic.dropped>0
before=diagnostic.queue.qsize();diagnostic.lock.acquire()
try:diagnostic.observe('s','stage',cost_ms=1)
finally:diagnostic.lock.release()
assert diagnostic.queue.qsize()==before
checks.append('nonblocking contention/full-queue drop, <=256 records, <=128 aggregation windows')
import numpy as np
from av import VideoFrame
# Import only the media adapter, replacing its historical logger. No avatar,
# torch, model loading, server, sockets or render worker is created.
sys.path.insert(0,str(ROOT/'third_party/LiveTalking'))
source=(ROOT/'third_party/LiveTalking/server/webrtc.py').read_text(encoding='utf-8')
source=source.replace('from utils.logger import logger as mylogger',"mylogger=logging.getLogger('offline-av-null')")
ns={'__name__':'offline_webrtc'};exec(compile(source,'offline_webrtc','exec'),ns)
events=[]
avatar=SimpleNamespace(sessionid='offline-session',notify=lambda e:events.append(e))
player=ns['HumanPlayer'](avatar);player._start=lambda track:None
player.diagnostic_context={'turn_id':'offline:1','generation':7}
image=np.zeros((16,16,3),dtype=np.uint8)
audio=np.arange(320,dtype=np.int16)
for i in range(2):
    player.push_video(image)
    player.push_audio(audio,{'turn_id':'offline:1','generation':7,'status':'start' if i==0 else 'end'})
assert player.video._queue.qsize()==2 and player.audio._queue.qsize()==2
async def consume():
    v1=await player.video.recv();v2=await player.video.recv()
    a1=await player.audio.recv();a2=await player.audio.recv()
    assert (v1.pts,v2.pts)==(0,3600) and (a1.pts,a2.pts)==(0,320)
    assert a1.sample_rate==16000 and np.array_equal(a1.to_ndarray().ravel(),audio)
    assert v1.width==16 and v2.height==16 and len(events)==2
asyncio.run(consume())
assert player.video._queue.empty() and player.audio._queue.empty()
checks.append('real synthetic PyAV frames: queue diagnostics preserve audio samples, video dimensions, 20ms/40ms PTS and one notification per audio event')
for file in ['third_party/LiveTalking/avatars/base_avatar.py','third_party/LiveTalking/avatars/audio_features/mel.py','third_party/LiveTalking/server/webrtc.py','third_party/LiveTalking/server/rtc_manager.py','third_party/LiveTalking/streamout/webrtc.py','experiments/avatar-bridge/control_service.py']:
    ast.parse((ROOT/file).read_text(encoding='utf-8'))
assert not any(name in sys.modules for name in ['torch','transformers','qwen_tts','faster_qwen3_tts'])
checks.append('all Python sources parse; no torch/AI imports or model/service starts')
(OUT/'contracts.json').write_text(json.dumps(dict(status='PASS',checks=checks,models_loaded=0,services_started=0),indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS',checks=checks),indent=2))
