import sys
import time
import threading

from modules.logger import logger
from modules.database import db
from modules.config_manager import config
from modules.tray_app import TrayController
from modules.scheduler import PipelineCoordinator


def background_daemon(stop_event: threading.Event, coordinator: PipelineCoordinator):
    """The central data pipeline background loop."""
    logger.info("Background daemon pipeline starting.")
    
    # Prove the foundations are still alive and accessible in the subthread
    with db.get_connection() as conn:
        mode = conn.cursor().execute("PRAGMA journal_mode;").fetchone()[0]
    
    douyin_accounts = config.get("douyin_accounts", [])
    logger.info(f"Data Pipeline fully initialized. DB Mode: {mode} | Discovered Accounts: {len(douyin_accounts)}")
    
    coordinator.start()
    
    # Infinite loop isolated from Windows UI lock. Runs until Exit clicks Set stop_event.
    while not stop_event.is_set():
        # Fast 1s polling granularity guarantees fast teardown responses.
        stop_event.wait(timeout=1.0)
        
    coordinator.shutdown()
    logger.info("Background daemon loop completed gracefully.")


def main():
    logger.info("Initializing DouyinSync Launch sequence...")
    
    # 1. Establish the Thread-Safe communication switch
    stop_event = threading.Event()
    
    # 2. Create the shared coordinator (single instance for the entire app)
    coordinator = PipelineCoordinator()
    
    # 3. Extract and launch core blocking routines into an isolated non-UI daemon thread
    daemon_thread = threading.Thread(
        target=background_daemon, 
        args=(stop_event, coordinator), 
        daemon=True,
        name="DataPipelineWorker"
    )
    daemon_thread.start()
    
    # 4. Hijack Main Thread rendering rights for Microsoft Windows specific UI safety.
    try:
        tray = TrayController(stop_event)
        tray.coordinator = coordinator  # Wire up for in-process manual_run
        # `.run()` acts as blocking loop internally until user clicks 'Exit'
        tray.run() 
    except KeyboardInterrupt:
        logger.warning("Caught keyboard interrupt. Signaling shutdown flag to workers.")
        stop_event.set()
        
    # Wait maximum 3s for background thread loop to safely close files/DB connection
    daemon_thread.join(timeout=3.0)
    logger.info("DouyinSync pipeline application officially closed. End of cycle.")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "dashboard":
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
    
    main()