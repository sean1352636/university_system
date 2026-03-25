from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection, transaction  # injected
from education_system.university_system.infrastructure.exceptions import (
    CourseNotFoundError,
    ValidationError,
)
from education_system.university_system.core.sql_safety import validate_table_name

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.modules.shared.utils.i18n import (
        get_text as _t,
        get_current_language,
        get_current_language_name,
        set_language,
        get_available_language_list,
        init_i18n,
    )
    from education_system.university_system.modules.shared.utils.gui_language_selector import (
        show_gui_language_selector,
    )
    I18N_AVAILABLE = True
    GUI_LANG_SELECTOR_AVAILABLE = True
    # Initialize i18n if not already done
    init_i18n()
except ImportError:
    I18N_AVAILABLE = False
    GUI_LANG_SELECTOR_AVAILABLE = False
    _t = lambda key, **kwargs: key  # Fallback: return key as-is
    get_current_language = lambda: "en"
    get_current_language_name = lambda: "English"
    set_language = lambda lang, save=True: False
    get_available_language_list = lambda: [("en", "English")]
    show_gui_language_selector = lambda parent=None: "en"

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
import os
import sys
from datetime import datetime, timedelta
import threading
import subprocess
import webbrowser
from pathlib import Path
from education_system.university_system.infrastructure.database.db import sqlite3
# This ensures full backward compatibility
try:
    from education_system.university_system.modules.domain.academics.services.module_scheduling import (
        ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES,
        display_enhanced_scheduling_menu  # Keep CLI available
    )
except ImportError:
    # If the original module isn't available, we'll define basic constants
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']
    ROOM_TYPES = ['Lecture Hall', 'Lab', 'Tutorial Room', 'Seminar Room', 'Workshop Room', 'Computer Lab', 'Other']
    
    # Import the ModuleScheduler class from the document
    try:
        from education_system.university_system.modules.domain.academics.services.module_scheduling import (ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES, display_enhanced_scheduling_menu)
    except Exception:
        class ModuleScheduler: pass

from education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui import ModuleSchedulingGUI

def create_management_tab(self):
    """Create the data management tab"""
    management_frame = ttk.Frame(self.notebook)
    self.notebook.add(management_frame, text=_t("scheduling.tabs.management"))
    
    # Backup section
    backup_frame = ttk.LabelFrame(management_frame, text=_t("scheduling.backup_restore"), padding=15)
    backup_frame.pack(fill=tk.X, padx=20, pady=10)

    backup_buttons = ttk.Frame(backup_frame)
    backup_buttons.pack(fill=tk.X)

    ttk.Button(backup_buttons, text=_t("scheduling.create_backup"),
              command=self.create_backup).pack(side=tk.LEFT, padx=5)
    ttk.Button(backup_buttons, text=_t("scheduling.list_backups"),
              command=self.list_backups).pack(side=tk.LEFT, padx=5)
    ttk.Button(backup_buttons, text=_t("scheduling.restore_backup"),
              command=self.restore_backup).pack(side=tk.LEFT, padx=5)

    # Data validation section
    validation_frame = ttk.LabelFrame(management_frame, text=_t("scheduling.data_validation"), padding=15)
    validation_frame.pack(fill=tk.X, padx=20, pady=10)

    validation_buttons = ttk.Frame(validation_frame)
    validation_buttons.pack(fill=tk.X)

    ttk.Button(validation_buttons, text=_t("scheduling.validate_data"),
              command=self.validate_data).pack(side=tk.LEFT, padx=5)
    ttk.Button(validation_buttons, text=_t("scheduling.clean_orphaned"),
              command=self.clean_orphaned_records).pack(side=tk.LEFT, padx=5)
    ttk.Button(validation_buttons, text=_t("scheduling.repair_issues"),
              command=self.repair_issues).pack(side=tk.LEFT, padx=5)

    # Import/Export section
    import_export_frame = ttk.LabelFrame(management_frame, text=_t("scheduling.import_export"), padding=15)
    import_export_frame.pack(fill=tk.X, padx=20, pady=10)

    import_export_buttons = ttk.Frame(import_export_frame)
    import_export_buttons.pack(fill=tk.X)

    ttk.Button(import_export_buttons, text=_t("scheduling.import_csv"),
              command=self.import_csv).pack(side=tk.LEFT, padx=5)
    ttk.Button(import_export_buttons, text=_t("scheduling.export_all_data"),
              command=self.export_all_data).pack(side=tk.LEFT, padx=5)
    ttk.Button(import_export_buttons, text=_t("scheduling.generate_reports"),
              command=self.generate_reports).pack(side=tk.LEFT, padx=5)

    # Templates section
    templates_frame = ttk.LabelFrame(management_frame, text=_t("scheduling.schedule_templates"), padding=15)
    templates_frame.pack(fill=tk.X, padx=20, pady=10)

    templates_buttons = ttk.Frame(templates_frame)
    templates_buttons.pack(fill=tk.X)

    ttk.Button(templates_buttons, text=_t("scheduling.save_template"),
              command=self.save_template).pack(side=tk.LEFT, padx=5)
    ttk.Button(templates_buttons, text=_t("scheduling.load_template"),
              command=self.load_template).pack(side=tk.LEFT, padx=5)
    ttk.Button(templates_buttons, text=_t("scheduling.list_templates"),
              command=self.list_templates).pack(side=tk.LEFT, padx=5)

    # Activity log
    log_frame = ttk.LabelFrame(management_frame, text=_t("scheduling.activity_log"), padding=15)
    log_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
    
    self.log_text = scrolledtext.ScrolledText(log_frame, height=15, state=tk.DISABLED)
    self.log_text.pack(fill=tk.BOTH, expand=True)

