import sys
import time
import threading

from modules.logger import logger
from modules.database import db
from modules.config_manager import config
from modules.tray_app import TrayController
from modules.scheduler import PipelineCoordinator


def background_daemon(stop_event: threading.Event):
    """The central data pipeline background loop."""
    logger.info("Background daemon pipeline starting.")
    
    # Prove the foundations are still alive and accessible in the subthread
    with db.get_connection() as conn:
        mode = conn.cursor().execute("PRAGMA journal_mode;").fetchone()[0]
    
    douyin_accounts = config.get("douyin_accounts", [])
    logger.info(f"Data Pipeline fully initialized. DB Mode: {mode} | Discovered Accounts: {len(douyin_accounts)}")
    
    # Instantiate Epic 4 Controller
    coordinator = PipelineCoordinator()
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
    
    # 2. Extract and launch core blocking routines into an isolated non-UI daemon thread
    daemon_thread = threading.Thread(
        target=background_daemon, 
        args=(stop_event,), 
        daemon=True,
        name="DataPipelineWorker"
    )
    daemon_thread.start()
    
    # 3. Hijack Main Thread rendering rights for Microsoft Windows specific UI safety.
    try:
        tray = TrayController(stop_event)
        # `.run()` acts as blocking loop internally until user clicks 'Exit'
        tray.run() 
    except KeyboardInterrupt:
        logger.warning("Caught keyboard interrupt. Signaling shutdown flag to workers.")
        stop_event.set()
        
    # Wait maximum 3s for background thread loop to safely close files/DB connection
    daemon_thread.join(timeout=3.0)
    logger.info("DouyinSync pipeline application officially closed. End of cycle.")


if __name__ == "__main__":
    main()
