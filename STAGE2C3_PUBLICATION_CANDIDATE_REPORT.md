# 本地语音交互AI系统（Local Voice-Interactive AI System）— Stage 2C-3公开候选报告

审查日期：2026-10-30（America/Vancouver）。

**已建立独立、保守的公开集成源码候选。可以进入“非完整运行包”的最终Git提交审核，不代表获准提交或公开发布。** 完整LiveTalking树、全部CONDITIONAL/BLOCKED源码、3项待确认新增及第三方修改补丁均未分发。候选不可完整启动七服务；没有通过缺件绕过许可或安全规则。

## 1. 独立工作区和入口检查

工作区：`D:\LocalVoiceInteractiveAI_PublicationCandidate`。目标原不存在，从GitHub仓库正常clone main，创建本地分支`windows-rebuild-publication-candidate`。HEAD与origin/main均为`3bacd16bf2b647bf7ace0fb0d05450d1f205219f`，原七个提交完整，非orphan/浅克隆，无历史重写。

开始前读取Stage2C1、2C2、FILE_CLASSIFICATION、RUNTIME_SCOPE、LOCAL_CHANGES及PUBLICATION_BLOCKERS。MigrationReview的276个非缓存文件与2C2最终哈希快照完全一致，Git状态一致，零暂存，无未报告改动。前端两个依赖文件与Stage2C1核对通过，冻结ZIP不变后才操作。整个MigrationReview始终只读。

## 2. 白名单、最终文件和旧入口

显式白名单从Stage2A已审查源码manifest中选取121个非vendor文件，再单列正式文档、模板、声明及许可证；总计167个精确路径。没有复制整个根目录或递归复制runtime/源码树。最终新增候选说明、报告及清单后，共173个待审核文件。

[白名单与最终完整清单](docs/release/PUBLICATION_FILE_LIST.md)逐个列出167个输入路径、173个候选文件以及完整MigrationReview中缺席的所有源路径。`PUBLICATION_SHA256SUMS.txt`覆盖除它本身以外的172个文件；自身哈希在被ignore的审计final-state。候选未包含.git对象目录在上述载荷计数内；Git历史另行核验。

正常clone后仅删除23个已知旧版活动文件（全部在新候选根下，逐路径核验）；包括旧活动启动/模块及过时.env模板，均仍可通过原Git祖先恢复。不保留第二套旧版可执行入口。删除清单：

- `.env.example`
- `backend/common/lviai_config.py`
- `backend/orchestrator/backend_client.py`
- `backend/orchestrator/playback.py`
- `backend/orchestrator/voice_ws_server.py`
- `backend/stt/stt_service.py`
- `backend/tts/tts_service.py`
- `backend/vad/vad_capture.py`
- `requirements/orchestrator.txt`
- `requirements/stt.txt`
- `requirements/tts.txt`
- `runtime/.gitkeep`
- `scripts/windows/Start-Demo.ps1`
- `scripts/windows/Stop-Demo.ps1`
- `scripts/windows/build-frontend.ps1`
- `scripts/windows/common.ps1`
- `scripts/windows/start-frontend.ps1`
- `scripts/windows/start-llm.ps1`
- `scripts/windows/start-stt.ps1`
- `scripts/windows/start-tts.ps1`
- `scripts/windows/start-websocket.ps1`
- `tests/test_launcher_hardening.ps1`
- `tests/test_stable_contracts.py`

## 3. 第三方排除与新增源码单独审阅

完整来源树的101个载荷加UPSTREAM.md共102个文件全部排除：11 BLOCKED、25 CONDITIONAL、65 READY均未随包携带。READY仅是原逐文件许可核验状态，不是必须vendor的理由。没有完整/部分LiveTalking运行树，没有内层.git、gitlink、submodule或补丁包。完整逐文件名称、来源哈希与原状态见[排除清单](docs/third-party/FILE_CLASSIFICATION.md)。

Wav2Lip模型/音频/hparams/预处理派生实现、face_detection、上游JS/HTML、11项修改和3项新增的实现全部未复制。8份官方许可证全文只是既有来源证据，逐字节保留，不为缺失的源码或权重重新授予许可。

