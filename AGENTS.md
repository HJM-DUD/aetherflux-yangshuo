# AGENTS.md — 以太通量 / AetherFlux 项目记忆（V0.2.5）

> **读者**：这是给 Codex 看的项目记忆文件。Codex 每次对话都会读取它，用来理解项目是什么、怎么分层、每个文件干什么。

---

## 1. 项目身份

- **中文名**：以太通量 / 目录名：`AetherFlux_yitaitongliang`
- **当前子项目**：旅游情报决策系统
- **版本**：V0.2.5（2026-05-30）
- **定位**：服务 GuGU 自己做内容选题、项目判断、风险识别、交叉验证、线上运营和后续 agent 决策。**不是游客攻略站，不是对外 SaaS。**
- **技术栈**：Python 3.9+ / FastAPI + React/Vite + Tailwind + SQLite / OpenCLI Browser Bridge
- **总目标**：最终做成 GuGU 自用的大型 agent 应用；外部人员只通过另行设计的 Web 端使用，不直接维护本机 Triagent 系统。

### 五大部分总框架

1. **情报收集站**：V0.2.x 当前主线。由 Hermes 或本地脚本承担长期采集调度，采集指定账号、公开平台搜索结果、评论、视频 ASR、官方信源和人工高权重消息，形成候选情报和每日资料包。
2. **超级智脑**：后续主线。调用 Codex / Hermes / Antigravity / DeepSeek，对资料包做真假判断、机会识别、风险识别、权重调整、交叉验证和决策建议。
3. **线上运维中心**：后续。管理 GuGU 的互联网账号规划、内容节奏、维护、获客和运营动作。
4. **内容生成工厂**：后续。根据情报和运营决策生成图文、视频、图片、笔记、脚本等内容，接入多模态工作流。
5. **线下经营智控**：后续。管理客户、行程、成本、资源和经营执行，例如旅游行业的行程规划、报价与履约控制。

V0.2.x 不要把第二到第五部分硬做成假功能，只需要为它们保留清晰接口、数据结构和页面入口。第一部分的数据量和质量是后续四部分的地基。

### V0.2.5 双模式采集子项目

| | shellCLI | agentCLI |
|---|---|---|
| **谁主导** | 固定脚本 + OpenCLI，预定义 JS eval 序列 | Agent（Hermes）观察页面 → 自主决策 → 安全闸门 → 执行 |
| **Agent 角色** | 监工：采集后筛选、诊断、质量判断 | 主导者：全程决策采集策略 |
| **适合场景** | 低成本日常定时采集，固定流程 | 复杂页面、异常处理、登录墙绕过、高价值线索深挖 |
| **采集流程** | 打开搜索 → 点筛选 → 点最新 → 点一天内 → 滚动提取 | Observe-Plan-Act 循环：观察页面 → agent 决策 action → 执行 |
| **稳定性** | 高，固定脚本结果可预期 | 灵活但依赖 agent 判断质量 |
| **当前状态** | ✅ 已可用，真实采集小红书+抖音（collection.py 已实现） | 🔧 骨架已有（cli/bundle/safety/agent_adapter），collector 实现中 |

- 两个子项目都必须可独立运行，并输出相同契约的每日资料包（manifest.json + 5 个 jsonl 文件）。
- 每日资料包本地保留一份；需要给主项目消费时，复制到 `data/daily_bundles_inbox/{mode}/{date}/{run_id}/`。
- 产品运行时的 agent 能力不依赖 Triagent；Hermes 只是默认 agent，通过各子项目 `config/agents.json` 命令模板替换。
- 视频号在 V0.2.5 只保留默认禁用占位，不进入真实采集队列。

### V0.2.5 三方审查修复（2026-05-30）

四项修复已合入 `codex/v025-collector-rebuild`，由 Codex + Hermes + Antigravity 交叉审查一致通过：

