# Story 2.3: Log Sanitization and Rotation

Status: done

## Story

As a low-maintenance daemon,
I want logs to auto-rotate daily and sanitize tokens,
So that data secrets never land in local storage or flood SSD space.

## Acceptance Criteria

1. Given active pipeline processes When writing to python logging Then tokens/cookies are asterisked out via Filter layer.
2. Given active pipeline processes When writing to python logging Then log rotation enforces max 10MB per file and retains no more than 5 historic backups.

## Tasks / Subtasks

- [x] Task 1: Implement LogSanitizer Filter in utils/sanitizer.py (AC: 1)
  - [x] Create class LogSanitizer(logging.Filter) overriding filter(self, record).
  - [x] Define SENSITIVE_PATTERNS constant with regex patterns for sessionid, access_token, client_secret, cookie, bearer.
  - [x] Apply substitutions against record.getMessage() via re.sub(), replacing matched values with REDACTED.
  - [x] Set record.msg and clear record.args in-place so handlers emit the sanitized string.
  - [x] Return True always (sanitizer mutates content, never drops records).
- [x] Task 2: Configure Global Rotating File Handler in utils/logger.py (AC: 2)
  - [x] Create utils/logger.py with setup_logging(log_dir, level) function.
  - [x] Create log_dir via os.makedirs(log_dir, exist_ok=True).
  - [x] Initialize RotatingFileHandler with maxBytes=10MB and backupCount=5.
  - [x] Add StreamHandler for console output at level INFO.
  - [x] Attach LogSanitizer() to both handlers.
- [x] Task 3: Integrate setup_logging at application entry point (AC: 1, 2)
  - [x] Call setup_logging() as the very first operation inside main.py.
- [x] Task 4: Enforce lazy-interpolation style across existing modules (AC: 1)
  - [x] Fixed f-string log calls in modules/youtube_uploader.py, config_manager.py, notifier.py, sweeper.py, downloader.py, tray_app.py, win_ocr.py, main.py.
- [x] Task 5: Develop Unit Tests in tests/test_sanitizer.py (AC: 1, 2)
  - [x] Test: LogSanitizer masks access_token= patterns.
  - [x] Test: LogSanitizer masks Douyin sessionid= cookie patterns.
  - [x] Test: LogSanitizer passes innocuous message unchanged.
  - [x] Test: LogSanitizer handles un-interpolated log record args safely.
  - [x] Test: setup_logging creates logs/ directory with RotatingFileHandler + StreamHandler.

### Review Findings
- [x] [Review][Patch] Double Logging Configuration & Sanitizer Bypass [modules/youtube_uploader.py:9] - FIXED

## Dev Agent Record

### Agent Model Used
Claude Sonnet 4.6 (Thinking)

### Completion Notes List
- Created utils/sanitizer.py: LogSanitizer(logging.Filter) with compiled regex for sessionid, access_token, client_secret, cookie, bearer. Always returns True.
- Created utils/logger.py: setup_logging() with RotatingFileHandler (10MB, backupCount=5) + StreamHandler + LogSanitizer on both. Returns handler tuple for tests.
- Modified main.py: Added setup_logging() as very first import.
- Fixed f-string log violations in 8 files across modules/.
- Created tests/test_sanitizer.py: 19 tests all passing.
- Full regression: 50/50 passed, 0 regressions.

### File List
- utils/sanitizer.py (New)
- utils/logger.py (New)
- tests/test_sanitizer.py (New)
- main.py (Modified)
- modules/youtube_uploader.py (Modified)
- modules/config_manager.py (Modified)
- modules/notifier.py (Modified)
- modules/sweeper.py (Modified)
- modules/downloader.py (Modified)
- modules/tray_app.py (Modified)
- modules/win_ocr.py (Modified)
