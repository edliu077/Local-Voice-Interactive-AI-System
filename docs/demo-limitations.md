# 本地语音交互AI系统（Local Voice-Interactive AI System）— Demo limitations

当前为Windows Functional Stable Candidate v1.0-rc1 — Known Quality Issues的源码迁移审查；七服务源码静态迁入不等于本副本已构建或运行。

原本地系统有数字人/WAV回退与连续流程功能证据；Q-001、Q-002仍OPEN，识别/回答质量没有全面通过。长期稳定、所有异常恢复、跨硬件与完整独立恢复未验收。

半双工、单用户回环、16GB RAM/8GB VRAM目标环境有限；无限会话不等于无限记忆。WebRTC完成回执含估算语义，任务管理器资源不异常不能证明25FPS或无卡顿。素材与模型外置，复制源码不形成完整独立运行副本。

当前许可、安全依赖和恢复门槛详见[Publication blockers](release/PUBLICATION_BLOCKERS.md)，不要依据旧版Demo指南启动，历史仅见[legacy](legacy/demo-stable/README.md)。
