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
