"""Tkinter view for User Management (Nursery System)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    """Build the User Management view into ``parent`` (placeholder)."""
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="User Management",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame,
              text="This feature is coming soon.").pack(anchor="w")
    return frame
