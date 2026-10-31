"""No model imports: NVML error paths, source gate and request monitor failure."""
import ast,copy,ctypes as c,importlib.util,json,os,sys,threading,time,uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import tts_gpu_monitor as gpu
import tts_nvml as nvml
import tts_helper_client as client
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runtime/tts-reliability-repair/offline'
checks=[]
def reject(call):
    try:call()
    except (RuntimeError,OSError,KeyError):return
    raise AssertionError('Unsafe monitor value accepted')
u='GPU-00000000-0000-0000-0000-000000000001'
for value in (u,u[4:],uuid.UUID(u[4:])):gpu.validate_cuda_uuid(value,1,u)
gpu.validate_cuda_uuid(SimpleNamespace(bytes=uuid.UUID(u[4:]).bytes),1,u)
gpu.validate_cuda_uuid(None,1,u)
reject(lambda:gpu.validate_cuda_uuid(None,2,u))
reject(lambda:gpu.validate_cuda_uuid('GPU-'+str(uuid.uuid4()),1,u))
checks.append('physical GPU mapping accepts matching binary/string UUID; mismatch/unknown multi-GPU rejected')
fake=nvml.NVML.__new__(nvml.NVML);fake.device=c.c_void_p(1);fake.uuid=u;fake.lock=threading.Lock()
fake.dll=SimpleNamespace(nvmlDeviceGetMemoryInfo_v2=lambda *args:999)
reject(fake.memory)
with patch.object(c,'WinDLL',side_effect=OSError('DLL unavailable')):reject(lambda:nvml.NVML(u))
def invalid(device,value):
    info=c.cast(value,c.POINTER(nvml.MemoryV2)).contents
    info.total=1024;info.used=2048;info.free=0
    return 0
fake.dll.nvmlDeviceGetMemoryInfo_v2=invalid;reject(fake.memory)
checks.append('missing NVML DLL, native API failure and invalid memory values fail closed, never fake zero')
monitor=gpu.GPUMonitor.__new__(gpu.GPUMonitor)
monitor.nvml=None;monitor.error=None;monitor.lock=threading.Condition();monitor.process=SimpleNamespace(poll=lambda:None)
monitor.last=1000;monitor.last_at=time.monotonic()-5
reject(monitor.used_mib)
monitor.last_at=time.monotonic();assert monitor.used_mib()==1000
monitor.error='test failure';reject(monitor.used_mib)
checks.append('fallback accepts actual fresh samples; stale/failed samples cannot bypass GPU guard')
restore=client.install(ROOT)
try:reject(lambda:client.launch('query')) # matching command alone is insufficient
finally:restore()
checks.append('GPU helper API called from wrong code source is rejected before pipe/process creation')
tree=ast.parse((ROOT/'experiments/qwen3-tts-e0/service/tts_service.py').read_text(encoding='utf-8'))
definition=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='RequestMonitor')
ns=dict(threading=threading,Exception=Exception,gpu_used_mib=lambda:(_ for _ in ()).throw(RuntimeError('sensor failure')),
        psutil=SimpleNamespace(Process=lambda:SimpleNamespace(memory_info=lambda:SimpleNamespace(rss=123))))
exec(compile(ast.Module(body=[definition],type_ignores=[]),'monitor-policy-contract','exec'),ns)
request=ns['RequestMonitor']();reject(request.start)
request=ns['RequestMonitor']();ns['gpu_used_mib']=lambda:1000
request.start();ns['gpu_used_mib']=lambda:(_ for _ in ()).throw(RuntimeError('background sensor failure'))
request._thread.join(timeout=2);assert request.error is not None
reject(request.finish)
checks.append('initial/background resource-sampling failure aborts monitor, joins thread and propagates through finish; no silent protection disable')
before=ast.parse((ROOT/'runtime/tts-reliability-repair/before/experiments_qwen3-tts-e0_service_tts_service.py').read_text(encoding='utf-8'))
def model_calls(tree):
    result=[]
    for node in ast.walk(tree):
        if not isinstance(node,ast.Call) or not isinstance(node.func,ast.Attribute) or node.func.attr not in ('from_pretrained','create_voice_clone_prompt','generate_voice_clone'):continue
        node=copy.deepcopy(node)
        if node.func.attr=='create_voice_clone_prompt':
            # Authorized local WAV -> decoded array adaptation only. All other
            # model, clone-mode/text and generation arguments remain compared.
            keyword=next(k for k in node.keywords if k.arg=='ref_audio')
            allowed=[ast.parse('str(REFERENCE_AUDIO)',mode='eval').body,ast.parse('(ref_audio, ref_sr)',mode='eval').body]
            assert ast.dump(keyword.value) in [ast.dump(value) for value in allowed]
            keyword.value=ast.Constant('same_reference_audio_decoded_without_external_probe')
        result.append(ast.dump(node,include_attributes=False))
    return result
assert model_calls(before)==model_calls(tree)
checks.append('model dtype/device/backend, clone text/x_vector mode and generation unchanged; only authorized path-to-array reference adaptation differs')
assert not any(n in sys.modules for n in ('torch','transformers','qwen_tts','faster_qwen3_tts'))
(OUT/'monitor-contracts.json').write_text(json.dumps(dict(status='PASS',checks=checks,model_loads=0),indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS',checks=checks),indent=2))
