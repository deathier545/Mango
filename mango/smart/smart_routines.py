"""Execute multi-step routines via the tool registry (balanced autonomy)."""

from __future__ import annotations

import logging
import re
from typing import Any

from mango.smart.smart_store import load_routines
from mango.tool_narration import (
    narrate_routine_step_after,
    narration_enabled,
    prefer_discord_for_tool,
    speak_progress,
    suppress_tool_narration,
    tool_start_line,
)

logger = logging.getLogger(__name__)

_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")

_AUTO_OK_RISKS = frozenset({"low", "medium"})


def _spotify_step_failed(out: str) -> bool:
    t = (out or "").casefold()
    if not t:
        return True
    if t.startswith("error:") or " error:" in t:
        return True
    if "{{query}}" in t or "query is empty" in t:
        return True
    if "track_played:" in t or "playing on spotify" in t or "playing in your browser" in t:
        return False
    if "opened spotify search" in t:
        return True
    return False


def _substitute(obj: Any, vars_map: dict[str, str]) -> Any:
    if isinstance(obj, str):
        def repl(m: re.Match[str]) -> str:
            return vars_map.get(m.group(1), m.group(0))

        return _PLACEHOLDER.sub(repl, obj)
    if isinstance(obj, dict):
        return {k: _substitute(v, vars_map) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute(v, vars_map) for v in obj]
    return obj


def list_routines_text() -> str:
    routines = load_routines()
    if not routines:
        return "No routines defined."
    lines = ["Routines:"]
    for r in routines:
        lines.append(f"- {r.get('id')}: {r.get('name')} — {r.get('description', '')}")
    return "\n".join(lines)


def execute_routine(
    registry: Any,
    routine_id: str,
    *,
    variables: dict[str, str] | None = None,
    auto_only: bool = True,
) -> str:
    routines = load_routines()
    routine = next((r for r in routines if r.get("id") == routine_id), None)
    if routine is None:
        return f"Unknown routine {routine_id!r}. {list_routines_text()}"

    steps = routine.get("steps")
    if not isinstance(steps, list) or not steps:
        return f"Routine {routine_id!r} has no steps."

    vars_map = dict(variables or {})
    lines = [f"Routine '{routine.get('name', routine_id)}':"]
    for i, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            continue
        tool = str(step.get("tool") or "").strip()
        args = step.get("arguments")
        if not tool or not isinstance(args, dict):
            lines.append(f"  {i}. skipped invalid step")
            continue
        args = _substitute(args, vars_map)
        if tool == "spotify_play":
            sq = args.get("query")
            if not isinstance(sq, str) or not sq.strip() or "{{" in sq:
                lines.append(
                    f"  {i}. spotify_play: skipped — missing song query "
                    f"(got {sq!r}); say which track to play."
                )
                continue
        if tool == "volume_control" and isinstance(args.get("percent"), str):
            try:
                args["percent"] = int(args["percent"])
            except ValueError:
                pass
        risk = registry.risk_level(tool)
        if auto_only and risk not in _AUTO_OK_RISKS:
            lines.append(f"  {i}. {tool}: skipped (risk={risk}, needs explicit user approval)")
            continue
        try:
            if narration_enabled():
                before = tool_start_line(tool, args)
                if before:
                    speak_progress(before, prefer_discord=prefer_discord_for_tool(tool, args))
            with suppress_tool_narration():
                out = registry.execute(tool, args)
            narrate_routine_step_after(tool, args, out)
            preview = (out or "").replace("\n", " ")[:120]
            lines.append(f"  {i}. {tool}: {preview}")
            if tool == "spotify_play" and _spotify_step_failed(out):
                lines.append(
                    "  (stopped routine — fix Spotify step before streaming to Discord.)"
                )
                break
        except Exception as exc:
            lines.append(f"  {i}. {tool}: ERR {exc}")
    return "\n".join(lines)
