import tkinter as tk
import threading
import os

from PIL import Image, ImageTk

from database import init_db
from tracker import Tracker
from gui import UsageWindow
from tray_icon import create_tray
from config import ICON_PATH, START_MINIMIZED


def _set_window_icon(root):
    try:
        img = Image.open(ICON_PATH).convert("RGBA")
        src_size = min(img.width, img.height)
        img = img.crop((0, 0, src_size, src_size))
        img = img.resize((32, 32), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        root.iconphoto(True, photo)
        root._icon_photo = photo  # prevent GC
    except Exception:
        pass


def main():
    script_path = os.path.abspath(__file__)

    init_db()

    root = tk.Tk()

    _set_window_icon(root)

    tracker = Tracker()
    tracker.start(root)

    gui = UsageWindow(root, script_path, tracker)

    def on_open():
        root.after(0, _show_window)

    def _show_window():
        root.deiconify()
        root.lift()
        root.focus_force()
        gui._refresh()

    def on_settings():
        root.after(0, _show_window)
        root.after(100, gui._open_settings)

    def on_exit():
        tracker.stop()
        tray.stop()
        root.after(0, root.destroy)

    tray = create_tray(on_open, on_settings, on_exit)

    if START_MINIMIZED:
        root.withdraw()

    root.protocol("WM_DELETE_WINDOW", lambda: root.withdraw())

    tray_thread = threading.Thread(target=tray.run, daemon=True)
    tray_thread.start()

    root.mainloop()


if __name__ == "__main__":
    main()
