from PIL import Image
import pystray

from config import ICON_PATH


def _load_icon_image():
    """Load app icon from ICON_PATH, crop to square, resize to 64x64 for tray."""
    try:
        img = Image.open(ICON_PATH).convert("RGBA")
        src_size = min(img.width, img.height)
        img = img.crop((0, 0, src_size, src_size))
        img = img.resize((64, 64), Image.LANCZOS)
        return img
    except Exception:
        # fallback: simple colored square
        return Image.new("RGB", (64, 64), "#2196F3")


def create_tray(on_open, on_settings, on_exit):
    """Create the system tray icon.

    Left-click (or double-click on older pystray versions) fires the
    default menu item to open the statistics panel.  Right-click shows
    the full context menu.
    """
    menu = pystray.Menu(
        pystray.MenuItem(
            "打开统计面板",
            lambda icon, item: on_open(),
            default=True,  # left-click / double-click → open
        ),
        pystray.MenuItem("设置...", lambda icon, item: on_settings()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("退出", lambda icon, item: on_exit()),
    )
    icon = pystray.Icon(
        "UsageTracker",
        _load_icon_image(),
        "应用使用时间追踪",
        menu,
    )
    return icon
