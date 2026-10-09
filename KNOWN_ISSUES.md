# Known Issues and Constraints

This file describes limitations of Demo Stable v0.9 and release-packaging items that remain open. It is not a bug tracker for every experiment in the private Development Snapshot.

## Platform and reproducibility

### Windows 11 is the only validated operating system

The stable path uses Windows-specific launch and audio behavior. macOS, Linux, WSL, Docker, and remote servers have not been validated.

### Hardware coverage is narrow

The complete chain has been validated on one laptop configuration: RTX 4060 Laptop GPU with 8 GB VRAM and 16 GB RAM. Other NVIDIA GPUs, integrated graphics, CPU-only TTS, and lower-memory systems are not guaranteed.

### Clean-clone validation has passed

A clean local clone was validated using the public package boundary. `.env` and private/model/audio/binary assets remained excluded. `npm ci`, ESLint, TypeScript `--noEmit`, the Next.js production build, stable contract tests (4/4), and launcher hardening tests all passed. This validates package reproducibility on the tested machine; it does not expand the supported platform or hardware scope.

## Models and startup

### Models are not bundled

VAD, STT, LLM, and TTS model artifacts must be obtained separately. The public repository should fail with a clear missing-path error instead of silently downloading large files during startup.

### TTS cold-start readiness delay

Qwen3-TTS startup performs model loading, voice-clone prompt creation, and CUDA graph warm-up before the service becomes ready. During this work, `/health` may be temporarily unavailable rather than reporting a ready state. On the target machine, the first ready response has taken from tens of seconds to roughly one minute. This is an observed startup range, not a hard SLA; it can vary with cache state, driver state, background load, and hardware.

Demo timing and launcher timeouts should distinguish cold-start readiness from warm per-turn latency. The unified launcher must wait for confirmed health rather than assuming that process creation means the TTS service is ready.

### TTS requires the validated CUDA environment

The stable TTS route has no claimed CPU fallback. CUDA wheel versions, GPU support, and model compatibility must match the documented environment.

## Conversation behavior

### The system is half-duplex

The microphone is closed while the assistant speaks. The user cannot interrupt the response by speaking over it. This is intentional for v0.9 and prevents self-listening.

### 1/2/6-turn modes are the validated interaction scope

The stable claim is limited to the tested finite modes. J2 bounded context, long-term memory, and indefinite conversation behavior are not part of Demo Stable.

### Local model output remains probabilistic

The 1.7B model may produce short, repetitive, or less nuanced responses. The stable project demonstrates integration and interaction control, not state-of-the-art conversational quality.

### Automatic emotion-expression mapping is excluded

J1-F.2 work exists in Development, but Demo Stable v0.9 does not claim automatic LLM-to-Live2D expression mapping.

## Audio and browser behavior

### Browser playback requires an active page and user interaction

Browser autoplay policies can suspend an audio context until the user interacts with the page. The UI should surface this as a recoverable playback error.

### Lip sync is amplitude-based

RMS lip sync follows energy in the played audio. It does not perform phoneme or viseme alignment, so mouth shapes are not linguistically exact.

### Environment noise affects endpoint detection

VAD behavior depends on microphone gain, room noise, speaker volume, and device selection. Thresholds validated on the target machine may require careful retesting elsewhere.

## Assets and redistribution

### Voice reference files are private

The voice-cloning reference audio and transcript are not distributed. A user must provide an authorized local reference and accept the associated privacy and consent responsibilities.

Approved generated cloned-voice media may be used in recruitment demo videos, portfolio videos, project presentations, and public demo media. This authorization does not apply to the reference WAV, transcript, derived voice prompt, voice embedding, cache, or other private source material.

### Live2D source assets remain excluded

The current tested Live2D character is authorized for public screenshots, GIFs, recruitment videos, project demo videos, and portfolio/recruitment presentations. Its original model files, textures, moc3, motions, expressions, and metadata remain excluded from the repository because display authorization does not grant source-asset redistribution rights. Cubism Core redistribution terms remain under verification, so the public repository continues to use placeholders and local-placement instructions.

## Security and deployment

### Local-only does not mean production-secure

Services bind to `127.0.0.1`, but v0.9 is not designed for hostile multi-user hosts, untrusted local processes, or internet exposure. It has no production authentication or authorization model.

### Frontend production dependencies are reconciled

The final frontend lockfile uses Next.js `16.3.8`, sharp `0.35.5`, and source-map-js `1.2.2`. `npm audit --omit=dev` reports zero production vulnerabilities.

The remaining npm audit findings are confined to the development-only `eslint-config-next` → `fast-glob` → `micromatch` → `braces` chain. They do not enter the production runtime. npm currently offers only a forced breaking downgrade to address this chain, so `npm audit fix --force` is intentionally not used. Treat this as a documented, non-blocking development-tooling limitation and re-evaluate when a compatible upstream fix is available.

## Reporting an issue

When reporting a reproducible problem, include:

- Windows version;
- CPU, GPU, VRAM, and RAM;
- Python, Node.js, npm, and browser versions;
- the failing service and local port;
- sanitized logs with personal transcripts and absolute user paths removed;
- whether the failure occurs on cold start, warm start, or a specific turn.
