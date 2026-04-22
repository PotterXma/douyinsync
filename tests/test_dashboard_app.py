import pytest
from unittest.mock import patch, MagicMock
import customtkinter as ctk

# We patch customtkinter completely or partial to avoid opening windows during CI/tests
from ui.dashboard_app import DashboardApp, PipelineStatusCard

@patch("ui.dashboard_app.ctk.CTk.mainloop")
@patch("ui.dashboard_app.ctk.CTk.withdraw")
@patch("ui.dashboard_app.ctk.CTk.deiconify")
def test_dashboard_initialization(mock_deiconify, mock_withdraw, mock_mainloop):
    app = DashboardApp()
    
    assert hasattr(app, "root")
    
    class DummyEvent:
        pass
    dummy_event = DummyEvent()
    dummy_event.widget = app.root
    
    app._on_focus_out(dummy_event)
    mock_withdraw.assert_called_once()
    
    app.show()
    mock_deiconify.assert_called_once()

@patch("ui.dashboard_app.ctk.CTk.mainloop")
def test_global_hud_components(mock_mainloop):
    app = DashboardApp()
    
    # Needs to render a progress bar and labels
    assert hasattr(app, "progress_bar")
    assert isinstance(app.progress_bar, ctk.CTkProgressBar)
    assert hasattr(app, "lbl_total_processed")
    assert hasattr(app, "lbl_total_success")

@patch("ui.dashboard_app.ctk.CTk.mainloop")
def test_pipeline_status_card(mock_mainloop):
    app = DashboardApp()
    # It should have a method to update cards or create them
    app.update_data_layer({"test_account": {"status": "pending", "success": 0, "total": 0}})
    
    assert "test_account" in app.cards
    card = app.cards["test_account"]
    assert isinstance(card, PipelineStatusCard)
    
    # Check if we can change status
    app.update_data_layer({"test_account": {"status": "failed", "success": 5, "total": 10}})
    # Let's say if failed, action button changes or becomes visible
