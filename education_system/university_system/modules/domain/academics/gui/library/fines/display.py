"""
Library Fines Management - Fine lookup and display UI.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.university_system.modules.shared.utils.i18n import get_text as _

from .constants import (
    ORIGINAL_LIBRARY_AVAILABLE,
    FINANCE_ACCOUNT_AVAILABLE,
)

try:
    from education_system.university_system.modules.domain.academics.services.library.database import get_db_connection
except ImportError:
    pass

try:
    from education_system.university_system.modules.shared.utils.finance_integration import get_student_finance_account_balance
except ImportError:
    pass


def show_fine_management(self):
    """Show fine management interface (basic - kept for backward compatibility)"""
    if not self.check_permission('manage_loans'):
        return

    dialog = tk.Toplevel(self.master)
    dialog.title(_("library.dialogs.fine_management"))
    dialog.geometry("700x500")
    dialog.transient(self.master)
    dialog.grab_set()

    main_frame = ttk.Frame(dialog)
    main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    title_label = ttk.Label(main_frame, text="Fine Management System", style='Title.TLabel')
    title_label.pack(pady=(0, 10))

    # Search frame
    search_frame = ttk.LabelFrame(main_frame, text="Find User")
    search_frame.pack(fill=tk.X, pady=(0, 10))

    search_inner = ttk.Frame(search_frame)
    search_inner.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(search_inner, text="User ID:").pack(side=tk.LEFT)
    self.fine_user_var = tk.StringVar()
    ttk.Entry(search_inner, textvariable=self.fine_user_var, width=20).pack(side=tk.LEFT, padx=5)
    ttk.Button(search_inner, text=_("common.search"), command=self.load_user_fines).pack(side=tk.LEFT, padx=5)

    # User info frame
    info_frame = ttk.LabelFrame(main_frame, text=_("library.frames.user_information"))
    info_frame.pack(fill=tk.X, pady=(0, 10))

    self.user_info_text = tk.Text(info_frame, height=3, state=tk.DISABLED)
    self.user_info_text.pack(fill=tk.X, padx=5, pady=5)

    # Fines table
    fines_frame = ttk.LabelFrame(main_frame, text="Outstanding Fines")
    fines_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

    columns = ('Loan ID', 'Book ID', 'Title', 'Days Overdue', 'Fine Amount')
    self.fines_tree = ttk.Treeview(fines_frame, columns=columns, show='headings', height=8)

    for col in columns:
        self.fines_tree.heading(col, text=col)
        self.fines_tree.column(col, width=100)

    fines_scrollbar = ttk.Scrollbar(fines_frame, orient=tk.VERTICAL, command=self.fines_tree.yview)
    self.fines_tree.configure(yscrollcommand=fines_scrollbar.set)

    self.fines_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
    fines_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

    # Payment frame
    payment_frame = ttk.LabelFrame(main_frame, text="Process Payment")
    payment_frame.pack(fill=tk.X)

    payment_inner = ttk.Frame(payment_frame)
    payment_inner.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(payment_inner, text="Payment Amount: £").pack(side=tk.LEFT)
    self.payment_amount_var = tk.StringVar()
    ttk.Entry(payment_inner, textvariable=self.payment_amount_var, width=10).pack(side=tk.LEFT, padx=5)
    ttk.Button(payment_inner, text="Process Payment", command=self.process_fine_payment).pack(side=tk.LEFT, padx=5)
    if FINANCE_ACCOUNT_AVAILABLE:
        ttk.Button(payment_inner, text="\U0001f4b0 Pay from Finance Account", command=self.pay_fine_from_finance_account).pack(side=tk.LEFT, padx=5)
    ttk.Button(payment_inner, text="\U0001f4b3 Pay via Finance System", command=self.pay_fine_via_finance).pack(side=tk.LEFT, padx=5)
    ttk.Button(payment_inner, text="Waive All Fines", command=self.waive_all_fines).pack(side=tk.LEFT, padx=5)
    ttk.Button(payment_inner, text="\U0001f504 Refund Fine", command=self.refund_fine_dialog).pack(side=tk.LEFT, padx=5)

    ttk.Button(main_frame, text=_("common.close"), command=dialog.destroy).pack(pady=10)


def load_user_fines(self):
    """Load outstanding fines for a user"""
    user_id = self.fine_user_var.get().strip()

    if not user_id:
        messagebox.showwarning(_("common.warning"), "Please enter a User ID")
        return

    # Clear existing data
    for item in self.fines_tree.get_children():
        self.fines_tree.delete(item)

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()

                # Get user info
                student_columns = self._get_student_columns()
                grade_sql = ', grade_level' if 'grade_level' in student_columns else ''
                cursor.execute('SELECT first_name, last_name' + grade_sql + ' FROM students WHERE student_id = ?', (user_id,))
                user_info = cursor.fetchone()

                if user_info:
                    first_name, last_name = user_info[:2]
                    grade = user_info[2] if len(user_info) > 2 else 'N/A'
                    info_text = f"Name: {first_name} {last_name}\nGrade: {grade}\nUser ID: {user_id}"
                else:
                    info_text = f"User ID: {user_id}\nName: Not found in student records"

                # Add finance account balance info
                if FINANCE_ACCOUNT_AVAILABLE:
                    balance = get_student_finance_account_balance(user_id)
                    if balance is not None:
                        info_text += f"\n\n\U0001f4b0 Finance Account: \u00a3{balance:.2f}"
                    else:
                        info_text += f"\n\n\U0001f4b0 Finance Account: Not created"

                self.user_info_text.config(state=tk.NORMAL)
                self.user_info_text.delete("1.0", tk.END)
                self.user_info_text.insert("1.0", info_text)
                self.user_info_text.config(state=tk.DISABLED)

                # Get outstanding fines
                cursor.execute('''
                SELECT bl.loan_id, bl.book_id, b.title,
                       julianday('now') - julianday(bl.due_date) as days_overdue,
                       bl.fine_amount
                FROM book_loans bl
                JOIN books b ON bl.book_id = b.book_id
                WHERE bl.user_id = ? AND bl.fine_amount > 0 AND bl.status != 'returned'
                ORDER BY bl.due_date
                ''', (user_id,))

                fines = cursor.fetchall()

                total_fines = 0
                for fine in fines:
                    loan_id, book_id, title, days_overdue, fine_amount = fine
                    total_fines += fine_amount

                    self.fines_tree.insert('', 'end', values=(
                        loan_id, book_id, title[:20], int(days_overdue), f"${fine_amount:.2f}"
                    ))

                # Update user info with total
                updated_info = info_text + f"\nTotal Outstanding Fines: ${total_fines:.2f}"
                self.user_info_text.config(state=tk.NORMAL)
                self.user_info_text.delete("1.0", tk.END)
                self.user_info_text.insert("1.0", updated_info)
                self.user_info_text.config(state=tk.DISABLED)

                conn.close()
        else:
            # Demo mode
            info_text = f"User ID: {user_id}\nName: Demo User\nTotal Fines: $5.00"
            self.user_info_text.config(state=tk.NORMAL)
            self.user_info_text.delete("1.0", tk.END)
            self.user_info_text.insert("1.0", info_text)
            self.user_info_text.config(state=tk.DISABLED)

            # Demo fine data
            self.fines_tree.insert('', 'end', values=(1, "B10001", "Demo Book", 5, "$5.00"))

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Error loading fines: {str(e)}")
