"""Consultations mixin for the Legal Services GUI."""

from education_system.systems.university.interfaces.gui.governance.legal._imports import (
    tk, ttk, messagebox, scrolledtext, simpledialog, traceback,
    datetime, timedelta,
    ConsultationManager, PaymentManager,
    calculate_service_fee,
    CASE_TYPES, CONSULTATION_STATUSES,
    _t, logger,
    send_email, render_template, EMAIL_AVAILABLE,
    record_payment_to_finance,
    get_student_finance_account_balance,
    process_student_finance_account_payment,
)


class ConsultationsMixin:
    """Consultations tab: schedule, pay, receipt, cancel."""

    def create_consultations_tab(self):
        """Create consultations tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("legal.tabs.consultations", default="Consultations"))

        # Split view
        paned = ttk.PanedWindow(tab, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Left: Consultations list
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=1)

        ttk.Label(
            left_frame,
            text=_t("legal.scheduled_consultations", default="Scheduled Consultations"),
            font=('Arial', 12, 'bold')
        ).pack(pady=5)

        # Filter frame
        filter_frame = ttk.Frame(left_frame)
        filter_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(filter_frame, text=_t("legal.labels.status", default="Status") + ":").pack(side=tk.LEFT, padx=2)
        self.consult_status_filter = ttk.Combobox(
            filter_frame,
            values=[_t("common.all", default="All")] + CONSULTATION_STATUSES,
            state='readonly', width=12
        )
        self.consult_status_filter.set(_t("common.all", default="All"))
        self.consult_status_filter.pack(side=tk.LEFT, padx=2)
        self.consult_status_filter.bind('<<ComboboxSelected>>', lambda e: self.load_consultations())

        ttk.Button(filter_frame, text=_t("common.refresh", default="Refresh"), command=self.load_consultations).pack(side=tk.RIGHT, padx=5)

        # Consultations treeview
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ('id', 'client', 'date', 'time', 'type', 'fee', 'payment', 'status')
        self.consult_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        self.consult_tree.heading('id', text='ID')
        self.consult_tree.heading('client', text=_t("legal.labels.client_name", default="Client"))
        self.consult_tree.heading('date', text=_t("legal.labels.scheduled_date", default="Date"))
        self.consult_tree.heading('time', text=_t("legal.labels.scheduled_time", default="Time"))
        self.consult_tree.heading('type', text=_t("legal.labels.case_type", default="Type"))
        self.consult_tree.heading('fee', text=_t("legal.labels.fee", default="Fee"))
        self.consult_tree.heading('payment', text=_t("legal.labels.payment_status", default="Payment"))
        self.consult_tree.heading('status', text=_t("legal.labels.status", default="Status"))

        self.consult_tree.column('id', width=40)
        self.consult_tree.column('client', width=100)
        self.consult_tree.column('date', width=90)
        self.consult_tree.column('time', width=60)
        self.consult_tree.column('type', width=100)
        self.consult_tree.column('fee', width=70)
        self.consult_tree.column('payment', width=80)
        self.consult_tree.column('status', width=80)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.consult_tree.yview)
        self.consult_tree.configure(yscrollcommand=scrollbar.set)

        self.consult_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.consult_tree.bind('<<TreeviewSelect>>', self.on_consultation_select)

        # Action buttons
        btn_frame = ttk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text=_t("legal.btn.process_payment", default="Process Payment"), command=self.process_consultation_payment).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t("legal.btn.send_receipt", default="Send Receipt"), command=self.send_consultation_receipt).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_frame, text=_t("legal.btn.cancel_consultation", default="Cancel"), command=self.cancel_consultation).pack(side=tk.LEFT, padx=2)

        # Right: Schedule new consultation
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)

        form_frame = ttk.LabelFrame(right_frame, text=_t("legal.btn.schedule_consultation", default="Schedule Consultation"), padding="10")
        form_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Get current user details
        user_name, user_email = self._get_user_details_from_db()
        user_id = self.current_user.get('student_id') or self.current_user.get('username', '')

        # Client Name
        ttk.Label(form_frame, text=_t("legal.labels.client_name", default="Client Name") + " *:").grid(row=0, column=0, sticky=tk.W, pady=3)
        self.consult_client_name = ttk.Entry(form_frame, width=30)
        self.consult_client_name.insert(0, user_name)
        self.consult_client_name.grid(row=0, column=1, pady=3, sticky=tk.EW)

        # Client ID
        ttk.Label(form_frame, text=_t("legal.labels.client_id", default="Client ID") + " *:").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.consult_client_id = ttk.Entry(form_frame, width=30)
        self.consult_client_id.insert(0, user_id)
        self.consult_client_id.grid(row=1, column=1, pady=3, sticky=tk.EW)

        # Client Email
        ttk.Label(form_frame, text=_t("legal.labels.client_email", default="Client Email") + ":").grid(row=2, column=0, sticky=tk.W, pady=3)
        self.consult_client_email = ttk.Entry(form_frame, width=30)
        self.consult_client_email.insert(0, user_email)
        self.consult_client_email.grid(row=2, column=1, pady=3, sticky=tk.EW)

        # Consultation Type
        ttk.Label(form_frame, text=_t("legal.labels.consultation_type", default="Type") + " *:").grid(row=3, column=0, sticky=tk.W, pady=3)
        self.consult_type_combo = ttk.Combobox(form_frame, values=CASE_TYPES, state='readonly', width=28)
        self.consult_type_combo.set('consultation')
        self.consult_type_combo.grid(row=3, column=1, pady=3, sticky=tk.EW)
        self.consult_type_combo.bind('<<ComboboxSelected>>', self.update_fee_display)

        # Date
        ttk.Label(form_frame, text=_t("legal.labels.scheduled_date", default="Date") + " *:").grid(row=4, column=0, sticky=tk.W, pady=3)
        self.consult_date = ttk.Entry(form_frame, width=30)
        self.consult_date.insert(0, (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'))
        self.consult_date.grid(row=4, column=1, pady=3, sticky=tk.EW)

        # Time
        ttk.Label(form_frame, text=_t("legal.labels.scheduled_time", default="Time") + " *:").grid(row=5, column=0, sticky=tk.W, pady=3)
        self.consult_time = ttk.Combobox(form_frame, values=[
            '09:00', '09:30', '10:00', '10:30', '11:00', '11:30',
            '13:00', '13:30', '14:00', '14:30', '15:00', '15:30', '16:00', '16:30'
        ], width=28)
        self.consult_time.set('10:00')
        self.consult_time.grid(row=5, column=1, pady=3, sticky=tk.EW)

        # Duration
        ttk.Label(form_frame, text=_t("legal.labels.duration", default="Duration") + ":").grid(row=6, column=0, sticky=tk.W, pady=3)
        self.consult_duration = ttk.Combobox(form_frame, values=['30', '60', '90', '120'], state='readonly', width=28)
        self.consult_duration.set('30')
        self.consult_duration.grid(row=6, column=1, pady=3, sticky=tk.EW)
        self.consult_duration.bind('<<ComboboxSelected>>', self.update_fee_display)

        # Lawyer
        ttk.Label(form_frame, text=_t("legal.labels.assigned_lawyer", default="Lawyer") + ":").grid(row=7, column=0, sticky=tk.W, pady=3)
        self.consult_lawyer = ttk.Entry(form_frame, width=30)
        self.consult_lawyer.grid(row=7, column=1, pady=3, sticky=tk.EW)

        # Fee display
        ttk.Label(form_frame, text=_t("legal.labels.fee", default="Fee") + ":").grid(row=8, column=0, sticky=tk.W, pady=3)
        self.fee_display_var = tk.StringVar(value="GBP 25.00")
        ttk.Label(form_frame, textvariable=self.fee_display_var, font=('Arial', 11, 'bold')).grid(row=8, column=1, sticky=tk.W, pady=3)

        # Notes
        ttk.Label(form_frame, text=_t("legal.labels.notes", default="Notes") + ":").grid(row=9, column=0, sticky=tk.NW, pady=3)
        self.consult_notes = scrolledtext.ScrolledText(form_frame, width=30, height=3)
        self.consult_notes.grid(row=9, column=1, pady=3, sticky=tk.EW)

        form_frame.columnconfigure(1, weight=1)

        ttk.Button(
            form_frame,
            text=_t("legal.btn.schedule_consultation", default="Schedule Consultation"),
            command=self.schedule_consultation
        ).grid(row=10, column=1, pady=15, sticky=tk.E)

        # Load consultations
        self.load_consultations()

    def schedule_consultation(self):
        """Schedule a new consultation"""
        try:
            client_name = self.consult_client_name.get().strip()
            client_id = self.consult_client_id.get().strip()
            client_email = self.consult_client_email.get().strip()
            consult_type = self.consult_type_combo.get()
            scheduled_date = self.consult_date.get().strip()
            scheduled_time = self.consult_time.get().strip()
            duration = int(self.consult_duration.get())
            lawyer_name = self.consult_lawyer.get().strip()
            notes = self.consult_notes.get('1.0', tk.END).strip()

            # Validation
            if not all([client_name, client_id, consult_type, scheduled_date, scheduled_time]):
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("legal.errors.fill_required", default="Please fill all required fields")
                )
                return

            # Validate date format
            try:
                datetime.strptime(scheduled_date, '%Y-%m-%d')
            except ValueError:
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("legal.errors.invalid_date", default="Please enter date in YYYY-MM-DD format")
                )
                return

            consultation_id = ConsultationManager.schedule_consultation(
                client_id=client_id,
                client_name=client_name,
                client_email=client_email,
                consultation_type=consult_type,
                scheduled_date=scheduled_date,
                scheduled_time=scheduled_time,
                duration_minutes=duration,
                lawyer_name=lawyer_name if lawyer_name else None,
                notes=notes
            )

            if consultation_id:
                fee = calculate_service_fee(consult_type, duration)
                messagebox.showinfo(
                    _t("common.success", default="Success"),
                    _t("legal.messages.consultation_scheduled", default="Consultation scheduled for {date} at {time}. Fee: GBP {fee:.2f}").format(
                        date=scheduled_date, time=scheduled_time, fee=fee
                    )
                )

                # Clear form
                self.consult_client_name.delete(0, tk.END)
                self.consult_client_id.delete(0, tk.END)
                self.consult_client_email.delete(0, tk.END)
                self.consult_lawyer.delete(0, tk.END)
                self.consult_notes.delete('1.0', tk.END)

                self.load_consultations()
            else:
                messagebox.showerror(
                    _t("common.error", default="Error"),
                    _t("legal.errors.schedule_failed", default="Failed to schedule consultation")
                )

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
            print(f"Error scheduling consultation: {traceback.format_exc()}")

    def process_consultation_payment(self):
        """Process payment for selected consultation"""
        if not self.selected_consultation:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.errors.no_consultation_selected", default="Please select a consultation first")
            )
            return

        if self.selected_consultation.get('payment_status') == 'paid':
            messagebox.showinfo(
                _t("common.info", default="Info"),
                _t("legal.messages.already_paid", default="This consultation has already been paid")
            )
            return

        try:
            consultation = ConsultationManager.get_consultation(self.selected_consultation['consultation_id'])
            if not consultation:
                messagebox.showerror(_t("common.error", default="Error"), "Consultation not found")
                return

            fee = consultation.get('fee', 0)
            client_id = consultation['client_id']

            # Check student account balance
            student_balance = get_student_finance_account_balance(client_id)

            # Payment method dialog
            dialog = tk.Toplevel(self.window)
            dialog.title(_t("legal.btn.process_payment", default="Process Payment"))
            dialog.geometry("400x350")
            dialog.transient(self.window)
            dialog.grab_set()

            ttk.Label(dialog, text=f"Client: {consultation['client_name']}", font=('Arial', 11)).pack(pady=5)
            ttk.Label(dialog, text=f"Amount Due: \u00a3{fee:.2f}", font=('Arial', 12, 'bold')).pack(pady=5)

            ttk.Label(dialog, text=_t("legal.labels.payment_method", default="Payment Method") + ":", font=('Arial', 10, 'bold')).pack(pady=(10, 5))

            # Payment method radio buttons
            payment_method_var = tk.StringVar(value="Cash")
            methods_frame = ttk.Frame(dialog)
            methods_frame.pack(pady=5)

            ttk.Radiobutton(methods_frame, text=_t("common.payment_methods.cash"), variable=payment_method_var, value="Cash").pack(anchor=tk.W)
            ttk.Radiobutton(methods_frame, text=_t("common.payment_methods.card"), variable=payment_method_var, value="Card").pack(anchor=tk.W)

            # Student Account option with balance display
            student_frame = ttk.Frame(methods_frame)
            student_frame.pack(anchor=tk.W)
            ttk.Radiobutton(student_frame, text=_t("common.payment_methods.student_account"), variable=payment_method_var, value="Student Account").pack(side=tk.LEFT)
            balance_text = f" (Balance: \u00a3{student_balance:.2f})" if student_balance else " (No account)"
            ttk.Label(student_frame, text=balance_text, font=('Arial', 9)).pack(side=tk.LEFT)

            def confirm_payment():
                payment_method = payment_method_var.get()

                # Handle Student Account payment
                if payment_method == "Student Account":
                    if student_balance < fee:
                        messagebox.showerror(
                            _t("common.error", default="Error"),
                            f"Insufficient balance. Current balance: \u00a3{student_balance:.2f}"
                        )
                        return
                    # Process student account payment
                    payment_result = process_student_finance_account_payment(
                        student_id=client_id,
                        amount=fee,
                        description=f"Legal consultation - {consultation['consultation_type']}",
                        transaction_source="LegalServices",
                        transaction_ref=str(consultation['consultation_id']),
                        processed_by=self.current_user.get('username', 'System')
                    )
                    if not payment_result.get('success'):
                        messagebox.showerror(_t("common.error", default="Error"), payment_result.get('message', "Failed to process student account payment"))
                        return

                payment_id = PaymentManager.record_payment(
                    client_id=client_id,
                    client_email=consultation.get('client_email', ''),
                    amount=fee,
                    payment_type='consultation_fee',
                    payment_method=payment_method,
                    consultation_id=consultation['consultation_id'],
                    case_id=consultation.get('case_id'),
                    processed_by=self.current_user.get('username')
                )

                if payment_id:
                    # Record revenue in central finance system
                    record_payment_to_finance(
                        student_id=client_id,
                        amount=fee,
                        payment_method=payment_method,
                        transaction_source='LegalServices',
                        transaction_ref=f"CONSULT-{consultation['consultation_id']}",
                        notes=f"Legal consultation fee - {consultation['consultation_type']}",
                        created_by=self.current_user.get('username')
                    )
                    logger.info(f"Revenue recorded: \u00a3{fee:.2f} for consultation {consultation['consultation_id']}")

                    messagebox.showinfo(
                        _t("common.success", default="Success"),
                        _t("legal.messages.payment_processed", default="Payment of GBP {amount:.2f} processed successfully").format(amount=fee)
                    )
                    dialog.destroy()
                    self.load_consultations()

                    # Ask to send receipt
                    client_email = consultation.get('client_email', '')
                    if client_email and '@' in client_email and messagebox.askyesno(
                        _t("common.confirm", default="Confirm"),
                        _t("legal.confirm.send_receipt", default="Send receipt to {email}?").format(email=client_email)
                    ):
                        self.send_consultation_receipt(consultation_id=consultation['consultation_id'])
                else:
                    messagebox.showerror(
                        _t("common.error", default="Error"),
                        _t("legal.errors.payment_failed", default="Payment processing failed")
                    )

            ttk.Button(dialog, text=_t("legal.btn.process_payment", default="Process Payment"), command=confirm_payment).pack(pady=20)

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
            print(f"Error processing payment: {traceback.format_exc()}")

    def send_consultation_receipt(self, consultation_id: int = None):
        """Send email receipt to client after payment"""
        if consultation_id is None:
            if not self.selected_consultation:
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("legal.errors.no_consultation_selected", default="Please select a consultation first")
                )
                return
            consultation_id = self.selected_consultation['consultation_id']

        try:
            consultation = ConsultationManager.get_consultation(consultation_id)
            if not consultation:
                messagebox.showerror(_t("common.error", default="Error"), "Consultation not found")
                return

            if consultation.get('payment_status') != 'paid':
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("legal.warnings.payment_required", default="Please process payment before sending receipt")
                )
                return

            client_email = consultation.get('client_email', '')
            if not client_email or '@' not in client_email:
                logger.info(f"Receipt email skipped - invalid email format: {client_email}")
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("legal.errors.no_email", default="Client email not available")
                )
                return

            # Get payment details
            payments = PaymentManager.get_all_payments({'consultation_id': consultation_id})
            payment = payments[0] if payments else None

            if not payment:
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("legal.warnings.no_payment_found", default="No payment record found")
                )
                return

            # Generate receipt - try to use template
            subject = None
            receipt_body = None
            if render_template:
                subject, receipt_body = render_template('commerce/legal/payment_receipt', {
                    'client_name': consultation['client_name'],
                    'receipt_number': payment['transaction_reference'],
                    'payment_date': payment['created_at'][:10],
                    'payment_method': payment['payment_method'],
                    'consultation_type': consultation['consultation_type'].replace('_', ' ').title(),
                    'scheduled_date': consultation['scheduled_date'],
                    'scheduled_time': consultation['scheduled_time'],
                    'duration': consultation['duration_minutes'],
                    'lawyer_name': consultation.get('lawyer_name', 'To be assigned'),
                    'service_fee': f"GBP {consultation['fee']:.2f}",
                    'amount_paid': f"GBP {payment['amount']:.2f}"
                })

            # Fallback if template not found
            if not subject or not receipt_body:
                receipt_body = f"""
