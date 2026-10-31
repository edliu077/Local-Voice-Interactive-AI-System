"""CPU services share the already validated exact-identity process tree manager."""
import importlib.util,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def make(name):
    s=importlib.util.spec_from_file_location(name+'_owner',ROOT/'scripts/livetalking-service.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    m.REPO=ROOT;m.RUNTIME=ROOT/f'runtime/{name}-service';m.OWNER=m.RUNTIME/'owner.json'
    m.ENTRY=ROOT/f'scripts/{name}-run.py';m.PYTHON=ROOT/'.venv-cpu/Scripts/python.exe';m.PORT={'stt':8766,'ws':8767}[name]
    m.MINIMUM_GPU_FREE_MIB=0
    # CPU services have explicit evidence-based gates, not the GPU manager default.
    m.MINIMUM_RAM_BYTES=m.resource_policy.POLICY['startup_ram_bytes'][name]
    m.HEALTH_PATH='/health';m.HEALTH_STATUS='ready';m.SERVICE_NAME='Rebuild '+name
    config=json.loads((ROOT/'config/rebuild.json').read_text())
    m.REQUIRED_INPUTS=(Path(config['stt_snapshot'])/'model.bin',ROOT/'experiments/hf-speech-to-speech/fixtures/zh-short.wav') if name=='stt' else (Path(config['vad_repository'])/'src/silero_vad/data/silero_vad.jit',)
    smi=shutil.which('nvidia-smi')
    if not smi:raise RuntimeError('GPU inventory tool missing')
    m.ALLOWED_AUXILIARY={str(Path(smi).resolve()).lower():{('--query-gpu=memory.used','--format=csv,noheader,nounits')}}
    return m
def cli(m):
    import argparse
    p=argparse.ArgumentParser();p.add_argument('action',choices=['preflight','start','stop','status']);a=p.parse_args().action
    if a=='preflight':print(json.dumps(m.preflight(),indent=2))
    elif a=='start':m.start()
    elif a=='stop':m.stop()
    elif m.OWNER.exists():m.assert_listener();print('Owned service ready')
    else:print('No owned service')
