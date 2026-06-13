import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext

# Import internationalization support
from education_system.university_system.core.i18n import get_text as _, init_i18n
# --- central logger (routes to university_system/logs/app.log) ----------
try:
    from education_system.university_system.infrastructure.logging.log_config import (
        configure_logging,
    )
    logger = configure_logging(name="attendance_tracker.gui.misc_tab")
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger("attendance_tracker.gui.misc_tab")
    if not logger.handlers:
        logger.addHandler(logging.StreamHandler())
        logger.setLevel(logging.INFO)
# -------------------------------------------------------------------------

init_i18n()

# Import HelpWindow from misc_windows
from education_system.university_system.modules.domain.academics.gui.attendance_tracker.misc_windows import HelpWindow


def show_help(self):
        """Show help information"""
        HelpWindow(self.root)

def show_about(self):
        """Show about dialog"""
        messagebox.showinfo(
            _("attendance.about.title"),
            _("attendance.about.message")
        )

