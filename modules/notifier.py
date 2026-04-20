import requests
from urllib.parse import quote
from modules.logger import logger
from modules.config_manager import config

class BarkNotifier:
    def __init__(self):
        server = str(config.get("bark_server", "")).strip('/')
        key = str(config.get("bark_key", "")).strip()
        
        if server and key:
            self.bark_url = f"{server}/{key}"
            self.enabled = True
        else:
            # Fallback: try legacy bark_url field
            self.bark_url = str(config.get("bark_url", "")).strip('/')
            self.enabled = bool(self.bark_url) and self.bark_url.startswith("http")
        
        if self.enabled:
            logger.info(f"BarkNotifier: Initialized successfully. Server: {server}")
        else:
            logger.warning("BarkNotifier: Disabled — missing bark_server/bark_key in config.json")

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
            resp = requests.get(dispatch_url, timeout=15.0)
            if resp.status_code == 200:
                logger.debug(f"BarkNotifier: Push delivered successfully.")
            else:
                logger.warning(f"BarkNotifier: Server returned status {resp.status_code}")
            
        except Exception as e:
            logger.warning(f"BarkNotifier: Failed bridging notification payload remotely -> {e}")
