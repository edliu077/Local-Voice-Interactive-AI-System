# 本地语音交互AI系统（Local Voice-Interactive AI System）— Excluded local modifications and additions

The full MigrationReview carries 11 upstream modifications and 3 additions. None of their implementations or upstream-context patches is bundled here. This document contains source metadata/descriptions only, not an authorization grant. The 11 modified paths are app.py, avatars/audio_features/base_asr.py, avatars/audio_features/mel.py, avatars/base_avatar.py, avatars/wav2lip/genavatar.py, avatars/wav2lip_avatar.py, server/routes.py, server/rtc_manager.py, server/webrtc.py, streamout/webrtc.py and utils/logger.py, relative to the excluded vendor tree. An unmodified upstream checkout cannot reproduce the integrated local system.

| Excluded addition | Individual static review | Decision |
| --- | --- | --- |
| server/audio_turns.py | Audio ledger/cancellation logic; only standard-library re/threading/uuid imports. | Excluded: structural separation does not prove authorship or publication rights. |
| tts/external.py | External-audio adapter uses upstream registry/decorator API. | Excluded: API coupling and absent grant remain; no implementation published. |
| utils/realtime_diagnostics.py | Bounded queue/logging metrics; standard-library imports. | Excluded: structural separation is not an independent origin/license proof. |

A bounded token comparison against the other carried upstream-origin Python files found short/common longest contiguous sequences of 7/10/14 tokens respectively. This is neither an exhaustive copying test nor evidence that no derivative material exists. No blanket Apache grant or invented copyright is added. Exact source hashes appear in the excluded inventory. No full code, source patch, runtime evidence or private media is copied.
