"""
utils/decorators.py

Retry and circuit-breaker decorators for external network operations.
These are sync-compatible and wrap both sync and async callable patterns.
"""
import time
import asyncio
import functools
import inspect
import logging
import datetime
from typing import Callable, Tuple, Type
from utils.exceptions import BasePipelineError

logger = logging.getLogger(__name__)

# Maximum retry attempts before a give_up state is assigned
MAX_RETRY_ATTEMPTS = 3


def auto_retry(
    max_retries: int = MAX_RETRY_ATTEMPTS,
    backoff_base: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (BasePipelineError,),
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
        actual_retries = max(1, max_retries)
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                last_exc = None
                for attempt in range(actual_retries):
                    try:
                        return await func(*args, **kwargs)
                    except exceptions as exc:
                        last_exc = exc
                        sleep_time = backoff_base ** attempt
                        logger.warning(
                            "auto_retry: attempt %s/%s failed for %s \u2014 %s. Retrying in %.1fs...",
                            attempt + 1, actual_retries, func.__name__, exc, sleep_time
                        )
                        if attempt < actual_retries - 1:
                            await asyncio.sleep(sleep_time)
                logger.error(
                    "auto_retry: %s exhausted all %s retries. Final error: %s",
                    func.__name__, actual_retries, last_exc
                )
                raise last_exc
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                last_exc = None
                for attempt in range(actual_retries):
                    try:
                        return func(*args, **kwargs)
                    except exceptions as exc:
                        last_exc = exc
                        sleep_time = backoff_base ** attempt
                        logger.warning(
                            "auto_retry: attempt %s/%s failed for %s \u2014 %s. Retrying in %.1fs...",
                            attempt + 1, actual_retries, func.__name__, exc, sleep_time
                        )
                        if attempt < actual_retries - 1:
                            time.sleep(sleep_time)
                logger.error(
                    "auto_retry: %s exhausted all %s retries. Final error: %s",
                    func.__name__, actual_retries, last_exc
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
    trip_on: Tuple[Type[Exception], ...] = (BasePipelineError,),
) -> Callable:
    """
    Decorator: Trips immediately on the specified exception types, signaling
    quota-exhaustion or hard-block scenarios without retry.
    Forcefully suspends execution until the next chronological reset period.
    """
    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):
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
