import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.constants import paths
from datetime import datetime, timedelta
import hashlib
import json
import sys
import os
import logging
from typing import Dict, List, Optional, Tuple, Any
import threading
import queue
from education_system.university_system.infrastructure.email.template_utils import render_template
from education_system.university_system.infrastructure.auth import UserAuth
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

# Use centralized path configuration
DEFAULT_DB_PATH = paths.DEFAULT_DB_PATH

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

try:
    # Import CLI components to maintain backwards compatibility. If available,
    # include the full database initializer so the GUI can create the
    # comprehensive schema when running stand‑alone.
    from education_system.university_system.infrastructure.database.db import get_connection
    from education_system.university_system.modules.domain.student_affairs.student_union.administration.student_union_core import init_student_union_db
    CLI_AVAILABLE = True
except (ImportError, ModuleNotFoundError):
    print("Warning: CLI system not available. Some features may be limited.")
    student_union_cli = None
    init_student_union_db = None
    CLI_AVAILABLE = False
    

class EquipmentCheckoutDialog:
    """Dialog for checking out equipment"""

    def __init__(self, parent, auth_manager, equipment_id, equipment_name):
        self.parent = parent
        self.auth = auth_manager
        self.equipment_id = equipment_id
        self.equipment_name = equipment_name

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Check Out Equipment")
        self.dialog.geometry("500x400")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        title_label = ttk.Label(main_frame, text=f"Check Out: {self.equipment_name}",
                               font=('Arial', 12, 'bold'))
        title_label.pack(pady=(0, 20))

        # Return date
        ttk.Label(main_frame, text="Expected Return Date:").pack(anchor='w', pady=(0, 5))
        self.return_date_var = tk.StringVar()
        ttk.Entry(main_frame, textvariable=self.return_date_var, width=30).pack(fill='x', pady=(0, 10))
        ttk.Label(main_frame, text="(Format: YYYY-MM-DD)", font=('Arial', 8)).pack(anchor='w', pady=(0, 10))

        # Purpose
        ttk.Label(main_frame, text="Purpose:").pack(anchor='w', pady=(0, 5))
        self.purpose_text = scrolledtext.ScrolledText(main_frame, height=8, wrap=tk.WORD)
        self.purpose_text.pack(fill='both', expand=True, pady=(0, 10))

        # Club (optional)
        ttk.Label(main_frame, text="For Club (optional):").pack(anchor='w', pady=(0, 5))
        self.club_var = tk.StringVar()
        self.club_combo = ttk.Combobox(main_frame, textvariable=self.club_var, width=27)
        self.club_combo.pack(fill='x', pady=(0, 10))
        self.load_clubs()

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Check Out", command=self.checkout).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='left')

    def load_clubs(self):
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            if not result:
                conn.close()
                return

            student_id = result[0]

            cursor.execute('''
            SELECT DISTINCT sc.club_id, sc.club_name
            FROM student_clubs sc
            INNER JOIN club_members cm ON sc.club_id = cm.club_id
            WHERE cm.student_id = ? AND sc.status = 'active'
            ORDER BY sc.club_name
            ''', (student_id,))

            clubs = cursor.fetchall()
            self.club_data = {f"{club[1]}": club[0] for club in clubs}
            self.club_combo['values'] = ['None'] + list(self.club_data.keys())
            self.club_combo.current(0)

            conn.close()
        except sqlite3.Error as e:
            pass

    def checkout(self):
        return_date = self.return_date_var.get().strip()
        purpose = self.purpose_text.get(1.0, tk.END).strip()

        if not return_date or not purpose:
            messagebox.showwarning("Warning", "Please fill in all required fields.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            student_id = cursor.fetchone()[0]

            selected_club = self.club_var.get()
            club_id = self.club_data.get(selected_club) if selected_club != 'None' else None

            cursor.execute('''
            INSERT INTO equipment_checkouts (equipment_id, borrower_id, club_id, checkout_date,
                                            expected_return, condition_out, notes, status)
            VALUES (?, ?, ?, ?, ?, 'good', ?, 'checked_out')
            ''', (self.equipment_id, student_id, club_id, datetime.now().isoformat(),
                 return_date, purpose))

            cursor.execute('''
            UPDATE union_equipment SET availability_status = 'checked_out'
            WHERE equipment_id = ?
            ''', (self.equipment_id,))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", "Equipment checked out successfully!")
            self.dialog.destroy()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to check out equipment: {str(e)}")



class MyEquipmentDialog:
    """Dialog for viewing user's checked out equipment"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("My Equipment")
        self.dialog.geometry("900x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_data()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        title_label = ttk.Label(main_frame, text="My Checked Out Equipment", font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 10))

        list_frame = ttk.LabelFrame(main_frame, text="Current Checkouts")
        list_frame.pack(fill='both', expand=True, pady=(0, 10))

        columns = ('Equipment', 'Checkout Date', 'Expected Return', 'Condition', 'Status')
        self.equipment_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)

        for col in columns:
            self.equipment_tree.heading(col, text=col)
            self.equipment_tree.column(col, width=150)

        scrollbar = ttk.Scrollbar(list_frame, orient='vertical', command=self.equipment_tree.yview)
        self.equipment_tree.configure(yscrollcommand=scrollbar.set)

        self.equipment_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Return Selected", command=self.return_equipment).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        try:
            if not self.auth or not self.auth.current_user:
                return

            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute('SELECT student_id FROM users WHERE id = ?', (self.auth.current_user['id'],))
            result = cursor.fetchone()
            if not result:
                conn.close()
                return

            student_id = result[0]

            cursor.execute('''
            SELECT ue.equipment_name, ec.checkout_date, ec.expected_return,
                   ec.condition_out, ec.status, ec.checkout_id
            FROM equipment_checkouts ec
            INNER JOIN union_equipment ue ON ec.equipment_id = ue.equipment_id
            WHERE ec.borrower_id = ? AND ec.status = 'checked_out'
            ORDER BY ec.expected_return
            ''', (student_id,))

            equipment = cursor.fetchall()

            for item in equipment:
                self.equipment_tree.insert('', 'end', values=item[:5], tags=(item[5],))

            conn.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to load equipment: {str(e)}")

    def return_equipment(self):
        selection = self.equipment_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select equipment to return.")
            return

        item = self.equipment_tree.item(selection[0])
        checkout_id = item['tags'][0] if item['tags'] else None

        if checkout_id and messagebox.askyesno("Confirm", "Return this equipment?"):
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('''
                UPDATE equipment_checkouts SET status = 'returned', actual_return = ?,
                       condition_in = 'good'
                WHERE checkout_id = ?
                ''', (datetime.now().isoformat(), checkout_id))

                cursor.execute('''
                SELECT equipment_id FROM equipment_checkouts WHERE checkout_id = ?
                ''', (checkout_id,))
                equipment_id = cursor.fetchone()[0]

                cursor.execute('''
                UPDATE union_equipment SET availability_status = 'available'
                WHERE equipment_id = ?
                ''', (equipment_id,))

                conn.commit()
                conn.close()

                messagebox.showinfo("Success", "Equipment returned successfully!")
                self.load_data()
            except sqlite3.Error as e:
                messagebox.showerror("Error", f"Failed to return equipment: {str(e)}")



class CheckOutEquipmentDialog:
    """Dialog for checking out equipment"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Check Out Equipment")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="✅ Check Out Equipment",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Equipment selection
        select_frame = ttk.LabelFrame(main_frame, text="Select Equipment")
        select_frame.pack(fill='x', pady=(0, 15))

        select_content = ttk.Frame(select_frame)
        select_content.pack(fill='x', padx=15, pady=10)

        ttk.Label(select_content, text="Equipment:").grid(row=0, column=0, sticky='w', pady=5)
        equipment_combo = ttk.Combobox(select_content, width=40, state='readonly')
        equipment_combo['values'] = ('Professional Camera (Canon EOS R5)',
                                     'Wireless Microphone System',
                                     'LED Light Panel (3-pack)',
                                     'Tripod (Manfrotto Pro)')
        equipment_combo.current(0)
        equipment_combo.grid(row=0, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(select_content, text="Quantity:").grid(row=1, column=0, sticky='w', pady=5)
        qty_spin = ttk.Spinbox(select_content, from_=1, to=5, width=10)
        qty_spin.set(1)
        qty_spin.grid(row=1, column=1, sticky='w', padx=10, pady=5)

        select_content.columnconfigure(1, weight=1)

        # Checkout details
        details_frame = ttk.LabelFrame(main_frame, text="Checkout Details")
        details_frame.pack(fill='x', pady=(0, 15))

        details_content = ttk.Frame(details_frame)
        details_content.pack(fill='x', padx=15, pady=10)

        ttk.Label(details_content, text="Your Name:").grid(row=0, column=0, sticky='w', pady=5)
        ttk.Entry(details_content, width=40).grid(row=0, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(details_content, text="Student ID:").grid(row=1, column=0, sticky='w', pady=5)
        ttk.Entry(details_content, width=40).grid(row=1, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(details_content, text="Email:").grid(row=2, column=0, sticky='w', pady=5)
        ttk.Entry(details_content, width=40).grid(row=2, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(details_content, text="Phone:").grid(row=3, column=0, sticky='w', pady=5)
        ttk.Entry(details_content, width=40).grid(row=3, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(details_content, text="Return Date:").grid(row=4, column=0, sticky='w', pady=5)
        ttk.Entry(details_content, width=40).grid(row=4, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(details_content, text="Purpose:").grid(row=5, column=0, sticky='w', pady=5)
        purpose_text = scrolledtext.ScrolledText(details_content, height=3, width=40)
        purpose_text.grid(row=5, column=1, sticky='ew', padx=10, pady=5)

        details_content.columnconfigure(1, weight=1)

        # Terms
        terms_frame = ttk.LabelFrame(main_frame, text="Terms & Conditions")
        terms_frame.pack(fill='x', pady=(0, 15))

        terms_text = """☑ I agree to return equipment on time
☑ I am responsible for any damage or loss
☑ Late returns incur £10/day fee
☑ I have received training on this equipment"""

        ttk.Label(terms_frame, text=terms_text, justify='left').pack(padx=15, pady=10)

        agree_var = tk.BooleanVar()
        ttk.Checkbutton(terms_frame, text="I agree to all terms and conditions", variable=agree_var).pack(padx=15, pady=(0, 10))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Complete Checkout", command=self.complete_checkout).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='right')

    def complete_checkout(self):
        messagebox.showinfo("Checkout Complete",
                          "Equipment checked out successfully!\n\n" +
                          "Equipment: Professional Camera (Canon EOS R5)\n" +
                          "Return Date: 2025-04-05\n" +
                          "Checkout ID: CHK-2025-00234\n\n" +
                          "IMPORTANT:\n" +
                          "- Return by due date to avoid fees\n" +
                          "- Inspect equipment before leaving\n" +
                          "- Report any damage immediately\n\n" +
                          "Confirmation email sent.")
        self.dialog.destroy()



class ReturnEquipmentDialog:
    """Dialog for returning equipment"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Return Equipment")
        self.dialog.geometry("700x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="↩️ Return Equipment",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Your checkouts
        checkouts_frame = ttk.LabelFrame(main_frame, text="Your Current Checkouts")
        checkouts_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('ID', 'Equipment', 'Checkout Date', 'Due Date', 'Days Left', 'Status')
        tree = ttk.Treeview(checkouts_frame, columns=columns, show='tree headings', height=6)

        for col in columns:
            tree.heading(col, text=col)
            if col == 'Equipment':
                tree.column(col, width=200)
            else:
                tree.column(col, width=90)

        tree.pack(fill='both', expand=True, padx=5, pady=5)

        # Sample checkouts
        checkouts = [
            ("CHK234", "Professional Camera (Canon EOS R5)", "2025-03-29", "2025-04-05", "3 days", "On Time"),
            ("CHK220", "Wireless Microphone System", "2025-03-25", "2025-04-01", "0 days", "Due Today"),
            ("CHK198", "Tripod (Manfrotto Pro)", "2025-03-15", "2025-03-22", "-5 days", "OVERDUE")
        ]

        for checkout in checkouts:
            tree.insert('', 'end', values=checkout)

        # Return form
        return_frame = ttk.LabelFrame(main_frame, text="Return Equipment")
        return_frame.pack(fill='x', pady=(0, 15))

        return_content = ttk.Frame(return_frame)
        return_content.pack(fill='x', padx=15, pady=10)

        ttk.Label(return_content, text="Checkout ID:").grid(row=0, column=0, sticky='w', pady=5)
        ttk.Entry(return_content, width=30).grid(row=0, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(return_content, text="Condition:").grid(row=1, column=0, sticky='w', pady=5)
        condition_combo = ttk.Combobox(return_content, width=28, state='readonly')
        condition_combo['values'] = ('Same as checkout (Good)', 'Excellent', 'Minor wear', 'Damaged - Minor', 'Damaged - Major')
        condition_combo.current(0)
        condition_combo.grid(row=1, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(return_content, text="Notes/Issues:").grid(row=2, column=0, sticky='nw', pady=5)
        notes_text = scrolledtext.ScrolledText(return_content, height=4, width=30)
        notes_text.grid(row=2, column=1, sticky='ew', padx=10, pady=5)
        notes_text.insert('1.0', "Equipment in good condition, no issues to report.")

        return_content.columnconfigure(1, weight=1)

        # Late fee warning
        fee_frame = ttk.Frame(main_frame)
        fee_frame.pack(fill='x', pady=(0, 15))

        ttk.Label(fee_frame, text="⚠️ Late Fee Calculation:", font=('Arial', 10, 'bold')).pack(anchor='w')
        ttk.Label(fee_frame, text="CHK198 (Tripod): 5 days overdue × £10/day = £50", foreground='red').pack(anchor='w', padx=20)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Process Return", command=self.process_return).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Report Damage", command=self.report_damage).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Cancel", command=self.dialog.destroy).pack(side='right')

    def process_return(self):
        messagebox.showinfo("Return Processed",
                          "Equipment return processed!\n\n" +
                          "Checkout ID: CHK234\n" +
                          "Equipment: Professional Camera (Canon EOS R5)\n" +
                          "Returned: 2025-04-02\n" +
                          "Condition: Same as checkout (Good)\n" +
                          "Late Fee: £0.00\n\n" +
                          "Thank you for returning on time!\n" +
                          "Confirmation email sent.")

    def report_damage(self):
        messagebox.showinfo("Report Damage",
                          "Damage Report Form:\n\n" +
                          "Please provide:\n" +
                          "- Description of damage\n" +
                          "- Photos if possible\n" +
                          "- How damage occurred\n\n" +
                          "Damage assessment will be conducted\n" +
                          "and you'll be notified of any charges.")



class ViewMyEquipmentCheckoutsDialog:
    """Dialog for viewing personal equipment checkouts"""

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("My Equipment Checkouts")
        self.dialog.geometry("1000x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="📚 My Equipment Checkouts",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Summary
        summary_frame = ttk.LabelFrame(main_frame, text="Summary")
        summary_frame.pack(fill='x', pady=(0, 15))

        summary_text = """Current Checkouts: 3
Overdue Items: 1
Total Borrowed (All Time): 18
On-Time Returns: 94% (17/18)"""

        ttk.Label(summary_frame, text=summary_text, justify='left', font=('Courier', 10)).pack(padx=15, pady=10)

        # Create notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Current tab
        current_frame = ttk.Frame(notebook)
        notebook.add(current_frame, text="Current Checkouts")

        columns = ('ID', 'Equipment', 'Checkout Date', 'Due Date', 'Days Left', 'Status')
        current_tree = ttk.Treeview(current_frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            current_tree.heading(col, text=col)
            if col == 'Equipment':
                current_tree.column(col, width=250)
            else:
                current_tree.column(col, width=110)

        current_tree.pack(fill='both', expand=True, padx=10, pady=10)

        current_checkouts = [
            ("CHK234", "Professional Camera (Canon EOS R5)", "2025-03-29", "2025-04-05", "3 days", "On Time"),
            ("CHK220", "Wireless Microphone System", "2025-03-25", "2025-04-01", "0 days", "Due Today"),
            ("CHK198", "Tripod (Manfrotto Pro)", "2025-03-15", "2025-03-22", "-5 days", "OVERDUE")
        ]

        for checkout in current_checkouts:
            current_tree.insert('', 'end', values=checkout)

        # History tab
        history_frame = ttk.Frame(notebook)
        notebook.add(history_frame, text="Checkout History")

        history_columns = ('ID', 'Equipment', 'Checkout Date', 'Return Date', 'Days Borrowed', 'Status')
        history_tree = ttk.Treeview(history_frame, columns=history_columns, show='tree headings', height=10)

        for col in history_columns:
            history_tree.heading(col, text=col)
            if col == 'Equipment':
                history_tree.column(col, width=250)
            else:
                history_tree.column(col, width=110)

        history_tree.pack(fill='both', expand=True, padx=10, pady=10)

        history_checkouts = [
            ("CHK187", "LED Light Panel (3-pack)", "2025-03-10", "2025-03-17", "7 days", "Returned On Time"),
            ("CHK156", "Laptop (Dell XPS 15)", "2025-02-25", "2025-03-04", "7 days", "Returned On Time"),
            ("CHK134", "Portable Speaker (JBL)", "2025-02-15", "2025-02-18", "3 days", "Returned On Time"),
            ("CHK112", "Projector (Epson 4K)", "2025-01-20", "2025-01-27", "7 days", "Returned On Time")
        ]

        for checkout in history_checkouts:
            history_tree.insert('', 'end', values=checkout)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Renew Checkout", command=self.renew).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Return Equipment", command=self.return_equipment).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Export History", command=self.export_history).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def renew(self):
        messagebox.showinfo("Renew Checkout",
                          "Renew checkout for 7 more days?\n\n" +
                          "Equipment: Professional Camera (Canon EOS R5)\n" +
                          "Current Due Date: 2025-04-05\n" +
                          "New Due Date: 2025-04-12\n\n" +
                          "Renewals allowed: 2/3")

    def return_equipment(self):
        dialog = ReturnEquipmentDialog(self.dialog, self.auth)

    def export_history(self):
        messagebox.showinfo("Export", "Checkout history exported to:\nmy_equipment_checkouts.csv\n\nIncludes all current and past checkouts.")



def open_checkout_equipment_dialog(self):
    """Open checkout equipment"""
    dialog = CheckOutEquipmentDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_return_equipment_dialog(self):
    """Open return equipment"""
    dialog = ReturnEquipmentDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def open_my_equipment_checkouts_dialog(self):
    """Open my equipment checkouts"""
    dialog = ViewMyEquipmentCheckoutsDialog(self.root, self.auth_manager)
    self.root.wait_window(dialog.dialog)


def check_out_equipment_gui(self):
    """Check out equipment"""
    try:
        dialog = EquipmentBrowseDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def return_equipment_gui(self):
    """Return equipment"""
    try:
        dialog = MyEquipmentDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


def view_my_equipment_checkouts(self):
    """View my equipment checkouts"""
    try:
        dialog = MyEquipmentDialog(self.root, self.auth_manager)
        self.root.wait_window(dialog.dialog)
    except (tk.TclError, AttributeError) as e:
        messagebox.showerror("Error", f"Failed to open dialog: {str(e)}")


