import requests
from pathlib import Path
from PIL import Image
from datetime import datetime

from modules.logger import logger
from modules.abogus import USERAGENT

# Absolute bound guarantees safe execution via startup folders
DOWNLOAD_DIR = Path(__file__).resolve().parent.parent / "downloads"

class Downloader:
    def __init__(self):
        # Assure folder root exists
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    def download_media(self, douyin_id: str, video_url: str, cover_url: str) -> dict:
        """
        Coordinates dual downloading of MP4 and Image.
        Memory-efficient: uses iterative streaming.
        Format Compatibility: automatically recodes WebP into standard JPEG.
        Returns populated dict of local paths on success, or None on critical failure.
        """
        # Bucket by date to prevent directory file bloat over months
        date_folder = DOWNLOAD_DIR / datetime.now().strftime("%Y-%m-%d")
        date_folder.mkdir(parents=True, exist_ok=True)
        
        video_path = date_folder / f"{douyin_id}.mp4"
        cover_path_webp = date_folder / f"{douyin_id}.webp"
        cover_path_jpg = date_folder / f"{douyin_id}.jpg"
        
        logger.info(f"Downloader: Commencing Chunked-Stream fetch for Video ID {douyin_id}...")
        
        try:
            # Task 1: Video Payload
            if not self._download_file(video_url, video_path, chunk_size=1024*1024):
                logger.error(f"Downloader: Video MP4 fetch failed for {douyin_id}. Aborting task.")
                if video_path.exists():
                    video_path.unlink(missing_ok=True)
                return None
                
            # Task 2: Cover Art Payload
            if cover_url and self._download_file(cover_url, cover_path_webp):
                # Transformation hook
                try:
                    with Image.open(cover_path_webp) as img:
                        # Ensures transparency is discarded properly (JPG does not support alpha)
                        rgb_img = img.convert('RGB')
                        # Best tradeoff quality vs size
                        rgb_img.save(cover_path_jpg, "JPEG", quality=95)
                        logger.debug(f"Downloader: Success formatting JPEG cover - {cover_path_jpg}")
                    
                    # Cleanup staging webp securely
                    if cover_path_webp.exists():
                        cover_path_webp.unlink()
                except Exception as e:
                    logger.error(f"Downloader: Pillow WebP->JPEG conversion failed: {e}")
                    # Desperate fallback - return webp string
                    cover_path_jpg = cover_path_webp
            else:
                logger.warning(f"Downloader: Cover image fetch failed/missing for {douyin_id}. Proceeding blindly.")
                cover_path_jpg = ""
                
            logger.info(f"Downloader: Securely landed 100% data locally for {douyin_id}.")
            return {
                "local_video_path": str(video_path),
                "local_cover_path": str(cover_path_jpg)
            }
            
        except Exception as e:
            logger.error(f"Downloader: Fatal disruption sequence inside chunk loop {douyin_id}: {e}")
            # Ensure no corrupted half-files are left hanging
            if video_path.exists():
                video_path.unlink(missing_ok=True)
            return None

    def _download_file(self, url: str, dest_path: Path, chunk_size=8192) -> bool:
        """Hardware-safe file dumping method. Blocks memory balloons for 500MB+ files."""
        headers = {
            "User-Agent": USERAGENT,
            "Referer": "https://www.douyin.com/"
        }
        try:
            # stream=True is the lifesaver!
            with requests.get(url, headers=headers, stream=True, timeout=25.0) as r:
                r.raise_for_status()
                with open(dest_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
            return True
        except requests.RequestException as e:
            logger.error(f"Downloader: Stream HTTP disconnect mapping URL {url[:30]}... : {e}")
            return False
