# Story 2.4: Local Storage Auto-Cleanup

Status: done

## Story

As a sustainable system,
I want background tracking that cleans leftover mp4/jpg assets,
So that continuous downloading does not monopolize User storage limits.

## Acceptance Criteria

1. Given hundreds of syncs (mp4, jpg, webp files accumulate in downloads/)
2. When the scheduled housekeeping (janitor_job) executes
3. Then all media files older than max_age_days (default: 7) are unlinked from the filesystem
4. And newer files are kept intact
5. And non-media extensions (e.g. .txt, .log) are never touched

## Tasks / Subtasks

- [x] Task 1: Harden modules/sweeper.py per-file exception handling (AC: 3, 5)
  - [x] Wrap each file_path.unlink() in try-except (PermissionError, OSError) so a locked file does not abort the sweep loop
  - [x] Log per-file error at WARNING level with lazy interpolation
- [x] Task 2: Wire storage_retention_days config into scheduler.py (AC: 3)
  - [x] In janitor_job(): read max_age_days = config.get storage_retention_days, 7 and pass it to sweeper.purge_stale_media()
- [x] Task 3: Create tests/test_sweeper.py with full coverage (AC: 1-5)
  - [x] Test: files older than threshold are deleted
  - [x] Test: files newer than threshold are kept
  - [x] Test: non-target extensions (.txt) are never deleted
  - [x] Test: check_preflight_space() returns False when disk free < 2 GB
  - [x] Test: check_preflight_space() returns True when disk free >= 2 GB
  - [x] Test: PermissionError during deletion does not halt the sweep loop

## Dev Agent Record

### Agent Model Used
Claude Sonnet 4.6 (Thinking)

### Completion Notes List
- Task 1: sweeper.py 逐文件增加 try-except (PermissionError, OSError)，保证单文件锁定不中断整个清扫循环
- Task 2: scheduler.janitor_job() 改为从 config 读取 storage_retention_days (默认 7)
- Task 3: 新建 tests/test_sweeper.py，15 个测试全部通过；全量回归 89/89 通过

### File List
- modules/sweeper.py (Modified)
- modules/scheduler.py (Modified)
- tests/test_sweeper.py (New)

### Change Log
