# 本地语音交互AI系统（Local Voice-Interactive AI System）— 早期开发阶段

这是原Demo Stable开发日志的阶段式整理，依据[固定旧提交的日志](https://github.com/edliu077/Local-Voice-Interactive-AI-System/blob/3bacd16bf2b647bf7ace0fb0d05450d1f205219f/DEVELOPMENT_LOG.md)。原日志与Git时间不变，新公开摘要按技术里程碑组织。

## Phase 1 — Environment and Model Validation

- A/B：建立Windows原生方案，验证Python环境与speech-to-speech接口。上游编排路径过早构造整条模型链，不适合无模型健康检查，因此逐组件验证并保留最小自有编排方案。
- C0：确定Faster-Whisper Small；GPU可加载但转录遇到CUDA运行时DLL问题。CPU INT8完成中文转录，成为目标设备基线，不扩写为所有中文场景准确率PASS。
- E0：验证Qwen3-TTS 0.6B Base本地声音克隆，将加载、克隆提示和预热置于持久服务，增加请求串行化和资源监测。
- F0-A：通过llama.cpp验证Qwen3-1.7B Q4_K_M CPU-only，连接持久TTS，保留-ngl 0以降低与TTS的显存竞争。

## Phase 2 — Voice Interaction Pipeline

- G0：从WAV输入串起STT、LLM和TTS，文件路径验证后再加入人工麦克风输入。
- V0/H0：加入Silero VAD，先确认起止检测，再接自动单轮和多轮流程，保留文件输入回退。
- H1/H2：一次性STT worker演进为持久服务，避免每轮模型重载；同步播放及显式半双工确保助手讲话时不采集麦克风。
- 工程经验：逐组件验证、明确输入输出和状态比直接堆叠整条链更易定位故障。

## Phase 3 — Early Digital Avatar Integration

- I0：本地WebSocket桥接，模型保留在独立服务；定义状态、事件和单活动会话。
- J0：Next.js页面呈现连接、会话、字幕与历史；麦克风仍由Python采集。
- J1-B/C：PixiJS 8兼容Live2D渲染，验证单角色、缩放、眨眼、物理、呼吸和待机；资源传播权与代码许可分开。
- J1-D.1：二进制WAV交给浏览器，加入播放开始/完成ACK；旧Windows播放作为开发回退。
- J1-E.1：最终浏览器音频RMS驱动ParamMouthOpenY，加入平滑与结束/取消归零，已有回归未见正常结束后的卡嘴。

## Phase 4 — Demo Stable Validation

### 稳定运行与开发实验分界

审计源码、权重、二进制、素材和运行资料，按Public/Private/Exclude分类。独立Demo Stable目录保护开发基线；可移植配置工作仅针对稳定语音链，STT/编排与CUDA TTS分环境。正式项目名称及页面/人设措辞在这一阶段整理。

J1-F.2自动情绪映射、J2记忆/摘要与4B独立可行性工作不被冒充早期稳定功能。

### 开发服务器OOM的定位与修复

1/2轮已通过而6轮接近结束时页面失联，日志指出JavaScript堆OOM；开发服务器next dev/Turbopack堆曾约6.4GB。问题被定位在该项目的开发服务运行方式，不归罪于整个Next.js、Python语音链或Live2D。

改用next build --webpack及next start后，生产前端初始工作集约80–90MiB，1/2/6轮回归通过，六轮前后前端内存基本平稳。以上是既有历史观测，不是本轮重新测量，也不是后续Windows Rebuild的直接动因。

### 启动器与生产配置

- 核对失效PID与实际监听者；未知占用失败关闭，不停止无关Python/Node/llama进程。
- TTS健康就绪后才启动后续服务。
- 修复Live2D客户端误用普通环境变量造成的生产资源404，改用NEXT_PUBLIC_LVIAI_LIVE2D_CORE_URL/MODEL_URL；实际URL返回200，并完成最终单轮语音smoke。

### 功能与源码包验收

目标设备已有人工作业支持1/2/6轮、生产页面、VAD/STT/1.7B/TTS/WebSocket/Browser Audio、Live2D/RMS、ACK顺序和半双工。

旧版依赖修订记录Next16.3.8、sharp0.35.5、source-map-js1.2.2；当时npm audit --omit=dev为零生产漏洞，剩余ESLint/braces开发链风险另记，未采用强制破坏性降级。这是旧版本审计时结果，不是当前依赖安全的永久证明。

干净本地克隆下npm ci、ESLint、TypeScript --noEmit、生产构建、4/4稳定契约和启动器检查通过；私有资产保持排除。此源码包验证不等于独立还原所有模型和声音/角色资产。

### 版权及资源证据

记录llama.cpp b10516、1.7B GGUF、TTS、Whisper snapshot来源/修订/哈希；Silero缓存精确commit及部分wheel哈希缺口继续保留。Live2D与批准的生成声音成片展示授权不延伸到原模型、Core、参考WAV/文本、prompt或embedding的再分发。

v0.9为招聘预览定位，v0.9.1是文档修订标识，不添加并不存在的历史发布Tag。公开Git七提交原样保留，不伪装成全部私人开发提交。

## 后续衔接

完整项目的Phase5–7见[统一开发日志](../../../DEVELOPMENT_LOG.md)，重构动机及成本见[WHY_WINDOWS_REBUILD](../../architecture/WHY_WINDOWS_REBUILD.md)。
