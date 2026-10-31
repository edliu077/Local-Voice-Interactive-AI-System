"""Process safeguards and HTTP business contract tests, without models/network."""
import asyncio
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
def load(name,path):
    s=importlib.util.spec_from_file_location(name,ROOT/path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=load('owner','scripts/livetalking-service.py')
class Process:
    def __init__(self,pid,exe,command):self.pid=pid;self.path=str(exe);self.command=command;self.created=10000000+pid
    def exe(self):return self.path
    def cmdline(self):return self.command
    def children(self,recursive=True):return [console] if self.pid==1 else []
parent=Process(1,m.PYTHON,[str(m.PYTHON),'-B','-s',str(m.ENTRY)])
console=Process(2,Path(os.environ['SystemRoot'])/'System32/conhost.exe',['conhost.exe','0x4'])
def identity(p):return dict(pid=p.pid,exe=p.exe(),cmdline=p.cmdline().copy(),creation_filetime_ticks=p.created)
record=dict(root=str(ROOT),entry=str(m.ENTRY),processes=[identity(parent),identity(console)])
saved=[]
with patch.object(m,'identity',identity),patch.object(m,'write',lambda name,value:saved.append(copy.deepcopy(value))),patch.object(m.psutil,'Process',side_effect=lambda pid:{1:parent,2:console}[pid]):
    assert m.verified(record['processes'][0]) is parent
    for key in ('pid','exe','cmdline','creation_filetime_ticks'):
        bad=copy.deepcopy(record['processes'][0]);bad[key]={'pid':2,'exe':'foreign.exe','cmdline':['foreign'],'creation_filetime_ticks':99}[key]
        try:m.verified(bad)
        except RuntimeError:pass
        else:raise AssertionError('Foreign identity accepted')
    console.command=['conhost.exe','0xffffffff','-ForceV1'];m.register_children(parent,record)
    assert len(record['console_startup_transitions'])==1
    assert m.verified(record['processes'][1]) is console
    console.created+=1
    try:m.register_children(parent,record)
    except RuntimeError:pass
    else:raise AssertionError('PID creation change accepted')
    console.created-=1;console.command=['conhost.exe','arbitrary']
    try:m.register_children(parent,record)
    except RuntimeError:pass
    else:raise AssertionError('Arbitrary console command accepted')

turns=load('turns','third_party/LiveTalking/server/audio_turns.py')
class Avatar:
    def __init__(self):self.audio_turns=turns.AudioTurns();self.uploads=[];self.flushes=0
    def put_audio_file(self,data,metadata):self.uploads.append((data,metadata))
    def flush_talk(self):self.flushes+=1
avatars={'a':Avatar(),'b':Avatar()}
class Request:
    def __init__(self,sid='a',turn='t1',payload=b'one'):self.sid=sid;self.turn=turn;self.payload=payload
    async def post(self):
        fields=dict(sessionid=self.sid,file=SimpleNamespace(file=io.BytesIO(self.payload)))
        if self.turn is not None:fields['turn_id']=self.turn
        return fields
    async def json(self):return dict(sessionid=self.sid,turn_id=self.turn)
with patch.dict(sys.modules,{'server.session_manager':SimpleNamespace(session_manager=SimpleNamespace(get_session=lambda sid:avatars.get(sid))),
                             'server.avatar_routes':SimpleNamespace(setup_avatar_routes=lambda _:None),
                             'utils.logger':SimpleNamespace(logger=SimpleNamespace(exception=lambda *a:None))}):
    routes=load('routes_contract','third_party/LiveTalking/server/routes.py')
async def contracts():
    async def call(fn,request):return json.loads((await fn(request)).text)
    first=await call(routes.humanaudio,Request());assert first['code']==0
    duplicate=await call(routes.humanaudio,Request());assert duplicate['data']['duplicate'] and len(avatars['a'].uploads)==1
    assert (await call(routes.humanaudio,Request(payload=b'other')))['code']==-1
    assert (await call(routes.humanaudio,Request(turn='t2')))['code']==-1
    assert (await call(routes.interrupt_talk,Request(turn='stale')))['code']==-1 and not avatars['a'].audio_turns.invalid
    cancelled=await call(routes.interrupt_talk,Request());assert cancelled['data']['reconnect_required']
    assert avatars['a'].flushes==1 and not avatars['b'].audio_turns.invalid
    assert (await call(routes.humanaudio,Request(turn='t2')))['code']==-1
    # Old Stage4 clients omit turn_id and retain code/msg compatibility.
    legacy=await call(routes.humanaudio,Request(sid='b',turn=None));assert legacy['code']==0 and legacy['msg']=='ok'
    assert legacy['data']['turn_id'].startswith('legacy-')
asyncio.run(contracts())
(ROOT/'runtime/stage5/ownership-route-checks.json').write_text(json.dumps(dict(status='PASS',ownership=['full-identity','pid-change','exe-change','command-change','creation-change','exact-console-transition','foreign-console-refused'],routes=['one-enqueue','duplicate-no-enqueue','digest-conflict','busy','stale-cancel','invalidate','other-session-untouched','legacy-two-field-upload']),indent=2),encoding='utf-8')
print('Ownership and route contracts PASS')
