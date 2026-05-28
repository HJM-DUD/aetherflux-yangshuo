# AetherFlux Yangshuo

“以太通量”当前子项目：阳朔旅游情报决策系统，用于自用内容选题、项目判断、风险识别、交叉验证、GEO 疑似度判断和后续运营 agent 数据接口。

V0.2.0 升级为本地优先的视频情报收集站：重点采集小红书、抖音、视频号的视频、评论、同题讨论、官方信源辅助信息，并生成每日资料包交给后续“超级智脑”分析。原始情报、截图、视频帧、音频、评论全文和转写全文只保存在本地或后续 NAS；Supabase Cloud 只用于登录和每日轻量日志索引。

## Quick Start

```bash
python3 -m unittest discover -s tests
python3 -m aetherflux.cli ingest
python3 -m aetherflux.cli review
python3 -m aetherflux.cli serve --host 127.0.0.1 --port 8788
```

打开：

```text
http://127.0.0.1:8788
```

`8765` 端口保留给 Triagent；AetherFlux Web 默认使用 `8788`，本地 worker/API 预留 `8789`。

## Daily Review

小红书首采近 7 天内容，并输出给后续 `ingest` 使用的 raw item JSON：

```bash
python3 -m aetherflux.cli xhs backfill --days 7 --source data/xhs_source_items.json --output artifacts/xhs_raw_items.json
python3 -m aetherflux.cli ingest --seed artifacts/xhs_raw_items.json
```

## V0.2.0 Local Collector

V0.2.0 的采集层按本地优先设计：

- `hard_dedupe_key` 只合并完全重复内容，例如同 URL、同平台内容 ID、同媒体指纹。
- `topic_cluster_key` 聚合不同用户讨论同一事件，不删除原始条目，作为热度信号交给第二部分判断。
- 视频处理优先使用本机 `ffmpeg` 生成关键帧和音频；语音转文字优先本地 ASR。
- 评论采集保留热门、最新、作者回复和命中风险/机会关键词的评论。
- 官方信源在后台单独配置；地点、行业、细分变化后需要重新确认，不能沿用上一个地区的官方地址。
- 每日生成 `daily_bundle_YYYY-MM-DD`，作为第一部分交给第二部分的标准资料包。

本地证据默认保留 48 小时，可在后台调整。清理任务只逐个删除明确文件路径，不删除目录，不使用批量删除命令。

之后每天只采当天且晚于上次成功水位线的新内容：

```bash
python3 -m aetherflux.cli xhs daily --source data/xhs_source_items.json --output artifacts/xhs_raw_items.json
python3 -m aetherflux.cli ingest --seed artifacts/xhs_raw_items.json
```

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
- `GET /api/admin/retention`：本地证据和云日志索引保留设置
- `POST /api/admin/retention`：调整本地证据保存小时数和云日志保留月数
- `GET /api/admin/official-sources`：官方信源列表
- `POST /api/admin/official-sources`：添加或更新官方信源
- `POST /api/admin/missions`：更新 mission；地点/行业/细分变化会标记官方信源需复核
- `GET /api/daily-bundles`：每日资料包索引
- `GET /api/cloud-log-syncs`：Supabase 轻量日志同步/清理记录

## Current Boundary

- `ingest` 仍可使用 `data/seed_items.json` 作为样本输入；小红书已新增 `xhs backfill` / `xhs daily` 采集入口，当前驱动读取登录态浏览器或 opencli 后续可落盘的 JSON feed。
- 抖音、视频号的视频采集适配器会按统一 raw item schema 继续扩展。
- PC worker 是预留部署模式：如果 Mac 长时间运行压力过大，可把第一部分迁移到 PC，由 PC 生成每日资料包，Mac 读取资料包进入第二部分。
- DeepSeek V4 是可插拔智库层；无 key 或 API 失败时回退规则审议，避免每日流程中断。
- 中英对照只在人工审阅前和最终呈现前生成，中间处理不做双语扩写以节省 token。
- 自动流程只生成待审稿，不自动发布；确认后的内容才进入网页精选和正式 API。
