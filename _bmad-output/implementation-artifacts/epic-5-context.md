# Epic 5 Context: Data Observability, Cleanup & Push Notifications

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

This epic represents the monitoring and maintenance layer. The application must communicate its successes and failures without requiring constant terminal hawking via Bark push notifications to Mobile. It also requires an on-demand graphical overview via Tkinter and an autonomous janitor (`DiskSweeper`) preventing infinite disk caching.

## Stories

- Story 5.1: Multi-tiered Bark Push Notifications & Aggregation
- Story 5.2: SQLite Visual Sync Dashboard
- Story 5.3: Autonomous Local Disk Sweeper

## Requirements & Constraints

- **Thread Independence**: Tkinter MUST run in isolation. Because `pystray` dominates the `.run()` block on the Main Thread, the `dashboard.py` MUST be invoked as a disparate Process (`subprocess.Popen`) to avoid catastrophic UI lockups.
- **Pre-flight Assertion**: Before downloading >500MB media, the sweeper must evaluate if Volume Space > 2GB.
- **Disk Janitor**: Any `*.mp4`, `*.webp`, or `*.jpg` surviving longer than configured retention bounds MUST logically be swept away by an APScheduler task.
