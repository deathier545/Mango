"""Load `.env` from project root or cwd only (never parent walk)."""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_project_dotenv(project_root: Path) -> None:
    """Load environment from ``project_root/.env`` or ``cwd/.env`` if present."""
    env_project = project_root / ".env"
    env_cwd = Path.cwd() / ".env"
    dotenv_path: Path | None = None
    if env_project.is_file():
        dotenv_path = env_project
    elif env_cwd.is_file():
        dotenv_path = env_cwd

    if dotenv_path is not None:
        load_dotenv(
            dotenv_path=dotenv_path,
            override=True,
            encoding="utf-8-sig",
        )
        logger.debug("Loaded .env from %s (override=True)", dotenv_path)
    else:
        logger.warning(
            "No .env at project root (%s) or cwd (%s); using existing environment only.",
            env_project,
            env_cwd,
        )

    logger.debug(
        ".env checked root=%s exists=%s cwd=%s exists=%s",
        env_project,
        env_project.is_file(),
        Path.cwd(),
        env_cwd.is_file(),
    )
