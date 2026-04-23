---
title: 'Epic 1.3: Develop System Tray UI & Status Interrogation Menu'
type: 'feature'
created: '2026-04-19'
status: 'done'
baseline_commit: 'NO_VCS'
context: ['_bmad-output/implementation-artifacts/epic-1-context.md']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The pipeline operates purely as an invisible background process. A user has no simple way to check if it's running, force an immediate configuration reload, or pause/terminate it gracefully without manually searching for the `python.exe` process in Task Manager and killing it.

**Approach:** Develop a lightweight Windows system tray UI using Python's `pystray` and `Pillow`. Construct a `TrayApp` controller in `modules/tray_app.py` that presents a right-click menu (Status, Reload Config, Process Exit). To ensure Windows GUI compatibility, `pystray` must possess the main thread, while the previous `main.py` daemon loop will be shifted into an asynchronous `threading.Thread` utilizing thread-safe `Event` flags to listen for shutdown signals.

## Boundaries & Constraints

**Always:** 
- Run the `pystray.Icon.run()` on the main execution thread; spawn the core pipeline looping logic as a background `daemon=True` thread to prevent Windows UI freezes.
- Generate a dynamic base icon using `Pillow` (e.g., a simple colored text square) so the app works standalone without shipping `.ico` asset files immediately.
- Use `threading.Event` to broadcast the terminate signal gracefully to the working loop.

**Ask First:** 
- If adding complex Tkinter/WebUI code to this exact module (Dashboards are scheduled for Epic 5).

**Never:** 
- Execute heavy, blocking backend tasks (e.g., config parsing, database writes) directly within a tray menu's `action(icon, item)` callback. Callbacks act only as signal dispatchers.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| User Action: Exit | Click "Exit" | Sets `stop_event`, tray unmounts, main thread ends gracefully | N/A |
| User Action: Reload | Click "Reload Config" | Calls `config.reload()` in background | If fails, UI remains responsive |

</frozen-after-approval>

## Code Map

- `modules/tray_app.py` -- GUI presentation layer building the `pystray.Icon` and menu actions.
- `main.py` -- Re-architected entrypoint bridging the UI main thread with the background scheduling thread.
- `requirements.txt` -- Dependency mapping.

## Tasks & Acceptance

**Execution:**
- [x] `requirements.txt` -- Add `pystray` and `Pillow` library definitions. -- Rationale: Prerequisite for rendering tray UI.
- [x] `modules/tray_app.py` -- Build dynamic icon payload and configure menu items (Status, Reload Config, Terminate). -- Rationale: Actionable user interface.
- [x] `main.py` -- Refactor to instantiate a `threading.Event()` passed into a background worker daemon loop. Transfer main thread control to `TrayApp.run()`. -- Rationale: Safe cross-thread termination.

**Acceptance Criteria:**
- Given `main.py` executes, when the process runs, a tray icon must appear in the Windows taskbar corner without crashing the script.
- Given the tray icon is right-clicked, when "Reload Config" is selected, the logger should output that configuration was refreshed successfully.
- Given the app traverses its standard loop, when the user selects "Exit" from the tray, the entire Python process terminates smoothly within 2 seconds.

## Spec Change Log

## Design Notes

```python
# Main Thread Decoupling Pattern
stop_event = threading.Event()

def background_task(stop_event):
    while not stop_event.is_set():
        time.sleep(1)

# Inside main() ->
threading.Thread(target=background_task, args=(stop_event,), daemon=True).start()
tray_app.run()  # Blocks until exit
```

## Verification

**Commands:**
- `pip install -r requirements.txt` -- expected: successfully installs pystray and Pillow
- `python main.py` -- expected: Icon appears in notification area. Right clicking allows safe application exit returning exit code 0.

## Suggested Review Order

- Threading decouping and Background Daemon initialization
  [`main.py:31`](../../main.py#L31)

- Dynamic Pillow icon generator and tray layout
  [`tray_app.py:8`](../../modules/tray_app.py#L8)

- Cross-thread execution of graceful Tray Teardown signalling
  [`tray_app.py:43`](../../modules/tray_app.py#L43)
