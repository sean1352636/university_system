import logging
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from typing import Any, Optional, List, Dict
from education_system.systems.university.infrastructure.i18n import get_text as _

gui_logger = logging.getLogger(__name__)

# Lazy imports to avoid circular dependency
def _get_add_academic_year_dialog():
    from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_academic import AddAcademicYearDialog
    return AddAcademicYearDialog

def _get_add_semester_dialog():
    from education_system.systems.university.interfaces.gui.academics.academic_calendar.dialogs_academic import AddSemesterDialog
    return AddSemesterDialog

class AcademicViewMixin:
    def _show_academic_years(self):
        """Show academic years management"""
        self._clear_content_area()
        self.current_view = "academic_years"

        # Header
        header_frame = ttk.Frame(self.content_area)
        header_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(header_frame, text=_("academic_calendar.academic_years.title"), style='Header.TLabel').pack(side=tk.LEFT)

        ttk.Button(header_frame, text=_("academic_calendar.academic_years.add_year"),
                  command=self._add_academic_year).pack(side=tk.RIGHT, padx=5)

        # Academic years list
        years_frame = ttk.LabelFrame(self.content_area, text=_("academic_calendar.academic_years.list_title"), padding=10)
        years_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self._create_academic_years_list(years_frame)

    def _create_academic_years_list(self, parent):
        """Create academic years list"""
        try:
            if not self.calendar_manager:
                return

            # Get academic years
            years = self.calendar_manager.db_manager.execute_query(
                "SELECT * FROM academic_years ORDER BY start_date DESC"
            )

            if years:
                # Treeview
                years_tree = ttk.Treeview(parent, columns=('Start', 'End', 'Added'), show='tree headings')
                years_tree.pack(fill=tk.BOTH, expand=True)

                years_tree.heading('#0', text=_("academic_calendar.columns.academic_year"))
                years_tree.heading('Start', text=_("academic_calendar.columns.start_date"))
                years_tree.heading('End', text=_("academic_calendar.columns.end_date"))
                years_tree.heading('Added', text=_("academic_calendar.columns.date_added"))

                years_tree.column('#0', width=150)
                years_tree.column('Start', width=120)
                years_tree.column('End', width=120)
                years_tree.column('Added', width=150)

                # Add years
                for year in years:
                    added_date = year['date_added'][:10] if year['date_added'] else ''
                    years_tree.insert('', 'end', text=year['id'],
                                    values=(year['start_date'], year['end_date'], added_date))

                # Scrollbar
                scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=years_tree.yview)
                years_tree.configure(yscrollcommand=scrollbar.set)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            else:
                ttk.Label(parent, text=_("academic_calendar.academic_years.no_years_found")).pack()

        except Exception as e:
            gui_logger.error(f"Failed to load academic years: {e}")
            ttk.Label(parent, text=_("academic_calendar.messages.error_loading_academic_years").format(error=e)).pack()

    def _show_semesters(self):
        """Show semesters management"""
        self._clear_content_area()
        self.current_view = "semesters"

        # Header
        header_frame = ttk.Frame(self.content_area)
        header_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(header_frame, text=_("academic_calendar.semesters.title"), style='Header.TLabel').pack(side=tk.LEFT)

        ttk.Button(header_frame, text=_("academic_calendar.semesters.add_semester"),
                  command=self._add_semester).pack(side=tk.RIGHT, padx=5)

        # Semesters list
        semesters_frame = ttk.LabelFrame(self.content_area, text=_("academic_calendar.semesters.list_title"), padding=10)
        semesters_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self._create_semesters_list(semesters_frame)

    def _create_semesters_list(self, parent):
        """Create semesters list"""
        try:
            if not self.calendar_manager:
                return

            # Get semesters
            semesters = self.calendar_manager.db_manager.execute_query("""
                SELECT s.*, ay.id as year_id FROM semesters s
                JOIN academic_years ay ON s.academic_year_id = ay.id
                ORDER BY ay.start_date DESC, s.start_date
            """)

            if semesters:
                # Treeview
                sem_tree = ttk.Treeview(parent,
                                      columns=('Year', 'Start', 'End', 'Added'),
                                      show='tree headings')
                sem_tree.pack(fill=tk.BOTH, expand=True)

                sem_tree.heading('#0', text=_("academic_calendar.columns.semester_name"))
                sem_tree.heading('Year', text=_("academic_calendar.columns.academic_year"))
                sem_tree.heading('Start', text=_("academic_calendar.columns.start_date"))
                sem_tree.heading('End', text=_("academic_calendar.columns.end_date"))
                sem_tree.heading('Added', text=_("academic_calendar.columns.date_added"))

                sem_tree.column('#0', width=150)
                sem_tree.column('Year', width=120)
                sem_tree.column('Start', width=120)
                sem_tree.column('End', width=120)
                sem_tree.column('Added', width=150)

                # Add semesters
                for semester in semesters:
                    added_date = semester['date_added'][:10] if semester['date_added'] else ''
                    sem_tree.insert('', 'end', text=semester['name'],
                                  values=(semester['year_id'], semester['start_date'],
                                         semester['end_date'], added_date))

                # Scrollbar
                scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=sem_tree.yview)
                sem_tree.configure(yscrollcommand=scrollbar.set)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            else:
                ttk.Label(parent, text=_("academic_calendar.semesters.no_semesters_found")).pack()

        except Exception as e:
            gui_logger.error(f"Failed to load semesters: {e}")
            ttk.Label(parent, text=_("academic_calendar.messages.error_loading_semesters").format(error=e)).pack()

    def _add_academic_year(self):
        """Add academic year dialog"""
        _get_add_academic_year_dialog()(self.root, self.calendar_manager,
                            lambda: self._refresh_current_view())

    def _add_semester(self):
        """Add semester dialog"""
        _get_add_semester_dialog()(self.root, self.calendar_manager,
                        lambda: self._refresh_current_view())

