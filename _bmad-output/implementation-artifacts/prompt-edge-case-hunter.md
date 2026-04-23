You are an Edge Case Hunter. Review the diff below. Check for unhandled exceptions, race conditions, edge case inputs, boundary errors, and logical paths that may fail under unexpected conditions. Output findings as a Markdown list. Each finding: one-line title and evidence from the diff.

# Code Changes (Diff)

```python
# ==========================================
# File: utils/exceptions.py
# ==========================================
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

# ==========================================
# File: utils/decorators.py
# ==========================================
import time
import asyncio
import functools
import logging
import datetime
from typing import Callable, Tuple, Type

logger = logging.getLogger(__name__)

# Maximum retry attempts before a give_up state is assigned
MAX_RETRY_ATTEMPTS = 3


def auto_retry(
    max_retries: int = MAX_RETRY_ATTEMPTS,
    backoff_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """
    Decorator: Retries the wrapped function with exponential backoff on failure.
    After max_retries exhausted, the final exception is re-raised.

    Usage:
        @auto_retry(max_retries=3, exceptions=(NetworkTimeoutError,))
        async def fetch_something(url: str) -> dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                last_exc = None
                for attempt in range(max_retries):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as exc:
                        last_exc = exc
                        sleep_time = backoff_base ** attempt
                        logger.warning(
                            "auto_retry: attempt %s/%s failed for %s \u2014 %s. Retrying in %.1fs...",
                            attempt + 1, max_retries, func.__name__, exc, sleep_time
                        )
                        if attempt < max_retries - 1:
                            await asyncio.sleep(sleep_time)
                logger.error(
                    "auto_retry: %s exhausted all %s retries. Final error: %s",
                    func.__name__, max_retries, last_exc
                )
                raise last_exc
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                last_exc = None
                for attempt in range(max_retries):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as exc:
                        last_exc = exc
                        sleep_time = backoff_base ** attempt
                        logger.warning(
                            "auto_retry: attempt %s/%s failed for %s \u2014 %s. Retrying in %.1fs...",
                            attempt + 1, max_retries, func.__name__, exc, sleep_time
                        )
                        if attempt < max_retries - 1:
                            time.sleep(sleep_time)
                logger.error(
                    "auto_retry: %s exhausted all %s retries. Final error: %s",
                    func.__name__, max_retries, last_exc
                )
                raise last_exc
            return sync_wrapper
    return decorator


def _get_seconds_until_midnight_pst() -> float:
    """Helper to calculate seconds until next midnight PST."""
    now = datetime.datetime.now(datetime.timezone.utc)
    # PST is UTC-8
    pst_tz = datetime.timezone(datetime.timedelta(hours=-8))
    now_pst = now.astimezone(pst_tz)
    tomorrow_pst = now_pst + datetime.timedelta(days=1)
    midnight_pst = datetime.datetime(tomorrow_pst.year, tomorrow_pst.month, tomorrow_pst.day, tzinfo=pst_tz)
    return (midnight_pst - now).total_seconds()


def circuit_breaker(
    trip_on: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """
    Decorator: Trips immediately on the specified exception types, signaling
    quota-exhaustion or hard-block scenarios without retry.
    Forcefully suspends execution until the next chronological reset period.
    """
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except trip_on as exc:
                    logger.error(
                        "circuit_breaker: TRIPPED on %s in %s \u2014 %s. Operation suspended.",
                        type(exc).__name__, func.__name__, exc
                    )
                    sleep_time = _get_seconds_until_midnight_pst()
                    logger.warning("circuit_breaker: Sleeping for %.1f seconds until midnight PST...", sleep_time)
                    await asyncio.sleep(sleep_time)
                    raise
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except trip_on as exc:
                    logger.error(
                        "circuit_breaker: TRIPPED on %s in %s \u2014 %s. Operation suspended.",
                        type(exc).__name__, func.__name__, exc
                    )
                    sleep_time = _get_seconds_until_midnight_pst()
                    logger.warning("circuit_breaker: Sleeping for %.1f seconds until midnight PST...", sleep_time)
                    time.sleep(sleep_time)
                    raise
            return sync_wrapper
    return decorator

# ==========================================
# File: tests/test_resilience.py
# ==========================================
import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch
from utils.decorators import auto_retry, circuit_breaker
from utils.exceptions import NetworkTimeoutError, YoutubeQuotaError

@pytest.mark.asyncio
async def test_auto_retry_async_success():
    """Test that auto_retry succeeds on the second attempt."""
    mock_func = AsyncMock(side_effect=[NetworkTimeoutError("Timeout"), "Success"])
    
    @auto_retry(max_retries=3, backoff_base=0.1, exceptions=(NetworkTimeoutError,))
    async def retry_func():
        return await mock_func()
        
    result = await retry_func()
    assert result == "Success"
    assert mock_func.call_count == 2

@pytest.mark.asyncio
async def test_auto_retry_async_exhausted():
    """Test that auto_retry fails after max_retries."""
    mock_func = AsyncMock(side_effect=NetworkTimeoutError("Timeout"))
    
    @auto_retry(max_retries=3, backoff_base=0.1, exceptions=(NetworkTimeoutError,))
    async def retry_func():
        return await mock_func()
        
    with pytest.raises(NetworkTimeoutError):
        await retry_func()
        
    assert mock_func.call_count == 3

@pytest.mark.asyncio
async def test_circuit_breaker_async_youtube_quota():
    """Test that circuit_breaker suspends execution natively using asyncio.sleep."""
    mock_func = AsyncMock(side_effect=YoutubeQuotaError("Quota Exceeded"))
    
    @circuit_breaker(trip_on=(YoutubeQuotaError,))
    async def cb_func():
        return await mock_func()
        
    with pytest.raises(YoutubeQuotaError):
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            await cb_func()
            mock_sleep.assert_called_once()
            # Assert sleep time was passed
            sleep_args = mock_sleep.call_args[0]
            assert sleep_args[0] > 0

def test_auto_retry_sync_success():
    """Test that auto_retry works for sync functions as well."""
    from unittest.mock import Mock
    mock_func = Mock(side_effect=[NetworkTimeoutError("Timeout"), "Success"])
    
    @auto_retry(max_retries=3, backoff_base=0.1, exceptions=(NetworkTimeoutError,))
    def retry_func():
        return mock_func()
        
    result = retry_func()
    assert result == "Success"
    assert mock_func.call_count == 2
```
