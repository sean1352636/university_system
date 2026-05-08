"""Refund processing GUI"""

from education_system.university_system.modules.domain.finance.gui.finance.transaction_manager._imports import (
    tk, ttk, messagebox, _, datetime, get_connection, get_auth,
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


REFUND_STATUSES = ["pending", "approved", "rejected", "processed", "cancelled"]
REFUND_EMAIL_TEMPLATES = {
    'created': 'finance/refund_created',
    'status_update': 'finance/refund_status_update',
}


def _lookup_student(student_id):
    """Return (full_name, email) for a student_id, or (None, None) on failure."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT first_name, last_name, email_address FROM students WHERE student_id = ?',
            (student_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return f"{row[0]} {row[1]}".strip(), row[2]
    except Exception as e:
        print(f"Refund email: failed to look up student {student_id}: {e}")
    return None, None


def _send_refund_email(*, kind, student_id, refund_id, amount, refund_type='',
                      refund_method='', status='pending', reason='',
                      request_date=''):
    """Send a refund-related email. kind = 'created' or 'status_update'.

    Templates and operational flags both live in
    ``templates/email/finance/refund_{kind}.json``. Disabling status-update
    emails is done by setting ``enabled: false`` on
    ``refund_status_update.json``.
    """
    try:
        template_name = REFUND_EMAIL_TEMPLATES.get(kind)
        if not template_name:
            return False
        template_data = load_template(template_name)
        if not template_data or not template_data.get('enabled', True):
            return False

        student_name, student_email = _lookup_student(student_id)
        if not student_email:
            return False

        fmt = {
            'student_name': student_name or 'Student',
            'refund_id': refund_id,
            'amount': f"{float(amount or 0):,.2f}",
            'refund_type': refund_type or '',
            'refund_method': refund_method or '',
            'status': status or '',
            'status_label': (status or '').capitalize(),
            'reason': reason or '',
            'request_date': request_date or datetime.now().strftime('%Y-%m-%d'),
        }
        subject, body = render_template(template_name, fmt)
        if not subject or not body:
            return False
        cc = None
        if template_data.get('send_copy_to_finance') and template_data.get('finance_email'):
            cc = [template_data['finance_email']]
        return bool(_send_email(student_email, subject, body, cc=cc))
    except Exception as e:
        print(f"Failed to send refund email: {e}")
        return False


class RefundsMixin:
    """Mixin for refund processing"""

    def _load_refund_students(self):
        """Return (display_list, id_map) of all students for the dropdown."""
        students = []
        id_map = {}
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                'SELECT student_id, first_name, last_name FROM students '
                'ORDER BY last_name, first_name'
            )
            for sid, first, last in cursor.fetchall():
                display = f"{sid} - {first} {last}"
                students.append(display)
                id_map[display] = sid
            conn.close()
        except Exception as e:
            print(f"Error loading students for refund dialog: {e}")
        return students, id_map

    def gui_process_refund(self):
        """GUI wrapper for process_refund"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_("finance_gui.transaction_manager.process_refund_title"))
        dialog.geometry("980x780")
        dialog.minsize(900, 700)
        dialog.transient(self.root)
        dialog.grab_set()

        # Scrollable container — bind the inner window to the canvas width so
        # there is no large empty gap on the right.
        main_container = tk.Frame(dialog)
        main_container.pack(fill='both', expand=True)

        canvas = tk.Canvas(main_container, bg='white', highlightthickness=0)
        scrollbar = ttk.Scrollbar(main_container, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg='white')

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        def _resize_inner(event):
            canvas.itemconfigure(window_id, width=event.width)
        canvas.bind('<Configure>', _resize_inner)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        # ----- Student selection (dropdown) -----
        student_frame = ttk.LabelFrame(
            scrollable_frame,
            text=_("finance_gui.transaction_manager.student_info_frame"),
            padding=15,
        )
        student_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(student_frame, text=_("finance_gui.transaction_manager.student_id_label"),
                 font=('Arial', 12)).pack(anchor='w')

        students, student_id_map = self._load_refund_students()
        student_var = tk.StringVar()
        student_combo = ttk.Combobox(
            student_frame, textvariable=student_var, values=students,
            state='readonly', font=('Arial', 12), width=50,
        )
        student_combo.pack(anchor='w', pady=5, fill='x')

        def _selected_student_id():
            return student_id_map.get(student_var.get(), '')

        ttk.Button(
            student_frame,
            text=_("finance_gui.transaction_manager.load_payment_history"),
            command=lambda: self.load_payment_history(_selected_student_id(), payments_tree),
        ).pack(anchor='w', pady=5)

        # ----- Payment history -----
        history_frame = ttk.LabelFrame(
            scrollable_frame,
            text=_("finance_gui.transaction_manager.payment_history_frame"),
            padding=15,
        )
        history_frame.pack(fill='both', expand=True, padx=20, pady=10)

        columns = ('Payment ID', 'Amount', 'Method', 'Date', 'Transaction ID')
        payments_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=8)
        for col in columns:
            payments_tree.heading(col, text=col)
            payments_tree.column(col, width=140, anchor='center')
        payments_tree.pack(fill='both', expand=True)

        # ----- Refund details -----
        refund_frame = ttk.LabelFrame(
            scrollable_frame,
            text=_("finance_gui.transaction_manager.refund_details_frame"),
            padding=15,
        )
        refund_frame.pack(fill='x', padx=20, pady=10)

        ttk.Label(refund_frame, text=_("finance_gui.transaction_manager.refund_type_label"),
                 font=('Arial', 12)).pack(anchor='w')
        refund_type_var = tk.StringVar(value="partial")
        refund_type_combo = ttk.Combobox(
            refund_frame, textvariable=refund_type_var,
            values=["full", "partial", "withdrawal", "overpayment"],
            state='readonly', font=('Arial', 12),
        )
        refund_type_combo.pack(anchor='w', pady=5)

        ttk.Label(refund_frame, text=_("finance_gui.transaction_manager.refund_amount_label"),
                 font=('Arial', 12)).pack(anchor='w')
        refund_amount_var = tk.StringVar()
        refund_amount_entry = ttk.Entry(refund_frame, textvariable=refund_amount_var,
                                       font=('Arial', 12), width=15)
        refund_amount_entry.pack(anchor='w', pady=5)

        def _selected_payment_amount():
            sel = payments_tree.selection()
            if not sel:
                return None
            try:
                return float(str(payments_tree.item(sel[0])['values'][1]).replace('£', ''))
            except (ValueError, IndexError):
                return None

        def _on_refund_type_change(*_a):
            if refund_type_var.get() == 'full':
                amt = _selected_payment_amount()
                if amt is not None:
                    refund_amount_var.set(f"{amt:.2f}")
                else:
                    messagebox.showinfo(
                        _("finance_gui.messages.info") if False else "Select payment",
                        "Select a payment from the history to use its amount as the full refund.",
                    )

        refund_type_combo.bind('<<ComboboxSelected>>', _on_refund_type_change)
        # When the user picks a different payment row, refresh full-refund amount.
        payments_tree.bind(
            '<<TreeviewSelect>>',
            lambda e: _on_refund_type_change() if refund_type_var.get() == 'full' else None,
        )

        ttk.Label(refund_frame, text=_("finance_gui.transaction_manager.refund_reason_label"),
                 font=('Arial', 12)).pack(anchor='w')
        reason_text = tk.Text(refund_frame, height=3, font=('Arial', 10))
        reason_text.pack(anchor='w', pady=5, fill='x')

        ttk.Label(refund_frame, text=_("finance_gui.transaction_manager.refund_method_label"),
                 font=('Arial', 12)).pack(anchor='w')
        refund_method_var = tk.StringVar(value="bank_transfer")
        ttk.Combobox(
            refund_frame, textvariable=refund_method_var,
            values=["bank_transfer", "original_payment_method", "check", "cash"],
            state='readonly', font=('Arial', 12),
        ).pack(anchor='w', pady=5)

        # ----- Existing refunds + status update -----
        manage_frame = ttk.LabelFrame(
            scrollable_frame, text="Existing Refunds — Update Status", padding=15,
        )
        manage_frame.pack(fill='both', expand=True, padx=20, pady=10)

        ref_columns = ('ID', 'Student', 'Amount', 'Type', 'Method', 'Status', 'Date')
        refunds_tree = ttk.Treeview(manage_frame, columns=ref_columns, show='headings', height=7)
        for col in ref_columns:
            refunds_tree.heading(col, text=col)
            refunds_tree.column(col, width=110, anchor='center')
        refunds_tree.pack(fill='both', expand=True)

        def load_existing_refunds(student_id=None):
            for item in refunds_tree.get_children():
                refunds_tree.delete(item)
            try:
                conn = get_connection()
                cursor = conn.cursor()
                if student_id:
                    cursor.execute(
                        '''SELECT refund_id, student_id, amount, refund_type, refund_method,
                                  status, COALESCE(refund_date, request_date)
                           FROM unified_refunds WHERE student_id = ?
                           ORDER BY refund_id DESC''', (student_id,))
                else:
                    cursor.execute(
                        '''SELECT refund_id, student_id, amount, refund_type, refund_method,
                                  status, COALESCE(refund_date, request_date)
                           FROM unified_refunds ORDER BY refund_id DESC LIMIT 100''')
                for rid, sid, amt, rtype, rmethod, status, date in cursor.fetchall():
                    refunds_tree.insert(
                        '', 'end',
                        values=(rid, sid, f"£{float(amt or 0):.2f}",
                                rtype or '', rmethod or '', status or '', date or ''),
                    )
                conn.close()
            except Exception as e:
                print(f"Error loading refunds: {e}")

        # Refresh existing refunds when student dropdown changes
        student_combo.bind(
            '<<ComboboxSelected>>',
            lambda e: load_existing_refunds(_selected_student_id()),
        )

        status_row = ttk.Frame(manage_frame)
        status_row.pack(fill='x', pady=8)

        ttk.Label(status_row, text="New status:", font=('Arial', 11)).pack(side='left', padx=5)
        new_status_var = tk.StringVar(value="approved")
        ttk.Combobox(
            status_row, textvariable=new_status_var, values=REFUND_STATUSES,
            state='readonly', width=15,
        ).pack(side='left', padx=5)

        def update_refund_status():
            selection = refunds_tree.selection()
            if not selection:
                messagebox.showwarning(
                    _("finance_gui.messages.warning"),
                    "Select a refund row to update its status.",
                )
                return
            row = refunds_tree.item(selection[0])['values']
            refund_id = row[0]
            new_status = new_status_var.get()

            auth = get_auth()
            username = 'system'
            if auth and hasattr(auth, 'is_logged_in') and auth.is_logged_in():
                user = auth.get_current_user() or {}
                username = user.get('username', 'system')

            try:
                conn = get_connection()
                cursor = conn.cursor()
                today = datetime.now().strftime('%Y-%m-%d')
                if new_status == 'approved':
                    cursor.execute(
                        '''UPDATE unified_refunds
                           SET status = ?, approved_by = ?, approval_date = ?
                           WHERE refund_id = ?''',
                        (new_status, username, today, refund_id),
                    )
                elif new_status in ('processed', 'completed'):
                    cursor.execute(
                        '''UPDATE unified_refunds
                           SET status = ?, processed_by = ?, refund_date = ?
                           WHERE refund_id = ?''',
                        (new_status, username, today, refund_id),
                    )
                else:
                    cursor.execute(
                        'UPDATE unified_refunds SET status = ? WHERE refund_id = ?',
                        (new_status, refund_id),
                    )
                # Look up refund details we need for the email before closing
                cursor.execute(
                    'SELECT student_id, amount FROM unified_refunds WHERE refund_id = ?',
                    (refund_id,),
                )
                refund_row = cursor.fetchone()
                conn.commit()
                conn.close()

                email_sent = False
                if refund_row:
                    sid, amt = refund_row
                    email_sent = _send_refund_email(
                        kind='status_update', student_id=sid, refund_id=refund_id,
                        amount=amt, status=new_status,
                    )

                msg = f"Refund {refund_id} status updated to {new_status}."
                if email_sent:
                    msg += "\nNotification email sent to the student."
                messagebox.showinfo(_("finance_gui.messages.success"), msg)
                load_existing_refunds(_selected_student_id())
            except Exception as e:
                messagebox.showerror(_("finance_gui.messages.error"),
                                    f"Failed to update status: {e}")

        ttk.Button(status_row, text="Update Status",
                  command=update_refund_status).pack(side='left', padx=10)
        ttk.Button(status_row, text="Refresh",
                  command=lambda: load_existing_refunds(_selected_student_id())
                  ).pack(side='left', padx=5)

        load_existing_refunds()

        # ----- Process new refund -----
        is_processing = {'busy': False}

        def process_refund():
            if is_processing['busy']:
                return
            is_processing['busy'] = True
            try:
                process_btn.config(state='disabled')
            except Exception:
                pass

            def _release():
                is_processing['busy'] = False
                try:
                    process_btn.config(state='normal')
                except Exception:
                    pass

            try:
                student_id = _selected_student_id()
                if not student_id:
                    messagebox.showerror(_("finance_gui.messages.error"),
                                        "Please select a student.")
                    _release()
                    return

                amount_str = (refund_amount_var.get() or "").strip()
                if not amount_str:
                    messagebox.showwarning(
                        _("finance_gui.messages.warning"),
                        "Please enter a refund amount.",
                    )
                    _release()
                    return
                try:
                    refund_amount = float(amount_str)
                except ValueError:
                    messagebox.showerror(
                        _("finance_gui.messages.error"),
                        _("finance_gui.transaction_manager.invalid_refund_amount"),
                    )
                    _release()
                    return
                if refund_amount <= 0:
                    messagebox.showerror(
                        _("finance_gui.messages.error"),
                        "Refund amount must be greater than zero.",
                    )
                    _release()
                    return

                refund_type = refund_type_var.get()
                refund_method = refund_method_var.get()
                reason = reason_text.get("1.0", tk.END).strip()

                if not all([refund_type, refund_method, reason]):
                    messagebox.showerror(
                        _("finance_gui.messages.error"),
                        _("finance_gui.transaction_manager.all_fields_required"),
                    )
                    _release()
                    return

                auth = get_auth()
                username = 'system'
                has_approve_permission = False
                if auth and hasattr(auth, 'is_logged_in') and auth.is_logged_in():
                    user = auth.get_current_user() or {}
                    username = user.get('username', 'system')
                    has_approve_permission = (
                        auth.has_permission('approve_refunds')
                        if hasattr(auth, 'has_permission') else False
                    )

                selected_item = payments_tree.selection()
                original_payment_id = None
                if selected_item:
                    payment_data = payments_tree.item(selected_item[0])['values']
                    original_payment_id = payment_data[0]
                    original_amount = float(str(payment_data[1]).replace('£', ''))
                    if refund_amount > original_amount:
                        messagebox.showerror(
                            _("finance_gui.messages.error"),
                            _("finance_gui.transaction_manager.refund_exceeds_original",
                              amount=original_amount),
                        )
                        _release()
                        return

                conn = get_connection()
                cursor = conn.cursor()
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                request_date = datetime.now().strftime('%Y-%m-%d')

                cursor.execute(
                    '''INSERT INTO unified_refunds
                       (student_id, reference_id, reference_type, amount, reason, refund_type,
                        refund_method, status, requested_by, request_date, refund_date,
                        source_type, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (student_id,
                     str(original_payment_id) if original_payment_id else None,
                     'payment' if original_payment_id else None,
                     refund_amount, reason, refund_type, refund_method,
                     'pending', username, request_date, request_date,
                     'general', now),
                )
                refund_id = cursor.lastrowid

                if has_approve_permission:
                    cursor.execute(
                        '''UPDATE unified_refunds
                           SET status = 'approved', approved_by = ?, approval_date = ?
                           WHERE refund_id = ?''',
                        (username, request_date, refund_id),
                    )
                    status_msg = _("finance_gui.transaction_manager.refund_approved")
                else:
                    status_msg = _("finance_gui.transaction_manager.refund_pending_approval")

                conn.commit()
                conn.close()

                final_status = 'approved' if has_approve_permission else 'pending'
                email_sent = _send_refund_email(
                    kind='created', student_id=student_id, refund_id=refund_id,
                    amount=refund_amount, refund_type=refund_type,
                    refund_method=refund_method, status=final_status,
                    reason=reason, request_date=request_date,
                )

                email_msg = "\nNotification email sent to the student." if email_sent else ""
                messagebox.showinfo(
                    _("finance_gui.messages.success"),
                    _("finance_gui.transaction_manager.refund_success") + "\n"
                    + _("finance_gui.transaction_manager.refund_id_label") + f" {refund_id}\n"
                    + _("finance_gui.transaction_manager.amount_label_display")
                    + f" £{refund_amount:.2f}\n"
                    + _("finance_gui.transaction_manager.status_label") + f" {status_msg}"
                    + email_msg,
                )

                load_existing_refunds(student_id)
                try:
                    self.update_status(f"Refund request created for £{refund_amount:.2f}")
                except Exception:
                    pass
                # Successful submission — clear the form and keep button disabled
                # to prevent accidental duplicate submissions. User can submit
                # another refund after re-selecting/filling the form.
                refund_amount_var.set("")
                reason_text.delete("1.0", tk.END)
                # Re-enable so a *new* refund can be entered for a different payment.
                _release()

            except ValueError:
                messagebox.showerror(
                    _("finance_gui.messages.error"),
                    _("finance_gui.transaction_manager.invalid_refund_amount"),
                )
                _release()
            except Exception as e:
                messagebox.showerror(
                    _("finance_gui.messages.error"),
                    _("finance_gui.transaction_manager.failed_process_refund", error=str(e)),
                )
                _release()

        button_frame = ttk.Frame(scrollable_frame)
        button_frame.pack(pady=15)

        process_btn = ttk.Button(
            button_frame,
            text=_("finance_gui.transaction_manager.btn_process_refund"),
            command=process_refund,
        )
        process_btn.pack(side='left', padx=10)
        ttk.Button(button_frame,
                  text=_("finance_gui.transaction_manager.btn_cancel"),
                  command=dialog.destroy).pack(side='left', padx=10)
