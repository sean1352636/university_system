from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH  # injected
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, scrolledtext, filedialog
from education_system.university_system.infrastructure.database.db import sqlite3
import datetime
import json
import threading
import csv
from typing import Optional, List, Dict, Any
import sys
import os
from education_system.university_system.infrastructure.auth import UserAuth
from education_system.university_system.infrastructure.shared_context import get_auth

# Import i18n for language support
from education_system.university_system.core.i18n import (
    init_i18n,
    get_text as _t,
    get_current_language,
)
from education_system.university_system.modules.shared.utils.gui_language_selector import (
    show_gui_language_selector,
    create_language_menu_button,
)

# Import email service for sending actual emails
try:
    from education_system.university_system.infrastructure.email.email_service import send_email, send_email_as_user
    EMAIL_SERVICE_AVAILABLE = True
except ImportError:
    EMAIL_SERVICE_AVAILABLE = False
    print("Warning: Email service not available - emails will be stored locally only")

# Import the original parent portal functionality
try:
    from education_system.university_system.modules.domain.academics.services.parent_portal import ParentPortal
except ImportError:
    # If direct import fails, try to import from the document content
    print("Warning: Could not import parent_portal module directly. Using embedded functionality.")
    # We'll create a simplified version that maintains compatibility



from education_system.university_system.modules.domain.academics.gui.parent_portal.base import ParentPortalGUI

