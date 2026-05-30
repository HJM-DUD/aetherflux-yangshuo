# 升级日志 / Changelog

本文档记录「以太通量 / AetherFlux」情报决策系统的所有版本变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，并使用 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

## [Unreleased]

## [V0.2.7] - 2026-05-31

### 修复 / Fixed

- **代码审查修补版本**：根据 Security、Quality、BugHunter、Concurrency & Perf、Architecture 五维度审查结果，优先修复真实崩溃、安全脱敏、SQLite 并发、日志 OOM、资料包索引脱节和前端轮询降噪问题。
- 修复 Web 后台 package 资料包脚本漏 `import os` 导致 `NameError` 的问题。
- 修复 agentCLI ASR 依赖探测中 `_mlx_whisper_cli()` 引用未定义 `fallback` 的问题。
- 修复 SQLite 业务新连接未设置 `busy_timeout`，并发读写时容易 `database is locked` 的问题。
- 限制采集任务日志接口返回大小，避免大日志一次性读入导致后端或浏览器卡死。
- 调整 `_safe_payload` 脱敏策略，兼顾真实 token 拦截和普通业务文本不被误杀。
- 让 `/api/v1/daily-bundles` 自动同步外部 inbox 中已存在的资料包元数据，避免磁盘有包但 Web 后台看不到。
- 为后台采集子进程增加总超时与进程组终止逻辑，避免任务永久 `running`。
- 降低采集操作台无活跃任务时的前端轮询频率。

### 变更 / Changed

- 项目版本展示统一更新到 `V0.2.7 / 0.2.7`。
- `/api/v1/admin/retention` 非法数字输入从 500 改为 422。
- `/api/v1/collection/jobs/{job_id}/log` 仍返回 `text/plain`，但大日志只返回尾部内容并带截断提示。

### 验证 / Verification

- 后端：`.venv/bin/python -m unittest discover -s tests`，95 个测试通过。
- 前端：`npm test`，1 个测试文件、11 个用例通过。
- 构建：`npm run build` 通过。

## [V0.2.6] - 2026-05-30

### 变更 / Changed

- **数据存储外迁**：所有运行时数据（数据库、日志、采集产物、每日资料包）从项目内相对路径迁移到统一外部目录 `AETHERFLUX_DATA_ROOT`（默认 `/Users/gugu/Documents/Agent/AetherFlux_Data`）。
- 新增 `aetherflux/paths.py` 统一路径解析模块，所有模块通过环境变量 `AETHERFLUX_DATA_ROOT` 读取数据根目录。
- 子项目 `aetherflux_agentCLI` 和 `aetherflux_shellCLI` 各自通过本地 `_DATA_ROOT` 常量解析路径，不引入跨包依赖。
- Web 后台 `/api/v1/*` 采集命令构建器中的资料包根路径、inbox 路径和清理扫描路径已同步更新。
- `.gitignore` 移除本地 `data/` 相关忽略规则（数据不再存于仓库内）。
- 更新 `scripts/daily_review.sh` 数据库默认路径。

### 修复 / Fixed

- 修复 `live_rotation.py` 和 `opencli_collectors.py` 中缺失的 `paths` 模块导入。

### 安全 / Security

- 原始情报、评论、转写、数据库等敏感数据不再出现在 Git 仓库工作树中，降低误提交风险。

## [V0.2.5] - 2026-05-30

### 新增 / Added

- 新增双主并行采集子项目：
  - `aetherflux_shellCLI`：脚本和 OpenCLI 主导，agent 做监工、筛选和诊断。
  - `aetherflux_agentCLI`：agent 主导，OpenCLI 和脚本作为辅助工具。
