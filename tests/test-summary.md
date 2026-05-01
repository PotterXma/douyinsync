# Test Automation Summary

## 当前范围

- **框架**: `pytest`（`tests/test_*.py`，当前 **16** 个模块测试文件）；开发依赖 **`requirements-dev.txt`**；发现范围与 asyncio 见 **`pytest.ini`**（CI 与本地一致）。
- **最近一次全量（参考）**: `python -m pytest tests/ -q` → **135 passed**（约 2m20s，Windows；含 `pytest.ini`）。若本地失败先执行 `pip install -r requirements-dev.txt`。

## 模块覆盖（摘要）

| 区域 | 测试文件 |
|------|-----------|
| DB / DAO | `test_database.py` |
| 调度与熔断相关 | `test_scheduler.py`, `test_resilience.py` |
| 抓取 / 下载 / 上传 | `test_douyin_fetcher.py`, `test_douyin_api.py`, `test_downloader.py`, `test_youtube_uploader.py` |
| 配置 / 日志脱敏 | `test_config_manager.py`, `test_sanitizer.py` |
| 托盘 / Dashboard / 设置解析 | `test_tray_icon.py`, `test_dashboard_app.py`, `test_ui_settings.py` |
| 经典 videolib 纯函数 / 导出 | `test_dashboard_library_formatters.py`、`test_dashboard_export_csv.py` |
| 清理 / 通知 | `test_sweeper.py`, `test_notifier.py` |

## 非自动化

- **端到端 / 真网环境**: 仍依赖本机 `config.json`、Cookie、代理与 GCP 凭证；可用根目录 **`test_pipeline.py`** 或 `python main.py manual_run` 做人工冒烟（勿纳入 CI 若无密钥）。

## 后续可选

- ~~接入 CI（GitHub Actions 等）在 PR 上跑 `pytest`~~：**`.github/workflows/ci.yml`** — `windows-latest`，Python **3.10–3.13** 矩阵（job 名 `test (Python x.y)`，`fail-fast: false`，单 job 超时 25min），`requirements-dev.txt`，全量 `pytest`；**任意目标分支的 PR** 均触发；支持 **Run workflow**。依赖更新见 **`.github/dependabot.yml`**（Actions + pip，按月）。
- ~~`asyncio.iscoroutinefunction` 弃用~~：已改为 `inspect.iscoroutinefunction`（`utils/decorators.py`）。
- ~~pytest RuntimeWarning（未 await 协程）~~：`test_downloader` 使用显式 `MagicMock` + `AsyncMock` 上下文；`test_scheduler` 全模块 mock `BackgroundScheduler`，且 `test_pipeline_lock_prevents_overlap` 对 `asyncio.run` 使用 `side_effect` 真正执行协程。
