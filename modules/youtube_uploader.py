import os
import httpx
import logging
import json
import aiofiles
from pathlib import Path
from typing import Optional

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials

from utils.models import VideoRecord, ProxyConfig, YoutubeQuotaError, YoutubeUploadError, YoutubeNetworkError
from utils.network import async_client_kwargs_from_proxy_config
from modules.logger import logger

class YoutubeUploader:
    SCOPES = ['https://www.googleapis.com/auth/youtube.upload']

    def __init__(self, client_secrets_file: str = "client_secret.json", token_file: str = "youtube_token.json", proxy_config: Optional[ProxyConfig] = None, token: Optional[str] = None):
        self.client_secrets_file = Path(client_secrets_file)
        self.token_file = Path(token_file)
        self.proxy_config = proxy_config
        if token is not None and str(token).strip():
            self.token = str(token).strip()
        else:
            self.token = None
        self._hydrate_token_from_storage()

    def _hydrate_token_from_storage(self) -> None:
        """If ``youtube_api_token`` was not passed in config, load (and optionally refresh) ``youtube_token.json``."""
        if self.token:
            return
        if not self.token_file.is_file():
            return
        try:
            creds = Credentials.from_authorized_user_file(str(self.token_file), self.SCOPES)
        except Exception as e:
            logger.warning("YoutubeUploader: cannot read token file %s: %s", self.token_file, e)
            return
        try:
            if not creds.valid:
                if creds.expired and creds.refresh_token:
                    logger.info("YoutubeUploader: refreshing expired token from %s", self.token_file)
                    creds.refresh(GoogleRequest())
                    self.token_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.token_file, "w", encoding="utf-8") as f:
                        f.write(creds.to_json())
                else:
                    logger.warning(
                        "YoutubeUploader: %s exists but credentials are not valid; run OAuth flow (authenticate).",
                        self.token_file,
                    )
                    return
            self.token = creds.token
            logger.info("YoutubeUploader: loaded access token from %s", self.token_file)
        except Exception as e:
            logger.warning("YoutubeUploader: token refresh failed: %s", e)

    def authenticate(self) -> bool:
        """Boots the OAuth 2.0 flow securely or retrieves via cached refresh tokens."""
        creds = None
        
        if self.token_file.exists():
            try:
                creds = Credentials.from_authorized_user_file(str(self.token_file), self.SCOPES)
            except Exception as e:
                logger.warning("Failed to parse cached token: %s", e)
                
        if not creds or not creds.valid:
            try:
                if creds and creds.expired and creds.refresh_token:
                    logger.info("Token expired, requesting refresh...")
                    creds.refresh(GoogleRequest())
                else:
                    if not self.client_secrets_file.exists():
                        logger.error("Missing %s.", self.client_secrets_file)
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.client_secrets_file), self.SCOPES
                    )
                    creds = flow.run_local_server(port=0, open_browser=True)
                    
                self.token_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.token_file, 'w') as token_cache:
                    token_cache.write(creds.to_json())
            except Exception as e:
                logger.error("Authentication failure: %s", e)
                return False
                
        self.token = creds.token
        return True

    from utils.decorators import auto_retry
    @auto_retry(max_retries=3, exceptions=(YoutubeNetworkError, YoutubeUploadError))
    async def upload(self, video: VideoRecord) -> str:
        if not os.path.exists(video.local_video_path):
            raise FileNotFoundError(f"Video file not found: {video.local_video_path}")

        if not self.token or not str(self.token).strip():
            raise YoutubeUploadError(
                "Missing YouTube OAuth access token (would send illegal 'Bearer ' header). "
                "Set youtube_api_token in config.json, or place a valid %s next to the application (run OAuth once)."
                % (self.token_file,)
            )

        client_kw = async_client_kwargs_from_proxy_config(self.proxy_config)

        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(os.path.getsize(video.local_video_path))
        }

        async with httpx.AsyncClient(**client_kw) as client:
            try:
                # 1. Initiate Resumable Upload
                metadata = {
                    "snippet": {
                        "title": video.title,
                        "description": video.description
                    },
                    "status": {
                        "privacyStatus": "public"
                    }
                }
                
                resp = await client.post(
                    "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                    json=metadata,
                    headers=headers
                )
                resp.raise_for_status()
                
                upload_url = resp.headers.get("Location")
                if not upload_url:
                    raise YoutubeUploadError("Resumable upload URL missing")
                
                # 2. Upload Video body
                async def stream_file(filepath):
                    async with aiofiles.open(filepath, "rb") as f:
                        while chunk := await f.read(1024 * 1024 * 2):
                            yield chunk
                            
                put_resp = await client.put(upload_url, content=stream_file(video.local_video_path))
                put_resp.raise_for_status()
                youtube_id = put_resp.json().get("id")
                    
                # 3. Upload thumbnail if exists
                if video.local_cover_path and os.path.exists(video.local_cover_path):
                    async with aiofiles.open(video.local_cover_path, "rb") as cf:
                        cover_content = await cf.read()
                    thumb_resp = await client.post(
                        f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={youtube_id}",
                        headers={"Authorization": f"Bearer {self.token}"},
                        content=cover_content
                    )
                    thumb_resp.raise_for_status()
                        
                return youtube_id

            except httpx.HTTPStatusError as e:
                # Map Quota errors safely without broad exception handling that swallows our own errors 
                if e.response.status_code == 403:
                    try:
                        err_json = e.response.json()
                        err_obj = err_json.get("error", {})
                        errors_list = err_obj.get("errors", [{}])
                        if errors_list and len(errors_list) > 0:
                            reason = errors_list[0].get("reason", "")
                            if reason == "quotaExceeded":
                                raise YoutubeQuotaError("Quota exceeded")
                    except ValueError:
                        pass
                raise YoutubeUploadError(f"Upload failed: {e}")
            except httpx.RequestError as e:
                raise YoutubeNetworkError(f"Network error: {e}")
