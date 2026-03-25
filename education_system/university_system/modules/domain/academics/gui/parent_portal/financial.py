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
from education_system.university_system.modules.shared.utils.i18n import (
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

def show_fees_interface(self):
    """Show fees and payments interface"""
    self.clear_content()
    self.update_status("Fees & Payments")

    title = ttk.Label(self.content_frame, text="Fees & Payments", style='Title.TLabel', font=('Arial', 20, 'bold'))
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

    # Fees display frame
    fees_frame = ttk.LabelFrame(self.content_frame, text="Fee Information", padding=15)
    fees_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

    def load_fees():
        for widget in fees_frame.winfo_children():
            widget.destroy()

        selected_child = child_var.get()
        if not selected_child:
            ttk.Label(fees_frame, text="Please select a child").pack(pady=20)
            return

        student_id = selected_child.split("ID: ")[1].rstrip(")")

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='student_fees'
            """)

            if cursor.fetchone():
                # Get fee information from student_fees and fee_types tables
                cursor.execute("""
                SELECT ft.fee_name, sf.amount, sf.currency, sf.due_date, sf.status,
                       COALESCE(ft.description, '')
                FROM student_fees sf
                LEFT JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                WHERE sf.student_id = ?
                ORDER BY sf.due_date
                """, (student_id,))

                fees = cursor.fetchall()

                # Also get account balance
                cursor.execute("""
                SELECT balance, currency FROM student_finance_accounts
                WHERE student_id = ?
                """, (student_id,))
                account = cursor.fetchone()

                if fees or account:
                    # Account balance summary
                    summary_frame = ttk.LabelFrame(fees_frame, text="Account Summary", padding=10)
                    summary_frame.pack(fill=tk.X, pady=(0, 10))

                    if account:
                        balance_color = 'green' if float(account[0]) >= 0 else 'red'
                        ttk.Label(summary_frame, text=f"Account Balance: {account[1]} {float(account[0]):.2f}",
                                 font=('Arial', 12, 'bold'), foreground=balance_color).pack(anchor='w')

                    # Total fees due
                    total_due = sum(float(fee[1]) for fee in fees if fee[4].lower() == 'unpaid')
                    if total_due > 0:
                        ttk.Label(summary_frame, text=f"Total Fees Due: {fees[0][2] if fees else 'GBP'} {total_due:.2f}",
                                 font=('Arial', 11), foreground='red').pack(anchor='w')
                    else:
                        ttk.Label(summary_frame, text="No outstanding fees",
                                 font=('Arial', 11), foreground='green').pack(anchor='w')

                    if fees:
                        # Fees list
                        columns = ("Fee Type", "Amount", "Currency", "Due Date", "Status", "Description")
                        tree = ttk.Treeview(fees_frame, columns=columns, show="headings", height=10)

                        tree.heading("Fee Type", text="Fee Type")
                        tree.heading("Amount", text="Amount")
                        tree.heading("Currency", text="Currency")
                        tree.heading("Due Date", text="Due Date")
                        tree.heading("Status", text="Status")
                        tree.heading("Description", text="Description")

                        tree.column("Fee Type", width=150)
                        tree.column("Amount", width=80)
                        tree.column("Currency", width=60)
                        tree.column("Due Date", width=100)
                        tree.column("Status", width=80)
                        tree.column("Description", width=150)

                        for fee in fees:
                            status = fee[4].capitalize() if fee[4] else 'Unknown'
                            tree.insert('', tk.END, values=fee, tags=(status,))

                        tree.tag_configure('Paid', foreground='green')
                        tree.tag_configure('Unpaid', foreground='red')
                        tree.tag_configure('Pending', foreground='orange')

                        scrollbar = ttk.Scrollbar(fees_frame, orient=tk.VERTICAL, command=tree.yview)
                        tree.configure(yscrollcommand=scrollbar.set)

                        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                    # Payment button
                    btn_frame = ttk.Frame(fees_frame)
                    btn_frame.pack(pady=10)
                    ttk.Button(btn_frame, text="Make Payment",
                              command=lambda: self.make_payment(student_id)).pack(side=tk.LEFT, padx=5)
                    ttk.Button(btn_frame, text="Payment History",
                              command=lambda: self.view_payment_history(student_id)).pack(side=tk.LEFT, padx=5)
                else:
                    ttk.Label(fees_frame, text="No fees or account found for this student", font=('Arial', 11)).pack(pady=50)
            else:
                ttk.Label(fees_frame, text="Fees system not configured",
                         font=('Arial', 11)).pack(pady=20)

            conn.close()

        except Exception as e:
            ttk.Label(fees_frame, text=f"Error loading fees: {str(e)}",
                     font=('Arial', 10)).pack(pady=20)

    ttk.Button(child_frame, text="Load Fees", command=load_fees).pack(side=tk.LEFT, padx=5)
    load_fees()
ParentPortalGUI.show_fees_interface = show_fees_interface

def make_payment(self, student_id):
    """Make a payment"""
    # Get fee information first
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='student_fees'
        """)

        if not cursor.fetchone():
            messagebox.showwarning("Not Available", "Fee system not configured.")
            conn.close()
            return

        cursor.execute("""
        SELECT ft.fee_name, sf.amount, sf.status, sf.student_fee_id, sf.currency
        FROM student_fees sf
        LEFT JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
        WHERE sf.student_id = ? AND LOWER(sf.status) = 'unpaid'
        """, (student_id,))

        unpaid_fees = cursor.fetchall()
        conn.close()

        if not unpaid_fees:
            messagebox.showinfo("No Fees Due", "There are no outstanding fees for this student.")
            return

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load fee information: {str(e)}")
        return

    # Create dialog window
    dialog = tk.Toplevel(self.root)
    dialog.title("Make Payment")
    dialog.geometry("600x550")
    dialog.transient(self.root)
    dialog.grab_set()

    # Main frame with padding
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Make Payment",
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    # Ensure payments table exists
    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='payments'
        """)

        if not cursor.fetchone():
            cursor.execute("""
            CREATE TABLE payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                fee_type TEXT,
                amount REAL,
                payment_method TEXT,
                payment_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                confirmation_number TEXT
            )
            """)
            conn.commit()

        conn.close()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to initialize database: {str(e)}")
        dialog.destroy()
        return

    # Display unpaid fees
    fees_frame = ttk.LabelFrame(main_frame, text="Outstanding Fees", padding=10)
    fees_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    columns = ("Fee Type", "Amount", "Currency", "Status")
    tree = ttk.Treeview(fees_frame, columns=columns, show="headings", height=6)

    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=120)

    total_amount = 0
    currency = 'GBP'
    for fee in unpaid_fees:
        # fee: (fee_name, amount, status, student_fee_id, currency)
        display_values = (fee[0] or 'Unknown Fee', fee[1], fee[4] or 'GBP', fee[2])
        tree.insert('', tk.END, values=display_values)
        total_amount += float(fee[1])
        currency = fee[4] or 'GBP'

    tree.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text=f"Total Amount Due: {currency} {total_amount:.2f}",
             font=('Arial', 12, 'bold')).pack(pady=10)

    # Payment method selection
    ttk.Label(main_frame, text="Payment Method:").pack(anchor='w', pady=(10, 0))
    payment_method = ttk.Combobox(main_frame, width=50, state="readonly")
    payment_method['values'] = ['Credit Card', 'Debit Card', 'Check', 'Cash', 'Bank Transfer']
    payment_method.pack(fill=tk.X, pady=(0, 10))

    def process_payment():
        if not payment_method.get():
            messagebox.showwarning("Validation Error", "Please select a payment method.")
            return

        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Generate confirmation number
            import random
            confirmation = f"PAY{random.randint(100000, 999999)}"

            # Record payment for each fee
            # fee tuple: (fee_name, amount, status, student_fee_id, currency)
            for fee in unpaid_fees:
                fee_name = fee[0] or 'Unknown Fee'
                fee_amount = fee[1]
                student_fee_id = fee[3]
                fee_currency = fee[4] or 'GBP'

                cursor.execute("""
                INSERT INTO payments (student_id, amount, currency, payment_method,
                                     transaction_id, payment_date, status, notes)
                VALUES (?, ?, ?, ?, ?, datetime('now'), 'completed', ?)
                """, (student_id, fee_amount, fee_currency, payment_method.get(),
                      confirmation, f"Payment for: {fee_name}"))

                # Update fee status to paid using the specific student_fee_id
                cursor.execute("""
                UPDATE student_fees
                SET status = 'paid', updated_at = datetime('now')
                WHERE student_fee_id = ?
                """, (student_fee_id,))

            conn.commit()
            conn.close()

            messagebox.showinfo("Success",
                               f"Payment of {currency} {total_amount:.2f} processed successfully!\n\n"
                               f"Confirmation Number: {confirmation}\n\n"
                               "Thank you for your payment.")
            dialog.destroy()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to process payment: {str(e)}")

    # Buttons
    button_frame = ttk.Frame(main_frame)
    button_frame.pack(pady=20)

    ttk.Button(button_frame, text="Process Payment", command=process_payment).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)
ParentPortalGUI.make_payment = make_payment

def view_payment_history(self, student_id):
    """View payment history"""
    # Create dialog window
    dialog = tk.Toplevel(self.root)
    dialog.title("Payment History")
    dialog.geometry("800x600")
    dialog.transient(self.root)
    dialog.grab_set()

    # Main frame with padding
    main_frame = ttk.Frame(dialog, padding=20)
    main_frame.pack(fill=tk.BOTH, expand=True)

    ttk.Label(main_frame, text="Payment History",
             font=('Arial', 14, 'bold')).pack(pady=(0, 20))

    try:
        conn = sqlite3.connect(str(DEFAULT_DB_PATH))
        cursor = conn.cursor()

        cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='payments'
        """)

        if not cursor.fetchone():
            ttk.Label(main_frame, text="No payment history available.",
                     font=('Arial', 11)).pack(pady=50)
            ttk.Button(main_frame, text="Close", command=dialog.destroy).pack()
            conn.close()
            return

        cursor.execute("""
        SELECT COALESCE(notes, 'Payment'), amount, currency, payment_method,
               payment_date, COALESCE(transaction_id, payment_id), status
        FROM payments
        WHERE student_id = ?
        ORDER BY payment_date DESC
        """, (student_id,))

        payments = cursor.fetchall()
        conn.close()

        if not payments:
            ttk.Label(main_frame, text="No payments found for this student.",
                     font=('Arial', 11)).pack(pady=50)
            ttk.Button(main_frame, text="Close", command=dialog.destroy).pack()
            return

        # Display payment history
        columns = ("Description", "Amount", "Currency", "Method", "Date", "Reference", "Status")
        tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=15)

        tree.heading("Description", text="Description")
        tree.heading("Amount", text="Amount")
        tree.heading("Currency", text="Currency")
        tree.heading("Method", text="Method")
        tree.heading("Date", text="Date")
        tree.heading("Reference", text="Reference")
        tree.heading("Status", text="Status")

        tree.column("Description", width=150)
        tree.column("Amount", width=80)
        tree.column("Currency", width=60)
        tree.column("Method", width=100)
        tree.column("Date", width=120)
        tree.column("Reference", width=100)
        tree.column("Status", width=80)

        total_paid = 0
        currency = 'GBP'
        for payment in payments:
            tree.insert('', tk.END, values=payment, tags=(payment[6],))
            if payment[6] == 'completed':
                total_paid += float(payment[1])
            currency = payment[2] or 'GBP'

        tree.tag_configure('completed', foreground='green')
        tree.tag_configure('pending', foreground='orange')
        tree.tag_configure('failed', foreground='red')

        scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Summary
        summary_frame = ttk.Frame(dialog, padding=20)
        summary_frame.pack(fill=tk.X)

        ttk.Label(summary_frame, text=f"Total Paid: {currency} {total_paid:.2f}",
                 font=('Arial', 12, 'bold')).pack(side=tk.LEFT)

        ttk.Button(summary_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load payment history: {str(e)}")
        dialog.destroy()
ParentPortalGUI.view_payment_history = view_payment_history
