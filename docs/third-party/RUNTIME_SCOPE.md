# 本地语音交互AI系统（Local Voice-Interactive AI System）— Candidate runtime scope

First-party managers/coordinator, native process/resource protection, VAD/STT/LLM/TTS interfaces, bounded context, audio bridge/controller, Next.js/WebRTC client and browser-WAV fallback are retained. Their presence does not make the candidate fully runnable.

Every LiveTalking/Wav2Lip/face_alignment/sample-JS implementation and all 3 uncleared additions are excluded. The designed runtime needs mel/audio/hparams/model v2/conv plus the SyncNet import, RTC/session tracks, external-TTS registration and prepared Avatar assets. These have not been replaced by stubs or patches; base upstream also lacks the 11 local modifications.

In the full source, Avatar detection/preprocessing and other TTS/transports/web samples were optional operations, but setup imported some routes/ASR helpers and registered a static web directory. This candidate does not try to construct a working partial vendor runtime: the whole tree is absent, and no reduced-runtime PASS is claimed.

Python environments, cut-down VAD source, model/tool files, STT fixture, reference voice and Avatar/scene assets remain external or unresolved. Missing assets and code are documented restoration blockers, not reasons to reduce protection. [Inventory](FILE_CLASSIFICATION.md) and [external source boundary](EXTERNAL_LIVETALKING.md) explain exclusions. No model/service/build/voice tests were run.
