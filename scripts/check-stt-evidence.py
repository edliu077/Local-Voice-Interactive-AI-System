"""No models/microphone: synthetic WAV and actual evidence module/WS contracts."""
import ast
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import runpy
import sys
from unittest.mock import patch
from uuid import uuid4
import wave

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'runtime/stt-evidence-patch-checks' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-') + uuid4().hex[:12])
OUT.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, str(ROOT / 'experiments/websocket-i0/server'))
from stt_evidence import SttEvidence, digest

checks = []


def fixture(label):
    root = OUT / label
    path = root / 'runtime/input/i0-vad-utterance.wav'
    path.parent.mkdir(parents=True)
    write_wav(path)
    return root, path


def write_wav(path):
    with wave.open(str(path), 'wb') as audio:
        audio.setnchannels(1); audio.setsampwidth(2); audio.setframerate(16000)
        audio.writeframes(b'\x10\x00' * 1600)


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def records(recorder, name):
    return list(recorder.directory.glob('*/' + name))


def contracts():
    root, source = fixture('disabled')
    for value in (None, '0', 'true', 'yes'):
        with patch.dict(os.environ, {}, clear=False):
            if value is None:os.environ.pop('CYBER_STT_EVIDENCE', None)
            else:os.environ['CYBER_STT_EVIDENCE'] = value
            with patch('pathlib.Path.resolve', side_effect=AssertionError('Disabled evidence touched filesystem')):
                assert SttEvidence.from_environment(root) is None
    assert not (root / 'runtime/stt-evidence').exists()
    checks.append('default off / only exact 1 enables; no evidence filesystem access when off')

    root, source = fixture('linked-three')
    with patch.dict(os.environ, {'CYBER_STT_EVIDENCE':'1'}):rec = SttEvidence.from_environment(root)
    before = source.read_bytes()
    response = dict(text='  測試短句  ', segments=[dict(start=0.0,end=.1,text='測試短句')], extra_actual_field={'value':7})
    for turn in range(1, 4):
        ticket = rec.begin(f'session-{turn}', turn, source, lambda:False)
        assert ticket and not ticket.failed
        assert source.read_bytes() == before
        meta = read(ticket.directory / 'input.json')
        assert meta['ws_session_id'] == f'session-{turn}' and meta['turn_id'] == turn
        assert meta['wav']['sample_frames'] == 1600 and meta['wav']['duration_seconds'] == .1
        assert meta['source_sha256'] == meta['copy_sha256'] == digest(source)
        rec.response(ticket, response, lambda:False)
        assert read(ticket.directory/'stt-response.json')['response'] == response
        rec.finish(ticket, '测试短句', lambda:False)
        marker = read(ticket.directory/'complete.json')
        assert marker['status'] == 'STT_EVIDENCE_COMPLETE'
        for name, checksum in marker['sha256'].items():assert digest(ticket.directory/name) == checksum
    assert rec.begin('new-session', 4, source, lambda:False) is None
    assert rec.begin('another-session', 5, source, lambda:False) is None
    assert len(records(rec, 'input.wav')) == len(records(rec, 'complete.json')) == 3
    assert 'audio_duration_seconds' not in read(records(rec, 'stt-response.json')[0])['response']
    checks.append('same input SHA/WAV metadata/session/turn/raw dict/normalized text; 3 attempts shared across sessions; no invented response fields')

    # A pre-existing record cannot be replaced even by atomic publication.
    sentinel = records(rec, 'input.json')[0]; old = sentinel.read_bytes()
    try:rec._json(sentinel, {'replacement':True})
    except FileExistsError:pass
    else:raise AssertionError('Exclusive evidence write overwrote a record')
    assert sentinel.read_bytes() == old
    checks.append('exclusive JSON/WAV directory creation; existing evidence remains unchanged')

    root, source = fixture('missing')
    rec = SttEvidence(root); source.unlink()
    for n in range(4):rec.begin('missing-session', n+1, source, lambda:False)
    assert rec.attempts == 3 and not records(rec, 'complete.json')
    checks.append('missing input reports incomplete; failed attempts consume budget')

    root, source = fixture('response-write-failure');rec=SttEvidence(root)
    ticket=rec.begin('write-failure',1,source,lambda:False)
    actual=rec._json
    def fail_response(path, value):
        if path.name == 'stt-response.json':raise PermissionError('synthetic failure')
        return actual(path,value)
    with patch.object(rec, '_json', side_effect=fail_response):
        rec.response(ticket,response,lambda:False)
        rec.finish(ticket,'测试短句',lambda:False)
    assert read(ticket.directory/'incomplete.json')['status']=='INCOMPLETE'
    assert not records(rec,'complete.json')
    checks.append('write failure is visibly incomplete; no success marker')

    root, source=fixture('source-changed');rec=SttEvidence(root)
    ticket=rec.begin('changed',1,source,lambda:False)
    source.write_bytes(b'changed between actual request boundaries')
    rec.response(ticket,response,lambda:False);rec.finish(ticket,'测试短句',lambda:False)
    assert not records(rec,'complete.json') and ticket.failed
    checks.append('changed input during STT cannot claim matching response')

    for phase in ('before-input','after-input','after-response'):
        root,source=fixture('cancel-'+phase);rec=SttEvidence(root)
        if phase=='before-input':
            assert rec.begin('cancelled',1,source,lambda:True) is None
        else:
            ticket=rec.begin('cancelled',1,source,lambda:False)
            rec.response(ticket,response,lambda:phase=='after-input')
            rec.finish(ticket,'测试短句',lambda:True)
        assert not records(rec,'complete.json')
    checks.append('cancellation before copy/after request/before completion never produces success')

    root,source=fixture('unserializable-response');rec=SttEvidence(root)
    ticket=rec.begin('bad-response',1,source,lambda:False)
    rec.response(ticket,dict(text='测试',not_json=object()),lambda:False)
    rec.finish(ticket,'测试',lambda:False)
    assert not records(rec,'complete.json')
    root,source=fixture('stt-exception');rec=SttEvidence(root)
    ticket=rec.begin('stt-exception',1,source,lambda:False)
    rec.fail(ticket,'stt_request_failed',RuntimeError('synthetic'))
    assert not records(rec,'complete.json')
    checks.append('STT exception/non-JSON response do not fabricate evidence')

    root,source=fixture('publish-failure');rec=SttEvidence(root)
    ticket=rec.begin('publish-failure',1,source,lambda:False)
    rec.response(ticket,response,lambda:False)
    real_link=os.link
    def fail_commit(src,dst):
        if Path(dst).name=='complete.json':raise OSError('synthetic commit failure')
        return real_link(src,dst)
    with patch('stt_evidence.os.link',side_effect=fail_commit):rec.finish(ticket,'测试',lambda:False)
    assert not records(rec,'complete.json') and records(rec,'incomplete.json')
    checks.append('atomic commit failure leaves pending/incomplete, not valid complete marker')


