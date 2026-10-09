# Privacy and Local Data Handling

Demo Stable v0.9 is designed for one user on one Windows computer. Its stable LLM path is local, and application services bind to loopback addresses. This reduces data exposure, but users still need to manage recordings, transcripts, voice references, generated speech, and logs carefully.

## Data-flow summary

For one turn, the system may process:

1. live microphone audio;
2. a temporary utterance WAV or in-memory audio buffer;
3. recognized user text;
4. local conversation context;
5. locally generated assistant text;
6. a generated TTS WAV;
7. browser playback metrics and acknowledgements.

The stable pipeline does not require a cloud LLM. Model downloads are separate setup actions and are not part of an ordinary conversation turn.

## Microphone audio

- The microphone should open only during the explicit listening state.
- Half-duplex behavior closes listening before assistant playback.
- Temporary utterance audio should be stored only in the configured ignored runtime directory when file-based handoff is required.
- Debug recording must be opt-in, clearly indicated, and easy to delete.
- Raw microphone audio must never be committed to Git.

## Transcripts and conversation text

Transcripts and assistant replies can contain personal information even when no audio is retained.

- Persistent event logging should be disabled or minimized in the public Demo Stable default.
- If debug logging is enabled, use a clear local location and retention policy.
- Do not include real conversation logs in bug reports, screenshots, tests, or commits.
- Use fictional sanitized fixtures for protocol and UI tests.
- Remove usernames, absolute paths, session identifiers, and conversation text before sharing diagnostics.

## Voice cloning

The reference voice recording and exact transcript are sensitive biometric-like personal data.

- Use only a voice for which the user has authorization and informed consent.
- Keep the WAV and transcript outside Git tracking.
- Do not place them in example configuration or documentation.
- Do not upload them to issue trackers or model-hosting services as part of this project.
- Treat any derived prompt, embedding, and cache as private. Generated samples remain private unless separately approved; the current approved generated cloned-voice media has public display authorization, but that approval does not cover reference or derived private artifacts.
- Provide a documented deletion procedure for local reference and generated files.

## Generated audio

TTS output can reveal both the assistant text and the reference voice identity.

- Store generated WAV files only in the ignored runtime directory.
- Delete warm-up and conversation output after testing when it is no longer needed.
- Do not publish generated samples without checking voice consent, content, and asset rights. Those checks have been completed for the current approved recruitment/demo and portfolio media only.

## Live2D and visual assets

Character models may have license and identity restrictions separate from the source code.

- Keep source model files private and outside Git unless repository redistribution is separately authorized.
- Public display authorization is confirmed for the current tested character in screenshots, GIFs, recruitment videos, project demo videos, and portfolio/recruitment presentations.
- Treat display authorization and repository redistribution as separate rights; the current source model assets remain excluded.
- Do not assume the rendering library license grants rights to character assets or Cubism Core.

## Local network exposure

All v0.9 services should bind to `127.0.0.1` only. The WebSocket handshake should allow only the configured local frontend origin.

Do not:

- bind the demo to `0.0.0.0`;
- forward its ports through a router, tunnel, or remote-development service;
- expose model or TTS endpoints to a local network;
- treat loopback binding as production authentication.

Other software running on the same computer may still attempt to reach local ports. Run the demo only on a trusted personal machine.

## Public repository exclusions

The public repository must exclude:

- `.env` and machine-specific configuration;
- private voice-reference audio and transcript;
- raw/processed microphone recordings;
- generated TTS audio;
- conversation/event logs;
- model weights and caches;
- PID and temporary files;
- personal machine environment reports;
- user-profile paths and names;
- Live2D source model assets and Cubism Core runtime.

## Before sharing logs or screenshots

Check for:

- user or account names;
- absolute Windows paths;
- microphone/device names;
- recognized speech and assistant replies;
- model cache paths;
- process IDs and session IDs;
- browser extensions or unrelated tabs;
- visible private character/voice assets.

When in doubt, reproduce the issue with fictional test text and a non-private fixture.

## Deletion checklist

To remove local conversation artifacts:

1. stop all project services;
2. clear the configured runtime input/output directories;
3. clear debug/event logs;
4. remove temporary browser downloads if any;
5. remove private voice assets only if the user intends to revoke or reset the voice configuration;
6. verify that deleted artifacts were never added to Git history or a cloud backup.

This project does not claim secure deletion from storage media or backups.
