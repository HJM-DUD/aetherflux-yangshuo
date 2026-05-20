# AetherFlux Yangshuo

阳朔旅游情报决策系统，用于自用内容选题、项目判断、风险识别和后续运营 agent 数据接口。

第一版是无外部依赖的 Python 最小闭环：采集样本、脚本化评分去重、Mac Codex 审议草稿、人工确认闸门、网页决策台和内部 JSON API。

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

如果服务跑在 PC 上，并且 Mac 通过 Tailscale 访问：

```bash
python3 -m aetherflux.cli serve --host 0.0.0.0 --port 8765
```

Mac 访问：

```text
http://100.123.181.83:8765
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
- 模型审议目前保留为可插拔边界，第一版默认用规则角色生成待审稿，避免每日 token 消耗失控。
- 自动流程只生成待审稿，不自动发布；确认后的内容才进入网页精选和正式 API。
