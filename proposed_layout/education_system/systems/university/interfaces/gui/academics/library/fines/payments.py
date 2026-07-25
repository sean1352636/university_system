"""
Library Fines Management - Payment processing (manual, finance account, GUI).
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime
from education_system.systems.university.infrastructure.i18n import get_text as _

from education_system.systems.university.interfaces.gui.academics.library.fines.constants import (
    ORIGINAL_LIBRARY_AVAILABLE,
    FINANCE_ACCOUNT_AVAILABLE,
    DatabaseError,
    sqlite3,
)

try:
    from education_system.systems.university.domain.academics.services.library.database import (
        get_db_connection, log_audit_event,
    )
    from education_system.systems.university.domain.academics.services.library.settings import get_current_user_id
except ImportError:
    pass

try:
    from education_system.systems.university.infrastructure.utils.finance_integration import (
        process_student_finance_account_payment,
        get_student_finance_account_balance,
        ensure_student_finance_account_exists,
        top_up_student_finance_account,
    )
except ImportError:
    pass


def process_fine_payment(self):
    """Process a manual fine payment (cash/card at library desk)"""
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

    # Get user details
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
                messagebox.showinfo("No Fines", "This user has no outstanding fines")
                conn.close()
                return

            if amount > total_fines:
                response = messagebox.askyesno(
                    "Payment Exceeds Fines",
                    f"Payment amount (£{amount:.2f}) exceeds total fines (£{total_fines:.2f}).\n\n"
                    f"Do you want to process payment of £{total_fines:.2f} (full balance) instead?"
                )
                if response:
                    amount = total_fines
                else:
                    conn.close()
                    return

            # Apply payment to fines (oldest first)
            cursor.execute('''
                SELECT loan_id, fine_amount FROM book_loans
                WHERE user_id = ? AND fine_amount > 0
                ORDER BY due_date ASC
            ''', (user_id,))

            loans_with_fines = cursor.fetchall()
            remaining_payment = amount
            current_date = datetime.now().strftime('%Y-%m-%d')

            for loan_id, fine_amount in loans_with_fines:
                if remaining_payment <= 0:
                    break

                if remaining_payment >= fine_amount:
                    # Pay full fine for this loan
                    cursor.execute('''
                        UPDATE book_loans
                        SET fine_amount = 0,
                            notes = COALESCE(notes || '; ', '') || 'Fine paid on ' || ?
                        WHERE loan_id = ?
                    ''', (current_date, loan_id))
                    remaining_payment -= fine_amount
                else:
                    # Partial payment
                    new_fine_amount = fine_amount - remaining_payment
                    cursor.execute('''
                        UPDATE book_loans
                        SET fine_amount = ?
                        WHERE loan_id = ?
                    ''', (new_fine_amount, loan_id))
                    remaining_payment = 0

            # _record_fine_payment was called here (per-loan payment rows on
            # the caller-owned conn) but it duplicated the summary INSERT in
            # _record_library_payment_in_finance below. One fine payment was
            # producing N+1 payment rows. Removed; the summary helper does
            # allocations and is GL-hooked.
            finance_success = self._record_library_payment_in_finance(
                user_id=user_id,
                amount=amount,
                payment_method="Cash/Card at Library Desk"
            )

            conn.commit()
            conn.close()

            # Log the action
            if ORIGINAL_LIBRARY_AVAILABLE:
                log_audit_event(get_current_user_id(),
                              f"GUI: Processed manual fine payment £{amount:.2f} for user {user_id}",
                              "book_loans", user_id)

            success_msg = (
                f"Payment of £{amount:.2f} processed successfully!\n\n"
                f"Payment Method: Manual (Cash/Card at Desk)\n"
                f"User ID: {user_id}\n"
                f"Remaining balance will be shown in the refreshed list."
            )

            if finance_success:
                success_msg += "\n\n\u2713 Payment recorded in Finance System"
            else:
                success_msg += "\n\n\u26a0 Payment processed but finance recording failed"

            messagebox.showinfo(_("common.success"), success_msg)

            # Clear payment amount field
            self.payment_amount_var.set("")

            # Refresh the fines display
            self.load_user_fines()

        else:
            # Demo mode
            messagebox.showinfo(_("common.demo"), f"Demo: Payment of £{amount:.2f} processed for {user_id}")

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Failed to process payment: {str(e)}")


def pay_fine_from_finance_account(self):
    """Process fine payment from student's finance account balance"""
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

    if not FINANCE_ACCOUNT_AVAILABLE:
        messagebox.showerror(_("common.error"), "Finance account integration is not available")
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
                messagebox.showinfo("No Fines", "This user has no outstanding fines")
                conn.close()
                return

            if amount > total_fines:
                response = messagebox.askyesno(
                    "Payment Exceeds Fines",
                    f"Payment amount (\u00a3{amount:.2f}) exceeds total fines (\u00a3{total_fines:.2f}).\n\n"
                    f"Do you want to process payment of \u00a3{total_fines:.2f} (full balance) instead?"
                )
                if response:
                    amount = total_fines
                else:
                    conn.close()
                    return

            # Check student finance account balance
            current_balance = get_student_finance_account_balance(user_id)
            if current_balance is None:
                # Offer to create a finance account
                create_account = messagebox.askyesno(
                    "No Finance Account",
                    f"No finance account found for user {user_id}.\n\n"
                    "Would you like to create a finance account now?"
                )
                if create_account:
                    if ensure_student_finance_account_exists(user_id):
                        current_balance = 0.0
                        messagebox.showinfo("Account Created",
                            f"Finance account created for user {user_id}.\n"
                            "The account has a \u00a30.00 balance. You can top up now.")
                    else:
                        messagebox.showerror(_("common.error"), "Failed to create finance account")
                        conn.close()
                        return
                else:
                    conn.close()
                    return

            if current_balance < amount:
                # Offer to top up the account
                shortfall = amount - current_balance
                topup_response = messagebox.askyesno(
                    "Insufficient Balance",
                    f"Student finance account balance is insufficient.\n\n"
                    f"Current Balance: \u00a3{current_balance:.2f}\n"
                    f"Required Amount: \u00a3{amount:.2f}\n"
                    f"Shortfall: \u00a3{shortfall:.2f}\n\n"
                    f"Would you like to top up the account now?"
                )
                if topup_response:
                    self._show_topup_dialog(user_id, shortfall, amount, total_fines, conn)
                    return
                else:
                    conn.close()
                    return

            # Process the payment from finance account
            processed_by = get_current_user_id() if ORIGINAL_LIBRARY_AVAILABLE else 'System'
            payment_result = process_student_finance_account_payment(
                student_id=user_id,
                amount=amount,
                description="Library fine payment",
                transaction_source="Library",
                transaction_ref=f"FINE_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                processed_by=processed_by,
                check_balance=True,
                send_low_balance_alert=True
            )

            if not payment_result['success']:
                messagebox.showerror("Payment Failed", payment_result['message'])
                conn.close()
                return

            # Apply payment to fines (oldest first)
            cursor.execute('''
                SELECT loan_id, fine_amount FROM book_loans
                WHERE user_id = ? AND fine_amount > 0
                ORDER BY due_date ASC
            ''', (user_id,))

            loans_with_fines = cursor.fetchall()
            remaining_payment = amount
            current_date = datetime.now().strftime('%Y-%m-%d')

            for loan_id, fine_amount in loans_with_fines:
                if remaining_payment <= 0:
                    break

                if remaining_payment >= fine_amount:
                    # Pay full fine for this loan
                    cursor.execute('''
                        UPDATE book_loans
                        SET fine_amount = 0,
                            notes = COALESCE(notes || '; ', '') || 'Fine paid via Finance Account on ' || ?
                        WHERE loan_id = ?
                    ''', (current_date, loan_id))
                    remaining_payment -= fine_amount
                else:
                    # Partial payment
                    new_fine_amount = fine_amount - remaining_payment
                    cursor.execute('''
                        UPDATE book_loans
                        SET fine_amount = ?
                        WHERE loan_id = ?
                    ''', (new_fine_amount, loan_id))
                    remaining_payment = 0

            # _record_fine_payment was called here too (same duplication as
            # the cash/card flow above). Removed; the summary helper below is
            # the single source of truth for the payment row.
            self._record_library_payment_in_finance(
                user_id=user_id,
                amount=amount,
                payment_method="Student Finance Account"
            )

            conn.commit()
            conn.close()

            # Log the action
            if ORIGINAL_LIBRARY_AVAILABLE:
                log_audit_event(get_current_user_id(),
                              f"GUI: Processed finance account payment \u00a3{amount:.2f} for user {user_id}",
                              "book_loans", user_id)

            # Build success message
            new_balance = payment_result.get('new_balance', 0)
            low_balance_email_sent = payment_result.get('email_sent', False)

            success_msg = (
                f"Payment of \u00a3{amount:.2f} processed successfully!\n\n"
                f"Payment Method: Student Finance Account\n"
                f"New Account Balance: \u00a3{new_balance:.2f}\n"
                f"User ID: {user_id}\n"
                f"Remaining library balance will be shown in the refreshed list."
            )

            if low_balance_email_sent:
                success_msg += "\n\n\u26a0 Low balance alert email sent to student"

            messagebox.showinfo(_("common.success"), success_msg)

            # Clear payment amount field
            self.payment_amount_var.set("")

            # Refresh the fines display
            self.load_user_fines()

        else:
            # Demo mode
            messagebox.showinfo(_("common.demo"), f"Demo: Finance account payment of \u00a3{amount:.2f} processed for {user_id}")

    except tk.TclError as e:
        messagebox.showerror(_("common.error"), f"Failed to process payment: {str(e)}")
    except Exception as e:
        messagebox.showerror(_("common.error"), f"Failed to process payment: {str(e)}")


