"""G0-A one-shot Speech -> local LLM -> persistent local TTS client."""

from __future__ import annotations

# Rebuild paths must be configured before third-party imports.
import sys as _rebuild_sys
from pathlib import Path as _RebuildPath
_rebuild_sys.path.insert(0, str(_RebuildPath(__file__).resolve().parents[3]))
from rebuild_config import ROOT as REBUILD_ROOT, owned_path, STT_SNAPSHOT, TTS_MODEL, VAD_REPOSITORY, CPU_PYTHON
from rebuild_config import LLM_BASE_URL as REBUILD_LLM_URL, MODEL_ALIAS as REBUILD_MODEL_ALIAS
from rebuild_config import require_owned_service, LLM
from reply_text import clean_reply_text


import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import traceback
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import psutil


PROJECT_ROOT = REBUILD_ROOT
STT_PYTHON = CPU_PYTHON
STT_WORKER = PROJECT_ROOT / "experiments" / "speech-chain-g0" / "stt" / "transcribe_once.py"
RECORDER = PROJECT_ROOT / "experiments" / "speech-chain-g0" / "client" / "record_once.py"
MODEL_ROOT = STT_SNAPSHOT
INPUT_WAV = PROJECT_ROOT / "runtime" / "input" / "g0a-input.wav"
LOG_DIR = PROJECT_ROOT / "experiments" / "speech-chain-g0" / "logs"
DEFAULT_SUMMARY = LOG_DIR / "stage-g0a-summary.md"
DEFAULT_PROGRESS = LOG_DIR / "stage-g0a-progress.txt"
STT_STDOUT_LOG = LOG_DIR / "stage-g0a-stt-stdout.txt"
STT_STDERR_LOG = LOG_DIR / "stage-g0a-stt-stderr.txt"
LLM_BASE_URL = REBUILD_LLM_URL
TTS_BASE_URL = "http://127.0.0.1:8765"
MODEL_ALIAS = REBUILD_MODEL_ALIAS
MAX_TURNS = 6
SYSTEM_PROMPT = "你是一个自然、温柔、亲近的中文聊天伙伴。你的回复应该像真实聊天，不要像客服或说明书。默认使用简短自然的中文回复，一般控制在一到三句话。除非用户明确要求，不要使用列表、标题、Markdown 或长篇解释。"


