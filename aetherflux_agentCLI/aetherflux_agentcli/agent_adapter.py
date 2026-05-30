"""Configurable local agent command templates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping


@dataclass(frozen=True)
class AgentCommandTemplate:
    name: str
    command: List[str]
    timeout_seconds: int = 300

    def render(self, payload: Mapping[str, Any]) -> List[str]:
        payload_text = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True)
        return [part.replace("{payload}", payload_text) for part in self.command]


def default_agent_payload(role: str, observation: Mapping[str, Any], allowed_actions: List[str]) -> Dict[str, Any]:
    return {
        "version": "0.2.5",
        "role": role,
        "observation": dict(observation),
        "allowed_actions": list(allowed_actions),
        "output_schema": {
            "decision": "APPROVED | NEED_HUMAN | RETRY_WITH_ACTION | STOP",
            "reason": "short Chinese explanation",
            "action_payload": {"action": "open | click | fill | scroll | wait | extract", "target": "string"},
            "extracted_items": ["object"],
        },
    }
