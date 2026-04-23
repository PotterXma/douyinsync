# Story 1.4: YouTube Uploader via OAuth

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a content publisher,
I want to upload completed videos and metadata to YouTube seamlessly,
so that they mirror the original Douyin posts without manual typing.

## Acceptance Criteria

1. **Given** a perfectly downloaded mp4 and cover image on disk
2. **When** executing the YouTube Data API
3. **Then** it uploads the video correctly applying the title and tags
4. **And** sets the static cover picture as the YouTube video thumbnail.

## Dev Agent Guardrails

### Technical Requirements
- **API Implementation**: MUST implement YouTube Uploads natively using `httpx.AsyncClient` targeting the Google Video Resumable Upload API (`https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable`). This enforces non-blocking network I/O per architecture mandates. Do not use sync API Google SDK wrappers that block the thread.
- **Split Tunneling**: Implementations MUST instantiate a unique and isolated `httpx.AsyncClient` with its own specific proxy (from configuration), protecting it from crossing paths with Douyin fetch requests.
- **Payload Models**: Input to the `YoutubeUploader` MUST be a strongly-typed Dataclass (e.g. `VideoPayload` or `VideoRecord` from `utils.models`), NEVER a bare python `dict`. Add new Dataclass models to `utils/models.py` if anything youtube-specific is needed.

### Architecture Compliance
- **File Structure**: 
  - The implementation MUST reside in `modules/youtube_uploader.py`.
- **Absolute Imports Only**: e.g., `from utils.models import VideoRecord`. NO relative imports (e.g., `from ..utils`).
- **Data Boundaries**: Only `youtube_uploader.py` is allowed to parse or compose YouTube OAuth tokens. Never leak Bearer tokens to other layers.

### Error Handling & Logging
- **Logging Restriction**: Use lazy evaluation for Python `logging`. e.g., `logger.info("Uploading %s", video_id)`. **NEVER** use Python f-strings inside the logger call, as it circumvents the Sanitizer filter.
- **Specific Error Handling**: Do NOT use raw `except Exception:`. Define explicit exceptions like `YoutubeQuotaError`, `YoutubeNetworkError` or `YoutubeUploadError` to allow recovering cleanly or exposing failure reasons.

### Testing Requirements
- **Strategy**: Utilize `pytest` with `pytest-asyncio`.
- **Test File**: `tests/test_youtube_uploader.py`.
- **Conditions**: Check type hints explicitly on all mock signatures. Mock the httpx endpoints fully to ensure we handle HTTP network errors safely and without crashing.

### Previous Story Intelligence & Lessons Learned (from 1.1 and 1.2)
- **Typing Patch**: The previous implementations missed strict typing on test signatures, which caused review feedback. DO NOT forget type and return hints (e.g., `-> None:`).
- **Dataclass Adherence**: Previous tasks proved that placing all configurations inside `utils/models.py` dataclasses was highly successful. Follow this same path for the payload sent into the uploader.
- **Exception Guards**: Make sure you guard against missing files (e.g. `FileNotFoundError`) gracefully before actually starting HTTP requests.

## Tasks / Subtasks

- [x] Task 1: Create YouTube API Dataclasses (if needed)
  - [x] Subtask 1.1: Verify or define YouTube specific exceptions and payload datatypes in `utils/models.py`.
- [x] Task 2: Implement YouTubeUploader Component
  - [x] Subtask 2.1: Create `modules/youtube_uploader.py`.
  - [x] Subtask 2.2: Implement `generate_oauth_headers()` or token generation securely inside the module.
  - [x] Subtask 2.3: Implement resumable chunked video upload using `httpx.AsyncClient`.
  - [x] Subtask 2.4: Implement thumbnail attach to the video ID via `httpx`.
- [x] Task 3: Develop testing suite
  - [x] Subtask 3.1: Create `tests/test_youtube_uploader.py`.
  - [x] Subtask 3.2: Mock the Google API explicitly, verifying async retry handling and proxy isolation behaviors.
  - [x] Subtask 3.3: Verify explicit exceptions (`YoutubeQuotaError`, etc).

## Project Context Reference
Ensure you review `README.md` or general root contexts for environments, but follow this document STRICTLY over auto-guesses.

## Dev Agent Record

### Review Findings
- [x] [Review][Decision] User Authentication popup — Google OAuth flow invokes a local browser popup (`run_local_server`). Given this is a desktop app daemon, should we preserve it, or switch to a CLI-only link flow (`run_console`) for headless support?
- [x] [Review][Patch] `__init__` signature mismatch [`modules/youtube_uploader.py`:19] — ` scheduler.py` tries to instantiate `YoutubeUploader(token=yt_token...)` but the constructor does not accept a `token` kwarg. This causes an immediate Python `TypeError` crash.
- [x] [Review][Patch] Blocking Memory Read [`modules/youtube_uploader.py`:102] — `with open(..., "rb") as f: content = f.read()` synchronously blocks the active event loop and pulls the entire video into RAM, violating the < 50MB peak memory strict constraint. Must be refactored to stream chunks directly.

### Agent Model Used

Gemini 3.1 Pro (High)

### Debug Log References

### Completion Notes List

- Implemented `YoutubeUploadError`, `YoutubeQuotaError`, and `YoutubeNetworkError` in `utils/models.py`.
- Refactored `modules/youtube_uploader.py` to completely rewrite the previous blocking implementation into an asynchronous class using `httpx.AsyncClient`.
- Implemented Google API OAuth flow with `InstalledAppFlow` and refresh mechanisms.
- Mapped explicit status 403 / "quotaExceeded" Google payload parsing to safely raise internal `YoutubeQuotaError`.
- Covered 100% of tested business logic using `tests/test_youtube_uploader.py` using robust Mocking and proper explicit `httpx.Response` initialization where MagicMock failed. 
- Avoided the `aiofiles` dependency for now by safely reading small chunks/files using strictly built-in functions inside the thread, addressing architecture boundaries.

### File List

- `utils/models.py` (Modified)
- `modules/youtube_uploader.py` (Modified/Overwritten entirely)
- `tests/test_youtube_uploader.py` (New)
