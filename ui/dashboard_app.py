import sqlite3
import subprocess
import sys
from pathlib import Path

import customtkinter as ctk

from modules.database import VideoDAO, DatabaseConnectionError
from modules.logger import logger
from utils.paths import manual_force_retry_request_path, manual_sync_request_path

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

YOUTUBE_QUOTA_MAX = 10000.0
YOUTUBE_QUOTA_COST_PER_VIDEO = 1600.0


def _format_account_counts(counts: dict[str, int]) -> str:
    order = [
        ("uploaded", "✓"),
        ("pending", "⏳"),
        ("downloaded", "↓"),
        ("processing", "⋯"),
        ("downloading", "⬇"),
        ("uploading", "⬆"),
        ("failed", "✗"),
        ("give_up", "!!"),
        ("give_up_fatal", "†"),
    ]
    parts: list[str] = []
    for key, sym in order:
        n = counts.get(key, 0)
        if n:
            parts.append(f"{sym}{n}")
    return " ".join(parts) if parts else "（无记录）"


class PipelineStatusCard(ctk.CTkFrame):
    def __init__(self, master, account_mark: str, **kwargs):
        super().__init__(master, **kwargs)
        self.account_mark = account_mark
        self.lbl_title = ctk.CTkLabel(self, text=account_mark, font=("Inter", 14, "bold"))
        self.lbl_title.pack(anchor="w", padx=10, pady=5)
        self.lbl_status = ctk.CTkLabel(self, text="status: …", anchor="w", justify="left")
        self.lbl_status.pack(anchor="w", padx=10, pady=2)

    def set_counts(self, counts: dict[str, int]) -> None:
        self.lbl_status.configure(text=_format_account_counts(counts))


