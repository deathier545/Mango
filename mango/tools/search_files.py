"""Search files under whitelisted user folders."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


DESCRIPTION = (
    "Search for files by substring in the FILE NAME only (not file contents) under Documents, "
    "Desktop, and Downloads. Does not search outside those folders. Result limit is fixed by the "
    "host — only pass query and optional extension. For 'text inside files', say you can only "
    "match names unless the user opens the file."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "Substring to match against file names (case-insensitive).",
        },
        "extension": {
            "type": "string",
            "description": "Optional file extension filter like .pdf or pdf.",
        },
    },
    "required": ["query"],
    "additionalProperties": False,
}


def _normalize_extension(ext: str | None) -> str | None:
    if not ext:
        return None
    e = ext.strip().lower()
    if not e:
        return None
    return e if e.startswith(".") else f".{e}"


def _is_under_root(candidate: Path, root: Path) -> bool:
    try:
        cand = candidate.resolve()
        root_r = root.resolve()
        cand.relative_to(root_r)
        return True
    except (ValueError, OSError):
        return False


def run(
    roots: tuple[Path, ...],
    cap: int,
    query: str,
    extension: str | None = None,
) -> str:
    if not roots:
        return "File search is unavailable: no allowed folders are configured."
    q = (query or "").strip().casefold()
    if not q:
        return "Error: query is empty."
    limit = max(1, min(cap, 50))
    ext = _normalize_extension(extension)
    hits: list[str] = []
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for path in root.rglob("*"):
                if len(hits) >= limit:
                    break
                if not path.is_file():
                    continue
                if not _is_under_root(path, root):
                    continue
                if ext and path.suffix.casefold() != ext.casefold():
                    continue
                if q in path.name.casefold():
                    hits.append(str(path.resolve()))
        except OSError as exc:
            logger.warning("Scan failed under %s: %s", root, exc, exc_info=True)
            hits.append(f"(scan error under {root}: {exc})")
    if not hits:
        return "No matching files found."
    lines = "\n".join(hits[:limit])
    suffix = "" if len(hits) <= limit else f"\n...and more ({len(hits) - limit} truncated)."
    return lines + suffix
