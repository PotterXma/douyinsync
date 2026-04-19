from modules.scheduler import PipelineCoordinator
from modules.logger import logger
import logging
import sys

# Force console output to be immediately visible
logging.getLogger().setLevel(logging.DEBUG)

if __name__ == "__main__":
    logger.info("TEST TRIGGER: Starting manual pipeline execution override...")
    coord = PipelineCoordinator()
    
    # 强制立刻执行一次主干任务
    coord.primary_sync_job()
    
    logger.info("TEST TRIGGER: Manual cycle finished.")
