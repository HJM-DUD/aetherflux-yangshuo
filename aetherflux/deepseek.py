"""DeepSeek V4 client used as a pluggable advisor layer."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

STATUS_PATH = Path("artifacts/deepseek_status.json")


class DeepSeekAdvisorError(RuntimeError):
    """Raised when the mandatory DeepSeek advisor gate cannot complete."""


@dataclass(frozen=True)
class DeepSeekConfig:
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-pro"
    timeout_seconds: int = 300
    max_attempts: int = 3

    @property
    def enabled(self) -> bool:
        return bool(self.api_key.strip())

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, dotenv_path: str = ".env") -> "DeepSeekConfig":
        source = dict(load_dotenv_values(dotenv_path))
        source.update(dict(env or os.environ))
        return cls(
            api_key=source.get("DEEPSEEK_API_KEY", "").strip(),
            base_url=source.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/"),
            model=source.get("DEEPSEEK_MODEL_ADVISOR", "deepseek-v4-pro").strip() or "deepseek-v4-pro",
            timeout_seconds=300,
            max_attempts=int(source.get("DEEPSEEK_MAX_ATTEMPTS", "3") or "3"),
        )


class DeepSeekClient:
    def __init__(self, config: DeepSeekConfig | None = None) -> None:
        self.config = config or DeepSeekConfig.from_env()

    def advise_candidates(self, candidates: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
        if not self.config.enabled:
            raise DeepSeekAdvisorError("DeepSeek is required but DEEPSEEK_API_KEY is not configured")
        prompt = build_advisor_prompt(list(candidates))
        return self.request_json(prompt)

    def request_json(self, prompt: str) -> Dict[str, Any]:
        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are the AetherFlux Yangshuo advisor think tank. "
                        "Return strict JSON only. Evaluate tourism intelligence, cross-check needs, "
                        "GEO-style information pollution risk, and bilingual display text."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            f"{self.config.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "AetherFlux-Yangshuo/0.2",
            },
            method="POST",
        )
        last_error = ""
        for attempt in range(1, self.config.max_attempts + 1):
            record_deepseek_status(
                {
                    "state": "awaiting_reply",
                    "model": self.config.model,
                    "base_url": self.config.base_url,
                    "checked_at": utc_now(),
                    "attempt": attempt,
                    "max_attempts": self.config.max_attempts,
                    "timeout_seconds": self.config.timeout_seconds,
                }
            )
            try:
                with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                    data = json.loads(response.read().decode("utf-8"))
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")
                parsed = parse_json_content(content)
            except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError, ValueError) as exc:
                last_error = str(exc)
                record_deepseek_status(
                    {
                        "state": "error",
                        "model": self.config.model,
                        "base_url": self.config.base_url,
                        "checked_at": utc_now(),
                        "attempt": attempt,
                        "max_attempts": self.config.max_attempts,
                        "timeout_seconds": self.config.timeout_seconds,
                        "error": last_error[:500],
                    }
                )
                continue
            if not isinstance(parsed, dict):
                last_error = "advisor response is not an object"
                continue
            record_deepseek_status(
                {
                    "state": "connected",
                    "model": self.config.model,
                    "base_url": self.config.base_url,
                    "checked_at": utc_now(),
                    "replied_at": utc_now(),
                    "attempt": attempt,
                    "max_attempts": self.config.max_attempts,
                }
            )
            return parsed
        record_deepseek_status(
            {
                "state": "failed_after_retries",
                "model": self.config.model,
                "base_url": self.config.base_url,
                "checked_at": utc_now(),
                "attempt": self.config.max_attempts,
                "max_attempts": self.config.max_attempts,
                "timeout_seconds": self.config.timeout_seconds,
                "error": last_error[:500],
            }
        )
        raise DeepSeekAdvisorError(
            f"DeepSeek advisor failed after {self.config.max_attempts} attempts: {last_error or 'unknown error'}"
        )


def parse_json_content(content: str) -> Dict[str, Any]:
    text = content.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1).strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"DeepSeek response is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("DeepSeek response must be a JSON object")
    return parsed


def load_dotenv_values(path: str = ".env") -> Dict[str, str]:
    if not os.path.exists(path):
        return {}
    values: Dict[str, str] = {}
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                values[key] = value
    return values


def read_deepseek_status(path: Path = STATUS_PATH) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def record_deepseek_status(status: Mapping[str, Any], path: Path = STATUS_PATH) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(dict(status), ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_advisor_prompt(candidates: list[Mapping[str, Any]]) -> str:
    compact = [
        {
            "id": item.get("id"),
            "title": item.get("title"),
            "summary": item.get("summary"),
            "language": item.get("language"),
            "platform": item.get("platform"),
            "source": item.get("source"),
            "signals": item.get("signals", []),
            "score": item.get("score", 0),
            "evidence": item.get("evidence", [])[:3],
        }
        for item in candidates[:30]
    ]
    return (
        "Evaluate these Yangshuo tourism intelligence candidates.\n"
        "Return JSON with this exact top-level shape: {\"items\": [...]}.\n"
        "For each item include: id, display {title_zh,title_en,summary_zh,summary_en}, "
        "translation_status, advisor_notes {confidence,summary,opportunities,risks,human_questions}, "
        "cross_check {status,supporting_sources,conflicting_sources,needs_more_sources,reasoning}, "
        "geo_risk {probability,level,reasons}, tags [short Chinese topic tags for human review].\n"
        "GEO risk means suspected generative-engine optimization, narrative manipulation, or information pollution; "
        "state probability only, never make accusations.\n"
        "Translate only for display and review. Do not invent sources.\n\n"
        + json.dumps({"candidates": compact}, ensure_ascii=False)
    )
