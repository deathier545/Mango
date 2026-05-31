"""Structured planner/executor state tracking for multi-step tool turns."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StepState:
    round_idx: int
    tool_name: str
    arguments: dict[str, Any]
    status: str = "pending"
    note: str = ""


@dataclass
class PlannerExecutorState:
    steps: list[StepState] = field(default_factory=list)

    def add_step(self, *, round_idx: int, tool_name: str, arguments: dict[str, Any]) -> StepState:
        step = StepState(round_idx=round_idx, tool_name=tool_name, arguments=arguments)
        self.steps.append(step)
        return step

    def mark_done(self, step: StepState, result: str) -> None:
        r = (result or "").strip()
        if r.startswith("ERR_") or r.startswith("PHONE_CALL_FAILED") or r.startswith("Tool call for"):
            step.status = "failed"
        elif r.startswith("HOST_PENDING_"):
            step.status = "needs_confirmation"
        else:
            step.status = "completed"
        step.note = (r[:160] + "…") if len(r) > 160 else r

    def compact_summary(self) -> str:
        if not self.steps:
            return "(no tool steps)"
        parts: list[str] = []
        for idx, s in enumerate(self.steps, start=1):
            parts.append(f"{idx}:{s.tool_name}:{s.status}")
        return " | ".join(parts)