class DashboardApp:
    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("DouyinSync Dashboard")
        self.root.geometry("440x780")

        self.progress_bar = ctk.CTkProgressBar(self.root)
        self.progress_bar.pack(pady=10, padx=20, fill="x")
        self.progress_bar.set(0)

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

        self.btn_library = ctk.CTkButton(
            self.root,
            text="打开视频库管理（筛选 / 重置 Pending）…",
            command=self._open_video_library,
        )
        self.btn_library.pack(pady=8, padx=20, fill="x")

        self.btn_manual_sync = ctk.CTkButton(
            self.root,
            text="立即执行一次同步（主进程管道）",
            command=self._request_manual_sync,
        )
        self.btn_manual_sync.pack(pady=(0, 4), padx=20, fill="x")

        self.btn_manual_rerun = ctk.CTkButton(
            self.root,
            text="手动重新执行（忽略重试上限）",
            command=self._request_manual_force_retry,
        )
        self.btn_manual_rerun.pack(pady=(0, 8), padx=20, fill="x")

        self.lbl_fail_header = ctk.CTkLabel(self.root, text="最近失败 / 放弃（只读）", font=("Inter", 13, "bold"))
        self.lbl_fail_header.pack(anchor="w", padx=20, pady=(12, 4))

        self.fail_log = ctk.CTkTextbox(self.root, height=160, font=("Consolas", 11), wrap="word")
        self.fail_log.pack(padx=20, pady=(0, 8), fill="both", expand=True)
        self.fail_log.configure(state="disabled")

        self.lbl_accounts = ctk.CTkLabel(self.root, text="分账号进度", font=("Inter", 13, "bold"))
        self.lbl_accounts.pack(anchor="w", padx=20, pady=(4, 2))

        self.cards_frame = ctk.CTkScrollableFrame(self.root, height=200)
        self.cards_frame.pack(padx=20, pady=(0, 10), fill="x")

        self.cards: dict[str, PipelineStatusCard] = {}

        # 不在 <FocusOut> 时自动隐藏：Windows 托盘通知会抢焦点，导致面板「一闪消失」。
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)

        self.root.after(100, self._bring_to_front_once)
        self.root.after(3000, self.poll_db)

    def _open_video_library(self) -> None:
        try:
            if getattr(sys, "frozen", False):
                subprocess.Popen([sys.executable, "videolib"])
            else:
                main_py = Path(__file__).resolve().parent.parent / "main.py"
                subprocess.Popen([sys.executable, str(main_py), "videolib"])
        except Exception as e:
            logger.error("Dashboard: failed to spawn videolib subprocess: %s", e)

    def _request_manual_sync(self) -> None:
        """Touch ``.manual_sync_request``; tray daemon consumes it and runs ``primary_sync_job`` once."""
        try:
            manual_sync_request_path().touch()
            logger.info("Dashboard: manual sync request file created.")
        except OSError as e:
            logger.error("Dashboard: could not create manual sync request: %s", e)

    def _request_manual_force_retry(self) -> None:
        """Touch ``.manual_force_retry_request`` — one run that resets give_up/failed rows and skips give_up caps."""
        try:
            manual_force_retry_request_path().touch()
            logger.info("Dashboard: force manual retry request file created.")
        except OSError as e:
            logger.error("Dashboard: could not create force retry request: %s", e)

    def _bring_to_front_once(self) -> None:
        try:
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(150, lambda: self.root.attributes("-topmost", False))
        except Exception:
            pass

    def _on_window_close(self):
        self.root.withdraw()

    def show(self):
        self.root.deiconify()

    def _set_fail_log_text(self, text: str) -> None:
        self.fail_log.configure(state="normal")
        self.fail_log.delete("1.0", "end")
        self.fail_log.insert("1.0", text)
        self.fail_log.configure(state="disabled")

    def update_data_layer(self, data: dict[str, dict[str, int]]) -> None:
        for account, counts in data.items():
            if account not in self.cards:
                self.cards[account] = PipelineStatusCard(self.cards_frame, account)
                self.cards[account].pack(pady=5, padx=4, fill="x")
            self.cards[account].set_counts(counts)

    def poll_db(self):
        try:
            stats = VideoDAO.get_pipeline_stats()
            uploaded_count = stats.get("uploaded", 0)
            pending_count = stats.get("pending", 0)
            processing_count = (
                stats.get("processing", 0) + stats.get("downloading", 0) + stats.get("uploading", 0)
            )
            downloaded_count = stats.get("downloaded", 0)
            failed_count = stats.get("failed", 0)
            give_up_count = stats.get("give_up_fatal", 0) + stats.get("give_up", 0)

            total_processed = uploaded_count + processing_count + failed_count + downloaded_count

            self.lbl_total_processed.configure(text=f"Processed: {total_processed}")
            self.lbl_total_success.configure(text=f"Success: {uploaded_count}")
            self.lbl_pending.configure(text=f"Pending: {pending_count}")
            self.lbl_failed.configure(text=f"Failed: {failed_count}")
            self.lbl_give_up.configure(text=f"Fatal Give Up: {give_up_count}")

            quota_usage = (uploaded_count * YOUTUBE_QUOTA_COST_PER_VIDEO) / YOUTUBE_QUOTA_MAX
            self.progress_bar.set(min(quota_usage, 1.0))

            accounts_data = VideoDAO.get_accounts_pipeline_stats()
            if accounts_data:
                self.update_data_layer(accounts_data)

            failures = VideoDAO.get_recent_failure_rows(30)
            if not failures:
                self._set_fail_log_text("（暂无失败记录）")
            else:
                lines = []
                for r in failures:
                    ts = r.get("updated_at")
                    lines.append(
                        f"[{r['status']}] retries={r['retry_count']} | {r['account_mark']}\n"
                        f"  {r['douyin_id'][:20]}… {r['title']}\n"
                        f"  path: {r['local_video_path'] or '—'}\n"
                    )
                self._set_fail_log_text("\n".join(lines))

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
    DashboardApp().run()
