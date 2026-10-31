"""Strict same-run stop-receipt reconciliation. No process termination."""
import importlib.util,json,time,hashlib
from pathlib import Path
import psutil
ROOT=Path(__file__).resolve().parents[1]
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
    manager=load('reconcile_manager','scripts/rebuild-system.py')
    receipt_module=load('reconcile_receipts','scripts/stack-stop-receipts.py')
    owner_path=manager.OWNER;original=owner_path.read_bytes();record=json.loads(original.decode('utf-8'))
    folder=ROOT/'runtime/stack/reconciliations'/f"{record['run_id']}-{time.time_ns()}";folder.mkdir(parents=True,exist_ok=False)
    (folder/'owner.original.json').write_bytes(original)
    if record.get('status') not in ['BLOCKED','STOPPING']:raise RuntimeError('Only blocked/stopping stacks may be reconciled')
    targets={item['service']:item.get('fingerprint') for item in record['started']}
    if record.get('pending'):targets.setdefault(record['pending']['service'],record['pending'].get('fingerprint'))
    proofs={name:receipt_module.prove(ROOT,name,record,expected,manager.process_identity) for name,expected in targets.items()}
    # Corroborate the preserved parent links with the matching archived identities.
    stream=ROOT/f"runtime/stack/resource-streams/{record['run_id']}.jsonl"
    snapshots=[json.loads(line) for line in stream.read_text(encoding='utf-8').splitlines()]
    parents=[]
    for proof in proofs.values():
        items=proof['owner']['processes'];ids={p['pid'] for p in items}
        for item in items:
            matches=[p for s in snapshots for p in s['owned_process_samples'] if p['service']==proof['service'] and p['pid']==item['pid'] and p['exe']==item['exe'] and p['command']==item['cmdline']]
            if not matches:raise RuntimeError('No matching preserved process/parent snapshot')
            parent_ids={p['parent_pid'] for p in matches}
            if len(parent_ids)!=1 or (item!=items[0] and not parent_ids<=ids):raise RuntimeError('Archived descendant parent conflict')
            parents.append(dict(pid=item['pid'],creation_filetime_ticks=item['creation_filetime_ticks'],parent_pid=next(iter(parent_ids)),source='same-run archived owner + exact-exe/argv resource snapshots'))
    ports=[dict(port=c.laddr.port,pid=c.pid) for c in psutil.net_connections('tcp') if c.status=='LISTEN' and c.laddr.port in manager.PORTS.values()]
    active=[str(p) for p in manager.RECORDS.values() if p.exists()]
    if ports or active:raise RuntimeError('Listener/service owner remains')
    coordinators=[]
    for p in psutil.process_iter(['name']):
        if 'python' not in (p.info['name'] or '').lower():continue
        try:
            if str(ROOT/'scripts/rebuild-system.py') in p.cmdline():coordinators.append(manager.process_identity(p))
        except psutil.NoSuchProcess:pass
    if coordinators:raise RuntimeError('Coordinator remains alive')
    unknown_path=ROOT/'runtime/tts-service/unattested-child-exit.json'
    unknown=manager.read(unknown_path) if unknown_path.exists() else None
    # An unproven transient PID never becomes a trusted SoX/process-tree record.
    if unknown and psutil.pid_exists(unknown['pid']):raise RuntimeError('Unattested PID currently exists; cannot correlate it safely')
    proof=dict(status='CORROBORATED_STOPPED',run_id=record['run_id'],time=time.time(),receipts=proofs,parent_links=parents,
               unknown_transient=dict(record=unknown,identity_proven=False,classification='NOT_ADOPTED; original NoSuchProcess preserved; no current PID'),
               ports=ports,active_service_owners=active,coordinators=coordinators,termination_operations=0)
    (folder/'proof.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    archive=manager.RUNTIME/'runs'/f"{record['run_id']}.json"
    if archive.exists() or owner_path.read_bytes()!=original:raise RuntimeError('Stack/archive changed; no overwrite')
    record.update(status='STOPPED',reconciled_at=proof['time'],reconciliation_proof=str(folder/'proof.json'),
                  original_cleanup_errors=record.get('cleanup_errors',[]),cleanup_errors=[])
    record.pop('pending',None)
    for item in record['started']:item['stopped']=True
    temp=folder/'owner.reconciled.json';temp.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    archive.parent.mkdir(exist_ok=True)
    # Preserve the original owner as the archive operation itself; then annotate archive.
    owner_path.rename(archive);temp.replace(archive)
    print(json.dumps(dict(status='STOPPED',archive=str(archive),proof=str(folder/'proof.json'),registered_instances=sum(len(p['exits']) for p in proofs.values()),unknown_identity_proven=False,termination_operations=0)))
if __name__=='__main__':main()
