"""Extracted function implementation."""

from .. import green_initiatives_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


def open_green_initiatives_dialog(self):
    """Open green initiatives and sustainability dialog"""
    dialog = GreenInitiativesDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)
