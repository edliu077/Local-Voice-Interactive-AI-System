# Local model directory

Model weights are intentionally not included. Provide these locally and set
the matching `LVIAI_*` paths in the process environment or a private `.env`:

- `Systran/faster-whisper-small` CTranslate2 cache for CPU INT8 STT.
- `Qwen3-1.7B-Q4_K_M.gguf` for the CPU-only llama.cpp server.
- `Qwen3-TTS-12Hz-0.6B-Base` for the CUDA/eager TTS service.
- A previously obtained Silero VAD torch hub cache.

Do not place model weights under version control.
