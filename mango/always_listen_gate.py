"""Gate always-listen VAD utterances: only answer when transcript starts with a phrase."""

from __future__ import annotations

from collections.abc import Sequence

# Default when MANGO_ALWAYS_LISTEN_PREFIX_ONLY=1 (merged with MANGO_ALWAYS_LISTEN_PREFIX CSV).
# "Hey …" sound-alikes for mango + non-hey starters (e.g. terminal "main go", "mingo") where letters
# differ from bare ``mango`` so they need their own prefix (see ``letters_only_lower``).
_DEFAULT_HEY_FAMILY: tuple[str, ...] = (
    "hey mango",
    "hey main go",
    "hey mingo",
    "hey margo",
    "hey mongo",
    "hey mungo",
    "hey mengo",
    "hey mangoe",
    "hey may go",
    "hey my go",
    "hey me go",
    "hey mah go",
    "hey moi go",
    "hay mango",
    "hi mango",
    "yo mango",
)
# No leading "hey": still common STT for the wake (letters differ from ``mango`` alone).
_NO_HEY_STARTERS: tuple[str, ...] = (
    "main go",
    "mingo",
    "margo",
    "mongo",
    "mungo",
    "mengo",
    "mangoe",
    "may go",
    "mah go",
    "mango",
)
DEFAULT_PREFIX_ONLY_MISHEARS: tuple[str, ...] = tuple(
    dict.fromkeys(_DEFAULT_HEY_FAMILY + _NO_HEY_STARTERS)
)


def letters_only_lower(s: str) -> str:
    return "".join(c.lower() for c in (s or "") if c.isalpha())


def transcript_starts_with_prefix(text: str, prefix: str) -> bool:
    """True if ``text`` begins with ``prefix``, ignoring case and non-letters (e.g. \"Hey, mango …\")."""
    t = letters_only_lower(text)
    p = letters_only_lower(prefix)
    if not p:
        return True
    return t.startswith(p)


def transcript_starts_with_any_prefix(text: str, prefixes: Sequence[str]) -> bool:
    """True if ``text`` matches the start of any non-empty ``prefixes`` entry (letters-only, case-insensitive).

    Empty ``prefixes`` is treated as \"no gate\" (always True). Each prefix is checked with
    :func:`transcript_starts_with_prefix`; put longer phrases before shorter shared stems in env if you
    add custom CSV order matters only when one prefix is a prefix of another's *letter* form.
    """
    if not prefixes:
        return True
    for raw in prefixes:
        if transcript_starts_with_prefix(text, raw):
            return True
    return False
