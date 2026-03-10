"""Payment processing dialog."""
import tkinter as tk
from tkinter import ttk, messagebox
import logging

from .. import get_connection


class PaymentDialog:
    """Dialog for processing parking fine payments"""

    def __init__(self, parent, violation_data, current_user=None):
        self.result = None
        self.violation_data = violation_data
        self.current_user = current_user
        self.payment_method = None

        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Pay Parking Fine")
        self.dialog.geometry("550x500")
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
        ttk.Label(main_frame, text=f"Pay Parking Fine - {self.violation_data[0]}",
                 font=('Arial', 14, 'bold')).pack(pady=(0, 15))

        # Violation details
        details_frame = ttk.LabelFrame(main_frame, text="Violation Details", padding="10")
        details_frame.pack(fill=tk.X, pady=(0, 15))

        details = [
            ("Type:", self.violation_data[2]),
            ("License Plate:", self.violation_data[1]),
            ("Date:", self.violation_data[3]),
            ("Location:", self.violation_data[6]),
            ("Fine Amount:", f"${float(self.violation_data[4]):.2f}"),
            ("Status:", self.violation_data[5])
        ]

        for i, (label, value) in enumerate(details):
            ttk.Label(details_frame, text=label, font=('Arial', 9, 'bold')).grid(
                row=i, column=0, sticky=tk.W, pady=2, padx=(0, 10))
            ttk.Label(details_frame, text=str(value)).grid(
                row=i, column=1, sticky=tk.W, pady=2)

        # Payment method selection
        method_frame = ttk.LabelFrame(main_frame, text="Select Payment Method", padding="10")
        method_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # Get student balance if available
        student_id = self.get_student_id_from_violation()
        current_balance = None
        new_balance = None

        if student_id:
            try:
                from education_system.university_system.modules.shared.utils.finance_integration import get_student_finance_account_balance
                current_balance = get_student_finance_account_balance(student_id)
                new_balance = current_balance - float(self.violation_data[4])
            except Exception as e:
                logging.warning(f"Could not get student balance: {e}")

        # Display balance if available
        if current_balance is not None:
            balance_frame = ttk.Frame(method_frame)
            balance_frame.pack(fill=tk.X, pady=(0, 10))

            ttk.Label(balance_frame, text=f"Current Student Account Balance: ${current_balance:.2f}",
                     foreground='blue', font=('Arial', 10)).pack()
            ttk.Label(balance_frame, text=f"New Balance After Payment: ${new_balance:.2f}",
                     foreground='green' if new_balance >= 0 else 'red',
                     font=('Arial', 10)).pack()

            if new_balance < 0:
                ttk.Label(balance_frame, text="⚠ Insufficient balance for student account payment",
                         foreground='red').pack()

        # Payment buttons
        btn_container = ttk.Frame(method_frame)
        btn_container.pack(fill=tk.BOTH, expand=True)

        tk.Button(btn_container, text="💵 Pay with Cash",
                 command=lambda: self.select_payment_method('cash'),
                 font=('Arial', 11, 'bold'), bg='#27ae60', fg='white',
                 activebackground='#229954', activeforeground='white',
                 relief='raised', padx=20, pady=12, cursor='hand2',
                 borderwidth=3).pack(pady=8, fill=tk.X)

        tk.Button(btn_container, text="💳 Pay with Card",
                 command=lambda: self.select_payment_method('card'),
                 font=('Arial', 11, 'bold'), bg='#3498db', fg='white',
                 activebackground='#2980b9', activeforeground='white',
                 relief='raised', padx=20, pady=12, cursor='hand2',
                 borderwidth=3).pack(pady=8, fill=tk.X)

        student_account_enabled = current_balance is not None and new_balance >= 0
        student_account_btn = tk.Button(btn_container, text="🏦 Pay with Student Account",
                                       command=lambda: self.select_payment_method('student_account'),
                                       font=('Arial', 11, 'bold'),
                                       bg='#9b59b6' if student_account_enabled else '#95a5a6',
                                       fg='white',
                                       activebackground='#8e44ad' if student_account_enabled else '#7f8c8d',
                                       activeforeground='white',
                                       relief='raised', padx=20, pady=12,
                                       cursor='hand2' if student_account_enabled else 'arrow',
                                       borderwidth=3,
                                       state='normal' if student_account_enabled else 'disabled')
        student_account_btn.pack(pady=8, fill=tk.X)

        # Cancel button
        ttk.Button(main_frame, text="Cancel", command=self.dialog.destroy).pack(pady=(10, 0))

    def get_student_id_from_violation(self):
        """Get student ID from violation license plate"""
        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Get vehicle owner from license plate
            cursor.execute("""
                SELECT owner_id FROM vehicles
                WHERE license_plate = ?
            """, (self.violation_data[1],))

            result = cursor.fetchone()
            conn.close()
            return result[0] if result else None
        except Exception as e:
            logging.error(f"Error getting student ID: {e}")
            return None

    def select_payment_method(self, method):
        """Process payment with selected method"""
        self.payment_method = method

        if not messagebox.askyesno("Confirm Payment",
                                   f"Process payment of ${float(self.violation_data[4]):.2f} via {method.replace('_', ' ').title()}?"):
            return

        self.result = {
            'violation_id': self.violation_data[0],
            'amount': float(self.violation_data[4]),
            'payment_method': method,
            'student_id': self.get_student_id_from_violation()
        }

        self.dialog.destroy()
