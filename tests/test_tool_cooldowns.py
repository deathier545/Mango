from __future__ import annotations

import time

from mango.tool_cooldowns import TOOL_COOLDOWN_SECONDS, check_tool_cooldown, record_tool_run


def test_tool_cooldown_blocks_repeat() -> None:
    last: dict[str, float] = {}
    name = "volume_control"
    assert check_tool_cooldown(last, name) is None
    record_tool_run(last, name)
    blocked = check_tool_cooldown(last, name)
    assert blocked is not None
    assert "ERR_TOOL_COOLDOWN" in blocked


def test_tool_cooldown_allows_after_window() -> None:
    last: dict[str, float] = {"volume_control": time.time() - TOOL_COOLDOWN_SECONDS["volume_control"] - 0.01}
    assert check_tool_cooldown(last, "volume_control") is None
