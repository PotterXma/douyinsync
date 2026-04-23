# Story 2.1: Decorative Circuit Breaker & Retries

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an automated system,
I want to employ exponential backoff and circuit-breaker decorators,
so that sudden API limits or 403 blocks safely pause operations natively.

## Acceptance Criteria

1. **Given** operations failing randomly against YouTube/Douyin
   **When** errors are thrown
   **Then** the retry logic runs up to 3 times before assigning a `give_up` status
   **And** completely trips and sleeps natively if quotas are breached.

## Tasks / Subtasks

- [x] Task 1: Create Custom Exception Hierarchy
  - [x] Define `NetworkTimeoutError`, `YoutubeQuotaError`, and other necessary exceptions.
  - [x] Place them in an appropriate utility module (e.g. `utils/exceptions.py` or inside `utils/decorators.py`).
- [x] Task 2: Implement the `@auto_retry` Decorator
  - [x] Implement exponential backoff for a maximum of 3 retries.
  - [x] Automatically catch specific non-fatal network exceptions (like `NetworkTimeoutError`).
  - [x] Ensure that after 3 failures, the error propagates so the orchestrator can assign a `give_up` status.
- [x] Task 3: Implement the `@circuit_breaker` Decorator
  - [x] Catch specific fatal exceptions (e.g. HTTP 403 Quota Exceeded for YouTube, caught as `YoutubeQuotaError`).
  - [x] When tripped, forcefully suspend execution of the targeted pipeline operations until the next chronological reset period (e.g. midnight PST for YouTube APIs).
- [x] Task 4: Implement Unit Tests
  - [x] Add rigorous test coverage in `tests/test_resilience.py`.
  - [x] Verify both the maximum 3-retry limit and the circuit breaker trip/sleep mechanics.

## Dev Notes

### Dev Agent Guardrails

- **Zero-Intrusion Design**: These patterns must be implemented as Python decorators to keep the core business logic in fetchers and uploaders completely decoupled from retry/sleep mechanics.
- **No Bare Exceptions**: Never use `except Exception:`. Explicitly catch targeted exceptions to prevent masking other critical system failures.
- **Log Interpolation**: Adhere strictly to the logging pattern: `logger.error("Failed because of: %s", err)`. **DO NOT** use `f-strings` in `logging` statements. This ensures the future log sanitization filter can scrub sensitive data out of the variables.
- **Native Implementation**: Implement these using native Python `asyncio.sleep` or `time.sleep` depending on the synchrony of the target methods, avoiding external third-party libraries (like tenacity) since the starter architecture calls for native decorators.

### Project Structure Notes

- **Code Locations**: 
  - `utils/decorators.py`: Location for the decorator implementations.
  - `tests/test_resilience.py`: Dedicated test file as outlined in the architectural directory tree.
- **Alignment with unified project structure**: The architectural document specifically dictates that these features reside in the `utils/` directory as cross-cutting support facilities.

### References

- Epic breakdown: `_bmad-output/planning-artifacts/epics.md` (FR18, FR19)
- Architect constraints: `_bmad-output/planning-artifacts/architecture.md` (API & Communication Patterns, Naming Conventions, Error Handling Patterns)

## Dev Agent Record

### Agent Model Used

Gemini 3.1 Pro (High)

### Debug Log References
- Pytest output verified all tests completed without regressions including asynchronous tests.

### Completion Notes List
- Sprint status was successfully updated to change epic-2 to `in-progress` and story 2-1 to `ready-for-dev`.
- Implemented `utils/exceptions.py` adding standard pipeline error taxonomy (`NetworkTimeoutError`, `YoutubeQuotaError`, `DouyinBlockError`).
- Migrated legacy sync-only @auto_retry and @circuit_breaker logic to fully transparent async/sync wrappers in `utils/decorators.py`.
- Built resilient native exponential backoff adhering strictly to maximum attempts limits via `asyncio.sleep()`.
- Confirmed with unit tests that `circuit_breaker` trips gracefully upon Quota Exhaustion block events calculating correct suspense times up to chronological Midnight PST reset.

### File List
- `utils/exceptions.py` (New file)
- `utils/decorators.py` (Modified file)
- `tests/test_resilience.py` (New file)

### Review Findings
- [x] [Review][Patch] Spec violation: Default Exception catch tuple violates "No Bare Exceptions" guardrail. — Fixed by defaulting to `(BasePipelineError,)`.
- [x] [Review][Patch] `auto_retry` crashes with `TypeError` if `max_retries <= 0`. [utils/decorators.py] — Fixed by clamping to `max(1, max_retries)`.
