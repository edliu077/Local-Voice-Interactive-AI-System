from pathlib import Path
import sys
import runpy
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import rebuild_config
sys.path.insert(0,str(ROOT/'experiments/avatar-bridge'))
if __name__=='__main__':runpy.run_path(str(ROOT/'experiments/avatar-bridge/control_service.py'),run_name='__main__')
