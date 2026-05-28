# AetherFlux Yangshuo

"AetherFlux" sub-project: Yangshuo Tourism Intelligence Decision System. For internal content planning, opportunity assessment, risk identification, cross-verification, GEO likelihood evaluation, and as a data backbone for downstream operations agents.

V0.2.0 upgrades the project into a local-first video intelligence collector. It focuses on Xiaohongshu, Douyin, and WeChat Channels video posts, comments, repeated-topic signals, and auxiliary official-source monitoring. Raw intelligence, screenshots, video frames, audio, full comments, and full transcripts stay local or on a future NAS. Supabase Cloud is used only for login and lightweight daily log indexes.

## Quick Start

```bash
python3 -m unittest discover -s tests
python3 -m aetherflux.cli ingest
python3 -m aetherflux.cli review
python3 -m aetherflux.cli serve --host 127.0.0.1 --port 8788
```

Open:

```text
http://127.0.0.1:8788
```

Port `8765` is reserved for Triagent. AetherFlux Web defaults to `8788`; the local worker/API port is reserved as `8789`.

## Daily Review

Xiaohongshu (RED) initial backfill of the last 7 days, outputting raw item JSON for subsequent `ingest`:

```bash
python3 -m aetherflux.cli xhs backfill --days 7 --source data/xhs_source_items.json --output artifacts/xhs_raw_items.json
python3 -m aetherflux.cli ingest --seed artifacts/xhs_raw_items.json
```

## V0.2.0 Local Collector

V0.2.0 is local-first:

- `hard_dedupe_key` only collapses exact duplicates, such as the same URL, platform item ID, or media fingerprint.
- `topic_cluster_key` groups different users discussing the same event without deleting the original items.
- Video processing uses local `ffmpeg` for keyframes and audio extraction; speech-to-text should prefer local ASR.
- Comment collection keeps hot comments, recent comments, author replies, and comments matching risk/opportunity keywords.
- Official sources are configured on a separate admin page. When mission place, industry, or segment changes, official sources must be reviewed again and cannot silently carry over from a previous region.
- Each day produces a `daily_bundle_YYYY-MM-DD` handoff package for the downstream Super Brain stage.

Local evidence defaults to 48 hours of retention and can be adjusted from the admin UI. Cleanup deletes explicit file paths one by one and never recursively removes directories.

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
- `GET /api/admin/retention` — Local evidence and cloud log retention settings
- `POST /api/admin/retention` — Update local evidence hours and cloud log months
- `GET /api/admin/official-sources` — Official source list
- `POST /api/admin/official-sources` — Add or update an official source
- `POST /api/admin/missions` — Update a mission and mark official sources for review when place/industry/segments change
- `GET /api/daily-bundles` — Daily bundle index
- `GET /api/cloud-log-syncs` — Supabase lightweight log sync/cleanup records

## Current Boundary

- `ingest` can still use `data/seed_items.json` as sample input; Xiaohongshu collection is now available via `xhs backfill` / `xhs daily`, driven by a logged-in browser or opencli, with output saved as JSON feed.
- Douyin and WeChat Channels video collectors will be expanded behind the same raw item schema.
- PC worker mode is planned: if long-running collection is too heavy for the Mac, Part 1 can move to a PC that generates daily bundles for the Mac-side Super Brain stage.
- DeepSeek V4 is a pluggable advisor layer; on missing key or API failure the system falls back to rules-based review to keep the daily pipeline running.
- Bilingual (Chinese/English) output is generated only before human review and final presentation; intermediate processing avoids bilingual expansion to save tokens.
- The automated pipeline only produces review drafts and never auto-publishes; confirmed items enter the web dashboard and formal API.
