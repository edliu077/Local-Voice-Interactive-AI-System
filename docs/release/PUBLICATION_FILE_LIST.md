# 本地语音交互AI系统（Local Voice-Interactive AI System）— Publication allowlist and final files

This list identifies candidate payload paths, excluding .git and ignored .publication-audit. SHA-256 verification uses Git-stored normalized blob bytes (read with git cat-file from the index or final commit), not raw Windows worktree bytes. Windows checkout line-ending rules may change raw-file SHA-256 without changing Git content. Ancestor Git objects remain unchanged and are audited separately. 167 exact source paths were selected; selected documents may be adapted for candidate scope and one mock fixture is deidentified. All 102 files under the full source third_party/LiveTalking path (101 payload + UPSTREAM.md) are excluded. No package/runtime/cache/media is recursively copied.

Final intended file count: **191**. PUBLICATION_SHA256SUMS.txt hashes the other 190 files, including this inventory and the report; it cannot self-hash. Its own hash is in ignored audit final-state. This is a review allowlist, not an instruction to stage or publish files.

## Stage5 showcase update

The current payload adds 18 explicitly approved showcase assets: six real screenshots, six proportional previews, and Chinese/English architecture SVG, PNG and Mermaid files. The two READMEs are updated and the frontend display title is aligned through exactly two JSX text replacements. Models, reference voices, runtime recordings, private logs and excluded vendor implementations remain outside the payload. The 167-path source-copy list below records the earlier migration selection; the 191-path final table is authoritative for the current tree. Existing Git history is retained. Checksums use normalized Git blob bytes and exclude the checksum file itself.

## Historical source-copy allowlist (167 paths; Stage2C3)

