"""No model loading: active 1.7B routing, caller identity and residency rollback."""
import ast,copy,importlib.util,json,os,runpy,sys,tempfile
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'runtime/stage7f'
sys.path.insert(0,str(ROOT));sys.stdout.reconfigure(encoding='utf-8')
os.environ['REBUILD_LLM_PROFILE']='1.7b'
import rebuild_config as cfg
checks=[]
assert cfg.PROFILE=='1.7b' and cfg.LLM_BASE_URL=='http://127.0.0.1:8081' and '1.7b' in cfg.MODEL_ALIAS
checks.append('central profile, URL, alias resolve to 1.7B/8081')
runpy.run_path(str(ROOT/'scripts/cpu-run.py'),run_name='_no_service_start')
assert os.environ['REBUILD_LLM_PROFILE']=='1.7b'
checks.append('CPU STT/WS launcher selects configured default without running either service')
spec=importlib.util.spec_from_file_location('migration_manager',ROOT/'scripts/rebuild-system.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
assert m.RECORDS['llm']==ROOT/'runtime/services-live/llm-1.7b/owner.json'
calls=[]
def capture(args,directory,timeout,env,on_timeout):calls.append(dict(args=args,env=env,timeout=timeout));return 'mock'
with patch.object(m,'run_logged',capture):
    m.invoke('llm','start','test-run')
    m.invoke('ws','start','test-run')
assert calls[0]['args'][-1]=='1.7b' and all(c['env']['REBUILD_LLM_PROFILE']=='1.7b' for c in calls)
checks.append('coordinator owner/explicit profile/environment aligned with 1.7B')
sys.path.insert(0,str(ROOT/'experiments/speech-chain-g0/client'))
import speech_chain_client as client
requests=[]
def fake_http(url,payload=None,timeout=180):
    requests.append(dict(url=url,payload=payload))
    return dict(choices=[dict(message=dict(content='正文'))],usage=dict(completion_tokens=2))
history=[dict(role='system',content=client.SYSTEM_PROMPT),dict(role='user',content='测试')]
before=copy.deepcopy(history)
with patch.object(client,'http_json',fake_http):
    client.llm_reply_raw(history);client.llm_reply(history)
    client.llm_reply_raw([dict(role='system',content='摘要契约占位'),dict(role='user',content='文本')])
assert all(r['url']=='http://127.0.0.1:8081/v1/chat/completions' and r['payload']['model']==cfg.MODEL_ALIAS for r in requests)
assert before==history
checks.append('real chat/raw/retry-summary helper routes mocked requests to same 1.7B alias; roles/history untouched')
# Caller verification keeps native time and exact active arguments; no real PID used.
args=['-m',cfg.LLM['model'],'--host','127.0.0.1','--port','8081','-ngl','0','-c','4096','-t','10','-tb','12','-np','1','--alias',cfg.MODEL_ALIAS,'--reasoning','off']
record=dict(Workspace=str(ROOT),Key='llm-1.7b',Executable=cfg.CONFIG['llama_server'],ProcessId=42,Arguments='\n'.join(args),CommandLine='exact command',CreatedUtc=datetime.fromtimestamp(1700000000,timezone.utc).isoformat(),Profile='1.7b',ModelPath=cfg.LLM['model'],ModelAlias=cfg.MODEL_ALIAS,ModelSHA256=cfg.LLM['model_sha256'],ConsoleRootIdentity=dict(Pid=42,ParentPid=41,CreationFiletime=123456789,CommandLine='exact command',Exe=cfg.CONFIG['llama_server']))
process=SimpleNamespace(pid=42,create_time=lambda:1700000000,exe=lambda:cfg.CONFIG['llama_server'],cmdline=lambda:[cfg.CONFIG['llama_server'],*args],ppid=lambda:41,net_connections=lambda kind:[SimpleNamespace(status='LISTEN',laddr=SimpleNamespace(ip='127.0.0.1',port=8081))])
file=SimpleNamespace(is_file=lambda:True,read_text=lambda **kwargs:json.dumps(record))
native_spec=SimpleNamespace(loader=SimpleNamespace(exec_module=lambda module:None))
with patch.object(cfg,'owned_path',lambda p:file),patch.object(m.psutil,'Process',lambda pid:process),patch.object(importlib.util,'spec_from_file_location',lambda *a,**k:native_spec),patch.object(importlib.util,'module_from_spec',lambda spec:SimpleNamespace(ticks=lambda pid:123456789)):
    cfg.require_owned_service('llm',8081)
    for field in ['ModelAlias','ModelSHA256']:
        previous=record[field];record[field]='wrong'
        try:cfg.require_owned_service('llm',8081)
        except RuntimeError:pass
        else:raise AssertionError('Caller accepted changed '+field)
        record[field]=previous
    record['ConsoleRootIdentity']['CreationFiletime']+=1
    try:cfg.require_owned_service('llm',8081)
    except RuntimeError:pass
    else:raise AssertionError('Caller accepted changed native FILETIME')
checks.append('caller accepts owned active model; rejects changed alias/hash/native FILETIME')
# If individual gates pass but final combined RAM is low, the original manager
# must roll back its owned service instead of declaring READY. All files/PIDs fake.
with tempfile.TemporaryDirectory(dir=OUT,prefix='contract-') as temp:
    directory=Path(temp);owner=directory/'service/owner.json';owner.parent.mkdir()
    def fake_call(name,action):
        if action=='preflight':return json.dumps(dict(status='READY'))
        if action=='start':owner.write_text(json.dumps(dict(root=str(directory),entry='mock',processes=[dict(pid=123)],StackRunId=stack.run_id)));return 'mock ready'
        if action=='status':return 'owned'
        if action=='stop':owner.unlink();return 'mock stopped'
        raise AssertionError(action)
    samples=iter([9*1024**3,5*1024**3,3*1024**3,9*1024**3,9*1024**3])
    with patch.multiple(m,ROOT=directory,RUNTIME=directory/'stack',OWNER=directory/'stack/owner.json',RECORDS={'llm':owner},ORDER=['llm']):
        stack=m.Stack(fake_call,lambda:dict(available_ram_bytes=next(samples)))
        stack.clean_start=lambda:None
        try:stack.start()
        except RuntimeError:pass
        else:raise AssertionError('Low combined residency declared READY')
        archive=json.loads(next((directory/'stack/runs').glob('*.json')).read_text())
        assert archive['startup_outcome']=='BLOCKED' and not owner.exists()
checks.append('combined residency below 4GiB refuses READY and reclaims owned mock service')
for path in ['rebuild_config.py','scripts/rebuild-system.py','scripts/cpu-run.py','scripts/rebuild-llm-profile.py','scripts/stage7f-model-inventory.py','scripts/stage7f-check-contracts.py']:
    ast.parse((ROOT/path).read_text(encoding='utf-8-sig'))
checks.append('Python syntax PASS')
result=dict(status='PASS',checks=checks,model_loads=0,real_network_requests=0)
(OUT/'contracts.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
