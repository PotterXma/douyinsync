"""
tests/test_sanitizer.py

Unit tests for utils.sanitizer.LogSanitizer and utils.logger.setup_logging.

Tests verify that:
- LogSanitizer redacts access_token= patterns in plain log messages
- LogSanitizer redacts Douyin cookie sessionid= patterns
- LogSanitizer passes innocuous messages through unchanged
- LogSanitizer safely handles un-interpolated log record args
- setup_logging creates the logs/ directory and attaches RotatingFileHandler + StreamHandler
"""

import logging
import os
import shutil
import tempfile
import pytest

from utils.sanitizer import LogSanitizer, sanitize_message
from utils.logger import setup_logging


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(msg: str, *args) -> logging.LogRecord:
    """Create a minimal LogRecord for testing."""
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg=msg,
        args=args,
        exc_info=None,
    )
    return record


# ---------------------------------------------------------------------------
# sanitize_message() unit tests
# ---------------------------------------------------------------------------

class TestSanitizeMessageFunction:
    def test_redacts_access_token(self):
        msg = "Uploading with access_token=ya29ABVbY3ABC123XYZ very sensitive"
        result = sanitize_message(msg)
        assert "ya29ABVbY3ABC123XYZ" not in result
        assert "***REDACTED***" in result

    def test_redacts_sessionid(self):
        msg = "Cookie header: sessionid=AbCdEfGh12345678IJKLMNOP"
        result = sanitize_message(msg)
        assert "AbCdEfGh12345678IJKLMNOP" not in result
        assert "***REDACTED***" in result

    def test_passes_innocuous_message(self):
        msg = "Pipeline started successfully. Fetched 3 videos."
        result = sanitize_message(msg)
        assert result == msg

    def test_redacts_client_secret(self):
        msg = "client_secret=s3cr3tV4luXYZabcdEFGH1234 loaded from file"
        result = sanitize_message(msg)
        assert "s3cr3tV4luXYZabcdEFGH1234" not in result
        assert "***REDACTED***" in result

    def test_handles_empty_string(self):
        assert sanitize_message("") == ""


# ---------------------------------------------------------------------------
# LogSanitizer.filter() unit tests
# ---------------------------------------------------------------------------

class TestLogSanitizer:
    def setup_method(self):
        self.sanitizer = LogSanitizer()

    def test_masks_access_token_in_log_record(self):
        record = _make_record("Got access_token=ya29ABVbY3ABC123XYZ from Google")
        result = self.sanitizer.filter(record)
        assert result is True  # must always return True
        assert "ya29ABVbY3ABC123XYZ" not in record.msg
        assert "***REDACTED***" in record.msg

    def test_masks_douyin_sessionid_cookie(self):
        record = _make_record(
            "Douyin request header Cookie: sessionid=SeSsIoNiD12345678abcde"
        )
        self.sanitizer.filter(record)
        assert "SeSsIoNiD12345678abcde" not in record.msg
        assert "***REDACTED***" in record.msg

    def test_passes_innocuous_message_unchanged(self):
        msg = "Scheduler started. Interval: 60 minutes."
        record = _make_record(msg)
        self.sanitizer.filter(record)
        assert record.msg == msg

    def test_handles_uninterpolated_args_safely(self):
        """LogSanitizer must handle records where args are not yet interpolated into msg."""
        # Use a token pattern that is captured by the key=value pattern
        record = _make_record(
            "Cookie: sessionid=%s count=%s",
            "SeSsIoNiD12345678abcde",
            5,
        )
        result = self.sanitizer.filter(record)
        assert result is True
        # After filter, args are cleared (interpolation happened inside filter)
        assert record.args is None
        # The sessionid value should be redacted in the interpolated message
        assert "SeSsIoNiD12345678abcde" not in record.msg

    def test_always_returns_true(self):
        """Sanitizer must never suppress log records."""
        record = _make_record("bearer token=SUPER_SECRET_TOKEN_VALUE_xyz12345ABCDE")
        result = self.sanitizer.filter(record)
        assert result is True

    def test_args_cleared_after_filter(self):
        """After filter, record.args must be None to prevent double-interpolation."""
        record = _make_record("Auth: access_token=%s user=%s", "tokABC123xyz789Abcde1234", "admin")
        self.sanitizer.filter(record)
        assert record.args is None


# ---------------------------------------------------------------------------
# setup_logging() integration tests
# ---------------------------------------------------------------------------

class TestSetupLogging:
    def setup_method(self):
        # Use a fresh temp directory for each test to avoid side effects
        self.tmp_dir = tempfile.mkdtemp()
        # Reset the named douyinsync logger between tests
        app_logger = logging.getLogger("douyinsync")
        app_logger.handlers.clear()

    def teardown_method(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)
        # Clean up named logger state
        app_logger = logging.getLogger("douyinsync")
        app_logger.handlers.clear()

    def test_creates_log_directory(self):
        log_dir = os.path.join(self.tmp_dir, "test_logs")
        assert not os.path.exists(log_dir)
        setup_logging(log_dir=log_dir)
        assert os.path.isdir(log_dir)

    def test_root_logger_has_rotating_file_handler(self):
        from logging.handlers import RotatingFileHandler
        log_dir = os.path.join(self.tmp_dir, "test_logs")
        file_handler, _ = setup_logging(log_dir=log_dir)
        assert isinstance(file_handler, RotatingFileHandler)

    def test_root_logger_has_stream_handler(self):
        log_dir = os.path.join(self.tmp_dir, "test_logs")
        _, console_handler = setup_logging(log_dir=log_dir)
        assert isinstance(console_handler, logging.StreamHandler)

    def test_rotating_file_handler_max_bytes(self):
        log_dir = os.path.join(self.tmp_dir, "test_logs")
        file_handler, _ = setup_logging(log_dir=log_dir)
        assert file_handler.maxBytes == 10 * 1024 * 1024  # 10 MB

    def test_rotating_file_handler_backup_count(self):
        log_dir = os.path.join(self.tmp_dir, "test_logs")
        file_handler, _ = setup_logging(log_dir=log_dir)
        assert file_handler.backupCount == 5

    def test_sanitizer_attached_to_file_handler(self):
        log_dir = os.path.join(self.tmp_dir, "test_logs")
        file_handler, _ = setup_logging(log_dir=log_dir)
        filter_types = [type(f) for f in file_handler.filters]
        assert LogSanitizer in filter_types

    def test_sanitizer_attached_to_stream_handler(self):
        log_dir = os.path.join(self.tmp_dir, "test_logs")
        _, console_handler = setup_logging(log_dir=log_dir)
        filter_types = [type(f) for f in console_handler.filters]
        assert LogSanitizer in filter_types

    def test_no_duplicate_handlers_on_second_call(self):
        log_dir = os.path.join(self.tmp_dir, "test_logs")
        setup_logging(log_dir=log_dir)
        setup_logging(log_dir=log_dir)  # second call
        app_logger = logging.getLogger("douyinsync")
        # Should still have only 2 handlers (file + console)
        assert len(app_logger.handlers) == 2
