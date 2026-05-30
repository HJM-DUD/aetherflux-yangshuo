---
name: aetherflux-agentcli-crawler
description: Use when working inside AetherFlux agentCLI crawler mode: agent-led OpenCLI/browser workflows, autonomous Observe-Plan-Act collection, action safety gates, Hermes or replaceable agent command templates, daily bundle generation, or V0.2.5 agentCLI workflow changes.
---

# AetherFlux AgentCLI Crawler

Use this skill when editing or running `/aetherflux_agentCLI`.

## Role

Treat this project as the autonomous collection mode:

- agent owns the control flow
- OpenCLI and scripts are tools
- Hermes is only the default operator and must be replaceable through `config/agents.json`

## Workflow

1. Run tests before and after changes:

   ```bash
   python3 -m unittest discover -s tests -p 'test_*.py'
   ```

2. Use dry-run before any real collection:

   ```bash
   python3 -m aetherflux_agentcli.cli run --dry-run
   ```

3. Real collection goes through `aetherflux_agentcli.collector`:

   ```bash
   python3 -m aetherflux_agentcli.cli run --platforms xiaohongshu douyin --queries "阳朔 旅游"
   ```

   The collector must run `opencli doctor`, apply newest/today filters, extract public visible text, locally reject stale rows, and close the OpenCLI browser session after each platform task.

4. Enforce action safety before executing browser actions. Stop for login, password, captcha, account settings, publish, payment, delete, or upload. agentCLI must wait for Hermes by default; if Hermes is unavailable or returns invalid JSON, stop the current task and record an error. Do not let local code take over the agent decision.

5. Write daily bundles as directory + JSONL:

   - `manifest.json`
   - `raw_items.jsonl`
   - `screened_items.jsonl`
   - `asr_results.jsonl`
   - `agent_decisions.jsonl`
   - `errors.jsonl`

5. Keep one local copy and optionally copy to the main project inbox with `--main-inbox`.

## Safety

Never batch-delete files or directories. Never write credentials, cookies, or tokens into code, docs, tests, logs, or bundles. Never bypass captcha or login gates automatically.
