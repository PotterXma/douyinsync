---
title: 'Epic 5: Observability & Janitor Tools'
type: 'feature'
created: '2026-04-19'
status: 'done'
baseline_commit: 'NO_VCS'
context: ['_bmad-output/implementation-artifacts/epic-5-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Users can't see the database comfortably without writing SQL. Long-term pipeline background operations silently drown local SSDs in massive MP4 caches over months. Unhandled server outages go utterly unnoticed by the operator absent of mobile notifications.

**Approach:** 
1. Build `modules/sweeper.py` ensuring `Pillow` WebP residuals and MP4s older than 7 days are wiped out, checking system capacity natively before any major downloading.
2. Build `modules/notifier.py` implementing a robust HTTP request hooking into Bark's official `/Title/Body` syntax.
3. Build `modules/dashboard.py` generating a Python `tkinter` GUI executing the `GROUP BY status` query.
4. Integrate the Dashboard via System Tray triggers (`tray_app.py`) executing it as a sub-process so it doesn't freeze the Tray Icon.

## Boundaries & Constraints

**Always:** 
- Discard visual charts if they break across Windows resolutions—stick to clean `ttk.Treeview` tables.
- Protect Bark API hooks with `try...except` so offline statuses don't break the pipeline reporting loop.

**Ask First:** 
- N/A

</frozen-after-approval>

## Code Map

- `modules/sweeper.py`
- `modules/notifier.py` 
- `modules/dashboard.py`

## Tasks & Acceptance

**Execution:**
- [x] Create `sweeper.py` with `check_preflight_space()` and `purge_stale_files()`.
- [x] Create `notifier.py` standardizing the `pip` requests against the Bark App URL parsed from Config.
- [x] Create `dashboard.py` encapsulating `tkinter.Tk()` utilizing native grid spacing.
- [x] Update `tray_app.py` menu to inject "Open Dashboard" via `subprocess`.
- [x] Link `sweeper.py` into the `PipelineCoordinator` (`scheduler.py`).

## Suggested Review Order

- Tkinter GUI layout and Subprocess threading isolation 
  [`dashboard.py:16`](../../modules/dashboard.py#L16)

- Autonomous cleanup calculations by age boundary
  [`sweeper.py:28`](../../modules/sweeper.py#L28)