def process_fine_payment_gui(self):
    """Process fine payment interface"""
    payment_window = tk.Toplevel(self.master)
    payment_window.title("Process Fine Payment")
    payment_window.geometry("600x500")

    ttk.Label(payment_window, text="Process Fine Payment",
             font=('Arial', 16, 'bold')).pack(pady=10)

    # Search frame
    search_frame = ttk.LabelFrame(payment_window, text="Find Loan with Fine", padding=15)
    search_frame.pack(fill=tk.X, padx=10, pady=10)

    search_type = tk.StringVar(value="user_id")
    search_value = tk.StringVar()

    ttk.Radiobutton(search_frame, text="By User ID", variable=search_type, value="user_id").grid(row=0, column=0, sticky=tk.W, padx=5)
    ttk.Radiobutton(search_frame, text="By Loan ID", variable=search_type, value="loan_id").grid(row=0, column=1, sticky=tk.W, padx=5)

    ttk.Entry(search_frame, textvariable=search_value, width=30).grid(row=1, column=0, columnspan=2, padx=5, pady=10)

    # Results frame
    results_frame = ttk.LabelFrame(payment_window, text="Outstanding Fines", padding=10)
    results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    columns = ('Loan ID', 'Book Title', 'User', 'Fine Amount', 'Days Overdue')
    fines_tree = ttk.Treeview(results_frame, columns=columns, show='headings', height=8)

    for col in columns:
        fines_tree.heading(col, text=col)
        fines_tree.column(col, width=110)

    fines_tree.pack(fill=tk.BOTH, expand=True)

    # Right-click: jump to student finance with fine_amount / loan_id
    # context, or send the borrower an overdue notice.
    try:
        from education_system.systems.university.interfaces.gui.academics.library import _cross_links
        _cross_links.attach_cross_link_menu(
            fines_tree, _cross_links.fines_menu_items,
            parent=payment_window,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Could not attach cross-link menu to fines_tree")

    def search_fines():
        for item in fines_tree.get_children():
            fines_tree.delete(item)

        stype = search_type.get()
        svalue = search_value.get().strip()

        if not svalue:
            messagebox.showwarning(_("common.warning"), "Please enter a search value")
            return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            if stype == "user_id":
                query = '''
                SELECT l.loan_id, b.title, l.user_id, l.fine_amount,
                       CAST((julianday('now') - julianday(l.due_date)) AS INTEGER) as days_overdue
                FROM book_loans l
                JOIN books b ON l.book_id = b.book_id
                WHERE l.user_id = ? AND l.fine_amount > 0 AND l.status != 'returned'
                '''
            else:
                query = '''
                SELECT l.loan_id, b.title, l.user_id, l.fine_amount,
                       CAST((julianday('now') - julianday(l.due_date)) AS INTEGER) as days_overdue
                FROM book_loans l
                JOIN books b ON l.book_id = b.book_id
                WHERE l.loan_id = ? AND l.fine_amount > 0 AND l.status != 'returned'
                '''

            cursor.execute(query, (svalue,))
            fines = cursor.fetchall()
            conn.close()

            for fine in fines:
                fines_tree.insert('', 'end', values=(
                    fine[0], fine[1][:40], fine[2], f"£{fine[3]:.2f}", fine[4]
                ))

            if not fines:
                messagebox.showinfo("No Fines", "No outstanding fines found")

        except (sqlite3.Error, DatabaseError, tk.TclError) as e:
            messagebox.showerror(_("common.error"), f"Search failed: {str(e)}")

    ttk.Button(search_frame, text=_("common.search"), command=search_fines).grid(row=1, column=2, padx=5)

    def process_payment():
        selection = fines_tree.selection()
        if not selection:
            messagebox.showwarning(_("common.warning"), "Please select a fine to pay")
            return

        item = fines_tree.item(selection[0])
        loan_id = item['values'][0]
        fine_amount_str = item['values'][3]
        fine_amount = float(fine_amount_str.replace('$', ''))

        # Payment dialog
        pay_dialog = tk.Toplevel(payment_window)
        pay_dialog.title("Process Payment")
        pay_dialog.geometry("400x300")

        ttk.Label(pay_dialog, text="Process Fine Payment",
                 font=('Arial', 12, 'bold')).pack(pady=10)

        info_frame = ttk.Frame(pay_dialog, padding=15)
        info_frame.pack(fill=tk.X)

        ttk.Label(info_frame, text=f"Loan ID: {loan_id}").pack(anchor=tk.W, pady=2)
        ttk.Label(info_frame, text=f"Fine Amount: £{fine_amount:.2f}",
                 font=('Arial', 11, 'bold')).pack(anchor=tk.W, pady=2)

        payment_method_var = tk.StringVar(value="cash")
        ttk.Label(info_frame, text="Payment Method:").pack(anchor=tk.W, pady=(10, 2))
        ttk.Radiobutton(info_frame, text="Cash", variable=payment_method_var, value="cash").pack(anchor=tk.W, padx=20)
        ttk.Radiobutton(info_frame, text="Card", variable=payment_method_var, value="card").pack(anchor=tk.W, padx=20)
        ttk.Radiobutton(info_frame, text="Check", variable=payment_method_var, value="check").pack(anchor=tk.W, padx=20)
        if FINANCE_ACCOUNT_AVAILABLE:
            ttk.Radiobutton(info_frame, text="Finance Account", variable=payment_method_var, value="finance_account").pack(anchor=tk.W, padx=20)

        # Get user_id from the selected fine
        user_id_for_payment = item['values'][2]

        def confirm_payment():
            try:
                payment_method = payment_method_var.get()
                payment_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Handle finance account payment separately
                if payment_method == "finance_account":
                    if not FINANCE_ACCOUNT_AVAILABLE:
                        messagebox.showerror(_("common.error"), "Finance account integration not available")
                        return

                    # Check if account exists
                    current_balance = get_student_finance_account_balance(user_id_for_payment)
                    if current_balance is None:
                        # Offer to create account
                        create = messagebox.askyesno("No Account",
                            f"No finance account found for {user_id_for_payment}.\n\nCreate one now?")
                        if create:
                            if ensure_student_finance_account_exists(user_id_for_payment):
                                current_balance = 0.0
                                messagebox.showinfo("Created", "Account created with \u00a30.00 balance.\nPlease top up first.")
                                return
                            else:
                                messagebox.showerror(_("common.error"), "Failed to create account")
                                return
                        else:
                            return

                    if current_balance < fine_amount:
                        shortfall = fine_amount - current_balance
                        topup = messagebox.askyesno("Insufficient Balance",
                            f"Balance: \u00a3{current_balance:.2f}\nRequired: \u00a3{fine_amount:.2f}\nShortfall: \u00a3{shortfall:.2f}\n\nTop up now?")
                        if topup:
                            # Show simple top-up dialog
                            topup_amt = simpledialog.askfloat("Top Up", f"Enter top-up amount (min \u00a3{shortfall:.2f}):",
                                minvalue=shortfall, initialvalue=shortfall)
                            if topup_amt:
                                result = top_up_student_finance_account(
                                    student_id=user_id_for_payment,
                                    amount=topup_amt,
                                    description="Top-up for library fine",
                                    payment_method="Cash/Card",
                                    processed_by=get_current_user_id()
                                )
                                if not result['success']:
                                    messagebox.showerror(_("common.error"), f"Top-up failed: {result.get('message')}")
                                    return
                                current_balance = result.get('new_balance', current_balance + topup_amt)
                            else:
                                return
                        else:
                            return

                    # Process payment from finance account
                    processed_by = get_current_user_id()
                    payment_result = process_student_finance_account_payment(
                        student_id=user_id_for_payment,
                        amount=fine_amount,
                        description=f"Library fine payment (Loan {loan_id})",
                        transaction_source="Library",
                        transaction_ref=f"FINE_{loan_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        processed_by=processed_by,
                        check_balance=True
                    )

                    if not payment_result['success']:
                        messagebox.showerror(_("common.error"), f"Payment failed: {payment_result.get('message')}")
                        return

                    new_balance = payment_result.get('new_balance', 0)

                # Update database
                conn = get_db_connection()
                cursor = conn.cursor()

                # Record payment in payments table with source_type='library_fine'
                cursor.execute('''
                INSERT INTO payments (
                    student_id, amount, currency, payment_method, payment_date, status,
                    notes, created_by, created_at, source_type, reference_id, reference_type,
                    payment_reference
                ) VALUES (?, ?, 'GBP', ?, ?, 'completed', ?, ?, ?, 'library_fine', ?, 'loan', ?)
                ''', (user_id_for_payment, fine_amount, payment_method, payment_date,
                      f'Library fine payment (Loan {loan_id})',
                      get_current_user_id(), payment_date,
                      str(loan_id),
                      f'FINE_{loan_id}_{datetime.now().strftime("%Y%m%d%H%M%S")}'))
                payment_row_id = cursor.lastrowid

                # Update loan - mark fine as paid
                cursor.execute('''
                UPDATE book_loans
                SET fine_amount = 0
                WHERE loan_id = ?
                ''', (loan_id,))

                conn.commit()
                conn.close()

                # Auto-post to GL (never raises)
                try:
                    from education_system.systems.university.domain.finance.ledger import notify_ledger
                    notify_ledger('payment', payment_row_id, posted_by=str(get_current_user_id() or 'library_fine'))
                except Exception as _e:
                    import logging
                    logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

                log_audit_event(get_current_user_id(),
                              f"Processed fine payment: £{fine_amount:.2f} for loan {loan_id} via {payment_method}",
                              "payments")

                # Generate receipt
                self.generate_fine_receipt_gui(loan_id, fine_amount, payment_method, payment_date)

                pay_dialog.destroy()

                if payment_method == "finance_account":
                    messagebox.showinfo(_("common.success"),
                        f"Payment processed successfully!\n\nAmount: \u00a3{fine_amount:.2f}\nNew Balance: \u00a3{new_balance:.2f}")
                else:
                    messagebox.showinfo(_("common.success"), f"Payment processed successfully!\n\nAmount: £{fine_amount:.2f}")

                search_fines()  # Refresh list

            except Exception as e:
                messagebox.showerror(_("common.error"), f"Payment failed: {str(e)}")

        ttk.Button(info_frame, text="Process Payment", command=confirm_payment).pack(pady=20)

    # Button frame
    button_frame = ttk.Frame(payment_window)
    button_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Button(button_frame, text="Process Payment", command=process_payment).pack(side=tk.LEFT, padx=5)
    ttk.Button(button_frame, text=_("common.close"), command=payment_window.destroy).pack(side=tk.RIGHT, padx=5)
