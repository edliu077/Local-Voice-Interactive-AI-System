# Model and Runtime Downloads

The public repository does not redistribute model weights, llama.cpp binaries, private voice references, Live2D models, or Cubism Core. Obtain each artifact from its authoritative source and keep it outside Git tracking.

## Stable artifact list

| Function | Stable artifact | Suggested local path |
|---|---|---|
| VAD | `snakers4/silero-vad`; local metadata `6.2.1`, exact commit **VERIFICATION REQUIRED** | `models/silero-vad/` |
| STT | `Systran/faster-whisper-small` snapshot `536b0662742c02347bc0e980a01041f333bce120` | `models/faster-whisper/small/` |
| LLM | `ggml-org/Qwen3-1.7B-GGUF` → `Qwen3-1.7B-Q4_K_M.gguf` | `models/llm/qwen3-1.7b-q4_k_m/` |
| LLM runtime | Official llama.cpp Windows CPU build | `tools/llama.cpp/` |
| TTS | `Qwen/Qwen3-TTS-12Hz-0.6B-Base` | `models/qwen3-tts/0.6b-base/` |
| Voice reference | User-authorized WAV + exact transcript | `private/voice-clone/` or an external private path |
| Character | Authorized local Live2D asset + permitted runtime | `private/live2d/` or release-defined ignored path |

The final release scripts may use environment variables to override these paths. They should never scan unrelated drives or user-profile caches automatically.

## 1. Silero VAD

Source: https://github.com/snakers4/silero-vad

Validated local evidence:

- local repository metadata version: `6.2.1`;
- loaded artifact: `src/silero_vad/data/silero_vad.jit`;
- SHA-256: `e1122837f4154c511485fe0b9c64455f7b929c96fbb8d79fbdb336383ebd3720`;
- license: MIT;
- exact Git commit: **VERIFICATION REQUIRED** because the retained Torch Hub `master` cache has no `.git` metadata.

The missing exact commit is a P2 reproducibility gap, not a blocker for publishing the source-only repository. For stricter reproduction, rebuild and retest the cache from a deliberately pinned upstream tag or commit. Keep the cache inside the configured model directory and verify offline startup after the first explicit download.

Do not allow an unexpected runtime download during a recruitment demo.

## 2. Faster-Whisper small

Source: https://huggingface.co/Systran/faster-whisper-small

Stable configuration:

- multilingual `small` model;
- CPU device;
- `int8` compute type;
- local-files-only operation after download.

Validated snapshot: `536b0662742c02347bc0e980a01041f333bce120`
License: MIT

Validated file checksums:

| File | SHA-256 |
|---|---|
| `config.json` | `b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828` |
| `model.bin` | `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671` |
| `tokenizer.json` | `fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab` |
| `vocabulary.txt` | `34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913` |

The Development Snapshot recorded a local model-directory size of `486,212,412` bytes. Treat this as an observed local result, not a permanent upstream download-size guarantee.

## 3. Qwen3-1.7B GGUF

Repository: https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF
Revision: `daeb8e2d528a760970442092f6bf1e55c3b659eb`
Stable file: `Qwen3-1.7B-Q4_K_M.gguf`
SHA-256: `d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5`

Stable configuration:

- llama.cpp local server;
- CPU-only model layers (`-ngl 0`);
- local address `127.0.0.1:8080`;
- no automatic substitution with a larger model.

The validated local file size is `1,282,439,264` bytes. The file remains external and is not redistributed through this repository.

Qwen3-4B is a separate Development feasibility experiment and must not be downloaded or selected by the stable setup.

## 4. llama.cpp

Source: https://github.com/ggml-org/llama.cpp/releases

Validated release evidence:

- release: `b10516`;
- source commit: `b95502ba9aa0eb73a2f4fc8878d7fbe6a847a0b9`;
- official asset: `llama-b10516-bin-win-cpu-x64.zip`;
- official URL: https://github.com/ggml-org/llama.cpp/releases/download/b10516/llama-b10516-bin-win-cpu-x64.zip;
- SHA-256: `fbbbc55e0eb2e1b07f9dcb9488616c98ed47d9003b90e15e7c8c7812c4307cd3`;
- license: MIT for llama.cpp; the official binary bundle remains external.

