"""Deterministic deadlines/readiness/exit/ownership tests: zero models or services."""
import importlib.util,json,types
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runtime/stage7b-tts-fix'
s=importlib.util.spec_from_file_location('tts_test',ROOT/'scripts/tts-service.py');tts=importlib.util.module_from_spec(s);s.loader.exec_module(tts)
Policy=tts.policy_module.StartupPolicy
checks=[]
def rejects(call,kind,text):
    try:call()
    except kind as error:assert text in str(error)
    else:raise AssertionError('Expected failure: '+text)
p=Policy(0);p.check(359);rejects(lambda:p.check(360),TimeoutError,'loading')
p=Policy(0);p.event({'event':'model_loaded','model_load_count':1},170);p.event({'event':'voice_clone_prompt_created'},178);p.event({'event':'warmup_started'},179);p.check(300)
p.event({'event':'warmup_completed'},320);p.event({'event':'service_ready'},321);p.check(340)
checks.append('historical slow load plus completed warmup can remain within TTS-only bounded budget')
p=Policy(0);p.event({'event':'model_loaded'},359);p.event({'event':'voice_clone_prompt_created'},478);rejects(lambda:p.check(600),TimeoutError,'absolute')
p=Policy(0);p.event({'event':'model_loaded'},1);p.event({'event':'model_loaded'},119);rejects(lambda:p.check(121),TimeoutError,'prompt')
p=Policy(0);p.event({'event':'model_loaded'},1);p.event({'event':'voice_clone_prompt_created'},2);rejects(lambda:p.check(182),TimeoutError,'warmup')
checks.append('absolute and stalled phase limits enforced; repeated event cannot extend wait')
rejects(lambda:Policy(0).event({'event':'initialization_failed','error':'real failure'},1),RuntimeError,'real failure')
rejects(lambda:Policy(0).event({'event':'tts_request_gpu_limit_exceeded'},1),RuntimeError,'failure')
rejects(lambda:Policy(0).event({'event':'model_loaded','model_load_count':2},1),RuntimeError,'Repeated')
checks.append('real initialization/GPU safety errors and repeated loading fail immediately')
body=dict(status='ready',model='Qwen/Qwen3-TTS-12Hz-0.6B-Base',device='cuda',voice_clone_prompt_ready=True,model_load_count=1,voice_clone_prompt_create_count=1,warmup_count=1,request_count=0)
tts.validate_ready(body)
rejects(lambda:tts.validate_ready(dict(body,warmup_count=0)),RuntimeError,'contract')
checks.append('READY requires exact model, clone, one completed warmup and zero target requests')
with patch.object(tts.manager,'register_children',side_effect=AssertionError('should not inspect exited process')):
    rejects(lambda:tts.wait_for_tts(types.SimpleNamespace(poll=lambda:7,returncode=7),None,{},0),RuntimeError,'exited 7')
with patch.object(tts.manager,'register_children',side_effect=RuntimeError('identity mismatch')):
    rejects(lambda:tts.wait_for_tts(types.SimpleNamespace(poll=lambda:None),None,{},0),RuntimeError,'identity mismatch')
checks.append('process exit and identity rejection are never postponed by larger timeout')
# Source guard: only observability was added around the existing warmup call.
before=(OUT/'tts_service.before.py').read_text(encoding='utf-8-sig');after=(ROOT/'experiments/qwen3-tts-e0/service/tts_service.py').read_text(encoding='utf-8-sig')
for line in ['        warmup_started = time.perf_counter()\n','        log("warmup_started", warmup_count=self.warmup_count)\n','        log("warmup_completed", seconds=time.perf_counter() - warmup_started, warmup_count=self.warmup_count)\n']:after=after.replace(line,'')
assert before==after
checks.append('model/clone/warmup implementation unchanged byte-for-byte after removing three diagnostic lines')
(OUT/'policy-checks.json').write_text(json.dumps(dict(status='PASS',checks=checks,model_loads=0,service_starts=0),indent=2))
print('TTS startup deterministic checks PASS:',len(checks))
