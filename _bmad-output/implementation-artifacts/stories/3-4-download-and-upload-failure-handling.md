# Story 3.4: Download / Upload Failure Handling

Status: done

## Story

As an operator,
I want predictable recovery when downloads or uploads fail,
so that transient CDN/YouTube issues are retried automatically and permanent failures surface clearly.

## Handling Matrix

| 场景 | 条件 | 状态与数据 | 后续行为 |
|------|------|------------|----------|
| **下载失败**（返回空 / 异常） | `retry_count + 1 < 3` | `pending`，`retry_count` 递增，清空本地路径字段 | 下周期重新拉流、刷新 URL、再下载 |
| **下载失败** | 已连续失败 3 次 | `give_up`，清空本地路径 | Bark 告警「Download Give Up」；不再自动排队 |
| **下载成功 → 上传失败**（空 `yt_id` 或非配额异常） | `retry_count + 1 < 3` | `failed`，保留 `local_video_path` / `local_cover_path`，`retry_count` 递增 | `get_uploadable_videos` 在下一周期 **Phase 3-Pre** 重试上传（与既有重传逻辑一致） |
| **下载成功 → 上传失败** | 上传侧已连续失败 3 次 | `give_up`，保留路径便于人工排查 | Bark「Upload Give Up」；不再进入可上传队列 |
| **配额超限** | `YoutubeQuotaError` | `downloaded`，不增加 `retry_count` | 24h 断路器；本地文件保留，配额恢复后再传 |
| **僵尸自愈** | 进程异常退出留在 `uploading` | 重启时改为 `downloaded` 且 `retry_count+1` | 见 `VideoDAO.revert_zombies` |

## 实现要点

- 成功写入 `downloaded` 时将 **`retry_count` 置 0**，与「下载阶段重试计数」解耦，使上传独立享有最多 3 次尝试（与 Phase 3-Pre 重传策略一致）。
- 下载阶段失败不长期停在无路径的 `failed`（旧行为难以自动重试）；改为 **`pending` 重试** 或 **`give_up` 终态**。
- Bark 与 Dashboard / 视频库中的 `give_up` / `failed` 行可用于人工介入（重设 `pending`、换代理等）。

## 代码锚点

- `modules/scheduler.py` — Phase 3-Main：`download_media` 失败分支；首传 `upload` 失败 / 空结果分支（对齐 Phase 3-Pre 的 `give_up` / `failed` 与 `retry_count`）。
- `modules/database.py` — `get_uploadable_videos`、`revert_zombies`
- `modules/downloader.py` — 失败时清理不完整 MP4，避免脏文件

## 回归测试

- `tests/test_scheduler.py`：`test_download_failure_requeues_as_pending`、`test_download_failure_third_strike_give_up`、`test_first_upload_empty_youtube_id_marks_failed`
