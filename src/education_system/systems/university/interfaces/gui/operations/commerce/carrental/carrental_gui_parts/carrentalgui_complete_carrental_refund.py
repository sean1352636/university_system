"""Methods _complete_carrental_refund through view_carrental_transaction_details."""

from .. import carrental_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class CarRentalGUI:
    def _complete_carrental_refund(self, transaction_id, amount, refund_method, customer_id):
        """Complete the refund process (for cash/card)"""
        try:
            # Generate refund reference
            refund_ref = f"CARRENTAL-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            with transaction() as conn:
                cursor = conn.cursor()

                # Update transaction status
                cursor.execute("""
                    UPDATE transactions
                    SET status = 'refunded',
                        reference_number = ?
                    WHERE transaction_id = ? AND source_type = 'car_rental'
                """, (refund_ref, transaction_id))

                # Create refund record in unified_refunds table
                # Get processed_by
                processed_by = None
                if self.current_user:
                    processed_by = self.current_user.get('username') or self.current_user.get('user_id', '')

                cursor.execute("""
                    INSERT INTO unified_refunds
                    (source_type, reference_id, reference_type, student_id, amount,
                     refund_method, refund_reference, refund_date, processed_by, status)
                    VALUES ('car_rental', ?, 'transaction', ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, 'processed')
                """, (str(transaction_id), customer_id, amount, refund_method, refund_ref, processed_by))
                refund_row_id = cursor.lastrowid

            # Auto-post to GL (cash has moved). Never raises.
            try:
                from education_system.systems.university.domains.finance.domain.ledger import notify_ledger
                notify_ledger('refund', refund_row_id, posted_by=processed_by or 'car_rental')
            except Exception as _e:
                import logging
                logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

            # Send receipt
            self.send_carrental_refund_receipt(customer_id, amount, refund_method, refund_ref)

            # Notify finance GUI
            self.notify_carrental_finance_gui(transaction_id, amount, refund_method, refund_ref)

            # Refresh list
            self.refresh_refunds_list()

            messagebox.showinfo(_t("common.success", default="Success"),
                              f"Refund processed successfully!\nReference: {refund_ref}")

        except Exception as e:
            logger.error(f"Error completing car rental refund: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to complete refund: {str(e)}")

    def add_carrental_refund_to_student_account(self, transaction_id, amount, customer_id):
        """Add refund amount to student finance account"""
        try:
            from education_system.systems.university.domains.finance.infrastructure.finance_integration import ensure_student_finance_account_exists

            # Ensure student account exists
            ensure_student_finance_account_exists(customer_id)

            # Generate refund reference
            refund_ref = f"CARRENTAL-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            with transaction() as conn:
                cursor = conn.cursor()

                # Update transaction status
                cursor.execute("""
                    UPDATE transactions
                    SET status = 'refunded',
                        reference_number = ?
                    WHERE transaction_id = ? AND source_type = 'car_rental'
                """, (refund_ref, transaction_id))

                # Create refund record in unified_refunds table
                # Get processed_by
                processed_by = None
                if self.current_user:
                    processed_by = self.current_user.get('username') or self.current_user.get('user_id', '')

                cursor.execute("""
                    INSERT INTO unified_refunds
                    (source_type, reference_id, reference_type, student_id, amount,
                     refund_method, refund_reference, refund_date, processed_by, status)
                    VALUES ('car_rental', ?, 'transaction', ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, 'processed')
                """, (str(transaction_id), customer_id, amount, 'student_account', refund_ref, processed_by))
                refund_row_id = cursor.lastrowid

                # Add to student finance account
                cursor.execute("""
                    UPDATE student_finance_accounts
                    SET balance = balance + ?
                    WHERE student_id = ?
                """, (amount, customer_id))

                # Get new balance and account_id after update
                cursor.execute("SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?", (customer_id,))
                result = cursor.fetchone()
                if result:
                    account_id, new_balance = result
                else:
                    account_id, new_balance = None, amount

                # Log transaction in transactions table
                cursor.execute("""
                    INSERT INTO transactions
                    (source_type, account_id, student_id, transaction_type, amount, balance_after, description,
                     reference_id, processed_by, created_at)
                    VALUES ('student_finance', ?, ?, 'credit', ?, ?, ?, ?, ?, ?)
                """, (account_id, customer_id, amount, new_balance, f'Car rental refund - {refund_ref}',
                      refund_ref, processed_by, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            # Auto-post to GL (cash has moved to student account). Never raises.
            try:
                from education_system.systems.university.domains.finance.domain.ledger import notify_ledger
                notify_ledger('refund', refund_row_id, posted_by=processed_by or 'car_rental')
            except Exception as _e:
                import logging
                logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

            # Send receipt
            self.send_carrental_refund_receipt(customer_id, amount, 'student_account', refund_ref, new_balance)

            # Notify finance GUI
            self.notify_carrental_finance_gui(transaction_id, amount, 'student_account', refund_ref)

            # Refresh list
            self.refresh_refunds_list()

            messagebox.showinfo(_t("common.success", default="Success"),
                              f"Refund added to student account!\n"
                              f"Reference: {refund_ref}\n"
                              f"New Balance: £{new_balance:.2f}")

        except Exception as e:
            logger.error(f"Error adding car rental refund to student account: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to add refund to account: {str(e)}")

    def send_carrental_refund_receipt(self, customer_id, amount, refund_method, refund_ref, new_balance=None):
        """Send refund receipt email to customer"""
        try:
            from education_system.systems.university.infrastructure.email.email_service import send_email

            # Get customer email - check students table first, then users table
            customer_email = None
            customer_name = customer_id

            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Try students table first
                cursor.execute("SELECT email_address, first_name, last_name FROM students WHERE student_id = ?", (customer_id,))
                result = cursor.fetchone()

                if result and result[0]:
                    customer_email = result[0]
                    first_name = result[1] or ''
                    last_name = result[2] or ''
                    customer_name = f"{first_name} {last_name}".strip() or customer_id
                else:
                    # Fall back to users table (for admin/staff accounts)
                    cursor.execute("SELECT email, first_name, last_name, username FROM users WHERE username = ? OR id = ?",
                                 (customer_id, customer_id))
                    result = cursor.fetchone()

                    if result and result[0]:
                        customer_email = result[0]
                        first_name = result[1] or ''
                        last_name = result[2] or ''
                        username = result[3] or customer_id
                        customer_name = f"{first_name} {last_name}".strip() or username

                if not customer_email:
                    logger.warning(f"No email found for customer {customer_id} in students or users table")
                    return

            # Format refund method for display
            method_display = {
                'cash': 'Cash',
                'card': 'Card',
                'student_account': 'Student Finance Account'
            }.get(refund_method, refund_method)

            # Build balance text if applicable
            balance_text = ""
            if new_balance is not None:
                balance_text = f"Your new student account balance is: £{new_balance:.2f}"

            # Use JSON template for email
            from education_system.systems.university.infrastructure.email.template_utils import render_template
            subject, body = render_template('commerce/carrental/refund_receipt', {
                'customer_name': customer_name,
                'refund_ref': refund_ref,
                'rental_number': 'N/A',
                'vehicle_info': 'N/A',
                'refund_amount': f"£{amount:.2f}",
                'refund_method': method_display,
                'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'balance_text': balance_text
            })

            # Send email
            send_email(
                recipient_email=customer_email,
                subject=subject,
                body=body
            )

            logger.info(f"Refund receipt sent to {customer_email}")

        except Exception as e:
            logger.error(f"Error sending car rental refund receipt: {e}")

    def notify_carrental_finance_gui(self, transaction_id, amount, refund_method, refund_ref):
        """Notify finance system about the refund"""
        try:
            # Finance refund data is now recorded in unified_refunds table
            # This method retains notification logic only
            logger.info(f"Finance GUI notified of refund {refund_ref}")

        except Exception as e:
            logger.error(f"Error notifying finance GUI: {e}")

    def view_carrental_transaction_details(self):
        """View detailed information about a transaction"""
        # Get selected transaction
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.no_selection", default="No Selection"),
                                  _t("carrental.refunds.select_transaction_view", default="Please select a transaction to view."))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']
        transaction_id = values[0]

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Get transaction details with rental info
                cursor.execute("""
                    SELECT
                        t.transaction_id,
                        t.customer_id,
                        TRIM(COALESCE(s.first_name, '') || ' ' || COALESCE(s.last_name, '')) as customer_name,
                        s.email_address,
                        t.amount,
                        t.transaction_type,
                        t.payment_method,
                        t.status,
                        t.reference_number,
                        t.created_at,
                        t.processed_by,
                        t.reference_id as rental_id,
                        r.start_date,
                        r.end_date,
                        r.vehicle_id,
                        v.make,
                        v.model,
                        v.registration
                    FROM transactions t
                    LEFT JOIN students s ON t.customer_id = s.student_id
                    LEFT JOIN carrental_rentals r ON t.reference_id = r.rental_id AND t.reference_type = 'rental'
                    LEFT JOIN carrental_vehicles v ON r.vehicle_id = v.vehicle_id
                    WHERE t.source_type = 'car_rental' AND t.transaction_id = ?
                """, (transaction_id,))

                trans = cursor.fetchone()

                if not trans:
                    messagebox.showerror(_t("common.error", default="Error"),
                                       _t("carrental.refunds.transaction_not_found", default="Transaction not found."))
                    return

                (trans_id, customer_id, customer_name, customer_email, amount, transaction_type,
                 payment_method, status, reference, created_at, processed_by, rental_id,
                 start_date, end_date, vehicle_id, make, model, registration) = trans

                # If customer info not found in students table, check users table
                if not customer_name or not customer_email:
                    cursor.execute("""
                        SELECT
                            TRIM(COALESCE(first_name, '') || ' ' || COALESCE(last_name, '')) as name,
                            email,
                            username
                        FROM users
                        WHERE username = ? OR id = ?
                    """, (customer_id, customer_id))
                    user_result = cursor.fetchone()

                    if user_result:
                        user_name, user_email, username = user_result
                        if not customer_name:
                            customer_name = user_name or username or customer_id
                        if not customer_email:
                            customer_email = user_email or 'Not available'

                # Ensure we have some value for customer_name
                if not customer_name:
                    customer_name = customer_id

                # Build rental details text
                rental_details = ""
                if rental_id:
                    rental_details = f"""
Rental Information:
  Rental ID: {rental_id}
  Start Date: {start_date or 'N/A'}
  End Date: {end_date or 'N/A'}
  Vehicle: {make or 'N/A'} {model or 'N/A'}
  Registration: {registration or 'N/A'}
"""

                # Create details window
                details_window = tk.Toplevel(self.root)
                details_window.title(_t("carrental.refunds.transaction_details", default="Transaction Details"))
                details_window.geometry("600x700")
                details_window.transient(self.root)

                # Create scrollable text widget
                text_frame = ttk.Frame(details_window)
                text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                text_widget = tk.Text(text_frame, wrap=tk.WORD, width=70, height=40)
                scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
                text_widget.configure(yscrollcommand=scrollbar.set)

                text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                # Build details text
                details = f"""
CAR RENTAL TRANSACTION DETAILS
{'=' * 50}

Transaction Information:
  Transaction ID: {trans_id}
  Status: {status}
  Type: {transaction_type}
  Reference: {reference or 'N/A'}
  Date: {created_at or 'N/A'}
  Processed By: {processed_by or 'N/A'}

Customer Information:
  Customer ID: {customer_id}
  Name: {customer_name or 'N/A'}
  Email: {customer_email or 'N/A'}
{rental_details}
Financial Details:
  Amount: £{amount:.2f}
  Payment Method: {payment_method or 'N/A'}

{'=' * 50}
"""

                text_widget.insert('1.0', details)
                text_widget.config(state='disabled')

                # Close button
                ttk.Button(details_window, text=_t("common.close", default="Close"),
                          command=details_window.destroy).pack(pady=10)

        except Exception as e:
            logger.error(f"Error viewing transaction details: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to load details: {str(e)}")
