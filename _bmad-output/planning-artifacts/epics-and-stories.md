# DouyinSync — Epic 与用户故事（全量补档）

> 与 `PRD-snapshot.md`、`docs/architecture.md` 一致。**状态**：Epic 1～5 已落地（含 **5-4 / 5-5** 上传进度与 Dashboard 当前任务）；详见 `sprint-status.yaml`。

---

## Epic 列表

| Epic | 标题 | 目标 |
|------|------|------|
| 1 | 守护进程与托盘外壳 | 主线程托盘 + 后台管道线程 + 生命周期与事件队列 |
| 2 | SQLite 状态机与 DAO | WAL、幂等、统计与僵尸恢复 |
| 3 | 抓取与下载 | 签名、过滤、分块下载、CDN 刷新、封面 |
| 4 | 上传与运营韧性 | OAuth 续传、配额熔断、清理、通知 |
| 5 | 可观测与操作 UI | CTk HUD、经典视频库、设置与统计子进程；**（扩展）**单视频活动与上传进度 |

---

## Epic 1：守护进程与托盘外壳

**目标**：UI 与管道解耦；退出可协作关闭调度器。

### Story 1-1：后台管道线程与事件队列

**作为** 维护者，**我希望** 管道在独立线程中运行，**以便** 托盘 UI 不被阻塞。

**验收：**

- **Given** 应用已启动 **When** 主线程进入托盘循环 **Then** `PipelineCoordinator` 在后台线程已 `start()` 且可执行 `primary_sync_job`
- **Given** 队列收到 `EXIT` **When** 守护循环处理 **Then** 调用 `coordinator.shutdown()` 并结束线程

**实现要点**：`main.py` — `background_daemon` + `queue.Queue` + `AppEvent`。

---

### Story 1-2：托盘图标与菜单动作

**作为** 运营者，**我希望** 通过托盘启停监控、打开子进程 UI，**以便** 无需命令行。

**验收：**

- **Given** 托盘已挂载 **When** 选择暂停/继续 **Then** APScheduler `pause`/`resume` 生效且图标状态变化
- **When** 选择手动执行一次 **Then** 在非阻塞线程中触发 `primary_sync_job`

**实现要点**：`ui/tray_icon.py`、`modules/tray_app.py`。

---

### Story 1-3：APScheduler 与协调器生命周期

**作为** 系统，**我希望** 定时间隔可配置，**以便** 控制抓取频率。

**验收：**

- **Given** `config.json` 中 `sync_interval_minutes` **When** 协调器启动 **Then** Job 按该间隔注册
- **When** `shutdown()` **Then** 调度器停止且不泄漏线程

**实现要点**：`modules/scheduler.py`、`modules/config_manager.py`。

---

## Epic 2：SQLite 状态机与 DAO

**目标**：单一数据源；安全并发；可观测聚合。

### Story 2-1：WAL 与表结构

**作为** 开发者，**我希望** 使用 `AppDatabase.get_connection()`，**以便** 统一 PRAGMA 与超时。

**验收：**

- **Given** 新库 **When** 初始化 **Then** `journal_mode=WAL` 且存在 `videos` 表
- **Then** 业务代码（含经典视频库 `modules/dashboard.py`）通过 `AppDatabase` / `VideoDAO` 访问数据库，不直接 `sqlite3.connect`

**实现要点**：`modules/database.py`。

---

### Story 2-2：幂等插入与状态迁移

**作为** 管道，**我希望** `INSERT OR IGNORE` 按 `douyin_id`，**以便** 重复抓取不重复行。

**验收：**

- **Given** 同一 `douyin_id` 两次插入 **When** 调用 `insert_video_if_unique` **Then** 第二次返回 `False`
- **Given** 合法状态迁移 **When** `update_status` **Then** `updated_at` 更新

---

### Story 2-3：僵尸恢复与聚合统计

**作为** 系统，**我希望** 异常退出后自动回滚中间态，**以便** 下一周期可重试。

**验收：**

