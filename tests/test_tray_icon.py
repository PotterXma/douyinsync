import pytest
import queue
from unittest.mock import patch, MagicMock
from ui.tray_icon import TrayApp
from utils.models import AppEvent

def test_tray_initialization():
    event_queue = queue.Queue()
    app = TrayApp(event_queue)
    assert app.event_queue == event_queue
    assert app.icon is None

@patch('ui.tray_icon.pystray')
@patch('ui.tray_icon.Image')
def test_tray_menu_actions(mock_image, mock_pystray):
    event_queue = queue.Queue()
    app = TrayApp(event_queue)

    mock_icon_instance = MagicMock()
    mock_pystray.Icon.return_value = mock_icon_instance

    app.setup()

    # Simulate clicking 'Reload Config'
    app.on_reload(mock_icon_instance, None)

    assert not event_queue.empty()
    event = event_queue.get()
    assert event.command == "RELOAD_CONFIG"
    mock_icon_instance.notify.assert_called_with("Config Reloaded", title="DouyinSync")

    # Simulate clicking 'Open Dashboard' - now also notifies (AC2)
    app.on_open_dashboard(mock_icon_instance, None)
    assert not event_queue.empty()
    event = event_queue.get()
    assert event.command == "OPEN_DASHBOARD"
    mock_icon_instance.notify.assert_called_with("Dashboard Opening", title="DouyinSync")

    app.on_open_settings(mock_icon_instance, None)
    assert not event_queue.empty()
    event = event_queue.get()
    assert event.command == "OPEN_SETTINGS"
    mock_icon_instance.notify.assert_called_with("正在打开搬运时间设置…", title="DouyinSync")

@patch('ui.tray_icon.pystray')
@patch('ui.tray_icon.Image')
def test_tray_exit_action(mock_image, mock_pystray):
    event_queue = queue.Queue()
    app = TrayApp(event_queue)
    mock_icon_instance = MagicMock()

    app.on_exit(mock_icon_instance, None)

    assert not event_queue.empty()
    event = event_queue.get()
    assert event.command == "EXIT"
    mock_icon_instance.stop.assert_called_once()
