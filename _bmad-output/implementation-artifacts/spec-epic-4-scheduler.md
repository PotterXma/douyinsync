---
title: 'Epic 4: APScheduler Coordination & Hard Resilience'
type: 'feature'
created: '2026-04-19'
status: 'done'
baseline_commit: 'NO_VCS'
context: ['_bmad-output/implementation-artifacts/epic-4-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** We have all the puzzle pieces separately built (Tray UI, DB Schema, Uploader, Downloader, Fetcher), but there isn't a heart to pump the blood. If the python script is just run, it does nothing but sit in the system tray. Furthermore, if the system is halted accidentally, previously working database records are trapped in 'processing' forever.

**Approach:** 
1. Build `modules/scheduler.py` containing `PipelineCoordinator`.
2. Hook `APScheduler` up to fire the `primary_sync_job` automatically every X minutes.
3. Update `VideoDAO` to recover stranded database processes.
4. Replace the dummy loop in `main.py` with this exact coordinator.
5. Emplace the "Network Pre-Flight" check and "Circuit Breaker" to make it robust against typical proxy dropouts.

## Boundaries & Constraints

**Always:** 
- Execute the primary flow within a single sweeping `try...except Exception` layer in the cron task, ensuring a single bug doesn't terminate the whole timer.
- Recover 'processing' zombies instantly BEFORE APScheduler engages its first tick.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Zombie Found | `douyin_id=X` has `status=processing` on Start | Rewritten to `pending`. Count Retry++ | N/A |
| Upload Quota hit | YouTube API throws 403 `quotaExceeded` | Flag active; skips Youtube tasks for 24h | Douyin fetching still occurs! |

</frozen-after-approval>

## Code Map

- `modules/scheduler.py`
- `modules/database.py` (Add missing DAOs)
- `main.py` (Integration injection)

## Tasks & Acceptance

**Execution:**
- [x] Modify `modules/database.py` to add `revert_zombies()` and `get_pending_videos()`.
- [x] Modify `modules/youtube_uploader.py` to return `"QUOTA_EXCEEDED"`.
- [x] Create `modules/scheduler.py` managing network pre-flights, apscheduler, and end-to-end traversal logic.
- [x] Integrate `PipelineCoordinator` into `main.py` threading model.
- [x] Append `apscheduler` to `requirements.txt`.

**Acceptance Criteria:**
- Given a complete setup, `main.py` instantiates the scheduler correctly, printing "Background APScheduler engaged".
- Given a YouTube Quota exceed, the flag is raised and the video remains in `downloaded` state safely.

## Suggested Review Order

- Pipeline Traversing logic checking Network and Circuit Breakers
  [`scheduler.py:34`](../../modules/scheduler.py#L34)

- The Zombie State recovery hooks
  [`database.py:76`](../../modules/database.py#L76)

- Main.py Background injection 
  [`main.py:23`](../../main.py#L23)
