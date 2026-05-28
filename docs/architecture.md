# 阳朔旅游情报决策系统架构

## 项目内模块架构

阳朔旅游情报中心是“以太通量 / AetherFlux_yitaitongliang”主项目内的子项目。取消 PC/Hermes 独立情报中心路线，由 Codex 作为每日情报控制 agent，DeepSeek V4 作为可插拔智库层。

## 数据流

1. `config/directions.json` 定义平台权重、地点、主题、关键词。
2. 采集器产出原始 JSON 条目。
3. `aetherflux.scoring` 完成语言识别、主题命中、基础权重、证据链。
4. `aetherflux.advisor` 在审阅前补充中英展示、交叉验证建议、GEO 疑似度和智库意见。
5. `aetherflux.storage` 保存候选池、人工决策和审议草稿。
6. `aetherflux.review` 生成待审稿，默认不自动发布。
7. `aetherflux.server` 提供网页后台和 agent API。

## DeepSeek 智库层

DeepSeek V4 通过 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL_ADVISOR` 启用。默认模型为 `deepseek-v4-pro`。无 key 或 API 失败时，系统必须回退本地规则审议。

智库层只参与审议、交叉验证、GEO 疑似度和最终呈现润色，不参与普通清洗、去重、关键词匹配等低价值任务。

## 中英对照

中英对照只在人工审阅前和最终网页/API 呈现前生成。中间采集、清洗、基础评分阶段保留原文，避免 token 消耗失控。

## 人工闸门

候选情报默认是 `pending`。只有通过网页或 API 写入 `approved` 的条目，才会进入：

- `/api/selected`
- `/api/daily`
- `/api/opportunities`
- `/api/foreign-signals`
- `/api/risks`
- `/api/content-briefs`

`rejected` 条目不会进入新的审议草稿。

## 后续扩展点

- 为每个平台增加独立 collector，统一输出 seed item shape。
- 接入 DeepSeek，把复杂跨语言判断、冲突裁决和日报主编点评放到模型层。
- 增强交叉验证中心，结构化保存 claim、支持证据、冲突证据和需要补充的来源。
- 增强 GEO 风险判断，持续校准 `probability`、`level` 和 `reasons`。
- 增加截图证据和网页快照。
- 增加信源长期权重和反馈闭环。
- 把通用 Webhook 适配为飞书/企业微信/n8n 消息卡片。