def progress(path: Path, marker: str) -> None:
    path = owned_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(marker + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def http_json(url: str, payload: dict[str, Any] | None = None, timeout: int = 180) -> dict[str, Any]:
    if url.startswith(LLM_BASE_URL + "/"):
        require_owned_service("llm", int(LLM["port"]))
    elif url.startswith(TTS_BASE_URL + "/"):
        require_owned_service("tts", 8765)
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    request = Request(url, data=data, headers=headers, method="POST" if payload is not None else "GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} from {url}: {exc.read().decode('utf-8', errors='replace')}") from exc
    except URLError as exc:
        raise RuntimeError(f"Connection failed for {url}: {exc.reason}") from exc


def clean_for_tts(text: str) -> str:
    text = clean_reply_text(text)
    if not text or len(text) > 300:
        raise RuntimeError("LLM reply is empty or exceeds the 300-character TTS limit")
    return text


def nvidia_used_mib() -> int | None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        return int(result.stdout.strip().splitlines()[0]) if result.returncode == 0 and result.stdout.strip() else None
    except Exception:
        return None


def health_checks() -> tuple[dict[str, Any], dict[str, Any]]:
    llm = http_json(f"{LLM_BASE_URL}/health", timeout=10)
    if llm.get("status") != "ok":
        raise RuntimeError(f"LLM service is not ready: {llm}")
    tts = http_json(f"{TTS_BASE_URL}/health", timeout=10)
    if tts.get("status") != "ready":
        raise RuntimeError(f"TTS service is not ready: {tts}")
    for key in ("model_load_count", "voice_clone_prompt_create_count", "warmup_count", "request_count"):
        if key not in tts:
            raise RuntimeError(f"TTS health response is missing {key}")
    return llm, tts


def run_stt(audio: Path) -> dict[str, Any]:
    if not STT_PYTHON.is_file() or not STT_WORKER.is_file():
        raise FileNotFoundError("G0-A STT Python or worker is missing")
    environment = os.environ.copy()
    environment.update({"PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8", "HF_HUB_OFFLINE": "1"})
    completed = subprocess.run(
        [str(STT_PYTHON), "-B", "-s", str(STT_WORKER), "--audio", str(audio), "--model-root", str(MODEL_ROOT)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", env=environment, cwd=PROJECT_ROOT, timeout=300,
    )
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    STT_STDOUT_LOG.write_text(completed.stdout, encoding="utf-8")
    STT_STDERR_LOG.write_text(completed.stderr, encoding="utf-8")
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"STT worker did not return one JSON object: {completed.stdout!r}; stderr={completed.stderr!r}") from exc
    if completed.returncode != 0 or not result.get("ok"):
        raise RuntimeError(f"STT worker failed: {result.get('error')}; stderr={completed.stderr}")
    return result


def llm_reply_raw(messages: list[dict[str, str]]) -> tuple[str, float, float | None]:
    started = time.perf_counter()
    response = http_json(f"{LLM_BASE_URL}/v1/chat/completions", {
        "model": MODEL_ALIAS, "messages": messages, "stream": False, "max_tokens": 120,
        "temperature": 0.8, "chat_template_kwargs": {"enable_thinking": False}, "reasoning_effort": "none",
    })
    latency = time.perf_counter() - started
    try:
        completion_tokens = response.get("usage", {}).get("completion_tokens")
        tokens_per_second = (
            float(completion_tokens) / latency
            if isinstance(completion_tokens, (int, float)) and completion_tokens > 0 and latency > 0
            else None
        )
        return str(response["choices"][0]["message"].get("content", "")), latency, tokens_per_second
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Unexpected llama.cpp completion response") from exc


def llm_reply(messages: list[dict[str, str]]) -> tuple[str, float, float | None]:
    """Legacy validated helper retained unchanged for H0/H1/H2 callers."""
    started = time.perf_counter()
    response = http_json(f"{LLM_BASE_URL}/v1/chat/completions", {
        "model": MODEL_ALIAS, "messages": messages, "stream": False, "max_tokens": 120,
        "temperature": 0.8, "chat_template_kwargs": {"enable_thinking": False}, "reasoning_effort": "none",
    })
    latency = time.perf_counter() - started
    try:
        completion_tokens = response.get("usage", {}).get("completion_tokens")
        tokens_per_second = (
            float(completion_tokens) / latency
            if isinstance(completion_tokens, (int, float)) and completion_tokens > 0 and latency > 0
            else None
        )
        return clean_for_tts(str(response["choices"][0]["message"].get("content", ""))), latency, tokens_per_second
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected llama.cpp response: {response}") from exc


def tts_reply(text: str) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    response = http_json(f"{TTS_BASE_URL}/tts", {"text": text}, timeout=180)
    latency = time.perf_counter() - started
    output = owned_path(str(response.get("audio_path", "")))
    output.relative_to((PROJECT_ROOT / "runtime" / "tts").resolve())
    if not response.get("ok") or not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"TTS did not produce a non-empty WAV: {response}")
    return response, latency


