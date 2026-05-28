# 升级日志 / Changelog

本文档记录「以太通量 / AetherFlux」阳朔旅游情报决策系统的所有版本变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，并使用 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

## [Unreleased]

## [V0.2.3] - 2026-05-29

### 新增 / Added

- 新增 ASR 优先的视频情报深处理框架：本地提取音频、选择本地 ASR 后端、输出 `transcript_full`、`transcript_segments`、`video_summary` 和 `decision_hints`。
- 新增混合关键词规划：手动关键词、地点/景点、细分赛道、风险词、机会词和 Hermes 探索词共同生成标题池搜索词。
- 新增最近 24 小时 freshness 解析与过滤字段：`published_at_raw`、`freshness_status`、`freshness_window_hours`、`ui_filter_applied`。
- 新增 `opencli-rotate --stage titles|screen|videos|all`，支持标题池、初筛、视频 ASR 和完整流程分阶段运行。
- 新增 Hermes 标题池初筛入口；Hermes 不可用或关闭时回退本地机会/风险规则筛选。

### 变更 / Changed

- 小红书/抖音 OpenCLI 采集从固定少量首屏结果升级为浏览器搜索、时间筛选尝试、多轮滚动和标题池抽取。
- 默认配置调整为 V0.2.3 压力档：每个平台约 200 条标题池，约 40 条进入深处理，抽帧默认关闭，ASR 为视频处理第一优先级。
- `scripts/hermes_collect_opencli.sh` 默认执行完整链路，并显式开启 Hermes 初筛。
- 项目版本号更新为 `0.2.3`。

### 安全 / Security

- 原始视频、音频、转写全文和深处理结果继续只保存在本地或未来 NAS，不上传 Supabase Cloud。
- 缺少 ASR 依赖或视频下载路径时明确标记失败原因，不写假成功数据。

### 发布 / Release

- 从 V0.2.3 起，正式版本必须同步 GitHub、推送 `main`、打 annotated tag，并尽量创建 GitHub Release。

## [V0.2.2] - 2026-05-29

### 新增 / Added

- 新增 OpenCLI Browser Bridge 采集层，默认复用当前常用 Chrome 登录态，不再默认启动专用 CDP Chrome。
- 新增 `python3 -m aetherflux.cli opencli-rotate`，按小红书/抖音交替轮转执行 OpenCLI 采集。
- 新增 `scripts/hermes_collect_opencli.sh`，作为 Hermes 默认真实采集入口，并在采集前执行 `opencli doctor`。
- 新增 OpenCLI 输出标准化，将小红书搜索、抖音话题/地点等 rows 转为 AetherFlux raw item schema。

### 变更 / Changed

- `scripts/hermes_collect_live.sh` 默认转向 OpenCLI 后端；旧 CDP 后端仅在 `AETHERFLUX_COLLECT_BACKEND=cdp` 时启用。
- OpenCLI 未打通 Browser Bridge 时直接停止采集，避免产生假成功数据。

### 修复 / Fixed

- 修正抖音 OpenCLI 采集入口：不再调用会跳转到创作者中心的 `douyin hashtag search`，改为通过 Browser Bridge 打开 `https://www.douyin.com/jingxuan`，再输入当前采集关键词搜索并抽取搜索结果页可见视频信号。
- 避免旧 CDP 专用 Chrome 登录态与平台风控冲突导致的安全限制页、协议页和无效正文污染候选池。

## [V0.2.1] - 2026-05-28

### 新增 / Added

- 新增 `config/live_collect.json`，把小红书/抖音平台、关键词、每日目标、单篇等待时间和单任务采集上限放到本地配置中。
- 新增自适应轮转慢采集：按“小红书 1 篇 → 抖音 1 篇 → 随机等待”的方式交替采集，默认每篇后等待 90-240 秒。
- 新增 `python3 -m aetherflux.cli live-rotate` 命令，支持 `--dry-run` 预览平台轮转计划。
- 新增采集质量闸门，标记协议页、安全限制页、备案页、空正文、base64 封面等低质量结果。

### 变更 / Changed

- `scripts/hermes_collect_live.sh` 改为调用轮转慢采集命令，不再按平台批量快速采集。
- Hermes 的默认角色调整为采集监督：读取采集 summary 和平台健康状态，判断继续、暂停平台或上报人工。
- 当前版本只写入本地更新日志，不同步 GitHub，不打 tag。

### 修复 / Fixed

- 修复旧采集脚本连续快速打开详情页容易触发平台限制、并把安全限制页/协议页当作有效情报的问题。
- 修复旧详情页抽取过粗导致页面页脚、备案、导航文本污染情报正文的问题，先通过质量闸门阻断进入正式候选。

### 新增 / Added

- 新增小红书/抖音登录态 Chrome CDP 采集 adapter 初版：支持搜索页可见卡片、前 N 条详情页轻量抽取、评论样本、视频关键帧计划字段。
- 新增 `python3 -m aetherflux.cli live {xiaohongshu,douyin}` 命令；视频号因无网页端内容入口暂时跳过。
- 新增 `scripts/open_chrome_cdp.sh`，用于打开 AetherFlux 专用 Chrome 采集 profile 和 `9222` 调试端口。

## [V0.2.0] - 2026-05-28

### 新增 / Added