| 本地新增源文件（均排除） | 单独检查结果 |
| --- | --- |
| server/audio_turns.py | 账本/取消逻辑，仅标准库导入；结构可分离不等于独立著作权和公开授权已证明。 |
| tts/external.py | 依赖上游registry注册接口；未证明可独立授权，不发布代码或替代patch。 |
| utils/realtime_diagnostics.py | 标准库有界队列/日志统计；未取得独立来源及明确许可证明。 |

对另有携带的上游来源Python文件进行有限token相似性检查，最长连续匹配分别7/10/14个token，只能说明未见大段直接匹配；不是穷尽检测，更不能证明原创或授权。原始文件保持原位，本候选只提供元数据/角色说明。后续不得把这些文件挪到第一方目录就自动视为权利问题消失。

## 4. 第一方工程成果保留

保留全部38个生产管理/运行封装脚本、七服务协调及安全停止、进程原生身份/FILETIME/owner/父子树与端口校验、RAM/Commit/分页/GPU门控、TTS有界启动和辅助进程证据逻辑。保留WebSocket/VAD导入闭包、持久STT/TTS、1.7B CPU接口、Avatar控制器/音频桥、Next.js/WebRTC客户端和浏览器WAV回退、摘要与重复保护、默认关闭的STT取证。

Stage2A的121个非vendor源码/配置/检查文件中，120个与MigrationReview逐字节相同；仅一个mock测试fixture中的硬件UUID替换为显式合成UUID。生产代码、模型/声音/采样参数、资源安全逻辑均未改。没有升级依赖、引入替代模型、生成素材或补写第三方算法。

文档只为候选范围适配：中英文README、架构/验收/配置/隐私/权利说明明确非完整运行包。DEVELOPMENT_LOG的Phase1–7及legacy阶段文档保持连贯，旧版贡献不贬低，不以月份重写阶段，不改Git时间。原有正式项目名称及版权保留；代码兼容标识CYBER_*、路径/alias暂不无关重命名。原原创代码继续按既有all-rights-reserved声明，没有凭本任务分配新的开源许可。

## 5. 安全依赖与冻结差异

frontend/package.json SHA-256：`043456bb73ebc1dcf028acf9d83eff2e1d4cfd6ff17648d524fbd0698dab49d6`。

frontend/package-lock.json SHA-256：`e1cc89d01c60e9c3f791a1279cb2a2dd1fde4e944f24459a9ee5c2e615016a20`。

两者与Stage2C1一致：Next/eslint-config-next16.4.3、sharp0.35.5、source-map-js1.2.2等安全补丁保留，未重新npm install/audit/build。Stage2C1的audit 0组、ESLint/TS/Webpack PASS是完整MigrationReview既有记录，不伪称本候选新结果。

冻结基线仍是**Windows Functional Stable Candidate v1.0-rc1 — Known Quality Issues**。本候选有冻结后的默认关闭STT取证、前端安全依赖与许可/文档整理，且排除vendor，不能等同原rc1。冻结ZIP SHA-256保持`9e1b6eeb4b05b47ce158cb0bb26a3cc82b6f34cdc159bd80e01793bf1a0a9971`。Q-001/Q-002 OPEN，长期稳定和完整独立恢复未验收。

## 6. 静态核验结果与实际边界

| 项目 | 本轮结果 |
| --- | --- |
| 原七提交、祖先关系与Git对象 | PASS，原SHA顺序保留；fsck正常，无浅历史、gitlink或嵌套.git。 |
| 白名单与文件类型 | PASS：173个纯文本候选文件，无权重/媒体/二进制/环境/cache/runtime载荷。 |
| 生产/配置不变性 | PASS：38生产脚本及模型、资源参数和前端依赖保持字节一致。 |
| Python | PASS：77个文件仅内存compile/AST语法，不import/执行项目代码，不产生pyc。 |
| PowerShell | PASS：13个文件仅Parser.ParseFile语法解析，不执行。 |
| TypeScript/JS | PASS：12个TS/TSX使用现有TS5.9.3解析器仅查语法，5个JS/CJS/MJS使用Node --check。不是tsc noEmit或构建。 |
| README/Markdown相对链接 | 最终清单生成后逐链接核对；外部HTTP可达性不作为本轮网络测试。 |
| 当前源隐私扫描 | 仅命中显式合成GPU UUID；未发现其他用户路径、密钥形状、私钥头或带凭据URL；不构成绝对无秘密证明。 |
| 历史隐私/类型扫描 | 原七提交81个唯一可达文件blob的有限模式扫描未命中上述风险或异常二进制；保留全部历史，不作历史重写。 |
| 第三方实现/资产排除 | PASS：完整vendor不在载荷，模型/声音/Avatar/WAV/Trace等不复制。 |
| Git diff --check | 通过，存在本机Git LF→CRLF常规提示，未改全局设置；之后实际暂存时须复核规范化diff。 |
| 完整类型检查/生产构建/动态接口 | 本候选未执行，不继承Stage2C1静态验收为自己的新结果。 |
| 七服务/浏览器/真人语音/独立恢复 | 未执行，当前缺件无法完成完整系统验证。 |

