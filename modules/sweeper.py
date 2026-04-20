import os
import sys
import time
import shutil
from pathlib import Path
from modules.logger import logger

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys.executable).parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

DOWNLOAD_DIR = PROJECT_ROOT / "downloads"

class DiskSweeper:
    def __init__(self):
        DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    def check_preflight_space(self) -> bool:
        """Determines if the OS host structure has > 2GB left physically."""
        try:
            total, used, free = shutil.disk_usage(DOWNLOAD_DIR.anchor)
            free_gb = free / (1024**3)
            if free_gb < 2.0:
                logger.critical(f"DiskSweeper: CRITICAL - Hard drive partition has only {free_gb:.2f}GB remaining! Danger zone.")
                return False
            return True
        except Exception as e:
            logger.warning(f"DiskSweeper: Failed to execute IO disk verification -> {e}")
            return True # Fallback

    def purge_stale_media(self, max_age_days: int = 7):
        """Recursively evicts any files aged past the boundary protecting the SSD infrastructure."""
        logger.info(f"DiskSweeper: Conducting sweep for media older than {max_age_days} days...")
        
        cutoff_epoch = time.time() - (max_age_days * 86400)
        reclaimed_bytes = 0
        target_exts = {'.mp4', '.webp', '.jpg'}
        
        try:
            for root, dirs, files in os.walk(DOWNLOAD_DIR):
                for file in files:
                    file_path = Path(root) / file
                    if file_path.suffix.lower() in target_exts:
                        mtime = file_path.stat().st_mtime
                        if mtime < cutoff_epoch:
                            size = file_path.stat().st_size
                            file_path.unlink(missing_ok=True)
                            reclaimed_bytes += size
                            
            if reclaimed_bytes > 0:
                logger.info(f"DiskSweeper: Janitor operation complete. Reprieved {reclaimed_bytes / (1024**2):.2f} MB of SSD sector space.")
            else:
                logger.debug("DiskSweeper: Floors are pristine. No garbage accumulation detected.")
                
        except Exception as e:
            logger.error(f"DiskSweeper: Unexpected recursive fault during janitor sequence: {e}")
