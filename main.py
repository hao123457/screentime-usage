import ctypes
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
    """Set window icon for title bar (iconphoto) AND taskbar (iconbitmap).

    - iconphoto  -> WM_SETICON per-window icon (title bar, Alt+Tab)
    - iconbitmap -> GCLP_HICON window-class icon (taskbar, task switcher)

    On Windows, the taskbar reads the window CLASS icon, not the per-window
    icon.  iconphoto() alone does NOT set the class icon, so we need BOTH.
    """
    import tempfile

    # 1. Set window CLASS icon via iconbitmap (Windows taskbar)
    iconbitmap_ok = False
    try:
        root.iconbitmap(ICON_PATH)
        iconbitmap_ok = True
    except Exception as e:
        print(f"[icon] iconbitmap failed with original ICO: {e}")

    if not iconbitmap_ok:
        # Fallback: use PIL to save a BMP-format ICO (no PNG compression)
        # that even legacy LoadImage / Win32 will accept.
        try:
            img = Image.open(ICON_PATH)
            img = img.resize((32, 32), Image.LANCZOS).convert("RGB")
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".ico")
            tmp_path = tmp.name
            tmp.close()
            img.save(tmp_path, format="ICO", sizes=[(32, 32)])
            root.iconbitmap(tmp_path)
            root._iconbitmap_temp = tmp_path
            print("[icon] iconbitmap succeeded with BMP ICO fallback")
        except Exception as e:
            print(f"[icon] BMP ICO fallback also failed: {e}")

    # 2. Set per-window icon via iconphoto (title bar, Alt+Tab)
    try:
        img = Image.open(ICON_PATH)
        # Resize to a sensible window-icon size; ICOs can be up to 256×256
        img = img.resize((48, 48), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)
        root.iconphoto(True, photo)
        root._icon_photo = photo  # prevent GC
    except Exception as e:
        print(f"[icon] iconphoto failed: {e}")


def main():
    script_path = os.path.abspath(__file__)

    init_db()

    # Must be called BEFORE tk.Tk() so Windows treats this as a
    # standalone app with its own taskbar icon, not python.exe.
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
        "hao.app_usage_tracker.v1"
    )

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
