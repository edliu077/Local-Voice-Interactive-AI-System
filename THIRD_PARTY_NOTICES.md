# Third-Party Notices

Status: **Documentation Revision v0.9.1 — release verification required**

This document records the components used or evaluated by the Local Voice-Interactive AI System. Version entries come from the last audited Development Snapshot and the validated-environment records. Before public release, compare every entry with the final Demo Stable manifests and installed-package exports.

This file is informational and is not legal advice. Upstream license files and terms remain authoritative.

## Distribution policy

The public repository should contain original source code and documentation only. Unless an entry explicitly states otherwise, the following are **not** redistributed:

- model weights;
- llama.cpp executable/DLL archives;
- Live2D character files and textures;
- Live2D Cubism Core runtime;
- private voice-reference audio or transcript;
- generated audio and logs.

## Frontend packages

| Component | Recorded version | Upstream | Recorded license / status | Public-repository treatment |
|---|---:|---|---|---|
| Next.js | `16.3.3` | https://github.com/vercel/next.js | MIT | Declared through `package-lock.json`; re-run vulnerability audit before release |
| React | `19.2.8` | https://github.com/facebook/react | MIT | Declared through lockfile |
| React DOM | `19.2.8` | https://github.com/facebook/react | MIT | Declared through lockfile |
| PixiJS | `8.20.0` | https://github.com/pixijs/pixijs | MIT recorded in audited package metadata; **verification required** against final lockfile/package | Dependency only; no claim that this license covers Live2D assets |
| untitled-pixi-live2d-engine | `1.3.5` | https://github.com/Untitled-Story/untitled-pixi-live2d-engine | MIT recorded in audited package metadata; **verification required** against final package | Dependency only; does not grant rights to Live2D models or Cubism Core |
| @pixi/sound | `6.0.1` | https://github.com/pixijs/sound | MIT | Transitive dependency; verify final lockfile |
| TypeScript | `5.9.3` | https://github.com/microsoft/TypeScript | Apache-2.0 | Development dependency |
| ESLint | Recorded in final lockfile | https://github.com/eslint/eslint | MIT | Development dependency; verify exact version |

## Speech and orchestration packages

| Component | Recorded version/model | Upstream | Recorded license / status | Public-repository treatment |
|---|---:|---|---|---|
| speech-to-speech | `0.2.11` | https://github.com/huggingface/speech-to-speech | Verify final package metadata | Dependency only; no upstream source copied |
| Faster-Whisper | `1.2.1` | https://github.com/SYSTRAN/faster-whisper | MIT recorded upstream; **verification required** against the final installed package | Dependency only; model terms are tracked separately |
| CTranslate2 | `4.8.1` | https://github.com/OpenNMT/CTranslate2 | MIT | Dependency only |
| PyAV | `18.0.0` | https://github.com/PyAV-Org/PyAV | BSD-3-Clause | Dependency only; verify final environment |
| NumPy | `2.4.6` | https://github.com/numpy/numpy | BSD-3-Clause | Dependency only |
| psutil | `7.2.2` | https://github.com/giampaolo/psutil | BSD-3-Clause | Dependency only |
| sounddevice | `0.5.5` | https://github.com/spatialaudio/python-sounddevice | MIT | Dependency only |
| websockets | `16.1.1` | https://github.com/python-websockets/websockets | BSD-3-Clause | Dependency only |
| opencc-python-reimplemented | Exact version pending verification | https://github.com/naivete5656/opencc-python | License and exact version: **verification required** | Dependency only; pin and verify before release |
| Silero VAD | `snakers4/silero-vad`, exact revision pending | https://github.com/snakers4/silero-vad | Model/repository terms at pinned revision: **verification required** | Do not bundle cache; record commit, terms, and checksum before release |

## Local LLM

| Component | Recorded version/model | Upstream | Recorded license / status | Public-repository treatment |
|---|---:|---|---|---|
| llama.cpp | Windows CPU build `b10516` recorded in Development Snapshot | https://github.com/ggml-org/llama.cpp | MIT recorded upstream; exact release asset and bundled-file terms: **verification required** | Do not commit EXE/DLL/ZIP; document official download URL and SHA-256 |
| Qwen3-1.7B GGUF | `ggml-org/Qwen3-1.7B-GGUF`, `Qwen3-1.7B-Q4_K_M.gguf` | https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF | Apache-2.0 recorded by the model repository; final revision/files: **verification required** | Do not redistribute weight; download separately and verify checksum; no redistribution claim is made |
| Qwen3-4B GGUF | Development-only feasibility artifact | https://huggingface.co/Qwen/Qwen3-4B-GGUF | Apache-2.0 | Not part of Demo Stable; do not include in stable download instructions |

## TTS packages and model

| Component | Recorded version/model | Upstream | Recorded license / status | Public-repository treatment |
|---|---:|---|---|---|
| PyTorch | `2.7.1+cu128` | https://github.com/pytorch/pytorch | BSD-style | Installed from official CUDA 12.8 wheel index; not redistributed |
| torchaudio | `2.7.1+cu128` | https://github.com/pytorch/audio | BSD-style | Dependency only |
| qwen-tts | `0.1.1` | Confirm final package source | **Verification required** from final package metadata | Dependency only; verify before release |
| faster-qwen3-tts | `0.3.2` | Confirm final package source | **Verification required** from final package metadata | Dependency only; verify before release |
| FastAPI | `0.140.13` | https://github.com/fastapi/fastapi | MIT | Dependency only |
| Pydantic | `2.13.4` | https://github.com/pydantic/pydantic | MIT | Dependency only |
| SoundFile | `0.14.0` | https://github.com/bastibe/python-soundfile | BSD-3-Clause | Dependency only; libsndfile carries separate terms |
| Uvicorn | `0.51.0` | https://github.com/encode/uvicorn | BSD-3-Clause | Dependency only |
| Qwen3-TTS Base | `Qwen/Qwen3-TTS-12Hz-0.6B-Base` | https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base | Apache-2.0 recorded by the model repository; final revision/files: **verification required** | Do not redistribute weight; download separately; no redistribution claim is made |

## Live2D and character assets

| Component | Recorded version/asset | Source | License/status | Public-repository treatment |
|---|---|---|---|---|
| Live2D Cubism Core | Cubism 5 SDK for Web R4 runtime used with the validated stack | Official Live2D Cubism SDK | Official terms and public-package treatment: **verification required** | Exclude runtime file unless the applicable terms are confirmed |
| Tested Live2D character model | User-provided local model | Private/local source | Local use recorded; public screenshot/video/repository permissions: **verification required** | Exclude all model, moc3, textures, motions, expressions, and metadata unless permissions are confirmed |
| Additional Development character assets | User-provided | Private/local source | **Verification required**; not part of public stable package | Exclude |

The MIT license of the renderer does not grant rights to redistribute Live2D Cubism Core or any character model.

## Private voice material

The voice-cloning reference WAV and transcript are user-controlled private assets. They are not third-party dependencies and are not licensed for repository distribution. They must remain outside Git and be referenced only through local configuration.

## Required release updates

Before the first public commit:

1. Export exact package versions from the final Demo Stable environments.
2. Reconcile `package-lock.json` and run a fresh dependency vulnerability scan.
3. Pin the Silero VAD revision and record its license and checksum.
4. Record the exact llama.cpp release asset URL and SHA-256.
5. Record model file/repository revisions and checksums.
6. Confirm `qwen-tts` and `faster-qwen3-tts` package sources and licenses.
7. Decide whether Cubism Core and any character asset can be redistributed; default to exclusion if uncertain.
8. Include upstream license texts where their terms require it.

