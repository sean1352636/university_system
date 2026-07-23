"""Utility operations manager for batch operations GUI."""
import os
import json
import shutil
import datetime
import threading

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from education_system.post_18.university_system.modules.shared.gui.batch_operations.constants import (
    _t, logger, sqlite3, DEFAULT_DB_PATH, GUI_SETTINGS_PATH,
    EXTERNAL_DB_CONFIG_PATH, EXTERNAL_API_CONFIG_PATH,
    IMPORT_HISTORY_PATH,
    get_log_file, schedule, Notebook,
)
from education_system.post_18.university_system.modules.shared.gui.batch_operations.models import OriginalBatchOperationManager
from education_system.post_18.university_system.modules.shared.gui.batch_operations.progress_dialog import GUIProgressDialog


class UtilityManager:
    """Manages utility operations for BatchOperationsGUI."""

    def __init__(self, gui):
        self.gui = gui

    def show_system_logs(self):
        """Show system logs dialog"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.dialogs.system_logs"))
        dialog.geometry("800x600")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 50, self.gui.root.winfo_rooty() + 50))

        # Header
        header = ttk.Label(dialog, text=_t("batch_ops.dialogs.system_logs"), font=("Arial", 14, "bold"))
        header.pack(pady=10)

        # Log display
        log_frame = ttk.Frame(dialog)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        log_text = scrolledtext.ScrolledText(log_frame, height=30, width=100)
        log_text.pack(fill=tk.BOTH, expand=True)

        # Load and display logs
        try:
            log_file_path = get_log_file("app.log")
            if os.path.exists(log_file_path):
                with open(log_file_path, 'r') as f:
                    log_content = f.read()
                    log_text.insert(tk.END, log_content)
            else:
                log_text.insert(tk.END, _t("batch_ops.logs.no_log_file"))
        except Exception as e:
            log_text.insert(tk.END, f"Error reading log file: {str(e)}")

        log_text.config(state='disabled')

        # Refresh button
        def refresh_logs():
            try:
                log_text.config(state='normal')
                log_text.delete(1.0, tk.END)

                log_file_path = get_log_file("app.log")
                if os.path.exists(log_file_path):
                    with open(log_file_path, 'r') as f:
                        log_content = f.read()
                        log_text.insert(tk.END, log_content)
                else:
                    log_text.insert(tk.END, _t("batch_ops.logs.no_log_file"))

                log_text.config(state='disabled')
                log_text.see(tk.END)  # Scroll to bottom

            except Exception as e:
                log_text.config(state='normal')
                log_text.insert(tk.END, f"\nError refreshing logs: {str(e)}")
                log_text.config(state='disabled')

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text=_t("batch_ops.buttons.refresh"), command=refresh_logs).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("batch_ops.buttons.close"), command=dialog.destroy).pack(side=tk.LEFT)

    def show_user_guide(self):
        """Show user guide dialog"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.windows.user_guide"))
        dialog.geometry("700x500")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 50, self.gui.root.winfo_rooty() + 50))

        # Header
        header = ttk.Label(dialog, text=_t("batch_ops.windows.user_guide"), font=("Arial", 16, "bold"))
        header.pack(pady=10)

        # Guide content
        guide_frame = ttk.Frame(dialog)
        guide_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        guide_text = scrolledtext.ScrolledText(guide_frame, height=25, width=80)
        guide_text.pack(fill=tk.BOTH, expand=True)

        user_guide_content = """ENHANCED STUDENT RECORDS BATCH OPERATIONS SYSTEM
USER GUIDE

OVERVIEW
========
This application provides a comprehensive GUI interface for managing student records with advanced batch operations, data quality tools, and automation features.

GETTING STARTED
===============
1. The application starts with the Import Operations tab selected
2. Use the tabs at the top to navigate between different functions
3. The status bar at the bottom shows current operation status
4. Database connection status is displayed in the bottom right

IMPORT OPERATIONS
=================
📊 Import from CSV/Excel: Import student data from files
   - Supports automatic validation and error handling
   - Progress tracking with ETA
   - Detailed results reporting

🔍 Import with Duplicate Detection: Smart duplicate handling
   - Configurable confidence thresholds
   - Multiple handling options (skip, update, merge)
   - Interactive duplicate resolution

👁️ Preview Import: Preview changes before applying
   - Shows sample data and import summary
   - No database changes until confirmed

UPDATE OPERATIONS
=================
✏️ Batch Update Records: Update multiple student records
   - Requires student_id column for matching
   - Only updates specified fields
   - Automatic backup before changes

📚 Bulk Module Operations: Manage module assignments
   - Add/remove modules for multiple students
   - Course-based or file-based student selection
   - Import module enrollments from CSV

📊 Import Grade Data: Import student grades
   - Links grades to students and modules
   - Supports semester/year tracking

EXPORT OPERATIONS
=================
📤 Export Students: Export data in multiple formats
   - CSV, Excel, or JSON output
   - Filtering by course or date range
   - Include/exclude module information

📈 Export Statistics: Generate enrollment reports
   - Course distribution
   - Age demographics
   - Registration trends

📋 Generate Reports: Detailed analysis reports
   - Import success rates
   - Error analysis
   - Performance trends

DATA QUALITY
=============
🔍 Validate Data: Check data integrity
   - Email format validation
   - Name completeness
   - Age/DOB consistency

🎯 Find Duplicates: Detect potential duplicates
   - Fuzzy matching algorithm
   - Configurable confidence levels
   - Interactive merge tools

🧹 Clean Data: Automatic data cleaning
   - Fix common formatting issues
   - Update calculated fields
   - Standardize data formats

📊 Quality Dashboard: Real-time quality metrics
   - Completeness percentages
   - Issue tracking
   - Trend analysis

UTILITIES
=========
📋 Generate Template: Create import templates
   - Pre-configured field layouts
   - Example data included
   - Multiple template types

💾 Create Backup: Database backup management
   - Automatic timestamped backups
   - Restore functionality
   - Cleanup old backups

↩️ Undo Last Import: Rollback recent changes
   - Identifies records from last import
   - Confirmation dialogs
   - History tracking

⚙️ Settings: Configure application behavior
   - Database paths
   - Backup settings
   - Import validation options

AUTOMATION
==========
📅 Scheduled Tasks: Automate regular operations
   - Daily/weekly import schedules
   - Email notifications
   - Directory monitoring

🌐 API Server: REST API for integrations
   - Import endpoints
   - Student management
   - Health monitoring

🔗 External Integration: Connect to external systems
   - Database connections (MySQL, PostgreSQL)
   - REST API integration
   - File share monitoring

KEYBOARD SHORTCUTS
==================
Ctrl+N: New Import
Ctrl+O: Open Database
Ctrl+S: Save/Export
Ctrl+B: Create Backup
F5: Refresh current view
Esc: Cancel current operation

TROUBLESHOOTING
===============
- Check system logs for detailed error information
- Ensure proper file formats and column headers
- Verify database connectivity
- Use preview mode to test imports
- Create backups before major operations

BACKWARDS COMPATIBILITY
=======================
The GUI application maintains full backwards compatibility with the original command-line interface:
- All original functions are available
- Same database format and structure
- Can switch to command-line mode anytime
- Import/export formats remain unchanged

For additional help, use the Help menu or check the system logs for detailed error information.
"""

        guide_text.insert(tk.END, user_guide_content)
        guide_text.config(state='disabled')

        # Close button
        ttk.Button(dialog, text=_t("batch_ops.buttons.close"), command=dialog.destroy).pack(pady=10)

    def show_about(self):
        """Show about dialog"""
        about_text = """Enhanced Student Records Batch Operations System
GUI Version 2.0

A comprehensive student data management system with:
• Advanced batch import/export capabilities
• Intelligent duplicate detection
• Data quality validation and cleaning
• Automated scheduling and monitoring
• REST API integration
• Full backwards compatibility

Built with Python and tkinter
© 2024 Student Records Management System"""

        messagebox.showinfo(_t("batch_ops.msg_titles.about"), about_text)

    def show_system_status(self):
        """Show system status dialog"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.windows.system_status"))
        dialog.geometry("700x550")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # System status content
        status_text = scrolledtext.ScrolledText(dialog, height=30, width=80)
        status_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Get system information
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM students")
            student_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM student_modules")
            module_count = cursor.fetchone()[0]
            conn.close()

            status_info = f"""SYSTEM STATUS REPORT
    Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

    DATABASE INFORMATION
    ====================
    Database Path: {self.gui.backend.db_path}
    Total Students: {student_count:,}
    Total Module Enrollments: {module_count:,}
    Database Size: {os.path.getsize(self.gui.backend.db_path) / 1024:.1f} KB

    IMPORT HISTORY
    ==============
    Total Import Operations: {len(self.gui.backend.import_history)}

    SCHEDULED TASKS
    ===============
    Active Scheduled Tasks: {len(schedule.get_jobs())}

    EXTERNAL INTEGRATIONS
    ====================
    Database Config: {'Yes' if EXTERNAL_DB_CONFIG_PATH.exists() else 'No'}
    API Config: {'Yes' if EXTERNAL_API_CONFIG_PATH.exists() else 'No'}
    """

            status_text.insert(tk.END, status_info)

        except Exception as e:
            status_text.insert(tk.END, f"Error retrieving status: {str(e)}")

        status_text.config(state='disabled')

        ttk.Button(dialog, text=_t("batch_ops.buttons.close"), command=dialog.destroy).pack(pady=10)

    def open_database(self):
        """Open a different database file - already implemented but ensure it's complete"""
        db_file = filedialog.askopenfilename(
            title="Select database file",
            filetypes=[("Database files", "*.db"), ("All files", "*.*")]
        )

        if db_file:
            try:
                self.gui.backend.db_path = db_file
                self.gui.db_status_label.config(text=f"Database: {os.path.basename(db_file)}")
                messagebox.showinfo(_t("batch_ops.msg_titles.database_opened"), f"Opened database: {os.path.basename(db_file)}")

                # Refresh displays
                self.gui.refresh_history()
                self.gui.refresh_quality_dashboard()

            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

    def open_command_line_mode(self):
        """Open the original command-line interface in a background thread."""
        if messagebox.askyesno(
            "Command Line Mode",
            "This will open the original command-line interface in a new window/terminal.\nContinue?"
        ):
            try:
                def cli_worker():
                    # Reuse same DB path so CLI and GUI share data
                    original_manager = OriginalBatchOperationManager(self.gui.backend.db_path)
                    # If CLI exists, run it; otherwise be noisy but not crash
                    if hasattr(original_manager, "display_batch_menu"):
                        original_manager.display_batch_menu()
                    else:
                        print("Command-line menu not available in this build.")

                threading.Thread(target=cli_worker, daemon=True).start()
                messagebox.showinfo(_t("batch_ops.msg_titles.command_line"), _t("batch_ops.messages.cli_started"))
            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), f"Failed to start command-line mode: {e}")

    def generate_template(self):
        """GUI version of template generation"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.windows.generate_template"))
        dialog.geometry("500x400")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 100))

        # Header
        header = ttk.Label(dialog, text="Generate Import Template", font=("Arial", 14, "bold"))
        header.pack(pady=10)

        # Template type
        type_frame = ttk.LabelFrame(dialog, text="Template Type", padding="10")
        type_frame.pack(fill=tk.X, padx=20, pady=10)

        template_var = tk.StringVar(value="new_students")

        ttk.Radiobutton(type_frame, text="New Student Import",
                       variable=template_var, value="new_students").pack(anchor='w')
        ttk.Radiobutton(type_frame, text="Student Update",
                       variable=template_var, value="update_students").pack(anchor='w')
        ttk.Radiobutton(type_frame, text="Module Enrollment",
                       variable=template_var, value="module_enrollment").pack(anchor='w')
        ttk.Radiobutton(type_frame, text="Grade Import",
                       variable=template_var, value="grade_import").pack(anchor='w')
        ttk.Radiobutton(type_frame, text="Custom Template",
                       variable=template_var, value="custom").pack(anchor='w')

        # Format selection
        format_frame = ttk.LabelFrame(dialog, text="File Format", padding="10")
        format_frame.pack(fill=tk.X, padx=20, pady=10)

        format_var = tk.StringVar(value="csv")

        ttk.Radiobutton(format_frame, text="CSV", variable=format_var, value="csv").pack(anchor='w')
        ttk.Radiobutton(format_frame, text="Excel", variable=format_var, value="xlsx").pack(anchor='w')

        # Include examples
        examples_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(format_frame, text="Include example data",
                       variable=examples_var).pack(anchor='w', pady=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def generate_selected_template():
            template_type = template_var.get()
            file_format = format_var.get()
            include_examples = examples_var.get()

            # Map GUI template types to backend keys
            template_type_map = {
                "new_students": "1",
                "update_students": "2",
                "module_enrollment": "3",
                "grade_import": "4",
                "custom": "1",
            }
            backend_template_type = template_type_map.get(template_type, "1")

            # Map GUI format to backend format ('1' = CSV, '2' = Excel)
            backend_format = "1" if file_format == "csv" else "2"

            # Get output file
            if file_format == "csv":
                file_extension = ".csv"
                file_types = [("CSV files", "*.csv")]
            else:
                file_extension = ".xlsx"
                file_types = [("Excel files", "*.xlsx")]

            output_file = filedialog.asksaveasfilename(
                title="Save template as",
                defaultextension=file_extension,
                filetypes=file_types + [("All files", "*.*")]
            )

            if not output_file:
                return

            dialog.destroy()

            try:
                example_data = self.gui.backend.get_example_data(backend_template_type)
                fields = list(example_data.keys()) if example_data else ['first_name', 'last_name', 'gender', 'dob', 'course']
                self.gui.backend.create_template_file(
                    fields=fields,
                    filename=output_file,
                    file_format=backend_format,
                    template_type=backend_template_type
                )
                messagebox.showinfo(_t("batch_ops.msg_titles.template_generated"), f"Template saved to {output_file}")

                # Show usage instructions
                self.show_template_instructions(template_type)

            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        ttk.Button(button_frame, text=_t("batch_ops.buttons.generate"), command=generate_selected_template).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("batch_ops.buttons.cancel"), command=dialog.destroy).pack(side=tk.LEFT)

    def show_template_instructions(self, template_type):
        """Show template usage instructions"""
        instructions = {
            "new_students": [
                "NEW STUDENT IMPORT INSTRUCTIONS:",
                "• Fill in all required fields: first_name, last_name, gender, dob, course",
                "• Valid gender values: male, female, other",
                "• DOB format: YYYY-MM-DD (e.g., 1995-01-15)",
                "• Valid course values: CS, DS",
                "• middle_name, email_address, phone_number are optional"
            ],
            "update_students": [
                "STUDENT UPDATE INSTRUCTIONS:",
                "• student_id is required and must match existing record",
                "• Only fill in fields you want to update",
                "• Leave fields blank to keep current values",
                "• Use same validation rules as new student import"
            ],
            "module_enrollment": [
                "MODULE ENROLLMENT INSTRUCTIONS:",
                "• student_id must exist in database",
                "• module_code should be unique identifier",
                "• module_type: compulsory, optional, CS, DS"
            ],
            "grade_import": [
                "GRADE IMPORT INSTRUCTIONS:",
                "• student_id and module_code must exist",
                "• grade: numeric value (0-100)",
                "• semester and year are optional"
            ]
        }

        if template_type in instructions:
            instruction_text = "\n".join(instructions[template_type])
            messagebox.showinfo(_t("batch_ops.msg_titles.template_instructions"), instruction_text)

    def create_backup(self):
        """GUI version of create backup"""
        if messagebox.askyesno(_t("batch_ops.msg_titles.create_backup"), "Create a backup of the current database?"):
            def backup_worker():
                try:
                    self.gui.update_status("Creating database backup...")

                    backup_path = self.gui.backend.create_database_backup()

                    self.gui.update_status("Ready")
                    messagebox.showinfo(_t("batch_ops.msg_titles.backup_created"), f"Database backup created successfully:\n{backup_path}")

                except Exception as e:
                    messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

            thread = threading.Thread(target=backup_worker)
            thread.daemon = True
            thread.start()

    def restore_backup(self):
        """GUI version of restore backup"""
        backup_file = filedialog.askopenfilename(
            title="Select backup file to restore",
            filetypes=[("Database files", "*.db"), ("All files", "*.*")]
        )

        if not backup_file:
            return

        if messagebox.askyesno("Restore Backup",
                              f"This will replace the current database with the backup.\n"
                              f"Current data will be lost!\n\n"
                              f"Restore from: {os.path.basename(backup_file)}?"):
            try:
                # Create a backup of current database first
                current_backup = self.gui.backend.create_database_backup()

                # Restore from selected backup
                shutil.copy2(backup_file, self.gui.backend.db_path)

                messagebox.showinfo("Restore Complete",
                                   f"Database restored successfully from {os.path.basename(backup_file)}\n"
                                   f"Previous database backed up to: {current_backup}")

                # Refresh any open displays
                self.gui.refresh_history()

            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

    def undo_import(self):
        """GUI version of undo last import"""
        # Load import history
        try:
            if not self.gui.backend.import_history:
                with open(IMPORT_HISTORY_PATH, 'r') as f:
                    self.gui.backend.import_history = json.load(f)
        except FileNotFoundError:
            messagebox.showinfo("No History", "No import history found")
            return

        if not self.gui.backend.import_history:
            messagebox.showinfo(_t("batch_ops.msg_titles.no_history"), _t("batch_ops.messages.no_imports_undo"))
            return

        last_import = self.gui.backend.import_history[-1]

        # Show confirmation dialog with details
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.windows.undo_last"))
        dialog.geometry("500x300")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 100))

        # Header
        header = ttk.Label(dialog, text="⚠️ Undo Last Import", font=("Arial", 14, "bold"))
        header.pack(pady=10)

        # Import details
        details_frame = ttk.LabelFrame(dialog, text="Last Import Details", padding="10")
        details_frame.pack(fill=tk.X, padx=20, pady=10)

        details_text = f"""Date: {last_import['timestamp']}
