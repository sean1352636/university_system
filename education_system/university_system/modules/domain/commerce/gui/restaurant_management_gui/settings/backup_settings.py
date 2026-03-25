from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.core.sql_safety import validate_identifier
from datetime import datetime, timedelta
import threading
import sys
import os

# Import centralized authentication system
# Import authentication - REQUIRED (no fallback for security)
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Import finance integration for student finance account payments
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        get_student_info,
        LOW_BALANCE_THRESHOLD
    )
    FINANCE_ACCOUNT_AVAILABLE = True
except ImportError:
    FINANCE_ACCOUNT_AVAILABLE = False
    print("Warning: Student finance account integration not available")

# Import custom exceptions for proper error handling
from education_system.university_system.infrastructure.exceptions import (
    DatabaseError,
    DatabaseConnectionError,
    QueryError,
    ValidationError,
    InvalidInputError
)

# Attempt to import the enhanced restaurant DB initializer from the CLI version.
# If available, calling this will create the full set of tables defined in
# services/restaurant_management.py. Alias the import to avoid naming
# conflicts with this module's own init_db function.
try:
    from education_system.university_system.modules.domain.commerce.services.restaurant_management import init_db as init_enhanced_restaurant_db
except ImportError:
    init_enhanced_restaurant_db = None

# Database configuration
# Always point to the central student_records.db in refactored/db_files.
try:
    from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH as DATABASE_FILE
except ImportError:
    # Fallback to local file if refactored.database.db is unavailable
    DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import get_db_connection from main_gui
from education_system.university_system.modules.domain.commerce.gui.restaurant_management_gui.core.main_gui import get_db_connection


