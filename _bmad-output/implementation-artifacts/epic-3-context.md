# Epic 3 Context: YouTube Content Publishing

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

This epic represents the final publishing stage. It constructs a secure connection to the YouTube Data API v3, applying automatic truncation to imported Douyin text to prevent rejection by YouTube's strict length constraints, and executing robust chunked-stream video uploads alongside custom thumbnail publication.

## Stories

- Story 3.1: YouTube Metadata Sanitization & Injection
- Story 3.2: Resumable Video Stream Uploader 
- Story 3.3: Custom JPEG Thumbnail Publisher

## Requirements & Constraints

- **Split-Tunneling Network**: YouTube API endpoints must respect the `proxy` set in `config.json`, unlike the direct domestic connection used for Douyin.
- **Resilient Upload**: `MediaFileUpload` chunking MUST be used to prevent RAM spikes (`NFR2`). Videos could be >500MB.
- **Metadata Boundaries**: Titles must be truncated to <= 100 chars, description to <= 5000 chars, appending `...` safely inside UTF-8.

## Technical Decisions

- **Identity Management**: Uses standard OAuth `client_secret.json` loading with local token caching.
- **Module Design**: `modules/youtube_uploader.py` bridges all three stories as a unified publisher logic sequence.
