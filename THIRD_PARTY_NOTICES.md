# Third-Party Notices

Status: **Documentation Revision v0.9.3 — external artifact evidence finalized**

This document records the components used or evaluated by the Local Voice-Interactive AI System. Version entries come from the audited Demo Stable manifests, installed-package exports, local artifact metadata, and checksums verified on 2026-10-08. External models, runtimes, binaries, and private assets remain outside the tracked repository.

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
| Faster-Whisper | `1.2.1` | https://github.com/SYSTRAN/faster-whisper | MIT confirmed from the final installed package metadata | Dependency only; model artifact tracked separately below |
| Faster-Whisper Small model | `Systran/faster-whisper-small`, snapshot `536b0662742c02347bc0e980a01041f333bce120` | https://huggingface.co/Systran/faster-whisper-small | MIT confirmed by the model repository | Model remains external; do not commit the local snapshot |
| CTranslate2 | `4.8.1` | https://github.com/OpenNMT/CTranslate2 | MIT | Dependency only |
| PyAV | `18.0.0` | https://github.com/PyAV-Org/PyAV | BSD-3-Clause | Dependency only; verify final environment |
| NumPy | `2.4.6` | https://github.com/numpy/numpy | BSD-3-Clause | Dependency only |
| psutil | `7.2.2` | https://github.com/giampaolo/psutil | BSD-3-Clause | Dependency only |
| sounddevice | `0.5.5` | https://github.com/spatialaudio/python-sounddevice | MIT | Dependency only |
| websockets | `16.1.1` | https://github.com/python-websockets/websockets | BSD-3-Clause | Dependency only |
| opencc-python-reimplemented | `0.1.7` | https://github.com/yichen0831/opencc-python | Apache License confirmed from installed package metadata | Dependency only |
| Silero VAD | `snakers4/silero-vad`; local metadata version `6.2.1`; exact commit **VERIFICATION REQUIRED** | https://github.com/snakers4/silero-vad | MIT confirmed from the local cache license and official repository | Cache remains external; `silero_vad.jit` SHA-256 `e1122837f4154c511485fe0b9c64455f7b929c96fbb8d79fbdb336383ebd3720`; missing commit is a P2 reproducibility gap, not a public-source blocker |

## Local LLM

| Component | Recorded version/model | Upstream | Recorded license / status | Public-repository treatment |
|---|---:|---|---|---|
| llama.cpp | Windows x64 CPU release `b10516`; commit `b95502ba9aa0eb73a2f4fc8878d7fbe6a847a0b9` | https://github.com/ggml-org/llama.cpp/releases/tag/b10516 | MIT confirmed upstream; official archive SHA-256 `fbbbc55e0eb2e1b07f9dcb9488616c98ed47d9003b90e15e7c8c7812c4307cd3` | EXE/DLL/ZIP remain external; use the official `llama-b10516-bin-win-cpu-x64.zip` release asset |
| Qwen3-1.7B GGUF | `ggml-org/Qwen3-1.7B-GGUF`, revision `daeb8e2d528a760970442092f6bf1e55c3b659eb`, file `Qwen3-1.7B-Q4_K_M.gguf` | https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF | Apache-2.0 confirmed by the model repository; SHA-256 `d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5` | Weight remains external; no repository redistribution claim is made |
| Qwen3-4B GGUF | Development-only feasibility artifact | https://huggingface.co/Qwen/Qwen3-4B-GGUF | Apache-2.0 | Not part of Demo Stable; do not include in stable download instructions |

## TTS packages and model

