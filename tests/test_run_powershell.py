"""Unit tests for whitelisted PowerShell tool."""

from __future__ import annotations

import shutil

import pytest

from mango.tools.run_powershell import run as run_powershell


def test_powershell_pending_without_host_approval():
    out = run_powershell("list_processes", _host_approved=False)
    assert "HOST_PENDING_POWERSHELL" in out


def test_powershell_unknown_key_even_when_approved():
    out = run_powershell("not_a_real_command", _host_approved=True)
    assert "unknown" in out.lower()


@pytest.mark.skipif(
    not (shutil.which("powershell") or shutil.which("pwsh")),
    reason="PowerShell not on PATH",
)
def test_powershell_approved_env_username_runs():
    out = run_powershell("env_username", _host_approved=True)
    assert out.strip()
    assert "HOST_PENDING" not in out
