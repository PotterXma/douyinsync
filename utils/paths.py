"""Resolved project paths (dev tree vs PyInstaller frozen exe directory)."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def data_root() -> Path:
    """
    数据根目录：``config.json``、``douyinsync.db``、``logs/``、``downloads/`` 都放这里。

    - 可选：环境变量 ``DOUYINSYNC_DATA_DIR`` 为 **绝对路径** 且目录存在时，优先生效
     （便于在源码运行 ``python main.py`` 时仍使用 ``dist\\DouyinSync`` 下的一套配置/库文件）。
    - 打包为 exe 时，默认为 ``DouyinSync.exe`` 所在目录（与当前工作目录无关）。
    - 源码开发时，默认为本仓库根目录（``utils`` 的上一级）。
    """
    override = (os.environ.get("DOUYINSYNC_DATA_DIR") or "").strip()
    if override:
        p = Path(override)
        if p.is_dir():
            return p.resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def project_root() -> Path:
    return data_root()


def manual_sync_request_path() -> Path:
    """Touch this file from Dashboard (subprocess) to ask the tray daemon to run one pipeline cycle."""
    return project_root() / ".manual_sync_request"


def manual_force_retry_request_path() -> Path:
    """Touch to ask the daemon for one cycle that resets exhausted failures and bypasses per-attempt give_up caps."""
    return project_root() / ".manual_force_retry_request"


def reload_config_request_path() -> Path:
    """Touch after writing ``config.json`` (e.g. from「搬运时间设置看板」) so the tray daemon reloads config and reapplies APScheduler primary jobs."""
    return project_root() / ".reload_config_request"


def hud_scheduler_state_path() -> Path:
    """主进程定期写入的调度快照；`dashboard` 子进程只读，用于显示任务名、下次触发（北京时间）与状态。"""
    return project_root() / ".hud_scheduler_state.json"
