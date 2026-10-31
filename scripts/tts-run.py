"""Existing cloned service and unchanged model/voice parameters; Rebuild only."""
from pathlib import Path
import sys
import importlib.util
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import rebuild_config
import uvicorn
if __name__=='__main__':
    spec=importlib.util.spec_from_file_location('tts_creation_evidence',ROOT/'scripts/tts-process-evidence.py')
    evidence=importlib.util.module_from_spec(spec);spec.loader.exec_module(evidence)
    restore_evidence=evidence.install(ROOT)
    spec=importlib.util.spec_from_file_location('optional_sox_probe',ROOT/'scripts/tts-sox-probe.py')
    probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
    restore=probe.install(ROOT)
    import tts_helper_client
    restore_guard=tts_helper_client.install(ROOT)
    import tts_gpu_monitor
    try:
        tts_gpu_monitor.initialize()
        uvicorn.run('experiments.qwen3-tts-e0.service.tts_service:app',host='127.0.0.1',port=8765,access_log=False)
    finally:
        if tts_gpu_monitor.monitor is not None:tts_gpu_monitor.monitor.close()
        restore_guard()
        restore()
        restore_evidence()
