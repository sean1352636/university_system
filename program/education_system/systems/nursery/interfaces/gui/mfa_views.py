"""Tkinter view for Multi-Factor Authentication (Nursery System)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    """Build the Multi-Factor Authentication view into ``parent`` (placeholder)."""
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Multi-Factor Authentication",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame,
              text="This feature is coming soon.").pack(anchor="w")
    return frame
