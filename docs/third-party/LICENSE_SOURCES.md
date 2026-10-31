# 本地语音交互AI系统（Local Voice-Interactive AI System）— License evidence

**Candidate scope:** associated runtime source is excluded. Historical references to local/upstream files below describe full MigrationReview, not bundled code. Texts do not clear unverified derivatives. See [current exclusions](FILE_CLASSIFICATION.md).

Stage 2C-2 bounded review, 2026-10-30. These are verbatim official license texts, not grants over an unverified derivative. Copyright, conditions and disclaimers are preserved. Adding a text alone does not clear a CONDITIONAL/BLOCKED file. No model/service execution.

| Text in licenses/ | Official revision/tag | Official source | SHA-256 of bytes |
| --- | --- | --- | --- |
| [LiveTalking-Apache-2.0.txt](licenses/LiveTalking-Apache-2.0.txt) | `c7269433a2b6ecebcd9342445d2ecc882c98b0da` | [Official text](https://raw.githubusercontent.com/lipku/LiveTalking/c7269433a2b6ecebcd9342445d2ecc882c98b0da/LICENSE) | `6b934ce628eac39c44f6401b52efc0884db51c937777f1122f0b56648813f0b6` |
| [face-alignment-BSD-3-Clause.txt](licenses/face-alignment-BSD-3-Clause.txt) | `608505febb47082eb83c2e54254294b3044d976f` | [Official text](https://raw.githubusercontent.com/1adrianb/face-alignment/608505febb47082eb83c2e54254294b3044d976f/LICENSE) | `cc001863f05fce94105ec8488ee55a273e1a85bffc788920705c63f2e7aeac0f` |
| [Recorder-MIT.txt](licenses/Recorder-MIT.txt) | `74180842defbcf1cf3c8bccabceb3cc0faed5b6f` | [Official text](https://raw.githubusercontent.com/xiangyuecn/Recorder/74180842defbcf1cf3c8bccabceb3cc0faed5b6f/LICENSE) | `1f973bafdf4edbb0b1e6c8005d4d0cc70160752904e9440f69f59427c885c5e2` |
| [FunASR-MIT.txt](licenses/FunASR-MIT.txt) | `dd00b0e42261b628466037f3a522d713399360b6` | [Official text](https://raw.githubusercontent.com/modelscope/FunASR/dd00b0e42261b628466037f3a522d713399360b6/LICENSE) | `f382b62dcc61fc566b9215b1e3b604b539bfd96ed52ae1eeff5090f6dc176057` |
| [SRS-MIT.txt](licenses/SRS-MIT.txt) | `ab03c94b0744ab392320253ad1767b21b6c82a59` | [Official text](https://raw.githubusercontent.com/ossrs/srs/ab03c94b0744ab392320253ad1767b21b6c82a59/LICENSE) | `31a0846e96dd64de65e386b48989a3c55994435cca89347d978e3e6bfa109631` |
| [mpegts-Apache-2.0.txt](licenses/mpegts-Apache-2.0.txt) | `v1.7.3` | [Official text](https://raw.githubusercontent.com/xqq/mpegts.js/v1.7.3/LICENSE) | `58d1e17ffe5109a7ae296caafcadfdbe6a7d176f0bc4ab01e12a689b0499d8bd` |
| [es6-promise-MIT.txt](licenses/es6-promise-MIT.txt) | `f97e2666e6928745c450752e74213d2438b48b4c` | [Official text](https://raw.githubusercontent.com/stefanpenner/es6-promise/f97e2666e6928745c450752e74213d2438b48b4c/LICENSE) | `da852e222c72bc04a0a9046aac35f2e5d33775a8ea9f1d8f59b1cfd195ef9bb0` |
| [aiortc-BSD-3-Clause.txt](licenses/aiortc-BSD-3-Clause.txt) | `1.14.0` | [Official text](https://raw.githubusercontent.com/aiortc/aiortc/1.14.0/LICENSE) | `bec75b5a59bbf89e979e4cb764775eb7b5d0167c5e907139e6f9953698c811b6` |

In the full MigrationReview only, LiveTalking LICENSE byte-matches pinned upstream. This candidate has no vendor root; the unchanged text under licenses/ is evidence only. No standalone upstream NOTICE was present in the fixed tree checked in Stage 2A; this is a downstream provenance record, not an upstream-authored NOTICE. Preserve original source headers in addition to full texts. Do not replace copyright holders with the project name.

## Evidence keys and limits

- LT: LiveTalking c7269433a2b6ecebcd9342445d2ecc882c98b0da, LICENSE and README/README-EN. Apache-2.0 covers applicable original portions, not unrelated embedded material.
- W2L: [Wav2Lip fixed README](https://github.com/Rudrabha/Wav2Lip/blob/bac9a81e63ecc153202353372e5724b83d9e6322/README.md), License and Citation / Disclaimer / Acknowledgments. Personal/research/non-commercial restrictions and commercial contact route are recorded; no blanket public redistribution grant established. Full README retained only in ignored audit evidence; it is not relabeled as a permissive license.
- FA: local face_detection/README.md attributes face_alignment; __init__.py names Adrian Bulat and version 1.0.1. Official BSD text establishes upstream terms, not every fork's history, batching changes or S3FD weight rights.
- SRS: local srs.sdk.js retains Winlin 2013-2021 copyright and MIT SPDX. The current full MIT does not prove the precise historical snapshot; preserve both original header and full text.
- REC: recorder-core.js/pcm.js/wav.js identify xiangyuecn/Recorder; official MIT text supplied, old copy not exact-matched.
- FUN: main.js/wsconnecter.js retain FunASR MIT heading and contributor credits. Current 2025 copyright does not replace historical 2021-2023 local headings.
- MPEGTS/ES6: bundle name 1.7.3 and embedded es6-promise v4.2.8+1e68dce6 header identify likely components; exact bundle/build and complete embedded notices remain unverified. mpegts license is pinned to the official tag plus content hash, not a claim the local bundle is byte-identical.
- RTC: aiortc 1.14.0 BSD license and examples/server/client.js, src/aiortc/contrib/media.py reviewed for player/example structure. Exact historical derivative attribution remains unproven; this is not an assertion that the local files were copied from that tag.
- LOCAL: three additions absent from fixed upstream; local hashes establish carriage, not an express publication license. No root project LICENSE supplies an assumed grant.

## Public media and asset boundary

Fixed local LiveTalking README.md line 240 / README-EN.md line 231 asks public-platform videos to retain LiveTalking watermark/logo. Record this separately from Apache source-license duties; do not claim it changes Apache's terms or grants trademark endorsement. Source availability, personal use, non-commercial portfolio display, public source redistribution, weight distribution and commercial operation are different permissions. Portfolio/recruitment display is not automatically cleared by a personal-use statement.

No model, voice, Avatar media, raw trace, hardware identifier or recording is included in these license records. Other installed Python/npm/binary dependencies are not certified as a redistributable environment image by this bounded vendor review.
