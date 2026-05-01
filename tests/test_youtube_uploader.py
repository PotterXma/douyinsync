import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from utils.models import VideoRecord, ProxyConfig, YoutubeQuotaError, YoutubeUploadError, YoutubeNetworkError
from modules.youtube_uploader import YoutubeUploader

@pytest.fixture
def proxy_config():
    return ProxyConfig(http="http://127.0.0.1:1080", https="http://127.0.0.1:1080")

@pytest.fixture(autouse=True)
def _stub_upload_progress_writes(monkeypatch):
    """Avoid touching real SQLite when upload() pulses VideoDAO progress."""
    monkeypatch.setattr(
        "modules.youtube_uploader.VideoDAO.update_upload_progress",
        lambda *args, **kwargs: None,
    )


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

    resumable_posts = [c for c in mock_instance.post.call_args_list if "uploadType=resumable" in str(c[0][0])]
    assert len(resumable_posts) == 1
    meta = resumable_posts[0].kwargs.get("json") or resumable_posts[0][1].get("json")
    assert meta["snippet"]["title"] == "Test Title"
    assert "#shorts" not in (meta["snippet"].get("description") or "").lower()
    assert meta["snippet"].get("categoryId")
    assert meta["status"].get("privacyStatus") in ("public", "private", "unlisted")

    # httpx >= 0.28: proxy via mounts + AsyncHTTPTransport (no ``proxies=`` kwarg)
    mock_client.assert_called_once()
    call_kw = mock_client.call_args.kwargs
    assert "timeout" in call_kw
    assert call_kw.get("follow_redirects") is False
    assert "mounts" in call_kw
    mounts = call_kw["mounts"]
    assert "http://" in mounts and "https://" in mounts
    assert isinstance(mounts["http://"], httpx.AsyncHTTPTransport)

    # Default behavior: do NOT upload thumbnail (use YouTube default / first-frame-like thumbnail)
    thumb_post_calls = [c for c in mock_instance.post.call_args_list if "thumbnails" in str(c[0][0])]
    assert len(thumb_post_calls) == 0


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
async def test_youtube_upload_rejects_empty_file(proxy_config, video_record, tmp_path):
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    video_record.local_video_path = str(empty)
    uploader = YoutubeUploader(proxy_config=proxy_config)
    uploader.token = "fake_token"
    with pytest.raises(YoutubeUploadError) as exc:
        await uploader.upload(video_record)
    assert "empty" in str(exc.value).lower()


@pytest.mark.asyncio
@patch("modules.youtube_uploader.httpx.AsyncClient")
async def test_resumable_post_401_static_token_fails_fast(mock_client, proxy_config, video_record, tmp_path):
    """401 on session POST with static token must not burn 8 attempts."""
    video_file = tmp_path / "v.mp4"
    video_file.write_bytes(b"data")
    video_record.local_video_path = str(video_file)

    req = httpx.Request("POST", "https://www.googleapis.com/upload/youtube/v3/videos")
    resp401 = httpx.Response(401, request=req)
    err401 = httpx.HTTPStatusError("401", request=req, response=resp401)

    mock_instance = AsyncMock()
    mock_instance.post.side_effect = err401
    mock_instance.__aenter__.return_value = mock_instance
    mock_instance.__aexit__.return_value = None
    mock_client.return_value = mock_instance

    missing = tmp_path / "no_token.json"
    uploader = YoutubeUploader(
        proxy_config=proxy_config,
        token="static_only",
        token_file=str(missing),
    )
    with pytest.raises(YoutubeUploadError) as exc:
        await uploader.upload(video_record)
    assert "401" in str(exc.value)
    assert "refresh" in str(exc.value).lower()
    assert mock_instance.post.call_count == 1


