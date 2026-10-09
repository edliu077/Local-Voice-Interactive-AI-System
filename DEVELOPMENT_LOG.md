# Development Log

This log summarizes the engineering progression that led to Demo Stable v0.9. It is a curated public record, not a copy of private logs or the full Development repository history.

## July 2026 — Environment and speech-recognition baseline

### A/B — Windows environment and orchestration feasibility

- Established a native Windows-first plan.
- Validated Python environment creation and the `speech-to-speech` package surface.
- Found that the upstream orchestration path constructed the full model chain too early for a model-free health test.
- Decision: validate each component separately and retain the option of a minimal local orchestrator.

### C0 — Faster-Whisper

- Fixed the transcription baseline to `Systran/faster-whisper-small`.
- GPU loading was possible, but GPU transcription encountered a CUDA runtime DLL issue in the tested setup.
- CPU `int8` completed Chinese transcription reliably and fast enough for the target interaction loop.
- Decision: keep STT on CPU and reserve GPU capacity for TTS.

## August 2026 — TTS, local LLM, and end-to-end voice chain

### E0 — Qwen3-TTS

- Validated Qwen3-TTS 0.6B Base voice cloning with a local, user-controlled reference recording.
- Moved model loading, voice-clone prompt creation, and warm-up into a persistent local service.
- Added request serialization and resource monitoring.

### F0-A — Local LLM

- Validated Qwen3-1.7B Q4_K_M through a CPU-only llama.cpp server.
- Connected text generation to the persistent TTS service.
- Kept `-ngl 0` to avoid competing with TTS for GPU memory.

### G0 — Speech chain

- Connected WAV input to STT, local LLM, and TTS.
- Added manual microphone capture after file-based validation.
- Confirmed that staged component validation was easier to debug than starting with a monolithic pipeline.

### V0/H0 — Voice endpointing and automatic turns

- Added Silero VAD on CPU.
- Validated automatic speech start/end detection before connecting it to the full chain.
- Built one-turn and multi-turn microphone flows.
- Preserved the earlier file-based path as a fallback.

### H1/H2 — Persistent STT and half-duplex playback

- Replaced per-turn STT model loading with a persistent Faster-Whisper service.
- Added synchronous playback and an explicit half-duplex state sequence.
- Confirmed that microphone capture stayed closed while assistant audio played.

## Late August–September 2026 — Browser and character integration

### I0 — WebSocket event bridge

- Added a local WebSocket orchestration layer.
- Kept model services outside the bridge process.
- Defined observable state events and one-active-session behavior.

### J0 — Next.js frontend

- Added connection controls, conversation controls, status display, subtitles, and session history.
- Kept microphone capture in the Python path rather than duplicating it in the browser.
- Validated browser connection and real conversation events.

### J1-B/J1-C — Live2D baseline

- Integrated a PixiJS 8-compatible Live2D renderer.
- Validated one character at a time, resize behavior, EyeBlink, Physics, Breath, and idle stability.
- Kept model/runtime redistribution separate from source-code publication.

### J1-D.1 — Browser audio handoff

- Replaced the stable-demo speaker path with binary WAV delivery to the browser.
- Added playback-started and playback-finished acknowledgements.
- Retained the earlier Windows playback route as a Development fallback.

### J1-E.1 — RMS lip sync

- Used the final browser playback signal as the lip-sync source.
- Mapped analyser RMS to `ParamMouthOpenY` with smoothing and reset behavior.
- Verified no stuck-mouth condition after normal finish or stop.

## October 2026 — Stable/demo separation and release preparation

### Development Snapshot audit

- Inventoried source, logs, binaries, models, audio, and Live2D assets.
- Confirmed that the complete Development Snapshot should not be uploaded directly.
- Defined Public, Private, and Exclude categories.
- Planned a separate Demo Stable directory so packaging work would not damage the development baseline.

### Portability and packaging pass

- Scoped path portability work to the stable chain instead of rewriting historical experiments.
- Kept STT/orchestration and CUDA TTS in separate environments.
- Preserved local-only networking and private-asset boundaries.
- Completed formal project identity and UI/persona naming for the Demo Stable line.

### Frontend development-server OOM → production frontend

The first Demo Stable regression passed the 1-turn and 2-turn tests. During the 6-turn test, the conversation was near completion when the frontend became unavailable. The frontend error log contained:

```text
FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory
```

Process and memory checks showed that the `next dev` / Turbopack development server heap had grown to approximately 6.4 GB. The failure was isolated to the development-server path used for the demo; it was not attributed to the Python voice chain, Browser Audio protocol, Live2D state, or a general Next.js defect.

The Demo Stable frontend was changed to:

- `next build --webpack`
- `next start`

The production frontend initially used approximately 80–90 MiB Working Set on the target machine. After the change, the complete 1-turn, 2-turn, and 6-turn regression suite passed. Frontend memory measured before and after the 6-turn test remained approximately flat rather than showing the earlier multi-gigabyte growth.

