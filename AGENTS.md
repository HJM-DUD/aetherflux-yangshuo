# AGENTS.md - 以太通量 / AetherFlux Project Memory

## User And Safety Rules

- 用户名字叫 GuGU，对编程只是略懂皮毛；回答和交付要清楚、耐心、少假设。
- 禁止批量删除文件或目录。
- 不要使用：
  - `del /s`
  - `rd /s`
  - `rmdir /s`
  - `Remove-Item -Recurse`
  - `rm -rf`
- 需要删除文件时，只能一次删除一个明确路径的文件。
- 如果需要批量删除文件，应停止操作，并请求用户手动删除。
- API key、cookie、token、账号密码等敏感信息不能写进仓库、文档、测试、前端代码或提交记录；DeepSeek key 只能通过环境变量或本机 `.env` 读取。

## Project Goal

本项目中文名是“以太通量”，目录名是 `AetherFlux_yitaitongliang`。

当前实施的子项目是“阳朔旅游情报决策系统”，用于 GuGU 自己做内容选题、项目判断、风险识别、交叉验证、GEO 疑似度判断和后续运营 agent 的数据依据。

它不是普通游客攻略站，也不是第一阶段给商家看的 SaaS。未来可以开放部分已审核内容给商家，但第一版只服务内部判断。

## Current Architecture

阳朔情报中心作为“以太通量”主项目内的子项目实施，由 Codex 作为每日情报控制 agent。V0.2.0 开始，第一部分“情报收集站”采用本地优先路线：Mac 可本机运行；如 Mac 压力过大，可迁移到 PC worker 24 小时采集，Mac 读取每日资料包进入第二部分。

V0.2.3 开始，真实采集优先走 OpenCLI Browser Bridge：小红书/抖音先建立最近 24 小时标题池，再由 Hermes 按机会/风险筛选，最后只对筛中的视频做本地 ASR 转写。抽帧不是重点，完整语音转文字才是后续“超级智脑”判断视频内容的第一依据。

系统现在按项目内模块分层：

1. **Collector Layer**
   - 负责平台采集和平台适配。
   - V0.2.0 第一优先平台是小红书、抖音、视频号，重点是视频内容、评论内容、同题讨论和基础官方信源辅助监控。
   - 每个平台必须输出统一 raw item schema，不能让平台差异污染后续流程。
   - `hard_dedupe_key` 只用于完全重复内容；不同用户讨论同一事件必须保留，并进入 `topic_cluster_key` 同题聚类。

2. **Normalization Layer**
   - 清洗正文、统一时间、识别语言、保存来源链接、保留原始证据。
   - 中间处理阶段不强制生成中英对照，避免浪费 token。

3. **Scoring Layer**
   - 低 token 规则评分、去重、基础分类、平台权重、新鲜度、互动热度、阳朔相关度、风险词、机会词。
   - 普通清洗、去重、关键词匹配不调用大模型。

4. **Cross Verification Center**
   - 负责 claim 拆解、来源独立性判断、跨平台支持/冲突检查、真假信息风险提示。
   - 重要信息不能只因为单个平台热就直接采信。

5. **GEO Risk Judge**
   - GEO 指 Generative Engine Optimization，即影响 ChatGPT、Gemini、Perplexity 等 AI 搜索/大模型回答的“标准答案”塑造行为。
   - 本项目只输出 GEO 疑似度、叙事操控风险、信息污染概率，不做定性指控。
   - 字段应包含 `geo_risk.probability`、`geo_risk.level`、`geo_risk.reasons`。

6. **DeepSeek V4 Advisor Layer**
   - DeepSeek V4 是可插拔“智库层”，由 Codex 调度参与每日审议、交叉验证建议、GEO 疑似度、内容机会、风险提醒和中英展示润色。
   - 默认模型：`deepseek-v4-pro`。
   - 配置来源：
     - `DEEPSEEK_API_KEY`
     - `DEEPSEEK_BASE_URL=https://api.deepseek.com`
     - `DEEPSEEK_MODEL_ADVISOR=deepseek-v4-pro`
   - 无 key 或 API 失败时必须回退到本地规则审议，不阻断每日流程。

