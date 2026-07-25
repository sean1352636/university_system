"""Billing mixin for the Legal Services GUI."""

from education_system.systems.university.interfaces.gui.governance.legal._imports import (
    tk, ttk, messagebox, scrolledtext, filedialog, traceback,
    datetime,
    transaction,
    CaseManager, ConsultationManager, PaymentManager,
    calculate_service_fee, generate_invoice_text,
    log_activity,
    _t, logger,
    send_email, EMAIL_AVAILABLE,
)


class BillingMixin:
    """Billing helpers: fee calculation, payment recording, invoice generation."""

    def calculate_service_fees(self, service_type: str, duration: int = 30) -> float:
        """Calculate fees for a given service type"""
        return calculate_service_fee(service_type, duration)

    def update_fee_display(self, event=None):
        """Update the fee display based on selected type and duration"""
        try:
            service_type = self.consult_type_combo.get()
            duration = int(self.consult_duration.get())
            fee = self.calculate_service_fees(service_type, duration)
            self.fee_display_var.set(f"GBP {fee:.2f}")
        except Exception:
            self.fee_display_var.set("GBP 25.00")

    def record_payment_transaction(self, client_id: str, amount: float, description: str, payment_method: str):
        """Record payment transaction in finance system to add to revenue"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()

                # Try to record in the main payments table
                payment_row_id = None
                try:
                    cursor.execute('''
                        INSERT INTO payments
                        (student_id, amount, payment_method, payment_date, status, notes, created_by, created_at)
                        VALUES (?, ?, ?, ?, 'completed', ?, ?, ?)
                    ''', (client_id, amount, payment_method, datetime.now().strftime('%Y-%m-%d'),
                          description, self.current_user.get('username'), datetime.now().isoformat()))
                    payment_row_id = cursor.lastrowid
                except Exception:
                    pass  # payments table may not exist

                # Auto-post to GL if the INSERT succeeded (never raises)
                if payment_row_id is not None:
                    try:
                        from education_system.systems.university.domain.finance.ledger import notify_ledger
                        notify_ledger('payment', payment_row_id,
                                      posted_by=self.current_user.get('username') or 'legal')
                    except Exception as _e:
                        import logging
                        logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

                # Try to update student finance account
                try:
                    cursor.execute('''
                        SELECT account_id FROM student_finance_accounts WHERE student_id = ?
                    ''', (client_id,))
                    account = cursor.fetchone()

                    if account:
                        cursor.execute('''
                            INSERT INTO transactions
                            (source_type, account_id, student_id, transaction_type, amount, description, processed_by, created_at)
                            VALUES ('student_finance', ?, ?, 'legal_service', ?, ?, ?, ?)
                        ''', (account[0], client_id, amount, description,
                              self.current_user.get('username'), datetime.now().isoformat()))
                except Exception:
                    pass  # Finance tables may not exist

            log_activity('record_payment', 'legal_services', details={
                'client_id': client_id,
                'amount': amount,
                'description': description
            })

            return True

        except Exception as e:
            print(f"Error recording payment transaction: {e}")
            return False

    def generate_invoice(self):
        """Generate invoice for the selected case"""
        case_selection = self.doc_case_combo.get()
        if not case_selection:
            messagebox.showwarning(
                _t("common.warning", default="Warning"),
                _t("legal.errors.no_case_selected", default="Please select a case first")
            )
            return

        try:
            case_number = case_selection.split(' - ')[0]
            case = CaseManager.get_case_by_number(case_number)
            if not case:
                messagebox.showerror(_t("common.error", default="Error"), "Case not found")
                return

            # Get payments and services
            payments = PaymentManager.get_all_payments({'case_id': case['case_id']})
            consultations = ConsultationManager.get_all_consultations({'case_id': case['case_id']}) if case.get('case_id') else []

            services = []
            for c in consultations:
                services.append(f"{c['consultation_type']} consultation ({c['duration_minutes']} min) - GBP {c['fee']:.2f}")

            invoice_text = generate_invoice_text(case, payments, services if services else ['Legal services as per agreement'])

            # Show invoice dialog
            dialog = tk.Toplevel(self.window)
            dialog.title(f"Invoice - {case['case_number']}")
            dialog.geometry("600x500")
            dialog.transient(self.window)

            text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=('Courier', 10))
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            text.insert('1.0', invoice_text)
            text.config(state='disabled')

            btn_frame = ttk.Frame(dialog)
            btn_frame.pack(fill=tk.X, pady=10)

            def save_invoice():
                file_path = filedialog.asksaveasfilename(
                    defaultextension=".txt",
                    filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
                    initialfile=f"invoice_{case['case_number']}.txt"
                )
                if file_path:
                    with open(file_path, 'w') as f:
                        f.write(invoice_text)
                    messagebox.showinfo(_t("common.success", default="Success"), "Invoice saved successfully")

            def email_invoice():
                client_email = case.get('client_email', '')
                if client_email and '@' in client_email:
                    if EMAIL_AVAILABLE:
                        result = send_email(
                            recipient_email=client_email,
                            subject=f"Invoice - {case['case_number']}",
                            body=invoice_text
                        )
                        if result:
                            logger.info(f"Invoice email sent to {client_email}")
                            messagebox.showinfo(_t("common.success", default="Success"), "Invoice sent successfully")
                        else:
                            messagebox.showerror(_t("common.error", default="Error"), "Failed to send invoice")
                    else:
                        messagebox.showwarning(_t("common.warning", default="Warning"), "Email service not available")
                else:
                    logger.info(f"Invoice email skipped - invalid email format: {client_email}")
                    messagebox.showwarning(_t("common.warning", default="Warning"), "No valid client email available")

            ttk.Button(btn_frame, text=_t("common.save_invoice"), command=save_invoice).pack(side=tk.LEFT, padx=10)
            ttk.Button(btn_frame, text="Email Invoice", command=email_invoice).pack(side=tk.LEFT, padx=10)
            ttk.Button(btn_frame, text=_t("common.close", default="Close"), command=dialog.destroy).pack(side=tk.RIGHT, padx=10)

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
            print(f"Error generating invoice: {traceback.format_exc()}")
