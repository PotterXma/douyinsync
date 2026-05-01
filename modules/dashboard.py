import csv
import tkinter as tk
from datetime import datetime
from tkinter import filedialog, ttk, messagebox
from typing import Optional
from zoneinfo import ZoneInfo

from modules.database import VideoDAO, db
from modules.logger import logger

_BJ = ZoneInfo("Asia/Shanghai")

# 表格仅展示最近 N 条（按 updated_at）；导出可单独提高上限。
VIDEOLIB_TABLE_ROW_LIMIT = 500
VIDEOLIB_EXPORT_ROW_LIMIT = 5000


def _format_last_error_summary(raw: Optional[object], max_len: int = 72) -> str:
    """Single-line snippet for videolib Treeview (scheduler persist column)."""
    if raw is None:
        return ""
    s = str(raw).strip().replace("\r", " ").replace("\n", " ")
    if not s:
        return ""
    return s if len(s) <= max_len else (s[: max_len - 1] + "…")


def _format_library_upload_progress(status: str, done: Optional[int], total: Optional[object]) -> str:
    """Table column: percent when ``upload_bytes_total`` known; ellipsis when uploading without total."""
    try:
        d = int(done or 0)
        t = int(total) if total is not None else 0
    except (TypeError, ValueError):
        return "—"
    if t > 0:
        pct = min(100, int(100 * d / t))
        return "%s%%" % pct
    if status == "uploading":
        return "…"
    return "—"


def _format_youtube_id_cell(raw: Optional[object]) -> str:
    if raw is None:
        return "—"
    s = str(raw).strip()
    return s if s else "—"


def _format_updated_at_bj(unix: Optional[int]) -> str:
    if unix is None:
        return "—"
    try:
        t = int(unix)
    except (TypeError, ValueError):
        return "—"
    if t <= 0:
        return "—"
    return datetime.fromtimestamp(t, tz=_BJ).strftime("%Y-%m-%d %H:%M:%S")


def write_videolib_csv_file(path: str, rows: list[tuple]) -> int:
    """
    Persist ``VideoDAO.list_videos_for_library`` tuples as UTF-8 with BOM (Excel-friendly).
    Includes full ``last_error_summary`` (not Treeview-truncated). Returns number of data rows written.
    """
    headers = (
        "douyin_id",
        "status",
        "account_mark",
        "retry_count",
        "title",
        "local_video_path",
        "updated_at_unix",
        "updated_at_beijing",
        "upload_bytes_done",
        "upload_bytes_total",
        "last_error_summary",
        "youtube_video_id",
    )
    n = 0
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for row in rows:
            if len(row) < 11:
                continue
            t_up = row[6]
            bj = _format_updated_at_bj(t_up) if t_up is not None else ""
            unix_v = int(t_up) if t_up is not None else ""
            err = row[9]
            yt = row[10] if len(row) > 10 else None
            w.writerow(
                [
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5] if row[5] is not None else "",
                    unix_v,
                    bj,
                    row[7],
                    row[8] if row[8] is not None else "",
                    err if err is not None else "",
                    yt if yt is not None else "",
                ]
            )
            n += 1
    return n


class SyncDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("视频状态管理库 | DouyinSync Dashboard")
        self.root.geometry("1420x600")
        self._last_row_count: int = 0
        self._summary_by_iid: dict[str, str] = {}
        self._yt_by_iid: dict[str, str] = {}

        # Top frame for controls
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(top_frame, text="按状态筛选:").pack(side=tk.LEFT, padx=(0, 5))
        self.status_var = tk.StringVar()
        self.status_cb = ttk.Combobox(top_frame, textvariable=self.status_var, state="readonly", width=15)
        self.status_cb["values"] = (
            "全部 (All)",
            "pending",
            "processing",
            "downloaded",
            "uploading",
            "uploaded",
            "failed",
            "give_up",
            "give_up_fatal",
        )
        self.status_cb.current(0)
        self.status_cb.pack(side=tk.LEFT, padx=5)
        self.status_cb.bind("<<ComboboxSelected>>", lambda e: self.fetch_metrics())

        refresh_btn = ttk.Button(top_frame, text="刷新数据", command=self.fetch_metrics)
        refresh_btn.pack(side=tk.LEFT, padx=10)

        export_btn = ttk.Button(top_frame, text="导出 CSV", command=self.export_csv)
        export_btn.pack(side=tk.LEFT, padx=(0, 10))

        reset_btn = ttk.Button(top_frame, text="重置选中为待处理 (Pending)", command=self.reset_selected)
        reset_btn.pack(side=tk.RIGHT, padx=5)

        hint = tk.Label(
            self.root,
            text="提示：表格最多展示最近 %s 条；选中行后底部显示摘要；双击或 Ctrl+C 复制；F5 刷新；「导出 CSV」按当前筛选最多导出 %s 条（错误摘要全文）。"
            % (VIDEOLIB_TABLE_ROW_LIMIT, VIDEOLIB_EXPORT_ROW_LIMIT),
            anchor=tk.W,
            fg="gray45",
            font=("Segoe UI", 9),
        )
        hint.pack(fill=tk.X, padx=10, pady=(0, 6))

        # Treeview setup（纵向 + 横向滚动：列总宽可能超过窗口）
        self.tree_frame = tk.Frame(self.root)
        self.tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        tree_inner = tk.Frame(self.tree_frame)
        tree_inner.pack(fill=tk.BOTH, expand=True)

        columns = ("ID", "Status", "Time", "Channel", "Retries", "Title", "Upload", "Summary", "Youtube", "Error")
        self.tree = ttk.Treeview(tree_inner, columns=columns, show="headings", selectmode="extended")

        self.tree.heading("ID", text="视频 ID")
        self.tree.heading("Status", text="状态")
        self.tree.heading("Time", text="最后更新 (北京)")
        self.tree.heading("Channel", text="发车频道(Account)")
        self.tree.heading("Retries", text="重试次数")
        self.tree.heading("Title", text="视频标题")
        self.tree.heading("Upload", text="上传进度")
        self.tree.heading("Summary", text="错误摘要")
        self.tree.heading("Youtube", text="YouTube ID")
        self.tree.heading("Error", text="本地路径")

        self.tree.column("ID", width=130, anchor=tk.CENTER)
        self.tree.column("Status", width=100, anchor=tk.CENTER)
        self.tree.column("Time", width=170, anchor=tk.CENTER)
        self.tree.column("Channel", width=130, anchor=tk.CENTER)
        self.tree.column("Retries", width=80, anchor=tk.CENTER)
        self.tree.column("Title", width=180, anchor=tk.W)
        self.tree.column("Upload", width=72, anchor=tk.CENTER)
        self.tree.column("Summary", width=180, anchor=tk.W)
        self.tree.column("Youtube", width=120, anchor=tk.W)
        self.tree.column("Error", width=150, anchor=tk.W)

        vs = ttk.Scrollbar(tree_inner, orient=tk.VERTICAL, command=self.tree.yview)
        hs = ttk.Scrollbar(self.tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vs.pack(side=tk.RIGHT, fill=tk.Y)
        hs.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_tree_double_click)
        self.root.bind("<Control-c>", self._on_copy_shortcut)
        self.root.bind("<F5>", self._on_f5_refresh)

        # Status bar
        self.status_lbl = tk.Label(self.root, text="已加载 0 条记录.", anchor=tk.W, justify=tk.LEFT)
        self.status_lbl.pack(fill=tk.X, padx=10, pady=2)

        self.fetch_metrics()

    def _current_db_filter(self) -> Optional[str]:
        filter_status = self.status_var.get()
        if filter_status and filter_status != "全部 (All)":
            return filter_status
        return None

    def export_csv(self) -> None:
        if not db.db_path.exists():
            messagebox.showwarning("提示", "数据库文件未找到，尚未初始化。")
            return
        out_path = filedialog.asksaveasfilename(
            parent=self.root,
            title="导出视频库 CSV",
            defaultextension=".csv",
            filetypes=[("CSV 表格", "*.csv"), ("所有文件", "*.*")],
        )
        if not out_path:
            return
        db_filter = self._current_db_filter()
        try:
            rows = VideoDAO.list_videos_for_library(
                filter_status=db_filter, limit=VIDEOLIB_EXPORT_ROW_LIMIT
            )
        except Exception as e:
            logger.exception("Videolib: export_csv query failed: %s", e)
            messagebox.showerror("数据库错误", str(e))
            return
        try:
            n = write_videolib_csv_file(out_path, rows)
        except OSError as e:
            logger.exception("Videolib: export_csv write failed: %s", e)
            messagebox.showerror("写入失败", str(e))
            return
        messagebox.showinfo("导出完成", "已写入 %s 条记录到:\n%s" % (n, out_path))

    def _status_base_text(self) -> str:
        return "已加载 %s 条记录。" % self._last_row_count

    def _on_tree_select(self, _event=None) -> None:
        sel = self.tree.selection()
        base = self._status_base_text()
        if not sel:
            self.status_lbl.config(text=base)
            return
        full = self._summary_by_iid.get(sel[0], "").strip()
        yt = self._yt_by_iid.get(sel[0], "").strip()
        if full:
            flat = full.replace("\r", " ").replace("\n", " ")
            if len(flat) > 420:
                flat = flat[:417] + "…"
            self.status_lbl.config(text=base + " ｜ 完整摘要: " + flat)
        elif yt:
            self.status_lbl.config(text=base + " ｜ YouTube ID: " + yt)
        else:
            self.status_lbl.config(text=base + " （当前行无错误摘要或 YouTube ID）")

    def _on_tree_double_click(self, _event=None) -> None:
        self._copy_selection_to_clipboard()

    def _on_copy_shortcut(self, _event=None) -> Optional[str]:
        if not self.tree.selection():
            return None
        self._copy_selection_to_clipboard()
        return "break"

    def _on_f5_refresh(self, _event=None) -> Optional[str]:
        self.fetch_metrics()
        return "break"

    def _copy_selection_to_clipboard(self) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        full = self._summary_by_iid.get(iid, "").strip()
        yt = self._yt_by_iid.get(iid, "").strip()
        base = self._status_base_text()
        copied = ""
        kind = ""
        try:
            if full:
                copied = full
                kind = "错误摘要"
                self.root.clipboard_clear()
                self.root.clipboard_append(full)
            elif yt:
                copied = yt
                kind = "YouTube 视频 ID"
                self.root.clipboard_clear()
                self.root.clipboard_append(yt)
            else:
                vals = self.tree.item(iid, "values")
                path = vals[-1] if vals else ""
                vid = vals[0] if vals else ""
                clip = (path or vid or "").strip()
                if not clip:
                    self.status_lbl.config(text=base + " （无可复制内容）")
                    return
                copied = clip
                kind = "本地路径" if (path or "").strip() else "视频 ID"
                self.root.clipboard_clear()
                self.root.clipboard_append(clip)
        except tk.TclError as e:
            logger.warning("Videolib: clipboard failed: %s", e)
            return
        self.root.update_idletasks()
        preview = copied.replace("\r", " ").replace("\n", " ")
        if len(preview) > 56:
            preview = preview[:53] + "…"
        self.status_lbl.config(text=base + " ｜ 已复制%s到剪贴板: %s" % (kind, preview))

    def fetch_metrics(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self._summary_by_iid.clear()
        self._yt_by_iid.clear()

        if not db.db_path.exists():
            self.status_lbl.config(text="数据库文件未找到，尚未初始化。")
            return

        db_filter = self._current_db_filter()

        try:
            rows = VideoDAO.list_videos_for_library(
                filter_status=db_filter, limit=VIDEOLIB_TABLE_ROW_LIMIT
            )
            self._last_row_count = len(rows)
            for row in rows:
                t_up = row[6] if len(row) > 6 else None
                up_done = row[7] if len(row) > 7 else 0
                up_total = row[8] if len(row) > 8 else None
                err_sum = row[9] if len(row) > 9 else None
                yt_raw = row[10] if len(row) > 10 else None
                st = row[1] if len(row) > 1 else ""
                iid = self.tree.insert(
                    "",
                    tk.END,
                    values=(
                        row[0],
                        st,
                        _format_updated_at_bj(t_up),
                        row[2] if row[2] else "Unknown",
                        row[3],
                        row[4],
                        _format_library_upload_progress(str(st), up_done, up_total),
                        _format_last_error_summary(err_sum),
                        _format_youtube_id_cell(yt_raw),
                        row[5] if row[5] else "",
                    ),
                )
                if err_sum is not None and str(err_sum).strip():
                    self._summary_by_iid[iid] = str(err_sum).strip()
                if yt_raw is not None and str(yt_raw).strip():
                    self._yt_by_iid[iid] = str(yt_raw).strip()
            self._on_tree_select()
        except Exception as e:
            logger.exception("Videolib: fetch_metrics failed: %s", e)
            messagebox.showerror("数据库错误", f"无法读取数据: {e}")

    def reset_selected(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("提示", "请先选中需要重置的行。")
            return

        if messagebox.askyesno(
            "确认操作",
            f"确定要把选中的 {len(selected_items)} 个任务状态重置为 Pending 吗？\n"
            "(这将会触发系统自动重新尝试下载和上传)",
        ):
            try:
                douyin_ids: list[str] = []
                for item in selected_items:
                    values = self.tree.item(item, "values")
                    douyin_ids.append(values[0])
                VideoDAO.bulk_reset_to_pending(douyin_ids)
                self.fetch_metrics()
                messagebox.showinfo("成功", "已成功重置！后台引擎会在下一次轮询时抓取它们。")
            except Exception as e:
                logger.exception("Videolib: reset_selected failed: %s", e)
                messagebox.showerror("重置失败", f"遇到错误: {e}")


def run_dashboard():
    app = tk.Tk()
    SyncDashboard(app)
    app.mainloop()


if __name__ == "__main__":
    run_dashboard()