ModuleSchedulingGUI.create_management_tab = create_management_tab

def create_backup(self, backup_name=None, description=""):
    """Create a backup of the database"""
    if not backup_name:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"backup_{timestamp}"

    from education_system.university_system.modules.shared.constants import paths
    import shutil
    import os
    os.makedirs(str(paths.BACKUP_DATABASE_DIR), exist_ok=True)

    backup_path = os.path.join(str(paths.BACKUP_DATABASE_DIR), f"{backup_name}.db")

    try:
        # Check if source database exists
        if not os.path.exists(DEFAULT_DB_PATH):
            messagebox.showerror("Error", f"Database file not found: {DEFAULT_DB_PATH}", parent=self.root)
            return None

        # Copy the database file
        shutil.copy2(DEFAULT_DB_PATH, backup_path)

        # Get file size
        file_size = os.path.getsize(backup_path)

        # Record backup in database
        with transaction() as conn:
            cursor = conn.cursor()

            cursor.execute('''
            INSERT INTO backups (backup_name, backup_path, backup_size, description)
            VALUES (?, ?, ?, ?)
            ''', (backup_name, backup_path, file_size, description))

        messagebox.showinfo("Success", f"Backup created successfully:\n{backup_path}", parent=self.root)
        return backup_path

    except Exception as e:
        messagebox.showerror("Error", f"Error creating backup: {str(e)}", parent=self.root)
        return None

ModuleSchedulingGUI.create_backup = create_backup

