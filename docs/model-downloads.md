# Model and Runtime Downloads

The public repository does not redistribute model weights, llama.cpp binaries, private voice references, Live2D models, or Cubism Core. Obtain each artifact from its authoritative source and keep it outside Git tracking.

## Stable artifact list

| Function | Stable artifact | Suggested local path |
|---|---|---|
| VAD | Pinned `snakers4/silero-vad` revision/cache | `models/silero-vad/` |
| STT | `Systran/faster-whisper-small` | `models/faster-whisper/small/` |
| LLM | `ggml-org/Qwen3-1.7B-GGUF` → `Qwen3-1.7B-Q4_K_M.gguf` | `models/llm/qwen3-1.7b-q4_k_m/` |
| LLM runtime | Official llama.cpp Windows CPU build | `tools/llama.cpp/` |
| TTS | `Qwen/Qwen3-TTS-12Hz-0.6B-Base` | `models/qwen3-tts/0.6b-base/` |
| Voice reference | User-authorized WAV + exact transcript | `private/voice-clone/` or an external private path |
| Character | Authorized local Live2D asset + permitted runtime | `private/live2d/` or release-defined ignored path |

The final release scripts may use environment variables to override these paths. They should never scan unrelated drives or user-profile caches automatically.

## 1. Silero VAD

Source: https://github.com/snakers4/silero-vad

Before release:

- pin the exact repository revision used by Demo Stable;
- record the applicable license at that revision;
- store the cache inside the configured project model directory;
- verify offline startup after the first explicit download.

Do not allow an unexpected runtime download during a recruitment demo.

## 2. Faster-Whisper small

Source: https://huggingface.co/Systran/faster-whisper-small

Stable configuration:

- multilingual `small` model;
- CPU device;
- `int8` compute type;
- local-files-only operation after download.

The Development Snapshot recorded a local model-directory size of `486,212,412` bytes. Treat this as an observed local result, not a permanent upstream download-size guarantee.

## 3. Qwen3-1.7B GGUF

Repository: https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF  
Stable file: `Qwen3-1.7B-Q4_K_M.gguf`

Stable configuration:

- llama.cpp local server;
- CPU-only model layers (`-ngl 0`);
- local address `127.0.0.1:8080`;
- no automatic substitution with a larger model.

The Development Snapshot recorded a local file size of `1,282,439,264` bytes. Record and verify the final SHA-256 before release.

Qwen3-4B is a separate Development feasibility experiment and must not be downloaded or selected by the stable setup.

## 4. llama.cpp

Source: https://github.com/ggml-org/llama.cpp/releases

The audited Development Snapshot recorded a Windows CPU build labeled `b10516`. Before release:

1. confirm that the Demo Stable build uses the same release or document the updated release;
2. record the exact official asset URL;
3. record SHA-256;
4. document the minimum required EXE/DLL set;
5. keep the downloaded package under ignored `tools/` storage.

Do not commit the binary archive or extracted executables to Git.

## 5. Qwen3-TTS 0.6B Base

Source: https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base

Stable configuration:

- Base voice-cloning model;
- CUDA/eager path recorded in the validated environment;
- local-files-only loading after download;
- model and voice-clone prompt loaded once in the persistent TTS process;
- GPU is prioritized for TTS.

The Development Snapshot recorded a local directory size of `2,516,107,450` bytes. Record the final repository revision and a reproducible file manifest before release.

Do not substitute the CustomVoice model or a larger TTS model without a separate validation cycle.

## 6. Private voice reference

Voice cloning requires:

- a WAV file that the user is authorized to use;
- an exact, confirmed transcript of the spoken reference;
- a private local path that is ignored by Git;
- an explicit decision about deletion and backup.

Never include the reference recording, transcript, voice embedding/prompt, or generated voice samples in the public repository without informed consent and a separate distribution decision.

## 7. Live2D assets

The tested Live2D character and Cubism Core runtime are not automatically redistributable with this repository. Until terms are confirmed:

- exclude `moc3`, textures, motions, expressions, model JSON, and Cubism Core;
- provide a placeholder or local-placement README;
- do not imply that the renderer's MIT license covers the model or runtime;
- do not publish screenshots or demo footage unless the asset terms permit that use.

## 8. Verification manifest

The release should provide a non-secret local manifest template:

| Artifact | Expected filename/revision | SHA-256 | Verified date |
|---|---|---|---|
| Silero VAD | To be pinned | To be recorded | To be recorded |
| Faster-Whisper small | Repository snapshot | To be recorded | To be recorded |
| Qwen3-1.7B Q4_K_M | `Qwen3-1.7B-Q4_K_M.gguf` | To be recorded | To be recorded |
| llama.cpp Windows build | Exact release asset | To be recorded | To be recorded |
| Qwen3-TTS 0.6B Base | Repository snapshot | To be recorded | To be recorded |

Checksums confirm local file identity; they do not replace upstream license review.

