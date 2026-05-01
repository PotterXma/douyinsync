import asyncio
import os
import re
import time
import httpx
import aiofiles
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials

from utils.models import (
    VideoRecord,
    ProxyConfig,
    YoutubeQuotaError,
    YoutubeUploadError,
    YoutubeNetworkError,
    YoutubeUploadInterrupted,
)
from utils.network import async_client_kwargs_from_proxy_config
from utils.cover_stamp import stamp_upload_sequence_on_cover
from modules.database import VideoDAO
from modules.logger import logger
from modules.config_manager import config
# Chunk uploads must be multiples of 256 KiB except the final chunk (YouTube resumable protocol).
_YT_CHUNK_GRANULARITY = 256 * 1024
_YT_DEFAULT_CHUNK_BYTES = 8 * 1024 * 1024


class _ThrottledUploadProgress:
    """Throttle SQLite writes during resumable upload (Story 5-5): ≥1s or ≥5% steps."""

    __slots__ = ("douyin_id", "total", "_last_mono", "_last_written")

    def __init__(self, douyin_id: str, total: int):
        self.douyin_id = douyin_id
        self.total = max(1, int(total))
        self._last_mono = 0.0
        self._last_written = -1

    def pulse(self, done: int, *, force: bool = False) -> None:
        done = max(0, min(int(done), self.total))
        now = time.monotonic()
        if force:
            VideoDAO.update_upload_progress(self.douyin_id, done, self.total)
            self._last_mono = now
            self._last_written = done
            return
        pct = 100.0 * done / self.total
        last_pct = 100.0 * self._last_written / self.total if self._last_written >= 0 else -100.0
        if (now - self._last_mono >= 1.0) or (done >= self.total) or (pct - last_pct >= 5.0):
            VideoDAO.update_upload_progress(self.douyin_id, done, self.total)
            self._last_mono = now
            self._last_written = done


def _format_httpx_request_error(exc: httpx.RequestError) -> str:
    """httpx 部分异常 str() 为空；用类型/URL/cause 便于排障。"""
    parts: list[str] = [type(exc).__name__]
    s = (str(exc) or "").strip()
    if s:
        parts.append(s)
    try:
        req = getattr(exc, "request", None)
        if req is not None:
            parts.append(f"method={getattr(req, 'method', '')!s} url={getattr(req, 'url', '')!s}")
    except Exception:
        pass
    cause = exc.__cause__
    if cause is not None:
        parts.append(f"cause={type(cause).__name__!s}:{cause!r}")
    return " | ".join(p for p in parts if p)


def _youtube_httpx_timeout() -> httpx.Timeout:
    """
    大文件分块 PUT 到 Google 若使用默认 5s 级超时，极易 ReadTimeout/WriteTimeout 且 str(e) 为空。
    可通过 config ``youtube_upload_read_timeout_seconds`` / ``youtube_upload_write_timeout_seconds`` 调整（秒）。
    """
    read_s = 1200.0
    write_s = 1200.0
    try:
        v = config.get("youtube_upload_read_timeout_seconds", None)
        if v is not None:
            read_s = max(60.0, float(v))
    except (TypeError, ValueError):
        pass
    try:
        v2 = config.get("youtube_upload_write_timeout_seconds", None)
        if v2 is not None:
            write_s = max(60.0, float(v2))
    except (TypeError, ValueError):
        pass
    return httpx.Timeout(connect=30.0, read=read_s, write=write_s, pool=30.0)


def _parse_range_next_byte(range_header: Optional[str]) -> Optional[int]:
    """Parse ``Range: bytes=0-999999`` → next byte offset ``1000000``. Returns None if unknown."""
    if not range_header:
        return None
    rh = range_header.strip()
    if not rh.lower().startswith("bytes="):
        return None
    spec = rh.split("=", 1)[1].strip()
    if "-" not in spec:
        return None
    try:
        last_byte = int(spec.split("-", 1)[1])
        return last_byte + 1
    except ValueError:
        return None


