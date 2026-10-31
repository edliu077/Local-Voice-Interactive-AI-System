"""Independent one-service profile entry; keeps the seven-service default unchanged."""
import argparse,importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    default=json.loads((ROOT/'config/rebuild.json').read_text(encoding='utf-8'))['default_llm_profile']
    p=argparse.ArgumentParser();p.add_argument('action',choices=['preflight','start','status','stop']);p.add_argument('--profile',choices=['1.7b','4b','4b-hybrid'],default=default);a=p.parse_args()
    if a.action in ('start','preflight') and a.profile!=default:
        p.error('This profile is archived. Only the configured 1.7B default may start.')
    spec=importlib.util.spec_from_file_location('isolated_coordinator',ROOT/'scripts/rebuild-system.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    m.ORDER=['llm'];m.RECORDS={'llm':ROOT/f'runtime/services-live/llm-{a.profile}/owner.json'}
    m.RUNTIME=ROOT/f'runtime/isolated-llm/{a.profile}';m.OWNER=m.RUNTIME/'owner.json'
    stack=m.Stack(call=lambda name,action:m.invoke(name,action,stack.run_id,profile=a.profile))
    if a.action=='preflight':
        stack.clean_start();print(json.dumps(dict(preflight=stack.preflight_one('llm'),system=m.resources()),indent=2))
    elif a.action=='start':stack.start()
    elif a.action=='stop':stack.stop()
    else:print(stack.call('llm','status'))
if __name__=='__main__':main()
