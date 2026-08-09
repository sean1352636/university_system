"""Extracted function implementation."""

from .. import train_station_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def main():
    root = tk.Tk()
    app = TrainStationApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
