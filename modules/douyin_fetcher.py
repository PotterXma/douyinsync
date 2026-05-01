import httpx
import json
from urllib.parse import urlparse, urlencode, quote
from typing import List, Tuple, Optional

from modules.logger import logger
from modules.config_manager import config
from modules.abogus import ABogus, USERAGENT
from utils.models import VideoRecord
from utils.decorators import auto_retry, circuit_breaker

class DouyinFetcher:
    def __init__(self):
        # We spoof a standard Windows browser to bypass basic generic WAF
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.douyin.com/",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate"
        }

    def _fetch_timeout(self) -> float:
        """HTTP client timeout for Douyin list API (seconds). See ``douyin_fetch_timeout_seconds`` in config.json."""
        try:
            return float(config.get("douyin_fetch_timeout_seconds", 15))
        except (TypeError, ValueError):
            return 15.0

    def _get_cookie_header(self):
        cookie = str(config.get("douyin_cookie", "")).strip()
        if cookie:
            return {"Cookie": cookie}
        return {}

    @auto_retry(max_retries=3, exceptions=(httpx.RequestError,))
    @circuit_breaker(trip_on=(httpx.HTTPStatusError,))
    async def fetch_user_posts(self, user_url: str, max_cursor: int = 0) -> Tuple[List[VideoRecord], int, bool]:
        """
        Parses profile to get videos with pagination support.
        Returns tuple of (posts_list, next_cursor, has_more).
        """
        logger.info("DouyinFetcher: Initiating scrape for URL -> %s (cursor=%s)", user_url, max_cursor)
        
        current_headers = self.headers.copy()
        current_headers.update(self._get_cookie_header())
        
        sec_user_id = self._extract_sec_user_id(user_url)
        if not sec_user_id:
            logger.error("DouyinFetcher: Could not extract valid sec_user_id from %s", user_url)
            return [], 0, False
            
        # Use exact endpoint mapping
        query_dict = {
            "device_platform": "webapp",
            "aid": "6383",
            "channel": "channel_pc_web",
            "update_version_code": "170400",
            "pc_client_type": "1",
            "version_code": "290100",
            "version_name": "29.1.0",
            "cookie_enabled": "true",
            "screen_width": "1536",
            "screen_height": "864",
            "browser_language": "zh-CN",
            "browser_platform": "Win32",
            "browser_name": "Chrome",
            "browser_version": "122.0.0.0",
            "browser_online": "true",
            "engine_name": "Blink",
            "engine_version": "122.0.0.0",
            "os_name": "Windows",
            "os_version": "10",
            "cpu_core_num": "16",
            "device_memory": "8",
            "platform": "PC",
            "downlink": "10",
            "effective_type": "4g",
            "round_trip_time": "200",
            "sec_user_id": sec_user_id,
            "count": 10,
            "max_cursor": max_cursor,
            "locate_query": "false",
            "show_live_replay_strategy": "1",
            "need_time_list": "1",
            "time_list_query": "0",
            "whale_cut_token": "",
            "cut_version": "1",
            "publish_video_strategy_type": "2",
        }
        
        # Ensure our header uses EXACTLY the user agent that ABogus signs for
        current_headers["User-Agent"] = USERAGENT
        current_headers["Referer"] = "https://www.douyin.com/"
        
        # Must specifically be urlencode with quote_via=quote for identical hashing
        query_str = urlencode(query_dict, quote_via=quote)
        
        # Feed exactly into JoeanAmier ABogus reverse engineered struct
        abogus_str = ABogus(user_agent=USERAGENT).get_value(query_str, method="GET")
        
        # Concat fully qualified signature
        api_url = f"https://www.douyin.com/aweme/v1/web/aweme/post/?{query_str}&a_bogus={abogus_str}"
        
        try:
            # Fresh AsyncClient per call: ``PipelineCoordinator`` uses ``asyncio.run()`` per sync cycle,
            # which closes the event loop — a long-lived client would raise "Event loop is closed".
            async with httpx.AsyncClient(timeout=self._fetch_timeout()) as client:
                response = await client.get(api_url, headers=current_headers)
                response.raise_for_status()
                data = response.json()

            posts = self._parse_video_list(data)
            next_cursor = data.get("max_cursor", 0)
            has_more = bool(data.get("has_more", 0))

            return posts, next_cursor, has_more
        except httpx.RequestError as e:
            logger.error("DouyinFetcher: Network error during fetch. %s", e)
            return [], 0, False
        except Exception as e:
            logger.error("DouyinFetcher: Exception during fetch payload parsing: %s", e)
            return [], 0, False

    def _extract_sec_user_id(self, url: str) -> str:
        """Extracts the unique sec_user_id from standard profile sharing URLs."""
        try:
            path = urlparse(url).path
            parts = path.strip('/').split('/')
            if "user" in parts:
                idx = parts.index("user")
                if idx + 1 < len(parts):
                    return parts[idx + 1]
        except Exception as e:
            logger.debug("Failed to URL-parse %s: %s", url, e)
        return ""

    def _parse_video_list(self, json_data: dict) -> List[VideoRecord]:
        """Safely distills Douyin JSON into strongly-typed VideoRecord instances."""
        results: List[VideoRecord] = []
        if not isinstance(json_data, dict):
            logger.warning("DouyinFetcher: Invalid JSON payload root format.")
            return results
            
        aweme_list = json_data.get("aweme_list", [])
        if not aweme_list:
            logger.warning("DouyinFetcher: Payload returned empty or null aweme_list. Likely blocked by Douyin WAF or Cookie expired.")
            return results
        
        for item in aweme_list:
            # Filter Layer: Discard Tuwen (Image posts) protecting downstream YouTube Uploader
            if item.get("images") is not None or item.get("aweme_type") == 68:
                logger.debug("DouyinFetcher: Filtering out unsupported Image-Post. ID: %s", item.get('aweme_id'))
                continue
                
            try:
                douyin_id = item["aweme_id"]
                title = item.get("desc", "")
                
                # Digging for primary MP4 (Highest Quality)
                video_info = item.get("video", {})
                bit_rate_list = video_info.get("bit_rate", [])
                video_url = ""
                if bit_rate_list:
                    # Sort by bit_rate value descending to grab the highest quality
                    bit_rate_list = sorted(bit_rate_list, key=lambda x: x.get("bit_rate", 0), reverse=True)
                    best_play_addr = bit_rate_list[0].get("play_addr", {}).get("url_list", [])
                    if best_play_addr:
                        video_url = best_play_addr[0]
                
                # Fallback to base play_addr if bit_rate array is missing
                if not video_url:
                    play_addr = video_info.get("play_addr", {}).get("url_list", [])
                    if not play_addr:
                        continue
                    video_url = play_addr[0]
                
                # Digging for WebP cover
                cover_addr = video_info.get("cover", {}).get("url_list", [])
                cover_url = cover_addr[0] if cover_addr else ""
                
                results.append(VideoRecord(
                    douyin_id=str(douyin_id),
                    title=title[:300],       # Soft fail-safe limit
                    description=title,
                    video_url=video_url,
                    cover_url=cover_url,
                ))
            except KeyError as e:
                logger.debug("DouyinFetcher: Skipped item missing fundamental keys %s", e)
                continue
                
        logger.info("DouyinFetcher: Successfully processed %s valid video records.", len(results))
        return results

    async def refresh_video_url(self, douyin_id: str, accounts: list) -> Optional[dict]:
        """
        Re-fetches the video list from the API and finds a matching video_id 
        to obtain a fresh CDN URL with valid time-based tokens.
        Searches up to 3 pages to handle accounts with many videos.
        Returns dict with fresh video_url/cover_url or None if not found.
        """
        for account in accounts:
            if isinstance(account, dict):
                if not account.get("enable", True):
                    continue
                account_url = account.get("url", "")
            else:
                account_url = str(account)
            
            if not account_url:
                continue
            
            try:
                # Search up to 3 pages to find the video (may not be in the first 10/13 results)
                cursor = 0
                for _page in range(3):
                    posts, next_cursor, has_more = await self.fetch_user_posts(account_url, max_cursor=cursor)
                    for post in posts:
                        if post.douyin_id == douyin_id:
                            return {
                                "video_url": post.video_url,
                                "cover_url": post.cover_url
                            }
                    if not has_more or next_cursor == 0:
                        break
                    cursor = next_cursor
            except Exception as e:
                logger.warning("DouyinFetcher: Error refreshing URL for %s: %s", douyin_id, e)
                continue
        
        return None
