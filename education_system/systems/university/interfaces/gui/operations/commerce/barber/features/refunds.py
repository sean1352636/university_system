"""Barber Shop GUI - Refunds feature methods."""

from education_system.systems.university.interfaces.gui.operations.commerce.barber.common import (
    tk, ttk, messagebox, filedialog, logging, csv, json,
    datetime, timedelta,
    _t, log_activity,
    get_db_connection, transaction,
    FINANCE_AVAILABLE, EMAIL_AVAILABLE,
    get_student_finance_account_balance,
    ensure_student_finance_account_exists,
    send_email,
)

logger = logging.getLogger(__name__)


class RefundsMixin:
    """Mixin providing refund-related methods for BarberGUI."""

    def refresh_refunds_list(self):
        """Refresh the refunds list with search support"""
        logger.info("Refreshing barber shop refunds list")

        # Clear existing items
        for item in self.refunds_tree.get_children():
            self.refunds_tree.delete(item)

        try:
            search_term = self.refund_search_var.get().lower()
            logger.debug(f"Search term: '{search_term}'")

            with get_db_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT
                        bt.transaction_id,
                        bt.created_at,
                        bt.customer_id,
                        COALESCE(s.first_name || ' ' || s.last_name, bt.customer_id),
                        bt.amount,
                        bt.tip_amount,
                        bt.payment_method,
                        bt.status,
                        bt.reference_number
                    FROM transactions bt
                    LEFT JOIN students s ON bt.customer_id = s.student_id
                    WHERE bt.source_type = 'barber' AND bt.transaction_type = 'service'
                    ORDER BY bt.created_at DESC
                """

                logger.debug("Executing refunds query")
                cursor.execute(query)
                transactions = cursor.fetchall()
                logger.info(f"Loaded {len(transactions)} transactions")

                displayed_count = 0
                for trans in transactions:
                    try:
                        transaction_id, date, customer_id, customer_name, amount, tip_amount, payment_method, status, reference = trans

                        # Calculate total amount
                        total_amount = (amount or 0) + (tip_amount or 0)

                        # Apply search filter
                        if search_term:
                            searchable = f"{transaction_id} {customer_id} {customer_name or ''} {status} {reference or ''}".lower()
                            if search_term not in searchable:
                                continue

                        # Format date
                        if date:
                            try:
                                date_obj = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
                                formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
                            except Exception as date_err:
                                logger.warning(f"Error parsing date '{date}': {date_err}")
                                formatted_date = date
                        else:
                            formatted_date = ''

                        # Color code by status
                        tag = 'refunded' if status == 'refunded' else 'completed'

                        self.refunds_tree.insert('', tk.END, values=(
                            transaction_id,
                            formatted_date,
                            customer_name or customer_id,
                            f"\u00a3{total_amount:.2f}",
                            payment_method or 'N/A',
                            status or 'completed',
                            reference or ''
                        ), tags=(tag,))
                        displayed_count += 1

                    except Exception as trans_err:
                        logger.error(f"Error processing transaction {transaction_id if 'transaction_id' in locals() else 'unknown'}: {trans_err}")
                        # Continue processing other transactions
                        continue

                # Configure tags
                self.refunds_tree.tag_configure('refunded', background='#ffcccc')
                self.refunds_tree.tag_configure('completed', background='#ccffcc')

                logger.info(f"Displayed {displayed_count} transactions after filtering")

        except Exception as e:
            error_msg = f"Failed to load refunds list: {str(e)}"
            logger.error(f"Error refreshing refunds list: {e}", exc_info=True)
            messagebox.showerror("Database Error", error_msg)

    def process_barber_refund(self):
        """Process a refund for a barber shop transaction"""
        logger.info("Starting barber shop refund process")

        # Get selected transaction
        selection = self.refunds_tree.selection()
        if not selection:
            logger.warning("No transaction selected for refund")
            messagebox.showwarning("No Selection", "Please select a transaction to refund.")
            return

        try:
            item = self.refunds_tree.item(selection[0])
            values = item['values']
            transaction_id = values[0]
            amount_str = values[3]
            status = values[5]

            logger.info(f"Processing refund for transaction {transaction_id}, current status: {status}")

            # Check if already refunded
            if status == 'refunded':
                logger.warning(f"Transaction {transaction_id} already refunded")
                messagebox.showwarning("Already Refunded", "This transaction has already been refunded.")
                return

            # Parse amount
            try:
                amount = float(amount_str.replace('\u00a3', '').replace(',', ''))
                logger.debug(f"Parsed refund amount: \u00a3{amount:.2f}")
            except Exception as parse_err:
                logger.error(f"Error parsing amount '{amount_str}': {parse_err}")
                messagebox.showerror("Invalid Amount", f"Cannot parse amount '{amount_str}'. Please contact support.")
                return

            # Confirm refund
            if not messagebox.askyesno("Confirm Refund", f"Refund \u00a3{amount:.2f} for Transaction #{transaction_id}?"):
                logger.info(f"Refund cancelled by user for transaction {transaction_id}")
                return

            # Get customer ID
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT customer_id FROM transactions WHERE transaction_id = ? AND source_type = 'barber'",
                             (transaction_id,))
                result = cursor.fetchone()
                if not result:
                    logger.error(f"Transaction {transaction_id} not found in database")
                    messagebox.showerror("Transaction Not Found", f"Transaction #{transaction_id} could not be found in the database.")
                    return
                customer_id = result[0]
                logger.info(f"Found customer ID: {customer_id}")

            # Show refund method dialog
            self.show_barber_refund_method_dialog(transaction_id, amount, customer_id)

        except Exception as e:
            error_msg = f"Failed to process refund: {str(e)}"
            logger.error(f"Error processing barber refund: {e}", exc_info=True)
            messagebox.showerror("Refund Error", error_msg)

    def show_barber_refund_method_dialog(self, transaction_id, amount, customer_id):
        """Show dialog to select refund method"""
        dialog = tk.Toplevel(self.parent)
        dialog.title(_t("Select Refund Method", "Select Refund Method"))
        dialog.geometry("500x350")
        dialog.transient(self.parent)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        # Header
        ttk.Label(dialog, text=_t("Select Refund Method", "Select Refund Method"),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        ttk.Label(dialog, text=f"Refund Amount: \u00a3{amount:.2f}").pack(pady=5)

        # Get current balance if finance is available
        current_balance = None
        if customer_id and FINANCE_AVAILABLE:
            try:
                current_balance = get_student_finance_account_balance(customer_id)
                ttk.Label(dialog, text=f"Current Student Account Balance: \u00a3{current_balance:.2f}",
                         foreground='blue').pack(pady=5)
                new_balance = current_balance + amount
                ttk.Label(dialog, text=f"New Balance After Refund: \u00a3{new_balance:.2f}",
                         foreground='green').pack(pady=5)
            except Exception as e:
                logger.warning(f"Could not get student balance: {e}")

        # Buttons frame
        buttons_frame = ttk.Frame(dialog)
        buttons_frame.pack(pady=20, fill=tk.BOTH, expand=True)

        def refund_cash():
            dialog.destroy()
            self._complete_barber_refund(transaction_id, amount, 'cash', customer_id)

        def refund_card():
            dialog.destroy()
            self._complete_barber_refund(transaction_id, amount, 'card', customer_id)

        def refund_student_account():
            if not FINANCE_AVAILABLE:
                messagebox.showerror(_t("Error", "Error"),
                                   _t("Finance system not available.", "Finance system not available."))
                return
            dialog.destroy()
            self.add_barber_refund_to_student_account(transaction_id, amount, customer_id)

        # Create buttons
        cash_btn = ttk.Button(buttons_frame, text=_t("\U0001f4b5 Refund as Cash", "\U0001f4b5 Refund as Cash"),
                             command=refund_cash, width=30)
        cash_btn.pack(pady=10)

        card_btn = ttk.Button(buttons_frame, text=_t("\U0001f4b3 Refund to Card", "\U0001f4b3 Refund to Card"),
                             command=refund_card, width=30)
        card_btn.pack(pady=10)

        account_btn = ttk.Button(buttons_frame, text=_t("\U0001f3e6 Refund to Student Account", "\U0001f3e6 Refund to Student Account"),
                                command=refund_student_account, width=30)
        account_btn.pack(pady=10)

        if not FINANCE_AVAILABLE:
            account_btn.config(state='disabled')

        ttk.Button(buttons_frame, text=_t("Cancel", "Cancel"),
                  command=dialog.destroy, width=30).pack(pady=10)

    def _complete_barber_refund(self, transaction_id, amount, refund_method, customer_id):
        """Complete the refund process (for cash/card)"""
        logger.info(f"Completing refund: Transaction {transaction_id}, Amount \u00a3{amount:.2f}, Method: {refund_method}")

        try:
            # Generate refund reference
            refund_ref = f"BARBER-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            logger.debug(f"Generated refund reference: {refund_ref}")

            # Get processed_by
            processed_by = 'System'
            try:
                user = self.current_user or {}
                processed_by = user.get('username', 'System')
            except Exception as auth_err:
                logger.warning(f"Could not get authenticated user: {auth_err}")

            with transaction() as conn:
                cursor = conn.cursor()

                # Update transaction reference
                logger.debug(f"Updating transaction {transaction_id} reference")
                cursor.execute("""
                    UPDATE transactions
                    SET reference_number = ?
                    WHERE transaction_id = ? AND source_type = 'barber'
                """, (refund_ref, transaction_id))

                if cursor.rowcount == 0:
                    raise Exception(f"Transaction {transaction_id} not found or could not be updated")

                # Use RefundManager to create refund record properly
                logger.debug(f"Creating refund record via RefundManager, processed by: {processed_by}")
                from education_system.systems.university.domain.operations.commerce.barber.services.barber_core import RefundManager
                RefundManager.issue_refund(
                    transaction_id=transaction_id,
                    amount=amount,
                    reason=f'Refund via {refund_method}',
                    refund_type=refund_method,
                    processed_by=processed_by
                )

            logger.info(f"Transaction {transaction_id} refunded successfully")

            # Log activity
            try:
                log_activity('refund', 'barber_transaction',
                            details={
                                'transaction_id': transaction_id,
                                'amount': amount,
                                'method': refund_method,
                                'reference': refund_ref
                            })
                logger.debug("Activity logged successfully")
            except Exception as log_err:
                logger.warning(f"Failed to log activity: {log_err}")

            # Send receipt
            try:
                self.send_barber_refund_receipt(customer_id, amount, refund_method, refund_ref, transaction_id=transaction_id)
                logger.info("Refund receipt email sent")
            except Exception as email_err:
                logger.warning(f"Failed to send refund receipt: {email_err}")
                # Don't fail the whole refund if email fails

            # Notify finance GUI
            try:
                self.notify_barber_finance_gui(transaction_id, amount, refund_method, refund_ref, customer_id)
                logger.debug("Finance system notified")
            except Exception as finance_err:
                logger.warning(f"Failed to notify finance system: {finance_err}")

            # Refresh list
            try:
                self.refresh_refunds_list()
            except Exception as refresh_err:
                logger.warning(f"Failed to refresh refunds list: {refresh_err}")

            logger.info(f"Refund completed successfully: {refund_ref}")
            messagebox.showinfo("Success", f"Refund processed successfully!\n\nReference: {refund_ref}\nAmount: \u00a3{amount:.2f}\nMethod: {refund_method.title()}")

        except Exception as e:
            error_msg = f"Failed to complete refund: {str(e)}"
            logger.error(f"Error completing barber refund for transaction {transaction_id}: {e}", exc_info=True)
            messagebox.showerror("Refund Failed", error_msg)

    def add_barber_refund_to_student_account(self, transaction_id, amount, customer_id):
        """Add refund amount to student finance account"""
        if not FINANCE_AVAILABLE:
            messagebox.showerror(_t("Error", "Error"),
                               _t("Finance system not available.", "Finance system not available."))
            return

        try:
            # Ensure student account exists
            ensure_student_finance_account_exists(customer_id)

            # Generate refund reference
            refund_ref = f"BARBER-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Get processed_by
            processed_by = 'System'
            try:
                user = self.current_user or {}
                processed_by = user.get('username', 'System')
            except Exception as auth_err:
                logger.warning(f"Could not get authenticated user: {auth_err}")

            # First, create refund in barber system (uses its own transaction)
            from education_system.systems.university.domain.operations.commerce.barber.services.barber_core import RefundManager
            RefundManager.issue_refund(
                transaction_id=transaction_id,
                amount=amount,
                reason='Refunded to student account',
                refund_type='student_account',
                processed_by=processed_by
            )

            # Then update student account and transaction reference (separate transaction)
            with transaction() as conn:
                cursor = conn.cursor()

                # Update transaction reference
                cursor.execute("""
                    UPDATE transactions
                    SET reference_number = ?
                    WHERE transaction_id = ? AND source_type = 'barber'
                """, (refund_ref, transaction_id))

                # Get account_id and balance before update
                cursor.execute("""
                    SELECT account_id, balance
                    FROM student_finance_accounts
                    WHERE student_id = ?
                """, (customer_id,))
                account_row = cursor.fetchone()

                if not account_row:
                    raise Exception(f"No finance account found for student {customer_id}")

                account_id = account_row[0]
                balance_before = account_row[1]
                balance_after = balance_before + amount

                # Add to student finance account
                cursor.execute("""
                    UPDATE student_finance_accounts
                    SET balance = balance + ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE student_id = ?
                """, (amount, customer_id))

                # Log in student finance transactions table
                sft_table = 'student_finance_transactions'
                cursor.execute(f"""
                    INSERT INTO {sft_table}
                    (account_id, student_id, transaction_type, amount, balance_before, balance_after, description, reference_id)
                    VALUES (?, ?, 'credit', ?, ?, ?, ?, ?)
                """, (account_id, customer_id, amount, balance_before, balance_after, 'Barber shop refund', refund_ref))

                # Use the calculated balance
                new_balance = balance_after

            # Log activity
            log_activity('refund', 'barber_transaction',
                        details={
                            'transaction_id': transaction_id,
                            'amount': amount,
                            'method': 'student_account',
                            'reference': refund_ref,
                            'new_balance': new_balance
                        })

            # Send receipt
            self.send_barber_refund_receipt(customer_id, amount, 'student_account', refund_ref, transaction_id=transaction_id, new_balance=new_balance)

            # Notify finance GUI
            self.notify_barber_finance_gui(transaction_id, amount, 'student_account', refund_ref, customer_id)

            # Refresh list
            self.refresh_refunds_list()

            messagebox.showinfo(_t("Success", "Success"),
                              f"Refund added to student account!\n"
                              f"Reference: {refund_ref}\n"
                              f"New Balance: \u00a3{new_balance:.2f}")

        except Exception as e:
            logger.error(f"Error adding barber refund to student account: {e}")
            messagebox.showerror(_t("Error", "Error"), f"Failed to add refund to account: {str(e)}")

    def send_barber_refund_receipt(self, customer_id, amount, refund_method, refund_ref, transaction_id=None, new_balance=None):
        """Send refund receipt email to customer"""
        if not EMAIL_AVAILABLE:
            logger.info("Email service not available, skipping receipt")
            return

        try:
            # Get customer email - check multiple tables
            customer_email = None
            customer_name = None

            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Try students table first (by student_id)
                cursor.execute("""
                    SELECT email_address, first_name || ' ' || last_name
                    FROM students
                    WHERE student_id = ?
                """, (customer_id,))
                result = cursor.fetchone()

                if result and result[0]:
                    customer_email = result[0]
                    customer_name = result[1] or customer_id
                else:
                    # Try users table (by username)
                    cursor.execute("""
                        SELECT email, first_name || ' ' || last_name
                        FROM users
                        WHERE username = ?
                    """, (customer_id,))
                    result = cursor.fetchone()

                    if result and result[0]:
                        customer_email = result[0]
                        customer_name = result[1] or customer_id
                    else:
                        # Try staff table (by username)
                        cursor.execute("""
                            SELECT email, name
                            FROM staff
                            WHERE username = ?
                        """, (customer_id,))
                        result = cursor.fetchone()

                        if result and result[0]:
                            customer_email = result[0]
                            customer_name = result[1] or customer_id

            if not customer_email:
                logger.warning(f"No email found for customer {customer_id} in any table (students/users/staff)")
                return

            if not customer_name:
                customer_name = customer_id

            # Format refund method for display
            method_display = {
                'cash': 'Cash',
                'card': 'Card',
                'student_account': 'Student Finance Account'
            }.get(refund_method, refund_method)

            # Build balance text
            balance_text = ""
            if new_balance is not None:
                balance_text = f"Your new student account balance is: \u00a3{new_balance:.2f}"

            # Render email from template
            from education_system.systems.university.infrastructure.email.template_utils import render_template
            subject, email_body = render_template('commerce/barber/refund_receipt', {
                'customer_name': customer_name,
                'refund_ref': refund_ref,
                'original_transaction': str(transaction_id),
                'refund_amount': f"\u00a3{amount:.2f}",
                'refund_method': method_display,
                'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'balance_text': balance_text
            })

            # Fallback if template not found
            if not subject or not email_body:
                subject = f"Barber Shop Refund Receipt - {refund_ref}"
                email_body = f"Dear {customer_name},\n\nYour refund of \u00a3{amount:.2f} has been processed.\nReference: {refund_ref}"

            # Send email
            send_email(
                to_email=customer_email,
                subject=subject,
                body=email_body
            )

            logger.info(f"Refund receipt sent to {customer_email}")

        except Exception as e:
            logger.error(f"Error sending barber refund receipt: {e}")

    def notify_barber_finance_gui(self, transaction_id, amount, refund_method, refund_ref, customer_id=None):
        """Notify finance system about the refund - refund already recorded in unified_refunds table"""
        try:
            # Refund is already recorded in unified_refunds by RefundManager.issue_refund
            logger.info(f"[Barber Shop] Refund {refund_ref} for transaction {transaction_id} "
                       f"recorded in unified_refunds (amount: £{amount:.2f}, method: {refund_method})")
        except Exception as e:
            logger.error(f"Error notifying finance GUI: {e}")

    def view_refund_transaction_details(self):
        """View detailed information about a transaction"""
        logger.info("Viewing transaction details")

        # Get selected transaction
        selection = self.refunds_tree.selection()
        if not selection:
            logger.warning("No transaction selected")
            messagebox.showwarning("No Selection", "Please select a transaction to view.")
            return

        try:
            item = self.refunds_tree.item(selection[0])
            values = item['values']
            transaction_id = values[0]
            logger.info(f"Loading details for transaction {transaction_id}")

            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Get transaction details with appointment info
                logger.debug("Fetching transaction details from database")
                cursor.execute("""
                    SELECT
                        bt.transaction_id,
                        bt.customer_id,
                        COALESCE(s.first_name || ' ' || s.last_name, bt.customer_id),
                        s.email_address,
                        bt.amount,
                        bt.tip_amount,
                        bt.payment_method,
                        bt.status,
                        bt.reference_number,
                        bt.created_at,
                        bt.processed_by,
                        bt.reference_id as appointment_id,
                        ba.appointment_date,
                        ba.appointment_time,
                        ba.status as appointment_status
                    FROM transactions bt
                    LEFT JOIN students s ON bt.customer_id = s.student_id
                    LEFT JOIN barber_appointments ba ON bt.reference_id = ba.appointment_id AND bt.reference_type = 'appointment'
                    WHERE bt.source_type = 'barber' AND bt.transaction_id = ?
                """, (transaction_id,))

                trans = cursor.fetchone()

                if not trans:
                    logger.error(f"Transaction {transaction_id} not found in database")
                    messagebox.showerror("Not Found", f"Transaction #{transaction_id} could not be found.")
                    return

                logger.debug("Transaction data retrieved successfully")

                (trans_id, customer_id, customer_name, customer_email, amount, tip_amount,
                 payment_method, status, reference, created_at, processed_by,
                 appointment_id, appt_date, appt_time, appt_status) = trans

                # Get service details for this appointment
                services_text = ""
                if appointment_id:
                    cursor.execute("""
                        SELECT
                            ba.service_name,
                            bs.service_type,
                            ba.duration_minutes,
                            ba.price
                        FROM barber_appointments ba
                        LEFT JOIN barber_services bs ON ba.service_id = bs.service_id
                        WHERE ba.appointment_id = ?
                    """, (appointment_id,))

                    service_row = cursor.fetchone()
                    if service_row:
                        service_name, service_type, duration, price = service_row
                        services_text = "\nService:\n"
                        services_text += f"\n{service_name}"
                        if service_type:
                            services_text += f" ({service_type})"
                        services_text += f"\n  Duration: {duration} mins | Price: \u00a3{price:.2f}\n"

                # Calculate totals
                service_total = amount or 0
                tip_total = tip_amount or 0
                grand_total = service_total + tip_total

                # Create details window
                details_window = tk.Toplevel(self.parent)
                details_window.title(_t("Transaction Details", "Transaction Details"))
                details_window.geometry("600x700")
                details_window.transient(self.parent)

                # Create scrollable text widget
                text_frame = ttk.Frame(details_window)
                text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                text_widget = tk.Text(text_frame, wrap=tk.WORD, width=70, height=40)
                scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
                text_widget.configure(yscrollcommand=scrollbar.set)

                text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                # Build details text
                divider_line = "\u2500" * 30
                section_break = "=" * 50
                details = f"""
