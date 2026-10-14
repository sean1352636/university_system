"""Extracted function implementation."""

from .. import musicshop_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def launch_musicshop_gui(parent=None, auth=None):
    """Launch the Music Shop GUI"""
    if parent:
        window = tk.Toplevel(parent)
    else:
        window = tk.Tk()

    app = MusicShopGUI(window, auth)

    if not parent:
        window.mainloop()

    return app
