"""Shared helpers for the Sixth Form User Management GUI.

Split out of ``user_management_views`` (2026-10-22); that module
re-exports every name defined here.
"""
from __future__ import annotations

import logging
from tkinter import ttk




logger = logging.getLogger("education_system.systems.sixth_form.interfaces.gui.governance.user_management.user_management_views")


def _clear(gui) -> ttk.Frame:
    for w in gui.content_frame.winfo_children():
        w.destroy()
    return gui.content_frame


def _heading(parent, text: str) -> None:
    ttk.Label(parent, text=text, font=("", 16, "bold")).pack(
        anchor="w", pady=(0, 8))
