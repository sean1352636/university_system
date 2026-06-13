from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from education_system.university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import threading
import sys
import os

# Import centralized authentication system
# Import authentication - REQUIRED (no fallback for security)
from education_system.university_system.infrastructure.auth import UserAuth, get_global_auth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from education_system.university_system.core.i18n import (
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
from education_system.university_system.core.exceptions import (
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


def view_tables_gui(self):
    """Display tables in the treeview"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return

        cursor = conn.cursor()
        cursor.execute('''
            SELECT table_id, capacity, status, location, table_type
            FROM restaurant_tables
            ORDER BY table_id
        ''')
        tables = cursor.fetchall()

        for item in self.tables_tree.get_children():
            self.tables_tree.delete(item)

        for table in tables:
            self.tables_tree.insert('', 'end', values=(
                table[0], table[1], table[2], table[3] or 'N/A', table[4] or 'Standard'
            ))

        conn.close()
        messagebox.showinfo("Success", f"Loaded {len(tables)} tables")

    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to load tables: {str(e)}")

def add_table_dialog(self):
    """Show dialog to add new table"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Add Restaurant Table")
    dialog.geometry("500x400")
    dialog.transient(self.root)
    dialog.grab_set()
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Add New Table", font=('Arial', 12, 'bold')).pack(pady=10)
    # Form
    form_frame = ttk.Frame(main_frame)
    form_frame.pack(fill='both', expand=True, pady=10)
    fields = {}
    row = 0
    ttk.Label(form_frame, text="Table ID:*").grid(row=row, column=0, sticky='w', pady=5)
    fields['table_id'] = ttk.Entry(form_frame, width=30)
    fields['table_id'].grid(row=row, column=1, pady=5, padx=10)
    row += 1
    ttk.Label(form_frame, text="Capacity:*").grid(row=row, column=0, sticky='w', pady=5)
    fields['capacity'] = ttk.Spinbox(form_frame, from_=1, to=20, width=28)
    fields['capacity'].grid(row=row, column=1, pady=5, padx=10)
    fields['capacity'].set(4)
    row += 1
    ttk.Label(form_frame, text="Location:").grid(row=row, column=0, sticky='w', pady=5)
    fields['location'] = ttk.Combobox(form_frame, values=['Indoor', 'Outdoor', 'Patio', 'VIP Area', 'Bar'], width=28)
    fields['location'].grid(row=row, column=1, pady=5, padx=10)
    fields['location'].current(0)
    row += 1
    ttk.Label(form_frame, text="Table Type:").grid(row=row, column=0, sticky='w', pady=5)
    fields['table_type'] = ttk.Combobox(form_frame, values=['Standard', 'Booth', 'High Top', 'Counter'], width=28)
    fields['table_type'].grid(row=row, column=1, pady=5, padx=10)
    fields['table_type'].current(0)
    row += 1
    ttk.Label(form_frame, text="Status:").grid(row=row, column=0, sticky='w', pady=5)
    fields['status'] = ttk.Combobox(form_frame, values=['Available', 'Occupied', 'Reserved', 'Maintenance'], width=28)
    fields['status'].grid(row=row, column=1, pady=5, padx=10)
    fields['status'].current(0)
    def save_table():
        table_id = fields['table_id'].get().strip()
        if not table_id:
            messagebox.showerror("Error", "Table ID is required")
            return
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO restaurant_tables (table_id, capacity, status, location, table_type)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                table_id,
                int(fields['capacity'].get()),
                fields['status'].get(),
                fields['location'].get(),
                fields['table_type'].get()
            ))
            conn.commit()
            conn.close()
            messagebox.showinfo("Success", f"Table {table_id} added successfully")
            self.view_tables_gui()
            dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to add table: {e}")
    buttons_frame = ttk.Frame(main_frame)
    buttons_frame.pack(pady=10)
    ttk.Button(buttons_frame, text="Save", command=save_table).pack(side='left', padx=5)
    ttk.Button(buttons_frame, text="Cancel", command=dialog.destroy).pack(side='left', padx=5)

