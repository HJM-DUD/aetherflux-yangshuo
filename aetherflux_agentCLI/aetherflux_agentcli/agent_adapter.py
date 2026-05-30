"""Configurable local agent command templates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping


@dataclass(frozen=True)
class AgentCommandTemplate:
    name: str
    command: List[str]
    timeout_seconds: int | None = None

    def render(self, payload: Mapping[str, Any]) -> List[str]:
        payload_text = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True)
        return [part.replace("{payload}", payload_text) for part in self.command]


def default_agent_payload(role: str, observation: Mapping[str, Any], allowed_actions: List[str]) -> Dict[str, Any]:
    return {
        "version": "0.2.7",
        "role": role,
        "instruction": "你是 agentCLI 的主导采集 agent。请只返回一个 JSON object，不要 Markdown，不要解释文字，不要代码块。若允许继续公开采集，decision=APPROVED；遇到登录、验证码、账号设置、发布、支付、删除、上传，decision=NEED_HUMAN。",
        "observation": dict(observation),
        "allowed_actions": list(allowed_actions),
        "output_schema": {
            "decision": "APPROVED | NEED_HUMAN | RETRY_WITH_ACTION | STOP",
            "reason": "short Chinese explanation",
            "action_payload": {"action": "open | click | fill | scroll | wait | extract", "target": "string"},
            "extracted_items": ["object"],
        },
    }
