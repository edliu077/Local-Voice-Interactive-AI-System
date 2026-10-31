import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import os
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('frontend_owner',ROOT/'scripts/livetalking-service.py')
manager=importlib.util.module_from_spec(s);s.loader.exec_module(manager)
manager.REPO=ROOT;manager.RUNTIME=ROOT/'runtime/frontend-service';manager.OWNER=manager.RUNTIME/'owner.json'
manager.ENTRY=ROOT/'scripts/frontend-run.py';manager.PORT=3000
manager.REQUIRED_INPUTS=(ROOT/'frontend/node_modules/next/dist/bin/next',ROOT/'frontend/package-lock.json')
if os.environ.get('REBUILD_FRONTEND_MODE','production')=='production':manager.REQUIRED_INPUTS+= (ROOT/'frontend/.next/BUILD_ID',)
manager.MINIMUM_RAM_BYTES=1024**3;manager.MINIMUM_GPU_FREE_MIB=0
manager.HEALTH_PATH='/';manager.HEALTH_STATUS=None;manager.SERVICE_NAME='Rebuild Next.js'
node=shutil.which('node.exe')
if not node:raise RuntimeError('Existing Node.js missing')
manager.ALLOWED_AUXILIARY={str(Path(node).resolve()).lower():{
    (str(ROOT/'frontend/node_modules/next/dist/bin/next'),'start','--hostname','127.0.0.1','--port','3000'),
    (str(ROOT/'frontend/node_modules/next/dist/bin/next'),'dev','--hostname','127.0.0.1','--port','3000','--webpack'),
    (str(ROOT/'frontend/node_modules/next/dist/server/lib/start-server.js'),),
    (str(ROOT/'frontend/node_modules/next/dist/compiled/jest-worker/processChild.js'),),
}}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['preflight','start','status','stop']);a=p.parse_args().action
    if a=='preflight':print(json.dumps(manager.preflight(),indent=2))
    elif a=='start':manager.start()
    elif a=='stop':manager.stop()
    elif manager.OWNER.exists():manager.assert_listener();print('Owned Next.js running')
    else:print('No owned Next.js service')
