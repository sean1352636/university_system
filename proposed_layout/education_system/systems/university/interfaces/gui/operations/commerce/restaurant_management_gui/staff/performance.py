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


def staff_performance(self):
    """Staff performance management menu"""
    perf_dialog = tk.Toplevel(self.root)
    perf_dialog.title("Staff Performance Management")
    perf_dialog.geometry("400x350")
    perf_dialog.transient(self.root)
    perf_dialog.grab_set()
    main_frame = ttk.Frame(perf_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Staff Performance Management",
             font=('Arial', 14, 'bold')).pack(pady=20)
    ttk.Button(main_frame, text="View Performance Rankings",
              command=lambda: [perf_dialog.destroy(), self.view_performance_rankings()],
              width=35).pack(pady=10)
    ttk.Button(main_frame, text="Update Performance Scores",
              command=lambda: [perf_dialog.destroy(), self.update_performance_scores()],
              width=35).pack(pady=10)
    ttk.Button(main_frame, text="Export Performance Report",
              command=lambda: [perf_dialog.destroy(), self.export_performance_report()],
              width=35).pack(pady=10)
    ttk.Button(main_frame, text="Close",
              command=perf_dialog.destroy,
              width=35).pack(pady=20)

def view_performance_rankings(self):
    """Display staff performance rankings"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        # Create performance table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staff_performance (
                performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id INTEGER,
                punctuality_score INTEGER DEFAULT 5,
                quality_score INTEGER DEFAULT 5,
                efficiency_score INTEGER DEFAULT 5,
                teamwork_score INTEGER DEFAULT 5,
                overall_score REAL DEFAULT 5.0,
                evaluation_date DATE DEFAULT CURRENT_DATE,
                notes TEXT,
                FOREIGN KEY (staff_id) REFERENCES restaurant_staff(staff_id)
            )
        ''')
        conn.commit()
        # Get performance rankings
        cursor.execute('''
            SELECT s.staff_id, s.name, s.position,
                   COALESCE(AVG(p.overall_score), 5.0) as avg_score,
                   COUNT(p.performance_id) as eval_count
            FROM restaurant_staff s
            LEFT JOIN staff_performance p ON s.staff_id = p.staff_id
            GROUP BY s.staff_id
            ORDER BY avg_score DESC
        ''')
        rankings = cursor.fetchall()
        conn.close()
        # Display rankings
        rank_dialog = tk.Toplevel(self.root)
        rank_dialog.title("Staff Performance Rankings")
        rank_dialog.geometry("800x600")
        rank_dialog.transient(self.root)
        main_frame = ttk.Frame(rank_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="Staff Performance Rankings",
                 font=('Arial', 14, 'bold')).pack(pady=10)
        # Create treeview
        columns = ('Rank', 'Staff ID', 'Name', 'Position', 'Avg Score', 'Evaluations', 'Performance')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=20)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100)
        rank = 1
        for staff_id, name, position, avg_score, eval_count in rankings:
            performance = "Excellent" if avg_score >= 8 else "Good" if avg_score >= 6 else "Needs Improvement"
            tree.insert('', 'end', values=(rank, staff_id, name, position,
                                          f"{avg_score:.1f}/10", eval_count, performance))
            rank += 1
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        ttk.Button(main_frame, text="Close",
                  command=rank_dialog.destroy).pack(pady=10)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to load performance rankings:\n{str(e)}")

def update_performance_scores(self):
    """Update individual staff performance scores"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        cursor.execute('SELECT staff_id, name, position FROM restaurant_staff ORDER BY name')
        staff_list = cursor.fetchall()
        conn.close()
        if not staff_list:
            messagebox.showinfo("No Staff", "No staff members found in database")
            return
        # Create dialog
        update_dialog = tk.Toplevel(self.root)
        update_dialog.title("Update Performance Scores")
        update_dialog.geometry("500x650")
        update_dialog.transient(self.root)
        main_frame = ttk.Frame(update_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="Update Performance Scores",
                 font=('Arial', 14, 'bold')).pack(pady=10)
        # Staff selection
        staff_frame = ttk.LabelFrame(main_frame, text="Select Staff Member", padding=10)
        staff_frame.pack(fill='x', pady=10)
        staff_var = tk.StringVar()
        staff_dropdown = ttk.Combobox(staff_frame, textvariable=staff_var, width=40, state='readonly')
        staff_dropdown['values'] = [f"{s[0]} - {s[1]} ({s[2]})" for s in staff_list]
        staff_dropdown.pack()
        # Performance criteria
        criteria_frame = ttk.LabelFrame(main_frame, text="Performance Criteria (1-10)", padding=10)
        criteria_frame.pack(fill='x', pady=10)
        punctuality_var = tk.IntVar(value=5)
        quality_var = tk.IntVar(value=5)
        efficiency_var = tk.IntVar(value=5)
        teamwork_var = tk.IntVar(value=5)
        ttk.Label(criteria_frame, text="Punctuality:").grid(row=0, column=0, sticky='w', pady=5)
        ttk.Scale(criteria_frame, from_=1, to=10, variable=punctuality_var, orient='horizontal', length=200).grid(row=0, column=1, padx=10)
        ttk.Label(criteria_frame, textvariable=punctuality_var).grid(row=0, column=2)
        ttk.Label(criteria_frame, text="Quality:").grid(row=1, column=0, sticky='w', pady=5)
        ttk.Scale(criteria_frame, from_=1, to=10, variable=quality_var, orient='horizontal', length=200).grid(row=1, column=1, padx=10)
        ttk.Label(criteria_frame, textvariable=quality_var).grid(row=1, column=2)
        ttk.Label(criteria_frame, text="Efficiency:").grid(row=2, column=0, sticky='w', pady=5)
        ttk.Scale(criteria_frame, from_=1, to=10, variable=efficiency_var, orient='horizontal', length=200).grid(row=2, column=1, padx=10)
        ttk.Label(criteria_frame, textvariable=efficiency_var).grid(row=2, column=2)
        ttk.Label(criteria_frame, text="Teamwork:").grid(row=3, column=0, sticky='w', pady=5)
        ttk.Scale(criteria_frame, from_=1, to=10, variable=teamwork_var, orient='horizontal', length=200).grid(row=3, column=1, padx=10)
        ttk.Label(criteria_frame, textvariable=teamwork_var).grid(row=3, column=2)
        # Notes
        notes_frame = ttk.LabelFrame(main_frame, text="Manager Comments", padding=10)
        notes_frame.pack(fill='both', expand=True, pady=10)
        notes_text = tk.Text(notes_frame, height=5, width=50)
        notes_text.pack(fill='both', expand=True)
        # Save button
        def save_performance():
            if not staff_var.get():
                messagebox.showwarning("No Selection", "Please select a staff member")
                return
            staff_id = int(staff_var.get().split(' - ')[0])
            overall_score = (punctuality_var.get() + quality_var.get() +
                           efficiency_var.get() + teamwork_var.get()) / 4
            try:
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        CREATE TABLE IF NOT EXISTS staff_performance (
                            performance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            staff_id INTEGER,
                            punctuality_score INTEGER,
                            quality_score INTEGER,
                            efficiency_score INTEGER,
                            teamwork_score INTEGER,
                            overall_score REAL,
                            evaluation_date DATE DEFAULT CURRENT_DATE,
                            notes TEXT,
                            FOREIGN KEY (staff_id) REFERENCES restaurant_staff(staff_id)
                        )
                    ''')
                    cursor.execute('''
                        INSERT INTO staff_performance
                        (staff_id, punctuality_score, quality_score, efficiency_score,
                         teamwork_score, overall_score, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (staff_id, punctuality_var.get(), quality_var.get(),
                         efficiency_var.get(), teamwork_var.get(), overall_score,
                         notes_text.get(1.0, tk.END)))
                    conn.commit()
                    conn.close()
                    messagebox.showinfo("Success", "Performance evaluation saved successfully!")
                    update_dialog.destroy()
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to save performance: {e}")
        ttk.Button(main_frame, text="Save Evaluation",
                  command=save_performance).pack(pady=10)
        ttk.Button(main_frame, text="Cancel",
                  command=update_dialog.destroy).pack()
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to update performance scores:\n{str(e)}")

