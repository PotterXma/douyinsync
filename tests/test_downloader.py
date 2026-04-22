import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

from modules.downloader import Downloader

class TestDownloader:
    @pytest.fixture(autouse=True)
    def setup_method(self, tmp_path):
        """Setup test environment before each test."""
        self.downloader = Downloader()
        self.test_dir = tmp_path
        
        # Patch DOWNLOAD_DIR securely to temp folder
        patcher = patch("modules.downloader.DOWNLOAD_DIR", tmp_path)
        self.mock_dir = patcher.start()
        yield
        patcher.stop()

    @pytest.mark.asyncio
    async def test_download_file_streams_chunks_not_all_at_once(self):
        """
        _download_file must use aiter_bytes (chunked streaming), never load
        the entire response body into memory in one shot.
        """
        chunk_data = [b"chunk1", b"chunk2"]
        dest = Path(self.test_dir) / "test_video.mp4"
        
        async def mock_aiter_bytes(*args, **kwargs):
            for c in chunk_data:
                yield c
                
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-length": "12"}
        mock_response.aiter_bytes = mock_aiter_bytes
        
        mock_stream_ctx = MagicMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_response)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=None)
        
        mock_client = MagicMock()
        mock_client.stream.return_value = mock_stream_ctx
        
        mock_client_ctx = MagicMock()
        mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client_ctx.__aexit__ = AsyncMock(return_value=None)
        
        with patch("modules.downloader.httpx.AsyncClient", return_value=mock_client_ctx):
            result = await self.downloader._download_file("http://fake/vid.mp4", dest)
            
        assert result is True
        assert dest.exists()
        assert dest.read_bytes() == b"chunk1chunk2"

    @pytest.mark.asyncio
    async def test_download_file_returns_false_on_network_error(self):
        """_download_file must return False and leave no partial file on connection error."""
        import httpx
        dest = Path(self.test_dir) / "corrupt_video.mp4"
        
        mock_client = AsyncMock()
        mock_client.stream.side_effect = httpx.RequestError("timeout")
        mock_client_ctx = AsyncMock()
        mock_client_ctx.__aenter__.return_value = mock_client
        
        with patch("modules.downloader.httpx.AsyncClient", return_value=mock_client_ctx):
            with patch("modules.downloader.asyncio.sleep", new_callable=AsyncMock): # Speed up retry delays
                result = await self.downloader._download_file("http://fake/bad.mp4", dest)
            
        assert result is False
        assert not dest.exists()

    @pytest.mark.asyncio
    async def test_download_file_aborts_on_403(self):
        """403 Forbidden from the CDN must cause immediate abort (CDN link expired)."""
        import httpx
        dest = Path(self.test_dir) / "forbidden_video.mp4"
        
        forbidden_req = httpx.Request("GET", "http://fake")
        forbidden_resp = httpx.Response(403, request=forbidden_req)
        
        mock_client = AsyncMock()
        mock_client.stream.side_effect = httpx.HTTPStatusError("403", request=forbidden_req, response=forbidden_resp)
        mock_client_ctx = AsyncMock()
        mock_client_ctx.__aenter__.return_value = mock_client
        
        with patch("modules.downloader.httpx.AsyncClient", return_value=mock_client_ctx):
            result = await self.downloader._download_file("http://fake/forbidden", dest)
            
        assert result is False

    @pytest.mark.asyncio
    async def test_download_media_returns_none_on_video_failure(self):
        """
        If the mp4 download fails, download_media must return None
        and must clean up any partial file.
        """
        with patch.object(self.downloader, "_download_file", new_callable=AsyncMock, return_value=False):
            result = await self.downloader.download_media("999", "http://bad/vid.mp4", "")
            
        assert result is None

    @pytest.mark.asyncio
    async def test_download_media_returns_path_dict_on_success(self):
        """
        download_media must return a dict with local_video_path and local_cover_path
        when both downloads succeed (cover conversion is tested independently).
        """
        async def fake_download(url: str, dest: Path, **kwargs) -> bool:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"FAKE_CONTENT")
            return True
            
        with patch.object(self.downloader, "_download_file", new_callable=AsyncMock, side_effect=fake_download):
            # Patch image processing sync blocking method to avoid complex pillow mock
            # since we're just testing the orchestration
            with patch.object(self.downloader, "_process_image_sync", return_value=("OCR_RES", "/mock/path/final_yt.jpg")):
                result = await self.downloader.download_media(
                    "DY_OK_001",
                    "http://fake/vid.mp4",
                    "http://fake/cover.webp",
                )
                
        assert result is not None
        assert "local_video_path" in result
        assert result["local_video_path"].endswith("DY_OK_001.mp4")
        assert result["local_cover_path"] == str(Path("/mock/path/final_yt.jpg"))
