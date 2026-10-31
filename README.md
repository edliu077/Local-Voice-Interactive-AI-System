# 本地语音交互AI系统（Local Voice-Interactive AI System）

[简体中文](README.zh-CN.md)

A native-Windows, local, half-duplex voice interaction project combining speech recognition, a CPU language model, cloned-voice synthesis and an audio-driven video avatar.

**Baseline: Windows Functional Stable Candidate v1.0-rc1 — Known Quality Issues.** Q-001 (STT accuracy/completeness) and Q-002 (repetitive replies) remain **OPEN**. This is not a final release or a claim of complete conversational quality.

## Repository status

This checkout is a **Windows Rebuild public integration-source candidate, not an out-of-the-box complete runtime package**. It retains first-party orchestration, safety managers, speech interfaces, frontend and technical history. The entire LiveTalking vendor tree is absent, including all CONDITIONAL/BLOCKED files and its three locally added files. READY vendor files are also omitted; no partial runtime or vendor patch is distributed.

Stage 2C-1 applied the reviewed frontend dependency security fixes. Stage 3A subsequently completed npm ci with lifecycle scripts disabled, full/production npm audits with zero known vulnerability package groups at the time of the queries, ESLint, TypeScript noEmit and the Next.js Webpack production build in this PublicationCandidate. The existing ESLint 9.39.5 unsupported-version warning remains; no remediation of that warning is claimed. These frontend-only results are not a permanent zero-risk guarantee and do not establish browser/WebRTC integration, backend or seven-service runtime, model quality or independent recovery. Original local-system acceptance remains separate. See [external integration](docs/third-party/EXTERNAL_LIVETALKING.md), [publication gates](docs/release/PUBLICATION_BLOCKERS.md) and [candidate file list](docs/release/PUBLICATION_FILE_LIST.md).

The original local development system has passed user-operated functional conversations, including the accepted eight-turn flow, first-click connection, manual ending, avatar playback, browser WAV fallback and safe shutdown. Those results do not transfer automatically to a public clone. Long-term stability and complete independent recovery remain unverified. The working source also includes a default-off STT evidence patch added after the frozen archive; it is not byte-identical to the rc1 ZIP.

## Current architecture

| Service | Local port | Implementation |
| --- | ---: | --- |
| Frontend | 3000 | Next.js production frontend |
| Avatar controller | 8011 | Owned session/audio control |
| TTS | 8765 | Qwen3-TTS 0.6B Base, CUDA voice cloning |
| Video avatar | 8010 | LiveTalking + Wav2Lip256, 25 FPS configuration |
| LLM | 8081 | Qwen3-1.7B Q4_K_M, llama.cpp CPU-only, 4096 context |
| STT | 8766 | Faster-Whisper Small, CPU INT8 |
| WebSocket / VAD | 8767 | Python orchestration + Silero VAD |

The default playback path sends final TTS audio through the avatar controller/audio bridge into LiveTalking/Wav2Lip and WebRTC. Browser WAV playback remains an advanced fallback. Listening resumes after the controlled playback lifecycle; this is not full-duplex interruption or streaming token-to-speech inference.

## Use and recovery boundary

Read [Windows setup](docs/windows-setup.md), [external models/assets](docs/model-downloads.md) and [privacy](docs/privacy.md) first. Weights, binaries, environments, private reference audio/text, avatar frames and build products are not bundled. Current recorded dependency lists are not a verified clean-install recipe.

The retained integration entry points are `Start-Rebuild.cmd` and `Stop-Rebuild.cmd`. The web address is `http://127.0.0.1:3000`. One user click connects/unlocks playback/starts a session; “结束对话” ends it, and WAV fallback is in advanced settings. These are baseline behaviors, **not instructions to start this incomplete checkout now; an unmodified upstream checkout does not restore the excluded local changes**. Resource and process ownership checks must remain intact.

## Seven Development Phases

1. **Phase 1 — Environment and Model Validation:** native Windows feasibility and independent STT/TTS/LLM validation.
2. **Phase 2 — Voice Interaction Pipeline:** VAD, persistent services, explicit audio ownership and half-duplex turns.
3. **Phase 3 — Early Digital Avatar Integration:** WebSocket, Next.js, Browser Audio, Live2D and RMS lip sync.
4. **Phase 4 — Demo Stable Validation:** production frontend, 1/2/6-turn functional acceptance, launcher and source-package review.
5. **Phase 5 — Windows Rebuild Architecture Decision:** preserve the successful baseline while choosing an audio-driven video avatar route.
6. **Phase 6 — Windows Rebuild Implementation:** external TTS bridge, WebRTC, seven-service management and product interaction cleanup.
7. **Phase 7 — Functional Acceptance and Quality Investigation:** rc1 functional freeze, bounded evidence collection and OPEN STT/LLM issues.

See the [complete development log](DEVELOPMENT_LOG.md), [historical Demo Stable](docs/legacy/demo-stable/README.md), and [Why Windows Rebuild](docs/architecture/WHY_WINDOWS_REBUILD.md). The seven original Git commits and their dates remain unchanged. Demo Stable v0.9 was a successful functional baseline; v0.9.1 is a documentation revision, not an invented release Tag.

## Documentation and rights

[Architecture](ARCHITECTURE.md) · [Validation](docs/validation.md) · [Known issues](KNOWN_ISSUES.md) · [Changelog](CHANGELOG.md) · [Roadmap](ROADMAP.md)

Copyright © 2026 Enhua Liu. All rights reserved for original source and documentation; no new open-source grant is made by this migration. Third-party code and assets retain their own terms. LiveTalking's Apache-2.0 license does not grant unrestricted rights to embedded derivatives, model weights or avatar/voice assets. See [Third-party notices](THIRD_PARTY_NOTICES.md) and the [component review](docs/release/PUBLICATION_BLOCKERS.md#third-party-component-matrix). No LiveTalking runtime tree is distributed here. Do not add unresolved source, patches, weights or demo media. Public viewing is not a new permissive project license.