- `.gitignore`
- `ARCHITECTURE.md`
- `CHANGELOG.md`
- `DEVELOPMENT_LOG.md`
- `DOCUMENTATION_PLAN.md`
- `KNOWN_ISSUES.md`
- `PORTABILITY_PLAN.md`
- `README.md`
- `README.zh-CN.md`
- `ROADMAP.md`
- `Start-LLM-1P7B.cmd`
- `Start-Rebuild.cmd`
- `Stop-LLM-1P7B.cmd`
- `Stop-Rebuild.cmd`
- `THIRD_PARTY_NOTICES.md`
- `assets/avatar/README.md`
- `assets/live2d/README.md`
- `assets/stt/README.md`
- `assets/voice-clone/README.md`
- `assets/voice/README.md`
- `config/README.md`
- `config/cpu-requirements.lock.txt`
- `config/livetalking-requirements.in`
- `config/livetalking-requirements.lock.txt`
- `config/livetalking-stage4.yaml`
- `config/rebuild.example.json`
- `config/resource-policy.json`
- `config/tts-requirements.lock.txt`
- `config/windows-runtime.example.json`
- `docs/architecture/WHY_WINDOWS_REBUILD.md`
- `docs/demo-limitations.md`
- `docs/legacy/demo-stable/README.md`
- `docs/legacy/demo-stable/architecture.md`
- `docs/legacy/demo-stable/development-phases.md`
- `docs/legacy/demo-stable/known-issues.md`
- `docs/model-downloads.md`
- `docs/privacy.md`
- `docs/release/PUBLICATION_BLOCKERS.md`
- `docs/third-party/FILE_CLASSIFICATION.md`
- `docs/third-party/LICENSE_SOURCES.md`
- `docs/third-party/RUNTIME_SCOPE.md`
- `docs/third-party/licenses/FunASR-MIT.txt`
- `docs/third-party/licenses/LiveTalking-Apache-2.0.txt`
- `docs/third-party/licenses/Recorder-MIT.txt`
- `docs/third-party/licenses/SRS-MIT.txt`
- `docs/third-party/licenses/aiortc-BSD-3-Clause.txt`
- `docs/third-party/licenses/es6-promise-MIT.txt`
- `docs/third-party/licenses/face-alignment-BSD-3-Clause.txt`
- `docs/third-party/licenses/mpegts-Apache-2.0.txt`
- `docs/validation.md`
- `docs/windows-setup.md`
- `experiments/auto-voice-h0/client/vad_capture.py`
- `experiments/auto-voice-h2/client/auto_voice_client.py`
- `experiments/auto-voice-h2/client/playback.py`
- `experiments/avatar-bridge/audio_adapter.py`
- `experiments/avatar-bridge/bridge.py`
- `experiments/avatar-bridge/control_service.py`
- `experiments/avatar-bridge/production_client.py`
- `experiments/avatar-bridge/test_bridge_state.py`
- `experiments/avatar-bridge/test_contracts.py`
- `experiments/avatar-bridge/test_ownership_and_routes.py`
- `experiments/avatar-bridge/validate_runtime.py`
- `experiments/hf-speech-to-speech/fixtures/README.md`
- `experiments/persistent-stt-h1/service/stt_service.py`
- `experiments/qwen3-tts-e0/service/tts_service.py`
- `experiments/speech-chain-g0/client/record_once.py`
- `experiments/speech-chain-g0/client/speech_chain_client.py`
- `experiments/speech-chain-g0/stt/transcribe_once.py`
- `experiments/websocket-i0/server/bounded_context.py`
- `experiments/websocket-i0/server/claim_proposals.py`
- `experiments/websocket-i0/server/claim_shadow_extraction.py`
- `experiments/websocket-i0/server/emotion_parser.py`
- `experiments/websocket-i0/server/evidence_store.py`
- `experiments/websocket-i0/server/memory_recall_guard.py`
- `experiments/websocket-i0/server/quality_trace.py`
- `experiments/websocket-i0/server/repetition_guard.py`
- `experiments/websocket-i0/server/reply_quality_guard.py`
- `experiments/websocket-i0/server/stt_evidence.py`
- `experiments/websocket-i0/server/voice_ws_server.py`
- `frontend/eslint.config.mjs`
- `frontend/next-env.d.ts`
- `frontend/next.config.ts`
- `frontend/package-lock.json`
- `frontend/package.json`
- `frontend/public/README.md`
- `frontend/public/live2d/README.md`
- `frontend/src/app/globals.css`
- `frontend/src/app/layout.tsx`
- `frontend/src/app/page.tsx`
- `frontend/src/components/AvatarVideo.tsx`
- `frontend/src/components/Live2DCharacter.tsx`
- `frontend/src/components/VoiceConsole.tsx`
- `frontend/src/lib/avatar-client.ts`
- `frontend/src/lib/expression-controller.ts`
- `frontend/src/lib/mouth-controller.ts`
- `frontend/src/lib/types.ts`
- `frontend/src/lib/websocket.ts`
- `frontend/tsconfig.json`
- `models/README.md`
- `rebuild_config.py`
- `reply_text.py`
- `scripts/avatar-control-run.py`
- `scripts/avatar-control-service.ps1`
- `scripts/avatar-control-service.py`
- `scripts/check-av-diagnostics.py`
- `scripts/check-av-frontend.cjs`
- `scripts/check-conhost-contracts.py`
- `scripts/check-conhost-tts-policy.py`
- `scripts/check-llm-identity-contracts.ps1`
- `scripts/check-productization-conversation.py`
- `scripts/check-productization-ui.cjs`
- `scripts/check-sox-import-probe.py`
- `scripts/check-stage7c-recovery.py`
- `scripts/check-stt-evidence.py`
- `scripts/check-tts-monitor-policy.py`
- `scripts/check-tts-process-evidence.py`
- `scripts/check-tts-reference-array.py`
- `scripts/check-tts-reliability-regressions.py`
- `scripts/check-tts-reliability.py`
- `scripts/check-tts-startup-policy.py`
- `scripts/check-tts-startup-repair.py`
- `scripts/cpu-run.py`
- `scripts/cpu-service.py`
- `scripts/frontend-run.py`
- `scripts/frontend-service.ps1`
- `scripts/frontend-service.py`
- `scripts/livetalking-env.ps1`
- `scripts/livetalking-run.py`
- `scripts/livetalking-service.ps1`
- `scripts/livetalking-service.py`
- `scripts/manual-rebuild.py`
- `scripts/rebuild-llm-profile.py`
- `scripts/rebuild-process-identity.ps1`
- `scripts/rebuild-service.ps1`
- `scripts/rebuild-system.ps1`
- `scripts/rebuild-system.py`
- `scripts/reconcile-stopped-stack.py`
- `scripts/resource-policy.py`
- `scripts/stack-stop-receipts.py`
- `scripts/stage3-check-contracts.py`
- `scripts/stage3-check-process-identity.ps1`
- `scripts/stage6-check-contracts.py`
- `scripts/stage6-frontend-contracts.cjs`
- `scripts/stage7-check-contracts.py`
- `scripts/stage7-frontend-contracts.cjs`
- `scripts/stage7f-check-contracts.py`
- `scripts/stage7f-check-model-contracts.ps1`
- `scripts/stage7h-check-contracts.py`
- `scripts/stage7i-check-contracts.py`
- `scripts/stt-run.py`
- `scripts/stt-service.ps1`
- `scripts/stt-service.py`
- `scripts/tts-process-evidence.py`
- `scripts/tts-run.py`
- `scripts/tts-service.ps1`
- `scripts/tts-service.py`
- `scripts/tts-sox-identity.py`
- `scripts/tts-sox-probe.py`
- `scripts/tts-startup-policy.py`
- `scripts/tts_gpu_monitor.py`
- `scripts/tts_helper_client.py`
- `scripts/tts_helper_lifecycle.py`
- `scripts/tts_nvml.py`
- `scripts/ws-run.py`
- `scripts/ws-service.ps1`
- `scripts/ws-service.py`
- `tools/README.md`

