"""Extracted function implementation."""

from .. import carrental_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def launch_carrental_gui(parent=None, auth=None):
    """Launch the Car Rental GUI"""
    if parent:
        window = tk.Toplevel(parent)
    else:
        window = tk.Tk()

    app = CarRentalGUI(window, auth)

    if not parent:
        window.mainloop()

    return app
