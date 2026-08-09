"""Extracted function implementation."""

from .. import first_aid_portal_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def main():
    _remove_legacy_db()
    root = tk.Tk()
    FirstAidPortal(root)
    root.mainloop()
