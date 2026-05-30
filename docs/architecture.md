# 阳朔旅游情报决策系统架构

## 项目内模块架构

阳朔旅游情报中心是“以太通量 / AetherFlux_yitaitongliang”主项目内的子项目。V0.2.7 在 V0.2.5 双模式采集系统之上完成代码审查修补：不改变采集路线，重点加强安全脱敏、SQLite 并发、日志尾部读取、资料包索引自愈和后台任务超时。前端为 React/Vite + Tailwind，后端为 FastAPI，主接口统一为 `/api/v1/*`。

`8765` 保留给 Triagent，AetherFlux Web/FastAPI 默认使用 `8788`，本地 worker/API 预留 `8789`。

## AetherFlux 五大部分

AetherFlux 的长期目标是一套 GuGU 自用的 agent 应用，而不是单独的采集脚本。系统分五个部分递进实现：

| 部分 | 定位 | 当前状态 |
|------|------|----------|
| 情报收集站 | 指定账号监控、公开平台采集、评论/视频 ASR、官方信源、人工干预、权重分级、每日资料包 | V0.2.x 当前主线 |
| 超级智脑 | 消费每日资料包，做真假判断、机会/风险识别、权重调整、交叉验证和决策建议 | 后续实现 |
| 线上运维中心 | 管理 GuGU 的互联网账号规划、维护、获客和运营动作 | 后续实现 |
| 内容生成工厂 | 按情报和运营决策生产图文、视频、图片、笔记、脚本等内容 | 后续实现 |
| 线下经营智控 | 管理客户、行程、成本、资源和线下经营执行 | 后续实现 |

V0.2.x 只要求把第一部分“情报收集站”做成可用基础设施，并为第二部分输出稳定资料包和 API。第二到第五部分只保留入口、数据边界和未来扩展方向，避免做没有真实能力的空壳功能。

### 情报收集站范围

- 长期采集由 Hermes 或本地脚本调度，目标是稳定形成足够大的标题池、评论池、视频 ASR 结果和候选情报，而不是少量样本演示。
- 采集方向由 GuGU 在 Web 后台配置：地点、行业、细分类别、自定义搜索词、指定账号、风险词、机会词和排除词。
- V0.2.x 行业先聚焦旅游；细分类别至少能表达景区、民宿、酒店、旅游餐饮、疗愈等方向，后续可扩展其他行业。
- 平台优先级：先打磨小红书和抖音；保留视频号、Instagram、TikTok、OTA 和更多公开平台的 collector 扩展位。
- 人工特别信息入口必须存在，供 GuGU 把内部消息作为 `T1` 最高权重信号加入审议。

## 人机交互与 Triagent

- 所有人机交互默认落在 Web 端：后台供 GuGU 调整采集、审阅情报、定稿和人工干预；前端供多人登录查看情报结果。
- Web 端采用 UI UX Pro Max 的专业工具设计方向：高信息密度、表格优先、控件明确、可扫描、可批量处理。
- Triagent 是内部能力，不作为外部用户产品暴露。Codex 做主脑和最终验收，Hermes 适合长期采集、搜索、日志分析和机械实现，Antigravity 适合多模态、长上下文、前端原型和替代方案分析。
- 外部人员如果需要使用系统，只通过后续单独设计的 Web 端能力进入，不直接接触本机 Triagent、Chrome 登录态、原始证据目录或本地配置。

## V0.2.7 paths.py 与运行时数据

`aetherflux/paths.py` 是统一路径解析模块：
- 读取 `AETHERFLUX_DATA_ROOT` 环境变量
- 提供 `db_path()`、`artifacts_dir()`、`logs_dir()`、`daily_bundles_inbox_dir()` 等函数
- 子项目各自通过本地 `_DATA_ROOT` 常量解析，不引入跨包依赖

## V0.2.7 Web 后台与接口行为

- 第一屏是“采集作战台”，优先展示平台状态、阶段任务、标题池目标、深处理上限、并发上限和本地日志。
- FastAPI 负责新版 `/api/v1/*`：dashboard、collection config/jobs、job detail/log/cancel、title pool、video processing、intelligence、official sources、retention、daily bundles、cloud logs、trash、system diagnostics、agent APIs、release status。
- `/api/v1/collection/jobs/{job_id}/log` 仍返回 `text/plain`，但只返回日志尾部 200KB；被截断时会在文本开头加提示，避免大日志导致后端或浏览器卡死。
- `/api/v1/admin/retention` 对 `evidence_hours` 和 `cloud_log_months` 做安全整数解析；非法数字、空字符串和 `null` 返回 422。
- `/api/v1/daily-bundles` 查询前会扫描 `daily_bundles_inbox/{mode}/{date}/{run_id}/manifest.json`，用 manifest 内容计算 sha256，并把元数据同步进 SQLite。
- 后台采集 job 有 2 小时总超时；超时后先终止进程组，等待 30 秒，仍未退出再强制结束，并把任务标记为 `failed`。
- `_safe_payload()` 会移除敏感字段名，URL 只剥离敏感 query，普通文本只有像真实 token 时才替换为 `redacted`。
- React 后台采用高信息密度管理台布局，桌面优先，手机可查看状态和执行简单操作。
- `python3 -m aetherflux.cli serve` 启动 V0.2.7 FastAPI 后台；`legacy-serve` 仅作为旧 V0.1 静态页面备用入口。
- 后台默认本机免登录，只监听 `127.0.0.1`，不开放公网。
- 多选删除只进入软删除回收站，14 天内可恢复；14 天后只标记可清理，不执行批量物理删除。
- 采集操作台有活跃任务时 5 秒轮询；无 `queued/running/cancelling` 任务时 30 秒轮询。

