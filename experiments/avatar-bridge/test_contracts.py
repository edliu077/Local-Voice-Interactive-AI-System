"""Deterministic signal/turn/cancel checks: never loads a model or synthesizes."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import numpy as np
import soundfile as sf
from audio_adapter import normalize,ROOT

spec=importlib.util.spec_from_file_location('turns',ROOT/'third_party/LiveTalking/server/audio_turns.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def rejected(fn):
    try:fn()
    except (ValueError,RuntimeError,sf.LibsndfileError):return
    raise AssertionError('Invalid input accepted')

out=ROOT/'runtime/stage5'
with tempfile.TemporaryDirectory(dir=out) as temp:
    base=Path(temp);source=base/'stereo.wav'
    sine=np.sin(np.arange(1001)*2*np.pi*440/24000)*.2
    sf.write(source,np.column_stack((sine,sine*.5)),24000)
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    result=normalize(source,base/'converted');assert result['source_sample_rate']==24000 and result['source_channels']==2
    assert result['output_frames']%320==0 and 0<=result['padding_frames']<320
    assert hashlib.sha256(source.read_bytes()).hexdigest()==digest
    short=base/'short.wav';sf.write(short,[.1],16000);tiny=normalize(short,base/'converted');assert tiny['output_frames']==640
    nan=base/'nan.wav';sf.write(nan,[np.nan],16000,subtype='FLOAT');rejected(lambda:normalize(nan))
    corrupt=base/'corrupt.wav';corrupt.write_bytes(b'bad');rejected(lambda:normalize(corrupt))
    empty=base/'empty.wav';sf.write(empty,np.zeros(0),16000);rejected(lambda:normalize(empty))
    long=base/'long.wav';sf.write(long,np.zeros(16000*61),16000);rejected(lambda:normalize(long))
    rejected(lambda:normalize(ROOT.parent/'outside.wav'))

a=m.AudioTurns();b=m.AudioTurns()
first,duplicate=a.begin('turn-1','abc');assert not duplicate
assert a.begin('turn-1','abc')[1]
rejected(lambda:a.begin('turn-1','different'))
rejected(lambda:a.begin('turn-2','def'))
rejected(lambda:a.cancel('wrong-turn'))
assert a.active=='turn-1' and not a.invalid
assert not a.event(dict(turn_id='turn-old',generation=1,status='end'))
assert not a.event(dict(turn_id='turn-1',generation=999,status='end'))
cancel=a.cancel('turn-1');assert cancel['reconnect_required'] and not cancel['playback_immediately_stopped']
assert not a.event(dict(turn_id='turn-1',generation=1,status='end'))
rejected(lambda:a.begin('turn-2','def'))
assert not b.invalid and b.active is None
second,_=b.begin('short-turn','ghi');assert b.event(dict(turn_id='short-turn',generation=second['generation'],status='start'))
assert b.event(dict(turn_id='short-turn',generation=second['generation'],status='end')) and b.active is None
assert b.begin('short-turn','ghi')[1]
for path in [*Path(__file__).parent.glob('*.py'),ROOT/'rebuild_config.py',* (ROOT/'scripts').glob('*tts*.py'),ROOT/'third_party/LiveTalking/server/routes.py',ROOT/'third_party/LiveTalking/avatars/base_avatar.py',ROOT/'scripts/livetalking-run.py',ROOT/'scripts/livetalking-service.py']:
    ast.parse(path.read_text(encoding='utf-8-sig'))
(out/'deterministic-checks.json').write_text(json.dumps(dict(status='PASS',adapter_cases=['24k-stereo','tiny-1-sample','NaN-reject','corrupt-reject','empty-reject','duration-reject','path-reject','source-unchanged'],turn_cases=['duplicate','conflict','busy','stale-cancel','stale-event','wrong-generation','cancel-invalidation','other-session-untouched','start-end','completed-duplicate']),indent=2),encoding='utf-8')
print('Adapter, turn ledger and cancellation contract checks PASS')
