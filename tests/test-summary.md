# Test Automation Summary

## 当前范围

- **框架**: `pytest`（`tests/test_*.py`，共十余个模块测试文件）。
- **最近一次全量**: `python -m pytest tests/ -q` 应全部通过（含数据库、调度、下载、上传、Dashboard、sweeper、notifier 等）。

## 模块覆盖（摘要）

| 区域 | 测试文件 |
|------|-----------|
| DB / DAO | `test_database.py` |
| 调度与熔断相关 | `test_scheduler.py`, `test_resilience.py` |
| 抓取 / 下载 / 上传 | `test_douyin_fetcher.py`, `test_douyin_api.py`, `test_downloader.py`, `test_youtube_uploader.py` |
| 配置 / 日志脱敏 | `test_config_manager.py`, `test_sanitizer.py` |
| 托盘 / Dashboard | `test_tray_icon.py`, `test_dashboard_app.py` |
| 清理 / 通知 | `test_sweeper.py`, `test_notifier.py` |

## 非自动化

- **端到端 / 真网环境**: 仍依赖本机 `config.json`、Cookie、代理与 GCP 凭证；可用根目录 **`test_pipeline.py`** 或 `python main.py manual_run` 做人工冒烟（勿纳入 CI 若无密钥）。

## 后续可选

- 接入 CI（GitHub Actions 等）在 PR 上跑 `pytest`。
- ~~`asyncio.iscoroutinefunction` 弃用~~：已改为 `inspect.iscoroutinefunction`（`utils/decorators.py`）。
- ~~pytest RuntimeWarning（未 await 协程）~~：`test_downloader` 使用显式 `MagicMock` + `AsyncMock` 上下文；`test_scheduler` 全模块 mock `BackgroundScheduler`，且 `test_pipeline_lock_prevents_overlap` 对 `asyncio.run` 使用 `side_effect` 真正执行协程。
