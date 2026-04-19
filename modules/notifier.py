import requests
from urllib.parse import quote
from modules.logger import logger
from modules.config_manager import config

class BarkNotifier:
    def __init__(self):
        # Format expects standard 'https://api.day.app/YOUR_KEY_HERE'
        self.bark_url = str(config.get("bark_url", "")).strip('/')
        self.enabled = bool(self.bark_url) and self.bark_url.startswith("http")

    def push(self, title: str, message: str, level: str = "active"):
        """
        Sends an immediate push payload to iOS mapped devices.
        Level: 'active' (default ringing), 'timeSensitive' (critical bypass), 'passive' (silent collection)
        """
        if not self.enabled:
            return

        logger.info(f"BarkNotifier: Emitting Mobile Broadcast [{title}]")
        try:
            safe_title = quote(title, safe='')
            safe_msg = quote(message, safe='')
            
            # API Pattern: https://api.day.app/key/title/content
            dispatch_url = f"{self.bark_url}/{safe_title}/{safe_msg}?level={level}"
            
            # 5 second timeout to prevent blocking thread execution
            requests.get(dispatch_url, timeout=5.0)
            
        except Exception as e:
            logger.warning(f"BarkNotifier: Failed bridging notification payload remotely -> {e}")
