"""Owned WAV -> mono PCM16/16kHz, padded to complete 20ms blocks."""
from pathlib import Path
from math import gcd
from uuid import uuid4
import hashlib
import json
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

ROOT=Path(__file__).resolve().parents[2]


def owned(path):
    p=Path(path).resolve()
    if not p.is_relative_to(ROOT) or p==ROOT:
        raise ValueError('Audio path must remain inside Rebuild')
    return p


def normalize(source, output_dir=None):
    source=owned(source)
    output_dir=owned(output_dir or ROOT/'runtime/avatar-bridge/audio')
    if not source.is_file() or not 0<source.stat().st_size<=50*1024**2:
        raise ValueError('Missing, empty or excessive audio file')
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    info=sf.info(source)
    if not 8000<=info.samplerate<=192000 or not 1<=info.channels<=8 or not 0<info.duration<=60:
        raise ValueError('Unsupported sample rate, channels or duration')
    data,sample_rate=sf.read(source,dtype='float64',always_2d=True)
    if not data.size or not np.isfinite(data).all():
        raise ValueError('Audio is empty or contains NaN/Inf')
    data=data.mean(axis=1)
    factor=gcd(sample_rate,16000)
    if sample_rate!=16000:
        data=resample_poly(data,16000//factor,sample_rate//factor,window=('kaiser',8.6))
    frames=len(data)
    clipped=int(np.count_nonzero(np.abs(data)>1))
    data=np.clip(data,-1,1)
    target=max(640,((frames+319)//320)*320)
    data=np.pad(data,(0,target-frames))
    output_dir.mkdir(parents=True,exist_ok=True)
    output=owned(output_dir/(uuid4().hex+'.wav'))
    with output.open('xb') as stream:
        sf.write(stream,data,16000,format='WAV',subtype='PCM_16')
    actual=sf.info(output)
    assert actual.subtype=='PCM_16' and actual.channels==1 and actual.samplerate==16000 and actual.frames==target
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    result=dict(source=str(source),source_sha256=before,source_sample_rate=sample_rate,source_channels=info.channels,
                source_frames=info.frames,source_seconds=info.duration,resampled_frames=frames,padding_frames=target-frames,
                padding_seconds=(target-frames)/16000,output=str(output),output_frames=target,output_seconds=target/16000,
                sample_rate=16000,channels=1,subtype='PCM_16',clipped_samples=clipped,
                output_sha256=hashlib.sha256(output.read_bytes()).hexdigest())
    output.with_suffix('.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result
