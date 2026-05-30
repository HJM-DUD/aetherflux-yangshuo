# AetherFlux AgentCLI Collector

版本：V0.2.7

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

按指定平台和关键词真实采集：

```bash
python3 -m aetherflux_agentcli.cli run \
  --platforms xiaohongshu douyin \
  --queries "阳朔 旅游" "阳朔 竹筏"
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

## 真实采集流程

`aetherflux_agentcli.collector` 已接通真实 OpenCLI 采集：

1. 运行 `opencli doctor`，失败则停止。
2. 读取 `config/collect.json` 和 `config/agents.json`。
3. 对小红书打开搜索页，点击 `筛选`、`最新`、`一天内` 后提取公开结果。
4. 对抖音优先使用 `sort_type=2&publish_time=1` 的最新/一天内搜索 URL，必要时再回落到普通搜索页。
5. 本地二次过滤缺失发布时间、昨天、天前、旧日期和导航噪音。
6. 每个平台任务结束后关闭独立 OpenCLI browser session，避免后台持续开空白页。

Hermes 默认负责给每次任务做行动决策；agentCLI 默认不设置 Hermes 超时，会一直等待 Hermes 返回结构化 JSON。Hermes 不可用或没有返回合法 JSON 时，当前任务停止并写入错误，不会用本地接管替 Hermes 做主导判断。

## 视频下载与 ASR

`stage=videos` 或默认 `stage=all` 时，agentCLI 会对初筛通过的视频执行：

1. 从抖音搜索 DOM 的 `waterfall_item_*` 提取内容 ID。
2. 区分 `video` 和 `image`；图文内容不做 ASR，写入 `not_video_content`。
3. 对视频拼出 `https://www.douyin.com/video/{id}`。
4. 优先用 OpenCLI 打开详情页，从浏览器里的 `video.currentSrc` 解析真实媒体地址，再用 `curl` 下载。
5. 浏览器媒体地址不可用时，再用 `yt-dlp` 作为备用下载路径。
6. 用 `ffmpeg` 提取 `audio.wav`。
7. 调用 `mlx_whisper`、`mlx_whisper` 命令行、`faster_whisper` 或 `whisper` 中可用的后端转写。
8. 在 `asr_results.jsonl` 写入 `download_status`、`asr_status`、`summary`、`transcript_ref`、`segments_ref` 和 `information_value`。

`information_value` 用来避免把纯配乐/风景/BGM 视频误判成可用情报：

- `useful`：ASR 或标题正文里有排队、避坑、路线、预约、涨价、停运等可行动信息。
- `low_value`：只有配乐、重复歌词、幻觉式转写或没有明确情报信号。
- `review_needed`：有地点实体但价值不确定，需要人工看一眼。
- `needs_ocr`：图文/滚动图片，图片已下载但需要后续 OCR 或视觉识别。

当前已按 GuGU 授权在 `config/collect.json` 把 `yt_dlp_cookies_from_browser` 设为 `chrome`。如果抖音仍返回 `Fresh cookies are needed`，说明 `yt-dlp` 没有拿到可用的新鲜登录态；这时会优先依赖浏览器媒体地址解析路径。

已学习 `douyin.txt` 里的下载插件源码：它会把抖音 URL 发给 `tiktokio.com` 解析，再从返回 HTML 里取 `.tk-down-link`。这只能作为 GuGU 明确允许后的外部解析备用方案，默认不启用，因为会把目标链接发送给第三方。

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
