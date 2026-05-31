"""Structured self-help / psychoeducation (not licensed therapy)."""

from __future__ import annotations

import re
from typing import Any

DESCRIPTION = (
    "Use when the user sounds emotionally low or needs support ideas — including casual venting without asking for "
    "'therapy' by name (e.g. bad day, rough day, feeling off, lonely, overwhelmed, anxious, stressed, sad, angry, "
    "can't sleep because of worry, burned out, heartbroken, scared, 'not okay', 'going through it'). "
    "Also use when they ask for coping, grounding, perspective, or self-help skills. "
    "Do NOT use for neutral PC tasks, facts-only questions, or brief mild annoyance that clearly targets a technical fix. "
    "Pass situation as a short honest summary of what they said (their words / gist). "
    "Returns brief skills plus safety framing — not diagnosis or clinical care; crisis guidance if self-harm is implied."
)

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "situation": {
            "type": "string",
            "description": (
                "Concise paraphrase of what the user said or implied this turn (feelings, stressors, context). "
                "Use their gist in your own words; do not invent facts they did not suggest."
            ),
        },
        "focus": {
            "type": "string",
            "description": "Optional theme hint: anxiety, sleep, stress, low_mood, anger, or general.",
            "enum": ["anxiety", "sleep", "stress", "low_mood", "anger", "general"],
        },
    },
    "required": ["situation"],
    "additionalProperties": False,
}

_DISCLAIMER = (
    "Safety note: this is self-help guidance, not clinical care.\n\n"
)

_CRISIS = (
    "If you are in immediate danger or might harm yourself: pause and call your local emergency number "
    "now (US/Canada: 988 or 911). You deserve support from a real person who can help in real time.\n\n"
)

_CRISIS_PAT = re.compile(
    r"\b(suicid|kill myself|end my life|end it all|self[- ]harm|hurt myself|"
    r"don'?t want to live|better off dead)\b",
    re.IGNORECASE,
)

_FOCUS_KEYS: dict[str, tuple[str, ...]] = {
    "anxiety": ("anxious", "anxiety", "panic", "worry", "nervous", "racing heart"),
    "sleep": ("sleep", "insomnia", "tired", "wake up", "can't sleep", "cant sleep"),
    "stress": ("stress", "overwhelm", "burnout", "pressure", "deadline"),
    "low_mood": ("sad", "depress", "hopeless", "empty", "down", "cry"),
    "anger": ("angry", "rage", "furious", "resent", "irritat"),
}


def _detect_focus(situation: str, hint: str | None) -> str:
    if hint and hint != "general":
        return hint
    t = situation.casefold()
    scores: dict[str, int] = {k: 0 for k in _FOCUS_KEYS}
    for name, keys in _FOCUS_KEYS.items():
        for k in keys:
            if k in t:
                scores[name] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


_BLOCKS: dict[str, str] = {
    "anxiety": (
        "Anxiety / worry (skills)\n"
        "- Grounding 5-4-3-2-1: name 5 things you see, 4 you feel, 3 you hear, 2 you smell, 1 you taste.\n"
        "- Slow exhale: breathe in ~4s, out ~6–8s, repeat for a few minutes (longer exhale cues calm).\n"
        "- Name the story vs facts: write one worried thought, then one sentence of what you actually know.\n"
        "- Short walk or cold water on wrists can blunt adrenaline spikes.\n"
    ),
    "sleep": (
        "Sleep (habits)\n"
        "- Fixed wake time daily; light soon after waking helps the circadian anchor.\n"
        "- Wind-down 30–60 min: dim light, same low-stimulation routine; bed mainly for sleep.\n"
        "- If awake >20 min in bed, get up, low light, return when sleepier (strengthens bed–sleep link).\n"
        "- Limit late caffeine; heavy late meals and alcohol fragment sleep even if they feel sedating.\n"
    ),
    "stress": (
        "Stress / overload\n"
        "- One-page brain dump: list tasks, then star only what matters today; defer the rest visibly.\n"
        "- 10-minute timer on the smallest next step — momentum beats planning loops.\n"
        "- Body reset: shoulders down, unclench jaw, slow exhale, 60s of stretching.\n"
        "- Boundaries: one clear sentence you can repeat ('I can’t take that on today').\n"
    ),
    "low_mood": (
        "Low mood (behavioral activation)\n"
        "- Pick one tiny action (shower, text one person, 5-min walk) — mood often follows motion, not the reverse.\n"
        "- Catch one small win and say it aloud; depression shrinks the scoreboard — widen it on purpose.\n"
        "- Reduce isolation in micro-doses: voice note a friend, sit on the porch, brief call.\n"
        "- If mood stays very low for weeks or you lose functioning, prioritize a clinician — tools here are adjuncts.\n"
    ),
    "anger": (
        "Anger / irritation\n"
        "- Pause label: say 'I’m activated' and wait 20 seconds before typing or speaking big decisions.\n"
        "- Ice or cold water + slow exhale to downshift physiology.\n"
        "- Write the insult you want to send, don’t send — delete after the wave passes.\n"
        "- Under anger is often hurt or fear — one sentence each: 'I’m hurt because…' 'I’m scared that…'\n"
    ),
    "general": (
        "General coping\n"
        "- HALT quick check: Hungry? Angry? Lonely? Tired? — fix the easiest lever first.\n"
        "- One self-compassion line you’d say to a friend; say it slowly to yourself.\n"
        "- 10-minute timer: one kind action for Future You (water, trash out, one email).\n"
        "- Pair worry with a calendar slot named 'worry time' so the mind learns it can defer spirals.\n"
    ),
}


def run(situation: str, focus: str | None = None) -> str:
    s = (situation or "").strip()
    if not s:
        return "Error: describe what you’re dealing with in a sentence or two."
    f = (focus or "general").strip().lower() or "general"
    if f not in _BLOCKS:
        f = "general"
    f = _detect_focus(s, f if f != "general" else None)

    parts: list[str] = [_DISCLAIMER]
    if _CRISIS_PAT.search(s):
        parts.append(_CRISIS)
    parts.append(f"User situation (paraphrase carefully in speech): {s[:500]}\n\n")
    parts.append(_BLOCKS.get(f, _BLOCKS["general"]))
    if f != "general":
        parts.append("\n" + _BLOCKS["general"])
    out = "".join(parts)
    if len(out) > 8000:
        out = out[:7960] + "\n…[truncated]"
    return out
