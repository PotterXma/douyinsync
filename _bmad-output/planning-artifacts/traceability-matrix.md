# 需求追溯矩阵（FR / Epic / 实现 / 测试）

| FR | Epic | 主要代码路径 | 测试（示例） |
|----|------|----------------|----------------|
| FR-01 | 3 | `modules/douyin_fetcher.py`, `modules/scheduler.py` | `test_douyin_fetcher.py`, `test_douyin_api.py`, `test_scheduler.py` |
| FR-02 | 2 | `modules/database.py` — `insert_video_if_unique` | `test_database.py` |
| FR-03 | 3 | `modules/downloader.py`, `modules/win_ocr.py` | `test_downloader.py` |
| FR-04 | 3–4 | `modules/config_manager.py`, `utils/network.py`, `modules/youtube_uploader.py` 代理注入 | `test_config_manager.py`, `test_youtube_uploader.py` |
| FR-05 | 4 | `modules/youtube_uploader.py` | `test_youtube_uploader.py` |
| FR-06 | 1 | `main.py`, `modules/scheduler.py`, `modules/tray_app.py` | `test_scheduler.py`, `test_tray_icon.py` |
| FR-07 | 2 | `modules/database.py` — `revert_zombies` | `test_database.py` |
| FR-08 | 4 | `utils/decorators.py`, `modules/youtube_uploader.py`, `modules/scheduler.py` | `test_resilience.py`, `test_scheduler.py` |
| FR-09 | 4 | `modules/sweeper.py`, `modules/scheduler.py` | `test_sweeper.py`, `test_scheduler.py` |
| FR-10 | 4 | `modules/notifier.py` | `test_notifier.py` |
| FR-11 | 5 | `main.py` argv, `ui/dashboard_app.py`, `modules/dashboard.py`, `modules/ui_settings.py`, `modules/ui_stats.py` | `test_dashboard_app.py` |
| FR-12 | 5 | `modules/dashboard.py`（写库重置） | 以手工/E2E 为主；单元可扩展 |

## Epic 5 扩展（规划中，待纳入 PRD 快照）

| 需求摘要 | Epic / Story | 主要代码路径 | 测试（规划） |
|----------|----------------|--------------|----------------|
| 单视频上传进度可感知 | 5 — `5-5-sqlite-upload-progress-persistence` | `modules/database.py`, `modules/youtube_uploader.py` | `test_database.py`, `test_youtube_uploader.py` |
| Dashboard 当前活动 + 进度条 | 5 — `5-4-dashboard-active-video-and-upload-progress` | `ui/dashboard_app.py`, `modules/database.py` | `test_dashboard_app.py`（或 DAO 单测） |

产品说明：[prd-per-video-upload-progress-ux.md](./prd-per-video-upload-progress-ux.md)

## NFR 追溯

| NFR | 证据 |
|-----|------|
| NFR-01 | `main.py` 线程模型；`docs/architecture.md` 3.6 |
| NFR-02 | `database.py` WAL / busy_timeout；`test_database.py` |
| NFR-03 | `utils/logger.py`, `utils/sanitizer.py`；`test_sanitizer.py` |
| NFR-04 | 各模块 `sys.frozen` 分支；`docs/project-context.md` |
| NFR-05 | `tests/test_*.py` 全量 pytest |

## 已关闭技术债

| 项 | 说明 |
|----|------|
| ~~TD-01~~ | `modules/dashboard.py` 已改为 `VideoDAO` / `AppDatabase`，与 `docs/project-context.md` 一致。 |
