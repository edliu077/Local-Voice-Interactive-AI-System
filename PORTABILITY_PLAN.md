# Demo Stable v0.9 Portability Boundary

`LVIAI` means **Local Voice-Interactive AI System**.

This workspace is an independent extraction of the validated local voice path.
It never falls back to a legacy Development path, the Development Snapshot, a
user profile, a global Hugging Face cache, or another drive.

## Configuration precedence

Python services use:

1. An explicit `LVIAI_*` process environment variable.
2. A path derived from `Path(__file__).resolve()` inside this workspace.
3. A clear missing-file or missing-directory error.

Windows launch scripts derive the root from `$PSScriptRoot`, optionally import
a private `.env`, and validate every critical path before starting one service.
All hosts remain `127.0.0.1`; port overrides must be integers in `1..65535`.

## Stable default path

The default path contains Silero VAD, Faster-Whisper Small CPU INT8,
Qwen3-1.7B Q4_K_M through CPU-only llama.cpp, Qwen3-TTS 0.6B Base, local
WebSocket orchestration, Browser Web Audio, Live2D, RMS lip sync, browser ACK,
and half-duplex microphone suppression.

Conversation sessions are explicitly limited to 1, 2, or 6 turns. The latest
six raw user/assistant pairs are retained; there is no summarizer, unlimited
loop, rolling summary, memory-recall retry, or hard-cap compaction path.

## Experimental exclusions

- J1-F.2: no emotion parser is imported, no emotion field is emitted, and the
  frontend contains no automatic emotion-to-expression mapping.
- J2: no bounded-context module is copied or imported; finite `max_turns` is
  enforced by the stable WebSocket entry point.
- F0-B: no 4B source, model path, port 8081, or launcher is present. The only
  LLM launcher fixes the validated Qwen3-1.7B generation parameters.

## Runtime invariants

Portability changes must not alter VAD thresholds, Faster-Whisper CPU INT8
parameters, llama.cpp generation parameters, TTS loading and voice cloning,
WebSocket event order, binary audio delivery, ACK waits, half-duplex ordering,
Live2D rendering, or RMS values (`0.018`, `7`, `0.25`, `0.15`).
