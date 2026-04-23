**Role**: Blind Hunter
**Goal**: Inspect database.py, douyin_fetcher.py, and downloader.py for resource leaks, anti-patterns, and bad practices.

**Focus**:
- Unclosed HTTP sessions via `requests`.
- Unclosed File handles.
- Error suppression without logging.