def check_meal_balance(self):
    """Check meal account balances with top-up functionality"""
    is_admin = self.is_admin()

    # For admin users, load all students from database
    if is_admin:
        students_list = self._load_all_students_from_db()
        if not students_list:
            messagebox.showinfo("No Students", "No students found in the system.")
            return
    else:
        # Non-admin users can only access their linked students
        if not self.children:
            messagebox.showinfo("No Students", "No students linked to your guardian account.")
            return
        students_list = self.children

    balance_window = tk.Toplevel(self.root)
    balance_window.title("Meal Account Management")
    balance_window.geometry("750x700")
    balance_window.minsize(700, 600)

    title = ttk.Label(balance_window, text="Meal Account Management", font=('Arial', 16, 'bold'))
    title.pack(pady=10)

    # Create scrollable canvas for main content
    canvas_container = ttk.Frame(balance_window)
    canvas_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    canvas = tk.Canvas(canvas_container)
    scrollbar = ttk.Scrollbar(canvas_container, orient="vertical", command=canvas.yview)
    main_frame = ttk.Frame(canvas)

    main_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=main_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    # Bind mousewheel
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    # Student selection
    selection_frame = ttk.LabelFrame(main_frame, text="Select Student", padding=10)
    selection_frame.pack(fill=tk.X, pady=5)

    student_var = tk.StringVar()
    student_combo = ttk.Combobox(selection_frame, textvariable=student_var, width=50, state="readonly")
    student_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in students_list]
    if students_list:
        student_combo.set(student_combo['values'][0])
    student_combo.pack(fill=tk.X, pady=5)

    # Balance display frame
    balance_frame = ttk.LabelFrame(main_frame, text="Account Balance", padding=10)
    balance_frame.pack(fill=tk.X, pady=5)

    balance_label = ttk.Label(balance_frame, text="Balance: Loading...", font=('Arial', 14))
    balance_label.pack(anchor='w')

    status_label = ttk.Label(balance_frame, text="Status: Loading...", font=('Arial', 12))
    status_label.pack(anchor='w')

    threshold_label = ttk.Label(balance_frame, text="Low Balance Threshold: Loading...", font=('Arial', 10))
    threshold_label.pack(anchor='w')

    # Cross-domain: show the campus restaurant POS balance derived
    # from the unified finance ledger via restaurant_bus. This must
    # match the local meal_accounts balance — if they diverge, a
    # top-up was recorded somewhere that didn't mirror to the bus.
    pos_balance_label = ttk.Label(
        balance_frame,
        text="Campus restaurant balance: Loading...",
        font=('Arial', 10), foreground='#06c',
    )
    threshold_label.pack(anchor='w')

    # Transaction history frame
    history_frame = ttk.LabelFrame(main_frame, text="Recent Transactions", padding=10)
    history_frame.pack(fill=tk.BOTH, expand=True, pady=5)

    trans_tree = ttk.Treeview(history_frame, columns=("Date", "Type", "Amount", "Description", "Balance After"), show='headings', height=8)
    trans_tree.heading("Date", text="Date")
    trans_tree.heading("Type", text="Type")
    trans_tree.heading("Amount", text="Amount")
    trans_tree.heading("Description", text="Description")
    trans_tree.heading("Balance After", text="Balance After")

    trans_tree.column("Date", width=100)
    trans_tree.column("Type", width=60)
    trans_tree.column("Amount", width=70)
    trans_tree.column("Description", width=150)
    trans_tree.column("Balance After", width=80)

    trans_scroll = ttk.Scrollbar(history_frame, orient="vertical", command=trans_tree.yview)
    trans_tree.configure(yscrollcommand=trans_scroll.set)
    trans_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    trans_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # Top-up frame
    topup_frame = ttk.LabelFrame(main_frame, text="Add Funds", padding=10)
    topup_frame.pack(fill=tk.X, pady=5)

    topup_row = ttk.Frame(topup_frame)
    topup_row.pack(fill=tk.X)

    ttk.Label(topup_row, text="Amount (£):").pack(side=tk.LEFT, padx=5)
    amount_var = tk.StringVar(value="20.00")
    amount_entry = ttk.Entry(topup_row, textvariable=amount_var, width=15)
    amount_entry.pack(side=tk.LEFT, padx=5)

    # Preset amounts
    preset_frame = ttk.Frame(topup_frame)
    preset_frame.pack(fill=tk.X, pady=5)

    ttk.Label(preset_frame, text="Quick amounts:").pack(side=tk.LEFT, padx=5)
    for amount in ["10.00", "20.00", "50.00", "100.00"]:
        ttk.Button(preset_frame, text=f"£{amount}", width=8,
                  command=lambda a=amount: amount_var.set(a)).pack(side=tk.LEFT, padx=2)

    def get_student_id():
        selected = student_var.get()
        if selected:
            try:
                return selected.split("ID: ")[1].rstrip(")")
            except (IndexError, AttributeError):
                return None
        return None

    def load_balance():
        student_id = get_student_id()
        if not student_id:
            return

        # Clear transaction tree
        for item in trans_tree.get_children():
            trans_tree.delete(item)

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            cursor = conn.cursor()

            # Get meal account balance
            cursor.execute('''
                SELECT balance, low_balance_threshold, auto_topup_enabled, auto_topup_amount
                FROM meal_accounts
                WHERE student_id = ?
            ''', (student_id,))

            account = cursor.fetchone()

            if account:
                balance, threshold, auto_topup, auto_amount = account
                balance = float(balance) if balance else 0.0
                threshold = float(threshold) if threshold else 10.0

                balance_label.config(text=f"Balance: £{balance:.2f}")

                if balance < threshold:
                    status_label.config(text="Status: LOW BALANCE", foreground="red")
                else:
                    status_label.config(text="Status: OK", foreground="green")

                threshold_label.config(text=f"Low Balance Threshold: £{threshold:.2f}")
            else:
                balance_label.config(text="Balance: £0.00")
                status_label.config(text="Status: No Account", foreground="orange")
                threshold_label.config(text="Low Balance Threshold: £10.00 (default)")

            # Cross-domain: pull the campus restaurant POS balance
            # from restaurant_bus so the parent can confirm the
            # campus POS sees the top-up too.
            try:
                from education_system.university_system.modules.services import (
                    restaurant_bus,
                )
                pos_balance = restaurant_bus.meal_plan_balance(student_id)
                pos_balance_label.config(
                    text=f"Campus restaurant balance: £{pos_balance:.2f}"
                )
            except Exception:
                pos_balance_label.config(
                    text="Campus restaurant balance: (unavailable)"
                )

            # Get recent transactions
            cursor.execute('''
                SELECT created_at, transaction_type, amount, description, balance_after
                FROM transactions
                WHERE source_type = 'meal' AND student_id = ?
                ORDER BY created_at DESC
                LIMIT 20
            ''', (student_id,))

            transactions = cursor.fetchall()
            for trans in transactions:
                trans_date, trans_type, amount, desc, balance_after = trans
                date_str = trans_date[:10] if trans_date else "Unknown"
                amount_str = f"£{float(amount):.2f}" if amount else "£0.00"
                balance_after_str = f"£{float(balance_after):.2f}" if balance_after else "-"
                trans_tree.insert("", tk.END, values=(
                    date_str, trans_type or "Unknown", amount_str,
                    desc or "", balance_after_str
                ))

            conn.close()

        except Exception as e:
            balance_label.config(text=f"Error: {e}")

    def add_funds():
        student_id = get_student_id()
        if not student_id:
            messagebox.showwarning("Error", "Please select a student.")
            return

        try:
            amount = float(amount_var.get())
            if amount <= 0:
                messagebox.showwarning("Invalid Amount", "Please enter a positive amount.")
                return
            if amount > 500:
                messagebox.showwarning("Amount Too High", "Maximum top-up is £500.")
                return
        except ValueError:
            messagebox.showwarning("Invalid Amount", "Please enter a valid number.")
            return

        # Confirm top-up
        selected_name = student_var.get().split(" (ID:")[0]
        if not messagebox.askyesno("Confirm Top-Up",
            f"Add £{amount:.2f} to {selected_name}'s meal account?"):
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
            cursor = conn.cursor()

            # Check if account exists
            cursor.execute("SELECT balance FROM meal_accounts WHERE student_id = ?", (student_id,))
            existing = cursor.fetchone()

            current_balance = float(existing[0]) if existing else 0.0
            new_balance = current_balance + amount
            now = datetime.datetime.now().isoformat()

            if existing:
                # Update balance
                cursor.execute('''
                    UPDATE meal_accounts
                    SET balance = ?, last_updated = ?
                    WHERE student_id = ?
                ''', (new_balance, now, student_id))
            else:
                # Create account
                cursor.execute('''
                    INSERT INTO meal_accounts (student_id, balance, last_updated)
                    VALUES (?, ?, ?)
                ''', (student_id, new_balance, now))

            # Record transaction
            cursor.execute('''
                INSERT INTO transactions
                (source_type, student_id, transaction_type, amount, description, created_at, balance_after)
                VALUES ('meal', ?, 'credit', ?, 'Parent/Guardian top-up', ?, ?)
            ''', (student_id, amount, now, new_balance))

            conn.commit()

            # Cross-domain: also route through restaurant_bus so the
            # restaurant POS, finance ledger, and unified student
            # account view see the same top-up. The bus writes a
            # negative-amount row to student_finance_transactions
            # which restaurant_bus.meal_plan_balance derives from —
            # without this, parents and the campus restaurant would
            # see different balances.
            try:
                from education_system.university_system.modules.services import (
                    restaurant_bus,
                )
                actor = "parent_portal"
                if getattr(self, 'auth', None) and self.auth.current_user:
                    actor = self.auth.current_user.get('username') or actor
                restaurant_bus.top_up_meal_plan(
                    student_id, amount, processed_by=actor,
                )
            except Exception as bus_err:
                print(f"restaurant_bus top-up mirror failed: {bus_err}")

            # Get student email for notification
            cursor.execute("SELECT email_address, first_name FROM students WHERE student_id = ?", (student_id,))
            student_info = cursor.fetchone()

            conn.close()

            # Send email notification to student
            if student_info and student_info[0]:
                student_email = student_info[0]
                student_name = student_info[1] or "Student"

                try:
                    # Render email from template
                    from education_system.university_system.infrastructure.email.template_utils import render_template

                    email_subject, email_body = render_template('parent_portal/meal_account_topup', {
                        'student_name': student_name,
                        'amount': f"{amount:.2f}",
                        'new_balance': f"{new_balance:.2f}",
                        'topup_datetime': datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
                    })

                    # Fallback if template not found
                    if not email_subject or not email_body:
                        email_subject = "Meal Account Top-Up Notification"
                        email_body = f"Dear {student_name},\n\nYour meal account has been topped up!\n\nAmount Added: £{amount:.2f}\nNew Balance: £{new_balance:.2f}\nDate: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\nThis top-up was made by your parent/guardian through the Family Portal.\n\nBest regards,\nUniversity Management System"

                    email_conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30)
                    try:
                        email_cursor = email_conn.cursor()

                        email_cursor.execute('''
                            INSERT INTO email_log
                            (recipient, subject, message, sent_date, status, related_to, student_id)
                            VALUES (?, ?, ?, ?, 'sent', 'meal_topup', ?)
                        ''', (student_email, email_subject, email_body, now, student_id))

                        email_conn.commit()
                    finally:
                        email_conn.close()

                except Exception as email_error:
                    print(f"Email notification error: {email_error}")

            messagebox.showinfo("Success",
                f"Successfully added £{amount:.2f} to meal account.\n\nNew Balance: £{new_balance:.2f}\n\nNotification sent to student.")

            load_balance()  # Refresh display

        except Exception as e:
            messagebox.showerror("Error", f"Error adding funds: {e}")

    # Top-up button
    ttk.Button(topup_frame, text="Add Funds", command=add_funds).pack(pady=10)

    # Bind student selection change
    student_combo.bind("<<ComboboxSelected>>", lambda e: load_balance())

    # Button frame
    btn_frame = ttk.Frame(balance_window)
    btn_frame.pack(pady=10)

    ttk.Button(btn_frame, text="Refresh", command=load_balance).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text="Close", command=balance_window.destroy).pack(side=tk.LEFT, padx=5)

    # Load initial balance
    load_balance()
