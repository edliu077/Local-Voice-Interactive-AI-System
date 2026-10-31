"""Installed API normalization + real WAV decoding, without AI imports/inference."""
import ast,copy,importlib.util,json,sys,tempfile
from pathlib import Path
from unittest.mock import patch
import _winapi
import numpy as np
import soundfile as sf
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'runtime/tts-reference-array-fix/offline';OUT.mkdir(parents=True,exist_ok=True)
service=ast.parse((ROOT/'experiments/qwen3-tts-e0/service/tts_service.py').read_text(encoding='utf-8'))
loader=next(n for n in service.body if isinstance(n,ast.FunctionDef) and n.name=='load_reference_audio')
namespace=dict(np=np,sf=sf,Path=Path)
exec(compile(ast.Module(body=[loader],type_ignores=[]),'reference_loader_contract','exec'),namespace)
read=namespace['load_reference_audio']
api_path=ROOT/'.venv-tts/Lib/site-packages/qwen_tts/inference/qwen3_tts_model.py'
api=ast.parse(api_path.read_text(encoding='utf-8'))
model=next(n for n in api.body if isinstance(n,ast.ClassDef) and n.name=='Qwen3TTSModel')
methods=[copy.deepcopy(n) for n in model.body if isinstance(n,ast.FunctionDef) and n.name in ('_ensure_list','_normalize_audio_inputs')]
# Execute the installed normalization method verbatim; do not import the model
# package, instantiate the real model, or invoke encode/embedding/generate.
prefix=ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)
wrapper=ast.ClassDef(name='NormalizationOnly',bases=[],keywords=[],body=methods,decorator_list=[])
normal_ns=dict(np=np)
exec(compile(ast.fix_missing_locations(ast.Module(body=[prefix,wrapper],type_ignores=[])),'installed_qwen_normalization','exec'),normal_ns)
normalizer=normal_ns['NormalizationOnly']()
path_calls=[]
def forbidden_path(value):
    path_calls.append(value)
    raise AssertionError('String-path decoder/audioread branch reached')
normalizer._load_audio_to_np=forbidden_path
calls=[n for n in ast.walk(service) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=='create_voice_clone_prompt']
assert len(calls)==1
keywords={k.arg:k.value for k in calls[0].keywords}
assert ast.dump(keywords['ref_audio'])==ast.dump(ast.parse('(ref_audio, ref_sr)',mode='eval').body)
assert isinstance(keywords['x_vector_only_mode'],ast.Constant) and keywords['x_vector_only_mode'].value is False
checks=[];native_calls=[]
def no_native_creation(*args,**kwargs):
    native_calls.append(True);raise AssertionError('Unexpected native process creation')
