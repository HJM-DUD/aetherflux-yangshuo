"""Local dashboard and internal JSON API server."""

from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict
from urllib.parse import parse_qs, urlparse

from .api import build_public_payloads
from .pipeline import run_ingest, run_review
from .storage import IntelligenceStore

WEB_DIR = Path(__file__).parent / "web"
DEFAULT_DIRECTIONS = Path("config/directions.json")
DEFAULT_SEED = Path("data/seed_items.json")


def render_index() -> str:
    return (WEB_DIR / "index.html").read_text(encoding="utf-8")


def run_server(store: IntelligenceStore, host: str = "127.0.0.1", port: int = 8765) -> None:
    handler = make_handler(store)
    httpd = ThreadingHTTPServer((host, port), handler)
    print(f"AetherFlux dashboard: http://{host}:{port}")
    httpd.serve_forever()


def make_handler(store: IntelligenceStore) -> type[BaseHTTPRequestHandler]:
    class AetherFluxHandler(BaseHTTPRequestHandler):
        server_version = "AetherFlux/0.1"

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_text(render_index(), "text/html; charset=utf-8")
                return
            if parsed.path.startswith("/static/"):
                self._send_static(parsed.path)
                return
            if parsed.path.startswith("/api/"):
                self._send_json(self._api_get(parsed.path))
                return
            self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            body = self._read_json_body()
            if parsed.path == "/api/decisions":
                candidate_id = str(body.get("id", ""))
                if not candidate_id:
                    self._send_json({"error": "id_required"}, HTTPStatus.BAD_REQUEST)
                    return
                weight = body.get("weight_override")
                weight_override = int(weight) if weight not in (None, "") else None
                store.set_human_decision(
                    candidate_id,
                    str(body.get("status", "pending")),
                    weight_override=weight_override,
                    note=str(body.get("note", "")),
                )
                self._send_json({"ok": True, "candidate": store.get_candidate(candidate_id)})
                return
            if parsed.path == "/api/run-ingest":
                query = parse_qs(parsed.query)
                directions = query.get("directions", [str(DEFAULT_DIRECTIONS)])[0]
                seed = query.get("seed", [str(DEFAULT_SEED)])[0]
                self._send_json(run_ingest(store, directions, seed))
                return
            if parsed.path == "/api/run-review":
                self._send_json(run_review(store, str(body.get("webhook_url", "")), top_n=int(body.get("top_n", 20))))
                return
            self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)

        def log_message(self, fmt: str, *args: Any) -> None:
            print("%s - %s" % (self.address_string(), fmt % args))

        def _api_get(self, path: str) -> Dict[str, Any]:
            payloads = build_public_payloads(store)
            if path == "/api/candidates":
                return {"items": store.list_candidates(limit=300)}
            if path == "/api/selected":
                return {"items": payloads["selected"]}
            if path == "/api/daily":
                return payloads["daily"]
            if path == "/api/opportunities":
                return {"items": payloads["opportunities"]}
            if path == "/api/foreign-signals":
                return {"items": payloads["foreign_signals"]}
            if path == "/api/risks":
                return {"items": payloads["risks"]}
            if path == "/api/content-briefs":
                return {"items": payloads["content_briefs"]}
            if path == "/api/review-drafts/latest":
                return store.latest_review_draft()
            if path.startswith("/api/evidence/"):
                candidate_id = path.rsplit("/", 1)[-1]
                candidate = store.get_candidate(candidate_id)
                return {"id": candidate_id, "evidence": candidate.get("evidence", []), "candidate": candidate}
            return {"error": "not_found"}

        def _send_static(self, path: str) -> None:
            relative = path.replace("/static/", "", 1)
            target = (WEB_DIR / relative).resolve()
            if not str(target).startswith(str(WEB_DIR.resolve())) or not target.exists():
                self._send_json({"error": "not_found"}, HTTPStatus.NOT_FOUND)
                return
            content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(target.read_bytes())

        def _read_json_body(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length == 0:
                return {}
            raw = self.rfile.read(length)
            return json.loads(raw.decode("utf-8"))

        def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_text(self, text: str, content_type: str) -> None:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(text.encode("utf-8"))

    return AetherFluxHandler
