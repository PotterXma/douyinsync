You are an **Acceptance Auditor**. 

Review the diff (provided in `diff.txt`) against the spec and context docs provided below. Check for: violations of acceptance criteria, deviations from spec intent, missing implementation of specified behavior, contradictions between spec constraints and actual code. Output findings as a Markdown list. Each finding: one-line title, which AC/constraint it violates, and evidence from the diff.

---
### Spec Document context (Story 4.3):
# Story 4.3: YouTube Quota Global Circuit Breaker

**Epic:** 4 — Automated Background Scheduling & Resilience
**Story ID:** 4.3
**Story Key:** 4-3-youtube-quota-global-circuit-breaker

## Story
As a production daemon,
I want a global circuit breaker that trips when YouTube returns a quota exhaustion error,
So that all upload operations are suspended for 24 hours to protect the API quota.

## Acceptance Criteria
1. **Given** the YouTube uploader encounters an `HttpError` 403 quota error
   **When** the circuit breaker trips
   **Then** all subsequent upload calls are blocked for 24 hours without retrying
2. **Given** the quota circuit breaker is tripped
   **When** the event happens
   **Then** a Bark notification is pushed to alert the operator of the quota exhaustion event
3. **Given** 24 hours have elapsed since the trip
   **When** the next scheduler cycle runs
   **Then** the breaker resets automatically and upload operations resume.

## Dev Notes
### 架构约束 (Architectural Guardrails)
- **绝对导入 (Absolute Imports)**: 禁止使用相对引用，所有包都要从根目录书写如 `from modules.scheduler import PipelineCoordinator`。
- **惰性日志 (Lazy Logging)**: 禁止在日志方法参数中提前作变量格式化，正确示例：`logger.info("Blocked util %s", expiry_time)`。
- **事件隔离**: NFR 标准规定底层模块不允许阻塞事件循环，保证使用 `async` 并通过协程处理。 

### 前序冲刺分析 & Retrospective 指示 (Retro Intel)
根据 `epic-all-retro-2026-04-22.md` 的教训，务必规避以下问题：
- **A1 Async/Sync 边界事故**: 由于 Uploader 是 `async` 调用，在 test 里面模拟被调用必须小心应用 `AsyncMock` 或由 `pytest-asyncio` 等驱动。
- **A2 Mock 重复样板开销过大**: 请使用前几个故事可能已建立好的 `tests/conftest.py` 中统一配置的 `mock_video_dao` 和 `mock_notifier` Fixtures 进行测试提效。如果还没建立，在这个 Story 初始化即可。
  
### Technical Research
根据最新 YouTube Data API V3 文档，当配额溢出时，Google API 在 payload 中的 `error.errors[0].reason` 精准返回 `quotaExceeded` 并伴随 `403` 代码，此机制在 `youtube_uploader.py` 本地转换应正确被隔离和识别，确保它与普通 `404` 甚至是 `500` 系统内部错开，确保不滥杀。
