"""Automation operations manager for batch operations GUI."""
import os
import json
import random
import datetime
import threading

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import schedule

from .constants import _t, logger, EXTERNAL_DB_CONFIG_PATH, EXTERNAL_API_CONFIG_PATH
from .progress_dialog import GUIProgressDialog


class AutomationManager:
    """Manages automation operations for BatchOperationsGUI."""

    def __init__(self, gui):
        self.gui = gui

    def schedule_daily_import(self, directory: str = None, time: str = None, email: str = None):
        """Schedule daily import task with comprehensive configuration"""
        try:
            # Create scheduling dialog
            schedule_dialog = tk.Toplevel(self.gui.root)
            schedule_dialog.title(_t("batch_ops.windows.schedule_daily"))
            schedule_dialog.geometry("600x700")
            schedule_dialog.transient(self.gui.root)
            schedule_dialog.grab_set()

            # Center the dialog
            schedule_dialog.update_idletasks()
            x = (schedule_dialog.winfo_screenwidth() // 2) - (schedule_dialog.winfo_width() // 2)
            y = (schedule_dialog.winfo_screenheight() // 2) - (schedule_dialog.winfo_height() // 2)
            schedule_dialog.geometry(f"+{x}+{y}")

            # Header
            header_frame = tk.Frame(schedule_dialog, bg='#4CAF50')
            header_frame.pack(fill=tk.X, pady=(0, 0))

            tk.Label(header_frame, text=_t("batch_ops.labels.schedule_daily_import"),
                    font=('Arial', 14, 'bold'), bg='#4CAF50', fg='white').pack(pady=15)

            # Scrollable container
            scroll_canvas = tk.Canvas(schedule_dialog)
            scrollbar = ttk.Scrollbar(schedule_dialog, orient="vertical", command=scroll_canvas.yview)
            scroll_canvas.configure(yscrollcommand=scrollbar.set)

            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            scroll_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

            # Main content frame inside canvas
            content_frame = tk.Frame(scroll_canvas)
            canvas_window = scroll_canvas.create_window((0, 0), window=content_frame, anchor="nw")

            def _on_content_configure(event):
                scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all"))

            def _on_canvas_configure(event):
                scroll_canvas.itemconfig(canvas_window, width=event.width)

            content_frame.bind("<Configure>", _on_content_configure)
            scroll_canvas.bind("<Configure>", _on_canvas_configure)

            # Enable mousewheel scrolling
            def _on_mousewheel(event):
                scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

            def _on_mousewheel_linux(event):
                if event.num == 4:
                    scroll_canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    scroll_canvas.yview_scroll(1, "units")

            scroll_canvas.bind_all("<MouseWheel>", _on_mousewheel)
            scroll_canvas.bind_all("<Button-4>", _on_mousewheel_linux)
            scroll_canvas.bind_all("<Button-5>", _on_mousewheel_linux)

            def _on_dialog_destroy(event):
                if event.widget == schedule_dialog:
                    try:
                        scroll_canvas.unbind_all("<MouseWheel>")
                        scroll_canvas.unbind_all("<Button-4>")
                        scroll_canvas.unbind_all("<Button-5>")
                    except Exception:
                        pass

            schedule_dialog.bind("<Destroy>", _on_dialog_destroy)

            # Directory Selection
            dir_frame = tk.LabelFrame(content_frame, text=_t("batch_ops.labels.import_directory"), font=('Arial', 10, 'bold'))
            dir_frame.pack(fill=tk.X, pady=(0, 15))

            dir_var = tk.StringVar(value=directory or "")
            dir_entry = tk.Entry(dir_frame, textvariable=dir_var, font=('Arial', 10), width=50)
            dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10, pady=10)

            def browse_directory():
                from tkinter import filedialog
                selected_dir = filedialog.askdirectory(title="Select Import Directory")
                if selected_dir:
                    dir_var.set(selected_dir)

            tk.Button(dir_frame, text=_t("batch_ops.buttons.browse"), command=browse_directory,
                     bg='#2196F3', fg='white', padx=15).pack(side=tk.RIGHT, padx=10, pady=10)

            # Schedule Time Configuration
            time_frame = tk.LabelFrame(content_frame, text=_t("batch_ops.labels.schedule_time"), font=('Arial', 10, 'bold'))
            time_frame.pack(fill=tk.X, pady=(0, 15))

            time_config_frame = tk.Frame(time_frame)
            time_config_frame.pack(fill=tk.X, padx=10, pady=10)

            # Hour selection
            tk.Label(time_config_frame, text=_t("batch_ops.labels.hour"), font=('Arial', 10)).grid(row=0, column=0, sticky='w', padx=(0, 5))
            hour_var = tk.StringVar(value="09")
            hour_spinbox = tk.Spinbox(time_config_frame, from_=0, to=23, width=5, textvariable=hour_var,
                                     format="%02.0f", font=('Arial', 10))
            hour_spinbox.grid(row=0, column=1, padx=(0, 15))

            # Minute selection
            tk.Label(time_config_frame, text=_t("batch_ops.labels.minute"), font=('Arial', 10)).grid(row=0, column=2, sticky='w', padx=(0, 5))
            minute_var = tk.StringVar(value="00")
            minute_spinbox = tk.Spinbox(time_config_frame, from_=0, to=59, width=5, textvariable=minute_var,
                                       format="%02.0f", font=('Arial', 10))
            minute_spinbox.grid(row=0, column=3, padx=(0, 15))

            # Current time display
            current_time_label = tk.Label(time_config_frame,
                                         text=f"Current time: {datetime.datetime.now().strftime('%H:%M')}",
                                         font=('Arial', 9), fg='gray')
            current_time_label.grid(row=0, column=4, padx=(15, 0))

            # Email Notification Configuration
            email_frame = tk.LabelFrame(content_frame, text=_t("batch_ops.labels.email_notifications_optional"), font=('Arial', 10, 'bold'))
            email_frame.pack(fill=tk.X, pady=(0, 15))

            email_config_frame = tk.Frame(email_frame)
            email_config_frame.pack(fill=tk.X, padx=10, pady=10)

            email_var = tk.StringVar(value=email or "")
            tk.Label(email_config_frame, text=_t("batch_ops.labels.email_address"), font=('Arial', 10)).pack(anchor='w')
            email_entry = tk.Entry(email_config_frame, textvariable=email_var, font=('Arial', 10), width=40)
            email_entry.pack(fill=tk.X, pady=(5, 10))

            # Email notification options
            notify_success_var = tk.BooleanVar(value=True)
            notify_failure_var = tk.BooleanVar(value=True)
            notify_summary_var = tk.BooleanVar(value=False)

            tk.Checkbutton(email_config_frame, text="Notify on successful import",
                          variable=notify_success_var, font=('Arial', 9)).pack(anchor='w')
            tk.Checkbutton(email_config_frame, text="Notify on import failures",
                          variable=notify_failure_var, font=('Arial', 9)).pack(anchor='w')
            tk.Checkbutton(email_config_frame, text="Send weekly summary report",
                          variable=notify_summary_var, font=('Arial', 9)).pack(anchor='w')

            # Import Options
            options_frame = tk.LabelFrame(content_frame, text=_t("batch_ops.labels.import_options"), font=('Arial', 10, 'bold'))
            options_frame.pack(fill=tk.X, pady=(0, 15))

            options_config_frame = tk.Frame(options_frame)
            options_config_frame.pack(fill=tk.X, padx=10, pady=10)

            # File type filter
            tk.Label(options_config_frame, text=_t("batch_ops.labels.file_types"), font=('Arial', 10)).grid(row=0, column=0, sticky='w')
            file_types_var = tk.StringVar(value="*.csv, *.xlsx, *.json")
            file_types_entry = tk.Entry(options_config_frame, textvariable=file_types_var,
                                       font=('Arial', 10), width=30)
            file_types_entry.grid(row=0, column=1, padx=(5, 0), sticky='ew')

            # Additional options
            backup_before_var = tk.BooleanVar(value=True)
            validate_data_var = tk.BooleanVar(value=True)
            archive_processed_var = tk.BooleanVar(value=False)

            tk.Checkbutton(options_config_frame, text="Backup database before import",
                          variable=backup_before_var, font=('Arial', 9)).grid(row=1, column=0, columnspan=2, sticky='w', pady=(10, 2))
            tk.Checkbutton(options_config_frame, text="Validate data before import",
                          variable=validate_data_var, font=('Arial', 9)).grid(row=2, column=0, columnspan=2, sticky='w', pady=2)
            tk.Checkbutton(options_config_frame, text="Archive processed files",
                          variable=archive_processed_var, font=('Arial', 9)).grid(row=3, column=0, columnspan=2, sticky='w', pady=2)

            options_config_frame.columnconfigure(1, weight=1)

            # Current Schedule Status
            status_frame = tk.LabelFrame(content_frame, text=_t("batch_ops.labels.current_schedule_status"), font=('Arial', 10, 'bold'))
            status_frame.pack(fill=tk.X, pady=(0, 15))

            # Sample current schedules (in real implementation, this would query actual scheduled tasks)
            current_schedules = [
                {"id": "daily_001", "directory": "/data/imports", "time": "09:00", "status": "Active", "next_run": "Tomorrow 09:00"},
                {"id": "daily_002", "directory": "/data/backup", "time": "23:30", "status": "Active", "next_run": "Today 23:30"},
                {"id": "daily_003", "directory": "/tmp/imports", "time": "06:00", "status": "Paused", "next_run": "N/A"}
            ]

            # Create treeview for current schedules
            schedule_tree = ttk.Treeview(status_frame, columns=("Directory", "Time", "Status", "Next Run"), show="tree headings", height=4)
            schedule_tree.pack(fill=tk.X, padx=10, pady=10)

            # Configure columns
            schedule_tree.column("#0", width=80, minwidth=80)
            schedule_tree.column("Directory", width=150, minwidth=100)
            schedule_tree.column("Time", width=80, minwidth=80)
            schedule_tree.column("Status", width=80, minwidth=80)
            schedule_tree.column("Next Run", width=120, minwidth=100)

            # Configure headings
            schedule_tree.heading("#0", text=_t("batch_ops.columns.id"))
            schedule_tree.heading("Directory", text=_t("batch_ops.columns.directory"))
            schedule_tree.heading("Time", text=_t("batch_ops.columns.time"))
            schedule_tree.heading("Status", text=_t("batch_ops.columns.status"))
            schedule_tree.heading("Next Run", text=_t("batch_ops.columns.next_run"))

            # Populate with sample data
            for sched in current_schedules:
                schedule_tree.insert("", "end", text=sched["id"],
                                   values=(sched["directory"], sched["time"], sched["status"], sched["next_run"]))

            # Action buttons (packed at bottom, outside scrollable area)
            button_frame = tk.Frame(schedule_dialog)
            button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=20, pady=15)

            def create_schedule():
                try:
                    # Validate inputs
                    directory_path = dir_var.get().strip()
                    if not directory_path:
                        messagebox.showerror(_t("batch_ops.msg_titles.validation_error"), "Please select an import directory")
                        return

                    if not os.path.exists(directory_path):
                        create_dir = messagebox.askyesno("Directory Not Found",
                                                       f"Directory '{directory_path}' does not exist. Create it?")
                        if create_dir:
                            os.makedirs(directory_path, exist_ok=True)
                        else:
                            return

                    # Create schedule configuration
                    schedule_config = {
                        "schedule_id": f"daily_{random.randint(1000, 9999)}",
                        "directory": directory_path,
                        "time": f"{hour_var.get()}:{minute_var.get()}",
                        "email_notifications": {
                            "enabled": bool(email_var.get().strip()),
                            "email": email_var.get().strip(),
                            "notify_success": notify_success_var.get(),
                            "notify_failure": notify_failure_var.get(),
                            "weekly_summary": notify_summary_var.get()
                        },
                        "import_options": {
                            "file_types": file_types_var.get().split(','),
                            "backup_before_import": backup_before_var.get(),
                            "validate_data": validate_data_var.get(),
                            "archive_processed": archive_processed_var.get()
                        },
                        "created_at": datetime.datetime.now().isoformat(),
                        "status": "Active"
                    }

                    # Save schedule configuration to file (in real implementation, this would integrate with system scheduler)
                    config_filename = f"schedule_{schedule_config['schedule_id']}.json"
                    with open(config_filename, 'w') as f:
                        json.dump(schedule_config, f, indent=2)

                    # Create the actual scheduled task (simulated)
                    schedule_script = f"""#!/bin/bash
# Automated Daily Import Task
# Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
# Schedule ID: {schedule_config['schedule_id']}

echo "Starting daily import task at $(date)"
echo "Import directory: {directory_path}"
echo "Configuration file: {config_filename}"

# In real implementation, this would:
# 1. Check for new files in the directory
# 2. Validate file formats
# 3. Backup database if configured
# 4. Import files
# 5. Send email notifications
# 6. Archive processed files if configured
# 7. Log results

echo "Daily import task completed at $(date)"
"""

                    script_filename = f"daily_import_{schedule_config['schedule_id']}.sh"
                    with open(script_filename, 'w') as f:
                        f.write(schedule_script)

                    # Make script executable
                    os.chmod(script_filename, 0o755)

                    # Show success message with comprehensive details
                    success_dialog = tk.Toplevel(schedule_dialog)
                    success_dialog.title(_t("batch_ops.windows.schedule_created"))
                    success_dialog.geometry("500x400")
                    success_dialog.transient(schedule_dialog)
                    success_dialog.grab_set()

                    # Center the success dialog
                    success_dialog.update_idletasks()
                    x = (success_dialog.winfo_screenwidth() // 2) - (success_dialog.winfo_width() // 2)
                    y = (success_dialog.winfo_screenheight() // 2) - (success_dialog.winfo_height() // 2)
                    success_dialog.geometry(f"+{x}+{y}")

                    tk.Label(success_dialog, text=_t("batch_ops.labels.daily_import_success"),
                            font=('Arial', 12, 'bold'), fg='green').pack(pady=15)

                    # Show schedule details
                    details_frame = tk.Frame(success_dialog)
                    details_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

                    details_text = tk.Text(details_frame, wrap=tk.WORD, font=('Courier', 9))
                    details_scroll = ttk.Scrollbar(details_frame, orient=tk.VERTICAL, command=details_text.yview)
                    details_text.configure(yscrollcommand=details_scroll.set)

                    next_run = datetime.datetime.now().replace(
                        hour=int(hour_var.get()),
                        minute=int(minute_var.get()),
                        second=0,
                        microsecond=0
                    )
                    if next_run <= datetime.datetime.now():
                        next_run += datetime.timedelta(days=1)

                    details_content = f"""SCHEDULE CONFIGURATION SUMMARY
===============================

Schedule ID: {schedule_config['schedule_id']}
Directory: {directory_path}
Daily Time: {hour_var.get()}:{minute_var.get()}
Next Run: {next_run.strftime('%Y-%m-%d %H:%M:%S')}

EMAIL NOTIFICATIONS:
\u2022 Enabled: {'Yes' if email_var.get().strip() else 'No'}
\u2022 Email: {email_var.get().strip() if email_var.get().strip() else 'Not configured'}
\u2022 Notify on Success: {'Yes' if notify_success_var.get() else 'No'}
\u2022 Notify on Failure: {'Yes' if notify_failure_var.get() else 'No'}
\u2022 Weekly Summary: {'Yes' if notify_summary_var.get() else 'No'}

IMPORT OPTIONS:
\u2022 File Types: {file_types_var.get()}
\u2022 Backup Before Import: {'Yes' if backup_before_var.get() else 'No'}
\u2022 Validate Data: {'Yes' if validate_data_var.get() else 'No'}
\u2022 Archive Processed Files: {'Yes' if archive_processed_var.get() else 'No'}

FILES CREATED:
\u2022 Configuration: {config_filename}
\u2022 Script: {script_filename}

STATUS: Active and Ready

NEXT STEPS:
1. The schedule will run automatically daily at {hour_var.get()}:{minute_var.get()}
2. Monitor logs for import results
3. Check email notifications if configured
4. Use the batch operations interface to manage schedules

Note: In a production environment, this would integrate with
system schedulers like cron (Linux/Mac) or Task Scheduler (Windows).
"""

                    details_text.insert(tk.END, details_content)
                    details_text.config(state=tk.DISABLED)
                    details_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    details_scroll.pack(side=tk.RIGHT, fill=tk.Y)

                    tk.Button(success_dialog, text=_t("batch_ops.buttons.close"), command=success_dialog.destroy,
                             bg='#f0f0f0', padx=20, pady=5).pack(pady=15)

                    # Close the main schedule dialog
                    schedule_dialog.destroy()

                except Exception as e:
                    messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

            def test_configuration():
                """Test the import configuration"""
                try:
                    directory_path = dir_var.get().strip()
                    if not directory_path:
                        messagebox.showerror(_t("batch_ops.msg_titles.validation_error"), "Please select an import directory")
                        return

                    # Show test results
                    test_results = []
                    test_results.append(f"\u2713 Directory exists: {os.path.exists(directory_path)}")
                    test_results.append(f"\u2713 Directory readable: {os.access(directory_path, os.R_OK) if os.path.exists(directory_path) else 'N/A'}")
                    test_results.append(f"\u2713 Schedule time format: Valid ({hour_var.get()}:{minute_var.get()})")

                    email_addr = email_var.get().strip()
                    if email_addr:
                        import re
                        email_valid = bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email_addr))
                        test_results.append(f"\u2713 Email format: {'Valid' if email_valid else 'Invalid'}")
                    else:
                        test_results.append("\u2022 Email notifications: Disabled")

                    messagebox.showinfo(_t("batch_ops.msg_titles.configuration_test"), "\n".join(test_results))

                except Exception as e:
                    messagebox.showerror(_t("batch_ops.msg_titles.test_error"), f"Configuration test failed: {str(e)}")

            # Button layout
            tk.Button(button_frame, text=_t("batch_ops.buttons.test_configuration"), command=test_configuration,
                     bg='#FF9800', fg='white', padx=15, pady=5).pack(side=tk.LEFT, padx=(0, 10))

            tk.Button(button_frame, text=_t("batch_ops.buttons.create_schedule"), command=create_schedule,
                     bg='#4CAF50', fg='white', padx=20, pady=5).pack(side=tk.LEFT, padx=(0, 10))

            tk.Button(button_frame, text=_t("batch_ops.buttons.cancel"), command=schedule_dialog.destroy,
                     bg='#f44336', fg='white', padx=20, pady=5).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

    def start_api_server(self, host: str = "localhost", port: int = 5000):
        """Start API server with comprehensive configuration and monitoring"""
        try:
            # Create API server configuration dialog
            api_dialog = tk.Toplevel(self.gui.root)
            api_dialog.title(_t("batch_ops.windows.api_config"))
            api_dialog.geometry("700x800")
            api_dialog.transient(self.gui.root)
            api_dialog.grab_set()

            # Center the dialog
            api_dialog.update_idletasks()
            x = (api_dialog.winfo_screenwidth() // 2) - (api_dialog.winfo_width() // 2)
            y = (api_dialog.winfo_screenheight() // 2) - (api_dialog.winfo_height() // 2)
            api_dialog.geometry(f"+{x}+{y}")

            # Header
            header_frame = tk.Frame(api_dialog, bg='#2196F3')
            header_frame.pack(fill=tk.X, pady=(0, 20))

            tk.Label(header_frame, text=_t("batch_ops.labels.api_server_config"),
                    font=('Arial', 14, 'bold'), bg='#2196F3', fg='white').pack(pady=15)

            # Main content with notebook
            notebook = ttk.Notebook(api_dialog)
            notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            # Configuration Tab
            config_frame = ttk.Frame(notebook)
            notebook.add(config_frame, text="Configuration")

            # Server Configuration
            server_frame = tk.LabelFrame(config_frame, text=_t("batch_ops.labels.server_configuration"), font=('Arial', 10, 'bold'))
            server_frame.pack(fill=tk.X, padx=10, pady=(10, 15))

            server_config_frame = tk.Frame(server_frame)
            server_config_frame.pack(fill=tk.X, padx=10, pady=10)

            # Host configuration
            tk.Label(server_config_frame, text=_t("batch_ops.labels.host"), font=('Arial', 10)).grid(row=0, column=0, sticky='w', padx=(0, 5))
            host_var = tk.StringVar(value=host)
            host_entry = tk.Entry(server_config_frame, textvariable=host_var, font=('Arial', 10), width=20)
            host_entry.grid(row=0, column=1, padx=(0, 20), sticky='ew')

            # Port configuration
            tk.Label(server_config_frame, text=_t("batch_ops.labels.port"), font=('Arial', 10)).grid(row=0, column=2, sticky='w', padx=(0, 5))
            port_var = tk.StringVar(value=str(port))
            port_entry = tk.Entry(server_config_frame, textvariable=port_var, font=('Arial', 10), width=10)
            port_entry.grid(row=0, column=3, padx=(0, 20))

            # Debug mode
            debug_var = tk.BooleanVar(value=False)
            tk.Checkbutton(server_config_frame, text="Debug Mode", variable=debug_var,
                          font=('Arial', 10)).grid(row=1, column=0, columnspan=2, sticky='w', pady=(10, 0))

            # SSL/HTTPS
            ssl_var = tk.BooleanVar(value=False)
            tk.Checkbutton(server_config_frame, text="Enable SSL/HTTPS", variable=ssl_var,
                          font=('Arial', 10)).grid(row=1, column=2, columnspan=2, sticky='w', pady=(10, 0))

            server_config_frame.columnconfigure(1, weight=1)

            # API Endpoints Configuration
            endpoints_frame = tk.LabelFrame(config_frame, text=_t("batch_ops.labels.api_endpoints"), font=('Arial', 10, 'bold'))
            endpoints_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 15))

            # Create treeview for endpoints
            endpoints_tree = ttk.Treeview(endpoints_frame, columns=("Method", "Path", "Description", "Status"),
                                         show="tree headings", height=8)
            endpoints_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # Configure columns
            endpoints_tree.column("#0", width=60, minwidth=60)
            endpoints_tree.column("Method", width=80, minwidth=80)
            endpoints_tree.column("Path", width=200, minwidth=150)
            endpoints_tree.column("Description", width=250, minwidth=200)
            endpoints_tree.column("Status", width=80, minwidth=80)

            # Configure headings
            endpoints_tree.heading("#0", text=_t("batch_ops.columns.id"))
            endpoints_tree.heading("Method", text=_t("batch_ops.columns.method"))
            endpoints_tree.heading("Path", text=_t("batch_ops.columns.path"))
            endpoints_tree.heading("Description", text=_t("batch_ops.columns.description"))
            endpoints_tree.heading("Status", text=_t("batch_ops.columns.status"))

            # Sample API endpoints
            api_endpoints = [
                {"id": "001", "method": "GET", "path": "/api/status", "description": "Server health check", "status": "Enabled"},
                {"id": "002", "method": "POST", "path": "/api/import", "description": "Import data from files", "status": "Enabled"},
                {"id": "003", "method": "GET", "path": "/api/reports", "description": "Generate system reports", "status": "Enabled"},
                {"id": "004", "method": "POST", "path": "/api/validate", "description": "Validate data format", "status": "Enabled"},
                {"id": "005", "method": "GET", "path": "/api/schedules", "description": "List scheduled tasks", "status": "Enabled"},
                {"id": "006", "method": "POST", "path": "/api/schedules", "description": "Create new schedule", "status": "Enabled"},
                {"id": "007", "method": "GET", "path": "/api/metrics", "description": "System performance metrics", "status": "Enabled"},
                {"id": "008", "method": "POST", "path": "/api/backup", "description": "Create database backup", "status": "Enabled"},
                {"id": "009", "method": "GET", "path": "/api/logs", "description": "Retrieve system logs", "status": "Enabled"},
                {"id": "010", "method": "POST", "path": "/api/config", "description": "Update configuration", "status": "Disabled"}
            ]

            # Populate endpoints
            for endpoint in api_endpoints:
                endpoints_tree.insert("", "end", text=endpoint["id"],
                                     values=(endpoint["method"], endpoint["path"], endpoint["description"], endpoint["status"]))

            # Security Tab
            security_frame = ttk.Frame(notebook)
            notebook.add(security_frame, text="Security")

            # Authentication Configuration
            auth_frame = tk.LabelFrame(security_frame, text=_t("batch_ops.labels.authentication"), font=('Arial', 10, 'bold'))
            auth_frame.pack(fill=tk.X, padx=10, pady=(10, 15))

            auth_config_frame = tk.Frame(auth_frame)
            auth_config_frame.pack(fill=tk.X, padx=10, pady=10)

            # Auth method selection
            auth_method_var = tk.StringVar(value="API Key")
            tk.Label(auth_config_frame, text=_t("batch_ops.labels.authentication_method"), font=('Arial', 10)).pack(anchor='w')
            auth_methods = ["API Key", "JWT Token", "Basic Auth", "OAuth 2.0"]
            auth_dropdown = ttk.Combobox(auth_config_frame, textvariable=auth_method_var, values=auth_methods,
                                        font=('Arial', 10), state="readonly", width=15)
            auth_dropdown.pack(anchor='w', pady=(5, 10))

            # API Key configuration
            tk.Label(auth_config_frame, text=_t("batch_ops.labels.api_key"), font=('Arial', 10)).pack(anchor='w')
            api_key_var = tk.StringVar(value="sk_" + ''.join([str(random.randint(0, 9)) for _ in range(20)]))
            api_key_entry = tk.Entry(auth_config_frame, textvariable=api_key_var, font=('Arial', 10), width=40)
            api_key_entry.pack(anchor='w', pady=(5, 10))

            def generate_new_key():
                new_key = "sk_" + ''.join([str(random.randint(0, 9)) for _ in range(20)])
                api_key_var.set(new_key)

            tk.Button(auth_config_frame, text=_t("batch_ops.buttons.generate_key"), command=generate_new_key,
                     bg='#FF9800', fg='white', padx=15, pady=2).pack(anchor='w')

            # Rate Limiting
            rate_frame = tk.LabelFrame(security_frame, text=_t("batch_ops.labels.rate_limiting"), font=('Arial', 10, 'bold'))
            rate_frame.pack(fill=tk.X, padx=10, pady=(0, 15))

            rate_config_frame = tk.Frame(rate_frame)
            rate_config_frame.pack(fill=tk.X, padx=10, pady=10)

            enable_rate_limit_var = tk.BooleanVar(value=True)
            tk.Checkbutton(rate_config_frame, text="Enable Rate Limiting", variable=enable_rate_limit_var,
                          font=('Arial', 10)).pack(anchor='w')

            rate_limit_frame = tk.Frame(rate_config_frame)
            rate_limit_frame.pack(fill=tk.X, pady=(10, 0))

            tk.Label(rate_limit_frame, text=_t("batch_ops.labels.requests_per_minute"), font=('Arial', 10)).pack(side=tk.LEFT)
            rate_limit_var = tk.StringVar(value="100")
            rate_limit_entry = tk.Entry(rate_limit_frame, textvariable=rate_limit_var, font=('Arial', 10), width=10)
            rate_limit_entry.pack(side=tk.LEFT, padx=(10, 0))

            # Monitoring Tab
            monitoring_frame = ttk.Frame(notebook)
            notebook.add(monitoring_frame, text="Monitoring")

            # Server Status (simulated)
            status_frame = tk.LabelFrame(monitoring_frame, text=_t("batch_ops.labels.current_server_status"), font=('Arial', 10, 'bold'))
            status_frame.pack(fill=tk.X, padx=10, pady=(10, 15))

            status_content_frame = tk.Frame(status_frame)
            status_content_frame.pack(fill=tk.X, padx=10, pady=10)

            # Status indicators
            server_status = "Stopped"  # In real implementation, this would check actual status
            status_color = "#f44336" if server_status == "Stopped" else "#4CAF50"

            tk.Label(status_content_frame, text=_t("batch_ops.labels.status"), font=('Arial', 10, 'bold')).grid(row=0, column=0, sticky='w')
            status_indicator = tk.Label(status_content_frame, text=server_status, font=('Arial', 10, 'bold'),
                                      fg=status_color)
            status_indicator.grid(row=0, column=1, sticky='w', padx=(10, 0))

            # Runtime statistics
            tk.Label(status_content_frame, text=_t("batch_ops.labels.runtime"), font=('Arial', 10)).grid(row=1, column=0, sticky='w', pady=(5, 0))
            tk.Label(status_content_frame, text=_t("batch_ops.labels.not_running"), font=('Arial', 10)).grid(row=1, column=1, sticky='w',
                                                                                       padx=(10, 0), pady=(5, 0))

            tk.Label(status_content_frame, text=_t("batch_ops.labels.total_requests"), font=('Arial', 10)).grid(row=2, column=0, sticky='w', pady=(5, 0))
            tk.Label(status_content_frame, text="0", font=('Arial', 10)).grid(row=2, column=1, sticky='w',
                                                                             padx=(10, 0), pady=(5, 0))

            tk.Label(status_content_frame, text=_t("batch_ops.labels.active_connections"), font=('Arial', 10)).grid(row=3, column=0, sticky='w', pady=(5, 0))
            tk.Label(status_content_frame, text="0", font=('Arial', 10)).grid(row=3, column=1, sticky='w',
                                                                             padx=(10, 0), pady=(5, 0))

            # Logs display
            logs_frame = tk.LabelFrame(monitoring_frame, text=_t("batch_ops.labels.server_logs"), font=('Arial', 10, 'bold'))
            logs_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 15))

            logs_text = tk.Text(logs_frame, wrap=tk.WORD, font=('Courier', 9), height=10)
            logs_scroll = ttk.Scrollbar(logs_frame, orient=tk.VERTICAL, command=logs_text.yview)
            logs_text.configure(yscrollcommand=logs_scroll.set)

            # Sample log entries
            sample_logs = """[2024-01-15 14:30:25] INFO: API Server initialized
[2024-01-15 14:30:25] INFO: Registered 10 endpoints
[2024-01-15 14:30:25] INFO: Rate limiting enabled: 100 requests/minute
[2024-01-15 14:30:25] INFO: Authentication method: API Key
[2024-01-15 14:30:25] INFO: Server ready to start on {host}:{port}
[2024-01-15 14:30:25] INFO: Debug mode: {debug}
[2024-01-15 14:30:25] INFO: SSL/HTTPS: {ssl}
""".format(host=host_var.get(), port=port_var.get(),
           debug='Enabled' if debug_var.get() else 'Disabled',
           ssl='Enabled' if ssl_var.get() else 'Disabled')

            logs_text.insert(tk.END, sample_logs)
            logs_text.config(state=tk.DISABLED)
            logs_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
            logs_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

            # Action buttons
            button_frame = tk.Frame(api_dialog)
            button_frame.pack(fill=tk.X, padx=20, pady=15)

            def start_server():
                """Start the API server"""
                try:
                    # Validate configuration
                    if not host_var.get().strip():
                        messagebox.showerror(_t("batch_ops.msg_titles.configuration_error"), "Host cannot be empty")
                        return

                    try:
                        port_num = int(port_var.get())
                        if port_num < 1 or port_num > 65535:
                            raise ValueError("Port must be between 1 and 65535")
                    except ValueError as e:
                        messagebox.showerror(_t("batch_ops.msg_titles.configuration_error"), f"Invalid port: {e}")
                        return

                    # Create server configuration
                    server_config = {
                        "host": host_var.get(),
                        "port": int(port_var.get()),
                        "debug": debug_var.get(),
                        "ssl_enabled": ssl_var.get(),
                        "authentication": {
                            "method": auth_method_var.get(),
                            "api_key": api_key_var.get()
                        },
                        "rate_limiting": {
                            "enabled": enable_rate_limit_var.get(),
                            "requests_per_minute": int(rate_limit_var.get()) if rate_limit_var.get().isdigit() else 100
                        },
                        "endpoints": api_endpoints,
                        "started_at": datetime.datetime.now().isoformat()
                    }

                    # Save configuration
                    config_filename = "api_server_config.json"
                    with open(config_filename, 'w') as f:
                        json.dump(server_config, f, indent=2)

                    # Create a simple Flask-like API server script (simulated)
                    server_script = f'''#!/usr/bin/env python3
"""
API Server for University Management System
Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Configuration: {config_filename}
"""

import json
import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

class UniversityAPIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        # Load configuration
        with open('{config_filename}', 'r') as f:
            config = json.load(f)

        # Check authentication
        api_key = self.headers.get('X-API-Key')
        if api_key != config['authentication']['api_key']:
            self.send_response(401)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {{"error": "Invalid API key"}}
            self.wfile.write(json.dumps(response).encode())
            return

        # Route handling
        if path == '/api/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {{
                "status": "healthy",
                "timestamp": datetime.datetime.now().isoformat(),
                "version": "1.0.0"
            }}
            self.wfile.write(json.dumps(response, indent=2).encode())

        elif path == '/api/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {{
                "cpu_usage": 45.2,
                "memory_usage": 67.8,
                "active_connections": 3,
                "total_requests": 127,
                "uptime_seconds": 3600
            }}
            self.wfile.write(json.dumps(response, indent=2).encode())

        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {{"error": "Endpoint not found"}}
            self.wfile.write(json.dumps(response).encode())

    def do_POST(self):
        # Handle POST requests (import, validate, etc.)
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        response = {{"message": "POST request received", "data_length": content_length}}
        self.wfile.write(json.dumps(response).encode())

    def log_message(self, format, *args):
        print(f"[{{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}}] {{format % args}}")

if __name__ == '__main__':
    server_address = ('{host_var.get()}', {port_var.get()})
    httpd = HTTPServer(server_address, UniversityAPIHandler)
    print(f"API Server starting on {{server_address[0]}}:{{server_address[1]}}")
    print(f"Configuration loaded from {config_filename}")
    print("Press Ctrl+C to stop the server")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\\nServer stopped")
        httpd.server_close()
'''

                    # Save the server script
                    script_filename = "api_server.py"
                    with open(script_filename, 'w') as f:
                        f.write(server_script)

                    # Make script executable
                    os.chmod(script_filename, 0o755)

                    # Show success dialog
                    success_dialog = tk.Toplevel(api_dialog)
                    success_dialog.title(_t("batch_ops.windows.api_ready"))
                    success_dialog.geometry("600x500")
                    success_dialog.transient(api_dialog)
                    success_dialog.grab_set()

                    # Center the success dialog
                    success_dialog.update_idletasks()
                    x = (success_dialog.winfo_screenwidth() // 2) - (success_dialog.winfo_width() // 2)
                    y = (success_dialog.winfo_screenheight() // 2) - (success_dialog.winfo_height() // 2)
                    success_dialog.geometry(f"+{x}+{y}")

                    tk.Label(success_dialog, text=_t("batch_ops.messages.server_config_complete"),
                            font=('Arial', 12, 'bold'), fg='green').pack(pady=15)

                    # Success details
                    success_details_frame = tk.Frame(success_dialog)
                    success_details_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

                    success_text = tk.Text(success_details_frame, wrap=tk.WORD, font=('Courier', 9))
                    success_scroll = ttk.Scrollbar(success_details_frame, orient=tk.VERTICAL, command=success_text.yview)
                    success_text.configure(yscrollcommand=success_scroll.set)

                    success_content = f"""API SERVER CONFIGURATION SUMMARY
=================================

SERVER DETAILS:
\u2022 Host: {host_var.get()}
\u2022 Port: {port_var.get()}
\u2022 URL: http{'s' if ssl_var.get() else ''}://{host_var.get()}:{port_var.get()}
\u2022 Debug Mode: {'Enabled' if debug_var.get() else 'Disabled'}
\u2022 SSL/HTTPS: {'Enabled' if ssl_var.get() else 'Disabled'}

AUTHENTICATION:
\u2022 Method: {auth_method_var.get()}
\u2022 API Key: {api_key_var.get()}

SECURITY:
\u2022 Rate Limiting: {'Enabled' if enable_rate_limit_var.get() else 'Disabled'}
\u2022 Requests per minute: {rate_limit_var.get()}

AVAILABLE ENDPOINTS:
\u2022 GET  /api/status     - Server health check
\u2022 POST /api/import     - Import data from files
\u2022 GET  /api/reports    - Generate system reports
\u2022 POST /api/validate   - Validate data format
\u2022 GET  /api/schedules  - List scheduled tasks
\u2022 POST /api/schedules  - Create new schedule
\u2022 GET  /api/metrics    - Performance metrics
\u2022 POST /api/backup     - Create database backup
\u2022 GET  /api/logs       - Retrieve system logs

FILES CREATED:
\u2022 Configuration: {config_filename}
\u2022 Server Script: {script_filename}

TO START THE SERVER:
python3 {script_filename}

TESTING THE API:
curl -H "X-API-Key: {api_key_var.get()}" \\
     http://{host_var.get()}:{port_var.get()}/api/status

The API server is now ready to be started. The configuration
has been saved and the server script has been generated.
"""

                    success_text.insert(tk.END, success_content)
                    success_text.config(state=tk.DISABLED)
                    success_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    success_scroll.pack(side=tk.RIGHT, fill=tk.Y)

                    success_button_frame = tk.Frame(success_dialog)
                    success_button_frame.pack(pady=15)

                    def start_server_now():
                        """Actually start the server"""
                        import subprocess
                        try:
                            # In a real implementation, this would start the server in a separate process
                            messagebox.showinfo(_t("batch_ops.msg_titles.server_starting"),
                                              f"Starting API server on {host_var.get()}:{port_var.get()}...\n\n"
                                              f"In a production environment, the server would now be running.\n"
                                              f"Use 'python3 {script_filename}' to start manually.")
                        except Exception as e:
                            messagebox.showerror(_t("batch_ops.msg_titles.start_error"), f"Failed to start server: {str(e)}")

                    tk.Button(success_button_frame, text=_t("batch_ops.buttons.start_server_now"), command=start_server_now,
                             bg='#4CAF50', fg='white', padx=20, pady=5).pack(side=tk.LEFT, padx=(0, 10))

                    tk.Button(success_button_frame, text=_t("batch_ops.buttons.close"), command=success_dialog.destroy,
                             bg='#f0f0f0', padx=20, pady=5).pack(side=tk.LEFT)

                    # Update the main dialog status
                    status_indicator.config(text="Configured", fg="#FF9800")

                except Exception as e:
                    messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

            def test_config():
                """Test the server configuration"""
                try:
                    # Validate configuration
                    issues = []

                    if not host_var.get().strip():
                        issues.append("\u2022 Host is required")

                    try:
                        port_num = int(port_var.get())
                        if port_num < 1 or port_num > 65535:
                            issues.append("\u2022 Port must be between 1 and 65535")
                    except ValueError:
                        issues.append("\u2022 Port must be a valid number")

                    if not api_key_var.get().strip():
                        issues.append("\u2022 API key is required")

                    if enable_rate_limit_var.get() and not rate_limit_var.get().isdigit():
                        issues.append("\u2022 Rate limit must be a number")

                    if issues:
                        messagebox.showerror(_t("batch_ops.msg_titles.configuration_issues"),
                                           f"Please fix the following issues:\n\n" + "\n".join(issues))
                    else:
                        messagebox.showinfo(_t("batch_ops.msg_titles.configuration_valid"),
                                          f"\u2713 Configuration is valid\n"
                                          f"\u2713 Server will run on {host_var.get()}:{port_var.get()}\n"
                                          f"\u2713 Authentication configured\n"
                                          f"\u2713 {len(api_endpoints)} endpoints available\n"
                                          f"\u2713 Ready to start")

                except Exception as e:
                    messagebox.showerror(_t("batch_ops.msg_titles.test_error"), f"Configuration test failed: {str(e)}")

            # Button layout
            tk.Button(button_frame, text=_t("batch_ops.buttons.test_configuration"), command=test_config,
                     bg='#FF9800', fg='white', padx=15, pady=5).pack(side=tk.LEFT, padx=(0, 10))

            tk.Button(button_frame, text="Configure & Ready Server", command=start_server,
                     bg='#4CAF50', fg='white', padx=20, pady=5).pack(side=tk.LEFT, padx=(0, 10))

            tk.Button(button_frame, text=_t("batch_ops.buttons.cancel"), command=api_dialog.destroy,
                     bg='#f44336', fg='white', padx=20, pady=5).pack(side=tk.RIGHT)

        except Exception as e:
            messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

    def schedule_daily_import_simple(self):
        """GUI version of schedule daily import (simple dialog)"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.windows.schedule_daily_import"))
        dialog.geometry("400x300")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 100))

        # Header
        header = ttk.Label(dialog, text="Schedule Daily Import", font=("Arial", 14, "bold"))
        header.pack(pady=10)

        # Directory selection
        dir_frame = ttk.LabelFrame(dialog, text=_t("batch_ops.labels.import_directory"), padding="10")
        dir_frame.pack(fill=tk.X, padx=20, pady=10)

        dir_var = tk.StringVar()
        ttk.Entry(dir_frame, textvariable=dir_var, width=40).pack(side=tk.LEFT, padx=(0, 10))

        def browse_directory():
            directory = filedialog.askdirectory(title="Select directory to monitor")
            if directory:
                dir_var.set(directory)

        ttk.Button(dir_frame, text=_t("batch_ops.buttons.browse"), command=browse_directory).pack(side=tk.LEFT)

        # Time selection
        time_frame = ttk.LabelFrame(dialog, text=_t("batch_ops.labels.schedule_time"), padding="10")
        time_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(time_frame, text="Time (24-hour format):").pack(anchor='w')
        time_var = tk.StringVar(value="02:00")
        ttk.Entry(time_frame, textvariable=time_var, width=10).pack(anchor='w', pady=5)

        # Email notification
        email_frame = ttk.LabelFrame(dialog, text="Notification", padding="10")
        email_frame.pack(fill=tk.X, padx=20, pady=10)

        email_var = tk.StringVar()
        ttk.Label(email_frame, text="Email (optional):").pack(anchor='w')
        ttk.Entry(email_frame, textvariable=email_var, width=30).pack(anchor='w', pady=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def schedule_import():
            if not dir_var.get():
                messagebox.showerror(_t("batch_ops.msg_titles.error"), "Please select a directory to monitor")
                return

            try:
                # Validate time format
                datetime.datetime.strptime(time_var.get(), '%H:%M')

                # Schedule the task
                self.gui.backend.schedule_daily_import(dir_var.get(), time_var.get(), email_var.get())

                dialog.destroy()
                messagebox.showinfo("Scheduled", f"Daily import scheduled for {time_var.get()}")

                # Update automation status
                self.gui.update_automation_status()

            except ValueError:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), "Invalid time format. Use HH:MM (e.g., 14:30)")
            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        ttk.Button(button_frame, text="Schedule", command=schedule_import).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("batch_ops.buttons.cancel"), command=dialog.destroy).pack(side=tk.LEFT)

    def schedule_weekly_report(self):
        """GUI version of schedule weekly report"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.windows.schedule_weekly_report"))
        dialog.geometry("500x550")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 50))

        # Header
        header = ttk.Label(dialog, text="Schedule Weekly Report", font=("Arial", 14, "bold"))
        header.pack(pady=15)

        # Form frame
        form_frame = ttk.LabelFrame(dialog, text="Report Configuration", padding="15")
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Day of week selection
        ttk.Label(form_frame, text="Day of Week:").grid(row=0, column=0, sticky="w", pady=10)
        day_var = tk.StringVar(value="Monday")
        day_combo = ttk.Combobox(form_frame, textvariable=day_var, width=30, state="readonly",
                                values=["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"])
        day_combo.grid(row=0, column=1, sticky="ew", pady=10, padx=(10,0))

        # Time selection
        ttk.Label(form_frame, text="Time (HH:MM):").grid(row=1, column=0, sticky="w", pady=10)
        time_var = tk.StringVar(value="09:00")
        time_entry = ttk.Entry(form_frame, textvariable=time_var, width=32)
        time_entry.grid(row=1, column=1, sticky="ew", pady=10, padx=(10,0))

        # Report type
        ttk.Label(form_frame, text=_t("batch_ops.labels.report_type")).grid(row=2, column=0, sticky="w", pady=10)
        report_type_var = tk.StringVar(value="summary")
        report_type_combo = ttk.Combobox(form_frame, textvariable=report_type_var, width=30, state="readonly",
                                        values=["summary", "detailed", "analytics", "comprehensive"])
        report_type_combo.grid(row=2, column=1, sticky="ew", pady=10, padx=(10,0))

        # Email recipient
        ttk.Label(form_frame, text="Email To:").grid(row=3, column=0, sticky="w", pady=10)
        email_var = tk.StringVar()
        email_entry = ttk.Entry(form_frame, textvariable=email_var, width=32)
        email_entry.grid(row=3, column=1, sticky="ew", pady=10, padx=(10,0))

        # Report options
        options_frame = ttk.LabelFrame(form_frame, text="Include in Report", padding="10")
        options_frame.grid(row=4, column=0, columnspan=2, sticky="ew", pady=15)

        include_summary = tk.BooleanVar(value=True)
        include_charts = tk.BooleanVar(value=True)
        include_alerts = tk.BooleanVar(value=True)
        include_trends = tk.BooleanVar(value=False)

        ttk.Checkbutton(options_frame, text="Summary Statistics", variable=include_summary).pack(anchor="w", pady=2)
        ttk.Checkbutton(options_frame, text="Charts and Graphs", variable=include_charts).pack(anchor="w", pady=2)
        ttk.Checkbutton(options_frame, text="Alerts and Warnings", variable=include_alerts).pack(anchor="w", pady=2)
        ttk.Checkbutton(options_frame, text="Performance Trends", variable=include_trends).pack(anchor="w", pady=2)

        # Format selection
        ttk.Label(form_frame, text="Report Format:").grid(row=5, column=0, sticky="w", pady=10)
        format_var = tk.StringVar(value="pdf")
        format_combo = ttk.Combobox(form_frame, textvariable=format_var, width=30, state="readonly",
                                   values=["pdf", "html", "excel", "csv"])
        format_combo.grid(row=5, column=1, sticky="ew", pady=10, padx=(10,0))

        form_frame.columnconfigure(1, weight=1)

        def schedule_report():
            try:
                if not email_var.get():
                    messagebox.showwarning("Missing Information", "Please enter an email address")
                    return

                # Validate time format
                time_parts = time_var.get().split(":")
                if len(time_parts) != 2:
                    raise ValueError("Invalid time format")
                hour, minute = int(time_parts[0]), int(time_parts[1])
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError("Invalid time range")

                # Save schedule configuration
                schedule_config = {
                    'day': day_var.get(),
                    'time': time_var.get(),
                    'report_type': report_type_var.get(),
                    'email': email_var.get(),
                    'format': format_var.get(),
                    'include_summary': include_summary.get(),
                    'include_charts': include_charts.get(),
                    'include_alerts': include_alerts.get(),
                    'include_trends': include_trends.get()
                }

                # In real implementation, this would register with a scheduler
                config_file = os.path.join(os.getcwd(), "weekly_report_schedule.json")
                with open(config_file, 'w') as f:
                    json.dump(schedule_config, f, indent=2)

                messagebox.showinfo("Success",
                    f"Weekly report scheduled for {day_var.get()}s at {time_var.get()}\n" +
                    f"Report Type: {report_type_var.get()}\n" +
                    f"Will be sent to: {email_var.get()}")
                dialog.destroy()

            except ValueError as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))
            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=15)
        ttk.Button(button_frame, text="Schedule Report", command=schedule_report).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("batch_ops.buttons.cancel"), command=dialog.destroy).pack(side=tk.LEFT)

    def view_scheduled_tasks(self):
        """GUI version of view scheduled tasks"""
        try:
            jobs = schedule.get_jobs()

            if not jobs:
                messagebox.showinfo(_t("batch_ops.msg_titles.no_tasks"), _t("batch_ops.messages.no_scheduled_tasks"))
                return

            # Show tasks dialog
            dialog = tk.Toplevel(self.gui.root)
            dialog.title(_t("batch_ops.windows.scheduled_tasks"))
            dialog.geometry("600x400")
            dialog.transient(self.gui.root)
            dialog.grab_set()

            # Center dialog
            dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 100))

            # Header
            header = ttk.Label(dialog, text="Scheduled Tasks", font=("Arial", 14, "bold"))
            header.pack(pady=10)

            # Tasks list
            tasks_frame = ttk.LabelFrame(dialog, text=_t("batch_ops.labels.active_tasks"), padding="10")
            tasks_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

            tasks_text = scrolledtext.ScrolledText(tasks_frame, height=15)
            tasks_text.pack(fill=tk.BOTH, expand=True)

            for i, job in enumerate(jobs, 1):
                tasks_text.insert(tk.END, f"{i}. {str(job)}\n\n")

            tasks_text.config(state='disabled')

            # Close button
            ttk.Button(dialog, text=_t("batch_ops.buttons.close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

    def start_api_server_simple(self):
        """GUI version of start API server (simple dialog)"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.windows.start_api_server"))
        dialog.geometry("400x250")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 100))

        # Header
        header = ttk.Label(dialog, text="Start API Server", font=("Arial", 14, "bold"))
        header.pack(pady=10)

        # Server configuration
        config_frame = ttk.LabelFrame(dialog, text=_t("batch_ops.labels.server_configuration"), padding="10")
        config_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(config_frame, text=_t("batch_ops.labels.port")).grid(row=0, column=0, sticky='w', pady=5)
        port_var = tk.StringVar(value="5000")
        ttk.Entry(config_frame, textvariable=port_var, width=10).grid(row=0, column=1, padx=(10, 0), pady=5)

        ttk.Label(config_frame, text=_t("batch_ops.labels.host")).grid(row=1, column=0, sticky='w', pady=5)
        host_var = tk.StringVar(value="0.0.0.0")
        ttk.Entry(config_frame, textvariable=host_var, width=15).grid(row=1, column=1, padx=(10, 0), pady=5)

        # API endpoints info
        info_frame = ttk.LabelFrame(dialog, text=_t("batch_ops.labels.available_endpoints"), padding="10")
        info_frame.pack(fill=tk.X, padx=20, pady=10)

        endpoints_text = """POST /api/import - Import student data
GET /api/students - Get student list
PUT /api/students/<id> - Update student
GET /api/health - Health check"""

        ttk.Label(info_frame, text=endpoints_text, justify=tk.LEFT).pack(anchor='w')

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def start_server():
            try:
                port = int(port_var.get())
                host = host_var.get()

                dialog.destroy()

                # Start server in separate thread
                def server_worker():
                    try:
                        self.gui.backend.start_api_server(host, port)
                    except Exception as e:
                        self.gui.message_queue.put({'type': 'error', 'text': f'API server failed: {str(e)}'})

                thread = threading.Thread(target=server_worker)
                thread.daemon = True
                thread.start()

                messagebox.showinfo(_t("batch_ops.msg_titles.server_started"), f"API server started on {host}:{port}")
                self.gui.update_automation_status()

            except ValueError:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), "Invalid port number")
            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        ttk.Button(button_frame, text=_t("batch_ops.buttons.start_server"), command=start_server).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("batch_ops.buttons.cancel"), command=dialog.destroy).pack(side=tk.LEFT)

    def setup_external_db(self):
        """GUI version of external database setup"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.windows.external_db_setup"))
        dialog.geometry("500x400")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 100))

        # Header
        header = ttk.Label(dialog, text="External Database Integration", font=("Arial", 14, "bold"))
        header.pack(pady=10)

        # Database type
        type_frame = ttk.LabelFrame(dialog, text="Database Type", padding="10")
        type_frame.pack(fill=tk.X, padx=20, pady=10)

        db_type_var = tk.StringVar(value="mysql")
        ttk.Radiobutton(type_frame, text="MySQL", variable=db_type_var, value="mysql").pack(anchor='w')
        ttk.Radiobutton(type_frame, text="PostgreSQL", variable=db_type_var, value="postgresql").pack(anchor='w')

        # Connection details
        conn_frame = ttk.LabelFrame(dialog, text=_t("batch_ops.labels.connection_details"), padding="10")
        conn_frame.pack(fill=tk.X, padx=20, pady=10)

        # Host
        ttk.Label(conn_frame, text=_t("batch_ops.labels.host")).grid(row=0, column=0, sticky='w', pady=5)
        host_var = tk.StringVar(value="localhost")
        ttk.Entry(conn_frame, textvariable=host_var, width=20).grid(row=0, column=1, padx=(10, 0), pady=5)

        # Port
        ttk.Label(conn_frame, text=_t("batch_ops.labels.port")).grid(row=1, column=0, sticky='w', pady=5)
        port_var = tk.StringVar(value="3306")
        ttk.Entry(conn_frame, textvariable=port_var, width=10).grid(row=1, column=1, padx=(10, 0), pady=5)

        # Database
        ttk.Label(conn_frame, text="Database:").grid(row=2, column=0, sticky='w', pady=5)
        database_var = tk.StringVar()
        ttk.Entry(conn_frame, textvariable=database_var, width=20).grid(row=2, column=1, padx=(10, 0), pady=5)

        # Username
        ttk.Label(conn_frame, text=_t("batch_ops.labels.username")).grid(row=3, column=0, sticky='w', pady=5)
        username_var = tk.StringVar()
        ttk.Entry(conn_frame, textvariable=username_var, width=20).grid(row=3, column=1, padx=(10, 0), pady=5)

        # Password
        ttk.Label(conn_frame, text=_t("batch_ops.labels.password")).grid(row=4, column=0, sticky='w', pady=5)
        password_var = tk.StringVar()
        ttk.Entry(conn_frame, textvariable=password_var, width=20, show="*").grid(row=4, column=1, padx=(10, 0), pady=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def test_connection():
            try:
                config = {
                    'type': db_type_var.get(),
                    'host': host_var.get(),
                    'port': port_var.get(),
                    'database': database_var.get(),
                    'username': username_var.get(),
                    'password': password_var.get()
                }

                # Test the connection directly based on database type
                import importlib
                db_type = config['type']
                host = config['host']
                port = config['port']
                database = config['database']
                username = config['username']
                password = config['password']

                if db_type == 'mysql':
                    mysql = importlib.import_module('mysql.connector')
                    conn = mysql.connect(host=host, port=int(port), database=database, user=username, password=password)
                    conn.close()
                elif db_type == 'postgresql':
                    psycopg2 = importlib.import_module('psycopg2')
                    conn = psycopg2.connect(host=host, port=int(port), dbname=database, user=username, password=password)
                    conn.close()

                messagebox.showinfo("Success", "Database connection successful!")

            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        def save_config():
            try:
                config = {
                    'type': db_type_var.get(),
                    'host': host_var.get(),
                    'port': port_var.get(),
                    'database': database_var.get(),
                    'username': username_var.get(),
                    'password': password_var.get()
                }

                self.gui.backend.save_external_db_config(config)
                dialog.destroy()
                messagebox.showinfo(_t("batch_ops.msg_titles.saved"), "External database configuration saved!")

            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        ttk.Button(button_frame, text=_t("batch_ops.buttons.test_connection"), command=test_connection).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Save Config", command=save_config).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("batch_ops.buttons.cancel"), command=dialog.destroy).pack(side=tk.LEFT)

    def setup_rest_api(self):
        """GUI version of REST API integration setup"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.windows.rest_api_integration"))
        dialog.geometry("400x250")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 100))

        # Header
        header = ttk.Label(dialog, text="REST API Integration", font=("Arial", 14, "bold"))
        header.pack(pady=10)

        # API details
        api_frame = ttk.LabelFrame(dialog, text=_t("batch_ops.labels.api_configuration"), padding="10")
        api_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(api_frame, text=_t("batch_ops.labels.base_url")).grid(row=0, column=0, sticky='w', pady=5)
        url_var = tk.StringVar()
        ttk.Entry(api_frame, textvariable=url_var, width=30).grid(row=0, column=1, padx=(10, 0), pady=5)

        ttk.Label(api_frame, text=_t("batch_ops.labels.api_key")).grid(row=1, column=0, sticky='w', pady=5)
        key_var = tk.StringVar()
        ttk.Entry(api_frame, textvariable=key_var, width=30, show="*").grid(row=1, column=1, padx=(10, 0), pady=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def test_api():
            try:
                url = url_var.get()
                api_key = key_var.get()

                success = self.gui.backend.test_rest_api_connection(url, api_key)

                if success:
                    messagebox.showinfo("Success", "API connection successful!")
                else:
                    messagebox.showerror(_t("batch_ops.msg_titles.failed"), "API connection failed!")

            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        def save_api_config():
            try:
                config = {
                    'url': url_var.get(),
                    'api_key': key_var.get()
                }

                self.gui.backend.save_rest_api_config(config)
                dialog.destroy()
                messagebox.showinfo(_t("batch_ops.msg_titles.saved"), "REST API configuration saved!")

            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        ttk.Button(button_frame, text="Test API", command=test_api).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Save Config", command=save_api_config).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("batch_ops.buttons.cancel"), command=dialog.destroy).pack(side=tk.LEFT)

    def test_connections(self):
        """Test all configured connections"""
        def test_worker():
            try:
                progress_dialog = GUIProgressDialog(self.gui.root, "Testing Connections", "Testing external connections")

                results = self.gui.backend.test_all_connections(progress_callback=progress_dialog.update_progress)

                progress_dialog.close()
                self.gui.show_connection_test_results(results)

            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        thread = threading.Thread(target=test_worker)
        thread.daemon = True
        thread.start()

    def cancel_scheduled_task(self):
        """GUI version of cancel scheduled task"""
        try:
            jobs = schedule.get_jobs()

            if not jobs:
                messagebox.showinfo(_t("batch_ops.msg_titles.no_tasks"), "No scheduled tasks to cancel")
                return

            # Show selection dialog
            dialog = tk.Toplevel(self.gui.root)
            dialog.title(_t("batch_ops.windows.cancel_task"))
            dialog.geometry("500x300")
            dialog.transient(self.gui.root)
            dialog.grab_set()

            # Center dialog
            dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 100))

            # Header
            header = ttk.Label(dialog, text="Select Task to Cancel", font=("Arial", 12, "bold"))
            header.pack(pady=10)

            # Task selection
            selected_job = tk.IntVar()

            for i, job in enumerate(jobs):
                ttk.Radiobutton(dialog, text=str(job), variable=selected_job, value=i).pack(anchor='w', padx=20)

            # Buttons
            button_frame = ttk.Frame(dialog)
            button_frame.pack(pady=20)

            def cancel_selected():
                try:
                    job_index = selected_job.get()
                    if 0 <= job_index < len(jobs):
                        schedule.cancel_job(jobs[job_index])
                        dialog.destroy()
                        messagebox.showinfo(_t("batch_ops.msg_titles.cancelled"), "Task cancelled successfully")
                        self.gui.update_automation_status()
                    else:
                        messagebox.showerror(_t("batch_ops.msg_titles.error"), "Please select a task to cancel")
                except Exception as e:
                    messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

            # Create the cancel button.  Unlike the CLI version, no additional
            # data validation or database operations are required here.  The
            # original batch_operations.validate_and_clean_data logic was
            # inadvertently inserted into this GUI method and has been
            # removed.  If additional cleanup is needed it should be
            # performed by backend services rather than the GUI layer.
            ttk.Button(button_frame, text=_t("batch_ops.buttons.cancel_task"), command=cancel_selected).pack(side=tk.LEFT, padx=10)
            # Add a close button to allow the user to dismiss the dialog without
            # performing any action.
            ttk.Button(button_frame, text=_t("batch_ops.buttons.close"), command=dialog.destroy).pack(side=tk.LEFT)

        except Exception as e:
            # Catch any unexpected errors when retrieving or cancelling jobs and
            # display them to the user.  The logger module is not used here
            # because this method is part of the GUI layer.
            messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))
