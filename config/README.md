# 本地语音交互AI系统（Local Voice-Interactive AI System）— 候选配置模板

只提供原参数不变的模板与依赖记录，当前缺少LiveTalking实现和本地适配，不可直接启动。不要通过修改参数/资源门槛补救。

未来合法依赖/适配闭环后，才可将rebuild.example.json和windows-runtime.example.json复制为对应实际JSON，填写本机核对路径；实际配置被ignore，本轮不创建。C:/LOCAL_ASSETS与C:/LOCAL_TOOLS为占位符。默认仅1.7B CPU-only、8081、4096上下文，Small CPU INT8、TTS Base CUDA、Wav2Lip256/25FPS，所有模型身份和资源政策未改；无4B/Hybrid活动profile。

旧版.env模板已从活动树排除，不应使用其8080/Browser Audio配置启动新版。三环境记录不合并；CPU裁剪VAD载荷、CUDA wheel、声音/人物和STT夹具的合法来源与干净恢复未验收。Stage2C1前端依赖修补已完成并保持，本候选不重装/构建。

见[Windows边界](../docs/windows-setup.md)、[模型说明](../docs/model-downloads.md)、[发布门槛](../docs/release/PUBLICATION_BLOCKERS.md)。所有输出/缓存/owner必须在工作区，外部模型只读，不链接旧可写目录。
