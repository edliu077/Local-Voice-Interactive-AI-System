# 本地语音交互AI系统（Local Voice-Interactive AI System）— Portability and recovery plan

**Historical planning record:** current candidate scope is defined by README and docs/release/PUBLICATION_BLOCKERS.md. This old plan is not a current audit result or an instruction to start the incomplete package.

源码迁入已完成静态准备，完整构建和独立恢复尚未验收。当前主要架构及入口见[README](README.md)、[Windows恢复前提](docs/windows-setup.md)，旧Demo Stable恢复资料通过固定祖先提交保留。

下一步仅在明确授权后：核定逐组件许可和前端安全方案；形成三环境可安装配方与VAD载荷来源；合法准备模型、工具、预热WAV、声音和Avatar；核对本地JSON；完成无私人夹具的静态/契约和生产构建；最后再决定有界恢复运行验证。

配置模板没有私人路径，实际JSON被ignore。不能复制旧venv/.next或私人资产冒充公开克隆可复现，也不能把模型独立成功平移为共同驻留通过。不改变CPU-only、模型/声音/画质、身份校验或资源阈值。

许可未定、依赖漏洞未处理、资产/测试夹具不可公开或恢复失败时继续BLOCKED，不自动安装、下载或推送。详见[门槛列表](docs/release/PUBLICATION_BLOCKERS.md)。
