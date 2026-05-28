# AetherFlux Yangshuo

"AetherFlux" sub-project: Yangshuo Tourism Intelligence Decision System. For internal content planning, opportunity assessment, risk identification, cross-verification, GEO likelihood evaluation, and as a data backbone for downstream operations agents.

Version one is a Python minimal closed loop with zero external dependencies: sample ingestion, scripted scoring & deduplication, Codex review drafts, pluggable DeepSeek V4 advisor layer, human confirmation gate, web dashboard, and internal JSON API.

## Quick Start

```bash
python3 -m unittest discover -s tests
python3 -m aetherflux.cli ingest
python3 -m aetherflux.cli review
python3 -m aetherflux.cli serve --host 127.0.0.1 --port 8765
```

Open:

```text
http://127.0.0.1:8765
```

## Daily Review

Xiaohongshu (RED) initial backfill of the last 7 days, outputting raw item JSON for subsequent `ingest`:

```bash
python3 -m aetherflux.cli xhs backfill --days 7 --source data/xhs_source_items.json --output artifacts/xhs_raw_items.json
python3 -m aetherflux.cli ingest --seed artifacts/xhs_raw_items.json
```

After that, daily collection of only new content posted after the last successful watermark:

```bash
python3 -m aetherflux.cli xhs daily --source data/xhs_source_items.json --output artifacts/xhs_raw_items.json
python3 -m aetherflux.cli ingest --seed artifacts/xhs_raw_items.json
```

Run daily review manually:

```bash
scripts/daily_review.sh
```

With a generic Webhook:

```bash
AETHERFLUX_WEBHOOK_URL="https://your-webhook.example.com" scripts/daily_review.sh
```

The Webhook payload is generic JSON, suitable for Feishu, WeCom, n8n, Dify, or custom bots.

Enable the DeepSeek advisor layer via local environment variables (never commit keys to the repo):

```bash
export DEEPSEEK_API_KEY="your-local-key"
export DEEPSEEK_BASE_URL="https://api.deepseek.com"
export DEEPSEEK_MODEL_ADVISOR="deepseek-v4-pro"
```

## API

- `GET /api/candidates` — Candidate pool
- `GET /api/selected` — Human-confirmed selections
- `GET /api/daily` — Daily brief structure
- `GET /api/opportunities` — Project opportunities
- `GET /api/foreign-signals` — International / foreign-language signals
- `GET /api/risks` — Risk alerts
- `GET /api/evidence/:id` — Evidence chain
- `GET /api/content-briefs` — Content briefs for operations agents
- `POST /api/decisions` — Human confirm, reject, or adjust weights
- `POST /api/run-ingest` — Trigger ingestion and basic scoring
- `POST /api/run-review` — Generate review drafts, optionally with `webhook_url`

## Current Boundary

- `ingest` can still use `data/seed_items.json` as sample input; Xiaohongshu collection is now available via `xhs backfill` / `xhs daily`, driven by a logged-in browser or opencli, with output saved as JSON feed.
- Douyin, Reddit, Tripadvisor, YouTube, and other platform collectors will be added incrementally.
- DeepSeek V4 is a pluggable advisor layer; on missing key or API failure the system falls back to rules-based review to keep the daily pipeline running.
- Bilingual (Chinese/English) output is generated only before human review and final presentation; intermediate processing avoids bilingual expansion to save tokens.
- The automated pipeline only produces review drafts and never auto-publishes; confirmed items enter the web dashboard and formal API.
