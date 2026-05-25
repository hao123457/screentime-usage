from PIL import Image, ImageDraw
import pystray


def _create_icon_image():
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # clock circle
    draw.ellipse([4, 4, 60, 60], outline="#2196F3", width=3)

    # hour markers
    for i in range(12):
        import math
        angle = math.radians(i * 30 - 90)
        x1 = 32 + 22 * math.cos(angle)
        y1 = 32 + 22 * math.sin(angle)
        x2 = 32 + 26 * math.cos(angle)
        y2 = 32 + 26 * math.sin(angle)
        draw.line([x1, y1, x2, y2], fill="#2196F3", width=2)

    # hour hand (pointing roughly at 10)
    draw.line([32, 32, 24, 18], fill="#1976D2", width=4)

    # minute hand (pointing roughly at 2)
    draw.line([32, 32, 44, 22], fill="#1976D2", width=3)

    # center dot
    draw.ellipse([29, 29, 35, 35], fill="#1565C0")

    return img


def create_tray(on_open, on_exit):
    menu = pystray.Menu(
        pystray.MenuItem("打开统计面板", lambda: on_open()),
        pystray.MenuItem("退出", lambda: on_exit()),
    )
    icon = pystray.Icon(
        "UsageTracker",
        _create_icon_image(),
        "应用使用时间追踪",
        menu,
    )
    return icon
