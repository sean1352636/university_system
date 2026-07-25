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

# Authentication is imported unconditionally above (required, no fallback)
AUTH_AVAILABLE = True
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


def manage_loyalty_dialog(self):
    """Show loyalty program management dialog"""
    dialog = tk.Toplevel(self.root)
    dialog.title("Loyalty Program Management")
    dialog.geometry("800x600")
    dialog.transient(self.root)
    dialog.grab_set()
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Loyalty Program Management", font=('Arial', 14, 'bold')).pack(pady=10)
    # Tier information frame
    tier_frame = ttk.LabelFrame(main_frame, text="Loyalty Tiers", padding=10)
    tier_frame.pack(fill='both', expand=True, pady=10)
    # Customer selection
    search_frame = ttk.Frame(tier_frame)
    search_frame.pack(fill='x', pady=5)
    ttk.Label(search_frame, text="Select Customer:").pack(side='left', padx=5)
    customer_var = tk.StringVar()
    customer_combo = ttk.Combobox(search_frame, textvariable=customer_var, width=40)
    customer_combo.pack(side='left', padx=5)
    # Load customers
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('SELECT customer_id, name, loyalty_tier, loyalty_points FROM restaurant_customers ORDER BY name')
            customers = cursor.fetchall()
            conn.close()
            customer_list = [f"{c[0]}: {c[1]} ({c[2]}, {c[3]} pts)" for c in customers]
            customer_combo['values'] = customer_list
    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to load customers: {e}")
    # Points adjustment frame
    adjust_frame = ttk.LabelFrame(tier_frame, text="Adjust Points", padding=10)
    adjust_frame.pack(fill='x', pady=10)
    ttk.Label(adjust_frame, text="Points to Add/Subtract:").grid(row=0, column=0, sticky='w', pady=5)
    points_var = tk.StringVar(value="0")
    ttk.Entry(adjust_frame, textvariable=points_var, width=15).grid(row=0, column=1, pady=5)
    ttk.Label(adjust_frame, text="Reason:").grid(row=1, column=0, sticky='w', pady=5)
    reason_var = tk.StringVar()
    ttk.Entry(adjust_frame, textvariable=reason_var, width=40).grid(row=1, column=1, pady=5, columnspan=2)
    def adjust_points():
        selection = customer_var.get()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a customer")
            return
        try:
            customer_id = int(selection.split(':')[0])
            points_change = int(points_var.get())
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE restaurant_customers
                    SET loyalty_points = loyalty_points + ?
                    WHERE customer_id = ?
                ''', (points_change, customer_id))
                conn.commit()
                conn.close()
                messagebox.showinfo("Success", f"Points adjusted by {points_change}")
                dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to adjust points: {e}")
    ttk.Button(adjust_frame, text="Apply Adjustment", command=adjust_points).grid(row=2, column=0, columnspan=3, pady=10)
    # Tier upgrade information
    info_frame = ttk.LabelFrame(tier_frame, text="Tier Information", padding=10)
    info_frame.pack(fill='both', expand=True, pady=10)
    info_text = ScrolledText(info_frame, height=10, width=70)
    info_text.pack(fill='both', expand=True)
    info_content = """Loyalty Tier Benefits:
ze (0-99 points):
2% discount on all orders
Birthday reward
er (100-499 points):
5% discount on all orders
Birthday reward
Priority reservations
 (500-999 points):
8% discount on all orders
Birthday reward
Priority reservations
Free appetizer monthly
inum (1000+ points):
10% discount on all orders
Birthday reward
Priority reservations
Free appetizer monthly
Exclusive menu access"""
    info_text.insert('1.0', info_content)
    info_text.config(state='disabled')
    # Advanced features buttons
    advanced_frame = ttk.LabelFrame(main_frame, text="Advanced Features", padding=10)
    advanced_frame.pack(fill='x', pady=10)
    btn_row = ttk.Frame(advanced_frame)
    btn_row.pack(fill='x', pady=5)
    ttk.Button(btn_row, text="View Loyalty Tiers",
              command=lambda: self.view_loyalty_tiers(dialog),
              width=20).pack(side='left', padx=5)
    ttk.Button(btn_row, text="Promote Customer Tier",
              command=lambda: self.promote_customer_tier(dialog),
              width=20).pack(side='left', padx=5)
    ttk.Button(btn_row, text="Award Bonus Points",
              command=lambda: self.award_bonus_points(dialog),
              width=20).pack(side='left', padx=5)
    ttk.Button(main_frame, text="Close", command=dialog.destroy).pack(pady=10)

def view_loyalty_tiers(self, parent_dialog):
    """View and manage loyalty tier structure"""
    tiers_dialog = tk.Toplevel(parent_dialog)
    tiers_dialog.title("Loyalty Tier Management")
    tiers_dialog.geometry("900x700")
    tiers_dialog.transient(parent_dialog)
    tiers_dialog.grab_set()
    main_frame = ttk.Frame(tiers_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Loyalty Tier Structure",
             font=('Arial', 14, 'bold')).pack(pady=10)
    # Tier definitions
    tier_frame = ttk.LabelFrame(main_frame, text="Tier Definitions", padding=15)
    tier_frame.pack(fill='both', expand=True, pady=10)
    # Tier details
    tiers = [
        {
            'name': 'Bronze',
            'range': '0-99 points',
            'discount': '2%',
            'benefits': ['Birthday reward', 'Email notifications']
        },
        {
            'name': 'Silver',
            'range': '100-499 points',
            'discount': '5%',
            'benefits': ['Birthday reward', 'Priority reservations', 'Email notifications']
        },
        {
            'name': 'Gold',
            'range': '500-999 points',
            'discount': '8%',
            'benefits': ['Birthday reward', 'Priority reservations', 'Free appetizer monthly',
                       'Exclusive promotions']
        },
        {
            'name': 'Platinum',
            'range': '1000+ points',
            'discount': '10%',
            'benefits': ['Birthday reward', 'Priority reservations', 'Free appetizer monthly',
                       'Exclusive menu access', 'VIP events', 'Dedicated support']
        }
    ]
    # Display tiers in a grid
    for idx, tier in enumerate(tiers):
        # Tier card frame
        tier_card = ttk.LabelFrame(tier_frame, text=f"{tier['name']} Tier", padding=10)
        tier_card.grid(row=idx//2, column=idx%2, padx=10, pady=10, sticky='nsew')
        # Tier details
        details_text = f"""
Points Range: {tier['range']}
Discount: {tier['discount']}

Benefits:
"""
        for benefit in tier['benefits']:
            details_text += f"  - {benefit}\n"

        ttk.Label(tier_card, text=details_text, justify='left',
                 font=('Arial', 9)).pack(anchor='w')
    # Configure grid weights
    tier_frame.columnconfigure(0, weight=1)
    tier_frame.columnconfigure(1, weight=1)
    # Statistics frame
    stats_frame = ttk.LabelFrame(main_frame, text="Customer Distribution by Tier", padding=15)
    stats_frame.pack(fill='x', pady=10)
    def update_tier_stats():
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                # Count customers in each tier
                cursor.execute('''
                    SELECT loyalty_tier, COUNT(*), AVG(loyalty_points)
                    FROM restaurant_customers
                    GROUP BY loyalty_tier
                    ORDER BY
                        CASE loyalty_tier
                            WHEN 'Platinum' THEN 4
                            WHEN 'Gold' THEN 3
                            WHEN 'Silver' THEN 2
                            WHEN 'Bronze' THEN 1
                            ELSE 0
                        END DESC
                ''')
                tier_stats = cursor.fetchall()
                cursor.execute("SELECT COUNT(*) FROM restaurant_customers")
                total_customers = cursor.fetchone()[0]
                conn.close()
                stats_text = "Customer Distribution:\n\n"
                for tier, count, avg_points in tier_stats:
                    percentage = (count / total_customers * 100) if total_customers > 0 else 0
                    bar = '█' * int(percentage / 2)
                    stats_text += f"{tier:12} {count:>4} customers ({percentage:>5.1f}%)  Avg: {avg_points:>6.1f} pts  {bar}\n"
                stats_label.config(text=stats_text)
        except sqlite3.Error as e:
            stats_label.config(text=f"Error loading statistics: {e}")
    stats_label = ttk.Label(stats_frame, text="Loading statistics...",
                           font=('Courier', 9), justify='left')
    stats_label.pack(anchor='w')
    update_tier_stats()
    # Tier upgrade rules
    rules_frame = ttk.LabelFrame(main_frame, text="Tier Upgrade Rules", padding=10)
    rules_frame.pack(fill='x', pady=10)
    rules_text = """
Automatic Tier Upgrades:
- Customers are automatically upgraded when they reach the points threshold for the next tier
- Points are earned at a rate of 1 point per GBP1 spent
- Points never expire
- Tier downgrades do not occur (tier is the highest achieved, not current points)

Manual Promotions:
- Managers can manually promote customers for exceptional loyalty
- Use the 'Promote Customer Tier' function to upgrade customers
- Manual promotions are permanent and recorded in the system
        """.strip()
    ttk.Label(rules_frame, text=rules_text, justify='left', font=('Arial', 9)).pack(anchor='w')
    # Buttons
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill='x', pady=10)
    ttk.Button(btn_frame, text="Refresh Statistics",
              command=update_tier_stats).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Close", command=tiers_dialog.destroy).pack(side='right', padx=5)

def promote_customer_tier(self, parent_dialog):
    """Manually promote a customer to a higher loyalty tier"""
    promote_dialog = tk.Toplevel(parent_dialog)
    promote_dialog.title("Promote Customer Tier")
    promote_dialog.geometry("700x600")
    promote_dialog.transient(parent_dialog)
    promote_dialog.grab_set()
    main_frame = ttk.Frame(promote_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Promote Customer to Higher Tier",
             font=('Arial', 14, 'bold')).pack(pady=10)
    ttk.Label(main_frame,
             text="Select a customer and promote them to a higher loyalty tier",
             foreground='blue').pack(pady=5)
    # Customer selection
    search_frame = ttk.LabelFrame(main_frame, text="Select Customer", padding=15)
    search_frame.pack(fill='x', pady=10)
    ttk.Label(search_frame, text="Customer:").grid(row=0, column=0, sticky='w', pady=5)
    customer_var = tk.StringVar()
    customer_combo = ttk.Combobox(search_frame, textvariable=customer_var,
                                  width=50, state='readonly')
    customer_combo.grid(row=0, column=1, pady=5, padx=10)
    # Load customers
    customer_data = {}
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT customer_id, name, loyalty_tier, loyalty_points
                FROM restaurant_customers
                ORDER BY name
            ''')
            customers = cursor.fetchall()
            conn.close()
            for cust in customers:
                label = f"{cust[1]} - {cust[2]} ({cust[3]} points)"
                customer_data[label] = cust
                customer_combo['values'] = list(customer_data.keys())
    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to load customers: {e}")
    # Current tier info
    current_info_frame = ttk.LabelFrame(main_frame, text="Current Information", padding=15)
    current_info_frame.pack(fill='x', pady=10)
    current_info_label = ttk.Label(current_info_frame,
                                  text="Select a customer to view their current tier",
                                  font=('Arial', 9))
    current_info_label.pack(pady=5)
    # New tier selection
    new_tier_frame = ttk.LabelFrame(main_frame, text="Promote To", padding=15)
    new_tier_frame.pack(fill='x', pady=10)
    ttk.Label(new_tier_frame, text="New Tier:").grid(row=0, column=0, sticky='w', pady=5)
    new_tier_var = tk.StringVar()
    new_tier_combo = ttk.Combobox(new_tier_frame, textvariable=new_tier_var,
                                 values=['Bronze', 'Silver', 'Gold', 'Platinum'],
                                 width=30, state='readonly')
    new_tier_combo.grid(row=0, column=1, pady=5, padx=10)
    ttk.Label(new_tier_frame, text="Reason:*").grid(row=1, column=0, sticky='w', pady=5)
    reason_entry = ttk.Entry(new_tier_frame, width=50)
    reason_entry.grid(row=1, column=1, pady=5, padx=10, columnspan=2)
    ttk.Label(new_tier_frame, text="Notes:").grid(row=2, column=0, sticky='nw', pady=5)
    notes_text = tk.Text(new_tier_frame, height=4, width=50)
    notes_text.grid(row=2, column=1, pady=5, padx=10)
    def update_customer_info(*args):
        """Update displayed customer information"""
        selection = customer_var.get()
        if selection and selection in customer_data:
            cust = customer_data[selection]
            info = f"""
Customer ID: {cust[0]}
Name: {cust[1]}
Current Tier: {cust[2]}
Loyalty Points: {cust[3]}
                """.strip()
            current_info_label.config(text=info)
            # Set default new tier to one above current
            tier_order = ['Bronze', 'Silver', 'Gold', 'Platinum']
            current_tier = cust[2]
            if current_tier in tier_order:
                current_idx = tier_order.index(current_tier)
                if current_idx < len(tier_order) - 1:
                    new_tier_combo.set(tier_order[current_idx + 1])
    customer_combo.bind('<<ComboboxSelected>>', update_customer_info)
    def promote_customer():
        """Execute the tier promotion"""
        selection = customer_var.get()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a customer")
            return
        if not new_tier_var.get():
            messagebox.showwarning("No Tier", "Please select a new tier")
            return
        if not reason_entry.get().strip():
            messagebox.showwarning("No Reason", "Please provide a reason for the promotion")
            return
        cust = customer_data[selection]
        current_tier = cust[2]
        new_tier = new_tier_var.get()
        # Validate promotion is an upgrade
        tier_order = ['Bronze', 'Silver', 'Gold', 'Platinum']
        if current_tier not in tier_order or new_tier not in tier_order:
            messagebox.showerror("Error", "Invalid tier selection")
            return
        current_idx = tier_order.index(current_tier)
        new_idx = tier_order.index(new_tier)
        if new_idx <= current_idx:
            messagebox.showerror("Invalid Promotion",
                               f"Cannot promote from {current_tier} to {new_tier}.\n"
                               f"New tier must be higher than current tier.")
            return
        # Confirm promotion
        confirm = messagebox.askyesno("Confirm Promotion",
                                     f"Promote {cust[1]} from {current_tier} to {new_tier}?\n\n"
                                     f"Reason: {reason_entry.get()}\n\n"
                                     f"This action will be recorded in the system.")
        if not confirm:
            return
        # Get current user
        current_user = "System"
        if AUTH_AVAILABLE:
            try:
                from education_system.systems.university.infrastructure.shared_context import get_auth
                auth = get_auth()
                if auth.current_user:
                    current_user = auth.current_user.get('username', 'Unknown')
            except (sqlite3.Error, tk.TclError, ValueError, TypeError):
                pass
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                # Create tier promotions table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS loyalty_tier_promotions (
                        promotion_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customer_id INTEGER NOT NULL,
                        old_tier TEXT NOT NULL,
                        new_tier TEXT NOT NULL,
                        reason TEXT,
                        notes TEXT,
                        promoted_by TEXT,
                        promotion_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (customer_id) REFERENCES restaurant_customers(customer_id)
                    )
                ''')
                # Update customer tier
                cursor.execute('''
                    UPDATE restaurant_customers
                    SET loyalty_tier = ?
                    WHERE customer_id = ?
                ''', (new_tier, cust[0]))
                # Record the promotion
                cursor.execute('''
                    INSERT INTO loyalty_tier_promotions
                    (customer_id, old_tier, new_tier, reason, notes, promoted_by)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (cust[0], current_tier, new_tier, reason_entry.get(),
                      notes_text.get('1.0', tk.END).strip(), current_user))
                conn.commit()
                conn.close()
                messagebox.showinfo("Success",
                                  f"Customer {cust[1]} promoted successfully!\n\n"
                                  f"{current_tier} → {new_tier}\n"
                                  f"Promoted by: {current_user}")
                promote_dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to promote customer: {e}")
    # Buttons
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill='x', pady=10)
    ttk.Button(btn_frame, text="Promote Customer",
              command=promote_customer).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Cancel",
              command=promote_dialog.destroy).pack(side='right', padx=5)

