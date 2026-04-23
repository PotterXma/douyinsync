import pytest
import asyncio
from unittest.mock import MagicMock, patch, call, AsyncMock
from modules.scheduler import PipelineCoordinator
from utils.models import VideoRecord, ProxyConfig


@pytest.fixture(autouse=True)
def _no_real_apscheduler():
    """Never spin a real BackgroundScheduler in this module (avoids gc-time coroutine warnings)."""
    with patch("modules.scheduler.BackgroundScheduler", return_value=MagicMock()):
        yield


@pytest.fixture
def mock_dependencies():
    with patch('modules.scheduler.VideoDAO') as mock_dao, \
         patch('modules.scheduler.DouyinFetcher') as mock_fetcher, \
         patch('modules.scheduler.Downloader') as mock_downloader, \
         patch('modules.scheduler.YoutubeUploader') as mock_uploader, \
         patch('modules.scheduler.config') as mock_config, \
         patch('modules.scheduler.logger') as mock_logger, \
         patch('modules.scheduler.BarkNotifier') as mock_notifier, \
         patch('utils.network.preflight_network_check', new_callable=AsyncMock) as mock_network_check:
        
        # Configure mock returns
        mock_fetcher.return_value.fetch_user_posts = AsyncMock(return_value=([], 0, False))
        mock_fetcher.return_value.refresh_video_url = AsyncMock(return_value=None)
        
        mock_config.get.side_effect = lambda k, default=None: {
            "douyin_accounts": [],
            "daily_upload_limit": 10,
            "max_videos_per_run": 5,
            "youtube_proxy": "http://user:pass@router:1234",
            "youtube_api_token": "mocked_oauth_token",
            "sync_schedule_mode": "interval",
            "sync_interval_minutes": 60,
        }.get(k, default)
        mock_dao.get_uploaded_today_count.return_value = 0
        
        mock_uploader.return_value.upload = AsyncMock(return_value="yt_123")
        mock_dao.revert_zombies.return_value = 0
        mock_dao.prepare_for_force_manual_retry = MagicMock(return_value=0)
        mock_network_check.return_value = True
        
        yield {
            'dao': mock_dao,
            'fetcher': mock_fetcher,
            'downloader': mock_downloader,
            'uploader': mock_uploader,
            'config': mock_config,
            'logger': mock_logger,
            'notifier': mock_notifier,
            'network_check': mock_network_check
        }

@pytest.mark.asyncio
async def test_force_retry_bypass_calls_prepare_and_uploadable_flag(mock_dependencies):
    coordinator = PipelineCoordinator()
    coordinator.sweeper.check_preflight_space = MagicMock(return_value=True)
    mock_dependencies["dao"].get_pending_videos.return_value = []
    mock_dependencies["dao"].get_uploadable_videos.return_value = []
    mock_dependencies["dao"].get_uploaded_today_count.return_value = 0
    mock_dependencies["dao"].prepare_for_force_manual_retry.return_value = 2

    await coordinator._run_async_cycle(force_retry_bypass=True)

    mock_dependencies["dao"].prepare_for_force_manual_retry.assert_called_once()
    mock_dependencies["dao"].get_uploadable_videos.assert_called()
    assert mock_dependencies["dao"].get_uploadable_videos.call_args.kwargs.get("ignore_retry_cap") is True


@pytest.mark.asyncio
async def test_pipeline_async_flow(mock_dependencies):
    # Setup Coordinator
    coordinator = PipelineCoordinator()
    
    # Mock sweeping passing
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
        "youtube_api_token": "mocked_oauth_token",
        "sync_schedule_mode": "interval",
        "sync_interval_minutes": 60,
    }.get(k, default)
    
    # Run loop
    await coordinator._run_async_cycle()
    
    # Assert DB got hit for updating status
    mock_dependencies['dao'].update_status.assert_any_call(
        'test_dy_1',
        'downloaded',
        {'local_video_path': '/mock/vid.mp4', 'local_cover_path': '/mock/cov.jpg', 'retry_count': 0},
    )
    mock_dependencies['dao'].update_status.assert_any_call('test_dy_1', 'uploaded')

