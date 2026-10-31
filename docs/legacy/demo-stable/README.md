# 本地语音交互AI系统（Local Voice-Interactive AI System）— Demo Stable历史

本文是早期Demo Stable的阶段式历史摘要，不是新版Windows Rebuild运行指南。Windows Rebuild是后续开发阶段名称，项目正式名称保持不变。

## 历史基准与版本含义

早期公开源码基准为提交[`3bacd16bf2b647bf7ace0fb0d05450d1f205219f`](https://github.com/edliu077/Local-Voice-Interactive-AI-System/tree/3bacd16bf2b647bf7ace0fb0d05450d1f205219f)。该提交及其六个祖先提交保留原内容、父子关系和提交时间。

- **Demo Stable / Recruitment Preview v0.9**：经过目标设备人工功能回归的早期语音交互基线。
- **Documentation Revision v0.9.1**：原DOCUMENTATION_PLAN中的文档修订标识，不据此宣称另有独立运行版或既存Git Tag。
- 后续版权、外部资源证据和文档修订也保留在原提交链中；文档修订号不自动等于软件发行号。
- 本次迁移准备没有创建Tag或新提交。完整私人开发过程并非全部存在于这七次公开包装提交中，不为早期阶段补造Git记录。

## 已实现与已验证的成果

早期基线在Windows 11、RTX 4060 Laptop 8GB VRAM、16GB RAM目标设备上，完成了Silero VAD → Faster-Whisper Small CPU INT8 → Qwen3-1.7B Q4_K_M / llama.cpp CPU → Qwen3-TTS 0.6B Base CUDA的本地语音链路。

浏览器通过Next.js生产前端和本地WebSocket显示状态、字幕并播放WAV；Live2D使用最终浏览器播放信号的RMS驱动口型。半双工流程等待播放ACK后再恢复Listening，避免助手声音被同步录入。

已有记录支持：1轮、2轮和6轮人工功能回归、生产前端稳定性检查、播放ACK顺序、Live2D/RMS联动和正常结束；发布准备另完成干净本地克隆下的依赖/类型/构建/契约与启动器检查。它们是当时目标环境的结果，不代表所有硬件、长期运行、自然语言质量或完整资产恢复均已验收。

Demo Stable是有效的功能与工程基线。后续改变数字人呈现路线，不否定已有语音链、轻量显示方案、安全启动和调试经验。

## 阶段导航

- Phase 1 — Environment and Model Validation：Windows环境、STT、TTS与本地LLM验证。
- Phase 2 — Voice Interaction Pipeline：语音链、VAD、持久STT与半双工。
- Phase 3 — Early Digital Avatar Integration：WebSocket、Next.js、Live2D、Browser Audio与RMS。
- Phase 4 — Demo Stable Validation：生产模式、人工回归、启动器和发布边界。

阶段细节见[早期开发阶段](development-phases.md)；全项目旧版与新版的统一索引见[开发日志](../../../DEVELOPMENT_LOG.md)。不按月份重新排列公开历史，也不改写原Git日期。

## 历史资料与恢复边界

- [早期架构](architecture.md)
- [早期限制](known-issues.md)
- [旧README原件](https://github.com/edliu077/Local-Voice-Interactive-AI-System/blob/3bacd16bf2b647bf7ace0fb0d05450d1f205219f/README.md)
- [旧开发日志原件](https://github.com/edliu077/Local-Voice-Interactive-AI-System/blob/3bacd16bf2b647bf7ace0fb0d05450d1f205219f/DEVELOPMENT_LOG.md)
- [重构说明](../../architecture/WHY_WINDOWS_REBUILD.md)

旧源码可在另一个独立目录检出该固定提交进行查看或恢复；不要覆盖现有运行目录。权重、工具二进制、参考声音和Live2D素材不在公开源码中，检出提交不等于拥有完整独立可运行副本。本次没有进行恢复测试。

原创源码与文档的既有版权/使用说明不因迁移改变；第三方资源分别受其许可证及授权范围约束。历史截图/成片展示许可不等于模型文件、声音参考或素材再分发许可。
