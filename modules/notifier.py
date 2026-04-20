import requests
from urllib.parse import quote
from modules.logger import logger
from modules.config_manager import config

class BarkNotifier:
    def __init__(self):
        # Just validate the initial config and log status. 
        # Actual connection params are read at push() time to support hot-reload.
        self._log_init_status()

    def _log_init_status(self):
        """Logs whether Bark is configured, without caching the values."""
        server = str(config.get("bark_server", "")).strip('/')
        key = str(config.get("bark_key", "")).strip()
        bark_url = str(config.get("bark_url", "")).strip('/')
        
        if (server and key) or (bark_url and bark_url.startswith("http")):
            logger.info(f"BarkNotifier: Initialized successfully. Server: {server or bark_url}")
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

        logger.info(f"BarkNotifier: Emitting Mobile Broadcast [{title}]")
        try:
            safe_title = quote(title, safe='')
            safe_msg = quote(message, safe='')
            
            # API Pattern: https://api.day.app/key/title/content
            sound = str(config.get("bark_sound", "minuet")).strip()
            dispatch_url = f"{bark_url}/{safe_title}/{safe_msg}?level={level}&sound={sound}"
            
            # 15 second timeout to prevent blocking thread execution
            resp = requests.get(dispatch_url, timeout=15.0)
            if resp.status_code == 200:
                logger.debug(f"BarkNotifier: Push delivered successfully.")
            else:
                logger.warning(f"BarkNotifier: Server returned status {resp.status_code}")
            
        except Exception as e:
            logger.warning(f"BarkNotifier: Failed bridging notification payload remotely -> {e}")