def test_pipeline_lock_prevents_overlap(mock_dependencies):
    coordinator = PipelineCoordinator()

    # Simulate an overlapping run: primary_sync_job returns before asyncio.run when lock not acquired.
    coordinator._pipeline_lock.acquire(blocking=False)
    coordinator.primary_sync_job()
    warning_call_args = mock_dependencies["logger"].warning.call_args[0][0]
    assert "already running" in warning_call_args or "Skipping duplicate" in warning_call_args

    coordinator._pipeline_lock.release()
    # Must not leave a coroutine from _run_async_cycle() un-awaited when patching asyncio.run.
    real_run = asyncio.run
    with patch("modules.scheduler.asyncio.run", side_effect=lambda coro: real_run(coro)) as mock_async_run:
        coordinator.primary_sync_job()
        mock_async_run.assert_called_once()

def test_scheduler_start_adds_jobs(mock_dependencies):
    coordinator = PipelineCoordinator()
    coordinator.scheduler = MagicMock()
    
    mock_dependencies['config'].get.side_effect = lambda k, default=None: {
        "sync_interval_minutes": 45,
        "sync_schedule_mode": "interval",
    }.get(k, default)
    
    # Patch start to prevent datetime module mock interference in start() logic
    with patch('modules.scheduler.BackgroundScheduler.start'):
        coordinator.start()
        
        # Verify 4 jobs added (primary, janitor, summary, immediate run)
        assert coordinator.scheduler.add_job.call_count == 4
        coordinator.scheduler.start.assert_called_once()


def test_scheduler_start_clock_mode_adds_one_job_per_time(mock_dependencies):
    coordinator = PipelineCoordinator()
    coordinator.scheduler = MagicMock()

    mock_dependencies["config"].get.side_effect = lambda k, default=None: {
        "sync_schedule_mode": "clock",
        "sync_clock_times": ["09:00", "14:30"],
        "sync_interval_minutes": 60,
    }.get(k, default)

    with patch("modules.scheduler.BackgroundScheduler.start"):
        coordinator.start()

    assert coordinator.scheduler.add_job.call_count == 5

def test_apply_primary_schedule_removes_primary_jobs(mock_dependencies):
    coordinator = PipelineCoordinator()
    coordinator.scheduler = MagicMock()
    j1 = MagicMock()
    j1.id = "primary_sync_0_0900"
    j2 = MagicMock()
    j2.id = "janitor_sync"
    coordinator.scheduler.get_jobs.return_value = [j1, j2]

    mock_dependencies["config"].get.side_effect = lambda k, default=None: {
        "sync_schedule_mode": "interval",
        "sync_interval_minutes": 15,
    }.get(k, default)

    coordinator.apply_primary_schedule()

    coordinator.scheduler.remove_job.assert_called_once_with("primary_sync_0_0900")
    assert coordinator.scheduler.add_job.call_count >= 1


def test_scheduler_shutdown_waits_for_job():
    from unittest.mock import MagicMock
    coordinator = PipelineCoordinator()
    coordinator.scheduler = MagicMock()
    
    coordinator.shutdown()
    
    # Verify the shutdown waits for job completion
    coordinator.scheduler.shutdown.assert_called_once_with(wait=True)

@pytest.mark.asyncio
async def test_circuit_breaker_trips_on_quota_error(mock_dependencies):
    from utils.models import YoutubeQuotaError
    import time
    coordinator = PipelineCoordinator()
    mock_dependencies['config'].get.side_effect = lambda k, default=None: {
        "douyin_accounts": ["user1"],
        "daily_upload_limit": 10,
        "max_videos_per_run": 10,
        "sync_schedule_mode": "interval",
        "sync_interval_minutes": 60,
    }.get(k, default)
    mock_dependencies['dao'].get_uploaded_today_count.return_value = 0
    coordinator.sweeper.check_preflight_space = MagicMock(return_value=True)
    
    mock_dependencies['uploader'].return_value.upload.side_effect = YoutubeQuotaError("Quota exceeded")
    
    mock_video = MagicMock(spec=VideoRecord)
    mock_video.douyin_id = "test_quota_fail_1"
    mock_dependencies['dao'].get_pending_videos.return_value = [mock_video]
    mock_dependencies['dao'].get_uploadable_videos.return_value = []
    
    mock_dependencies['downloader'].return_value.download_media = AsyncMock(return_value={
        'local_video_path': '/mock/vid.mp4',
        'local_cover_path': '/mock/cov.jpg'
    })
    
    now = time.time()
    await coordinator._run_async_cycle()
    
    assert coordinator.youtube_quota_exceeded_until >= now + 86400
    mock_dependencies['dao'].update_status.assert_any_call('test_quota_fail_1', 'downloaded')
    mock_dependencies['notifier'].return_value.push.assert_called()

