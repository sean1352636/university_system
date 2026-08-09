"""Methods process_payment through reschedule_appointment."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import nailbar_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class NailBarGUI:
    def process_payment(self):
        """Process payment - Function 23"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        booking_ref = item['values'][0]
        payment_status = item['values'][6]

        if payment_status == 'paid':
            messagebox.showinfo(_t("common.info"), _t("nailbar.messages.already_paid"))
            return

        from education_system.systems.university.domains.operations.domain.commerce.nailbar.services.nailbar_core import AppointmentManager, TransactionManager
        appt = AppointmentManager.get_appointment_by_reference(booking_ref)

        if not appt:
            return

        # Get customer details
        customer_id = appt.get('customer_id', self.current_user.get('student_id', 'guest'))
        customer_email = appt.get('customer_email') or self.current_user.get('email', '')
        customer_name = appt.get('customer_name') or self.current_user.get('full_name', '')

        # Payment dialog
        payment_window = tk.Toplevel(self.parent)
        payment_window.title(_t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_process_payment.windows.process_payment', default="Process Payment"))
        payment_window.geometry("500x550")
        payment_window.transient(self.parent)
        payment_window.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(payment_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        ttk.Label(main_frame, text=_t("nailbar.labels.payment_details"),
                 font=('Helvetica', 16, 'bold')).pack(pady=(0, 15))

        # Appointment info frame
        info_frame = ttk.LabelFrame(main_frame, text=_t("nailbar.labels.appointment_info"), padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(info_frame, text=f"Booking: {booking_ref}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Customer: {customer_name}").pack(anchor=tk.W)

        # Treatments list
        treatments = appt.get('treatments', [])
        treatments_text = ', '.join(t['treatment_name'] for t in treatments)
        ttk.Label(info_frame, text=f"Treatments: {treatments_text[:50]}{'...' if len(treatments_text) > 50 else ''}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Technician: {appt.get('technician_name', 'Any')}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Service Total: £{appt['total_amount']:.2f}",
                 font=('Helvetica', 12, 'bold')).pack(anchor=tk.W, pady=(5, 0))

        # Tip frame
        tip_frame = ttk.Frame(main_frame)
        tip_frame.pack(fill=tk.X, pady=10)
        ttk.Label(tip_frame, text=_t("nailbar.labels.add_tip")).pack(side=tk.LEFT)
        tip_var = tk.StringVar(value="0")
        ttk.Entry(tip_frame, textvariable=tip_var, width=10).pack(side=tk.LEFT, padx=10)

        # Payment method frame
        method_frame = ttk.LabelFrame(main_frame, text=_t("nailbar.labels.select_payment_method"), padding="10")
        method_frame.pack(fill=tk.X, pady=10)

        payment_method_var = tk.StringVar(value=_t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_process_payment.values.card', default="card"))

        # Cash option
        ttk.Radiobutton(method_frame, text=_t("nailbar.labels.cash"), variable=payment_method_var,
                       value="cash").pack(anchor=tk.W, pady=2)

        # Card option
        ttk.Radiobutton(method_frame, text=_t("nailbar.labels.card"), variable=payment_method_var,
                       value="card").pack(anchor=tk.W, pady=2)

        # Student Account option with balance
        student_balance = 0.0
        balance_text=_t("nailbar.labels.balance_not_available")
        if FINANCE_AVAILABLE:
            try:
                ensure_student_finance_account_exists(customer_id)
                student_balance = get_student_finance_account_balance(customer_id) or 0.0
                balance_text = f"Balance: £{student_balance:.2f}"
            except Exception as e:
                logger.error(f"Error getting student balance: {e}")

        student_frame = ttk.Frame(method_frame)
        student_frame.pack(anchor=tk.W, fill=tk.X)
        ttk.Radiobutton(student_frame, text=_t("nailbar.labels.student_account"),
                       variable=payment_method_var, value="student_account").pack(side=tk.LEFT)
        balance_label = ttk.Label(student_frame, text=balance_text,
                                 foreground='green' if student_balance > 0 else 'gray')
        balance_label.pack(side=tk.LEFT, padx=10)

        # Total display
        total_frame = ttk.Frame(main_frame)
        total_frame.pack(fill=tk.X, pady=10)

        def update_total(*args):
            try:
                tip = float(tip_var.get() or 0)
                total = appt['total_amount'] + tip
                total_label.config(text=f"Total: £{total:.2f}")
            except ValueError:
                pass

        tip_var.trace('w', update_total)
        total_label = ttk.Label(total_frame, text=f"Total: £{appt['total_amount']:.2f}",
                               font=('Helvetica', 14, 'bold'))
        total_label.pack()

        # Email receipt option
        send_receipt_var = tk.BooleanVar(value=True if customer_email else False)
        receipt_frame = ttk.Frame(main_frame)
        receipt_frame.pack(fill=tk.X, pady=5)
        ttk.Checkbutton(receipt_frame, text=f"Send receipt to: {customer_email}",
                       variable=send_receipt_var,
                       state='normal' if customer_email else 'disabled').pack(anchor=tk.W)

        def confirm_payment():
            method = payment_method_var.get()
            try:
                tip = float(tip_var.get() or 0)
            except ValueError:
                messagebox.showerror(_t("nailbar.msg_titles.error"), _t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_process_payment.dialogs.invalid_tip_amount', default="Invalid tip amount."))
                return

            total_amount = appt['total_amount'] + tip

            try:
                transaction_ref = f"NAILBAR-{appt['appointment_id']}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                if method == 'student_account':
                    # Check if finance integration available
                    if not FINANCE_AVAILABLE:
                        messagebox.showerror(_t("nailbar.msg_titles.error"), _t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_process_payment.dialogs.student_account_payment_is_not_available', default="Student account payment is not available."))
                        return

                    # Check balance
                    if student_balance < total_amount:
                        messagebox.showerror(_t("nailbar.msg_titles.insufficient_balance"),
                            f"Your account balance (£{student_balance:.2f}) is insufficient.\n"
                            f"Required: £{total_amount:.2f}")
                        return

                    # Process student account payment
                    result = process_student_finance_account_payment(
                        student_id=customer_id,
                        amount=total_amount,
                        description=f"Nail Bar: {treatments_text[:30]}",
                        transaction_source="NailBar",
                        transaction_ref=transaction_ref,
                        processed_by=self.current_user.get('username', 'system')
                    )

                    if not result.get('success'):
                        messagebox.showerror(_t("nailbar.msg_titles.payment_failed"), result.get('message', 'Unknown error'))
                        return

                    payment_id = result.get('transaction_id')

                else:
                    # Cash or Card payment - record to central finance
                    if FINANCE_AVAILABLE:
                        payment_id = record_payment_to_finance(
                            student_id=customer_id,
                            amount=total_amount,
                            payment_method=method.title(),
                            transaction_source="NailBar",
                            transaction_ref=transaction_ref,
                            notes=f"Treatments: {treatments_text[:50]}" + (f", Tip: £{tip:.2f}" if tip > 0 else ""),
                            created_by=self.current_user.get('username', 'system')
                        )
                    else:
                        payment_id = None

                # Record in nailbar transactions table
                local_trans_id = TransactionManager.process_payment(
                    appointment_id=appt['appointment_id'],
                    amount=appt['total_amount'],
                    payment_method=method,
                    customer_id=customer_id,
                    tip_amount=tip,
                    processed_by=self.current_user.get('username')
                )

                # Send receipt email if requested
                if send_receipt_var.get() and customer_email:
                    self._send_payment_receipt(
                        appt=appt,
                        total_amount=total_amount,
                        tip=tip,
                        payment_method=method,
                        transaction_ref=transaction_ref,
                        customer_email=customer_email,
                        customer_name=customer_name
                    )

                log_activity('payment', 'nailbar_appointment',
                            details={'appointment_id': appt['appointment_id'],
                                   'amount': total_amount,
                                   'method': method})

                messagebox.showinfo(_t("nailbar.msg_titles.success"),
                    f"Payment of £{total_amount:.2f} processed successfully!\n\n"
                    f"Method: {method.replace('_', ' ').title()}\n"
                    f"Reference: {transaction_ref}")
                payment_window.destroy()
                self._load_appointments()

            except Exception as e:
                logger.error(f"Payment processing error: {e}")
                messagebox.showerror(_t("nailbar.msg_titles.error"), f"Payment failed: {str(e)}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(btn_frame, text=_t("nailbar.btn.confirm_payment"),
                  command=confirm_payment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t("nailbar.btn.cancel"),
                  command=payment_window.destroy).pack(side=tk.RIGHT, padx=5)

    def _send_payment_receipt(self, appt: dict, total_amount: float, tip: float,
                              payment_method: str, transaction_ref: str,
                              customer_email: str, customer_name: str):
        """Send payment receipt email to customer."""
        try:
            treatments = appt.get('treatments', [])
            treatments_text = '\n'.join(f"  - {t['treatment_name']}: £{t['price']:.2f}"
                                       for t in treatments)

            # Use JSON template for email
            from education_system.systems.university.infrastructure.email.template_utils import render_template
            subject, body = render_template('commerce/nailbar/payment_receipt', {
                'customer_name': customer_name,
                'booking_reference': appt['booking_reference'],
                'appointment_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'technician_name': appt.get('technician_name', 'Any available'),
                'treatments_list': treatments_text,
                'subtotal': f"£{appt['total_amount']:.2f}",
                'tip_amount': f"£{tip:.2f}",
                'total_amount': f"£{total_amount:.2f}",
                'payment_method': payment_method.replace('_', ' ').title(),
                'transaction_ref': transaction_ref
            })

            # Try to send email - import directly to ensure it works
            try:
                from education_system.systems.university.infrastructure.email.email_service import send_email as send_email_func
                send_email_func(customer_email, subject, body)
                logger.info(f"Receipt sent to {customer_email}")

                # Mark receipt as sent
                from education_system.systems.university.domains.operations.domain.commerce.nailbar.services.nailbar_core import TransactionManager
                TransactionManager.mark_receipt_sent(appt['appointment_id'])
            except ImportError:
                logger.warning("Email service not available - receipt not sent")
            except Exception as email_err:
                logger.error(f"Email sending failed: {email_err}")

        except Exception as e:
            logger.error(f"Failed to prepare receipt email: {e}")

    def send_receipt_email(self, appointment: dict, transaction_id: int, tip: float = 0):
        """Send receipt email - Function 24 (legacy method)"""
        try:
            if not EMAIL_AVAILABLE:
                logger.warning("Email service not available")
                return

            total = appointment['total_amount'] + tip
            treatments_text = '\n'.join(f"  - {t['treatment_name']}: £{t['price']:.2f}"
                                       for t in appointment.get('treatments', []))

            # Use JSON template for email
            from education_system.systems.university.infrastructure.email.template_utils import render_template
            subject, body = render_template('commerce/nailbar/payment_receipt', {
                'customer_name': appointment['customer_name'],
                'booking_reference': appointment['booking_reference'],
                'appointment_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'technician_name': appointment.get('technician_name', 'N/A'),
                'treatments_list': treatments_text,
                'subtotal': f"£{appointment['total_amount']:.2f}",
                'tip_amount': f"£{tip:.2f}",
                'total_amount': f"£{total:.2f}",
                'payment_method': 'N/A',
                'transaction_ref': str(transaction_id)
            })

            send_email(
                recipient_email=appointment['customer_email'],
                subject=subject,
                body=body
            )

            from education_system.systems.university.domains.operations.domain.commerce.nailbar.services.nailbar_core import TransactionManager
            TransactionManager.mark_receipt_sent(transaction_id)

            logger.info(f"Receipt sent to {appointment['customer_email']}")

        except Exception as e:
            logger.error(f"Failed to send receipt: {e}")

    def cancel_appointment(self):
        """Cancel appointment - Function 25"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.select_appointment"))
            return

        if not messagebox.askyesno(_t("common.confirm"), _t("nailbar.confirm.cancel_appointment")):
            return

        item = self.appointments_tree.item(selected[0])
        booking_ref = item['values'][0]

        try:
            from education_system.systems.university.domains.operations.domain.commerce.nailbar.services.nailbar_core import AppointmentManager
            appt = AppointmentManager.get_appointment_by_reference(booking_ref)

            if appt:
                AppointmentManager.cancel_appointment(appt['appointment_id'], 'Cancelled by user')
                log_activity('cancel', 'nailbar_appointment',
                            details={'appointment_id': appt['appointment_id']})
                messagebox.showinfo(_t("common.success"), _t("nailbar.messages.appointment_cancelled"))
                self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def reschedule_appointment(self):
        """Reschedule appointment"""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("nailbar.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        booking_ref = item['values'][0]

        from education_system.systems.university.domains.operations.domain.commerce.nailbar.services.nailbar_core import AppointmentManager
        appt = AppointmentManager.get_appointment_by_reference(booking_ref)

        if not appt:
            return

        resched_window = tk.Toplevel(self.parent)
        resched_window.title(_t("nailbar.labels.reschedule"))
        resched_window.geometry("350x200")
        resched_window.transient(self.parent)
        resched_window.grab_set()

        ttk.Label(resched_window, text=f"{_t('nailbar.labels.booking_ref')}: {booking_ref}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(resched_window)
        frame.pack(pady=10)

        ttk.Label(frame, text=_t("nailbar.labels.new_date") + ":").grid(row=0, column=0, pady=5)
        new_date_var = tk.StringVar(value=appt['appointment_date'])
        ttk.Entry(frame, textvariable=new_date_var, width=12).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text=_t("nailbar.labels.new_time") + ":").grid(row=1, column=0, pady=5)
        new_time_combo = ttk.Combobox(frame, state="readonly", width=10)
        new_time_combo['values'] = self._get_time_slots()
        new_time_combo.set(appt['appointment_time'])
        new_time_combo.grid(row=1, column=1, pady=5)

        def confirm_reschedule():
            new_date = new_date_var.get().strip()
            new_time = new_time_combo.get()

            try:
                AppointmentManager.reschedule_appointment(appt['appointment_id'], new_date, new_time)
                log_activity('reschedule', 'nailbar_appointment',
                            details={'appointment_id': appt['appointment_id']})
                messagebox.showinfo(_t("common.success"), _t("nailbar.messages.appointment_rescheduled"))
                resched_window.destroy()
                self._load_appointments()
            except Exception as e:
                messagebox.showerror(_t("common.error"), str(e))

        ttk.Button(resched_window, text=_t("nailbar.btn.confirm_reschedule"),
                  command=confirm_reschedule).pack(pady=20)
