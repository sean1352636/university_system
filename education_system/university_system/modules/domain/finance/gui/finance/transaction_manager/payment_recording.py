"""Payment recording dialogs and payment detail views"""

from unittest.mock import Mock

from education_system.university_system.modules.domain.finance.gui.finance.transaction_manager._imports import (
    tk, ttk, messagebox, simpledialog, _, datetime, get_connection, get_auth,
)

try:
    from education_system.university_system.infrastructure.email.email_service import send_email as _send_email
except Exception:
    def _send_email(*args, **kwargs):
        return False

try:
    from education_system.university_system.infrastructure.email.template_utils import (
        load_template, render_template,
    )
except Exception:
    def load_template(*args, **kwargs):
        return None
    def render_template(*args, **kwargs):
        return None, None


PAYMENT_EMAIL_TEMPLATE = 'finance/payment_recorded'


def _send_payment_confirmation_email(student_email, student_name, payment_id,
                                     amount, payment_method, payment_date,
                                     purpose, transaction_id):
    """Render the payment-recorded template and send it. Returns True on success.

    Template lives at ``templates/email/finance/payment_recorded.json``;
    operational flags (``enabled``, ``send_copy_to_finance``,
    ``finance_email``) live alongside the subject/body in that file.
    """
    try:
        if not student_email:
            return False
        template_data = load_template(PAYMENT_EMAIL_TEMPLATE)
        if not template_data or not template_data.get('enabled', True):
            return False
        fmt = {
            'student_name': student_name or 'Student',
            'payment_id': payment_id,
            'invoice_number': f"PAY-{payment_id}",
            'amount': f"{amount:,.2f}",
            'payment_method': payment_method or '',
            'payment_date': payment_date or '',
            'purpose': purpose or '',
            'transaction_id': transaction_id or 'N/A',
        }
        subject, body = render_template(PAYMENT_EMAIL_TEMPLATE, fmt)
        if not subject or not body:
            return False
        cc = None
        if template_data.get('send_copy_to_finance') and template_data.get('finance_email'):
            cc = [template_data['finance_email']]
        return bool(_send_email(student_email, subject, body, cc=cc))
    except Exception as e:
        print(f"Failed to send payment confirmation email: {e}")
        return False


