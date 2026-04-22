import time
import threading
import requests
import asyncio
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
from utils.models import VideoRecord, ProxyConfig

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

    def check_network(self) -> bool:
        """Epic 4.2 Pre-flight network probe."""
        try:
            # We enforce direct domestic connection testing
            requests.get("https://www.baidu.com", timeout=5)
            return True
        except Exception as e:
            logger.warning("PipelineCoordinator: Pre-flight network probe isolated environment -> %s", e)
            return False

    def recover_zombies(self):
        """Epic 4.4 Self-Healing."""
        logger.info("PipelineCoordinator: Executing Self-Healing Zombie Reverter sequence...")
        reverted = VideoDAO.revert_zombies()
        if reverted > 0:
            logger.warning("PipelineCoordinator: Successfully rescued %s stranded zombie tasks from previous unexpected halt.", reverted)

    def primary_sync_job(self):
        """The master scheduled task bridging and governing all Epics."""
        if not self._pipeline_lock.acquire(blocking=False):
            logger.warning("PipelineCoordinator: Pipeline already running. Skipping duplicate invocation.")
            return
        
        try:
            asyncio.run(self._run_async_cycle())
        finally:
            self._pipeline_lock.release()

    async def _run_async_cycle(self):
        """Internal sync cycle, executed asynchronously."""
        logger.info("PipelineCoordinator: === Initiating Scheduled Primary Sync Cycle ===")
        
        # Hot-reload configurations
        config.reload()

        if not self.check_network():
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
        yt_token = str(config.get("youtube_api_token", ""))
        yt_proxy = str(config.get("youtube_proxy", ""))
        proxy_config = ProxyConfig(http=yt_proxy, https=yt_proxy) if yt_proxy else None
        
        # Isolated network client
        uploader = YoutubeUploader(token=yt_token, proxy_config=proxy_config)

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
                logger.info("PipelineCoordinator: Daily upload limit reached.")
            else:
                max_per_cycle = config.get("max_videos_per_run", 1)
                slots_left = min(daily_limit - uploaded_today, max_per_cycle)
                
                # Phase 3-Pre: Re-upload videos
                if not is_youtube_blocked:
                    uploadable = VideoDAO.get_uploadable_videos(limit=slots_left)
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
                        VideoDAO.update_status(dy_id, 'uploading')
                        
                        try:
                            # Non-blocking async upload
                            yt_id = await uploader.upload(video)
                            if yt_id:
                                VideoDAO.update_status(dy_id, 'uploaded')
                                self.notifier.record_upload_success()  # AC2: daily counter
                                slots_left -= 1
                            else:
                                retry = video.retry_count + 1
                                new_status = 'give_up' if retry >= 3 else 'failed'
                                VideoDAO.update_status(dy_id, new_status, {'retry_count': retry})
                                if new_status == 'give_up':
                                    await asyncio.to_thread(
                                        self.notifier.push,  # AC3: immediate critical alert
                                        "DouyinSync: Upload Give Up",
                                        "Video [%s] failed 3 times and was abandoned" % dy_id,
                                        level="timeSensitive"
                                    )
                        except Exception as e:
                            logger.error("Youtube upload error for [%s]: %s", dy_id, e)
                            if type(e).__name__ in ["YoutubeQuotaError", "QuotaExceededError"]:
                                logger.critical("PipelineCoordinator: Engaged Hard Circuit Breaker (24h block) for YouTube Quota!")
                                self.youtube_quota_exceeded_until = time.time() + 86400
                                VideoDAO.update_status(dy_id, 'downloaded')
                                await asyncio.to_thread(
                                    self.notifier.push,  # AC3: quota exhaustion alert
                                    "DouyinSync: YouTube Quota Exhausted",
                                    "API quota exceeded for account [%s]. Suspended 24h." % video.account_mark,
                                    level="timeSensitive"
                                )
                                break
                            VideoDAO.update_status(dy_id, 'failed', {'retry_count': video.retry_count + 1})
                
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
                            VideoDAO.update_status(dy_id, 'failed')
                            continue
                    except Exception as e:
                        logger.error("PipelineCoordinator: Downloader Exception for [%s]: %s", dy_id, e)
                        VideoDAO.update_status(dy_id, 'failed')
                        continue
                    
                    video.local_video_path = paths['local_video_path']
                    video.local_cover_path = paths['local_cover_path']
                    
                    VideoDAO.update_status(dy_id, 'downloaded', {
                        'local_video_path': video.local_video_path,
                        'local_cover_path': video.local_cover_path
                    })

                    if is_youtube_blocked:
                         continue
                         
                    VideoDAO.update_status(dy_id, 'uploading')
                    
                    try:
                        # Async network upload natively via httpx
                        yt_id = await uploader.upload(video)
                        if yt_id:
                            VideoDAO.update_status(dy_id, 'uploaded')
                            self.notifier.record_upload_success()  # AC2: daily counter
                            slots_left -= 1
                            if slots_left <= 0: break
                        else:
                            VideoDAO.update_status(dy_id, 'failed')
                    except Exception as e:
                        logger.error("Youtube upload exception: %s", e)
                        if type(e).__name__ == "YoutubeQuotaError":
                            logger.critical("Circuit Breaker Quota engaged!")
                            self.youtube_quota_exceeded_until = time.time() + 86400
                            VideoDAO.update_status(dy_id, 'downloaded')
                            await asyncio.to_thread(
                                self.notifier.push,  # AC3: quota critical alert
                                "DouyinSync: YouTube Quota Exhausted",
                                "API quota limit hit. Pipeline suspended 24h.",
                                level="timeSensitive"
                            )
                            break
                        VideoDAO.update_status(dy_id, 'failed')

        except Exception as e:
            logger.error("PipelineCoordinator: Unhandled Exception in main sync loop engine: %s", e)

        logger.info("PipelineCoordinator: === Pipeline Cycle Terminated ===")

    def janitor_job(self):
        """Scheduled routine for Epic 5.3 deleting stale media traces."""
        self.sweeper.purge_stale_media(max_age_days=7)

    def start(self):
        """Mounts background logical dependencies cleanly."""
        self.recover_zombies()
        
        interval = config.get("sync_interval_minutes", 60)
        self.scheduler.add_job(
            self.primary_sync_job, 
            IntervalTrigger(minutes=interval), 
            id='primary_sync',
            max_instances=1
        )
        
        self.scheduler.add_job(self.janitor_job, IntervalTrigger(hours=24), id='janitor_sync')
        
        # Epic 3.2: Daily passive Bark summary (sent at 23:50)
        self.scheduler.add_job(self.notifier.push_daily_summary, CronTrigger(hour=23, minute=50), id='daily_summary_push')
        
        self.scheduler.start()
        
        import datetime
        self.scheduler.add_job(self.primary_sync_job, 'date', run_date=datetime.datetime.now() + datetime.timedelta(seconds=5))
        logger.info("PipelineCoordinator: Background APScheduler engaged natively. Rhythm: %s minutes.", interval)

    def shutdown(self):
        logger.info("PipelineCoordinator: Received shutdown broadcast. Emptying queues gracefully...")
        self.scheduler.shutdown(wait=True)
