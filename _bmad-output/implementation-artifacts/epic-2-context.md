# Epic 2 Context: Douyin Content Collection & Processing

<!-- Compiled from planning artifacts. Edit freely. Regenerate with compile-epic-context if planning docs change. -->

## Goal

This epic establishes the frontline crawler and deduplication layer. It tracks unique Douyin videos using a SQLite State Machine, fetches metadata from target profiles safely, and downloads the heavy MP4/WebP files via chunked I/O—converting the cover art to JPEG formats needed for Epic 3's YouTube uploads.

## Stories

- Story 2.1: SQLite Deduplication State Machine
- Story 2.2: Douyin Profile Fetcher & Metadata Parser
- Story 2.3: Stream Download Engine & Cover Format Converter

## Requirements & Constraints

- **Zero Duplication**: The database MUST use the video's unique `douyin_id` as the primary key. Existing non-pending processing states must skip downloads to prevent double-upload or bandwidth waste.
- **Resilient Media Parsing**: Image-posts (图文集) must be detected and gracefully skipped. No crashes allowed.
- **Resource Limits**: Video downloads must enforce memory-efficient chunked streaming `< 300MB` overhead.

## Technical Decisions

- **State Machine**: The `videos` table dictates the pipeline. Valid statuses: `pending`, `processing`, `downloaded`, `uploaded`, `failed`, `give_up_fatal`.
- **Image Conversion**: WebP to JPEG is done instantly post-download via `Pillow`.

## Cross-Story Dependencies

- Story 2.3 relies entirely on the deduplicated targets passed down by Story 2.1 and the extraction logic mapped in Story 2.2.
