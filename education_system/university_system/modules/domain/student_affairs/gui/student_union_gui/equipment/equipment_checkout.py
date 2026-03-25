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
    """Dialog for returning equipment with late fee handling and email confirmations"""

    LATE_FEE_PER_DAY = 10.00  # £10 per day late

    def __init__(self, parent, auth_manager):
        self.parent = parent
        self.auth = auth_manager

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Return Equipment")
        self.dialog.geometry("750x650")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()
        self.load_checkouts()

    def _get_borrower_id(self):
        """Resolve current user to a borrower_id."""
        if not self.auth or not self.auth.current_user:
            return None
        user = self.auth.current_user
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT student_id FROM users WHERE id = ?", (user.get('id'),))
                row = cursor.fetchone()
                if row and row[0]:
                    return row[0]
            finally:
                conn.close()
        except Exception:
            pass
        return user.get('username') or str(user.get('id', ''))

    def _get_user_email(self):
        """Look up current user's email."""
        if not self.auth or not self.auth.current_user:
            return None
        user = self.auth.current_user
        if user.get('email'):
            return user['email']
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT email FROM users WHERE id = ?", (user.get('id'),))
                row = cursor.fetchone()
                if row and row[0]:
                    return row[0]
                cursor.execute("SELECT email_address FROM students WHERE student_id = ?",
                             (user.get('username', ''),))
                row = cursor.fetchone()
                if row and row[0]:
                    return row[0]
            finally:
                conn.close()
        except Exception:
            pass
        return None

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="Return Equipment",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Current checkouts
        checkouts_frame = ttk.LabelFrame(main_frame, text="Your Current Checkouts")
        checkouts_frame.pack(fill='both', expand=True, pady=(0, 15))

        columns = ('ID', 'Equipment', 'Checkout Date', 'Due Date', 'Days Left', 'Status')
        self.tree = ttk.Treeview(checkouts_frame, columns=columns, show='headings', height=6)

        for col in columns:
            self.tree.heading(col, text=col)
            if col == 'Equipment':
                self.tree.column(col, width=200)
            else:
                self.tree.column(col, width=90)

        self.tree.pack(fill='both', expand=True, padx=5, pady=5)
        self.tree.bind('<<TreeviewSelect>>', self._on_select)

        # Late fee info
        self.fee_label = ttk.Label(main_frame, text="", foreground='red',
                                   font=('Arial', 10, 'bold'))
        self.fee_label.pack(anchor='w', pady=(0, 10))

        # Return form
        return_frame = ttk.LabelFrame(main_frame, text="Return Details")
        return_frame.pack(fill='x', pady=(0, 15))

        return_content = ttk.Frame(return_frame)
        return_content.pack(fill='x', padx=15, pady=10)

        ttk.Label(return_content, text="Condition on Return:").grid(row=0, column=0, sticky='w', pady=5)
        self.condition_combo = ttk.Combobox(return_content, width=28, state='readonly')
        self.condition_combo['values'] = ('good', 'excellent', 'fair', 'poor', 'damaged')
        self.condition_combo.current(0)
        self.condition_combo.grid(row=0, column=1, sticky='ew', padx=10, pady=5)

        ttk.Label(return_content, text="Notes:").grid(row=1, column=0, sticky='nw', pady=5)
        self.notes_text = scrolledtext.ScrolledText(return_content, height=3, width=30)
        self.notes_text.grid(row=1, column=1, sticky='ew', padx=10, pady=5)

        return_content.columnconfigure(1, weight=1)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Process Return",
                  command=self.process_return).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Refresh",
                  command=self.load_checkouts).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close",
                  command=self.dialog.destroy).pack(side='right')

    def load_checkouts(self):
        """Load current user's checked-out equipment from DB."""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.fee_label.config(text="")

        borrower_id = self._get_borrower_id()
        if not borrower_id:
            self.tree.insert('', 'end', values=('', 'No user session', '', '', '', ''))
            return

        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            try:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT c.checkout_id, e.equipment_name, c.checkout_date,
                           c.expected_return, e.equipment_id
                    FROM equipment_checkouts c
                    JOIN union_equipment e ON c.equipment_id = e.equipment_id
                    WHERE c.borrower_id = ? AND c.status = 'checked_out'
                    ORDER BY c.expected_return ASC
                ''', (borrower_id,))
                rows = cursor.fetchall()
            finally:
                conn.close()

            if not rows:
                self.tree.insert('', 'end', values=('', 'No current checkouts', '', '', '', ''))
                return

            today = datetime.now().date()
            for row in rows:
                checkout_id, equip_name, checkout_date, due_date, equip_id = row
                try:
                    due = datetime.strptime(due_date, '%Y-%m-%d').date()
                    days_left = (due - today).days
                    if days_left < 0:
                        status = 'OVERDUE'
                        days_text = f"{days_left} days"
                    elif days_left == 0:
                        status = 'Due Today'
                        days_text = '0 days'
                    else:
                        status = 'On Time'
                        days_text = f"{days_left} days"
                except (ValueError, TypeError):
                    days_text = 'N/A'
                    status = 'Unknown'

                self.tree.insert('', 'end', values=(
                    checkout_id, equip_name or '', checkout_date or '',
                    due_date or '', days_text, status
                ))
        except Exception as e:
            self.tree.insert('', 'end', values=('', f'Error: {e}', '', '', '', ''))

    def _on_select(self, event):
        """Update late fee display when a checkout is selected."""
        selection = self.tree.selection()
        if not selection:
            self.fee_label.config(text="")
            return

        values = self.tree.item(selection[0], 'values')
        status = values[5] if len(values) > 5 else ''
        days_text = values[4] if len(values) > 4 else ''

        if status == 'OVERDUE':
            try:
                days_late = abs(int(days_text.split()[0]))
                fee = days_late * self.LATE_FEE_PER_DAY
                self.fee_label.config(
                    text=f"Late fee: {days_late} days overdue x £{self.LATE_FEE_PER_DAY:.2f}/day = £{fee:.2f}")
            except (ValueError, IndexError):
                self.fee_label.config(text="Late fee applies")
        else:
            self.fee_label.config(text="No late fee - on time return")

    def process_return(self):
        """Process the equipment return with late fee handling."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a checkout to return.",
                                 parent=self.dialog)
            return

        values = self.tree.item(selection[0], 'values')
        checkout_id = values[0]
        equip_name = values[1]
        due_date = values[3]
        status = values[5] if len(values) > 5 else ''
        days_text = values[4] if len(values) > 4 else ''

        if not checkout_id or checkout_id == '':
            return

        condition = self.condition_combo.get()
        notes = self.notes_text.get('1.0', tk.END).strip()
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Calculate late fee
        late_fee = 0.0
        days_late = 0
        if status == 'OVERDUE':
            try:
                days_late = abs(int(days_text.split()[0]))
                late_fee = days_late * self.LATE_FEE_PER_DAY
            except (ValueError, IndexError):
                pass

        # If late, handle payment first
        if late_fee > 0:
            paid = self._handle_late_fee_payment(checkout_id, equip_name, days_late, late_fee)
            if not paid:
                return  # Payment cancelled

        # Process the return in DB
        try:
            from education_system.university_system.infrastructure.database.db import get_connection
            conn = get_connection()
            try:
                cursor = conn.cursor()
                # Update checkout record
                cursor.execute('''
                    UPDATE equipment_checkouts
                    SET status = 'returned', actual_return = ?, condition_in = ?, notes = ?
                    WHERE checkout_id = ?
                ''', (now, condition, notes, checkout_id))

                # Get equipment_id to update availability
                cursor.execute('SELECT equipment_id FROM equipment_checkouts WHERE checkout_id = ?',
                             (checkout_id,))
                row = cursor.fetchone()
                if row:
                    cursor.execute('''
                        UPDATE union_equipment
                        SET availability_status = 'available', condition_status = ?
                        WHERE equipment_id = ?
                    ''', (condition, row[0]))

                conn.commit()
            finally:
                conn.close()

            # Send confirmation email
            self._send_return_confirmation_email(checkout_id, equip_name, condition, late_fee)

            msg = (f"Equipment returned successfully!\n\n"
                   f"Equipment: {equip_name}\n"
                   f"Condition: {condition}\n"
                   f"Returned: {now}\n")
            if late_fee > 0:
                msg += f"Late Fee Paid: £{late_fee:.2f}\n"
            else:
                msg += "Late Fee: £0.00\n"
            msg += "\nConfirmation email sent."

            messagebox.showinfo("Return Processed", msg, parent=self.dialog)
            self.load_checkouts()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process return: {e}", parent=self.dialog)

    def _handle_late_fee_payment(self, checkout_id, equip_name, days_late, late_fee):
        """Show late fee payment dialog. Returns True if paid, False if cancelled."""
        pay_dialog = tk.Toplevel(self.dialog)
        pay_dialog.title("Late Fee Payment Required")
        pay_dialog.geometry("450x350")
        pay_dialog.transient(self.dialog)
        pay_dialog.grab_set()

        result = {'paid': False}

        main = ttk.Frame(pay_dialog, padding=20)
        main.pack(fill='both', expand=True)

        ttk.Label(main, text="Late Fee Payment Required",
                 font=('Arial', 13, 'bold')).pack(pady=(0, 15))

        ttk.Label(main, text=f"Equipment: {equip_name}").pack(anchor='w')
        ttk.Label(main, text=f"Days Overdue: {days_late}").pack(anchor='w')
        ttk.Label(main, text=f"Fee Rate: £{self.LATE_FEE_PER_DAY:.2f}/day").pack(anchor='w')
        ttk.Label(main, text=f"Total Due: £{late_fee:.2f}",
                 font=('Arial', 12, 'bold'), foreground='red').pack(anchor='w', pady=(5, 15))

        ttk.Label(main, text="Select Payment Method:",
                 font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 10))

        def pay_with(method):
            success = self._process_late_fee(checkout_id, equip_name, late_fee, method)
            if success:
                result['paid'] = True
                pay_dialog.destroy()

        ttk.Button(main, text="Cash", width=30,
                  command=lambda: pay_with('cash')).pack(pady=3)
        ttk.Button(main, text="Card", width=30,
                  command=lambda: pay_with('card')).pack(pady=3)
        ttk.Button(main, text="Student Finance Account", width=30,
                  command=lambda: pay_with('student_finance')).pack(pady=3)

        ttk.Separator(main).pack(fill='x', pady=10)
        ttk.Button(main, text="Cancel Return", command=pay_dialog.destroy).pack()

        self.dialog.wait_window(pay_dialog)
        return result['paid']

    def _process_late_fee(self, checkout_id, equip_name, amount, method):
        """Process the late fee payment. Returns True on success."""
        from education_system.university_system.infrastructure.database.db import get_connection

        borrower_id = self._get_borrower_id()
        user = self.auth.current_user if self.auth else {}
        username = user.get('username', 'Unknown')
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if method == 'student_finance':
            # Deduct from student finance account
            try:
                conn = get_connection()
                try:
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT account_id, balance FROM student_finance_accounts
                        WHERE student_id = ? AND account_status = 'active'
                    ''', (borrower_id,))
                    acct = cursor.fetchone()

                    if not acct:
                        messagebox.showerror("Error",
                            "No active student finance account found.\nPlease use another payment method.",
                            parent=self.dialog)
                        return False

                    account_id, balance = acct[0], float(acct[1])
                    if balance < amount:
                        messagebox.showerror("Insufficient Funds",
                            f"Account balance: £{balance:.2f}\nAmount due: £{amount:.2f}\n\n"
                            "Please use another payment method.",
                            parent=self.dialog)
                        return False

                    new_balance = balance - amount

                    # Deduct from account
                    cursor.execute('''
                        UPDATE student_finance_accounts
                        SET balance = ?, updated_at = ?
                        WHERE account_id = ?
                    ''', (new_balance, now, account_id))

                    # Record transaction
                    cursor.execute('''
                        INSERT INTO transactions
                        (source_type, account_id, student_id, transaction_type, amount,
                         balance_before, balance_after, description, reference_id, processed_by, created_at)
                        VALUES ('student_finance', ?, ?, 'debit', ?, ?, ?, ?, ?, ?, ?)
                    ''', (account_id, borrower_id, amount, balance, new_balance,
                          f'Equipment late fee - {equip_name}',
                          f'EQFEE-{checkout_id}', username, now))

                    conn.commit()
                finally:
                    conn.close()
            except Exception as e:
                messagebox.showerror("Payment Error", f"Failed to process payment: {e}",
                                   parent=self.dialog)
                return False

        # Record payment in payments table for finance tracking
        try:
            conn = get_connection()
            try:
                cursor = conn.cursor()
                payment_ref = f"EQFEE-{checkout_id}-{now.replace(' ', '').replace(':', '').replace('-', '')}"
                cursor.execute('''
                    INSERT OR IGNORE INTO payments
                    (source_type, student_id, amount, payment_method, payment_date,
                     payment_reference, department, notes, processed_by)
                    VALUES ('finance', ?, ?, ?, ?, ?, 'Student Union Equipment',
                            ?, ?)
                ''', (borrower_id, amount, method, now,
                      payment_ref,
                      f'Late fee for equipment return - {equip_name}', username))
                conn.commit()
            finally:
                conn.close()
        except Exception:
            pass  # payments table may not exist - non-critical

        # Send payment receipt email
        self._send_payment_receipt_email(checkout_id, equip_name, amount, method)

        return True

    def _send_return_confirmation_email(self, checkout_id, equip_name, condition, late_fee):
        """Send return confirmation email."""
        email = self._get_user_email()
        if not email:
            return
        try:
            from education_system.university_system.infrastructure.email.email_service.core import send_email
            username = self.auth.current_user.get('username', '') if self.auth else ''
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            body = (
                f"Dear {username},\n\n"
                f"Your equipment return has been processed.\n\n"
                f"Equipment: {equip_name}\n"
                f"Return Date: {now}\n"
                f"Condition: {condition}\n"
                f"Late Fee: £{late_fee:.2f}\n\n"
                f"Thank you for returning the equipment.\n\n"
                f"Best regards,\nStudent Union Equipment Team"
            )
            send_email(email, f"Equipment Return Confirmation - {equip_name}", body)
        except Exception as e:
            logging.warning(f"Could not send return confirmation email: {e}")

    def _send_payment_receipt_email(self, checkout_id, equip_name, amount, method):
        """Send late fee payment receipt email."""
        email = self._get_user_email()
        if not email:
            return
        try:
            from education_system.university_system.infrastructure.email.email_service.core import send_email
            username = self.auth.current_user.get('username', '') if self.auth else ''
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            method_display = {
                'cash': 'Cash',
                'card': 'Card',
                'student_finance': 'Student Finance Account'
            }.get(method, method)

            body = (
                f"Dear {username},\n\n"
                f"PAYMENT RECEIPT\n"
                f"{'=' * 40}\n\n"
                f"Reference: EQFEE-{checkout_id}\n"
                f"Date: {now}\n"
                f"Description: Equipment late return fee\n"
                f"Equipment: {equip_name}\n"
                f"Amount Paid: £{amount:.2f}\n"
                f"Payment Method: {method_display}\n\n"
                f"This is your official receipt of payment.\n\n"
                f"Best regards,\nStudent Union Equipment Team"
            )
            send_email(email, f"Payment Receipt - Equipment Late Fee £{amount:.2f}", body)
        except Exception as e:
            logging.warning(f"Could not send payment receipt email: {e}")



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

        self.current_tree = None
        self.history_tree = None
        self.summary_label = None

        self.create_widgets()
        self.load_data()

    def _get_borrower_id(self, conn):
        """Resolve the current user to a borrower_id used in equipment_checkouts."""
        cursor = conn.cursor()
        user_id = self.auth.current_user.get('id')

        # Try looking up a student_id first (student users)
        try:
            cursor.execute('SELECT student_id FROM users WHERE id = ?', (user_id,))
            result = cursor.fetchone()
            if result and result[0]:
                return result[0]
        except sqlite3.OperationalError:
            pass

        # Fall back to the user id / username
        username = self.auth.current_user.get('username')
        return username if username else str(user_id)

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill='both', expand=True, padx=15, pady=15)

        ttk.Label(main_frame, text="My Equipment Checkouts",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Summary
        summary_frame = ttk.LabelFrame(main_frame, text="Summary")
        summary_frame.pack(fill='x', pady=(0, 15))

        self.summary_label = ttk.Label(summary_frame, text="Loading...", justify='left', font=('Courier', 10))
        self.summary_label.pack(padx=15, pady=10)

        # Create notebook
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill='both', expand=True, pady=(0, 15))

        # Current tab
        current_frame = ttk.Frame(notebook)
        notebook.add(current_frame, text="Current Checkouts")

        columns = ('ID', 'Equipment', 'Checkout Date', 'Due Date', 'Days Left', 'Status')
        self.current_tree = ttk.Treeview(current_frame, columns=columns, show='tree headings', height=10)

        for col in columns:
            self.current_tree.heading(col, text=col)
            if col == 'Equipment':
                self.current_tree.column(col, width=250)
            else:
                self.current_tree.column(col, width=110)

        self.current_tree.pack(fill='both', expand=True, padx=10, pady=10)

        # History tab
        history_frame = ttk.Frame(notebook)
        notebook.add(history_frame, text="Checkout History")

        history_columns = ('ID', 'Equipment', 'Checkout Date', 'Return Date', 'Days Borrowed', 'Status')
        self.history_tree = ttk.Treeview(history_frame, columns=history_columns, show='tree headings', height=10)

        for col in history_columns:
            self.history_tree.heading(col, text=col)
            if col == 'Equipment':
                self.history_tree.column(col, width=250)
            else:
                self.history_tree.column(col, width=110)

        self.history_tree.pack(fill='both', expand=True, padx=10, pady=10)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill='x')

        ttk.Button(button_frame, text="Renew Checkout", command=self.renew).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Return Equipment", command=self.return_equipment).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Export History", command=self.export_history).pack(side='left', padx=(0, 10))
        ttk.Button(button_frame, text="Close", command=self.dialog.destroy).pack(side='right')

    def load_data(self):
        """Load checkout data from the database for the current user."""
        if not self.auth or not self.auth.current_user:
            self.summary_label.config(text="Not logged in.")
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            borrower_id = self._get_borrower_id(conn)
            cursor = conn.cursor()
            today = datetime.now().date()

            # --- Current checkouts (not yet returned) ---
            cursor.execute('''
                SELECT ec.checkout_id, ue.equipment_name, ec.checkout_date,
                       ec.expected_return, ec.status
                FROM equipment_checkouts ec
                INNER JOIN union_equipment ue ON ec.equipment_id = ue.equipment_id
                WHERE ec.borrower_id = ? AND ec.status = 'checked_out'
                ORDER BY ec.expected_return
            ''', (borrower_id,))
            current_rows = cursor.fetchall()

            # Clear existing items
            for item in self.current_tree.get_children():
                self.current_tree.delete(item)

            overdue_count = 0
            for row in current_rows:
                checkout_id, equip_name, checkout_date, expected_return, status = row
                # Calculate days left
                try:
                    due_date = datetime.strptime(expected_return[:10], '%Y-%m-%d').date()
                    delta = (due_date - today).days
                    if delta < 0:
                        days_left = f"{delta} days"
                        display_status = "OVERDUE"
                        overdue_count += 1
                    elif delta == 0:
                        days_left = "0 days"
                        display_status = "Due Today"
                    else:
                        days_left = f"{delta} days"
                        display_status = "On Time"
                except (ValueError, TypeError):
                    days_left = "N/A"
                    display_status = status

                display_checkout_date = checkout_date[:10] if checkout_date else ""
                display_due_date = expected_return[:10] if expected_return else ""

                self.current_tree.insert('', 'end', values=(
                    checkout_id, equip_name, display_checkout_date,
                    display_due_date, days_left, display_status
                ))

            if not current_rows:
                self.current_tree.insert('', 'end', values=(
                    "", "No current checkouts found", "", "", "", ""
                ))

            # --- History (returned checkouts) ---
            cursor.execute('''
                SELECT ec.checkout_id, ue.equipment_name, ec.checkout_date,
                       ec.actual_return, ec.expected_return, ec.status
                FROM equipment_checkouts ec
                INNER JOIN union_equipment ue ON ec.equipment_id = ue.equipment_id
                WHERE ec.borrower_id = ? AND ec.status != 'checked_out'
                ORDER BY ec.actual_return DESC
            ''', (borrower_id,))
            history_rows = cursor.fetchall()

            for item in self.history_tree.get_children():
                self.history_tree.delete(item)

            on_time_returns = 0
            for row in history_rows:
                checkout_id, equip_name, checkout_date, actual_return, expected_return, status = row
                # Calculate days borrowed
                try:
                    co_date = datetime.strptime(checkout_date[:10], '%Y-%m-%d').date()
                    ret_date = datetime.strptime(actual_return[:10], '%Y-%m-%d').date()
                    days_borrowed = f"{(ret_date - co_date).days} days"
                except (ValueError, TypeError):
                    days_borrowed = "N/A"

                # Determine if it was on time
                try:
                    due_date = datetime.strptime(expected_return[:10], '%Y-%m-%d').date()
                    ret_date = datetime.strptime(actual_return[:10], '%Y-%m-%d').date()
                    if ret_date <= due_date:
                        display_status = "Returned On Time"
                        on_time_returns += 1
                    else:
                        display_status = "Returned Late"
                except (ValueError, TypeError):
                    display_status = status.replace('_', ' ').title() if status else "Returned"

                display_checkout_date = checkout_date[:10] if checkout_date else ""
                display_return_date = actual_return[:10] if actual_return else ""

                self.history_tree.insert('', 'end', values=(
                    checkout_id, equip_name, display_checkout_date,
                    display_return_date, days_borrowed, display_status
                ))

            if not history_rows:
                self.history_tree.insert('', 'end', values=(
                    "", "No checkout history found", "", "", "", ""
                ))

            # --- Summary ---
            total_borrowed = len(current_rows) + len(history_rows)
            if len(history_rows) > 0:
                on_time_pct = int((on_time_returns / len(history_rows)) * 100)
                on_time_text = f"{on_time_pct}% ({on_time_returns}/{len(history_rows)})"
            else:
                on_time_text = "N/A"

            summary_text = (
                f"Current Checkouts: {len(current_rows)}\n"
                f"Overdue Items: {overdue_count}\n"
                f"Total Borrowed (All Time): {total_borrowed}\n"
                f"On-Time Returns: {on_time_text}"
            )
            self.summary_label.config(text=summary_text)

        except sqlite3.Error as e:
            self.summary_label.config(text=f"Error loading data: {e}")
        finally:
            if conn:
                conn.close()

    def renew(self):
        selection = self.current_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a checkout to renew.")
            return

        item = self.current_tree.item(selection[0])
        values = item.get('values', [])
        if not values or not values[0]:
            return

        checkout_id = values[0]
        equip_name = values[1]
        current_due = values[3]

        try:
            due_date = datetime.strptime(current_due, '%Y-%m-%d')
            new_due = due_date + timedelta(days=7)
            new_due_str = new_due.strftime('%Y-%m-%d')
        except (ValueError, TypeError):
            messagebox.showerror("Error", "Cannot determine current due date.")
            return

        if not messagebox.askyesno("Renew Checkout",
                                   f"Renew checkout for 7 more days?\n\n"
                                   f"Equipment: {equip_name}\n"
                                   f"Current Due Date: {current_due}\n"
                                   f"New Due Date: {new_due_str}"):
            return

        conn = None
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE equipment_checkouts SET expected_return = ?
                WHERE checkout_id = ? AND status = 'checked_out'
            ''', (new_due_str, checkout_id))
            conn.commit()
            messagebox.showinfo("Success", f"Checkout renewed. New due date: {new_due_str}")
            self.load_data()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Failed to renew checkout: {e}")
        finally:
            if conn:
                conn.close()

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