def award_bonus_points(self, parent_dialog):
    """Award promotional bonus points to customers"""
    bonus_dialog = tk.Toplevel(parent_dialog)
    bonus_dialog.title("Award Bonus Points")
    bonus_dialog.geometry("800x650")
    bonus_dialog.transient(parent_dialog)
    bonus_dialog.grab_set()
    main_frame = ttk.Frame(bonus_dialog, padding=20)
    main_frame.pack(fill='both', expand=True)
    ttk.Label(main_frame, text="Award Bonus Loyalty Points",
             font=('Arial', 14, 'bold')).pack(pady=10)
    ttk.Label(main_frame,
             text="Award bonus points to customers for promotions, events, or special occasions",
             foreground='blue').pack(pady=5)
    # Award type selection
    type_frame = ttk.LabelFrame(main_frame, text="Award Type", padding=15)
    type_frame.pack(fill='x', pady=10)
    award_type_var = tk.StringVar(value='individual')
    ttk.Radiobutton(type_frame, text="Individual Customer",
                   variable=award_type_var, value='individual').pack(anchor='w', pady=2)
    ttk.Radiobutton(type_frame, text="All Customers in Tier",
                   variable=award_type_var, value='tier').pack(anchor='w', pady=2)
    ttk.Radiobutton(type_frame, text="All Customers",
                   variable=award_type_var, value='all').pack(anchor='w', pady=2)
    # Selection frame (changes based on award type)
    selection_frame = ttk.LabelFrame(main_frame, text="Select Recipients", padding=15)
    selection_frame.pack(fill='x', pady=10)
    # Individual customer selection
    individual_frame = ttk.Frame(selection_frame)
    ttk.Label(individual_frame, text="Customer:").pack(side='left', padx=5)
    customer_var = tk.StringVar()
    customer_combo = ttk.Combobox(individual_frame, textvariable=customer_var,
                                  width=50, state='readonly')
    customer_combo.pack(side='left', padx=5)
    # Tier selection
    tier_frame_inner = ttk.Frame(selection_frame)
    ttk.Label(tier_frame_inner, text="Tier:").pack(side='left', padx=5)
    tier_var = tk.StringVar()
    tier_combo = ttk.Combobox(tier_frame_inner, textvariable=tier_var,
                              values=['Bronze', 'Silver', 'Gold', 'Platinum'],
                              width=20, state='readonly')
    tier_combo.pack(side='left', padx=5)
    # All customers frame
    all_frame = ttk.Frame(selection_frame)
    ttk.Label(all_frame, text="This will award points to ALL customers in the system",
             foreground='red', font=('Arial', 9, 'bold')).pack(pady=5)
    # Load customers
    customer_data = {}
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT customer_id, name, loyalty_tier, loyalty_points
                FROM restaurant_customers
                ORDER BY name
            ''')
            customers = cursor.fetchall()
            conn.close()
            for cust in customers:
                label = f"{cust[1]} - {cust[2]} ({cust[3]} points)"
                customer_data[label] = cust
            customer_combo['values'] = list(customer_data.keys())
    except sqlite3.Error as e:
        messagebox.showerror("Error", f"Failed to load customers: {e}")
    def update_selection_ui(*args):
        """Update UI based on award type selection"""
        # Hide all frames
        individual_frame.pack_forget()
        tier_frame_inner.pack_forget()
        all_frame.pack_forget()
        # Show appropriate frame
        if award_type_var.get() == 'individual':
            individual_frame.pack(fill='x', pady=5)
        elif award_type_var.get() == 'tier':
            tier_frame_inner.pack(fill='x', pady=5)
        else:  # 'all'
            all_frame.pack(fill='x', pady=5)
    award_type_var.trace('w', update_selection_ui)
    update_selection_ui()  # Initial setup
    # Points and reason
    details_frame = ttk.LabelFrame(main_frame, text="Bonus Details", padding=15)
    details_frame.pack(fill='x', pady=10)
    ttk.Label(details_frame, text="Bonus Points:*").grid(row=0, column=0, sticky='w', pady=5)
    points_entry = ttk.Entry(details_frame, width=20)
    points_entry.grid(row=0, column=1, sticky='w', pady=5, padx=10)
    points_entry.insert(0, "100")
    ttk.Label(details_frame, text="Reason/Campaign:*").grid(row=1, column=0, sticky='w', pady=5)
    reason_entry = ttk.Entry(details_frame, width=50)
    reason_entry.grid(row=1, column=1, pady=5, padx=10, columnspan=2)
    ttk.Label(details_frame, text="Description:").grid(row=2, column=0, sticky='nw', pady=5)
    desc_text = tk.Text(details_frame, height=4, width=50)
    desc_text.grid(row=2, column=1, pady=5, padx=10)
    # Preview
    preview_frame = ttk.LabelFrame(main_frame, text="Preview", padding=10)
    preview_frame.pack(fill='x', pady=10)
    preview_label = ttk.Label(preview_frame, text="Configure award details above",
                             font=('Arial', 9))
    preview_label.pack()
    def update_preview(*args):
        """Update preview of who will receive points"""
        try:
            points = int(points_entry.get() or 0)
            award_type = award_type_var.get()
            if award_type == 'individual':
                if customer_var.get():
                    cust = customer_data[customer_var.get()]
                    preview_label.config(
                        text=f"Will award {points} points to:\n{cust[1]} (Current: {cust[3]} → New: {cust[3] + points})")
                else:
                    preview_label.config(text="Please select a customer")
            elif award_type == 'tier':
                if tier_var.get():
                    conn = get_db_connection()
                    if conn:
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT COUNT(*) FROM restaurant_customers
                            WHERE loyalty_tier = ?
                        ''', (tier_var.get(),))
                        count = cursor.fetchone()[0]
                        conn.close()
                        preview_label.config(
                            text=f"Will award {points} points to {count} customers in {tier_var.get()} tier")
                else:
                    preview_label.config(text="Please select a tier")
            else:  # 'all'
                conn = get_db_connection()
                if conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM restaurant_customers")
                    count = cursor.fetchone()[0]
                    conn.close()
                    preview_label.config(
                        text=f"Will award {points} points to ALL {count} customers")
        except sqlite3.Error:
            preview_label.config(text="Configure award details above")
    points_entry.bind('<KeyRelease>', update_preview)
    customer_var.trace('w', update_preview)
    tier_var.trace('w', update_preview)
    award_type_var.trace('w', update_preview)
    def award_points():
        """Execute the bonus points award"""
        try:
            points = int(points_entry.get())
            if points <= 0:
                messagebox.showwarning("Invalid Points", "Points must be greater than 0")
                return
        except ValueError:
            messagebox.showwarning("Invalid Input", "Please enter a valid number of points")
            return
        if not reason_entry.get().strip():
            messagebox.showwarning("Missing Reason", "Please provide a reason for the bonus points")
            return
        award_type = award_type_var.get()
        # Validate selection
        if award_type == 'individual' and not customer_var.get():
            messagebox.showwarning("No Selection", "Please select a customer")
            return
        elif award_type == 'tier' and not tier_var.get():
            messagebox.showwarning("No Selection", "Please select a tier")
            return
        # Get current user
        current_user = "System"
        if AUTH_AVAILABLE:
            try:
                from education_system.systems.university.infrastructure.shared_context import get_auth
                auth = get_auth()
                if auth.current_user:
                    current_user = auth.current_user.get('username', 'Unknown')
            except (sqlite3.Error, tk.TclError):
                pass
        # Confirm award
        if award_type == 'all':
            confirm = messagebox.askyesno("Confirm Award",
                                        f"Award {points} bonus points to ALL customers?\n\n"
                                        f"Reason: {reason_entry.get()}\n\n"
                                        f"This cannot be undone.")
        else:
            confirm = messagebox.askyesno("Confirm Award",
                                        f"Award {points} bonus points?\n\n"
                                        f"Reason: {reason_entry.get()}")
        if not confirm:
            return
        try:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                # Create bonus points table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS loyalty_bonus_points (
                        bonus_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        customer_id INTEGER,
                        points_awarded INTEGER NOT NULL,
                        reason TEXT NOT NULL,
                        description TEXT,
                        awarded_by TEXT,
                        award_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (customer_id) REFERENCES restaurant_customers(customer_id)
                    )
                ''')
                customers_affected = 0
                if award_type == 'individual':
                    cust = customer_data[customer_var.get()]
                    cursor.execute('''
                        UPDATE restaurant_customers
                        SET loyalty_points = loyalty_points + ?
                        WHERE customer_id = ?
                    ''', (points, cust[0]))
                    cursor.execute('''
                        INSERT INTO loyalty_bonus_points
                        (customer_id, points_awarded, reason, description, awarded_by)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (cust[0], points, reason_entry.get(),
                          desc_text.get('1.0', tk.END).strip(), current_user))
                    customers_affected = 1
                elif award_type == 'tier':
                    # Get all customers in tier
                    cursor.execute('''
                        SELECT customer_id FROM restaurant_customers
                        WHERE loyalty_tier = ?
                    ''', (tier_var.get(),))
                    tier_customers = cursor.fetchall()
                    tier_customer_ids = [row[0] for row in tier_customers]
                    if tier_customer_ids:
                        # Batch update loyalty points to avoid N+1
                        placeholders = ','.join('?' * len(tier_customer_ids))
                        cursor.execute('''
                            UPDATE restaurant_customers
                            SET loyalty_points = loyalty_points + ?
                            WHERE customer_id IN (''' + placeholders + ''')
                        ''', [points] + tier_customer_ids)
                        # Batch insert bonus points records to avoid N+1
                        reason_text = reason_entry.get()
                        description_text = desc_text.get('1.0', tk.END).strip()
                        bonus_data = [
                            (cust_id, points, reason_text, description_text, current_user)
                            for cust_id in tier_customer_ids
                        ]
                        cursor.executemany('''
                            INSERT INTO loyalty_bonus_points
                            (customer_id, points_awarded, reason, description, awarded_by)
                            VALUES (?, ?, ?, ?, ?)
                        ''', bonus_data)
                    customers_affected = len(tier_customers)
                else:  # 'all'
                    cursor.execute("SELECT customer_id FROM restaurant_customers")
                    all_customers = cursor.fetchall()
                    all_customer_ids = [row[0] for row in all_customers]
                    if all_customer_ids:
                        # Batch update loyalty points to avoid N+1
                        cursor.execute('''
                            UPDATE restaurant_customers
                            SET loyalty_points = loyalty_points + ?
                        ''', (points,))
                        # Batch insert bonus points records to avoid N+1
                        reason_text = reason_entry.get()
                        description_text = desc_text.get('1.0', tk.END).strip()
                        bonus_data = [
                            (cust_id, points, reason_text, description_text, current_user)
                            for cust_id in all_customer_ids
                        ]
                        cursor.executemany('''
                            INSERT INTO loyalty_bonus_points
                            (customer_id, points_awarded, reason, description, awarded_by)
                            VALUES (?, ?, ?, ?, ?)
                        ''', bonus_data)
                    customers_affected = len(all_customers)
                conn.commit()
                conn.close()
                messagebox.showinfo("Success",
                                  f"Bonus points awarded successfully!\n\n"
                                  f"Points Awarded: {points}\n"
                                  f"Customers Affected: {customers_affected}\n"
                                  f"Awarded by: {current_user}")
                bonus_dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to award bonus points: {e}")
    # Buttons
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill='x', pady=10)
    ttk.Button(btn_frame, text="Award Points",
              command=award_points).pack(side='left', padx=5)
    ttk.Button(btn_frame, text="Cancel",
              command=bonus_dialog.destroy).pack(side='right', padx=5)

