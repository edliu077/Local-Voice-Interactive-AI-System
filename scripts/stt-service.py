import importlib.util
from pathlib import Path
s=importlib.util.spec_from_file_location('cpu_manager',Path(__file__).with_name('cpu-service.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
manager=m.make('stt')
if __name__=='__main__':m.cli(manager)