Operation: {last_import['operation_type']}
Records Imported: {last_import['successful_imports']}
File: {os.path.basename(last_import['file_path'])}

This will delete all records from the last import operation.
This action cannot be undone!"""

        ttk.Label(details_frame, text=details_text, justify=tk.LEFT).pack(anchor='w')

        # Warning
        warning_frame = ttk.Frame(dialog)
        warning_frame.pack(fill=tk.X, padx=20, pady=10)

        warning_text = "⚠️ WARNING: This action is irreversible!"
        warning_label = ttk.Label(warning_frame, text=warning_text, foreground="red",
                                 font=("Arial", 10, "bold"))
        warning_label.pack()

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def confirm_undo():
            dialog.destroy()

            def undo_worker():
                try:
                    progress_dialog = GUIProgressDialog(self.gui.root, "Undo Import", "Undoing last import")

                    deleted_count = self.gui.backend.undo_last_import(progress_callback=progress_dialog.update_progress)

                    progress_dialog.close()
                    messagebox.showinfo(_t("batch_ops.msg_titles.undo_complete"), f"Successfully deleted {deleted_count} records")

                    # Refresh displays
                    self.gui.refresh_history()

                except Exception as e:
                    messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

            thread = threading.Thread(target=undo_worker)
            thread.daemon = True
            thread.start()

        ttk.Button(button_frame, text=_t("batch_ops.buttons.confirm_undo"), command=confirm_undo,
                  style='Danger.TButton').pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("batch_ops.buttons.cancel"), command=dialog.destroy).pack(side=tk.LEFT)

    def show_settings(self):
        """Show application settings dialog"""
        dialog = tk.Toplevel(self.gui.root)
        dialog.title(_t("batch_ops.windows.application_settings"))
        dialog.geometry("500x400")
        dialog.transient(self.gui.root)
        dialog.grab_set()

        # Center dialog
        dialog.geometry("+%d+%d" % (self.gui.root.winfo_rootx() + 100, self.gui.root.winfo_rooty() + 100))

        # Header
        header = ttk.Label(dialog, text="Application Settings", font=("Arial", 14, "bold"))
        header.pack(pady=10)

        # Settings notebook
        settings_notebook = Notebook(dialog)
        settings_notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # General settings
        general_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(general_frame, text="General")

        # Database settings
        db_frame = ttk.LabelFrame(general_frame, text="Database", padding="10")
        db_frame.pack(fill=tk.X, pady=10)

        ttk.Label(db_frame, text="Database Path:").grid(row=0, column=0, sticky='w', pady=5)
        db_path_var = tk.StringVar(value=self.gui.backend.db_path)
        db_entry = ttk.Entry(db_frame, textvariable=db_path_var, width=40)
        db_entry.grid(row=0, column=1, padx=(10, 0), pady=5)

        def browse_db():
            file_path = filedialog.askopenfilename(
                title="Select database file",
                filetypes=[("Database files", "*.db"), ("All files", "*.*")]
            )
            if file_path:
                db_path_var.set(file_path)

        ttk.Button(db_frame, text=_t("batch_ops.buttons.browse"), command=browse_db).grid(row=0, column=2, padx=(5, 0))

        # Backup settings
        backup_frame = ttk.LabelFrame(general_frame, text=_t("batch_ops.labels.backup"), padding="10")
        backup_frame.pack(fill=tk.X, pady=10)

        ttk.Label(backup_frame, text=_t("batch_ops.labels.backup_directory")).grid(row=0, column=0, sticky='w', pady=5)
        backup_dir_var = tk.StringVar(value=self.gui.backend.backup_dir)
        backup_entry = ttk.Entry(backup_frame, textvariable=backup_dir_var, width=40)
        backup_entry.grid(row=0, column=1, padx=(10, 0), pady=5)

        auto_backup_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(backup_frame, text="Automatic backup before imports",
                       variable=auto_backup_var).grid(row=1, column=0, columnspan=2, sticky='w', pady=5)

        # Import settings
        import_frame = ttk.Frame(settings_notebook)
        settings_notebook.add(import_frame, text="Import")

        import_settings_frame = ttk.LabelFrame(import_frame, text="Import Behavior", padding="10")
        import_settings_frame.pack(fill=tk.X, pady=10)

        duplicate_threshold_var = tk.DoubleVar(value=0.7)
        ttk.Label(import_settings_frame, text="Duplicate Detection Threshold:").grid(row=0, column=0, sticky='w', pady=5)
        threshold_scale = ttk.Scale(import_settings_frame, from_=0.5, to=0.95,
                                   variable=duplicate_threshold_var, orient='horizontal')
        threshold_scale.grid(row=0, column=1, padx=(10, 0), pady=5, sticky='ew')

        validate_on_import_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(import_settings_frame, text="Validate data during import",
                       variable=validate_on_import_var).grid(row=1, column=0, columnspan=2, sticky='w', pady=5)

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def save_settings():
            try:
                # Apply settings
                self.gui.backend.db_path = db_path_var.get()
                self.gui.backend.backup_dir = backup_dir_var.get()

                # Save settings to file
                settings = {
                    'db_path': db_path_var.get(),
                    'backup_dir': backup_dir_var.get(),
                    'auto_backup': auto_backup_var.get(),
                    'duplicate_threshold': duplicate_threshold_var.get(),
                    'validate_on_import': validate_on_import_var.get()
                }

                with open(GUI_SETTINGS_PATH, 'w') as f:
                    json.dump(settings, f, indent=2)

                dialog.destroy()
                messagebox.showinfo("Settings Saved", "Settings have been saved successfully")

            except Exception as e:
                messagebox.showerror(_t("batch_ops.msg_titles.error"), _t("batch_ops.errors.generic_error", error=str(e)))

        ttk.Button(button_frame, text=_t("batch_ops.buttons.save"), command=save_settings).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text=_t("batch_ops.buttons.cancel"), command=dialog.destroy).pack(side=tk.LEFT)