7. **Codex Review Brain**
   - Codex 是每日情报审议总控。
   - 自动生成待审稿，但不自动发布。
   - 对候选信息组织多角色审议、调用 DeepSeek 智库层、提出人工确认问题。

8. **Human Gate + Web/API**
   - 人工确认后才进入网页精选、日报和正式 API。
   - 人工审阅页和最终呈现页要支持中英对照，尤其外网平台内容。
   - 翻译只发生在人工审阅前和最终网页/API 呈现前，中间采集处理不做双语扩写。

## Implemented MVP

当前已实现一个 Python 本地优先闭环，并开始进入 V0.2.0 本地视频情报采集站：

- 低 token 评分与去重：`aetherflux/scoring.py`
- DeepSeek 配置与 JSON client：`aetherflux/deepseek.py`
- 智库层回退/合并逻辑：`aetherflux/advisor.py`
- 多角色审议草稿：`aetherflux/review.py`
- SQLite 存储与人工决策：`aetherflux/storage.py`
- V0.2.0 采集基础模型：`aetherflux/collector_model.py`
- API payload 组装：`aetherflux/api.py`
- 本地网页/API 服务：`aetherflux/server.py`
- 命令行入口：`aetherflux/cli.py`
- 配置驱动流水线：`aetherflux/pipeline.py`
- 网页前端：`aetherflux/web/`
- 默认方向配置：`config/directions.json`
- 样本数据：`data/seed_items.json`
- 每日审议脚本：`scripts/daily_review.sh`
- 架构文档：`docs/architecture.md`

## How To Run

测试：

```bash
python3 -m unittest discover -s tests
python3 -m compileall aetherflux
```

跑一次样本采集和审议：

```bash
python3 -m aetherflux.cli ingest
python3 -m aetherflux.cli review
```

启动本地网页：

```bash
python3 -m aetherflux.cli serve --host 127.0.0.1 --port 8788
```

访问：

```text
http://127.0.0.1:8788
```

`8765` 端口保留给 Triagent；本地 worker/API 预留 `8789`。

每日脚本：

```bash
scripts/daily_review.sh
```

带通用 Webhook：

```bash
AETHERFLUX_WEBHOOK_URL="https://your-webhook.example.com" scripts/daily_review.sh
```

DeepSeek 智库层本地配置示例：

```bash
export DEEPSEEK_API_KEY="your-local-key"
export DEEPSEEK_BASE_URL="https://api.deepseek.com"
export DEEPSEEK_MODEL_ADVISOR="deepseek-v4-pro"
```

## Important Product Decisions

- 第一版优先小红书，但架构必须支持多平台扩展。
- 国内外平台都要考虑；阳朔是全球知名旅游目的地，外网信号不能缺席。
- AI HOT 是重要参考，但本项目呈现要更偏“旅游情报决策台”，不是泛资讯流。
- 网页要好看、有深度，但信息密度应服务内部判断，不做营销落地页。
- 信息交叉验证是核心能力，不是后续附属功能。
- GEO 只表达疑似度和风险概率，不表达事实定罪。
- DeepSeek V4 作为智库层参与审议，不参与低价值机械清洗。
- 自动审议但不自动发布，人工确认后才进入网页和正式 API。
- Supabase Cloud 不保存原始情报、截图、HTML、音视频、评论全文或转写全文；只用于登录和每日轻量日志索引。
- 原始证据默认本地保留 48 小时，可在后台调整；后续可把数据根目录和证据根目录指向 NAS。

## Human Gate

候选情报默认是 `pending`。

只有人工确认成 `approved` 后，才进入：

