import tkinter as tk
import threading
import os

from database import init_db
from tracker import Tracker
from gui import UsageWindow
from tray_icon import create_tray


def main():
    script_path = os.path.abspath(__file__)

    init_db()

    root = tk.Tk()
    root.withdraw()

    tracker = Tracker()
    tracker.start(root)

    gui = UsageWindow(root, script_path)

    def on_open():
        root.after(0, _show_window)

    def _show_window():
        root.deiconify()
        root.lift()
        root.focus_force()
        gui._refresh()

    def on_exit():
        tracker.stop()
        tray.stop()
        root.after(0, root.destroy)

    tray = create_tray(on_open, on_exit)

    root.protocol("WM_DELETE_WINDOW", lambda: root.withdraw())

    tray_thread = threading.Thread(target=tray.run, daemon=True)
    tray_thread.start()

    root.mainloop()


if __name__ == "__main__":
    main()
