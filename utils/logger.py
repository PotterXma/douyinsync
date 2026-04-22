"""
utils/logger.py

Central logging configuration for DouyinSync.

Call setup_logging() as the VERY FIRST operation in main.py before any other
module imports that might trigger logging. This configures the root logger so
that all child loggers (modules/*.py, utils/*.py) inherit handlers automatically.
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Tuple

from utils.sanitizer import LogSanitizer

_APP_LOGGER_NAME = "douyinsync"


def setup_logging(
    log_dir: str = "logs",
    level: int = logging.DEBUG,
) -> Tuple[RotatingFileHandler, logging.StreamHandler]:
    """
    Configure the application logger with:
    - RotatingFileHandler: logs/app.log, max 10MB per file, 5 historic backups.
    - StreamHandler: console output at INFO level.
    - LogSanitizer filter on both handlers to redact credentials.

    Also sets the root logger level so all child loggers inherit it.

    Args:
        log_dir: Directory for log files (created if absent). Defaults to "logs".
        level:   Logger verbosity. Defaults to logging.DEBUG.

    Returns:
        Tuple of (file_handler, console_handler) for testability.
    """
    # Create output directory safely (exist_ok avoids race conditions)
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "app.log")

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    sanitizer = LogSanitizer()

    # --- Rotating File Handler (10 MB cap, 5 backups) ---
    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(sanitizer)

    # --- Console Handler (INFO and above) ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(sanitizer)

    # Configure the named app logger (avoids conflicts with pytest's root captures)
    app_logger = logging.getLogger(_APP_LOGGER_NAME)
    app_logger.setLevel(level)

    # Also propagate level to root so child loggers in modules/ inherit it
    logging.getLogger().setLevel(level)

    # Avoid adding duplicate handlers on repeated calls (e.g. during testing)
    if not app_logger.handlers:
        app_logger.addHandler(file_handler)
        app_logger.addHandler(console_handler)

    return file_handler, console_handler
