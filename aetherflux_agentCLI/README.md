# AetherFlux AgentCLI Collector

版本：V0.2.5

这个子项目是“agent 主导、OpenCLI/脚本辅助”的采集模式。它适合深挖、复杂页面、异常处理和高价值线索追踪。Hermes 暂时作为默认主导 agent，但必须能通过配置替换。

## 怎么用

干跑，不触发真实采集：

```bash
python3 -m aetherflux_agentcli.cli run --dry-run
python3 -m aetherflux_agentcli.cli scheduler-hook --dry-run
python3 -m aetherflux_agentcli.cli backend-hook --dry-run
```

生成本地每日资料包：

```bash
python3 -m aetherflux_agentcli.cli run --bundle-root data/daily_bundles
```

生成本地资料包并复制到主项目统一入口：

```bash
python3 -m aetherflux_agentcli.cli run \
  --bundle-root data/daily_bundles \
  --main-inbox ../data/daily_bundles_inbox
```

## 自主边界

agentCLI 可以在白名单范围内高度自主：

- 打开公开平台页面
- 搜索
- 滚动
- 展开公开评论
- 提取公开可见文本

必须停止并请求 GuGU 的动作：

- 登录、填密码、验证码、滑块
- 账号设置
- 发布/发帖/评论/私信
- 支付、下单、邀请、修改外部账号设置
- 删除
- 上传私有文件

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

## Agent 替换

`config/agents.json` 里配置 agent 命令模板。默认是 Hermes：

```json
["hermes", "-z", "{payload}", "--provider", "deepseek", "--model", "deepseek-v4-pro"]
```

以后换成其他 agent 时，先改配置，不要把模型命令写死在工作流里。