BARBER SHOP TRANSACTION DETAILS
{section_break}

Transaction Information:
  Transaction ID: {trans_id}
  Status: {status}
  Reference: {reference or 'N/A'}
  Date: {created_at or 'N/A'}
  Processed By: {processed_by or 'N/A'}

Customer Information:
  Customer ID: {customer_id}
  Name: {customer_name or 'N/A'}
  Email: {customer_email or 'N/A'}

Appointment Information:
  Appointment ID: {appointment_id or 'N/A'}
  Date: {appt_date or 'N/A'}
  Time: {appt_time or 'N/A'}
  Status: {appt_status or 'N/A'}
{services_text}

Financial Details:
  Service Amount: \u00a3{service_total:.2f}
  Tip Amount: \u00a3{tip_total:.2f}
  {divider_line}
  Total Amount: \u00a3{grand_total:.2f}

  Payment Method: {payment_method or 'N/A'}

{section_break}
"""

                text_widget.insert('1.0', details)
                text_widget.config(state='disabled')

                # Close button
                ttk.Button(details_window, text=_t("Close", "Close"),
                          command=details_window.destroy).pack(pady=10)

                logger.info(f"Transaction details displayed successfully for {transaction_id}")

        except Exception as e:
            error_msg = f"Failed to load transaction details: {str(e)}"
            logger.error(f"Error viewing transaction details for {transaction_id if 'transaction_id' in locals() else 'unknown'}: {e}", exc_info=True)
            messagebox.showerror("View Details Error", error_msg)

    def export_refunds_to_csv(self):
        """Export refunds data to CSV file"""
        logger.info("Starting CSV export of refunds")

        try:
            # Ask for file location
            default_filename = f'barber_refunds_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            file_path = filedialog.asksaveasfilename(
                defaultextension='.csv',
                filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
                initialfile=default_filename
            )

            if not file_path:
                logger.info("CSV export cancelled by user")
                return

            logger.info(f"Exporting refunds to: {file_path}")

            with get_db_connection() as conn:
                cursor = conn.cursor()

                logger.debug("Fetching transactions from database")
                cursor.execute("""
                    SELECT
                        bt.transaction_id,
                        bt.created_at,
                        bt.customer_id,
                        COALESCE(s.first_name || ' ' || s.last_name, bt.customer_id),
                        bt.amount,
                        bt.tip_amount,
                        bt.payment_method,
                        bt.status,
                        bt.reference_number
                    FROM transactions bt
                    LEFT JOIN students s ON bt.customer_id = s.student_id
                    WHERE bt.source_type = 'barber' AND bt.transaction_type = 'service'
                    ORDER BY bt.created_at DESC
                """)

                transactions = cursor.fetchall()
                logger.info(f"Found {len(transactions)} transactions to export")

            # Write to CSV
            logger.debug("Writing data to CSV file")
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(['Transaction ID', 'Date', 'Customer ID', 'Customer Name',
                               'Service Amount', 'Tip Amount', 'Total Amount', 'Payment Method',
                               'Status', 'Reference'])

                # Write data
                rows_written = 0
                for trans in transactions:
                    try:
                        transaction_id, date, customer_id, customer_name, amount, tip_amount, payment_method, status, reference = trans
                        total = (amount or 0) + (tip_amount or 0)
                        writer.writerow([
                            transaction_id,
                            date or '',
                            customer_id,
                            customer_name or '',
                            f'{amount:.2f}' if amount else '0.00',
                            f'{tip_amount:.2f}' if tip_amount else '0.00',
                            f'{total:.2f}',
                            payment_method or '',
                            status or 'completed',
                            reference or ''
                        ])
                        rows_written += 1
                    except Exception as row_err:
                        logger.warning(f"Error writing transaction {transaction_id if 'transaction_id' in locals() else 'unknown'}: {row_err}")
                        continue

            logger.info(f"Successfully exported {rows_written} transactions to {file_path}")
            messagebox.showinfo("Export Successful", f"Refunds exported successfully!\n\nFile: {file_path}\nRecords: {rows_written}")

        except Exception as e:
            error_msg = f"Failed to export refunds: {str(e)}"
            logger.error(f"Error exporting refunds to CSV: {e}", exc_info=True)
            messagebox.showerror("Export Error", error_msg)