- 两个子项目均可独立运行，并统一输出目录 + JSONL 每日资料包。
- 每日资料包统一包含 `manifest.json`、`raw_items.jsonl`、`screened_items.jsonl`、`asr_results.jsonl`、`agent_decisions.jsonl` 和 `errors.jsonl`。
- 新增主项目资料包 inbox 复制约定：`data/daily_bundles_inbox/{mode}/{date}/{run_id}/`。
- 新增 `config/agents.json` 命令模板方式，Hermes 暂作默认 agent，但可替换为其他本地 agent。
- 新增两个子项目专用 Codex skill，分别固化 shellCLI 监工流程和 agentCLI 自主采集流程。
- agentCLI 新增抖音视频深处理链路：优先通过浏览器详情页解析 `video.currentSrc` 下载，`yt-dlp` 作为备用；随后 `ffmpeg` 抽音频并调用 Whisper 后端转写。
- agentCLI 新增媒体信息价值判断：`asr_results.jsonl` 写入 `information_value`，区分 `useful`、`low_value`、`review_needed` 和 `needs_ocr`，避免纯配乐或低信号视频进入高价值情报。
- agentCLI 新增图文/滚动图片处理占位：下载图片引用并标记 `needs_ocr`，后续接 OCR/视觉识别。

### 修复 / Fixed（Codex + Hermes + Antigravity 三方审查）

- **P2 浏览器 session 泄漏**：`collector.py` 中 `_run_sequence` 未捕获 `TimeoutExpired`/`FileNotFoundError`，task 循环未用 `try/finally`，导致 OpenCLI 异常时浏览器 session 残留。修复：`_run_sequence` 内加异常捕获返回 error dict，task 循环加 `try/finally` 确保 `_close_browser_session` 总执行。

- **P1 配置传递链断开**：Web 后台选了平台/关键词，但 `_build_collection_command` 不读 `payload.platform`，shellCLI CLI 无 `--platforms/--queries` 参数，采集永远用子项目 `collect.json` 默认值。同时存在配置双重存储（主项目 `live_collect.json` vs 子项目 `collect.json`）和 `CollectionJobRequest` 缺少 `queries` 字段。修复：打通前端 → API → CLI → collector 的 platforms/queries/override 全链路，`PUT config` 时 `_sync_collect_json` 同步子项目配置文件。

- **P1 package 生成空资料包**：`_bundle_script_body` 传空数组创建空 bundle，`auto_pipeline` 第三步新建空包进入 inbox。修复：`_bundle_command` 改为 `_copy_latest_bundle_script`，查找最近真实 bundle，`raw_items=0` 时跳过打包。

- **UX 关键词为空无拦截**（Antigravity 发现）：前端 `startCollectionJob` 未检查关键词是否为空。修复：加关键词为空前置拦截 + fetch body 传 `queries` 字段。

### 安全 / Security

- agentCLI 高度自主但设硬边界：登录、验证码、账号设置、发布、支付、删除、上传私有文件等动作必须停止并请求 GuGU。
- 第三方抖音解析器默认禁用：`douyin.txt` 插件源码会把目标 URL 发给 `tiktokio.com` 并读取 `.tk-down-link`，只能在 GuGU 明确允许后作为外部备用下载方案。
- 视频号在 V0.2.5 只保留默认禁用占位，不进入真实采集队列，不写假成功。

### 验证 / Verification

- 新增 `aetherflux_shellCLI/tests/test_shellcli_workflow.py`，覆盖每日资料包、主项目 inbox 复制、视频号禁用占位、agent 命令模板和 CLI 钩子。
- 新增 `aetherflux_agentCLI/tests/test_agentcli_workflow.py`，覆盖每日资料包、主项目 inbox 复制、自主动作安全拦截、agent 命令模板、CLI 钩子、真实采集命令、浏览器媒体下载、ASR 和信息价值判断。
- agentCLI 子项目测试 17/17 通过。
- 修复经过 Codex + Hermes + Antigravity 三方交叉审查，一致确认通过。

## [V0.2.4] - 2026-05-29

### 新增 / Added

