import sys
import tkinter as tk
from tkinter import ttk, messagebox
import json
from pathlib import Path

if getattr(sys, 'frozen', False):
    PROJECT_ROOT = Path(sys.executable).parent
else:
    PROJECT_ROOT = Path(__file__).resolve().parent.parent

CONFIG_FILE = PROJECT_ROOT / "config.json"

class SettingsDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("搬运时间设置看板 | 设定同步计划")
        self.root.geometry("450x300")
        
        # Load config
        self.config = {}
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except Exception:
                pass
                
        # Main Frame
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        tk.Label(frame, text="全局自动化调度时机设置", font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 15))
        
        # Hour
        tk.Label(frame, text="每日执行小时 (0-23):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.hour_var = tk.StringVar(value=str(self.config.get("cron_hour", "2")))
        self.hour_entry = ttk.Entry(frame, textvariable=self.hour_var, width=10)
        self.hour_entry.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # Minute
        tk.Label(frame, text="每日执行分钟 (0-59):").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.minute_var = tk.StringVar(value=str(self.config.get("cron_minute", "0")))
        self.minute_entry = ttk.Entry(frame, textvariable=self.minute_var, width=10)
        self.minute_entry.grid(row=2, column=1, sticky=tk.W, pady=5)
        
        # Max videos
        tk.Label(frame, text="单次最高抓取限制数:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.limit_var = tk.StringVar(value=str(self.config.get("max_videos_per_run", "5")))
        self.limit_entry = ttk.Entry(frame, textvariable=self.limit_var, width=10)
        self.limit_entry.grid(row=3, column=1, sticky=tk.W, pady=5)
        
        # Save Button
        save_btn = ttk.Button(frame, text="💾 保存并生效设置", command=self.save_settings)
        save_btn.grid(row=4, column=0, columnspan=2, pady=20)

    def save_settings(self):
        try:
            h = int(self.hour_var.get())
            m = int(self.minute_var.get())
            limit = int(self.limit_var.get())
            
            if not (0 <= h <= 23) or not (0 <= m <= 59):
                raise ValueError("时间超出了0-23或0-59范围！")
                
            self.config["cron_hour"] = h
            self.config["cron_minute"] = m
            self.config["max_videos_per_run"] = limit
            
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
                
            messagebox.showinfo("成功", "时间设置已保存！\n(后台服务将在下一次轮询时应用新排期配置)")
            self.root.destroy()
        except ValueError as e:
            messagebox.showerror("无效输入", f"请输入正确的数字:\n{e}")

def run_settings_ui():
    app = tk.Tk()
    SettingsDashboard(app)
    app.mainloop()

if __name__ == "__main__":
    run_settings_ui()