- `/api/selected`
- `/api/daily`
- `/api/opportunities`
- `/api/foreign-signals`
- `/api/risks`
- `/api/evidence/:id`
- `/api/content-briefs`

`rejected` 条目不会进入新的审议草稿。

## Current API

- `GET /api/candidates`：候选池
- `GET /api/selected`：已确认精选
- `GET /api/daily`：日报结构
- `GET /api/opportunities`：项目机会
- `GET /api/foreign-signals`：外网/外语信号
- `GET /api/risks`：风险预警
- `GET /api/evidence/:id`：证据链
- `GET /api/content-briefs`：后续内容运营 agent 的选题简报
- `POST /api/decisions`：人工确认、驳回、调整权重
- `POST /api/run-ingest`：触发采集与基础评分
- `POST /api/run-review`：生成待审稿
- `GET/POST /api/admin/retention`：本地证据和云日志索引保留设置
- `GET/POST /api/admin/official-sources`：官方信源配置
- `POST /api/admin/missions`：mission 更新，地点/行业/细分变化会标记官方信源需要复核
- `GET /api/daily-bundles`：每日资料包索引
- `GET /api/cloud-log-syncs`：Supabase 轻量日志同步和清理记录

候选和精选 payload 可包含：

- `display.title_zh`
- `display.title_en`
- `display.summary_zh`
- `display.summary_en`
- `translation_status`
- `advisor_notes`
- `cross_check`
- `geo_risk`

## Current Caveats

- `data/seed_items.json` 目前只是样本输入，不是真实平台采集器。
- `data/aetherflux.db` 是本地运行数据库，已被 `.gitignore` 忽略。
- `artifacts/` 是本地截图/验证产物，已被 `.gitignore` 忽略。
- 当前网页/API 使用 Python 标准库 HTTP server，适合 MVP 和内网验证；后续可迁移 FastAPI。
- 视频号视频采集器还未完整实现；V0.2.3 已先把小红书/抖音推进到 OpenCLI 登录态标题池、最近 24 小时过滤、Hermes 初筛和本地 ASR 深处理框架。

## Recommended Next Steps

1. 完成真实小红书、抖音、视频号登录态视频采集 adapter。
2. 接入本地 ASR，把视频音频转成分段文字。
3. 完成 PC worker 部署脚本和每日资料包读取流程。
4. 完成后台采集控制页、官方信源页、保留时长页和云日志页。
5. 第二部分“超级智脑”读取每日资料包，做权重、真假、广告和项目价值判断。

## 版本管理 / Versioning Rules

本项目使用 [Semantic Versioning](https://semver.org/lang/zh-CN/)，格式为 `V主版本.次版本.修订号`（如 `V0.1.0`）。

从 V0.2.3 开始，每个正式版本都必须同步 GitHub 仓库并发布版本号；不能再只写本地更新日志。

### 每次版本更新必须执行

1. **更新 `CHANGELOG.md`**：在文件顶部按格式新增版本条目，记录新增、变更、修复、移除等内容。
2. **提交并推送 GitHub**：验证通过后提交到当前版本分支，并推送 `main` 到 `origin`。
3. **Git 标签**：在对应 commit 上打 annotated tag，格式 `v0.1.0`（小写 v），并推送标签到 GitHub。
   ```bash
   git push origin main
   git tag -a v0.1.0 -m "V0.1.0 初始版本"
   git push origin v0.1.0
   ```
4. **GitHub Release**：如果 `gh` 已安装并已登录，创建对应 Release；如果未登录，必须在最终汇报中说明 tag 已推送但 Release 需要补发。

### 文档语言规范

- 项目主 README（`README.md`）以中文书写，面向中文使用者。
- 英文使用者请查阅 `README_EN.md`。
- 所有代码注释、提交信息、升级日志均可使用中文。
- AGENTS.md 为本项目的记忆文件，Codex 在每次对话中都会读取。
