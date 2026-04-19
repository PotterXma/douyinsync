import logging
import os
import re
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

# Project root relative to this file
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Setup logs directory
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True, parents=True)
LOG_FILE = LOG_DIR / "douyinsync.log"

class SecretSanitizer(logging.Filter):
    """
    Dynamically redacts sensitive keys (e.g. sessionid, access_token) from logs.
    """
    def filter(self, record):
        msg = str(record.msg)
        # Redact common token patterns: matches `sessionid=VALUE` or `access_token=VALUE`
        # and replaces VALUE with [REDACTED]
        record.msg = re.sub(r'(sessionid=|access_token=|a_bogus=)[^&\s]+', r'\1[REDACTED]', msg, flags=re.IGNORECASE)
        return True

def setup_logger(name="DouyinSync"):
    logger = logging.getLogger(name)
    
    # Only configure if not already configured to prevent duplication
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(name)s | %(levelname)s | %(message)s'
        )
        
        # Rotating File Handler (Daily, max 5 backups)
        file_handler = TimedRotatingFileHandler(
            filename=LOG_FILE,
            when="midnight",
            interval=1,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(SecretSanitizer())
        
        # Console Handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(SecretSanitizer())
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
    return logger

logger = setup_logger()
