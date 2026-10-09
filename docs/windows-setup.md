# Windows Setup

This is the first-draft setup guide for Recruitment Preview v0.9. The final release must be tested from a clean copy before these instructions are marked complete.

## 1. Supported target

Validated configuration:

- Windows 11 x64
- NVIDIA RTX 4060 Laptop GPU with 8 GB VRAM
- 16 GB RAM
- Python 3.12 x64 environment recorded during Development
- Node.js and npm suitable for the committed frontend lockfile
- Chromium-based browser used for manual acceptance

Other configurations may work, but they are not part of the v0.9 compatibility claim.

## 2. Important boundaries

- Do not expose any service beyond `127.0.0.1`.
- Do not place voice references, generated audio, logs, or models under Git tracking.
- Do not install or change the system CUDA Toolkit solely because `nvidia-smi` reports a CUDA compatibility version.
- Use the documented PyTorch CUDA wheel index for the TTS environment.
- Keep TTS isolated from orchestration/STT dependencies.
- Do not enable J1-F.2, J2, or the Qwen3-4B experiment in Demo Stable.

## 3. Prerequisites

Install and verify:

1. Git for Windows
2. Python 3.12 x64 with `venv`
3. Node.js and npm
4. A current NVIDIA driver compatible with the validated PyTorch wheel
5. A microphone and audio output device
6. A browser that allows local Web Audio after user interaction

Optional system `ffmpeg` may help with diagnostics, but the stable Faster-Whisper path uses PyAV and should not require a global ffmpeg executable for ordinary WAV input.

## 4. Repository layout

The release package is expected to use the following local-only directories:

```text
project-root/
├─ models/                 # ignored by Git
├─ tools/                  # ignored binaries such as llama.cpp
├─ private/                # ignored voice and character assets
├─ runtime/                # ignored input/output/PID data
├─ requirements/
├─ scripts/windows/
├─ frontend/
└─ backend/
```

The final `.env.example` and launch scripts are authoritative if names differ from this draft.

## 5. Create isolated Python environments

From PowerShell in the project root:

```powershell
py -3.12 -m venv .venv-orchestrator
py -3.12 -m venv .venv-stt
py -3.12 -m venv .venv-tts
```

Install only the requirements for each service:

```powershell
& .\.venv-orchestrator\Scripts\python.exe -m pip install --upgrade pip
& .\.venv-orchestrator\Scripts\python.exe -m pip install -r .\requirements\orchestrator.txt

& .\.venv-stt\Scripts\python.exe -m pip install --upgrade pip
& .\.venv-stt\Scripts\python.exe -m pip install -r .\requirements\stt.txt

& .\.venv-tts\Scripts\python.exe -m pip install --upgrade pip
& .\.venv-tts\Scripts\python.exe -m pip install -r .\requirements\tts.txt
```

Do not combine the CUDA TTS environment with STT unless the final release explicitly validates that combination.

## 6. Install frontend dependencies

```powershell
Set-Location .\frontend
npm ci
npm run lint
npx next build --webpack
Set-Location ..
```

Use `npm ci`, not an unconstrained install, so the committed lockfile controls the dependency graph. The validated Demo Stable frontend uses a webpack production build and `next start`; it does not use `next dev` / Turbopack for the recruitment run. Run a fresh dependency audit before release.

## 7. Download models and local tools

Follow [model-downloads.md](model-downloads.md). The stable chain requires:

- Silero VAD cache/repository at the pinned revision;
- `Systran/faster-whisper-small` local model;
- Qwen3-1.7B Q4_K_M GGUF;
- a pinned official llama.cpp Windows CPU build;
- Qwen3-TTS 0.6B Base local model;
- a private, authorized voice reference WAV and exact transcript.

Do not download the 4B LLM for Demo Stable.

## 8. Configure private paths

Copy the release template without placing secrets in source control:

```powershell
Copy-Item .\.env.example .\.env
```

Set only local paths beneath the resolved project root where possible. Private reference audio may be stored outside the repository. Configuration precedence should be:

1. explicit process environment variable;
2. path derived from the project root;
3. clear startup failure.

The application should not search user profiles, global model caches, or other drives automatically.

Browser-visible Live2D asset URLs use only the public Next.js variables:

```text
NEXT_PUBLIC_LVIAI_LIVE2D_CORE_URL
NEXT_PUBLIC_LVIAI_LIVE2D_MODEL_URL
```

These values must be browser-relative URLs, not filesystem paths. Other backend/private configuration continues to use the `LVIAI_*` prefix.

## 9. Start and stop the Demo

From the project root, use the unified launcher:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Start-Demo.ps1
```

The launcher starts LLM → STT → TTS → WebSocket → Frontend, verifies the listener/readiness boundary at each stage, waits for Qwen3-TTS `/health` to report `status=ready`, and then opens `http://127.0.0.1:3000/`. A cold TTS start may take tens of seconds to roughly one minute on the validated machine; the launcher waits for confirmed readiness rather than assuming that process creation means ready.

To stop the validated stack safely:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\windows\Stop-Demo.ps1
```

The stop script terminates only verified project processes. Stale PID files are recovered automatically, and unknown port owners fail closed rather than being killed. Administrator privileges are not required, and the workflow does not require a permanent PowerShell execution-policy change.

The five individual service launchers remain available under `scripts/windows/` for troubleshooting and manual recovery.

## 10. Port map

| Service | Local address |
|---|---|
| Frontend | `http://127.0.0.1:3000` |
| llama.cpp | `http://127.0.0.1:8080` |
| Qwen3-TTS | `http://127.0.0.1:8765` |
| Faster-Whisper | `http://127.0.0.1:8766` |
| WebSocket orchestrator | `ws://127.0.0.1:8767` |

No service should bind to `0.0.0.0` in v0.9.

## 11. Acceptance check

After a clean start:

1. Confirm all local health checks.
2. Load the production frontend.
3. Confirm the formal project name and persona/UI labels.
4. Run one turn and verify transcript, response, one browser playback, RMS mouth motion, mouth reset, and playback ACK.
5. Run two turns and confirm context and half-duplex behavior.
6. Run six turns and confirm the selected turn limit stops correctly.
7. Stop the stack and confirm only verified project processes are terminated.
8. Check that no private WAV, transcript, log, model, or binary became Git-tracked.

## 12. Troubleshooting order

Diagnose from the lowest dependency upward:

1. model/private asset path;
2. STT health;
3. llama.cpp health;
4. TTS health and CUDA availability;
5. WebSocket health;
6. frontend connection;
7. browser audio context;
8. Live2D/RMS rendering.

See [../KNOWN_ISSUES.md](../KNOWN_ISSUES.md) before changing model versions, CUDA wheels, ports, or VAD parameters.

