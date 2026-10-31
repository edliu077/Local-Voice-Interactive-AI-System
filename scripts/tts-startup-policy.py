"""Finite TTS-only startup budgets; progress events never reset the absolute cap."""
TOTAL_SECONDS=600.0
PHASE_LIMITS={'loading':360.0,'prompt':120.0,'warmup':180.0,'health':30.0}
class StartupPolicy:
    def __init__(self,started):
        self.started=started;self.phase='loading';self.phase_started=started;self.seen=[]
    def event(self,data,now):
        name=data.get('event')
        if name in ('initialization_failed','tts_request_gpu_limit_exceeded'):
            raise RuntimeError('TTS initialization failure: '+str(data.get('error',name)))
        for key in ('model_load_count','voice_clone_prompt_create_count'):
            if data.get(key,0)>1:raise RuntimeError('Repeated TTS initialization: '+key)
        if name in self.seen:return
        if name=='model_loaded' and self.phase=='loading':self.phase='prompt';self.phase_started=now
        elif name in ('voice_clone_prompt_created','warmup_started') and self.phase in ('loading','prompt'):
            self.phase='warmup';self.phase_started=now
        elif name in ('warmup_completed','service_ready') and self.phase!='health':
            self.phase='health';self.phase_started=now
        if name in ('model_loaded','voice_clone_prompt_created','warmup_started','warmup_completed','service_ready'):self.seen.append(name)
    def check(self,now):
        if now-self.started>=TOTAL_SECONDS:raise TimeoutError('TTS absolute startup limit exceeded (600 seconds)')
        if now-self.phase_started>=PHASE_LIMITS[self.phase]:
            raise TimeoutError(f'TTS {self.phase} startup phase limit exceeded ({PHASE_LIMITS[self.phase]:g} seconds)')
    def snapshot(self,now):
        return dict(phase=self.phase,elapsed_seconds=now-self.started,phase_elapsed_seconds=now-self.phase_started,
                    total_limit_seconds=TOTAL_SECONDS,phase_limit_seconds=PHASE_LIMITS[self.phase],events=self.seen.copy())
