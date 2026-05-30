# Changelog

## [V0.2.5] - 2026-05-30

### Added

- 新建 shellCLI 独立采集子项目骨架。
- 新增目录 + JSONL 每日资料包生成器。
- 新增主项目资料包 inbox 复制入口。
- 新增 Hermes 命令模板配置 `config/agents.json`。
- 新增小红书/抖音支持平台规划，视频号默认禁用占位。
- 新增 `run`、`scheduler-hook`、`backend-hook` 三个 CLI 入口。
- 新增项目内 Codex skill：`aetherflux-shellcli-collector`。
- 新增真实 OpenCLI 采集路径：运行前检查 `opencli doctor`，按配置打开小红书/抖音页面、搜索、滚动、解析 JSON，并写入每日资料包。
- 新增 `config/collect.json` 默认采集配置。