def manage_reservations_dialog(self):
    """Show reservations management dialog"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Reservations Management")
    dialog.geometry("900x700")
    dialog.transient(self.root)
    dialog.grab_set()
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Reservations Management", font=('Arial', 14, 'bold')).pack(pady=10)
    # Create reservations table if it doesn't exist
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS restaurant_reservations (
                    reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    customer_id INTEGER,
                    table_id INTEGER,
                    reservation_date TEXT NOT NULL,
                    reservation_time TEXT NOT NULL,
                    party_size INTEGER NOT NULL,
                    status TEXT DEFAULT 'Confirmed',
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (customer_id) REFERENCES restaurant_customers(customer_id),
                    FOREIGN KEY (table_id) REFERENCES restaurant_tables(table_id)
                )
            ''')
            conn.commit()
            conn.close()
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Failed to initialize reservations table: {e}")
        dialog.destroy()
        return
    # Button frame
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill='x', pady=10)
    def new_reservation():
        res_dialog = tk.Toplevel(dialog)
        res_dialog.title("New Reservation")
        res_dialog.geometry("500x600")
        res_dialog.transient(dialog)
        res_dialog.grab_set()
        form_frame = ttk.Frame(res_dialog, padding=20)
        form_frame.pack(fill='both', expand=True)
        fields = {}
        row = 0
        ttk.Label(form_frame, text="Customer:").grid(row=row, column=0, sticky='w', pady=5)
        fields['customer'] = ttk.Combobox(form_frame, width=35)
        fields['customer'].grid(row=row, column=1, pady=5, padx=10)
        # Load customers
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('SELECT customer_id, name FROM restaurant_customers ORDER BY name')
                customers = cursor.fetchall()
                conn.close()
                fields['customer']['values'] = [f"{c[0]}: {c[1]}" for c in customers]
        except sqlite3.Error:
            pass
        row += 1
        ttk.Label(form_frame, text="Table:").grid(row=row, column=0, sticky='w', pady=5)
        fields['table'] = ttk.Combobox(form_frame, width=35)
        fields['table'].grid(row=row, column=1, pady=5, padx=10)
        # Load tables
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('SELECT table_id, capacity, location FROM restaurant_tables WHERE status = "Available" ORDER BY table_id')
                tables = cursor.fetchall()
                conn.close()
                fields['table']['values'] = [f"Table {t[0]} (Capacity: {t[1]}, {t[2]})" for t in tables]
        except sqlite3.Error:
            pass
        row += 1
        ttk.Label(form_frame, text="Date (YYYY-MM-DD):*").grid(row=row, column=0, sticky='w', pady=5)
        fields['date'] = ttk.Entry(form_frame, width=35)
        fields['date'].grid(row=row, column=1, pady=5, padx=10)
        fields['date'].insert(0, datetime.now().strftime('%Y-%m-%d'))
        row += 1
        ttk.Label(form_frame, text="Time (HH:MM):*").grid(row=row, column=0, sticky='w', pady=5)
        fields['time'] = ttk.Entry(form_frame, width=35)
        fields['time'].grid(row=row, column=1, pady=5, padx=10)
        fields['time'].insert(0, "18:00")
        row += 1
        ttk.Label(form_frame, text="Party Size:*").grid(row=row, column=0, sticky='w', pady=5)
        fields['party_size'] = ttk.Spinbox(form_frame, from_=1, to=20, width=33)
        fields['party_size'].grid(row=row, column=1, pady=5, padx=10)
        fields['party_size'].set(2)
        row += 1
        ttk.Label(form_frame, text="Notes:").grid(row=row, column=0, sticky='nw', pady=5)
        fields['notes'] = tk.Text(form_frame, height=5, width=35)
        fields['notes'].grid(row=row, column=1, pady=5, padx=10)
        def save_reservation():
            try:
                customer_selection = fields['customer'].get()
                customer_id = int(customer_selection.split(':')[0]) if customer_selection else None
                table_selection = fields['table'].get()
                table_id = int(table_selection.split()[1]) if table_selection else None
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO restaurant_reservations
                        (customer_id, table_id, reservation_date, reservation_time, party_size, notes, status)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (customer_id, table_id, fields['date'].get(), fields['time'].get(),
                          int(fields['party_size'].get()), fields['notes'].get('1.0', tk.END).strip(), 'Confirmed'))
                    conn.commit()
                    conn.close()
                    messagebox.showinfo("Success", "Reservation created successfully!")
                    res_dialog.destroy()
                    load_reservations()
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to create reservation: {e}")
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=row+1, column=0, columnspan=2, pady=20)
        ttk.Button(button_frame, text="Save", command=save_reservation).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=res_dialog.destroy).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="New Reservation", command=new_reservation).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Refresh", command=lambda: load_reservations()).pack(side='left', padx=5)
    # Reservations treeview
    tree_frame = ttk.Frame(main_frame)
    tree_frame.pack(fill='both', expand=True, pady=10)
    columns = ('ID', 'Customer', 'Table', 'Date', 'Time', 'Party Size', 'Status')
    reservations_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)
    for col in columns:
        reservations_tree.heading(col, text=col)
        reservations_tree.column(col, width=120)
    scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=reservations_tree.yview)
    reservations_tree.configure(yscrollcommand=scrollbar.set)
    reservations_tree.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')
    def load_reservations():
        for item in reservations_tree.get_children():
            reservations_tree.delete(item)
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT r.reservation_id, COALESCE(c.name, 'Walk-in'), r.table_id,
                           r.reservation_date, r.reservation_time, r.party_size, r.status
                    FROM restaurant_reservations r
                    LEFT JOIN restaurant_customers c ON r.customer_id = c.customer_id
                    ORDER BY r.reservation_date DESC, r.reservation_time DESC
                    LIMIT 100
                ''')
                reservations = cursor.fetchall()
                conn.close()
                for res in reservations:
                    reservations_tree.insert('', 'end', values=res)
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load reservations: {e}")
    load_reservations()
    ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

def optimize_table_structure(self):
    """Optimize table arrangement based on utilization data"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        # Get table utilization data
        cursor.execute('''
            SELECT t.table_id, t.capacity, t.location, t.table_type,
                   COUNT(r.reservation_id) as reservation_count,
                   AVG(r.party_size) as avg_party_size
            FROM restaurant_tables t
            LEFT JOIN restaurant_reservations r ON t.table_id = r.table_id
            WHERE r.reservation_date >= date('now', '-30 days')
            GROUP BY t.table_id
            ORDER BY reservation_count DESC
        ''')
        utilization_data = cursor.fetchall()
        # Get revenue per table (if order data exists)
        cursor.execute('''
            SELECT t.table_id, SUM(o.total_amount) as total_revenue
            FROM restaurant_tables t
            LEFT JOIN orders o ON t.table_id = o.table_id
            WHERE o.order_date >= datetime('now', '-30 days')
            GROUP BY t.table_id
        ''')
        revenue_data = dict(cursor.fetchall())
        conn.close()
        # Display optimization analysis
        opt_dialog = tk.Toplevel(self.root)
        opt_dialog.title("Table Structure Optimization")
        opt_dialog.geometry("900x700")
        opt_dialog.transient(self.root)
        main_frame = ttk.Frame(opt_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="Table Structure Optimization Analysis",
                 font=('Arial', 14, 'bold')).pack(pady=10)
        # Create scrolled text for report
        report_text = ScrolledText(main_frame, height=35, width=100)
        report_text.pack(fill='both', expand=True)
        report = "TABLE STRUCTURE OPTIMIZATION ANALYSIS\n"
        report += "=" * 90 + "\n\n"
        # Table utilization analysis
        report += "TABLE UTILIZATION ANALYSIS (Last 30 Days):\n"
        report += "-" * 90 + "\n"
        report += f"{'Table':<10} {'Capacity':<10} {'Reservations':<15} {'Avg Party':<12} {'Revenue':<15} {'Efficiency':<15}\n"
        report += "-" * 90 + "\n"
        total_capacity = 0
        total_reservations = 0
        underutilized = []
        overutilized = []
        for table_id, capacity, location, table_type, res_count, avg_party in utilization_data:
            revenue = revenue_data.get(table_id, 0)
            efficiency = (avg_party / capacity * 100) if capacity and avg_party else 0
            total_capacity += capacity
            total_reservations += res_count
            report += f"{table_id:<10} {capacity:<10} {res_count:<15} {avg_party or 0:<12.1f} £{revenue:<14.2f} {efficiency:<14.1f}%\n"
            if efficiency < 60 and res_count > 5:
                underutilized.append((table_id, capacity, efficiency))
            elif efficiency > 95 and res_count > 10:
                overutilized.append((table_id, capacity, efficiency))
        # Capacity vs Demand analysis
        report += "\n\nCAPACITY VS DEMAND ANALYSIS:\n"
        report += "-" * 90 + "\n"
        report += f"Total Seating Capacity: {total_capacity} seats\n"
        report += f"Total Reservations (30 days): {total_reservations}\n"
        if utilization_data:
            avg_util = (total_reservations / (len(utilization_data) * 30)) * 100
            report += f"Average Table Utilization: {avg_util:.1f}%\n\n"
        # Recommendations
        report += "OPTIMIZATION RECOMMENDATIONS:\n"
        report += "-" * 90 + "\n"
        if underutilized:
            report += "\n1. UNDERUTILIZED TABLES (< 60% efficiency):\n"
            for table_id, capacity, efficiency in underutilized:
                report += f"   • Table {table_id} ({capacity} seats) - {efficiency:.1f}% efficiency\n"
                report += f"     Recommendation: Consider converting to smaller table or different configuration\n"
        if overutilized:
            report += "\n2. OVERUTILIZED TABLES (> 95% efficiency):\n"
            for table_id, capacity, efficiency in overutilized:
                report += f"   • Table {table_id} ({capacity} seats) - {efficiency:.1f}% efficiency\n"
                report += f"     Recommendation: High demand - consider adding similar capacity tables\n"
        if not underutilized and not overutilized:
            report += "• Current table configuration appears well-balanced\n"
            report += "• Continue monitoring utilization trends\n"
        # Revenue optimization
        report += "\n3. REVENUE OPTIMIZATION:\n"
        top_revenue = sorted(revenue_data.items(), key=lambda x: x[1], reverse=True)[:3]
        if top_revenue:
            report += "   Top revenue-generating tables:\n"
            for table_id, revenue in top_revenue:
                report += f"   • Table {table_id}: £{revenue:.2f}\n"
            report += "   Recommendation: Prioritize these table locations for expansion\n"
        # Turnover rate analysis
        report += "\n4. TURNOVER RATE ANALYSIS:\n"
        if total_reservations > 0:
            daily_turnover = total_reservations / 30
            report += f"   • Average daily table turnovers: {daily_turnover:.1f}\n"
            if daily_turnover < 2:
                report += "   • Recommendation: Low turnover - consider strategies to increase table turnover\n"
            elif daily_turnover > 4:
                report += "   • Recommendation: High turnover - ensure service quality is maintained\n"
        report += "\n\nACTION ITEMS:\n"
        report += "-" * 90 + "\n"
        report += "1. Review underutilized tables for reconfiguration\n"
        report += "2. Monitor overutilized tables for customer satisfaction\n"
        report += "3. Consider adding capacity in high-revenue areas\n"
        report += "4. Optimize table allocation during peak hours\n"
        report += "5. Review reservation patterns for better planning\n"
        report_text.insert(1.0, report)
        report_text.config(state='disabled')
        ttk.Button(main_frame, text="Close",
                  command=opt_dialog.destroy).pack(pady=10)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to analyze table structure:\n{str(e)}")

