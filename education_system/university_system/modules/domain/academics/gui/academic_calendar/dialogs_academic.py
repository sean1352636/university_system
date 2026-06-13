import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict
from education_system.university_system.core.i18n import get_text as _
from education_system.university_system.modules.domain.academics.gui.academic_calendar.utils import safe_grab_set

gui_logger = logging.getLogger(__name__)

class AddAcademicYearDialog:
    """Dialog for adding academic years"""

    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.add_academic_year.title"))
        self.dialog.geometry("400x300")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)
        self._create_widgets()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text=_("academic_calendar.dialogs.add_academic_year.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Academic year
        ttk.Label(main_frame, text=_("academic_calendar.labels.academic_year_example")).pack(anchor=tk.W)
        self.year_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.year_var, width=40).pack(fill=tk.X, pady=(5, 15))

        # Start date
        ttk.Label(main_frame, text=_("academic_calendar.labels.start_date_format_required")).pack(anchor=tk.W)
        self.start_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.start_date_var, width=40).pack(fill=tk.X, pady=(5, 15))

        # End date
        ttk.Label(main_frame, text=_("academic_calendar.labels.end_date_format_required")).pack(anchor=tk.W)
        self.end_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.end_date_var, width=40).pack(fill=tk.X, pady=(5, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text=_("common.cancel"), command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text=_("common.add"), command=self._add_year).pack(side=tk.RIGHT)

    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

    def _add_year(self):
        """Add academic year"""
        try:
            year = self.year_var.get().strip()
            start_date = self.start_date_var.get().strip()
            end_date = self.end_date_var.get().strip()

            if not all([year, start_date, end_date]):
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.all_fields_required"))
                return

            success, message = self.calendar_manager.add_academic_year(year, start_date, end_date)

            if success:
                messagebox.showinfo(_("common.success"), message)
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror(_("common.error"), message)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_to_add_academic_year").format(error=e))


class AddSemesterDialog:
    """Dialog for adding semesters"""

    def __init__(self, parent, calendar_manager, callback=None):
        self.calendar_manager = calendar_manager
        self.callback = callback

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(_("academic_calendar.dialogs.add_semester.title"))
        self.dialog.geometry("400x350")
        self.dialog.transient(parent)
        safe_grab_set(self.dialog, parent)

        self._create_widgets()
        self._load_academic_years()
        self._center_dialog()

    def _create_widgets(self):
        """Create dialog widgets"""
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text=_("academic_calendar.dialogs.add_semester.header"),
                 font=('Arial', 14, 'bold')).pack(pady=(0, 20))

        # Academic year
        ttk.Label(main_frame, text=_("academic_calendar.labels.academic_year_required")).pack(anchor=tk.W)
        self.year_var = tk.StringVar()
        self.year_combo = ttk.Combobox(main_frame, textvariable=self.year_var, width=37)
        self.year_combo.pack(fill=tk.X, pady=(5, 15))

        # Semester name
        ttk.Label(main_frame, text=_("academic_calendar.labels.semester_name_required")).pack(anchor=tk.W)
        self.name_var = tk.StringVar()
        name_combo = ttk.Combobox(main_frame, textvariable=self.name_var, width=37,
                                values=["Fall", "Spring", "Summer", "Winter"])
        name_combo.pack(fill=tk.X, pady=(5, 15))

        # Start date
        ttk.Label(main_frame, text=_("academic_calendar.labels.start_date_format_required")).pack(anchor=tk.W)
        self.start_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.start_date_var, width=40).pack(fill=tk.X, pady=(5, 15))

        # End date
        ttk.Label(main_frame, text=_("academic_calendar.labels.end_date_format_required")).pack(anchor=tk.W)
        self.end_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.end_date_var, width=40).pack(fill=tk.X, pady=(5, 15))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text=_("common.cancel"), command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text=_("common.add"), command=self._add_semester).pack(side=tk.RIGHT)

    def _load_academic_years(self):
        """Load academic years into combo box"""
        try:
            years = self.calendar_manager.db_manager.execute_query(
                "SELECT id FROM academic_years ORDER BY start_date DESC"
            )
            year_list = [year['id'] for year in years]
            self.year_combo['values'] = year_list

            if year_list:
                self.year_var.set(year_list[0])

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_to_load_academic_years").format(error=e))

    def _center_dialog(self):
        """Center dialog on parent"""
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

    def _add_semester(self):
        """Add semester"""
        try:
            academic_year = self.year_var.get().strip()
            name = self.name_var.get().strip()
            start_date = self.start_date_var.get().strip()
            end_date = self.end_date_var.get().strip()

            if not all([academic_year, name, start_date, end_date]):
                messagebox.showerror(_("common.error"), _("academic_calendar.messages.all_fields_required"))
                return

            success, message = self.calendar_manager.add_semester(academic_year, name, start_date, end_date)

            if success:
                messagebox.showinfo(_("common.success"), message)
                if self.callback:
                    self.callback()
                self.dialog.destroy()
            else:
                messagebox.showerror(_("common.error"), message)

        except Exception as e:
            messagebox.showerror(_("common.error"), _("academic_calendar.messages.failed_to_add_semester").format(error=e))


