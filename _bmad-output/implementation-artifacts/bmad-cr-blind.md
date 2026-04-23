**Role**: Blind Hunter
**Goal**: Find flaws, resource leaks, logic errors, and anti-patterns with ZERO context.

**Diff**:
+++ b/requirements.txt
+pystray==0.19.5
+Pillow==10.0.0

+++ b/modules/tray_app.py
[Added pystray Icon setup, reload_config using config.reload(), and exit using stop_event.set() + icon.stop()]

+++ b/main.py
[Moved while-loop to background threading.Thread. Added Event to join cleanly against TrayApp on the main thread.]
