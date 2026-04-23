# Epic 3 — 抓取与下载

**状态**: done  

完整故事与验收见 [epics-and-stories.md](./epics-and-stories.md) 中「Epic 3」章节。

**Story 键**: `3-1-douyin-fetch-signature-and-filter`, `3-2-chunked-download-and-cover-pipeline`, `3-3-cdn-403-url-refresh-path`, `3-4-download-and-upload-failure-handling`

**主要代码**: `modules/douyin_fetcher.py`, `modules/downloader.py`, `modules/win_ocr.py`；失败重试与终态见 `modules/scheduler.py`（与 Story 3.4 笔记）
