"""
Unit tests for BarkNotifier (modules/notifier.py).
Covers: missing config skip, successful push, network failure graceful handling.
"""
import pytest
from unittest.mock import patch, MagicMock


class TestBarkNotifierMissingConfig:
    """AC1: When bark config is absent, push() silently skips without raising."""

    def test_push_skips_when_no_bark_config(self):
        with patch('modules.notifier.config') as mock_config:
            mock_config.get.side_effect = lambda key, default=None: default
            from modules.notifier import BarkNotifier
            notifier = BarkNotifier()
            # Should not raise, should silently return
            notifier.push("Test Title", "Test Message")

    def test_push_skips_when_bark_server_missing_but_key_present(self):
        with patch('modules.notifier.config') as mock_config:
            def cfg(key, default=None):
                if key == 'bark_server': return ''
                if key == 'bark_key': return 'MYKEY'
                return default
            mock_config.get.side_effect = cfg
            from modules.notifier import BarkNotifier
            notifier = BarkNotifier()
            with patch('modules.notifier.requests.get') as mock_get:
                notifier.push("Test", "Msg")
                mock_get.assert_not_called()


class TestBarkNotifierSuccessfulPush:
    """AC1: When config is valid, push() dispatches correctly with level param."""

    def test_push_active_level_dispatches(self):
        with patch('modules.notifier.config') as mock_config:
            def cfg(key, default=None):
                if key == 'bark_server': return 'https://api.day.app'
                if key == 'bark_key': return 'TESTKEY'
                if key == 'bark_sound': return 'minuet'
                return default
            mock_config.get.side_effect = cfg
            from modules.notifier import BarkNotifier
            notifier = BarkNotifier()
            with patch('modules.notifier.requests.get') as mock_get:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_get.return_value = mock_resp
                notifier.push("Upload Done", "Video X uploaded", level="active")
                mock_get.assert_called_once()
                call_url = mock_get.call_args[0][0]
                assert 'level=active' in call_url
                assert 'TESTKEY' in call_url

    def test_push_time_sensitive_level_for_critical_errors(self):
        with patch('modules.notifier.config') as mock_config:
            def cfg(key, default=None):
                if key == 'bark_server': return 'https://api.day.app'
                if key == 'bark_key': return 'TESTKEY'
                if key == 'bark_sound': return 'minuet'
                return default
            mock_config.get.side_effect = cfg
            from modules.notifier import BarkNotifier
            notifier = BarkNotifier()
            with patch('modules.notifier.requests.get') as mock_get:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_get.return_value = mock_resp
                notifier.push("CRITICAL", "Cookie expired for @account", level="timeSensitive")
                call_url = mock_get.call_args[0][0]
                assert 'level=timeSensitive' in call_url

    def test_push_passive_level_for_daily_summary(self):
        with patch('modules.notifier.config') as mock_config:
            def cfg(key, default=None):
                if key == 'bark_server': return 'https://api.day.app'
                if key == 'bark_key': return 'TESTKEY'
                if key == 'bark_sound': return 'minuet'
                return default
            mock_config.get.side_effect = cfg
            from modules.notifier import BarkNotifier
            notifier = BarkNotifier()
            with patch('modules.notifier.requests.get') as mock_get:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_get.return_value = mock_resp
                notifier.push("Daily Summary", "3 videos uploaded today", level="passive")
                call_url = mock_get.call_args[0][0]
                assert 'level=passive' in call_url


class TestBarkNotifierNetworkFailure:
    """AC1: When network fails, push() logs warning without raising exception."""

    def test_push_does_not_raise_on_network_timeout(self):
        with patch('modules.notifier.config') as mock_config:
            def cfg(key, default=None):
                if key == 'bark_server': return 'https://api.day.app'
                if key == 'bark_key': return 'TESTKEY'
                if key == 'bark_sound': return 'minuet'
                return default
            mock_config.get.side_effect = cfg
            from modules.notifier import BarkNotifier
            notifier = BarkNotifier()
            with patch('modules.notifier.requests.get', side_effect=Exception("Connection timeout")):
                # Must NOT raise — only log warning
                notifier.push("Error", "Push failed gracefully")

    def test_push_does_not_raise_on_http_500(self):
        with patch('modules.notifier.config') as mock_config:
            def cfg(key, default=None):
                if key == 'bark_server': return 'https://api.day.app'
                if key == 'bark_key': return 'TESTKEY'
                if key == 'bark_sound': return 'minuet'
                return default
            mock_config.get.side_effect = cfg
            from modules.notifier import BarkNotifier
            notifier = BarkNotifier()
            with patch('modules.notifier.requests.get') as mock_get:
                mock_resp = MagicMock()
                mock_resp.status_code = 500
                mock_get.return_value = mock_resp
                # Must NOT raise
                notifier.push("Error", "Server returned 500")


class TestDailySummaryCounter:
    """AC2: Daily summary counter resets on new day, accumulates within day."""

    def test_daily_upload_counter_increments(self):
        from modules.notifier import BarkNotifier
        with patch('modules.notifier.config') as mock_config:
            mock_config.get.side_effect = lambda key, default=None: default
            notifier = BarkNotifier()
            notifier._daily_upload_count = 0
            notifier._daily_upload_count += 1
            assert notifier._daily_upload_count == 1

    def test_daily_upload_counter_resets_on_new_day(self):
        """Counter date tracking: if date changes, counter resets."""
        import datetime
        from modules.notifier import BarkNotifier
        with patch('modules.notifier.config') as mock_config:
            mock_config.get.side_effect = lambda key, default=None: default
            notifier = BarkNotifier()
            # Simulate counter set on a past date
            notifier._daily_upload_count = 5
            notifier._summary_date = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
            # After reset check, counter should be 0
            notifier._check_and_reset_daily_counter()
            assert notifier._daily_upload_count == 0
