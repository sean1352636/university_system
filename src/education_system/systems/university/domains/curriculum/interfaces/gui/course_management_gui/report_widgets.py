"""Compatibility path for the Academics report widgets.

The widgets moved to ``academics.interfaces.gui.report_widgets`` so that GUIs
outside Course Management (the Academic Calendar reports) can use them
without importing this package, whose ``__init__`` loads the whole Course
Management application. Existing ``course_management_gui.report_widgets``
imports keep working through this module.
"""

from education_system.systems.university.infrastructure.ui.report_widgets import (  # noqa: F401
    ACCENT,
    BAD,
    BG,
    CARD,
    FONT,
    HEADER,
    LABEL,
    MUTED,
    OK,
    VALUE,
    WARN,
    banner,
    card,
    clear,
    kv_grid,
    report_window,
    scrollable,
    stat_strip,
    status_list,
    table,
    verdict,
)

__all__ = [
    "scrollable", "clear", "banner", "stat_strip", "card", "kv_grid",
    "status_list", "verdict", "table", "report_window",
    "BG", "CARD", "HEADER", "ACCENT", "LABEL", "VALUE", "MUTED",
    "OK", "WARN", "BAD", "FONT",
]
