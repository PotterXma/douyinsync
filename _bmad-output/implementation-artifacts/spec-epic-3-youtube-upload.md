---
title: 'Epic 3: YouTube Uploader Engine'
type: 'feature'
created: '2026-04-19'
status: 'done'
baseline_commit: 'NO_VCS'
context: ['_bmad-output/implementation-artifacts/epic-3-context.md', 'config.json']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Downloaded MP4 videos sitting on disk generate no value. Because Douyin titles can exceed YouTube's 100-character limits, and the original WebP covers need mapping to YouTube's strict `thumbnails.set` paradigm, we need a formalized publishing agent equipped with `MediaFileUpload` chunking to gracefully push heavyweight files through proxy networks.

**Approach:** Develop `modules/youtube_uploader.py` which unifies Stories 3.1, 3.2, and 3.3. 
1. The class will authenticate utilizing `google-auth-oauthlib`, locally saving the token payload.
2. An internal scrubber maps metadata (`title[:95] + "..."` and `description`).
3. Core `MediaFileUpload` handles resumable API pushes bridging across the proxy tunnel.
4. Thumbnail insertion guarantees the finalized aesthetic.

## Boundaries & Constraints

**Always:** 
- Force standard `httplib2` requests beneath the Google API client to securely utilize the `config.get_proxies()` routing. (You MUST explicitly inject HTTP proxy wrappers into the build client).
- Use `chunksize=1024*1024*2` (2MB chunks) with `resumable=True` for robust transmission over unstable VPN proxies.

**Ask First:** 
- N/A

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Too Long Title | `title` scraped is 120 chars | Truncated to 97 chars + `...` | Prevent HTTP 400 rejection |
| Missing Thumbnail | `local_cover_path` is empty | Uploads video flawlessly, skips thumbnail step gracefully | N/A |

</frozen-after-approval>

## Code Map

- `modules/youtube_uploader.py` -- Central module encompassing authentication, sanitization, and upload execution.
- `requirements.txt` -- Adding Google OAuth tools.

## Tasks & Acceptance

**Execution:**
- [x] `requirements.txt` -- Append `google-api-python-client`, `google-auth-httplib2`, and `google-auth-oauthlib`.
- [x] `modules/youtube_uploader.py` -- Construct the OAuth Bootstrapper taking into account `httplib2.ProxyInfo` routing sourced from `config.json`.
- [x] `modules/youtube_uploader.py` -- Develop `upload_video_with_thumbnail(...)` using `MediaFileUpload`. 

**Acceptance Criteria:**
- Given a valid MP4 string, when uploaded, `description` and `title` are securely restricted.
- Given a proxy string, `googleapiclient` forces the traffic through the HTTP proxy tunnel.

## Suggested Review Order

- OAuth Local Token Caching and Authority refresh logic
  [`youtube_uploader.py:59`](../../modules/youtube_uploader.py#L59)

- Safe text truncation string slicing mapped against API maximum length constraints
  [`youtube_uploader.py:94`](../../modules/youtube_uploader.py#L94)

- Split-Tunneling Network logic constructing deep httplib2 Proxy Injection for API Client requests 
  [`youtube_uploader.py:32`](../../modules/youtube_uploader.py#L32)
