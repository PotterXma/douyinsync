# Component Inventory

### User interfaces

- **`ui/tray_icon.py`**: PyStray 托盘入口、`TrayApp` 与后台 `event_queue` 协作。
- **`modules/tray_app.py`**: 托盘菜单动作（启停调度、手动跑一轮、子进程拉起 Dashboard / 设置 / 统计等）。
- **`ui/dashboard_app.py`**: Epic 5 CustomTkinter HUD（`python main.py dashboard`）；只读轮询 DB，可再拉起经典视频库。
- **`modules/dashboard.py`**: 经典 Tk 视频表（`python main.py videolib`）；通过 `VideoDAO.list_videos_for_library` / `bulk_reset_to_pending` 读写。
- **`modules/ui_settings.py`** / **`modules/ui_stats.py`**: 设置与统计子进程 UI。

### Core pipeline

- **`modules/scheduler.py`**: `PipelineCoordinator` + APScheduler 主循环。
- **`modules/douyin_fetcher.py`**: 抖音作品列表抓取与签名。
- **`modules/downloader.py`**: 分块下载与封面处理。
- **`modules/youtube_uploader.py`**: OAuth 与可续传上传。
- **`modules/database.py`**: `AppDatabase` / `VideoDAO`、WAL 与僵尸恢复。

### Supporting

- **`modules/sweeper.py`**: 磁盘保留期清理。
- **`modules/notifier.py`**: Bark 推送。
- **`modules/config_manager.py`**: `config.json` 热重载单例。
- **`modules/win_ocr.py`**: Windows OCR 封装。
- **`utils/logger.py`** + **`modules/logger.py`**: 根日志配置与业务侧 `logger` 代理。
