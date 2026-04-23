"""Resolved project paths (dev tree vs PyInstaller frozen exe directory)."""

from __future__ import annotations

import sys
from pathlib import Path


def project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def manual_sync_request_path() -> Path:
    """Touch this file from Dashboard (subprocess) to ask the tray daemon to run one pipeline cycle."""
    return project_root() / ".manual_sync_request"


def manual_force_retry_request_path() -> Path:
    """Touch to ask the daemon for one cycle that resets exhausted failures and bypasses per-attempt give_up caps."""
    return project_root() / ".manual_force_retry_request"
