"""modules.ui_settings: clock parsing and hours mapping."""
import pytest

from modules import ui_settings


def test_parse_clock_times_comma_and_chinese_comma():
    s = "08:00，20:00 , 06:30"
    assert ui_settings._parse_clock_times(s) == ["08:00", "20:00", "06:30"]


def test_parse_clock_times_newlines():
    assert ui_settings._parse_clock_times("09:00\n\n10:15") == ["09:00", "10:15"]


def test_parse_clock_times_invalid():
    with pytest.raises(ValueError):
        ui_settings._parse_clock_times("25:00")
    with pytest.raises(ValueError):
        ui_settings._parse_clock_times("")


def test_minutes_to_display_hours():
    assert ui_settings._minutes_to_display_hours(1) == 1
    assert ui_settings._minutes_to_display_hours(60) == 1
    assert ui_settings._minutes_to_display_hours(61) == 2
    assert ui_settings._minutes_to_display_hours(240) == 4


def test_reload_config_request_path_exists():
    from utils.paths import reload_config_request_path

    p = reload_config_request_path()
    assert p.name == ".reload_config_request"
