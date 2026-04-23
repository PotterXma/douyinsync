---
title: 'Epic 2.1: SQLite Deduplication State Machine'
type: 'feature'
created: '2026-04-19'
status: 'done'
baseline_commit: 'NO_VCS'
context: ['_bmad-output/implementation-artifacts/epic-2-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** If we endlessly scrape Douyin profiles without memory, we will download identical gigabytes of videos every day and re-upload duplicates to YouTube, triggering bans and bandwidth exhaustion.
**Approach:** Extend `modules/database.py` with an idempotent schema tracking table `videos`. Implement `INSERT OR IGNORE` methods utilizing `douyin_id` as the primary key. Introduce state-transition methods (`mark_processing`, `mark_downloaded`, `mark_failed`) so pipeline workers know what is secure to grab without stepping on each other.

## Boundaries & Constraints

**Always:** 
- Use `INSERT OR IGNORE` or graceful `WHERE NOT EXISTS` clauses to discard duplicate `douyin_id`s on insertion automatically.
- Fallback `status` to `'pending'` on initial insert.

**Ask First:** 
- N/A

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| First Discovery | `videoA` is parsed | DB inserts `videoA` as `pending` | N/A |
| Duplicate Scrape | `videoA` in DB is `uploaded` / Scraper sees it again | `INSERT OR IGNORE` silently skips it, state remains `uploaded` | N/A |

</frozen-after-approval>

## Code Map

- `modules/database.py` -- Schema extension and `VideoDAO` data manipulation wrapper.

## Tasks & Acceptance

**Execution:**
- [x] `modules/database.py` -- Update `_initialize_db` to auto-create the `videos` table schema with all constraints. 
- [x] `modules/database.py` -- Create `VideoDAO` or helper methods: `insert_video()`, `get_pending_videos()`, `update_video_status()`. 

**Acceptance Criteria:**
- Given a script inserts a `douyin_id='123'`, it is saved as `pending`.
- When the same `douyin_id='123'` is inserted again by the crawler loop, it does not raise an exception and the state does not reset.

## Suggested Review Order

- Schema Generation Injection
  [`database.py:16`](../../modules/database.py#L16)
- Core Idempotent DAO Methods
  [`database.py:38`](../../modules/database.py#L38)
