from university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText
from university_system.infrastructure.database.db import sqlite3
from datetime import datetime, timedelta
import threading
import sys
import os

# Import centralized authentication system
# Import authentication - REQUIRED (no fallback for security)
from university_system.infrastructure.auth import UserAuth, get_global_auth
from university_system.infrastructure.shared_context import get_auth

# Import i18n for multi-language support
from university_system.modules.shared.utils.i18n import (
    init_i18n,
    get_text as _t,
    set_language,
    get_current_language,
    get_current_language_name,
    get_available_languages,
)
from university_system.modules.shared.utils.gui_language_selector import show_gui_language_selector

# Import finance integration for student finance account payments
try:
    from university_system.modules.shared.utils.finance_integration import (
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
from university_system.infrastructure.exceptions import (
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
    from university_system.modules.domain.commerce.services.restaurant_management import init_db as init_enhanced_restaurant_db
except ImportError:
    init_enhanced_restaurant_db = None

# Database configuration
# Always point to the central student_records.db in refactored/db_files.
try:
    from university_system.infrastructure.database.db import DEFAULT_DB_PATH as DATABASE_FILE
except ImportError:
    # Fallback to local file if refactored.database.db is unavailable
    DATABASE_FILE = str(DEFAULT_DB_PATH)

# Import get_db_connection from main_gui
from university_system.modules.domain.commerce.gui.restaurant_management_gui.core.main_gui import get_db_connection


def view_inventory_gui(self):
    """Display inventory in the treeview"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
            
        cursor = conn.cursor()
        cursor.execute('''
            SELECT item_id, name, quantity, unit, cost_per_unit, reorder_level 
            FROM restaurant_inventory 
            ORDER BY name
        ''')
        items = cursor.fetchall()
        
        for item in self.inventory_tree.get_children():
            self.inventory_tree.delete(item)
            
        for item in items:
            cost_str = f"£{item[4]:.2f}" if item[4] else "N/A"
            reorder_str = f"{item[5]:.1f}" if item[5] else "N/A"
            
            self.inventory_tree.insert('', 'end', values=(
                item[0], item[1], f"{item[2]:.1f}", item[3], cost_str, reorder_str
            ))
            
        conn.close()
        messagebox.showinfo("Success", f"Loaded {len(items)} inventory items")
        
    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to load inventory: {str(e)}")

def waste_tracking_dialog(self):
    """Show waste tracking dialog"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Waste Tracking")
    dialog.geometry("900x600")
    dialog.transient(self.root)
    dialog.grab_set()
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Waste Tracking", font=('Arial', 14, 'bold')).pack(pady=10)
    # Create waste tracking table if it doesn't exist
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS restaurant_waste (
                    waste_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_name TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    unit TEXT,
                    reason TEXT,
                    cost_value REAL,
                    waste_date DATE NOT NULL,
                    recorded_by TEXT,
                    notes TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()
    except sqlite3.Error as e:
        messagebox.showerror("Database Error", f"Failed to initialize waste tracking table: {e}")
        dialog.destroy()
        return
    # Button frame
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill='x', pady=10)
    def record_waste():
        waste_dialog = tk.Toplevel(dialog)
        waste_dialog.title("Record Waste")
        waste_dialog.geometry("500x550")
        waste_dialog.transient(dialog)
        waste_dialog.grab_set()
        form_frame = ttk.Frame(waste_dialog, padding=20)
        form_frame.pack(fill='both', expand=True)
        fields = {}
        row = 0
        ttk.Label(form_frame, text="Item Name:*").grid(row=row, column=0, sticky='w', pady=5)
        fields['item'] = ttk.Entry(form_frame, width=40)
        fields['item'].grid(row=row, column=1, pady=5, padx=10)
        row += 1
        ttk.Label(form_frame, text="Quantity:*").grid(row=row, column=0, sticky='w', pady=5)
        fields['quantity'] = ttk.Entry(form_frame, width=40)
        fields['quantity'].grid(row=row, column=1, pady=5, padx=10)
        row += 1
        ttk.Label(form_frame, text="Unit:").grid(row=row, column=0, sticky='w', pady=5)
        fields['unit'] = ttk.Combobox(form_frame, values=['kg', 'L', 'pieces', 'portions'], width=38)
        fields['unit'].grid(row=row, column=1, pady=5, padx=10)
        fields['unit'].current(0)
        row += 1
        ttk.Label(form_frame, text="Estimated Cost (£):").grid(row=row, column=0, sticky='w', pady=5)
        fields['cost'] = ttk.Entry(form_frame, width=40)
        fields['cost'].grid(row=row, column=1, pady=5, padx=10)
        fields['cost'].insert(0, "0.00")
        row += 1
        ttk.Label(form_frame, text="Reason:").grid(row=row, column=0, sticky='w', pady=5)
        fields['reason'] = ttk.Combobox(form_frame,
            values=['Spoilage', 'Overproduction', 'Preparation waste', 'Expired', 'Damaged', 'Other'],
            width=38)
        fields['reason'].grid(row=row, column=1, pady=5, padx=10)
        fields['reason'].current(0)
        row += 1
        ttk.Label(form_frame, text="Date:*").grid(row=row, column=0, sticky='w', pady=5)
        fields['date'] = ttk.Entry(form_frame, width=40)
        fields['date'].grid(row=row, column=1, pady=5, padx=10)
        fields['date'].insert(0, datetime.now().strftime('%Y-%m-%d'))
        row += 1
        ttk.Label(form_frame, text="Notes:").grid(row=row, column=0, sticky='nw', pady=5)
        fields['notes'] = tk.Text(form_frame, height=4, width=40)
        fields['notes'].grid(row=row, column=1, pady=5, padx=10)
        def save_waste():
            try:
                if not fields['item'].get().strip() or not fields['quantity'].get().strip():
                    messagebox.showwarning("Missing Info", "Item name and quantity are required")
                    return
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO restaurant_waste
                        (item_name, quantity, unit, reason, cost_value, waste_date, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (fields['item'].get(), float(fields['quantity'].get()), fields['unit'].get(),
                          fields['reason'].get(), float(fields['cost'].get()), fields['date'].get(),
                          fields['notes'].get('1.0', tk.END).strip()))
                    conn.commit()
                    conn.close()
                    messagebox.showinfo("Success", "Waste record added successfully!")
                    waste_dialog.destroy()
                    load_waste()
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to record waste: {e}")
        button_frame = ttk.Frame(form_frame)
        button_frame.grid(row=row+1, column=0, columnspan=2, pady=20)
        ttk.Button(button_frame, text="Save", command=save_waste).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Cancel", command=waste_dialog.destroy).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Record Waste", command=record_waste).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Refresh", command=lambda: load_waste()).pack(side='left', padx=5)
    # Waste treeview
    tree_frame = ttk.Frame(main_frame)
    tree_frame.pack(fill='both', expand=True, pady=10)
    columns = ('ID', 'Item', 'Quantity', 'Unit', 'Cost', 'Reason', 'Date')
    waste_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=20)
    for col in columns:
        waste_tree.heading(col, text=col)
        waste_tree.column(col, width=110)
    scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', command=waste_tree.yview)
    waste_tree.configure(yscrollcommand=scrollbar.set)
    waste_tree.pack(side='left', fill='both', expand=True)
    scrollbar.pack(side='right', fill='y')
    def load_waste():
        for item in waste_tree.get_children():
            waste_tree.delete(item)
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT waste_id, item_name, quantity, unit, cost_value, reason, waste_date
                    FROM restaurant_waste
                    ORDER BY waste_date DESC
                    LIMIT 100
                ''')
                waste_records = cursor.fetchall()
                conn.close()
                for record in waste_records:
                    cost_display = f"£{record[4]:.2f}" if record[4] else "N/A"
                    display_record = list(record)
                    display_record[4] = cost_display
                    waste_tree.insert('', 'end', values=display_record)
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load waste records: {e}")
    load_waste()
    # Summary frame
    summary_frame = ttk.LabelFrame(main_frame, text="Waste Summary", padding=10)
    summary_frame.pack(fill='x', pady=10)
    summary_text = tk.StringVar(value="Loading summary...")
    ttk.Label(summary_frame, textvariable=summary_text).pack()
    def update_summary():
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT COUNT(*), SUM(cost_value), SUM(quantity)
                    FROM restaurant_waste
                    WHERE waste_date >= date('now', '-30 days')
                ''')
                stats = cursor.fetchone()
                conn.close()
                if stats:
                    summary_text.set(
                        f"Last 30 days: {stats[0]} records | " +
                        f"Total Cost: £{stats[1]:.2f if stats[1] else 0:.2f} | " +
                        f"Total Waste: {stats[2]:.1f if stats[2] else 0:.1f} units"
                    )
        except sqlite3.Error:
            summary_text.set("Unable to load summary")
    update_summary()
    # Additional buttons
    button_frame_bottom = ttk.Frame(main_frame)
    button_frame_bottom.pack(fill='x', pady=10)
    ttk.Button(button_frame_bottom, text="View Detailed Reports",
              command=self.view_waste_reports).pack(side='left', padx=5)
    ttk.Button(button_frame_bottom, text="Close", command=dialog.destroy).pack(side='left', padx=5)

