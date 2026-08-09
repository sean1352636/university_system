"""Methods process_nailbar_refund through notify_nailbar_finance_gui."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from .. import nailbar_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})


class NailBarGUI:
    def process_nailbar_refund(self):
        """Process a refund for selected nail bar transaction"""
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("nailbar.msg_titles.no_selection"), _t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_process_nailbar_refund.dialogs.please_select_a_transaction_to_refund', default="Please select a transaction to refund."))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']

        if len(values) < 7:
            messagebox.showerror(_t("nailbar.msg_titles.error"), _t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_process_nailbar_refund.dialogs.invalid_transaction_data', default="Invalid transaction data."))
            return

        transaction_id = values[0]
        appointment_id = values[1]
        amount_str = values[4].replace('£', '').strip()
        try:
            amount = float(amount_str)
        except ValueError:
            messagebox.showerror(_t("nailbar.msg_titles.error"), _t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_process_nailbar_refund.dialogs.invalid_amount_format', default="Invalid amount format."))
            return

        status = values[6]

        # Check if already refunded
        if status == 'REFUNDED':
            messagebox.showinfo(_t("nailbar.msg_titles.already_refunded"), _t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_process_nailbar_refund.dialogs.this_transaction_has_already_been_refunded', default="This transaction has already been refunded."))
            return

        # Confirm refund
        if not messagebox.askyesno(_t("nailbar.msg_titles.confirm_refund"), f"Process refund of £{amount:.2f} for transaction {transaction_id}?"):
            return

        # Get transaction details
        try:
            with get_db_connection() as conn:
                cursor = conn.execute('''
                    SELECT customer_id, payment_method
                    FROM transactions
                    WHERE transaction_id = ? AND source_type = 'nail_bar'
                ''', (transaction_id,))

                trans_data = cursor.fetchone()

                if not trans_data:
                    messagebox.showerror(_t("nailbar.msg_titles.error"), _t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_process_nailbar_refund.dialogs.transaction_not_found_in_database', default="Transaction not found in database."))
                    return

                customer_id = trans_data[0]
                payment_method = trans_data[1]

        except Exception as e:
            messagebox.showerror(_t("nailbar.msg_titles.database_error"), f"Error fetching transaction details: {e}")
            return

        # Show refund method dialog
        refund_method = self.show_nailbar_refund_method_dialog(amount, transaction_id, customer_id)

        if not refund_method:
            return

        # Process refund
        try:
            with get_db_connection() as conn:
                # Update transaction status to refunded
                conn.execute('''
                    UPDATE transactions
                    SET status = 'refunded'
                    WHERE transaction_id = ? AND source_type = 'nail_bar'
                ''', (transaction_id,))

                # Generate refund reference
                refund_ref = f"NAILBAR-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                # Insert refund record into unified refunds table
                processed_by = self.current_user.get('username', 'System')
                refund_notes = f"Nail Bar/Salon service refund (transaction_id={transaction_id})"
                cur = conn.execute('''
                    INSERT INTO unified_refunds
                    (source_type, reference_id, reference_type, refund_date, amount,
                     refund_method, refund_reference, student_id, processed_by, notes, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'processed')
                ''', ('nail_bar',
                      str(appointment_id) if appointment_id != 'N/A' else None,
                      'appointment',
                      datetime.now().strftime('%Y-%m-%d %H:%M:%S'), amount, refund_method,
                      refund_ref, customer_id, processed_by, refund_notes))
                refund_row_id = cur.lastrowid

                conn.commit()

            # Auto-post to GL (cash has moved). Never raises.
            try:
                from education_system.systems.university.domains.finance.domain.ledger import notify_ledger
                notify_ledger('refund', refund_row_id, posted_by=processed_by)
            except Exception as _e:
                import logging
                logging.getLogger(__name__).warning("ledger hook failed: %s", _e)

            # If student account refund, add to their account
            if refund_method == 'Student Account':
                success = self.add_nailbar_refund_to_student_account(customer_id, amount, refund_ref)
                if not success:
                    messagebox.showwarning(_t("nailbar.msg_titles.partial_success"),
                                         _t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_process_nailbar_refund.dialogs.refund_recorded_but_failed_to_credit_student_account_please_cred', default="Refund recorded but failed to credit student account. Please credit manually."))

            # Send refund receipt email
            self.send_nailbar_refund_receipt(transaction_id, customer_id, amount, refund_method, refund_ref)

            # Notify finance GUI
            self.notify_nailbar_finance_gui(transaction_id, amount, refund_method, refund_ref, customer_id)

            log_activity('refund', 'nailbar_transaction', details={'transaction_id': transaction_id, 'amount': amount})

            messagebox.showinfo(_t("nailbar.msg_titles.refund_processed"),
                              f"Refund of £{amount:.2f} processed successfully.\nRefund Reference: {refund_ref}")

            # Refresh the list
            self.refresh_refunds_list()

        except Exception as e:
            messagebox.showerror(_t("nailbar.msg_titles.database_error"), f"Error processing refund: {e}")
            logger.error(f"Error processing refund: {e}")

    def show_nailbar_refund_method_dialog(self, amount, transaction_id, customer_id):
        """Show dialog to select refund method"""
        dialog = tk.Toplevel(self.parent)
        dialog.title(_t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_process_nailbar_refund.windows.select_refund_method', default="Select Refund Method"))
        dialog.geometry("400x350")
        dialog.transient(self.parent)
        dialog.grab_set()

        result = {'method': None}

        ttk.Label(dialog, text=f"Refund Amount: £{amount:.2f}", font=('Arial', 12, 'bold')).pack(pady=10)
        ttk.Label(dialog, text=f"Transaction ID: {transaction_id}").pack(pady=5)

        # Show student account balance if customer_id available and finance integration enabled
        if customer_id and FINANCE_AVAILABLE:
            try:
                current_balance = get_student_finance_account_balance(customer_id)
                if current_balance is not None:
                    new_balance = current_balance + amount
                    balance_frame = ttk.LabelFrame(dialog, text=_t("nailbar.labels.student_finance_account"), padding=10)
                    balance_frame.pack(pady=10, padx=20, fill=tk.X)

                    ttk.Label(balance_frame, text=f"Current Balance: £{current_balance:.2f}").pack(anchor='w')
                    ttk.Label(balance_frame, text=f"After Refund: £{new_balance:.2f}",
                            font=('Arial', 10, 'bold')).pack(anchor='w')
            except Exception as e:
                logger.error(f"Error getting balance: {e}")

        ttk.Label(dialog, text=_t("nailbar.labels.select_refund_method"), font=('Arial', 10)).pack(pady=10)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def select_cash():
            result['method'] = 'Cash'
            dialog.destroy()

        def select_card():
            result['method'] = 'Card'
            dialog.destroy()

        def select_student_account():
            if not customer_id:
                messagebox.showerror(_t("nailbar.msg_titles.error"), _t('gui.operations.commerce.nailbar.nailbar_gui_parts.nailbargui_process_nailbar_refund.dialogs.no_customer_id_associated_with_this_transaction', default="No customer ID associated with this transaction."))
                return
            result['method'] = 'Student Account'
            dialog.destroy()

        ttk.Button(button_frame, text=_t("nailbar.btn.cash_refund"), command=select_cash, width=20).pack(pady=5)
        ttk.Button(button_frame, text=_t("nailbar.btn.card_refund"), command=select_card, width=20).pack(pady=5)

        if customer_id and FINANCE_AVAILABLE:
            ttk.Button(button_frame, text=_t("nailbar.labels.student_finance_account"), command=select_student_account, width=20).pack(pady=5)

        ttk.Button(button_frame, text=_t("nailbar.btn.cancel"), command=dialog.destroy, width=20).pack(pady=10)

        dialog.wait_window()
        return result['method']

    def add_nailbar_refund_to_student_account(self, customer_id, amount, refund_ref):
        """Add refund amount to student finance account"""
        if not FINANCE_AVAILABLE:
            return False

        try:
            with get_db_connection() as conn:
                # Check if student finance account exists
                cursor = conn.execute(
                    'SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?',
                    (customer_id,)
                )
                account = cursor.fetchone()

                if not account:
                    # Create account with refund amount
                    conn.execute('''
                        INSERT INTO student_finance_accounts (student_id, balance, created_at)
                        VALUES (?, ?, ?)
                    ''', (customer_id, amount, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                    # Get the new account_id
                    cursor = conn.execute(
                        'SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?',
                        (customer_id,)
                    )
                    account = cursor.fetchone()
                    account_id = account[0]
                    balance_before = 0
                    balance_after = amount
                else:
                    # Update existing account
                    account_id = account[0]
                    balance_before = account[1]
                    balance_after = balance_before + amount

                    conn.execute('''
                        UPDATE student_finance_accounts
                        SET balance = balance + ?
                        WHERE student_id = ?
                    ''', (amount, customer_id))

                # Record transaction
                processed_by = self.current_user.get('username', 'System')
                conn.execute('''
                    INSERT INTO transactions
                    (source_type, account_id, student_id, transaction_type, amount, balance_before,
                     balance_after, description, reference_id, processed_by)
                    VALUES ('student_finance', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (account_id, customer_id, 'credit', amount, balance_before, balance_after,
                      'Nail Bar/Salon Service Refund', refund_ref, processed_by))

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error adding refund to student account: {e}")
            return False

    def send_nailbar_refund_receipt(self, transaction_id, customer_id, amount, method, refund_ref):
        """Send refund receipt email to customer"""
        if not EMAIL_AVAILABLE:
            return

        try:
            from education_system.systems.university.domains.finance.infrastructure.finance_integration import get_student_info
            from education_system.systems.university.infrastructure.email.template_utils import render_template

            # Get customer email
            customer_info = get_student_info(customer_id)
            if not customer_info or not customer_info.get('email'):
                logger.warning(f"No email found for customer {customer_id}")
                return

            customer_email = customer_info['email']
            customer_name = customer_info.get('full_name', 'Valued Customer')

            # Get updated balance if student account refund
            balance_text = ""
            if method == 'Student Account' and FINANCE_AVAILABLE:
                try:
                    new_balance = get_student_finance_account_balance(customer_id)
                    if new_balance is not None:
                        balance_text = f"Your updated account balance is: £{new_balance:.2f}"
                except Exception:
                    logger.debug("Could not retrieve updated student finance balance")

            # Use JSON template for email
            subject, body = render_template('commerce/nailbar/refund_receipt', {
                'customer_name': customer_name,
                'refund_ref': refund_ref,
                'original_transaction': str(transaction_id),
                'refund_amount': f"£{amount:.2f}",
                'refund_method': method,
                'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'balance_text': balance_text
            })

            result = send_email(customer_email, subject, body)
            if result:
                logger.info(f"Refund receipt sent to {customer_email}")
            else:
                logger.warning(f"Failed to send refund receipt to {customer_email}")

        except Exception as e:
            logger.error(f"Error sending refund receipt: {e}")

    def notify_nailbar_finance_gui(self, transaction_id, amount, method, refund_ref, customer_id):
        """Notify finance GUI about the refund"""
        try:
            # Finance refund is now recorded via unified_refunds table;
            # no separate finance_refunds insert needed.
            logger.info(f"Finance notified of nail bar refund: ref={refund_ref}, amount={amount}")
        except Exception as e:
            logger.error(f"Error notifying finance GUI: {e}")
