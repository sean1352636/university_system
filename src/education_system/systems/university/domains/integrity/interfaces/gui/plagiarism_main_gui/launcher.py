"""Entry points other screens use to open Academic Integrity.

The old plagiarism checker window (with its whole-database backup and
restore, mock sign-in and simulated workflow) was replaced by
:mod:`window`; these names are kept so existing menus keep working.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def launch_gui_from_main_system(auth=None, parent=None):
    """Open Academic Integrity for whoever is signed in to ``auth``."""
    import tkinter as tk

    from education_system.systems.university.domains.integrity.interfaces.gui.plagiarism_main_gui.window import (  # noqa: E501
        open_integrity_window,
    )
    if parent is None:
        parent = tk._default_root
    if parent is None:
        logger.error("Academic Integrity needs the University window to be open")
        return None
    return open_integrity_window(parent, auth)


def integrate_plagiarism_checker_with_main():
    """Nothing to wire up: Academic Integrity is opened from the University
    window's menus. Kept for the CLI start-up hook that calls it."""
    return True


def main():
    print("Academic Integrity is opened from the University window after signing in.")
    return 1