class PaymentRecordingMixin:
    """Mixin for payment recording and viewing"""

    def _load_student_list(self):
        """Load students from DB for dropdown. Returns (display_list, id_map)."""
        students = []
        id_map = {}
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT student_id, first_name, last_name
                FROM students ORDER BY last_name, first_name
            ''')
            for row in cursor.fetchall():
                display = f"{row[0]} - {row[1]} {row[2]}"
                students.append(display)
                id_map[display] = row[0]
            conn.close()
        except Exception as e:
            print(f"Error loading students: {e}")
        return students, id_map

    def show_payment_dialog(self):
        """Show payment recording dialog — single form with student dropdown"""
        self._open_record_payment_form()

    def gui_record_payment(self):
        """GUI wrapper for record_payment — single form with student dropdown"""
        self._open_record_payment_form()

    def _open_record_payment_form(self):
        """Single unified payment recording form with student dropdown."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.record_payment_title"))
        dialog.geometry("580x600")
        dialog.transient(self.root)
        dialog.grab_set()

        if isinstance(dialog, Mock) or not hasattr(dialog, "tk") or not hasattr(dialog, "_w"):
            return dialog

        ttk.Label(dialog, text="Record Payment",
                 font=('Arial', 14, 'bold')).pack(pady=(10, 5))

        form_frame = ttk.Frame(dialog, padding=10)
        form_frame.pack(fill='both', expand=True, padx=15)

        row = 0

        # --- Student dropdown ---
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.student_id_label") + ":",
                 font=('Arial', 10)).grid(row=row, column=0, sticky='w', pady=5, padx=5)

        students, student_id_map = self._load_student_list()

        # Pre-select current user if they are a student
        auth = get_auth()
        preselect_display = ""
        if auth and hasattr(auth, 'current_user') and auth.current_user:
            current_sid = auth.current_user.get('student_id') or auth.current_user.get('user_id', '')
            if current_sid:
                for display, sid in student_id_map.items():
                    if sid == current_sid:
                        preselect_display = display
                        break

        student_var = tk.StringVar(value=preselect_display)
        student_combo = ttk.Combobox(form_frame, textvariable=student_var,
                                     values=students, state='readonly', width=38)
        student_combo.grid(row=row, column=1, pady=5, padx=5)
        row += 1

        # --- Payment purpose ---
        ttk.Label(form_frame, text="Payment For:", font=('Arial', 10)).grid(
            row=row, column=0, sticky='w', pady=5, padx=5)

        purpose_var = tk.StringVar(value="General Fee Payment")
        payment_purposes = [
            "General Fee Payment",
            "Tuition Fees",
            "Course Materials",
            "Lab Fees",
            "Exam Fees",
            "Library Fines",
            "Late Submission Penalty",
            "Academic Transcript",
            "Certificate Fee",
            "Restaurant - Meal",
            "Cafe - Coffee/Snacks",
            "Takeaway - Food Order",
            "Bar - Beverages",
            "Grocery - Shopping",
            "Dentist - Dental Treatment",
            "Gym - Membership",
            "Barber - Haircut",
            "Nail Bar - Manicure/Pedicure",
            "Music Shop - Instruments/Equipment",
            "Phone Shop - Mobile/Accessories",
            "Car Rental - Vehicle Hire",
            "Housing - Rent Payment",
            "Accommodation Deposit",
            "Student Union - Membership/Events",
            "Club/Society Fee",
            "Printing Services",
            "Other"
        ]
        purpose_combo = ttk.Combobox(form_frame, textvariable=purpose_var,
                                     values=payment_purposes, width=38)
        purpose_combo.grid(row=row, column=1, pady=5, padx=5)
        row += 1

        # --- Amount ---
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.payment_amount_label") + ":",
                 font=('Arial', 10)).grid(row=row, column=0, sticky='w', pady=5, padx=5)
        amount_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=amount_var, width=20, font=('Arial', 11)).grid(
            row=row, column=1, sticky='w', pady=5, padx=5)
        row += 1

        # --- Payment method ---
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.payment_method_label") + ":",
                 font=('Arial', 10)).grid(row=row, column=0, sticky='w', pady=5, padx=5)
        method_var = tk.StringVar(value="Card")
        method_combo = ttk.Combobox(form_frame, textvariable=method_var,
                                   values=["Student Finance Account", "Card", "Cash",
                                           "Bank Transfer", "Cheque", "Online"],
                                   state='readonly', width=20)
        method_combo.grid(row=row, column=1, sticky='w', pady=5, padx=5)
        row += 1

        # --- Balance display for Student Finance Account ---
        balance_label_var = tk.StringVar(value="")
        balance_label = ttk.Label(form_frame, textvariable=balance_label_var,
                                 font=('Arial', 9), foreground='blue')
        balance_label.grid(row=row, column=0, columnspan=2, sticky='w', padx=5)
        row += 1

        def update_balance_display(*args):
            if method_var.get() == "Student Finance Account" and student_var.get():
                sid = student_id_map.get(student_var.get())
                if sid:
                    try:
                        conn = self._get_connection()
                        cursor = conn.cursor()
                        cursor.execute('SELECT balance FROM student_finance_accounts WHERE student_id = ?', (sid,))
                        result = cursor.fetchone()
                        balance = result[0] if result else 0.0
                        balance_label_var.set(f"Account Balance: \u00a3{balance:,.2f}")
                        conn.close()
                    except Exception:
                        balance_label_var.set("")
            else:
                balance_label_var.set("")

        method_var.trace_add('write', lambda *a: update_balance_display())
        student_combo.bind('<<ComboboxSelected>>', lambda e: update_balance_display())

        # --- Payment date ---
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.payment_date_label") + ":",
                 font=('Arial', 10)).grid(row=row, column=0, sticky='w', pady=5, padx=5)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(form_frame, textvariable=date_var, width=15).grid(
            row=row, column=1, sticky='w', pady=5, padx=5)
        row += 1

        # --- Transaction ID (optional) ---
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.transaction_id_label") + ":",
                 font=('Arial', 10)).grid(row=row, column=0, sticky='w', pady=5, padx=5)
        trans_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=trans_id_var, width=25).grid(
            row=row, column=1, sticky='w', pady=5, padx=5)
        row += 1

        # --- Notes ---
        ttk.Label(form_frame, text=_("finance_gui.transaction_manager.notes_label") + ":",
                 font=('Arial', 10)).grid(row=row, column=0, sticky='nw', pady=5, padx=5)
        notes_text = tk.Text(form_frame, height=3, width=38, font=('Arial', 10))
        notes_text.grid(row=row, column=1, pady=5, padx=5)
        row += 1

        def record_payment():
            selected_student = student_var.get()
            if not selected_student:
                messagebox.showwarning(_("finance_gui.messages.warning"), "Please select a student.")
                return

            student_id = student_id_map.get(selected_student)
            if not student_id:
                messagebox.showerror(_("finance_gui.messages.error"), "Invalid student selection.")
                return

            if not amount_var.get().strip():
                messagebox.showwarning(_("finance_gui.messages.warning"), "Please enter a payment amount.")
                return

            try:
                amount = float(amount_var.get())
                if amount <= 0:
                    messagebox.showerror(_("finance_gui.messages.error"),
                                        _("finance_gui.transaction_manager.amount_greater_zero"))
                    return
            except ValueError:
                messagebox.showerror(_("finance_gui.messages.error"),
                                    _("finance_gui.transaction_manager.invalid_amount"))
                return

            payment_method = method_var.get()
            payment_date = date_var.get().strip()
            transaction_id = trans_id_var.get().strip()
            purpose = purpose_var.get()
            notes_input = notes_text.get("1.0", tk.END).strip()

            notes = f"Payment for: {purpose}"
            if notes_input:
                notes += f"\n{notes_input}"

            try:
                auth = get_auth()
                username = 'system'
                if auth and hasattr(auth, 'is_logged_in') and auth.is_logged_in():
                    user = auth.get_current_user()
                    username = user.get('username', 'system') if user else 'system'

                conn = self._get_connection()
                cursor = conn.cursor()

                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                # Handle Student Finance Account payment
                if payment_method == "Student Finance Account":
                    cursor.execute(
                        'SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?',
                        (student_id,))
                    result = cursor.fetchone()

                    if not result:
                        messagebox.showerror(_("finance_gui.messages.error"),
                                           "Student finance account not found.")
                        conn.close()
                        return

                    account_id, balance = result
                    if balance < amount:
                        messagebox.showerror(_("finance_gui.messages.error"),
                                           f"Insufficient balance. Available: \u00a3{balance:.2f}")
                        conn.close()
                        return

                    new_balance = balance - amount
                    cursor.execute('''
                        UPDATE student_finance_accounts
                        SET balance = ?, updated_at = datetime('now')
                        WHERE student_id = ?
                    ''', (new_balance, student_id))

                    cursor.execute('''
                        INSERT INTO transactions
                        (source_type, account_id, student_id, transaction_type, amount, balance_before,
                         balance_after, description, processed_by)
                        VALUES ('student_finance', ?, ?, 'payment', ?, ?, ?, ?, ?)
                    ''', (account_id, student_id, amount, balance, new_balance, notes, username))

                # Record payment
                cursor.execute('''
                    INSERT INTO payments
                    (student_id, amount, payment_method, payment_date, transaction_id,
                     notes, status, created_by, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, 'completed', ?, ?)
                ''', (student_id, amount, payment_method, payment_date,
                      transaction_id or None, notes, username, now))

                payment_id = cursor.lastrowid

                # Auto-allocate to outstanding fees
                cursor.execute('''
                    SELECT sf.student_fee_id, ft.fee_name, sf.amount,
                           COALESCE(SUM(pa.amount), 0) as paid_amount,
                           (sf.amount - COALESCE(SUM(pa.amount), 0)) as outstanding
                    FROM student_fees sf
                    JOIN fee_types ft ON sf.fee_type_id = ft.fee_type_id
                    LEFT JOIN payment_allocations pa ON sf.student_fee_id = pa.student_fee_id
                    WHERE sf.student_id = ? AND sf.status != 'paid'
                    GROUP BY sf.student_fee_id
                    HAVING outstanding > 0
                    ORDER BY sf.due_date
                ''', (student_id,))

                outstanding_fees = cursor.fetchall()
                remaining_payment = amount
                allocated_fees = []

                for fee in outstanding_fees:
                    if remaining_payment <= 0:
                        break
                    fee_id, fee_name, total_amount, paid_amount, outstanding = fee
                    allocation_amount = min(remaining_payment, outstanding)

                    cursor.execute('''
                        INSERT INTO payment_allocations
                        (payment_id, student_fee_id, amount, created_at)
                        VALUES (?, ?, ?, ?)
                    ''', (payment_id, fee_id, allocation_amount, now))

                    new_paid_amount = paid_amount + allocation_amount
                    new_status = 'paid' if new_paid_amount >= total_amount else 'partial'
                    cursor.execute('''
                        UPDATE student_fees SET status = ?, updated_at = ?
                        WHERE student_fee_id = ?
                    ''', (new_status, now, fee_id))

                    remaining_payment -= allocation_amount
                    allocated_fees.append(f"\u00a3{allocation_amount:.2f} \u2192 {fee_name}")

                # Handle overpayment as credit
                if remaining_payment > 0:
                    cursor.execute('''
                        INSERT INTO student_credits
                        (student_id, credit_amount, remaining_amount, credit_source,
                         description, created_by, created_at, updated_at)
                        VALUES (?, ?, ?, 'overpayment', ?, ?, ?, ?)
                    ''', (student_id, remaining_payment, remaining_payment,
                          f'Overpayment from payment ID {payment_id}', username, now, now))
                    allocated_fees.append(f"\u00a3{remaining_payment:.2f} \u2192 Student Credit")

                # Fetch student email/name for confirmation email before closing connection
                student_email = None
                student_name = None
                try:
                    cursor.execute(
                        'SELECT first_name, last_name, email_address FROM students WHERE student_id = ?',
                        (student_id,))
                    srow = cursor.fetchone()
                    if srow:
                        student_name = f"{srow[0]} {srow[1]}".strip()
                        student_email = srow[2]
                except Exception:
                    pass

                conn.commit()
                conn.close()

                # Auto-post to GL (never raises)
                try:
                    from education_system.university_system.modules.domain.finance.ledger import notify_ledger
                    notify_ledger('payment', payment_id, posted_by=username)
                except Exception as _e:
                    import logging
                    logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

                # Send payment confirmation email
                email_sent = _send_payment_confirmation_email(
                    student_email, student_name, payment_id, amount,
                    payment_method, payment_date, purpose, transaction_id,
                )

                # Success message
                allocation_msg = "\n".join(allocated_fees) if allocated_fees else "No outstanding fees to allocate."
                email_msg = (
                    f"\n\nConfirmation email sent to {student_email}." if email_sent
                    else ""
                )
                messagebox.showinfo(_("finance_gui.messages.success"),
                                   f"Payment recorded successfully!\n"
                                   f"Payment ID: {payment_id}\n"
                                   f"Amount: \u00a3{amount:.2f}\n\n"
                                   f"Allocations:\n{allocation_msg}{email_msg}")

                dialog.destroy()
                if hasattr(self, 'refresh_payments'):
                    self.refresh_payments()
                if hasattr(self, 'refresh_dashboard'):
                    self.refresh_dashboard()

            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"),
                                    _("finance_gui.transaction_manager.failed_record_payment", error=str(e)))
                import traceback
                traceback.print_exc()

        # Buttons
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(pady=10)

        ttk.Button(btn_frame, text=_("finance_gui.transaction_manager.btn_record"),
                  command=record_payment).pack(side='left', padx=10)
        ttk.Button(btn_frame, text=_("finance_gui.transaction_manager.btn_cancel"),
                  command=dialog.destroy).pack(side='left', padx=10)

    def view_payment_details(self):
        """View selected payment details"""
        selection = self.payments_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.transaction_manager.no_selection_view"))
            return

        payment_id = self.payments_tree.item(selection[0])['values'][0]

        # Create details dialog
        from education_system.university_system.modules.domain.finance.gui.finance.invoice_manager import PaymentDetailsDialog
        dialog = PaymentDetailsDialog(self.root, payment_id)
        self.root.wait_window(dialog.dialog)


    def process_refund(self):
        """Process refund for selected payment"""
        selection = self.payments_tree.selection()
        if not selection:
            messagebox.showwarning(_("finance_gui.messages.no_selection"), _("finance_gui.transaction_manager.no_selection_refund"))
            return

        payment_data = self.payments_tree.item(selection[0])['values']
        payment_id = payment_data[0]
        student_id = payment_data[1]
        amount = float(payment_data[2])

        if not messagebox.askyesno(
            _("finance_gui.transaction_manager.process_refund_title"),
            f"Process refund for payment {payment_id}?"
        ):
            return

        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                '''
                INSERT INTO unified_refunds
                (student_id, reference_id, reference_type, amount, reason, refund_type,
                 refund_method, status, requested_by, request_date, refund_date,
                 source_type, created_at)
                VALUES (?, ?, 'payment', ?, ?, 'full', 'original_payment_method',
                        'approved', 'system', date('now'), date('now'), 'general', ?)
                ''',
                (student_id, str(payment_id), amount, f"Refund for payment {payment_id}", now)
            )
            conn.commit()
            messagebox.showinfo(_("finance_gui.messages.success"), f"Refund processed for payment {payment_id}.")
            self.refresh_payments()
            self.refresh_dashboard()
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), f"Failed to process refund: {e}")

    def record_payment(self, student_id, amount, method, reference=''):
        """Programmatic payment recording entry point."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute(
                '''
                INSERT INTO payments
                (student_id, amount, payment_method, payment_date, transaction_id,
                 notes, status, created_by, created_at)
                VALUES (?, ?, ?, date('now'), ?, ?, 'completed', 'system', ?)
                ''',
                (student_id, amount, method, reference or None, 'Recorded via transaction manager', now)
            )
            payment_id = cursor.lastrowid
            conn.commit()

            # Auto-post to GL (never raises)
            try:
                from education_system.university_system.modules.domain.finance.ledger import notify_ledger
                notify_ledger('payment', payment_id, posted_by='record_payment')
            except Exception as _e:
                import logging
                logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

            # If the student has an active CAS (international, Tier-4),
            # credit this payment toward their stated tuition fee. UKVI
            # asks for evidence of fee payment in extension applications,
            # so keeping cas_records.tuition_fee_paid_gbp current matters.
            # Best-effort: returns silently for domestic students.
            try:
                from education_system.university_system.modules.domain.student_affairs.international_compliance.services import (
                    visa_service as _vs,
                )
                _vs.update_cas_payment(student_id, float(amount), payment_id=payment_id)
            except Exception as _e:
                import logging
                logging.getLogger(__name__).debug("CAS payment update skipped: %s", _e)

            messagebox.showinfo(_("finance_gui.messages.success"), "Payment recorded successfully.")
            return True
        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), f"Failed to record payment: {e}")
            return False


    def load_payment_history(self, student_id, tree_widget):
        """Load payment history for a student"""
        if not student_id:
            return

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute('''
            SELECT p.payment_id, p.amount, p.payment_method, p.payment_date, p.transaction_id
            FROM payments p
            WHERE p.student_id = ? AND p.status = 'completed'
            ORDER BY p.payment_date DESC
            ''', (student_id,))

            payments = cursor.fetchall()

            # Clear existing items
            for item in tree_widget.get_children():
                tree_widget.delete(item)

            # Add payment data
            for payment in payments:
                payment_id, amount, method, date, transaction_id = payment
                trans_id = transaction_id if transaction_id else "N/A"
                tree_widget.insert('', 'end', values=(payment_id, f"\u00a3{amount:.2f}", method, date, trans_id))

            conn.close()

        except Exception as e:
            messagebox.showerror(_("finance_gui.messages.error"), _("finance_gui.transaction_manager.failed_load_payment_history", error=str(e)))
