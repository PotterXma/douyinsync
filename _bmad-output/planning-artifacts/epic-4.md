# Epic 4 — 上传与运营韧性

**状态**: done  

完整故事与验收见 [epics-and-stories.md](./epics-and-stories.md) 中「Epic 4」章节。

**Story 键**: `4-1-youtube-oauth-resumable-upload`, `4-2-quota-circuit-breaker-and-retries`, `4-3-sweeper-preflight-and-bark-notifier`, `4-4-manual-run-and-schedule-modes`

**主要代码**: `modules/youtube_uploader.py`, `modules/sweeper.py`, `modules/notifier.py`, `utils/decorators.py`；APScheduler 间隔/固定时刻与手动触发见 `modules/scheduler.py`、`main.py`、`ui/tray_icon.py`（Story 4.4）
