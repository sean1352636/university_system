from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from education_system.systems.university.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import threading
import sys
import os

# Import centralized authentication system
# Import authentication - REQUIRED (no fallback for security)
from education_system.systems.university.infrastructure.auth import UserAuth, get_global_auth
from education_system.systems.university.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.systems.university.infrastructure.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from education_system.systems.university.infrastructure.utils.gui_language_selector import show_gui_language_selector

# Import finance integration for student finance account payments
try:
    from education_system.systems.university.infrastructure.utils.finance_integration import (
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
from education_system.systems.university.infrastructure.exceptions import (
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
    from education_system.systems.university.domain.operations.commerce.services.restaurant_management import init_db as init_enhanced_restaurant_db
except ImportError:
    init_enhanced_restaurant_db = None

# Database configuration
# Always point to the central student_records.db in refactored/db_files.
try:
    from education_system.systems.university.infrastructure.database.db import DEFAULT_DB_PATH as DATABASE_FILE
except ImportError:
    # Fallback to local file if refactored.database.db is unavailable
    DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import get_db_connection from main_gui
from education_system.systems.university.interfaces.gui.operations.commerce.restaurant_management_gui.core.main_gui import get_db_connection


def view_staff_gui(self):
    """Display staff in the treeview"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return

        cursor = conn.cursor()
        cursor.execute('''
            SELECT staff_id, name, role, hourly_rate, status, performance_score
            FROM restaurant_staff
            ORDER BY name
        ''')
        staff = cursor.fetchall()

        for item in self.staff_tree.get_children():
            self.staff_tree.delete(item)

        for member in staff:
            hourly_rate = f"£{member[3]:.2f}" if member[3] else "N/A"
            performance = f"{member[5]:.1f}/10" if member[5] else "N/A"

            self.staff_tree.insert('', 'end', values=(
                member[0], member[1], member[2], hourly_rate, member[4], performance
            ))

        conn.close()
        messagebox.showinfo("Success", f"Loaded {len(staff)} staff members")

    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to load staff: {str(e)}")

def add_staff_dialog(self):
    """Show dialog to add new staff"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Add Staff Member")
    dialog.geometry("500x500")
    dialog.transient(self.root)
    dialog.grab_set()
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Add New Staff Member", font=('Arial', 12, 'bold')).pack(pady=10)
    # Form
    form_frame = ttk.Frame(main_frame)
    form_frame.pack(fill='both', expand=True, pady=10)
    fields = {}
    row = 0
    ttk.Label(form_frame, text="Name:*").grid(row=row, column=0, sticky='w', pady=5)
    fields['name'] = ttk.Entry(form_frame, width=30)
    fields['name'].grid(row=row, column=1, pady=5, padx=10)
    row += 1
    ttk.Label(form_frame, text="Role:*").grid(row=row, column=0, sticky='w', pady=5)
    fields['role'] = ttk.Combobox(form_frame, values=['Waiter', 'Chef', 'Manager', 'Bartender', 'Host', 'Cleaner'], width=28)
    fields['role'].grid(row=row, column=1, pady=5, padx=10)
    fields['role'].current(0)
    row += 1
    ttk.Label(form_frame, text="Hourly Rate (£):*").grid(row=row, column=0, sticky='w', pady=5)
    fields['hourly_rate'] = ttk.Entry(form_frame, width=30)
    fields['hourly_rate'].grid(row=row, column=1, pady=5, padx=10)
    fields['hourly_rate'].insert(0, "10.00")
    row += 1
    ttk.Label(form_frame, text="Email:").grid(row=row, column=0, sticky='w', pady=5)
    fields['email'] = ttk.Entry(form_frame, width=30)
    fields['email'].grid(row=row, column=1, pady=5, padx=10)
    row += 1
    ttk.Label(form_frame, text="Phone:").grid(row=row, column=0, sticky='w', pady=5)
    fields['phone'] = ttk.Entry(form_frame, width=30)
    fields['phone'].grid(row=row, column=1, pady=5, padx=10)
    row += 1
    ttk.Label(form_frame, text="Status:").grid(row=row, column=0, sticky='w', pady=5)
    fields['status'] = ttk.Combobox(form_frame, values=['Active', 'On Leave', 'Inactive'], width=28)
    fields['status'].grid(row=row, column=1, pady=5, padx=10)
    fields['status'].current(0)
    def save_staff():
        name = fields['name'].get().strip()
        if not name:
            messagebox.showerror("Error", "Name is required")
            return
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO restaurant_staff (name, role, hourly_rate, email, phone, status, performance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                name,
                fields['role'].get(),
                float(fields['hourly_rate'].get()),
                fields['email'].get() or None,
                fields['phone'].get() or None,
                fields['status'].get(),
                5.0  # Default performance score
            ))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", f"Staff member {name} added successfully")
            self.view_staff_gui()
            dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to add staff member: {e}")
    buttons_frame = ttk.Frame(main_frame)
    buttons_frame.pack(pady=10)
    ttk.Button(buttons_frame, text="Save", command=save_staff).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)


