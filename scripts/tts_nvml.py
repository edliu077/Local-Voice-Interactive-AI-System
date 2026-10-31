"""Whole-device NVML telemetry via the installed System32 driver DLL only."""
import ctypes as c
import os
from pathlib import Path
import threading


class Memory(c.Structure):
    _fields_=[('total',c.c_ulonglong),('free',c.c_ulonglong),('used',c.c_ulonglong)]


class MemoryV2(c.Structure):
    _fields_=[('version',c.c_uint),('total',c.c_ulonglong),('reserved',c.c_ulonglong),('free',c.c_ulonglong),('used',c.c_ulonglong)]


class NVML:
    def __init__(self, uuid):
        if not isinstance(uuid,str) or not uuid.startswith('GPU-') or len(uuid)>96:
            raise RuntimeError('Invalid physical GPU UUID')
        self.uuid=uuid;self.lock=threading.Lock()
        path=Path(os.environ['SystemRoot'])/'System32/nvml.dll'
        self.dll=c.WinDLL(str(path.resolve()))
        self.dll.nvmlInit_v2.restype=c.c_int
        self.dll.nvmlDeviceGetHandleByUUID.argtypes=[c.c_char_p,c.POINTER(c.c_void_p)]
        self.dll.nvmlDeviceGetUUID.argtypes=[c.c_void_p,c.c_char_p,c.c_uint]
        self.dll.nvmlDeviceGetMemoryInfo_v2.argtypes=[c.c_void_p,c.POINTER(MemoryV2)]
        self.check(self.dll.nvmlInit_v2())
        self.device=c.c_void_p()
        self.check(self.dll.nvmlDeviceGetHandleByUUID(uuid.encode('ascii'),c.byref(self.device)))
        actual=c.create_string_buffer(96)
        self.check(self.dll.nvmlDeviceGetUUID(self.device,actual,len(actual)))
        if actual.value.decode()!=uuid:raise RuntimeError('NVML GPU UUID mismatch')

    @staticmethod
    def check(code):
        if code!=0:raise RuntimeError(f'NVML query failed: code {code}')

    def memory(self):
        with self.lock:
            value=MemoryV2();value.version=c.sizeof(value)|(2<<24)
            self.check(self.dll.nvmlDeviceGetMemoryInfo_v2(self.device,c.byref(value)))
            if value.total<=0 or value.used>value.total or value.free>value.total:
                raise RuntimeError('NVML returned invalid whole-device memory')
            return dict(uuid=self.uuid,total_bytes=value.total,used_bytes=value.used,free_bytes=value.free,
                        reserved_bytes=value.reserved,
                        used_mib=(value.used+1024**2-1)//(1024**2),backend='nvmlDeviceGetMemoryInfo_v2')
