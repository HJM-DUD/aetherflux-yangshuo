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

取消 PC/Hermes 独立情报中心路线。阳朔情报中心作为“以太通量”主项目内的子项目实施，由 Codex 作为每日情报控制 agent。

系统现在按项目内模块分层：

1. **Collector Layer**
   - 负责平台采集和平台适配。
   - 第一优先平台是小红书，后续扩展抖音、微博、大众点评、携程、Tripadvisor、Reddit、YouTube、Instagram/TikTok、官方公告、天气交通等。
   - 每个平台必须输出统一 raw item schema，不能让平台差异污染后续流程。

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

当前已实现一个无外部依赖的 Python 最小闭环：

- 低 token 评分与去重：`aetherflux/scoring.py`
- DeepSeek 配置与 JSON client：`aetherflux/deepseek.py`
- 智库层回退/合并逻辑：`aetherflux/advisor.py`
- 多角色审议草稿：`aetherflux/review.py`
- SQLite 存储与人工决策：`aetherflux/storage.py`
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
python3 -m aetherflux.cli serve --host 127.0.0.1 --port 8765
```

访问：

```text
http://127.0.0.1:8765
```

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
- 真实小红书、抖音、Reddit、Tripadvisor、YouTube 等采集器还未实现。

## Recommended Next Steps

1. 在项目内实现小红书采集适配器，统一输出 raw item schema。
2. 增强 Cross Verification Center，把 claim 拆解、来源独立性、支持/冲突证据做成结构化字段。
3. 把 GEO 疑似度显示继续优化到审阅页和最终精选页。
4. 增加真实平台信源长期权重、截图证据、网页快照和反馈闭环。
5. 扩展到抖音、微博、大众点评、携程、Tripadvisor、Reddit、YouTube 等平台。

## 版本管理 / Versioning Rules

本项目使用 [Semantic Versioning](https://semver.org/lang/zh-CN/)，格式为 `V主版本.次版本.修订号`（如 `V0.1.0`）。

### 每次版本更新必须执行

1. **更新 `CHANGELOG.md`**：在文件顶部按格式新增版本条目，记录新增、变更、修复、移除等内容。
2. **Git 标签**：在对应 commit 上打 annotated tag，格式 `v0.1.0`（小写 v），并推送标签到 GitHub。
   ```bash
   git tag -a v0.1.0 -m "V0.1.0 初始版本"
   git push origin v0.1.0
   ```
3. **提交推送**：将 `CHANGELOG.md` 的更新和标签一起提交并推送到 GitHub。

### 文档语言规范

- 项目主 README（`README.md`）以中文书写，面向中文使用者。
- 英文使用者请查阅 `README_EN.md`。
- 所有代码注释、提交信息、升级日志均可使用中文。
- AGENTS.md 为本项目的记忆文件，Codex 在每次对话中都会读取。
