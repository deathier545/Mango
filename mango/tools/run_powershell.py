"""Run a tiny set of whitelisted PowerShell snippets (host-enforced approval only)."""

from __future__ import annotations

import logging
import subprocess

from mango.timeouts import POWERSHELL_S

logger = logging.getLogger(__name__)

DESCRIPTION = (
    "Run a safe, pre-approved PowerShell command identified by command_key. "
    "Depending on host settings, Mango may require the user to agree in a follow-up message before execution; "
    "if so, first explain what will run and ask permission, then call again with the same command_key after they agree."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "command_key": {
            "type": "string",
            "enum": [
                "list_processes",
                "network_ipv4",
                "disk_free_space",
                "env_username",
            ],
            "description": "Which approved command to run.",
        },
    },
    "required": ["command_key"],
    "additionalProperties": False,
}


_ALLOWED: dict[str, str] = {
    "list_processes": (
        "Get-Process | Sort-Object CPU -Descending "
        "| Select-Object -First 15 Name,Id,CPU | Format-Table -AutoSize | Out-String -Width 200"
    ),
    "network_ipv4": (
        "Get-NetIPAddress -AddressFamily IPv4 "
        "| Where-Object { $_.IPAddress -notlike '169.254*' } "
        "| Select-Object InterfaceAlias,IPAddress | Format-Table -AutoSize | Out-String -Width 200"
    ),
    "disk_free_space": (
        "Get-PSDrive -PSProvider FileSystem "
        "| Select-Object Name,Used,Free | Format-Table -AutoSize | Out-String -Width 200"
    ),
    "env_username": "$env:USERNAME",
}


def run(command_key: str, *, _host_approved: bool = False) -> str:
    """Execute only when ``_host_approved`` is True (set exclusively by ``ToolRegistry``)."""
    key = (command_key or "").strip()
    if key not in _ALLOWED:
        logger.warning("Unknown command_key %r", key)
        return f"Error: unknown command_key {key!r}."
    if not _host_approved:
        logger.debug("PowerShell %r — host approval required (not executing).", key)
        return (
            "HOST_PENDING_POWERSHELL: not executed. In one sentence, describe what this read-only "
            "command shows, then ask the user for permission. When they clearly agree (e.g. yes, go ahead, "
            "or approve shell), call run_powershell again with the same command_key."
        )
    script = _ALLOWED[key]
    logger.warning("Host-approved PowerShell run: command_key=%s", key)
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=POWERSHELL_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.error("PowerShell timed out after %.0fs command_key=%r", POWERSHELL_S, key)
        return "PowerShell command timed out."
    except OSError as exc:
        logger.exception("Failed to spawn PowerShell")
        return f"Failed to launch PowerShell: {exc}"
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0:
        logger.warning(
            "PowerShell exit=%s stderr_preview=%r",
            proc.returncode,
            (err or "")[:400],
        )
        return f"Exit {proc.returncode}. STDERR: {err or '(empty)'}"
    if err:
        return f"{out}\nSTDERR: {err}" if out else err
    return out or "(no output)"
