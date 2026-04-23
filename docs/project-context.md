---
title: "Project Context: DouyinSync"
last_updated: "2026-04-21"
sections_completed: 6
description: "Core AI rules, technology stack, and implementation conventions for DouyinSync codebase."
---

# Project Context: DouyinSync

This document contains the critical rules, architecture decisions, and code patterns for the DouyinSync project. AI agents **must** read and adhere to these guidelines when modifying or adding code to this repository.

## 1. Technology Stack

- **Primary Language**: Python 3.10+
- **Packaging/Distribution**: PyInstaller (for compiling to standalone `.exe` Windows executable)
- **Database**: SQLite3 (using `sqlite3` built-in module)
- **Key Dependencies**:
  - `requests`: Sync HTTP operations and streaming downloads
  - `apscheduler`: Background job scheduling (`BackgroundScheduler`)
  - `pystray` & `Pillow`: System tray icon and image format conversions (WebP -> JPEG)
  - `google-api-python-client`, `google-auth-oauthlib`: YouTube Data API v3 integration
  - Windows 10/11 Native OCR via `winrt.windows.media.ocr`

## 2. Architecture Overview

DouyinSync is a background daemon that automatically scrapes Douyin videos, downloads them, converts thumbnails, and uploads them to YouTube.

### Core Modules
- `main.py`: Entry point, initializes the scheduler and tray menu.
- `modules/config_manager.py`: Thread-safe singleton (`ConfigManager`) managing `config.json`. Hot-reloadable via lock mechanism.
- `modules/database.py`: DAO pattern wrapper (`VideoDAO`). SQLite with `PRAGMA journal_mode=WAL;` for concurrency.
- `modules/scheduler.py`: The `PipelineCoordinator` manages the main sync loop, handles queue tasks, and triggers `apscheduler` jobs.
- `modules/douyin_fetcher.py`: Scrapes video links (MP4, WebP) from Douyin user profiles by bypassing WAF with `a_bogus`.
- `modules/downloader.py`: Chunked, stream-based downloading for large files. Automatically creates YouTube-compatible thumbnails with text OCR.
- `modules/youtube_uploader.py`: Resumable chunked video uploads and custom thumbnail setter to YouTube API.
- `modules/notifier.py`: Delivers push notifications via the Bark App API.
- `modules/win_ocr.py`: Synchronous wrapper over Windows Native OCR for extracting text from cover images.

### Structural Boundaries
- **UI and Worker Separation**: The tray flow (`ui/tray_icon.py` + `modules/tray_app.py`) must never block the main loop. Inter-component commands run via detached background threads or threading locks.
- **Resource Limits**: The app strictly streams large videos to disk (avoiding memory bloat >300MB). RAM footprint is kept minimal.
- **Paths**: Must support frozen executables (PyInstaller). Use `sys.frozen` and `sys.executable` fallbacks instead of just `__file__`.

## 3. Implementation Rules

### AI Code Generation Rules

✅ **DO:**
1. **Use `logger` over `print()`**: All diagnostic outputs must use `from modules.logger import logger` (e.g., `logger.info()`). DO NOT use `print()`.
2. **Handle PyInstaller Paths**: Always load assets or databases dynamically checking Python's `sys.frozen` state:
   ```python
   import sys
   from pathlib import Path
   if getattr(sys, 'frozen', False):
       PROJECT_ROOT = Path(sys.executable).parent
   else:
       PROJECT_ROOT = Path(__file__).resolve().parent.parent
   ```
3. **Database Concurrency**: Only use the `AppDatabase` connection context (`with db.get_connection() as conn:`) from `database.py`. The Database is WAL enabled. Do not use raw sqlite3 connects outside this DAO.
4. **Resumable Downloads/Uploads**: Ensure any file touching I/O handles chunking. Use `iter_content` for downloads and `googleapiclient.http.MediaFileUpload` chunking for YouTube uploads.
5. **Absolute Imports**: Always use absolute imports originating from the project root (`from modules.database import db`). No relative imports.

❌ **DO NOT:**
1. **DO NOT hold the thread**: Functions triggered by `.config_manager.reload()` or system tray clicks must not block execution. 
2. **DO NOT leak credentials**: The log outputs must not print direct access tokens, passwords, or cookies. (Handled gracefully via `logger` sanitization).
3. **DO NOT make naked HTTP calls**: Use proper headers including `User-Agent`. When reaching Douyin, inject the required cookie.
4. **DO NOT rely on Linux tools**: This application runs on Windows OS.

## 4. State Management (SQLite)

The `videos` table in `douyinsync.db` dictates the flow of state transitions for each video:
- `pending`: Newly found on Douyin, waiting to process.
- `processing`: Locked by the scheduler, currently downloading.
- `downloaded`: Safely sitting on the hard drive, ready for YouTube.
- `uploading`: Actively chunking up to YouTube.
- `uploaded`: Complete. Never touch again.
- `failed`: An error occurred. Retries handle this depending on count.

**Zombie State Recovery**: If the app shuts down ungracefully in a `processing` or `uploading` state, `database.py` includes a `recover_zombies` query that resets to `pending`/`downloaded` on next launch.

## 5. Network Tolerance & API Fallbacks

- **Douyin WAF**: Relies on specific HTTP parameters (`a_bogus` signature, headers, etc.).
- **CDN Expiration**: Douyin Video URLs expire. The daemon will auto-refresh the URLs by fetching posts again if a 403 occurs during the download phase.
- **YouTube API Quotas**: Extremely limited. If the `youtube_uploader` throws a `QuotaExceeded` error (HTTP 403), the loop enters a 24-hour circuit-breaker mode.
- **Automatic Fallbacks**: Missing the custom `og.jpg` fallback thumbnail generator template will gracefully degrade to a black background image. Missing OCR modules degrade to no-text overlays.

## 6. Config Updates & Hot Reload

- Notification keys (`bark_server`, `bark_key`), proxies, and upload limits (`daily_upload_limit`, `max_videos_per_run`) are read directly through `config`.
- `config_manager.ConfigManager` holds a `threading.Lock()` enabling hot reloading of the JSON configuration immediately taking effect for the next operation without application restart.
