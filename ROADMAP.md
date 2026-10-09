# Roadmap

The roadmap separates required release work from optional Development research. Items below are plans, not completion claims.

## v0.9 — Recruitment Preview packaging

### Completed in Demo Stable working copy

The following items are complete in the current Demo Stable working directory, including the recorded clean local clone validation on the tested machine.

- [x] Root `.gitignore` added for private assets, models, logs, runtime output, caches, and binaries.
- [x] `.env.example` added without private values.
- [x] Local frontend Origin allowlist added to the WebSocket boundary.
- [x] Formal project naming applied.
- [x] Persona wording and recruitment UI copy cleaned up.
- [x] Frontend moved from `next dev` / Turbopack to `next build --webpack` + `next start`.
- [x] Development-server OOM isolated and the production frontend path regression-tested.
- [x] Demo Stable 1-turn, 2-turn, and 6-turn acceptance passed.
- [x] Stable scope separated from J1-F.2, J2, and Qwen3-4B work.
- [x] English and Chinese README drafts completed, including Demo and contribution sections.
- [x] Architecture, development log, known issues, roadmap, third-party, Windows setup, model download, privacy, and demo limitation drafts completed.
- [x] Unified `Start-Demo.ps1` and `Stop-Demo.ps1` validated in the Demo Stable working copy.
- [x] Stale PID recovery and verified listener-PID reconciliation added.
- [x] Qwen3-TTS startup now waits for confirmed `/health` readiness.
- [x] Public-facing internal names were cleaned up.
- [x] Live2D production browser configuration moved to `NEXT_PUBLIC_LVIAI_*` URLs and regression-tested.
- [x] Final post-hardening 1-turn speech smoke passed.
- [x] Clean local clone validated with `.env` and private/model/audio/binary assets excluded.
- [x] `npm ci`, ESLint, TypeScript `--noEmit`, and the Next.js production build passed in the clean clone.
- [x] Stable contract tests (4/4) and launcher hardening tests passed in the clean clone.
- [x] Frontend production dependencies reconciled to Next.js `16.3.8`, sharp `0.35.5`, and source-map-js `1.2.2`; production audit reports zero vulnerabilities.
- [x] Current tested Live2D character authorized for public screenshots, GIFs, recruitment/demo videos, and portfolio/recruitment presentation.
- [x] Approved generated cloned-voice media authorized for public recruitment/demo and portfolio media.
- [x] Original project code/document policy recorded as All rights reserved.
- [x] Final candidate privacy/scope and Markdown-link scans passed before Git initialization.

### Still required before public GitHub release

- [ ] Complete external model/runtime artifact revision and checksum records.
- [ ] Record exact Python, Node.js, npm, browser, and GPU-driver versions used for the release acceptance run.
- [ ] Record checksums for stable model artifacts and the exact llama.cpp release package.
- [ ] Confirm Cubism Core publication and runtime redistribution terms; continue excluding it until verified.
- [ ] Re-run 1/2/6-turn acceptance from the clean package.
- [ ] Capture and review sanitized screenshots.
- [ ] Record and review the 60–90 second recruitment demo.
- [ ] Re-run final repository link checking if filenames or document layout change before public push.

## v0.10 — Test and diagnostics improvements

- [ ] Add portable unit and contract tests that do not depend on a fixed drive path.
- [ ] Add a non-model protocol test mode for WebSocket and browser audio handoff.
- [ ] Add sanitized sample events for frontend regression tests.
- [ ] Improve startup diagnostics for missing models, ports, audio devices, and CUDA wheels.
- [ ] Add a release checklist that produces a machine-readable pass/fail summary.
- [ ] Measure cold-start and warm-turn latency after the packaging freeze.

## Development candidates — not committed to Demo Stable

### J1-F.2 automatic emotion-expression mapping

Evaluate only after its parser, backend contract, lifecycle reset, and real-browser regressions pass independently. Promotion must not contaminate spoken text with control tags.

### J2 bounded context and memory

Evaluate rolling summaries and memory recall only after deterministic tests cover conflicting facts, corrections, repetition, and hard history caps. Privacy documentation must be updated before any persistent memory is added.

### Qwen3-4B feasibility

Keep 4B isolated until full-chain RAM, latency, and quality measurements show a clear benefit on the 16 GB target machine. It must not silently replace the 1.7B stable baseline.

### Audio and interaction research

- improved endpoint tuning across microphones;
- optional streaming STT/TTS experiments;
- interruption handling only if self-listening protection remains reliable;
- phoneme/viseme lip sync only if the added complexity produces a visible benefit.

## Explicitly out of scope for the current project line

- public internet hosting;
- multi-user accounts or remote microphone access;
- always-on background listening;
- real-time diffusion/video avatar generation on the validated laptop;
- automatic collection or upload of private audio;
- claims of production readiness without a separate security and operational review.
