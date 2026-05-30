# AGENTS.md - AetherFlux AgentCLI Collector

GuGU 对编程只是略懂皮毛，回复要尽量中文、直接、少术语。

## 子项目定位

这是 V0.2.5 的 agentCLI 采集子项目：agent 掌握控制流，OpenCLI 或本地脚本只提供工具。它必须能独立运行，并产出与 shellCLI 相同契约的每日资料包。

## 安全规则

- 禁止批量删除文件或目录。
- 不要使用 `rm -rf`、`del /s`、`rd /s`、`rmdir /s`、`Remove-Item -Recurse`。
- 需要删除文件时，只能一次删除一个明确路径的文件。
- 不写入 API key、cookie、token、密码。
- 不上传原始情报正文、评论全文、截图、HTML、视频帧、音频、转写全文到云端。

## 自主操作硬边界

允许：

- 打开公开平台页面
- 搜索
- 滚动
- 展开公开评论
- 提取公开可见文本

必须停止并请求 GuGU：

- 登录、密码、验证码、滑块
- 账号设置
- 发布、评论、私信、邀请
- 支付、下单
- 删除
- 上传私有文件

## 当前状态（V0.2.5，2026-05-30）

- `cli.py`：骨架已完成（`run`/`scheduler-hook`/`backend-hook`），已加 `--platforms`/`--queries` 参数。
- `bundle.py`：每日资料包契约已实现。
- `safety.py`：自主操作硬边界已实现。
- `agent_adapter.py`：Hermes 命令模板已实现。
- `collector.py`：Observe-Plan-Act 采集循环**实现中**。
- CLI 已加 `--platforms`/`--queries`（TODO: agentCLI collector 实现后接线）。

## 工作流接口

- `run` 是人工/脚本直接运行入口。
- `scheduler-hook` 留给定时任务。
- `backend-hook` 留给主项目 Web 后台按钮。
- `config/agents.json` 是 agent 替换入口。
- 本地保留资料包；如传入 `--main-inbox`，再复制到主项目统一入口。
