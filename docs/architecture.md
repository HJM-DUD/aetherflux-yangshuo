# 阳朔旅游情报决策系统架构

## 两段式架构

PC 情报工厂负责低 token 的重活：采集、清洗、去重、基础评分、候选池入库。Mac Codex 审议主脑负责每日审议：读取候选池、组织角色评估、生成待审稿、通过 Webhook 提醒。

## 数据流

1. `config/directions.json` 定义平台权重、地点、主题、关键词。
2. 采集器产出原始 JSON 条目。
3. `aetherflux.scoring` 完成语言识别、主题命中、基础权重、证据链。
4. `aetherflux.storage` 保存候选池、人工决策和审议草稿。
5. `aetherflux.review` 生成待审稿，默认不自动发布。
6. `aetherflux.server` 提供网页后台和 agent API。

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
- 增加截图证据和网页快照。
- 增加信源长期权重和反馈闭环。
- 把通用 Webhook 适配为飞书/企业微信/n8n 消息卡片。
