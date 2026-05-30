---
name: aetherflux-shellcli-collector
description: Use when working inside AetherFlux shellCLI collector mode: OpenCLI/script-led collection, Hermes or another agent as supervisor, daily bundle generation, scheduler/backend hooks, platform support policy, or V0.2.5 shellCLI workflow changes.
---

# AetherFlux ShellCLI Collector

Use this skill when editing or running `/aetherflux_shellCLI`.

## Role

Treat this project as the industrial collection mode:

- scripts and OpenCLI own the control flow
- agent output is advisory and structured
- Hermes is only the default supervisor and must be replaceable through `config/agents.json`

## Workflow

1. Run tests before and after changes:

   ```bash
   python3 -m unittest discover -s tests -p 'test_*.py'
   ```

2. Use dry-run before any real collection:

   ```bash
   python3 -m aetherflux_shellcli.cli run --dry-run
   ```

3. Before real collection, verify OpenCLI:

   ```bash
   opencli doctor
   ```

4. Keep video channel as disabled placeholder in V0.2.5. Do not add it to real collection unless GuGU explicitly starts that work.

5. Write daily bundles as directory + JSONL:

   - `manifest.json`
   - `raw_items.jsonl`
   - `screened_items.jsonl`
   - `asr_results.jsonl`
   - `agent_decisions.jsonl`
   - `errors.jsonl`

6. Keep one local copy and optionally copy to the main project inbox with `--main-inbox`.

## Safety

Never batch-delete files or directories. Never write credentials, cookies, or tokens into code, docs, tests, logs, or bundles.
