"""Methods process_payment_dialog through process_refund_dialog."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import finance_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class LibraryFinanceManager:
    def process_payment_dialog(self):
        """Dialog to process a fine payment"""
        selection = self.fines_tree.selection()
        if not selection:
            messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.no_selection', default="No Selection"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.please_select_a_fine_to_process_payment', default="Please select a fine to process payment."))
            return

        values = self.fines_tree.item(selection[0])['values']
        loan_id = values[0]
        user_id = values[1]
        fine_amount = float(str(values[6]).replace('£', ''))

        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.windows.process_fine_payment', default="Process Fine Payment"))
        dialog.geometry("400x300")
        dialog.transient(self.root)

        tk.Label(dialog, text=f"Loan ID: {loan_id}", font=('Arial', 10, 'bold')).pack(pady=5)
        tk.Label(dialog, text=f"User ID: {user_id}", font=('Arial', 10)).pack(pady=5)
        tk.Label(dialog, text=f"Fine Amount: £{fine_amount:.2f}", font=('Arial', 10, 'bold')).pack(pady=5)

        tk.Label(dialog, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.labels.payment_amount', default="Payment Amount (£):"), font=('Arial', 10)).pack(pady=5)
        payment_var = tk.StringVar(value=str(fine_amount))
        ttk.Entry(dialog, textvariable=payment_var, width=30).pack(pady=5)

        tk.Label(dialog, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.labels.payment_method', default="Payment Method:"), font=('Arial', 10)).pack(pady=5)
        method_var = tk.StringVar(value=_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.values.cash', default="Cash"))
        payment_methods = ["Cash", "Card", "Bank Transfer", "Online"]
        if FINANCE_ACCOUNT_AVAILABLE:
            payment_methods.append("Finance Account")
        ttk.Combobox(dialog, textvariable=method_var, values=payment_methods,
                     state='readonly', width=28).pack(pady=5)

        # Show finance account balance if available
        if FINANCE_ACCOUNT_AVAILABLE:
            balance = get_student_finance_account_balance(user_id)
            if balance is not None:
                tk.Label(dialog, text=f"💰 Finance Account Balance: £{balance:.2f}",
                        font=('Arial', 9), fg='green').pack(pady=2)
            else:
                tk.Label(dialog, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.labels.finance_account_not_created', default="💰 Finance Account: Not created"),
                        font=('Arial', 9), fg='gray').pack(pady=2)

        def process():
            payment_str = payment_var.get().strip()
            if not payment_str:
                messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.input_required', default="Input Required"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.please_enter_payment_amount', default="Please enter payment amount."), parent=dialog)
                return
            try:
                payment_amount = float(payment_str)
                if payment_amount <= 0:
                    messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.invalid_amount', default="Invalid Amount"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.payment_must_be_greater_than_0', default="Payment must be greater than 0."), parent=dialog)
                    return
                if payment_amount > fine_amount:
                    messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.overpayment', default="Overpayment"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.payment_exceeds_fine_amount', default="Payment exceeds fine amount."), parent=dialog)
                    return

                payment_method = method_var.get()

                # Handle Finance Account payment
                if payment_method == "Finance Account":
                    if not FINANCE_ACCOUNT_AVAILABLE:
                        messagebox.showerror(_("common.error"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.finance_account_not_available', default="Finance account not available"), parent=dialog)
                        return

                    current_balance = get_student_finance_account_balance(user_id)
                    if current_balance is None:
                        create = messagebox.askyesno(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.no_account', default="No Account"),
                            f"No finance account for {user_id}.\nCreate one now?", parent=dialog)
                        if create:
                            if ensure_student_finance_account_exists(user_id):
                                messagebox.showinfo(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.created', default="Created"),
                                    _t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.account_created_with_0_00_balance_please_top_up_first', default="Account created with £0.00 balance.\nPlease top up first."), parent=dialog)
                            else:
                                messagebox.showerror(_("common.error"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.failed_to_create_account', default="Failed to create account"), parent=dialog)
                        return

                    if current_balance < payment_amount:
                        shortfall = payment_amount - current_balance
                        topup = messagebox.askyesno(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.insufficient_balance', default="Insufficient Balance"),
                            f"Balance: £{current_balance:.2f}\nRequired: £{payment_amount:.2f}\n"
                            f"Shortfall: £{shortfall:.2f}\n\nTop up now?", parent=dialog)
                        if topup:
                            topup_amt = simpledialog.askfloat(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.top_up', default="Top Up"),
                                f"Enter top-up amount (min £{shortfall:.2f}):",
                                minvalue=shortfall, initialvalue=shortfall, parent=dialog)
                            if topup_amt:
                                result = top_up_student_finance_account(
                                    student_id=user_id,
                                    amount=topup_amt,
                                    description="Top-up for library fine",
                                    payment_method="Cash/Card",
                                    processed_by=get_current_user_id()
                                )
                                if not result['success']:
                                    messagebox.showerror(_("common.error"), f"Top-up failed: {result.get('message')}", parent=dialog)
                                    return
                                current_balance = result.get('new_balance', current_balance + topup_amt)
                            else:
                                return
                        else:
                            return

                    # Process finance account payment
                    payment_result = process_student_finance_account_payment(
                        student_id=user_id,
                        amount=payment_amount,
                        description=f"Library fine payment (Loan {loan_id})",
                        transaction_source="Library",
                        transaction_ref=f"FINE_{loan_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                        processed_by=get_current_user_id(),
                        check_balance=True
                    )

                    if not payment_result['success']:
                        messagebox.showerror(_("common.error"), f"Payment failed: {payment_result.get('message')}", parent=dialog)
                        return

                    new_balance = payment_result.get('new_balance', 0)

                from education_system.systems.university.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()
                current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                new_fine = round(fine_amount - payment_amount, 2)
                if new_fine < 0.01:
                    new_fine = 0.0

                cursor.execute('UPDATE book_loans SET fine_amount = ? WHERE loan_id = ?', (new_fine, loan_id))
                cursor.execute('''
                    INSERT INTO payments (student_id, amount, currency, payment_method, payment_date, status, notes, created_at)
                    VALUES (?, ?, 'GBP', ?, DATE('now'), 'completed', 'Library fine payment - Loan ID: ' || ?, ?)
                ''', (user_id, payment_amount, payment_method, loan_id, current_datetime))

                payment_id = cursor.lastrowid

                cursor.execute('''
                    SELECT b.title FROM book_loans bl JOIN books b ON bl.book_id = b.book_id WHERE bl.loan_id = ?
                ''', (loan_id,))
                book_result = cursor.fetchone()
                book_title = book_result[0] if book_result else "Unknown Book"

                conn.commit()
                conn.close()

                # Auto-post to GL (never raises)
                try:
                    from education_system.systems.university.domains.finance.domain.ledger import notify_ledger
                    notify_ledger('payment', payment_id, posted_by='library_fine')
                except Exception as _e:
                    import logging
                    logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

                user_info = self.get_user_email(user_id)
                if user_info:
                    self.send_payment_receipt_email(user_info, fine_amount, payment_amount, payment_method,
                                                     book_title, f"LIB-{payment_id}", current_datetime)

                if payment_method == "Finance Account":
                    messagebox.showinfo(_("common.success"),
                        f"Payment of £{payment_amount:.2f} processed from Finance Account.\n"
                        f"Remaining fine: £{new_fine:.2f}\nNew balance: £{new_balance:.2f}",
                        parent=dialog)
                else:
                    messagebox.showinfo(_("common.success"),
                        f"Payment of £{payment_amount:.2f} processed successfully.\nRemaining fine: £{new_fine:.2f}",
                        parent=dialog)
                dialog.destroy()
                self.load_all_fines()

            except ValueError:
                messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.invalid_input', default="Invalid Input"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.please_enter_a_valid_amount_variant_2', default="Please enter a valid amount."), parent=dialog)
            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to process payment:\n{str(e)}", parent=dialog)

        tk.Button(dialog, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.buttons.process_payment', default="Process Payment"), command=process, bg=self.colors['success'], fg='white',
                  font=('Arial', 10, 'bold'), padx=20, pady=8).pack(pady=20)

    def process_refund_dialog(self):
        """Dialog to process a library fine refund"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.windows.process_library_fine_refund', default="Process Library Fine Refund"))
        dialog.geometry("700x750")
        dialog.transient(self.root)

        tk.Label(dialog, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.labels.process_library_fine_refund', default="Process Library Fine Refund"), font=('Arial', 14, 'bold')).pack(pady=10)

        # Student search
        search_frame = ttk.LabelFrame(dialog, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.labels.find_student', default="Find Student"), padding=10)
        search_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(search_frame, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.labels.student_id', default="Student ID:"), font=('Arial', 10)).grid(row=0, column=0, padx=5, pady=5, sticky='w')
        student_id_var = tk.StringVar()
        ttk.Entry(search_frame, textvariable=student_id_var, width=20).grid(row=0, column=1, padx=5, pady=5)

        # Paid fines list
        fines_frame = ttk.LabelFrame(dialog, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.labels.paid_fines_select_to_refund', default="Paid Fines (Select to Refund)"), padding=10)
        fines_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns = ('Loan ID', 'Book ID', 'Book Title', 'Payment Date', 'Amount')
        fines_tree = ttk.Treeview(fines_frame, columns=columns, show='headings', height=6)

        for col in columns:
            fines_tree.heading(col, text=col)
        fines_tree.column('Loan ID', width=80, anchor='center')
        fines_tree.column('Book ID', width=100)
        fines_tree.column('Book Title', width=200)
        fines_tree.column('Payment Date', width=120, anchor='center')
        fines_tree.column('Amount', width=100, anchor='e')

        fines_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        def load_paid_fines():
            student_id = student_id_var.get().strip()
            if not student_id:
                messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.input_required', default="Input Required"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.please_enter_a_student_id', default="Please enter a student ID"), parent=dialog)
                return

            for item in fines_tree.get_children():
                fines_tree.delete(item)

            try:
                from education_system.systems.university.infrastructure.database.db import get_connection
                conn = get_connection()
                cursor = conn.cursor()

                # Query the payments table for actual paid library fines
                cursor.execute('''
                    SELECT p.reference_id as loan_id, NULL as book_id, p.notes as book_title,
                           p.payment_date,
                           (p.amount - COALESCE((SELECT SUM(ur.amount) FROM unified_refunds ur
                                                  WHERE ur.source_type = 'library'
                                                  AND ur.reference_id = CAST(p.payment_id AS TEXT)), 0)) as available_amount
                    FROM payments p
                    WHERE p.student_id = ?
                    AND p.source_type = 'library'
                    AND p.status = 'completed'
                    AND (p.amount - COALESCE((SELECT SUM(ur.amount) FROM unified_refunds ur
                                              WHERE ur.source_type = 'library'
                                              AND ur.reference_id = CAST(p.payment_id AS TEXT)), 0)) > 0
                    ORDER BY p.payment_date DESC
                ''', (student_id,))

                paid_fines = cursor.fetchall()
                conn.close()

                for fine in paid_fines:
                    loan_id, book_id, title, payment_date, amount = fine
                    fines_tree.insert('', 'end', values=(
                        loan_id, book_id, title[:40] if title else 'N/A',
                        payment_date if payment_date else 'N/A', f"£{amount:.2f}"
                    ))

                if not paid_fines:
                    messagebox.showinfo(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.no_paid_fines', default="No Paid Fines"), f"No paid fines found for student {student_id}", parent=dialog)
                else:
                    print(f"Loaded {len(paid_fines)} refundable payments for {student_id}")

            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to load paid fines:\n{str(e)}", parent=dialog)

        tk.Button(search_frame, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.buttons.load_paid_fines', default="Load Paid Fines"), command=load_paid_fines,
                  bg=self.colors['secondary'], fg='white', font=('Arial', 10, 'bold')).grid(row=0, column=2, padx=5, pady=5)

        # Refund details
        refund_frame = ttk.LabelFrame(dialog, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.labels.refund_details', default="Refund Details"), padding=10)
        refund_frame.pack(fill=tk.X, padx=10, pady=10)

        tk.Label(refund_frame, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.labels.refund_amount', default="Refund Amount (£):"), font=('Arial', 10)).grid(row=0, column=0, padx=5, pady=5, sticky='w')
        refund_amount_var = tk.StringVar()
        ttk.Entry(refund_frame, textvariable=refund_amount_var, width=15).grid(row=0, column=1, padx=5, pady=5, sticky='w')

        tk.Label(refund_frame, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.labels.refund_method', default="Refund Method:"), font=('Arial', 10)).grid(row=1, column=0, padx=5, pady=5, sticky='w')
        refund_method_var = tk.StringVar(value=_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.values.cash', default="Cash"))
        ttk.Combobox(refund_frame, textvariable=refund_method_var,
                     values=["Cash", "Card", "Student Finance Account"],
                     state='readonly', width=22).grid(row=1, column=1, padx=5, pady=5, sticky='w')

        tk.Label(refund_frame, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.labels.refund_reason', default="Refund Reason:"), font=('Arial', 10)).grid(row=2, column=0, padx=5, pady=5, sticky='nw')
        reason_text = tk.Text(refund_frame, height=3, width=35)
        reason_text.grid(row=2, column=1, padx=5, pady=5)

        def process_refund():
            selection = fines_tree.selection()
            if not selection:
                messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.no_selection', default="No Selection"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.please_select_a_paid_fine_to_refund', default="Please select a paid fine to refund"), parent=dialog)
                return

            student_id = student_id_var.get().strip()
            refund_amount_str = refund_amount_var.get().strip()
            refund_method = refund_method_var.get()
            refund_reason = reason_text.get("1.0", tk.END).strip()

            if not all([student_id, refund_amount_str, refund_method, refund_reason]):
                messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.input_required', default="Input Required"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.please_fill_all_fields', default="Please fill all fields"), parent=dialog)
                return

            try:
                refund_amount = float(refund_amount_str)
                if refund_amount <= 0:
                    messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.invalid_amount', default="Invalid Amount"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.refund_amount_must_be_greater_than_0', default="Refund amount must be greater than 0"), parent=dialog)
                    return

                values = fines_tree.item(selection[0])['values']
                loan_id = values[0]
                book_title = values[2]

                # Process the refund
                success = self._process_library_refund(
                    student_id=student_id,
                    loan_id=loan_id,
                    refund_amount=refund_amount,
                    refund_method=refund_method,
                    refund_reason=refund_reason,
                    book_title=book_title
                )

                if success:
                    messagebox.showinfo(_("common.success"),
                        f"Refund of £{refund_amount:.2f} processed successfully!\n\n"
                        f"Method: {refund_method}\n"
                        f"Student: {student_id}", parent=dialog)
                    dialog.destroy()
                    self.load_all_fines()
                    self.refresh_overview()
                else:
                    messagebox.showerror(_("common.error"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.failed_to_process_refund', default="Failed to process refund"), parent=dialog)

            except ValueError:
                messagebox.showwarning(_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.invalid_input', default="Invalid Input"), _t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.dialogs.please_enter_a_valid_amount', default="Please enter a valid amount"), parent=dialog)
            except Exception as e:
                messagebox.showerror(_("common.error"), f"Failed to process refund:\n{str(e)}", parent=dialog)

        tk.Button(refund_frame, text=_t('gui.academics.library.finance_parts.libraryfinancemanager_process_payment_dialog.buttons.process_refund', default="Process Refund"), command=process_refund,
                  bg=self.colors['success'], fg='white', font=('Arial', 10, 'bold'),
                  padx=20, pady=8).grid(row=3, column=0, columnspan=2, pady=15)