- 重建 V0.2.4 Web 后台：新增 React/Vite + Tailwind + shadcn 风格组件的专业情报控制台。
- 新增 FastAPI 后端与统一新版 `/api/v1/*` 接口，覆盖总览、采集配置、采集任务、候选审阅、官方信源、证据保留、每日资料包、云日志、系统诊断、Agent API 和发布状态。
- 新增后台任务记录模型：平台、阶段、状态、命令、日志路径、开始/结束时间、退出码和错误摘要。
- 新增本地采集配置存储：关键词、细分赛道、风险词、机会词、freshness、滚动轮数、等待时间、冷却时间和并发上限。
- 新增软删除回收站：支持多选移入回收站和恢复；14 天后只标记为可清理，不执行批量物理删除。
- 新增前端测试和构建链路：`npm test`、`npm run build`。
- 新增 V0.2.4 Web 后台补完：
  - 采集操作台支持从采集配置读取启用平台，平台用小红书/抖音图标色块展示。
  - 采集操作台移除旧“启动完整采集流程”按钮，改为两种并行采集模式：
    - 采集模式一（脚本主导）：对接 `aetherflux_shellCLI` 子项目，适合固定脚本、OpenCLI 和低成本日常采集。
    - 采集模式二（Agent主导）：对接 `aetherflux_agentCLI` 子项目，适合复杂页面、异常处理和高价值线索深挖。
  - 两种采集模式均在 Web 端提供“网页手动启动”“启动自动化任务采集”“停止采集”三个控制按钮。
  - 采集操作台新增手动/自动滑块选择器：手动模式下 GuGU 可手动按步骤执行；自动模式下后台按采集、清理、打包三步结构执行。
  - 采集流程拆为三个明确步骤：第一步采集任务、第二步清理数据、第三步生成当日资料包。
  - 第二步清理数据只做扫描、整理和进度记录，不执行物理删除，继续遵守禁止批量删除规则。
  - 第三步打包会调用对应子项目 bundle writer，生成当日资料包并复制到主项目 `data/daily_bundles_inbox`，作为第二部分“超级智脑”的入口。
  - 每个采集模式下方展示当前任务包名称、已采集数量、占用磁盘空间和已执行时长。
  - 任务队列支持停止按钮、分页展示、每 5 秒刷新、中文状态、阶段色块和平台图标。
  - 任务队列新增模式字段，可区分脚本主导、Agent 主导和旧采集流程。
  - 新增手动主题切换：系统、浅色、深色，并保留跟随系统模式。
  - 标题池新增最新文件采集日期、中文空状态和本地模糊检索，可按标题、平台、关键词、摘要、ID、链接查找采集对象。
  - 候选审阅改为四个平级分区：候选待确认、已确认、已驳回、软删除；确认/驳回/软删除后议题进入对应分区。
  - 候选审阅每个议题按“原文”和“翻译”两块展示，原文为爬取内容，翻译为反向语言展示。
  - 候选审阅合并生成式搜索风险，不再单独保留左侧“生成式搜索风险”页面；每个议题底部展示风险概率、中文等级和智脑分析原因。
  - 候选审阅新增标签热度系统：读取智脑返回的 `tags` / `advisor_tags` / `topic_tags`，按当日候选重复度计算颜色梯队，频率越高越红，越低越浅绿。
  - 分数改为 0-100 五档色谱大色块展示；状态、平台、分数均居中排版。
- 新增 Web 后台整体导航与设置体系：
  - 左侧导航改为固定侧边栏，横向窗口变窄时不再移动到页面顶部。
  - 左侧导航新增折叠/展开按钮；展开时显示图标和文字，折叠时只保留图标。
  - 左侧导航按五大板块分组：采集控制、情报处理、核验信源、输出接口、数据治理。
  - 系统诊断、版本发布、全局设置移动到左侧栏底部固定功能区，不随上方菜单滚动消失。
  - 新增“全局设置”页面，配齿轮图标，包含外观和关于两个大板块。
  - 外观板块新增主题、语言、主题色、分析面板主颜色设置；浅色/深色/跟随系统切换从顶部主栏迁移到全局设置。
  - 语言设置支持中文/English 切换，先覆盖后台固定壳层、左侧菜单、全局设置页和主题按钮；每日选题内容不做自动翻译。
  - 主题色和分析面板主颜色会写入本地 `localStorage`，并同步更新 CSS 主题变量。
- 新增采集操作台整体采集进度条：
  - 在采集流程控制区域下方展示整体采集进度。
  - 右上角显示带颜色变化的百分比。
  - 进度条使用渐变和动效展示执行状态。
  - 进度条下方显示当前任务执行步骤，如等待调度、采集任务、清理数据、打包资料包、停止收束、失败或完成。
  - 优先读取后端任务字段 `progress_percent` / `progress` 和 `current_step` / `step_label`；字段缺失时按 `stage` 与 `status` 保守估算进度。
