# Epic 1 Context: Core System Setup & Configuration Management

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

This epic establishes the foundational pipeline architecture, secure logging constraints, global configuration parsing, and the concurrent SQLite (WAL mode) schema tracker. It provisions the base layer required for the independent Fetching and Uploading epics to operate concurrently and safely.

## Stories

- Story 1.1: Initialize Modular Architecture & Database Base
- Story 1.2: Implement ConfigManager & Proxy Parsing
- Story 1.3: Develop System Tray UI & Status Interrogation Menu

## Requirements & Constraints

- **Resilience**: The database must enforce WAL (Write-Ahead Logging) mode and use strict transaction checkpoints with backoff timeouts (e.g., `>= 10s`) to prevent deadlocks when GUI and background threads poll simultaneously.
- **Security**: Raw tokens or Cookies must *never* be persisted in plaintext. A Sanitizer layer must dynamically intercept log emissions and HTTP response dumps to redact sensitive keys.
- **Boot sequence**: Application termination states (`processing`) must automatically safely rollback to `pending` upon restart to avoid zombie state artifacts.

## Technical Decisions

- **Architecture Scaffold**: Strict adoption of the headless background daemon structure modeled after the `youtebe搬运` project. Core logic utilizes abstract pathing (`pathlib`).
- **Data Layer**: SQLite handles all inter-epic state tracking via predefined statuses (`pending`, `processing`, `uploaded`, `failed`, `give_up`). DB schema is lazily generated when specifically needed by the pipeline logic.
- **Config Management**: Uses external JSON file injection with "hot reload" support (handled via system tray IPC).
- **Concurrency & UI IPC**: System tray operates via `pystray`. Decoupling requires the main scheduling daemon and GUI worker to communicate safely without mutual blocking.

## cross-Story Dependencies

- Story 1.2 requires the base pipeline scaffold established in Story 1.1.
- Story 1.3 provides the user interface hooks (Tray Menu) into the mechanisms provisioned in 1.1 and 1.2.
