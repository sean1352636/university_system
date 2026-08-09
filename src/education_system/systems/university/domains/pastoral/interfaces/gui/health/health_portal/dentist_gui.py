"""Backward-compatible entry point for the modular dental-clinic GUI."""

import tkinter as tk

from .dentist.controller import DentistGUI

__all__ = ["DentistGUI", "launch_dentist_gui"]


def launch_dentist_gui(root=None, auth=None):
    """Create the dental GUI and return its root window."""
    if root is None:
        root = tk.Tk()
    DentistGUI(root, auth)
    return root
