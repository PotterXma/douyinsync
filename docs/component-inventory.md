# Component Inventory

### User Interfaces
- **`tray_app.py`**: PyStray GUI binding bridging app closing and dashboard showing contexts.
- **`dashboard.py`**: Tkinter UI showing realtime queue stats running independently from logic.

### Utilities
- **`sweeper.py`**: Purger to permanently remove local logs and videos older than defined retention timeframe (e.g. 7 days)
- **`notifier.py`**: Bark HTTP requests wrapping payload formatted notifications tracking errors direct to user Mobile devices.
- **`config_manager.py`**: Class Singleton for reloading `config.json` rules dynamically.

### APIs
- **`douyin_fetcher.py`**: User profile post endpoint scraper logic.
- **`youtube_uploader.py`**: Google OAuth handshake + Chunk uploading mechanics.