def list_backups(self):
    """List all available backups in a dialog"""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
        SELECT backup_name, backup_date, backup_size, description
        FROM backups
        ORDER BY backup_date DESC
        ''')

        backups = cursor.fetchall()

    if not backups:
        messagebox.showinfo("Backups", "No backups found.", parent=self.root)
        return

    # Create dialog to show backups
    dialog = tk.Toplevel(self.root)
    dialog.title("Available Backups")
    dialog.geometry("800x400")
    dialog.transient(self.root)

    # Create treeview
    columns = ('Name', 'Date', 'Size (KB)', 'Description')
    tree = ttk.Treeview(dialog, columns=columns, show='headings')

    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=180)

    for backup in backups:
        name, date, size, desc = backup
        backup_date = datetime.fromisoformat(date).strftime("%Y-%m-%d %H:%M") if date else "N/A"
        size_kb = round(size / 1024, 2) if size else 0
        tree.insert('', tk.END, values=(name, backup_date, size_kb, desc or ''))

    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Buttons
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

ModuleSchedulingGUI.list_backups = list_backups

def restore_backup(self, backup_name=None):
    """Restore from a backup"""
    from education_system.university_system.modules.shared.constants import paths
    import shutil
    import os
    from tkinter import filedialog

    # If no backup_name provided, show file selection dialog
    if backup_name is None:
        backup_path = filedialog.askopenfilename(
            title="Select Backup File to Restore",
            initialdir=str(paths.BACKUP_DATABASE_DIR),
            filetypes=[
                ("Database Backup", "*.db"),
                ("All Files", "*.*")
            ]
        )

        if not backup_path:
            return False  # User cancelled

        # Extract backup name from path for display
        backup_name = os.path.basename(backup_path).replace('.db', '')
    else:
        backup_path = os.path.join(str(paths.BACKUP_DATABASE_DIR), f"{backup_name}.db")

    if not os.path.exists(backup_path):
        messagebox.showerror("Error", f"Backup file not found: {backup_path}", parent=self.root)
        return False

    # Confirm restoration
    confirm = messagebox.askyesno(
        "Confirm Restore",
        f"WARNING: This will replace the current database with the backup from {backup_name}\n\n"
        "A pre-restore backup will be created automatically.\n\n"
        "Are you sure you want to continue?"
    , parent=self.root)

    if not confirm:
        return False

    try:
        # Create a backup of current state before restoring
        self.create_backup("pre_restore_backup", "Automatic backup before restore")

        # Replace current database
        shutil.copy2(backup_path, DEFAULT_DB_PATH)

        messagebox.showinfo("Success", f"Database restored from backup: {backup_name}\n\nPlease restart the application.", parent=self.root)
        return True

    except Exception as e:
        messagebox.showerror("Error", f"Error restoring backup: {str(e)}", parent=self.root)
        return False

ModuleSchedulingGUI.restore_backup = restore_backup

def validate_data(self):
    """Validate data consistency"""
    try:
        self.update_status("Validating data...")
        
        issues = self.scheduler.validate_data_consistency()
        
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        
        if issues:
            self.log_text.insert(tk.END, "Data Consistency Issues Found:\n")
            self.log_text.insert(tk.END, "=" * 50 + "\n")
            for i, issue in enumerate(issues, 1):
                self.log_text.insert(tk.END, f"{i}. {issue}\n")
            self.log_text.insert(tk.END, "=" * 50 + "\n")
            
            if messagebox.askyesno("Issues Found", f"Found {len(issues)} data consistency issues.\n\nWould you like to fix them automatically?", parent=self.root):
                self.clean_orphaned_records()
        else:
            self.log_text.insert(tk.END, "No data consistency issues found.\n")
            messagebox.showinfo("Validation Complete", "No data consistency issues found.", parent=self.root)
        
        self.log_text.config(state=tk.DISABLED)
        self.notebook.select(7)  # Switch to management tab
        
        self.update_activity_log("Performed data validation")
        self.update_status("Ready")
        
    except Exception as e:
        messagebox.showerror("Error", f"Failed to validate data: {str(e)}", parent=self.root)
        self.update_status("Ready")

ModuleSchedulingGUI.validate_data = validate_data

def clean_orphaned_records(self):
    """Clean up orphaned records"""
    confirm = messagebox.askyesno(
        "Confirm Cleanup",
        "This will remove schedules with invalid room or instructor references.\n\n"
        "Are you sure you want to continue?"
    , parent=self.root)

    if not confirm:
        return

    try:
        with transaction() as conn:
            cursor = conn.cursor()

            # Remove schedules with invalid room references
            cursor.execute('''
            DELETE FROM module_schedule
            WHERE room_id NOT IN (SELECT id FROM rooms)
            ''')
            removed_room_refs = cursor.rowcount

            # Remove schedules with invalid instructor references
            cursor.execute('''
            DELETE FROM module_schedule
            WHERE instructor_id NOT IN (SELECT id FROM instructors)
            ''')
            removed_instructor_refs = cursor.rowcount

        message = f"Cleanup completed:\n\n" \
                 f"• Removed {removed_room_refs} schedules with invalid room references\n" \
                 f"• Removed {removed_instructor_refs} schedules with invalid instructor references"

        messagebox.showinfo("Cleanup Complete", message, parent=self.root)
        self.refresh_all_data()

    except Exception as e:
        messagebox.showerror("Error", f"Error during cleanup: {str(e)}", parent=self.root)

ModuleSchedulingGUI.clean_orphaned_records = clean_orphaned_records

def repair_issues(self):
    """Repair common data issues"""
    try:
        self.update_status("Repairing issues...")
        
        # Run validation and cleanup
        issues = self.scheduler.validate_data_consistency()
        if issues:
            self.scheduler.clean_orphaned_records()
            messagebox.showinfo("Success", "Common issues repaired.", parent=self.root)
        else:
            messagebox.showinfo("Info", "No issues found to repair.", parent=self.root)
        
        self.refresh_all_data()
        self.update_activity_log("Repaired data issues")
        self.update_status("Ready")
        
    except Exception as e:
        messagebox.showerror("Error", f"Failed to repair issues: {str(e)}", parent=self.root)
        self.update_status("Ready")

ModuleSchedulingGUI.repair_issues = repair_issues

def import_csv(self):
    """Import schedules from CSV file"""
    try:
        file_path = filedialog.askopenfilename(
            title="Select CSV file to import",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        
        if file_path:
            self.update_status("Importing CSV...")
            
            success = self.scheduler.import_schedules_from_csv(file_path)
            
            if success:
                messagebox.showinfo("Success", "CSV imported successfully!", parent=self.root)
                self.refresh_all_data()
                self.update_activity_log(f"Imported data from {os.path.basename(file_path)}")
            else:
                messagebox.showerror("Error", "Failed to import CSV file.", parent=self.root)
            
            self.update_status("Ready")
        
    except Exception as e:
        messagebox.showerror("Error", f"Failed to import CSV: {str(e)}", parent=self.root)
        self.update_status("Ready")

ModuleSchedulingGUI.import_csv = import_csv

def export_all_data(self):
    """Export all schedule data"""
    try:
        self.update_status("Exporting data...")
        
        filename = self.scheduler.export_all_schedules_to_csv()
        
        if filename:
            if messagebox.askyesno("Export Complete", f"Data exported successfully!\n\nFile: {filename}\n\nWould you like to open the file location?", parent=self.root):
                folder_path = os.path.dirname(os.path.abspath(filename))
                webbrowser.open(f"file://{folder_path}")
            
            self.update_activity_log("Exported all schedule data")
        else:
            messagebox.showerror("Error", "Failed to export data.", parent=self.root)
        
        self.update_status("Ready")
        
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export data: {str(e)}", parent=self.root)
        self.update_status("Ready")

ModuleSchedulingGUI.export_all_data = export_all_data

def import_schedules_from_csv(self):
    """Import schedules from CSV file"""
    filename = filedialog.askopenfilename(
        title="Select CSV File",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )

    if not filename:
        return

    try:
        import csv

        with open(filename, 'r') as f:
            reader = csv.DictReader(f)
            imported = 0
            errors = []

            with transaction() as conn:
                cursor = conn.cursor()

                for row in reader:
                    try:
                        # Validate required fields
                        module_code = row.get('module_code')
                        day = row.get('day_of_week')
                        start_time = row.get('start_time')
                        end_time = row.get('end_time')
                        room_id = row.get('room_id')
                        instructor_id = row.get('instructor_id')
                        session_type = row.get('session_type', 'Lecture')

                        if not all([module_code, day, start_time, end_time, room_id, instructor_id]):
                            errors.append(f"Row missing required fields: {row}")
                            continue

                        cursor.execute('''
                        INSERT INTO module_schedule
                        (module_code, day_of_week, start_time, end_time, room_id, instructor_id, session_type)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (module_code, day, start_time, end_time, int(room_id), int(instructor_id), session_type))

                        imported += 1

                    except Exception as e:
                        errors.append(f"Error importing row: {str(e)}")

        message = f"Import completed!\n\nImported: {imported} schedules"
        if errors:
            message += f"\nErrors: {len(errors)}\n\nFirst 5 errors:\n" + "\n".join(errors[:5])

        messagebox.showinfo("Import Complete", message, parent=self.root)
        self.refresh_all_data()

    except Exception as e:
        messagebox.showerror("Import Error", f"Failed to import CSV: {str(e)}", parent=self.root)

