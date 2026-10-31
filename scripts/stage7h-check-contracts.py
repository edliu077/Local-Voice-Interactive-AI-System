"""Model-free Stage 7H policy, ownership, routing and rollback contracts."""
import ast,importlib.util,json,runpy,sys,time
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runtime/stage7h/offline';OUT.mkdir(parents=True,exist_ok=True)
sys.stdout.reconfigure(encoding='utf-8')
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
p=module('policy','scripts/resource-policy.py');G=1024**3
checks=[]
def sample(ram=8*G,commit=20*G,gpu=7000,when=0,pageout=0):
    return dict(time=when,available_ram_bytes=ram,commit_headroom_bytes=commit,gpu_free_mib=gpu,page_size_bytes=4096,pages_output_per_second=pageout)
for name,floor in p.POLICY['startup_ram_bytes'].items():
    assert not p.violations(sample(floor),name)
    assert p.violations(sample(floor-1),name)
    assert p.violations(sample(commit=floor-1),name)
checks.append('all seven service RAM/commit boundaries accept equality, reject below floor')
assert p.POLICY['startup_ram_bytes']['llm-1.7b']==4*G
assert p.POLICY['startup_ram_bytes']['stt']==int(2.5*G)
assert p.POLICY['startup_ram_bytes']['ws']==int(2.5*G)
assert not p.violations(sample(int(2.8*G)),'stt')
assert p.violations(sample(int(2.8*G)),'llm-1.7b')
for name,gpu in [('tts',5120),('livetalking',2048)]:
    assert not p.violations(sample(gpu=gpu),name,gpu_minimum=gpu)
    assert p.violations(sample(gpu=gpu-1),name,gpu_minimum=gpu)
checks.append('STT and LLM distinguished; TTS5120/Wav2048 GPU gates retained')
pressure=p.Pressure()
assert pressure.check(sample(2*G))=='SAFE'
assert pressure.check(sample(int(1.5*G)))=='WARNING_BELOW_TARGET'
for item in [sample(int(1.5*G)-1),sample(commit=int(1.5*G)-1)]:
    try:pressure.check(item)
    except RuntimeError:pass
    else:raise AssertionError('resident memory rejection lost')
pressure=p.Pressure();rate=p.POLICY['paging_output_bytes_per_second']/4096
pressure.check(sample(int(1.8*G),when=1,pageout=rate))
try:pressure.check(sample(int(1.8*G),when=11,pageout=rate))
except RuntimeError:pass
else:raise AssertionError('sustained paging accepted')
pressure=p.Pressure();pressure.check(sample(int(1.8*G),when=1,pageout=rate))
pressure.check(sample(3*G,when=12,pageout=rate))
checks.append('resident hard floor, target warning, commit and sustained paging guard work')
cpu=module('cpu_policy','scripts/cpu-service.py')
for name in ['stt','ws']:
    manager=cpu.make(name)
    assert manager.MINIMUM_RAM_BYTES==int(2.5*G) and manager.MINIMUM_GPU_FREE_MIB==0
tts=module('tts_policy','scripts/tts-service.py').manager
assert tts.MINIMUM_RAM_BYTES==4*G and tts.MINIMUM_GPU_FREE_MIB==5120
lt=module('lt_policy','scripts/livetalking-service.py')
assert lt.MINIMUM_RAM_BYTES==4*G and lt.MINIMUM_GPU_FREE_MIB==2048
with patch.object(lt,'resources',lambda:sample(8*G,gpu=2047)),patch.object(lt,'listeners',lambda:[]),patch.object(lt,'OWNER',OUT/'absent-owner'),patch.object(lt,'write',lambda *a:None):
    assert lt.preflight()['status']=='BLOCKED_RESOURCES'
checks.append('actual manager bindings and actual GPU preflight reject insufficient VRAM')
# Reuse existing no-model contracts without editing their source or history outputs.
cases=[('scripts/check-conhost-contracts.py',"OUT=ROOT/'runtime/stage7b-conhost'",'conhost'),
       ('scripts/check-stage7c-recovery.py',"OUT=ROOT/'runtime/stage7c-recovery'",'recovery')]
