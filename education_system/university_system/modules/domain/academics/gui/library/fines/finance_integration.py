"""
Library Fines Management - Finance system integration (top-up, finance payment, GUI launch).
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from education_system.university_system.modules.shared.utils.i18n import get_text as _

from education_system.university_system.modules.domain.academics.gui.library.fines.constants import (
    ORIGINAL_LIBRARY_AVAILABLE,
    FINANCE_ACCOUNT_AVAILABLE,
    DatabaseError,
    sqlite3,
)

try:
    from education_system.university_system.modules.domain.academics.services.library.database import (
        get_db_connection, log_audit_event,
    )
    from education_system.university_system.modules.domain.academics.services.library.settings import get_current_user_id
except ImportError:
    pass

try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        top_up_student_finance_account,
    )
except ImportError:
    pass


def _show_topup_dialog(self, user_id, shortfall, fine_amount, total_fines, conn):
    """Show dialog to top up finance account and pay fine"""
    dialog = tk.Toplevel(self.root)
    dialog.title(_("library.dialogs.top_up_finance_account"))
    dialog.geometry("400x300")
    dialog.transient(self.root)
    dialog.grab_set()

    # Get current balance
    current_balance = get_student_finance_account_balance(user_id) or 0.0

    ttk.Label(dialog, text=f"Top Up Account for User: {user_id}",
              font=('Segoe UI', 12, 'bold')).pack(pady=10)

    info_frame = ttk.Frame(dialog)
    info_frame.pack(fill=tk.X, padx=20, pady=5)

    ttk.Label(info_frame, text=f"Current Balance: \u00a3{current_balance:.2f}").pack(anchor=tk.W)
    ttk.Label(info_frame, text=f"Fine Amount: \u00a3{fine_amount:.2f}").pack(anchor=tk.W)
    ttk.Label(info_frame, text=f"Minimum Top-up Required: \u00a3{shortfall:.2f}").pack(anchor=tk.W)

    ttk.Separator(dialog, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=20, pady=10)

    # Top-up amount entry
    amount_frame = ttk.Frame(dialog)
    amount_frame.pack(fill=tk.X, padx=20, pady=5)

    ttk.Label(amount_frame, text="Top-up Amount: \u00a3").pack(side=tk.LEFT)
    topup_var = tk.StringVar(value=str(round(shortfall, 2)))
    topup_entry = ttk.Entry(amount_frame, textvariable=topup_var, width=15)
    topup_entry.pack(side=tk.LEFT, padx=5)

    # Quick amount buttons
    quick_frame = ttk.Frame(dialog)
    quick_frame.pack(fill=tk.X, padx=20, pady=5)
    ttk.Label(quick_frame, text="Quick amounts:").pack(side=tk.LEFT)
    for amt in [5, 10, 20, 50]:
        ttk.Button(quick_frame, text=f"\u00a3{amt}",
                   command=lambda a=amt: topup_var.set(str(a))).pack(side=tk.LEFT, padx=2)

    # Pay full fines button
    ttk.Button(quick_frame, text=f"\u00a3{shortfall:.2f} (exact)",
               command=lambda: topup_var.set(str(round(shortfall, 2)))).pack(side=tk.LEFT, padx=2)

    def process_topup_and_pay():
        try:
            topup_amount = float(topup_var.get())
            if topup_amount < shortfall:
                messagebox.showwarning(_("common.warning"),
                    f"Top-up amount (\u00a3{topup_amount:.2f}) is less than required (\u00a3{shortfall:.2f}).\n"
                    "Please enter at least the minimum amount.")
                return

            # Process top-up
            processed_by = get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'System'
            topup_result = top_up_student_finance_account(
                student_id=user_id,
                amount=topup_amount,
                description="Top-up for library fine payment",
                payment_method="Cash/Card at Library",
                processed_by=processed_by
            )

            if not topup_result['success']:
                messagebox.showerror("Top-up Failed", topup_result.get('message', 'Unknown error'))
                return

            # Now process the fine payment
            new_balance = topup_result.get('new_balance', current_balance + topup_amount)

            payment_result = process_student_finance_account_payment(
                student_id=user_id,
                amount=fine_amount,
                description="Library fine payment",
                transaction_source="Library",
                transaction_ref=f"FINE_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                processed_by=processed_by,
                check_balance=True,
                send_low_balance_alert=True
            )

            if not payment_result['success']:
                messagebox.showerror("Payment Failed",
                    f"Top-up succeeded but payment failed: {payment_result.get('message', 'Unknown error')}")
                return

            # Update fines in database
            cursor = conn.cursor()
            cursor.execute('''
                SELECT loan_id, fine_amount FROM book_loans
                WHERE user_id = ? AND fine_amount > 0
                ORDER BY due_date ASC
            ''', (user_id,))

            loans_with_fines = cursor.fetchall()
            remaining_payment = fine_amount
            current_date = datetime.now().strftime('%Y-%m-%d')

            for loan_id, loan_fine in loans_with_fines:
                if remaining_payment <= 0:
                    break
                if remaining_payment >= loan_fine:
                    cursor.execute('''
                        UPDATE book_loans
                        SET fine_amount = 0,
                            notes = COALESCE(notes || '; ', '') || 'Fine paid via Finance Account on ' || ?
                        WHERE loan_id = ?
                    ''', (current_date, loan_id))
                    remaining_payment -= loan_fine
                else:
                    new_fine = loan_fine - remaining_payment
                    cursor.execute('''
                        UPDATE book_loans SET fine_amount = ? WHERE loan_id = ?
                    ''', (new_fine, loan_id))
                    remaining_payment = 0

            conn.commit()
            conn.close()

            final_balance = payment_result.get('new_balance', new_balance - fine_amount)
            messagebox.showinfo(_("common.success"),
                f"Transaction completed successfully!\n\n"
                f"Top-up Amount: \u00a3{topup_amount:.2f}\n"
                f"Fine Paid: \u00a3{fine_amount:.2f}\n"
                f"New Account Balance: \u00a3{final_balance:.2f}")

            dialog.destroy()
            self.payment_amount_var.set("")
            self.load_user_fines()

        except ValueError:
            messagebox.showwarning(_("common.warning"), "Please enter a valid amount")
        except Exception as e:
            messagebox.showerror(_("common.error"), f"Failed to process: {str(e)}")

    # Buttons
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill=tk.X, padx=20, pady=20)

    ttk.Button(btn_frame, text="Top Up & Pay Fine", command=process_topup_and_pay).pack(side=tk.LEFT, padx=5)
    ttk.Button(btn_frame, text=_("common.cancel"), command=lambda: [conn.close(), dialog.destroy()]).pack(side=tk.LEFT, padx=5)


def pay_fine_via_finance(self):
    """Pay library fines through the finance system"""
    user_id = self.fine_user_var.get().strip()
    payment_amount = self.payment_amount_var.get().strip()

    if not user_id:
        messagebox.showwarning(_("common.warning"), "Please search for a user first")
        return

    if not payment_amount:
        messagebox.showwarning(_("common.warning"), "Please enter a payment amount")
        return

    try:
        amount = float(payment_amount)
        if amount <= 0:
            messagebox.showwarning(_("common.warning"), "Payment amount must be greater than 0")
            return
    except ValueError:
        messagebox.showwarning(_("common.warning"), "Please enter a valid payment amount")
        return

    # Get user details for the finance transaction
    try:
        if ORIGINAL_LIBRARY_AVAILABLE:
            conn = get_db_connection()
            if conn:
                cursor = conn.cursor()
                cursor.execute('SELECT first_name, last_name, email_address FROM students WHERE student_id = ?', (user_id,))
                user_info = cursor.fetchone()
                conn.close()

                if not user_info:
                    messagebox.showerror(_("common.error"), "Student not found in system")
                    return

                first_name, last_name, email = user_info
            else:
                first_name, last_name, email = "Demo", "User", "demo@university.edu"
        else:
            first_name, last_name, email = "Demo", "User", "demo@university.edu"

        # Create finance transaction via Finance GUI
        success = self._process_library_fine_payment(
            student_id=user_id,
            amount=amount,
            student_name=f"{first_name} {last_name}",
            email=email
        )

        if success:
            messagebox.showinfo(_("common.success"),
                f"Library fine payment of £{amount:.2f} processed successfully!\n"
                f"Payment has been charged to {first_name} {last_name}'s account.")

            # Send email confirmation
            self._send_library_payment_confirmation_email(
                student_id=user_id,
                student_name=f"{first_name} {last_name}",
                email=email,
                amount=amount
            )

            # Refresh the fines display
            self.load_user_fines()
        else:
            messagebox.showerror(_("common.error"),
                "Failed to process payment through finance system.\n"
                "Please try again or contact the finance office.")

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Failed to process finance payment: {e}")


def _process_library_fine_payment(self, student_id, amount, student_name, email):
    """Process library fine payment through finance system"""
    try:
        # Try to integrate with finance GUI
        from education_system.university_system.infrastructure.database.db import sqlite3, DEFAULT_DB_PATH

        with sqlite3.connect(str(DEFAULT_DB_PATH)) as conn:
            cursor = conn.cursor()
            current_date = datetime.now().strftime('%Y-%m-%d')
            due_date = current_date  # Library fines are due immediately

            # Check for existing unpaid library fee, or create new one
            cursor.execute('''
                SELECT student_fee_id, amount FROM student_fees
                WHERE student_id = ? AND fee_type_id = 3 AND status = 'unpaid'
                ORDER BY created_at DESC LIMIT 1
            ''', (student_id,))

            existing_fee = cursor.fetchone()

            if existing_fee:
                # Update existing fee
                student_fee_id, current_fee_amount = existing_fee
                new_fee_amount = max(0, current_fee_amount - amount)

                if new_fee_amount == 0:
                    # Fully paid
                    cursor.execute('''
                        UPDATE student_fees
                        SET status = 'paid', updated_at = ?
                        WHERE student_fee_id = ?
                    ''', (current_date, student_fee_id))
                else:
                    # Partial payment
                    cursor.execute('''
                        UPDATE student_fees
                        SET amount = ?, updated_at = ?
                        WHERE student_fee_id = ?
                    ''', (new_fee_amount, current_date, student_fee_id))
            else:
                # Create new fee record (already paid)
                cursor.execute('''
                    INSERT INTO student_fees
                    (student_id, fee_type_id, amount, currency, status, due_date, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (student_id, 3, 0.00, 'GBP', 'paid', due_date, current_date, current_date))
                student_fee_id = cursor.lastrowid
                # Skip GL hook — zero-amount synthetic placeholder fee, not a real revenue event.

            # Record payment in payments table
            cursor.execute('''
                INSERT INTO payments
                (student_id, amount, payment_method, payment_date, status, payment_reference, description, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                student_id, amount, 'Student Account', current_date, 'completed',
                f'LIB-{student_id}-{datetime.now().strftime("%Y%m%d%H%M%S")}',
                f'Library fine payment for {student_name}', current_date
            ))
            payment_id = cursor.lastrowid

            # Auto-post to GL now that the SQL is valid (never raises).
            try:
                from education_system.university_system.modules.domain.finance.ledger import notify_ledger
                notify_ledger('payment', payment_id, posted_by='library_fine')
            except Exception as _e:
                import logging
                logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

            # Link payment to fee via payment_allocations
            cursor.execute('''
                INSERT INTO payment_allocations
                (payment_id, student_fee_id, amount, created_at)
                VALUES (?, ?, ?, ?)
            ''', (payment_id, student_fee_id, amount, current_date))

            # Update library fine status to paid (set amount to 0, add note)
            cursor.execute('''
                UPDATE book_loans
                SET fine_amount = 0,
                    notes = COALESCE(notes || '; ', '') || 'Fine paid on ' || ?
                WHERE user_id = ? AND fine_amount > 0
            ''', (current_date, student_id))

            conn.commit()
            return True

    except (sqlite3.Error, DatabaseError) as e:
        print(f"Finance integration error: {e}")
        import traceback
        traceback.print_exc()
        return False


def open_finance_payment_for_user(self, user_id, amount):
    """Open finance system for user to pay late fees"""
    try:
        # Try to launch finance GUI for payment
        try:
            from education_system.university_system.modules.domain.finance.gui.finance import FinanceGUI
            finance_window = tk.Toplevel(self.master)
            finance_window.title(f"Pay Library Fees - £{amount:.2f}")
            finance_window.geometry("800x600")

            # Initialize finance GUI in payment mode
            finance_gui = FinanceGUI(finance_window, auth=self.auth)
            # Pre-populate with library fee information if method exists
            if hasattr(finance_gui, 'prepopulate_library_fee_payment'):
                finance_gui.prepopulate_library_fee_payment(user_id, amount)

        except ImportError:
            # Fallback to showing fine management dialog
            self.fine_user_var = tk.StringVar(value=user_id)
            self.payment_amount_var = tk.StringVar(value=str(amount))
            self.show_fine_management()

    except (tk.TclError, ValueError, TypeError) as e:
        messagebox.showerror(_("common.error"), f"Could not open payment system: {e}")
