import sys
import subprocess
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import threading

from modules.logger import logger
from modules.config_manager import config

def create_image():
    """Generates an elegant dynamic base icon (Blue box with white center) natively 
    since we don't have .ico static files yet."""
    width = 64
    height = 64
    color1 = (43, 108, 222)   # Deep pleasant blue
    color2 = (255, 255, 255)  # White center
    
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle(
        (width // 4, height // 4, width * 3 // 4, height * 3 // 4),
        fill=color2)
    return image

class TrayController:
    def __init__(self, stop_event: threading.Event):
        self.stop_event = stop_event
        self.icon = None

    def _setup_icon(self):
        # Construct dynamic Right-Click schema matching user layout
        menu = (
            item('▶ 启动定时监控', self.action_start_monitor),
            item('⏹ 停止定时监控', self.action_stop_monitor),
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
        self.icon = pystray.Icon("DouyinSync", create_image(), "DouyinSync Pipeline Daemon", menu)

    def no_action(self, icon, item):
        """Null route for display-only menu items."""
        pass

    def action_start_monitor(self, icon, item):
        logger.info("Tray Menu UI: Triggered Start Monitor")

    def action_stop_monitor(self, icon, item):
        logger.info("Tray Menu UI: Triggered Stop Monitor")

    def action_open_settings(self, icon, item):
        logger.info("Tray Menu UI: Opening Settings Dashboard")
        self.action_dashboard(icon, item)

    def action_manual_run(self, icon, item):
        logger.info("Tray Menu UI: Manually running pipeline")
        import subprocess
        try:
            # Fork testing pipeline manually
            subprocess.Popen([sys.executable, "test_pipeline.py", "e2e"], shell=True)
        except Exception as e:
            logger.error(f"Manual Run Failed: {e}")

    def action_open_config_folder(self, icon, item):
        logger.info("Tray Menu UI: Opening Config Folder")
        import os
        import platform
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
        self.action_dashboard(icon, item)

    def action_dashboard(self, icon, item):
        """Epic 5.2: Dispatches the Tkinter script within an independent execution process. 
        Critical defense ensuring the Main Thread UI lock remains exclusively possessed by pystray."""
        logger.info("Tray Menu UI: Constructing detached Python Process for Tkinter Dashboard...")
        try:
            # sys.executable securely targets the active virtual environment mapping.
            subprocess.Popen([sys.executable, "-m", "modules.dashboard"])
        except Exception as e:
            logger.error(f"Tray Menu UI: Process Fork Failed -> {e}")

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
