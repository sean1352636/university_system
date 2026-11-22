"""Methods process_taxi_refund through send_taxi_refund_receipt."""

from .. import taxi_booking_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})

from education_system.systems.university.domains.operations.domain.campus.mobility.services import taxi_booking_service


class TaxiBookingApp:
    def process_taxi_refund(self):
        """Process a refund for selected taxi ticket"""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.warning", default="Warning"),
                                   _t("taxi.refunds.select_ticket", default="Please select a ticket to refund"))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']
        ticket_id = values[0]
        ticket_number = values[1]
        amount_str = values[5]
        status = values[7]

        # Check if already refunded
        if 'refund' in status.lower():
            messagebox.showwarning(_t("common.warning", default="Warning"),
                                   _t("taxi.refunds.already_refunded", default="This ticket has already been refunded"))
            return

        # Parse amount
        try:
            amount = float(amount_str.replace('£', '').replace(',', ''))
        except ValueError:
            messagebox.showerror(_t("common.error", default="Error"),
                                 _t("taxi.refunds.invalid_amount", default="Invalid amount format"))
            return

        # Show refund method dialog
        self.show_taxi_refund_method_dialog(ticket_id, ticket_number, amount)

    def show_taxi_refund_method_dialog(self, ticket_id, ticket_number, amount):
        """Show dialog to select refund method"""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("taxi.refunds.select_method", default="Select Refund Method"))
        dialog.geometry("500x450")
        dialog.configure(bg=ModernStyle.BG_PRIMARY)
        dialog.resizable(False, False)
        dialog.transient(self.root)

        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (dialog.winfo_screenheight() // 2) - (450 // 2)
        dialog.geometry(f"500x450+{x}+{y}")

        # Grab focus after window is positioned
        dialog.grab_set()

        # Content frame
        content_frame = tk.Frame(dialog, bg=ModernStyle.BG_CARD, padx=30, pady=30)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # Header
        tk.Label(content_frame, text="💸 " + _t("taxi.refunds.process_refund", default="Process Refund"),
                font=ModernStyle.FONT_TITLE, bg=ModernStyle.BG_CARD,
                fg=ModernStyle.TEXT_PRIMARY).pack(pady=(0, 20))

        # Ticket info
        info_frame = tk.Frame(content_frame, bg=ModernStyle.BG_SECONDARY, padx=15, pady=15)
        info_frame.pack(fill=tk.X, pady=(0, 20))

        tk.Label(info_frame, text=_t("taxi.refunds.ticket_number", default="Ticket Number") + f": {ticket_number}",
                font=ModernStyle.FONT_BODY, bg=ModernStyle.BG_SECONDARY,
                fg=ModernStyle.TEXT_PRIMARY).pack(anchor='w')
        tk.Label(info_frame, text=_t("taxi.refunds.refund_amount", default="Refund Amount") + f": £{amount:.2f}",
                font=("Segoe UI", 14, "bold"), bg=ModernStyle.BG_SECONDARY,
                fg=ModernStyle.SUCCESS).pack(anchor='w', pady=(5, 0))

        # Instructions
        tk.Label(content_frame, text=_t("taxi.refunds.select_method_instruction", default="Select refund method:"),
                font=ModernStyle.FONT_SUBTITLE, bg=ModernStyle.BG_CARD,
                fg=ModernStyle.TEXT_PRIMARY).pack(anchor='w', pady=(0, 10))

        # Get student account balance if available
        student_balance = None
        student_id = None
        if FINANCE_AVAILABLE and self.current_user:
            student_id = self._get_current_user_student_id()
            if student_id:
                student_balance = get_student_finance_account_balance(student_id)

        # Refund method buttons
        def select_cash():
            dialog.destroy()
            self._complete_taxi_refund(ticket_id, ticket_number, amount, "Cash", student_id)

        def select_card():
            dialog.destroy()
            self._complete_taxi_refund(ticket_id, ticket_number, amount, "Card", student_id)

        def select_student_account():
            dialog.destroy()
            self.add_taxi_refund_to_student_account(ticket_id, ticket_number, amount, student_id)

        # Cash button
        cash_btn = tk.Frame(content_frame, bg=ModernStyle.BG_SECONDARY, padx=15, pady=12, cursor="hand2")
        cash_btn.pack(fill=tk.X, pady=5)
        tk.Label(cash_btn, text="💵 " + _t("taxi.refunds.cash", default="Cash Refund"),
                font=ModernStyle.FONT_BUTTON, bg=ModernStyle.BG_SECONDARY,
                fg=ModernStyle.TEXT_PRIMARY, cursor="hand2").pack()
        cash_btn.bind("<Button-1>", lambda e: select_cash())

        # Card button
        card_btn = tk.Frame(content_frame, bg=ModernStyle.BG_SECONDARY, padx=15, pady=12, cursor="hand2")
        card_btn.pack(fill=tk.X, pady=5)
        tk.Label(card_btn, text="💳 " + _t("taxi.refunds.card", default="Card Refund"),
                font=ModernStyle.FONT_BUTTON, bg=ModernStyle.BG_SECONDARY,
                fg=ModernStyle.TEXT_PRIMARY, cursor="hand2").pack()
        card_btn.bind("<Button-1>", lambda e: select_card())

        # Student account button
        student_btn = tk.Frame(content_frame, bg=ModernStyle.BG_SECONDARY, padx=15, pady=12, cursor="hand2")
        student_btn.pack(fill=tk.X, pady=5)

        student_text = _t("taxi.refunds.student_account", default="Student Finance Account")
        if student_balance is not None:
            student_text += f" (£{student_balance:.2f})"

        tk.Label(student_btn, text="🎓 " + student_text,
                font=ModernStyle.FONT_BUTTON, bg=ModernStyle.BG_SECONDARY,
                fg=ModernStyle.TEXT_PRIMARY, cursor="hand2").pack()

        if student_id and FINANCE_AVAILABLE:
            student_btn.bind("<Button-1>", lambda e: select_student_account())
        else:
            student_btn.configure(bg=ModernStyle.BORDER)
            tk.Label(student_btn, text=_t("taxi.refunds.student_account_unavailable", default="(Not available)"),
                    font=ModernStyle.FONT_SMALL, bg=ModernStyle.BORDER,
                    fg=ModernStyle.TEXT_SECONDARY).pack()

        # Cancel button
        cancel_btn = self.create_button(content_frame, _t("common.cancel", default="Cancel"), dialog.destroy)
        cancel_btn.pack(fill=tk.X, pady=(20, 0))

    def _complete_taxi_refund(self, ticket_id, ticket_number, amount, refund_method, student_id):
        """Complete cash or card refund"""
        try:
            processed_by = self.current_user.get('username', 'System') if self.current_user else 'System'

            # The service writes the refund once and posts it to Finance.
            outcome = taxi_booking_service.process_refund(
                ticket_id, ticket_number, amount, refund_method, student_id=student_id,
                processed_by=processed_by,
            )
            refund_ref = outcome['refund_ref']

            # Send refund receipt email
            self.send_taxi_refund_receipt(ticket_number, refund_ref, amount, refund_method, None, None)

            # Notify finance GUI
            self.notify_taxi_finance_gui(refund_ref, amount, refund_method, ticket_number)

            # Show success message
            messagebox.showinfo(_t("common.success", default="Success"),
                                _t("taxi.refunds.success_message", default=f"Refund processed successfully!\n\nRefund Reference: {refund_ref}\nAmount: £{amount:.2f}\nMethod: {refund_method}"))

            # Refresh the list
            self.refresh_refunds_list()

        except Exception as e:
            logger.error(f"Error processing taxi refund: {e}")
            messagebox.showerror(_t("common.error", default="Error"),
                                 _t("taxi.refunds.error_processing", default=f"Error processing refund: {str(e)}"))

    def add_taxi_refund_to_student_account(self, ticket_id, ticket_number, amount, student_id):
        """Add refund to student finance account"""
        if not FINANCE_AVAILABLE:
            messagebox.showerror(_t("common.error", default="Error"),
                                 _t("taxi.refunds.finance_unavailable", default="Student finance system is not available"))
            return

        if not student_id:
            messagebox.showerror(_t("common.error", default="Error"),
                                 _t("taxi.refunds.no_student_id", default="Student ID not found"))
            return

        try:
            processed_by = self.current_user.get('username', 'System') if self.current_user else 'System'

            # The service credits the student account, writes the refund once
            # and posts it to Finance.
            outcome = taxi_booking_service.process_refund(
                ticket_id, ticket_number, amount, 'Student Account', student_id=student_id,
                processed_by=processed_by,
            )
            refund_ref = outcome['refund_ref']
            old_balance = outcome['old_balance'] or 0.0
            new_balance = outcome['new_balance'] or 0.0

            # Send refund receipt email
            self.send_taxi_refund_receipt(ticket_number, refund_ref, amount, 'Student Account',
                                          old_balance, new_balance)

            # Notify finance GUI
            self.notify_taxi_finance_gui(refund_ref, amount, 'Student Account', ticket_number)

            # Show success message
            messagebox.showinfo(_t("common.success", default="Success"),
                                _t("taxi.refunds.student_account_success", default=f"Refund added to student account!\n\nRefund Reference: {refund_ref}\nAmount: £{amount:.2f}\n\nOld Balance: £{old_balance:.2f}\nNew Balance: £{new_balance:.2f}"))

            # Refresh the list
            self.refresh_refunds_list()

        except Exception as e:
            logger.error(f"Error adding taxi refund to student account: {e}")
            messagebox.showerror(_t("common.error", default="Error"),
                                 _t("taxi.refunds.error_student_account", default=f"Error adding refund to student account: {str(e)}"))

    def send_taxi_refund_receipt(self, ticket_number, refund_ref, amount, refund_method, old_balance, new_balance):
        """Send refund receipt via email"""
        if not EMAIL_AVAILABLE:
            logger.warning("Email service not available")
            return False

        try:
            # Get user email
            user_email = None
            student_id = self._get_current_user_student_id()

            if self.current_user and self.current_user.get('email'):
                user_email = self.current_user['email']
            elif student_id and FINANCE_AVAILABLE:
                user_email = get_student_email(student_id)

            if not user_email:
                logger.warning("No email address found for refund receipt")
                return False

            # Build email content
            customer_name = self.current_user.get('full_name', 'Valued Customer') if self.current_user else 'Valued Customer'

            # Try to use template first, fall back to i18n-based email
            try:
                if TEMPLATE_AVAILABLE:
                    subject, body = render_template('taxi_refund_receipt', {
                        'customer_name': customer_name,
                        'booking_id': ticket_number,
                        'refund_amount': f"{amount:.2f}",
                        'refund_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'payment_method': refund_method,
                        'refund_id': refund_ref
                    })
                else:
                    raise Exception("Template not available")
            except Exception as template_error:
                logger.warning(f"Failed to render template: {template_error}. Using i18n-based email.")
                # Fallback to i18n-based email
                subject = _t("taxi.refunds.email_subject", default=f"Taxi Booking Refund Receipt - {refund_ref}")
                body = f"""{_t("common.dear", default="Dear")} {customer_name},

{_t("taxi.refunds.email_intro", default="Your taxi booking refund has been processed successfully.")}

═══════════════════════════════════════════════════════
                {_t("taxi.refunds.email_details", default="REFUND DETAILS")}
═══════════════════════════════════════════════════════

{_t("taxi.refunds.refund_reference", default="Refund Reference")}: {refund_ref}
{_t("taxi.refunds.ticket_number", default="Ticket Number")}: {ticket_number}
{_t("taxi.refunds.refund_amount", default="Refund Amount")}: £{amount:.2f}
{_t("taxi.refunds.refund_method", default="Refund Method")}: {refund_method}
{_t("common.date", default="Date")}: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

                if old_balance is not None and new_balance is not None:
                    body += f"""
{_t("taxi.refunds.email_balance_section", default="ACCOUNT BALANCE")}:
────────────────────────────────────────
{_t("taxi.refunds.previous_balance", default="Previous Balance")}: £{old_balance:.2f}
{_t("taxi.refunds.refund_amount", default="Refund Amount")}: £{amount:.2f}
{_t("taxi.refunds.new_balance", default="New Balance")}: £{new_balance:.2f}
"""

                body += f"""
═══════════════════════════════════════════════════════

{_t("taxi.refunds.email_footer", default="If you have any questions about this refund, please contact our support team.")}

{_t("common.thank_you", default="Thank you")},
TaxiGo - {_t("taxi.subtitle", default="Your Campus Ride")}

---
{_t("common.auto_message", default="This is an automated message. Please do not reply.")}
"""

            result = send_email(user_email, subject, body)
            if result:
                logger.info(f"Refund receipt email sent to {user_email}")
                return True
            else:
                logger.warning(f"Failed to send refund receipt email to {user_email}")
                return False

        except Exception as e:
            logger.error(f"Error sending refund receipt email: {e}")
            return False