- **P2 浏览器 session 泄漏**：`collector.py` 的 `_run_sequence` 加 `TimeoutExpired`/`FileNotFoundError` 捕获，task 循环加 `try/finally` 确保 close。
- **P1 配置传递链**：打通前端 → API → CLI → collector 的 platforms/queries/override 全链路，`PUT config` 时 `_sync_collect_json` 解决配置双重存储。
- **P1 空资料包**：`_bundle_command` 改为 `_copy_latest_bundle_script`，查找最近真实 bundle，`raw_items=0` 时跳过。
- **UX 关键词拦截**：前端加关键词为空前置拦截 + fetch body 传 `queries` 字段。

### Web 与权重原则

- 所有人机交互默认落到 Web 端：后台给 GuGU 调整采集、审阅、定稿、人工干预；前端给多人登录查看情报结果。
- Web 端设计默认遵循 UI UX Pro Max：高信息密度、专业工具感、清晰表格和可操作控件，避免做成宣传页。
- 采集方向必须可由 GuGU 人工配置：地点（如武汉、帕劳、阳朔）、行业（V0.2.x 先旅游）、细分类别（景区、民宿、酒店、旅游餐饮、疗愈等）和自定义搜索词。
- 平台设计要保留扩展位：当前优先小红书、抖音；后续接视频号、Instagram、TikTok、OTA 和更多公开平台。
- 权重分级统一使用 `T1` 到 `T5`：`T1` 最高权重（例如 GuGU 手动录入的内部消息），`T2` 高权重，`T3` 中权重，`T4` 次级权重，`T5` 低权重。
- 人工特别信息干预入口必须保留；这类信息可以作为最高权重情报进入审议，但仍需标注来源为人工输入。

---

## 2. 安全规则（本项目特有）

1. **禁止批量删除**：`rm -rf`、`del /s`、`rd /s`、`rmdir /s`、`Remove-Item -Recurse` 全部封禁。需要删文件时一次只删一个明确路径；需要批量删除时停止操作，请 GuGU 手动处理。
2. **回收站**：前端多选删除只进入软删除回收站，14 天内可恢复；14 天后只标记「可清理」，不执行批量物理删除。
3. **敏感信息**：API key、cookie、token、密码不写仓库、文档、测试、前端代码或提交记录。DeepSeek key 只能通过环境变量或 `.env` 读取。
4. **Supabase 边界**：Supabase Cloud 只用于登录和每日轻量日志索引。**不上传**：原始情报正文、评论全文、截图、HTML、视频帧、音频、转写全文。
5. **本地证据**：原始证据默认本地保留 48 小时，可在后台 `GET/POST /api/v1/admin/retention` 调整。
6. **高风险操作**：凭据、隐私文件、浏览器登录态、外部账号动作、删除/迁移、跨模块大改、支付/发布必须先问 GuGU。

---

## 3. Triagent 协作规则（浓缩）

Codex 是主脑，Hermes（DeepSeek）和 Antigravity（Gemini）是子 agent。

- **Hermes 适合**：代码搜索、文件梳理、日志分析、依赖盘点、低/中风险机械改动、明确路径内的小范围实现。不要把图片塞给 Hermes。
- **Antigravity 适合**：多模态、长上下文、前端/原型、Google 生态、替代方案分析。
- **`/all`**：超复杂任务，Codex 先定义问题，三方交叉验证，Codex 最终裁决。
- **子 agent 任务包**：必须包含删除规则、当前工作目录、是否允许编辑、允许路径、输出格式和停止条件。
- **正式任务优先走 `triagent run`**（网页观察台可看到日志），直接 CLI 仅备用/调试。
- **Codex 必须审查子 agent 的 diff**，运行验证命令，再向 GuGU 汇报。

---

## 4. 架构分层（V0.2.5 实际文件映射）