## 数据流

1. 后台或子项目配置 mission：地点、行业、细分、关键词、排除词、指定账号和官方信源。
2. `aetherflux_shellCLI` 或 `aetherflux_agentCLI` 执行平台采集：搜索列表、详情页、视频处理、评论抽样、官方信源监控。
3. 采集器输出统一 raw item schema，并写入本地 SQLite。
4. `hard_dedupe_key` 只合并完全重复内容；`topic_cluster_key` 聚合同题讨论但保留原始条目。
5. 视频证据保存为本地封面、关键帧、音频、字幕/转写索引。
6. 前端只读地读取 `artifacts/opencli/live/` 下的标题池和视频处理结果。
7. 每天生成目录 + JSONL 形式的 `daily_bundle_YYYY-MM-DD/RUN_ID`，复制到 `daily_bundles_inbox/{mode}/{date}/{run_id}/` 后自动进入 Web 后台资料包列表。
8. Supabase Cloud 只同步每日轻量日志索引，不保存原始情报数据。

## V0.2.5 双模式采集子项目

- `aetherflux_shellCLI`：脚本和 OpenCLI 主导，agent 做监工、日志诊断、标题筛选和 ASR 深处理判断。
- `aetherflux_agentCLI`：agent 主导，OpenCLI 和脚本作为工具，适合深挖、异常处理和高价值线索追踪；当前已接通小红书/抖音真实采集、最新/一天内筛选、本地新鲜度过滤和每日资料包输出。
- 所有运行时数据迁移到 `AETHERFLUX_DATA_ROOT`（默认 `/Users/gugu/Documents/Agent/AetherFlux_Data`）。路径由 `aetherflux/paths.py` 统一解析。
- Hermes 只是默认 agent，子项目通过 `config/agents.json` 的命令模板替换 agent。
- agentCLI 必须等待 Hermes 返回结构化决策；默认不设置 agent 超时。Hermes 不可用或返回非 JSON 时，collector 停止当前采集任务并记录错误，不允许本地接管替 agent 做主导判断。
- agentCLI 的视频深处理由 `media_asr.py` 执行：抖音搜索卡片从 `waterfall_item_*` 提取内容 ID，视频拼 `/video/{id}` 后优先打开详情页解析浏览器里的 `video.currentSrc` 下载；失败时再走 `yt-dlp`，随后用 `ffmpeg` 抽音频、Whisper 后端转写。图文内容下载图片并标记 `needs_ocr`，不做 ASR。
- agentCLI 的 ASR 结果必须继续做信息价值判断：`useful` 进入后续情报判断，`low_value` 表示纯配乐/低信号视频，`review_needed` 留给人工复核，`needs_ocr` 留给图文 OCR/视觉识别。已按 GuGU 授权允许 `yt-dlp` 使用 Chrome cookie，本机实际可用 ASR 后端是 `mlx_whisper_cli`。
- 第三方抖音解析器默认禁用：`douyin.txt` 插件源码显示其会把抖音 URL 发给 `tiktokio.com` 并读取 `.tk-down-link`，只能在 GuGU 明确允许后作为外部备用下载方案。
- 视频号在 V0.2.7 只保留禁用占位，不进入真实采集队列。

## DeepSeek 智库层

DeepSeek V4 通过 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL_ADVISOR` 启用。默认模型为 `deepseek-v4-pro`。无 key 或 API 失败时，系统必须回退本地规则审议。

智库层只参与审议、交叉验证、GEO 疑似度和最终呈现润色，不参与普通清洗、去重、关键词匹配等低价值任务。

## V0.2.0 本地采集站

- 数据库继续使用本地 SQLite，不迁移到 Supabase 情报库。
- 原始情报、评论、转写、截图、HTML、视频帧和音频只存本地文件系统，后续可通过 `AETHERFLUX_DATA_ROOT` / `AETHERFLUX_EVIDENCE_ROOT` 切到 NAS。
- Supabase Cloud 只用于登录和 `collection_daily_logs` 轻量索引；默认保留最近 3 个自然月。
- 官方信源单独管理，绑定 mission；地点、行业或细分变化后必须重新确认，不能沿用上一个地区地址。
- Mac/PC 双部署：Mac 可运行完整采集；如果压力过大，PC worker 负责 24 小时采集和每日资料包生成，Mac 读取资料包进入第二部分。

## 中英对照

中英对照只在人工审阅前和最终网页/API 呈现前生成。中间采集、清洗、基础评分阶段保留原文，避免 token 消耗失控。

## 人工闸门

候选情报默认是 `pending`。只有通过网页或 API 写入 `approved` 的条目，才会进入新版 `/api/v1/intelligence/*` 输出：

- `/api/v1/intelligence/selected`
- `/api/v1/intelligence/daily`
- `/api/v1/intelligence/opportunities`
- `/api/v1/intelligence/foreign-signals`
- `/api/v1/intelligence/risks`

`rejected` 条目不会进入新的审议草稿。

## 后续扩展点

- 为每个平台增加独立 collector，统一输出 raw item shape；小红书 collector 已先接入时间窗口、硬去重和水位线状态。
- 扩展抖音和视频号视频采集，重点保存关键帧、音频转写、评论和同题聚类。
- 接入 DeepSeek，把复杂跨语言判断、冲突裁决和日报主编点评放到模型层。
- 增强交叉验证中心，结构化保存 claim、支持证据、冲突证据和需要补充的来源。
- 增强 GEO 风险判断，持续校准 `probability`、`level` 和 `reasons`。
- 增加截图证据和网页快照。
- 增加信源长期权重和反馈闭环。
- 把通用 Webhook 适配为飞书/企业微信/n8n 消息卡片。
