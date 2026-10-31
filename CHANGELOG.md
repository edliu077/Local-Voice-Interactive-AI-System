# 本地语音交互AI系统（Local Voice-Interactive AI System）— Changelog

**Stage2C3候选范围：本文保留原完整本地系统的设计及历史事实；公开候选未包含LiveTalking运行树、3项待确认新增或修改补丁，不是完整运行包。** Stage2C1依赖修补保持，但此前的build/audit结果不等于本候选运行验收。Q-001/Q-002 OPEN。见[当前发布门槛](docs/release/PUBLICATION_BLOCKERS.md)。

按版本与技术里程碑记录；不补造发布日期或不存在的Git Tag，不改写原提交时间。

## Unreleased — Windows Rebuild migration review

- 七服务源码及必要LiveTalking本地改动按白名单静态迁入；排除权重、环境、声音/人物素材及运行资料。
- 配置模板、外置资源说明、统一阶段式历史与当前架构文档就位。
- Stage2B只核对许可、安全公告和文档；运行算法、模型设置、依赖锁、进程/资源保护未改。
- 公开发布、依赖安全修补、完整构建与独立恢复仍有未通过门槛。

## Post-freeze diagnostics — after the rc1 archive

默认关闭的STT证据补丁保存最多三条实际输入及当次响应，用于取证，不改变识别/VAD参数或修复Q-001。迁移源码携带该补丁；原冻结ZIP不变。有限Q-002 Trace未复现重复且没有重试，不标记修复。

## v1.0-rc1 — Functional baseline with known quality issues

Windows Functional Stable Candidate v1.0-rc1 — Known Quality Issues。原本地系统七服务、首次点击、数字人8轮、人工结束、WAV回退与安全关闭有人工作业支持；关联日志实际轮数另作证据索引，不与人工质量PASS混同。

Q-001/Q-002 OPEN。长期稳定性、完整异常恢复及独立恢复未验收。冻结校验通过只说明快照完整性。

## Demo Stable v0.9 — early validated pipeline

本地VAD/Small INT8/1.7B CPU/TTS CUDA、WebSocket、生产Next.js、Browser Audio、Live2D/RMS、ACK及半双工在目标设备完成1/2/6轮功能验证。旧前端OOM已在当时生产路径解决，不是后续重构直接原因。

## Demo Stable documentation revisions

原Documentation Revision v0.9.1及后续权利/外部资源文档修订保留在七次原Git提交中，不能虚构为独立运行版/既存Tag。原公开基准为3bacd16bf2b647bf7ace0fb0d05450d1f205219f。[旧版阶段说明](docs/legacy/demo-stable/README.md)保留技术贡献。
