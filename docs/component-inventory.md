# Component Inventory

### User interfaces

- **`ui/tray_icon.py`**: **当前主程序**（`main.py`）使用的 PyStray 托盘：`TrayApp` 经 `queue.Queue` 投递 `AppEvent`（`EXIT` / `RELOAD_CONFIG` / `RUN_PIPELINE_NOW` / `OPEN_DASHBOARD` / `OPEN_SETTINGS`）到后台守护线程。
- **`modules/tray_app.py`**: 另一套 **中文右键菜单** 托盘实现（含启停调度、子进程拉起等）；与 `ui/tray_icon.py` **二选一**挂载，勿假设两者同时运行。
- **`ui/dashboard_app.py`**: Epic 5 CustomTkinter HUD（`python main.py dashboard`）；只读轮询 DB；可写 `.manual_sync_request` / `.manual_force_retry_request`。
- **`modules/dashboard.py`**: 经典 Tk 视频表（`python main.py videolib`）；列含上传进度、**`last_error_summary`**、**`youtube_video_id`**（选中行状态栏展示摘要或 YouTube ID；**双击 / Ctrl+C** 按优先级复制；**F5** 刷新）；表格支持纵向/横向滚动；可按当前筛选 **导出 CSV**（UTF-8 BOM，`last_error_summary` 全文）；`VideoDAO.list_videos_for_library` / `bulk_reset_to_pending`。
- **`modules/ui_settings.py`**: **搬运时间设置看板**（`python main.py settings`）：`sync_schedule_mode` + 间隔小时 / 定点时刻；保存后 **`touch` `reload_config_request_path()`** 触发主进程重载排期。
- **`modules/ui_stats.py`**: 统计子进程 UI（`python main.py stats`）。

### Core pipeline

- **`modules/scheduler.py`**: `PipelineCoordinator` + APScheduler 主循环。
- **`modules/douyin_fetcher.py`**: 抖音作品列表抓取与签名。
- **`modules/downloader.py`**: 分块下载与封面处理。
- **`modules/youtube_uploader.py`**: OAuth 与 **Google Resumable Upload**（`httpx` 分块 PUT + 状态探测）。
- **`modules/database.py`**: `AppDatabase` / `VideoDAO`、WAL 与僵尸恢复。

### Supporting

- **`scripts/build_douyinsync.ps1`** / **`build.bat`**: PyInstaller onedir 构建，产出 `dist/DouyinSync/`。
- **`modules/sweeper.py`**: 磁盘保留期清理。
- **`modules/notifier.py`**: Bark 推送。
- **`modules/config_manager.py`**: `config.json` 热重载单例。
- **`modules/win_ocr.py`**: Windows OCR 封装。
- **`utils/logger.py`** + **`modules/logger.py`**: 根日志配置与业务侧 `logger` 代理。
