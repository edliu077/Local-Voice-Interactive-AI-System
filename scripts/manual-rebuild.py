"""Console + durable full top-level log for Explorer double-click startup."""
import argparse,datetime,json,os,subprocess,sys,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(command,folder):
    folder.mkdir(parents=True,exist_ok=False)
    print('Persistent startup log directory: '+str(folder),flush=True)
    files={name:(folder/(name+'.log')).open('wb') for name in ['stdout','stderr']}
    status=dict(command=command,status='STARTING')
    (folder/'result.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
    done=threading.Event()
    def copy(name):
        target=getattr(sys,name)
        with (folder/(name+'.log')).open('rb') as source:
            while True:
                line=source.readline()
                if line:target.write(line.decode('utf-8-sig',errors='replace'));target.flush()
                elif done.is_set():return
                else:done.wait(.1)
    try:
        env=os.environ.copy();env.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1')
        # File-backed handles avoid waiting for EOF inherited by another process.
        process=subprocess.Popen(command,cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=files['stdout'],stderr=files['stderr'],close_fds=True)
        status.update(pid=process.pid)
        (folder/'result.json').write_text(json.dumps(status,indent=2),encoding='utf-8')
        threads=[threading.Thread(target=copy,args=(name,),daemon=True) for name in ['stdout','stderr']]
        for thread in threads:thread.start()
        code=process.wait()
        done.set()
        for thread in threads:thread.join()
        status.update(status='EXITED',returncode=code)
        return code
    except BaseException as error:
        status.update(status='LOGGER_ERROR',error=repr(error));raise
    finally:
        done.set()
        for file in files.values():file.close()
        (folder/'result.json').write_text(json.dumps(status,indent=2),encoding='utf-8')

if __name__=='__main__':
    argparse.ArgumentParser().parse_args()
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
    sys.exit(run([sys.executable,'-B','-s',str(ROOT/'scripts/rebuild-system.py'),'start'],ROOT/'runtime/manual-start'/stamp))
