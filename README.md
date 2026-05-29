# AetherFlux Yangshuo / 以太通量阳朔情报系统

这是“以太通量”项目下的阳朔旅游情报子项目，用于 GuGU 自己做内容选题、项目判断、风险识别和后续 agent 分析，不是游客攻略站，也不是对外 SaaS。

## 项目总框架

以太通量最终不是单一爬虫或单一后台，而是 GuGU 自用的一套大型 agent 应用。系统分五大部分逐步落地：

1. **情报收集站**：当前重点，V0.2.x 基本实现。负责指定账号监控、公开平台搜索采集、评论和视频 ASR 深处理、人工审阅、权重分级和每日资料包输出。
2. **超级智脑**：后续重点。消费第一部分的每日资料包，利用 Codex、Hermes、Antigravity 和 DeepSeek 做真假判断、机会识别、风险识别、权重调整和交叉验证。
3. **线上运维中心**：用于 GuGU 自己经营的互联网账号规划、维护、获客和运营决策，依据超级智脑输出制定行动。
4. **内容生成工厂**：根据第二、第三部分的判断，生产图文、视频、图片、笔记、脚本等内容，后续接入多模态工作流。
5. **线下经营智控**：用于客户、行程、成本、资源和经营管理，例如旅游行业里的客人行程规划、报价和执行控制。

V0.2.x 只把第一部分“情报收集站”打扎实，并为第二部分预留标准资料包和 API。后续部分先做架构预留，不在当前版本强行实现。

“情报收集站”的 V0.2.x 范围是：让 Hermes 或本地脚本承担长期采集调度；支持 GuGU 手动指定账号监控；支持按地点、行业、细分类别和自定义搜索词生成采集方向；当前行业先聚焦旅游，后续保留扩展到更多行业。平台路线先打磨小红书、抖音，保留视频号、Instagram、TikTok、OTA 和更多公开平台接入能力。

所有人机交互默认落到 Web 端：后台给 GuGU 调整采集、审阅情报、定稿和人工干预；前端给多人登录查看情报结果。Web 端设计规范默认使用 UI UX Pro Max 的高密度专业工具风格。

Triagent 是本项目的核心能力之一：Codex 做主脑和最终验收，Hermes 适合长期采集、代码搜索、日志分析和机械实现，Antigravity 适合多模态、长上下文、前端原型和替代方案分析。这个系统不面向外人维护；外部用户如需使用，只能通过单独设计的 Web 端能力进入。

## 当前版本状态

当前版本是 **V0.2.4：Web 后台重建版本**。

这一版把 V0.1.0 的旧静态 Web 后台完全换成新的 **React/Vite 前端 + FastAPI 后端**。后台第一屏是“采集作战台”，优先服务小红书/抖音的标题池、初筛、ASR 深处理、任务日志、回收站和系统诊断。

V0.2.4 继续沿用 V0.2.3 的“最近 24 小时标题池 → Hermes 初筛 → 本地 ASR 深处理”采集路线：

- 混合关键词池：手动关键词 + 地点/景点/细分/风险/机会词 + Hermes 探索词
- 最近 24 小时信息优先：平台 UI 筛选尝试 + 本地发布时间二次过滤
- 多轮滚动标题池采集，减少每次只抓首屏重复内容的问题
- Hermes 只读轻量标题池，按机会/风险筛选需要深处理的视频
- 深处理以全视频 ASR 转写为核心，抽帧默认不是重点
- 原始视频、音频、转写和证据仍只保存在本地或未来 NAS
- 从 V0.2.3 起，每个正式版本都必须同步 GitHub、打 tag，并尽量创建 GitHub Release

视频号仍因没有稳定网页端内容入口暂时跳过。

## 运行方式

