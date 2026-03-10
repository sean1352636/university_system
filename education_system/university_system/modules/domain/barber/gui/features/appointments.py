"""Barber Shop GUI - Appointment management feature methods."""

from education_system.university_system.modules.domain.barber.gui.common import (
    tk, ttk, messagebox, logging,
    datetime, timedelta,
    _t, get_db_connection, transaction, log_activity,
    EMAIL_AVAILABLE, FINANCE_AVAILABLE,
    record_payment_to_finance,
    get_student_finance_account_balance,
    process_student_finance_account_payment,
    ensure_student_finance_account_exists,
)

logger = logging.getLogger(__name__)


class AppointmentsMixin:
    """Mixin providing appointment management methods for BarberGUI."""

    def book_appointment(self):
        """Book a new appointment."""
        # Use current user details - build full name from first/last if available
        first_name = self.current_user.get('first_name', '')
        last_name = self.current_user.get('last_name', '')
        if first_name and last_name:
            customer_name = f"{first_name} {last_name}"
        else:
            customer_name = self.current_user.get('full_name') or self.current_user.get('username', 'Guest')

        customer_email = self.current_user.get('email', '')
        customer_phone = self.current_user.get('phone', '')
        # Use student_id, then username, then id as fallback for customer_id
        customer_id = (self.current_user.get('student_id') or
                      self.current_user.get('username') or
                      str(self.current_user.get('id', 'guest')))

        service_str = self.appt_service_combo.get()
        staff_str = self.appt_staff_combo.get()
        appt_date = self.appt_date_var.get().strip()
        appt_time = self.appt_time_combo.get()

        if not service_str or not appt_date or not appt_time:
            messagebox.showerror(_t("common.error"), "Please select a service, date and time.")
            return

        try:
            service_id = int(service_str.split(':')[0])
            staff_id = None
            if staff_str != 'Any':
                staff_id = int(staff_str.split(':')[0])

            from education_system.university_system.modules.domain.barber.services.barber_core import AppointmentManager

            appt_id, appt_number = AppointmentManager.book_appointment(
                customer_id=customer_id,
                customer_name=customer_name,
                service_id=service_id,
                appointment_date=appt_date,
                appointment_time=appt_time,
                staff_id=staff_id,
                customer_email=customer_email,
                customer_phone=customer_phone
            )

            log_activity('create', 'barber_appointment',
                        details={'appointment_id': appt_id})

            messagebox.showinfo(_t("common.success"),
                              _t("barber.messages.appointment_booked").format(appointment_number=appt_number))

            self._clear_appointment_form()
            self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("barber.errors.booking_failed").format(error=str(e)))

    def check_in_customer(self):
        """Check in customer for appointment."""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("barber.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        try:
            from education_system.university_system.modules.domain.barber.services.barber_core import AppointmentManager
            appt = AppointmentManager.get_appointment_by_number(appt_number)

            if appt:
                AppointmentManager.update_status(appt['appointment_id'], 'checked_in',
                                                self.current_user.get('user_id'))
                messagebox.showinfo(_t("common.success"), _t("barber.messages.checked_in"))
                self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def start_service(self):
        """Mark service as started."""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("barber.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        try:
            from education_system.university_system.modules.domain.barber.services.barber_core import AppointmentManager
            appt = AppointmentManager.get_appointment_by_number(appt_number)

            if appt:
                AppointmentManager.update_status(appt['appointment_id'], 'in_progress',
                                                self.current_user.get('user_id'))
                messagebox.showinfo(_t("common.success"), _t("barber.messages.service_started"))
                self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def complete_service(self):
        """Mark service as completed."""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("barber.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        try:
            from education_system.university_system.modules.domain.barber.services.barber_core import AppointmentManager
            appt = AppointmentManager.get_appointment_by_number(appt_number)

            if appt:
                AppointmentManager.update_status(appt['appointment_id'], 'completed',
                                                self.current_user.get('user_id'))
                messagebox.showinfo(_t("common.success"), _t("barber.messages.service_completed"))
                self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def process_payment(self):
        """Process payment for appointment."""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("barber.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]
        payment_status = item['values'][6]

        if payment_status == 'paid':
            messagebox.showinfo(_t("common.info"), _t("barber.messages.already_paid"))
            return

        from education_system.university_system.modules.domain.barber.services.barber_core import AppointmentManager, TransactionManager
        appt = AppointmentManager.get_appointment_by_number(appt_number)

        if not appt:
            return

        # Get customer details
        customer_id = appt.get('customer_id', self.current_user.get('user_id', 'guest'))
        customer_email = appt.get('customer_email') or self.current_user.get('email', '')
        customer_name = appt.get('customer_name') or self.current_user.get('full_name', '')

        # Payment dialog
        payment_window = tk.Toplevel(self.parent)
        payment_window.title("Process Payment")
        payment_window.geometry("500x500")
        payment_window.transient(self.parent)
        payment_window.grab_set()

        # Main frame with padding
        main_frame = ttk.Frame(payment_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        ttk.Label(main_frame, text="Payment Details",
                 font=('Helvetica', 16, 'bold')).pack(pady=(0, 15))

        # Appointment info frame
        info_frame = ttk.LabelFrame(main_frame, text="Appointment Information", padding="10")
        info_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(info_frame, text=f"Appointment: {appt_number}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Customer: {customer_name}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Service: {appt['service_name']}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Price: £{appt['price']:.2f}",
                 font=('Helvetica', 12, 'bold')).pack(anchor=tk.W, pady=(5, 0))

        # Tip frame
        tip_frame = ttk.Frame(main_frame)
        tip_frame.pack(fill=tk.X, pady=10)
        ttk.Label(tip_frame, text="Add Tip (£):").pack(side=tk.LEFT)
        tip_var = tk.StringVar(value="0")
        ttk.Entry(tip_frame, textvariable=tip_var, width=10).pack(side=tk.LEFT, padx=10)

        # Payment method frame
        method_frame = ttk.LabelFrame(main_frame, text="Select Payment Method", padding="10")
        method_frame.pack(fill=tk.X, pady=10)

        payment_method_var = tk.StringVar(value="card")

        # Cash option
        ttk.Radiobutton(method_frame, text="Cash", variable=payment_method_var,
                       value="cash").pack(anchor=tk.W, pady=2)

        # Card option
        ttk.Radiobutton(method_frame, text="Card", variable=payment_method_var,
                       value="card").pack(anchor=tk.W, pady=2)

        # Student Account option with balance
        student_balance = 0.0
        balance_text = "Balance: Not available"
        if FINANCE_AVAILABLE:
            try:
                ensure_student_finance_account_exists(customer_id)
                student_balance = get_student_finance_account_balance(customer_id) or 0.0
                balance_text = f"Balance: £{student_balance:.2f}"
            except Exception as e:
                logger.error(f"Error getting student balance: {e}")

        student_frame = ttk.Frame(method_frame)
        student_frame.pack(anchor=tk.W, fill=tk.X)
        ttk.Radiobutton(student_frame, text="Student Account",
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
                total = appt['price'] + tip
                total_label.config(text=f"Total: £{total:.2f}")
            except ValueError:
                pass

        tip_var.trace('w', update_total)
        total_label = ttk.Label(total_frame, text=f"Total: £{appt['price']:.2f}",
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
                messagebox.showerror("Error", "Invalid tip amount.")
                return

            total_amount = appt['price'] + tip

            # Process based on payment method
            try:
                transaction_ref = f"BARBER-{appt['appointment_id']}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                if method == 'student_account':
                    # Check if finance integration available
                    if not FINANCE_AVAILABLE:
                        messagebox.showerror("Error", "Student account payment is not available.")
                        return

                    # Check balance
                    if student_balance < total_amount:
                        messagebox.showerror("Insufficient Balance",
                            f"Your account balance (£{student_balance:.2f}) is insufficient.\n"
                            f"Required: £{total_amount:.2f}")
                        return

                    # Process student account payment
                    result = process_student_finance_account_payment(
                        student_id=customer_id,
                        amount=total_amount,
                        description=f"Barber service: {appt['service_name']}",
                        transaction_source="Barber",
                        transaction_ref=transaction_ref,
                        processed_by=self.current_user.get('username', 'system')
                    )

                    if not result.get('success'):
                        messagebox.showerror("Payment Failed", result.get('message', 'Unknown error'))
                        return

                    payment_id = result.get('transaction_id')

                else:
                    # Cash or Card payment - record to central finance
                    if FINANCE_AVAILABLE:
                        payment_id = record_payment_to_finance(
                            student_id=customer_id,
                            amount=total_amount,
                            payment_method=method.title(),
                            transaction_source="Barber",
                            transaction_ref=transaction_ref,
                            notes=f"Service: {appt['service_name']}" + (f", Tip: £{tip:.2f}" if tip > 0 else ""),
                            created_by=self.current_user.get('username', 'system')
                        )
                    else:
                        payment_id = None

                # Record in barber transactions table
                local_trans_id = TransactionManager.process_payment(
                    appointment_id=appt['appointment_id'],
                    amount=appt['price'],
                    payment_method=method,
                    customer_id=customer_id,
                    tip_amount=tip,
                    processed_by=self.current_user.get('username')
                )

                # Send receipt email if requested
                if send_receipt_var.get() and customer_email and EMAIL_AVAILABLE:
                    self._send_payment_receipt(
                        appt=appt,
                        total_amount=total_amount,
                        tip=tip,
                        payment_method=method,
                        transaction_ref=transaction_ref,
                        customer_email=customer_email,
                        customer_name=customer_name
                    )

                log_activity('payment', 'barber_appointment',
                            details={'appointment_id': appt['appointment_id'],
                                   'amount': total_amount,
                                   'method': method})

                messagebox.showinfo("Success",
                    f"Payment of £{total_amount:.2f} processed successfully!\n\n"
                    f"Method: {method.replace('_', ' ').title()}\n"
                    f"Reference: {transaction_ref}")
                payment_window.destroy()
                self._load_appointments()

            except Exception as e:
                logger.error(f"Payment processing error: {e}")
                messagebox.showerror("Error", f"Payment failed: {str(e)}")

        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(btn_frame, text="Confirm Payment",
                  command=confirm_payment).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel",
                  command=payment_window.destroy).pack(side=tk.RIGHT, padx=5)

    def _send_payment_receipt(self, appt: dict, total_amount: float, tip: float,
                              payment_method: str, transaction_ref: str,
                              customer_email: str, customer_name: str):
        """Send payment receipt email to customer."""
        try:
            from education_system.university_system.infrastructure.email.template_utils import render_template

            # Render email from template
            subject, body = render_template('commerce/barber/payment_receipt', {
                'customer_name': customer_name,
                'appointment_number': appt['appointment_number'],
                'service_name': appt['service_name'],
                'barber_name': appt.get('staff_name', 'Any available'),
                'appointment_date': appt.get('appointment_date', datetime.now().strftime('%Y-%m-%d')),
                'appointment_time': appt.get('appointment_time', ''),
                'service_price': f"£{appt['price']:.2f}",
                'tip_amount': f"£{tip:.2f}",
                'total_amount': f"£{total_amount:.2f}",
                'payment_method': payment_method.replace('_', ' ').title(),
                'transaction_ref': transaction_ref
            })

            # Fallback if template not found
            if not subject or not body:
                subject = f"Barber Shop Receipt - {appt['appointment_number']}"
                body = f"Dear {customer_name},\n\nThank you for your payment of £{total_amount:.2f}.\nReference: {transaction_ref}"

            # Try to send email
            try:
                from education_system.university_system.infrastructure.email.email_service import send_email as send_email_func
                send_email_func(customer_email, subject, body)
                logger.info(f"Receipt sent to {customer_email}")
            except ImportError:
                logger.warning("Email service not available - receipt not sent")
            except Exception as email_err:
                logger.error(f"Email sending failed: {email_err}")

        except Exception as e:
            logger.error(f"Failed to prepare receipt email: {e}")

    def send_receipt_email(self, appointment: dict, transaction_id: int, tip: float = 0):
        """Send receipt email to customer."""
        try:
            from education_system.university_system.infrastructure.email.email_service import send_email

            total = appointment['price'] + tip
            subject = _t("barber.email.receipt_subject").format(appointment_number=appointment['appointment_number'])

            body = _t("barber.email.receipt_body").format(
                customer_name=appointment['customer_name'],
                appointment_number=appointment['appointment_number'],
                service=appointment['service_name'],
                barber=appointment.get('staff_name', 'N/A'),
                service_price=f"£{appointment['price']:.2f}",
                tip=f"£{tip:.2f}",
                total=f"£{total:.2f}",
                date=datetime.now().strftime('%Y-%m-%d %H:%M')
            )

            send_email(
                recipient_email=appointment['customer_email'],
                subject=subject,
                body=body
            )

            from education_system.university_system.modules.domain.barber.services.barber_core import TransactionManager
            TransactionManager.mark_receipt_sent(transaction_id)

            logger.info(f"Receipt sent to {appointment['customer_email']}")

        except Exception as e:
            logger.error(f"Failed to send receipt: {e}")

    def cancel_appointment(self):
        """Cancel an appointment."""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("barber.errors.select_appointment"))
            return

        if not messagebox.askyesno(_t("common.confirm"), _t("barber.confirm.cancel_appointment")):
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        try:
            from education_system.university_system.modules.domain.barber.services.barber_core import AppointmentManager
            appt = AppointmentManager.get_appointment_by_number(appt_number)

            if appt:
                AppointmentManager.cancel_appointment(appt['appointment_id'], 'Cancelled by user')
                log_activity('cancel', 'barber_appointment',
                            details={'appointment_id': appt['appointment_id']})
                messagebox.showinfo(_t("common.success"), _t("barber.messages.appointment_cancelled"))
                self._load_appointments()

        except Exception as e:
            messagebox.showerror(_t("common.error"), str(e))

    def reschedule_appointment(self):
        """Reschedule an appointment."""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning(_t("common.warning"), _t("barber.errors.select_appointment"))
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        from education_system.university_system.modules.domain.barber.services.barber_core import AppointmentManager
        appt = AppointmentManager.get_appointment_by_number(appt_number)

        if not appt:
            return

        # Reschedule dialog
        resched_window = tk.Toplevel(self.parent)
        resched_window.title(_t("barber.labels.reschedule"))
        resched_window.geometry("350x200")
        resched_window.transient(self.parent)
        resched_window.grab_set()

        ttk.Label(resched_window, text=f"{_t('barber.labels.appointment')}: {appt_number}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(resched_window)
        frame.pack(pady=10)

        ttk.Label(frame, text=_t("barber.labels.new_date") + ":").grid(row=0, column=0, pady=5)
        new_date_var = tk.StringVar(value=appt['appointment_date'])
        ttk.Entry(frame, textvariable=new_date_var, width=12).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text=_t("barber.labels.new_time") + ":").grid(row=1, column=0, pady=5)
        new_time_combo = ttk.Combobox(frame, state="readonly", width=10)
        new_time_combo['values'] = self._get_time_slots()
        new_time_combo.set(appt['appointment_time'])
        new_time_combo.grid(row=1, column=1, pady=5)

        def confirm_reschedule():
            new_date = new_date_var.get().strip()
            new_time = new_time_combo.get()

            try:
                AppointmentManager.reschedule_appointment(appt['appointment_id'], new_date, new_time)
                log_activity('reschedule', 'barber_appointment',
                            details={'appointment_id': appt['appointment_id']})

                # Send email confirmation to customer
                if appt.get('customer_email') and EMAIL_AVAILABLE:
                    try:
                        from education_system.university_system.infrastructure.email.email_service import send_email
                        from education_system.university_system.infrastructure.email.template_utils import render_template

                        # Format the date nicely
                        from datetime import datetime as dt
                        try:
                            date_obj = dt.strptime(new_date, '%Y-%m-%d')
                            formatted_date = date_obj.strftime('%A, %B %d, %Y')
                        except (ValueError, TypeError):
                            formatted_date = new_date

                        # Get old date/time for reference
                        try:
                            old_date_obj = dt.strptime(appt['appointment_date'], '%Y-%m-%d')
                            old_formatted_date = old_date_obj.strftime('%A, %B %d, %Y')
                        except (ValueError, TypeError):
                            old_formatted_date = appt['appointment_date']

                        # Render email from template
                        subject, body = render_template('commerce/barber/appointment_rescheduled', {
                            'customer_name': appt['customer_name'],
                            'old_date': old_formatted_date,
                            'old_time': appt['appointment_time'],
                            'new_date': formatted_date,
                            'new_time': new_time,
                            'barber_name': appt.get('staff_name', 'Any available')
                        })

                        # Fallback if template not found
                        if not subject or not body:
                            subject = "Appointment Rescheduled - Barber Shop"
                            body = f"Dear {appt['customer_name']},\n\nYour appointment has been rescheduled to {formatted_date} at {new_time}."

                        send_email(
                            recipient_email=appt['customer_email'],
                            subject=subject,
                            body=body
                        )
                        logger.info(f"Reschedule confirmation email sent to {appt['customer_email']}")
                    except Exception as email_err:
                        logger.warning(f"Failed to send reschedule email: {email_err}")
                        # Don't fail the whole reschedule if email fails

                messagebox.showinfo(_t("common.success"),
                                  _t("barber.messages.appointment_rescheduled") + "\n" +
                                  ("Email confirmation sent!" if appt.get('customer_email') and EMAIL_AVAILABLE else ""))
                resched_window.destroy()
                self._load_appointments()
            except Exception as e:
                messagebox.showerror(_t("common.error"), str(e))

        ttk.Button(resched_window, text=_t("barber.btn.confirm_reschedule"),
                  command=confirm_reschedule).pack(pady=20)

    def generate_admin_report(self):
        """Generate admin report."""
        try:
            from education_system.university_system.modules.domain.barber.services.barber_core import ReportManager
            report = ReportManager.generate_admin_report()

            self.report_text.delete("1.0", tk.END)
            self.report_text.insert("1.0", report)

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("barber.errors.report_failed").format(error=str(e)))

    def email_admin_report(self):
        """Email admin report."""
        report_content = self.report_text.get("1.0", tk.END).strip()

        if not report_content:
            self.generate_admin_report()
            report_content = self.report_text.get("1.0", tk.END).strip()

        try:
            from education_system.university_system.infrastructure.email.email_service import send_email

            with get_db_connection() as conn:
                admin = conn.execute(
                    "SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL LIMIT 1"
                ).fetchone()

            if admin and admin['email']:
                send_email(
                    recipient_email=admin['email'],
                    subject=f"Barber Shop Admin Report - {datetime.now().strftime('%Y-%m-%d')}",
                    body=report_content
                )

                log_activity('email', 'barber_report', user_id=self.current_user.get('user_id'))
                messagebox.showinfo(_t("common.success"), _t("barber.messages.report_emailed"))
            else:
                messagebox.showwarning(_t("common.warning"), _t("barber.errors.no_admin_email"))

        except Exception as e:
            messagebox.showerror(_t("common.error"), _t("barber.errors.email_failed").format(error=str(e)))

    # ==================== ADVANCED APPOINTMENT FEATURES ====================

    def view_appointment_history(self):
        """View appointment history for selected customer or all."""
        history_window = tk.Toplevel(self.parent)
        history_window.title("Appointment History")
        history_window.geometry("800x500")
        history_window.transient(self.parent)

        # Filter frame
        filter_frame = ttk.Frame(history_window, padding="10")
        filter_frame.pack(fill=tk.X)

        ttk.Label(filter_frame, text="Customer ID:").pack(side=tk.LEFT)
        customer_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=customer_var, width=20).pack(side=tk.LEFT, padx=5)

        ttk.Label(filter_frame, text="From:").pack(side=tk.LEFT, padx=(20, 5))
        from_var = tk.StringVar(value=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
        ttk.Entry(filter_frame, textvariable=from_var, width=12).pack(side=tk.LEFT)

        ttk.Label(filter_frame, text="To:").pack(side=tk.LEFT, padx=(10, 5))
        to_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(filter_frame, textvariable=to_var, width=12).pack(side=tk.LEFT)

        # History list
        columns = ('date', 'time', 'customer', 'service', 'barber', 'status', 'amount')
        tree = ttk.Treeview(history_window, columns=columns, show='headings', height=18)

        for col in columns:
            tree.heading(col, text=col.title())
            tree.column(col, width=100)

        scrollbar = ttk.Scrollbar(history_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        def load_history():
            for item in tree.get_children():
                tree.delete(item)
            try:
                with get_db_connection() as conn:
                    query = """
                        SELECT a.appointment_date, a.appointment_time, a.customer_name,
                               s.name as service_name, st.name as staff_name, a.status,
                               COALESCE(t.amount, s.price) as amount
                        FROM barber_appointments a
                        LEFT JOIN barber_services s ON a.service_id = s.service_id
                        LEFT JOIN barber_staff st ON a.staff_id = st.staff_id
                        LEFT JOIN barber_transactions t ON a.appointment_id = t.appointment_id
                        WHERE a.appointment_date BETWEEN ? AND ?
                    """
                    params = [from_var.get(), to_var.get()]
                    if customer_var.get().strip():
                        query += " AND a.customer_id = ?"
                        params.append(customer_var.get().strip())
                    query += " ORDER BY a.appointment_date DESC, a.appointment_time DESC"

                    rows = conn.execute(query, params).fetchall()
                    for row in rows:
                        tree.insert('', tk.END, values=(
                            row['appointment_date'], row['appointment_time'],
                            row['customer_name'], row['service_name'] or 'N/A',
                            row['staff_name'] or 'Any', row['status'],
                            f"£{row['amount']:.2f}" if row['amount'] else 'N/A'
                        ))
            except Exception as e:
                logger.error(f"Error loading history: {e}")

        ttk.Button(filter_frame, text="Search", command=load_history).pack(side=tk.LEFT, padx=20)
        load_history()

    def show_weekly_calendar(self):
        """Show weekly calendar view of appointments."""
        cal_window = tk.Toplevel(self.parent)
        cal_window.title("Weekly Calendar")
        cal_window.geometry("1000x600")
        cal_window.transient(self.parent)

        # Week navigation
        nav_frame = ttk.Frame(cal_window, padding="10")
        nav_frame.pack(fill=tk.X)

        current_week_start = datetime.now() - timedelta(days=datetime.now().weekday())
        week_var = tk.StringVar(value=current_week_start.strftime('%Y-%m-%d'))

        def prev_week():
            date = datetime.strptime(week_var.get(), '%Y-%m-%d') - timedelta(days=7)
            week_var.set(date.strftime('%Y-%m-%d'))
            load_week()

        def next_week():
            date = datetime.strptime(week_var.get(), '%Y-%m-%d') + timedelta(days=7)
            week_var.set(date.strftime('%Y-%m-%d'))
            load_week()

        ttk.Button(nav_frame, text="< Prev", command=prev_week).pack(side=tk.LEFT)
        ttk.Label(nav_frame, textvariable=week_var, font=('Helvetica', 12, 'bold')).pack(side=tk.LEFT, padx=20)
        ttk.Button(nav_frame, text="Next >", command=next_week).pack(side=tk.LEFT)

        # Calendar grid
        cal_frame = ttk.Frame(cal_window, padding="10")
        cal_frame.pack(fill=tk.BOTH, expand=True)

        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        day_frames = []

        for i, day in enumerate(days):
            col_frame = ttk.LabelFrame(cal_frame, text=day, padding="5")
            col_frame.grid(row=0, column=i, sticky='nsew', padx=2, pady=2)
            cal_frame.columnconfigure(i, weight=1)
            day_frames.append(col_frame)

        cal_frame.rowconfigure(0, weight=1)

        def load_week():
            for frame in day_frames:
                for widget in frame.winfo_children():
                    widget.destroy()

            start = datetime.strptime(week_var.get(), '%Y-%m-%d')
            try:
                with get_db_connection() as conn:
                    for i in range(7):
                        day_date = (start + timedelta(days=i)).strftime('%Y-%m-%d')
                        appointments = conn.execute("""
                            SELECT appointment_time, customer_name, status
                            FROM barber_appointments
                            WHERE appointment_date = ?
                            ORDER BY appointment_time
                        """, (day_date,)).fetchall()

                        ttk.Label(day_frames[i], text=day_date, font=('Helvetica', 8)).pack()
                        for appt in appointments:
                            color = 'green' if appt['status'] == 'completed' else 'blue'
                            lbl = ttk.Label(day_frames[i],
                                          text=f"{appt['appointment_time']}\n{appt['customer_name'][:15]}",
                                          foreground=color)
                            lbl.pack(pady=2)
            except Exception as e:
                logger.error(f"Error loading week: {e}")

        load_week()

    def bulk_cancel_appointments(self):
        """Bulk cancel appointments."""
        cancel_window = tk.Toplevel(self.parent)
        cancel_window.title("Bulk Cancel Appointments")
        cancel_window.geometry("500x400")
        cancel_window.transient(self.parent)
        cancel_window.grab_set()

        ttk.Label(cancel_window, text="Bulk Cancel Appointments",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        # Options
        options_frame = ttk.LabelFrame(cancel_window, text="Cancel Options", padding="10")
        options_frame.pack(fill=tk.X, padx=20, pady=10)

        ttk.Label(options_frame, text="Date:").grid(row=0, column=0, sticky=tk.W, pady=5)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(options_frame, textvariable=date_var, width=15).grid(row=0, column=1, pady=5)

        ttk.Label(options_frame, text="Staff ID (optional):").grid(row=1, column=0, sticky=tk.W, pady=5)
        staff_var = tk.StringVar()
        ttk.Entry(options_frame, textvariable=staff_var, width=15).grid(row=1, column=1, pady=5)

        ttk.Label(options_frame, text="Reason:").grid(row=2, column=0, sticky=tk.W, pady=5)
        reason_var = tk.StringVar(value="Staff unavailable")
        ttk.Entry(options_frame, textvariable=reason_var, width=30).grid(row=2, column=1, pady=5)

        notify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_frame, text="Notify customers via email",
                       variable=notify_var).grid(row=3, column=0, columnspan=2, pady=5)

        result_text = tk.Text(cancel_window, height=10, width=50)
        result_text.pack(padx=20, pady=10)

        def execute_cancel():
            if not messagebox.askyesno("Confirm", "Are you sure you want to cancel these appointments?"):
                return
            try:
                with transaction() as conn:
                    query = """
                        SELECT appointment_id, customer_name, customer_email, appointment_time
                        FROM barber_appointments
                        WHERE appointment_date = ? AND status IN ('scheduled', 'checked_in')
                    """
                    params = [date_var.get()]
                    if staff_var.get().strip():
                        query += " AND staff_id = ?"
                        params.append(int(staff_var.get()))

                    appointments = conn.execute(query, params).fetchall()

                    cancelled = 0
                    for appt in appointments:
                        conn.execute("""
                            UPDATE barber_appointments
                            SET status = 'cancelled', cancellation_reason = ?
                            WHERE appointment_id = ?
                        """, (reason_var.get(), appt['appointment_id']))
                        cancelled += 1

                        if notify_var.get() and appt['customer_email'] and EMAIL_AVAILABLE:
                            try:
                                from education_system.university_system.infrastructure.email.email_service import send_email
                                from education_system.university_system.infrastructure.email.template_utils import render_template

                                subject, body = render_template('commerce/barber/appointment_cancelled', {
                                    'customer_name': appt['customer_name'],
                                    'appointment_date': date_var.get(),
                                    'appointment_time': appt['appointment_time'],
                                    'cancellation_reason': reason_var.get()
                                })

                                if not subject or not body:
                                    subject = "Appointment Cancelled"
                                    body = f"Dear {appt['customer_name']},\n\nYour appointment has been cancelled.\nReason: {reason_var.get()}"

                                send_email(appt['customer_email'], subject, body)
                            except Exception:
                                pass

                    log_activity('bulk_cancel', 'barber_appointments',
                                details={'count': cancelled, 'date': date_var.get()})

                result_text.delete('1.0', tk.END)
                result_text.insert('1.0', f"Successfully cancelled {cancelled} appointments.")
                self._load_appointments()

            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(cancel_window, text="Cancel Appointments", command=execute_cancel).pack(pady=10)

    def set_appointment_reminder(self):
        """Set reminder for appointment."""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an appointment.")
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        reminder_window = tk.Toplevel(self.parent)
        reminder_window.title("Set Reminder")
        reminder_window.geometry("400x300")
        reminder_window.transient(self.parent)
        reminder_window.grab_set()

        ttk.Label(reminder_window, text=f"Set Reminder for {appt_number}",
                 font=('Helvetica', 12, 'bold')).pack(pady=10)

        frame = ttk.Frame(reminder_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Reminder Type:").grid(row=0, column=0, sticky=tk.W, pady=5)
        type_var = tk.StringVar(value="email")
        ttk.Radiobutton(frame, text="Email", variable=type_var, value="email").grid(row=0, column=1, sticky=tk.W)
        ttk.Radiobutton(frame, text="SMS", variable=type_var, value="sms").grid(row=1, column=1, sticky=tk.W)

        ttk.Label(frame, text="Hours Before:").grid(row=2, column=0, sticky=tk.W, pady=5)
        hours_var = tk.StringVar(value="24")
        ttk.Combobox(frame, textvariable=hours_var, values=['1', '2', '4', '12', '24', '48'],
                    width=10).grid(row=2, column=1, sticky=tk.W)

        ttk.Label(frame, text="Message:").grid(row=3, column=0, sticky=tk.W, pady=5)
        msg_text = tk.Text(frame, height=4, width=30)
        msg_text.grid(row=3, column=1, pady=5)
        msg_text.insert('1.0', "Don't forget your appointment!")

        def save_reminder():
            try:
                from education_system.university_system.modules.domain.barber.services.barber_core import (
                    AppointmentManager, ReminderManager
                )
                appt = AppointmentManager.get_appointment_by_number(appt_number)
                if appt:
                    # Calculate send_at time (appointment datetime minus hours_before)
                    appt_datetime = datetime.strptime(
                        f"{appt['appointment_date']} {appt['appointment_time']}",
                        '%Y-%m-%d %H:%M'
                    )
                    send_at = appt_datetime - timedelta(hours=int(hours_var.get()))
                    send_at_str = send_at.strftime('%Y-%m-%d %H:%M:%S')

                    ReminderManager.schedule_reminder(
                        appointment_id=appt['appointment_id'],
                        reminder_type=type_var.get(),
                        send_at=send_at_str,
                        channel='email'
                    )
                    messagebox.showinfo("Success", "Reminder scheduled successfully!")
                    reminder_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(reminder_window, text="Save Reminder", command=save_reminder).pack(pady=10)

    def mark_no_show(self):
        """Mark appointment as no-show."""
        selected = self.appointments_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select an appointment.")
            return

        item = self.appointments_tree.item(selected[0])
        appt_number = item['values'][0]

        if not messagebox.askyesno("Confirm", f"Mark appointment {appt_number} as no-show?"):
            return

        try:
            from education_system.university_system.modules.domain.barber.services.barber_core import (
                AppointmentManager, NoShowManager
            )
            appt = AppointmentManager.get_appointment_by_number(appt_number)
            if appt:
                # Get current user for marked_by parameter
                marked_by = self.current_user.get('username', 'admin')

                NoShowManager.mark_no_show(
                    appointment_id=appt['appointment_id'],
                    marked_by=marked_by,
                    add_to_watchlist=False
                )
                log_activity('no_show', 'barber_appointment',
                            details={'appointment_id': appt['appointment_id']})
                messagebox.showinfo("Success", "Appointment marked as no-show.")
                self._load_appointments()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def view_waitlist(self):
        """View waitlist."""
        waitlist_window = tk.Toplevel(self.parent)
        waitlist_window.title("Waitlist")
        waitlist_window.geometry("700x400")
        waitlist_window.transient(self.parent)

        columns = ('id', 'customer', 'service', 'preferred_date', 'preferred_time', 'status', 'added')
        tree = ttk.Treeview(waitlist_window, columns=columns, show='headings', height=15)

        for col in columns:
            tree.heading(col, text=col.replace('_', ' ').title())
            tree.column(col, width=90)

        scrollbar = ttk.Scrollbar(waitlist_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=10)

        def load_waitlist():
            for item in tree.get_children():
                tree.delete(item)
            try:
                from education_system.university_system.modules.domain.barber.services.barber_core import WaitlistManager
                # get_waitlist() filters to status='waiting' by default
                entries = WaitlistManager.get_waitlist()
                for entry in entries:
                    tree.insert('', tk.END, values=(
                        entry['waitlist_id'], entry['customer_name'],
                        entry.get('service_name', 'Any'), entry['preferred_date'],
                        entry.get('preferred_time', 'Any'), entry['status'], entry['created_at'][:10]
                    ))
            except Exception as e:
                logger.error(f"Error loading waitlist: {e}")

        btn_frame = ttk.Frame(waitlist_window)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(btn_frame, text="Refresh", command=load_waitlist).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Notify Selected", command=lambda: self._notify_waitlist_entry(tree)).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Remove Selected", command=lambda: self._remove_waitlist_entry(tree, load_waitlist)).pack(side=tk.LEFT, padx=5)

        load_waitlist()

    def _notify_waitlist_entry(self, tree):
        """Helper to notify waitlist entry."""
        selected = tree.selection()
        if not selected:
            return
        item = tree.item(selected[0])
        waitlist_id = item['values'][0]

        # Prompt for available slot
        slot_window = tk.Toplevel(self.parent)
        slot_window.title("Available Slot")
        slot_window.geometry("300x150")
        slot_window.transient(self.parent)
        slot_window.grab_set()

        ttk.Label(slot_window, text="Enter available slot:").pack(pady=10)

        slot_frame = ttk.Frame(slot_window, padding="10")
        slot_frame.pack()

        ttk.Label(slot_frame, text="Date:").grid(row=0, column=0, sticky=tk.W, pady=5)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(slot_frame, textvariable=date_var, width=15).grid(row=0, column=1, pady=5)

        ttk.Label(slot_frame, text="Time:").grid(row=1, column=0, sticky=tk.W, pady=5)
        time_combo = ttk.Combobox(slot_frame, values=self._get_time_slots(), width=12)
        time_combo.grid(row=1, column=1, pady=5)

        def confirm_notify():
            if not time_combo.get():
                messagebox.showerror("Error", "Please select a time.")
                return

            available_slot = f"{date_var.get()} {time_combo.get()}"
            try:
                from education_system.university_system.modules.domain.barber.services.barber_core import WaitlistManager

                # Get customer details from waitlist entry
                with get_db_connection() as conn:
                    waitlist_entry = conn.execute('''
                        SELECT w.*, s.name as service_name
                        FROM barber_waitlist w
                        LEFT JOIN barber_services s ON w.service_id = s.service_id
                        WHERE w.waitlist_id = ?
                    ''', (waitlist_id,)).fetchone()

                if not waitlist_entry:
                    messagebox.showerror("Error", "Waitlist entry not found.")
                    return

                # Update waitlist status
                WaitlistManager.notify_waitlist(waitlist_id, available_slot)

                # Send notification email
                customer_email = waitlist_entry['customer_email']
                customer_name = waitlist_entry['customer_name']
                service_name = waitlist_entry['service_name'] or 'Your requested service'

                if customer_email:
                    try:
                        from education_system.university_system.infrastructure.email.email_service import send_email
                        from education_system.university_system.infrastructure.email.template_utils import render_template

                        subject, body = render_template('commerce/barber/waitlist_availability', {
                            'customer_name': customer_name,
                            'available_date': date_var.get(),
                            'available_time': time_combo.get(),
                            'barber_name': 'Any available',
                            'service_name': service_name
                        })

                        if not subject or not body:
                            subject = "Barber Shop - Appointment Slot Available!"
                            body = f"Dear {customer_name},\n\nAn appointment slot is available on {date_var.get()} at {time_combo.get()}."

                        send_email(
                            recipient_email=customer_email,
                            subject=subject,
                            body=body
                        )
                        logger.info(f"Availability notification email sent to {customer_email}")
                    except Exception as e:
                        logger.error(f"Failed to send availability notification email: {e}")
                        # Don't fail the whole operation if email fails

                messagebox.showinfo("Success", f"Customer notified of available slot: {available_slot}\nEmail sent to: {customer_email if customer_email else 'No email on file'}")
                slot_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(slot_window, text="Notify", command=confirm_notify).pack(pady=10)

    def _remove_waitlist_entry(self, tree, reload_func):
        """Helper to remove waitlist entry."""
        selected = tree.selection()
        if not selected:
            return
        item = tree.item(selected[0])
        waitlist_id = item['values'][0]
        try:
            from education_system.university_system.modules.domain.barber.services.barber_core import WaitlistManager
            WaitlistManager.remove_from_waitlist(waitlist_id)
            reload_func()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def add_to_waitlist(self):
        """Add customer to waitlist."""
        waitlist_window = tk.Toplevel(self.parent)
        waitlist_window.title("Add to Waitlist")
        waitlist_window.geometry("400x350")
        waitlist_window.transient(self.parent)
        waitlist_window.grab_set()

        ttk.Label(waitlist_window, text="Add to Waitlist",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(waitlist_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        # Use current user
        customer_id = (self.current_user.get('student_id') or
                      self.current_user.get('username') or
                      str(self.current_user.get('id', '')))
        customer_name = self.current_user.get('full_name') or self.current_user.get('username', 'Guest')

        ttk.Label(frame, text=f"Customer: {customer_name}").grid(row=0, column=0, columnspan=2, pady=5)

        ttk.Label(frame, text="Service:").grid(row=1, column=0, sticky=tk.W, pady=5)
        service_combo = ttk.Combobox(frame, state="readonly", width=25)
        service_combo['values'] = self.appt_service_combo['values']
        service_combo.grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Preferred Date:").grid(row=2, column=0, sticky=tk.W, pady=5)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(frame, textvariable=date_var, width=15).grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Preferred Time:").grid(row=3, column=0, sticky=tk.W, pady=5)
        time_combo = ttk.Combobox(frame, values=self._get_time_slots(), width=10)
        time_combo.grid(row=3, column=1, pady=5)

        ttk.Label(frame, text="Notes:").grid(row=4, column=0, sticky=tk.W, pady=5)
        notes_text = tk.Text(frame, height=3, width=25)
        notes_text.grid(row=4, column=1, pady=5)

        def add_entry():
            try:
                service_id = None
                service_name = "Any Service"
                if service_combo.get():
                    service_id = int(service_combo.get().split(':')[0])
                    service_name = service_combo.get().split(':', 1)[1].strip()

                # Get customer email and phone from current user
                customer_email = self.current_user.get('email', '')
                customer_phone = self.current_user.get('phone', '')

                from education_system.university_system.modules.domain.barber.services.barber_core import WaitlistManager
                WaitlistManager.add_to_waitlist(
                    customer_id=customer_id,
                    customer_name=customer_name,
                    customer_email=customer_email,
                    customer_phone=customer_phone,
                    preferred_date=date_var.get(),
                    preferred_time=time_combo.get(),
                    service_id=service_id,
                    notes=notes_text.get('1.0', tk.END).strip()
                )

                # Send confirmation email
                if customer_email:
                    try:
                        from education_system.university_system.infrastructure.email.email_service import send_email
                        from education_system.university_system.infrastructure.email.template_utils import render_template

                        subject, body = render_template('commerce/barber/waitlist_confirmation', {
                            'customer_name': customer_name,
                            'service_name': service_name,
                            'preferred_barber': 'Any available',
                            'waitlist_position': 'Next available'
                        })

                        if not subject or not body:
                            subject = "Barber Shop - Added to Waitlist"
                            body = f"Dear {customer_name},\n\nYou have been added to our waitlist for {service_name}."

                        send_email(
                            recipient_email=customer_email,
                            subject=subject,
                            body=body
                        )
                        logger.info(f"Waitlist confirmation email sent to {customer_email}")
                    except Exception as e:
                        logger.error(f"Failed to send waitlist confirmation email: {e}")
                        # Don't fail the whole operation if email fails

                messagebox.showinfo("Success", "Added to waitlist! Confirmation email sent.")
                waitlist_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(waitlist_window, text="Add to Waitlist", command=add_entry).pack(pady=10)

    def notify_waitlist_availability(self):
        """Notify waitlist about availability."""
        try:
            from education_system.university_system.modules.domain.barber.services.barber_core import WaitlistManager
            count = WaitlistManager.notify_available_slots()
            messagebox.showinfo("Success", f"Notified {count} customers about availability.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def block_time_slot(self):
        """Block time slot."""
        block_window = tk.Toplevel(self.parent)
        block_window.title("Block Time Slot")
        block_window.geometry("400x350")
        block_window.transient(self.parent)
        block_window.grab_set()

        ttk.Label(block_window, text="Block Time Slot",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(block_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Date:").grid(row=0, column=0, sticky=tk.W, pady=5)
        date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        ttk.Entry(frame, textvariable=date_var, width=15).grid(row=0, column=1, pady=5)

        ttk.Label(frame, text="Start Time:").grid(row=1, column=0, sticky=tk.W, pady=5)
        start_combo = ttk.Combobox(frame, values=self._get_time_slots(), width=10)
        start_combo.grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="End Time:").grid(row=2, column=0, sticky=tk.W, pady=5)
        end_combo = ttk.Combobox(frame, values=self._get_time_slots(), width=10)
        end_combo.grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Staff (optional):").grid(row=3, column=0, sticky=tk.W, pady=5)
        staff_combo = ttk.Combobox(frame, values=self.appt_staff_combo['values'], width=20)
        staff_combo.grid(row=3, column=1, pady=5)

        ttk.Label(frame, text="Reason:").grid(row=4, column=0, sticky=tk.W, pady=5)
        reason_var = tk.StringVar(value="Break")
        ttk.Entry(frame, textvariable=reason_var, width=25).grid(row=4, column=1, pady=5)

        def block_slot():
            try:
                staff_id = None
                if staff_combo.get() and staff_combo.get() != 'Any':
                    staff_id = int(staff_combo.get().split(':')[0])

                from education_system.university_system.modules.domain.barber.services.barber_core import BlockedSlotManager
                # Get current user for blocked_by parameter
                blocked_by = self.current_user.get('username', 'admin')

                BlockedSlotManager.block_slot(
                    staff_id=staff_id,
                    date=date_var.get(),
                    start_time=start_combo.get(),
                    end_time=end_combo.get(),
                    reason=reason_var.get(),
                    blocked_by=blocked_by
                )
                messagebox.showinfo("Success", "Time slot blocked!")
                block_window.destroy()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(block_window, text="Block Slot", command=block_slot).pack(pady=10)

    def recurring_appointment(self):
        """Create recurring appointment."""
        recurring_window = tk.Toplevel(self.parent)
        recurring_window.title("Recurring Appointment")
        recurring_window.geometry("450x450")
        recurring_window.transient(self.parent)
        recurring_window.grab_set()

        ttk.Label(recurring_window, text="Create Recurring Appointment",
                 font=('Helvetica', 14, 'bold')).pack(pady=10)

        frame = ttk.Frame(recurring_window, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)

        customer_name = self.current_user.get('full_name') or self.current_user.get('username', 'Guest')
        ttk.Label(frame, text=f"Customer: {customer_name}").grid(row=0, column=0, columnspan=2, pady=5)

        ttk.Label(frame, text="Service:").grid(row=1, column=0, sticky=tk.W, pady=5)
        service_combo = ttk.Combobox(frame, state="readonly", width=25)
        service_combo['values'] = self.appt_service_combo['values']
        service_combo.grid(row=1, column=1, pady=5)

        ttk.Label(frame, text="Staff:").grid(row=2, column=0, sticky=tk.W, pady=5)
        staff_combo = ttk.Combobox(frame, values=self.appt_staff_combo['values'], width=20)
        staff_combo.set('Any')
        staff_combo.grid(row=2, column=1, pady=5)

        ttk.Label(frame, text="Preferred Day:").grid(row=3, column=0, sticky=tk.W, pady=5)
        day_combo = ttk.Combobox(frame, values=['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'], width=15)
        day_combo.grid(row=3, column=1, pady=5)

        ttk.Label(frame, text="Preferred Time:").grid(row=4, column=0, sticky=tk.W, pady=5)
        time_combo = ttk.Combobox(frame, values=self._get_time_slots(), width=10)
        time_combo.grid(row=4, column=1, pady=5)

        ttk.Label(frame, text="Frequency:").grid(row=5, column=0, sticky=tk.W, pady=5)
        freq_combo = ttk.Combobox(frame, values=['weekly', 'biweekly', 'monthly'], width=15)
        freq_combo.set('monthly')
        freq_combo.grid(row=5, column=1, pady=5)

        ttk.Label(frame, text="Number of Occurrences:").grid(row=6, column=0, sticky=tk.W, pady=5)
        count_var = tk.StringVar(value="6")
        ttk.Entry(frame, textvariable=count_var, width=10).grid(row=6, column=1, pady=5)

        def create_recurring():
            try:
                if not service_combo.get():
                    messagebox.showerror("Error", "Please select a service.")
                    return

                if not day_combo.get():
                    messagebox.showerror("Error", "Please select a day of the week.")
                    return

                if not time_combo.get():
                    messagebox.showerror("Error", "Please select a time.")
                    return

                customer_id = (self.current_user.get('student_id') or
                              self.current_user.get('username') or
                              str(self.current_user.get('id', '')))
                service_id = int(service_combo.get().split(':')[0])
                staff_id = None
                if staff_combo.get() and staff_combo.get() != 'Any':
                    staff_id = int(staff_combo.get().split(':')[0])

                # Convert day name to number (0=Monday, 6=Sunday)
                day_map = {
                    'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
                    'Friday': 4, 'Saturday': 5, 'Sunday': 6
                }
                day_of_week = day_map.get(day_combo.get())
                if day_of_week is None:
                    messagebox.showerror("Error", "Invalid day selected.")
                    return

                from education_system.university_system.modules.domain.barber.services.barber_core import RecurringAppointmentManager
                # Get customer email from current user
                customer_email = self.current_user.get('email', '')
                # Calculate start and end dates
                start_date = datetime.now().strftime('%Y-%m-%d')
                end_date = (datetime.now() + timedelta(days=int(count_var.get()) * 7)).strftime('%Y-%m-%d')

                RecurringAppointmentManager.create_recurring(
                    customer_id=customer_id,
                    customer_name=customer_name,
                    customer_email=customer_email,
                    service_id=service_id,
                    staff_id=staff_id,
                    day_of_week=day_of_week,
                    time=time_combo.get(),
                    frequency=freq_combo.get(),
                    start_date=start_date,
                    end_date=end_date
                )
                messagebox.showinfo("Success", "Recurring appointment created!")
                recurring_window.destroy()
                self._load_appointments()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(recurring_window, text="Create Recurring", command=create_recurring).pack(pady=10)