This became a representative stabilization case for the project: reproduce the failure, inspect the component-specific log, measure the suspected process, isolate the failing runtime mode, change only that boundary, and then repeat the full regression sequence.

### Release launcher hardening

The Windows launcher layer was hardened before release packaging:

- stale or invalid PID files are recovered automatically;
- PID files are reconciled to the verified process that actually owns the expected listener port;
- unknown port owners fail closed and are never terminated automatically;
- Qwen3-TTS startup waits for `GET /health` to report `status=ready` before later services continue;
- `Start-Demo.ps1` starts LLM → STT → TTS → WebSocket → Frontend with readiness checks;
- `Stop-Demo.ps1` stops only verified project processes and preserves unrelated Python/Node/llama.cpp processes.

### Live2D production environment hotfix

A final production-browser regression exposed a configuration-boundary issue: the client component read ordinary `LVIAI_LIVE2D_*` variables, which were not available to the Next.js browser bundle, so the production build fell back to `/live2d/model/model3.json` and returned HTTP 404.

The fix was intentionally limited to browser-safe URL configuration:

- `NEXT_PUBLIC_LVIAI_LIVE2D_CORE_URL`
- `NEXT_PUBLIC_LVIAI_LIVE2D_MODEL_URL`

The real model URL and Cubism Core URL then returned HTTP 200, the old fallback was no longer requested, and a final manual 1-turn speech smoke confirmed Live2D rendering, Browser Audio, RMS lip sync, playback ACK, and return to Listening.

### Demo Stable manual acceptance

Validated on the target Windows machine:

- 1-turn conversation
- 2-turn conversation
- 6-turn conversation
- Production frontend stability
- VAD → STT → Qwen3-1.7B → TTS → WebSocket → Browser Audio
- Live2D rendering and RMS lip sync
- playback ACK ordering
- half-duplex self-listening prevention

### Frontend dependency security remediation

The frontend dependency lock was updated without a forced audit fix or a major-version downgrade:

- Next.js `16.3.8`;
- sharp `0.35.5`;
- source-map-js `1.2.2`.

`npm ci`, ESLint, TypeScript `--noEmit`, and the Next.js Webpack production build passed after the update. `npm audit --omit=dev` reported zero production vulnerabilities. The remaining audit advisory is confined to the development-only ESLint/braces chain; it is non-runtime and is not being addressed through the breaking downgrade proposed by `npm audit fix --force`.

### Clean-clone validation

A clean local clone completed the documented package validation with `.env` and private/model/audio/binary assets excluded. The following checks passed:

- `npm ci`;
- ESLint;
- TypeScript `--noEmit`;
- Next.js production build;
- stable contract tests (4/4);
- launcher hardening tests.

### Public media rights boundary

Public display authorization has been confirmed for the current tested Live2D character in screenshots, GIFs, recruitment videos, project demo videos, and portfolio/recruitment presentations. The character's original model files, textures, moc3, motions, expressions, and metadata remain excluded because display authorization does not grant repository redistribution rights. Cubism Core remains external and is not redistributed; future runnable application and media publication classification remains separately governed by the applicable Live2D terms.

Approved generated cloned-voice output is authorized for public recruitment/demo and portfolio media. The reference WAV, reference transcript, derived voice prompt, voice embedding, cache, and other private source material remain private and excluded from Git.

### External artifact evidence finalization

The final local evidence review recorded:

- llama.cpp release `b10516`, commit `b95502ba9aa0eb73a2f4fc8878d7fbe6a847a0b9`, and the official Windows CPU ZIP checksum;
- Qwen3-1.7B Q4_K_M revision `daeb8e2d528a760970442092f6bf1e55c3b659eb` and matching GGUF checksum;
- Qwen3-TTS 0.6B Base revision `5d83992436eae1d760afd27aff78a71d676296fc` and main model/tokenizer weight checksums;
- Faster-Whisper Small snapshot `536b0662742c02347bc0e980a01041f333bce120`;
- Silero local metadata version `6.2.1` and JIT checksum, with the exact cached commit retained as a P2 reproducibility gap;
- PyTorch and torchaudio `2.7.1+cu128` with CUDA build `12.8`, while wheels remain external.

### Current stage

The runtime and source package are ready for the repository visibility decision. Git is initialized on `main`; clean-clone validation, frontend production dependency remediation, privacy/scope scans, media-rights review, external-artifact evidence review, and final tracked-tree/full-history audit have passed. No P0/P1 source-publication blocker remains. Exact Silero commit recovery, optional wheel hashes, future Cubism runnable/media publication classification, and final sanitized media capture remain documented P2 follow-up work.

## Development-only work not promoted to Demo Stable

### J1-F.2 — Automatic emotion-expression mapping

Implementation and experiments exist in Development, but the feature is not claimed as complete in Demo Stable v0.9.

### J2 — Bounded context and memory

Context summarization and memory-related work exists in Development. It is not part of the stable 1/2/6-turn demo claim.

### F0-B — Qwen3-4B feasibility

The 4B model remains an isolated feasibility experiment. The stable model is Qwen3-1.7B.
