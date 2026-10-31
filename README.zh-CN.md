# 本地语音交互AI系统（Local Voice-Interactive AI System）

> **这是Windows Rebuild的公开集成源码候选，不是开箱即用的完整运行包。** 保留第一方管理器、接口、前端与阶段式文档；完整LiveTalking vendor树、全部CONDITIONAL/BLOCKED文件、三个待确认本地新增及修改补丁均未分发。READY文件也未组成半套运行树。取得未修改上游不能恢复所需的11项改动和3项新增。
>
> 原本地系统的八轮等人工功能事实保留，不能转移为本候选验收。Stage2C1在完整迁移副本完成的前端安全/构建检查仅为既有证据；本候选未安装、构建或运行。Q-001/Q-002 OPEN，长期稳定和独立恢复未验收。见[完整文件清单](docs/release/PUBLICATION_FILE_LIST.md)、[外部集成边界](docs/third-party/EXTERNAL_LIVETALKING.md)与[发布门槛](docs/release/PUBLICATION_BLOCKERS.md)。

[English](README.md)

本项目在原生Windows本机连接语音检测、识别、语言模型、声音克隆和音频驱动视频数字人，面向单用户半双工交互，不是公网多用户服务。

**冻结基线：Windows Functional Stable Candidate v1.0-rc1 — Known Quality Issues。Q-001、Q-002均为OPEN。** 功能流程通过不等于完整对话质量、长期稳定性或独立恢复通过。

## 当前迁移状态

Windows Rebuild是当前目标架构和开发阶段名称，不是新的正式项目名。公开候选只携带许可白名单中的第一方工程与说明。Stage2C1在完整迁移副本已通过前端安全/静态构建检查；本候选未安装、构建、七服务运行或独立恢复。完整运行包的授权和恢复仍BLOCKED，详见[当前门槛](docs/release/PUBLICATION_BLOCKERS.md)。

原本地开发系统已有七服务联启、首次点击、数字人连续8轮流程、主动结束、WAV回退及安全关闭人工功能反馈；不能将这些直接写成公开克隆已经运行成功。当前工作源码含冻结后默认关闭的STT取证补丁，不等于冻结ZIP原件。

## 七服务与语音链

| 服务 | 端口 | 当前实现 |
| --- | ---: | --- |
| 前端 | 3000 | Next.js生产前端 |
| Avatar控制器 | 8011 | 本地会话、音频提交和播放控制 |
| TTS | 8765 | Qwen3-TTS 0.6B Base CUDA声音克隆 |
| 视频数字人 | 8010 | LiveTalking + Wav2Lip256，25FPS配置 |
| LLM | 8081 | Qwen3-1.7B Q4_K_M、llama.cpp CPU-only、4096上下文 |
| STT | 8766 | Faster-Whisper Small CPU INT8 |
| WebSocket/VAD | 8767 | Python编排及Silero VAD |

默认路径是VAD→STT→1.7B→TTS→Avatar音频桥→LiveTalking/Wav2Lip→WebRTC。浏览器WAV备用播放保留在高级设置。系统控制听说顺序，普通会话不因六轮自动结束，历史仍有界；不代表无限记忆、全双工打断或流式逐token合成。

## 使用前提

先读[Windows准备与恢复说明](docs/windows-setup.md)、[模型/素材](docs/model-downloads.md)及[隐私](docs/privacy.md)。本仓库不含权重、二进制、三套Python环境、参考声音/文本、Avatar帧和前端生产构建，不能克隆后直接启动。

完成全部门槛和合法本地准备后，正式入口为`Start-Rebuild.cmd`与`Stop-Rebuild.cmd`，页面为`http://127.0.0.1:3000`。用户点击一次“连接并开始对话”完成连接和音频解锁，点击“结束对话”停止会话。这是原基线的操作方式，不是授权本轮运行不完整副本；必须保留资源预检、持续监护和严格进程归属。

## 历史与贡献

早期Demo Stable已实现本地语音链、Live2D/Browser Audio/RMS、ACK及1/2/6轮功能验证，是后续工作的有效基线。新路线改变数字人呈现和传输职责，复用既有组件和工程经验；不以贬低旧版解释重构。

[七阶段开发日志](DEVELOPMENT_LOG.md)同时覆盖环境/模型、语音链、早期数字人、Demo Stable验证、Rebuild决策、实现及质量调查。[旧版说明](docs/legacy/demo-stable/README.md)与[重构原因](docs/architecture/WHY_WINDOWS_REBUILD.md)保留技术事实；原七次Git提交和时间不变，v0.9.1仅按已确认的文档修订定位说明。

## 已知问题与发布边界

Q-001：个别漏识别/替换有原声确认，早前多轮恶化根因未知。Q-002：历史存在重试后仍重复；后来六轮未复现且未触发重试，不能宣布解决。长期稳定性、完整异常恢复和独立重建未完成。详见[已知问题](KNOWN_ISSUES.md)和[验收分层](docs/validation.md)。

原创源码/文档继续Copyright © 2026 Enhua Liu，All rights reserved。第三方各有条款；顶层Apache-2.0不能覆盖全部Wav2Lip派生代码、模型、声音或人物素材。展示权不等于再分发权。[许可与阻塞](docs/release/PUBLICATION_BLOCKERS.md)核定前不发布当前第三方树或新Demo媒体。