def write_summary(path: Path, result: dict[str, Any]) -> None:
    path = owned_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if result.get("status") != "PASS":
        path.write_text("# G0-A Speech to LLM to TTS\n\nStatus: FAIL\n\n```text\n" + result.get("error", "unknown error") + "\n```\n", encoding="utf-8")
        return
    stt, tts = result["stt"], result["tts"]
    minimum_ram = int(stt["minimum_available_ram_observed_bytes"])
    ram_warning = (
        "WARNING: available RAM dropped below 700 MiB; do not run microphone G0-A2."
        if minimum_ram < 700 * 1024 * 1024
        else "WARNING: available RAM dropped below 1 GiB."
        if minimum_ram < 1024 * 1024 * 1024
        else "none"
    )
    lines = [
        "# G0-A Speech to LLM to TTS", "", "Status: PASS", "", "## STT", "",
        "- model: Systran/faster-whisper-small", "- device: cpu", "- compute type: int8",
        f"- source audio: {stt['audio']}", f"- audio duration: {stt['audio_duration_seconds']:.3f}s",
        f"- transcript: {stt['text']}", f"- latency: {stt['transcription_seconds']:.3f}s",
        f"- RTF: {stt['rtf']:.3f}", f"- STT RSS: {stt['stt_rss_peak_observed_bytes']}", "",
        "## LLM", "", f"- model alias: {MODEL_ALIAS}", "- CPU-only: -ngl 0",
        f"- latency: {result['llm_latency_seconds']:.3f}s", f"- tokens/s: {result['llm_tokens_per_second']}", "", "## TTS", "",
        f"- synthesis time: {tts.get('synthesis_seconds')}", f"- RTF: {tts.get('rtf')}",
        f"- output WAV: {tts.get('audio_path')}", f"- GPU peak MiB: {tts.get('request_gpu_peak_mib')}", "",
        "## System", "", f"- available RAM before STT: {stt['available_ram_before_bytes']}",
        f"- minimum available RAM: {stt['minimum_available_ram_observed_bytes']}",
        f"- available RAM after STT release: {stt['available_ram_after_model_release_bytes']}", f"- RAM warning: {ram_warning}",
        f"- GPU used before MiB: {result['gpu_used_before_mib']}", f"- GPU used after MiB: {result['gpu_used_after_mib']}",
        f"- total latency: {result['total_latency_seconds']:.3f}s", "", "## Result", "", "PASS",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_file(audio: Path, messages: list[dict[str, str]], progress_path: Path) -> dict[str, Any]:
    _, tts_before = health_checks()
    gpu_before = nvidia_used_mib()
    total_started = time.perf_counter()
    progress(progress_path, "stt_start")
    stt = run_stt(audio)
    progress(progress_path, "stt_done")
    if stt.get("device") != "cpu" or stt.get("compute_type") != "int8":
        raise RuntimeError(f"Unexpected STT execution mode: {stt.get('device')} / {stt.get('compute_type')}")
    text = str(stt["text"]).strip()
    if not text or not re.search(r"[\u4e00-\u9fff]", text):
        raise RuntimeError("STT transcript is empty or has no Chinese characters")
    messages.append({"role": "user", "content": text})
    progress(progress_path, "llm_start")
    assistant, llm_latency, llm_tokens_per_second = llm_reply(messages)
    messages.append({"role": "assistant", "content": assistant})
    progress(progress_path, "llm_done")
    progress(progress_path, "tts_start")
    tts, _ = tts_reply(assistant)
    progress(progress_path, "tts_done")
    _, tts_after = health_checks()
    for key in ("model_load_count", "voice_clone_prompt_create_count", "warmup_count"):
        if tts_after[key] != tts_before[key]:
            raise RuntimeError(f"TTS {key} changed unexpectedly: {tts_before[key]} -> {tts_after[key]}")
    if tts_after["request_count"] != tts_before["request_count"] + 1:
        raise RuntimeError(f"TTS request_count was not incremented by one: {tts_before['request_count']} -> {tts_after['request_count']}")
    return {
        "status": "PASS", "stt": stt, "assistant": assistant, "llm_latency_seconds": llm_latency,
        "llm_tokens_per_second": llm_tokens_per_second,
        "tts": tts, "tts_health_before": tts_before, "tts_health_after": tts_after,
        "gpu_used_before_mib": gpu_before, "gpu_used_after_mib": nvidia_used_mib(),
        "total_latency_seconds": time.perf_counter() - total_started,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio-file", type=Path)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--progress", type=Path, default=DEFAULT_PROGRESS)
    args = parser.parse_args()
    args.progress = owned_path(args.progress)
    args.summary = owned_path(args.summary)
    args.progress.parent.mkdir(parents=True, exist_ok=True)
    args.progress.write_text("", encoding="utf-8")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    try:
        if args.audio_file:
            result = run_file(args.audio_file, messages, args.progress)
            write_summary(args.summary, result)
            progress(args.progress, "complete")
            print(json.dumps(result, ensure_ascii=False), flush=True)
            return 0
        print("CyberGirlfriend G0-A", flush=True)
        print("LLM: ready; TTS: ready; STT: Faster-Whisper small CPU int8", flush=True)
        health_checks()
        while True:
            command = input("Press Enter to record, or type /exit: ").strip()
            if command == "/exit":
                return 0
            if psutil.virtual_memory().available < 700 * 1024 * 1024:
                raise RuntimeError("Available RAM is below 700 MiB; microphone G0-A2 is blocked by the safety policy")
            completed = subprocess.run([str(STT_PYTHON), "-B", "-s", str(RECORDER), "--output", str(INPUT_WAV)], cwd=PROJECT_ROOT)
            if completed.returncode != 0:
                print("Recording failed; no request was sent.", flush=True)
                continue
            result = run_file(INPUT_WAV, messages, args.progress)
            print("You said:\n" + str(result["stt"]["text"]), flush=True)
            print("AI:\n" + result["assistant"], flush=True)
            print(f"STT: {result['stt']['transcription_seconds']:.3f}s; LLM: {result['llm_latency_seconds']:.3f}s; TTS RTF: {result['tts'].get('rtf')}; Total: {result['total_latency_seconds']:.3f}s", flush=True)
            print("Audio: " + str(result["tts"].get("audio_path")), flush=True)
            while len(messages) > 1 + MAX_TURNS * 2:
                del messages[1:3]
    except Exception:
        error = traceback.format_exc()
        write_summary(args.summary, {"status": "FAIL", "error": error})
        progress(args.progress, "failed")
        print(json.dumps({"status": "FAIL", "error": error}, ensure_ascii=False), file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
