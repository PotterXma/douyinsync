import sqlite3
import customtkinter as ctk
from typing import Dict, Any

from modules.database import VideoDAO, DatabaseConnectionError
from modules.logger import logger

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

YOUTUBE_QUOTA_MAX = 10000.0
YOUTUBE_QUOTA_COST_PER_VIDEO = 1600.0

class PipelineStatusCard(ctk.CTkFrame):
    def __init__(self, master, account_mark, **kwargs):
        super().__init__(master, **kwargs)
        self.account_mark = account_mark
        self.lbl_title = ctk.CTkLabel(self, text=account_mark, font=("Inter", 14, "bold"))
        self.lbl_title.pack(anchor="w", padx=10, pady=5)
        self.lbl_status = ctk.CTkLabel(self, text="status: unknown")
        self.lbl_status.pack(anchor="w", padx=10, pady=2)

class DashboardApp:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("DouyinSync Dashboard")
        self.root.geometry("400x600")
        
        # UI requirements from tests and architecture
        self.progress_bar = ctk.CTkProgressBar(self.root)
        self.progress_bar.pack(pady=10, padx=20, fill="x")
        self.progress_bar.set(0)
        
        # Telemetry Labels
        self.lbl_total_processed = ctk.CTkLabel(self.root, text="Processed: 0")
        self.lbl_total_processed.pack()
        self.lbl_total_success = ctk.CTkLabel(self.root, text="Success: 0")
        self.lbl_total_success.pack()
        self.lbl_pending = ctk.CTkLabel(self.root, text="Pending: 0")
        self.lbl_pending.pack()
        self.lbl_failed = ctk.CTkLabel(self.root, text="Failed: 0")
        self.lbl_failed.pack()
        self.lbl_give_up = ctk.CTkLabel(self.root, text="Fatal Give Up: 0")
        self.lbl_give_up.pack()
        
        self.cards: Dict[str, PipelineStatusCard] = {}
        
        self.root.bind("<FocusOut>", self._on_focus_out)
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        
        # Start DB Polling loop
        self.root.after(3000, self.poll_db)
        
    def _on_focus_out(self, event):
        if hasattr(event, 'widget') and getattr(event, 'widget') == self.root:
            self.root.withdraw()

    def _on_window_close(self):
        self.root.withdraw()

            
    def show(self):
        self.root.deiconify()
        
    def update_data_layer(self, data: Dict[str, dict]):
        for account, info in data.items():
            if account not in self.cards:
                self.cards[account] = PipelineStatusCard(self.root, account)
                self.cards[account].pack(pady=5, padx=20, fill="x")
            card = self.cards[account]
            card.lbl_status.configure(text=f"status: {info.get('status', 'unknown')}")

    def poll_db(self):
        try:
            stats = VideoDAO.get_pipeline_stats()
            # Map stats explicitly
            uploaded_count = stats.get("uploaded", 0)
            pending_count = stats.get("pending", 0)
            processing_count = stats.get("processing", 0) + stats.get("downloading", 0) + stats.get("uploading", 0)
            downloaded_count = stats.get("downloaded", 0)
            failed_count = stats.get("failed", 0)
            give_up_count = stats.get("give_up_fatal", 0) + stats.get("give_up", 0)
            
            total_processed = uploaded_count + processing_count + failed_count + downloaded_count
            
            self.lbl_total_processed.configure(text=f"Processed: {total_processed}")
            self.lbl_total_success.configure(text=f"Success: {uploaded_count}")
            self.lbl_pending.configure(text=f"Pending: {pending_count}")
            self.lbl_failed.configure(text=f"Failed: {failed_count}")
            self.lbl_give_up.configure(text=f"Fatal Give Up: {give_up_count}")
            
            # Quota progress estimation
            quota_usage = (uploaded_count * YOUTUBE_QUOTA_COST_PER_VIDEO) / YOUTUBE_QUOTA_MAX
            self.progress_bar.set(min(quota_usage, 1.0))
            
            # Populate per-account progress
            # In a real implementation this might fetch grouped results:
            accounts_data = VideoDAO.get_accounts_pipeline_stats() if hasattr(VideoDAO, 'get_accounts_pipeline_stats') else {}
            if accounts_data:
                self.update_data_layer(accounts_data)
            
        except sqlite3.Error as e:
            logger.error("DB Poll failed (sqlite3.Error): %s", e)
        except DatabaseConnectionError as e:
            logger.error("DB Poll failed (Connection): %s", e)
        except Exception as e:
            logger.error("DB Poll failed (Unknown): %s", e)
        finally:
            self.root.after(3000, self.poll_db)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = DashboardApp()
    app.run()
