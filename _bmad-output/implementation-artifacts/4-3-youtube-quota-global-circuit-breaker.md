# Story 4.3: YouTube Quota Global Circuit Breaker

**Status:** done
**Epic:** 4 — Automated Background Scheduling & Resilience
**Story ID:** 4.3
**Story Key:** 4-3-youtube-quota-global-circuit-breaker

---

## Story

As a production daemon,
I want a global circuit breaker that trips when YouTube returns a quota exhaustion error,
So that all upload operations are suspended for 24 hours to protect the API quota.

---

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

---

## 关键背景 (Context Intel)

### ⚡ 现有代码状态 (Critical — 读此再动手)
`modules/scheduler.py` 中 `PipelineCoordinator` 和 `modules/youtube_uploader.py` **已经部分或完整实现**了本故事的核心逻辑。**不要重写，只需验证并补全缺失的测试套件以锁定行为契约。**

**已实现的关键代码点（请逐一核验作为首要任务）：**
| 功能点 | 位置 | 状态 |
|--------|------|------|
| QuotaError 状态变量 | `PipelineCoordinator.__init__` (L28) | ✅ 存在 (`self.youtube_quota_exceeded_until`) |
| API Quota 错误捕获 | `YoutubeUploader.upload` (L125) 处理 HTTPStatusError | ✅ 存在 (转出 `YoutubeQuotaError`) |
| 异常捕获与熔断触发 | `PipelineCoordinator._run_async_cycle` 阶段 3 | ✅ 存在 (超时 86400s 并 Bark 通报) |
| 循环前置拦截逻辑 | `PipelineCoordinator._run_async_cycle` 阶段 3 前置判断 | ✅ 存在 (`is_youtube_blocked`) |

---

## Tasks / Subtasks

- [x] **Task 1: 核验 YouTubeUploader 异常转换逻辑** (AC 1)
  - [x] 检查 `modules/youtube_uploader.py` 文件中，对 403 及 `quotaExceeded` 判断和转译 `YoutubeQuotaError` 的稳健性。

- [x] **Task 2: 核验 PipelineCoordinator 熔断流程** (AC 1, 2)
  - [x] 校验 `modules/scheduler.py` 中的 `is_youtube_blocked` 是否涵盖了 Phase 3 的所有上传调用（包含重新上传失败视频及全新下载的上传）。
  - [x] 并验证在对应 catch `YoutubeQuotaError` 时会调用 Bark 推送报警，并将该视频返回 `downloaded` 状态。

- [x] **Task 3: 检查并补齐容灾逻辑的 Test 套件 `tests/test_scheduler.py`** (AC 1, 2, 3)
  - [x] 在 `tests/test_scheduler.py` 中补充专门测试熔断逻辑的三个核心用例：
    - `test_circuit_breaker_trips_on_quota_error`: 强制模拟 uploader 抛出 `YoutubeQuotaError`，验证 `youtube_quota_exceeded_until` 变量被正确设置并触发了 `notifier.push` 警告消息。
    - `test_circuit_breaker_blocks_subsequent_uploads`: 初始化 coordinator，人为让 `youtube_quota_exceeded_until` 处于明天时，确认系统虽执行了循环但跳过了上传代码。
    - `test_circuit_breaker_resets_after_24_hours`: 初始化 coordinator，让时间处于昨天时，系统正常执行了上传逻辑。

- [x] **Task 4: 全量测试与收尾**
  - [x] 使用 `pytest tests/test_scheduler.py -v` 验证新测试点。
  - [x] 全局回归测试通过。

---

## Dev Notes

### 架构约束 (Architectural Guardrails)
- **绝对导入 (Absolute Imports)**: 禁止使用相对引用，所有包都要从根目录书写如 `from modules.scheduler import PipelineCoordinator`。
- **惰性日志 (Lazy Logging)**: 禁止在日志方法参数中提前作变量格式化，正确示例：`logger.info("Blocked util %s", expiry_time)`。
- **事件隔离**: NFR 标准规定底层模块不允许阻塞事件循环，保证使用 `async` 并通过协程处理。 

### 前序冲刺分析 & Retrospective 指示 (Retro Intel)
根据 `epic-all-retro-2026-04-22.md` 的教训，务必规避以下问题：
- **A1 Async/Sync 边界事故**: 由于 Uploader 是 `async` 调用，在 test 里面模拟被调用必须小心应用 `AsyncMock` 或由 `pytest-asyncio` 等驱动。
- **A2 Mock 重复样板开销过大**: 请使用前几个故事可能已建立好的 `tests/conftest.py` 中统一配置的 `mock_video_dao` 和 `mock_notifier` Fixtures 进行测试提效。如果还没建立，在这个 Story 初始化即可。
  
### Technical Research 🌐
根据最新 YouTube Data API V3 文档，当配额溢出时，Google API 在 payload 中的 `error.errors[0].reason` 精准返回 `quotaExceeded` 并伴随 `403` 代码，此机制在 `youtube_uploader.py` 本地转换应正确被隔离和识别，确保它与普通 `404` 甚至是 `500` 系统内部错开，确保不滥杀。

---

## File List
- `tests/test_scheduler.py` (Modified - Added tests and corrected preflight network check mock)

---

## Change Log
- 2026-04-22: Implemented test cases for YouTube Quota circuit breaker, covering trip activation, blockage persistence, and 24h reset logic. Fixed async mock issues with `preflight_network_check`.

---

## Dev Agent Record
- **Implementation Notes:** Checked core exception handling in `YoutubeUploader` and evaluated `PipelineCoordinator`, confirming the 24-hour block behavior was already correctly mapped to variables and logic. Focused heavily on providing 3 detailed integration tests. Also repaired `mock_dependencies` which was failing testing environment because `preflight_network_check` needed `AsyncMock` to cleanly emulate `utils.network`.
- **Completion Notes:** Story tasks correctly solved and 100% tests passing locally across all Epic 4 logic.

### Review Findings
- [x] [Review][Patch] 存储保护配置存在负数和零值漏洞 — `<max_age_days>` 未防御负数或 `0` 输入，若因配置失误可能导致正常视频被立即清除。 [`modules/scheduler.py`:`janitor_job`]
- [x] [Review][Patch] 熔断验证时间校验不严谨 — 测试用例中断言 `>= now + 86000`，而准确熔断窗口应严格核对为 24 小时 (即 86400 秒)。 [`tests/test_scheduler.py`:`test_circuit_breaker_trips_on_quota_error`]
- [x] [Review][Patch] 熔断恢复边界测试弱化 (违背 AC 3) — 用例中使用前置 `- 1000` 秒模拟，未能准确映射“已经过 24 小时”的核心规约，应更正为 `- 86400`。 [`tests/test_scheduler.py`:`test_circuit_breaker_resets_after_24_hours`]
