# 本地语音交互AI系统（Local Voice-Interactive AI System）— Windows候选恢复边界

**这是公开集成源码候选，不是开箱即用完整运行包，不要直接运行Start-Rebuild.cmd。** 当前缺失完整LiveTalking实现和必要本地变更；不能简单clone上游、复制私人素材或放宽预检来补齐。本轮不安装、下载模型、构建或启动服务。

## 保留与缺失

保留第一方七服务协调/停止、进程身份与资源保护、语音接口、音频桥、Next.js及参数未变的配置模板。LiveTalking树、11项本地修改和3项新增未分发，无补丁或替代stub，详见[外部边界](third-party/EXTERNAL_LIVETALKING.md)。

三环境仍为.venv-cpu、.venv-tts、.venv-livetalking，版本记录见config下的CPU/TTS锁及LiveTalking.in/.lock。它们不是已验收的干净安装配方，不应合并；CPU裁剪speech_to_speech.VAD.vad_iterator载荷的合法来源/哈希和恢复步骤仍需补齐。

## 配置和资产

config/rebuild.example.json与windows-runtime.example.json是占位模板；实际JSON被ignore，本轮不创建。默认保持Qwen3-1.7B CPU-only、8081、4096上下文、Small CPU INT8、TTS Base CUDA及Wav2Lip256/25FPS设计。缺文件或健康/归属失败必须拒绝，不得降低RAM、Commit、分页、GPU门槛。

还需合法的llama.cpp、模型/Tokenizer、Silero、STT预热WAV、TTS参考/确认文本、Avatar图像/坐标、前端场景图。参考文本首行仍要求STATUS: CONFIRMED，其后按原代码排除空行和裁剪元数据后恰有一行确认转写；不要伪造私人正文。外置资产详见[模型说明](model-downloads.md)，没有授权的不入仓。

## 验证边界

完整MigrationReview在Stage2C1记录完整/生产audit 0组、lint/type/Webpack PASS；候选中依赖文件哈希保持，但没有node_modules、.next或新构建结果。原本地真人功能验收不能转移为候选恢复PASS。一些历史无模型检查依赖被排除的runtime/before或vendor模块，不能直接当作自足测试套件。

未来必须先解决必要变更授权、三环境与全部外部依赖，再另行授权运行。Start-Rebuild.cmd/Stop-Rebuild.cmd仅作为第一方工程入口保留，当前不保证可用。正常安全停止仍核对PID、FILETIME、exe、命令行、父子树及owner，禁止按进程名kill或手删owner。

设计日志目录为runtime/manual-start、runtime/stack及各服务/experiments的私有runtime/diagnostics，均不复制。本轮未产生真实运行日志。http://127.0.0.1:3000、一次点击连接、数字人音轨默认与WAV备用是完整本地系统行为，不是本候选实测。
