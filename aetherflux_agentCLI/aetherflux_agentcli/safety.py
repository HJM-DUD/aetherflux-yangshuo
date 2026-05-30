"""Hard safety boundary for autonomous browser actions."""

from __future__ import annotations

from enum import Enum
from typing import Mapping


class ActionSafety(str, Enum):
    ALLOWED = "allowed"
    NEED_HUMAN = "need_human"


BLOCKED_TERMS = (
    "登录",
    "密码",
    "验证码",
    "滑动",
    "账号设置",
    "发布",
    "支付",
    "删除",
    "上传",
    "private-file",
)
ALLOWED_ACTIONS = {"open", "click", "fill", "scroll", "wait", "extract"}


def classify_action(action: Mapping[str, object]) -> ActionSafety:
    action_name = str(action.get("action", "")).lower()
    target = str(action.get("target", ""))
    if action_name not in ALLOWED_ACTIONS:
        return ActionSafety.NEED_HUMAN
    if any(term.lower() in target.lower() for term in BLOCKED_TERMS):
        return ActionSafety.NEED_HUMAN
    if action_name == "upload":
        return ActionSafety.NEED_HUMAN
    return ActionSafety.ALLOWED
