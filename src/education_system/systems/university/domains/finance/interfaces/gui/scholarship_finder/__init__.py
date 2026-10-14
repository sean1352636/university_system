"""GUI interface for Scholarship Finder.

``scholarship_finder_gui`` hosts the Financial Aid student portal in its own
window with a finder navigation bar; the finder pages themselves live in
``financial_aid/student_portal/finder.py`` so the Financial Aid GUI shares them.
The CLI remains at ``interfaces/cli/scholarship_finder/scholarship_cli.py``.

The window module is imported lazily so importing this package stays free of
tkinter.
"""

from __future__ import annotations

__all__ = ["ScholarshipFinderWindow", "open_window", "main"]


def __getattr__(name: str):
    if name in __all__:
        from education_system.systems.university.domains.finance.interfaces.gui.scholarship_finder import (
            scholarship_finder_gui,
        )
        return getattr(scholarship_finder_gui, name)
    raise AttributeError(name)