| Component | Recorded version/model | Upstream | Recorded license / status | Public-repository treatment |
|---|---:|---|---|---|
| PyTorch | `2.7.1+cu128`; CUDA build `12.8` | https://github.com/pytorch/pytorch | BSD-style | Installed from the official CUDA 12.8 wheel index; wheel remains external; exact wheel URL/hash is an optional P2 reproducibility record |
| torchaudio | `2.7.1+cu128` | https://github.com/pytorch/audio | BSD-style | Installed from the official CUDA 12.8 wheel index; wheel remains external |
| qwen-tts | `0.1.1` | https://github.com/QwenLM/Qwen3-TTS | Apache-2.0 confirmed from final installed package metadata | Dependency only |
| faster-qwen3-tts | `0.3.2` | https://github.com/andimarafioti/faster-qwen3-tts | MIT confirmed from final installed package metadata | Dependency only |
| FastAPI | `0.140.13` | https://github.com/fastapi/fastapi | MIT | Dependency only |
| Pydantic | `2.13.4` | https://github.com/pydantic/pydantic | MIT | Dependency only |
| SoundFile | `0.14.0` | https://github.com/bastibe/python-soundfile | BSD-3-Clause | Dependency only; libsndfile carries separate terms |
| Uvicorn | `0.51.0` | https://github.com/encode/uvicorn | BSD-3-Clause | Dependency only |
| Qwen3-TTS Base | `Qwen/Qwen3-TTS-12Hz-0.6B-Base`, revision `5d83992436eae1d760afd27aff78a71d676296fc` | https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base | Apache-2.0 confirmed by the model repository; main model SHA-256 `180b3b10eb1c9f1b4db7806d5475bae3071c0243c299d49926bab1da3b6946f6`; speech tokenizer SHA-256 `836b7b357f5ea43e889936a3709af68dfe3751881acefe4ecf0dbd30ba571258` | Weights remain external; no repository redistribution claim is made |

## Live2D and character assets

| Component | Recorded version/asset | Source | License/status | Public-repository treatment |
|---|---|---|---|---|
| Live2D Cubism Core | Cubism 5 SDK for Web R4 runtime used with the validated stack | Official Live2D Cubism SDK | Proprietary Live2D terms; public runnable/media publication classification remains separately governed | External local dependency only; the tracked source repository does not contain or redistribute Core |
| Tested Live2D character model | User-provided local model | Private/local source | Public display authorization confirmed for screenshots, GIFs, recruitment videos, project demo videos, and portfolio/recruitment presentations; repository redistribution is not granted | Exclude all model, moc3, textures, motions, expressions, and metadata; display authorization does not grant source-asset redistribution rights |
| Additional Development character assets | User-provided | Private/local source | **Verification required**; not part of public stable package | Exclude |

The MIT license of the renderer does not grant rights to redistribute Live2D Cubism Core or any character model. Excluding Core resolves the current source-repository redistribution boundary; it does not replace review of the applicable Live2D publication terms for a future public runnable package, hosted application, or demo media.

## Private voice material

The voice-cloning reference WAV and transcript are user-controlled private assets. They are not third-party dependencies and are not licensed for repository distribution. The reference WAV, transcript, derived voice prompt, voice embedding, cache, and other private source material must remain outside Git and be referenced only through local configuration.

Generated cloned-voice media has separate authorization for public recruitment demo videos, portfolio videos, project presentations, and public demo media. This display authorization applies only to approved generated output; it does not authorize redistribution of the reference material or derived private voice artifacts in the repository.

## Final release evidence and non-blocking gaps

The final frontend lockfile is reconciled at Next.js `16.3.8`, sharp `0.35.5`, and source-map-js `1.2.2`; `npm audit --omit=dev` reports zero vulnerabilities. External artifact evidence for llama.cpp, Qwen3-1.7B GGUF, Qwen3-TTS, and Faster-Whisper Small is recorded above and in `docs/model-downloads.md`.

The remaining external-artifact items are non-blocking for publication of the current source-only repository:

1. Recover or deliberately repin the exact Silero VAD commit; the local `6.2.1` metadata and JIT checksum are recorded, but the Torch Hub cache did not preserve Git metadata.
2. Optionally record exact PyTorch and torchaudio wheel URLs and hashes for stricter environment reproducibility.
3. Review the applicable Live2D publication classification separately before distributing a runnable package, hosted application, or public media that uses Cubism Core; continue excluding Core from Git.
4. Keep all tested Live2D source model assets excluded even though public media display is authorized.

No third-party source, model, runtime, wheel, or binary is vendored in the tracked repository. Upstream license texts must be added if a future release begins redistributing such material.