ModuleSchedulingGUI.import_schedules_from_csv = import_schedules_from_csv

def export_all_schedules_to_csv(self):
    """Export all schedules to CSV file"""
    filename = filedialog.asksaveasfilename(
        title="Export Schedules to CSV",
        defaultextension=".csv",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )

    if not filename:
        return

    try:
        import csv

        with get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute('''
            SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week,
                   ms.start_time, ms.end_time, ms.room_id, r.building, r.room_number,
                   ms.instructor_id, i.first_name, i.last_name, ms.session_type
            FROM module_schedule ms
            LEFT JOIN modules m ON ms.module_code = m.module_code
            LEFT JOIN rooms r ON ms.room_id = r.id
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            ORDER BY ms.day_of_week, ms.start_time
            ''')

            schedules = cursor.fetchall()

        with open(filename, 'w', newline='') as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow([
                'id', 'module_code', 'module_name', 'day_of_week', 'start_time', 'end_time',
                'room_id', 'building', 'room_number', 'instructor_id', 'instructor_first_name',
                'instructor_last_name', 'session_type'
            ])

            # Write data
            writer.writerows(schedules)

        messagebox.showinfo("Export Complete", f"Exported {len(schedules)} schedules to:\n{filename}", parent=self.root)

    except Exception as e:
        messagebox.showerror("Export Error", f"Failed to export CSV: {str(e)}", parent=self.root)

