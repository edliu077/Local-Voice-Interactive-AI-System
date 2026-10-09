# Roadmap

The roadmap separates required release work from optional Development research. Items below are plans, not completion claims.

## v0.9 — Recruitment Preview packaging

### Completed in Demo Stable working copy

The following items are complete in the current Demo Stable working directory. They are not yet a claim that a fresh public clone reproduces the same result.

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

### Still required before public GitHub release

- [ ] Validate the complete published package from a clean clone/directory using only public instructions.
- [ ] Reconcile every dependency and runtime version with the final Demo Stable manifests and installed-package exports.
- [ ] Record exact Python, Node.js, npm, browser, and GPU-driver versions used for the release acceptance run.
- [ ] Record checksums for stable model artifacts and the exact llama.cpp release package.
- [ ] Select the public license for original project code and document exclusions clearly.
- [ ] Confirm Live2D model and Cubism Core screenshot/video/runtime redistribution permissions.
- [ ] Run the full pre-commit scan for secrets, transcripts, usernames, absolute paths, binaries, audio, model weights, and large files.
- [ ] Re-run frontend lint and `next build --webpack` from the clean package.
- [ ] Re-run 1/2/6-turn acceptance from the clean package.
- [ ] Capture and review sanitized screenshots.
- [ ] Record and review the 60–90 second recruitment demo.
- [ ] Run final repository link checking after filenames and layout are frozen.
- [ ] Confirm that no Git repository is initialized until the clean package passes the privacy and scope checks.

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