def export_performance_report(self):
    """Export staff performance report"""
    try:
        from tkinter import filedialog
        import csv
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        # Get comprehensive performance data
        cursor.execute('''
            SELECT s.staff_id, s.name, s.position,
                   AVG(p.punctuality_score) as avg_punctuality,
                   AVG(p.quality_score) as avg_quality,
                   AVG(p.efficiency_score) as avg_efficiency,
                   AVG(p.teamwork_score) as avg_teamwork,
                   AVG(p.overall_score) as avg_overall,
                   COUNT(p.performance_id) as eval_count,
                   MAX(p.evaluation_date) as latest_eval
            FROM restaurant_staff s
            LEFT JOIN staff_performance p ON s.staff_id = p.staff_id
            GROUP BY s.staff_id
            ORDER BY avg_overall DESC
        ''')
        performance_data = cursor.fetchall()
        conn.close()
        if not performance_data:
            messagebox.showinfo("No Data", "No performance data available")
            return
        # Ask for export format
        format_choice = messagebox.askquestion("Export Format",
                                              "Export as CSV?\n(No = Display in window)")
        if format_choice == 'yes':
            filename = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                initialfile="staff_performance_report.csv"
            )
            if filename:
                with open(filename, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Staff ID', 'Name', 'Position', 'Punctuality', 'Quality',
                                   'Efficiency', 'Teamwork', 'Overall Score', 'Evaluations', 'Latest Eval'])
                    for record in performance_data:
                        writer.writerow(record)
                messagebox.showinfo("Success", f"Performance report exported to:\n{filename}")
        else:
            # Display in report window
            report = "STAFF PERFORMANCE REPORT\n"
            report += "=" * 120 + "\n\n"
            report += f"{'ID':<6} {'Name':<20} {'Position':<15} {'Punct':<7} {'Quality':<8} {'Effic':<7} {'Team':<7} {'Overall':<8} {'Evals':<7} {'Latest':<12}\n"
            report += "-" * 120 + "\n"
            for (staff_id, name, position, punc, qual, effic, team, overall, evals, latest) in performance_data:
                report += f"{staff_id:<6} {name:<20} {position:<15} "
                report += f"{punc or 0:<7.1f} {qual or 0:<8.1f} {effic or 0:<7.1f} {team or 0:<7.1f} "
                report += f"{overall or 0:<8.1f} {evals or 0:<7} {latest or 'N/A':<12}\n"
            # Show in main report area if available, otherwise create dialog
            if hasattr(self, 'report_text'):
                self.report_text.delete(1.0, tk.END)
                self.report_text.insert(tk.END, report)
            else:
                report_dialog = tk.Toplevel(self.root)
                report_dialog.title("Performance Report")
                report_dialog.geometry("1000x600")
                report_text = ScrolledText(report_dialog, height=30, width=120)
                report_text.pack(fill='both', expand=True, padx=10, pady=10)
                report_text.insert(1.0, report)
                report_text.config(state='disabled')
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to export performance report:\n{str(e)}")