ModuleSchedulingGUI.export_all_schedules_to_csv = export_all_schedules_to_csv

def _migrate_database(self):
    """Migrate existing database tables to add missing columns for GUI compatibility"""
    try:
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()

            # Check if schedule_conflicts table has wrong schema (from course planning)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schedule_conflicts'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(schedule_conflicts)")
                conflict_columns = {row[1] for row in cursor.fetchall()}

                # Check if it has course planning schema (conflict_id instead of id)
                if 'conflict_id' in conflict_columns and 'plan_id' in conflict_columns:
                    # Rename the course planning table
                    cursor.execute("ALTER TABLE schedule_conflicts RENAME TO course_plan_conflicts")
                    print("Renamed course planning conflicts table to course_plan_conflicts")

                    # Create the module scheduling conflicts table
                    cursor.execute('''
                    CREATE TABLE IF NOT EXISTS schedule_conflicts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        conflict_type TEXT,
                        description TEXT,
                        affected_schedules TEXT,
                        resolved BOOLEAN DEFAULT 0,
                        resolution_notes TEXT,
                        detected_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        resolved_date TIMESTAMP
                    )
                    ''')
                    print("Created module scheduling conflicts table")
                    conn.commit()

            # Check and add missing columns to instructors table
            cursor.execute("PRAGMA table_info(instructors)")
            existing_columns = {row[1] for row in cursor.fetchall()}

            migrations = []
            if 'email' not in existing_columns:
                migrations.append("ALTER TABLE instructors ADD COLUMN email TEXT")
            if 'max_hours_per_week' not in existing_columns:
                migrations.append("ALTER TABLE instructors ADD COLUMN max_hours_per_week INTEGER DEFAULT 40")
            if 'preferred_days' not in existing_columns:
                migrations.append("ALTER TABLE instructors ADD COLUMN preferred_days TEXT")
            if 'preferred_times' not in existing_columns:
                migrations.append("ALTER TABLE instructors ADD COLUMN preferred_times TEXT")
            if 'is_active' not in existing_columns:
                migrations.append("ALTER TABLE instructors ADD COLUMN is_active BOOLEAN DEFAULT 1")
            if 'specialization' not in existing_columns:
                migrations.append("ALTER TABLE instructors ADD COLUMN specialization TEXT DEFAULT ''")
            if 'max_courses_per_semester' not in existing_columns:
                migrations.append("ALTER TABLE instructors ADD COLUMN max_courses_per_semester INTEGER DEFAULT 4")

            # Check if rooms table exists and add is_active column
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='rooms'")
            if cursor.fetchone():
                cursor.execute("PRAGMA table_info(rooms)")
                existing_columns = {row[1] for row in cursor.fetchall()}
                if 'is_active' not in existing_columns:
                    migrations.append("ALTER TABLE rooms ADD COLUMN is_active BOOLEAN DEFAULT 1")

            # Fix foreign key issues by ensuring modules table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='modules'")
            if not cursor.fetchone():
                # Create modules table if it doesn't exist
                cursor.execute('''
                CREATE TABLE modules (
                    module_code TEXT PRIMARY KEY,
                    module_name TEXT NOT NULL,
                    description TEXT,
                    credits INTEGER DEFAULT 0,
                    instructor_id INTEGER,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (instructor_id) REFERENCES instructors (id)
                )
                ''')
                print("Created modules table")

            # Check module_schedule table and fix foreign key references
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='module_schedule'")
            if cursor.fetchone():
                # Check if there are any orphaned records in module_schedule
                cursor.execute('''
                SELECT DISTINCT module_code FROM module_schedule
                WHERE module_code NOT IN (SELECT module_code FROM modules WHERE module_code IS NOT NULL)
                ''')
                orphaned_modules = cursor.fetchall()

                # Insert missing modules
                for (module_code,) in orphaned_modules:
                    if module_code:  # Only if module_code is not None/empty
                        cursor.execute('''
                        INSERT OR IGNORE INTO modules (module_code, module_name, is_active)
                        VALUES (?, ?, 1)
                        ''', (module_code, f"Module {module_code}"))
                        print(f"Added missing module: {module_code}")

            # Fix attendance table foreign key references
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='attendance'")
            if cursor.fetchone():
                cursor.execute('''
                SELECT DISTINCT module_code FROM attendance
                WHERE module_code IS NOT NULL
                AND module_code NOT IN (SELECT module_code FROM modules WHERE module_code IS NOT NULL)
                ''')
                orphaned_attendance_modules = cursor.fetchall()

                for (module_code,) in orphaned_attendance_modules:
                    if module_code:
                        cursor.execute('''
                        INSERT OR IGNORE INTO modules (module_code, module_name, is_active)
                        VALUES (?, ?, 1)
                        ''', (module_code, f"Module {module_code}"))
                        print(f"Added missing module for attendance: {module_code}")

            # Fix document_repository table foreign key references
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='document_repository'")
            if cursor.fetchone():
                cursor.execute('''
                SELECT DISTINCT module_code FROM document_repository
                WHERE module_code IS NOT NULL
                AND module_code NOT IN (SELECT module_code FROM modules WHERE module_code IS NOT NULL)
                ''')
                orphaned_doc_modules = cursor.fetchall()

                for (module_code,) in orphaned_doc_modules:
                    if module_code:
                        cursor.execute('''
                        INSERT OR IGNORE INTO modules (module_code, module_name, is_active)
                        VALUES (?, ?, 1)
                        ''', (module_code, f"Module {module_code}"))
                        print(f"Added missing module for document_repository: {module_code}")

            # Check for other tables that might reference modules
            cursor.execute('''
            SELECT DISTINCT tbl_name FROM sqlite_master
            WHERE type='table' AND sql LIKE '%module_code%'
            AND tbl_name NOT IN ('modules', 'module_schedule', 'attendance', 'document_repository')
            ''')
            other_tables = cursor.fetchall()

            for (table_name,) in other_tables:
                try:
                    safe_table = validate_table_name(table_name, conn=conn)
                    cursor.execute('''
                    SELECT DISTINCT module_code FROM [''' + safe_table + ''']
                    WHERE module_code IS NOT NULL
                    AND module_code NOT IN (SELECT module_code FROM modules WHERE module_code IS NOT NULL)
                    ''')
                    orphaned_other_modules = cursor.fetchall()

                    for (module_code,) in orphaned_other_modules:
                        if module_code:
                            cursor.execute('''
                            INSERT OR IGNORE INTO modules (module_code, module_name, is_active)
                            VALUES (?, ?, 1)
                            ''', (module_code, f"Module {module_code}"))
                            print(f"Added missing module for {table_name}: {module_code}")
                except Exception as e:
                    print(f"Could not check table {table_name}: {e}")

            # Only execute migrations if there are any needed
            if migrations:
                # Execute all migrations
                for migration in migrations:
                    try:
                        cursor.execute(migration)
                        print(f"GUI Migration executed: {migration}")
                    except sqlite3.Error as e:
                        # If migration fails, it might have been done already by the service
                        if "duplicate column name" in str(e).lower():
                            print(f"GUI Migration skipped (already exists): {migration}")
                        else:
                            print(f"GUI Migration failed: {migration} - {e}")

                conn.commit()

    except Exception as e:
        print(f"GUI Migration error: {e}")

