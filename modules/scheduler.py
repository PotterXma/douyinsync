import time
import threading
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from modules.logger import logger
from modules.config_manager import config
from modules.database import VideoDAO
from modules.douyin_fetcher import DouyinFetcher
from modules.downloader import Downloader
from modules.youtube_uploader import YouTubeUploader
from modules.sweeper import DiskSweeper
from modules.notifier import BarkNotifier

class PipelineCoordinator:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.fetcher = DouyinFetcher()
        self.downloader = Downloader()
        self.uploader = YouTubeUploader()
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
            logger.warning(f"PipelineCoordinator: Pre-flight network probe isolated environment -> {e}")
            return False

    def recover_zombies(self):
        """Epic 4.4 Self-Healing."""
        logger.info("PipelineCoordinator: Executing Self-Healing Zombie Reverter sequence...")
        reverted = VideoDAO.revert_zombies()
        if reverted > 0:
            logger.warning(f"PipelineCoordinator: Successfully rescued {reverted} stranded zombie tasks from previous unexpected halt.")

    def primary_sync_job(self):
        """The master scheduled task bridging and governing all Epics."""
        if not self._pipeline_lock.acquire(blocking=False):
            logger.warning("PipelineCoordinator: Pipeline already running. Skipping duplicate invocation.")
            return
        
        try:
            self._run_sync_cycle()
        finally:
            self._pipeline_lock.release()

    def _run_sync_cycle(self):
        """Internal sync cycle, always called under lock."""
        logger.info("PipelineCoordinator: === Initiating Scheduled Primary Sync Cycle ===")
        
        if not self.check_network():
            logger.warning("PipelineCoordinator: Offline state detected. Aborting this sync cycle safely.")
            return
            
        if not self.sweeper.check_preflight_space():
            self.notifier.push("Storage Critical", "DouyinSync task blocked safely. Hard Drive has <2GB remaining.", "timeSensitive")
            return

        is_youtube_blocked = time.time() < self.youtube_quota_exceeded_until
        if is_youtube_blocked:
             logger.warning("PipelineCoordinator: CIRCUIT BREAKER ACTIVE. YouTube APIs are suspended until the next 24h cycle resets. (Douyin scraping will continue mapping natively.)")

        try:
            # Phase 1. Fetcher Subroutine - with pagination support
            douyin_accounts = config.get("douyin_accounts", [])
            for account in douyin_accounts:
                if isinstance(account, dict):
                    if not account.get("enable", True):
                        logger.debug(f"PipelineCoordinator: Skipping disabled account [{account.get('mark', '?')}]")
                        continue
                    account_url = account.get("url", "")
                    account_mark = account.get("mark", "")
                else:
                    account_url = str(account)
                    account_mark = account_url
                
                if not account_url:
                    continue
                
                # Pagination loop: keep fetching until we find at least 1 new pending video
                max_cursor = 0
                max_pages = config.get("max_scroll_pages", 5)
                found_new = False
                
                for page in range(max_pages):
                    posts, next_cursor, has_more = self.fetcher.fetch_user_posts(account_url, max_cursor=max_cursor)
                    
                    # Phase 2. Database Deduplication Filter
                    for post in posts:
                        post['account_mark'] = account_mark
                        is_new = VideoDAO.insert_video_if_unique(post)
                        if is_new:
                            logger.info(f"PipelineCoordinator: Tracked new video discovery mapping [{post['douyin_id']}]")
                            found_new = True
                    
                    # Check if we now have pending videos
                    pending_check = VideoDAO.get_pending_videos(limit=1)
                    if pending_check:
                        logger.info(f"PipelineCoordinator: Found pending videos after page {page + 1}. Stopping pagination.")
                        break
                    
                    # If no more pages available, stop
                    if not has_more or next_cursor == 0:
                        logger.info(f"PipelineCoordinator: Reached end of video list for account [{account_mark}] after {page + 1} pages.")
                        break
                    
                    max_cursor = next_cursor
                    logger.info(f"PipelineCoordinator: All videos on page {page + 1} already processed. Scrolling to next page (cursor={max_cursor})...")

            # Phase 3. Downloader & Uploader Sync — STRICT: only 1 video per cycle
            daily_limit = config.get("daily_upload_limit", 1)
            uploaded_today = VideoDAO.get_uploaded_today_count()
            
            if uploaded_today >= daily_limit:
                logger.info(f"PipelineCoordinator: Daily upload limit reached ({uploaded_today}/{daily_limit}). Upload paused until tomorrow.")
                pending_videos = []
            else:
                # STRICT: always limit to 1 video per cycle
                pending_videos = VideoDAO.get_pending_videos(limit=1)
                
            if pending_videos:
                logger.info(f"PipelineCoordinator: Processing 1 video this cycle (strict single-video mode).")
            
            for video in pending_videos:
                dy_id = video['douyin_id']
                title_short = (video['title'] or dy_id)[:50]
                VideoDAO.update_status(dy_id, 'processing')
                
                # Phase 3A: Download
                paths = self.downloader.download_media(dy_id, video['video_url'], video['cover_url'])
                if not paths:
                    VideoDAO.update_status(dy_id, 'failed')
                    self.notifier.push("下载失败", f"视频 [{title_short}] 下载失败", "timeSensitive")
                    continue
                
                self.notifier.push("下载完成", f"视频 [{title_short}] 已保存到本地", "active")
                    
                # Phase 3A-Post: Store local mapping paths and lock downloaded
                VideoDAO.update_status(dy_id, 'downloaded', {
                    'local_video_path': paths['local_video_path'],
                    'local_cover_path': paths['local_cover_path']
                })

                # Epic 4.3 Check Quota circuit
                if is_youtube_blocked:
                     continue # Hold it locked in downloaded state securely
                     
                # Phase 3B: Upload
                VideoDAO.update_status(dy_id, 'uploading')
                
                ocr_text = paths.get('ocr_text', '')
                base_title = video['title'] or dy_id
                
                # Prepend the OCR text dynamically to the YouTube title, max 90 chars total to be safe
                if ocr_text:
                    enhanced_title = f"{ocr_text} | {base_title}"[:90]
                    enhanced_desc = f"{video['description']}\n\n[OCR Data: {ocr_text}]"
                else:
                    enhanced_title = base_title[:90]
                    enhanced_desc = video['description']
                    
                yt_id = self.uploader.upload_video_sequence(
                    dy_id, paths['local_video_path'], paths['local_cover_path'], enhanced_title, enhanced_desc
                )
                
                if yt_id == "QUOTA_EXCEEDED":
                    logger.critical("PipelineCoordinator: Engaged Hard Circuit Breaker (24h block) for YouTube Quota Limits!")
                    self.notifier.push("Quota Exceeded", "YouTube API daily limitation reached. Circuit Breaker locked for 24h.", "timeSensitive")
                    self.youtube_quota_exceeded_until = time.time() + 86400
                    VideoDAO.update_status(dy_id, 'downloaded') # Revert the 'uploading' lock
                    continue
                
                if yt_id:
                    # Successfully completely mapped
                    VideoDAO.update_status(dy_id, 'uploaded')
                    self.notifier.push("上传成功", f"视频 [{title_short}] 已成功上传YouTube!", "active")
                else:
                    VideoDAO.update_status(dy_id, 'failed')
                    self.notifier.push("上传失败", f"视频 [{title_short}] 上传YouTube失败", "timeSensitive")

        except Exception as e:
            logger.error(f"PipelineCoordinator: Unhandled Exception in main sync loop engine: {e}. Auto-Recovering for next cycle.")
            self.notifier.push("系统异常", f"Pipeline 异常: {str(e)[:100]}", "timeSensitive")

        logger.info("PipelineCoordinator: === Pipeline Cycle Terminated ===")

    def janitor_job(self):
        """Scheduled routine for Epic 5.3 deleting stale media traces."""
        self.sweeper.purge_stale_media(max_age_days=7)

    def start(self):
        """Mounts background logical dependencies cleanly."""
        self.recover_zombies()
        
        # Dynamic config interval loading
        interval = config.get("sync_interval_minutes", 60)
        self.scheduler.add_job(
            self.primary_sync_job, 
            IntervalTrigger(minutes=interval), 
            id='primary_sync',
            max_instances=1 # Prevents overlapping parallel jobs if one block processes videos too long
        )
        
        # Fire Janitor logic sweeping orphaned mp4s daily independently
        self.scheduler.add_job(self.janitor_job, IntervalTrigger(hours=24), id='janitor_sync')
        
        self.scheduler.start()
        
        # Fire once immediately for immediate bootstrapping feedback
        import datetime
        self.scheduler.add_job(self.primary_sync_job, 'date', run_date=datetime.datetime.now() + datetime.timedelta(seconds=5))
        logger.info(f"PipelineCoordinator: Background APScheduler engaged natively. Rhythm: {interval} minutes.")

    def shutdown(self):
        logger.info("PipelineCoordinator: Received shutdown broadcast. Emptying queues gracefully...")
        self.scheduler.shutdown(wait=False)
