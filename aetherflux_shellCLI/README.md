# AetherFlux ShellCLI Collector

版本：V0.2.5

这个子项目是“脚本主导、agent 监工”的采集模式。它适合稳定、重复、低 token 成本的日常采集：OpenCLI 和本地脚本负责跑固定流程，Hermes 暂时负责监工、日志诊断、标题筛选和 ASR 深处理判断。

## 怎么用

干跑，不触发真实采集：

```bash
python3 -m aetherflux_shellcli.cli run --dry-run
python3 -m aetherflux_shellcli.cli scheduler-hook --dry-run
python3 -m aetherflux_shellcli.cli backend-hook --dry-run
```

真实采集前先确认 OpenCLI Browser Bridge 已通：

```bash
opencli doctor
```

生成本地每日资料包：

```bash
python3 -m aetherflux_shellcli.cli run --config config/collect.json --no-sleep
```

生成本地资料包并复制到主项目统一入口：

```bash
python3 -m aetherflux_shellcli.cli run \
  --config config/collect.json \
  --main-inbox ../data/daily_bundles_inbox
```

`--no-sleep` 适合调试；正式长期采集时不要加，让脚本按配置里的 `wait_seconds` 慢一点跑，降低平台风控风险。

## 配置

默认配置在 `config/collect.json`：

- `platforms`：默认小红书、抖音、视频号占位。
- `queries`：搜索词。
- `target_per_platform`：每个平台取多少轮关键词。
- `max_items_per_task`：每个关键词最多取多少条。
- `freshness_window_hours`：新鲜度窗口。
- `scroll_rounds_per_query`：每个关键词滚动轮数。
- `main_inbox`：主项目资料包统一入口。

## 输出

资料包默认写入：

```text
data/daily_bundles/daily_bundle_YYYY-MM-DD/RUN_ID/
```

每个资料包包含：

- `manifest.json`
- `raw_items.jsonl`
- `screened_items.jsonl`
- `asr_results.jsonl`
- `agent_decisions.jsonl`
- `errors.jsonl`

主项目入口按 `mode/date/run_id` 保存，所以 shellCLI 和 agentCLI 可以并行对比。

采集过程中还会写：

- `artifacts/opencli/live/`：每个 OpenCLI 任务的归一化结果。
- `logs/opencli/live/`：每个 OpenCLI 任务的原始 stdout/stderr 摘要。

## Agent 替换

`config/agents.json` 里配置当前 agent 命令模板。默认是 Hermes：

```json
["hermes", "-z", "{payload}", "--provider", "deepseek", "--model", "deepseek-v4-pro"]
```

以后要换 agent，优先改这个配置，不要把模型名写死到采集流程里。

## 平台状态

- 小红书：V0.2.5 支持。
- 抖音：V0.2.5 支持。
- 视频号：V0.2.5 只保留占位，默认跳过并写入错误记录，不进入真实采集队列。