- **Given** 存在 `processing`/`downloading`/`uploading` 行 **When** `revert_zombies()` **Then** 状态回到设计规则（见架构 4.1）
- **When** 调用 `get_pipeline_stats` **Then** 返回各 `status` 计数
- **When** 调用 `get_accounts_pipeline_stats` / `get_recent_failure_rows` **Then** 返回分账号与失败样本（Epic 5 依赖）

---

## Epic 3：抓取与下载

**目标**：稳定取链、省内存下载、403 可恢复。

### Story 3-1：抖音列表抓取与过滤

**作为** 管道，**我希望** 仅保留可下载 MP4 类稿件，**以便** 下游不处理无效类型。

**验收：**

- **Given** 有效 Cookie 与签名 **When** `fetch_all` **Then** 新视频写入 `pending` 或忽略重复

**实现要点**：`modules/douyin_fetcher.py`、`abogus`/`xbogus`。

---

### Story 3-2：分块下载与封面管线

**作为** 系统，**我希望** `iter_content` 小块写盘，**以便** 大文件不占满内存。

**验收：**

- **Given** 合法 `video_url` **When** 下载完成 **Then** `status=downloaded` 且本地路径非空（成功路径）

**实现要点**：`modules/downloader.py`、`modules/win_ocr.py`（可选）。

---

### Story 3-3：CDN 过期刷新

**作为** 下载器，**我希望** 403 时刷新 URL，**以便** 减少人工干预。

**验收：**

- **Given** 下载返回 403 **When** 触发刷新流程 **Then** 调用 `update_fresh_urls` 后重试路径存在

---

## Epic 4：上传与运营韧性

**目标**：可恢复上传；配额保护；磁盘与推送。

### Story 4-1：OAuth 与可续传上传

**作为** 运营者，**我希望** Token 持久化与刷新，**以便** 长期无人值守。

**验收：**

- **Given** 有效 `client_secret` **When** 首次授权 **Then** 生成 token 文件且后续可静默刷新（成功路径）
- **When** 上传大文件 **Then** 使用 resumable / 分块 API 路径

**实现要点**：`modules/youtube_uploader.py`。

---

### Story 4-2：配额熔断与重试装饰器

**作为** 系统，**我希望** 配额耗尽时暂停上传直至配额重置窗口，**以便** 不刷爆 API。

**验收：**

- **Given** 模拟 Quota 类错误 **When** 进入熔断 **Then** 调度行为符合 `utils/decorators.py` 与调度器集成测试预期

---

### Story 4-3：Sweeper 预检与 Bark 通知

**作为** 运维，**我希望** 磁盘不足前阻断或告警，**并在** 关键失败时收到推送。

**验收：**

- **Given** Sweeper 配置 **When** `purge_stale_media` **Then** 超保留期文件删除策略生效（见测试）
- **When** `notifier.push` 被调用 **Then** HTTP 层可 mock 验证

**实现要点**：`modules/sweeper.py`、`modules/notifier.py`。

---

## Epic 5：可观测与操作 UI

**目标**：子进程隔离 GUI；只读 HUD；可选写库管理库。

**扩展（2026-04-24）**：单条管道活动与 YouTube 上传百分比可感知，产品说明见 [prd-per-video-upload-progress-ux.md](./prd-per-video-upload-progress-ux.md)。**5-5**（SQLite 持久化进度）与 **5-4**（Dashboard 展示）已于 2026-05-01 落地。

### Story 5-1：CustomTkinter HUD（`dashboard`）

**作为** 运营者，**我希望** 每 ~3 秒看到全局与分账号统计及最近失败，**以便** 快速判断健康度。

**验收：**

- **Given** 数据库可连 **When** 启动 `python main.py dashboard` **Then** 展示进度条、聚合标签、`get_accounts_pipeline_stats` 卡片与失败列表（只读）
- **Then** 使用 `root.after` 轮询而非阻塞 `sleep`

**实现要点**：`ui/dashboard_app.py`、`main.py` 分支。

---

### Story 5-2：经典视频库（`videolib`）

**作为** 运营者，**我希望** 表格筛选与批量重置 `pending`，**以便** 纠错重跑。

**验收：**

- **Given** `python main.py videolib` **When** 用户确认重置 **Then** 选中行 `status=pending` 且 `retry_count` 规则符合 UI 逻辑

