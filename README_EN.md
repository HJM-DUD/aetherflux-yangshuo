# AetherFlux Yangshuo

"AetherFlux" sub-project: Yangshuo Tourism Intelligence Decision System. For internal content planning, opportunity assessment, risk identification, cross-verification, GEO likelihood evaluation, and as a data backbone for downstream operations agents.

## Product Frame

AetherFlux is planned as GuGU's internal agent application, not a public SaaS product. It will grow in five parts:

1. **Intelligence Collection Station**: the V0.2.x focus. Monitors specified accounts, searches public platforms, processes comments and video ASR, supports manual high-weight input, and emits daily bundles.
2. **Super Brain**: downstream analysis with Codex, Hermes, Antigravity, DeepSeek, cross-verification, opportunity/risk judgment, and weighting.
3. **Online Operations Center**: planning and operating GuGU's internet accounts, acquisition channels, and maintenance workflows.
4. **Content Generation Factory**: producing posts, scripts, images, videos, and notes based on intelligence and operations decisions.
5. **Offline Business Control**: managing customers, itineraries, costs, resources, and offline execution.

V0.2.x should make Part 1 reliable and expose clean handoff data/API surfaces for Part 2. Parts 2-5 should remain planned interfaces until real workflows are implemented.

V0.2.5 starts the dual-mode collector rebuild on top of the V0.2.4 Web admin:

- `aetherflux_shellCLI`: script/OpenCLI-led collection, with an agent supervising, screening, and diagnosing logs.
- `aetherflux_agentCLI`: agent-led collection, with OpenCLI and scripts as helper tools.

Both modes emit the same daily bundle contract and can copy bundles into `data/daily_bundles_inbox/{mode}/{date}/{run_id}/` for the downstream Super Brain stage.

V0.2.4 rebuilt the old V0.1 static dashboard as a React/Vite admin frontend plus a FastAPI backend. The first screen is a collection control console for title pools, screening, ASR processing, task logs, trash recovery, diagnostics, and release checks. Raw intelligence, videos, audio, full comments, and full transcripts stay local or on a future NAS. Supabase Cloud is used only for login and lightweight daily log indexes.

## Quick Start

```bash
python3 -m unittest discover -s tests
python3 -m compileall aetherflux
npm install
npm test
npm run build
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

Xiaohongshu (RED) `xhs` commands process JSON feed snapshots captured separately by another browser driver or manual export. They are not live crawlers, and they output raw item JSON for subsequent `ingest`:

```bash
python3 -m aetherflux.cli xhs backfill --days 7 --source data/xhs_source_items.json --output artifacts/xhs_raw_items.json
python3 -m aetherflux.cli ingest --seed artifacts/xhs_raw_items.json
```

## V0.2.3 ASR-First Collector

V0.2.3 is local-first and ASR-first:

- `hard_dedupe_key` only collapses exact duplicates, such as the same URL, platform item ID, or media fingerprint.
- `topic_cluster_key` groups different users discussing the same event without deleting the original items.
- Query planning uses manual keywords plus rule-based place/segment/risk/opportunity combinations, with optional Hermes exploration terms.
- OpenCLI Browser Bridge performs logged-in browser search, recent-time filtering attempts, scrolling, and title-pool extraction.
- Hermes screens the lightweight title pool and selects videos for deeper ASR processing.
- Video processing prioritizes full-video ASR transcripts over frame extraction. Keyframes are optional evidence only.
- Local `ffmpeg` extracts audio; ASR uses local backends such as `mlx-whisper`, `faster-whisper`, or `whisper` when installed.
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

Run V0.2.3 OpenCLI collection:

```bash
opencli doctor
AETHERFLUX_DRY_RUN=1 scripts/hermes_collect_opencli.sh
scripts/hermes_collect_opencli.sh
```

Run one stage only:

```bash
python3 -m aetherflux.cli opencli-rotate --stage titles
python3 -m aetherflux.cli opencli-rotate --stage screen
python3 -m aetherflux.cli opencli-rotate --stage videos
python3 -m aetherflux.cli opencli-rotate --stage all
```

Run the V0.2.5 collector subprojects:

```bash
cd aetherflux_shellCLI
python3 -m aetherflux_shellcli.cli run --dry-run
python3 -m aetherflux_shellcli.cli run --config config/collect.json --main-inbox ../data/daily_bundles_inbox

cd ../aetherflux_agentCLI
python3 -m aetherflux_agentcli.cli run --dry-run
python3 -m aetherflux_agentcli.cli run --main-inbox ../data/daily_bundles_inbox
```

Enable the DeepSeek advisor layer via local environment variables (never commit keys to the repo):

```bash
export DEEPSEEK_API_KEY="your-local-key"
export DEEPSEEK_BASE_URL="https://api.deepseek.com"
export DEEPSEEK_MODEL_ADVISOR="deepseek-v4-pro"
```

## API

V0.2.5 uses `/api/v1/*` as the formal API namespace:

- `GET /api/v1/dashboard/summary`
- `GET/PUT /api/v1/collection/config`
- `GET/POST /api/v1/collection/jobs`
- `GET /api/v1/collection/jobs/{job_id}`
- `GET /api/v1/collection/jobs/{job_id}/log`
- `POST /api/v1/collection/jobs/{job_id}/cancel`
- `GET /api/v1/intelligence/candidates`
- `POST /api/v1/intelligence/decisions`
- `GET /api/v1/intelligence/selected`
- `GET /api/v1/intelligence/daily`
- `GET /api/v1/intelligence/opportunities`
- `GET /api/v1/intelligence/foreign-signals`
- `GET /api/v1/intelligence/risks`
- `GET/POST /api/v1/admin/official-sources`
- `GET/POST /api/v1/admin/retention`
- `GET /api/v1/daily-bundles`
- `GET /api/v1/cloud-log-syncs`
- `GET/POST /api/v1/trash`
- `POST /api/v1/trash/restore`
- `POST /api/v1/trash/mark-cleanable`
- `GET /api/v1/system/status`
- `POST /api/v1/system/deepseek-smoke-test`
- `GET /api/v1/system/opencli-doctor`
- `GET /api/v1/system/diagnose`
- `GET /api/v1/title-pool`
- `GET /api/v1/video-processing`
- `GET /api/v1/agent/apis`
- `GET /api/v1/release/status`

The old `/api/*` routes remain only as legacy dashboard references, not the main V0.2.5 interface.

## Current Boundary

- `ingest` can still use `data/seed_items.json` as sample input; Xiaohongshu JSON feed processing is available via `xhs backfill` / `xhs daily`, while live logged-in browser collection is handled separately by `live` and `opencli-rotate`.
- WeChat Channels remains skipped until a reliable non-mobile collection path exists.
- From V0.2.3 onward, every formal version must be committed to GitHub, tagged, and released when GitHub CLI authentication is available.
- PC worker mode is planned: if long-running collection is too heavy for the Mac, Part 1 can move to a PC that generates daily bundles for the Mac-side Super Brain stage.
- DeepSeek V4 is a pluggable advisor layer; on missing key or API failure the system falls back to rules-based review to keep the daily pipeline running.
- Bilingual (Chinese/English) output is generated only before human review and final presentation; intermediate processing avoids bilingual expansion to save tokens.
- The automated pipeline only produces review drafts and never auto-publishes; confirmed items enter the web dashboard and formal API.
- Multi-select deletion in the admin UI is soft-delete only. Items can be restored within 14 days; the system never batch-deletes files or directories.
