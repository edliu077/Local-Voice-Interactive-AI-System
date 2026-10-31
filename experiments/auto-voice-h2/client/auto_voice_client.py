"""H2 strict half-duplex automatic conversation with synchronous Windows playback."""
from __future__ import annotations

# Rebuild paths must be configured before third-party imports.
import sys as _rebuild_sys
from pathlib import Path as _RebuildPath
_rebuild_sys.path.insert(0, str(_RebuildPath(__file__).resolve().parents[3]))
from rebuild_config import ROOT as REBUILD_ROOT, owned_path, STT_SNAPSHOT, TTS_MODEL, VAD_REPOSITORY, CPU_PYTHON
from rebuild_config import LLM_BASE_URL as REBUILD_LLM_URL, MODEL_ALIAS as REBUILD_MODEL_ALIAS
from rebuild_config import require_owned_service

import argparse,json,sys,time,traceback
from enum import Enum
from pathlib import Path
from urllib.request import Request,urlopen
import psutil
PROJECT=REBUILD_ROOT;sys.path.insert(0,str(PROJECT/"experiments"/"auto-voice-h0"/"client"));sys.path.insert(0,str(PROJECT/"experiments"/"speech-chain-g0"/"client"))
from vad_capture import VadCapture
from speech_chain_client import health_checks,llm_reply,tts_reply,nvidia_used_mib
from playback import play_sync
LOG=PROJECT/"experiments"/"auto-voice-h2"/"logs";INPUT=PROJECT/"runtime"/"input"/"h2-vad-utterance.wav";PROMPT="你是一个自然、温柔、亲近的中文聊天伙伴。你的回复应该像真实聊天，不要像客服或说明书。默认使用简短自然的中文回复，一般控制在一到三句话。除非用户明确要求，不要使用列表、标题、Markdown 或长篇解释。"
class State(str,Enum): IDLE="IDLE";LISTENING="LISTENING";TRANSCRIBING="TRANSCRIBING";THINKING="THINKING";SYNTHESIZING="SYNTHESIZING";SPEAKING="SPEAKING";ERROR="ERROR"
def stt_health():
 require_owned_service("stt",8766)
 with urlopen("http://127.0.0.1:8766/health",timeout=10) as r:return json.loads(r.read().decode("utf-8"))
def stt(path):
 require_owned_service("stt",8766)
 data=json.dumps({"audio_path":str(path)},ensure_ascii=False).encode("utf-8");req=Request("http://127.0.0.1:8766/transcribe",data=data,headers={"Content-Type":"application/json; charset=utf-8"},method="POST");started=time.perf_counter()
 with urlopen(req,timeout=180) as r:out=json.loads(r.read().decode("utf-8"))
 if not out.get("ok") or not out.get("text") or out.get("device")!="cpu":raise RuntimeError(f"Persistent STT failed: {out}")
 out["http_total_seconds"]=time.perf_counter()-started;return out
def main():
 p=argparse.ArgumentParser();p.add_argument("--max-turns",type=int,default=1);a=p.parse_args();LOG.mkdir(parents=True,exist_ok=True);(LOG/"stage-h2-progress.txt").write_text("",encoding="utf-8")
 state=State.IDLE;sequence=[];turns=[];messages=[{"role":"system","content":PROMPT}]
 def set_state(next_state):
  nonlocal state;state=next_state;sequence.append(next_state.value);print(next_state.value+"...",flush=True)
 try:
  if stt_health().get("status")!="ready":raise RuntimeError("H1 STT service unavailable")
  health_checks();vad=VadCapture();print("CyberGirlfriend H2\nVAD: ready\nSTT: ready\nLLM: ready\nTTS: ready",flush=True)
  while len(turns)<a.max_turns:
   set_state(State.LISTENING);capture=vad.capture_once(INPUT,print)
   if capture["status"]=="NO_SPEECH":print("No speech detected. Listening again...",flush=True);continue
   set_state(State.TRANSCRIBING);out=stt(INPUT);print("You:\n"+out["text"],flush=True);messages.append({"role":"user","content":out["text"]})
   set_state(State.THINKING);reply,llm_latency,_=llm_reply(messages);messages.append({"role":"assistant","content":reply});print("AI:\n"+reply,flush=True)
   set_state(State.SYNTHESIZING);_,tb=health_checks();tts,tts_http=tts_reply(reply);_,ta=health_checks()
   for key in ("model_load_count","voice_clone_prompt_create_count","warmup_count"):
    if ta[key]!=tb[key]:raise RuntimeError(f"TTS {key} changed unexpectedly")
   if ta["request_count"]!=tb["request_count"]+1:raise RuntimeError("TTS request count mismatch")
   set_state(State.SPEAKING);play_start=time.perf_counter();metrics=play_sync(tts["audio_path"]);play_end=time.perf_counter();print("Playback finished.",flush=True)
   minimum=psutil.virtual_memory().available
   if minimum<700*1024*1024:raise RuntimeError("Memory safety stop")
   turns.append({"capture":capture,"stt":out,"assistant":reply,"llm_latency":llm_latency,"tts":tts,"tts_http":tts_http,"playback":metrics,"speech_end_to_playback_start":play_start-capture["speech_end_clock"],"speech_end_to_playback_end":play_end-capture["speech_end_clock"],"minimum_ram":minimum,"gpu_mib":nvidia_used_mib()})
   while len(messages)>13:del messages[1:3]
  set_state(State.IDLE);summary=["# H2 Automatic Playback","","Status: PASS","","## Playback Backend","","- backend: winsound","- mode: synchronous half-duplex","- microphone active during playback: false",""]
  for i,t in enumerate(turns,1):summary += [f"## Turn {i}","",f"- transcript: {t['stt']['text']}",f"- STT transcription/HTTP: {t['stt']['transcription_seconds']} / {t['stt']['http_total_seconds']}",f"- LLM latency: {t['llm_latency']}",f"- TTS RTF: {t['tts'].get('rtf')}",f"- WAV: {t['playback']['wav_path']}",f"- audio duration/playback: {t['playback']['duration_seconds']} / {t['playback']['playback_seconds']}",f"- speech-end to playback start/end: {t['speech_end_to_playback_start']} / {t['speech_end_to_playback_end']}",f"- state sequence: {' -> '.join(sequence)}",f"- minimum RAM: {t['minimum_ram']}",f"- GPU MiB: {t['gpu_mib']}",""]
  summary += ["## Self-Hearing Protection","","- mic closed before playback: true (capture_once returned before SPEAKING)","- playback finished before next listening: true (synchronous winsound)","- unexpected VAD during speaking: false (no InputStream is opened)","","## Result","","PASS"];(LOG/"stage-h2-summary.md").write_text("\n".join(summary)+"\n",encoding="utf-8");return 0
 except KeyboardInterrupt:print("Stopped by Ctrl+C.",flush=True);return 0
 except Exception:print(traceback.format_exc(),file=sys.stderr,flush=True);return 1
if __name__=="__main__":raise SystemExit(main())