- 新增交叉验证页面结构化展示：
  - 交叉验证页不再直接展示 `JSON.stringify(cross_check)` 原始对象。
  - 每个议题改为中文卡片展示：验证状态、是否需要补证、支持来源、冲突来源、智脑核验判断。
  - `unverified`、`partially_verified`、`verified`、`conflict` 等内部状态改为中文色块。
  - 常见英文智脑核验判断增加中文兜底解释，避免页面出现大段难读英文。

### 变更 / Changed

- `python3 -m aetherflux.cli serve` 默认启动 V0.2.4 FastAPI 后台；旧 V0.1 静态后台改为 `legacy-serve` 备用入口。
- 项目版本号更新为 `0.2.4`。
- 正式后台 API 主路径迁移到 `/api/v1/*`，旧 `/api/*` 只作为旧壳兼容参考，不再是主接口。
- SQLite 连接改为自动关闭的 context manager，减少长期运行后台时的资源泄露风险。
- Web 后台固定主标题为“以太情报后台”，除 GuGU 明确要求外不再改名。
- Web 后台主栏改为页面下滑时固定在顶部，避免滚动后主控制栏消失。
- 左侧栏折叠/展开按钮移动到顶部固定主栏，并放在“以太情报后台”标题前方，避免折叠状态下挤压 AF 图标。
- 采集配置以 `config/live_collect.json` 为真实采集主源，后台保存配置时同步写入文件和 SQLite 缓存。
- 后台采集任务请求扩展 `mode`、`action`、`run_mode` 字段，支持从同一 Web 操作台调度 `shellCLI`、`agentCLI`、清理扫描、打包资料包和自动三步流程。
- 候选审阅中的“已驳回”状态色块改为与“驳回”按钮一致的红底白字风格。
- DeepSeek Advisor 提示词增加 `tags` 输出要求，后端合并智脑返回标签并为无模型回退结果生成基础标签。
- 候选审阅中“原文”区域改为深色内容框，与“翻译”和“标签热度”形成清晰层级。
- 候选审阅中缺少 `geo_risk` 的议题不再隐藏风险模块，统一显示“生成式搜索风险 0% / 极小风险”。
- 交叉验证来源展示改为直接显示来源链接，不再把 `redacted` 前端翻译成“来源已脱敏”。
- Web 后台页面状态从中文标题切换为稳定页面 ID，避免中英文切换后页面路由状态混乱。

### 修复 / Fixed

- 修复缺少 Playwright 时 live collector 错误提示不包含 Chrome remote debugging 和 `9222` 操作指引的问题。
- 修复 `opencli-rotate --stage titles|screen|videos|all` 阶段参数没有正确传给 OpenCLI 轮转流程的问题。
- 修复旧 `live-rotate` 路径引用不存在 stage 参数的崩溃风险。
- 修复任务队列状态直接显示英文 `running` / `succeeded` 等内部状态的问题。
- 修复标题池空状态显示 `no_matching_files` 的问题。
- 修复候选审阅软删除后页面状态不明确的问题：软删除后留在候选审阅页但进入软删除分区，并提供撤销删除。
- 修复浅色/深色主题下部分警告色块背景不跟随主题的问题。
- 修复后端 `_safe_payload()` 误伤小红书来源 URL 的问题：旧逻辑只要字符串包含 `token` 就把整条 URL 变成 `redacted`；现在只移除 URL 中敏感查询参数，例如 `xsec_token`，保留来源链接主体和非敏感参数。
- 修复交叉验证页显示 `supporting_sources`、`conflicting_sources`、`needs_more_sources` 等原始字段的问题。
- 修复 Web 顶部主题切换和全局设置重复的问题：主题切换统一放入全局设置。

### 安全 / Security