@pytest.mark.asyncio
async def test_circuit_breaker_blocks_subsequent_uploads(mock_dependencies):
    import time
    coordinator = PipelineCoordinator()
    mock_dependencies['config'].get.side_effect = lambda k, default=None: {
        "douyin_accounts": ["user1"],
        "daily_upload_limit": 10,
        "max_videos_per_run": 10,
        "sync_schedule_mode": "interval",
        "sync_interval_minutes": 60,
    }.get(k, default)
    mock_dependencies['dao'].get_uploaded_today_count.return_value = 0
    coordinator.sweeper.check_preflight_space = MagicMock(return_value=True)
    
    coordinator.youtube_quota_exceeded_until = time.time() + 86400
    
    mock_video = MagicMock(spec=VideoRecord)
    mock_video.douyin_id = "test_quota_blocked_1"
    mock_dependencies['dao'].get_pending_videos.return_value = [mock_video]
    mock_dependencies['dao'].get_uploadable_videos.return_value = []
    
    mock_dependencies['downloader'].return_value.download_media = AsyncMock(return_value={
        'local_video_path': '/mock/vid2.mp4',
        'local_cover_path': '/mock/cov2.jpg'
    })
    
    await coordinator._run_async_cycle()
    mock_dependencies['uploader'].return_value.upload.assert_not_called()

@pytest.mark.asyncio
async def test_circuit_breaker_resets_after_24_hours(mock_dependencies):
    import time
    coordinator = PipelineCoordinator()
    mock_dependencies['config'].get.side_effect = lambda k, default=None: {
        "douyin_accounts": ["user1"],
        "daily_upload_limit": 10,
        "max_videos_per_run": 10,
        "sync_schedule_mode": "interval",
        "sync_interval_minutes": 60,
    }.get(k, default)
    mock_dependencies['dao'].get_uploaded_today_count.return_value = 0
    coordinator.sweeper.check_preflight_space = MagicMock(return_value=True)
    
    coordinator.youtube_quota_exceeded_until = time.time() - 86400
    
    mock_video = MagicMock(spec=VideoRecord)
    mock_video.douyin_id = "test_quota_ok_1"
    mock_dependencies['dao'].get_pending_videos.return_value = [mock_video]
    mock_dependencies['dao'].get_uploadable_videos.return_value = []
    
    mock_dependencies['downloader'].return_value.download_media = AsyncMock(return_value={
        'local_video_path': '/mock/vid3.mp4',
        'local_cover_path': '/mock/cov3.jpg'
    })
    
    await coordinator._run_async_cycle()
    mock_dependencies['uploader'].return_value.upload.assert_called_once()

@pytest.mark.asyncio
async def test_preflight_network_probe_fail_skips_cycle(mock_dependencies):
    coordinator = PipelineCoordinator()
    mock_dependencies['network_check'].return_value = False
    
    await coordinator._run_async_cycle()
    
    # Notice: we should assert that logger was called.
    mock_dependencies['logger'].warning.assert_any_call("PipelineCoordinator: Offline state detected. Aborting this sync cycle safely.")
    mock_dependencies['dao'].get_pending_videos.assert_not_called()