def _parse_retry_after_header(raw: Optional[str]) -> Optional[float]:
    """
    Parse ``Retry-After`` per RFC 7231: non-negative integer seconds, or HTTP-date.
    Returns seconds to wait, capped at 86400; None if absent or unparsable.
    """
    if not raw:
        return None
    s = raw.strip()
    if not s:
        return None
    if s.isdigit():
        return float(min(int(s), 86400))
    try:
        dt = parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        if delta <= 0:
            return None
        return float(min(delta, 86400))
    except (TypeError, ValueError):
        return None


def _retry_after_sleep_seconds(resp: httpx.Response, fallback: float, cap: float = 3600.0) -> float:
    """Honor ``Retry-After`` when present: ``min(cap, max(fallback, retry_after))``."""
    parsed = _parse_retry_after_header(resp.headers.get("Retry-After") or resp.headers.get("retry-after"))
    base = max(float(fallback), parsed if parsed is not None else 0.0)
    return min(float(cap), base)


def _is_loop_shutdown_error(exc: BaseException) -> bool:
    t = f"{type(exc).__name__} {exc!r}".lower()
    if "cannot schedule new futures after shutdown" in t:
        return True
    if "event loop is closed" in t or "interpreter shutdown" in t:
        return True
    if "cannot be called from a running event loop" in t:
        return True
    return False


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

    @staticmethod
    def _strip_shorts_hashtag(text: str) -> str:
        """Remove ``#shorts`` tokens (case-insensitive) to reduce Shorts-only signaling in metadata."""
        if not text:
            return text
        cleaned = re.sub(r"(?i)#shorts\b", "", text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _build_upload_metadata(self, video: VideoRecord) -> Dict[str, Any]:
        """Snippet + status from config (category, privacy) and optional Shorts hashtag strip."""
        raw_privacy = str(config.get("youtube_privacy_status", "public") or "public").strip().lower()
        if raw_privacy not in ("public", "private", "unlisted"):
            raw_privacy = "public"

        cat = config.get("youtube_category_id", "22")
        try:
            category_id = str(int(cat))
        except (TypeError, ValueError):
            category_id = "22"

        strip_hs = config.get("youtube_strip_shorts_hashtag", True)
        if isinstance(strip_hs, str):
            strip_hs = strip_hs.strip().lower() not in ("0", "false", "no", "off")

        raw_title = (video.title or "").strip()
        raw_desc = (video.description or raw_title).strip()
        if strip_hs:
            title = self._strip_shorts_hashtag(raw_title)
            description = self._strip_shorts_hashtag(raw_desc)
        else:
            title, description = raw_title, raw_desc

        title = (title or "Untitled")[:100]
        description = description[:5000]

        return {
            "snippet": {
                "title": title,
                "description": description,
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": raw_privacy,
            },
        }

    def _youtube_upload_chunk_size(self) -> int:
        raw = config.get("youtube_upload_chunk_size_bytes", None)
        if raw is None:
            n = _YT_DEFAULT_CHUNK_BYTES
        else:
            try:
                n = int(raw)
            except (TypeError, ValueError):
                n = _YT_DEFAULT_CHUNK_BYTES
        n = max(_YT_CHUNK_GRANULARITY, n)
        return (n // _YT_CHUNK_GRANULARITY) * _YT_CHUNK_GRANULARITY

    def _ensure_token_fresh_sync(self) -> None:
        """Refresh OAuth access token from disk when expired (slow uploads exceed ~1h access token TTL)."""
        if not self.token_file.is_file():
            return
        try:
            creds = Credentials.from_authorized_user_file(str(self.token_file), self.SCOPES)
        except Exception as e:
            logger.warning("YoutubeUploader: cannot reload credentials from %s: %s", self.token_file, e)
            return
        try:
            if creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
                self.token_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.token_file, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
            if creds.token:
                self.token = creds.token
        except Exception as e:
            logger.warning("YoutubeUploader: OAuth refresh failed: %s", e)

    def _oauth_refresh_supported(self) -> bool:
        """True if ``youtube_token.json`` can rotate access tokens (large uploads exceed ~1h bearer TTL)."""
        if not self.token_file.is_file():
            return False
        try:
            creds = Credentials.from_authorized_user_file(str(self.token_file), self.SCOPES)
        except Exception:
            return False
        return bool(creds.refresh_token)

    @staticmethod
    def _maybe_raise_quota_http_error(resp: httpx.Response) -> None:
        if resp.status_code != 403:
            return
        try:
            err_json = resp.json()
            err_obj = err_json.get("error", {})
            errors_list = err_obj.get("errors", [{}])
            if errors_list and errors_list[0].get("reason") == "quotaExceeded":
                raise YoutubeQuotaError("Quota exceeded")
        except YoutubeQuotaError:
            raise
        except ValueError:
            pass

    async def _query_resumable_status(
        self,
        client: httpx.AsyncClient,
        upload_url: str,
        total: int,
    ) -> Tuple[Optional[str], int]:
        """Probe bytes uploaded or completed video id (YouTube ``bytes */total`` status PUT)."""
        probe_headers_base = {
            "Content-Length": "0",
            "Content-Range": "bytes */%s" % total,
        }
        transient_round = 0
        for attempt in range(14):
            await asyncio.to_thread(self._ensure_token_fresh_sync)
            probe_headers = dict(probe_headers_base)
            probe_headers["Authorization"] = "Bearer %s" % self.token
            resp = await client.put(upload_url, content=b"", headers=probe_headers)

            if resp.status_code in (200, 201):
                try:
                    body = resp.json()
                except ValueError as e:
                    raise YoutubeUploadError("Status probe returned success without JSON body") from e
                youtube_id = body.get("id") if isinstance(body, dict) else None
                if youtube_id:
                    return str(youtube_id), total
                raise YoutubeUploadError("Status probe succeeded but response had no video id")

            if resp.status_code == 308:
                nb = _parse_range_next_byte(resp.headers.get("Range") or resp.headers.get("range"))
                next_off = nb if nb is not None else 0
                return None, next_off

            if resp.status_code == 404:
                raise YoutubeUploadError(
                    "Resumable upload session expired (HTTP 404). Retry will start a new upload from byte 0."
                )

            if resp.status_code in (429, 500, 502, 503, 504):
                transient_round += 1
                fb = min(60.0, 2 ** min(transient_round, 5))
                sleep_s = _retry_after_sleep_seconds(resp, fb, cap=3600.0)
                logger.warning(
                    "YoutubeUploader: HTTP %s on status probe (round %s); sleeping %.1fs",
                    resp.status_code,
                    transient_round,
                    sleep_s,
                )
                await asyncio.sleep(sleep_s)
                continue

            self._maybe_raise_quota_http_error(resp)
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise YoutubeUploadError("Upload status probe failed: %s" % e) from e
            return None, 0

        raise YoutubeUploadError("Upload status probe exhausted retries after transient HTTP errors")

    async def _upload_video_resumable_chunks(
        self,
        client: httpx.AsyncClient,
        upload_url: str,
        filepath: str,
        total: int,
        content_type: str,
        progress_douyin_id: Optional[str] = None,
    ) -> str:
        chunk_sz = self._youtube_upload_chunk_size()
        offset = 0
        consecutive_net_errors = 0
        consecutive_401 = 0
        iter_guard = 0
        max_iters = max(200, (total // max(_YT_CHUNK_GRANULARITY, 1)) + 50)
        progress = (
            _ThrottledUploadProgress(progress_douyin_id, total) if progress_douyin_id else None
        )
        if progress:
            await asyncio.to_thread(lambda: progress.pulse(0, force=True))

        while offset < total:
            iter_guard += 1
            if iter_guard > max_iters:
                raise YoutubeUploadError(
                    "YouTube upload exceeded internal iteration limit (offset=%s total=%s)" % (offset, total)
                )

            await asyncio.to_thread(self._ensure_token_fresh_sync)
            remaining = total - offset
            piece_len = chunk_sz if remaining > chunk_sz else remaining

            async with aiofiles.open(filepath, "rb") as f:
                await f.seek(offset)
                data = await f.read(piece_len)

            if len(data) != piece_len:
                raise YoutubeUploadError("Short read from local video file at offset %s" % offset)

            end_byte = offset + len(data) - 1
            content_range = "bytes %s-%s/%s" % (offset, end_byte, total)
            put_headers = {
                "Authorization": "Bearer %s" % self.token,
                "Content-Length": str(len(data)),
                "Content-Type": content_type,
                "Content-Range": content_range,
            }

            try:
                put_resp = await client.put(upload_url, content=data, headers=put_headers)
            except httpx.RequestError as e:
                consecutive_net_errors += 1
                detail = _format_httpx_request_error(e)
                logger.warning(
                    "YoutubeUploader: chunk PUT RequestError at offset %s (%s); probing upload status",
                    offset,
                    detail,
                )
                if consecutive_net_errors > 12:
                    logger.error("YoutubeUploader: HTTPX RequestError: %s", detail)
                    raise YoutubeNetworkError("Network error: %s" % detail) from e
                fb = min(30.0, 2 ** min(consecutive_net_errors, 4))
                await asyncio.sleep(fb)
                done_id, offset = await self._query_resumable_status(client, upload_url, total)
                if done_id:
                    if progress:
                        await asyncio.to_thread(lambda: progress.pulse(total, force=True))
                    return done_id
                if progress:
                    await asyncio.to_thread(lambda p=progress, o=offset: p.pulse(o))
                continue

            consecutive_net_errors = 0

            if put_resp.status_code != 401:
                consecutive_401 = 0

            if put_resp.status_code == 401:
                consecutive_401 += 1
                await asyncio.to_thread(self._ensure_token_fresh_sync)
                if not self._oauth_refresh_supported():
                    raise YoutubeUploadError(
                        "YouTube returned HTTP 401 during upload. A static youtube_api_token cannot be refreshed; "
                        "long uploads require %s with a refresh_token (complete OAuth once beside the application)."
                        % (self.token_file,)
                    )
                if consecutive_401 > 5:
                    raise YoutubeUploadError(
                        "YouTube repeatedly returned HTTP 401 after token refresh. "
                        "Re-authenticate or verify youtube.upload scope and API credentials."
                    )
                logger.info(
                    "YoutubeUploader: HTTP 401 on chunk PUT (attempt %s); retrying after OAuth refresh",
                    consecutive_401,
                )
                await asyncio.sleep(1)
                continue

            if put_resp.status_code in (200, 201):
                try:
                    body = put_resp.json()
                except ValueError as e:
                    raise YoutubeUploadError("YouTube success response was not JSON") from e
                youtube_id = body.get("id") if isinstance(body, dict) else None
                if not youtube_id:
                    raise YoutubeUploadError("YouTube returned no video id after upload")
                if progress:
                    await asyncio.to_thread(lambda: progress.pulse(total, force=True))
                return str(youtube_id)

            if put_resp.status_code == 308:
                nb = _parse_range_next_byte(put_resp.headers.get("Range") or put_resp.headers.get("range"))
                if nb is not None:
                    offset = nb
                else:
                    offset = end_byte + 1
                if offset > total:
                    raise YoutubeUploadError("Server Range exceeded declared file size")
                if progress:
                    await asyncio.to_thread(lambda p=progress, o=offset: p.pulse(o))
                continue

            if put_resp.status_code in (429, 500, 502, 503, 504):
                logger.warning(
                    "YoutubeUploader: HTTP %s on chunk PUT at offset %s; probing status",
                    put_resp.status_code,
                    offset,
                )
                consecutive_net_errors += 1
                fb = min(60.0, 2 ** min(consecutive_net_errors, 5))
                sleep_s = _retry_after_sleep_seconds(put_resp, fb, cap=3600.0)
                if _parse_retry_after_header(
                    put_resp.headers.get("Retry-After") or put_resp.headers.get("retry-after")
                ) is not None:
                    logger.info("YoutubeUploader: honoring Retry-After on chunk PUT → sleep %.1fs", sleep_s)
                await asyncio.sleep(sleep_s)
                done_id, offset = await self._query_resumable_status(client, upload_url, total)
                if done_id:
                    if progress:
                        await asyncio.to_thread(lambda: progress.pulse(total, force=True))
                    return done_id
                if progress:
                    await asyncio.to_thread(lambda p=progress, o=offset: p.pulse(o))
                continue

            try:
                self._maybe_raise_quota_http_error(put_resp)
                put_resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise YoutubeUploadError("Upload failed: %s" % e) from e

        done_id, _ = await self._query_resumable_status(client, upload_url, total)
        if done_id:
            if progress:
                await asyncio.to_thread(lambda: progress.pulse(total, force=True))
            return done_id
        raise YoutubeUploadError("Upload ended without success response")

    async def _resumable_upload_video_payload(
        self,
        client: httpx.AsyncClient,
        headers: dict,
        video: VideoRecord,
        metadata: dict,
    ) -> str:
        """Start resumable session (POST), then chunked PUT with resume. No whole-function auto_retry (avoids duplicate videos)."""
        try:
            filepath = video.local_video_path
            total = os.path.getsize(filepath)
            content_type = headers.get("X-Upload-Content-Type") or "video/mp4"

            upload_url: Optional[str] = None
            last_post_exc: Optional[BaseException] = None
            for attempt in range(8):
                try:
                    await asyncio.to_thread(self._ensure_token_fresh_sync)
                    session_headers = dict(headers)
                    session_headers["Authorization"] = "Bearer %s" % self.token
                    resp = await client.post(
                        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                        json=metadata,
                        headers=session_headers,
                    )
                    self._maybe_raise_quota_http_error(resp)
                    resp.raise_for_status()
                    upload_url = resp.headers.get("Location")
                    if upload_url:
                        break
                    last_post_exc = YoutubeUploadError("Resumable upload URL missing")
                except YoutubeQuotaError:
                    raise
                except httpx.HTTPStatusError as e:
                    last_post_exc = e
                    self._maybe_raise_quota_http_error(e.response)
                    if e.response.status_code == 401:
                        if not self._oauth_refresh_supported():
                            raise YoutubeUploadError(
                                "YouTube returned HTTP 401 on resumable session POST. A static youtube_api_token "
                                "cannot be refreshed; complete OAuth once so %s contains a refresh_token "
                                "(youtube.upload scope)."
                                % (self.token_file,)
                            ) from e
                        logger.warning(
                            "YoutubeUploader: HTTP 401 on resumable POST (attempt %s/8); refreshing OAuth",
                            attempt + 1,
                        )
                        await asyncio.sleep(2 ** min(attempt, 4))
                        continue
                    if e.response.status_code in (429, 500, 502, 503, 504):
                        fb = float(2 ** min(attempt, 5))
                        sleep_s = _retry_after_sleep_seconds(e.response, fb, cap=3600.0)
                        logger.warning(
                            "YoutubeUploader: HTTP %s on resumable POST (attempt %s/8); sleeping %.1fs",
                            e.response.status_code,
                            attempt + 1,
                            sleep_s,
                        )
                        await asyncio.sleep(sleep_s)
                        continue
                    raise YoutubeUploadError("Upload failed: %s" % e) from e
                except httpx.RequestError as e:
                    last_post_exc = e
                    detail = _format_httpx_request_error(e)
                    logger.warning(
                        "YoutubeUploader: resumable POST RequestError (attempt %s/8): %s",
                        attempt + 1,
                        detail,
                    )
                    await asyncio.sleep(2 ** min(attempt, 5))
                    continue

                if not upload_url:
                    await asyncio.sleep(2 ** attempt)

            if not upload_url:
                if isinstance(last_post_exc, httpx.RequestError):
                    raise YoutubeNetworkError(
                        "Network error: %s" % _format_httpx_request_error(last_post_exc)
                    ) from last_post_exc
                if isinstance(last_post_exc, BaseException):
                    raise YoutubeUploadError("Could not start resumable upload: %s" % last_post_exc) from last_post_exc
                raise YoutubeUploadError("Could not start resumable upload")

            return await self._upload_video_resumable_chunks(
                client,
                upload_url,
                filepath,
                total,
                str(content_type),
                progress_douyin_id=video.douyin_id,
            )
        except (RuntimeError, asyncio.CancelledError) as e:
            if isinstance(e, asyncio.CancelledError) or _is_loop_shutdown_error(e):
                raise YoutubeUploadInterrupted(
                    "Upload stopped because the event loop closed (exit app only after upload completes)."
                ) from e
            raise
        except httpx.HTTPStatusError as e:
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
            raise YoutubeUploadError("Upload failed: %s" % e)
        except httpx.RequestError as e:
            detail = _format_httpx_request_error(e)
            logger.error("YoutubeUploader: HTTPX RequestError: %s", detail)
            raise YoutubeNetworkError("Network error: %s" % detail) from e

    async def _upload_thumbnail_if_needed(self, client: httpx.AsyncClient, video: VideoRecord, youtube_id: str) -> None:
        if not video.local_cover_path or not os.path.exists(video.local_cover_path):
            return
        await asyncio.to_thread(self._ensure_token_fresh_sync)
        seq = VideoDAO.count_uploaded_for_account(getattr(video, "account_mark", None) or "") + 1
        stamped = stamp_upload_sequence_on_cover(video.local_cover_path, seq)
        thumb_path = stamped or video.local_cover_path
        try:
            async with aiofiles.open(thumb_path, "rb") as cf:
                cover_content = await cf.read()
            thumb_resp = await client.post(
                f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={youtube_id}",
                headers={"Authorization": f"Bearer {self.token}"},
                content=cover_content,
            )
            thumb_resp.raise_for_status()
        finally:
            if stamped and stamped != video.local_cover_path:
                try:
                    os.unlink(stamped)
                except OSError:
                    pass

    async def upload(self, video: VideoRecord) -> str:
        if not os.path.exists(video.local_video_path):
            raise FileNotFoundError(f"Video file not found: {video.local_video_path}")

        video_size = os.path.getsize(video.local_video_path)
        if video_size <= 0:
            raise YoutubeUploadError(
                "Video file is empty (0 bytes); cannot upload to YouTube: %s" % (video.local_video_path,)
            )

        if not self.token or not str(self.token).strip():
            raise YoutubeUploadError(
                "Missing YouTube OAuth access token (would send illegal 'Bearer ' header). "
                "Set youtube_api_token in config.json, or place a valid %s next to the application (run OAuth once)."
                % (self.token_file,)
            )

        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Upload-Content-Type": "video/mp4",
            "X-Upload-Content-Length": str(video_size),
        }

        metadata = self._build_upload_metadata(video)

        client_kw = async_client_kwargs_from_proxy_config(
            self.proxy_config,
            timeout=_youtube_httpx_timeout(),
        )
        client_kw.setdefault("follow_redirects", False)

        try:
            async with httpx.AsyncClient(**client_kw) as client:
                youtube_id = await self._resumable_upload_video_payload(client, headers, video, metadata)
                upload_thumb = config.get("youtube_upload_thumbnail", False)
                if isinstance(upload_thumb, str):
                    upload_thumb = upload_thumb.strip().lower() in ("1", "true", "yes", "on")
                if upload_thumb:
                    try:
                        await self._upload_thumbnail_if_needed(client, video, youtube_id)
                    except Exception as e:
                        logger.warning(
                            "YoutubeUploader: thumbnail upload failed but video is already on YouTube (%s): %s",
                            youtube_id,
                            e,
                        )
                return youtube_id
        except (RuntimeError, asyncio.CancelledError) as e:
            if isinstance(e, asyncio.CancelledError) or _is_loop_shutdown_error(e):
                raise YoutubeUploadInterrupted(
                    "Upload interrupted (shutting down). Wait until upload finishes before closing the app."
                ) from e
            raise
        except YoutubeUploadInterrupted:
            raise
