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

- `cli.py`：已接入真实采集入口（`run`/`scheduler-hook`/`backend-hook`），支持 `--platforms`、`--queries`、`--stage`、`--no-sleep`。
- `collector.py`：已实现 agent 主导 + OpenCLI 辅助的真实采集；小红书会点击 `筛选`/`最新`/`一天内`，抖音优先使用 `sort_type=2&publish_time=1`，并在每个平台任务后关闭 browser session。
- `bundle.py`：每日资料包契约已实现。
- `safety.py`：自主操作硬边界已实现。
- `agent_adapter.py`：Hermes 命令模板已实现。
- `media_asr.py`：视频下载 + `ffmpeg` 音频提取 + Whisper ASR 已接入；优先通过 OpenCLI 详情页解析 `video.currentSrc` 下载，`yt-dlp` 是备用路径；已按 GuGU 授权允许 `yt-dlp` 使用 Chrome cookie；当前可识别 `/Users/gugu/Library/Python/3.9/bin/mlx_whisper` 命令行后端。
- `media_asr.py`：ASR 后必须写 `information_value`，用 `useful`、`low_value`、`review_needed`、`needs_ocr` 区分可用情报、纯配乐/低信号视频、待人工复核和图文待 OCR。
- `douyin.txt`：插件源码显示第三方解析路径会把抖音 URL 发给 `tiktokio.com` 并读取 `.tk-down-link`；这只能作为 GuGU 明确允许后的外部备用方案，默认不启用。
- `config/collect.json`：真实采集默认配置已补齐；`config/agents.json` 仍是 agent 替换入口。

## 工作流接口

- `run` 是人工/脚本直接运行入口。
- `scheduler-hook` 留给定时任务。
- `backend-hook` 留给主项目 Web 后台按钮。
- `config/agents.json` 是 agent 替换入口。
- 本地保留资料包；如传入 `--main-inbox`，再复制到主项目统一入口。
- agentCLI 必须等待 Hermes 返回结构化决策；默认不设置 agent 超时。Hermes 不可用或返回非 JSON 时，collector 停止当前采集任务并记录错误，不允许本地接管替 agent 做主导判断。
- `stage=videos/all` 时，`asr_results.jsonl` 必须写真实处理状态：`done`、`failed` 或 `skipped`，不能再写假性的 `pending_media_download` 占位。
- `stage=videos/all` 时，配乐、重复歌词、幻觉式 ASR 或无明确情报信号的视频必须标为 `information_value.status=low_value`，不能仅因下载和转写成功就进入高价值情报。