def show_staff_analytics(self):
    """Show staff analytics"""
    try:
        analytics_window = tk.Toplevel(self.root)
        analytics_window.title("Staff Analytics")
        analytics_window.geometry("800x600")

        text_area = ScrolledText(analytics_window, height=30, width=80)
        text_area.pack(fill='both', expand=True, padx=10, pady=10)

        analytics_text = self.generate_staff_analytics()
        text_area.insert('1.0', analytics_text)
        text_area.config(state='disabled')

    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to generate analytics: {str(e)}")

def generate_staff_analytics(self):
    """Generate staff analytics text"""
    try:
        conn = get_db_connection()
        if not conn:
            return "Database connection failed"

        cursor = conn.cursor()

        text = "STAFF ANALYTICS\n"
        text += "=" * 50 + "\n\n"

        cursor.execute('''
            SELECT role, COUNT(*) as count, AVG(hourly_rate) as avg_rate, AVG(performance_score) as avg_performance
            FROM restaurant_staff
            WHERE status = 'Active'
            GROUP BY role
        ''')

        role_data = cursor.fetchall()

        text += "Staff by Role:\n"
        text += "-" * 50 + "\n"
        for role in role_data:
            avg_rate = f"£{role[2]:.2f}" if role[2] else "N/A"
            avg_perf = f"{role[3]:.1f}/10" if role[3] else "N/A"
            text += f"{role[0]}: {role[1]} staff, Avg Rate: {avg_rate}, Avg Performance: {avg_perf}\n"

        conn.close()
        return text

    except sqlite3.Error as e:
        return f"Error generating analytics: {str(e)}"

