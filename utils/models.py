from dataclasses import dataclass, field
from typing import List, Optional, Any

@dataclass
class TargetConfig:
    douyin_id: str
    name: Optional[str] = None

@dataclass
class ProxyConfig:
    http: Optional[str] = None
    https: Optional[str] = None

@dataclass
class AppConfig:
    targets: List[TargetConfig] = field(default_factory=list)
    proxies: ProxyConfig = field(default_factory=ProxyConfig)

@dataclass
class VideoRecord:
    douyin_id: str
    account_mark: str = ""
    title: str = ""
    description: str = ""
    video_url: str = ""
    cover_url: str = ""
    status: str = "pending"
    retry_count: int = 0
    local_video_path: Optional[str] = None
    local_cover_path: Optional[str] = None
    created_at: Optional[int] = None
    updated_at: Optional[int] = None
    upload_bytes_done: int = 0
    upload_bytes_total: Optional[int] = None
    last_error_summary: Optional[str] = None
    youtube_video_id: Optional[str] = None

class YoutubeUploadError(Exception):
    pass

class YoutubeQuotaError(YoutubeUploadError):
    pass

class YoutubeNetworkError(YoutubeUploadError):
    pass


class YoutubeUploadInterrupted(Exception):
    """Do not inherit YoutubeUploadError — avoids @auto_retry re-running upload when the loop is shutting down."""

    pass

@dataclass
class AppEvent:
    command: str
    payload: Optional[Any] = None