测试：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -e .
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m compileall aetherflux
npm install
npm test
npm run build
```

启动 V0.2.4 本地后台：

```bash
npm run build
.venv/bin/python -m aetherflux.cli serve --host 127.0.0.1 --port 8788
```

打开：

```text
http://127.0.0.1:8788
```

端口说明：

- `8765`：保留给 Triagent 后台
- `8788`：AetherFlux 本地网页
- `8789`：预留给本地 worker/API

旧 V0.1.0 静态后台只作为备用调试入口：

```bash
.venv/bin/python -m aetherflux.cli legacy-serve --host 127.0.0.1 --port 8788
```

## 当前可以演示的流程

当前仍然保留 V0.1.0 的样本演示流程：

```bash
python3 -m aetherflux.cli ingest
python3 -m aetherflux.cli review
```

也可以用外部工具或人工方式先准备一个 JSON feed，然后让系统读取：

```bash
python3 -m aetherflux.cli xhs backfill --days 7 --source data/xhs_source_items.json --output artifacts/xhs_raw_items.json
python3 -m aetherflux.cli ingest --seed artifacts/xhs_raw_items.json
```

注意：这里的 `xhs backfill` **不是直接登录小红书并自动爬取真实平台**。它目前读取的是已经落盘的 JSON 数据，用来测试后续真实采集 adapter 的入库流程。

## OpenCLI 登录态采集

V0.2.3 默认使用 OpenCLI Browser Bridge 复用当前 Chrome 登录态，不读取 cookie 文件，不绕验证码，不支持视频号网页端。

先确认 OpenCLI 已打通：

```bash
opencli doctor
```

预览 V0.2.3 标题池采集计划：

```bash
AETHERFLUX_DRY_RUN=1 scripts/hermes_collect_opencli.sh
```

执行完整流程：

```bash
scripts/hermes_collect_opencli.sh
```

按阶段执行：

```bash
python3 -m aetherflux.cli opencli-rotate --stage titles
python3 -m aetherflux.cli opencli-rotate --stage screen
python3 -m aetherflux.cli opencli-rotate --stage videos
python3 -m aetherflux.cli opencli-rotate --stage all
```

阶段说明：

- `titles`：只采集最近 24 小时标题池。
- `screen`：标题池 + Hermes/本地规则初筛。
- `videos`：标题池 + 初筛 + 视频 ASR 深处理。
- `all`：默认完整流程。

## V0.2.0 的核心设计

### 本地优先

所有原始情报、截图、视频帧、音频、评论全文、转写全文都只保存在本机，后续可以切到 NAS。

Supabase Cloud 只用于：

- 登录账号
- 每日轻量日志索引

Supabase Cloud 不保存：

- 原始情报正文
- 评论全文
- 截图
- HTML
- 视频帧
- 音频
- 转写全文

### 去重与聚类

V0.2.0 明确区分两件事：

- `hard_dedupe_key`：只合并完全重复内容，比如同 URL、同平台内容 ID、同媒体指纹。
- `topic_cluster_key`：不同用户讨论同一件事，不删除原始内容，而是聚合成同题热度。

不同用户都在说“阳朔某景区排队”“某路线爆火”“某项目避雷”，这不是垃圾重复，而是重要情报信号。

### ASR 是视频理解重点

V0.2.3 不把抽帧作为主要能力，核心是用完整语音转文字低成本理解视频在说什么。

深处理字段包括：

- 标题
- 作者
- 发布时间
- 点赞/评论/收藏/转发
- 来源链接
- `asr_status`
- `asr_backend`
- `transcript_full`
- `transcript_segments`
- `video_summary`
- `decision_hints`

本机已有 `ffmpeg` 时可提取音频。ASR 后端按本地依赖自动选择：Apple Silicon 优先 `mlx-whisper`，其他环境优先 `faster-whisper`，缺依赖时会明确标记失败原因，不写假成功数据。

### 评论是重点

评论区不是附属内容，而是判断真实体验、争议、广告植入和重复讨论的重要材料。

默认应采集：

- 热门评论
- 最新评论
- 作者回复
- 命中风险词的评论
- 命中机会词的评论
- 提到价格、排队、投诉、推荐、避雷的评论

相似评论不直接删除，而是保留为热度、水军或广告疑似信号，交给第二部分“超级智脑”判断。

### 官方信源

官方信源是独立辅助模块，不是社媒主采集战场。

后台需要单独页面维护官方来源地址，例如：

- 文旅官网
- 景区公告
- 交通公告
- 天气/应急通知
- 票务/预约页面

地点、行业、细分方向变化后，官方信源必须重新确认，不能自动沿用上一个地区的官方地址。

## V0.2.4 新后台 API

正式后台主接口统一迁移到 `/api/v1/*`。主要接口包括：

- `GET /api/v1/dashboard/summary`
- `GET/PUT /api/v1/collection/config`
- `GET/POST /api/v1/collection/jobs`
- `GET /api/v1/collection/jobs/{job_id}`
- `GET /api/v1/collection/jobs/{job_id}/log`
- `POST /api/v1/collection/jobs/{job_id}/cancel`
- `GET /api/v1/intelligence/candidates`
- `POST /api/v1/intelligence/decisions`
- `GET /api/v1/intelligence/selected`
- `GET /api/v1/intelligence/daily`
- `GET /api/v1/intelligence/opportunities`
- `GET /api/v1/intelligence/foreign-signals`
- `GET /api/v1/intelligence/risks`
- `GET/POST /api/v1/admin/official-sources`
- `GET/POST /api/v1/admin/retention`
- `GET /api/v1/daily-bundles`
- `GET /api/v1/cloud-log-syncs`
- `GET/POST /api/v1/trash`
- `POST /api/v1/trash/restore`
- `POST /api/v1/trash/mark-cleanable`
- `GET /api/v1/system/status`
- `POST /api/v1/system/deepseek-smoke-test`
- `GET /api/v1/system/opencli-doctor`
- `GET /api/v1/system/diagnose`
- `GET /api/v1/title-pool`
- `GET /api/v1/video-processing`
- `GET /api/v1/agent/apis`
- `GET /api/v1/release/status`

旧 `/api/*` 只作为旧后台兼容参考，不再是 V0.2.4 的主接口。

## 下一步重点

V0.2.4 后续真正要继续推进的是：

1. 把更多标题池、ASR 队列、任务日志字段接成真实可编辑表格。
2. 完成小红书/抖音真实登录态 adapter 的稳定化。
3. 视频号真实登录态视频采集 adapter。
4. 评论分层采集。
5. 每日资料包与第二部分“超级智脑”的消费闭环。
6. PC worker 部署方案。

换句话说：**V0.2.4 已经把后台控制台骨架和主 API 换到新架构；真实平台采集的稳定性仍要继续打磨。**

## DeepSeek 智库层

DeepSeek 仍然是后续审议和分析层使用的可插拔智库，不参与低价值机械采集。

本机环境变量示例：

```bash
export DEEPSEEK_API_KEY="your-local-key"
export DEEPSEEK_BASE_URL="https://api.deepseek.com"
export DEEPSEEK_MODEL_ADVISOR="deepseek-v4-pro"
```

不要把 API key 写进仓库。

## 安全边界

- 不把账号密码、cookie、token、API key 写进仓库
- 不把原始采集数据上传 Supabase Cloud
- 默认本地证据保留 48 小时，可后续调整
- 清理文件时只能逐个明确路径删除，不允许批量删除目录
- 后台多选删除只做软删除回收站，14 天内可恢复；14 天后只标记可清理
- 自动流程不自动发布，人工确认后才进入正式输出
