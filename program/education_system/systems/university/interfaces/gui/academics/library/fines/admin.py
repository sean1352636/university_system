"""
Library Fines Management - Admin actions (waive, adjust, view history).
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from education_system.systems.university.infrastructure.i18n import get_text as _

from education_system.systems.university.interfaces.gui.academics.library.fines.constants import ORIGINAL_LIBRARY_AVAILABLE

try:
    from education_system.systems.university.domain.academics.services.library.database import (
        get_db_connection, log_audit_event,
    )
    from education_system.systems.university.domain.academics.services.library.settings import get_current_user_id
except ImportError:
    pass


def waive_all_fines(self):
    """Waive all outstanding fines for a user"""
    user_id = self.fine_user_var.get().strip()

    if not user_id:
        messagebox.showwarning(_("common.warning"), "Please search for a user first")
        return

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror(_("common.error"), "Database connection unavailable")
                return

            cursor = conn.cursor()

            # Get total outstanding fines
            cursor.execute('''
                SELECT SUM(fine_amount) FROM book_loans
                WHERE user_id = ? AND fine_amount > 0
            ''', (user_id,))
            total_fines = cursor.fetchone()[0] or 0.0

            if total_fines == 0:
                messagebox.showinfo("No Fines", "This user has no outstanding fines to waive")
                conn.close()
                return

            # Confirm waiver
            response = messagebox.askyesno(
                "Confirm Waive Fines",
                f"Are you sure you want to waive all fines for user {user_id}?\n\n"
                f"Total amount to be waived: £{total_fines:.2f}\n\n"
                f"This action cannot be undone."
            )

            if not response:
                conn.close()
                return

            # Waive all fines
            current_date = datetime.now().strftime('%Y-%m-%d')
            cursor.execute('''
                UPDATE book_loans
                SET fine_amount = 0,
                    notes = COALESCE(notes || '; ', '') || 'Fine waived on ' || ?
                WHERE user_id = ? AND fine_amount > 0
            ''', (current_date, user_id))

            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()

            # Log the action
            if ORIGINAL_LIBRARY_AVAILABLE:
                log_audit_event(get_current_user_id(),
                              f"GUI: Waived all fines (£{total_fines:.2f}) for user {user_id}",
                              "book_loans", user_id)

            messagebox.showinfo(_("common.success"),
                f"All fines waived successfully!\n\n"
                f"User ID: {user_id}\n"
                f"Amount waived: £{total_fines:.2f}\n"
                f"Loans affected: {rows_affected}")

            # Refresh the fines display
            self.load_user_fines()

        else:
            # Demo mode
            messagebox.showinfo(_("common.demo"), f"Demo: All fines waived for {user_id}")

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Failed to waive fines: {str(e)}")


def view_fine_history(self):
    """View complete fine payment and waiver history for a user"""
    user_id = self.fine_user_var.get().strip()

    if not user_id:
        messagebox.showwarning(_("common.warning"), "Please search for a user first")
        return

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror(_("common.error"), "Database connection unavailable")
                return

            cursor = conn.cursor()

            # Get all fine-related transactions
            cursor.execute('''
                SELECT loan_id, book_id, checkout_date, due_date, return_date,
                       fine_amount, status, notes
                FROM book_loans
                WHERE user_id = ?
                ORDER BY checkout_date DESC
            ''', (user_id,))

            transactions = cursor.fetchall()
            conn.close()

            if not transactions:
                messagebox.showinfo("No History", "No fine history found for this user")
                return

            # Create history window
            history_window = tk.Toplevel()
            history_window.title(f"Fine History - User {user_id}")
            history_window.geometry("900x500")

            # Header
            header_frame = ttk.Frame(history_window)
            header_frame.pack(fill='x', padx=10, pady=10)

            ttk.Label(header_frame, text=f"Complete Fine History for User: {user_id}",
                     font=('Arial', 12, 'bold')).pack()

            # Calculate statistics
            total_paid = sum(0 for _, _, _, _, _, fine, _, notes in transactions
                           if notes and 'Fine paid on' in notes)
            total_waived = sum(0 for _, _, _, _, _, fine, _, notes in transactions
                             if notes and 'Fine waived on' in notes)
            total_outstanding = sum(fine for _, _, _, _, _, fine, _, _ in transactions if fine > 0)

            stats_frame = ttk.Frame(history_window)
            stats_frame.pack(fill='x', padx=10, pady=5)

            ttk.Label(stats_frame, text=f"Payments: {total_paid} | Waivers: {total_waived} | Outstanding: £{total_outstanding:.2f}",
                     font=('Arial', 10)).pack()

            # Scrollable frame for transactions
            canvas = tk.Canvas(history_window)
            scrollbar = ttk.Scrollbar(history_window, orient="vertical", command=canvas.yview)
            scrollable_frame = ttk.Frame(canvas)

            scrollable_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
            )

            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            # Display transactions
            for loan_id, book_id, checkout, due, returned, fine, status, notes in transactions:
                trans_frame = ttk.LabelFrame(scrollable_frame, text=f"Loan #{loan_id} - Book: {book_id}",
                                            relief='solid', borderwidth=1)
                trans_frame.pack(fill='x', padx=10, pady=5)

                info_text = f"Checkout: {checkout} | Due: {due} | Status: {status}\n"
                if returned:
                    info_text += f"Returned: {returned}\n"
                if fine > 0:
                    info_text += f"Current Fine: £{fine:.2f}\n"
                if notes:
                    info_text += f"Notes: {notes}\n"

                ttk.Label(trans_frame, text=info_text).pack(padx=10, pady=5)

            canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
            scrollbar.pack(side="right", fill="y")

            # Close button
            ttk.Button(history_window, text=_("common.close"), command=history_window.destroy).pack(pady=10)

        else:
            messagebox.showinfo(_("common.demo"), f"Demo: Fine history for {user_id}")

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Failed to load fine history: {str(e)}")


def adjust_fine_amount(self):
    """Manually adjust a fine amount for a specific loan"""
    user_id = self.fine_user_var.get().strip()

    if not user_id:
        messagebox.showwarning(_("common.warning"), "Please search for a user first")
        return

    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if not conn:
                messagebox.showerror(_("common.error"), "Database connection unavailable")
                return

            cursor = conn.cursor()

            # Get loans with fines
            cursor.execute('''
                SELECT loan_id, book_id, fine_amount FROM book_loans
                WHERE user_id = ? AND fine_amount > 0
                ORDER BY due_date ASC
            ''', (user_id,))

            loans = cursor.fetchall()

            if not loans:
                messagebox.showinfo("No Fines", "This user has no outstanding fines to adjust")
                conn.close()
                return

            # Create adjustment dialog
            adjust_dialog = tk.Toplevel()
            adjust_dialog.title("Adjust Fine Amount")
            adjust_dialog.geometry("500x400")

            ttk.Label(adjust_dialog, text="Select Loan and Adjust Fine",
                     font=('Arial', 12, 'bold')).pack(pady=10)

            # Loan selection
            loan_frame = ttk.LabelFrame(adjust_dialog, text="Select Loan", padding=10)
            loan_frame.pack(fill='x', padx=10, pady=5)

            loan_var = tk.StringVar()
            for loan_id, book_id, fine_amt in loans:
                ttk.Radiobutton(loan_frame,
                               text=f"Loan #{loan_id} - Book: {book_id} - Current Fine: £{fine_amt:.2f}",
                               variable=loan_var,
                               value=f"{loan_id}:{fine_amt}").pack(anchor='w', pady=2)

            # Adjustment options
            adjust_options_frame = ttk.LabelFrame(adjust_dialog, text="Adjustment", padding=10)
            adjust_options_frame.pack(fill='x', padx=10, pady=10)

            adjust_type_var = tk.StringVar(value="set")
            ttk.Radiobutton(adjust_options_frame, text="Set to specific amount",
                           variable=adjust_type_var, value="set").grid(row=0, column=0, sticky='w')
            ttk.Radiobutton(adjust_options_frame, text="Increase by",
                           variable=adjust_type_var, value="increase").grid(row=1, column=0, sticky='w')
            ttk.Radiobutton(adjust_options_frame, text="Decrease by",
                           variable=adjust_type_var, value="decrease").grid(row=2, column=0, sticky='w')

            amount_var = tk.StringVar()
            ttk.Entry(adjust_options_frame, textvariable=amount_var, width=15).grid(row=0, column=1, padx=5)
            ttk.Entry(adjust_options_frame, textvariable=amount_var, width=15).grid(row=1, column=1, padx=5)
            ttk.Entry(adjust_options_frame, textvariable=amount_var, width=15).grid(row=2, column=1, padx=5)

            # Reason
            reason_frame = ttk.LabelFrame(adjust_dialog, text="Reason for Adjustment", padding=10)
            reason_frame.pack(fill='both', expand=True, padx=10, pady=5)

            reason_text = tk.Text(reason_frame, height=4, width=50)
            reason_text.pack(fill='both', expand=True)

            def process_adjustment():
                if not loan_var.get():
                    messagebox.showwarning(_("common.warning"), "Please select a loan")
                    return

                try:
                    loan_id, current_fine = loan_var.get().split(':')
                    current_fine = float(current_fine)
                    adjustment = float(amount_var.get())
                    adjust_type = adjust_type_var.get()
                    reason = reason_text.get('1.0', 'end-1c').strip()

                    if not reason:
                        messagebox.showwarning(_("common.warning"), "Please provide a reason for adjustment")
                        return

                    # Calculate new fine amount
                    if adjust_type == "set":
                        new_fine = adjustment
                    elif adjust_type == "increase":
                        new_fine = current_fine + adjustment
                    else:  # decrease
                        new_fine = max(0, current_fine - adjustment)

                    # Update database
                    current_date = datetime.now().strftime('%Y-%m-%d')
                    cursor.execute('''
                        UPDATE book_loans
                        SET fine_amount = ?,
                            notes = COALESCE(notes || '; ', '') || 'Fine adjusted on ' || ? || ': ' || ?
                        WHERE loan_id = ?
                    ''', (new_fine, current_date, reason, loan_id))

                    conn.commit()
                    conn.close()

                    # Log the action
                    if ORIGINAL_LIBRARY_AVAILABLE:
                        log_audit_event(get_current_user_id(),
                                      f"GUI: Adjusted fine for loan {loan_id} from £{current_fine:.2f} to £{new_fine:.2f}. Reason: {reason}",
                                      "book_loans", loan_id)

                    messagebox.showinfo(_("common.success"),
                        f"Fine adjusted successfully!\n\n"
                        f"Loan ID: {loan_id}\n"
                        f"Previous amount: £{current_fine:.2f}\n"
                        f"New amount: £{new_fine:.2f}")

                    adjust_dialog.destroy()
                    self.load_user_fines()

                except ValueError:
                    messagebox.showerror(_("common.error"), "Please enter a valid amount")
                except tk.TclError as e:
                    messagebox.showerror(_("common.error"), f"Failed to adjust fine: {str(e)}")

            # Buttons
            button_frame = ttk.Frame(adjust_dialog)
            button_frame.pack(fill='x', padx=10, pady=10)

            ttk.Button(button_frame, text="Apply Adjustment",
                      command=process_adjustment).pack(side='left', padx=5)
            ttk.Button(button_frame, text=_("common.cancel"),
                      command=adjust_dialog.destroy).pack(side='right', padx=5)

        else:
            messagebox.showinfo(_("common.demo"), f"Demo: Adjust fine for {user_id}")

    except (tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_("common.error"), f"Failed to open adjustment dialog: {str(e)}")