ParentPortalGUI.check_meal_balance = check_meal_balance

def view_all_meal_transactions(self, child):
    """View all meal account transactions for a child"""
    self.clear_content()
    self.update_status(f"All Meal Transactions - {child[1]} {child[3]}")

    title = ttk.Label(self.content_frame, text=f"All Meal Transactions - {child[1]} {child[3]}",
                     style='Title.TLabel', font=('Arial', 18, 'bold'))
    title.pack(pady=20)

    # Transactions table
    trans_frame = ttk.Frame(self.content_frame)
    trans_frame.pack(fill=tk.BOTH, expand=True, padx=20)

    columns = ('Date', 'Type', 'Amount', 'Description', 'Balance After')
    tree = ttk.Treeview(trans_frame, columns=columns, show='headings', height=15)

    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120)

    # Sample transaction data
    transactions = [
        ('2024-01-20', 'Credit', '£20.00', 'Parent top-up', '£25.50'),
        ('2024-01-19', 'Debit', '£3.50', 'Lunch purchase', '£5.50'),
        ('2024-01-18', 'Debit', '£2.75', 'Snack purchase', '£9.00'),
    ]

    for transaction in transactions:
        tree.insert('', tk.END, values=transaction)

    scrollbar = ttk.Scrollbar(trans_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
ParentPortalGUI.view_all_meal_transactions = view_all_meal_transactions

def show_meal_interface(self):
    """Show meal accounts interface"""
    self.clear_content()
    self.update_status("Meal Accounts")

    title = ttk.Label(self.content_frame, text="Meal Accounts", style='Title.TLabel', font=('Arial', 20, 'bold'))
    title.pack(pady=20)

    if not self.children:
        ttk.Label(self.content_frame, text="No students linked to your guardian account.").pack(pady=50)
        return

    # Child selection
    child_frame = ttk.Frame(self.content_frame)
    child_frame.pack(fill=tk.X, padx=20, pady=10)

    ttk.Label(child_frame, text="Select Student:").pack(side=tk.LEFT, padx=5)
    child_var = tk.StringVar()
    child_combo = ttk.Combobox(child_frame, textvariable=child_var, width=40, state="readonly")
    child_combo['values'] = [f"{child[1]} {child[3]} (ID: {child[0]})" for child in self.children]
    if child_combo['values']:
        child_combo.set(child_combo['values'][0])
    child_combo.pack(side=tk.LEFT, padx=5)

    # Meal account display frame
    meal_frame = ttk.LabelFrame(self.content_frame, text="Meal Account Information", padding=15)
    meal_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def load_meal_info():
        for widget in meal_frame.winfo_children():
            widget.destroy()

        selected_child = child_var.get()
        if not selected_child:
            ttk.Label(meal_frame, text="Please select a child").pack(pady=20)
            return

        student_id = selected_child.split("ID: ")[1].rstrip(")")

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='meal_accounts'
            """)

            if cursor.fetchone():
                cursor.execute("""
                SELECT balance, low_balance_threshold, auto_topup_enabled, auto_topup_amount, last_updated
                FROM meal_accounts
                WHERE student_id = ?
                """, (student_id,))

                meal_data = cursor.fetchone()

                if meal_data:
                    # Balance information
                    balance_frame = ttk.LabelFrame(meal_frame, text="Account Balance", padding=10)
                    balance_frame.pack(fill=tk.X, pady=(0, 10))

                    balance_val = float(meal_data[0]) if meal_data[0] else 0.0
                    balance_color = 'green' if balance_val > 0 else 'red'
                    ttk.Label(balance_frame, text=f"Current Balance: £{balance_val:.2f}",
                             font=('Arial', 14, 'bold'), foreground=balance_color).pack(anchor='w', pady=5)
                    ttk.Label(balance_frame, text=f"Low Balance Alert: £{float(meal_data[1] or 10.0):.2f}",
                             font=('Arial', 10)).pack(anchor='w', pady=3)
                    ttk.Label(balance_frame, text=f"Last Updated: {meal_data[4] or 'N/A'}",
                             font=('Arial', 10)).pack(anchor='w', pady=3)

                    # Auto top-up information
                    if meal_data[2]:  # auto_topup_enabled
                        topup_frame = ttk.LabelFrame(meal_frame, text="Auto Top-Up Settings", padding=10)
                        topup_frame.pack(fill=tk.X, pady=(0, 10))

                        ttk.Label(topup_frame, text="Auto Top-Up: Enabled",
                                 font=('Arial', 10), foreground='green').pack(anchor='w', pady=3)
                        ttk.Label(topup_frame, text=f"Top-Up Amount: £{float(meal_data[3] or 20.0):.2f}",
                                 font=('Arial', 10)).pack(anchor='w', pady=3)

                    # Recent transactions
                    cursor.execute("""
                    SELECT created_at, transaction_type, amount, description
                    FROM transactions
                    WHERE source_type = 'meal' AND student_id = ?
                    ORDER BY created_at DESC
                    LIMIT 15
                    """, (student_id,))

                    transactions = cursor.fetchall()

                    if transactions:
                        trans_frame = ttk.LabelFrame(meal_frame, text="Recent Transactions", padding=10)
                        trans_frame.pack(fill=tk.BOTH, expand=True)

                        columns = ("Date", "Type", "Amount", "Description")
                        tree = ttk.Treeview(trans_frame, columns=columns, show="headings", height=8)

                        for col in columns:
                            tree.heading(col, text=col)
                            tree.column(col, width=120)

                        for trans in transactions:
                            tree.insert('', tk.END, values=trans)

                        scrollbar = ttk.Scrollbar(trans_frame, orient=tk.VERTICAL, command=tree.yview)
                        tree.configure(yscrollcommand=scrollbar.set)

                        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                    # Action buttons
                    btn_frame = ttk.Frame(meal_frame)
                    btn_frame.pack(pady=10)
                    ttk.Button(btn_frame, text="Add Funds",
                              command=lambda: self.add_meal_funds(student_id)).pack(side=tk.LEFT, padx=5)
                    ttk.Button(btn_frame, text="Update Meal Plan",
                              command=lambda: self.update_meal_plan(student_id)).pack(side=tk.LEFT, padx=5)
                else:
                    ttk.Label(meal_frame, text="No meal account found",
                             font=('Arial', 11)).pack(pady=50)
            else:
                ttk.Label(meal_frame, text="Meal account system not configured",
                         font=('Arial', 11)).pack(pady=20)

            conn.close()

        except Exception as e:
            ttk.Label(meal_frame, text=f"Error loading meal account: {str(e)}",
                     font=('Arial', 10)).pack(pady=20)

    ttk.Button(child_frame, text="Load Meal Info", command=load_meal_info).pack(side=tk.LEFT, padx=5)
    load_meal_info()
ParentPortalGUI.show_meal_interface = show_meal_interface

def add_meal_funds(self, student_id):
    """Add funds to meal account"""
    # Ask for amount
    amount = simpledialog.askfloat("Add Funds", "Enter amount to add to meal account:", minvalue=0.01)

    if not amount:
        return

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        # Ensure tables exist
        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='meal_accounts'
        """)

        if not cursor.fetchone():
            messagebox.showwarning("Not Available", "Meal account system not configured.")
            conn.close()
            return

        # NOTE: meal transactions now use the unified 'transactions' table
        # with source_type = 'meal'

        # Update balance
        cursor.execute("""
        UPDATE meal_accounts
        SET balance = balance + ?,
            last_transaction_date = CURRENT_TIMESTAMP
        WHERE student_id = ?
        """, (amount, student_id))

        # Record transaction
        cursor.execute("""
        INSERT INTO transactions (source_type, student_id, amount, description, transaction_type)
        VALUES ('meal', ?, ?, ?, ?)
        """, (student_id, amount, f"Funds added: £{amount:.2f}", "Credit"))

        conn.commit()
        conn.close()

        messagebox.showinfo("Success", f"£{amount:.2f} has been added to the meal account!")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to add funds: {str(e)}")