def view_schedule_conflicts(self):
    """Identify and display scheduling conflicts"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        # Find overlapping shifts
        cursor.execute('''
            SELECT s1.shift_id as shift1_id, s1.staff_id, s1.shift_date, s1.start_time, s1.end_time,
                   s2.shift_id as shift2_id, s2.start_time as overlap_start, s2.end_time as overlap_end,
                   st.name
            FROM restaurant_shifts s1
            JOIN restaurant_shifts s2 ON s1.staff_id = s2.staff_id
                AND s1.shift_id != s2.shift_id
                AND s1.shift_date = s2.shift_date
                AND s1.start_time < s2.end_time
                AND s1.end_time > s2.start_time
            JOIN restaurant_staff st ON s1.staff_id = st.staff_id
            WHERE s1.shift_date >= date('now')
            ORDER BY s1.shift_date, s1.start_time
        ''')
        conflicts = cursor.fetchall()
        # Check for understaffed periods (need at least 2 staff per 4-hour period)
        cursor.execute('''
            SELECT shift_date, start_time, COUNT(*) as staff_count
            FROM restaurant_shifts
            WHERE shift_date >= date('now')
            GROUP BY shift_date, start_time
            HAVING COUNT(*) < 2
            ORDER BY shift_date, start_time
        ''')
        understaffed = cursor.fetchall()
        # Check for overstaffed periods (more than 6 staff at once)
        cursor.execute('''
            SELECT shift_date, start_time, COUNT(*) as staff_count
            FROM restaurant_shifts
            WHERE shift_date >= date('now')
            GROUP BY shift_date, start_time
            HAVING COUNT(*) > 6
            ORDER BY shift_date, start_time
        ''')
        overstaffed = cursor.fetchall()
        conn.close()
        # Display conflicts
        conflict_dialog = tk.Toplevel(self.root)
        conflict_dialog.title("Schedule Conflicts")
        conflict_dialog.geometry("900x700")
        conflict_dialog.transient(self.root)
        main_frame = ttk.Frame(conflict_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="Schedule Conflicts & Issues",
                 font=('Arial', 14, 'bold')).pack(pady=10)
        report_text = ScrolledText(main_frame, height=35, width=100)
        report_text.pack(fill='both', expand=True)
        report = "SCHEDULE CONFLICTS REPORT\n"
        report += "=" * 90 + "\n\n"
        # Overlapping shifts
        report += "1. OVERLAPPING SHIFTS (Double-booked staff):\n"
        report += "-" * 90 + "\n"
        if conflicts:
            for shift1_id, staff_id, shift_date, start1, end1, shift2_id, start2, end2, name in conflicts:
                report += f"Staff: {name} (ID: {staff_id})\n"
                report += f"  Date: {shift_date}\n"
                report += f"  Shift 1: {start1} - {end1} (ID: {shift1_id})\n"
                report += f"  Shift 2: {start2} - {end2} (ID: {shift2_id})\n"
                report += "  CONFLICT: Shifts overlap!\n\n"
            report += f"\nTotal conflicts found: {len(conflicts)}\n"
        else:
            report += "No overlapping shifts detected.\n"
        # Understaffed periods
        report += "\n\n2. UNDERSTAFFED PERIODS (< 2 staff):\n"
        report += "-" * 90 + "\n"
        if understaffed:
            for shift_date, start_time, staff_count in understaffed:
                report += f"Date: {shift_date}, Time: {start_time} - Staff Count: {staff_count}\n"
            report += f"\nTotal understaffed periods: {len(understaffed)}\n"
        else:
            report += "No understaffed periods detected.\n"
        # Overstaffed periods
        report += "\n\n3. OVERSTAFFED PERIODS (> 6 staff):\n"
        report += "-" * 90 + "\n"
        if overstaffed:
            for shift_date, start_time, staff_count in overstaffed:
                report += f"Date: {shift_date}, Time: {start_time} - Staff Count: {staff_count}\n"
            report += f"\nTotal overstaffed periods: {len(overstaffed)}\n"
        else:
            report += "No overstaffed periods detected.\n"
        # Recommendations
        report += "\n\nRECOMMENDATIONS:\n"
        report += "-" * 90 + "\n"
        if conflicts:
            report += "• Resolve overlapping shifts immediately\n"
            report += "• Contact affected staff to confirm availability\n"
            report += "• Update shift assignments\n"
        if understaffed:
            report += "• Schedule additional staff for understaffed periods\n"
            report += "• Consider part-time staff or on-call arrangements\n"
        if overstaffed:
            report += "• Reduce staff during overstaffed periods to optimize costs\n"
            report += "• Reassign staff to other duties or locations\n"
        if not conflicts and not understaffed and not overstaffed:
            report += "• Schedule appears well-balanced\n"
            report += "• Continue monitoring for future conflicts\n"
        report_text.insert(1.0, report)
        report_text.config(state='disabled')
        ttk.Button(main_frame, text="Close",
                  command=conflict_dialog.destroy).pack(pady=10)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to check schedule conflicts:\n{str(e)}")

def manage_schedules_dialog(self):
    """Launch the Shifts Management & Scheduling GUI"""
    try:
        from education_system.systems.university.interfaces.gui.operations.commerce.restaurant_management_gui.staff.shifts_gui import (
            ShiftsManagementGUI,
            init_shifts_tables
        )

        # Initialize tables if needed
        init_shifts_tables()

        # Create and show the Shifts Management GUI
        shifts_window = tk.Toplevel(self.root)
        shifts_window.title("Shifts Management & Payroll")
        shifts_window.geometry("1400x800")
        shifts_window.transient(self.root)

        # Launch the GUI
        ShiftsManagementGUI(shifts_window)

    except ImportError as e:
        messagebox.showerror("Error", f"Failed to load Shifts Management module:\n{str(e)}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Shifts Management:\n{str(e)}")