The validated launcher calls `llama-server.exe`. Keep the complete official extracted archive together so CPU-dispatch DLL selection is not broken by an incomplete guessed subset.

Do not commit the binary archive or extracted executables to Git.

## 5. Qwen3-TTS 0.6B Base

Source: https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base

Validated revision: `5d83992436eae1d760afd27aff78a71d676296fc`

Stable configuration:

- Base voice-cloning model;
- CUDA/eager path recorded in the validated environment;
- local-files-only loading after download;
- model and voice-clone prompt loaded once in the persistent TTS process;
- GPU is prioritized for TTS.

The validated local directory size is `2,516,107,450` bytes. Main weight checksums:

| File | SHA-256 |
|---|---|
| `model.safetensors` | `180b3b10eb1c9f1b4db7806d5475bae3071c0243c299d49926bab1da3b6946f6` |
| `speech_tokenizer/model.safetensors` | `836b7b357f5ea43e889936a3709af68dfe3751881acefe4ecf0dbd30ba571258` |

The snapshot remains external and is not redistributed through this repository.

Do not substitute the CustomVoice model or a larger TTS model without a separate validation cycle.

## 6. Private voice reference

Voice cloning requires:

- a WAV file that the user is authorized to use;
- an exact, confirmed transcript of the spoken reference;
- a private local path that is ignored by Git;
- an explicit decision about deletion and backup.

Never include the reference recording, transcript, voice embedding/prompt, cache, or generated voice samples in the public repository without informed consent and a separate distribution decision. The current approved generated cloned-voice media may be presented in recruitment/demo and portfolio media, but that public display authorization does not permit repository distribution of the reference or derived private materials.

## 7. Live2D assets

The current tested Live2D character is authorized for public screenshots, GIFs, recruitment videos, project demo videos, and portfolio/recruitment presentations. This display authorization does not permit redistribution of its source assets. Cubism Core is an external local dependency and is not redistributed by the tracked source repository. Public runnable application and media publication classifications remain separately governed by the applicable Live2D terms. Therefore:

- exclude `moc3`, textures, motions, expressions, model JSON, and Cubism Core;
- provide a placeholder or local-placement README;
- do not imply that the renderer's MIT license covers the model or runtime;
- publish screenshots or demo footage only within the confirmed display authorization; do not infer source-asset or Cubism Core redistribution rights from that authorization.

## 8. Verification manifest

The release should provide a non-secret local manifest template:

| Artifact | Expected filename/revision | SHA-256 | Verified date |
|---|---|---|---|
| Silero VAD | Local metadata `6.2.1`; exact commit **VERIFICATION REQUIRED** | `silero_vad.jit`: `e1122837f4154c511485fe0b9c64455f7b929c96fbb8d79fbdb336383ebd3720` | 2026-10-08 |
| Faster-Whisper small | Snapshot `536b0662742c02347bc0e980a01041f333bce120` | `model.bin`: `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671` | 2026-10-08 |
| Qwen3-1.7B Q4_K_M | Revision `daeb8e2d528a760970442092f6bf1e55c3b659eb`; `Qwen3-1.7B-Q4_K_M.gguf` | `d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5` | 2026-10-08 |
| llama.cpp Windows CPU | Release `b10516`; commit `b95502ba9aa0eb73a2f4fc8878d7fbe6a847a0b9`; `llama-b10516-bin-win-cpu-x64.zip` | `fbbbc55e0eb2e1b07f9dcb9488616c98ed47d9003b90e15e7c8c7812c4307cd3` | 2026-10-08 |
| Qwen3-TTS 0.6B Base | Revision `5d83992436eae1d760afd27aff78a71d676296fc` | Main: `180b3b10eb1c9f1b4db7806d5475bae3071c0243c299d49926bab1da3b6946f6`; tokenizer: `836b7b357f5ea43e889936a3709af68dfe3751881acefe4ecf0dbd30ba571258` | 2026-10-08 |
| PyTorch / torchaudio TTS wheels | `2.7.1+cu128`; CUDA build `12.8` | Exact wheel URL/hash optional P2; wheels are not redistributed | 2026-10-08 |

Checksums confirm local file identity; they do not replace upstream license review.
