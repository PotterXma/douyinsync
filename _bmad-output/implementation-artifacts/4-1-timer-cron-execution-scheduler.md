# Story 4.1: 定时器 & Cron 执行调度器

**Status:** done
**Epic:** 4 — Automated Background Scheduling & Resilience
**Story ID:** 4.1
**Story Key:** 4-1-timer-cron-execution-scheduler

---

## Story

As an automation manager,
I want APScheduler to orchestrate the pipeline loop in a non-overlapping background thread,
So that the system syncs Douyin content to YouTube on a configured interval without any user intervention.

---

## Acceptance Criteria

1. **Given** the daemon has started and the configuration is valid
   **When** the application reaches ready state
   **Then** `APScheduler` sets up a `BackgroundScheduler` job running on the configured interval
   **And** a `threading.Lock` prevents overlapping executions if a previous run is still in progress
   **And** the scheduler shuts down gracefully when a stop signal is received.

2. **Given** the `primary_sync_job` is already running
   **When** APScheduler fires it again before the previous run finishes
   **Then** the second invocation detects the lock and logs a warning before immediately returning.

3. **Given** a shutdown signal is received
   **When** `coordinator.shutdown()` is called
   **Then** APScheduler's `shutdown(wait=True)` blocks until the current job completes cleanly.

---

## 关键背景（Context Intel）

### ⚡ 现有代码状态（Critical — 读此再动手）

`modules/scheduler.py` 中 `PipelineCoordinator` **已经完整实现**了本故事所有核心逻辑。**不要重写，只需验证、补强缺失测试与边界。**

**已实现的关键代码点（逐一核验）：**

| 功能点 | 位置 | 状态 |
|--------|------|------|
| `BackgroundScheduler` 初始化 | `__init__` → `self.scheduler` | ✅ 存在 |
| `IntervalTrigger` 绑定 `primary_sync_job` | `start()` L283 | ✅ 存在 |
| `threading.Lock` 防并发执行 | `self._pipeline_lock` + `acquire(blocking=False)` | ✅ 存在 |
| `asyncio.run(_run_async_cycle)` 桥接 | `primary_sync_job()` L57 | ✅ 存在 |
| `scheduler.shutdown(wait=True)` | `shutdown()` L302 | ✅ 存在 |
| 首次立即触发（启动后 5s） | `start()` L298 | ✅ 存在 |
| `janitor_job` 每 24h 磁盘清理 | `start()` L290 | ✅ 存在 |
| `push_daily_summary` Cron 23:50 | `start()` L293 | ✅ 存在 |

### 已存在的装饰器支持

`utils/decorators.py` 包含：
- `@auto_retry(max_retries, backoff_base, exceptions)` — 同时支持 async/sync 函数
- `@circuit_breaker(trip_on)` — 触发时睡到下一个 PST 午夜

---

## Tasks / Subtasks

- [x] **Task 1: 核验 PipelineCoordinator 实现完整性** (AC: 1)
  - [x] 打开 `modules/scheduler.py`，逐行确认 `__init__`、`start()`、`shutdown()` 三个方法均符合 AC 1 要求。
  - [x] 验证 `_pipeline_lock.acquire(blocking=False)` 路径存在并有 `logger.warning` 告警日志（AC: 2）。
  - [x] 无需修改，仅确认。

- [x] **Task 2: 检查并补全 `tests/test_scheduler.py`** (AC: 1,2,3)
  - [x] 确认测试文件存在：`tests/test_scheduler.py`。
  - [x] 检查是否覆盖以下测试用例（不存在则新增）：
    - `test_scheduler_starts_with_background_job` — 验证 `start()` 后 `scheduler.get_jobs()` 包含 `primary_sync` 任务。
    - `test_concurrent_lock_skips_duplicate_run` — Mock `_run_async_cycle` 使其挂起，然后二次调用 `primary_sync_job()`，断言第二次直接返回（不 await 进 `_run_async_cycle`）。
    - `test_scheduler_shutdown_waits_for_job` — 验证 `shutdown()` 调用了 `scheduler.shutdown(wait=True)`。
  - [x] 确保所有测试使用绝对导入：`from modules.scheduler import PipelineCoordinator`。

