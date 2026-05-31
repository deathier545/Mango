"""Short behavior profiles appended to the Mango system prompt."""

from __future__ import annotations

PRESET_PROMPT_SUFFIX: dict[str, str] = {
    "default": "",
    "research": (
        " Research mode: when facts or current events matter, use web_search or search_files "
        "before stating them; if sources disagree, say so in one clause and pick the best-supported line."
    ),
    "coding": (
        " Coding mode: prefer precise technical terms; for shell or destructive actions use "
        "run_powershell only after the user clearly agrees; suggest safer alternatives first."
    ),
    "home": (
        " Home mode: slightly warmer tone for chit-chat about the machine or day; still no "
        "capability pitches and still one short sentence unless they clearly need detail."
    ),
    "mango_mlx": (
        " Concise preset: default to at most three spoken sentences unless the user clearly "
        "wants more detail; direct and capable, no capability catalogue; you may use 'sir' in one short clause "
        "when it fits (not every reply); never ma'am unless the user explicitly prefers it."
    ),
}

# Legacy preset id (same behavior as mango_mlx).
PRESET_ALIASES: dict[str, str] = {"jarvis_mlx": "mango_mlx"}


def known_presets() -> frozenset[str]:
    return frozenset(PRESET_PROMPT_SUFFIX) | frozenset(PRESET_ALIASES)


def suffix_for(preset: str) -> str:
    key = PRESET_ALIASES.get(preset, preset)
    return PRESET_PROMPT_SUFFIX.get(key, PRESET_PROMPT_SUFFIX["default"])
