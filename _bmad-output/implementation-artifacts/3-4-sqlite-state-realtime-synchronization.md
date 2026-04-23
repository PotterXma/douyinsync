# Story 3.4: SQLite State Realtime Synchronization

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As the UI Frontend,
I want to fetch SQLite data via timer-based passive read-only queries,
So that changes dynamically render onto my UI without pipeline direct manipulation.

## Acceptance Criteria

1. **Given** the Dashboard is visible
   **When** 3000ms `.after()` loops trigger
   **Then** it invokes a `SELECT COUNT` polling query safely grabbing DB telemetry
   **And** updates numbers correctly back onto the widget displays.

## Tasks / Subtasks

- [x] Task 1: Add Telemetry Query to VideoDAO (AC: 3)
  - [x] Update `modules/database.py` -> `VideoDAO` to add a new `get_pipeline_stats() -> dict[str, int]` method.
  - [x] Implement a safe `SELECT status, COUNT(*) FROM videos GROUP BY status` query.
  - [x] Add unit tests in `tests/test_database.py` (or `test_db_locks.py`) to verify it correctly groups counts.
- [x] Task 2: Implement Passive UI Polling Loop (AC: 1, 2)
  - [x] In `ui/dashboard_app.py` (or wherever the dashboard is implemented), create a polling mechanism using `CustomTkinter`'s `.after(3000, method)`.
  - [x] Inside the polled method, call `VideoDAO.get_pipeline_stats()` safely (wrap in try-except to avoid UI crash).
- [x] Task 3: Render Telemetry to Widgets (AC: 4)
  - [x] Map the dictionary of stats (pending, processing, uploaded, failed, give_up) to the respective CustomTkinter labels/cards in the Dashboard class.
  - [x] Ensure any UI update happens purely inside the main thread (Tkinter standard requirement).

## Dev Notes

### Architecture & Implementation Guidelines
- **Strict One-Way Data Flow**: 
  - Pipeline updates DB -> DB holds State -> UI reads DB every 3 seconds.
  - The UI MUST NOT have any SQL `UPDATE` / `INSERT` commands.
  - Do NOT pass objects between Pipeline and UI using Callbacks. Rely solely on this polling mechanism!
- **Database Safety**:
  - `VideoDAO` already wraps `sqlite3` using the `AppDatabase` context manager. You can safely call this from the main UI thread because `SQLite` is configured with `PRAGMA journal_mode=WAL` and `busy_timeout=10000`, effectively decoupling readers from writers.
- **CustomTkinter Loop**:
  - `root.after(3000, self.poll_db)` is non-blocking. Do **NOT** use `time.sleep()` in the UI thread.
  - `sqlite3.connect()` acts fast enough for simple `SELECT COUNT(*)` that it won't stutter the main loop frame-rate.
- **Dependency Isolation**:
  - Ensure `ui` only imports `from modules.database import VideoDAO`. It does NOT need to import pipeline runners.

### Known Traps to Avoid (Anti-patterns)
- ❌ Re-inventing the database connection. Must use `db.get_connection()` context manager already in `database.py`.
- ❌ Running `get_pipeline_stats` in a separate `threading.Thread`. Not necessary! `sqlite3` reads in WAL mode are lightning-fast. Keep it in the `.after()` callback on the main thread to avoid thread-safety issues with `CustomTkinter` labels.
- ❌ Using strings or unformatted dictionaries for logger if an error occurs. Stick to `logger.error("DB Poll failed: %s", e)` and avoid f-strings.
- ❌ Using `time.sleep(3)` which halts the GUI event loop.

### Project Structure Notes
- Modify `modules/database.py` (add `get_pipeline_stats`)
- Modify / Create Dashboard logic in `ui/dashboard_app.py`
- Absolute imports are required e.g. `from modules.database import VideoDAO`.

### References
- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.4: SQLite State Realtime Synchronization]
- [Source: _bmad-output/planning-artifacts/architecture.md#Frontend Architecture (UI IPC & GUI Framework)]
- [Source: _bmad-output/planning-artifacts/architecture.md#Pattern Examples]

## Dev Agent Record

### Agent Model Used
Gemini 3.1 Pro (High)

### Debug Log References
None

### Completion Notes List
- Evaluated `modules/database.py` and confirmed `VideoDAO` needs a bulk telemetry method.
- Documented disaster-prevention logic prohibiting threads/sleeping/callbacks in favor of Tkinter `.after()` & SQLite WAL reads.
- Validated UI components won't be blocked by UI polls.
- ✅ Implemented `get_pipeline_stats()` to safely aggregate DB counts without write-lock clashes.
- ✅ Created `ui/dashboard_app.py` UI skeleton with `CustomTkinter` displaying a visual sync map.
- ✅ Setup `.after(3000)` polling loop securely decoupled via `try...except sqlite.Error`.
- ✅ All 74 unit tests passed locally via regression check.

### File List
- modules/database.py
- ui/dashboard_app.py
- tests/test_database.py
