# Story 4.4: Self-Healing Zombie State Reverter

**Status:** done
**Epic:** 4 — Automated Background Scheduling & Resilience
**Story ID:** 4.4
**Story Key:** 4-4-self-healing-zombie-state-reverter

---

## Story

As a crash-resilient system,
I want stranded `processing` and `uploading` database rows to be automatically reverted on startup,
So that an ungraceful shutdown never permanently blocks videos from re-entering the pipeline.

---

## Acceptance Criteria

1. **Given** the daemon is starting up
   **When** the database initialization sequence runs
   **Then** any rows in `processing` state are reverted to `pending`
   **And** any rows in `uploading` state are reverted to `downloaded`
   **And** the count of reverted rows is logged at the `INFO` level for observability.

---

## 关键背景 (Context Intel)

### ⚡ 现有代码状态 (Critical — 读此再动手)

`modules/database.py` 中 `VideoDAO` 已经初步实现了 `revert_zombies()` 方法，并且 `modules/scheduler.py` 中 `PipelineCoordinator` 在 `start()` 时已经调用了 `recover_zombies()`。
本 Story 主要目的在于验证并完善其核心逻辑，补充测试体系，确保该功能在实际中能 100% 按验收标准工作。

**已实现的关键代码点（逐一核验）：**
- `Database.py (VideoDAO.revert_zombies)`: ✅ 已包含将 `processing` / `downloading` 还原为 `pending`，`uploading` 还原为 `downloaded` 等机制，还包含了对连跪 3 次以上的 task 设置为 `give_up_fatal` 的操作。
- `Scheduler.py (PipelineCoordinator.recover_zombies)`: ✅ 记录回滚总数，并抛出有关于成功挽救了 zombie 任务的日志，随后在 `start()` 方法开头被调用。

---

## Tasks / Subtasks

- [x] **Task 1: 核验逻辑的完备程度**
  - [x] 检查 `modules/database.py` 内部 `revert_zombies` 对于影响行数（`rowcount`）的总和计算。
  - [x] 确保 `PipelineCoordinator.recover_zombies()` 正确打印了 `INFO` （目前代码可能使用的是 `INFO` 然后在数量大于0时追加了一次 `WARNING`，需保证至少有 `INFO` 级别的日志或两者皆有，根据架构防雪崩要求使用惰性日志拼接法，即 `logger.info("msg %s", count)` 格式）。

- [x] **Task 2: 编写测试用例 `tests/test_database.py`**
  - [x] 确认测试文件 `tests/test_database.py` 存在。
  - [x] 增加 `test_revert_zombies` 用例：
    - 手动 `insert` 一些状态为 `processing`、`uploading`、`downloading` 以及超过 3 次 `retry_count` 且为 `pending` 的测试数据。
    - 调用 `VideoDAO.revert_zombies()`。
    - 断言原 `processing` 的 ID 现在变为 `pending` 并且 `retry_count` += 1。
    - 断言原 `uploading` 的 ID 现在变为 `downloaded` 并且 `retry_count` += 1。
    - 断言返回值等于实际上做了变换的行数。
  - [x] 保证断言精准到位。

- [x] **Task 3: 完善对日志的断言监控与全量测试**
  - [x] 运行 `pytest tests/test_database.py -v` 确保 `revert_zombies` 功能工作正常。
  - [x] 同步修改如有涉及的文件，确保导入规则（绝对导入）符合要求规范。

---

## Dev Notes

### 架构约束 (必须遵守)

- **绝对导入**：所有 import 必须使用根路径，禁止相对导入。
- **SQLite 并发写入防护**：确保 `revert_zombies` 共用一条 `db.get_connection()` 的上下文，不在多次调用时触发数据库多锁。现有的实现中是一条 `with db.get_connection() as conn:` 包含了多条 SQL，这是正确的，确保不被破破坏。
- **惰性日志记录**：所有的 `logger.info` 禁止使用 f-string，必须使用 `logger.info("Reverted %s tasks.", count)` 形式！

### 文件结构 (本 Story 涉及文件)

```
modules/
  database.py         ← 核验 DAO 实现，调整完善
  scheduler.py        ← 核验调用位置
tests/
  test_database.py    ← 补全僵尸重置测试用例
```

### 参考来源

- [epics.md#Story 4.4](../planning-artifacts/epics.md)
- [architecture.md](../planning-artifacts/architecture.md)

---

## Dev Agent Record

### Agent Model Used
Gemini 3.1 Pro (High)

### Debug Log References
- Tests run successfully: `pytest tests/test_database.py -v` returns 100% pass for all 6 database tests.

### Completion Notes List
- Verified `database.py` existing implementation of `revert_zombies` correctly implements zombie state rollback logic, adding rowcount sums accurately.
- Verified `scheduler.py` uses correct layout and lazy interpolations for logging.
- Extended `tests/test_database.py` with `test_revert_zombies` inserting 5 conditions and verifying correct state change and returned counts. Full test suite validation passes.

### File List
- tests/test_database.py
