"""Windows resource evidence and Stage 7H gates; never starts/stops a service."""
import argparse
import ctypes
from ctypes import wintypes as w
import json
from pathlib import Path
import time
import psutil

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT/'config/resource-policy.json').read_text(encoding='utf-8'))


class Performance(ctypes.Structure):
    _fields_ = [('cb', w.DWORD)] + [(n, ctypes.c_size_t) for n in
        ['CommitTotal','CommitLimit','CommitPeak','PhysicalTotal','PhysicalAvailable',
         'SystemCache','KernelTotal','KernelPaged','KernelNonpaged','PageSize']] + [
        ('HandleCount',w.DWORD),('ProcessCount',w.DWORD),('ThreadCount',w.DWORD)]


class Paging:
    """English PDH counters work independently of Windows display language."""
    def __init__(self):
        self.dll = ctypes.WinDLL('pdh')
        self.query = ctypes.c_void_p()
        self.dll.PdhOpenQueryW.argtypes=[w.LPCWSTR,ctypes.c_size_t,ctypes.POINTER(ctypes.c_void_p)]
        self.dll.PdhAddEnglishCounterW.argtypes=[ctypes.c_void_p,w.LPCWSTR,ctypes.c_size_t,ctypes.POINTER(ctypes.c_void_p)]
        self.dll.PdhCollectQueryData.argtypes=[ctypes.c_void_p]
        self.dll.PdhGetFormattedCounterValue.argtypes=[ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD),ctypes.c_void_p]
        if self.dll.PdhOpenQueryW(None,0,ctypes.byref(self.query)):raise RuntimeError('PDH open failed')
        self.counters={}
        for name,path in [('pages_input_per_second',r'\Memory\Pages Input/sec'),
                          ('pages_output_per_second',r'\Memory\Pages Output/sec')]:
            counter=ctypes.c_void_p()
            if self.dll.PdhAddEnglishCounterW(self.query,path,0,ctypes.byref(counter)):
                raise RuntimeError('PDH counter unavailable: '+path)
            self.counters[name]=counter
        if self.dll.PdhCollectQueryData(self.query):raise RuntimeError('PDH initial sample failed')
        self.began=time.monotonic()

    def sample(self):
        class Value(ctypes.Structure):
            _fields_=[('status',w.DWORD),('value',ctypes.c_double)]
        if self.dll.PdhCollectQueryData(self.query):raise RuntimeError('PDH collection failed')
        result={}
        for name,counter in self.counters.items():
            value=Value()
            status=self.dll.PdhGetFormattedCounterValue(counter,0x200,None,ctypes.byref(value))
            if status or value.status not in (0,1):raise RuntimeError('PDH value invalid: '+name)
            result[name]=value.value
        return result


_paging=None


def snapshot():
    global _paging
    info=Performance();info.cb=ctypes.sizeof(info)
    dll=ctypes.WinDLL('psapi',use_last_error=True)
    dll.GetPerformanceInfo.argtypes=[ctypes.POINTER(Performance),w.DWORD]
    if not dll.GetPerformanceInfo(ctypes.byref(info),info.cb):raise ctypes.WinError(ctypes.get_last_error())
    first=_paging is None
    if first:_paging=Paging()
    # A first rate sample has no interval. Explicitly mark it unavailable, never zero.
    paging=dict(pages_input_per_second=None,pages_output_per_second=None) if first else _paging.sample()
    return dict(time=time.time(),available_ram_bytes=psutil.virtual_memory().available,
                committed_bytes=info.CommitTotal*info.PageSize,
                commit_limit_bytes=info.CommitLimit*info.PageSize,
                commit_headroom_bytes=(info.CommitLimit-info.CommitTotal)*info.PageSize,
                system_commit_peak_bytes=info.CommitPeak*info.PageSize,page_size_bytes=info.PageSize,**paging)


def violations(sample,service=None,minimum=None,gpu_minimum=0):
    floor=(POLICY['startup_ram_bytes'][service] if service else POLICY['resident_minimum_bytes']) if minimum is None else minimum
    errors=[]
    if sample['available_ram_bytes']<floor:errors.append('available RAM below '+str(floor))
    if sample['commit_headroom_bytes']<floor:errors.append('commit headroom below '+str(floor))
    if gpu_minimum and sample['gpu_free_mib']<gpu_minimum:errors.append('GPU free below '+str(gpu_minimum))
    return errors


class Pressure:
    def __init__(self):self.since=None
    def check(self,sample):
        errors=violations(sample)
        output=sample.get('pages_output_per_second')
        pressure=(sample['available_ram_bytes']<POLICY['resident_target_bytes'] and output is not None
                  and output*sample['page_size_bytes']>=POLICY['paging_output_bytes_per_second'])
        now=sample['time']
        if pressure:
            if self.since is None:self.since=now
            if now-self.since>=POLICY['paging_pressure_seconds']:errors.append('sustained page-out pressure with low RAM')
        else:self.since=None
        if errors:raise RuntimeError('Resource safety rejection: '+'; '.join(errors))
        return 'WARNING_BELOW_TARGET' if sample['available_ram_bytes']<POLICY['resident_target_bytes'] else 'SAFE'


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--service',required=True);args=parser.parse_args()
    result=snapshot();result['minimum_ram_bytes']=POLICY['startup_ram_bytes'][args.service]
    result['resource_errors']=violations(result,args.service)
    print(json.dumps(result))