ModuleSchedulingGUI._migrate_database = _migrate_database

def open_activity_log_window(self):
    """Open activity log in a new window"""
    try:
        # Create new window
        activity_window = tk.Toplevel(self.root)
        activity_window.title("Activity Log - Module Scheduling System")
        activity_window.geometry("1000x600")
        activity_window.transient(self.root)

        main_frame = ttk.Frame(activity_window, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(main_frame, text="System Activity Log", font=('Arial', 14, 'bold'))
        title_label.pack(pady=10)

        # Controls frame
        controls_frame = ttk.Frame(main_frame)
        controls_frame.pack(fill=tk.X, pady=5)

        ttk.Button(controls_frame, text="🔄 Refresh", command=lambda: self._refresh_activity_log(activity_tree)).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="🗑️ Clear Old Logs", command=lambda: self._clear_old_activity_logs(activity_tree)).pack(side=tk.LEFT, padx=5)
        ttk.Button(controls_frame, text="📥 Export", command=lambda: self._export_activity_log()).pack(side=tk.LEFT, padx=5)

        # Activity log treeview
        tree_frame = ttk.Frame(main_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ("Timestamp", "Action", "Entity", "Details", "User")
        activity_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=20)

        for col in columns:
            activity_tree.heading(col, text=col)
            if col == "Details":
                activity_tree.column(col, width=300)
            elif col == "Timestamp":
                activity_tree.column(col, width=150)
            else:
                activity_tree.column(col, width=120)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=activity_tree.yview)
        activity_tree.configure(yscrollcommand=scrollbar.set)

        activity_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Load initial data
        self._refresh_activity_log(activity_tree)

        # Center window
        activity_window.update_idletasks()
        x = (activity_window.winfo_screenwidth() // 2) - (activity_window.winfo_width() // 2)
        y = (activity_window.winfo_screenheight() // 2) - (activity_window.winfo_height() // 2)
        activity_window.geometry(f"+{x}+{y}")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to open activity log: {str(e)}", parent=self.root)

ModuleSchedulingGUI.open_activity_log_window = open_activity_log_window

def _refresh_activity_log(self, tree):
    """Refresh the activity log tree"""
    try:
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)

        # Get activity logs from database
        # Schema: id, user_id, username, action, details, timestamp, ip_address
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, action, username, details, user_id
                FROM activity_log
                ORDER BY timestamp DESC
                LIMIT 1000
            ''')
            logs = cursor.fetchall()

        for log in logs:
            timestamp, action, username, details, user_id = log
            # Parse details if JSON
            try:
                import json
                details_dict = json.loads(details) if details else {}
                details_str = ', '.join([f"{k}: {v}" for k, v in details_dict.items()])
            except (ValueError, TypeError, KeyError):
                details_str = details if details else ''

            # Display format: Timestamp, Action, Entity (from details or action), Details, User
            entity = username or f"User {user_id}" if user_id else 'System'

            tree.insert("", tk.END, values=(
                timestamp,
                action,
                entity,
                details_str[:100] + ('...' if len(details_str) > 100 else ''),
                username or user_id or 'System'
            ))

    except Exception as e:
        messagebox.showerror("Error", f"Failed to refresh activity log: {str(e)}", parent=self.root)

ModuleSchedulingGUI._refresh_activity_log = _refresh_activity_log

def _clear_old_activity_logs(self, tree):
    """Clear activity logs older than 30 days"""
    if not messagebox.askyesno("Confirm", "Clear activity logs older than 30 days?", parent=self.root):
        return

    try:
        from education_system.university_system.infrastructure.database.db import transaction
        from datetime import datetime, timedelta
        cutoff_date = (datetime.now() - timedelta(days=30)).isoformat()

        with transaction() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM activity_log WHERE timestamp < ?', (cutoff_date,))
            deleted_count = cursor.rowcount

        messagebox.showinfo("Success", f"Deleted {deleted_count} old activity log entries.", parent=self.root)
        self._refresh_activity_log(tree)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to clear old logs: {str(e)}", parent=self.root)

ModuleSchedulingGUI._clear_old_activity_logs = _clear_old_activity_logs

def _export_activity_log(self):
    """Export activity log to CSV"""
    try:
        from tkinter import filedialog
        import csv

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if not filename:
            return

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, user_id, username, action, details, timestamp, ip_address
                FROM activity_log
                ORDER BY timestamp DESC
            ''')
            logs = cursor.fetchall()

        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['ID', 'User ID', 'Username', 'Action', 'Details', 'Timestamp', 'IP Address'])
            writer.writerows(logs)

        messagebox.showinfo("Success", f"Activity log exported to {filename}", parent=self.root)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to export activity log: {str(e)}", parent=self.root)

ModuleSchedulingGUI._export_activity_log = _export_activity_log

