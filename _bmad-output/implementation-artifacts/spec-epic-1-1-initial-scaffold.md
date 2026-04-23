---
title: 'Epic 1.1: Initialize Modular Architecture & Database Base'
type: 'chore'
created: '2026-04-19'
status: 'done'
baseline_commit: 'NO_VCS'
context: ['_bmad-output/implementation-artifacts/epic-1-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The DouyinSync backend requires a completely resilient, concurrent execution foundation. Without a thread-safe data tracker (SQLite WAL) and secure logging, subsequent data scraping and uploading modules will corrupt each other's state or leak sensitive user Cookies into cleartext log files.

**Approach:** Scaffold the exact Python project skeleton modeled after `youtebe搬运`. Build a robust Database Access layer (`modules/database.py`) that strictly enforces SQLite's WAL (Write-Ahead Logging) mode upon connection. Set up a globally configured `logger.py` that includes a custom Filter/Sanitizer to dynamically redact secrets from all log streams.

## Boundaries & Constraints

**Always:** 
- Use native `sqlite3` and `logging` libraries. 
- Enforce `PRAGMA journal_mode=WAL` upon DB connection initialization.
- Use `pathlib` for all internal filesystem references.
- Create all persistable data (logs, db) in a local `dist/` or `data/` folder to prevent clutter.

**Ask First:** 
- If adding any third-party pip dependencies beyond standard libraries at this stage.
- If altering the core backend module structure `modules/`.

**Never:** 
- Bulk-create domain-specific tables (like `videos` or `deduplication`) in this story—this story only establishes the base DAO architecture and `WAL` initialization.
- Write raw tokens/cookies/passwords to disk under any debug level.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| New Install | `dist/douyinsync.db` missing | Creates file and executes `PRAGMA journal_mode=WAL` | Raise OSError if disk full/locked |
| Log Emission | `logger.info("sessionid=123xyz")` | Logs `sessionid=[REDACTED_SECRET]` | Failsafe: drop bad key, print warning |

</frozen-after-approval>

## Code Map

- `main.py` -- Application entry daemon (initializes DB and Logger, keeps process alive).
- `modules/database.py` -- SQLite DAO layer providing connection factory and `WAL` enforcer.
- `modules/logger.py` -- Structured logging with custom regex `SanitizerFilter` and daily rotating file handler.
- `requirements.txt` -- Base setup dependency pin.

## Tasks & Acceptance

**Execution:**
- [x] `modules/logger.py` -- Implement global `logging` configuration with a rotating file handler and a `RegexFilter` that scrubs `sessionid`, `a_bogus`, `access_token` -- Rationale: Zero-exfiltration. 
- [x] `modules/database.py` -- Implement a `get_connection()` context manager/factory that auto-executes `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;` -- Rationale: Prevent UI vs Background concurrency blocks.
- [x] `main.py` -- Import logger and db base; run a sleep daemon -- Rationale: Anchor process for later scheduling.

**Acceptance Criteria:**
- Given a fresh run, when `main.py` executes, then `dist/douyinsync.db` and `logs/douyinsync.log` are generated automatically.
- Given the app runs, when queried by CLI, then `douyinsync.db` returns `WAL` as the journal mode.
- Given a log is emitted containing sensitive data, when captured in `logs/douyinsync.log`, then exactly that snippet is replaced with a redacting mask string.

## Spec Change Log

## Design Notes

```python
# Secret Sanitization Filter Strategy
class SecretSanitizer(logging.Filter):
    def filter(self, record):
        msg = str(record.msg)
        record.msg = re.sub(r'(sessionid=|access_token=)[^&\s]+', r'\1[REDACTED]', msg)
        return True
```

## Verification

**Commands:**
- `python main.py` -- expected: Starts gracefully without errors, generates standard pipeline folders (`dist/`, `logs/`).
- `sqlite3 dist/douyinsync.db "PRAGMA journal_mode;"` -- expected: Prints `wal`.

## Suggested Review Order

- Daemon anchor preventing early exit and initializing dependencies
  [`main.py:1`](../../main.py#L1)

- SQLite context manager with pre-configured WAL pragma
  [`database.py:17`](../../modules/database.py#L17)

- Log sanitizer that intercepts and redacts sensitive credentials
  [`logger.py:11`](../../modules/logger.py#L11)
