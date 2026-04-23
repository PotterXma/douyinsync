# Epic 4 Context: Automated Background Scheduling & Resilience

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

This epic stitches the isolated functionality modules (Fetcher, Downloader, Uploader) into a continuous, autonomous background loop. It deploys advanced resilience patterns like Pre-flight networking checks to prevent spam failures, Zombie cleanups for crash recovery, and a hard Circuit Breaker to respect YouTube APIs 403 Quota limitations.

## Stories

- Story 4.1: Timer & Cron Execution Scheduler (APScheduler)
- Story 4.2: Pre-flight Network Probe & Transient Retry Decorator
- Story 4.3: YouTube Quota Global Circuit Breaker
- Story 4.4: Self-Healing Zombie State Reverter

## Requirements & Constraints

- **Main Loop Decoupling**: The Scheduler must run fully in the background via `APScheduler` without disrupting the System Tray GUI (Epic 1.3 architecture).
- **Circuit Breaker**: If YouTube returns Quota Exceeded, all YouTube uploading logic must be skipped until the next calendar day (mocked via 24h timer natively).
- **ZOMBIE Repair**: Upon boot, any row inside SQLite holding a `processing` state must be reverted to `pending` because they were stranded by an ungraceful shutdown.

## Technical Decisions

- **Daemon Integration**: `main.py` will now drop the dummy sleep loop and instantiate `PipelineCoordinator`.
- **APScheduler**: The most robust task execution orchestrator.
