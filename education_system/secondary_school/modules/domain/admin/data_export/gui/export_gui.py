"""Data Export GUI."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from education_system.secondary_school.modules.domain.admin.data_export.services.export_service import ExportService

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"

EXPORTS = [
    ("Students", "students"),
    ("Grades", "grades"),
    ("Attendance", "attendance"),
    ("Behaviour", "behaviour"),
    ("Timetable", "timetable"),
]


class ExportFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = ExportService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Data Export", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        content = tk.Frame(self, bg=MAIN_BG, padx=30, pady=20)
        content.pack(fill="both", expand=True)

        tk.Label(content, text="Export data to CSV files", font=("Helvetica", 11),
                 bg=MAIN_BG).pack(anchor="w", pady=(0, 15))

        for label, key in EXPORTS:
            row = tk.Frame(content, bg=MAIN_BG)
            row.pack(fill="x", pady=4)
            ttk.Button(row, text=f"Export {label}", width=20,
                       command=lambda k=key, l=label: self._do_export(k, l)).pack(side="left", padx=4)
            tk.Label(row, text=f"Export all {label.lower()} records to CSV",
                     bg=MAIN_BG, font=("Helvetica", 9), fg="#7f8c8d").pack(side="left", padx=10)

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        pass

    def _do_export(self, key, label):
        try:
            if key == "students":
                csv_data = self._svc.export_students()
            elif key == "grades":
                csv_data = self._svc.export_grades()
            elif key == "attendance":
                csv_data = self._svc.export_attendance()
            elif key == "behaviour":
                csv_data = self._svc.export_behaviour()
            elif key == "timetable":
                csv_data = self._svc.export_timetable()
            else:
                return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        if not csv_data:
            messagebox.showinfo("Info", f"No {label.lower()} data to export.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"{key}_export.csv",
            title=f"Save {label} Export")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as f:
                f.write(csv_data)
            self._status_var.set(f"Exported {label} to {path}")
            messagebox.showinfo("Success", f"{label} exported to:\n{path}")
        except OSError as e:
            messagebox.showerror("Error", f"Failed to save: {e}")