@pytest.mark.asyncio
@patch("modules.youtube_uploader.httpx.AsyncClient")
async def test_youtube_chunk_401_without_refresh_raises_clear_error(mock_client, proxy_config, video_record, tmp_path):
    """Static config token + HTTP 401 must not spin until iteration guard."""
    video_file = tmp_path / "v.mp4"
    video_file.write_bytes(b"data")
    video_record.local_video_path = str(video_file)

    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.headers = {"Location": "http://resumable-upload-url"}

    mock_put_401 = MagicMock()
    mock_put_401.status_code = 401

    mock_instance = AsyncMock()
    mock_instance.post.return_value = mock_post_resp
    mock_instance.put.return_value = mock_put_401
    mock_instance.__aenter__.return_value = mock_instance
    mock_instance.__aexit__.return_value = None
    mock_client.return_value = mock_instance

    missing_token_json = tmp_path / "no_token.json"
    uploader = YoutubeUploader(
        proxy_config=proxy_config,
        token="static_only_token",
        token_file=str(missing_token_json),
    )
    with pytest.raises(YoutubeUploadError) as exc:
        await uploader.upload(video_record)
    assert "401" in str(exc.value)
    assert "refresh" in str(exc.value).lower()
    assert mock_instance.put.call_count == 1


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
@patch("modules.youtube_uploader.VideoDAO.count_uploaded_for_account", return_value=0)
@patch("modules.youtube_uploader.stamp_upload_sequence_on_cover", return_value=None)
@patch("modules.youtube_uploader.config.get")
@patch("modules.youtube_uploader.httpx.AsyncClient")
async def test_youtube_upload_thumbnail_failure_still_returns_id(
    mock_client, mock_config_get, _stamp, _count, proxy_config, video_record, tmp_path
):
    """Thumbnail errors must not retry the resumable body upload (would create duplicate videos)."""
    def _fake_get(key, default=None):
        if key == "youtube_upload_thumbnail":
            return True
        return default
    mock_config_get.side_effect = _fake_get

    video_file = tmp_path / "test_video.mp4"
    video_file.write_bytes(b"mock video data")
    cover_file = tmp_path / "test_cover.jpg"
    cover_file.write_bytes(b"cover")
    video_record.local_video_path = str(video_file)
    video_record.local_cover_path = str(cover_file)

    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.headers = {"Location": "http://resumable-upload-url"}

    mock_put_resp = MagicMock()
    mock_put_resp.status_code = 200
    mock_put_resp.json.return_value = {"id": "youtube_vid_id"}

    mock_instance = AsyncMock()

    async def mock_post(url, *args, **kwargs):
        if "uploadType=resumable" in str(url):
            return mock_post_resp
        req = httpx.Request("POST", str(url))
        return httpx.Response(400, request=req)

    mock_instance.post.side_effect = mock_post
    mock_instance.put.return_value = mock_put_resp
    mock_instance.__aenter__.return_value = mock_instance
    mock_instance.__aexit__.return_value = None
    mock_client.return_value = mock_instance

    uploader = YoutubeUploader(proxy_config=proxy_config)
    uploader.token = "fake_token"
    youtube_id = await uploader.upload(video_record)
    assert youtube_id == "youtube_vid_id"
    resumable_posts = [c for c in mock_instance.post.call_args_list if "uploadType=resumable" in str(c[0][0])]
    assert len(resumable_posts) == 1
    assert mock_instance.put.call_count == 1


@pytest.mark.asyncio
@patch("modules.youtube_uploader.config.get")
@patch("modules.youtube_uploader.httpx.AsyncClient")
async def test_youtube_upload_chunked_308_then_201(mock_client, mock_config_get, proxy_config, video_record, tmp_path):
    """Large files use chunked PUT; intermediate success is HTTP 308 with Range header."""
    chunk = 256 * 1024

    def _cfg(key, default=None):
        if key == "youtube_upload_chunk_size_bytes":
            return chunk
        return default

    mock_config_get.side_effect = _cfg

    video_file = tmp_path / "chunked.bin"
    video_file.write_bytes(b"z" * (chunk + 50))
    video_record.local_video_path = str(video_file)
    video_record.local_cover_path = ""

    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.headers = {"Location": "http://resumable-upload-url"}

    mock_put_308 = MagicMock()
    mock_put_308.status_code = 308
    mock_put_308.headers = {"Range": "bytes=0-%s" % (chunk - 1)}

    mock_put_201 = MagicMock()
    mock_put_201.status_code = 201
    mock_put_201.json.return_value = {"id": "vid_chunked"}

    mock_instance = AsyncMock()
    mock_instance.post.return_value = mock_post_resp
    mock_instance.put.side_effect = [mock_put_308, mock_put_201]
    mock_instance.__aenter__.return_value = mock_instance
    mock_instance.__aexit__.return_value = None
    mock_client.return_value = mock_instance

    uploader = YoutubeUploader(proxy_config=proxy_config)
    uploader.token = "fake_token"
    yt_id = await uploader.upload(video_record)
    assert yt_id == "vid_chunked"
    assert mock_instance.put.call_count == 2


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


def test_parse_retry_after_header_numeric():
    from modules.youtube_uploader import _parse_retry_after_header

    assert _parse_retry_after_header("120") == 120.0
    assert _parse_retry_after_header(None) is None
    assert _parse_retry_after_header("") is None
    assert _parse_retry_after_header("not-a-date") is None


def test_retry_after_sleep_seconds():
    from modules.youtube_uploader import _retry_after_sleep_seconds

    r = MagicMock()
    r.headers = {"Retry-After": "15"}
    assert _retry_after_sleep_seconds(r, 2.0) == 15.0
    assert _retry_after_sleep_seconds(r, 30.0) == 30.0

    r2 = MagicMock()
    r2.headers = {}
    assert _retry_after_sleep_seconds(r2, 8.0) == 8.0
