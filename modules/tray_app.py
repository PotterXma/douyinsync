import sys
import subprocess
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import threading
from tkinter import messagebox

from modules.logger import logger
from modules.config_manager import config

def create_image(status="running"):
    """Generates an elegant dynamic base icon reflecting the monitoring status."""
    width = 64
    height = 64
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    
    if status == "running":
        # Vibrant red/coral block
        dc.rounded_rectangle((4, 14, 60, 50), radius=10, fill=(231, 76, 60))
        # Play triangle pointing right
        dc.polygon([(26, 22), (26, 42), (42, 32)], fill=(255, 255, 255))
    else:
        # Grayed out block for paused state
        dc.rounded_rectangle((4, 14, 60, 50), radius=10, fill=(149, 165, 166))
        # Pause vertical bars
        dc.rectangle((24, 24, 30, 40), fill=(255, 255, 255))
        dc.rectangle((34, 24, 40, 40), fill=(255, 255, 255))
        
    return image

class TrayController:
    def __init__(self, stop_event: threading.Event):
        self.stop_event = stop_event
        self.icon = None
        self.is_monitoring = True
        self.coordinator = None  # Set by main.py after PipelineCoordinator is created

    def _setup_icon(self):
        # Construct dynamic Right-Click schema matching user layout
        menu = (
            item(lambda text: '▶ 启动定时监控' if not self.is_monitoring else '▶ 启动定时监控 (已运行)', 
                 self.action_start_monitor,
                 enabled=lambda item: not self.is_monitoring),
            item(lambda text: '⏹ 停止定时监控' if self.is_monitoring else '⏹ 停止定时监控 (已暂停)', 
                 self.action_stop_monitor,
                 enabled=lambda item: self.is_monitoring),
            item('─' * 20, self.no_action, enabled=False),
            item('⚙️ 搬运时间设置看板', self.action_open_settings),
            item('─' * 20, self.no_action, enabled=False),
            item('🔙 手动执行一次', self.action_manual_run),
            item('─' * 20, self.no_action, enabled=False),
            item('🎥 视频状态管理库', self.action_dashboard),
            item('📁 打开配置文件夹', self.action_open_config_folder),
            item('📊 查看统计信息', self.action_view_stats),
            item('─' * 20, self.no_action, enabled=False),
            item('❌ 退出程序', self.action_exit)
        )
        self.icon = pystray.Icon("DouyinSync", create_image("running"), "DouyinSync Pipeline Daemon", menu)

    def no_action(self, icon, item):
        """Null route for display-only menu items."""
        pass

    def action_start_monitor(self, icon, item):
        logger.info("Tray Menu UI: Triggered Start Monitor")
        self.is_monitoring = True
        self.icon.icon = create_image("running")
        self.icon.update_menu()
        # Resume the APScheduler if it was paused
        if self.coordinator and hasattr(self.coordinator, 'scheduler'):
            try:
                self.coordinator.scheduler.resume()
            except Exception:
                pass
        messagebox.showinfo("服务状态", "定时监控引擎已激活。后台将在设定时间拉取资源。")

    def action_stop_monitor(self, icon, item):
        logger.info("Tray Menu UI: Triggered Stop Monitor")
        self.is_monitoring = False
        self.icon.icon = create_image("paused")
        self.icon.update_menu()
        # Pause the APScheduler to actually stop scheduled jobs
        if self.coordinator and hasattr(self.coordinator, 'scheduler'):
            try:
                self.coordinator.scheduler.pause()
            except Exception:
                pass
        messagebox.showinfo("服务状态", "定时监控引擎已暂停！")

    def action_open_settings(self, icon, item):
        logger.info("Tray Menu UI: Opening Settings Dashboard")
        import subprocess
        import os
        try:
            if getattr(sys, 'frozen', False):
                cmd = [sys.executable, "settings"]
                subprocess.Popen(cmd)
            else:
                path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "main.py")
                cmd = [sys.executable, path, "settings"]
                subprocess.Popen(cmd)
        except Exception as e:
            logger.error("Tray Menu UI: Process Fork Failed -> %s", e)

    def action_manual_run(self, icon, item):
        logger.info("Tray Menu UI: Manually running pipeline (in-process)")
        if self.coordinator:
            import threading
            t = threading.Thread(target=self.coordinator.primary_sync_job, daemon=True)
            t.start()
        else:
            logger.error("Tray Menu UI: No coordinator reference available for manual run.")

    def action_open_config_folder(self, icon, item):
        logger.info("Tray Menu UI: Opening Config Folder")
        import os
        import platform
        import sys
        if getattr(sys, 'frozen', False):
            project_root = os.path.dirname(sys.executable)
        else:
            path = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(path)
        if platform.system() == "Windows":
            os.startfile(project_root)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", project_root])
        else:
            subprocess.Popen(["xdg-open", project_root])

    def action_view_stats(self, icon, item):
        logger.info("Tray Menu UI: Viewing Statistics")
        import subprocess
        import os
        try:
            if getattr(sys, 'frozen', False):
                cmd = [sys.executable, "stats"]
                subprocess.Popen(cmd)
            else:
                path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "main.py")
                cmd = [sys.executable, path, "stats"]
                subprocess.Popen(cmd)
        except Exception as e:
            logger.error("Tray Menu UI: Process Fork Failed -> %s", e)

    def action_dashboard(self, icon, item):
        logger.info("Tray Menu UI: Constructing detached Python Process for Tkinter Dashboard...")
        import subprocess
        import os
        try:
            if getattr(sys, 'frozen', False):
                cmd = [sys.executable, "dashboard"]
                subprocess.Popen(cmd)
            else:
                path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "main.py")
                cmd = [sys.executable, path, "dashboard"]
                subprocess.Popen(cmd)
        except Exception as e:
            logger.error("Tray Menu UI: Process Fork Failed -> %s", e)

    def action_reload_config(self, icon, item):
        """Dispatches a request to cleanly fetch from config.json again."""
        logger.info("Tray Menu UI: User triggered explicit Config Reload.")
        # Reload operation acts synchronously inside thread scope 
        # (It's rapid pure local file I/O so won't drop frames)
        success = config.reload()
        if success:
            logger.info("Tray Menu UI: Reload Sequence succeeded. Daemon will fetch fresh config on next heartbeat.")
        else:
            logger.error("Tray Menu UI: Reload Sequence failed due to malformed configs, rolling back.")

    def action_exit(self, icon, item):
        """Gracefully halts the background logic thread and tears down the GUI."""
        logger.info("Tray Menu UI: Safely extracting via user Exit command...")
        
        # Signal the separate threading structure.
        self.stop_event.set()
        
        if self.icon:
            # Drop the system tray mount immediately so Windows UI doesn't hang
            self.icon.stop() 

    def run(self):
        """BLOCKING call. Must be instantiated inside Main system Thread (not sub-threads) for GUI."""
        logger.info("Mounting Windows pystray Graphic Controls...")
        self._setup_icon()
        self.icon.run()