- V0.2.4 后台默认本机免登录并监听 `127.0.0.1`。
- API 输出会过滤 `api_key`、cookie、token、password、secret 等敏感字段或敏感文本。
- 回收站只做软删除，不批量物理删除文件或目录。
- Web 后台不暴露 service key、cookie、token；云日志边界只展示轻量日志同步记录。
- Web 端不提供批量物理删除入口；删除动作均进入软删除回收站，可恢复。
- 采集操作台的“清理数据”步骤只做文件扫描和日志记录，不提供批量物理删除入口。
- 来源 URL 允许在本地后台展示，但后端会剔除敏感查询参数，避免把平台 token 类参数暴露到前端。

### 验证 / Verification

- 前端：新增/更新 `tests/frontend/App.test.tsx`，覆盖固定标题、采集操作台、整体采集进度条、任务分页刷新、固定可折叠侧边栏、五大导航分组、底部固定功能区、全局设置、语言切换、主题切换、标题池检索、候选审阅分区、翻译展示、GEO 风险合并、标签热度、交叉验证结构化展示和状态色块。
- 前端：采集操作台测试新增覆盖两种采集模式、手动/自动切换、网页手动启动、自动化任务、停止采集、清理数据、打包资料包和旧“启动完整采集流程”按钮移除。
- 后端：新增/更新 V0.2.4 API、Advisor、标题池文件元数据相关测试。
- 后端：采集任务 API 测试新增覆盖 `shellCLI` / `agentCLI` 子项目钩子、`mode` / `action` / `run_mode` 字段、自动三步流程命令、清理扫描不物理删除和本地日志大小记录。
- 后端：新增/更新 `tests/test_v024_admin_api.py`，覆盖候选来源 URL 保留主体、剔除敏感查询参数且不再误输出 `redacted`。
- 构建与基础校验：已多次运行 `npm test -- --run tests/frontend/App.test.tsx`、`npm run build`、`.venv/bin/python -m unittest tests.test_advisor`、`.venv/bin/python -m unittest tests.test_v024_admin_api`、`.venv/bin/python -m compileall aetherflux`。

## [V0.2.3] - 2026-05-29

### 新增 / Added

- 新增 ASR 优先的视频情报深处理框架：本地提取音频、选择本地 ASR 后端、输出 `transcript_full`、`transcript_segments`、`video_summary` 和 `decision_hints`。
- 新增混合关键词规划：手动关键词、地点/景点、细分赛道、风险词、机会词和 Hermes 探索词共同生成标题池搜索词。
- 新增最近 24 小时 freshness 解析与过滤字段：`published_at_raw`、`freshness_status`、`freshness_window_hours`、`ui_filter_applied`。
- 新增 `opencli-rotate --stage titles|screen|videos|all`，支持标题池、初筛、视频 ASR 和完整流程分阶段运行。
- 新增 Hermes 标题池初筛入口；Hermes 不可用或关闭时回退本地机会/风险规则筛选。

### 变更 / Changed

- 小红书/抖音 OpenCLI 采集从固定少量首屏结果升级为浏览器搜索、时间筛选尝试、多轮滚动和标题池抽取。
- 默认配置调整为 V0.2.3 压力档：每个平台约 200 条标题池，约 40 条进入深处理，抽帧默认关闭，ASR 为视频处理第一优先级。
- `scripts/hermes_collect_opencli.sh` 默认执行完整链路，并显式开启 Hermes 初筛。
- 项目版本号更新为 `0.2.3`。

### 安全 / Security

- 原始视频、音频、转写全文和深处理结果继续只保存在本地或未来 NAS，不上传 Supabase Cloud。
- 缺少 ASR 依赖或视频下载路径时明确标记失败原因，不写假成功数据。

### 发布 / Release

- 从 V0.2.3 起，正式版本必须同步 GitHub、推送 `main`、打 annotated tag，并尽量创建 GitHub Release。

## [V0.2.2] - 2026-05-29

### 新增 / Added

- 新增 OpenCLI Browser Bridge 采集层，默认复用当前常用 Chrome 登录态，不再默认启动专用 CDP Chrome。
- 新增 `python3 -m aetherflux.cli opencli-rotate`，按小红书/抖音交替轮转执行 OpenCLI 采集。
- 新增 `scripts/hermes_collect_opencli.sh`，作为 Hermes 默认真实采集入口，并在采集前执行 `opencli doctor`。
- 新增 OpenCLI 输出标准化，将小红书搜索、抖音话题/地点等 rows 转为 AetherFlux raw item schema。

