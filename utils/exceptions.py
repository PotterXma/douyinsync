class BasePipelineError(Exception):
    """Base exception for all DouyinSync pipeline errors."""
    pass

class NetworkTimeoutError(BasePipelineError):
    """Raised when a non-fatal network timeout occurs."""
    pass

class YoutubeQuotaError(BasePipelineError):
    """Raised when the YouTube API quota is exceeded (HTTP 403)."""
    pass

class DouyinBlockError(BasePipelineError):
    """Raised when Douyin blocks the request (e.g., a_bogus signature validation fails)."""
    pass