ParentPortalGUI.add_meal_funds = add_meal_funds

def update_meal_plan(self, student_id):
    """Update meal plan"""
    # Create dialog window
    dialog = tk.Toplevel(self.root)
    dialog.title("Update Meal Plan")
    dialog.geometry("500x400")
    dialog.transient(self.root)
    dialog.grab_set()

    # Main frame with padding
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Update Meal Plan",
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Get current meal plan
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='meal_accounts'
        """)

        if not cursor.fetchone():
            messagebox.showwarning("Not Available", "Meal account system not configured.")
            conn.close()
            dialog.destroy()
            return

        cursor.execute("""
        SELECT meal_plan FROM meal_accounts WHERE student_id = ?
        """, (student_id,))

        current_plan = cursor.fetchone()
        conn.close()

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load meal plan: {str(e)}")
        dialog.destroy()
        return

    # Meal plan options
    ttk.Label(main_frame, text="Select Meal Plan:").pack(anchor='w', pady=(5, 0))

    meal_plans = [
        ('Standard', 'Standard meal plan - All meals included'),
        ('Breakfast Only', 'Breakfast only meal plan'),
        ('Lunch Only', 'Lunch only meal plan'),
        ('Breakfast & Lunch', 'Breakfast and lunch meal plan'),
        ('No Plan', 'No meal plan - Pay as you go')
    ]

    plan_var = tk.StringVar()
    if current_plan and current_plan[0]:
        plan_var.set(current_plan[0])

    for plan_name, plan_desc in meal_plans:
        frame = ttk.Frame(main_frame)
        frame.pack(fill=tk.X, pady=5)

        rb = ttk.Radiobutton(frame, text=plan_name, variable=plan_var, value=plan_name)
        rb.pack(anchor='w')

        ttk.Label(frame, text=plan_desc, font=('Arial', 9, 'italic')).pack(anchor='w', padx=20)

    def save_plan():
        if not plan_var.get():
            messagebox.showwarning("Validation Error", "Please select a meal plan.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Update meal plan
            cursor.execute("""
            UPDATE meal_accounts
            SET meal_plan = ?
            WHERE student_id = ?
            """, (plan_var.get(), student_id))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success", f"Meal plan updated to: {plan_var.get()}")
            dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to update meal plan: {str(e)}")

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    ttk.Button(button_frame, text="Save", command=save_plan).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.update_meal_plan = update_meal_plan