def inventory_transactions(self):
    """Display detailed inventory transaction log"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        # Create transactions table if doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory_transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                item_id INTEGER,
                transaction_type TEXT,
                quantity REAL,
                transaction_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                user_id INTEGER,
                notes TEXT
            )
        ''')
        conn.commit()
        # Get recent transactions
        cursor.execute('''
            SELECT t.transaction_id, t.item_id, i.name, t.transaction_type,
                   t.quantity, t.transaction_date, t.notes
            FROM inventory_transactions t
            LEFT JOIN restaurant_inventory i ON t.item_id = i.item_id
            ORDER BY t.transaction_date DESC
            LIMIT 100
        ''')
        transactions = cursor.fetchall()
        conn.close()
        # Display transactions
        trans_dialog = tk.Toplevel(self.root)
        trans_dialog.title("Inventory Transactions Log")
        trans_dialog.geometry("1000x600")
        trans_dialog.transient(self.root)
        main_frame = ttk.Frame(trans_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        ttk.Label(main_frame, text="Inventory Transactions Log (Last 100)",
                 font=('Arial', 14, 'bold')).pack(pady=10)
        # Create treeview
        columns = ('Trans ID', 'Item ID', 'Item Name', 'Type', 'Quantity', 'Date', 'Notes')
        tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=25)
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=120)
        for trans in transactions:
            tree.insert('', 'end', values=trans)
        scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        ttk.Button(main_frame, text="Close",
                  command=trans_dialog.destroy).pack(pady=10)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to load transactions:\n{str(e)}")

def low_stock_alerts(self):
    """Show automated low stock alerts"""
    try:
        conn = get_db_connection()
        if not conn:
            messagebox.showerror("Error", "Database connection failed")
            return
        cursor = conn.cursor()
        # Get low stock items
        cursor.execute('''
            SELECT item_id, name, quantity, reorder_level, unit
            FROM restaurant_inventory
            WHERE quantity <= reorder_level
            ORDER BY (quantity / NULLIF(reorder_level, 0))
        ''')
        low_stock = cursor.fetchall()
        conn.close()
        # Display alerts
        alerts_dialog = tk.Toplevel(self.root)
        alerts_dialog.title("Low Stock Alerts")
        alerts_dialog.geometry("700x500")
        alerts_dialog.transient(self.root)
        main_frame = ttk.Frame(alerts_dialog, padding=20)
        main_frame.pack(fill='both', expand=True)
        if not low_stock:
            ttk.Label(main_frame, text="✓ No Low Stock Alerts",
                     font=('Arial', 14, 'bold'), foreground='green').pack(pady=20)
            ttk.Label(main_frame, text="All inventory levels are adequate.",
                     font=('Arial', 12)).pack(pady=10)
        else:
            ttk.Label(main_frame, text=f"⚠ {len(low_stock)} Low Stock Alerts",
                     font=('Arial', 14, 'bold'), foreground='orange').pack(pady=20)
            # Create treeview for alerts
            columns = ('Item ID', 'Item Name', 'Current Qty', 'Reorder Level', 'Status')
            tree = ttk.Treeview(main_frame, columns=columns, show='headings', height=15)
            for col in columns:
                tree.heading(col, text=col)
                tree.column(col, width=120)
            for item_id, name, qty, reorder, unit in low_stock:
                status = "CRITICAL" if qty < (reorder * 0.5) else "LOW"
                tree.insert('', 'end', values=(item_id, name, f"{qty:.1f} {unit}",
                                              f"{reorder:.1f} {unit}", status),
                           tags=(status,))
            # Color code by status
            tree.tag_configure('CRITICAL', background='#ffcccc')
            tree.tag_configure('LOW', background='#ffffcc')
            scrollbar = ttk.Scrollbar(main_frame, orient='vertical', command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            tree.pack(side='left', fill='both', expand=True)
            scrollbar.pack(side='right', fill='y')
            # Action buttons
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(pady=10)
            def send_alert_email():
                messagebox.showinfo("Email Alert",
                                   f"Low stock alert email would be sent to procurement team.\n\n" +
                                   f"{len(low_stock)} items require reordering.")
            ttk.Button(button_frame, text="Send Email Alert",
                      command=send_alert_email).pack(side='left', padx=5)
        ttk.Button(main_frame, text="Close",
                  command=alerts_dialog.destroy).pack(pady=10)
    except (sqlite3.Error, tk.TclError) as e:
        messagebox.showerror("Error", f"Failed to load low stock alerts:\n{str(e)}")

def waste_tracking_dialog(self):
    """Launch the Waste Tracking management GUI"""
    try:
        from university_system.modules.domain.commerce.gui.restaurant_management_gui.inventory.waste_tracking_gui import (
            WasteTrackingGUI,
            init_waste_tracking_tables
        )

        # Initialize tables if needed
        init_waste_tracking_tables()

        # Create and show the Waste Tracking GUI
        waste_window = tk.Toplevel(self.root)
        waste_window.title("Waste Tracking & Analysis")
        waste_window.geometry("1200x700")
        waste_window.transient(self.root)

        # Launch the GUI
        WasteTrackingGUI(waste_window)

    except ImportError as e:
        messagebox.showerror("Error", f"Failed to load Waste Tracking module:\n{str(e)}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch Waste Tracking:\n{str(e)}")

