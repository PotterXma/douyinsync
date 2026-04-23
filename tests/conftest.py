import pytest
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture
def mock_video_dao(monkeypatch):
    """统一 VideoDAO 静态方法 Mock 工厂。"""
    mock = MagicMock()
    mock.get_pending_videos.return_value = []
    mock.revert_zombies.return_value = 0
    monkeypatch.setattr("modules.scheduler.VideoDAO", mock)
    return mock

@pytest.fixture
def mock_notifier():
    notifier = MagicMock()
    notifier.push = MagicMock()
    notifier.push_daily_summary = MagicMock()
    return notifier
