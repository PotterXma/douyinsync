---
story_key: 5-5-sqlite-upload-progress-persistence
status: backlog
epic_ref: Epic 5
depends_on: []
blocks: 5-4-dashboard-active-video-and-upload-progress
---

# Story 5-5-sqlite-upload-progress-persistence

**状态**: backlog  

**产品依据**: [prd-per-video-upload-progress-ux.md](../../planning-artifacts/prd-per-video-upload-progress-ux.md)  

**依赖**: 无（应先于 5-4 实现或与之同一迭代合并验收）。  

**实现要点（建议）**: `modules/database.py`（迁移/新列）、`utils/models.py` — `VideoRecord`、`modules/youtube_uploader.py`（分块上传回调节流写库）、必要时 `modules/scheduler.py` 在进入/离开上传时清零字段。

---

## 用户故事

**作为** 运营者，**我希望** 上传大文件时进度持久化在 SQLite 中，**以便** Dashboard 子进程只读数据库即可展示百分比且不依赖日志解析。

---

## 验收标准（AC）

1. **Schema**  
   - **Given** 既有 `douyinsync.db` **When** 应用启动或迁移逻辑执行 **Then** `videos` 表存在（或等价迁移成功）以下列（名称可微调，但语义需一致）：  
     - `upload_bytes_done INTEGER`（默认 0）  
     - `upload_bytes_total INTEGER`（可为 NULL，表示未知）  
     - `last_error_summary TEXT`（可选，与 5-4 失败文案共用）  
   - 旧库升级无静默丢数据。

2. **DAO**  
   - **Given** 某 `douyin_id` 处于 `uploading` **When** 调用 `VideoDAO.update_upload_progress(douyin_id, done, total)` **Then** 对应行更新且 `updated_at` 刷新。  
   - **When** 上传结束（成功或失败）**Then** 协调器或上传器将进度字段重置为 0/NULL（或文档约定保留最后一次），且与僵尸恢复 `revert_zombies` 行为不冲突。

3. **上传器**  
   - **Given** YouTube 分块/resumable 上传进行中 **When** 每完成若干字节或若干分块 **Then** 以**节流**方式（如 ≥1s 或每 5%）写库，避免 WAL 锁风暴。  
   - **When** 无 token 或 API 错误 **Then** `last_error_summary` 可写入**脱敏**后的简短原因（不含密钥）。

4. **测试**  
   - **Given** mock 上传循环 **When** 多次进度回调 **Then** `test_database.py` / `test_youtube_uploader.py` 中至少一条用例断言 DB 中 `upload_bytes_done` 单调非减直至完成。

---

## 非目标

- 不在本期实现抖音下载字节级进度（仅 YouTube 上传侧）。  
- 不强制 Bark 推送进度事件（见 PRD V2）。
