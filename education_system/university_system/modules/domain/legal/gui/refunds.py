"""Refunds mixin for the Legal Services GUI."""

from ._imports import (
    tk, ttk, messagebox, filedialog, traceback,
    datetime,
    get_connection, transaction,
    log_activity,
    _t, logger,
    send_email, render_template, EMAIL_AVAILABLE,
    get_student_finance_account_balance,
    FINANCE_AVAILABLE,
)


class RefundsMixin:
    """Refunds tab: process refunds, receipts, export, payment details."""

    def create_refunds_tab(self):
        """Create the refunds management tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("legal.tabs.refunds", default="Refunds"))

        # Header
        header_frame = ttk.Frame(tab)
        header_frame.pack(fill=tk.X, pady=(10, 10), padx=10)

        ttk.Label(header_frame, text=_t("legal.refunds.title", default="Legal Services Refunds"),
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT)

        # Search frame
        search_frame = ttk.LabelFrame(tab, text=_t("common.search", default="Search"), padding="10")
        search_frame.pack(fill=tk.X, pady=(0, 10), padx=10)

        ttk.Label(search_frame, text=_t("common.search_label", default="Search:")).grid(row=0, column=0, sticky=tk.W, padx=5)
        self.refund_search_var = tk.StringVar()
        self.refund_search_var.trace('w', lambda *args: self.refresh_refunds_list())
        search_entry = ttk.Entry(search_frame, textvariable=self.refund_search_var, width=40)
        search_entry.grid(row=0, column=1, sticky=tk.W, padx=5)

        # Table frame
        table_frame = ttk.Frame(tab)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10), padx=10)

        # Create treeview with 7 columns
        columns = ('payment_id', 'date', 'client', 'amount', 'payment_type', 'payment_method', 'status')
        self.refunds_tree = ttk.Treeview(table_frame, columns=columns, show='headings', height=15)

        # Configure columns
        self.refunds_tree.heading('payment_id', text=_t('legal.refunds.payment_id', default='Payment ID'))
        self.refunds_tree.heading('date', text=_t('common.date', default='Date'))
        self.refunds_tree.heading('client', text=_t('legal.common.client', default='Client'))
        self.refunds_tree.heading('amount', text=_t('common.amount', default='Amount'))
        self.refunds_tree.heading('payment_type', text=_t('legal.refunds.payment_type', default='Service Type'))
        self.refunds_tree.heading('payment_method', text=_t('common.payment_method', default='Payment Method'))
        self.refunds_tree.heading('status', text=_t('common.status', default='Status'))

        self.refunds_tree.column('payment_id', width=100)
        self.refunds_tree.column('date', width=150)
        self.refunds_tree.column('client', width=150)
        self.refunds_tree.column('amount', width=100)
        self.refunds_tree.column('payment_type', width=120)
        self.refunds_tree.column('payment_method', width=120)
        self.refunds_tree.column('status', width=100)

        # Scrollbars
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.refunds_tree.yview)
        hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=self.refunds_tree.xview)
        self.refunds_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.refunds_tree.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        hsb.grid(row=1, column=0, sticky=(tk.E, tk.W))

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        # Buttons frame
        buttons_frame = ttk.Frame(tab)
        buttons_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Button(buttons_frame, text=_t("legal.refunds.process", default="Process Refund"),
                  command=self.process_legal_refund).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text=_t("common.view_details", default="View Details"),
                  command=self.view_legal_payment_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text=_t("common.refresh", default="Refresh"),
                  command=self.refresh_refunds_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text=_t("common.export_csv", default="Export to CSV"),
                  command=self.export_refunds_to_csv).pack(side=tk.LEFT, padx=5)

        # Load data
        self.refresh_refunds_list()

    def refresh_refunds_list(self):
        """Refresh the refunds list with search support"""
        # Clear existing items
        for item in self.refunds_tree.get_children():
            self.refunds_tree.delete(item)

        try:
            search_term = self.refund_search_var.get().lower()

            with get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT
                        p.payment_id,
                        p.created_at,
                        p.client_id,
                        p.client_email,
                        p.amount,
                        p.payment_type,
                        p.payment_method,
                        p.status,
                        p.transaction_reference
                    FROM legal_payments p
                    ORDER BY p.created_at DESC
                """

                cursor.execute(query)
                payments = cursor.fetchall()

                for payment in payments:
                    payment_id, date, client_id, client_email, amount, payment_type, payment_method, status, reference = payment

                    # Apply search filter
                    if search_term:
                        searchable = f"{payment_id} {client_id} {client_email or ''} {payment_type} {status} {reference or ''}".lower()
                        if search_term not in searchable:
                            continue

                    # Format date
                    if date:
                        try:
                            date_obj = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
                            formatted_date = date_obj.strftime('%Y-%m-%d %H:%M')
                        except (ValueError, TypeError):
                            formatted_date = date
                    else:
                        formatted_date = ''

                    # Color code by status
                    tag = 'refunded' if status == 'refunded' else 'completed'

                    self.refunds_tree.insert('', tk.END, values=(
                        payment_id,
                        formatted_date,
                        client_email or client_id,
                        f"\u00a3{amount:.2f}",
                        payment_type or 'N/A',
                        payment_method or 'N/A',
                        status or 'completed'
                    ), tags=(tag,))

                # Configure tags
                self.refunds_tree.tag_configure('refunded', background='#ffcccc')
                self.refunds_tree.tag_configure('completed', background='#ccffcc')

        except Exception as e:
            logger.error(f"Error refreshing refunds list: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to load refunds: {str(e)}")

    def process_legal_refund(self):
        """Process a refund for a legal service payment"""
        # Get selected payment
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.no_selection", default="No Selection"),
                                  _t("legal.refunds.select_payment", default="Please select a payment to refund."))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']
        payment_id = values[0]
        amount_str = values[3]
        status = values[6]

        # Check if already refunded
        if status == 'refunded':
            messagebox.showwarning(_t("legal.refunds.already_refunded", default="Already Refunded"),
                                  _t("legal.refunds.already_refunded_msg", default="This payment has already been refunded."))
            return

        # Parse amount
        try:
            amount = float(amount_str.replace('\u00a3', '').replace(',', ''))
        except (ValueError, TypeError):
            messagebox.showerror(_t("common.error", default="Error"),
                               _t("common.invalid_amount", default="Invalid amount format."))
            return

        # Confirm refund
        if not messagebox.askyesno(_t("legal.refunds.confirm", default="Confirm Refund"),
                                   f"Refund \u00a3{amount:.2f} for Payment #{payment_id}?"):
            return

        try:
            # Get client ID
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT client_id, client_email FROM legal_payments WHERE payment_id = ?",
                             (payment_id,))
                result = cursor.fetchone()
                if not result:
                    messagebox.showerror(_t("common.error", default="Error"),
                                       _t("legal.refunds.payment_not_found", default="Payment not found."))
                    return
                client_id, client_email = result

            # Show refund method dialog
            self.show_legal_refund_method_dialog(payment_id, amount, client_id, client_email)

        except Exception as e:
            logger.error(f"Error processing legal refund: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to process refund: {str(e)}")

    def show_legal_refund_method_dialog(self, payment_id, amount, client_id, client_email):
        """Show dialog to select refund method"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("legal.refunds.select_method", default="Select Refund Method"))
        dialog.geometry("500x350")
        dialog.transient(self.window)
        dialog.grab_set()

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        # Header
        ttk.Label(dialog, text=_t("legal.refunds.select_method", default="Select Refund Method"),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        ttk.Label(dialog, text=f"Refund Amount: \u00a3{amount:.2f}").pack(pady=5)

        # Get current balance if finance is available
        current_balance = None
        if client_id and FINANCE_AVAILABLE:
            try:
                current_balance = get_student_finance_account_balance(client_id)
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
            self._complete_legal_refund(payment_id, amount, 'cash', client_id, client_email)

        def refund_card():
            dialog.destroy()
            self._complete_legal_refund(payment_id, amount, 'card', client_id, client_email)

        def refund_student_account():
            if not FINANCE_AVAILABLE:
                messagebox.showerror(_t("common.error", default="Error"),
                                   _t("common.finance_unavailable", default="Finance system not available."))
                return
            dialog.destroy()
            self.add_legal_refund_to_student_account(payment_id, amount, client_id, client_email)

        # Create buttons
        cash_btn = ttk.Button(buttons_frame, text=_t("common.refund_cash", default="\U0001f4b5 Refund as Cash"),
                             command=refund_cash, width=30)
        cash_btn.pack(pady=10)

        card_btn = ttk.Button(buttons_frame, text=_t("common.refund_card", default="\U0001f4b3 Refund to Card"),
                             command=refund_card, width=30)
        card_btn.pack(pady=10)

        account_btn = ttk.Button(buttons_frame, text=_t("common.refund_account", default="\U0001f3e6 Refund to Student Account"),
                                command=refund_student_account, width=30)
        account_btn.pack(pady=10)

        if not FINANCE_AVAILABLE:
            account_btn.config(state='disabled')

        ttk.Button(buttons_frame, text=_t("common.cancel", default="Cancel"),
                  command=dialog.destroy, width=30).pack(pady=10)

    def _complete_legal_refund(self, payment_id, amount, refund_method, client_id, client_email):
        """Complete the refund process (for cash/card)"""
        try:
            # Generate refund reference
            refund_ref = f"LEGAL-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            with transaction() as conn:
                cursor = conn.cursor()

                # Update payment status
                cursor.execute("""
                    UPDATE legal_payments
                    SET status = 'refunded',
                        transaction_reference = ?
                    WHERE payment_id = ?
                """, (refund_ref, payment_id))

                # Create refund record in legal_refunds table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS legal_refunds (
                        refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        payment_id INTEGER,
                        client_id TEXT,
                        client_email TEXT,
                        amount DECIMAL(10,2),
                        refund_method TEXT,
                        refund_reference TEXT,
                        refunded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_by TEXT,
                        FOREIGN KEY (payment_id) REFERENCES legal_payments(payment_id)
                    )
                """)

                # Get processed_by
                processed_by = None
                if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                    user = self.auth.current_user
                    processed_by = user.get('username') or user.get('user_id', '')

                cursor.execute("""
                    INSERT INTO legal_refunds
                    (payment_id, client_id, client_email, amount, refund_method, refund_reference, processed_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (payment_id, client_id, client_email, amount, refund_method, refund_ref, processed_by))

            # Log activity
            log_activity('refund', 'legal_payment',
                        payment_id=payment_id,
                        amount=amount,
                        details={'method': refund_method, 'reference': refund_ref})

            # Send receipt
            self.send_legal_refund_receipt(client_email, amount, refund_method, refund_ref)

            # Notify finance GUI
            self.notify_legal_finance_gui(payment_id, amount, refund_method, refund_ref)

            # Refresh list
            self.refresh_refunds_list()

            messagebox.showinfo(_t("common.success", default="Success"),
                              f"Refund processed successfully!\nReference: {refund_ref}")

        except Exception as e:
            logger.error(f"Error completing legal refund: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to complete refund: {str(e)}")

    def add_legal_refund_to_student_account(self, payment_id, amount, client_id, client_email):
        """Add refund amount to student finance account"""
        if not FINANCE_AVAILABLE:
            messagebox.showerror(_t("common.error", default="Error"),
                               _t("common.finance_unavailable", default="Finance system not available."))
            return

        try:
            from education_system.university_system.modules.shared.utils.finance_integration import ensure_student_finance_account_exists

            # Ensure student account exists
            ensure_student_finance_account_exists(client_id)

            # Generate refund reference
            refund_ref = f"LEGAL-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            with transaction() as conn:
                cursor = conn.cursor()

                # Update payment status
                cursor.execute("""
                    UPDATE legal_payments
                    SET status = 'refunded',
                        transaction_reference = ?
                    WHERE payment_id = ?
                """, (refund_ref, payment_id))

                # Create refund record
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS legal_refunds (
                        refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        payment_id INTEGER,
                        client_id TEXT,
                        client_email TEXT,
                        amount DECIMAL(10,2),
                        refund_method TEXT,
                        refund_reference TEXT,
                        refunded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_by TEXT,
                        FOREIGN KEY (payment_id) REFERENCES legal_payments(payment_id)
                    )
                """)

                # Get processed_by
                processed_by = None
                if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                    user = self.auth.current_user
                    processed_by = user.get('username') or user.get('user_id', '')

                cursor.execute("""
                    INSERT INTO legal_refunds
                    (payment_id, client_id, client_email, amount, refund_method, refund_reference, processed_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (payment_id, client_id, client_email, amount, 'student_account', refund_ref, processed_by))

                # Add to student finance account
                cursor.execute("""
                    UPDATE student_finance_accounts
                    SET balance = balance + ?
                    WHERE student_id = ?
                """, (amount, client_id))

                # Get new balance and account_id after update
                cursor.execute("SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?", (client_id,))
                result = cursor.fetchone()
                if result:
                    account_id, new_balance = result
                else:
                    account_id, new_balance = None, amount

                # Log transaction in student_finance_transactions
                cursor.execute("""
                    INSERT INTO student_finance_transactions
                    (account_id, student_id, transaction_type, amount, balance_after, description,
                     reference_id, processed_by, created_at)
                    VALUES (?, ?, 'credit', ?, ?, ?, ?, ?, ?)
                """, (account_id, client_id, amount, new_balance, f'Legal services refund - {refund_ref}',
                      refund_ref, processed_by, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

            # Log activity
            log_activity('refund', 'legal_payment',
                        details={'payment_id': payment_id, 'amount': amount, 'method': 'student_account', 'reference': refund_ref, 'new_balance': new_balance})

            # Send receipt
            self.send_legal_refund_receipt(client_email, amount, 'student_account', refund_ref, new_balance)

            # Notify finance GUI
            self.notify_legal_finance_gui(payment_id, amount, 'student_account', refund_ref)

            # Refresh list
            self.refresh_refunds_list()

            messagebox.showinfo(_t("common.success", default="Success"),
                              f"Refund added to student account!\n"
                              f"Reference: {refund_ref}\n"
                              f"New Balance: \u00a3{new_balance:.2f}")

        except Exception as e:
            logger.error(f"Error adding legal refund to student account: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to add refund to account: {str(e)}")

    def send_legal_refund_receipt(self, client_email, amount, refund_method, refund_ref, new_balance=None):
        """Send refund receipt email to client"""
        if not EMAIL_AVAILABLE or not client_email:
            logger.info("Email service not available or no email address, skipping receipt")
            return

        try:
            # Get client name
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT full_name FROM students WHERE student_id = (SELECT client_id FROM legal_payments WHERE transaction_reference = ?)",
                             (refund_ref,))
                result = cursor.fetchone()

                client_name = result[0] if result else client_email

            # Format refund method for display
            method_display = {
                'cash': 'Cash',
                'card': 'Card',
                'student_account': 'Student Finance Account'
            }.get(refund_method, refund_method)

            # Build balance text
            balance_text = ""
            if new_balance is not None:
                balance_text = f"\nYour new student account balance is: \u00a3{new_balance:.2f}"

            # Try to render from template
            subject = None
            email_body = None
            if render_template:
                subject, email_body = render_template('commerce/legal/refund_receipt', {
                    'client_name': client_name,
                    'refund_amount': f"\u00a3{amount:.2f}",
                    'refund_method': method_display,
                    'refund_ref': refund_ref,
                    'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'balance_text': balance_text
                })

            # Fallback if template not found
            if not subject or not email_body:
                subject = f"Legal Services Refund Receipt - {refund_ref}"
                email_body = f"""
Dear {client_name},

This is to confirm that your legal services refund has been processed successfully.

Refund Details:
- Refund Amount: \u00a3{amount:.2f}
- Refund Method: {method_display}
- Reference Number: {refund_ref}
- Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}
{balance_text}

