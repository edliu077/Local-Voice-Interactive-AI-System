"""Trusted WS-side submission of an already generated WAV; never synthesizes."""
import importlib.util
import json
from pathlib import Path
import urllib.request

ROOT=Path(__file__).resolve().parents[2]


def control_request(action,data):
    if action not in ('bind','audio','cancel'):raise ValueError('Unsupported control action')
    spec=importlib.util.spec_from_file_location('production_control_owner',ROOT/'scripts/avatar-control-service.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.manager.assert_listener()
    secret=(ROOT/'runtime/avatar-control/internal-secret.txt').read_text(encoding='utf-8')
    request=urllib.request.Request('http://127.0.0.1:8011/internal/'+action,data=json.dumps(data).encode(),
                                   headers={'Content-Type':'application/json','X-Rebuild-Control':secret},method='POST')
    with urllib.request.urlopen(request,timeout=90) as response:result=json.load(response)
    if result.get('code')!=0:raise RuntimeError('Owned avatar control rejected the operation')
    return result
