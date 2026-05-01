import json
import re
import tkinter as tk
from tkinter import messagebox, ttk

from utils.paths import data_root, reload_config_request_path

CONFIG_FILE = data_root() / "config.json"


def _minutes_to_display_hours(minutes: int) -> int:
    """Map stored minutes to spinbox hours (ceil), at least 1."""
    try:
        m = max(1, int(minutes))
    except (TypeError, ValueError):
        m = 60
    return max(1, (m + 59) // 60)


def _parse_clock_times(raw: str) -> list[str]:
    """Accept English/Chinese commas and newlines; return normalized HH:MM strings."""
    slots: list[str] = []
    for chunk in re.split(r"[\s,，;；]+", (raw or "").strip()):
        part = chunk.strip()
        if not part or part.startswith("#"):
            continue
        if ":" not in part:
            raise ValueError("时间点需为 HH:MM 格式，无效片段: %r" % (part,))
        a, b = part.split(":", 1)
        h = int(a.strip())
        m = int(b.strip())
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError("时间越界: %r" % (part,))
        slots.append("%02d:%02d" % (h, m))
    if not slots:
        raise ValueError("请至少填写一个执行时间点（如 06:30 或 08:00,20:00）")
    return slots


def _touch_reload_request() -> None:
    try:
        reload_config_request_path().touch(exist_ok=True)
    except OSError:
        pass


class SettingsDashboard:
    """搬运时间设置看板：间隔（按小时）与定点（本地 HH:MM，逗号分隔）。"""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("搬运时间设置看板")
        self.root.geometry("520x320")
        self.root.minsize(480, 280)

        self.config: dict = {}
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
            except Exception:
                pass

        mode = str(self.config.get("sync_schedule_mode", "interval") or "interval").lower()
        if mode not in ("interval", "clock"):
            mode = "interval"
        self.mode_var = tk.StringVar(value=mode)

        outer = tk.Frame(self.root, padx=16, pady=12)
        outer.pack(fill=tk.BOTH, expand=True)

        lf_mode = tk.LabelFrame(outer, text="调度模式选择", padx=10, pady=8)
        lf_mode.pack(fill=tk.X, pady=(0, 10))

        tk.Radiobutton(
            lf_mode,
            text="1. 间隔模式（如：每过 N 小时执行一次）",
            variable=self.mode_var,
            value="interval",
            command=self._toggle_mode_fields,
            anchor=tk.W,
        ).pack(fill=tk.X, pady=2)
        tk.Radiobutton(
            lf_mode,
            text="2. 定点模式（如：每天 08:00, 20:00 执行）",
            variable=self.mode_var,
            value="clock",
            command=self._toggle_mode_fields,
            anchor=tk.W,
        ).pack(fill=tk.X, pady=2)

        lf_params = tk.LabelFrame(outer, text="参数设置", padx=10, pady=8)
        lf_params.pack(fill=tk.X, pady=(0, 12))

        row_i = tk.Frame(lf_params)
        row_i.pack(fill=tk.X, pady=6)
        tk.Label(row_i, text="执行间隔 (小时):").pack(side=tk.LEFT, padx=(0, 8))
        im = self.config.get("sync_interval_minutes", 240)
        self.hours_var = tk.StringVar(value=str(_minutes_to_display_hours(im)))
        self.spin_hours = tk.Spinbox(
            row_i,
            from_=1,
            to=168,
            width=6,
            textvariable=self.hours_var,
            justify=tk.RIGHT,
        )
        self.spin_hours.pack(side=tk.LEFT)

        row_t = tk.Frame(lf_params)
        row_t.pack(fill=tk.X, pady=6)
        tk.Label(row_t, text="执行时间点:").pack(side=tk.LEFT, padx=(0, 8))
        self.times_var = tk.StringVar(value=self._initial_clock_string())
        self.times_entry = ttk.Entry(row_t, textvariable=self.times_var, width=22)
        self.times_entry.pack(side=tk.LEFT, padx=(0, 6))
        tk.Label(row_t, text="(用英文逗号分隔，如 08:00, 20:00)", fg="#555").pack(side=tk.LEFT)

        hint = tk.Label(
            outer,
            text="保存后若主程序（托盘）正在运行，将自动重载排期；单独打开本窗口时请重新启动主程序或点托盘「Reload Config」。",
            font=("Segoe UI", 8),
            fg="#666",
            wraplength=480,
            justify=tk.LEFT,
        )
        hint.pack(fill=tk.X, pady=(0, 6))

        bar = tk.Frame(outer)
        bar.pack(fill=tk.X, side=tk.BOTTOM)
        ttk.Button(bar, text="保存并生效", command=self.save_settings).pack(side=tk.RIGHT)

        self._toggle_mode_fields()

    def _initial_clock_string(self) -> str:
        raw = self.config.get("sync_clock_times")
        if isinstance(raw, list) and raw:
            parts = [str(x).strip() for x in raw if str(x).strip()]
            if parts:
                return ", ".join(parts)
        try:
            h = int(self.config.get("cron_hour", 6))
            m = int(self.config.get("cron_minute", 30))
            return "%02d:%02d" % (h, m)
        except (TypeError, ValueError):
            return "06:30"

    def _toggle_mode_fields(self) -> None:
        use_interval = self.mode_var.get() == "interval"
        self.spin_hours.configure(state="normal" if use_interval else "disabled")
        self.times_entry.configure(state="disabled" if use_interval else "normal")

    def save_settings(self) -> None:
        try:
            mode = self.mode_var.get()
            if mode not in ("interval", "clock"):
                raise ValueError("无效的调度方式")

            if mode == "interval":
                h = int(self.hours_var.get())
                if h < 1:
                    raise ValueError("间隔至少为 1 小时")
                self.config["sync_schedule_mode"] = "interval"
                self.config["sync_interval_minutes"] = h * 60
            else:
                slots = _parse_clock_times(self.times_var.get())
                self.config["sync_schedule_mode"] = "clock"
                self.config["sync_clock_times"] = slots
                h0, m0 = int(slots[0][:2]), int(slots[0][3:5])
                self.config["cron_hour"] = h0
                self.config["cron_minute"] = m0

            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)

            _touch_reload_request()
            messagebox.showinfo(
                "已保存",
                "已写入 config.json，并已通知主进程重载排期（若托盘程序正在运行）。\n"
                "若当前仅单独打开了本窗口，请启动主程序或手动 Reload Config。",
            )
            self.root.destroy()
        except ValueError as e:
            messagebox.showerror("无效输入", str(e))


def run_settings_ui() -> None:
    app = tk.Tk()
    SettingsDashboard(app)
    app.mainloop()


if __name__ == "__main__":
    run_settings_ui()
