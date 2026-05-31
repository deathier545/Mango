"""Keep rolling chat history bounded so latency and token spend stay predictable."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def trim_conversation(messages: list[dict[str, Any]], max_messages: int) -> None:
    """Retain system prompt plus the last ``max_messages`` non-system messages.

    Drops orphaned ``tool`` messages at the front of the kept suffix so we do not
    lead with tool results without their assistant/tool_calls pair. (Rare edge case.)
    """
    if max_messages <= 0 or len(messages) <= 1:
        return
    cap = max_messages
    if len(messages) <= 1 + cap:
        return

    system = messages[0]
    if system.get("role") != "system":
        logger.debug(
            "trim_conversation: first message not system — trimming suffix only",
        )
        tail = messages[-cap:]
        while tail and tail[0].get("role") == "tool":
            tail = tail[1:]
        messages[:] = tail
        return

    tail = messages[1:][-cap:]
    while tail and tail[0].get("role") == "tool":
        tail = tail[1:]
    new_len = 1 + len(tail)
    if new_len < len(messages):
        logger.debug(
            "Trimmed conversation: %d -> %d messages (cap=%d)",
            len(messages),
            new_len,
            cap,
        )
    messages[:] = [system, *tail]
