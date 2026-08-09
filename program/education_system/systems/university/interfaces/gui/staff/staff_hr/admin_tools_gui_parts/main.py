"""Extracted function implementation."""

from .. import admin_tools_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def main():
    """Main function for standalone execution."""
    root = tk.Tk()
    app = AdminToolsGUI(root, None)
    root.mainloop()
