import sys
import subprocess
import threading
import queue
from pathlib import Path

# ── Logging MUST be configured before any other module import ──────────────
from utils.paths import data_root
from utils.logger import setup_logging

setup_logging(str(data_root() / "logs"))
# ───────────────────────────────────────────────────────────────────────────

from modules.logger import logger
from modules.database import db
from modules.config_manager import config
from ui.tray_icon import TrayApp
from utils.models import AppEvent
from modules.scheduler import PipelineCoordinator
from utils.paths import (
    manual_force_retry_request_path,
    manual_sync_request_path,
    reload_config_request_path,
)


def _launch_dashboard_subprocess() -> None:
    """Spawn CustomTkinter HUD (same contract as modules/tray_app.py)."""
    if getattr(sys, "frozen", False):
        exe_dir = str(Path(sys.executable).parent)
        subprocess.Popen([sys.executable, "dashboard"], cwd=exe_dir, close_fds=False)
    else:
        project_root = Path(__file__).resolve().parent
        subprocess.Popen(
            [sys.executable, str(project_root / "main.py"), "dashboard"],
            cwd=str(project_root),
            close_fds=False,
        )


def _launch_settings_subprocess() -> None:
    """Spawn settings UI (``main.py settings`` / ``DouyinSync.exe settings``)."""
    if getattr(sys, "frozen", False):
        exe_dir = str(Path(sys.executable).parent)
        subprocess.Popen([sys.executable, "settings"], cwd=exe_dir, close_fds=False)
    else:
        project_root = Path(__file__).resolve().parent
        subprocess.Popen(
            [sys.executable, str(project_root / "main.py"), "settings"],
            cwd=str(project_root),
            close_fds=False,
        )


def _consume_manual_sync_request_file() -> bool:
    """Dashboard subprocess touches ``.manual_sync_request``; daemon runs one cycle and deletes it."""
    p = manual_sync_request_path()
    if not p.is_file():
        return False
    try:
        p.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _consume_manual_force_retry_request_file() -> bool:
    """Dashboard ``.manual_force_retry_request`` — one cycle with retry-cap bypass and DB normalization."""
    p = manual_force_retry_request_path()
    if not p.is_file():
        return False
    try:
        p.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _consume_reload_config_request_file() -> bool:
    """Settings UI touches ``.reload_config_request`` so the daemon reapplies schedule without tray menu."""
    p = reload_config_request_path()
    if not p.is_file():
        return False
    try:
        p.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def background_daemon(event_queue: queue.Queue, coordinator: PipelineCoordinator):
    """The central data pipeline background loop."""
    logger.info("Background daemon pipeline starting.")
    
    # Prove the foundations are still alive and accessible in the subthread
    with db.get_connection() as conn:
        mode = conn.cursor().execute("PRAGMA journal_mode;").fetchone()[0]
    
    douyin_accounts = config.get("douyin_accounts", [])
    logger.info("Data Pipeline fully initialized. DB Mode: %s | Discovered Accounts: %s", mode, len(douyin_accounts))
    
    coordinator.start()
    
    # Infinite loop isolated from Windows UI lock.
    while True:
        if _consume_reload_config_request_file():
            logger.info("Reload config request file consumed (e.g. from settings dashboard).")
            if config.reload():
                coordinator.apply_primary_schedule()
        if _consume_manual_force_retry_request_file():
            logger.info("Manual sync: force-retry request (normalize give_up/failed; bypass per-attempt caps).")
            coordinator.primary_sync_job(force_retry_bypass=True)
        elif _consume_manual_sync_request_file():
            logger.info("Manual sync: request file from Dashboard (or external touch).")
            coordinator.primary_sync_job()
        try:
            event = event_queue.get(timeout=1.0)
            if event.command == "EXIT":
                logger.info("Received EXIT command. Shutting down daemon.")
                break
            elif event.command == "RELOAD_CONFIG":
                logger.info("Reloading config.")
                if config.reload():
                    coordinator.apply_primary_schedule()
            elif event.command == "RUN_PIPELINE_NOW":
                logger.info("Manual sync: tray command RUN_PIPELINE_NOW.")
                coordinator.primary_sync_job()
            elif event.command == "OPEN_DASHBOARD":
                logger.info("Open dashboard command received.")
                try:
                    _launch_dashboard_subprocess()
                except Exception as e:
                    logger.exception("Failed to spawn dashboard subprocess: %s", e)
            elif event.command == "OPEN_SETTINGS":
                logger.info("Open settings command received.")
                try:
                    _launch_settings_subprocess()
                except Exception as e:
                    logger.exception("Failed to spawn settings subprocess: %s", e)
        except queue.Empty:
            pass
            
    coordinator.shutdown()
    logger.info("Background daemon loop completed gracefully.")


def main():
    logger.info("Initializing DouyinSync Launch sequence...")
    
    # 1. Establish the Thread-Safe communication switch
    event_queue = queue.Queue()
    
    # 2. Create the shared coordinator (single instance for the entire app)
    coordinator = PipelineCoordinator()
    
    # 3. Extract and launch core blocking routines into an isolated non-UI daemon thread
    daemon_thread = threading.Thread(
        target=background_daemon, 
        args=(event_queue, coordinator), 
        daemon=True,
        name="DataPipelineWorker"
    )
    daemon_thread.start()
    
    # 4. Hijack Main Thread rendering rights for Microsoft Windows specific UI safety.
    try:
        tray = TrayApp(event_queue)
        # `.run()` acts as blocking loop internally until user clicks 'Exit'
        tray.run() 
    except KeyboardInterrupt:
        logger.warning("Caught keyboard interrupt. Signaling shutdown flag to workers.")
        event_queue.put(AppEvent(command="EXIT"))
        
    # Wait maximum 3s for background thread loop to safely close files/DB connection
    daemon_thread.join(timeout=3.0)
    logger.info("DouyinSync pipeline application officially closed. End of cycle.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "dashboard":
            # Epic 5: CustomTkinter HUD in isolated subprocess (tray spawns this).
            from ui.dashboard_app import DashboardApp

            DashboardApp().run()
            sys.exit(0)
        elif sys.argv[1] == "videolib":
            # Classic Tk tree + reset workflow (optional deep management).
            from modules import dashboard

            dashboard.run_dashboard()
            sys.exit(0)
        elif sys.argv[1] == "settings":
            from modules import ui_settings
            ui_settings.run_settings_ui()
            sys.exit(0)
        elif sys.argv[1] == "stats":
            from modules import ui_stats
            ui_stats.run_stats_ui()
            sys.exit(0)
        elif sys.argv[1] == "manual_run":
            # For manual execution, run in same process 
            # (since it's already a detached subprocess fork)
            import test_pipeline
            test_pipeline.setup_logging()
            test_pipeline.test_e2e()
            sys.exit(0)
        elif sys.argv[1] == "bark_test":
            # Standalone Bark push test: does not require pipeline execution.
            from modules.notifier import BarkNotifier

            title = "DouyinSync Bark Test"
            message = "这是一条测试推送（含铃声）。"
            if len(sys.argv) > 2 and str(sys.argv[2]).strip():
                message = str(sys.argv[2]).strip()
            BarkNotifier().push(title, message, level="active")
            sys.exit(0)
    
    main()