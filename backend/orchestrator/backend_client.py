"""Validated loopback clients for STT, llama.cpp, and Qwen3-TTS."""
from __future__ import annotations

import json
from pathlib import Path
import re
import subprocess
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from lviai_config import loopback_host, port


STT_HOST = loopback_host("LVIAI_STT_HOST")
LLM_HOST = loopback_host("LVIAI_LLM_HOST")
TTS_HOST = loopback_host("LVIAI_TTS_HOST")
STT_PORT = port("LVIAI_STT_PORT", 8766)
LLM_PORT = port("LVIAI_LLM_PORT", 8080)
TTS_PORT = port("LVIAI_TTS_PORT", 8765)
STT_BASE_URL = f"http://{STT_HOST}:{STT_PORT}"
LLM_BASE_URL = f"http://{LLM_HOST}:{LLM_PORT}"
TTS_BASE_URL = f"http://{TTS_HOST}:{TTS_PORT}"
MODEL_ALIAS = "lviai-qwen3"


def http_json(url: str, payload: dict[str, Any] | None = None, timeout: int = 180) -> dict[str, Any]:
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
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Connection failed for {url}: {exc.reason}") from exc


def clean_for_tts(text: str) -> str:
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"</?think>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```[A-Za-z0-9_+-]*\s*(.*?)```", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", text)
    text = re.sub(r"(?m)^\s*[-*+]\s+", "", text)
    text = text.strip()
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


def stt_health() -> dict[str, Any]:
    return http_json(f"{STT_BASE_URL}/health", timeout=10)


def stt_transcribe(path: Path) -> dict[str, Any]:
    started = time.perf_counter()
    result = http_json(f"{STT_BASE_URL}/transcribe", {"audio_path": str(path)}, timeout=180)
    if not result.get("ok") or not result.get("text") or result.get("device") != "cpu":
        raise RuntimeError(f"Persistent STT failed: {result}")
    result["http_total_seconds"] = time.perf_counter() - started
    return result


def health_checks() -> tuple[dict[str, Any], dict[str, Any]]:
    llm = http_json(f"{LLM_BASE_URL}/health", timeout=10)
    if llm.get("status") != "ok":
        raise RuntimeError(f"LLM service is not ready: {llm}")
    tts = http_json(f"{TTS_BASE_URL}/health", timeout=10)
    if tts.get("status") != "ready":
        raise RuntimeError(f"TTS service is not ready: {tts}")
    return llm, tts


def llm_reply(messages: list[dict[str, str]]) -> tuple[str, float, float | None]:
    started = time.perf_counter()
    response = http_json(
        f"{LLM_BASE_URL}/v1/chat/completions",
        {
            "model": MODEL_ALIAS, "messages": messages, "stream": False, "max_tokens": 120,
            "temperature": 0.8, "chat_template_kwargs": {"enable_thinking": False},
            "reasoning_effort": "none",
        },
    )
    latency = time.perf_counter() - started
    try:
        completion_tokens = response.get("usage", {}).get("completion_tokens")
        tokens_per_second = (
            float(completion_tokens) / latency
            if isinstance(completion_tokens, (int, float)) and completion_tokens > 0 and latency > 0
            else None
        )
        content = str(response["choices"][0]["message"].get("content", ""))
        return clean_for_tts(content), latency, tokens_per_second
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Unexpected llama.cpp completion response") from exc


def tts_reply(text: str) -> tuple[dict[str, Any], float]:
    started = time.perf_counter()
    response = http_json(f"{TTS_BASE_URL}/tts", {"text": text}, timeout=180)
    latency = time.perf_counter() - started
    output = Path(str(response.get("audio_path", "")))
    if not response.get("ok") or not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"TTS did not produce a non-empty WAV: {response}")
    return response, latency
