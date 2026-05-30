# Changelog

## [V0.2.5] - 2026-05-30

### Added

- 新建 agentCLI 独立采集子项目骨架。
- 新增目录 + JSONL 每日资料包生成器。
- 新增主项目资料包 inbox 复制入口。
- 新增 Hermes 命令模板配置 `config/agents.json`。
- 新增自主动作安全拦截：登录、验证码、账号设置、发布、支付、删除、上传等必须请求 GuGU。
- 新增 `run`、`scheduler-hook`、`backend-hook` 三个 CLI 入口。
- 新增项目内 Codex skill：`aetherflux-agentcli-crawler`。
- 新增 `collector.py` 真实采集：OpenCLI doctor、agent 决策记录、小红书/抖音最新发布与一天内筛选、公开结果提取、session 自动关闭。
- 新增 `config/collect.json`，打通 platforms/queries/stage/main-inbox 等运行配置。
- 修正 agentCLI 主导权：默认无限等待 Hermes 决策；Hermes 不可用或返回非 JSON 时停止当前任务，不再由本地逻辑接管继续采集。
- 新增 `media_asr.py`：视频 URL 提取、`yt-dlp` 下载、`ffmpeg` 音频提取、Whisper ASR、转写引用写入 `asr_results.jsonl`。
- 修正抖音搜索结果无 `<a href>` 的问题：从 `waterfall_item_*` 提取内容 ID，视频拼 `/video/{id}`，图文跳过 ASR。
- 新增浏览器媒体地址下载路径：优先打开抖音详情页读取 `video.currentSrc`，用 `curl` 下载；`yt-dlp` 保留为备用路径。
- 新增图文图片下载占位：滚动图片/图文内容下载图片引用，并标记为待 OCR/视觉识别。
- 新增 `information_value` 判断：ASR 后把视频标为 `useful`、`low_value`、`review_needed` 或 `needs_ocr`，避免纯配乐、重复歌词或幻觉式转写进入高价值情报。
- 明确第三方解析器边界：`douyin.txt` 插件使用 `tiktokio.com` 解析 `.tk-down-link`，默认不启用，只能在 GuGU 明确允许后作为外部备用方案。
