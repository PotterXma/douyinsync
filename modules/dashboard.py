import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_FILE = PROJECT_ROOT / "dist" / "douyinsync.db"

class SyncDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("视频状态管理库 | DouyinSync Dashboard")
        self.root.geometry("1000x600")

        # Top frame for controls
        top_frame = tk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(top_frame, text="按状态筛选:").pack(side=tk.LEFT, padx=(0, 5))
        self.status_var = tk.StringVar()
        self.status_cb = ttk.Combobox(top_frame, textvariable=self.status_var, state="readonly", width=15)
        self.status_cb['values'] = ("全部 (All)", "pending", "processing", "downloaded", "uploading", "uploaded", "failed", "give_up_fatal")
        self.status_cb.current(0)
        self.status_cb.pack(side=tk.LEFT, padx=5)
        self.status_cb.bind("<<ComboboxSelected>>", lambda e: self.fetch_metrics())

        refresh_btn = ttk.Button(top_frame, text="刷新数据", command=self.fetch_metrics)
        refresh_btn.pack(side=tk.LEFT, padx=10)

        reset_btn = ttk.Button(top_frame, text="重置选中为待处理 (Pending)", command=self.reset_selected)
        reset_btn.pack(side=tk.RIGHT, padx=5)

        # Treeview setup
        self.tree_frame = tk.Frame(self.root)
        self.tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ('ID', 'Status', 'Channel', 'Retries', 'Title', 'Error')
        self.tree = ttk.Treeview(self.tree_frame, columns=columns, show='headings', selectmode="extended")
        
        self.tree.heading('ID', text='视频 ID')
        self.tree.heading('Status', text='状态')
        self.tree.heading('Channel', text='发车频道(Account)')
        self.tree.heading('Retries', text='重试次数')
        self.tree.heading('Title', text='视频标题')
        self.tree.heading('Error', text='本地路径/信息')

        self.tree.column('ID', width=130, anchor=tk.CENTER)
        self.tree.column('Status', width=100, anchor=tk.CENTER)
        self.tree.column('Channel', width=150, anchor=tk.CENTER)
        self.tree.column('Retries', width=80, anchor=tk.CENTER)
        self.tree.column('Title', width=300, anchor=tk.W)
        self.tree.column('Error', width=150, anchor=tk.W)

        scrollbar = ttk.Scrollbar(self.tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Status bar
        self.status_lbl = tk.Label(self.root, text="已加载 0 条记录.", anchor=tk.W)
        self.status_lbl.pack(fill=tk.X, padx=10, pady=2)

        self.fetch_metrics()

    def fetch_metrics(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        if not DB_FILE.exists():
            self.status_lbl.config(text="数据库文件未找到，尚未初始化。")
            return

        filter_status = self.status_var.get()
        
        sql = "SELECT douyin_id, status, account_mark, retry_count, title, local_video_path FROM videos"
        params = []
        if filter_status and filter_status != "全部 (All)":
            sql += " WHERE status = ?"
            params.append(filter_status)
        sql += " ORDER BY updated_at DESC LIMIT 500"

        count = 0
        try:
            with sqlite3.connect(str(DB_FILE), timeout=5.0) as conn:
                cursor = conn.cursor()
                for row in cursor.execute(sql, tuple(params)):
                    self.tree.insert('', tk.END, values=(
                        row[0],
                        row[1],
                        row[2] if row[2] else 'Unknown',
                        row[3],
                        row[4],
                        row[5] if row[5] else ''
                    ))
                    count += 1
            self.status_lbl.config(text=f"已加载 {count} 条记录.")
        except Exception as e:
            messagebox.showerror("数据库错误", f"无法读取数据: {e}")

    def reset_selected(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("提示", "请先选中需要重置的行。")
            return

        if messagebox.askyesno("确认操作", f"确定要把选中的 {len(selected_items)} 个任务状态重置为 Pending 吗？\n(这将会触发系统自动重新尝试下载和上传)"):
            try:
                with sqlite3.connect(str(DB_FILE), timeout=5.0) as conn:
                    cursor = conn.cursor()
                    for item in selected_items:
                        values = self.tree.item(item, 'values')
                        douyin_id = values[0]
                        cursor.execute("UPDATE videos SET status = 'pending', retry_count = 0, updated_at = CURRENT_TIMESTAMP WHERE douyin_id = ?", (douyin_id,))
                    conn.commit()
                self.fetch_metrics()
                messagebox.showinfo("成功", "已成功重置！后台引擎会在下一次轮询时抓取它们。")
            except Exception as e:
                messagebox.showerror("重置失败", f"遇到错误: {e}")

if __name__ == "__main__":
    app = tk.Tk()
    dashboard = SyncDashboard(app)
    app.mainloop()
