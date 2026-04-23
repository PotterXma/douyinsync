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
        self.root.title("搬运时间设置看板 | 同步计划")
        self.root.geometry("520x480")
        
        self.config = {}
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except Exception:
                pass
                
        frame = tk.Frame(self.root, padx=20, pady=20)
        frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(frame, text="全局自动化调度", font=("Arial", 12, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 10), sticky=tk.W)

        mode = str(self.config.get("sync_schedule_mode", "interval") or "interval").lower()
        if mode not in ("interval", "clock"):
            mode = "interval"
        self.mode_var = tk.StringVar(value=mode)

        tk.Label(frame, text="调度方式:").grid(row=1, column=0, sticky=tk.W, pady=4)
        modes = tk.Frame(frame)
        modes.grid(row=1, column=1, sticky=tk.W, pady=4)
        tk.Radiobutton(modes, text="按间隔（每 N 分钟）", variable=self.mode_var, value="interval", command=self._toggle_mode_fields).pack(anchor=tk.W)
        tk.Radiobutton(modes, text="按固定时刻（本地 HH:MM，可多行）", variable=self.mode_var, value="clock", command=self._toggle_mode_fields).pack(anchor=tk.W)

        tk.Label(frame, text="间隔（分钟）:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.interval_var = tk.StringVar(value=str(self.config.get("sync_interval_minutes", 60)))
        self.interval_entry = ttk.Entry(frame, textvariable=self.interval_var, width=12)
        self.interval_entry.grid(row=2, column=1, sticky=tk.W, pady=5)

        tk.Label(frame, text="固定时刻（每行 HH:MM）:").grid(row=3, column=0, sticky=tk.NW, pady=5)
        times_lines = self._initial_clock_lines()
        self.times_text = tk.Text(frame, width=22, height=6, font=("Consolas", 10))
        self.times_text.grid(row=3, column=1, sticky=tk.W, pady=5)
        self.times_text.insert("1.0", times_lines)

        tk.Label(frame, text="单次最高抓取限制数:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.limit_var = tk.StringVar(value=str(self.config.get("max_videos_per_run", "5")))
        self.limit_entry = ttk.Entry(frame, textvariable=self.limit_var, width=12)
        self.limit_entry.grid(row=4, column=1, sticky=tk.W, pady=5)

        tk.Label(
            frame,
            text="保存后请在托盘菜单点「Reload Config」以立即重载排期。",
            font=("Arial", 9),
            fg="#555",
        ).grid(row=5, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))

        save_btn = ttk.Button(frame, text="保存到 config.json", command=self.save_settings)
        save_btn.grid(row=6, column=0, columnspan=2, pady=18)

        self._toggle_mode_fields()

    def _initial_clock_lines(self) -> str:
        raw = self.config.get("sync_clock_times")
        if isinstance(raw, list) and raw:
            lines = [str(x).strip() for x in raw if str(x).strip()]
            if lines:
                return "\n".join(lines) + "\n"
        try:
            h = int(self.config.get("cron_hour", 2))
            m = int(self.config.get("cron_minute", 0))
            return "%02d:%02d\n" % (h, m)
        except (TypeError, ValueError):
            return "02:00\n"

    def _toggle_mode_fields(self) -> None:
        use_interval = self.mode_var.get() == "interval"
        state_i = "normal" if use_interval else "disabled"
        state_t = "normal" if not use_interval else "disabled"
        self.interval_entry.configure(state=state_i)
        self.times_text.configure(state=state_t)

    def save_settings(self) -> None:
        try:
            limit = int(self.limit_var.get())
            mode = self.mode_var.get()
            if mode not in ("interval", "clock"):
                raise ValueError("无效的调度方式")

            if mode == "interval":
                interval = int(self.interval_var.get())
                if interval < 1:
                    raise ValueError("间隔至少为 1 分钟")
                self.config["sync_schedule_mode"] = "interval"
                self.config["sync_interval_minutes"] = interval
            else:
                raw_body = self.times_text.get("1.0", "end")
                slots: list[str] = []
                for line in raw_body.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if ":" not in line:
                        raise ValueError("每行需为 HH:MM 格式: %r" % (line,))
                    a, b = line.split(":", 1)
                    h = int(a.strip())
                    m = int(b.strip())
                    if not (0 <= h <= 23 and 0 <= m <= 59):
                        raise ValueError("时间越界: %r" % (line,))
                    slots.append("%02d:%02d" % (h, m))
                if not slots:
                    raise ValueError("请至少填写一行固定时刻")
                self.config["sync_schedule_mode"] = "clock"
                self.config["sync_clock_times"] = slots
                if slots:
                    h0, m0 = int(slots[0][:2]), int(slots[0][3:5])
                    self.config["cron_hour"] = h0
                    self.config["cron_minute"] = m0

            self.config["max_videos_per_run"] = limit

            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)

            messagebox.showinfo("成功", "已写入 config.json。\n请在托盘菜单执行 Reload Config 以应用排期。")
            self.root.destroy()
        except ValueError as e:
            messagebox.showerror("无效输入", str(e))


def run_settings_ui():
    app = tk.Tk()
    SettingsDashboard(app)
    app.mainloop()

if __name__ == "__main__":
    run_settings_ui()
