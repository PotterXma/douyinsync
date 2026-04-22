import requests
import datetime
from urllib.parse import quote
from modules.logger import logger
from modules.config_manager import config

class BarkNotifier:
    def __init__(self):
        self._daily_upload_count: int = 0
        self._summary_date: str = datetime.date.today().isoformat()
        self._log_init_status()

    def _log_init_status(self):
        """Logs whether Bark is configured, without caching the values."""
        server = str(config.get("bark_server", "")).strip('/')
        key = str(config.get("bark_key", "")).strip()
        bark_url = str(config.get("bark_url", "")).strip('/')
        
        if (server and key) or (bark_url and bark_url.startswith("http")):
            logger.info("BarkNotifier: Initialized successfully. Server: %s", server or bark_url)
        else:
            logger.warning("BarkNotifier: Disabled — missing bark_server/bark_key in config.json")

    def _get_bark_url(self) -> str:
        """Dynamically reads bark connection URL from config (supports hot-reload)."""
        server = str(config.get("bark_server", "")).strip('/')
        key = str(config.get("bark_key", "")).strip()
        if server and key:
            return f"{server}/{key}"
        # Fallback: try legacy bark_url field
        bark_url = str(config.get("bark_url", "")).strip('/')
        if bark_url and bark_url.startswith("http"):
            return bark_url
        return ""

    def push(self, title: str, message: str, level: str = "active"):
        """
        Sends an immediate push payload to iOS mapped devices.
        Level: 'active' (default ringing), 'timeSensitive' (critical bypass), 'passive' (silent collection)
        Config is read fresh each call to support hot-reload.
        """
        bark_url = self._get_bark_url()
        if not bark_url:
            return

        logger.info("BarkNotifier: Emitting Mobile Broadcast [%s]", title)
        try:
            safe_title = quote(title, safe='')
            safe_msg = quote(message, safe='')
            
            # API Pattern: https://api.day.app/key/title/content
            sound = str(config.get("bark_sound", "minuet")).strip()
            dispatch_url = f"{bark_url}/{safe_title}/{safe_msg}?level={level}&sound={sound}"
            
            # 15 second timeout to prevent blocking thread execution
            resp = requests.get(dispatch_url, timeout=15.0)
            if resp.status_code == 200:
                logger.debug("BarkNotifier: Push delivered successfully.")
            else:
                logger.warning("BarkNotifier: Server returned status %s", resp.status_code)
            
        except Exception as e:
            logger.warning("BarkNotifier: Failed bridging notification payload remotely -> %s", e)

    def _check_and_reset_daily_counter(self) -> None:
        """Resets the daily upload counter if the calendar date has changed."""
        today = datetime.date.today().isoformat()
        if today != self._summary_date:
            self._daily_upload_count = 0
            self._summary_date = today

    def record_upload_success(self) -> None:
        """Increments the in-memory daily upload counter. Call once per successful upload."""
        self._check_and_reset_daily_counter()
        self._daily_upload_count += 1

    def push_daily_summary(self) -> None:
        """
        Sends a passive daily summary push with the current accumulated upload count.
        Uses level='passive' (silent delivery) to avoid notification fatigue.
        No-op if counter is zero.
        """
        self._check_and_reset_daily_counter()
        count = self._daily_upload_count
        if count == 0:
            return
        self.push(
            "DouyinSync Daily Summary",
            "%s video(s) uploaded today" % count,
            level="passive"
        )
