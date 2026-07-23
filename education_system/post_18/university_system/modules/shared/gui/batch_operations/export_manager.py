"""Export operations manager for batch operations GUI."""
import os
import json
import csv
import datetime
import threading

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from education_system.post_18.university_system.modules.shared.gui.batch_operations.constants import _t, logger, sqlite3, DEFAULT_DB_PATH
from education_system.post_18.university_system.modules.shared.gui.batch_operations.progress_dialog import GUIProgressDialog


class ExportManager:
    """Manages export operations for BatchOperationsGUI."""

    def __init__(self, gui):
        self.gui = gui

    def export_students(self):
        """GUI version of export students"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.windows.export_students"))
        dialog.geometry("500x400")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 100))

        # Header
        header = ttk.Label(dialog, text=_t("batch_ops.labels.export_students_label"), font=("Arial", 14, "bold"))
        header.pack(pady=10)

        # Format selection
        format_frame = ttk.LabelFrame(dialog, text="Export Format", padding="10")
        format_frame.pack(fill=tk.X, padx=20, pady=10)

        format_var = tk.StringVar(value="csv")

        ttk.Radiobutton(format_frame, text="CSV", variable=format_var, value="csv").pack(anchor='w')
        ttk.Radiobutton(format_frame, text="Excel", variable=format_var, value="xlsx").pack(anchor='w')
        ttk.Radiobutton(format_frame, text="JSON", variable=format_var, value="json").pack(anchor='w')

        # Filter options
        filter_frame = ttk.LabelFrame(dialog, text="Filter Options", padding="10")
        filter_frame.pack(fill=tk.X, padx=20, pady=10)

        filter_var = tk.StringVar(value="all")

        ttk.Radiobutton(filter_frame, text="All students", variable=filter_var, value="all").pack(anchor='w')
        ttk.Radiobutton(filter_frame, text="Filter by course", variable=filter_var, value="course").pack(anchor='w')
        ttk.Radiobutton(filter_frame, text="Filter by date range", variable=filter_var, value="date").pack(anchor='w')

        # Course selection
        course_frame = ttk.Frame(filter_frame)
        course_frame.pack(fill=tk.X, pady=5)

        ttk.Label(course_frame, text=_t("batch_ops.labels.course")).pack(side=tk.LEFT)
        course_combo = ttk.Combobox(course_frame, values=["CS", "DS"], state="readonly", width=10)
        course_combo.set("CS")
        course_combo.pack(side=tk.LEFT, padx=(10, 0))

        # Date range
        date_frame = ttk.Frame(filter_frame)
        date_frame.pack(fill=tk.X, pady=5)

        ttk.Label(date_frame, text=_t("batch_ops.labels.from_date")).pack(side=tk.LEFT)
        start_date_entry = ttk.Entry(date_frame, width=12)
        start_date_entry.insert(0, "2024-01-01")
        start_date_entry.pack(side=tk.LEFT, padx=(5, 10))

        ttk.Label(date_frame, text=_t("batch_ops.labels.to_date")).pack(side=tk.LEFT)
        end_date_entry = ttk.Entry(date_frame, width=12)
        end_date_entry.insert(0, datetime.datetime.now().strftime("%Y-%m-%d"))
        end_date_entry.pack(side=tk.LEFT, padx=(5, 0))

        # Include modules option
        include_modules_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(filter_frame, text="Include module information",
                       variable=include_modules_var).pack(anchor='w', pady=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def execute_export():
            export_format = format_var.get()
            filter_type = filter_var.get()
            include_modules = include_modules_var.get()

            # Get output file
            if export_format == "csv":
                file_extension = ".csv"
                file_types = [("CSV files", "*.csv")]
            elif export_format == "xlsx":
                file_extension = ".xlsx"
                file_types = [("Excel files", "*.xlsx")]
            else:
                file_extension = ".json"
                file_types = [("JSON files", "*.json")]

            output_file = filedialog.asksaveasfilename(
                title="Save export as",
                defaultextension=file_extension,
                filetypes=file_types + [("All files", "*.*")]
            )

            if not output_file:
                return

            # Capture widget values before destroying the dialog
            course_value = course_combo.get()
            start_date_value = start_date_entry.get()
            end_date_value = end_date_entry.get()

            dialog.destroy()

            # Execute export
            def export_worker():
                try:
                    progress_dialog = GUIProgressDialog(self.gui.root, "Export", "Exporting student data")

                    # Build filter parameters
                    filter_params = {}
                    if filter_type == "course":
                        filter_params['course'] = course_value
                    elif filter_type == "date":
                        filter_params['start_date'] = start_date_value
                        filter_params['end_date'] = end_date_value

                    self.gui.report_mgr.export_students_to_file(
                        output_file, export_format, filter_params, include_modules,
                        progress_callback=progress_dialog.update_progress
                    )

                    progress_dialog.close()
                    messagebox.showinfo(_t("batch_ops.msg_titles.export_complete"), f"Students exported successfully to {output_file}")

                except Exception as e:
                    messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

            thread = threading.Thread(target=export_worker)
            thread.daemon = True
            thread.start()

        ttk.Button(button_frame, text="Export", command=execute_export).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("batch_ops.buttons.cancel"), command=dialog.destroy).pack(side=tk.LEFT)

    def export_statistics(self):
        """GUI version of export statistics"""
        output_file = filedialog.asksaveasfilename(
            title="Save statistics as",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if not output_file:
            return


        def export_worker():
            try:
                self.gui.update_status("Generating statistics...")

                stats = self.gui.generate_enrollment_statistics()

                with open(output_file, 'w') as f:
                    json.dump(stats, f, indent=2, default=str)

                self.gui.update_status("Ready")
                messagebox.showinfo(_t("batch_ops.msg_titles.export_complete"), f"Statistics exported to {output_file}")

            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        thread = threading.Thread(target=export_worker)
        thread.daemon = True
        thread.start()

    def generate_reports(self):
        """GUI version of generate reports"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.windows.generate_reports"))
        dialog.geometry("400x300")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 100))

        # Header
        header = ttk.Label(dialog, text="Generate Reports", font=("Arial", 14, "bold"))
        header.pack(pady=10)

        # Report type selection
        report_frame = ttk.LabelFrame(dialog, text="Report Type", padding="10")
        report_frame.pack(fill=tk.X, padx=20, pady=10)

        report_var = tk.StringVar(value="success_rates")

        ttk.Radiobutton(report_frame, text="Import success rates",
                       variable=report_var, value="success_rates").pack(anchor='w')
        ttk.Radiobutton(report_frame, text="Common error analysis",
                       variable=report_var, value="error_analysis").pack(anchor='w')
        ttk.Radiobutton(report_frame, text="Performance trends",
                       variable=report_var, value="performance").pack(anchor='w')
        ttk.Radiobutton(report_frame, text="Comprehensive report",
                       variable=report_var, value="comprehensive").pack(anchor='w')

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def generate_selected_report():
            report_type = report_var.get()
            dialog.destroy()

            def report_worker():
                try:
                    self.gui.update_status(f"Generating {report_type} report...")

                    if report_type == "success_rates":
                        self.gui.backend.generate_success_rate_report()
                    elif report_type == "error_analysis":
                        self.gui.backend.generate_error_analysis_report()
                    elif report_type == "performance":
                        self.gui.backend.generate_performance_report()
                    else:
                        self.gui.backend.generate_comprehensive_report()

                    self.gui.update_status("Ready")
                    messagebox.showinfo(_t("batch_ops.msg_titles.report_generated"), f"{report_type.replace('_', ' ').title()} report generated successfully")

                except Exception as e:
                    messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

            thread = threading.Thread(target=report_worker)
            thread.daemon = True
            thread.start()

        ttk.Button(button_frame, text=_t("batch_ops.buttons.generate"), command=generate_selected_report).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("batch_ops.buttons.cancel"), command=dialog.destroy).pack(side=tk.LEFT)