def unchanged_business_ast():
    original=ROOT/'archives/v1.0-rc1-20261028T103241Z/snapshot/experiments/websocket-i0/server/voice_ws_server.py'
    modified=ROOT/'experiments/websocket-i0/server/voice_ws_server.py'
    class RemoveDiagnostic(ast.NodeTransformer):
        def visit_ImportFrom(self,node):return None if node.module=='stt_evidence' else node
        def visit_Assign(self,node):
            if any(isinstance(t,ast.Name) and t.id in ('evidence','ticket') for t in node.targets):return None
            if any(isinstance(t,ast.Attribute) and t.attr=='stt_evidence' for t in node.targets):return None
            return self.generic_visit(node)
        def visit_If(self,node):
            if any(isinstance(n,ast.Name) and n.id=='evidence' for n in ast.walk(node.test)):return None
            return self.generic_visit(node)
        def visit_Try(self,node):
            stt_try=(isinstance(node.body[0],ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('stt','raw_transcript') for t in node.body[0].targets))
            if stt_try:
                result=[]
                for item in node.body:
                    value=self.visit(item)
                    if value is not None:result.extend(value if isinstance(value,list) else [value])
                return result
            return self.generic_visit(node)
    clean=RemoveDiagnostic().visit(ast.parse(modified.read_text(encoding='utf-8')))
    assert ast.dump(clean,include_attributes=False)==ast.dump(ast.parse(original.read_text(encoding='utf-8')),include_attributes=False)
    checks.append('removing diagnostic-only hooks restores bytecode AST of frozen business source')


def existing_ws_contracts():
    # Execute the existing actual eight-turn mock workflow with output redirected;
    # preserve its historical result files and ensure diagnostic OFF touches no WAV.
    source=(ROOT/'scripts/check-productization-conversation.py').read_text(encoding='utf-8')
    source=source.replace("OUT = ROOT / 'runtime/pre-freeze-productization'", 'OUT = Path('+repr(str(OUT/'existing-ws-regression'))+')')
    namespace={'__file__':str(ROOT/'scripts/check-productization-conversation.py'),'__name__':'__main__'}
    with patch.dict(os.environ,{'CYBER_STT_EVIDENCE':'0'}):exec(compile(source,'<existing WS contracts>','exec'),namespace)
    checks.append('actual WS model-free eight-turn/bounded-context/stop contracts PASS with evidence OFF')

    # Enabled integration: real WS hook placement, but all speech/model functions
    # remain mocked and INPUT_WAV is a synthetic file in a fresh test workspace.
    root, wav = fixture('ws-enabled')
    enabled = (ROOT/'scripts/check-productization-conversation.py').read_text(encoding='utf-8')
    enabled = enabled.replace("OUT = ROOT / 'runtime/pre-freeze-productization'", 'OUT = Path('+repr(str(OUT/'enabled-ws-regression'))+')')
    enabled = enabled.replace("bridge = ws.VoiceBridge('avatar_webrtc')", "bridge = ws.VoiceBridge('avatar_webrtc')\n        ws.INPUT_WAV = Path("+repr(str(wav))+')\n        bridge.stt_evidence = __import__("stt_evidence").SttEvidence(Path('+repr(str(root))+'))')
    with patch.dict(os.environ,{'CYBER_STT_EVIDENCE':'1'}):
        exec(compile(enabled,'<enabled WS contracts>','exec'),dict(__file__=str(ROOT/'scripts/check-productization-conversation.py'),__name__='__main__'))
    folders=list((root/'runtime/stt-evidence').glob('*/*'))
    assert len(folders)==3
    for index,folder in enumerate(sorted(folders),1):
        original=read(folder/'stt-response.json')
        final=read(folder/'normalized.json')
        assert original['turn_id']==final['turn_id']==index
        assert original['response']['text']==final['opencc_text']
        assert (folder/'complete.json').exists()
    checks.append('actual enabled WS hooks pair same-call response/normalized text with exactly first 3 synthetic inputs across 8 mocked turns')


if __name__=='__main__':
    contracts();unchanged_business_ast();existing_ws_contracts()
    (OUT/'result.json').write_text(json.dumps(dict(status='PASS',checks=checks,real_models=0,real_microphone_captures=0),indent=2),encoding='utf-8')
    print('STT evidence offline contracts PASS: '+str(OUT/'result.json'))