- **本地视频情报收集站**：V0.2.0 聚焦小红书、抖音、视频号的视频、评论、同题讨论和官方信源辅助监控。
- **端口调整**：`8765` 保留给 Triagent，AetherFlux Web 默认改为 `8788`，本地 worker/API 预留 `8789`。
- **本地 SQLite 扩展**：新增 mission、官方信源、证据保留、每日资料包、Supabase 轻量日志同步记录等本地表。
- **硬去重与同题聚类拆分**：新增 `hard_dedupe_key`、`topic_cluster_key`、`copy_similarity`，避免把不同用户讨论同一件事误删。
- **视频采集基础模型**：新增关键帧时间规划、评论抽样、每日资料包 manifest 等本地采集基础能力。
- **官方信源复核规则**：mission 的地点、行业、细分变化后，相关官方信源自动标记为 `needs_review`。
- **每日资料包索引**：新增本地 `daily_bundles` 记录，作为第一部分交给第二部分“超级智脑”的标准交付物。
- **云日志清理记录**：新增 `cloud_log_syncs`，Supabase Cloud 只允许保存轻量日志索引和清理状态。

### 变更 / Changed

- **Supabase 边界收窄**：不保存原始情报、截图、HTML、音视频、评论全文或转写全文；只用于登录和每日轻量日志索引。
- **存储路线明确本地优先**：情报数据继续使用本地 SQLite 和本地文件系统，后续可通过配置切到 NAS。
- **Hermes 定位调整**：Hermes 作为监工和异常分析 agent，不参与机械采集循环，避免 token 消耗失控。
- **README / README_EN / 架构文档更新**：补充 V0.2.0 本地视频采集站、Mac/PC 部署、资料包和安全边界。

### 安全 / Security

- 原始采集证据默认保留 48 小时，可在后台调整。
- 清理任务必须逐个删除明确文件路径，不允许批量删除目录。
- API key、cookie、浏览器 profile、Supabase service key 不写入仓库。

## [V0.1.0] - 2026-05-20

### 新增 / Added

- **项目骨架**：Python 项目结构，`pyproject.toml`，`.gitignore`
- **采集层 / Collector Layer**：`aetherflux/pipeline.py` 配置驱动流水线框架，为多平台采集预留统一 raw item schema
- **清洗层 / Normalization Layer**：基础清洗、语言识别、来源链接保留
- **评分层 / Scoring Layer**：`aetherflux/scoring.py` 低 token 规则评分、去重、基础分类、平台权重、新鲜度、互动热度、阳朔相关度、风险词、机会词
- **交叉验证中心 / Cross Verification Center**：claim 拆解、来源独立性判断、跨平台支持/冲突检查、真假信息风险提示
- **GEO 风险判断 / GEO Risk Judge**：`aetherflux/review.py` 中 GEO 疑似度输出（`geo_risk.probability`、`geo_risk.level`、`geo_risk.reasons`），只表达风险概率不做法事实定罪
- **DeepSeek V4 智库层 / DeepSeek V4 Advisor Layer**：`aetherflux/deepseek.py` 可插拔 JSON client，`aetherflux/advisor.py` 回退/合并逻辑，通过环境变量配置（`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL_ADVISOR`），无 key 时回退规则审议
- **Codex 审议脑 / Codex Review Brain**：`aetherflux/review.py` 多角色审议草稿生成，不自动发布
- **人工闸门 / Human Gate**：`aetherflux/storage.py` SQLite 存储 + 人工决策（pending → approved/rejected），`aetherflux/api.py` payload 组装
- **网页决策台 / Web Dashboard**：`aetherflux/server.py` Python 标准库 HTTP server，`aetherflux/web/` 前端（HTML/CSS/JS）
- **命令行入口 / CLI**：`aetherflux/cli.py` 支持 `ingest`、`review`、`serve` 子命令
- **API 端点 / API Endpoints**：
  - `GET /api/candidates`、`/api/selected`、`/api/daily`
  - `GET /api/opportunities`、`/api/foreign-signals`、`/api/risks`
  - `GET /api/evidence/:id`、`/api/content-briefs`
  - `POST /api/decisions`、`/api/run-ingest`、`/api/run-review`
- **样本数据 / Seed Data**：`data/seed_items.json`
- **默认方向配置**：`config/directions.json`
- **每日审议脚本**：`scripts/daily_review.sh`，支持通用 Webhook
- **架构文档**：`docs/architecture.md`
- **测试 / Tests**：`tests/` 下覆盖评分、审议、存储、API 和流水线的基础测试
- **中文 README**：`README.md`
- **项目记忆文件**：`AGENTS.md` 记录架构决策、安全规则和运行指南

### 产品决策 / Product Decisions

- 第一版优先小红书，架构已为多平台扩展做准备
- 国内外平台兼顾，阳朔作为全球旅游目的地外网信号不能缺席
- 呈现偏「旅游情报决策台」而非泛资讯流
- 信息交叉验证是核心能力，不是附属功能
- GEO 只表达疑似度，不表达事实定罪
- DeepSeek V4 参与审议但不参与低价值机械清洗
- 自动审议但不自动发布，人工确认后才进入网页和正式 API

---

[V0.2.0]: https://github.com/HJM-DUD/aetherflux-yangshuo/releases/tag/v0.2.0
[V0.1.0]: https://github.com/HJM-DUD/aetherflux-yangshuo/releases/tag/v0.1.0
