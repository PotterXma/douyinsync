import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from pathlib import Path

from utils.paths import data_root

DB_FILE = data_root() / "douyinsync.db"

class StatsDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("统计信息 | 同步转化率看板")
        self.root.geometry("400x300")
        
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(frame, text="Douyin->YouTube 总体资产", font=("Arial", 12, "bold")).pack(pady=(0, 15))
        
        self.stats_text = tk.StringVar(value="读取中...")
        lbl = tk.Label(frame, textvariable=self.stats_text, justify=tk.LEFT, font=("Consolas", 11))
        lbl.pack(fill=tk.BOTH, expand=True)
        
        ttk.Button(frame, text="刷新", command=self.load_stats).pack(pady=10)
        
        self.load_stats()
        
    def load_stats(self):
        if not DB_FILE.exists():
            self.stats_text.set("当前系统内尚无数据库文件配置，统计信息无法拉取。\n请确保应用正在运行或已连接有效配置。")
            return
            
        try:
            with sqlite3.connect(str(DB_FILE), timeout=5.0) as conn:
                cursor = conn.cursor()
                
                # Fetch global state counts
                rows = cursor.execute("SELECT status, COUNT(*) FROM videos GROUP BY status").fetchall()
                total = cursor.execute("SELECT COUNT(*) FROM videos").fetchone()[0]
                
                stats_dict = dict(rows)
                
                t = f"总共捕获视频数目: {total} 个\n"
                t += f"------------------------------------\n"
                t += f"等待执行的 (Pending):  {stats_dict.get('pending', 0)} 个\n"
                t += f"处理截图中 (Processing): {stats_dict.get('processing', 0)} 个\n"
                t += f"资源已落盘 (Downloaded): {stats_dict.get('downloaded', 0)} 个\n"
                t += f"等待油管API (Uploading): {stats_dict.get('uploading', 0)} 个\n"
                t += f"完美上传的 (Uploaded):  {stats_dict.get('uploaded', 0)} 个\n"
                t += f"\n异常失效废弃 (Failed/Give Up): {stats_dict.get('failed', 0) + stats_dict.get('give_up_fatal', 0)} 个"
                
                self.stats_text.set(t)
        except Exception as e:
            self.stats_text.set(f"无法正确读取状态:\n{e}")

def run_stats_ui():
    app = tk.Tk()
    StatsDashboard(app)
    app.mainloop()

if __name__ == "__main__":
    run_stats_ui()
