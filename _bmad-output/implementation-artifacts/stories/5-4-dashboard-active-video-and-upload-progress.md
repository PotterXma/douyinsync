---
story_key: 5-4-dashboard-active-video-and-upload-progress
status: done
epic_ref: Epic 5
depends_on: 5-5-sqlite-upload-progress-persistence
---

# Story 5-4-dashboard-active-video-and-upload-progress

**状态**: done  

**产品依据**: [prd-per-video-upload-progress-ux.md](../../planning-artifacts/prd-per-video-upload-progress-ux.md)  

**依赖**: **5-5**（上传字节持久化）；若短期仅展示「当前 `uploading` 条目标题」无百分比，可在技术评审后标为**弱依赖**并拆分子迭代。  

**实现要点（建议）**: `modules/database.py` — `VideoDAO.get_active_pipeline_video()`（按 PRD 优先级：`uploading` → `downloading`/`processing` → 空）；`ui/dashboard_app.py` — 当前活动卡片 + 子进度条 +「最近一条成功/失败」只读摘要；`tests/test_dashboard_app.py` 或 DAO 单测。

---

## 用户故事

**作为** 运营者，**我希望** 在 Dashboard 主界面看到**当前正在处理的一条视频**及**上传进度**，**以便** 判断管道未卡死并预估剩余时间。

---

## 验收标准（AC）

1. **当前活动识别**  
   - **Given** 库中存在 `status='uploading'` 且 `updated_at` 最早的一条 **When** Dashboard 轮询刷新 **Then** 主卡片展示该条 **标题（截断）**、`account_mark`、`douyin_id` 短码及文案「正在上传」。  
   - **Given** 无 `uploading` 但存在 `downloading`（或协调器使用的等价状态）**Then** 展示「正在下载」及对应行信息。  
   - **Given** 无上述状态 **Then** 展示明确空闲态（如「当前无活动任务」），**不得**显示随机旧进度。

2. **上传进度**  
   - **Given** 5-5 已落地且 `upload_bytes_total > 0` **When** 刷新 **Then** 展示 0–100% 或「已传 MB / 总 MB」，且与 DB 一致。  
   - **Given** `upload_bytes_total` 为空 **Then** 仅展示阶段标签，**不展示**虚假百分比。

3. **最近一条结果（只读）**  
   - **Given** 最近一次在本会话或轮询窗口内变为 `uploaded` **Then** 展示成功提示；若库中已有 YouTube 视频 id 列（由实现 Story 与迁移引入）则一并展示并可复制，否则至少展示「已成功」与标题/`douyin_id`。  
   - **Given** 最近一次失败 **Then** 展示一行人类可读摘要（优先 `last_error_summary`，否则沿用现有失败列表逻辑）。

4. **与全局 UI 关系**  
   - **Then** 顶部 YouTube 配额条保留；在活动卡片旁或脚注区分「账号当日配额」与「当前单条进度」（文案即可，无需改配额算法）。

5. **测试**  
   - **Given** 内存或临时 DB 注入 `uploading` + 进度字段 **When** 调用 Dashboard 数据组装函数 **Then** 断言卡片文本与进度数值符合预期。

---

## 非目标

- 托盘 tooltip 实时进度（PRD V2）。  
- 视频库表格列扩展（可另开 Story 或标为 5-4  stretch）。
