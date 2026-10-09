# Documentation Plan — Recruitment Preview v0.9

Status: Documentation Revision v0.9.1  
Project: **Local Voice-Interactive AI System / 本地语音交互AI系统**  
Target repository: `local-voice-interactive-ai-system`

## Documentation goals

The v0.9 documentation should let a recruiter, product manager, or technical reviewer answer five questions quickly:

1. What problem does the project solve?
2. What did the author design and implement?
3. Which parts have actually been validated on the target Windows laptop?
4. What trade-offs were made under an RTX 4060 Laptop 8 GB / 16 GB RAM constraint?
5. What is intentionally excluded from the stable demo and from the public repository?

## Claim policy

Every project statement belongs to one of three levels:

| Level | Meaning | Examples |
|---|---|---|
| Validated in Demo Stable | Manually exercised in the final Demo Stable build | 1/2/6-turn conversations, production frontend, VAD, STT, Qwen3-1.7B, TTS, WebSocket, browser audio, Live2D, RMS lip sync, ACK, half-duplex |
| Implemented or explored in Development | Code or experiments exist, but the feature is not part of the stable demo | J1-F.2 automatic emotion mapping, J2 bounded context / memory work |
| Future evaluation | No stable completion claim | Qwen3-4B feasibility and later optimizations |

The documents must not describe Development-only or future work as a completed Demo Stable feature.

## v0.9.1 revision focus

- Add an honest Demo placeholder without inventing a video, GIF, screenshot, or repository URL.
- Add English and Chinese contribution sections focused on architecture, integration, resource allocation, orchestration, stability, and release hardening.
- Record the project-specific frontend development-server OOM investigation and production-path regression.
- Keep the observed TTS cold-start delay documented; PID bookkeeping was hardened in the final Demo Stable launcher pass.
- Separate working-copy completions from public-release gates in the roadmap.
- Keep third-party license and redistribution statements at `verification required` where the final release evidence is incomplete.

## File map

| File | Primary audience | Purpose |
|---|---|---|
| `README.md` | Recruiters and technical reviewers | English-first project overview, validated scope, design decisions, quick navigation |
| `README.zh-CN.md` | Chinese-speaking reviewers | Chinese counterpart to the main README |
| `ARCHITECTURE.md` | Engineers and hiring managers | Component boundaries, ports, event flow, resource allocation, state machine, safety boundaries |
| `DEVELOPMENT_LOG.md` | Reviewers interested in process | Milestones, experiments, failures, decisions, and stable-version promotion history |
| `KNOWN_ISSUES.md` | Users and reviewers | Current constraints and reproducibility risks without overstating maturity |
| `ROADMAP.md` | Reviewers and maintainers | Packaging work, test work, and optional future research separated by release gate |
| `THIRD_PARTY_NOTICES.md` | Maintainers and compliance reviewers | Component sources, recorded versions, licenses, redistribution status, verification gaps |
| `docs/windows-setup.md` | Windows users | Prerequisites, isolated environments, configuration, startup order, health checks |
| `docs/model-downloads.md` | Local installers | Exact stable model IDs, expected placement, local-only loading, redistribution rules |
| `docs/privacy.md` | Users and reviewers | Audio, voice reference, logs, local processing, deletion, and public-repository boundaries |
| `docs/demo-limitations.md` | Recruiters and evaluators | Honest statement of what the demo does not prove |

## Cross-linking plan

- The main README links to all detailed documents.
- The Chinese README links to the same English technical documents and explains that the repository is English-first.
- Setup links to model downloads, privacy, known issues, and third-party notices.
- Architecture links to limitations and roadmap whenever a boundary could be mistaken for a completed feature.
- Third-party notices links to model downloads for installation details and privacy for private voice/avatar assets.

## Pre-release verification checklist

- Compare dependency versions against the final Demo Stable lockfiles and installed-package exports.
- Confirm the public launcher and configuration filenames used in the docs.
- Confirm that the release frontend uses `next build --webpack` and `next start` from a clean package.
- Confirm the exact Python version used by each validated environment.
- Record the llama.cpp release URL and SHA-256 for the stable binary package.
- Record SHA-256 values for the three stable model artifacts or manifests.
- Verify Live2D model and Cubism SDK redistribution terms before including any runtime asset.
- Run link checking after the repository layout is finalized.
- Run secret, path, log, audio, model-weight, and large-file scans before the first commit.
- Verify that the public clone passes frontend lint/build and the documented health-check sequence.

