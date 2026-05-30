# 🐛 AetherFlux 调试与审查日志

> **规则**：此文件由 GuGU 手动要求更新。记录每次代码审查、重大修改、发现的问题和后续计划。
> **最后更新**：2026-05-30 | V0.2.6

---

## 2026-05-30 — Antigravity 默认模型固定

**当前模型**：Gemini 3.5 Flash (Medium)（`~/.gemini/antigravity-cli/settings.json`）
**操作**：确认已使用 3.5 Flash，更新 triagent SKILL.md 模型指南，移除 3.1 Pro 推荐，固定 3.5 Flash 为默认。


---

## 2026-05-30 — V0.2.6 数据路径外迁 + 深度代码审查

### 执行人
Codex (主脑) + Hermes (DeepSeek v4-pro) + Antigravity (Gemini 3.1 Pro)

---

### 一、数据存储外迁

**目标**：所有运行时数据从项目内相对路径迁移到 `/Users/gugu/Documents/Agent/AetherFlux_Data`

**做了什么**：
- 新增 `aetherflux/paths.py` 统一路径解析模块，读取 `AETHERFLUX_DATA_ROOT` 环境变量
- 修改 14 个文件：cli.py, storage.py, server.py, deepseek.py, admin_api.py, opencli_collectors.py, live_rotation.py, 子项目 cli.py×2, collector.py×2, collect.json×2, daily_review.sh, .gitignore
- 新增数据目录：`AetherFlux_Data/{artifacts,logs,daily_bundles_inbox,agentCLI,shellCLI}/`
- 发现并修复 bug：agentCLI 采集命令误用 `shellcli_bundle_root()` → 已修正为 `agentcli_bundle_root()`

**设计决定**：子项目各自通过本地 `_DATA_ROOT` 常量解析路径，不引入跨包依赖，保持独立运行能力。

---

### 二、五维度深度代码审查

| 维度 | 审查方 | 发现问题 | 评分 |
|------|--------|----------|------|
| 安全性 | Hermes | 6 问题 + 6 通过 | 7.5 |
| 漏洞猎手 | Hermes | 6 问题 + 3 通过 | 7.0 |
| 并发性能 | Hermes | 3 问题 + 3 通过 | 6.5 |
| 代码质量 | Antigravity | 10 问题 | 6.5 |
| 架构评估 | Antigravity | 7 问题 | 7.0 |

**审查报告存档**：
- Hermes 报告：Triagent 任务 `1a272be8`（安全+BugHunter+并发）
- Antigravity 报告：Triagent 任务 `3e8b4bac` + Artifact `~/.gemini/antigravity-cli/brain/17255ef5.../code_review_and_architecture_evaluation.md`

---

### 三、GuGU 架构决策

| # | 决策 | 结论 |
|---|------|------|
| 1 | 下线旧 server.py？ | V0.2.6 标记弃用，V0.3.0 移除 |
| 2 | 子项目提取公共包？ | ❌ 不重构。独立运行是设计原则 |
| 3 | 中央配置引擎？ | 延后到 V0.3.0 |

---

### 四、本次已修复

| 优先级 | 问题 | 文件 | 描述 |
|--------|------|------|------|
| P0 | E4 数据库回滚缺失 | storage.py | `_connect` 增加 `except: rollback()` |
| P0 | E22 SQLite 写竞争 | storage.py | `initialize()` 加 WAL + busy_timeout |
| P0 | E3 配置遗漏 agentCLI | admin_api.py | `_sync_collect_json` 增加 agentCLI 同步 |
| P1 | E15 重试无退避 | deepseek.py | 指数退避 1s/2s/4s/8s |
| P1 | E2 敏感值泄露 | admin_api.py | 增加 Bearer/sk-/dsk- 模式扫描 |
| P2 | E16 静默吞错 | admin_api.py | `_load_collection_config` 打印 stderr |
| P2 | E17 异常分类 | opencli_collectors.py | `_screen_with_hermes` 区分超时/未找到 |
| P2 | E6 硬编码路径 | admin_api.py | 内嵌脚本改用 `os.environ.get()` |
| P2 | E6 mlx_whisper | media_asr.py | 硬编码路径→`site.getusersitepackages()` |

**修改文件**：storage.py, admin_api.py, deepseek.py, opencli_collectors.py, media_asr.py（5个）

---

### 五、已知未修复（延后）

| 版本 | 问题 | 说明 |
|------|------|------|
| V0.2.7 | `_run_job_sync` process.wait 无超时 | 需改动任务调度逻辑 |
| V0.2.7 | `_safe_payload` 值级深度扫描 | 需确认不误杀正常数据 |
| V0.2.7 | `deepseek_status` base_url 脱敏 | 低风险 |
| V0.2.7 | shellCLI ASR 占位符契约 | 需确认设计意图 |
| V0.3.0 | 下线 server.py | 需迁移残留路由 |
| V0.3.0 | 中央配置引擎 Pydantic-settings | 大工程 |
| V0.3.0 | TypedDict 强类型约束 | 需定义完整 DTO |
| V0.3.0 | 采集器注册器模式 | 架构级改动 |
| V0.3.0 | 子进程超时 + 并发测试 | 集成测试 |

---

### 六、后续计划

1. **V0.2.6 收尾**：提交当前改动 → 更新 CHANGELOG → PR → 合并 main
2. **V0.2.7**：修复 `_run_job_sync` 超时 + shellCLI ASR 契约 + 敏感值深度扫描
3. **V0.3.0**：下线 server.py + 中央配置引擎 + 架构升级

---

### 七、测试状态

```
编译：全部通过 ✅
单元测试：89/89 通过 ✅
```

