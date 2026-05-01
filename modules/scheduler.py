import time
import threading
import re
import requests
import asyncio
from typing import Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from modules.logger import logger
from modules.config_manager import config
from modules.database import VideoDAO
from modules.douyin_fetcher import DouyinFetcher
from modules.downloader import Downloader
from modules.youtube_uploader import YoutubeUploader
from modules.sweeper import DiskSweeper
from modules.notifier import BarkNotifier
from utils.models import VideoRecord, ProxyConfig, YoutubeUploadInterrupted
from utils.scheduler_hud import write_hud_state_file

# Bark：铃音/有声推送使用 active（与 config 中 bark_sound 一起）；时间敏感/放弃用 timeSensitive
_BARK_OK = "active"
_BARK_ERR = "active"


def _bark_snip(s: str, n: int = 160) -> str:
    t = (s or "").strip()
    if len(t) <= n:
        return t
    return t[: n - 1] + "…"


def _bark_video_caption(video) -> str:
    dy = getattr(video, "douyin_id", "") or ""
    ti = (getattr(video, "title", None) or "").strip()
    if ti:
        return f"{dy}\n{_bark_snip(ti, 100)}"
    return dy or "—"


def _upload_error_summary(exc: BaseException) -> str:
    s = (str(exc) or type(exc).__name__).strip().replace("\n", " ")
    s = re.sub(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*", "Bearer ***", s)
    if len(s) > 400:
        s = s[:397] + "..."
    return s


def _begin_upload_tracking(dy_id: str, local_video_path: Optional[str]) -> None:
    import os

    total = None
    if local_video_path and os.path.isfile(local_video_path):
        total = os.path.getsize(local_video_path)
    VideoDAO.update_status(
        dy_id,
        "uploading",
        {
            "upload_bytes_done": 0,
            "upload_bytes_total": total,
            "last_error_summary": None,
        },
    )


def _finish_upload_success(dy_id: str, yt_id: str) -> None:
    VideoDAO.update_status(
        dy_id,
        "uploaded",
        {
            "youtube_video_id": yt_id,
            "upload_bytes_done": 0,
            "upload_bytes_total": None,
            "last_error_summary": None,
        },
    )


def _upload_failure_extras(retry: int, *, summary: Optional[str] = None) -> dict:
    d = {
        "retry_count": retry,
        "upload_bytes_done": 0,
        "upload_bytes_total": None,
    }
    if summary:
        d["last_error_summary"] = summary
    return d


def _downloaded_after_interrupt_extras(retry_count: int) -> dict:
    return {
        "retry_count": retry_count,
        "upload_bytes_done": 0,
        "upload_bytes_total": None,
    }


def _quota_revert_downloaded() -> dict:
    return {"upload_bytes_done": 0, "upload_bytes_total": None}


def _normalize_schedule_mode(raw: object) -> str:
    m = str(raw or "interval").lower().strip()
    if m in ("clock", "cron", "fixed_times", "fixed", "time", "daily"):
        return "clock"
    return "interval"


def parse_clock_times_from_config() -> list[tuple[int, int]]:
    """Build local-time (hour, minute) slots from ``sync_clock_times`` or legacy ``cron_hour`` / ``cron_minute``."""
    out: list[tuple[int, int]] = []
    raw_times = config.get("sync_clock_times", None)
    if isinstance(raw_times, list):
        for t in raw_times:
            if not isinstance(t, str) or ":" not in t:
                continue
            parts = t.strip().split(":", 1)
            try:
                h = int(parts[0].strip())
                m = int(parts[1].strip())
            except ValueError:
                continue
            if 0 <= h <= 23 and 0 <= m <= 59:
                out.append((h, m))
    if out:
        return out
    try:
        h = int(config.get("cron_hour", 2))
        m = int(config.get("cron_minute", 0))
    except (TypeError, ValueError):
        return []
    if 0 <= h <= 23 and 0 <= m <= 59:
        return [(h, m)]
    return []


class PipelineCoordinator:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.fetcher = DouyinFetcher()
        self.downloader = Downloader()
        self.sweeper = DiskSweeper()
        self.notifier = BarkNotifier()
        
        # Epic 4.3: YouTube Quota Global Circuit Breaker (timestamp mapping locking APIs until passed)
        self.youtube_quota_exceeded_until = 0
        
        # Mutex lock preventing concurrent pipeline runs
        self._pipeline_lock = threading.Lock()
        # HUD 快照写盘由调度线程/主管道并发触发，与 utils.scheduler_hud.write_hud_state_file 成对使用
        self._hud_file_lock = threading.Lock()
        self._primary_pipeline_active = False
        self._hud_persist_stop = threading.Event()
        self._hud_persist_thread: threading.Thread | None = None

    def recover_zombies(self):
        """Epic 4.4 Self-Healing."""
        logger.info("PipelineCoordinator: Executing Self-Healing Zombie Reverter sequence...")
        reverted = VideoDAO.revert_zombies()
        if reverted > 0:
            logger.warning("PipelineCoordinator: Successfully rescued %s stranded zombie tasks from previous unexpected halt.", reverted)

    def primary_sync_job(self, force_retry_bypass: bool = False):
        """The master scheduled task bridging and governing all Epics."""
        if not self._pipeline_lock.acquire(blocking=False):
            logger.warning("PipelineCoordinator: Pipeline already running. Skipping duplicate invocation.")
            return

        self._primary_pipeline_active = True
        write_hud_state_file(self)
        try:
            asyncio.run(self._run_async_cycle(force_retry_bypass))
        finally:
            self._primary_pipeline_active = False
            self._pipeline_lock.release()
            write_hud_state_file(self)

    async def _run_async_cycle(self, force_retry_bypass: bool = False):
        """Internal sync cycle, executed asynchronously."""
        logger.info("PipelineCoordinator: === Initiating Scheduled Primary Sync Cycle ===")
        if force_retry_bypass:
            n = VideoDAO.prepare_for_force_manual_retry()
            logger.info(
                "PipelineCoordinator: Force manual retry — normalized %s DB row(s); this cycle ignores give_up caps.",
                n,
            )
        
        # Hot-reload configurations
        config.reload()

        from utils.network import preflight_network_check
        if not await preflight_network_check():
            logger.warning("PipelineCoordinator: Offline state detected. Aborting this sync cycle safely.")
            return
            
        if not self.sweeper.check_preflight_space():
            await asyncio.to_thread(
                self.notifier.push, "Storage Critical", "DouyinSync task blocked safely. Hard Drive has <2GB remaining.", level="timeSensitive"
            )
            return

        is_youtube_blocked = time.time() < self.youtube_quota_exceeded_until
        if is_youtube_blocked:
             logger.warning("PipelineCoordinator: CIRCUIT BREAKER ACTIVE. YouTube APIs are suspended until the next 24h cycle resets.")

        # Story 1.5 - Setup YouTube parameters and proxy securely
        yt_token = str(config.get("youtube_api_token", "") or "").strip()
        yt_proxy = str(config.get("youtube_proxy", ""))
        token_file = str(config.get("youtube_token_file", "youtube_token.json") or "youtube_token.json")
        client_secret = str(
            config.get("youtube_client_secret_file", "client_secret.json") or "client_secret.json"
        )
        proxy_config = ProxyConfig(http=yt_proxy, https=yt_proxy) if yt_proxy else None

        # Isolated network client (token may be filled from youtube_token.json inside YoutubeUploader)
        uploader = YoutubeUploader(
            client_secrets_file=client_secret,
            token=yt_token or None,
            proxy_config=proxy_config,
            token_file=token_file,
        )

        # Auto OAuth bootstrap: if no access token provided and no cached youtube_token.json,
        # trigger one-time OAuth flow to generate/refresh youtube_token.json.
        # This avoids requiring a dedicated tray/menu "Authorize" entry.
        if not uploader.token or not str(uploader.token).strip():
            try:
                ok = await asyncio.to_thread(uploader.authenticate)
            except Exception as e:
                ok = False
                logger.error("PipelineCoordinator: YouTube OAuth flow failed: %s", e)
            if not ok or not uploader.token or not str(uploader.token).strip():
                logger.error(
                    "PipelineCoordinator: YouTube OAuth token missing. Ensure %s exists and complete browser authorization.",
                    client_secret,
                )
                return

        try:
            # Phase 1. Fetcher Subroutine
            douyin_accounts = config.get("douyin_accounts", [])
            for account in douyin_accounts:
                if isinstance(account, dict):
                    if not account.get("enable", True):
                        continue
                    account_url = account.get("url", "")
                    account_mark = account.get("mark", "")
                else:
                    account_url = str(account)
                    account_mark = account_url
                
                if not account_url:
                    continue
                
                max_cursor = 0
                max_pages = config.get("max_scroll_pages", 5)
                
                for page in range(max_pages):
                    try:
                        posts, next_cursor, has_more = await self.fetcher.fetch_user_posts(account_url, max_cursor)
                    except Exception as e:
                        logger.error("PipelineCoordinator: Fetcher failed for account [%s]: %s", account_url, e)
                        break
                    
                    # Phase 2. Database Deduplication Filter
                    for post in posts:
                        # Augment the already-typed VideoRecord with account context
                        post.account_mark = account_mark
                        
                        is_new = VideoDAO.insert_video_if_unique(post)
                        if is_new:
                            logger.info("PipelineCoordinator: Tracked new video discovery mapping [%s]", post.douyin_id)
                    
                    pending_check = VideoDAO.get_pending_videos(limit=1)
                    if pending_check:
                        break
                    
                    if not has_more or next_cursor == 0:
                        break
                    
                    max_cursor = next_cursor

            # Phase 3. Downloader & Uploader Sync
            daily_limit = config.get("daily_upload_limit", 1)
            uploaded_today = VideoDAO.get_uploaded_today_count()
            
            if uploaded_today >= daily_limit:
                logger.warning(
                    "PipelineCoordinator: Daily upload limit reached (%s/%s uploads today); "
                    "skipping download/upload — pending queue will not advance until tomorrow or you raise daily_upload_limit.",
                    uploaded_today,
                    daily_limit,
                )
            else:
                max_per_cycle = config.get("max_videos_per_run", 1)
                slots_left = min(daily_limit - uploaded_today, max_per_cycle)
                
                # Phase 3-Pre: Re-upload videos
                if not is_youtube_blocked:
                    uploadable = VideoDAO.get_uploadable_videos(
                        limit=slots_left, ignore_retry_cap=force_retry_bypass
                    )
                    for video in uploadable:
                        if slots_left <= 0: break
                        dy_id = video.douyin_id
                        local_video = video.local_video_path
                        
                        from pathlib import Path
                        if not local_video or not Path(local_video).exists():
                            logger.warning("PipelineCoordinator: Local video missing for [%s], skipping re-upload.", dy_id)
                            VideoDAO.update_status(dy_id, 'pending')
                            continue
                        
                        logger.info("PipelineCoordinator: Re-uploading previously downloaded video [%s]", dy_id)
                        _begin_upload_tracking(dy_id, local_video)
                        
                        try:
                            # Non-blocking async upload
                            yt_id = await uploader.upload(video)
                            if yt_id:
                                _finish_upload_success(dy_id, yt_id)
                                self.notifier.record_upload_success()  # AC2: daily counter
                                await asyncio.to_thread(
                                    self.notifier.push,
                                    "DouyinSync 上传成功",
                                    f"{_bark_video_caption(video)}\nYouTube ID: {yt_id}",
                                    _BARK_OK,
                                )
                                slots_left -= 1
                                logger.info(
                                    "PipelineCoordinator: Re-upload succeeded for [%s] → YouTube video id %s",
                                    dy_id,
                                    yt_id,
                                )
                            else:
                                retry = video.retry_count + 1
                                exhausted = retry >= 3 and not force_retry_bypass
                                new_status = 'give_up' if exhausted else 'failed'
                                VideoDAO.update_status(
                                    dy_id,
                                    new_status,
                                    _upload_failure_extras(retry, summary="Empty YouTube video id"),
                                )
                                if new_status == 'give_up':
                                    logger.error(
                                        "PipelineCoordinator: Re-upload give_up [%s] after empty YouTube id (retry=%s). No further auto upload.",
                                        dy_id,
                                        retry,
                                    )
                                    await asyncio.to_thread(
                                        self.notifier.push,  # AC3: immediate critical alert
                                        "DouyinSync: Upload Give Up",
                                        "Video [%s] failed 3 times and was abandoned" % dy_id,
                                        level="timeSensitive"
                                    )
                                else:
                                    await asyncio.to_thread(
                                        self.notifier.push,
                                        "DouyinSync 上传无视频ID",
                                        f"{_bark_video_caption(video)}\n将重试 {retry}/3 (failed)",
                                        _BARK_ERR,
                                    )
                                    logger.warning(
                                        "PipelineCoordinator: Re-upload empty YouTube id [%s] → status=failed retry=%s/3. "
                                        "Will retry upload on a later sync (get_uploadable_videos).",
                                        dy_id,
                                        retry,
                                    )
                        except YoutubeUploadInterrupted as e:
                            logger.warning("PipelineCoordinator: Re-upload skipped — %s (status left as downloaded).", e)
                            VideoDAO.update_status(
                                dy_id, "downloaded", _downloaded_after_interrupt_extras(video.retry_count)
                            )
                        except Exception as e:
                            logger.error("Youtube upload error for [%s]: %s", dy_id, e, exc_info=True)
                            if type(e).__name__ in ["YoutubeQuotaError", "QuotaExceededError"]:
                                logger.critical("PipelineCoordinator: Engaged Hard Circuit Breaker (24h block) for YouTube Quota!")
                                self.youtube_quota_exceeded_until = time.time() + 86400
                                VideoDAO.update_status(dy_id, 'downloaded', _quota_revert_downloaded())
                                await asyncio.to_thread(
                                    self.notifier.push,  # AC3: quota exhaustion alert
                                    "DouyinSync: YouTube Quota Exhausted",
                                    "API quota exceeded for account [%s]. Suspended 24h." % video.account_mark,
                                    level="timeSensitive"
                                )
                                break
                            new_rc = video.retry_count + 1
                            VideoDAO.update_status(
                                dy_id,
                                'failed',
                                _upload_failure_extras(new_rc, summary=_upload_error_summary(e)),
                            )
                            await asyncio.to_thread(
                                self.notifier.push,
                                "DouyinSync 上传异常",
                                f"{_bark_video_caption(video)}\n重试 {new_rc}/3\n{_bark_snip(str(e), 140)}",
                                _BARK_ERR,
                            )
                            logger.warning(
                                "PipelineCoordinator: Re-upload exception [%s] → status=failed retry=%s/3. "
                                "Will retry on a later sync if local file still exists. Error: %s",
                                dy_id,
                                new_rc,
                                e,
                            )
                
                # Phase 3-Main: Download + Upload new
                if slots_left > 0:
                    pending_videos = VideoDAO.get_pending_videos(limit=slots_left)
                else:
                    pending_videos = []
                
                for video in pending_videos:
                    dy_id = video.douyin_id
                    VideoDAO.update_status(dy_id, 'processing')
                    
                    video_url = video.video_url
                    cover_url = video.cover_url
                    try:
                        fresh = await self.fetcher.refresh_video_url(dy_id, douyin_accounts)
                        if fresh:
                            video_url = fresh.get('video_url', video_url)
                            cover_url = fresh.get('cover_url', cover_url)
                            VideoDAO.update_fresh_urls(dy_id, video_url, cover_url)
                    except Exception as e:
                        logger.warning("PipelineCoordinator: URL refresh failed for [%s]: %s", dy_id, e)
                    
                    try:
                        paths = await self.downloader.download_media(dy_id, video_url, cover_url)
                        if not paths:
                            retry = video.retry_count + 1
                            if retry >= 3 and not force_retry_bypass:
                                VideoDAO.update_status(
                                    dy_id,
                                    "give_up",
                                    {"retry_count": retry, "local_video_path": None, "local_cover_path": None},
                                )
                                await asyncio.to_thread(
                                    self.notifier.push,
                                    "DouyinSync: Download Give Up",
                                    "Video [%s] failed to download after 3 attempts." % dy_id,
                                    level="timeSensitive",
                                )
                                logger.error(
                                    "PipelineCoordinator: Download give_up [%s] after 3 failed attempts (empty result).",
                                    dy_id,
                                )
                            else:
                                VideoDAO.update_status(
                                    dy_id,
                                    "pending",
                                    {
                                        "retry_count": retry,
                                        "local_video_path": None,
                                        "local_cover_path": None,
                                    },
                                )
                                await asyncio.to_thread(
                                    self.notifier.push,
                                    "DouyinSync 下载未成功",
                                    f"{_bark_video_caption(video)}\n无媒体，将重试 {retry}/3。",
                                    _BARK_ERR,
                                )
                                logger.warning(
                                    "PipelineCoordinator: Download failed for [%s]; queued retry %s%s.",
                                    dy_id,
                                    retry,
                                    " (force bypass: stays pending)" if force_retry_bypass and retry >= 3 else "/3",
                                )
                            continue
                    except Exception as e:
                        logger.error("PipelineCoordinator: Downloader Exception for [%s]: %s", dy_id, e)
                        retry = video.retry_count + 1
                        if retry >= 3 and not force_retry_bypass:
                            VideoDAO.update_status(
                                dy_id,
                                "give_up",
                                {"retry_count": retry, "local_video_path": None, "local_cover_path": None},
                            )
                            await asyncio.to_thread(
                                self.notifier.push,
                                "DouyinSync: Download Give Up",
                                "Video [%s] raised after 3 attempts: %s" % (dy_id, e),
                                level="timeSensitive",
                            )
                            logger.error(
                                "PipelineCoordinator: Download give_up [%s] after 3 exceptions: %s",
                                dy_id,
                                e,
                            )
                        else:
                            VideoDAO.update_status(
                                dy_id,
                                "pending",
                                {
                                    "retry_count": retry,
                                    "local_video_path": None,
                                    "local_cover_path": None,
                                },
                            )
                            await asyncio.to_thread(
                                self.notifier.push,
                                "DouyinSync 下载异常",
                                f"{_bark_video_caption(video)}\n重试 {retry}/3\n{_bark_snip(str(e), 150)}",
                                _BARK_ERR,
                            )
                            logger.warning(
                                "PipelineCoordinator: Download exception [%s]; queued retry %s → pending. Error: %s",
                                dy_id,
                                retry,
                                e,
                            )
                        continue
                    
                    video.local_video_path = paths['local_video_path']
                    video.local_cover_path = paths['local_cover_path']
                    
                    VideoDAO.update_status(dy_id, 'downloaded', {
                        'local_video_path': video.local_video_path,
                        'local_cover_path': video.local_cover_path,
                        'retry_count': 0,
                    })
                    video.retry_count = 0

                    await asyncio.to_thread(
                        self.notifier.push,
                        "DouyinSync 下载完成",
                        f"{_bark_video_caption(video)}\nMP4/封面 已落盘。",
                        _BARK_OK,
                    )

                    if is_youtube_blocked:
                         continue
                         
                    _begin_upload_tracking(dy_id, video.local_video_path)
                    
                    try:
                        # Async network upload natively via httpx
                        yt_id = await uploader.upload(video)
                        if yt_id:
                            _finish_upload_success(dy_id, yt_id)
                            self.notifier.record_upload_success()  # AC2: daily counter
                            await asyncio.to_thread(
                                self.notifier.push,
                                "DouyinSync 上传成功",
                                f"{_bark_video_caption(video)}\nYouTube ID: {yt_id}",
                                _BARK_OK,
                            )
                            slots_left -= 1
                            logger.info(
                                "PipelineCoordinator: First-pass upload succeeded for [%s] → YouTube video id %s",
                                dy_id,
                                yt_id,
                            )
                            if slots_left <= 0: break
                        else:
                            retry = video.retry_count + 1
                            exhausted = retry >= 3 and not force_retry_bypass
                            new_status = 'give_up' if exhausted else 'failed'
                            VideoDAO.update_status(
                                dy_id,
                                new_status,
                                _upload_failure_extras(retry, summary="Empty YouTube video id"),
                            )
                            if new_status == 'give_up':
                                logger.error(
                                    "PipelineCoordinator: First-pass upload give_up [%s] — empty YouTube id after retry=%s.",
                                    dy_id,
                                    retry,
                                )
                                await asyncio.to_thread(
                                    self.notifier.push,
                                    "DouyinSync: Upload Give Up",
                                    "Video [%s] returned empty YouTube id after 3 attempts." % dy_id,
                                    level="timeSensitive",
                                )
                            else:
                                await asyncio.to_thread(
                                    self.notifier.push,
                                    "DouyinSync 上传无视频ID",
                                    f"{_bark_video_caption(video)}\n重试 {retry}/3 (failed，稍后重传)",
                                    _BARK_ERR,
                                )
                                logger.warning(
                                    "PipelineCoordinator: First-pass upload empty YouTube id [%s] → status=failed retry=%s/3. "
                                    "Later sync will re-attempt via Phase 3-Pre (get_uploadable_videos).",
                                    dy_id,
                                    retry,
                                )
                    except YoutubeUploadInterrupted as e:
                        logger.warning(
                            "PipelineCoordinator: First-pass upload skipped — %s (status left as downloaded, no failed retry).",
                            e,
                        )
                        VideoDAO.update_status(
                            dy_id, "downloaded", _downloaded_after_interrupt_extras(video.retry_count)
                        )
                    except Exception as e:
                        logger.error("Youtube upload exception: %s", e, exc_info=True)
                        if type(e).__name__ == "YoutubeQuotaError":
                            logger.critical("Circuit Breaker Quota engaged!")
                            self.youtube_quota_exceeded_until = time.time() + 86400
                            VideoDAO.update_status(dy_id, 'downloaded', _quota_revert_downloaded())
                            await asyncio.to_thread(
                                self.notifier.push,  # AC3: quota critical alert
                                "DouyinSync: YouTube Quota Exhausted",
                                "API quota limit hit. Pipeline suspended 24h.",
                                level="timeSensitive"
                            )
                            break
                        retry = video.retry_count + 1
                        exhausted = retry >= 3 and not force_retry_bypass
                        new_status = 'give_up' if exhausted else 'failed'
                        VideoDAO.update_status(
                            dy_id,
                            new_status,
                            _upload_failure_extras(retry, summary=_upload_error_summary(e)),
                        )
                        if new_status == 'give_up':
                            logger.error(
                                "PipelineCoordinator: First-pass upload give_up [%s] after exception (retry=%s): %s",
                                dy_id,
                                retry,
                                e,
                            )
                            await asyncio.to_thread(
                                self.notifier.push,
                                "DouyinSync: Upload Give Up",
                                "Video [%s] failed after 3 upload attempts: %s" % (dy_id, e),
                                level="timeSensitive",
                            )
                        else:
                            await asyncio.to_thread(
                                self.notifier.push,
                                "DouyinSync 上传失败",
                                f"{_bark_video_caption(video)}\n重试 {retry}/3\n{_bark_snip(str(e), 150)}",
                                _BARK_ERR,
                            )
                            logger.warning(
                                "PipelineCoordinator: First-pass upload exception [%s] → status=failed retry=%s. "
                                "Keeps local file; next sync retries via Phase 3-Pre. Error: %s",
                                dy_id,
                                retry,
                                e,
                            )

        except Exception as e:
            logger.error("PipelineCoordinator: Unhandled Exception in main sync loop engine: %s", e)
            try:
                await asyncio.to_thread(
                    self.notifier.push,
                    "DouyinSync 周期异常",
                    f"主同步循环未捕获错误：\n{_bark_snip(str(e), 200)}",
                    _BARK_ERR,
                )
            except Exception:
                pass

        logger.info("PipelineCoordinator: === Pipeline Cycle Terminated ===")

    def janitor_job(self):
        """Scheduled routine for Epic 5.3 deleting stale media traces."""
        try:
            max_age_days = int(float(config.get("storage_retention_days", 7)))
            if max_age_days <= 0:
                raise ValueError("max_age_days must be strictly positive")
        except (ValueError, TypeError):
            logger.warning("PipelineCoordinator: Invalid storage_retention_days config value, defaulting to 7 days.")
            max_age_days = 7
        self.sweeper.purge_stale_media(max_age_days=max_age_days)

    def _add_primary_sync_jobs(self) -> None:
        """Register primary pipeline job(s) from ``sync_schedule_mode`` (interval vs clock)."""
        mode = _normalize_schedule_mode(config.get("sync_schedule_mode", "interval"))
        if mode == "clock":
            times = parse_clock_times_from_config()
            if not times:
                logger.warning(
                    "PipelineCoordinator: sync_schedule_mode=clock but no valid times; "
                    "falling back to interval."
                )
                mode = "interval"
        if mode == "interval":
            interval = config.get("sync_interval_minutes", 60)
            try:
                interval = max(1, int(interval))
            except (TypeError, ValueError):
                interval = 60
            self.scheduler.add_job(
                self.primary_sync_job,
                IntervalTrigger(minutes=interval),
                id="primary_sync",
                max_instances=1,
            )
            logger.info(
                "PipelineCoordinator: Primary sync schedule = interval every %s minute(s).",
                interval,
            )
            return
        for i, (h, m) in enumerate(times):
            jid = "primary_sync_%s_%02d%02d" % (i, h, m)
            self.scheduler.add_job(
                self.primary_sync_job,
                CronTrigger(hour=h, minute=m),
                id=jid,
                max_instances=1,
            )
        logger.info("PipelineCoordinator: Primary sync schedule = clock at local times %s.", times)

    def apply_primary_schedule(self) -> None:
        """Drop all ``primary_sync*`` jobs and re-add from current config (after ``config.reload()``)."""
        try:
            jobs = self.scheduler.get_jobs()
        except Exception:
            return
        for job in jobs:
            jid = getattr(job, "id", "") or ""
            if jid.startswith("primary_sync"):
                try:
                    self.scheduler.remove_job(jid)
                except Exception:
                    pass
        self._add_primary_sync_jobs()
        write_hud_state_file(self)

    def _hud_persist_loop(self) -> None:
        while not self._hud_persist_stop.wait(5.0):
            write_hud_state_file(self)

    def start(self):
        """Mounts background logical dependencies cleanly."""
        self.recover_zombies()

        self._add_primary_sync_jobs()

        self.scheduler.add_job(self.janitor_job, IntervalTrigger(hours=24), id='janitor_sync')
        
        # Epic 3.2: Daily passive Bark summary (sent at 23:50)
        self.scheduler.add_job(self.notifier.push_daily_summary, CronTrigger(hour=23, minute=50), id='daily_summary_push')
        
        self.scheduler.start()

        import datetime

        self.scheduler.add_job(
            self.primary_sync_job,
            "date",
            run_date=datetime.datetime.now() + datetime.timedelta(seconds=5),
            id="primary_sync_bootstrap",
        )
        self._hud_persist_thread = threading.Thread(
            target=self._hud_persist_loop, daemon=True, name="HudStatePersist"
        )
        self._hud_persist_thread.start()
        write_hud_state_file(self)
        mode = _normalize_schedule_mode(config.get("sync_schedule_mode", "interval"))
        if mode == "interval":
            interval = config.get("sync_interval_minutes", 60)
            try:
                interval = max(1, int(interval))
            except (TypeError, ValueError):
                interval = 60
            logger.info("PipelineCoordinator: Background APScheduler engaged. Interval: %s min.", interval)
        else:
            logger.info(
                "PipelineCoordinator: Background APScheduler engaged. Clock: %s.",
                parse_clock_times_from_config(),
            )

    def shutdown(self):
        logger.info("PipelineCoordinator: Received shutdown broadcast. Emptying queues gracefully...")
        self._hud_persist_stop.set()
        t = self._hud_persist_thread
        if t is not None and t.is_alive():
            t.join(timeout=1.0)
        self.scheduler.shutdown(wait=True)
