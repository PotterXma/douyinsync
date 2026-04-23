# Story 1-5（装配）— PipelineCoordinator 主干顺序

> 对应 Epic 1 / Epic 4 与 `modules/scheduler.py` 实现；供实现评审与 onboarding。

## 启动阶段（每次 `primary_sync_job` 或等价入口）

1. **并发锁**：若已有运行中同步，跳过或等待策略以代码为准（`threading.Lock`）。
2. **`VideoDAO.revert_zombies()`** — 崩溃自愈，避免 `processing`/`downloading`/`uploading` 卡死。
3. **`DiskSweeper.check_preflight_space()`** — 磁盘预检，空间不足时阻断或记录（见 sweeper 实现）。
4. **`DiskSweeper.purge_stale_media()`** — 清理过期本地媒体（Epic 4 / 定时任务可能单独注册）。
5. **`DouyinFetcher.fetch_all()`** — 拉取新稿并 `insert_video_if_unique`。
6. **`Downloader.process_pending()`** — 消费 `pending` → 本地文件 → `downloaded`（或失败路径）。
7. **`YoutubeUploader.upload_queue()`** — 消费可上传队列 → YouTube → `uploaded` 或重试/熔断路径。

## 关闭阶段

- `PipelineCoordinator.shutdown()`：停止 APScheduler，释放后台资源（见 `scheduler.py`）。

## 依赖关系简图

```mermaid
flowchart LR
  Z[revert_zombies] --> S[sweeper checks]
  S --> F[fetch_all]
  F --> D[process_pending]
  D --> U[upload_queue]
```

## 验收关联

- 与 `epics-and-stories.md` 中 Epic 1 Story 1-3、Epic 3、Epic 4 的 Given/When/Then 一致。
- 单测入口：`tests/test_scheduler.py`、`tests/test_database.py`、`tests/test_sweeper.py` 等。
