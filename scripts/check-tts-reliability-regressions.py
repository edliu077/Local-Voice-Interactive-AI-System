"""Run prior strict safety checks without overwriting historical evidence."""
from pathlib import Path
import json,time
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'scripts/check-tts-process-evidence.py'
destination='runtime/tts-reliability-repair/offline/prior-regression-'+str(time.time_ns())
source=path.read_text(encoding='utf-8').replace('runtime/repair-tts-launch-race-20261026/offline',
                                             destination)
exec(compile(source,str(path),'exec'),{'__file__':str(path),'__name__':'tts_reliability_regression'})
result=json.loads((ROOT/destination/'result.json').read_text(encoding='utf-8'))
(ROOT/'runtime/tts-reliability-repair/offline/prior-regression-latest.json').write_text(
    json.dumps(dict(status=result['status'],directory=str(ROOT/destination),models_loaded=0),indent=2),encoding='utf-8')
