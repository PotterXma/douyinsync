# Story 4.4: Manual Run & Dual Schedule Modes

Status: done

## Story

As an operator,
I want to trigger a sync run manually and choose between interval-based and clock-based automation,
so that I can align runs with infrastructure limits and ad-hoc needs without waiting for the next tick.

## Acceptance Criteria

1. **Given** the tray daemon is running  
   **When** the user chooses “Run sync now” (tray) or creates the dashboard request flag  
   **Then** one non-overlapping `primary_sync_job` executes (same lock as scheduled runs).

2. **Given** `config.json` sets `sync_schedule_mode` to `interval`  
   **When** the coordinator starts or receives `RELOAD_CONFIG` after save  
   **Then** APScheduler registers a single `IntervalTrigger` using `sync_interval_minutes`.

3. **Given** `sync_schedule_mode` is `clock` and `sync_clock_times` lists valid `HH:MM` values (local time)  
   **When** the coordinator starts or reapplies schedule  
   **Then** one cron job per time slot is registered; invalid lists fall back to interval with a warning.

4. **Given** the settings UI saves schedule fields  
   **When** the user triggers tray “Reload Config”  
   **Then** primary jobs are removed and rebuilt from disk (`apply_primary_schedule`).

## Implementation Notes

- `config.json`: `sync_schedule_mode` (`interval` | `clock`), `sync_interval_minutes`, `sync_clock_times` (array of strings). Legacy `cron_hour` / `cron_minute` used when `sync_clock_times` is absent.
- Cross-process manual run: `utils.paths.manual_sync_request_path()` → touch `.manual_sync_request` (gitignored); daemon consumes before each queue wait.
- `ConfigManager.reload()` + `get()` read arbitrary keys from mirrored `_raw` (fixes prior silent defaults for non-`proxies` keys).

## Dev Agent References

- `modules/scheduler.py` — `_add_primary_sync_jobs`, `apply_primary_schedule`, `parse_clock_times_from_config`
- `main.py` — `RUN_PIPELINE_NOW`, `RELOAD_CONFIG` → `apply_primary_schedule`, flag polling
- `modules/ui_settings.py` — mode radio + interval / multi-line times
- `modules/config_manager.py` — `_raw`, `reload()`, corrected `_parse_and_store_locked` body