import tts_helper_client as guard
with patch.object(_winapi,'CreateProcess',no_native_creation):
    restore=guard.install(ROOT)
    try:
        import librosa
        import audioread
        with patch.object(audioread,'available_backends',side_effect=AssertionError('External decoder discovery reached')),patch.object(librosa,'load',side_effect=AssertionError('librosa path load reached')):
            ref_path=ROOT/'assets/voice-clone/reference-short.wav'
            actual,sr=read(ref_path)
            raw,native_sr=sf.read(str(ref_path),dtype='float32',always_2d=False)
            expected=librosa.to_mono(raw.T)
            np.testing.assert_array_equal(actual,expected)
            assert sr==native_sr and actual.ndim==1 and actual.size>0 and actual.dtype==np.float32
            normalized=normalizer._normalize_audio_inputs(normalizer._ensure_list((actual,sr)))
            np.testing.assert_array_equal(normalized[0][0],actual);assert normalized[0][1]==sr
            metadata=dict(sample_rate=sr,samples=len(actual),seconds=len(actual)/sr,original_channels=sf.info(str(ref_path)).channels)
            with tempfile.TemporaryDirectory(dir=OUT,prefix='synthetic-') as temp:
                for rate in (16000,22050,44100):
                    for channels in (1,2,3):
                        source=np.linspace(-.4,.4,600*channels,dtype=np.float32).reshape(600,channels)
                        if channels==1:source=source[:,0]
                        path=Path(temp)/f'{rate}-{channels}.wav'
                        sf.write(str(path),source,rate,subtype='FLOAT')
                        samples,original_rate=read(path)
                        expected=librosa.to_mono(source.T)
                        np.testing.assert_array_equal(samples,expected)
                        assert samples.ndim==1 and original_rate==rate
                        result=normalizer._normalize_audio_inputs([(samples,original_rate)])
                        np.testing.assert_array_equal(result[0][0],expected);assert result[0][1]==rate
            assert not path_calls and not native_calls
            checks.append('installed Qwen tuple normalization executes with real reference and nine synthetic WAVs, without librosa.load/audioread discovery/native process creation')
            checks.append('mono/stereo/three-channel output exactly equals installed librosa.to_mono; all original sample rates and float32 samples preserved')
        for samples,rate in [(np.array([],dtype=np.float32),24000),(np.zeros((4,0),dtype=np.float32),24000),(np.array([np.nan],dtype=np.float32),24000),(np.array([np.inf],dtype=np.float32),24000),(np.zeros((2,2,2),dtype=np.float32),24000),(np.ones(4,dtype=np.float32),0),(np.ones(4,dtype=np.float32),-1),(np.ones(4,dtype=np.float32),True),(np.ones(4,dtype=np.float32),24000.5)]:
            with patch.object(sf,'read',return_value=(samples,rate)):
                try:read(Path('invalid.wav'))
                except ValueError:pass
                else:raise AssertionError('Invalid reference accepted')
        checks.append('empty, invalid shape, non-finite samples and invalid sample rates refused')
        import subprocess
        try:subprocess.Popen(['cmd.exe','/c','echo unregistered'])
        except RuntimeError as exc:assert 'Unregistered TTS external creation refused' in str(exc)
        else:raise AssertionError('Unknown process bypassed safety gate')
        assert not native_calls
        checks.append('unchanged production safety gate still rejects unknown command before OS creation; zero actual subprocesses')
    finally:restore()
assert not any(n in sys.modules for n in ('torch','qwen_tts','faster_qwen3_tts','transformers'))
policy_spec=importlib.util.spec_from_file_location('reference_fix_resource_policy',ROOT/'scripts/resource-policy.py')
policy=importlib.util.module_from_spec(policy_spec);policy_spec.loader.exec_module(policy)
G=1024**3
def sample(ram=8*G,commit=20*G,gpu=7000,when=1,pageout=0):
    return dict(time=when,available_ram_bytes=ram,commit_headroom_bytes=commit,gpu_free_mib=gpu,page_size_bytes=4096,pages_output_per_second=pageout)
floor=policy.POLICY['startup_ram_bytes']['tts']
assert floor==4*G
assert not policy.violations(sample(ram=floor,gpu=5120),'tts',gpu_minimum=5120)
for value in [sample(ram=floor-1),sample(commit=floor-1),sample(gpu=5119)]:
    assert policy.violations(value,'tts',gpu_minimum=5120)
pressure=policy.Pressure();rate=policy.POLICY['paging_output_bytes_per_second']/4096
pressure.check(sample(ram=int(1.8*G),when=1,pageout=rate))
try:pressure.check(sample(ram=int(1.8*G),when=11,pageout=rate))
except RuntimeError:pass
else:raise AssertionError('Paging pressure guard disabled')
checks.append('unchanged TTS RAM/Commit/GPU boundaries and sustained paging rejection PASS with synthetic samples')
(OUT/'contracts.json').write_text(json.dumps(dict(status='PASS',checks=checks,reference=metadata,model_loads=0,inference_calls=0,external_processes=0),ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(dict(status='PASS',checks=checks,reference=metadata),ensure_ascii=False,indent=2))
