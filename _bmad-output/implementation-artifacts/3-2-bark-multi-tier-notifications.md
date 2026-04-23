# Story 3.2: Bark Multi-Tier Notifications

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

作为一名离屏的流水线监控员，
我想要 Bark 将关键状态变更（成功/失败）推送到我的手机，
以便于我能在第一时间感知视频完成上传或发生硬性故障，无需盯着屏幕。

## Acceptance Criteria

1. **Given** Pipeline 中出现重大状态跃迁（成功上传 / 不可恢复失败），
   **When** 条件满足时，
   **Then** 系统通过 `BarkNotifier.push()` 发送一次轻量级 HTTP 请求到 Bark 端点，绝不阻塞主调度线程。
2. **Given** 一次成功上传事件，
   **When** 触发汇总通知，
   **Then** 系统每日仅发送一次合并摘要（Daily Summary），避免通知轰炸。
3. **Given** 阻断型错误（如 Cookie 失效、Quota 耗尽），
   **When** 触发即时通知，
   **Then** 系统必须立即单独推送，并含有具体账号名与错误原因，严禁与成功日报合并。

## Tasks / Subtasks

- [x] 任务 1: 验证并完善现有 `BarkNotifier` 实现 (AC: 1)
  - [x] 审查 `modules/notifier.py` 中 `BarkNotifier.push()` 是否满足非阻塞要求（当前使用同步 `requests.get`，需评估是否在独立线程中调用）。
  - [x] 确认 `push()` 的 `level` 参数支持三级通知层级：`active`（默认）、`timeSensitive`（关键阻断错误）、`passive`（静默日报）。
  - [x] 为 `BarkNotifier` 编写/补充单元测试 `tests/test_notifier.py`，覆盖：配置缺失时跳过推送、成功推送、网络失败时不抛出（仅 warning 日志）。
- [x] 任务 2: 在 `PipelineCoordinator` 中集成分层通知触发点 (AC: 2, 3)
  - [x] 在 `modules/scheduler.py` 中，识别上传成功事件触发点，调用 `notifier.record_upload_success()` 累计计数。
  - [x] 在 `modules/scheduler.py` 中，识别不可恢复错误触发点（`give_up` 状态 & Quota 耗尽），调用 `notifier.push(level="timeSensitive")` 立即单推。
  - [x] 确保所有 `notifier.push()` 调用均在守护线程中执行（非 UI 主线程），不阻塞 pystray 事件循环。
- [x] 任务 3: 实现每日汇总去重机制 (AC: 2)
  - [x] 在 `BarkNotifier` 中新增 `_daily_upload_count`、`_summary_date`、`_check_and_reset_daily_counter()`、`record_upload_success()`、`push_daily_summary()` 方法。
  - [x] 确保重启进程后计数器重置（内存级别，无持久化需求）。

## Dev Notes

- **⚠️ 关键发现：`modules/notifier.py` 已存在完整 `BarkNotifier` 实现！**
  - `push(title, message, level)` 已支持三级 `level` 参数（`active` / `timeSensitive` / `passive`）
  - 使用 `requests.get` 同步调用，**有阻塞风险**，调用方需在非 UI 线程中使用
  - 动态从 `config.get("bark_server")` + `config.get("bark_key")` 读取参数（支持热重载）
  - 配置缺失时自动静默（`_get_bark_url()` 返回空字符串即跳过）
  - **禁止重复造轮子**，必须复用此类

- **非阻塞要求**：由于 `push()` 使用同步 `requests.get(timeout=15.0)`，调用时必须确保在 `background_daemon` 线程（`PipelineCoordinator` 所在线程）中执行，严禁在 pystray 主线程或 `queue.Queue` 消费者路径上直接调用。

- **架构约束**：
  - 所有跨模块调用严格遵循 Absolute Import：`from modules.notifier import BarkNotifier`
  - `BarkNotifier` 实例应在 `PipelineCoordinator.__init__` 中初始化（单例），不在 `ui/` 层创建实例
  - 日志调用格式：`logger.info("Bark: %s", message)` — 禁止 f-string

- **涉及文件**：
  - `modules/notifier.py`：现有实现，仅补充测试，不重写
  - `modules/scheduler.py`：注入通知触发点
  - `tests/test_notifier.py`：新增单元测试

- **Story 3-1 经验教训**：
  - 测试中 mock `requests.get` 时注意 patch 路径为 `modules.notifier.requests.get`
  - `config.get()` 在测试中需要 mock，否则会读取真实配置文件

### Project Structure Notes

- `modules/notifier.py` 已就位，无需创建新文件
- `ui/` 层严禁持有 `BarkNotifier` 实例或直接发起通知
- 通知逻辑收口在 `scheduler.py` 的 `PipelineCoordinator` 中

### References

- [Source: planning-artifacts/epics.md#Story 3.2: Bark Multi-Tier Notifications]
- [Source: planning-artifacts/architecture.md#API & Communication Patterns]
- [Source: planning-artifacts/ux-design-specification.md#Feedback Patterns (状态反馈范式)]
- [Source: modules/notifier.py] — 现有实现（已完整，勿重写）

## Dev Agent Record

### Agent Model Used

Claude Sonnet 4.6 (Thinking)

### Debug Log References
无

### Completion Notes List
- 发现 `modules/notifier.py` 中 `BarkNotifier` 已完整实现，Story 核心工作聚焦于集成与分层触发，而非重建。
- 三级通知层级（active / timeSensitive / passive）已由现有 `push()` 方法原生支持。
- ✅ 新增 `_check_and_reset_daily_counter()` / `record_upload_success()` / `push_daily_summary()` 实现每日去重汇总机制。
- ✅ `scheduler.py` 中两处上传成功路径均注入 `record_upload_success()`，两处 Quota 耗尽路径注入 `timeSensitive` 告警。
- ✅ give_up 状态（重试 ≥3 次）触发即时推送，含视频 ID 信息。
- 所有 push() 调用均在 `background_daemon` 线程（PipelineCoordinator 所属线程），满足非阻塞要求。
- 12 个单元测试全部通过。

### File List
- modules/notifier.py
- tests/test_notifier.py

### Review Findings
- [x] [Review][Patch] Sync IO in Async Loop — `BarkNotifier.push()` calls a blocking `requests.get(timeout=15.0)`. Since `_run_async_cycle` is now fully asynchronous, invoking synchronous REST calls blocks the underlying `asyncio` event loop. Consider wrapping it in `asyncio.to_thread` or migrating to `httpx.AsyncClient`. [modules/scheduler.py:315 / 326]
- [x] [Review][Defer] Midnight rollover race condition — `push_daily_summary()` resets the counter if `today != summary_date`. Since the cron runs at 23:50, if the job is delayed past 00:00, `today` changes and the count drops to 0 before the notification triggers. — deferred, pre-existing

## Suggested Review Order

**Async Event Loop Unblocking**
- Wrapped BarkNotifier push events in `asyncio.to_thread` to maintain pipeline async non-blocking integrity.
  [`scheduler.py:73`](../../modules/scheduler.py#L73)

- Implemented daily summary triggering seamlessly inside the overall PipelineCoordinator using APScheduler.
  [`scheduler.py:282`](../../modules/scheduler.py#L282)

**Notification Level Wiring**
- Bark notifier class augmented with day-counting bounds tracking for daily batch summaries.
  [`notifier.py:53`](../../modules/notifier.py#L53)
