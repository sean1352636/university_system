"""Data export GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from education_system.primary_school.modules.domain.admin.data_export.services.data_export_service import DataExportService
from education_system.primary_school.core.defaults import YEAR_GROUPS
import traceback


class DataExportFrame(tk.Frame):
    """Data export screen with export buttons and filter options."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = DataExportService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Data Export", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Filter options
        filter_frame = tk.LabelFrame(self, text="Filter Options", padx=10, pady=10)
        filter_frame.pack(fill="x", padx=15, pady=10)

        row1 = tk.Frame(filter_frame)
        row1.pack(fill="x", pady=3)

        tk.Label(row1, text="Year Group:", width=15, anchor="w").pack(side="left")
        self._year_filter = ttk.Combobox(row1, values=["All"] + YEAR_GROUPS,
                                          state="readonly", width=16)
        self._year_filter.set("All")
        self._year_filter.pack(side="left", padx=5)

        tk.Label(row1, text="Status:", width=10, anchor="w").pack(side="left", padx=(15, 0))
        self._status_filter = ttk.Combobox(row1, values=["All", "Active", "Left", "Transferred"],
                                            state="readonly", width=16)
        self._status_filter.set("All")
        self._status_filter.pack(side="left", padx=5)

        row2 = tk.Frame(filter_frame)
        row2.pack(fill="x", pady=3)

        tk.Label(row2, text="Date From:", width=15, anchor="w").pack(side="left")
        self._date_from = tk.Entry(row2, width=18)
        self._date_from.pack(side="left", padx=5)
        self._date_from.insert(0, "YYYY-MM-DD")

        tk.Label(row2, text="Date To:", width=10, anchor="w").pack(side="left", padx=(15, 0))
        self._date_to = tk.Entry(row2, width=18)
        self._date_to.pack(side="left", padx=5)
        self._date_to.insert(0, "YYYY-MM-DD")

        # Export buttons
        btn_frame = tk.LabelFrame(self, text="Export Actions", padx=10, pady=10)
        btn_frame.pack(fill="x", padx=15, pady=10)

        btn_style = {"width": 25, "height": 2}

        btn_row1 = tk.Frame(btn_frame)
        btn_row1.pack(fill="x", pady=5)

        tk.Button(btn_row1, text="Export Pupils CSV",
                  command=self._export_pupils, **btn_style).pack(side="left", padx=10)
        tk.Button(btn_row1, text="Export Attendance CSV",
                  command=self._export_attendance, **btn_style).pack(side="left", padx=10)
        tk.Button(btn_row1, text="Export Assessments CSV",
                  command=self._export_assessments, **btn_style).pack(side="left", padx=10)

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, anchor="w", bg="#ecf0f1",
                 padx=10).pack(fill="x", side="bottom")

    def refresh(self):
        self._status_var.set("Ready")

    def _get_filters(self):
        """Collect current filter values."""
        filters = {}
        yg = self._year_filter.get()
        if yg != "All":
            filters["year_group"] = yg
        status = self._status_filter.get()
        if status != "All":
            filters["status"] = status
        date_from = self._date_from.get().strip()
        if date_from and date_from != "YYYY-MM-DD":
            filters["date_from"] = date_from
        date_to = self._date_to.get().strip()
        if date_to and date_to != "YYYY-MM-DD":
            filters["date_to"] = date_to
        return filters

    def _export_pupils(self):
        filepath = filedialog.asksaveasfilename(
            parent=self,
            title="Export Pupils CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not filepath:
            return
        try:
            filters = self._get_filters()
            self._service.export_pupils(filepath, **filters)
            self._status_var.set(f"Pupils exported to {filepath}")
            messagebox.showinfo("Success", f"Pupils exported to:\n{filepath}", parent=self)
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to export pupils: {e}", parent=self)

    def _export_attendance(self):
        filepath = filedialog.asksaveasfilename(
            parent=self,
            title="Export Attendance CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not filepath:
            return
        try:
            filters = self._get_filters()
            self._service.export_attendance(filepath, **filters)
            self._status_var.set(f"Attendance exported to {filepath}")
            messagebox.showinfo("Success", f"Attendance exported to:\n{filepath}", parent=self)
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to export attendance: {e}", parent=self)

    def _export_assessments(self):
        filepath = filedialog.asksaveasfilename(
            parent=self,
            title="Export Assessments CSV",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not filepath:
            return
        try:
            filters = self._get_filters()
            self._service.export_assessments(filepath, **filters)
            self._status_var.set(f"Assessments exported to {filepath}")
            messagebox.showinfo("Success", f"Assessments exported to:\n{filepath}", parent=self)
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to export assessments: {e}", parent=self)