**实现要点**：`modules/dashboard.py` — 使用 `VideoDAO.list_videos_for_library` / `VideoDAO.bulk_reset_to_pending`。

---

### Story 5-3：设置与统计子进程

**作为** 运营者，**我希望** 从托盘打开设置与统计窗口，**以便** 调整间隔与查看历史感知的汇总。

**验收：**

- **Given** 冻结或非冻结环境 **When** 托盘选择对应菜单 **Then** `subprocess` 拉起 `main.py settings|stats` 成功路径无阻塞托盘线程

**实现要点**：`modules/ui_settings.py`、`modules/ui_stats.py`、`modules/tray_app.py`。

---

### Story 5-5：SQLite 上传进度持久化

**作为** 运营者，**我希望** 上传过程中进度写入数据库，**以便** Dashboard 等只读进程能轮询到真实百分比。

**验收：**

- **Given** 旧库 **When** 迁移/启动 **Then** `videos` 增加进度相关列（`upload_bytes_done` / `upload_bytes_total` 等）且无静默数据损坏
- **Given** resumable 上传进行中 **When** 分块推进 **Then** 节流写库，`VideoDAO` 可测
- **When** 上传结束 **Then** 进度字段与僵尸恢复逻辑协调一致

**实现要点**：`modules/database.py`、`utils/models.py`、`modules/youtube_uploader.py`、`tests/test_database.py`、`tests/test_youtube_uploader.py`。

**Story 键**：`5-5-sqlite-upload-progress-persistence`

---

### Story 5-4：Dashboard 当前活动与上传进度

**作为** 运营者，**我希望** 在主 HUD 看到「当前一条」及上传进度条，**以便** 确认未卡死。

**验收：**

- **Given** 存在 `uploading` 行 **When** 轮询 **Then** 主卡片展示标题、`account_mark`、阶段「正在上传」
- **Given** 5-5 已提供 `upload_bytes_total` **Then** 展示 0–100% 或等价字节文案；无总量时不展示假进度
- **Given** 无活动任务 **Then** 明确空闲态
- **Then** 与顶部 YouTube 配额条文案区分账号级 vs 单条

**实现要点**：`modules/database.py` — 查询活动行；`ui/dashboard_app.py`。

**Story 键**：`5-4-dashboard-active-video-and-upload-progress`

---

## FR 覆盖摘要

| FR 段 | 主要 Epic |
|-------|------------|
| FR-01~02 | Epic 3、2 |
| FR-03 | Epic 3 |
| FR-04~05 | Epic 3、4 |
| FR-06~08 | Epic 1、2、4 |
| FR-09~10 | Epic 4 |
| FR-11~12 | Epic 5 |

详见 `traceability-matrix.md`。

---

## Story 键 ↔ `sprint-status.yaml`

| development_status 键 | 文档小节 |
|-------------------------|----------|
| `1-1-daemon-thread-and-event-queue` | Story 1-1 |
| `1-2-tray-menu-and-coordinator-hooks` | Story 1-2 |
| `1-3-apscheduler-startup-shutdown` | Story 1-3 |
| `2-1-sqlite-wal-schema-and-dao` | Story 2-1 |
| `2-2-idempotent-insert-and-status-updates` | Story 2-2 |
| `2-3-zombie-recovery-and-aggregated-stats` | Story 2-3 |
| `3-1-douyin-fetch-signature-and-filter` | Story 3-1 |
| `3-2-chunked-download-and-cover-pipeline` | Story 3-2 |
| `3-3-cdn-403-url-refresh-path` | Story 3-3 |
| `4-1-youtube-oauth-resumable-upload` | Story 4-1 |
| `4-2-quota-circuit-breaker-and-retries` | Story 4-2 |
| `4-3-sweeper-preflight-and-bark-notifier` | Story 4-3 |
| `5-1-ctk-hud-dashboard-subprocess` | Story 5-1 |
| `5-2-classic-videolib-table-and-reset` | Story 5-2 |
| `5-3-settings-stats-subprocess-from-tray` | Story 5-3 |
| `5-5-sqlite-upload-progress-persistence` | Story 5-5 |
| `5-4-dashboard-active-video-and-upload-progress` | Story 5-4 |