### 变更 / Changed

- `scripts/hermes_collect_live.sh` 默认转向 OpenCLI 后端；旧 CDP 后端仅在 `AETHERFLUX_COLLECT_BACKEND=cdp` 时启用。
- OpenCLI 未打通 Browser Bridge 时直接停止采集，避免产生假成功数据。

### 修复 / Fixed

- 修正抖音 OpenCLI 采集入口：不再调用会跳转到创作者中心的 `douyin hashtag search`，改为通过 Browser Bridge 打开 `https://www.douyin.com/jingxuan`，再输入当前采集关键词搜索并抽取搜索结果页可见视频信号。
- 避免旧 CDP 专用 Chrome 登录态与平台风控冲突导致的安全限制页、协议页和无效正文污染候选池。

## [V0.2.1] - 2026-05-28

### 新增 / Added

- 新增 `config/live_collect.json`，把小红书/抖音平台、关键词、每日目标、单篇等待时间和单任务采集上限放到本地配置中。
- 新增自适应轮转慢采集：按“小红书 1 篇 → 抖音 1 篇 → 随机等待”的方式交替采集，默认每篇后等待 90-240 秒。
- 新增 `python3 -m aetherflux.cli live-rotate` 命令，支持 `--dry-run` 预览平台轮转计划。
- 新增采集质量闸门，标记协议页、安全限制页、备案页、空正文、base64 封面等低质量结果。

### 变更 / Changed

- `scripts/hermes_collect_live.sh` 改为调用轮转慢采集命令，不再按平台批量快速采集。
- Hermes 的默认角色调整为采集监督：读取采集 summary 和平台健康状态，判断继续、暂停平台或上报人工。
- 当前版本只写入本地更新日志，不同步 GitHub，不打 tag。

### 修复 / Fixed

- 修复旧采集脚本连续快速打开详情页容易触发平台限制、并把安全限制页/协议页当作有效情报的问题。
- 修复旧详情页抽取过粗导致页面页脚、备案、导航文本污染情报正文的问题，先通过质量闸门阻断进入正式候选。

### 新增 / Added

- 新增小红书/抖音登录态 Chrome CDP 采集 adapter 初版：支持搜索页可见卡片、前 N 条详情页轻量抽取、评论样本、视频关键帧计划字段。
- 新增 `python3 -m aetherflux.cli live {xiaohongshu,douyin}` 命令；视频号因无网页端内容入口暂时跳过。
- 新增 `scripts/open_chrome_cdp.sh`，用于打开 AetherFlux 专用 Chrome 采集 profile 和 `9222` 调试端口。

## [V0.2.0] - 2026-05-28

### 新增 / Added

- **本地视频情报收集站**：V0.2.0 聚焦小红书、抖音、视频号的视频、评论、同题讨论和官方信源辅助监控。
- **端口调整**：`8765` 保留给 Triagent，AetherFlux Web 默认改为 `8788`，本地 worker/API 预留 `8789`。
- **本地 SQLite 扩展**：新增 mission、官方信源、证据保留、每日资料包、Supabase 轻量日志同步记录等本地表。
- **硬去重与同题聚类拆分**：新增 `hard_dedupe_key`、`topic_cluster_key`、`copy_similarity`，避免把不同用户讨论同一件事误删。
- **视频采集基础模型**：新增关键帧时间规划、评论抽样、每日资料包 manifest 等本地采集基础能力。
- **官方信源复核规则**：mission 的地点、行业、细分变化后，相关官方信源自动标记为 `needs_review`。
- **每日资料包索引**：新增本地 `daily_bundles` 记录，作为第一部分交给第二部分“超级智脑”的标准交付物。
- **云日志清理记录**：新增 `cloud_log_syncs`，Supabase Cloud 只允许保存轻量日志索引和清理状态。

### 变更 / Changed

