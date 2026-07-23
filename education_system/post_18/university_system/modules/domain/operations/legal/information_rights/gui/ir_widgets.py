"""Embeddable widgets for Information Rights.

Drop into any dashboard for a one-line view of statutory-deadline
state. Mirrors the External-QA widget pattern.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.post_18.university_system.modules.domain.operations.legal.information_rights.services.information_rights_core import (
    InformationRightsService,
)

logger = logging.getLogger(__name__)


class IRStatusStrip(ttk.Frame):
    """One-line strip showing Open / Due-this-week / Overdue counts."""

    def __init__(self, parent, poll_seconds: int = 60, **kw):
        super().__init__(parent, **kw)
        self._svc = InformationRightsService()
        ttk.Label(self, text="Information Rights:",
                  font=("TkDefaultFont", 9, "bold")).pack(side=tk.LEFT,
                                                          padx=(0, 6))
        self._open = ttk.Label(self, text="open —", padding=(6, 0))
        self._open.pack(side=tk.LEFT)
        self._due = ttk.Label(self, text="due 7d —",
                                padding=(6, 0), foreground="#c47f00")
        self._due.pack(side=tk.LEFT)
        self._overdue = ttk.Label(self, text="overdue —",
                                    padding=(6, 0), foreground="#a32424")
        self._overdue.pack(side=tk.LEFT)
        self._poll_ms = max(0, int(poll_seconds * 1000))
        self.refresh()
        if self._poll_ms:
            self._schedule()

    def refresh(self) -> None:
        try:
            s = self._svc.dashboard_summary()
        except Exception:
            logger.exception("IRStatusStrip refresh failed")
            return
        self._open.configure(text=f"open {s.get('total_open', 0)}")
        self._due.configure(text=f"due 7d {s.get('due_within_7_days', 0)}")
        self._overdue.configure(text=f"overdue {s.get('overdue_count', 0)}")

    def _schedule(self) -> None:
        try:
            self.after(self._poll_ms, self._tick)
        except Exception:
            pass

    def _tick(self) -> None:
        if not self.winfo_exists():
            return
        self.refresh()
        self._schedule()


__all__ = ["IRStatusStrip"]
