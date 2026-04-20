import os
import httplib2
from pathlib import Path
from urllib.parse import urlparse

# Google API Client tools
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

import sys
from modules.logger import logger
from modules.config_manager import config

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys.executable).parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

class YouTubeUploader:
    # Essential scopes for full YouTube Data API v3 upload ability
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
    
    def __init__(self):
        self.api_service_name = "youtube"
        self.api_version = "v3"
        self.client_secrets_file = PROJECT_ROOT / config.get("youtube_client_secret_file", "client_secret.json")
        self.token_file = PROJECT_ROOT / "youtube_token.json"
        
        self.category_id = config.get("youtube_category_id", "22")
        self.privacy_status = config.get("youtube_privacy_status", "public")
        self.youtube_client = None

    def _build_proxy_http(self):
        """Constructs a raw httplib2 instance mapped securely through the split-tunnel proxy config."""
        proxies = config.get_proxies()
        
        # If proxy is explicitly configured (e.g. "http://127.0.0.1:7890"), we bridge the python-socket
        if proxies and "http" in proxies:
            proxy_url = proxies["http"]
            parsed = urlparse(proxy_url)
            
            host = parsed.hostname
            port = parsed.port
            
            if host and port:
                logger.info(f"YouTubeUploader: Routing traffic via Proxy -> {host}:{port}")
                proxy_info = httplib2.ProxyInfo(
                    proxy_type=httplib2.socks.PROXY_TYPE_HTTP_NO_TUNNEL if proxy_url.startswith("http") else httplib2.socks.PROXY_TYPE_SOCKS5,
                    proxy_host=host,
                    proxy_port=port
                )
                return httplib2.Http(proxy_info=proxy_info, timeout=60)
        
        # Direct connection fallback bypassing OS defaults
        logger.debug("YouTubeUploader: Routing traffic via DIRECT connection.")
        return httplib2.Http(timeout=60)

    def authenticate(self) -> bool:
        """Boots the OAuth 2.0 flow securely or retrieves via cached refresh tokens."""
        creds = None
        
        logger.info(f"YouTubeUploader: Token file path: {self.token_file}")
        logger.info(f"YouTubeUploader: Client secrets path: {self.client_secrets_file}")
        
        if self.token_file.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_file), self.SCOPES)
                logger.info("YouTubeUploader: Loaded cached token successfully.")
            except Exception as e:
                logger.warning(f"YouTubeUploader: Failed to parse cached token. Rebooting auth cycle: {e}")
                
        # If no valid credentials, run the auth flow locally
        if not creds or not creds.valid:
            try:
                if creds and creds.expired and creds.refresh_token:
                    logger.info("YouTubeUploader: Token expired, requesting refresh from Google...")
                    try:
                        # Use proxy-aware session for token refresh
                        import google.auth.transport.requests
                        import requests as req_lib
                        
                        session = req_lib.Session()
                        proxies = config.get_proxies()
                        if proxies:
                            session.proxies.update(proxies)
                            logger.info(f"YouTubeUploader: Using proxy for token refresh: {proxies.get('http', 'none')}")
                        
                        creds.refresh(google.auth.transport.requests.Request(session=session))
                        logger.info("YouTubeUploader: Token refreshed successfully.")
                    except Exception as refresh_err:
                        logger.warning(f"YouTubeUploader: Refresh failed: {refresh_err}. Forcing re-auth.")
                        creds = None
                
                if not creds:
                    if not self.client_secrets_file.exists():
                        logger.error(f"YouTubeUploader: FATAL! Missing {self.client_secrets_file}.")
                        return False
                    
                    logger.info("YouTubeUploader: Starting browser OAuth flow. Please complete login in browser.")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.client_secrets_file), self.SCOPES
                    )
                    creds = flow.run_local_server(port=0, open_browser=True)
                    logger.info("YouTubeUploader: Browser auth completed successfully.")
                    
                # Ensure parent directory exists before writing token
                self.token_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.token_file, 'w') as token_cache:
                    token_cache.write(creds.to_json())
                logger.info(f"YouTubeUploader: Token cached to {self.token_file}")
            except Exception as e:
                logger.error(f"YouTubeUploader: Authentication failure: {e}")
                import traceback
                logger.error(f"YouTubeUploader: Traceback: {traceback.format_exc()}")
                return False
                
        try:
            # Use google-auth native transport (requests-based) instead of httplib2
            # httplib2 has a known bug: "Redirected but the response is missing a Location: header"
            # during YouTube resumable uploads. credentials= param uses requests which works correctly.
            self.youtube_client = build(
                self.api_service_name, 
                self.api_version, 
                credentials=creds, 
                cache_discovery=False
            )
            logger.info("YouTubeUploader: API service built successfully (google-auth native).")
            return True
        except Exception as e:
            logger.error(f"YouTubeUploader: Failed to build API service: {e}")
            import traceback
            logger.error(f"YouTubeUploader: Traceback: {traceback.format_exc()}")
            return False

    def _sanitize_metadata(self, text: str, limit: int) -> str:
        """Safely truncates text boundaries to strict YouTube constraints, appending ellipsis gracefully."""
        if not text:
            return ""
        if len(text) > limit:
            return text[:limit - 3] + "..."
        return text

    def upload_video_sequence(self, douyin_id: str, video_path: str, cover_path: str, title: str, desc: str) -> str:
        """
        Master operation: Stream chunk MP4, inserts Metadata, then overrides tracking Custom Thumbnail.
        Returns the published YouTube Video ID gracefully, or False if aborted.
        """
        if not self.youtube_client:
            if not self.authenticate():
                return False

        if not os.path.exists(video_path):
            logger.error(f"YouTubeUploader: Core Video payload missing locally at {video_path}")
            return False

        logger.info(f"YouTubeUploader: Initiating Chunked Sequence API Upload for [{douyin_id}]")

        safe_title = self._sanitize_metadata(title, 100)
        safe_desc = self._sanitize_metadata(desc, 5000)

        body = {
            'snippet': {
                'title': safe_title,
                'description': safe_desc,
                'categoryId': self.category_id
            },
            'status': {
                'privacyStatus': self.privacy_status,
                'selfDeclaredMadeForKids': False
            }
        }

        try:
            # Resumable Chunk Controller (2MB slices ensures no memory stack blows out per NFR2)
            media = MediaFileUpload(
                video_path,
                chunksize=1024*1024*2, 
                resumable=True
            )

            request = self.youtube_client.videos().insert(
                part=",".join(body.keys()),
                body=body,
                media_body=media
            )
            
            # Blocking byte transfer wrapper loop
            response = None
            import time
            last_log_time = time.time()
            retry_count = 0
            max_chunk_retries = 10
            
            while response is None:
                try:
                    # num_retries=3 handles basic HTTP 5xx codes internally
                    status, response = request.next_chunk(num_retries=3)
                    if status:
                        percent = int(status.progress() * 100)
                        if time.time() - last_log_time >= 5.0 or percent == 100:
                            logger.info(f"YouTubeUploader: Uploading stream payload... {percent}% done")
                            last_log_time = time.time()
                    # Reset generic retry count upon successful progress
                    retry_count = 0
                except Exception as e:
                    # Catch all network-level drops (SSL EOF, connection reset, read timeout)
                    # F8: Use precise quota detection - check for HttpError with 403 + quotaExceeded reason
                    is_quota_error = False
                    try:
                        from googleapiclient.errors import HttpError
                        if isinstance(e, HttpError) and e.resp.status == 403:
                            error_details = str(e.content).lower()
                            if 'quotaexceeded' in error_details or 'usagelimits' in error_details:
                                is_quota_error = True
                    except ImportError:
                        pass
                    
                    if is_quota_error or 'quotaexceeded' in str(e).lower():
                        raise  # Let the outer except handle the hard circuit breaker
                    
                    retry_count += 1
                    logger.warning(f"YouTubeUploader: Chunk upload interrupted ({retry_count}/{max_chunk_retries}): {e}")
                    
                    if retry_count > max_chunk_retries:
                        logger.error(f"YouTubeUploader: Max chunk retries reached. Aborting upload.")
                        raise
                        
                    sleep_time = min(60, 2 ** retry_count)
                    logger.info(f"YouTubeUploader: Sleeping for {sleep_time}s before resuming chunk upload...")
                    time.sleep(sleep_time)
                    continue  # F12: explicitly continue the while loop

            yt_video_id = response.get('id')
            logger.info(f"YouTubeUploader: SUCCESS! Video broadcast complete. https://youtu.be/{yt_video_id}")

            # Custom Thumbnail Publisher Trigger overlay (Epic 3.3)
            if cover_path and os.path.exists(cover_path):
                self._upload_thumbnail(yt_video_id, cover_path)
                
            return yt_video_id

        except Exception as e:
            # Trap Quota Exceeded precisely via googleapiclient HttpError
            is_quota = False
            try:
                from googleapiclient.errors import HttpError
                if isinstance(e, HttpError) and e.resp.status == 403:
                    error_details = str(e.content).lower()
                    if 'quotaexceeded' in error_details or 'usagelimits' in error_details:
                        is_quota = True
            except ImportError:
                pass
            
            if is_quota or 'quotaexceeded' in str(e).lower():
                logger.critical(f"YouTubeUploader: CIRCUIT BREAKER TRIGGERED! API Quota globally exhausted: {e}")
                return "QUOTA_EXCEEDED"
            logger.error(f"YouTubeUploader: Upload transmission crashed or severely rejected: {e}")
            return False

    def _upload_thumbnail(self, video_id: str, cover_path: str):
        """Attaches the converted JPEG cover precisely onto the freshly minted video node."""
        try:
            logger.info(f"YouTubeUploader: Commencing Custom Thumbnail API injection for hook [{video_id}]...")
            # Explicitly setting mimetype='image/jpeg' bypasses Windows Registry MIME guessing bugs
            self.youtube_client.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(cover_path, mimetype='image/jpeg')
            ).execute()
            logger.debug(f"YouTubeUploader: Custom Thumbnail mounted flawlessly.")
        except Exception as e:
            logger.warning(f"YouTubeUploader: Thumbnail injection severed! Video is online but lacks specified custom mapping. {e}")