- **Supabase 边界收窄**：不保存原始情报、截图、HTML、音视频、评论全文或转写全文；只用于登录和每日轻量日志索引。
- **存储路线明确本地优先**：情报数据继续使用本地 SQLite 和本地文件系统，后续可通过配置切到 NAS。
- **Hermes 定位调整**：Hermes 作为监工和异常分析 agent，不参与机械采集循环，避免 token 消耗失控。
- **README / README_EN / 架构文档更新**：补充 V0.2.0 本地视频采集站、Mac/PC 部署、资料包和安全边界。

### 安全 / Security

- 原始采集证据默认保留 48 小时，可在后台调整。
- 清理任务必须逐个删除明确文件路径，不允许批量删除目录。
- API key、cookie、浏览器 profile、Supabase service key 不写入仓库。

## [V0.1.0] - 2026-05-20

### 新增 / Added

- **项目骨架**：Python 项目结构，`pyproject.toml`，`.gitignore`
- **采集层 / Collector Layer**：`aetherflux/pipeline.py` 配置驱动流水线框架，为多平台采集预留统一 raw item schema
- **清洗层 / Normalization Layer**：基础清洗、语言识别、来源链接保留
- **评分层 / Scoring Layer**：`aetherflux/scoring.py` 低 token 规则评分、去重、基础分类、平台权重、新鲜度、互动热度、阳朔相关度、风险词、机会词
- **交叉验证中心 / Cross Verification Center**：claim 拆解、来源独立性判断、跨平台支持/冲突检查、真假信息风险提示
- **GEO 风险判断 / GEO Risk Judge**：`aetherflux/review.py` 中 GEO 疑似度输出（`geo_risk.probability`、`geo_risk.level`、`geo_risk.reasons`），只表达风险概率不做法事实定罪
- **DeepSeek V4 智库层 / DeepSeek V4 Advisor Layer**：`aetherflux/deepseek.py` 可插拔 JSON client，`aetherflux/advisor.py` 回退/合并逻辑，通过环境变量配置（`DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL_ADVISOR`），无 key 时回退规则审议
- **Codex 审议脑 / Codex Review Brain**：`aetherflux/review.py` 多角色审议草稿生成，不自动发布
- **人工闸门 / Human Gate**：`aetherflux/storage.py` SQLite 存储 + 人工决策（pending → approved/rejected），`aetherflux/api.py` payload 组装
- **网页决策台 / Web Dashboard**：`aetherflux/server.py` Python 标准库 HTTP server，`aetherflux/web/` 前端（HTML/CSS/JS）
- **命令行入口 / CLI**：`aetherflux/cli.py` 支持 `ingest`、`review`、`serve` 子命令
- **API 端点 / API Endpoints**：
  - `GET /api/candidates`、`/api/selected`、`/api/daily`
  - `GET /api/opportunities`、`/api/foreign-signals`、`/api/risks`
  - `GET /api/evidence/:id`、`/api/content-briefs`
  - `POST /api/decisions`、`/api/run-ingest`、`/api/run-review`
- **样本数据 / Seed Data**：`data/seed_items.json`
- **默认方向配置**：`config/directions.json`
- **每日审议脚本**：`scripts/daily_review.sh`，支持通用 Webhook
- **架构文档**：`docs/architecture.md`
- **测试 / Tests**：`tests/` 下覆盖评分、审议、存储、API 和流水线的基础测试
- **中文 README**：`README.md`
- **项目记忆文件**：`AGENTS.md` 记录架构决策、安全规则和运行指南

### 产品决策 / Product Decisions

- 第一版优先小红书，架构已为多平台扩展做准备
- 国内外平台兼顾，阳朔作为全球旅游目的地外网信号不能缺席
- 呈现偏「旅游情报决策台」而非泛资讯流
- 信息交叉验证是核心能力，不是附属功能
- GEO 只表达疑似度，不表达事实定罪
- DeepSeek V4 参与审议但不参与低价值机械清洗
- 自动审议但不自动发布，人工确认后才进入网页和正式 API

---

[V0.2.0]: https://github.com/HJM-DUD/aetherflux-yangshuo/releases/tag/v0.2.0
[V0.1.0]: https://github.com/HJM-DUD/aetherflux-yangshuo/releases/tag/v0.1.0
