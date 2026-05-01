import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from tkinter import messagebox

import customtkinter as ctk

from modules.database import VideoDAO, DatabaseConnectionError
from modules.logger import logger
from utils.paths import manual_force_retry_request_path, manual_sync_request_path
from utils.scheduler_hud import (
    build_schedule_caption,
    is_hud_state_fresh,
    load_config_json_fresh,
    read_hud_state_from_disk,
    HUD_STATE_STALE_SEC,
)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

YOUTUBE_QUOTA_MAX = 10000.0
YOUTUBE_QUOTA_COST_PER_VIDEO = 1600.0


def _mb_bytes(n: int) -> str:
    return "%.1f MB" % (max(0, int(n)) / (1024 * 1024))


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
        self.root.geometry("460x900")

        self.frm_sync = ctk.CTkFrame(self.root, border_width=1, fg_color=("gray85", "gray20"))
        self.frm_sync.pack(pady=(12, 8), padx=16, fill="x")
        self.lbl_sync_header = ctk.CTkLabel(
            self.frm_sync, text="同步任务 · 时间 · 状态", font=("Inter", 14, "bold")
        )
        self.lbl_sync_header.pack(anchor="w", padx=12, pady=(8, 4))
        self.lbl_sync_task = ctk.CTkLabel(
            self.frm_sync, text="任务: …", anchor="w", justify="left", wraplength=400
        )
        self.lbl_sync_task.pack(anchor="w", padx=12, pady=2, fill="x")
        self.lbl_sync_plan = ctk.CTkLabel(
            self.frm_sync, text="计划: …", anchor="w", justify="left", wraplength=400
        )
        self.lbl_sync_plan.pack(anchor="w", padx=12, pady=2, fill="x")
        self.lbl_sync_next = ctk.CTkLabel(
            self.frm_sync, text="下次(北京): …", anchor="w", justify="left", wraplength=400
        )
        self.lbl_sync_next.pack(anchor="w", padx=12, pady=2, fill="x")
        self.lbl_sync_st = ctk.CTkLabel(
            self.frm_sync, text="运行态: …", anchor="w", justify="left", wraplength=400
        )
        self.lbl_sync_st.pack(anchor="w", padx=12, pady=2, fill="x")
        self.lbl_sync_note = ctk.CTkLabel(
            self.frm_sync, text=" ", anchor="w", justify="left", wraplength=400, text_color="gray"
        )
        self.lbl_sync_note.pack(anchor="w", padx=12, pady=(0, 10), fill="x")

        self.frm_active = ctk.CTkFrame(self.root, border_width=1, fg_color=("gray85", "gray20"))
        self.frm_active.pack(pady=(0, 8), padx=16, fill="x")
        self.lbl_active_header = ctk.CTkLabel(
            self.frm_active, text="当前任务（单条）", font=("Inter", 13, "bold")
        )
        self.lbl_active_header.pack(anchor="w", padx=12, pady=(8, 4))
        self.lbl_active_stage = ctk.CTkLabel(
            self.frm_active, text="阶段: …", anchor="w", justify="left", wraplength=400
        )
        self.lbl_active_stage.pack(anchor="w", padx=12, pady=2, fill="x")
        self.lbl_active_detail = ctk.CTkLabel(
            self.frm_active, text="…", anchor="w", justify="left", wraplength=400
        )
        self.lbl_active_detail.pack(anchor="w", padx=12, pady=2, fill="x")
        self.active_upload_bar = ctk.CTkProgressBar(self.frm_active)
        self.active_upload_bar.pack(padx=12, pady=4, fill="x")
        self.active_upload_bar.set(0)
        self.lbl_active_bytes = ctk.CTkLabel(
            self.frm_active, text=" ", anchor="w", text_color="gray", wraplength=400
        )
        self.lbl_active_bytes.pack(anchor="w", padx=12, pady=(0, 2))
        self.lbl_recent_ok = ctk.CTkLabel(
            self.frm_active, text="最近成功: —", anchor="w", justify="left", wraplength=400
        )
        self.lbl_recent_ok.pack(anchor="w", padx=12, pady=(2, 4), fill="x")
        self._last_youtube_id_clip = ""
        self.btn_copy_ytid = ctk.CTkButton(
            self.frm_active,
            text="复制最近 YouTube 视频 ID",
            width=200,
            command=self._copy_last_youtube_id,
        )
        self.btn_copy_ytid.pack(anchor="w", padx=12, pady=(0, 10))

        self.progress_bar = ctk.CTkProgressBar(self.root)
        self.progress_bar.pack(pady=10, padx=20, fill="x")
        self.progress_bar.set(0)

        self.lbl_quota_hint = ctk.CTkLabel(
            self.root,
            text=(
                "上方进度条为「当日上传配额」估算（账号级）；"
                "「当前任务」区为正在处理的单条视频及上传字节进度。"
            ),
            text_color="gray",
            wraplength=420,
            justify="left",
            anchor="w",
        )
        self.lbl_quota_hint.pack(padx=20, pady=(0, 6), anchor="w")

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
            text="立即同步一次（抓取新视频并入管道）",
            command=self._request_manual_sync,
        )
        self.btn_manual_sync.pack(pady=(0, 4), padx=20, fill="x")

        self.btn_manual_rerun = ctk.CTkButton(
            self.root,
            text="手动重新执行（失败下载/上传重试）",
            command=self._request_manual_force_retry,
        )
        self.btn_manual_rerun.pack(pady=(0, 8), padx=20, fill="x")
        # 首轮 poll 前尚无统计，先禁用；有 failed / give_up / give_up_fatal 时再启用
        self.btn_manual_rerun.configure(state="disabled")

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
        self.root.after(200, self._refresh_sync_status_panel)
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
        """Touch ``.manual_sync_request``：主进程立刻跑一轮主同步（拉新视频 + 管道处理）。"""
        try:
            manual_sync_request_path().touch()
            logger.info("Dashboard: manual sync request file created.")
            try:
                messagebox.showinfo(
                    "DouyinSync",
                    "已通知主进程：立刻执行一轮同步（约 1 秒内开始）。\n\n"
                    "说明：若 config 里 daily_upload_limit 已达「今日已上传」上限，"
                    "本轮只会拉抖音列表、不会下载/上传待处理视频；"
                    "日志会出现 Daily upload limit reached。可调大 daily_upload_limit 或次日再试。",
                    parent=self.root,
                )
            except Exception:
                pass
        except OSError as e:
            logger.error("Dashboard: could not create manual sync request: %s", e)

    def _request_manual_force_retry(self) -> None:
        """Touch ``.manual_force_retry_request``：仅对下载/上传失败或放弃行做归一并重跑（需主进程）。"""
        try:
            stats = VideoDAO.get_pipeline_stats()
            retry_pool = (
                stats.get("failed", 0)
                + stats.get("give_up", 0)
                + stats.get("give_up_fatal", 0)
            )
            if retry_pool <= 0:
                logger.info("Dashboard: force retry skipped — no failed or give_up rows.")
                return
        except (sqlite3.Error, DatabaseConnectionError) as e:
            logger.error("Dashboard: force retry — DB stats read failed: %s", e)
            return
        except Exception as e:
            logger.error("Dashboard: force retry — unexpected error reading stats: %s", e)
            return
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

    def _refresh_sync_status_panel(self) -> None:
        """Epic 5-1 扩展：展示主同步任务名、计划、下次（北京）、监控/管道路径状态。"""
        payload = read_hud_state_from_disk()
        fresh = is_hud_state_fresh(payload)
        cfg = load_config_json_fresh()
        cap = build_schedule_caption(cfg)
        default_task = "主同步（抖音拉取 → 本地下载 → YouTube 上传）"

        if fresh and isinstance(payload, dict):
            self.lbl_sync_task.configure(
                text=f"任务: {payload.get('task_name_zh', default_task)}"
            )
            if cap.mode == "clock" and cap.clock_slots_zh and cap.clock_slots_zh != "—":
                t = f"  |  钟点 {cap.clock_slots_zh}（与配置一致）"
            elif cap.mode == "interval" and cap.interval_minutes is not None:
                t = f"  |  每 {cap.interval_minutes} 分（与配置一致）"
            else:
                t = ""
            self.lbl_sync_plan.configure(
                text=f"计划: {payload.get('schedule_detail_zh', cap.detail_zh)}{t}"
            )
            self.lbl_sync_next.configure(
                text=f"下次(北京, 调度器): {payload.get('earliest_next_bj', '—')}"
            )
            st1 = payload.get("scheduler_status_zh", "—")
            st2 = payload.get("pipeline_cycle_zh", "—")
            self.lbl_sync_st.configure(text=f"运行态: {st1}  ·  {st2}")
            if payload.get("updated_at") is not None:
                try:
                    age = max(0.0, time.time() - float(payload["updated_at"]))
                    stamp = f"主进程心跳: {age:.0f}s 前"
                except (TypeError, ValueError):
                    stamp = "主进程心跳: —"
            else:
                stamp = ""
            if stamp:
                note = (
                    f"{stamp}  ·  间隔模式自调度/启动起算；要固定钟点请用 "
                    "sync_schedule_mode=clock 与 sync_clock_times。"
                )
            else:
                note = "间隔模式自调度/启动起算；要固定钟点请用 clock + sync_clock_times。"
            self.lbl_sync_note.configure(text_color=("gray30", "gray50"), text=note)
            return

        # 子进程可单独打开：主应用未开或心跳超 {HUD_STATE_STALE_SEC} 秒
        self.lbl_sync_task.configure(text=f"任务: {default_task}（无进程快照，按配置）")
        plan_line = cap.detail_zh
        if cap.mode == "clock" and cap.clock_slots_zh and cap.clock_slots_zh != "—":
            plan_line = f"{plan_line}  |  钟点 {cap.clock_slots_zh}"
        self.lbl_sync_plan.configure(text=f"计划(仅 config): {plan_line}")
        self.lbl_sync_next.configure(
            text=f"下次(北京): 未知（需托盘主程序运行，才显示调度器实际下次时间）"
        )
        self.lbl_sync_st.configure(
            text="运行态: 未知  ·  主进程: 可能未开或 HUD 未刷新"
        )
        self.lbl_sync_note.configure(
            text_color=("gray30", "gray60"),
            text=(
                f"已 {int(HUD_STATE_STALE_SEC)}+ 秒未收到主进程写入的 "
                f".hud_scheduler_state.json；"
                f"单开 Dashboard 仅显示配置推断。请先运行 DouyinSync 主程序后再打开本窗。"
            ),
        )

    def update_data_layer(self, data: dict[str, dict[str, int]]) -> None:
        for account, counts in data.items():
            if account not in self.cards:
                self.cards[account] = PipelineStatusCard(self.cards_frame, account)
                self.cards[account].pack(pady=5, padx=4, fill="x")
            self.cards[account].set_counts(counts)

    def _copy_last_youtube_id(self) -> None:
        tid = (self._last_youtube_id_clip or "").strip()
        if not tid:
            return
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(tid)
        except Exception as e:
            logger.warning("Dashboard: clipboard copy failed: %s", e)

    def _refresh_active_task_panel(self) -> None:
        active = VideoDAO.get_active_pipeline_video()
        recent = VideoDAO.get_latest_uploaded_snapshot()

        if recent:
            ytid = (recent.get("youtube_video_id") or "").strip()
            self._last_youtube_id_clip = ytid
            rtitle = (recent.get("title") or "")[:48]
            rd = str(recent.get("douyin_id") or "")
            rd_short = rd[:16] + ("…" if len(rd) > 16 else "")
            if ytid:
                self.lbl_recent_ok.configure(
                    text="最近成功: %s | dy:%s | YT:%s" % (rtitle, rd_short, ytid)
                )
                self.btn_copy_ytid.configure(state="normal")
            else:
                self.lbl_recent_ok.configure(text="最近成功: %s | dy:%s" % (rtitle, rd_short))
                self.btn_copy_ytid.configure(state="disabled")
        else:
            self.lbl_recent_ok.configure(text="最近成功: （暂无记录）")
            self._last_youtube_id_clip = ""
            self.btn_copy_ytid.configure(state="disabled")

        if not active:
            self.lbl_active_stage.configure(text="阶段: 空闲")
            self.lbl_active_detail.configure(text="当前无上传/下载中的任务。")
            self.active_upload_bar.set(0)
            self.lbl_active_bytes.configure(text=" ")
            return

        st = active["status"]
        title = (active.get("title") or "（无标题）")[:56]
        aid = active.get("account_mark") or "Unknown"
        dy = str(active.get("douyin_id") or "")
        dy_short = dy[:18] + ("…" if len(dy) > 18 else "")

        if st == "uploading":
            self.lbl_active_stage.configure(text="阶段: 正在上传到 YouTube")
            done = int(active.get("upload_bytes_done") or 0)
            total = active.get("upload_bytes_total")
            self.lbl_active_detail.configure(
                text="账号: %s  |  dy:%s  |  %s" % (aid, dy_short, title)
            )
            if total is not None and int(total) > 0:
                tot = int(total)
                pct = min(1.0, done / tot)
                self.active_upload_bar.set(pct)
                self.lbl_active_bytes.configure(
                    text="已传 %s / %s（%.0f%%）"
                    % (_mb_bytes(done), _mb_bytes(tot), pct * 100)
                )
            else:
                self.active_upload_bar.set(0)
                self.lbl_active_bytes.configure(text="总大小未记录，仅显示阶段（无百分比）。")
        else:
            self.lbl_active_stage.configure(text="阶段: 正在下载 / 准备下载")
            self.lbl_active_detail.configure(
                text="账号: %s  |  dy:%s  |  %s" % (aid, dy_short, title)
            )
            self.active_upload_bar.set(0)
            self.lbl_active_bytes.configure(text="下载细粒度进度见日志（未写入数据库）。")

    def poll_db(self):
        try:
            self._refresh_sync_status_panel()
            self._refresh_active_task_panel()
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

            retry_pool = failed_count + give_up_count
            self.btn_manual_rerun.configure(
                state="normal" if retry_pool > 0 else "disabled"
            )

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
