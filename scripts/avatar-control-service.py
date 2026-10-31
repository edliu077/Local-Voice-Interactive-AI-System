import argparse
import importlib.util
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('control_owner',ROOT/'scripts/livetalking-service.py')
manager=importlib.util.module_from_spec(s);s.loader.exec_module(manager)
manager.REPO=ROOT;manager.RUNTIME=ROOT/'runtime/avatar-control-service';manager.OWNER=manager.RUNTIME/'owner.json'
manager.ENTRY=ROOT/'scripts/avatar-control-run.py';manager.PORT=8011
manager.REQUIRED_INPUTS=(ROOT/'experiments/avatar-bridge/control_service.py',)
manager.MINIMUM_RAM_BYTES=512*1024**2;manager.MINIMUM_GPU_FREE_MIB=0
manager.HEALTH_PATH='/health';manager.HEALTH_STATUS='ok';manager.SERVICE_NAME='Avatar control'
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['preflight','start','status','stop']);a=p.parse_args().action
    if a=='preflight':print(json.dumps(manager.preflight(),indent=2))
    elif a=='start':manager.start()
    elif a=='stop':manager.stop()
    elif manager.OWNER.exists():manager.assert_listener();print('Owned avatar control running')
    else:print('No owned avatar control')
