# Third-Party Notices

Status: **Documentation Revision v0.9.2 — rights and release status synchronized**

This document records the components used or evaluated by the Local Voice-Interactive AI System. Version entries come from the last audited Development Snapshot and the validated-environment records. Before public release, compare every entry with the final Demo Stable manifests and installed-package exports.

This file is informational and is not legal advice. Upstream license files and terms remain authoritative.

## Distribution policy

The public repository should contain original source code and documentation only. Unless an entry explicitly states otherwise, the following are **not** redistributed:

- model weights;
- llama.cpp executable/DLL archives;
- Live2D character files and textures;
- Live2D Cubism Core runtime;
- private voice-reference audio or transcript;
- generated audio and logs, except separately approved generated-voice media published outside the repository.

## Frontend packages

| Component | Recorded version | Upstream | Recorded license / status | Public-repository treatment |
|---|---:|---|---|---|
| Next.js | `16.3.8` | https://github.com/vercel/next.js | MIT | Declared through the final `package-lock.json`; production dependency audit passed |
| React | `19.2.8` | https://github.com/facebook/react | MIT | Declared through lockfile |
| React DOM | `19.2.8` | https://github.com/facebook/react | MIT | Declared through lockfile |
| PixiJS | `8.20.0` | https://github.com/pixijs/pixijs | MIT confirmed from the final lockfile/package metadata | Dependency only; no claim that this license covers Live2D assets |
| untitled-pixi-live2d-engine | `1.3.5` | https://github.com/Untitled-Story/untitled-pixi-live2d-engine | MIT confirmed from the final lockfile/package metadata | Dependency only; does not grant rights to Live2D models or Cubism Core |
| @pixi/sound | `6.0.1` | https://github.com/pixijs/sound | MIT confirmed from the final lockfile/package metadata | Transitive dependency |
| sharp | `0.35.5` | https://github.com/lovell/sharp | Apache-2.0 confirmed from the final lockfile/package metadata | Production transitive dependency; installed through Next.js |
| source-map-js | `1.2.2` | https://github.com/7rulnik/source-map-js | BSD-3-Clause confirmed from the final lockfile/package metadata | Production transitive dependency; installed through PostCSS/Next.js |
| TypeScript | `5.9.3` | https://github.com/microsoft/TypeScript | Apache-2.0 | Development dependency |
| ESLint | `9.39.5` | https://github.com/eslint/eslint | MIT confirmed from the final lockfile/package metadata | Development dependency; residual `braces` advisory is documented separately as non-runtime |

## Speech and orchestration packages

| Component | Recorded version/model | Upstream | Recorded license / status | Public-repository treatment |
|---|---:|---|---|---|
| speech-to-speech | `0.2.11` | https://github.com/huggingface/speech-to-speech | Apache-2.0 confirmed from installed package metadata | Dependency only; no upstream source copied |
| Faster-Whisper | `1.2.1` | https://github.com/SYSTRAN/faster-whisper | MIT confirmed from the final installed package metadata | Dependency only; model terms are tracked separately |
| CTranslate2 | `4.8.1` | https://github.com/OpenNMT/CTranslate2 | MIT | Dependency only |
| PyAV | `18.0.0` | https://github.com/PyAV-Org/PyAV | BSD-3-Clause | Dependency only; verify final environment |
| NumPy | `2.4.6` | https://github.com/numpy/numpy | BSD-3-Clause | Dependency only |
| psutil | `7.2.2` | https://github.com/giampaolo/psutil | BSD-3-Clause | Dependency only |
| sounddevice | `0.5.5` | https://github.com/spatialaudio/python-sounddevice | MIT | Dependency only |
| websockets | `16.1.1` | https://github.com/python-websockets/websockets | BSD-3-Clause | Dependency only |
| opencc-python-reimplemented | `0.1.7` | https://github.com/yichen0831/opencc-python | Apache License confirmed from installed package metadata | Dependency only |
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
| qwen-tts | `0.1.1` | https://github.com/QwenLM/Qwen3-TTS | Apache-2.0 confirmed from final installed package metadata | Dependency only |
| faster-qwen3-tts | `0.3.2` | https://github.com/andimarafioti/faster-qwen3-tts | MIT confirmed from final installed package metadata | Dependency only |
| FastAPI | `0.140.13` | https://github.com/fastapi/fastapi | MIT | Dependency only |
| Pydantic | `2.13.4` | https://github.com/pydantic/pydantic | MIT | Dependency only |
| SoundFile | `0.14.0` | https://github.com/bastibe/python-soundfile | BSD-3-Clause | Dependency only; libsndfile carries separate terms |
| Uvicorn | `0.51.0` | https://github.com/encode/uvicorn | BSD-3-Clause | Dependency only |
| Qwen3-TTS Base | `Qwen/Qwen3-TTS-12Hz-0.6B-Base` | https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base | Apache-2.0 recorded by the model repository; final revision/files: **verification required** | Do not redistribute weight; download separately; no redistribution claim is made |

## Live2D and character assets

| Component | Recorded version/asset | Source | License/status | Public-repository treatment |
|---|---|---|---|---|
| Live2D Cubism Core | Cubism 5 SDK for Web R4 runtime used with the validated stack | Official Live2D Cubism SDK | Official terms and public-package treatment: **verification required** | Exclude runtime file unless the applicable terms are confirmed |
| Tested Live2D character model | User-provided local model | Private/local source | Public display authorization confirmed for screenshots, GIFs, recruitment videos, project demo videos, and portfolio/recruitment presentations; repository redistribution is not granted | Exclude all model, moc3, textures, motions, expressions, and metadata; display authorization does not grant source-asset redistribution rights |
| Additional Development character assets | User-provided | Private/local source | **Verification required**; not part of public stable package | Exclude |

The MIT license of the renderer does not grant rights to redistribute Live2D Cubism Core or any character model.

## Private voice material

The voice-cloning reference WAV and transcript are user-controlled private assets. They are not third-party dependencies and are not licensed for repository distribution. The reference WAV, transcript, derived voice prompt, voice embedding, cache, and other private source material must remain outside Git and be referenced only through local configuration.

Generated cloned-voice media has separate authorization for public recruitment demo videos, portfolio videos, project presentations, and public demo media. This display authorization applies only to approved generated output; it does not authorize redistribution of the reference material or derived private voice artifacts in the repository.

## Remaining release updates

The final frontend lockfile is reconciled at Next.js `16.3.8`, sharp `0.35.5`, and source-map-js `1.2.2`; `npm audit --omit=dev` reports zero vulnerabilities. Remaining third-party release work is:

1. Pin the Silero VAD revision and record its license and checksum.
2. Record the exact llama.cpp `b10516` release asset URL and SHA-256.
3. Record the Qwen3-1.7B GGUF and Qwen3-TTS model repository revisions, file manifests, and checksums.
4. Confirm the applicable Cubism Core publication and redistribution terms; default to exclusion if uncertain.
5. Keep the tested Live2D source model assets excluded even though public media display is authorized.
6. Include upstream license texts where their terms require it.
