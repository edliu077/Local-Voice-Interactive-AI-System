"""Shared configuration for isolated CPU STT/WS launchers."""
from pathlib import Path
import json,os,runpy,sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ['REBUILD_LLM_PROFILE']=json.loads((ROOT/'config/rebuild.json').read_text(encoding='utf-8'))['default_llm_profile']
import rebuild_config
def run(relative):
    os.environ['CYBER_PLAYBACK_MODE']='avatar_webrtc'
    sys.path.insert(0,str((ROOT/relative).parent))
    runpy.run_path(str(ROOT/relative),run_name='__main__')
