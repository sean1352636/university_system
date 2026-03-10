import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import json
import os
from datetime import datetime, timedelta

from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.utils.logging.gui.helpers import _t


class ExportImportMixin:
    """Mixin providing export/import functionality."""

    def export_logs_dialog(self):
        """Show export logs dialog"""
        export_window = tk.Toplevel(self.root)
        export_window.title(_t("log_management.dialogs.export.title"))
        export_window.geometry("500x400")

        ttk.Label(export_window, text=_t("log_management.dialogs.export.title"), font=("Arial", 14, "bold")).pack(pady=10)

        # Export options frame
        options_frame = ttk.LabelFrame(export_window, text=_t("log_management.export_options.title"))
        options_frame.pack(fill=tk.X, padx=10, pady=5)

        # Format selection
        format_frame = ttk.Frame(options_frame)
        format_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(format_frame, text=_t("log_management.export_options.format")).pack(side=tk.LEFT)
        format_var = tk.StringVar(value="json")
        format_combo = ttk.Combobox(format_frame, textvariable=format_var,
                                   values=["json", "csv", "excel"], state="readonly")
        format_combo.pack(side=tk.LEFT, padx=5)

        # Date range
        date_frame = ttk.Frame(options_frame)
        date_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(date_frame, text=_t("log_management.export_options.last")).pack(side=tk.LEFT)
        days_var = tk.StringVar(value="7")
        ttk.Entry(date_frame, textvariable=days_var, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Label(date_frame, text=_t("log_management.export_options.days")).pack(side=tk.LEFT)

        # Export function
        def perform_export():
            try:
                days = int(days_var.get())
                file_format = format_var.get()

                # Get export file path
                if file_format == "csv":
                    file_path = filedialog.asksaveasfilename(
                        defaultextension=".csv",
                        filetypes=[("CSV files", "*.csv")]
                    )
                elif file_format == "excel":
                    file_path = filedialog.asksaveasfilename(
                        defaultextension=".xlsx",
                        filetypes=[("Excel files", "*.xlsx")]
                    )
                else:
                    file_path = filedialog.asksaveasfilename(
                        defaultextension=".json",
                        filetypes=[("JSON files", "*.json")]
                    )

                if not file_path:
                    return

                # Get logs for export
                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)
                filters = {
                    'date_from': start_date.strftime('%Y-%m-%d'),
                    'date_to': end_date.strftime('%Y-%m-%d')
                }

                results = self.log_manager.db.search_logs(filters, limit=10000)

                if not results:
                    messagebox.showwarning(_t("log_management.export_options.no_data"), _t("log_management.export_options.no_logs_for_export"))
                    return

                # Export based on format
                if file_format == "csv":
                    import pandas as pd
                    df = pd.DataFrame(results)
                    df.to_csv(file_path, index=False)
                elif file_format == "excel":
                    import pandas as pd
                    df = pd.DataFrame(results)
                    df.to_excel(file_path, index=False)
                else:  # JSON
                    export_data = {
                        "export_info": {
                            "timestamp": datetime.now().isoformat(),
                            "filters": filters,
                            "record_count": len(results)
                        },
                        "logs": results
                    }
                    with open(file_path, 'w') as f:
                        json.dump(export_data, f, indent=2)

                messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.export_options.success", count=len(results), path=file_path))
                export_window.destroy()

            except Exception as e:
                messagebox.showerror(_t("log_management.messages.error"), _t("log_management.export_options.error", error=str(e)))

        ttk.Button(options_frame, text=_t("log_management.dialogs.export.export"), command=perform_export).pack(pady=10)

    def import_logs_dialog(self):
        """Show import logs dialog"""
        file_path = filedialog.askopenfilename(
            title=_t("log_management.import_dialog.select_file"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if not file_path:
            return

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            logs = data.get('logs', [])
            if not logs:
                messagebox.showwarning(_t("log_management.import_dialog.no_data"), _t("log_management.import_dialog.no_logs_in_file"))
                return

            if messagebox.askyesno(_t("log_management.import_dialog.confirm_title"), _t("log_management.import_dialog.confirm_message", count=len(logs))):
                imported_count = 0
                for log in logs:
                    try:
                        self.log_manager.db.insert_log(log)
                        imported_count += 1
                    except Exception as e:
                        print(f"Error importing log: {e}")

                messagebox.showinfo(_t("log_management.import_dialog.complete"), _t("log_management.import_dialog.success", count=imported_count, total=len(logs)))
                self.update_dashboard()

        except Exception as e:
            messagebox.showerror(_t("log_management.import_dialog.error"), _t("log_management.import_dialog.error_message", error=str(e)))

    def bulk_export_by_date(self, log_manager, auth):
        """Bulk export by date range"""
        export_window = tk.Toplevel(self.root)
        export_window.title(_t("log_management.bulk_export.title"))
        export_window.geometry("400x300")

        ttk.Label(export_window, text=_t("log_management.bulk_export.title_header"),
                 font=("Arial", 12, "bold")).pack(pady=10)

        # Date range inputs
        date_frame = ttk.Frame(export_window)
        date_frame.pack(pady=10)

        ttk.Label(date_frame, text=_t("log_management.bulk_export.from_date")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        from_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=from_var, width=15).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(date_frame, text=_t("log_management.bulk_export.to_date")).grid(row=1, column=0, padx=5, pady=5, sticky="w")
        to_var = tk.StringVar()
        ttk.Entry(date_frame, textvariable=to_var, width=15).grid(row=1, column=1, padx=5, pady=5)

        # Format selection
        format_frame = ttk.Frame(export_window)
        format_frame.pack(pady=10)

        ttk.Label(format_frame, text=_t("log_management.bulk_export.export_format")).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        format_var = tk.StringVar(value="json")
        format_combo = ttk.Combobox(format_frame, textvariable=format_var, values=["json", "csv", "excel"])
        format_combo.grid(row=0, column=1, padx=5, pady=5)

        def perform_bulk_export():
            try:
                filters = {}
                if from_var.get():
                    filters['date_from'] = from_var.get()
                if to_var.get():
                    filters['date_to'] = to_var.get()

                results = log_manager.db.search_logs(filters, limit=10000)

                if results:
                    # Get save location
                    filename = filedialog.asksaveasfilename(
                        defaultextension=f".{format_var.get()}",
                        filetypes=[(f"{format_var.get().upper()} files", f"*.{format_var.get()}"), ("All files", "*.*")]
                    )

                    if filename:
                        if format_var.get() == "csv":
                            import pandas as pd
                            df = pd.DataFrame(results)
                            df.to_csv(filename, index=False)
                        elif format_var.get() == "excel":
                            import pandas as pd
                            df = pd.DataFrame(results)
                            df.to_excel(filename, index=False)
                        else:  # JSON
                            with open(filename, 'w') as f:
                                json.dump({"results": results, "filters": filters}, f, indent=2)

                        messagebox.showinfo(_t("log_management.messages.success"), _t("log_management.bulk_export.success", count=len(results), path=filename))
                        export_window.destroy()
                else:
                    messagebox.showwarning(_t("log_management.bulk_export.no_data"), _t("log_management.bulk_export.no_logs_in_range"))

            except Exception as e:
                messagebox.showerror(_t("log_management.messages.error"), _t("log_management.bulk_export.error", error=str(e)))

        ttk.Button(export_window, text=_t("log_management.bulk_export.export"), command=perform_bulk_export).pack(pady=20)

    def custom_format_export(self, log_manager, auth):
        """Custom format export dialog"""
        format_window = tk.Toplevel(self.root)
        format_window.title(_t("log_management.custom_format_export.title"))
        format_window.geometry("600x500")

        ttk.Label(format_window, text=_t("log_management.custom_format_export.title"),
                 font=("Arial", 12, "bold")).pack(pady=10)

        # Template selection
        template_frame = ttk.LabelFrame(format_window, text=_t("log_management.custom_format_export.templates"))
        template_frame.pack(fill=tk.X, padx=10, pady=5)

        template_var = tk.StringVar(value="detailed_csv")
        templates = [
            ("Detailed CSV", "detailed_csv"),
            ("Summary Report", "summary_report"),
            ("Security Audit", "security_audit"),
            ("Custom XML", "custom_xml")
        ]

        for text, value in templates:
            ttk.Radiobutton(template_frame, text=text, variable=template_var, value=value).pack(anchor="w", padx=10, pady=2)

        # Custom fields selection
        fields_frame = ttk.LabelFrame(format_window, text="Include Fields")
        fields_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Create checkboxes for fields
        field_vars = {}
        fields = ["timestamp", "user_id", "username", "action", "module", "details", "status", "ip_address"]

        for i, field in enumerate(fields):
            var = tk.BooleanVar(value=True)
            field_vars[field] = var
            ttk.Checkbutton(fields_frame, text=field.replace("_", " ").title(), variable=var).grid(
                row=i//3, column=i%3, sticky="w", padx=10, pady=2)

        # Preview area
        preview_frame = ttk.LabelFrame(format_window, text="Format Preview")
        preview_frame.pack(fill=tk.X, padx=10, pady=5)

        preview_text = tk.Text(preview_frame, height=6, width=70)
        preview_text.pack(padx=5, pady=5)

        def update_preview():
            template = template_var.get()
            selected_fields = [field for field, var in field_vars.items() if var.get()]

            if template == "detailed_csv":
                preview_content = "CSV Format with columns:\n" + ", ".join(selected_fields)
            elif template == "summary_report":
                preview_content = "Summary Report Format:\n- Activity counts by user\n- Time period analysis\n- Status breakdown"
            elif template == "security_audit":
                preview_content = "Security Audit Format:\n- Failed login attempts\n- Admin actions\n- Unusual activity patterns"
            else:
                preview_content = "Custom XML Format:\n<logs>\n  <log>\n    " + "\n    ".join(f"<{field}></{field}>" for field in selected_fields) + "\n  </log>\n</logs>"

            preview_text.delete("1.0", tk.END)
            preview_text.insert("1.0", preview_content)

        # Update preview when template changes
        template_var.trace("w", lambda *args: update_preview())
        update_preview()

        def generate_custom_export():
            try:
                # Get date range
                days = tk.simpledialog.askinteger("Date Range", "Export last how many days?", initialvalue=7)
                if not days:
                    return

                end_date = datetime.now()
                start_date = end_date - timedelta(days=days)

                filters = {
                    'date_from': start_date.strftime('%Y-%m-%d'),
                    'date_to': end_date.strftime('%Y-%m-%d')
                }

                results = log_manager.db.search_logs(filters, limit=10000)

                if not results:
                    messagebox.showwarning("No Data", "No logs found for export")
                    return

                # Get save location
                filename = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
                )

                if filename:
                    selected_fields = [field for field, var in field_vars.items() if var.get()]

                    with open(filename, 'w') as f:
                        if template_var.get() == "custom_xml":
                            f.write("<logs>\n")
                            for log in results:
                                f.write("  <log>\n")
                                for field in selected_fields:
                                    value = log.get(field, '')
                                    f.write(f"    <{field}>{value}</{field}>\n")
                                f.write("  </log>\n")
                            f.write("</logs>\n")
                        else:
                            # Write as formatted text
                            for log in results:
                                for field in selected_fields:
                                    f.write(f"{field}: {log.get(field, '')}\n")
                                f.write("-" * 40 + "\n")

                    messagebox.showinfo("Success", f"Custom export saved to {filename}")
                    format_window.destroy()

            except Exception as e:
                messagebox.showerror("Error", f"Export failed: {str(e)}")

        ttk.Button(format_window, text=_t("log_management.custom_format.buttons.export"), command=generate_custom_export).pack(pady=10)

    def bulk_import_logs_gui(self):
        """GUI version of bulk log import"""
        import_window = tk.Toplevel(self.root)
        import_window.title(_t("log_management.dialogs.bulk_import"))
        import_window.geometry("500x400")

        ttk.Label(import_window, text=_t("log_management.bulk_import.title"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        # File selection frame
        file_frame = ttk.LabelFrame(import_window, text="File Selection")
        file_frame.pack(fill=tk.X, padx=10, pady=5)

        file_path_var = tk.StringVar()
        file_entry = ttk.Entry(file_frame, textvariable=file_path_var, width=50)
        file_entry.pack(side=tk.LEFT, padx=5, pady=10, fill=tk.X, expand=True)

        def browse_file():
            filename = filedialog.askopenfilename(
                title="Select log file to import",
                filetypes=[("JSON files", "*.json"), ("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if filename:
                file_path_var.set(filename)

        ttk.Button(file_frame, text=_t("log_management.buttons.browse"), command=browse_file).pack(side=tk.RIGHT, padx=5, pady=10)

        # Import options frame
        options_frame = ttk.LabelFrame(import_window, text="Import Options")
        options_frame.pack(fill=tk.X, padx=10, pady=5)

        validate_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Validate data before import",
                       variable=validate_var).pack(anchor="w", padx=10, pady=5)

        backup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Create backup before import",
                       variable=backup_var).pack(anchor="w", padx=10, pady=5)

        # Progress frame
        progress_frame = ttk.LabelFrame(import_window, text="Import Progress")
        progress_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        progress_text = scrolledtext.ScrolledText(progress_frame, height=10)
        progress_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        progress_bar.pack(fill=tk.X, padx=5, pady=5)

        def perform_import():
            file_path = file_path_var.get()
            if not file_path:
                messagebox.showerror("Error", "Please select a file to import")
                return

            if not os.path.exists(file_path):
                messagebox.showerror("Error", "File not found")
                return

            try:
                progress_text.insert(tk.END, f"Starting import from {file_path}\n")
                progress_text.see(tk.END)

                # Read file
                if file_path.endswith('.json'):
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                    logs = data.get('logs', []) if isinstance(data, dict) else data
                else:
                    messagebox.showerror("Error", "Only JSON files are currently supported")
                    return

                if not logs:
                    progress_text.insert(tk.END, "No logs found in file\n")
                    return

                progress_text.insert(tk.END, f"Found {len(logs)} logs to import\n")
                progress_bar['maximum'] = len(logs)

                imported_count = 0
                error_count = 0

                for i, log in enumerate(logs):
                    try:
                        if validate_var.get():
                            # Basic validation
                            required_fields = ['timestamp', 'user_id', 'username', 'action', 'module']
                            if not all(field in log for field in required_fields):
                                error_count += 1
                                continue

                        self.log_manager.db.insert_log(log)
                        imported_count += 1

                        if (i + 1) % 100 == 0:
                            progress_text.insert(tk.END, f"Imported {imported_count} logs...\n")
                            progress_text.see(tk.END)
                            progress_bar['value'] = i + 1
                            import_window.update()

                    except Exception as e:
                        error_count += 1
                        if error_count <= 10:  # Only show first 10 errors
                            progress_text.insert(tk.END, f"Error importing log {i+1}: {str(e)}\n")

                progress_bar['value'] = len(logs)
                progress_text.insert(tk.END, f"\nImport completed!\n")
                progress_text.insert(tk.END, f"Successfully imported: {imported_count}\n")
                progress_text.insert(tk.END, f"Errors: {error_count}\n")

                messagebox.showinfo("Import Complete",
                                   f"Successfully imported {imported_count}/{len(logs)} logs")

            except Exception as e:
                progress_text.insert(tk.END, f"Import failed: {str(e)}\n")
                messagebox.showerror("Import Error", f"Error importing logs: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(import_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text=_t("log_management.bulk_import.import"), command=perform_import).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("log_management.buttons.close"), command=import_window.destroy).pack(side=tk.RIGHT, padx=5)

    def bulk_cleanup_data_gui(self):
        """GUI version of bulk data cleanup"""
        cleanup_window = tk.Toplevel(self.root)
        cleanup_window.title(_t("log_management.dialogs.bulk_cleanup"))
        cleanup_window.geometry("500x400")

        ttk.Label(cleanup_window, text=_t("log_management.bulk_cleanup.title"),
                 font=("Arial", 14, "bold")).pack(pady=10)

        # Warning
        warning_frame = ttk.Frame(cleanup_window)
        warning_frame.pack(fill=tk.X, padx=10, pady=5)

        warning_text = "⚠️ WARNING: This will permanently delete data!\nThis action cannot be undone!"
        ttk.Label(warning_frame, text=warning_text, foreground="red",
                 font=("Arial", 10, "bold")).pack()

        # Cleanup options frame
        options_frame = ttk.LabelFrame(cleanup_window, text="Cleanup Options")
        options_frame.pack(fill=tk.X, padx=10, pady=10)

        # Date threshold
        date_frame = ttk.Frame(options_frame)
        date_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(date_frame, text=_t("log_management.bulk_cleanup.delete_older_than")).pack(side=tk.LEFT)
        days_var = tk.StringVar(value="90")
        days_spinbox = ttk.Spinbox(date_frame, from_=1, to=365, textvariable=days_var, width=10)
        days_spinbox.pack(side=tk.LEFT, padx=5)
        ttk.Label(date_frame, text=_t("log_management.bulk_cleanup.days")).pack(side=tk.LEFT)

        # Status filter
        status_frame = ttk.Frame(options_frame)
        status_frame.pack(fill=tk.X, padx=10, pady=5)

        status_var = tk.StringVar(value="all")
        ttk.Label(status_frame, text=_t("log_management.bulk_cleanup.delete_by_status")).pack(side=tk.LEFT)
        status_combo = ttk.Combobox(status_frame, textvariable=status_var,
                                   values=["all", "success", "failure"], width=15)
        status_combo.pack(side=tk.LEFT, padx=5)

        # Preview frame
        preview_frame = ttk.LabelFrame(cleanup_window, text="Cleanup Preview")
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        preview_text = scrolledtext.ScrolledText(preview_frame, height=8)
        preview_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        def preview_cleanup():
            try:
                days = int(days_var.get())
                cutoff_date = datetime.now() - timedelta(days=days)

                filters = {'date_to': cutoff_date.strftime('%Y-%m-%d')}
                if status_var.get() != "all":
                    filters['status'] = status_var.get()

                logs_to_delete = self.log_manager.db.search_logs(filters, limit=50000)

                preview_content = f"""Cleanup Preview
================

Date threshold: {cutoff_date.strftime('%Y-%m-%d')}
Status filter: {status_var.get()}

Logs that would be deleted: {len(logs_to_delete):,}

Sample logs to be deleted:
"""

                for log in logs_to_delete[:10]:  # Show first 10 as sample
                    timestamp = log.get('timestamp', '')[:19]
                    user = log.get('username', '')
                    action = log.get('action', '')
                    status = log.get('status', '')
                    preview_content += f"  {timestamp} - {user}: {action} ({status})\n"

                if len(logs_to_delete) > 10:
                    preview_content += f"  ... and {len(logs_to_delete) - 10:,} more logs\n"

                preview_text.delete("1.0", tk.END)
                preview_text.insert("1.0", preview_content)

            except Exception as e:
                preview_text.delete("1.0", tk.END)
                preview_text.insert("1.0", f"Error generating preview: {str(e)}")

        def perform_cleanup():
            try:
                days = int(days_var.get())
                cutoff_date = datetime.now() - timedelta(days=days)

                # Double confirmation
                if not messagebox.askyesno("Confirm Cleanup",
                                          f"Delete logs older than {days} days?\n"
                                          f"This action cannot be undone!"):
                    return

                if not messagebox.askyesno("Final Confirmation",
                                          "Are you absolutely sure?\n"
                                          "Type 'DELETE' in the next dialog to confirm."):
                    return

                confirmation = tk.simpledialog.askstring("Type DELETE",
                                                        "Type 'DELETE' to confirm:",
                                                        show='*')

                if confirmation != "DELETE":
                    messagebox.showinfo("Cancelled", "Cleanup cancelled - confirmation failed")
                    return

                # Perform cleanup (for demo, we'll just show what would happen)
                filters = {'date_to': cutoff_date.strftime('%Y-%m-%d')}
                if status_var.get() != "all":
                    filters['status'] = status_var.get()

                logs_to_delete = self.log_manager.db.search_logs(filters, limit=50000)

                preview_text.insert(tk.END, f"\n--- CLEANUP SIMULATION ---\n")
                preview_text.insert(tk.END, f"Would delete {len(logs_to_delete):,} logs\n")
                preview_text.insert(tk.END, "Actual deletion not performed for safety\n")

                messagebox.showinfo("Cleanup Complete",
                                   f"Cleanup simulation complete.\n"
                                   f"Would have deleted {len(logs_to_delete):,} logs.")

            except Exception as e:
                messagebox.showerror("Error", f"Cleanup failed: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(cleanup_window)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(button_frame, text="Preview Cleanup", command=preview_cleanup).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Perform Cleanup", command=perform_cleanup).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_t("log_management.buttons.close"), command=cleanup_window.destroy).pack(side=tk.RIGHT, padx=5)

    def schedule_export(log_manager, auth):
        """Schedule automatic exports"""
        schedule_window = tk.Toplevel(self.root)
        schedule_window.title(_t("log_management.dialogs.schedule_export"))
        schedule_window.geometry("500x450")

        ttk.Label(schedule_window, text=_t("log_management.schedule_export.title"),
                 font=("Arial", 12, "bold")).pack(pady=10)

        # Form frame
        form_frame = ttk.Frame(schedule_window, padding="20")
        form_frame.pack(fill=tk.BOTH, expand=True)

        # Frequency selection
        ttk.Label(form_frame, text=_t("log_management.schedule_export.frequency")).grid(row=0, column=0, sticky="w", pady=5)
        frequency_var = tk.StringVar(value="daily")
        frequency_combo = ttk.Combobox(form_frame, textvariable=frequency_var,
                                       values=["hourly", "daily", "weekly", "monthly"], state="readonly")
        frequency_combo.grid(row=0, column=1, sticky="ew", pady=5, padx=(10,0))

        # Time selection
        ttk.Label(form_frame, text=_t("log_management.schedule_export.time")).grid(row=1, column=0, sticky="w", pady=5)
        time_frame = ttk.Frame(form_frame)
        time_frame.grid(row=1, column=1, sticky="ew", pady=5, padx=(10,0))

        hour_var = tk.StringVar(value="00")
        minute_var = tk.StringVar(value="00")
        ttk.Spinbox(time_frame, from_=0, to=23, width=5, textvariable=hour_var, format="%02.0f").pack(side=tk.LEFT)
        ttk.Label(time_frame, text=":").pack(side=tk.LEFT, padx=2)
        ttk.Spinbox(time_frame, from_=0, to=59, width=5, textvariable=minute_var, format="%02.0f").pack(side=tk.LEFT)

        # Export format
        ttk.Label(form_frame, text="Export Format:").grid(row=2, column=0, sticky="w", pady=5)
        format_var = tk.StringVar(value="json")
        format_combo = ttk.Combobox(form_frame, textvariable=format_var,
                                    values=["json", "csv", "txt"], state="readonly")
        format_combo.grid(row=2, column=1, sticky="ew", pady=5, padx=(10,0))

        # Export directory
        ttk.Label(form_frame, text="Export Directory:").grid(row=3, column=0, sticky="w", pady=5)
        dir_var = tk.StringVar(value=os.path.join(os.getcwd(), "exports"))
        dir_frame = ttk.Frame(form_frame)
        dir_frame.grid(row=3, column=1, sticky="ew", pady=5, padx=(10,0))
        ttk.Entry(dir_frame, textvariable=dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(dir_frame, text=_t("log_management.buttons.browse"), command=lambda: dir_var.set(
            filedialog.askdirectory(initialdir=dir_var.get()))).pack(side=tk.LEFT, padx=(5,0))

        # Filters
        ttk.Label(form_frame, text="Level Filter:").grid(row=4, column=0, sticky="w", pady=5)
        level_var = tk.StringVar(value="all")
        level_combo = ttk.Combobox(form_frame, textvariable=level_var,
                                   values=["all", "info", "warning", "error", "critical"], state="readonly")
        level_combo.grid(row=4, column=1, sticky="ew", pady=5, padx=(10,0))

        # Enable/disable
        enabled_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(form_frame, text="Enable scheduled export",
                       variable=enabled_var).grid(row=5, column=0, columnspan=2, pady=15)

        form_frame.columnconfigure(1, weight=1)

        def save_schedule():
            try:
                schedule_config = {
                    'enabled': enabled_var.get(),
                    'frequency': frequency_var.get(),
                    'time': f"{hour_var.get()}:{minute_var.get()}",
                    'format': format_var.get(),
                    'directory': dir_var.get(),
                    'level_filter': level_var.get()
                }

                # Create export directory if it doesn't exist
                os.makedirs(dir_var.get(), exist_ok=True)

                # Save configuration
                config_file = os.path.join(os.getcwd(), "scheduled_export_config.json")
                with open(config_file, 'w') as f:
                    json.dump(schedule_config, f, indent=2)

                messagebox.showinfo("Success",
                    f"Export scheduled {frequency_var.get()} at {hour_var.get()}:{minute_var.get()}\n" +
                    f"Exports will be saved to: {dir_var.get()}")
                schedule_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to schedule export: {str(e)}")

        # Buttons
        button_frame = ttk.Frame(schedule_window)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Save Schedule", command=save_schedule).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=schedule_window.destroy).pack(side=tk.LEFT, padx=5)
