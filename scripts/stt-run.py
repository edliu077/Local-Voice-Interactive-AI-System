from importlib.util import spec_from_file_location,module_from_spec
from pathlib import Path
s=spec_from_file_location('cpu_launch',Path(__file__).with_name('cpu-run.py'));m=module_from_spec(s);s.loader.exec_module(m)
if __name__=='__main__':m.run('experiments/persistent-stt-h1/service/stt_service.py')
