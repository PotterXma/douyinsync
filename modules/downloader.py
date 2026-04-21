import requests
from pathlib import Path
from PIL import Image
from datetime import datetime

from modules.logger import logger
from modules.abogus import USERAGENT

import os
import sys
import time

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys.executable).parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

DOWNLOAD_DIR = PROJECT_ROOT / "downloads"

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
            ocr_text = ""
            if cover_url and self._download_file(cover_url, cover_path_webp):
                # Transformation hook
                try:
                    from PIL import ImageFilter
                    with Image.open(cover_path_webp) as img:
                        # Ensures transparency is discarded properly (JPG does not support alpha)
                        rgb_img = img.convert('RGB')
                        # Save Original
                        rgb_img.save(cover_path_jpg, "JPEG", quality=95)
                        
                        # --- OCR Extraction ---
                        try:
                            from modules.win_ocr import get_text_from_image
                            # Extract baked text from original cover
                            extracted = get_text_from_image(str(cover_path_jpg))
                            if extracted:
                                ocr_text = " ".join(extracted.split())
                                logger.info(f"Downloader: OCR Extracted Cover Text: {ocr_text}")
                        except Exception as ocr_e:
                            logger.warning(f"Downloader: Windows OCR Module failed or missing: {ocr_e}")
                            
                        # --- YouTube 16:9 Thumbnail Generation using Template ---
                        # Look for og.jpg template
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
                                logger.error(f"Downloader: Could NOT load og.jpg template: {e}")
                                bg_img = Image.new('RGB', (1280, 720), (0, 0, 0))
                                target_w, target_h = 1280, 720
                        else:
                            # Fallback if og.jpg not found - blank black background
                            bg_img = Image.new('RGB', (1280, 720), (0, 0, 0))
                            target_w, target_h = 1280, 720
                            logger.warning("Downloader: og.jpg template not found! Using black background.")
                        
                        # --- Overlay OCR Text ---
                        if ocr_text:
                            try:
                                from PIL import ImageDraw, ImageFont
                                import platform
                                draw = ImageDraw.Draw(bg_img)
                                
                                # Font discovery
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
                                    font = ImageFont.truetype(font_path, 80) # Increased font size for template
                                else:
                                    font = ImageFont.load_default()
                                    
                                # Split long title into multiple lines if needed
                                max_len = 16
                                lines = [ocr_text[i:i+max_len] for i in range(0, len(ocr_text), max_len)][:2]
                                
                                # Dynamic vertical spacing based on exact font envelope
                                line_spacing = 20
                                total_height = 0
                                line_heights = []
                                
                                for line in lines:
                                    bbox = draw.textbbox((0, 0), line, font=font)
                                    h = bbox[3] - bbox[1]
                                    line_heights.append(h)
                                    total_height += h + line_spacing
                                    
                                if lines:
                                    total_height -= line_spacing # Remove trailing space
                                    
                                start_y = (target_h - total_height) / 2
                                current_y = start_y
                                
                                for idx, line in enumerate(lines):
                                    # Left alignment, starting around 10%~15% from the left edge
                                    text_x = 180 
                                    text_y = current_y
                                    
                                    # Draw black border shadow for readability
                                    shadow_offset = 4
                                    draw.text((text_x + shadow_offset, text_y + shadow_offset), line, font=font, fill=(0, 0, 0))
                                    # Draw striking yellow/white text
                                    draw.text((text_x, text_y), line, font=font, fill=(255, 235, 59))
                                    
                                    current_y += line_heights[idx] + line_spacing
                            except Exception as text_err:
                                logger.warning(f"Downloader: Could not draw OCR text overlay onto cover: {text_err}")
                                
                        yt_cover_path = date_folder / f"{douyin_id}_yt.jpg"
                        bg_img.save(yt_cover_path, "JPEG", quality=95)
                        
                        # Set the standard cover to the Youtube format
                        cover_path_jpg = yt_cover_path
                        logger.debug(f"Downloader: Success formatting YouTube Cover with Template + Text Overlay - {cover_path_jpg}")
                    
                    # Cleanup staging webp securely
                    if cover_path_webp.exists():
                        cover_path_webp.unlink()
                except Exception as e:
                    logger.error(f"Downloader: Pillow WebP->JPEG/YouTube transformation failed: {e}")
                    # Desperate fallback - return webp string
                    cover_path_jpg = cover_path_webp
            else:
                logger.warning(f"Downloader: Cover image fetch failed/missing for {douyin_id}. Proceeding blindly.")
                cover_path_jpg = ""
                
            logger.info(f"Downloader: Securely landed 100% data locally for {douyin_id}.")
            return {
                "local_video_path": str(video_path),
                "local_cover_path": str(cover_path_jpg),
                "ocr_text": ocr_text
            }
            
        except Exception as e:
            logger.error(f"Downloader: Fatal disruption sequence inside chunk loop {douyin_id}: {e}")
            # Ensure no corrupted half-files are left hanging
            if video_path.exists():
                video_path.unlink(missing_ok=True)
            return None

    def _download_file(self, url: str, dest_path: Path, chunk_size=8192) -> bool:
        """Hardware-safe file dumping method. Blocks memory balloons for 500MB+ files."""
        from modules.config_manager import config
        headers = {
            "User-Agent": USERAGENT,
            "Referer": "https://www.douyin.com/"
        }
        
        # Inject Douyin cookie for CDN authentication (prevents 403 Forbidden)
        cookie = str(config.get("douyin_cookie", "")).strip()
        if cookie:
            headers["Cookie"] = cookie
        
        max_retries = 5
        downloaded = 0
        total_size = 0
        
        for attempt in range(max_retries):
            try:
                # timeout=(connect_timeout, read_timeout)
                # connect: 10s to establish connection
                # read: 120s max wait between chunks (large videos need more time)
                req_headers = headers.copy()
                if downloaded > 0:
                    req_headers["Range"] = f"bytes={downloaded}-"
                    logger.info(f"Downloader: Resuming {dest_path.name} from byte {downloaded}...")
                else:
                    # Clean any existing file on first attempt
                    if dest_path.exists():
                        dest_path.unlink()
                        
                with requests.get(url, headers=req_headers, stream=True, timeout=(10, 120)) as r:
                    r.raise_for_status()
                    
                    # 206 Partial Content: server accepted Range header, we can resume
                    if r.status_code == 206:
                        mode = "ab"
                        # Parse total size from Content-Range: bytes X-Y/TOTAL
                        content_range = r.headers.get('content-range', '')
                        if '/' in content_range:
                            try:
                                total_size = int(content_range.split('/')[-1])
                            except (ValueError, IndexError):
                                total_size = downloaded + int(r.headers.get('content-length', 0))
                        else:
                            total_size = downloaded + int(r.headers.get('content-length', 0))
                    else:
                        # Server returned 200: doesn't support Range -> delete any corrupt partial file first
                        if dest_path.exists():
                            dest_path.unlink()
                        mode = "wb"
                        downloaded = 0
                        total_size = int(r.headers.get('content-length', 0))
                        
                    last_log_time = time.time()
                    with open(dest_path, mode) as f:
                        for chunk in r.iter_content(chunk_size=chunk_size):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                
                                # Print download progress every 5 seconds
                                if total_size > 0 and time.time() - last_log_time >= 5.0:
                                    percent = (downloaded / total_size) * 100
                                    logger.info(f"Downloader: {dest_path.name} 下载进度 {percent:.1f}% ({downloaded/1024/1024:.1f}MB/{total_size/1024/1024:.1f}MB)")
                                    last_log_time = time.time()
                    
                    if total_size > 0 and downloaded < total_size:
                        logger.error(f"Downloader: Incomplete download for {dest_path.name}: {downloaded}/{total_size} bytes")
                        if attempt < max_retries - 1:
                            logger.info(f"Downloader: Retrying download ({attempt + 1}/{max_retries})...")
                            time.sleep(2)
                            continue
                        return False
                        
                    logger.info(f"Downloader: Finished streaming {dest_path.name} ({downloaded / 1024 / 1024:.1f} MB)")
                return True
                
            except requests.exceptions.HTTPError as e:
                # If we get a 416 Range Not Satisfiable, maybe the file changed or is fully downloaded but we failed to recognize it.
                if e.response.status_code == 416 and downloaded > 0 and downloaded == total_size:
                     logger.info(f"Downloader: Server reported 416, but local size equals total_size. Considering file complete.")
                     return True
                     
                if e.response.status_code == 403:
                    logger.error(f"Downloader: 403 Forbidden. The CDN URL has expired and cannot be retried. {e}")
                    return False
                    
                logger.error(f"Downloader: HTTP Error {e.response.status_code}: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Downloader: Retrying download ({attempt + 1}/{max_retries})...")
                    time.sleep(2)
                    continue
                return False
                
            except Exception as e:
                logger.error(f"Downloader: Stream HTTP disconnect mapping URL {url[:80]}... : {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Downloader: Retrying download ({attempt + 1}/{max_retries})...")
                    time.sleep(2)
                    continue
                return False
                
        return False
