import os
import sys
import time
import asyncio
from pathlib import Path
from datetime import datetime

import httpx
import aiofiles
from PIL import Image

from modules.logger import logger
from modules.abogus import USERAGENT
from modules.config_manager import config

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys.executable).parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

DOWNLOAD_DIR = PROJECT_ROOT / "downloads"

class Downloader:
    def __init__(self):
        # Assure folder root exists
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    async def download_media(self, douyin_id: str, video_url: str, cover_url: str) -> dict:
        """
        Coordinates dual downloading of MP4 and Image.
        Memory-efficient: uses async iterative streaming via httpx and aiofiles.
        Format Compatibility: automatically recodes WebP into standard JPEG asynchronously via thread pool.
        Returns populated dict of local paths on success, or None on critical failure.
        """
        # Bucket by date to prevent directory file bloat over months
        date_folder = DOWNLOAD_DIR / datetime.now().strftime("%Y-%m-%d")
        date_folder.mkdir(parents=True, exist_ok=True)
        
        video_path = date_folder / f"{douyin_id}.mp4"
        cover_path_webp = date_folder / f"{douyin_id}.webp"
        cover_path_jpg = date_folder / f"{douyin_id}.jpg"
        
        logger.info("Downloader: Commencing Chunked-Stream fetch for Video ID %s...", douyin_id)
        
        try:
            # Task 1: Video Payload
            if not await self._download_file(video_url, video_path, chunk_size=1048576):
                logger.error("Downloader: Video MP4 fetch failed for %s. Aborting task.", douyin_id)
                if video_path.exists():
                    video_path.unlink(missing_ok=True)
                return None
                
            # Task 2: Cover Art Payload
            ocr_text = ""
            if cover_url and await self._download_file(cover_url, cover_path_webp):
                # Transformation hook
                try:
                    ocr_text, final_cover_jpg = await asyncio.to_thread(
                        self._process_image_sync,
                        str(cover_path_webp),
                        str(cover_path_jpg),
                        douyin_id,
                        str(date_folder)
                    )
                    cover_path_jpg = Path(final_cover_jpg)
                except Exception as e:
                    logger.error("Downloader: Pillow WebP->JPEG/YouTube transformation failed: %s", e)
                    # Desperate fallback - return webp string
                    cover_path_jpg = cover_path_webp
            else:
                logger.warning("Downloader: Cover image fetch failed/missing for %s. Proceeding blindly.", douyin_id)
                cover_path_jpg = ""
                
            logger.info("Downloader: Securely landed 100%% data locally for %s.", douyin_id)
            return {
                "local_video_path": str(video_path),
                "local_cover_path": str(cover_path_jpg) if cover_path_jpg else "",
                "ocr_text": ocr_text
            }
            
        except Exception as e:
            logger.error("Downloader: Fatal disruption sequence inside chunk loop %s: %s", douyin_id, e)
            # Ensure no corrupted half-files are left hanging
            if video_path.exists():
                video_path.unlink(missing_ok=True)
            return None

    def _process_image_sync(self, cover_path_webp: str, cover_path_jpg: str, douyin_id: str, date_folder_str: str):
        """Blocking Image processing function intended to run in a thread."""
        date_folder = Path(date_folder_str)
        ocr_text = ""
        with Image.open(cover_path_webp) as img:
            rgb_img = img.convert('RGB')
            rgb_img.save(cover_path_jpg, "JPEG", quality=95)
            
        # --- OCR Extraction ---
        try:
            from modules.win_ocr import get_text_from_image
            extracted = get_text_from_image(str(cover_path_jpg))
            if extracted:
                ocr_text = " ".join(extracted.split())
                logger.info("Downloader: OCR Extracted Cover Text: %s", ocr_text)
        except Exception as ocr_e:
            logger.warning("Downloader: Windows OCR Module failed or missing: %s", ocr_e)
            
        # --- YouTube 16:9 Thumbnail Generation using Template ---
        og_template_path = None
        candidates = [
            PROJECT_ROOT / "og.jpg",
            PROJECT_ROOT.parent / "og.jpg",
        ]
        for c in candidates:
            if c.exists():
                og_template_path = c
                break
                
        if og_template_path:
            try:
                bg_img = Image.open(og_template_path).convert('RGB')
                target_w, target_h = bg_img.size
            except Exception as e:
                logger.error("Downloader: Could NOT load og.jpg template: %s", e)
                bg_img = Image.new('RGB', (1280, 720), (0, 0, 0))
                target_w, target_h = 1280, 720
        else:
            bg_img = Image.new('RGB', (1280, 720), (0, 0, 0))
            target_w, target_h = 1280, 720
        
        # --- Overlay OCR Text ---
        if ocr_text:
            try:
                from PIL import ImageDraw, ImageFont
                import platform
                draw = ImageDraw.Draw(bg_img)
                
                font_path = ""
                if platform.system() == "Windows":
                    fallback_fonts = [
                        "C:\\Windows\\Fonts\\simkai.ttf",
                        "C:\\Windows\\Fonts\\msyhbd.ttc",
                        "C:\\Windows\\Fonts\\msyh.ttc",
                        "C:\\Windows\\Fonts\\simhei.ttf"
                    ]
                    for f in fallback_fonts:
                        if os.path.exists(f):
                            font_path = f
                            break
                        
                if font_path:
                    font = ImageFont.truetype(font_path, 80)
                else:
                    font = ImageFont.load_default()
                    
                max_len = 16
                lines = [ocr_text[i:i+max_len] for i in range(0, len(ocr_text), max_len)][:2]
                
                line_spacing = 20
                total_height = 0
                line_heights = []
                
                for line in lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    h = bbox[3] - bbox[1]
                    line_heights.append(h)
                    total_height += h + line_spacing
                    
                if lines:
                    total_height -= line_spacing
                    
                start_y = (target_h - total_height) / 2
                current_y = start_y
                
                for idx, line in enumerate(lines):
                    text_x = 180 
                    text_y = current_y
                    
                    shadow_offset = 4
                    draw.text((text_x + shadow_offset, text_y + shadow_offset), line, font=font, fill=(0, 0, 0))
                    draw.text((text_x, text_y), line, font=font, fill=(255, 235, 59))
                    
                    current_y += line_heights[idx] + line_spacing
            except Exception as text_err:
                logger.warning("Downloader: Could not draw OCR text overlay onto cover: %s", text_err)
                
        yt_cover_path = date_folder / f"{douyin_id}_yt.jpg"
        bg_img.save(yt_cover_path, "JPEG", quality=95)
        
        if Path(cover_path_webp).exists():
            Path(cover_path_webp).unlink()
            
        return ocr_text, str(yt_cover_path)

    async def _download_file(self, url: str, dest_path: Path, chunk_size=1048576) -> bool:
        """Hardware-safe file dumping method. Blocks memory balloons for massive MP4 streams."""
        headers = {
            "User-Agent": USERAGENT,
            "Referer": "https://www.douyin.com/"
        }
        
        cookie = str(config.get("douyin_cookie", "")).strip()
        if cookie:
            headers["Cookie"] = cookie
        
        max_retries = 5
        downloaded = 0
        total_size = 0
        
        for attempt in range(max_retries):
            try:
                req_headers = headers.copy()
                if downloaded > 0:
                    req_headers["Range"] = f"bytes={downloaded}-"
                    logger.info("Downloader: Resuming %s from byte %s...", dest_path.name, downloaded)
                else:
                    if dest_path.exists():
                        dest_path.unlink()
                        
                timeout = httpx.Timeout(10.0, read=120.0)
                async with httpx.AsyncClient(timeout=timeout) as client:
                    async with client.stream("GET", url, headers=req_headers) as r:
                        r.raise_for_status()
                        
                        if r.status_code == 206:
                            mode = "ab"
                            content_range = r.headers.get('content-range', '')
                            if '/' in content_range:
                                try:
                                    total_size = int(content_range.split('/')[-1])
                                except (ValueError, IndexError):
                                    total_size = downloaded + int(r.headers.get('content-length', 0))
                            else:
                                total_size = downloaded + int(r.headers.get('content-length', 0))
                        else:
                            if dest_path.exists():
                                dest_path.unlink()
                            mode = "wb"
                            downloaded = 0
                            total_size = int(r.headers.get('content-length', 0))
                            
                        last_log_time = time.time()
                        async with aiofiles.open(dest_path, mode) as f:
                            async for chunk in r.aiter_bytes(chunk_size=chunk_size):
                                if chunk:
                                    await f.write(chunk)
                                    downloaded += len(chunk)
                                    
                                    if total_size > 0 and time.time() - last_log_time >= 5.0:
                                        percent = (downloaded / total_size) * 100
                                        logger.info("Downloader: %s 下载进度 %.1f%% (%.1fMB/%.1fMB)", dest_path.name, percent, downloaded/1024/1024, total_size/1024/1024)
                                        last_log_time = time.time()
                        
                        if total_size > 0 and downloaded < total_size:
                            logger.error("Downloader: Incomplete download for %s: %s/%s bytes", dest_path.name, downloaded, total_size)
                            if attempt < max_retries - 1:
                                logger.info("Downloader: Retrying download (%s/%s)...", attempt + 1, max_retries)
                                await asyncio.sleep(2)
                                continue
                            return False
                            
                        logger.info("Downloader: Finished streaming %s (%.1f MB)", dest_path.name, downloaded / 1024 / 1024)
                    return True
                    
            except httpx.HTTPError as e:
                response = getattr(e, "response", None)
                if response:
                    if response.status_code == 416 and downloaded > 0 and downloaded == total_size:
                         logger.info("Downloader: Server reported 416, but local size equals total_size. Considering file complete.")
                         return True
                         
                    if response.status_code == 403:
                        logger.error("Downloader: 403 Forbidden. The CDN URL has expired and cannot be retried. %s", e)
                        return False
                        
                logger.error("Downloader: HTTP Error %s", e)
                if attempt < max_retries - 1:
                    logger.info("Downloader: Retrying download (%s/%s)...", attempt + 1, max_retries)
                    await asyncio.sleep(2)
                    continue
                return False
                
            except Exception as e:
                logger.error("Downloader: Stream disconnect mapping URL %s... : %s", url[:80], e)
                if attempt < max_retries - 1:
                    logger.info("Downloader: Retrying download (%s/%s)...", attempt + 1, max_retries)
                    await asyncio.sleep(2)
                    continue
                return False
                
        return False
