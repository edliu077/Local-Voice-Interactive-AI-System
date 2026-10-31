"""Fixed local Next.js development command; no npm shell or legacy modules."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]
NODE=shutil.which('node.exe')
if not NODE:raise RuntimeError('Existing Node.js executable missing')
os.environ.pop('NODE_PATH',None)
os.environ['NODE_OPTIONS']='--max-old-space-size=1024'
os.environ['NEXT_TELEMETRY_DISABLED']='1'
os.environ['NEXT_DISABLE_MEM_OVERRIDE']='1'
os.environ['TEMP']=str(ROOT/'runtime/tmp');os.environ['TMP']=os.environ['TEMP']
if __name__=='__main__':
    mode=os.environ.get('REBUILD_FRONTEND_MODE','production')
    if mode not in ('production','development'):raise ValueError('Invalid frontend mode')
    args=['dev','--hostname','127.0.0.1','--port','3000','--webpack'] if mode=='development' else ['start','--hostname','127.0.0.1','--port','3000']
    sys.exit(subprocess.call([NODE,str(ROOT/'frontend/node_modules/next/dist/bin/next'),*args],cwd=ROOT/'frontend'))