for path,old,folder in cases:
    directory=OUT/folder;directory.mkdir(exist_ok=True)
    source=(ROOT/path).read_text(encoding='utf-8').replace(old,'OUT=Path('+repr(str(directory))+')')
    if folder=='conhost':
        # Historical byte-for-byte resource-gate checks are intentionally obsolete;
        # retain all identity/cleanup cases, and test new resource gates above.
        source=source.split("before=(OUT/'livetalking-service.before.py')")[0]+"\n(OUT/'identity-contracts.json').write_text(json.dumps(dict(status='PASS',checks=checks),indent=2))\n"
    source=source.replace("lambda:dict(available_ram_bytes=9*1024**3)","lambda:dict(time=0,available_ram_bytes=9*1024**3,commit_headroom_bytes=20*1024**3,page_size_bytes=4096,pages_output_per_second=0)")
    exec(compile(source,str(ROOT/path),'exec'),{'__file__':str(ROOT/path),'__name__':'_stage7h_contract'})
    checks.append(folder+' original ownership/cleanup contracts PASS in isolated evidence directory')
# Existing real client routing checks, stopping before obsolete 4GiB final-floor case.
source=(ROOT/'scripts/stage7f-check-contracts.py').read_text(encoding='utf-8').split('# If individual gates pass')[0]
source=source.replace("OUT=ROOT/'runtime/stage7f'",'OUT=Path('+repr(str(OUT))+')')
exec(compile(source,str(ROOT/'scripts/stage7f-check-contracts.py'),'exec'),{'__file__':str(ROOT/'scripts/stage7f-check-contracts.py'),'__name__':'_stage7h_routes'})
checks.append('real client/profile/alias/8081/native FILETIME routing contracts PASS; no HTTP requests')
m=module('stack_policy','scripts/rebuild-system.py')
for profile in ['4b','4b-hybrid']:
    try:m.invoke('llm','start',profile=profile)
    except RuntimeError as exc:assert 'Retired' in str(exc)
    else:raise AssertionError('retired profile enabled')
checks.append('4B and Hybrid rejected before any subprocess')
# Exercise final resident floor rollback with real coordinator and fake owners.
import tempfile
with tempfile.TemporaryDirectory(dir=OUT) as temp:
    directory=Path(temp);owner=directory/'llm.json'
    def call(name,action):
        if action=='preflight':return json.dumps(dict(status='READY'))
        if action=='start':owner.write_text(json.dumps(dict(root='fake',entry='fake',processes=[dict(pid=42)],StackRunId=stack.run_id)));return 'ready'
        if action=='status':return 'owned'
        if action=='stop':owner.unlink();return 'stopped'
    count=[0]
    def resource():
        count[0]+=1
        return sample(int(1.4*G) if count[0]>=6 else 9*G)
    with patch.multiple(m,ROOT=directory,RUNTIME=directory/'stack',OWNER=directory/'stack/owner.json',RECORDS={'llm':owner},ORDER=['llm']):
        stack=m.Stack(call,resource);stack.clean_start=lambda:None
        try:stack.start()
        except RuntimeError:pass
        else:raise AssertionError('low resident state accepted')
        assert not owner.exists() and not m.OWNER.exists()
        archive=json.loads(next((directory/'stack/runs').glob('*.json')).read_text(encoding='utf-8'))
        assert archive['startup_outcome']=='BLOCKED'
checks.append('new final resident floor rejects READY and reclaims owned mock service')
for path in ['scripts/resource-policy.py','scripts/cpu-service.py','scripts/livetalking-service.py','scripts/rebuild-system.py','scripts/stage7h-check-contracts.py']:
    ast.parse((ROOT/path).read_text(encoding='utf-8-sig'))
result=dict(status='PASS',checks=checks,models_loaded=0,real_inference_requests=0)
(OUT/'contracts.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