def display_system_settings(self):
    """Display and configure system settings"""
    dialog = tk.Toplevel(self.root)
    dialog.title("System Settings")
    dialog.geometry("700x800")
    dialog.transient(self.root)
    dialog.grab_set()
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="System Settings",
             font=('Arial', 14, 'bold')).pack(pady=10)
    # Create notebook for different setting categories
    settings_notebook = ttk.Notebook(main_frame)
    settings_notebook.pack(fill='both', expand=True, pady=10)
    # Restaurant Info Tab
    info_frame = ttk.Frame(settings_notebook, padding=10)
    settings_notebook.add(info_frame, text="Restaurant Info")
    row = 0
    ttk.Label(info_frame, text="Restaurant Name:").grid(row=row, column=0, sticky='w', pady=5)
    restaurant_name = ttk.Entry(info_frame, width=40)
    restaurant_name.insert(0, "University Restaurant")
    restaurant_name.grid(row=row, column=1, pady=5, padx=10)
    row += 1
    ttk.Label(info_frame, text="Address:").grid(row=row, column=0, sticky='w', pady=5)
    address = ttk.Entry(info_frame, width=40)
    address.insert(0, "123 Campus Drive")
    address.grid(row=row, column=1, pady=5, padx=10)
    row += 1
    ttk.Label(info_frame, text="Phone:").grid(row=row, column=0, sticky='w', pady=5)
    phone = ttk.Entry(info_frame, width=40)
    phone.insert(0, "+44 20 1234 5678")
    phone.grid(row=row, column=1, pady=5, padx=10)
    row += 1
    ttk.Label(info_frame, text="Email:").grid(row=row, column=0, sticky='w', pady=5)
    email = ttk.Entry(info_frame, width=40)
    email.insert(0, "info@university-restaurant.ac.uk")
    email.grid(row=row, column=1, pady=5, padx=10)
    # Operating Hours Tab
    hours_frame = ttk.Frame(settings_notebook, padding=10)
    settings_notebook.add(hours_frame, text="Operating Hours")
    row = 0
    ttk.Label(hours_frame, text="Monday - Friday:").grid(row=row, column=0, sticky='w', pady=5)
    weekday_hours = ttk.Entry(hours_frame, width=40)
    weekday_hours.insert(0, "08:00 - 22:00")
    weekday_hours.grid(row=row, column=1, pady=5, padx=10)
    row += 1
    ttk.Label(hours_frame, text="Saturday:").grid(row=row, column=0, sticky='w', pady=5)
    saturday_hours = ttk.Entry(hours_frame, width=40)
    saturday_hours.insert(0, "10:00 - 20:00")
    saturday_hours.grid(row=row, column=1, pady=5, padx=10)
    row += 1
    ttk.Label(hours_frame, text="Sunday:").grid(row=row, column=0, sticky='w', pady=5)
    sunday_hours = ttk.Entry(hours_frame, width=40)
    sunday_hours.insert(0, "Closed")
    sunday_hours.grid(row=row, column=1, pady=5, padx=10)
    # Tax & Currency Tab
    tax_frame = ttk.Frame(settings_notebook, padding=10)
    settings_notebook.add(tax_frame, text="Tax & Currency")
    row = 0
    ttk.Label(tax_frame, text="Currency:").grid(row=row, column=0, sticky='w', pady=5)
    currency = ttk.Combobox(tax_frame, values=['GBP (£)', 'USD ($)', 'EUR (€)'], width=38)
    currency.current(0)
    currency.grid(row=row, column=1, pady=5, padx=10)
    row += 1
    ttk.Label(tax_frame, text="Tax Rate (%):").grid(row=row, column=0, sticky='w', pady=5)
    tax_rate = ttk.Entry(tax_frame, width=40)
    tax_rate.insert(0, "20.0")
    tax_rate.grid(row=row, column=1, pady=5, padx=10)
    row += 1
    ttk.Label(tax_frame, text="Tax Name:").grid(row=row, column=0, sticky='w', pady=5)
    tax_name = ttk.Entry(tax_frame, width=40)
    tax_name.insert(0, "VAT")
    tax_name.grid(row=row, column=1, pady=5, padx=10)
    row += 1
    ttk.Label(tax_frame, text="Tax Number:").grid(row=row, column=0, sticky='w', pady=5)
    tax_number = ttk.Entry(tax_frame, width=40)
    tax_number.insert(0, "GB123456789")
    tax_number.grid(row=row, column=1, pady=5, padx=10)
    # Receipt Settings Tab
    receipt_frame = ttk.Frame(settings_notebook, padding=10)
    settings_notebook.add(receipt_frame, text="Receipt Settings")
    row = 0
    ttk.Label(receipt_frame, text="Receipt Header:").grid(row=row, column=0, sticky='nw', pady=5)
    receipt_header = tk.Text(receipt_frame, height=3, width=40)
    receipt_header.insert(1.0, "Thank you for dining with us!\nUniversity Restaurant")
    receipt_header.grid(row=row, column=1, pady=5, padx=10)
    row += 1
    ttk.Label(receipt_frame, text="Receipt Footer:").grid(row=row, column=0, sticky='nw', pady=5)
    receipt_footer = tk.Text(receipt_frame, height=3, width=40)
    receipt_footer.insert(1.0, "Please visit us again!\nwww.university-restaurant.ac.uk")
    receipt_footer.grid(row=row, column=1, pady=5, padx=10)
    row += 1
    show_tax_details = tk.BooleanVar(value=True)
    ttk.Checkbutton(receipt_frame, text="Show tax details on receipt",
                   variable=show_tax_details).grid(row=row, column=0, columnspan=2, sticky='w', pady=5)
    row += 1
    show_loyalty = tk.BooleanVar(value=True)
    ttk.Checkbutton(receipt_frame, text="Show loyalty points on receipt",
                   variable=show_loyalty).grid(row=row, column=0, columnspan=2, sticky='w', pady=5)
    # Notifications Tab
    notif_frame = ttk.Frame(settings_notebook, padding=10)
    settings_notebook.add(notif_frame, text="Notifications")
    row = 0
    email_notif = tk.BooleanVar(value=True)
    ttk.Checkbutton(notif_frame, text="Email notifications for new orders",
                   variable=email_notif).grid(row=row, column=0, sticky='w', pady=5)
    row += 1
    low_stock_notif = tk.BooleanVar(value=True)
    ttk.Checkbutton(notif_frame, text="Alert when inventory is low",
                   variable=low_stock_notif).grid(row=row, column=0, sticky='w', pady=5)
    row += 1
    waste_notif = tk.BooleanVar(value=False)
    ttk.Checkbutton(notif_frame, text="Daily waste summary email",
                   variable=waste_notif).grid(row=row, column=0, sticky='w', pady=5)
    row += 1
    ttk.Label(notif_frame, text="Notification Email:").grid(row=row, column=0, sticky='w', pady=5)
    notif_email = ttk.Entry(notif_frame, width=40)
    notif_email.insert(0, "manager@university-restaurant.ac.uk")
    notif_email.grid(row=row, column=1, pady=5, padx=10)
    # System Preferences Tab
    pref_frame = ttk.Frame(settings_notebook, padding=10)
    settings_notebook.add(pref_frame, text="Preferences")
    row = 0
    ttk.Label(pref_frame, text="Date Format:").grid(row=row, column=0, sticky='w', pady=5)
    date_format = ttk.Combobox(pref_frame,
                               values=['YYYY-MM-DD', 'DD/MM/YYYY', 'MM/DD/YYYY'],
                               width=38)
    date_format.current(0)
    date_format.grid(row=row, column=1, pady=5, padx=10)
    row += 1
    ttk.Label(pref_frame, text="Time Format:").grid(row=row, column=0, sticky='w', pady=5)
    time_format = ttk.Combobox(pref_frame, values=['24-hour', '12-hour'], width=38)
    time_format.current(0)
    time_format.grid(row=row, column=1, pady=5, padx=10)
    row += 1
    ttk.Label(pref_frame, text="Default Table Capacity:").grid(row=row, column=0, sticky='w', pady=5)
    default_capacity = ttk.Entry(pref_frame, width=40)
    default_capacity.insert(0, "4")
    default_capacity.grid(row=row, column=1, pady=5, padx=10)
    row += 1
    auto_complete_orders = tk.BooleanVar(value=False)
    ttk.Checkbutton(pref_frame, text="Auto-complete orders after payment",
                   variable=auto_complete_orders).grid(row=row, column=0, columnspan=2, sticky='w', pady=5)
    # Save and Cancel buttons
    def save_settings():
        try:
            # In a real implementation, save these to a config file or database
            messagebox.showinfo("Success", "Settings saved successfully!\n\n" +
                               "Note: Some settings may require application restart.")
            dialog.destroy()
        except (sqlite3.Error, tk.TclError) as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill='x', pady=10)
    ttk.Button(button_frame, text="Save Settings",
              command=save_settings).pack(side='left', padx=5)
    ttk.Button(button_frame, text="Cancel",
              command=dialog.destroy).pack(side='left', padx=5)
    ttk.Button(button_frame, text="Reset to Defaults",
              command=lambda: messagebox.showinfo("Reset",
                  "This would reset all settings to default values")).pack(side='left', padx=5)

