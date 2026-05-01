"""
Dashboard / Epic 5：主同步「任务名、计划说明、运行态」序列化与展示文案。
与 BMad 5-1 一致：子进程只读本文件 + config 推断计划（主进程未运行时回退为纯配置说明）。
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from modules.config_manager import config
from modules.logger import logger
from utils.paths import hud_scheduler_state_path

Z_BJ = __import__("zoneinfo", fromlist=["ZoneInfo"]).ZoneInfo("Asia/Shanghai")

PRIMARY_JOB_ID_PREFIX = "primary_sync"

# 超过该秒数未刷新则视为主进程可能未在运行（Dashboard 子进程用）
HUD_STATE_STALE_SEC = 30.0


@dataclass
class ScheduleCaption:
    mode: str
    detail_zh: str
    interval_minutes: int | None
    clock_slots_zh: str


def _norm_mode(raw: object) -> str:
    m = str(raw or "interval").lower().strip()
    if m in ("clock", "cron", "fixed_times", "fixed", "time", "daily"):
        return "clock"
    return "interval"


def _parse_clock_times_from_dict(data: dict[str, Any]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    raw_times = data.get("sync_clock_times", None)
    if isinstance(raw_times, list):
        for t in raw_times:
            if not isinstance(t, str) or ":" not in t:
                continue
            parts = t.strip().split(":", 1)
            try:
                h = int(parts[0].strip())
                mi = int(parts[1].strip())
            except ValueError:
                continue
            if 0 <= h <= 23 and 0 <= mi <= 59:
                out.append((h, mi))
    if out:
        return out
    try:
        h = int(data.get("cron_hour", 2))
        mi = int(data.get("cron_minute", 0))
    except (TypeError, ValueError):
        return []
    if 0 <= h <= 23 and 0 <= mi <= 59:
        return [(h, mi)]
    return []


def _fmt_hm(t: tuple[int, int]) -> str:
    return f"{t[0]:02d}:{t[1]:02d}"


def build_schedule_caption(data: dict[str, Any] | None) -> ScheduleCaption:
    """从 config 根 dict 生成计划说明（定时的 HH:MM 为与系统时区一致；在中国即北京时间）。"""
    d = data or {}
    mode = _norm_mode(d.get("sync_schedule_mode", "interval"))
    if mode == "clock":
        slots = _parse_clock_times_from_dict(d)
        if not slots:
            return ScheduleCaption(
                "interval",
                "已选「定时」但未配有效时间，主进程会退回间隔模式（以日志为准）",
                None,
                "—",
            )
        s = "、".join(_fmt_hm(t) for t in sorted(slots))
        return ScheduleCaption(
            "clock",
            f"按本机时区整点（中国为北京时间 UTC+8）每日：{s}",
            None,
            s,
        )
    im = d.get("sync_interval_minutes", 60)
    try:
        im = max(1, int(im))
    except (TypeError, ValueError):
        im = 60
    if im >= 1440 and im % 1440 == 0:
        d_str = f"{im // 1440} 天" if im > 1440 else "24 小时"
        return ScheduleCaption(
            "interval",
            f"间隔 {im} 分钟（每 {d_str}）——自调度/启动起算，非每天固定整点",
            im,
            "—",
        )
    return ScheduleCaption("interval", f"间隔 {im} 分钟", im, "—")


def _dt_to_bj_str(dt: datetime) -> str:
    # naive：APScheduler 的 next_run 多为「本地时区墙钟」且无时区信息。在中国区 Windows
    # 上通常可视为与 Asia/Shanghai 一致。若显式为 aware，则正常换算到东八区显示。
    if dt.tzinfo is None:
        t = dt.replace(tzinfo=Z_BJ)
    else:
        t = dt.astimezone(Z_BJ)
    return t.strftime("%Y-%m-%d %H:%M:%S 北京")


def _scheduler_state_name(sched) -> str:
    try:
        from apscheduler.schedulers.base import STATE_PAUSED, STATE_STOPPED, STATE_RUNNING

        st = getattr(sched, "state", None)
        if st == STATE_PAUSED:
            return "监控已暂停（不触发定时间隔/定时点）"
        if st == STATE_STOPPED:
            return "监控已停止"
        if st == STATE_RUNNING:
            return "监控运行中"
    except Exception:
        pass
    if getattr(sched, "running", False):
        return "监控运行中"
    return "监控状态未知"


def _primary_sync_jobs(coordinator) -> list:
    out: list = []
    for j in coordinator.scheduler.get_jobs():
        jid = (getattr(j, "id", None) or "") and str(j.id)
        if jid and jid.startswith(PRIMARY_JOB_ID_PREFIX):
            out.append(j)
    return out


def _pipeline_hot(coordinator) -> bool:
    if getattr(coordinator, "_primary_pipeline_active", False):
        return True
    lk = getattr(coordinator, "_pipeline_lock", None)
    if lk is not None and hasattr(lk, "locked") and lk.locked():
        return True
    return False


def build_hud_payload_dict(coordinator) -> dict[str, Any]:
    """在守护进程、持有 PipelineCoordinator 时构建写入磁盘的 JSON。"""
    t0 = time.time()
    raw: dict[str, Any] = {}
    try:
        p = Path(config.config_file)
        if p.is_file():
            with open(p, "r", encoding="utf-8") as f:
                raw = json.load(f)
    except Exception as e:
        logger.debug("hud: load config for caption failed: %s", e)
    cap = build_schedule_caption(raw)
    sched = coordinator.scheduler
    st_name = _scheduler_state_name(sched)
    jobs = _primary_sync_jobs(coordinator)
    next_runs: list[dict[str, Any]] = []
    for j in jobs:
        nr = getattr(j, "next_run_time", None)
        if nr is not None and isinstance(nr, datetime):
            next_runs.append(
                {
                    "job_id": str(j.id),
                    "next_local_iso": nr.isoformat(),
                    "next_bj": _dt_to_bj_str(nr),
                }
            )
    # 最早一次（按真实 datetime 排序）
    by_iso: list[tuple[datetime, Any]] = []
    for j in jobs:
        nr = getattr(j, "next_run_time", None)
        if isinstance(nr, datetime):
            by_iso.append((nr, j))
    earliest_bj: str
    if by_iso:
        by_iso.sort(key=lambda x: x[0])
        earliest_bj = _dt_to_bj_str(by_iso[0][0])
    elif next_runs:
        earliest_bj = next_runs[0].get("next_bj", "—")
    else:
        earliest_bj = "—（调度器无下次触发时间）"

    return {
        "version": 1,
        "updated_at": t0,
        "task_id": "primary_sync",
        "task_name_zh": "主同步（抖音拉取 → 本地下载 → YouTube 上传）",
        "schedule_mode": cap.mode,
        "schedule_detail_zh": cap.detail_zh,
        "clock_slots_zh": cap.clock_slots_zh,
        "interval_minutes": cap.interval_minutes,
        "scheduler_status_zh": st_name,
        "pipeline_cycle_zh": "主管道执行中" if _pipeline_hot(coordinator) else "主管道空闲",
        "next_runs": next_runs,
        "earliest_next_bj": earliest_bj,
    }


def _replace_with_retries(src: Path, dst: Path, *, attempts: int = 12) -> None:
    """Windows 上其它进程短时占用 ``dst``（只读打开）时 ``os.replace`` 可能 WinError 5；短暂退避重试。"""
    delay = 0.04
    last_exc: OSError | None = None
    for i in range(attempts):
        try:
            os.replace(src, dst)
            return
        except OSError as e:
            last_exc = e
            winerr = getattr(e, "winerror", None)
            if winerr == 5 or e.errno in (13, 11):  # 拒绝访问 / EAGAIN
                time.sleep(min(0.35, delay * (i + 1)))
                continue
            raise
    if last_exc is not None:
        raise last_exc


def _overwrite_dst_from_tmp(tmp: Path, dst: Path, *, text: str, attempts: int = 10) -> None:
    """
    ``os.replace`` 在 Win32 上偶发 WinError 5（目标被其它进程以不兼容的共享方式打开）时，
    退化为对目标路径就地写入（仍非完美，但常比 replace 更易成功）；成功后删除临时文件。
    """
    delay = 0.04
    last_exc: OSError | None = None
    for i in range(attempts):
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            with open(dst, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            tmp.unlink(missing_ok=True)
            return
        except OSError as e:
            last_exc = e
            winerr = getattr(e, "winerror", None)
            if winerr == 5 or e.errno in (13, 11):
                time.sleep(min(0.45, delay * (i + 1)))
                continue
            raise
    if last_exc is not None:
        raise last_exc


def write_hud_state_file(coordinator) -> None:
    """原子写入主目录下的 HUD 快照；与 coordinator 上的 _hud_file_lock 配合避免并发写同一 tmp。"""
    lock = getattr(coordinator, "_hud_file_lock", None)
    ctx = lock if lock is not None else nullcontext()
    with ctx:
        try:
            payload = build_hud_payload_dict(coordinator)
            out = Path(hud_scheduler_state_path())
            out.parent.mkdir(parents=True, exist_ok=True)
            data = json.dumps(payload, ensure_ascii=False, indent=2)
            fd, tname = tempfile.mkstemp(
                dir=str(out.parent), prefix=".hud_", suffix=".json.tmp"
            )
            tpath = Path(tname)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(data)
                try:
                    _replace_with_retries(tpath, out)
                except OSError:
                    _overwrite_dst_from_tmp(tpath, out, text=data)
            except Exception:
                tpath.unlink(missing_ok=True)
                raise
        except Exception as e:
            logger.debug("write_hud_state_file: %s", e)


def load_config_json_fresh() -> dict[str, Any]:
    p = Path(config.config_file)
    if not p.is_file():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def read_hud_state_from_disk() -> dict[str, Any] | None:
    p = Path(hud_scheduler_state_path())
    if not p.is_file():
        return None
    delay = 0.04
    for i in range(12):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.debug("read_hud_state_from_disk: %s", e)
            return None
        except OSError as e:
            winerr = getattr(e, "winerror", None)
            if winerr == 5 or e.errno in (13, 11):
                time.sleep(delay * (i + 1))
                continue
            logger.debug("read_hud_state_from_disk: %s", e)
            return None
    return None


def is_hud_state_fresh(payload: dict[str, Any] | None, max_age: float = HUD_STATE_STALE_SEC) -> bool:
    if not payload or "updated_at" not in payload:
        return False
    try:
        ts = float(payload["updated_at"])
    except (TypeError, ValueError):
        return False
    return (time.time() - ts) <= max_age