@pytest.mark.asyncio
async def test_download_failure_requeues_as_pending(mock_dependencies):
    coordinator = PipelineCoordinator()
    coordinator.sweeper.check_preflight_space = MagicMock(return_value=True)
    mock_video = MagicMock(spec=VideoRecord)
    mock_video.douyin_id = "dy_dl_pending"
    mock_video.retry_count = 0
    mock_video.title = "t"
    mock_video.description = "d"
    mock_video.video_url = "u"
    mock_video.cover_url = "c"
    mock_dependencies["dao"].get_pending_videos.return_value = [mock_video]
    mock_dependencies["dao"].get_uploadable_videos.return_value = []
    mock_dependencies["downloader"].return_value.download_media = AsyncMock(return_value=None)
    mock_dependencies["config"].get.side_effect = lambda k, default=None: {
        "douyin_accounts": [],
        "daily_upload_limit": 10,
        "max_videos_per_run": 1,
        "youtube_proxy": "",
        "youtube_api_token": "tok",
        "sync_schedule_mode": "interval",
        "sync_interval_minutes": 60,
    }.get(k, default)
    await coordinator._run_async_cycle()
    mock_dependencies["dao"].update_status.assert_any_call(
        "dy_dl_pending",
        "pending",
        {"retry_count": 1, "local_video_path": None, "local_cover_path": None},
    )
    mock_dependencies["uploader"].return_value.upload.assert_not_called()


@pytest.mark.asyncio
async def test_download_failure_third_strike_give_up(mock_dependencies):
    coordinator = PipelineCoordinator()
    coordinator.sweeper.check_preflight_space = MagicMock(return_value=True)
    mock_video = MagicMock(spec=VideoRecord)
    mock_video.douyin_id = "dy_dl_giveup"
    mock_video.retry_count = 2
    mock_video.title = "t"
    mock_video.description = "d"
    mock_video.video_url = "u"
    mock_video.cover_url = "c"
    mock_dependencies["dao"].get_pending_videos.return_value = [mock_video]
    mock_dependencies["dao"].get_uploadable_videos.return_value = []
    mock_dependencies["downloader"].return_value.download_media = AsyncMock(return_value=None)
    mock_dependencies["config"].get.side_effect = lambda k, default=None: {
        "douyin_accounts": [],
        "daily_upload_limit": 10,
        "max_videos_per_run": 1,
        "youtube_proxy": "",
        "youtube_api_token": "tok",
        "sync_schedule_mode": "interval",
        "sync_interval_minutes": 60,
    }.get(k, default)
    await coordinator._run_async_cycle()
    mock_dependencies["dao"].update_status.assert_any_call(
        "dy_dl_giveup",
        "give_up",
        {"retry_count": 3, "local_video_path": None, "local_cover_path": None},
    )


@pytest.mark.asyncio
async def test_first_upload_empty_youtube_id_marks_failed(mock_dependencies):
    coordinator = PipelineCoordinator()
    coordinator.sweeper.check_preflight_space = MagicMock(return_value=True)
    mock_video = MagicMock(spec=VideoRecord)
    mock_video.douyin_id = "dy_up_fail"
    mock_video.retry_count = 0
    mock_video.title = "t"
    mock_video.description = "d"
    mock_video.video_url = "u"
    mock_video.cover_url = "c"
    mock_dependencies["dao"].get_pending_videos.return_value = [mock_video]
    mock_dependencies["dao"].get_uploadable_videos.return_value = []
    mock_dependencies["downloader"].return_value.download_media = AsyncMock(
        return_value={
            "local_video_path": "/mock/v.mp4",
            "local_cover_path": "/mock/c.jpg",
            "ocr_text": "",
        }
    )
    mock_dependencies["uploader"].return_value.upload = AsyncMock(return_value=None)
    mock_dependencies["config"].get.side_effect = lambda k, default=None: {
        "douyin_accounts": [],
        "daily_upload_limit": 10,
        "max_videos_per_run": 1,
        "youtube_proxy": "",
        "youtube_api_token": "tok",
        "sync_schedule_mode": "interval",
        "sync_interval_minutes": 60,
    }.get(k, default)
    await coordinator._run_async_cycle()
    mock_dependencies["dao"].update_status.assert_any_call("dy_up_fail", "failed", {"retry_count": 1})
