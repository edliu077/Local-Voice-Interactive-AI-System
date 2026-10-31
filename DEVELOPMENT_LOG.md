# 本地语音交互AI系统（Local Voice-Interactive AI System）— Development Log

本日志按开发阶段与技术里程碑统一整理早期Demo Stable及后续Windows Rebuild。阶段标题不按月份组织；必要的版本与验收事实保留，原Git提交及其时间不改写。

**公开集成候选状态：完整MigrationReview已完成源码迁入及Stage2C1前端安全/静态构建检查；当前候选按许可白名单排除全部LiveTalking树及修改补丁，不是完整运行包。** 七阶段历史保留；本候选未安装、构建、启动或验收独立恢复。

早期事实依据[固定旧提交开发日志](https://github.com/edliu077/Local-Voice-Interactive-AI-System/blob/3bacd16bf2b647bf7ace0fb0d05450d1f205219f/DEVELOPMENT_LOG.md)及其架构/限制文档；新版依据现有本地实施、冻结、审计与取证结论，仅整理脱敏技术事实，不复制原始运行资料。

## Phase 1 — Environment and Model Validation

### Windows环境与逐组件验证

建立原生Windows-first范围，验证Python环境与speech-to-speech接口。上游编排代码在无模型检查前构造过多组件，因此选择逐个模型验收和最小本地编排，不以Docker/WSL作为已验证前提。

### STT、TTS与LLM

- Faster-Whisper Small可在GPU加载，但测试转录遇到CUDA运行时DLL问题；CPU INT8完成中文转录，成为目标设备方案，为CUDA TTS保留显存。
- Qwen3-TTS 0.6B Base用用户控制的本地参考声音完成克隆验证；加载、prompt和预热进入持久服务，加入请求串行化与资源监测。
- Qwen3-1.7B Q4_K_M通过llama.cpp CPU-only验证，保持-ngl 0，随后接入持久TTS。

这些验证不等于任意发音/噪声下的STT质量或任意对话的生成质量保证。

## Phase 2 — Voice Interaction Pipeline

### 文件输入到自动语音轮次

G0连接WAV→STT→LLM→TTS，先文件后人工麦克风。V0/H0引入Silero VAD，先验证语音起止，再加入自动单轮与多轮，保留文件回退。

### 持久服务与半双工

H1将每轮加载的STT worker变为持久服务；H2以同步播放和明确状态保证采集结束后再识别/生成，助手播放期间不打开麦克风。完成一次播放后才Listening，不把全双工打断作为已经实现的能力。

核心经验是逐组件验证、清晰音频所有权、可观测状态和保留已验收回退，而不是直接构造不可定位的整条模型链。

## Phase 3 — Early Digital Avatar Integration

### WebSocket与浏览器

I0采用独立模型服务和本地WebSocket桥，建立单活动会话与状态事件。J0增加Next.js状态、字幕、历史和会话控制；麦克风仍属于Python路径。

### Live2D、Browser Audio与RMS

J1-B/C集成PixiJS 8兼容Live2D并验证角色缩放、眨眼、物理、呼吸及待机。J1-D.1将WAV交给浏览器并接收开始/结束ACK；旧Windows播放保留作开发回退。J1-E.1从最终播放信号取得RMS并驱动嘴型平滑/归零，已有正常结束回归未见卡嘴。

轻量Live2D是当时对消费级资源条件的主动选择，形成了有效数字人交互基线。模型/Core/参考声音的权利与源代码许可分别管理。

## Phase 4 — Demo Stable Validation

### 稳定范围与目录保护

盘点开发快照，区分Public、Private和Exclude。独立Demo Stable目录保护开发成果，稳定链做路径配置和分环境整理，完成正式项目名称及页面/人设措辞。J1-F.2情绪映射、J2摘要/记忆及4B独立实验未作为v0.9已交付功能。

### 前端OOM定位与生产路径

1/2轮通过后，早期6轮接近结束时前端失联。已有日志将OOM定位为next dev/Turbopack开发服务堆约6.4GB增长；没有归因于整个Next.js、Python链或Live2D。

改为next build --webpack和next start后，生产前端初始工作集约80–90MiB，1/2/6轮回归通过，六轮前后前端内存基本平稳。该故障已在旧版解决，是工程调试案例，**不是后来Windows Rebuild的直接原因**。

### 启动器与生产Live2D配置

旧启动器增加失效PID与监听者对账、未知占用拒绝、TTS真实health就绪门控和仅停止已核实项目进程。普通Live2D环境变量未进入浏览器bundle造成的404，通过NEXT_PUBLIC_LVIAI_LIVE2D_CORE_URL/MODEL_URL修复，URL返回200并完成最终单轮smoke。

### 功能、依赖与源码包验证

当时目标设备通过1/2/6轮、生产页面、语音链、Live2D/RMS、ACK和半双工人工功能回归。依赖修订记录Next16.3.8、sharp0.35.5、source-map-js1.2.2；当时生产依赖audit为零，ESLint/braces开发链剩余风险单列，未强制降级。历史audit不是当前永久安全结论。

干净本地克隆在排除私有资产条件下通过npm ci、ESLint、TypeScript --noEmit、生产构建、4/4契约及启动器检查；不等于独立恢复所有外部模型、声音和角色。

### 版本、权利与外部资源

v0.9是Recruitment Preview基线，v0.9.1是原文档修订标识，不捏造独立运行发布或既存Tag。来源记录覆盖llama.cpp、1.7B GGUF、TTS、Whisper；Silero精确缓存commit及部分wheel哈希缺口仍保留。素材/声音成片展示许可不等于源素材再分发许可。

更多早期事实见[legacy阶段摘要](docs/legacy/demo-stable/development-phases.md)及[早期架构](docs/legacy/demo-stable/architecture.md)。

## Phase 5 — Windows Rebuild Architecture Decision

### 呈现路线改变，核心成果延续

用户在已有工作基线之上选择LiveTalking + Wav2Lip音频驱动视频数字人路线，保留Windows原生与本地运行。它是新的呈现目标，不是旧Live2D方案失败。[独立重构说明](docs/architecture/WHY_WINDOWS_REBUILD.md)记录动机、复用和代价；不补写未经确认的商业/产品动机。

独立Rebuild工作区通过保护旧目录、只读复用模型和分阶段替换显示/传输层，避免在稳定目录反复施工。原VAD、STT、LLM接口、TTS、前端/WS、半双工和上下文工程成果尽可能沿用。

### 最终模型与资源取舍

曾有限评估4B CPU、Hybrid和分时方案；真实资源门控与联合驻留证据暴露了16GB RAM/8GB VRAM约束。最终明确恢复Qwen3-1.7B Q4_K_M CPU-only为正式路线，8081、4096上下文，TTS与Wav2Lip保留原模型。此处记录退役决定，不授权继续4B实验，也不把1.7B选择写成所有资源问题自动消失。

## Phase 6 — Windows Rebuild Implementation

### 本地隔离、七服务与两种播放路径

建立Rebuild自己的日志、缓存、PID/owner和输出边界，只读引用已有模型/程序。七服务顺序为Next.js3000、Avatar控制器8011、TTS8765、LiveTalking/Wav2Lip8010、1.7B8081、STT8766、WebSocket/VAD8767。

Qwen3-TTS外部音频经Avatar控制器和音频桥送入LiveTalking/Wav2Lip256，再由WebRTC送浏览器；浏览器WAV仍作备用。保留Wav2Lip256/25FPS、声音克隆和原模型；上述源码已完成静态迁入，但没有在本迁移副本运行。

### 初始化、身份与资源安全

原生PID/FILETIME、exe、精确命令行、父子树和owner/端口验证配合RAM、Commit、分页与GPU监护；失败只回收已核实自有进程，不接管无关实例。TTS采用600秒总预算优先的分阶段有界等待。

历史问题分别处理：有限conhost参数变化兼容、协调器启动等待/部分启动对账、短辅助进程创建时登记与句柄退出证明、NVML整卡采样替代高频外部查询。未能证明身份的旧PID没有被事后追认为合法；未知创建继续拒绝。

参考声音路径经第三方解码器触发FFmpeg探测的问题，改用soundfile读取原WAV并经公开支持的数组/采样率接口传入，保留原声道混合语义、参考内容和克隆模式。不能将单项离线契约PASS写成每次真实初始化或异常恢复均已通过。

### 对话与产品化

解除LLM强制emotion tag输出要求，普通中文正文经清理后进入历史与TTS，兼容neutral字段。普通会话不再因六轮上限结束，仍保留有界上下文/滚动摘要；长期记忆质量并未因此解决。

主操作合并为一次用户点击连接、解锁音频和开始；默认数字人音轨，WAV回退移入高级设置，保留结束按钮，页面视觉沿用暖色书房场景。浏览器权限仍需要用户交互，不能宣称自动采集麦克风或无点击发声。

## Phase 7 — Functional Acceptance and Quality Investigation

### 冻结的功能等级

当前冻结基线为**Windows Functional Stable Candidate v1.0-rc1 — Known Quality Issues**。用户已确认七服务联启、首次点击连接、数字人连续8轮、人工结束、浏览器WAV回退和安全关闭等功能流程；此前也有2/3/6轮人工反馈。

冻结关联日志实际覆盖12轮完成、下一轮主动停止，与“用户确认8轮功能”的口径分别保留，不据额外日志推断所有轮次质量PASS。数字人完成回执含bounded_media_estimate，不能等同声卡声学证明。曾出现的音视频卡顿近期短测试未明显复现，不据此宣布所有实时性问题永久解决。

### Q-001 — OPEN

后续转录不完整/漏字/错字的整体质量问题仍开放。一次最多三句取证任务已完成：用户试听确认轻读连读处漏识别、一个清晰词语发生替换；另一处存在发音因素，不能判独立模型错误。没有发现可证明VAD提前截断的证据，早前多轮渐进恶化根因仍未知。

冻结后增加默认关闭的STT诊断补丁用于有限取证，未改识别/判停算法。不能将工作副本的诊断补丁描述为冻结ZIP原有内容或质量修复。

### Q-002 — OPEN

早前12轮记录证实后段部分回复在重复重试后仍相同/高度相似，但旧请求、原候选及摘要正文缺失，生成/摘要/选择的具体因果未确定。

后续单次最多六轮定向Trace完整，实际完成六轮；故事有不同具体情节，未复现明显重复，重复检测/重试均未触发，不能说重试成功修复问题。上下文与最终文本传递核对正常；识别污染和局部任务落实不足仍可见，未形成应立即调参的故障证据。建议暂缓无证据修改。

### 验收边界与迁移状态

长期稳定性、所有异常恢复、完整独立恢复和广泛硬件兼容未验收。快照校验通过不等于恢复运行通过，七服务READY不等于识别/生成质量通过。

本迁移分支保留原七提交，源码白名单与配置模板已经静态迁入；本副本未运行模型/七服务，也未提交或推送。第三方权利、依赖安全、资产/隐私、完整构建和独立恢复仍有门槛，详见发布审查文档；不能继承旧版audit作为新版结论。

## 证据和隐私边界

新版叙述只读参考本地阶段报告、冻结报告、产品化/功能审计、Q-001结论和Q-002真实Trace分析。完整Trace、录音、私人转录、声音参考、Avatar原素材和运行日志没有复制到该迁移副本。

原公开历史：[基准提交](https://github.com/edliu077/Local-Voice-Interactive-AI-System/commit/3bacd16bf2b647bf7ace0fb0d05450d1f205219f)。历史日期和Git时间原样保留，公开日志采用阶段/版本组织，不伪造早期提交。