Dear {consultation['client_name']},

Thank you for your payment. This email confirms your legal consultation payment.

{'='*60}
                    PAYMENT RECEIPT
{'='*60}

Receipt Number:     {payment['transaction_reference']}
Payment Date:       {payment['created_at'][:10]}
Payment Method:     {payment['payment_method']}

{'='*60}
CONSULTATION DETAILS
{'='*60}

Consultation Type:  {consultation['consultation_type'].replace('_', ' ').title()}
Scheduled Date:     {consultation['scheduled_date']}
Scheduled Time:     {consultation['scheduled_time']}
Duration:           {consultation['duration_minutes']} minutes
Lawyer:             {consultation.get('lawyer_name', 'To be assigned')}

{'='*60}
PAYMENT DETAILS
{'='*60}

Service Fee:        GBP {consultation['fee']:.2f}
Amount Paid:        GBP {payment['amount']:.2f}

{'='*60}

If you need to reschedule or cancel your consultation, please contact us
at least 24 hours in advance.

Thank you for using University Legal Aid Center.

Best regards,
University Legal Services
legal@university.edu
"""
                subject = f"Legal Services Receipt - {payment['transaction_reference']}"

            if EMAIL_AVAILABLE:
                result = send_email(
                    recipient_email=client_email,
                    subject=subject,
                    body=receipt_body
                )

                if result:
                    PaymentManager.mark_receipt_sent(payment['payment_id'])
                    messagebox.showinfo(
                        _t("common.success", default="Success"),
                        _t("legal.messages.receipt_sent", default="Receipt sent to {email}").format(email=client_email)
                    )
                else:
                    messagebox.showerror(
                        _t("common.error", default="Error"),
                        _t("legal.errors.email_failed", default="Failed to send email")
                    )
            else:
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("legal.warnings.email_unavailable", default="Email service not available. Receipt not sent.")
                )

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
            print(f"Error sending receipt: {traceback.format_exc()}")

    def cancel_consultation(self):
        """Cancel a scheduled consultation"""
        if not self.selected_consultation:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.errors.no_consultation_selected", default="Please select a consultation first")
            )
            return

        if self.selected_consultation.get('status') in ['cancelled', 'completed']:
            messagebox.showinfo(
                _t("common.info", default="Info"),
                _t("legal.messages.cannot_cancel", default="This consultation cannot be cancelled")
            )
            return

        reason = simpledialog.askstring(
            _t("legal.btn.cancel_consultation", default="Cancel Consultation"),
            _t("legal.prompts.cancel_reason", default="Enter cancellation reason:")
        )

        if reason is None:
            return

        try:
            # Check if refund is needed
            if self.selected_consultation.get('payment_status') == 'paid':
                if messagebox.askyesno(
                    _t("common.confirm", default="Confirm"),
                    _t("legal.confirm.process_refund", default="This consultation was paid. Process refund?")
                ):
                    # Get payment and process refund
                    payments = PaymentManager.get_all_payments({'consultation_id': self.selected_consultation['consultation_id']})
                    if payments:
                        PaymentManager.process_refund(
                            payments[0]['payment_id'],
                            reason=reason,
                            processed_by=self.current_user.get('username')
                        )

            if ConsultationManager.cancel_consultation(self.selected_consultation['consultation_id'], reason):
                messagebox.showinfo(
                    _t("common.success", default="Success"),
                    _t("legal.messages.consultation_cancelled", default="Consultation cancelled successfully")
                )
                self.load_consultations()
            else:
                messagebox.showerror(
                    _t("common.error", default="Error"),
                    _t("legal.errors.cancel_failed", default="Failed to cancel consultation")
                )

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))

    def load_consultations(self):
        """Load consultations into the treeview"""
        try:
            for item in self.consult_tree.get_children():
                self.consult_tree.delete(item)

            filters = {}
            status_filter = self.consult_status_filter.get()
            if status_filter != _t("common.all", default="All"):
                filters['status'] = status_filter

            self.consultations_data = ConsultationManager.get_all_consultations(filters)

            for consult in self.consultations_data:
                self.consult_tree.insert('', tk.END, values=(
                    consult['consultation_id'],
                    consult['client_name'],
                    consult['scheduled_date'],
                    consult['scheduled_time'],
                    consult['consultation_type'],
                    f"GBP {consult['fee']:.2f}",
                    consult['payment_status'],
                    consult['status']
                ))

        except Exception as e:
            print(f"Error loading consultations: {e}")

    def on_consultation_select(self, event):
        """Handle consultation selection"""
        selected = self.consult_tree.selection()
        if selected:
            item = self.consult_tree.item(selected[0])
            consult_id = item['values'][0]
            self.selected_consultation = next((c for c in self.consultations_data if c['consultation_id'] == consult_id), None)
