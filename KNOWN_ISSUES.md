# 本地语音交互AI系统（Local Voice-Interactive AI System）— Known Issues

**Stage2C3候选范围：本文保留原完整本地系统的设计及历史事实；公开候选未包含LiveTalking运行树、3项待确认新增或修改补丁，不是完整运行包。** Stage2C1依赖修补保持，但此前的build/audit结果不等于本候选运行验收。Q-001/Q-002 OPEN。见[当前发布门槛](docs/release/PUBLICATION_BLOCKERS.md)。

基线：Windows Functional Stable Candidate v1.0-rc1 — Known Quality Issues。当前迁移源码含冻结后默认关闭的STT取证补丁，不是原冻结ZIP的字节副本。

## Q-001 — OPEN：STT漏识别/替换与多轮质量

用户反馈后段转录不完整、漏字和识别错误。三句原声取证中，轻读连读处漏识别和清晰词语替换已有用户试听确认；另一处存在发音因素。该有限取证任务已完成，不等于Q-001解决。

没有证明VAD提前截断；早前多轮逐渐恶化的机制仍未知。不可仅凭短转录/时长认定截断，亦不把预设句自动视为实际口述真值。

## Q-002 — OPEN：重复回答与重试选择

历史12轮日志显示部分回复重试后仍高度相似/相同，完整旧候选和摘要内容不足以确定生成/上下文/选择的具体因果。后来六轮定向Trace完整、故事更具体，未复现明显重复，且未触发重试；不能说重复保护已修复或重试成功。

有转录污染及局部任务落实不足，但不足以据此开展无边界调参。当前保留模型、Prompt、摘要及选择机制，优先保护功能基线。

## Complete-runtime distribution and recovery — BLOCKED

- 第三方逐组件来源/许可及声明未全部闭环；Wav2Lip权利不能由LiveTalking Apache-2.0推断。权重和素材没有再分发默认授权。
- 前端安全依赖已在Stage2C1修补；Stage3A在PublicationCandidate实际进行的完整与生产npm审计当次均为0个已知漏洞包组，ESLint、TypeScript noEmit和Webpack生产构建通过。ESLint9.39.5停止支持警告仍在，不宣称已修复。该审计不保证永久零风险，也不是运行时可利用性或完整系统安全认证。见[前端安全证据](docs/release/PUBLICATION_BLOCKERS.md#frontend-security-review)。
- 三环境记录不是已验收的clean-install配方；VAD裁剪模块、wheel及外置资产准备仍有缺口。
- 本候选已完成前端生产构建及独立TypeScript noEmit检查，Next生成类型由该次构建真实产生，没有复制旧.next冒充通过。浏览器/WebRTC联动、后端与七服务动态运行、完整恢复和长期稳定性仍未验收。
- 部分历史检查依赖未公开的before/冻结源码，不能直接作为公共克隆的独立回归套件。

## Runtime limitations

仅有目标Windows单机功能证据，不保证跨硬件或低资源运行。半双工，未实现语音打断；无限会话生命周期不等于无限上下文或长期记忆质量。数字人音视频曾卡顿，近期短测未明显复现不构成长期无冻结保证。

长期稳定性、所有异常恢复、完整独立恢复未验收。回环绑定和内部归属/令牌检查不是公网生产认证；禁止公网暴露。资源不足应保留安全拒绝。

原始录音、Trace、私人对话与参考声音不随问题报告公开。早期限制见[legacy](docs/legacy/demo-stable/known-issues.md)。
