"""Clipboard summarize / rewrite / todo extraction via one-shot LLM."""

from __future__ import annotations

import re
from typing import Any

from mango.config import Config
from mango.tools import read_clipboard

DESCRIPTION = (
    "Read the Windows clipboard and summarize, rewrite, or extract todo lines. "
    "Use when the user asks about pasted/copied content without pasting it in chat."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["summarize", "rewrite", "extract_todos"],
        },
        "style": {
            "type": "string",
            "description": "For rewrite: tone hint (concise, formal, friendly).",
        },
    },
    "required": ["action"],
    "additionalProperties": False,
}


def _extract_todos_heuristic(text: str) -> str:
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.search(r"\b(TODO|FIXME|ACTION)\b", line, re.I):
            lines.append(line)
        elif line.startswith(("-", "*", "•")) and len(line) > 2:
            lines.append(line.lstrip("-*• ").strip())
        elif re.match(r"^\d+[\).\]]\s+", line):
            lines.append(re.sub(r"^\d+[\).\]]\s+", "", line))
    if not lines:
        return "No obvious todos found — try summarizing the clip instead."
    return "Todos from clipboard:\n" + "\n".join(f"- {x}" for x in lines[:20])


def _llm_transform(text: str, instruction: str) -> str:
    cfg = Config.load()
    if not cfg.groq_api_key:
        return "Set GROQ_API_KEY for clipboard AI transforms."
    from mango.llm import GroqLLM

    llm = GroqLLM(api_key=cfg.groq_api_key, model=cfg.groq_model)
    messages = [
        {
            "role": "system",
            "content": "You transform clipboard text for a voice assistant. Be concise.",
        },
        {
            "role": "user",
            "content": f"{instruction}\n\n---\n{text[:12000]}",
        },
    ]
    completion = llm.chat(messages, tools=[])
    msg = completion.choices[0].message
    return (msg.content or "").strip() or "(empty response)"


def run(action: str, *, style: str | None = None) -> str:
    act = (action or "").strip().lower()
    clip = read_clipboard.run()
    if clip.startswith("Clipboard") and "empty" in clip.casefold():
        return clip
    if "ERR" in clip[:20]:
        return clip
    text = clip.strip()
    if not text:
        return "Clipboard is empty."

    if act == "extract_todos":
        return _extract_todos_heuristic(text)
    if act == "summarize":
        return _llm_transform(text, "Summarize this clipboard text in 2-4 short sentences.")
    if act == "rewrite":
        tone = (style or "concise").strip()
        return _llm_transform(text, f"Rewrite this clipboard text in a {tone} tone. Keep meaning.")
    return f"Unknown action {act!r}"
