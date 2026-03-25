import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog, scrolledtext

# Import internationalization support
from education_system.university_system.modules.shared.utils.i18n import get_text as _, init_i18n
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

