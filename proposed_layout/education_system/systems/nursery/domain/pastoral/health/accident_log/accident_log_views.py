"""Tkinter view for the Accident & Incident Log (Nursery System).

Delegates to the shared Accident / Incident register view (``accident_report``):
the Daily-Care "Log" and the Compliance "Report" render the same manager.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from education_system.systems.nursery.domain.pastoral.health.accident_report import (
    accident_report_views as _impl,
)


def open_manager(host) -> None:
    """Open the shared Accident / Incident register in the host content pane."""
    _impl.open_accident_report_window(host)


def build(parent: tk.Misc, auth=None) -> ttk.Frame:
    frame = ttk.Frame(parent, padding=16)
    ttk.Label(frame, text="Accident & Incident Log",
              font=("", 14, "bold")).pack(anchor="w", pady=(0, 6))
    ttk.Label(frame, text="Open the Accident & Incident Log from the navigation menu."
              ).pack(anchor="w")
    return frame