- [x] **Task 3: 补全日志级别验证** (AC: 2)
  - [x] 在 `test_concurrent_lock_skips_duplicate_run` 中，使用 `caplog` fixture 断言锁竞争时打印了包含 `"already running"` 或 `"Skipping duplicate"` 的 WARNING 级别日志。

- [x] **Task 4: 回顾行动项 A2 — `tests/conftest.py` 共享 Mock 工厂**
  - [x] 确认 `tests/conftest.py` 是否已存在。若不存在，创建最小可用版本：

- [x] **Task 5: 执行全量测试，确保无回归**
  - [x] 运行 `pytest tests/test_scheduler.py -v` 确认本 Story 相关测试全部通过。
  - [x] 运行 `pytest --tb=short -q` 确认全量测试无回归。

---

## Dev Notes

### 架构约束（必须遵守）

- **绝对导入**：所有 import 必须使用根路径，如 `from modules.scheduler import PipelineCoordinator`，禁止相对导入。
- **惰性日志**：禁止 f-string 日志，使用 `logger.warning("msg: %s", var)` 格式。
- **Type Hinting**：所有新增函数必须包含完整类型签名。
- **async/sync 边界**：`BackgroundScheduler` 运行在同步线程中；`_run_async_cycle` 必须通过 `asyncio.run()` 桥接，禁止在同步上下文直接 `await`。

### 关键技术陷阱（Anti-patterns）

- ❌ **不要** 在 `primary_sync_job` 内用 `asyncio.get_event_loop().run_until_complete()`，现已用 `asyncio.run()` 即可，且协程安全。
- ❌ **不要** 使用 `max_instances=1`（APScheduler 参数）代替 `threading.Lock`。`max_instances` 不能防止同一进程内手动重复调用，Lock 才是真正的互斥保障。
- ❌ **不要** 在测试中直接调用 `scheduler.start()` 而不 Mock APScheduler，否则测试会真的启动后台线程导致测试挂起。
- ❌ **不要** 在 `shutdown()` 后调用 `scheduler.get_jobs()`，APScheduler 已关闭会抛出异常。

### 文件结构（本 Story 涉及文件）

```
modules/
  scheduler.py        ← 核验，通常无需修改
tests/
  conftest.py         ← 新建（若不存在）
  test_scheduler.py   ← 补全测试用例
```

### 关于回顾行动项

**综合回顾（epic-all-retro-2026-04-22.md）要求 Epic 4 开始前完成：**
- [A1] `project-context.md` 补充 async/sync 边界规则 — *本 Story 不需强制，可于 Task 2 注释中体现*
- [A2] `tests/conftest.py` 统一 Mock 工厂 — **本 Story Task 4 处理**
- [A3] `utils/paths.py` 统一路径工具 — *与本 Story 无直接关系，下一个 Story 视情况处理*

### 参考来源

- [epics.md#Story 4.1](../planning-artifacts/epics.md)
- [architecture.md — Scheduler & Queue Controller](../planning-artifacts/architecture.md)
- [epic-4-context.md](./epic-4-context.md)
- [epic-all-retro-2026-04-22.md — 行动项 A1/A2/A3](./epic-all-retro-2026-04-22.md)

---

## Dev Agent Record

### Agent Model Used
Gemini 3.1 Pro (High)

### Debug Log References
- No implementation bugs encountered.
- Test log inspection revealed `caplog` fixture conflict with mocked `logger` dependency, resolved using `mock_logger.warning.call_args` directly instead of `logging.WARNING` trap.

### Completion Notes List
- 验证了 `PipelineCoordinator` 原本的正确实现，没有进行任何逻辑重构，降低了引入故障的风险。
- 创建了 `tests/conftest.py` 全局的 Mock Factory，极大简化了之后的编写测试步骤。
- 于 `tests/test_scheduler.py` 中补充防并发拦截测试 (AC 2) 以及强制阻塞关机行为（AC 3）的单元测试。
- 确认全部 94 个单元测试顺利满分通过退出（Exit code: 0）。

### File List
- `modules/scheduler.py`
- `tests/conftest.py` (新增)
- `tests/test_scheduler.py` (修改)
