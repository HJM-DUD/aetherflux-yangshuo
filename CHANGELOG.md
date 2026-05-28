# 升级日志 / Changelog

本文档记录「以太通量 / AetherFlux」阳朔旅游情报决策系统的所有版本变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，并使用 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

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

[V0.1.0]: https://github.com/HJM-DUD/aetherflux-yangshuo/releases/tag/v0.1.0
