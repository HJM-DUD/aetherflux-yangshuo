# AetherFlux Yangshuo

“以太通量”当前子项目：阳朔旅游情报决策系统，用于自用内容选题、项目判断、风险识别、交叉验证、GEO 疑似度判断和后续运营 agent 数据接口。

第一版是无外部依赖的 Python 最小闭环：采集样本、脚本化评分去重、Codex 审议草稿、可插拔 DeepSeek V4 智库层、人工确认闸门、网页决策台和内部 JSON API。

## Quick Start

```bash
python3 -m unittest discover -s tests
python3 -m aetherflux.cli ingest
python3 -m aetherflux.cli review
python3 -m aetherflux.cli serve --host 127.0.0.1 --port 8765
```

打开：

```text
http://127.0.0.1:8765
```

## Daily Review

手动跑每日审议：

```bash
scripts/daily_review.sh
```

带通用 Webhook：

```bash
AETHERFLUX_WEBHOOK_URL="https://your-webhook.example.com" scripts/daily_review.sh
```

Webhook payload 是通用 JSON，后续可以接飞书、企业微信、n8n、Dify 或自定义机器人。

DeepSeek 智库层通过本机环境变量启用；不要把密钥写进仓库：

```bash
export DEEPSEEK_API_KEY="your-local-key"
export DEEPSEEK_BASE_URL="https://api.deepseek.com"
export DEEPSEEK_MODEL_ADVISOR="deepseek-v4-pro"
```

## API

- `GET /api/candidates`：候选池
- `GET /api/selected`：人工确认后的精选
- `GET /api/daily`：日报结构
- `GET /api/opportunities`：项目机会
- `GET /api/foreign-signals`：外网/外语信号
- `GET /api/risks`：风险预警
- `GET /api/evidence/:id`：证据链
- `GET /api/content-briefs`：供内容运营 agent 使用的选题简报
- `POST /api/decisions`：人工确认、驳回、调整权重
- `POST /api/run-ingest`：触发采集与基础评分
- `POST /api/run-review`：生成待审稿，可附带 `webhook_url`

## Current Boundary

- 采集器目前使用 `data/seed_items.json` 作为样本输入，真实小红书、抖音、Reddit、Tripadvisor、YouTube 等采集器后续逐个替换。
- DeepSeek V4 是可插拔智库层；无 key 或 API 失败时回退规则审议，避免每日流程中断。
- 中英对照只在人工审阅前和最终呈现前生成，中间处理不做双语扩写以节省 token。
- 自动流程只生成待审稿，不自动发布；确认后的内容才进入网页精选和正式 API。
