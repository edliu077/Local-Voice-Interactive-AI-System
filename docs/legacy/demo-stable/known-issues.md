# 本地语音交互AI系统（Local Voice-Interactive AI System）— Demo Stable限制

本文保留早期基线的限制，依据[旧KNOWN_ISSUES](https://github.com/edliu077/Local-Voice-Interactive-AI-System/blob/3bacd16bf2b647bf7ace0fb0d05450d1f205219f/KNOWN_ISSUES.md)。历史限制不是新增故障，也不代表后续Rebuild已经解决。

## Phase 1 — Environment and Model Validation：平台与依赖

- 只在Windows 11、RTX 4060 Laptop 8GB VRAM/16GB RAM目标配置验证；不承诺其他GPU、低内存平台、CPU TTS、Linux/macOS或远程部署。
- 模型和llama.cpp程序不随源码分发。缺文件应明确拒绝，不隐式下载大量资源。
- TTS依赖已验证CUDA环境；加载、克隆提示与CUDA graph预热期间HTTP健康可能暂不可用。历史首次READY约数十秒至一分钟，不是SLA或后续版本超时策略。
- 干净本地克隆的源码包检查已通过；Silero缓存精确commit、部分PyTorch/torchaudio wheel来源哈希仍是已记录的可复现性缺口，不能称完整独立恢复已通过。

## Phase 2 — Voice Interaction Pipeline：会话与识别

- 半双工，助手说话时不能语音打断；1/2/6轮为当时功能验收范围，长期记忆/无限轮不在该稳定声明内。
- 1.7B输出具有随机性，可能重复、简略或不够细腻；功能回归不等于对话质量全面PASS。
- 麦克风增益、噪声、扬声器和设备选择影响VAD，不能凭一次体验把问题归因于模型或截断。

## Phase 3 — Early Digital Avatar Integration：音频与资产

- 页面需要用户交互解锁浏览器音频，后台/暂停AudioContext会影响播放。
- RMS口型是音量驱动，不是音素/视素级同步；自动情绪映射未纳入早期Stable。
- Live2D模型、纹理、moc3、表情及Cubism Core不在仓库；公开展示许可不等于源码资产传播权。
- 参考声音WAV/文本、派生prompt/embedding/cache保持私有；批准生成成片的公开展示不改变这条边界。

## Phase 4 — Demo Stable Validation：发布与安全

- 原环境生产依赖审计结果只适用于当时锁文件；ESLint/braces开发工具链剩余风险已记录，未采用npm audit fix --force。未来重新评估，不把历史零漏洞当永久保证。
- 回环绑定不等于完整生产认证；不支持恶意多用户本机或公网环境。
- 1/2/6轮、构建/契约及启动器检查支持功能声明，不支持长期稳定、所有异常恢复和跨硬件保证。

## 与当前质量问题的关系

Windows Rebuild的Q-001、Q-002仍为OPEN。它们是后续明确编号的质量调查，不能根据旧版短轮次功能PASS宣称不存在，也不能将未有证据的新版根因追溯写入旧历史。当前边界见[统一开发日志Phase7](../../../DEVELOPMENT_LOG.md#phase-7--functional-acceptance-and-quality-investigation)。

报告问题时只提供脱敏的环境、失败阶段和必要统计，不提交录音、私人转录、声音参考或完整Trace。
