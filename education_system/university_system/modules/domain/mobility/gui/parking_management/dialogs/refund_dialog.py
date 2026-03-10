"""Refund processing dialog."""
import tkinter as tk
from tkinter import ttk, messagebox
import logging


class RefundDialog:
    """Dialog for processing parking payment refunds"""

    def __init__(self, parent, payment_data, current_user=None):
        self.result = None
        self.payment_data = payment_data
        self.current_user = current_user
        self.refund_method = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Refund Parking Payment")
        self.dialog.geometry("550x450")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (self.dialog.winfo_width() // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")

        self.create_widgets()

    def create_widgets(self):
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        ttk.Label(main_frame, text=f"Refund Payment - {self.payment_data[4]}",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Payment details
        details_frame = ttk.LabelFrame(main_frame, text="Payment Details", padding="10")
        details_frame.pack(fill=tk.X, pady=(0, 15))

        details = [
            ("Payment ID:", self.payment_data[0]),
            ("Violation ID:", self.payment_data[1]),
            ("Amount:", f"${float(self.payment_data[2]):.2f}"),
            ("Payment Method:", self.payment_data[3].replace('_', ' ').title()),
            ("Payment Reference:", self.payment_data[4]),
            ("Payment Date:", self.payment_data[5])
        ]

        for i, (label, value) in enumerate(details):
            ttk.Label(details_frame, text=label, font=('Arial', 9, 'bold')).grid(
                row=i, column=0, sticky=tk.W, pady=2, padx=(0, 10))
            ttk.Label(details_frame, text=str(value)).grid(
                row=i, column=1, sticky=tk.W, pady=2)

        # Refund method selection
        method_frame = ttk.LabelFrame(main_frame, text="Select Refund Method", padding="10")
        method_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Get student balance if refunding to student account
        student_id = self.payment_data[6] if len(self.payment_data) > 6 else None
        current_balance = None
        new_balance = None

        if student_id:
            try:
                from education_system.university_system.modules.shared.utils.finance_integration import get_student_finance_account_balance
                current_balance = get_student_finance_account_balance(student_id)
                new_balance = current_balance + float(self.payment_data[2])

                balance_frame = ttk.Frame(method_frame)
                balance_frame.pack(fill=tk.X, pady=(0, 10))

                ttk.Label(balance_frame, text=f"Current Student Account Balance: ${current_balance:.2f}",
                         foreground='blue', font=('Arial', 10)).pack()
                ttk.Label(balance_frame, text=f"New Balance After Refund: ${new_balance:.2f}",
                         foreground='green', font=('Arial', 10)).pack()
            except Exception as e:
                logging.warning(f"Could not get student balance: {e}")

        # Refund buttons
        btn_container = ttk.Frame(method_frame)
        btn_container.pack(fill=tk.BOTH, expand=True)

        tk.Button(btn_container, text="💵 Refund as Cash",
                 command=lambda: self.select_refund_method('cash'),
                 font=('Arial', 11, 'bold'), bg='#27ae60', fg='white',
                 activebackground='#229954', activeforeground='white',
                 relief='raised', padx=20, pady=12, cursor='hand2',
                 borderwidth=3).pack(pady=8, fill=tk.X)

        tk.Button(btn_container, text="💳 Refund to Card",
                 command=lambda: self.select_refund_method('card'),
                 font=('Arial', 11, 'bold'), bg='#3498db', fg='white',
                 activebackground='#2980b9', activeforeground='white',
                 relief='raised', padx=20, pady=12, cursor='hand2',
                 borderwidth=3).pack(pady=8, fill=tk.X)

        tk.Button(btn_container, text="🏦 Refund to Student Account",
                 command=lambda: self.select_refund_method('student_account'),
                 font=('Arial', 11, 'bold'), bg='#9b59b6', fg='white',
                 activebackground='#8e44ad', activeforeground='white',
                 relief='raised', padx=20, pady=12, cursor='hand2',
                 borderwidth=3).pack(pady=8, fill=tk.X)

        # Cancel button
        ttk.Button(main_frame, text="Cancel", command=self.dialog.destroy).pack(pady=(10, 0))

    def select_refund_method(self, method):
        """Process refund with selected method"""
        self.refund_method = method

        if not messagebox.askyesno("Confirm Refund",
                                   f"Process refund of ${float(self.payment_data[2]):.2f} via {method.replace('_', ' ').title()}?"):
            return

        self.result = {
            'payment_id': self.payment_data[0],
            'violation_id': self.payment_data[1],
            'amount': float(self.payment_data[2]),
            'refund_method': method,
            'student_id': self.payment_data[6] if len(self.payment_data) > 6 else None
        }

        self.dialog.destroy()
