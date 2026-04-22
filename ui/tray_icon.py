import pystray
from pystray import MenuItem as item, Menu
from PIL import Image, ImageDraw
import queue
from utils.models import AppEvent

def create_image():
    # Create an image for the tray icon
    width = 64
    height = 64
    image = Image.new('RGB', (width, height), color=(30, 30, 30))
    dc = ImageDraw.Draw(image)
    dc.rectangle(
        (width // 4, height // 4, width * 3 // 4, height * 3 // 4),
        fill=(46, 204, 113)
    )
    return image

class TrayApp:
    def __init__(self, event_queue: queue.Queue):
        self.event_queue = event_queue
        self.icon = None

    def on_reload(self, icon, item):
        self.event_queue.put(AppEvent(command="RELOAD_CONFIG"))
        icon.notify("Config Reloaded", title="DouyinSync")

    def on_open_dashboard(self, icon, item):
        self.event_queue.put(AppEvent(command="OPEN_DASHBOARD"))
        icon.notify("Dashboard Opening", title="DouyinSync")

    def on_exit(self, icon, item):
        self.event_queue.put(AppEvent(command="EXIT"))
        icon.stop()

    def setup(self):
        menu = Menu(
            item('Open Dashboard', self.on_open_dashboard, default=True),
            item('Reload Config', self.on_reload),
            item('Exit', self.on_exit)
        )
        self.icon = pystray.Icon("DouyinSync", create_image(), "DouyinSync", menu)

    def run(self):
        if not self.icon:
            self.setup()
        self.icon.run()
