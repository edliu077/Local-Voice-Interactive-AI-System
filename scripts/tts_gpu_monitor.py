"""One whole-GPU telemetry backend per TTS process, chosen before model import."""
import atexit,json,os,threading,time,uuid
from tts_nvml import NVML
from tts_helper_client import launch


class GPUMonitor:
    def __init__(self):
        self.lock=threading.Condition();self.process=None;self.error=None;self.last=None;self.last_at=0
        self.uuid=os.environ['REBUILD_TTS_GPU_UUID'];self.nvml=None;self.closed=False
        if os.environ.get('REBUILD_TTS_GPU_BACKEND')=='nvml':
            try:self.nvml=NVML(self.uuid);self.nvml.memory()
            except Exception as exc:
                self.nvml=None
                print(json.dumps(dict(event='nvml_unavailable_using_registered_helper',error=repr(exc))),flush=True)
        if self.nvml is None:self._start_loop()
        self.used_mib()
        print(json.dumps(dict(event='gpu_telemetry_ready',uuid=self.uuid,backend='nvml-v2' if self.nvml else 'registered-smi-loop',sample_period_seconds=.2)),flush=True)
        atexit.register(self.close)

    def _start_loop(self):
        self.process=launch('loop')
        self.stderr_tail=''
        def read_errors():
            for line in self.process.stderr:
                self.stderr_tail=(self.stderr_tail+line)[-4096:]
        threading.Thread(target=read_errors,daemon=True,name='tts-gpu-query-stderr').start()
        def read():
            try:
                for line in self.process.stdout:
                    value=line.strip()
                    if not value.isdecimal():raise RuntimeError('nvidia-smi emitted invalid memory sample')
                    with self.lock:self.last=int(value);self.last_at=time.monotonic();self.lock.notify_all()
                if not self.closed:raise RuntimeError('nvidia-smi telemetry stream ended: '+self.stderr_tail)
            except BaseException as exc:
                with self.lock:self.error=repr(exc);self.lock.notify_all()
        threading.Thread(target=read,daemon=True,name='tts-registered-gpu-query').start()

    def _one_shot(self):
        # Same protocol for required future/calibration short calls and offline
        # contracts; normal production NVML sampling does not invoke this.
        process=launch('query')
        stdout,stderr=process.communicate(timeout=10)
        if process.returncode or not stdout.strip().isdecimal():raise RuntimeError('Registered GPU query failed')
        return int(stdout.strip())

    def used_mib(self):
        if self.error:raise RuntimeError('GPU protection telemetry previously failed: '+self.error)
        if self.nvml is not None:
            try:return self.nvml.memory()['used_mib']
            except Exception as exc:
                self.error=repr(exc)
                raise RuntimeError('GPU protection telemetry failed') from exc
        deadline=time.monotonic()+10
        with self.lock:
            while self.last is None and not self.error:
                left=deadline-time.monotonic()
                if left<=0:raise RuntimeError('GPU protection first-sample deadline exceeded')
                self.lock.wait(left)
            if self.error or time.monotonic()-self.last_at>2 or self.process.poll() is not None:
                raise RuntimeError('GPU protection telemetry unavailable/stale: '+str(self.error))
            return self.last

    def close(self):
        self.closed=True
        if self.process is not None and self.process.poll() is None:
            self.process.terminate();self.process.wait(timeout=10)


monitor=None
def validate_cuda_uuid(actual,count,expected):
    if actual is None:
        if count!=1:raise RuntimeError('Cannot prove CUDA/NVML mapping on multiple physical GPUs')
        return
    try:
        raw=getattr(actual,'bytes',None)
        normalized=uuid.UUID(bytes=bytes(raw)) if raw is not None else uuid.UUID(str(actual).removeprefix('GPU-'))
        target=uuid.UUID(expected.removeprefix('GPU-'))
    except (ValueError,TypeError,AttributeError) as exc:raise RuntimeError('Unrecognized CUDA GPU UUID') from exc
    if normalized!=target:raise RuntimeError('CUDA/NVML physical GPU UUID mismatch')

def initialize():
    global monitor
    if monitor is None:monitor=GPUMonitor()
    return monitor
def used_mib():return initialize().used_mib()
