from dataclasses import dataclass, field
from typing import List, Optional

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
