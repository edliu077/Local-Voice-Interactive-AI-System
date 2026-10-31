"""Corroborate a Python service's already completed stop; never kill/adopt."""
import hashlib,json,time
from pathlib import Path
import psutil

def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def fingerprint(record):return dict(root=record['root'],entry=record['entry'],process=record['processes'][0])

def prove(root,name,stack,expected=None,native_identity=None):
    if name not in ['frontend','avatar-control','tts','livetalking','stt','ws']:
        raise RuntimeError('No supported Python stop receipt for this service')
    folder=root/('runtime/livetalking' if name=='livetalking' else f'runtime/{name}-service')
    if (folder/'owner.json').exists():raise RuntimeError('Active service owner still exists')
    receipt_path=folder/'stop-result.json';receipt=read(receipt_path)
    archive_path=Path(receipt['owner_archive']).resolve()
    if not archive_path.is_relative_to(folder.resolve()) or not archive_path.name.startswith('stopped-'):
        raise RuntimeError('Stop receipt archive escaped service directory')
    owner=read(archive_path)
    if (receipt['status']!='STOPPED' or owner.get('StackRunId')!=stack['run_id']
        or owner.get('root')!=str(root) or owner.get('entry')!=str(root/f'scripts/{name}-run.py')
        or not stack['before']['time']<=receipt['time']<=time.time()):
        raise RuntimeError('Stop receipt run/root/entry/time conflict')
    if expected is not None and fingerprint(owner)!=expected:raise RuntimeError('Archived root fingerprint changed')
    identities=owner['processes']
    if not identities or receipt['process_ids']!=[p['pid'] for p in identities] or len(set(receipt['process_ids']))!=len(identities):
        raise RuntimeError('Stop receipt identity set conflict')
    exits=[]
    for item in identities:
        if (not isinstance(item.get('pid'),int) or not isinstance(item.get('creation_filetime_ticks'),int)
            or item['creation_filetime_ticks']<=0 or not Path(item.get('exe','')).is_absolute()
            or not isinstance(item.get('cmdline'),list) or not item['cmdline']):
            raise RuntimeError('Incomplete native identity in archived owner')
        try:
            process=psutil.Process(item['pid'])
            current=native_identity(process)
            if current['creation_filetime_ticks']==item['creation_filetime_ticks']:
                raise RuntimeError('Recorded instance still alive; no reconciliation')
            exits.append(dict(expected=item,state='ORIGINAL_EXIT_CORROBORATED_PID_REUSED_UNTOUCHED',
                              current=dict(pid=current['pid'],exe=current['exe'],creation_filetime_ticks=current['creation_filetime_ticks'])))
        except psutil.NoSuchProcess:exits.append(dict(expected=item,state='EXIT_CORROBORATED_BY_SAME_RUN_STOP_RECEIPT'))
    for pid,parent in owner.get('console_parents',{}).items():
        if int(pid) not in receipt['process_ids'] or parent not in identities:
            raise RuntimeError('Console parent baseline not present in archived process set')
    transient=folder/'unattested-child-exit.json'
    if transient.exists():
        event=read(transient)
        same_run=(event.get('StackRunId')==stack['run_id'] or
                  ('StackRunId' not in event and stack['before']['time']<=transient.stat().st_mtime<=receipt['time']))
        if same_run and psutil.pid_exists(event['pid']):raise RuntimeError('Unattested same-run PID remains; refuse stop receipt reconciliation')
    return dict(service=name,receipt_path=str(receipt_path),receipt=receipt,archive_path=str(archive_path),
                archive_sha256=hashlib.sha256(archive_path.read_bytes()).hexdigest(),owner=owner,exits=exits)
