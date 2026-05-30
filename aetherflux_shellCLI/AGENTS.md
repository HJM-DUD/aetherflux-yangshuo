# AGENTS.md - AetherFlux ShellCLI Collector

GuGU 对编程只是略懂皮毛，回复要尽量中文、直接、少术语。

## 子项目定位

这是 V0.2.5 的 shellCLI 采集子项目：脚本和 OpenCLI 掌握控制流，agent 只做监工、筛选、日志诊断和 ASR 深处理判断。它必须能独立运行，并产出与 agentCLI 相同契约的每日资料包。

## 安全规则

- 禁止批量删除文件或目录。
- 不要使用 `rm -rf`、`del /s`、`rd /s`、`rmdir /s`、`Remove-Item -Recurse`。
- 需要删除文件时，只能一次删除一个明确路径的文件。
- 不写入 API key、cookie、token、密码。
- 不上传原始情报正文、评论全文、截图、HTML、视频帧、音频、转写全文到云端。

## 工作流边界

- 常规采集由 `python3 -m aetherflux_shellcli.cli run` 或脚本入口触发。
- `scheduler-hook` 留给定时任务。
- `backend-hook` 留给主项目 Web 后台按钮。
- Hermes 当前只是默认监工 agent，可通过 `config/agents.json` 替换。
- 视频号在 V0.2.5 默认禁用，不允许制造假成功。
- 真实采集前必须经过 `opencli doctor`；如果 OpenCLI Browser Bridge 没通，停止，不写假成功资料包。

## 输出要求

每日资料包必须包含：

- `manifest.json`
- `raw_items.jsonl`
- `screened_items.jsonl`
- `asr_results.jsonl`
- `agent_decisions.jsonl`
- `errors.jsonl`

本地保留一份；如传入 `--main-inbox`，再复制一份到主项目统一入口。
