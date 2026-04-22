import pytest
import asyncio
from unittest.mock import MagicMock, patch, call, AsyncMock
from modules.scheduler import PipelineCoordinator
from utils.models import VideoRecord, ProxyConfig

@pytest.fixture
def mock_dependencies():
    with patch('modules.scheduler.VideoDAO') as mock_dao, \
         patch('modules.scheduler.DouyinFetcher') as mock_fetcher, \
         patch('modules.scheduler.Downloader') as mock_downloader, \
         patch('modules.scheduler.YoutubeUploader') as mock_uploader, \
         patch('modules.scheduler.config') as mock_config, \
         patch('modules.scheduler.logger') as mock_logger:
        
        # Configure mock returns
        from unittest.mock import AsyncMock
        mock_fetcher.return_value.fetch_user_posts = AsyncMock(return_value=([], 0, False))
        mock_fetcher.return_value.refresh_video_url = AsyncMock(return_value=None)
        
        mock_uploader.return_value.upload = AsyncMock(return_value="yt_123")
        mock_dao.revert_zombies.return_value = 0
        
        yield {
            'dao': mock_dao,
            'fetcher': mock_fetcher,
            'downloader': mock_downloader,
            'uploader': mock_uploader,
            'config': mock_config,
            'logger': mock_logger
        }

@pytest.mark.asyncio
async def test_pipeline_async_flow(mock_dependencies):
    # Setup Coordinator
    coordinator = PipelineCoordinator()
    
    # Mock network passing
    coordinator.check_network = MagicMock(return_value=True)
    coordinator.sweeper.check_preflight_space = MagicMock(return_value=True)
    
    # Simulate pending video in DB
    mock_video = MagicMock(spec=VideoRecord)
    mock_video.douyin_id = "test_dy_1"
    mock_video.title = "test_title"
    mock_video.description = "test_desc"
    mock_video.video_url = "test_vid_url"
    mock_video.cover_url = "test_cover_url"
    
    mock_dependencies['dao'].get_pending_videos.return_value = [mock_video]
    mock_dependencies['dao'].get_uploadable_videos.return_value = []
    mock_dependencies['dao'].get_uploaded_today_count.return_value = 0
    
    # Configure downloader response
    mock_dependencies['downloader'].return_value.download_media = AsyncMock(return_value={
        'local_video_path': '/mock/vid.mp4',
        'local_cover_path': '/mock/cov.jpg',
        'ocr_text': ''
    })
    
    # Configure config for loop
    mock_dependencies['config'].get.side_effect = lambda k, default=None: {
        "douyin_accounts": [],
        "daily_upload_limit": 10,
        "max_videos_per_run": 1,
        "youtube_proxy": "http://user:pass@router:1234",
        "youtube_api_token": "mocked_oauth_token"
    }.get(k, default)
    
    # Run loop
    await coordinator._run_async_cycle()
    
    # Assert DB got hit for updating status
    mock_dependencies['dao'].update_status.assert_any_call('test_dy_1', 'downloaded', {'local_video_path': '/mock/vid.mp4', 'local_cover_path': '/mock/cov.jpg'})
    mock_dependencies['dao'].update_status.assert_any_call('test_dy_1', 'uploaded')

def test_pipeline_lock_prevents_overlap(mock_dependencies):
    coordinator = PipelineCoordinator()
    
    # Acquire the lock manually to simulate an running job
    coordinator._pipeline_lock.acquire(blocking=False)
    
    # Patch asyncio.run so we can determine if the async cycle was run
    with patch('modules.scheduler.asyncio.run') as mock_async_run:
        coordinator.primary_sync_job()
        
        # Should not be called because it's locked
        mock_async_run.assert_not_called()
        
    # Free the lock and test again
    coordinator._pipeline_lock.release()
    with patch('modules.scheduler.asyncio.run') as mock_async_run:
        coordinator.primary_sync_job()
        mock_async_run.assert_called_once()

def test_scheduler_start_adds_jobs(mock_dependencies):
    coordinator = PipelineCoordinator()
    coordinator.scheduler = MagicMock()
    
    mock_dependencies['config'].get.side_effect = lambda k, default=None: {
        "sync_interval_minutes": 45
    }.get(k, default)
    
    # Patch start to prevent datetime module mock interference in start() logic
    with patch('modules.scheduler.BackgroundScheduler.start'):
        coordinator.start()
        
        # Verify 4 jobs added (primary, janitor, summary, immediate run)
        assert coordinator.scheduler.add_job.call_count == 4
        coordinator.scheduler.start.assert_called_once()