某些保留的历史contract脚本读取runtime/before原始快照或导入被排除的vendor，不能称本候选已具备自足的可执行测试套件。当前不运行这些脚本，也不复制私有历史记录补齐测试。

## 7. 可运行性与合法外部依赖

公开候选的第一方入口和设计端口保留（3000/8011/8765/8010/8081/8766/8767），但第三方实现和适配缺失，实际配置、三套venv、模型/Tokenizer/VAD、STT夹具、声音与人物素材均需依法准备。未修改上游本身缺少本地11+3，不是可复现恢复方案。

README/Windows恢复说明明确“公开集成源码候选，不是开箱即用完整运行包”；不把原本地七服务/八轮人工PASS移植为本候选通过。既有缺失依赖、健康、资源和归属失败保持拒绝，未生成stub或假READY。恢复和授权未闭环前不建议运行Start-Rebuild，也不通过先启动其他服务掩盖缺件。

完整运行分发、权重传播、人物/声音源素材和商业/作品集展示各有独立权利条件。没有安装/下载/上传第三方载荷。合法用户自行获取不等于获得派生修改或素材传播权，后续必须另行审核而非自动提供patch。

## 8. 与完整MigrationReview的精确差异

所有source→candidate选择、原/现SHA及候选适配diff保存在被ignore的`.publication-audit/`；公开完整清单只列相对路径与排除原因，不复制私人证据。分类如下：

- 显式选入167个来源文件，最终其中147个逐字节保持，20个为候选文档/ignore或单个测试fixture适配。
- 来源276个文件中，当前候选缺席108个，包括102个vendor记录及未迁入的完整内部阶段审查材料/旧.env等；完整名称见公开清单。
- 候选专有说明/清单/报告为其余文件；总载荷173个。Stage2C1/2C2内部报告未整份复制，不将完整源审阅材料当作公开源码发布。

MigrationReview和原Rebuild/三个历史保护目录均没有写入；冻结ZIP未动。最终再对MigrationReview276个非缓存文件及Git状态与入口快照比较，防止读源操作造成变更。

## 9. Git状态、提交审核条件和停止点

本地分支windows-rebuild-publication-candidate，HEAD为旧main，原七SHA完整。当前候选仅有工作树修改/删除/新文件，index为空，无git add/commit/tag/push/main合并。原提交已在GitHub，候选新文件尚未上传。SHA清单校验针对工作树原始字节，之后Git行尾规范化需在最终暂存审阅单独核对，不假称已创建提交。

**建议进入下一步最终Git提交审核，仅限已经明确声明的非完整运行源码候选。** 审核应以完整白名单、排除清单、checksum、实际diff及版权/使用边界为准；这不是现在执行提交/发布的授权，也不关闭完整运行包的许可与恢复门槛。若将来要补入vendor、patch或私有素材，须先取得相应授权并单独审查，不能沿用本次PASS。

本轮完成即停止，不启动模型或服务、不进一步迁入第三方代码、不执行任何Git发布操作。

## 10. 最终核验回执

最终白名单、172项SHA-256、全部Markdown相对链接与锚点、许可全文、不含vendor/媒体/权重、原Git祖先、隐私模式和受保护来源不变性检查均PASS。MigrationReview276个非缓存文件及Git状态保持入口原样，冻结ZIP相同。

当前Git工作树：23项删除、27项修改、139项未跟踪文件；这些是相对原main的全部候选准备变更，未暂存。仍是windows-rebuild-publication-candidate，HEAD为原main，没有创建新提交或Tag，也没有Push。完整机器核验回执保存在被ignore的.publication-audit/final-state.json；不能将这些静态结果写为完整运行包或语音测试PASS。
