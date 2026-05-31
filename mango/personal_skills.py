"""Load optional Markdown skill snippets from disk (minimal personal catalog).

Drop ``*.md`` files under ``%USERPROFILE%\\.mango\\skills`` (or ``MANGO_SKILLS_DIR``).
Each file is injected into the system prompt under a bounded character budget.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def default_skills_dir() -> Path:
    return Path.home() / ".mango" / "skills"


def load_skills_markdown(skills_dir: Path, max_chars: int) -> str:
    """Return a single markdown block for the system prompt, or empty string."""
    max_chars = max(500, min(max_chars, 12_000))
    if not skills_dir.is_dir():
        logger.debug("Skills directory missing: %s", skills_dir)
        return ""

    parts: list[str] = []
    used = 0
    files = sorted(skills_dir.glob("*.md"))
    if not files:
        logger.debug("No .md skills in %s", skills_dir)
        return ""

    header_all = "\n\n## Personal skills (user notes; apply when relevant)\n"
    used += len(header_all)

    for path in files:
        try:
            raw = path.read_text(encoding="utf-8", errors="replace").strip()
        except OSError as exc:
            logger.warning("Could not read skill %s: %s", path, exc)
            continue
        if not raw:
            continue
        section_head = f"\n### {path.stem}\n"
        budget = max_chars - used - len(section_head)
        if budget < 120:
            logger.info(
                "Skills budget exhausted after %d section(s); remaining files skipped.",
                len(parts),
            )
            break
        body = raw if len(raw) <= budget else raw[: budget - 12] + "\n[truncated]"
        chunk = section_head + body
        parts.append(chunk)
        used += len(chunk)

    if not parts:
        return ""

    logger.info(
        "Loaded %d personal skill file(s) from %s (~%d chars).",
        len(parts),
        skills_dir,
        used,
    )
    return header_all + "".join(parts)