```
┌─────────────────────────────────────────────────┐
│  Collector Layer（采集层）                        │
│  collector_model.py   统一 raw item schema       │
│  xhs.py               小红书离线 JSON feed 驱动   │
│  live_collectors.py   Chrome CDP 实时采集 (V0.2.1)│
│  live_rotation.py     自适应轮转慢采集调度         │
│  opencli_collectors.py OpenCLI Browser Bridge (V0.2.2→V0.2.3主路线)│
│  query_planner.py     混合关键词池规划             │
├─────────────────────────────────────────────────┤
│  Normalization Layer（清洗层）                    │
│  freshness.py         24h新鲜度解析与过滤          │
│  quality.py           采集质量闸门                 │
├─────────────────────────────────────────────────┤
│  Scoring Layer（评分层）                          │
│  scoring.py           低token规则评分/去重/分类/权重│
├─────────────────────────────────────────────────┤
│  Review Layer（审议层）                           │
│  review.py            多角色审议 + 交叉验证 + GEO   │
│  deepseek.py          DeepSeek JSON client        │
│  advisor.py           智库层回退/合并逻辑           │
├─────────────────────────────────────────────────┤
│  ASR Pipeline（视频深处理）                       │
│  asr_pipeline.py      音频提取→ASR转写→分段→摘要   │
├─────────────────────────────────────────────────┤
│  Storage（存储层）                                │
│  storage.py           SQLite + 候选状态管理        │
├─────────────────────────────────────────────────┤
│  API & Server（服务层）                           │
│  admin_api.py         V0.2.4 FastAPI /api/v1/*    │
│  server.py            V0.1 旧静态 HTTP（备用）      │
│  api.py               payload 组装 + 旧 /api/* 兼容│
├─────────────────────────────────────────────────┤
│  Frontend（前端）                                 │
│  web/                 V0.1 旧静态 HTML/CSS/JS      │
│  web-admin/           V0.2.4 React/Vite + shadcn   │
├─────────────────────────────────────────────────┤
│  V0.2.5 Collector Subprojects（双模式采集子项目） │
│  aetherflux_shellCLI/ OpenCLI/脚本主导 + agent监工│
│  aetherflux_agentCLI/ agent主导 + OpenCLI辅助     │
├─────────────────────────────────────────────────┤
│  CLI & Pipeline（入口）                           │
│  cli.py               命令入口                     │
│  pipeline.py          配置驱动流水线               │
├─────────────────────────────────────────────────┤
│  Config（配置）                                   │
│  config/directions.json     地点/主题/平台权重     │
│  config/live_collect.json   V0.2.1+ 采集参数       │
└─────────────────────────────────────────────────┘
```

### 辅助目录

| 目录 | 说明 |
|------|------|
| `tests/` | 覆盖评分、审议、存储、API、采集、ASR、前端等 19 个测试文件 |
| `scripts/` | `daily_review.sh`、`hermes_collect_opencli.sh`、`open_chrome_cdp.sh` 等 |
| `data/` | `seed_items.json`（样本）、`aetherflux.db`（本地库，.gitignore） |
| `artifacts/` | 截图、采集输出、验证产物（.gitignore） |
| `logs/` | 采集日志（.gitignore） |
| `dist/` | `npm run build` 产物（.gitignore） |
| `docs/` | `architecture.md` 架构文档 |

---

## 5. 数据流

```
后台配置 mission → 混合关键词池 → OpenCLI 标题池（24h 过滤）
→ Hermes 初筛 → 视频 ASR 深处理 → 本地 SQLite 入库
→ 评分去重 → 交叉验证 → GEO 疑似度 → DeepSeek 智库审议
→ 人工确认（pending→approved）→ /api/v1/intelligence/* 输出
→ 每日资料包 → 第二部分「超级智脑」
```

关键概念：

- **`hard_dedupe_key`**：只在完全重复时合并（同 URL、同平台 ID、同媒体指纹）
- **`topic_cluster_key`**：不同用户讨论同一事件保留原内容，聚合热度
- **ASR 优先**：完整语音转文字是视频理解第一依据，抽帧默认关闭
- **`geo_risk`**：只输出 `probability` / `level` / `reasons`，不做定性指控

---

## 6. 关键产品决策

