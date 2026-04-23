---
title: 'Epic 1.2: Implement ConfigManager & Proxy Parsing'
type: 'feature'
created: '2026-04-19'
status: 'done'
baseline_commit: 'NO_VCS'
context: ['_bmad-output/implementation-artifacts/epic-1-context.md', 'config.json']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The data pipeline requires dynamic configuration parameters (Douyin accounts, Cookies, YouTube OAuth paths, and proxies) that users can edit locally. Currently, a `config.json` exists on disk, but the Python backend has no centralized, structured way to parse it, provide defaults, or translate proxy strings into usable Python standard dicts for HTTP requests.

**Approach:** Develop `modules/config_manager.py`. Build a `ConfigManager` class that parses `config.json`, caches it in memory, and provides a `reload()` function (essential for the future Tray UI "Hot Reload" feature). Expose a dedicated network proxy formatter helper that constructs `{"http": ..., "https": ...}` dicts for downstream modules.

## Boundaries & Constraints

**Always:** 
- Cache the loaded JSON configuration in memory to avoid repetitive disk I/O on every API call.
- Provide a robust `reload()` method to refresh the cache.
- Expose settings via dictionary-like access (e.g., `config.get("douyin_cookie", "")`) with safe fallbacks.

**Ask First:** 
- If you need to fundamentally restructure the existing `config.json` keys (e.g., changing `max_retry` to a nested object).

**Never:** 
- Implement code that *writes* or *modifies* the user's `config.json`. This tool operates on read-only configuration assumptions.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Healthy Config | `config.json` exists and is valid | Loaded into memory, `.get("proxy")` returns value | N/A |
| Missing File | `config.json` does not exist | Logs critical failure and raises error | `FileNotFoundError` |
| Malformed JSON | User missed a comma in `config.json` | Rejects load, retains previous working config in memory | Catch `JSONDecodeError`, log error but don't crash if previously loaded |

</frozen-after-approval>

## Code Map

- `modules/config_manager.py` -- Global settings parser and proxy dictionary generation.
- `main.py` -- Inject the config manager into the daemon lifecycle for verification.

## Tasks & Acceptance

**Execution:**
- [x] `modules/config_manager.py` -- Create `ConfigManager` singleton that parses `config.json`, handles `reload()`, and handles `get_proxies()`. -- Rationale: Centralized settings state.
- [x] `main.py` -- Import `config` from `config_manager.py`, and print a parameter (e.g., `bark_server`) in the test loop. -- Rationale: Verify singleton instantiation and integration.

**Acceptance Criteria:**
- Given a valid `config.json`, when `config.get('douyin_accounts')` is called, it returns the parsed Python list.
- Given `config.json` specifies `"proxy": "http://127.0.0.1:7890"`, when `config.get_proxies()` is called, it returns `{"http": "http://127.0.0.1:7890", "https": "http://127.0.0.1:7890"}`.
- Given an invalid JSON update, when `reload()` is called, it gracefully logs the JSON decode error without crashing the application.

## Spec Change Log

## Design Notes

```python
# Singleton Instantiation Example
class ConfigManager:
    ...
    def get_proxies(self):
        proxy = self.get("proxy", "").strip()
        return {"http": proxy, "https": proxy} if proxy else None

# Pre-instantiate for global import
config = ConfigManager()
```

## Verification

**Commands:**
- `python main.py` -- expected: Daemon starts, logger prints a configuration key (e.g., loaded X accounts), and sleeps, proving parsing works.

## Suggested Review Order

- Config parsing Singleton pattern with fallback Reload guard
  [`config_manager.py:7`](../../modules/config_manager.py#L7)

- Request-compatible `get_proxies()` translator
  [`config_manager.py:35`](../../modules/config_manager.py#L35)

- Integration of Config validation into daemon lifespan
  [`main.py:18`](../../main.py#L18)
