# 阳朔旅游情报决策系统架构

## 项目内模块架构

阳朔旅游情报中心是“以太通量 / AetherFlux_yitaitongliang”主项目内的子项目。V0.2.4 在 V0.2.3 ASR 优先采集路线之上重建 Web 后台：前端为 React/Vite + Tailwind，后端为 FastAPI，主接口统一为 `/api/v1/*`。

`8765` 保留给 Triagent，AetherFlux Web/FastAPI 默认使用 `8788`，本地 worker/API 预留 `8789`。

## V0.2.4 Web 后台

- 第一屏是“采集作战台”，优先展示平台状态、阶段任务、标题池目标、深处理上限、并发上限和本地日志。
- FastAPI 负责新版 `/api/v1/*`：dashboard、collection config/jobs、intelligence、official sources、retention、daily bundles、cloud logs、trash、system diagnostics、agent APIs、release status。
- React 后台采用高信息密度管理台布局，桌面优先，手机可查看状态和执行简单操作。
- `python3 -m aetherflux.cli serve` 启动 V0.2.4 FastAPI 后台；`legacy-serve` 仅作为旧 V0.1 静态页面备用入口。
- 后台默认本机免登录，只监听 `127.0.0.1`，不开放公网。
- 多选删除只进入软删除回收站，14 天内可恢复；14 天后只标记可清理，不执行批量物理删除。

## 数据流

1. 后台配置 mission：地点、行业、细分、关键词、排除词、指定账号和官方信源。
2. 本地 worker 执行平台采集：搜索列表、详情页、视频处理、评论抽样、官方信源监控。
3. 采集器输出统一 raw item schema，并写入本地 SQLite。
4. `hard_dedupe_key` 只合并完全重复内容；`topic_cluster_key` 聚合同题讨论但保留原始条目。
5. 视频证据保存为本地封面、关键帧、音频、字幕/转写索引。
6. 每天生成 `daily_bundle_YYYY-MM-DD`，供第二部分“超级智脑”读取。
7. Supabase Cloud 只同步每日轻量日志索引，不保存原始情报数据。

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