1. **本地优先**：原始情报、评论、音频、转写只存本地/NAS。Supabase 只做登录 + 日志索引。
2. **ASR > 抽帧**：完整语音转写才是理解视频内容的核心。
3. **人工闸门**：自动审议但不自动发布。`pending` → 人工确认 `approved` → 才进入 `/api/v1/intelligence/*`。
4. **GEO 只表达概率**：疑似度、叙事操控风险、信息污染概率，不做事实定性。
5. **评论是重点**：热评、最新评论、作者回复、风险/机会词命中评论分层采集。相似评论保留为热度/水军信号。
6. **去重≠删讨论**：不同人说同一件事 = 重要信号，用 `topic_cluster_key` 聚合而非删除。
7. **中英对照**：只在人工审阅前和最终网页/API 呈现前生成。中间采集处理不做双语扩写，省 token。
8. **第一版优先小红书**，架构已为抖音、视频号多平台准备。国内外平台都覆盖。
9. **DeepSeek V4**：可插拔智库层，参与审议/GEO/润色，不参与低价值机械清洗。无 key 时回退规则审议。
10. **官方信源**：独立模块，地点/行业变化后必须重新确认，不自动沿用。

---

## 7. 入口命令速查

| 命令 | 说明 |
|------|------|
| `python3 -m aetherflux.cli serve` | 启动 V0.2.5 FastAPI 后台（默认 127.0.0.1:8788） |
| `python3 -m aetherflux.cli legacy-serve` | V0.1 旧静态后台（备用） |
| `python3 -m aetherflux.cli ingest` | 样本采集与评分 |
| `python3 -m aetherflux.cli review` | 生成审议草稿 |
| `python3 -m aetherflux_shellcli.cli run` | shellCLI 真实采集（脚本主导） |
| `python3 -m aetherflux_agentcli.cli run` | agentCLI 真实采集（agent 主导，实现中） |
| `python3 -m aetherflux.cli opencli-rotate` | OpenCLI 采集轮转（V0.2.3 旧入口，V0.2.5 Web 后台已不再使用） |
| `python3 -m aetherflux.cli live-rotate` | CDP 采集轮转（旧） |
| `scripts/hermes_collect_opencli.sh` | Hermes 完整采集流程 |
| `npm run build && npm test` | 前端构建 + 测试 |

端口：`8765`（Triagent）、`8788`（AetherFlux Web）、`8789`（预留 worker/API）。

DeepSeek 配置：`DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL_ADVISOR=deepseek-v4-pro`。

---

## 8. V0.2.4 主 API（`/api/v1/*`）

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
- `GET/POST /api/v1/trash` / `/api/v1/trash/restore` / `/api/v1/trash/mark-cleanable`
- `GET /api/v1/system/status` / `/api/v1/system/deepseek-smoke-test` / `/api/v1/system/opencli-doctor` / `/api/v1/system/diagnose`
- `GET /api/v1/title-pool` / `/api/v1/video-processing`
- `GET /api/v1/agent/apis` / `/api/v1/release/status`

旧 `/api/*` 只做旧壳兼容，V0.2.4 主接口已统一迁移到 `/api/v1/*`。

---

## 9. 当前限制（V0.2.5）

- 视频号无稳定网页端内容入口，V0.2.5 仅保留禁用占位，不进入真实采集队列。
- 小红书/抖音采集依赖 OpenCLI Browser Bridge + Chrome 登录态，采集稳定性仍在打磨。
- `data/seed_items.json` 只是样本输入，不是真实平台采集器。
- PC worker 部署方案未完成。
- 第二部分「超级智脑」（每日资料包消费、权重/真假/广告判断）尚未开始。

---

## 10. 版本管理

- **SemVer**：`V主版本.次版本.修订号`（如 V0.2.4）
- **每次版本发布**：
  1. 更新 `CHANGELOG.md`
  2. 提交 + 推送 `main`
  3. 打 annotated tag（`git tag -a v0.2.4 -m "V0.2.4 …"`）+ 推送 tag
  4. 创建 GitHub Release（`gh` 已登录时；否则告知 GuGU tag 已推送需补发 Release）
- **文档语言**：`README.md` 中文，`README_EN.md` 英文。代码注释、提交信息可用中文。
- **AGENTS.md** 是本文件，Codex 每次对话都会读取。版本更新时同步更新此文件。
