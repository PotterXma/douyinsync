# Story 1.1: Config Manager Parsing

Status: done

## Story

As a Pipeline Administrator,
I want the system to parse and monitor multiple Douyin accounts from a config.json file,
so that I can manage my sync targets without code changes.

## Acceptance Criteria

1. **Given** a valid `config.json` containing targets and proxies
2. **When** the Daemon starts up
3. **Then** it loads as a strongly-typed Dataclass model
4. **And** throws an organized exception blocking startup if malformed

## Tasks / Subtasks

- [x] Task 1: Define application configuration data models (AC: 1, 3)
  - [x] Subtask 1.1: Create `utils/models.py` (if it does not exist) to store configuration dataclasses.
  - [x] Subtask 1.2: Define strongly-typed dataclasses for configuration parts (e.g., `TargetConfig`, `ProxyConfig`).
  - [x] Subtask 1.3: Define the main `AppConfig` dataclass integrating targets and proxies.
- [x] Task 2: Implement ConfigManager logic (AC: 1, 2, 4)
  - [x] Subtask 2.1: Create `modules/config_manager.py`.
  - [x] Subtask 2.2: Implement `ConfigManager` class logic to read and parse `config.json`.
  - [x] Subtask 2.3: Implement specific exception handling (e.g., raise `ConfigParseError` or similar) that halts daemon startup upon invalid/missing configuration.
- [x] Task 3: Create tests for config manager (AC: 1, 2, 3, 4)
  - [x] Subtask 3.1: Create `tests/test_config_manager.py`.
  - [x] Subtask 3.2: Verify successful load of valid JSON mapping into the `AppConfig` dataclass.
  - [x] Subtask 3.3: Verify correct exceptions are thrown for missing file and malformed schema.

## Dev Notes

- **Architecture Compliance**:
  - The module MUST reside in `modules/config_manager.py`.
  - **Absolute Imports Only**: e.g., `from utils.models import AppConfig`. NO relative imports to eliminate ImportError risks.
  - State must flow in a strongly-typed manner via `@dataclass`. **Do not pass bare `dict` objects around.** 
  - Global Dataclasses like AppConfig should go into `utils/models.py`.
- **Naming Conventions**:
  - Functions and variables: `snake_case` (e.g., `load_config`).
  - Classes: `PascalCase` (e.g., `ConfigManager`, `ConfigParseError`).
- **Error Handling Details**:
  - Use specific custom exceptions when blocking startup rather than bare assertions (`except Exception:` is prohibited).
- **Tech Stack**: Python 3.10+, Type Hinting is strictly required for all signatures.

### Project Structure Notes

- Alignment with unified project structure: Requires touching `modules/config_manager.py` and `utils/models.py`.

### References

- Epic breakdown: [Source: planning-artifacts/epics.md]
- Architecture strict guidelines: [Source: planning-artifacts/architecture.md]

## Dev Agent Record

### Agent Model Used

Gemini 3.1 Pro (High)

### Debug Log References

### Completion Notes List

- Implemented strongly-typed dataclasses `AppConfig`, `TargetConfig`, `ProxyConfig` in `utils/models.py`.
- Replaced the old dict-based `ConfigManager` in `modules/config_manager.py` with strongly-typed `AppConfig` logic.
- ConfigManager now strictly enforces exception throwing (`ConfigParseError`, `ConfigNotFoundError`) when parsing fails, correctly enabling daemon startup blocking.
- Wrote extensive tests using `pytest` to fully cover invalid JSON syntax, missing target properties, and mapping accuracy. All 4 tests passed.

### File List

- `utils/models.py` (New)
- `modules/config_manager.py` (Modified)
- `tests/test_config_manager.py` (New)

### Review Findings
- [x] [Review][Decision] API Compatibility Breakage (Export rename, get() removed) — Is this intentional API breakage or an oversight?
- [x] [Review][Decision] Missing Target Validation — Missing 'targets' array defaults to [] instead of throwing an error. Should 0 targets block startup?
- [x] [Review][Patch] Thread Safety and Singleton State Overwriting [`modules/config_manager.py`]
- [x] [Review][Patch] Missing OSError and IsADirectoryError Exception Guards [`modules/config_manager.py`]
- [x] [Review][Patch] Missing primitive type validation for parsed JSON fields [`modules/config_manager.py`]
- [x] [Review][Patch] Missing strictly required signature type hints [`tests/test_config_manager.py`]
- [x] [Review][Patch] Temporary File orphaned on test crashes [`tests/test_config_manager.py`]

