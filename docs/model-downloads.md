# 本地语音交互AI系统（Local Voice-Interactive AI System）— External models and assets

本页提供来源和恢复前提，不执行下载，也不授予权重/素材传播权。优先合法复用本机已校验资源。当前源码副本不含完整运行环境，许可和恢复仍有BLOCKED项。

| 资源 | 已记录来源/版本 | 本地恢复条件 |
| --- | --- | --- |
| Qwen3-1.7B Q4_K_M | [ggml-org/Qwen3-1.7B-GGUF](https://huggingface.co/ggml-org/Qwen3-1.7B-GGUF)，既有revision daeb8e2d528a760970442092f6bf1e55c3b659eb | GGUF路径填本机JSON；SHA-256 d2387ca2dbfee2ffabce7120d3770dadca0b293052bc2f0e138fdc940d9bc7b5 |
| llama.cpp CPU | [b10516](https://github.com/ggml-org/llama.cpp/releases/tag/b10516)，commit b95502ba9aa0eb73a2f4fc8878d7fbe6a847a0b9 | Windows CPU可执行文件及所需DLL；不迁入Hybrid运行时 |
| Faster-Whisper Small | [Systran/faster-whisper-small](https://huggingface.co/Systran/faster-whisper-small)，snapshot 536b0662742c02347bc0e980a01041f333bce120 | 完整snapshot，不只model.bin；CPU INT8参数不变 |
| Silero VAD | [官方仓库](https://github.com/snakers4/silero-vad)；既有缓存元数据6.2.1，精确commit未恢复 | hubconf.py及src/silero_vad/data/silero_vad.jit；另有VADIterator裁剪载荷缺口 |
| Qwen3-TTS 0.6B Base | [Qwen官方模型](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base)，既有revision 5d83992436eae1d760afd27aff78a71d676296fc | 模型/tokenizer依赖完整，保留CUDA/克隆/预热配置 |
| Wav2Lip256 / S3FD | 固定LiveTalking README提供的模型目录及face_alignment作者指定S3FD来源 | 不随仓库分发；衍生权重独立授权未确认，见[许可矩阵](release/PUBLICATION_BLOCKERS.md#third-party-component-matrix) |
| STT预热夹具 | experiments/hf-speech-to-speech/fixtures/zh-short.wav | 真实预热输入，传播权未确认；不提供原录音或伪造替代 |
| TTS参考 | assets/voice-clone/reference-short.wav与.txt | 私有且需用户授权；文本文件必须符合原代码要求的确认格式，不公开正文 |
| 视频数字人 | third_party/LiveTalking/data/avatars/cybergirlfriend_avatar_v1/ | 需要coords.pkl、原配置匹配的图像序列等；仅合法本地准备，不上传派生帧 |
| 前端场景图 | frontend/public/avatar-idle.png | 私人/未获再分发授权图片未打包，缺失影响画面/背景 |
| 可选Live2D/Core | 历史兼容源码仍在 | 非当前默认；素材与Core外置，不沿用旧展示许可推定传播权 |

既有来源/修订是开发证据记录，不代表本轮重新下载或核验发布者签名。来源可访问不等于有权重新分发。模型许可、训练数据条款、衍生权重与成片/人物/声音权利分开核定；无确认保留BLOCKED。
