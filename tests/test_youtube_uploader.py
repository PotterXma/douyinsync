import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from utils.models import VideoRecord, ProxyConfig, YoutubeQuotaError, YoutubeUploadError, YoutubeNetworkError
from modules.youtube_uploader import YoutubeUploader

@pytest.fixture
def proxy_config():
    return ProxyConfig(http="http://127.0.0.1:1080", https="http://127.0.0.1:1080")

@pytest.fixture
def video_record():
    return VideoRecord(
        douyin_id="12345",
        title="Test Title",
        description="Test Tags #shorts",
        local_video_path="test_video.mp4",
        local_cover_path="test_cover.jpg"
    )

@pytest.mark.asyncio
async def test_youtube_uploader_initialization(proxy_config):
    uploader = YoutubeUploader(proxy_config=proxy_config)
    uploader.token = "fake_token"
    assert uploader.token == "fake_token"
    assert uploader.proxy_config == proxy_config

@pytest.mark.asyncio
@patch("modules.youtube_uploader.httpx.AsyncClient")
async def test_youtube_upload_success(mock_client, proxy_config, video_record, tmp_path):
    video_file = tmp_path / "test_video.mp4"
    video_file.write_bytes(b"mock video data")
    cover_file = tmp_path / "test_cover.jpg"
    cover_file.write_bytes(b"mock cover data")
    
    video_record.local_video_path = str(video_file)
    video_record.local_cover_path = str(cover_file)
    
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.headers = {"Location": "http://resumable-upload-url"}
    
    mock_put_resp = MagicMock()
    mock_put_resp.status_code = 200
    mock_put_resp.json.return_value = {"id": "youtube_vid_id"}
    
    mock_thumb_resp = MagicMock()
    mock_thumb_resp.status_code = 200
    
    mock_instance = AsyncMock()
    # 1. session post, 2. video chunk put, 3. thumbnail post.
    # We will mock the side_effect for post to handle different URL bases (upload vs thumbnail)
    
    async def mock_post(url, *args, **kwargs):
        if "uploadType=resumable" in str(url):
            return mock_post_resp
        return mock_thumb_resp
        
    mock_instance.post.side_effect = mock_post
    mock_instance.put.return_value = mock_put_resp
    
    mock_instance.__aenter__.return_value = mock_instance
    mock_instance.__aexit__.return_value = None
    mock_client.return_value = mock_instance
    
    uploader = YoutubeUploader(proxy_config=proxy_config)
    uploader.token = "fake_token"
    youtube_id = await uploader.upload(video_record)
    
    assert youtube_id == "youtube_vid_id"
    # httpx >= 0.28: proxy via mounts + AsyncHTTPTransport (no ``proxies=`` kwarg)
    mock_client.assert_called_once()
    call_kw = mock_client.call_args.kwargs
    assert "mounts" in call_kw
    mounts = call_kw["mounts"]
    assert "http://" in mounts and "https://" in mounts
    assert isinstance(mounts["http://"], httpx.AsyncHTTPTransport)

    # Ensure thumbnail was uploaded
    thumb_post_calls = [c for c in mock_instance.post.call_args_list if "thumbnails" in str(c[0][0])]
    assert len(thumb_post_calls) == 1


@pytest.mark.asyncio
async def test_upload_rejects_blank_token_without_file(tmp_path, proxy_config):
    video_file = tmp_path / "v.mp4"
    video_file.write_bytes(b"x")
    vr = VideoRecord(
        douyin_id="1",
        title="t",
        description="d",
        local_video_path=str(video_file),
        local_cover_path="",
    )
    missing = tmp_path / "no_such_token.json"
    uploader = YoutubeUploader(proxy_config=proxy_config, token=None, token_file=str(missing))
    with pytest.raises(YoutubeUploadError) as exc:
        await uploader.upload(vr)
    assert "Missing YouTube OAuth" in str(exc.value)


@pytest.mark.asyncio
@patch("modules.youtube_uploader.httpx.AsyncClient")
async def test_youtube_upload_file_not_found(mock_client, proxy_config, video_record):
    uploader = YoutubeUploader(proxy_config=proxy_config)
    uploader.token = "fake_token"
    video_record.local_video_path = "non_existent.mp4"
    
    with pytest.raises(FileNotFoundError):
        await uploader.upload(video_record)

@pytest.mark.asyncio
@patch("modules.youtube_uploader.httpx.AsyncClient")
async def test_youtube_upload_quota_error(mock_client, proxy_config, video_record, tmp_path):
    video_file = tmp_path / "test_video.mp4"
    video_file.write_bytes(b"mock video data")
    video_record.local_video_path = str(video_file)
    
    # Use authentic httpx Response instead of MagicMock for error testing
    req = httpx.Request("POST", "https://api")
    mock_post_resp = httpx.Response(
        status_code=403,
        json={
            "error": {
                "errors": [{"reason": "quotaExceeded"}],
                "message": "Quota exceeded"
            }
        },
        request=req
    )
    http_err = httpx.HTTPStatusError("403", request=req, response=mock_post_resp)
    
    mock_instance = AsyncMock()
    mock_instance.post.side_effect = http_err
    mock_instance.__aenter__.return_value = mock_instance
    mock_instance.__aexit__.return_value = None
    mock_client.return_value = mock_instance
    
    uploader = YoutubeUploader(proxy_config=proxy_config)
    uploader.token = "fake_token"
    with pytest.raises(YoutubeQuotaError):
        await uploader.upload(video_record)

@pytest.mark.asyncio
@patch("modules.youtube_uploader.httpx.AsyncClient")
async def test_youtube_network_error(mock_client, proxy_config, video_record, tmp_path):
    video_file = tmp_path / "test_video.mp4"
    video_file.write_bytes(b"mock video data")
    video_record.local_video_path = str(video_file)
    
    mock_instance = AsyncMock()
    mock_instance.post.side_effect = httpx.ConnectError("Network is down")
    mock_instance.__aenter__.return_value = mock_instance
    mock_instance.__aexit__.return_value = None
    mock_client.return_value = mock_instance
    
    uploader = YoutubeUploader(proxy_config=proxy_config)
    uploader.token = "fake_token"
    with pytest.raises(YoutubeNetworkError):
        await uploader.upload(video_record)