## Complete final candidate file list (191 paths)

| Candidate path | Preparation |
| --- | --- |
| `.gitignore` | Selected source copy; candidate-only privacy/doc adaptation |
| `ARCHITECTURE.md` | Selected source copy; candidate-only privacy/doc adaptation |
| `CHANGELOG.md` | Selected source copy; candidate-only privacy/doc adaptation |
| `DEVELOPMENT_LOG.md` | Selected source copy; candidate-only privacy/doc adaptation |
| `DOCUMENTATION_PLAN.md` | Selected source copy; candidate-only privacy/doc adaptation |
| `KNOWN_ISSUES.md` | Selected source copy; candidate-only privacy/doc adaptation |
| `PORTABILITY_PLAN.md` | Selected source copy; candidate-only privacy/doc adaptation |
| `PUBLICATION_SHA256SUMS.txt` | New candidate documentation / inventory |
| `README.md` | Selected source copy; candidate-only privacy/doc adaptation |
| `README.zh-CN.md` | Selected source copy; candidate-only privacy/doc adaptation |
| `ROADMAP.md` | Selected source copy; candidate-only privacy/doc adaptation |
| `STAGE2C3_PUBLICATION_CANDIDATE_REPORT.md` | New candidate documentation / inventory |
| `Start-LLM-1P7B.cmd` | Byte-identical selected source |
| `Start-Rebuild.cmd` | Byte-identical selected source |
| `Stop-LLM-1P7B.cmd` | Byte-identical selected source |
| `Stop-Rebuild.cmd` | Byte-identical selected source |
| `THIRD_PARTY_NOTICES.md` | Selected source copy; candidate-only privacy/doc adaptation |
| `assets/architecture/SEVEN_SERVICE_ARCHITECTURE.mmd` | Stage5 first-party architecture diagram / editable source |
| `assets/architecture/SEVEN_SERVICE_ARCHITECTURE.png` | Stage5 first-party architecture diagram / editable source |
| `assets/architecture/SEVEN_SERVICE_ARCHITECTURE.svg` | Stage5 first-party architecture diagram / editable source |
| `assets/architecture/SEVEN_SERVICE_ARCHITECTURE_EN.mmd` | Stage5 first-party architecture diagram / editable source |
| `assets/architecture/SEVEN_SERVICE_ARCHITECTURE_EN.png` | Stage5 first-party architecture diagram / editable source |
| `assets/architecture/SEVEN_SERVICE_ARCHITECTURE_EN.svg` | Stage5 first-party architecture diagram / editable source |
| `assets/avatar/README.md` | Byte-identical selected source |
| `assets/live2d/README.md` | Byte-identical selected source |
| `assets/screenshots/s1-initial-interface-preview.jpg` | User-approved real system screenshot / proportional preview |
| `assets/screenshots/s1-initial-interface.jpg` | User-approved real system screenshot / proportional preview |
| `assets/screenshots/s2-listening-preview.jpg` | User-approved real system screenshot / proportional preview |
| `assets/screenshots/s2-listening.jpg` | User-approved real system screenshot / proportional preview |
| `assets/screenshots/s3-chinese-interaction-preview.jpg` | User-approved real system screenshot / proportional preview |
| `assets/screenshots/s3-chinese-interaction.jpg` | User-approved real system screenshot / proportional preview |
| `assets/screenshots/s4-continuous-conversation-preview.jpg` | User-approved real system screenshot / proportional preview |
| `assets/screenshots/s4-continuous-conversation.jpg` | User-approved real system screenshot / proportional preview |
| `assets/screenshots/s5-multilingual-interaction-1-preview.jpg` | User-approved real system screenshot / proportional preview |
| `assets/screenshots/s5-multilingual-interaction-1.jpg` | User-approved real system screenshot / proportional preview |
| `assets/screenshots/s6-multilingual-interaction-2-preview.jpg` | User-approved real system screenshot / proportional preview |
| `assets/screenshots/s6-multilingual-interaction-2.jpg` | User-approved real system screenshot / proportional preview |
| `assets/stt/README.md` | Byte-identical selected source |
| `assets/voice-clone/README.md` | Byte-identical selected source |
| `assets/voice/README.md` | Byte-identical selected source |
| `config/README.md` | Selected source copy; candidate-only privacy/doc adaptation |
| `config/cpu-requirements.lock.txt` | Byte-identical selected source |
| `config/livetalking-requirements.in` | Byte-identical selected source |
| `config/livetalking-requirements.lock.txt` | Byte-identical selected source |
| `config/livetalking-stage4.yaml` | Byte-identical selected source |
| `config/rebuild.example.json` | Byte-identical selected source |
| `config/resource-policy.json` | Byte-identical selected source |
| `config/tts-requirements.lock.txt` | Byte-identical selected source |
| `config/windows-runtime.example.json` | Byte-identical selected source |
| `docs/architecture/WHY_WINDOWS_REBUILD.md` | Byte-identical selected source |
| `docs/demo-limitations.md` | Byte-identical selected source |
| `docs/legacy/demo-stable/README.md` | Byte-identical selected source |
| `docs/legacy/demo-stable/architecture.md` | Byte-identical selected source |
| `docs/legacy/demo-stable/development-phases.md` | Byte-identical selected source |
| `docs/legacy/demo-stable/known-issues.md` | Byte-identical selected source |
| `docs/model-downloads.md` | Byte-identical selected source |
| `docs/privacy.md` | Selected source copy; candidate-only privacy/doc adaptation |
| `docs/release/PUBLICATION_BLOCKERS.md` | Selected source copy; candidate-only privacy/doc adaptation |
| `docs/release/PUBLICATION_FILE_LIST.md` | New candidate documentation / inventory |
| `docs/third-party/EXTERNAL_LIVETALKING.md` | New candidate documentation / inventory |
| `docs/third-party/FILE_CLASSIFICATION.md` | Selected source copy; candidate-only privacy/doc adaptation |
| `docs/third-party/LICENSE_SOURCES.md` | Selected source copy; candidate-only privacy/doc adaptation |
| `docs/third-party/LOCAL_CHANGES.md` | New candidate documentation / inventory |
| `docs/third-party/RUNTIME_SCOPE.md` | Selected source copy; candidate-only privacy/doc adaptation |
| `docs/third-party/licenses/FunASR-MIT.txt` | Byte-identical selected source |
| `docs/third-party/licenses/LiveTalking-Apache-2.0.txt` | Byte-identical selected source |
| `docs/third-party/licenses/Recorder-MIT.txt` | Byte-identical selected source |
| `docs/third-party/licenses/SRS-MIT.txt` | Byte-identical selected source |
| `docs/third-party/licenses/aiortc-BSD-3-Clause.txt` | Byte-identical selected source |
| `docs/third-party/licenses/es6-promise-MIT.txt` | Byte-identical selected source |
| `docs/third-party/licenses/face-alignment-BSD-3-Clause.txt` | Byte-identical selected source |
| `docs/third-party/licenses/mpegts-Apache-2.0.txt` | Byte-identical selected source |
| `docs/validation.md` | Selected source copy; candidate-only privacy/doc adaptation |
| `docs/windows-setup.md` | Selected source copy; candidate-only privacy/doc adaptation |
| `experiments/auto-voice-h0/client/vad_capture.py` | Byte-identical selected source |
| `experiments/auto-voice-h2/client/auto_voice_client.py` | Byte-identical selected source |
| `experiments/auto-voice-h2/client/playback.py` | Byte-identical selected source |
| `experiments/avatar-bridge/audio_adapter.py` | Byte-identical selected source |
| `experiments/avatar-bridge/bridge.py` | Byte-identical selected source |
| `experiments/avatar-bridge/control_service.py` | Byte-identical selected source |
| `experiments/avatar-bridge/production_client.py` | Byte-identical selected source |
| `experiments/avatar-bridge/test_bridge_state.py` | Byte-identical selected source |
| `experiments/avatar-bridge/test_contracts.py` | Byte-identical selected source |
| `experiments/avatar-bridge/test_ownership_and_routes.py` | Byte-identical selected source |
| `experiments/avatar-bridge/validate_runtime.py` | Byte-identical selected source |
| `experiments/hf-speech-to-speech/fixtures/README.md` | Byte-identical selected source |
| `experiments/persistent-stt-h1/service/stt_service.py` | Byte-identical selected source |
| `experiments/qwen3-tts-e0/service/tts_service.py` | Byte-identical selected source |
| `experiments/speech-chain-g0/client/record_once.py` | Byte-identical selected source |
| `experiments/speech-chain-g0/client/speech_chain_client.py` | Byte-identical selected source |
| `experiments/speech-chain-g0/stt/transcribe_once.py` | Byte-identical selected source |
| `experiments/websocket-i0/server/bounded_context.py` | Byte-identical selected source |
| `experiments/websocket-i0/server/claim_proposals.py` | Byte-identical selected source |
| `experiments/websocket-i0/server/claim_shadow_extraction.py` | Byte-identical selected source |
| `experiments/websocket-i0/server/emotion_parser.py` | Byte-identical selected source |
| `experiments/websocket-i0/server/evidence_store.py` | Byte-identical selected source |
| `experiments/websocket-i0/server/memory_recall_guard.py` | Byte-identical selected source |
| `experiments/websocket-i0/server/quality_trace.py` | Byte-identical selected source |
| `experiments/websocket-i0/server/repetition_guard.py` | Byte-identical selected source |
| `experiments/websocket-i0/server/reply_quality_guard.py` | Byte-identical selected source |
| `experiments/websocket-i0/server/stt_evidence.py` | Byte-identical selected source |
| `experiments/websocket-i0/server/voice_ws_server.py` | Byte-identical selected source |
| `frontend/eslint.config.mjs` | Byte-identical selected source |
| `frontend/next-env.d.ts` | Byte-identical selected source |
| `frontend/next.config.ts` | Byte-identical selected source |
| `frontend/package-lock.json` | Byte-identical selected source |
| `frontend/package.json` | Byte-identical selected source |
| `frontend/public/README.md` | Byte-identical selected source |
| `frontend/public/live2d/README.md` | Byte-identical selected source |
| `frontend/src/app/globals.css` | Byte-identical selected source |
| `frontend/src/app/layout.tsx` | Byte-identical selected source |
| `frontend/src/app/page.tsx` | Byte-identical selected source |
| `frontend/src/components/AvatarVideo.tsx` | Byte-identical selected source |
| `frontend/src/components/Live2DCharacter.tsx` | Byte-identical selected source |
| `frontend/src/components/VoiceConsole.tsx` | Byte-identical selected source |
| `frontend/src/lib/avatar-client.ts` | Byte-identical selected source |
| `frontend/src/lib/expression-controller.ts` | Byte-identical selected source |
| `frontend/src/lib/mouth-controller.ts` | Byte-identical selected source |
| `frontend/src/lib/types.ts` | Byte-identical selected source |
| `frontend/src/lib/websocket.ts` | Byte-identical selected source |
| `frontend/tsconfig.json` | Byte-identical selected source |
| `models/README.md` | Byte-identical selected source |
| `rebuild_config.py` | Byte-identical selected source |
| `reply_text.py` | Byte-identical selected source |
| `scripts/avatar-control-run.py` | Byte-identical selected source |
| `scripts/avatar-control-service.ps1` | Byte-identical selected source |
| `scripts/avatar-control-service.py` | Byte-identical selected source |
| `scripts/check-av-diagnostics.py` | Byte-identical selected source |
| `scripts/check-av-frontend.cjs` | Byte-identical selected source |
| `scripts/check-conhost-contracts.py` | Byte-identical selected source |
| `scripts/check-conhost-tts-policy.py` | Byte-identical selected source |
| `scripts/check-llm-identity-contracts.ps1` | Byte-identical selected source |
| `scripts/check-productization-conversation.py` | Byte-identical selected source |
| `scripts/check-productization-ui.cjs` | Byte-identical selected source |
| `scripts/check-sox-import-probe.py` | Byte-identical selected source |
| `scripts/check-stage7c-recovery.py` | Byte-identical selected source |
| `scripts/check-stt-evidence.py` | Byte-identical selected source |
| `scripts/check-tts-monitor-policy.py` | Selected source copy; candidate-only privacy/doc adaptation |
| `scripts/check-tts-process-evidence.py` | Byte-identical selected source |
| `scripts/check-tts-reference-array.py` | Byte-identical selected source |
| `scripts/check-tts-reliability-regressions.py` | Byte-identical selected source |
| `scripts/check-tts-reliability.py` | Byte-identical selected source |
| `scripts/check-tts-startup-policy.py` | Byte-identical selected source |
| `scripts/check-tts-startup-repair.py` | Byte-identical selected source |
| `scripts/cpu-run.py` | Byte-identical selected source |
| `scripts/cpu-service.py` | Byte-identical selected source |
| `scripts/frontend-run.py` | Byte-identical selected source |
| `scripts/frontend-service.ps1` | Byte-identical selected source |
| `scripts/frontend-service.py` | Byte-identical selected source |
| `scripts/livetalking-env.ps1` | Byte-identical selected source |
| `scripts/livetalking-run.py` | Byte-identical selected source |
| `scripts/livetalking-service.ps1` | Byte-identical selected source |
| `scripts/livetalking-service.py` | Byte-identical selected source |
| `scripts/manual-rebuild.py` | Byte-identical selected source |
| `scripts/rebuild-llm-profile.py` | Byte-identical selected source |
| `scripts/rebuild-process-identity.ps1` | Byte-identical selected source |
| `scripts/rebuild-service.ps1` | Byte-identical selected source |
| `scripts/rebuild-system.ps1` | Byte-identical selected source |
| `scripts/rebuild-system.py` | Byte-identical selected source |
| `scripts/reconcile-stopped-stack.py` | Byte-identical selected source |
| `scripts/resource-policy.py` | Byte-identical selected source |
| `scripts/stack-stop-receipts.py` | Byte-identical selected source |
| `scripts/stage3-check-contracts.py` | Byte-identical selected source |
| `scripts/stage3-check-process-identity.ps1` | Byte-identical selected source |
| `scripts/stage6-check-contracts.py` | Byte-identical selected source |
| `scripts/stage6-frontend-contracts.cjs` | Byte-identical selected source |
| `scripts/stage7-check-contracts.py` | Byte-identical selected source |
| `scripts/stage7-frontend-contracts.cjs` | Byte-identical selected source |
| `scripts/stage7f-check-contracts.py` | Byte-identical selected source |
| `scripts/stage7f-check-model-contracts.ps1` | Byte-identical selected source |
| `scripts/stage7h-check-contracts.py` | Byte-identical selected source |
| `scripts/stage7i-check-contracts.py` | Byte-identical selected source |
| `scripts/stt-run.py` | Byte-identical selected source |
| `scripts/stt-service.ps1` | Byte-identical selected source |
| `scripts/stt-service.py` | Byte-identical selected source |
| `scripts/tts-process-evidence.py` | Byte-identical selected source |
| `scripts/tts-run.py` | Byte-identical selected source |
| `scripts/tts-service.ps1` | Byte-identical selected source |
| `scripts/tts-service.py` | Byte-identical selected source |
| `scripts/tts-sox-identity.py` | Byte-identical selected source |
| `scripts/tts-sox-probe.py` | Byte-identical selected source |
| `scripts/tts-startup-policy.py` | Byte-identical selected source |
| `scripts/tts_gpu_monitor.py` | Byte-identical selected source |
| `scripts/tts_helper_client.py` | Byte-identical selected source |
| `scripts/tts_helper_lifecycle.py` | Byte-identical selected source |
| `scripts/tts_nvml.py` | Byte-identical selected source |
| `scripts/ws-run.py` | Byte-identical selected source |
| `scripts/ws-service.ps1` | Byte-identical selected source |
| `scripts/ws-service.py` | Byte-identical selected source |
| `third_party/README.md` | New candidate documentation / inventory |
| `tools/README.md` | Byte-identical selected source |

