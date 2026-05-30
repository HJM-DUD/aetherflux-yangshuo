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


def default_agent_payload(role: str, context: Mapping[str, Any], data: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "version": "0.2.7",
        "role": role,
        "context": dict(context),
        "data": dict(data),
        "output_schema": {
            "decision": "APPROVED | REJECTED | NEED_HUMAN | RETRY",
            "reason": "short Chinese explanation",
            "selected_item_ids": ["string"],
            "error_type": "auth_required | security_block | empty_result | command_failed | none",
        },
    }
