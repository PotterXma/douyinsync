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
        推送至 Bark；URL 带 config 的 ``bark_sound``，一般为有声铃音。

        * ``active``：默认、普通通知+铃声
        * ``timeSensitive``：时间敏感/更高打扰（仍带 sound，非 silent）
        * ``passive``：静默、仅进列表（如每日 23:50 汇总，避免刷爆）
        每次从 config 读入，支持热重载。
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
        """重置每日上传计数器（若日历日期已变更则归零）。"""
        today = datetime.date.today().isoformat()
        if today != self._summary_date:
            self._daily_upload_count = 0
            self._summary_date = today

    def _snapshot_and_reset_daily_counter(self) -> int:
        """
        原子性地快照当前计数并在跨日时重置。
        先读取再重置，避免午夜滚动竞态：
          - 若调度器在 23:59 准备触发，但实际执行已过 00:00，
            直接调用 _check_and_reset_daily_counter 会先归零再读取，
            导致前一天数据丢失。本方法先快照后重置，保证数据不丢。
        返回快照值（前一天或当天的计数）。
        """
        snapshot = self._daily_upload_count
        today = datetime.date.today().isoformat()
        if today != self._summary_date:
            # 日期已翻滚：snapshot 持有前一天数据，现在安全重置
            self._daily_upload_count = 0
            self._summary_date = today
        return snapshot

    def record_upload_success(self) -> None:
        """Increments the in-memory daily upload counter. Call once per successful upload."""
        self._check_and_reset_daily_counter()
        self._daily_upload_count += 1

    def push_daily_summary(self) -> None:
        """
        发送当日上传汇总推送（passive 静默级别，防止通知疲劳）。
        若计数为 0 则静默跳过。
        使用 _snapshot_and_reset_daily_counter 避免午夜滚动竞态：
        即使调度器延迟触发跨过午夜，也能正确发送前一天的统计数据。
        """
        count = self._snapshot_and_reset_daily_counter()
        if count == 0:
            return
        self.push(
            "DouyinSync Daily Summary",
            "%s video(s) uploaded today" % count,
            level="passive"
        )
