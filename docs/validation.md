# 本地语音交互AI系统（Local Voice-Interactive AI System）— Validation boundaries

| Evidence | Actual status |
| --- | --- |
| Demo Stable | Original 1/2/6-turn functional evidence; seven Git ancestors and phase documents preserved. |
| Original Windows Rebuild | User-confirmed seven services, first click, eight-turn avatar flow, manual end, WAV fallback and safe stop; functional scope only. |
| Frozen rc1 | Windows Functional Stable Candidate v1.0-rc1 — Known Quality Issues; Q-001/Q-002 OPEN; archive untouched. |
| Full MigrationReview Stage2C1 | Recorded full/prod audit zero groups, ESLint/TS/Webpack PASS; no public-clone runtime acceptance. |
| This candidate | Static file/history/hash/privacy/syntax/link review only; no installation, build, HTTP/model/service start or speech test. |
| Independent restore/long-term stability | Not accepted. Required vendor/local changes/assets absent or uncleared. |

Default-off post-freeze STT evidence capability and Stage2C1 security dependencies are retained; this is not byte-identical to the frozen ZIP. Some carried contract scripts need excluded runtime/before snapshots, vendor modules or installed environments. They are engineering evidence, not a self-contained executable test suite. This round parses/compiles text only, never imports or runs these scripts.

See [file list](release/PUBLICATION_FILE_LIST.md), [report](../STAGE2C3_PUBLICATION_CANDIDATE_REPORT.md), [external restrictions](third-party/EXTERNAL_LIVETALKING.md). Static success is not full runtime or quality acceptance.