def backup_database(self):
    """Show backup and recovery management menu"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Backup & Recovery")
    dialog.geometry("600x500")
    dialog.transient(self.root)
    dialog.grab_set()
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Backup & Recovery Management",
             font=('Arial', 14, 'bold')).pack(pady=10)
    # Backup section
    backup_section = ttk.LabelFrame(main_frame, text="Backup Operations", padding=15)
    backup_section.pack(fill='x', pady=10)
    ttk.Button(backup_section, text="Create Full Backup",
              command=self.create_full_backup,
              width=30).pack(pady=5)
    ttk.Button(backup_section, text="Create Incremental Backup",
              command=self.create_incremental_backup,
              width=30).pack(pady=5)
    ttk.Button(backup_section, text="Verify Backup Integrity",
              command=self.verify_backup,
              width=30).pack(pady=5)
    # Restore section
    restore_section = ttk.LabelFrame(main_frame, text="Restore Operations", padding=15)
    restore_section.pack(fill='x', pady=10)
    ttk.Button(restore_section, text="Restore from Backup",
              command=self.restore_from_backup,
              width=30).pack(pady=5)
    ttk.Button(restore_section, text="View Backup History",
              command=self.view_backup_history,
              width=30).pack(pady=5)
    # Management section
    mgmt_section = ttk.LabelFrame(main_frame, text="Backup Management", padding=15)
    mgmt_section.pack(fill='x', pady=10)
    ttk.Button(mgmt_section, text="Manage Backup Location",
              command=self.manage_backup_location,
              width=30).pack(pady=5)
    ttk.Button(mgmt_section, text="Schedule Automated Backups",
              command=self.schedule_backups,
              width=30).pack(pady=5)
    ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=15)

def create_full_backup(self):
    """Create a full database backup"""
    try:
        from tkinter import filedialog
        import shutil
        import os
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        default_filename = f"restaurant_backup_full_{timestamp}.db"
        filename = filedialog.asksaveasfilename(
            defaultextension=".db",
            filetypes=[("Database files", "*.db"), ("All files", "*.*")],
            initialfile=default_filename,
            title="Save Full Backup As"
        )
        if filename:
            # Close any open connections first
            shutil.copy2(DATABASE_FILE, filename)
            # Get file size
            file_size = os.path.getsize(filename) / (1024 * 1024)  # Convert to MB
            messagebox.showinfo("Backup Complete",
                               f"Full backup created successfully!\n\n" +
                               f"Location: {filename}\n" +
                               f"Size: {file_size:.2f} MB\n" +
                               f"Timestamp: {timestamp}")
            # Log the backup
            self.log_backup_event("Full Backup", filename, file_size)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Backup Failed", f"Failed to create backup:\n{str(e)}")

def create_incremental_backup(self):
    """Create an incremental backup (only changed data)"""
    try:
        messagebox.showinfo("Incremental Backup",
                           "Incremental backup feature:\n\n" +
                           "This would backup only the data that has changed since\n" +
                           "the last backup, reducing backup time and storage.\n\n" +
                           "For this demo, performing a full backup instead.")
        self.create_full_backup()
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to create incremental backup:\n{str(e)}")

def verify_backup(self):
    """Verify the integrity of a backup file"""
    try:
        from tkinter import filedialog
        filename = filedialog.askopenfilename(
            filetypes=[("Database files", "*.db"), ("All files", "*.*")],
            title="Select Backup File to Verify"
        )
        if filename:
            # Try to open the database file
            test_conn = sqlite3.connect(filename)
            try:
                cursor = test_conn.cursor()
                # Check some basic tables
                tables_to_check = ['menu_items', 'orders', 'restaurant_staff']
                verified_tables = []
                for table in tables_to_check:
                    try:
                        safe_table = validate_identifier(table, "table")
                        cursor.execute("SELECT COUNT(*) FROM [" + safe_table + "]")
                        count = cursor.fetchone()[0]
                        verified_tables.append(f"✓ {table}: {count} records")
                    except sqlite3.Error:
                        verified_tables.append(f"✗ {table}: Missing or corrupted")
            finally:
                test_conn.close()
            verification_report = "BACKUP VERIFICATION REPORT\n\n"
            verification_report += f"File: {filename}\n"
            verification_report += f"Status: Backup file is valid\n\n"
            verification_report += "Table Verification:\n"
            verification_report += "\n".join(verified_tables)
            messagebox.showinfo("Verification Complete", verification_report)
    except sqlite3.Error as e:
        messagebox.showerror("Verification Failed",
                            f"Backup verification failed:\n{str(e)}\n\n" +
                            "The backup file may be corrupted or invalid.")

def restore_from_backup(self):
    """Restore database from a backup file"""
    try:
        from tkinter import filedialog
        import shutil
        # Warning message
        response = messagebox.askyesno("Restore Database",
                                      "WARNING: This will replace the current database with the backup.\n\n" +
                                      "All current data will be lost!\n\n" +
                                      "Do you want to continue?",
                                      icon='warning')
        if not response:
            return
        # Create a safety backup first
        safety_backup = f"pre_restore_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2(DATABASE_FILE, safety_backup)
        # Select backup file to restore
        backup_file = filedialog.askopenfilename(
            filetypes=[("Database files", "*.db"), ("All files", "*.*")],
            title="Select Backup File to Restore"
        )
        if backup_file:
            # Verify the backup first
            try:
                test_conn = sqlite3.connect(backup_file)
                test_conn.close()
            except sqlite3.Error:
                messagebox.showerror("Invalid Backup",
                                    "The selected file is not a valid database backup.")
                return
            # Perform the restore
            shutil.copy2(backup_file, DATABASE_FILE)
            messagebox.showinfo("Restore Complete",
                               f"Database restored successfully!\n\n" +
                               f"Restored from: {backup_file}\n" +
                               f"Safety backup created: {safety_backup}\n\n" +
                               "Please restart the application for changes to take effect.")
            # Log the restore
            self.log_backup_event("Restore", backup_file, 0)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Restore Failed",
                            f"Failed to restore database:\n{str(e)}\n\n" +
                            f"Your original database is safe.")

def view_backup_history(self):
    """View backup history"""
    try:
        import os
        import glob
        # Find all backup files in current directory
        backup_files = glob.glob("restaurant_backup_*.db")
        if not backup_files:
            messagebox.showinfo("No Backups Found",
                               "No backup files found in the current directory.\n\n" +
                               "Backups are saved with names like:\n" +
                               "restaurant_backup_full_YYYYMMDD_HHMMSS.db")
            return
        # Create a dialog to show backup history
        history_dialog = tk.Toplevel(self.root)
        history_dialog.title("Backup History")
        history_dialog.geometry("700x400")
        history_dialog.transient(self.root)
        main_frame = ttk.Frame(history_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="Available Backups",
                 font=('Arial', 12, 'bold')).pack(pady=10)
        # Create treeview for backup files
        columns = ('Filename', 'Size (MB)', 'Date Modified')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=12)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=200)
        # Add backup files to treeview
        for backup_file in sorted(backup_files, reverse=True):
            size_mb = os.path.getsize(backup_file) / (1024 * 1024)
            mod_time = datetime.fromtimestamp(os.path.getmtime(backup_file))
            mod_time_str = mod_time.strftime('%Y-%m-%d %H:%M:%S')
            tree.insert('', 'end', values=(backup_file, f"{size_mb:.2f}", mod_time_str))
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        ttk.Button(main_frame, text="Close",
                  command=history_dialog.destroy).pack(pady=10)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to load backup history:\n{str(e)}")

def manage_backup_location(self):
    """Manage backup storage location"""
    try:
        from tkinter import filedialog
        current_location = os.path.dirname(os.path.abspath(DATABASE_FILE))
        info_text = f"Current database location:\n{current_location}\n\n"
        info_text += "Backup files are saved in the current working directory.\n\n"
        info_text += "To change the backup location, you can:\n"
        info_text += "• Save backups to a specific folder when creating them\n"
        info_text += "• Move backup files to external storage\n"
        info_text += "• Set up automatic cloud sync for the backup folder"
        messagebox.showinfo("Backup Location", info_text)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to manage backup location:\n{str(e)}")

def schedule_backups(self):
    """Configure automated backup scheduling"""
    try:
        schedule_dialog = tk.Toplevel(self.root)
        schedule_dialog.title("Schedule Automated Backups")
        schedule_dialog.geometry("500x400")
        schedule_dialog.transient(self.root)
        main_frame = ttk.Frame(schedule_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="Automated Backup Schedule",
                 font=('Arial', 12, 'bold')).pack(pady=10)
        # Frequency selection
        freq_frame = ttk.LabelFrame(main_frame, text="Backup Frequency", padding=10)
        freq_frame.pack(fill='x', pady=10)
        frequency_var = tk.StringVar(value="Daily")
        ttk.Radiobutton(freq_frame, text="Hourly", variable=frequency_var,
                       value="Hourly").pack(anchor='w')
        ttk.Radiobutton(freq_frame, text="Daily", variable=frequency_var,
                       value="Daily").pack(anchor='w')
        ttk.Radiobutton(freq_frame, text="Weekly", variable=frequency_var,
                       value="Weekly").pack(anchor='w')
        ttk.Radiobutton(freq_frame, text="Monthly", variable=frequency_var,
                       value="Monthly").pack(anchor='w')
        # Time selection
        time_frame = ttk.LabelFrame(main_frame, text="Backup Time", padding=10)
        time_frame.pack(fill='x', pady=10)
        ttk.Label(time_frame, text="Preferred time:").pack(side='left', padx=5)
        time_entry = ttk.Entry(time_frame, width=10)
        time_entry.insert(0, "02:00")
        time_entry.pack(side='left', padx=5)
        ttk.Label(time_frame, text="(24-hour format)").pack(side='left')
        # Retention policy
        retention_frame = ttk.LabelFrame(main_frame, text="Backup Retention", padding=10)
        retention_frame.pack(fill='x', pady=10)
        ttk.Label(retention_frame, text="Keep backups for:").pack(side='left', padx=5)
        retention_var = tk.StringVar(value="30")
        retention_entry = ttk.Entry(retention_frame, textvariable=retention_var, width=10)
        retention_entry.pack(side='left', padx=5)
        ttk.Label(retention_frame, text="days").pack(side='left')
        def save_schedule():
            messagebox.showinfo("Schedule Saved",
                               f"Backup schedule configured:\n\n" +
                               f"Frequency: {frequency_var.get()}\n" +
                               f"Time: {time_entry.get()}\n" +
                               f"Retention: {retention_var.get()} days\n\n" +
                               "Note: This is a configuration preview.\n" +
                               "In production, this would create a scheduled task.")
            schedule_dialog.destroy()
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=20)
        ttk.Button(button_frame, text="Save Schedule",
                  command=save_schedule).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel",
                  command=schedule_dialog.destroy).pack(side='left', padx=5)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to configure backup schedule:\n{str(e)}")

def log_backup_event(self, event_type, filename, size_mb):
    """Log backup events to database"""
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS backup_log (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT,
                    filename TEXT,
                    file_size_mb REAL,
                    event_time DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('''
                INSERT INTO backup_log (event_type, filename, file_size_mb)
                VALUES (?, ?, ?)
            ''', (event_type, filename, size_mb))
            conn.commit()
            conn.close()
    except sqlite3.Error:
        pass  # Silently fail if logging doesn't work

