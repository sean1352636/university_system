"""Module Scheduling — Timetables tab (thin launcher).

The full timetable feature (generate / view / email / export student &
instructor timetables) has moved into its own standalone window,
``academics.gui.timetable_management.TimetableManagementGUI``, which is also
launched from the main GUI. This tab now just provides buttons to open it.

A handful of general scheduling helpers that happen to have lived in this
file historically remain here because other tabs depend on them:
``_select_module_dialog`` (schedules tab), ``view_calendar`` (settings tab),
``show_grid_view`` / ``_show_drag_drop_grid`` (main toolbar) and
``_show_student_timetable_dialog``.
"""
from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH, get_connection  # noqa: F401

# Import internationalization (i18n) for multi-language support
try:
    from education_system.systems.university.infrastructure.i18n import get_text as _t
    init_available = True
except ImportError:
    init_available = False
    _t = lambda key, **kwargs: key  # noqa: E731

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime

from education_system.systems.university.interfaces.gui.academics.module_scheduling.main_gui import ModuleSchedulingGUI
from education_system.systems.university.interfaces.gui.academics.module_scheduling.dialogs import GridViewWindow


def create_timetables_tab(self):
    """Create the (thin) timetables tab: buttons that open the standalone
    Timetable Manager window."""
    timetables_frame = ttk.Frame(self.notebook)
    self.notebook.add(timetables_frame, text=_t("scheduling.tabs.timetables"))

    box = ttk.LabelFrame(timetables_frame,
                         text=_t("scheduling.tabs.timetables"), padding=20)
    box.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

    ttk.Label(
        box,
        text="Generate, view, email and export student & instructor "
             "timetables in the Timetable Manager.",
        font=("Arial", 11), wraplength=520, justify=tk.LEFT,
    ).pack(anchor="w", pady=(0, 14))

    ttk.Button(box, text="Open Timetable Manager…",
               command=self.open_timetable_manager).pack(anchor="w", pady=4)
    ttk.Button(box, text="Open Student Timetable Viewer…",
               command=self._show_student_timetable_dialog).pack(anchor="w", pady=4)


ModuleSchedulingGUI.create_timetables_tab = create_timetables_tab


def open_timetable_manager(self):
    """Open the standalone Timetable Manager window."""
    try:
        from education_system.systems.university.interfaces.gui.academics.timetable_management import (
            TimetableManagementGUI,
        )
        app = TimetableManagementGUI(self.root, auth=getattr(self, "auth", None))
        try:
            app.window.transient(self.root)
            app.window.grab_set()
        except Exception:
            pass
    except Exception as e:
        messagebox.showerror("Error",
                             f"Failed to open Timetable Manager: {e}",
                             parent=self.root)


ModuleSchedulingGUI.open_timetable_manager = open_timetable_manager


# ---------------------------------------------------------------------------
# Shared helpers retained here because OTHER tabs depend on them.
# ---------------------------------------------------------------------------
def _select_module_dialog(self):
    """Show dialog to select a module. Used by the schedules tab."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT module_code, module_name FROM modules ORDER BY module_code")
        modules = cursor.fetchall()

    if not modules:
        messagebox.showinfo("No Modules", "No modules found in the system.", parent=self.root)
        return None

    dialog = tk.Toplevel(self.root)
    dialog.title("Select Module")
    dialog.geometry("600x400")
    dialog.transient(self.root)
    dialog.grab_set()

    selected = [None]

    listbox = tk.Listbox(dialog, font=('Arial', 10))
    for code, name in modules:
        listbox.insert(tk.END, f"{code} - {name}")
    listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def on_select():
        if listbox.curselection():
            idx = listbox.curselection()[0]
            selected[0] = modules[idx][0]
            dialog.destroy()

    ttk.Button(dialog, text="Select", command=on_select).pack(pady=5)

    dialog.wait_window()
    return selected[0]


ModuleSchedulingGUI._select_module_dialog = _select_module_dialog


def view_calendar(self):
    """View academic calendar - opens the full academic calendar GUI.

    Used by the settings tab.
    """
    try:
        from education_system.systems.university.interfaces.gui.academics.academic_calendar.main_gui import CalendarGUI

        calendar_window = tk.Toplevel(self.root)
        calendar_window.title("Academic Calendar")
        calendar_window.geometry("1200x800")

        try:
            CalendarGUI(parent_window=calendar_window)
            self.update_activity_log("Opened Academic Calendar")
            return
        except Exception as e:
            print(f"Could not load full calendar GUI: {e}")
            calendar_window.destroy()
            calendar_window = tk.Toplevel(self.root)
            calendar_window.title("Academic Calendar - Basic View")
            calendar_window.geometry("600x400")

        calendar_text = scrolledtext.ScrolledText(calendar_window, font=('Courier', 10))
        calendar_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()
            current_month = datetime.now().strftime("%Y-%m")
            cursor.execute('''
            SELECT holiday_name, start_date, end_date, description
            FROM holidays
            WHERE start_date LIKE ?
            ORDER BY start_date
            ''', (f"{current_month}%",))
            holidays = cursor.fetchall()

        calendar_text.insert(tk.END, f"Academic Calendar - {datetime.now().strftime('%B %Y')}\n")
        calendar_text.insert(tk.END, "=" * 60 + "\n")

        if holidays:
            for holiday in holidays:
                name, start, end, desc = holiday
                if start == end:
                    calendar_text.insert(tk.END, f"{start}: {name}\n")
                else:
                    calendar_text.insert(tk.END, f"{start} to {end}: {name}\n")
                if desc:
                    calendar_text.insert(tk.END, f"  {desc}\n")
                calendar_text.insert(tk.END, "\n")
        else:
            calendar_text.insert(tk.END, "No holidays scheduled for this month.\n")

        calendar_text.insert(tk.END, "=" * 60 + "\n")
        calendar_text.config(state=tk.DISABLED)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to view calendar: {str(e)}", parent=self.root)


ModuleSchedulingGUI.view_calendar = view_calendar


def show_grid_view(self):
    """Show schedule in grid view. Used by the main toolbar."""
    GridViewWindow(self.root, self.scheduler)


ModuleSchedulingGUI.show_grid_view = show_grid_view


def _show_student_timetable_dialog(self):
    """Open the per-student week-grid viewer."""
    try:
        from education_system.systems.university.interfaces.gui.academics.module_scheduling.student_timetable_dialog import StudentTimetableDialog
        StudentTimetableDialog(self.root, self.scheduler)
    except Exception as e:
        messagebox.showerror("Error",
                             f"Failed to open student timetable viewer: {e}",
                             parent=self.root)


ModuleSchedulingGUI._show_student_timetable_dialog = _show_student_timetable_dialog


def _show_drag_drop_grid(self):
    """Open the canvas-based drag-and-drop weekly grid. Used by the main toolbar."""
    try:
        from education_system.systems.university.interfaces.gui.academics.module_scheduling.drag_grid_dialog import DragDropTimetableDialog
        DragDropTimetableDialog(self.root, self.scheduler, gui=self)
    except Exception as e:
        messagebox.showerror("Error",
                             f"Failed to open drag-drop grid: {e}",
                             parent=self.root)


ModuleSchedulingGUI._show_drag_drop_grid = _show_drag_drop_grid