If you have any questions about this refund, please contact the Legal Services Center.

Best regards,
University Legal Services Center
"""

            # Send email
            send_email(
                to_email=client_email,
                subject=subject,
                body=email_body
            )

            logger.info(f"Refund receipt sent to {client_email}")

        except Exception as e:
            logger.error(f"Error sending legal refund receipt: {e}")

    def notify_legal_finance_gui(self, payment_id, amount, refund_method, refund_ref):
        """Notify finance system about the refund"""
        try:
            with transaction() as conn:
                cursor = conn.cursor()

                # Create finance_refunds table if not exists
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS finance_refunds (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        refund_reference TEXT UNIQUE,
                        department TEXT,
                        transaction_id TEXT,
                        amount DECIMAL(10,2),
                        refund_method TEXT,
                        refund_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        processed_by TEXT,
                        notes TEXT
                    )
                """)

                # Get processed_by
                processed_by = None
                if self.auth and hasattr(self.auth, 'current_user') and self.auth.current_user:
                    user = self.auth.current_user
                    processed_by = user.get('username') or user.get('user_id', '')

                # Insert refund record
                cursor.execute("""
                    INSERT INTO finance_refunds
                    (refund_reference, department, transaction_id, amount, refund_method, processed_by, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (refund_ref, 'Legal Services', str(payment_id), amount, refund_method, processed_by,
                     'Legal services payment refund'))

            logger.info(f"Finance GUI notified of refund {refund_ref}")

        except Exception as e:
            logger.error(f"Error notifying finance GUI: {e}")

    def view_legal_payment_details(self):
        """View detailed information about a payment"""
        # Get selected payment
        selection = self.refunds_tree.selection()
        if not selection:
            messagebox.showwarning(_t("common.no_selection", default="No Selection"),
                                  _t("legal.refunds.select_payment_view", default="Please select a payment to view."))
            return

        item = self.refunds_tree.item(selection[0])
        values = item['values']
        payment_id = values[0]

        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Get payment details
                cursor.execute("""
                    SELECT
                        p.payment_id,
                        p.client_id,
                        p.client_email,
                        p.amount,
                        p.payment_type,
                        p.payment_method,
                        p.status,
                        p.transaction_reference,
                        p.created_at,
                        p.processed_by,
                        p.case_id,
                        p.consultation_id
                    FROM legal_payments p
                    WHERE p.payment_id = ?
                """, (payment_id,))

                payment = cursor.fetchone()

                if not payment:
                    messagebox.showerror(_t("common.error", default="Error"),
                                       _t("legal.refunds.payment_not_found", default="Payment not found."))
                    return

                (pid, client_id, client_email, amount, payment_type, payment_method,
                 status, reference, created_at, processed_by, case_id, consultation_id) = payment

                # Get case/consultation details
                service_details = ""
                if case_id:
                    cursor.execute("SELECT case_number, case_type FROM legal_cases WHERE case_id = ?", (case_id,))
                    case = cursor.fetchone()
                    if case:
                        service_details = f"\nCase Number: {case[0]}\nCase Type: {case[1]}"
                elif consultation_id:
                    cursor.execute("SELECT scheduled_date, scheduled_time FROM legal_consultations WHERE consultation_id = ?",
                                 (consultation_id,))
                    consultation = cursor.fetchone()
                    if consultation:
                        service_details = f"\nConsultation Date: {consultation[0]}\nConsultation Time: {consultation[1]}"

                # Create details window
                details_window = tk.Toplevel(self.window)
                details_window.title(_t("legal.refunds.payment_details", default="Payment Details"))
                details_window.geometry("600x600")
                details_window.transient(self.window)

                # Create scrollable text widget
                text_frame = ttk.Frame(details_window)
                text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

                text_widget = tk.Text(text_frame, wrap=tk.WORD, width=70, height=35)
                scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
                text_widget.configure(yscrollcommand=scrollbar.set)

                text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

                # Build details text
                details = f"""
LEGAL SERVICES PAYMENT DETAILS
{'=' * 50}

Payment Information:
  Payment ID: {pid}
  Status: {status}
  Reference: {reference or 'N/A'}
  Date: {created_at or 'N/A'}
  Processed By: {processed_by or 'N/A'}

Client Information:
  Client ID: {client_id}
  Email: {client_email or 'N/A'}

Service Details:
  Payment Type: {payment_type}{service_details}

Financial Details:
  Amount: \u00a3{amount:.2f}
  Payment Method: {payment_method or 'N/A'}

{'=' * 50}
"""

                text_widget.insert('1.0', details)
                text_widget.config(state='disabled')

                # Close button
                ttk.Button(details_window, text=_t("common.close", default="Close"),
                          command=details_window.destroy).pack(pady=10)

        except Exception as e:
            logger.error(f"Error viewing payment details: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to load details: {str(e)}")

    def export_refunds_to_csv(self):
        """Export refunds data to CSV file"""
        try:
            import csv

            # Ask for file location
            file_path = filedialog.asksaveasfilename(
                defaultextension='.csv',
                filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
                initialfile=f'legal_refunds_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            )

            if not file_path:
                return

            with get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT
                        p.payment_id,
                        p.created_at,
                        p.client_id,
                        p.client_email,
                        p.amount,
                        p.payment_type,
                        p.payment_method,
                        p.status,
                        p.transaction_reference
                    FROM legal_payments p
                    ORDER BY p.created_at DESC
                """)

                payments = cursor.fetchall()

            # Write to CSV
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)

                # Write header
                writer.writerow(['Payment ID', 'Date', 'Client ID', 'Client Email',
                               'Amount', 'Payment Type', 'Payment Method', 'Status', 'Reference'])

                # Write data
                for payment in payments:
                    payment_id, date, client_id, client_email, amount, payment_type, payment_method, status, reference = payment
                    writer.writerow([
                        payment_id,
                        date or '',
                        client_id,
                        client_email or '',
                        f'{amount:.2f}' if amount else '0.00',
                        payment_type or '',
                        payment_method or '',
                        status or 'completed',
                        reference or ''
                    ])

            messagebox.showinfo(_t("common.success", default="Success"),
                              f"Refunds exported successfully to:\n{file_path}")

        except Exception as e:
            logger.error(f"Error exporting refunds to CSV: {e}")
            messagebox.showerror(_t("common.error", default="Error"), f"Failed to export refunds: {str(e)}")
