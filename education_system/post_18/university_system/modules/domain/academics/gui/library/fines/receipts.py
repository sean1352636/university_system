"""
Library Fines Management - Receipt generation and display.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from datetime import datetime
from education_system.post_18.university_system.core.i18n import get_text as _

try:
    from education_system.post_18.university_system.modules.domain.academics.services.library.database import get_db_connection
except ImportError:
    pass


def generate_fine_receipt_gui(self, loan_id, amount, payment_method, payment_date):
    """Generate and display fine receipt"""
    receipt_window = tk.Toplevel(self.master)
    receipt_window.title("Fine Payment Receipt")
    receipt_window.geometry("500x600")

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Get loan details
        cursor.execute('''
        SELECT b.title, b.author, l.user_id, l.checkout_date, l.due_date
        FROM book_loans l
        JOIN books b ON l.book_id = b.book_id
        WHERE l.loan_id = ?
        ''', (loan_id,))

        loan_details = cursor.fetchone()
        conn.close()

        if loan_details:
            title, author, user_id, checkout, due = loan_details

            receipt_text = f"""
\u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557
\u2551                  FINE PAYMENT RECEIPT                        \u2551
\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d

Receipt Date: {payment_date}
Receipt ID: FP-{loan_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}

PAYMENT DETAILS:
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
Loan ID:         {loan_id}
User ID:         {user_id}

Book:            {title}
Author:          {author}

Checkout Date:   {checkout[:10]}
Due Date:        {due[:10]}

PAYMENT INFORMATION:
\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501
Fine Amount:     £{amount:.2f}
Payment Method:  {payment_method.upper()}
Status:          PAID IN FULL

Thank you for your payment!

For questions, please contact the library front desk.
"""

            text_widget = ScrolledText(receipt_window, height=30, width=70, font=('Courier', 9))
            text_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            text_widget.insert('1.0', receipt_text)
            text_widget.config(state=tk.DISABLED)

            def print_receipt():
                try:
                    file_path = filedialog.asksaveasfilename(
                        defaultextension=".txt",
                        filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                        initialfile=f"receipt_{loan_id}.txt"
                    )

                    if file_path:
                        with open(file_path, 'w') as f:
                            f.write(receipt_text)
                        messagebox.showinfo(_("common.success"), f"Receipt saved to:\n{file_path}")

                except (OSError, IOError, tk.TclError) as e:
                    messagebox.showerror(_("common.error"), f"Failed to save receipt: {str(e)}")

            button_frame = ttk.Frame(receipt_window)
            button_frame.pack(fill=tk.X, padx=10, pady=10)

            ttk.Button(button_frame, text="Save Receipt", command=print_receipt).pack(side=tk.LEFT, padx=5)
            ttk.Button(button_frame, text=_("common.close"), command=receipt_window.destroy).pack(side=tk.RIGHT, padx=5)

    except (OSError, IOError, tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_("common.error"), f"Failed to generate receipt: {str(e)}")
        receipt_window.destroy()
