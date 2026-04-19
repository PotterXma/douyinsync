# Architecture Document

## Overview
DouyinSync implements an event-driven decoupled cron pipeline where fetchers, downloaders, and uploaders operate independently, communicating state sequentially via a local SQLite `.db` registry.

## Components & Modules

### 1. The Coordinator (`scheduler.py`)
Central conductor using `APScheduler`. Executes every X minutes (default 30) configured via `config.json`. Enforces business logic: ensuring disk space availability, pausing if YouTube QUOTA drops, or rescuing zombie tasks on boot crash.

### 2. Douyin Fetcher (`douyin_fetcher.py`)
Spoofs Windows Chrome footprints and hashes signatures natively using `abogus`. Skips unsupported payloads (like Image Tuwens) and isolates purely the highest-resolution MP4 chunks and Webp covers. 

### 3. State Management (`database.py`)
Locks items via `douyin_id` string hashes. Primary statuses loop through: `pending -> processing -> downloaded -> uploading -> uploaded`. Ensures idempotency.

### 4. Downloader and YouTube Uploader (`downloader.py`, `youtube_uploader.py`)
Streams video in low-memory `iter_content` loops. Passes media to Google API's `MediaFileUpload(resumable=True)`.

### 5. CLI & Testing
`test_pipeline.py` provides modular granular access points avoiding full scheduler engagement.
