# Demo Limitations

Recruitment Preview v0.9 demonstrates a validated local integration, not a production AI product. The following boundaries are intentional.

## What the demo proves

On the tested Windows 11 laptop, the Demo Stable build can complete controlled 1/2/6-turn conversations through:

- voice endpoint detection;
- speech recognition;
- local 1.7B LLM inference;
- local voice-cloning TTS;
- WebSocket state and audio transfer;
- browser playback;
- Live2D rendering;
- RMS-driven mouth movement;
- playback acknowledgement;
- half-duplex self-listening prevention.

It also demonstrates staged validation, CPU/GPU resource allocation, local-service separation, failure boundaries, and an explicit distinction between Development and Stable scope.

## What the demo does not prove

### Production readiness

The project has not been validated for multi-user security, authentication, uptime, monitoring, deployment automation, support, or internet exposure.

### Broad hardware compatibility

The complete chain has been accepted on one RTX 4060 Laptop 8 GB / 16 GB RAM configuration. Performance on other hardware is unknown until measured.

### Full-duplex conversation

The user cannot interrupt the assistant during playback. The half-duplex choice is deliberate and protects against self-listening.

### Perfect speech recognition

Recognition quality varies with microphone quality, background noise, accent, speaking rate, and room acoustics.

### State-of-the-art LLM quality

Qwen3-1.7B was selected as a practical local model for the constrained machine. The demo is primarily an integration project; response quality is not presented as equivalent to large hosted models.

### Long-term memory

J2 bounded-context and memory work remains in Development. The stable 1/2/6-turn modes do not constitute a claim of persistent user memory.

### Automatic emotional animation

J1-F.2 structured emotion tags and expression mapping are not completed Demo Stable features. Stable visual behavior is Live2D rendering plus audio RMS lip sync.

### Qwen3-4B support

The 4B model is an isolated feasibility experiment. It is not the stable LLM and is not part of the release setup.

### Generative avatar output

The project does not generate real-time human video. Live2D was chosen to reduce GPU/memory/latency pressure and keep resources available for TTS.

### Asset redistribution

The public code package may not include the tested voice reference, character model, or Cubism runtime. A local demonstration can depend on private authorized assets that are not downloadable from the repository.

## Evaluation guidance

Review the demo as evidence of:

- system decomposition;
- technical trade-off analysis;
- local AI component integration;
- staged testing and rollback baselines;
- event-driven browser/backend coordination;
- resource-aware product engineering;
- privacy and release-boundary awareness.

Do not interpret it as evidence that the system is ready for unattended use, external customers, public hosting, or arbitrary hardware.

