"""Email centre, as a lecturer sees it.

The same screen as the admin view rather than a second implementation:
teaching staff write to their learners from exactly the same log, and
splitting it would let the two drift into different rules about what
counts as sent.

Screens resolve under ``windows/<view>/``, so a shared screen has to be
re-exported into each view that offers it.
"""

from __future__ import annotations

from education_system.systems.fe_college.interfaces.gui.windows.admin.email import (
    TITLE,
    Screen,
    open_window,
)

__all__ = ["TITLE", "Screen", "open_window"]
