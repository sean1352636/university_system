"""Extracted function implementation."""

from .. import finance_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def start_gui_library_system():
    """Start the GUI library system"""
    root = tk.Tk()
    app = LibraryGUI(root)

    # Setup keyboard shortcuts
    setup_keyboard_shortcuts(root, app)

    root.mainloop()
