import pytest
from unittest.mock import patch, MagicMock
import customtkinter as ctk

# We patch customtkinter completely or partial to avoid opening windows during CI/tests
from ui.dashboard_app import DashboardApp, PipelineStatusCard

@patch("ui.dashboard_app.ctk.CTk.mainloop")
@patch("ui.dashboard_app.ctk.CTk.after")
@patch("ui.dashboard_app.ctk.CTk.deiconify")
def test_dashboard_initialization(mock_deiconify, mock_after, mock_mainloop):
    mock_after.return_value = None
    app = DashboardApp()

    assert hasattr(app, "root")

    app.show()
    mock_deiconify.assert_called_once()

@patch("ui.dashboard_app.ctk.CTk.mainloop")
def test_global_hud_components(mock_mainloop):
    app = DashboardApp()

    assert hasattr(app, "progress_bar")
    assert isinstance(app.progress_bar, ctk.CTkProgressBar)
    assert hasattr(app, "lbl_total_processed")
    assert hasattr(app, "lbl_total_success")
    assert hasattr(app, "fail_log")
    assert isinstance(app.fail_log, ctk.CTkTextbox)
    assert hasattr(app, "btn_library")
    assert hasattr(app, "btn_manual_sync")
    assert hasattr(app, "btn_manual_rerun")

@patch("ui.dashboard_app.ctk.CTk.mainloop")
def test_pipeline_status_card(mock_mainloop):
    app = DashboardApp()
    app.update_data_layer({"test_account": {"pending": 2, "uploaded": 1}})

    assert "test_account" in app.cards
    card = app.cards["test_account"]
    assert isinstance(card, PipelineStatusCard)

    app.update_data_layer({"test_account": {"failed": 1, "uploaded": 5}})
    text = card.lbl_status.cget("text")
    assert "✓5" in text
    assert "✗1" in text
