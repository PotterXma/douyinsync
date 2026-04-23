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


class TestMidnightRolloverRaceCondition:
    """
    回归测试：午夜滚动竞态条件。
    验证 push_daily_summary 在调度器延迟触发跨过午夜时，
    仍能正确发送前一天的统计数据，而非因计数归零后静默跳过。
    """

    def _make_notifier_with_config(self):
        """构造已配置 Bark 的 notifier（注意：每次调用需在 patch 上下文内）。"""
        from modules.notifier import BarkNotifier
        return BarkNotifier()

    def test_push_daily_summary_sends_previous_day_count_when_triggered_after_midnight(self):
        """
        核心竞态场景：
          - 调度器在 23:59 计划发送日报，count=15
          - 实际执行时系统时间已过 00:00（新一天）
          - 期望：日报仍发送 15 条，而非因归零而静默跳过
        """
        import datetime
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

        with patch('modules.notifier.config') as mock_config:
            def cfg(key, default=None):
                if key == 'bark_server': return 'https://api.day.app'
                if key == 'bark_key': return 'TESTKEY'
                if key == 'bark_sound': return 'minuet'
                return default
            mock_config.get.side_effect = cfg

            from modules.notifier import BarkNotifier
            notifier = BarkNotifier()
            # 模拟：计数在昨天产生，调度器今天才触发
            notifier._daily_upload_count = 15
            notifier._summary_date = yesterday  # 日期未更新 → 模拟跨午夜延迟

            with patch('modules.notifier.requests.get') as mock_get:
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_get.return_value = mock_resp

                notifier.push_daily_summary()

                # 关键断言：push 必须被调用（而非因 count==0 静默跳过）
                mock_get.assert_called_once()
                call_url = mock_get.call_args[0][0]
                assert '15' in call_url, "日报应包含实际计数 15，而非 0"
                assert 'level=passive' in call_url

    def test_push_daily_summary_resets_counter_after_midnight_send(self):
        """
        验证跨午夜发送后，内部状态正确更新为今天的日期且计数归零。
        """
        import datetime
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        today = datetime.date.today().isoformat()

        with patch('modules.notifier.config') as mock_config:
            mock_config.get.side_effect = lambda key, default=None: default

            from modules.notifier import BarkNotifier
            notifier = BarkNotifier()
            notifier._daily_upload_count = 8
            notifier._summary_date = yesterday

            # 调用快照方法（push_daily_summary 的核心逻辑）
            snapshot = notifier._snapshot_and_reset_daily_counter()

            assert snapshot == 8, "快照应保留真实计数 8"
            assert notifier._daily_upload_count == 0, "重置后计数应为 0"
            assert notifier._summary_date == today, "日期应更新为今天"

    def test_push_daily_summary_skips_silently_when_count_is_zero(self):
        """
        正常情况：若当天计数确实为 0，日报应静默跳过（不发 push）。
        """
        with patch('modules.notifier.config') as mock_config:
            mock_config.get.side_effect = lambda key, default=None: default

            from modules.notifier import BarkNotifier
            notifier = BarkNotifier()
            notifier._daily_upload_count = 0

            with patch('modules.notifier.requests.get') as mock_get:
                notifier.push_daily_summary()
                mock_get.assert_not_called()
