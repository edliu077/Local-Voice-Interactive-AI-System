# 本地语音交互AI系统（Local Voice-Interactive AI System）— Roadmap

**Stage2C3候选范围：本文保留原完整本地系统的设计及历史事实；公开候选未包含LiveTalking运行树、3项待确认新增或修改补丁，不是完整运行包。** Stage2C1依赖修补保持，但此前的build/audit结果不等于本候选运行验收。Q-001/Q-002 OPEN。见[当前发布门槛](docs/release/PUBLICATION_BLOCKERS.md)。

按里程碑组织，不用月份作为开发结构。下列状态不代表授权自动执行后续步骤。

| 里程碑 | 状态 |
| --- | --- |
| 早期本地语音链、Live2D/RMS与1/2/6轮 | 目标环境历史功能验收有证据，保留贡献 |
| Windows Rebuild七服务与产品化 | 原本地开发系统有功能验收记录 |
| v1.0-rc1功能候选冻结 | 已冻结，Known Quality Issues |
| 历史文档与源码白名单迁入 | 已静态准备，未提交/推送 |
| 当前技术文档与发布阻塞审查 | Stage2B完成说明整理；未知项仍BLOCKED |
| 第三方可公开范围/声明 | BLOCKED，需逐组件闭环或审查替代发布方案 |
| 迁移副本前端最小安全修补 | 仅建议，尚未修改锁或验证 |
| 合法外置资产及三环境恢复配方 | BLOCKED，尚未独立重建 |
| 完整构建/可移植契约/恢复验收 | 未完成，需后续范围授权 |
| 审查提交、推送或Release | 未执行，须完成门槛并明确授权 |
| Q-001 / Q-002 | OPEN；不以无限复测/调参替代证据 |
| 长期稳定性/全异常恢复 | 未验收 |

不规划重启4B、Hybrid、GPU层数或分时研究，也不通过降低音视频质量、安全门槛或删除数字人来换取表面READY。

技术沿革见[七阶段开发日志](DEVELOPMENT_LOG.md)，下一步具体门槛见[Publication blockers](docs/release/PUBLICATION_BLOCKERS.md)。