## Complete source paths absent from candidate

These are exclusions relative to full MigrationReview, not deletions from it. Ancestor old-version files may separately be absent from the active candidate tree while remaining in Git history.

- `.env.example`
- `STAGE2A_SOURCE_MIGRATION_REPORT.md`
- `STAGE2B_PUBLICATION_READINESS_REPORT.md`
- `STAGE2C1_FRONTEND_SECURITY_REPORT.md`
- `STAGE2C2_THIRD_PARTY_PUBLICATION_REPORT.md`
- `runtime/.gitkeep`
- `third_party/LiveTalking/LICENSE`
- `third_party/LiveTalking/README-EN.md`
- `third_party/LiveTalking/README.md`
- `third_party/LiveTalking/UPSTREAM.md`
- `third_party/LiveTalking/app.py`
- `third_party/LiveTalking/avatars/__init__.py`
- `third_party/LiveTalking/avatars/audio_features/__init__.py`
- `third_party/LiveTalking/avatars/audio_features/base_asr.py`
- `third_party/LiveTalking/avatars/audio_features/hubert.py`
- `third_party/LiveTalking/avatars/audio_features/mel.py`
- `third_party/LiveTalking/avatars/audio_features/whisper.py`
- `third_party/LiveTalking/avatars/base_avatar.py`
- `third_party/LiveTalking/avatars/wav2lip/audio.py`
- `third_party/LiveTalking/avatars/wav2lip/face_detection/README.md`
- `third_party/LiveTalking/avatars/wav2lip/face_detection/__init__.py`
- `third_party/LiveTalking/avatars/wav2lip/face_detection/api.py`
- `third_party/LiveTalking/avatars/wav2lip/face_detection/detection/__init__.py`
- `third_party/LiveTalking/avatars/wav2lip/face_detection/detection/core.py`
- `third_party/LiveTalking/avatars/wav2lip/face_detection/detection/sfd/__init__.py`
- `third_party/LiveTalking/avatars/wav2lip/face_detection/detection/sfd/bbox.py`
- `third_party/LiveTalking/avatars/wav2lip/face_detection/detection/sfd/detect.py`
- `third_party/LiveTalking/avatars/wav2lip/face_detection/detection/sfd/net_s3fd.py`
- `third_party/LiveTalking/avatars/wav2lip/face_detection/detection/sfd/sfd_detector.py`
- `third_party/LiveTalking/avatars/wav2lip/face_detection/models.py`
- `third_party/LiveTalking/avatars/wav2lip/face_detection/utils.py`
- `third_party/LiveTalking/avatars/wav2lip/genavatar.py`
- `third_party/LiveTalking/avatars/wav2lip/hparams.py`
- `third_party/LiveTalking/avatars/wav2lip/inference_silence.py`
- `third_party/LiveTalking/avatars/wav2lip/models/__init__.py`
- `third_party/LiveTalking/avatars/wav2lip/models/conv.py`
- `third_party/LiveTalking/avatars/wav2lip/models/syncnet.py`
- `third_party/LiveTalking/avatars/wav2lip/models/wav2lip.py`
- `third_party/LiveTalking/avatars/wav2lip/models/wav2lip_v2.py`
- `third_party/LiveTalking/avatars/wav2lip_avatar.py`
- `third_party/LiveTalking/config.py`
- `third_party/LiveTalking/config.yaml`
- `third_party/LiveTalking/docs/admin_api.md`
- `third_party/LiveTalking/docs/api.md`
- `third_party/LiveTalking/docs/avatar_api.md`
- `third_party/LiveTalking/docs/virtualcam_guide.md`
- `third_party/LiveTalking/llm.py`
- `third_party/LiveTalking/registry.py`
- `third_party/LiveTalking/requirements.txt`
- `third_party/LiveTalking/server/__init__.py`
- `third_party/LiveTalking/server/asr_server.py`
- `third_party/LiveTalking/server/audio_turns.py`
- `third_party/LiveTalking/server/avatar_routes.py`
- `third_party/LiveTalking/server/routes.py`
- `third_party/LiveTalking/server/rtc_manager.py`
- `third_party/LiveTalking/server/session_manager.py`
- `third_party/LiveTalking/server/task_manager.py`
- `third_party/LiveTalking/server/webrtc.py`
- `third_party/LiveTalking/streamout/__init__.py`
- `third_party/LiveTalking/streamout/base_output.py`
- `third_party/LiveTalking/streamout/rtmp.py`
- `third_party/LiveTalking/streamout/virtualcam.py`
- `third_party/LiveTalking/streamout/webrtc.py`
- `third_party/LiveTalking/tts/__init__.py`
- `third_party/LiveTalking/tts/azure.py`
- `third_party/LiveTalking/tts/base_tts.py`
- `third_party/LiveTalking/tts/doubao.py`
- `third_party/LiveTalking/tts/edge.py`
- `third_party/LiveTalking/tts/external.py`
- `third_party/LiveTalking/tts/omnitts.py`
- `third_party/LiveTalking/tts/qwentts.py`
- `third_party/LiveTalking/tts/sovits.py`
- `third_party/LiveTalking/tts/tencent.py`
- `third_party/LiveTalking/tts/xtts.py`
- `third_party/LiveTalking/utils/async_utils.py`
- `third_party/LiveTalking/utils/audio.py`
- `third_party/LiveTalking/utils/audioutil.py`
- `third_party/LiveTalking/utils/device.py`
- `third_party/LiveTalking/utils/image.py`
- `third_party/LiveTalking/utils/logger.py`
- `third_party/LiveTalking/utils/realtime_diagnostics.py`
- `third_party/LiveTalking/web/admin-en.html`
- `third_party/LiveTalking/web/admin.html`
- `third_party/LiveTalking/web/asr/index.html`
- `third_party/LiveTalking/web/asr/main.js`
- `third_party/LiveTalking/web/asr/pcm.js`
- `third_party/LiveTalking/web/asr/recorder-core.js`
- `third_party/LiveTalking/web/asr/wav.js`
- `third_party/LiveTalking/web/asr/wsconnecter.js`
- `third_party/LiveTalking/web/avatar-en.html`
- `third_party/LiveTalking/web/avatar.html`
- `third_party/LiveTalking/web/client.js`
- `third_party/LiveTalking/web/dashboard.html`
- `third_party/LiveTalking/web/index-en.html`
- `third_party/LiveTalking/web/index-whep.html`
- `third_party/LiveTalking/web/index.html`
- `third_party/LiveTalking/web/mpegts-1.7.3.min.js`
- `third_party/LiveTalking/web/rtcpushapi.html`
- `third_party/LiveTalking/web/rtcpushchat.html`
- `third_party/LiveTalking/web/rtmpapi.html`
- `third_party/LiveTalking/web/rtmpchat.html`
- `third_party/LiveTalking/web/srs.sdk.js`
- `third_party/LiveTalking/web/tts/index-en.html`
- `third_party/LiveTalking/web/tts/index.html`
- `third_party/LiveTalking/web/virtualcam.html`
- `third_party/LiveTalking/web/webrtcapi-asr.html`
- `third_party/LiveTalking/web/webrtcapi.html`
- `third_party/LiveTalking/web/whep.js`
