"""Charity Shop - Refunds mixin for CharityShopApp."""

import csv

from ._imports import (
    tk, ttk, messagebox, filedialog, ScrolledText,
    datetime, json, sqlite3,
    DEFAULT_DB_PATH,
    FINANCE_INTEGRATION_AVAILABLE, EMAIL_SERVICE_AVAILABLE,
    get_student_finance_account_balance, get_student_info,
    send_email,
    logger,
)


class RefundsMixin:
    """Refund operations for CharityShopApp."""

    def show_refunds_window(self):
        """Display refunds management window"""
        refunds_window = tk.Toplevel(self.root)
        refunds_window.title("Charity Shop Refunds")
        refunds_window.geometry("900x600")
        refunds_window.transient(self.root)

        main_frame = ttk.Frame(refunds_window, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Header
        header_label = ttk.Label(main_frame, text="Charity Shop Transaction Refunds",
                                font=('Arial', 16, 'bold'))
        header_label.pack(pady=10)

        # Search frame
        search_frame = ttk.LabelFrame(main_frame, text="Search Transactions", padding="10")
        search_frame.pack(fill=tk.X, pady=5)

        ttk.Label(search_frame, text="Search by Transaction ID or Student ID:").pack(side=tk.LEFT, padx=5)
        refunds_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=refunds_search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)

        # Transactions table
        trans_frame = ttk.Frame(main_frame)
        trans_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ('transaction_id', 'date', 'student_id', 'amount', 'payment_method', 'status')
        refunds_tree = ttk.Treeview(trans_frame, columns=columns, show='headings', height=15)

        refunds_tree.heading('transaction_id', text='Transaction ID')
        refunds_tree.heading('date', text='Date')
        refunds_tree.heading('student_id', text='Student ID')
        refunds_tree.heading('amount', text='Amount')
        refunds_tree.heading('payment_method', text='Payment Method')
        refunds_tree.heading('status', text='Status')

        refunds_tree.column('transaction_id', width=200)
        refunds_tree.column('date', width=150)
        refunds_tree.column('student_id', width=120)
        refunds_tree.column('amount', width=100)
        refunds_tree.column('payment_method', width=130)
        refunds_tree.column('status', width=100)

        scrollbar = ttk.Scrollbar(trans_frame, orient=tk.VERTICAL, command=refunds_tree.yview)
        refunds_tree.configure(yscrollcommand=scrollbar.set)

        refunds_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def refresh_transactions_list():
            """Refresh the transactions list"""
            for item in refunds_tree.get_children():
                refunds_tree.delete(item)

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Ensure table exists
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS charity_shop_transactions (
                        transaction_id TEXT PRIMARY KEY,
                        transaction_date TEXT NOT NULL,
                        student_id TEXT,
                        total_amount REAL NOT NULL,
                        payment_method TEXT NOT NULL,
                        status TEXT DEFAULT 'completed',
                        items_json TEXT
                    )
                ''')

                search_term = refunds_search_var.get().strip()
                if search_term:
                    query = '''
                        SELECT transaction_id, transaction_date, student_id, total_amount,
                               payment_method, status
                        FROM charity_shop_transactions
                        WHERE transaction_id LIKE ? OR student_id LIKE ?
                        ORDER BY transaction_date DESC
                        LIMIT 500
                    '''
                    search_pattern = f'%{search_term}%'
                    cursor.execute(query, (search_pattern, search_pattern))
                else:
                    query = '''
                        SELECT transaction_id, transaction_date, student_id, total_amount,
                               payment_method, status
                        FROM charity_shop_transactions
                        ORDER BY transaction_date DESC
                        LIMIT 500
                    '''
                    cursor.execute(query)

                transactions = cursor.fetchall()

                for trans in transactions:
                    transaction_id, trans_date, student_id, amount, payment_method, status = trans

                    refunds_tree.insert('', tk.END, values=(
                        transaction_id,
                        trans_date,
                        student_id or 'Walk-in',
                        f"\u00a3{amount:.2f}",
                        payment_method,
                        status.upper()
                    ))

                conn.close()

            except Exception as e:
                messagebox.showerror("Database Error", f"Error loading transactions: {e}")

        def process_refund():
            """Process a refund for selected transaction"""
            selection = refunds_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a transaction to refund.")
                return

            item = refunds_tree.item(selection[0])
            values = item['values']

            if len(values) < 6:
                messagebox.showerror("Error", "Invalid transaction data.")
                return

            transaction_id = values[0]
            amount_str = values[3].replace('\u00a3', '').strip()
            try:
                amount = float(amount_str)
            except ValueError:
                messagebox.showerror("Error", "Invalid amount format.")
                return

            status = values[5]

            # Check if already refunded
            if status == 'REFUNDED':
                messagebox.showinfo("Already Refunded", "This transaction has already been refunded.")
                return

            # Confirm refund
            if not messagebox.askyesno("Confirm Refund", f"Process refund of \u00a3{amount:.2f} for transaction {transaction_id}?"):
                return

            # Get transaction details
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT student_id, payment_method
                    FROM charity_shop_transactions
                    WHERE transaction_id = ?
                ''', (transaction_id,))

                trans_data = cursor.fetchone()
                conn.close()

                if not trans_data:
                    messagebox.showerror("Error", "Transaction not found in database.")
                    return

                student_id = trans_data[0]
                payment_method = trans_data[1]

            except Exception as e:
                messagebox.showerror("Database Error", f"Error fetching transaction details: {e}")
                return

            # Show refund method dialog
            refund_method = self._show_charity_refund_method_dialog(refunds_window, amount, transaction_id, student_id)

            if not refund_method:
                return

            # Process refund
            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                # Update transaction status
                cursor.execute('''
                    UPDATE charity_shop_transactions
                    SET status = 'refunded'
                    WHERE transaction_id = ?
                ''', (transaction_id,))

                # Generate refund reference
                refund_ref = f"CHARITY-REFUND-{datetime.now().strftime('%Y%m%d%H%M%S')}"

                # Create refunds table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS charity_shop_refunds (
                        refund_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        transaction_id TEXT NOT NULL,
                        refund_date TEXT NOT NULL,
                        refund_amount REAL NOT NULL,
                        refund_method TEXT NOT NULL,
                        refund_reference TEXT UNIQUE,
                        student_id TEXT,
                        processed_by TEXT,
                        notes TEXT,
                        FOREIGN KEY (transaction_id) REFERENCES charity_shop_transactions (transaction_id)
                    )
                ''')

                # Insert refund record
                processed_by = self.current_user.get('username', 'System') if self.current_user else 'System'
                cursor.execute('''
                    INSERT INTO charity_shop_refunds
                    (transaction_id, refund_date, refund_amount, refund_method, refund_reference, student_id, processed_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (transaction_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), amount, refund_method,
                      refund_ref, student_id, processed_by))

                conn.commit()
                conn.close()

                # If student account refund, add to their account
                if refund_method == 'Student Account':
                    success = self._add_charity_refund_to_student_account(student_id, amount, refund_ref)
                    if not success:
                        messagebox.showwarning("Partial Success",
                                             "Refund recorded but failed to credit student account. Please credit manually.")

                # Send refund receipt email
                self._send_charity_refund_receipt(transaction_id, student_id, amount, refund_method, refund_ref)

                # Notify finance GUI
                self._notify_charity_finance_gui(transaction_id, amount, refund_method, refund_ref, student_id)

                messagebox.showinfo("Refund Processed",
                                  f"Refund of \u00a3{amount:.2f} processed successfully.\nRefund Reference: {refund_ref}")

                # Refresh the list
                refresh_transactions_list()

            except Exception as e:
                messagebox.showerror("Database Error", f"Error processing refund: {e}")

        def view_transaction_details():
            """View detailed transaction information"""
            selection = refunds_tree.selection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a transaction to view details.")
                return

            item = refunds_tree.item(selection[0])
            values = item['values']

            if len(values) < 6:
                messagebox.showerror("Error", "Invalid transaction data.")
                return

            transaction_id = values[0]

            try:
                conn = sqlite3.connect(str(DEFAULT_DB_PATH))
                cursor = conn.cursor()

                cursor.execute('''
                    SELECT transaction_id, transaction_date, student_id, total_amount,
                           payment_method, status, items_json
                    FROM charity_shop_transactions
                    WHERE transaction_id = ?
                ''', (transaction_id,))

                trans = cursor.fetchone()
                conn.close()

                if not trans:
                    messagebox.showerror("Error", "Transaction not found.")
                    return

                # Create details window
                details_window = tk.Toplevel(refunds_window)
                details_window.title(f"Transaction Details - {transaction_id}")
                details_window.geometry("500x500")
                details_window.transient(refunds_window)

                details_frame = ttk.Frame(details_window, padding=20)
                details_frame.pack(fill=tk.BOTH, expand=True)

                # Transaction information
                info_text = ScrolledText(details_frame, width=60, height=25, wrap=tk.WORD)
                info_text.pack(fill=tk.BOTH, expand=True)

                # Parse items
                items = []
                if trans[6]:
                    try:
                        items = json.loads(trans[6])
                    except (ValueError, json.JSONDecodeError):
                        pass

                items_text = ""
                for item in items:
                    subtotal = item['price'] * item['quantity']
                    items_text += f"\n{item['name']}\n"
                    items_text += f"  Quantity: {item['quantity']} x \u00a3{item['price']:.2f} = \u00a3{subtotal:.2f}\n"

                details = f"""TRANSACTION DETAILS
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550

Transaction ID:     {trans[0]}
Date:               {trans[1]}
Student ID:         {trans[2] or 'Walk-in Customer'}
Payment Method:     {trans[4]}
Status:             {trans[5].upper()}

\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
ITEMS PURCHASED
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
{items_text}

\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
TOTAL:              \u00a3{trans[3]:.2f}
\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550
"""

                info_text.insert('1.0', details)
                info_text.config(state='disabled')

                ttk.Button(details_frame, text="Close", command=details_window.destroy).pack(pady=10)

            except Exception as e:
                messagebox.showerror("Database Error", f"Error loading transaction details: {e}")

        def export_to_csv():
            """Export transactions list to CSV file"""
            try:
                filename = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile=f"charity_shop_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                )

                if not filename:
                    return

                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)

                    # Write header
                    writer.writerow(['Transaction ID', 'Date', 'Student ID', 'Amount',
                                   'Payment Method', 'Status'])

                    # Write data
                    for item in refunds_tree.get_children():
                        values = refunds_tree.item(item)['values']
                        writer.writerow(values)

                messagebox.showinfo("Export Successful", f"Data exported to:\n{filename}")

            except Exception as e:
                messagebox.showerror("Export Error", f"Error exporting data: {e}")

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Search", command=refresh_transactions_list).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Show All", command=lambda: [refunds_search_var.set(''), refresh_transactions_list()]).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Process Refund", command=process_refund).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="View Details", command=view_transaction_details).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export to CSV", command=export_to_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Close", command=refunds_window.destroy).pack(side=tk.LEFT, padx=5)

        # Initial load
        refresh_transactions_list()

    def _show_charity_refund_method_dialog(self, parent, amount, transaction_id, student_id):
        """Show dialog to select refund method"""
        dialog = tk.Toplevel(parent)
        dialog.title("Select Refund Method")
        dialog.geometry("400x350")
        dialog.transient(parent)
        dialog.grab_set()

        result = {'method': None}

        ttk.Label(dialog, text=f"Refund Amount: \u00a3{amount:.2f}", font=('Arial', 12, 'bold')).pack(pady=10)
        ttk.Label(dialog, text=f"Transaction ID: {transaction_id}").pack(pady=5)

        # Show student account balance if student_id available
        if student_id and FINANCE_INTEGRATION_AVAILABLE:
            try:
                current_balance = get_student_finance_account_balance(student_id)
                if current_balance is not None:
                    new_balance = current_balance + amount
                    balance_frame = ttk.LabelFrame(dialog, text="Student Finance Account", padding=10)
                    balance_frame.pack(pady=10, padx=20, fill=tk.X)

                    ttk.Label(balance_frame, text=f"Current Balance: \u00a3{current_balance:.2f}").pack(anchor='w')
                    ttk.Label(balance_frame, text=f"After Refund: \u00a3{new_balance:.2f}",
                            font=('Arial', 10, 'bold')).pack(anchor='w')
            except Exception as e:
                logger.error(f"Error getting balance: {e}")

        ttk.Label(dialog, text="Select refund method:", font=('Arial', 10)).pack(pady=10)

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)

        def select_cash():
            result['method'] = 'Cash'
            dialog.destroy()

        def select_card():
            result['method'] = 'Card'
            dialog.destroy()

        def select_student_account():
            if not student_id:
                messagebox.showerror("Error", "No student ID associated with this transaction.")
                return
            result['method'] = 'Student Account'
            dialog.destroy()

        ttk.Button(button_frame, text="Cash Refund", command=select_cash, width=20).pack(pady=5)
        ttk.Button(button_frame, text="Card Refund", command=select_card, width=20).pack(pady=5)

        if student_id and FINANCE_INTEGRATION_AVAILABLE:
            ttk.Button(button_frame, text="Student Finance Account", command=select_student_account, width=20).pack(pady=5)

        ttk.Button(button_frame, text="Cancel", command=dialog.destroy, width=20).pack(pady=10)

        dialog.wait_window()
        return result['method']

    def _add_charity_refund_to_student_account(self, student_id, amount, refund_ref):
        """Add refund amount to student finance account"""
        try:
            # Use finance integration if available for better handling
            if FINANCE_INTEGRATION_AVAILABLE:
                try:
                    from education_system.university_system.modules.shared.utils.finance_integration import top_up_student_finance_account
                    result = top_up_student_finance_account(
                        student_id=student_id,
                        amount=amount,
                        payment_method='Refund',
                        processed_by=self.current_user.get('username', 'System') if self.current_user else 'System',
                        description=f'Charity Shop Purchase Refund - {refund_ref}'
                    )
                    if result.get('success'):
                        logger.info(f"Refund credited to finance account for {student_id}: \u00a3{amount:.2f}")
                        return True
                    else:
                        logger.error(f"Finance integration failed: {result.get('message')}")
                        # Fall through to manual method
                except Exception as e:
                    logger.warning(f"Finance integration error, using fallback: {e}")
                    # Fall through to manual method

            # Fallback: Direct database update with correct schema
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Check if student finance account exists and get account_id and current balance
            cursor.execute('SELECT account_id, balance FROM student_finance_accounts WHERE student_id = ?', (student_id,))
            account = cursor.fetchone()

            if not account:
                # Create account with refund amount
                cursor.execute('''
                    INSERT INTO student_finance_accounts (student_id, balance, created_at)
                    VALUES (?, ?, ?)
                ''', (student_id, amount, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))

                # Get the newly created account_id
                cursor.execute('SELECT account_id FROM student_finance_accounts WHERE student_id = ?', (student_id,))
                account = cursor.fetchone()
                account_id = account[0]
                balance_before = 0.0
                balance_after = amount

                logger.info(f"Created new finance account for {student_id} with refund of \u00a3{amount:.2f}")
            else:
                account_id = account[0]
                balance_before = account[1]
                balance_after = balance_before + amount

                # Update existing account
                cursor.execute('''
                    UPDATE student_finance_accounts
                    SET balance = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE student_id = ?
                ''', (balance_after, student_id))
                logger.info(f"Updated finance account for {student_id}: +\u00a3{amount:.2f}")

            # Record transaction with correct schema
            processed_by = self.current_user.get('username', 'System') if self.current_user else 'System'
            cursor.execute('''
                INSERT INTO student_finance_transactions
                (account_id, student_id, transaction_type, amount, balance_before, balance_after,
                 description, reference_id, processed_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (account_id, student_id, 'credit', amount, balance_before, balance_after,
                  'Charity Shop Purchase Refund', refund_ref, processed_by))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"Error adding refund to student account: {e}")
            return False

    def _send_charity_refund_receipt(self, transaction_id, student_id, amount, method, refund_ref):
        """Send refund receipt email to customer"""
        try:
            if not student_id:
                logger.warning("No student ID available for email receipt")
                return

            # Get customer email
            customer_email = None
            customer_name = "Valued Customer"

            if FINANCE_INTEGRATION_AVAILABLE:
                student_info = get_student_info(student_id)
                if student_info:
                    customer_email = student_info.get('email')
                    customer_name = student_info.get('full_name', customer_name)

            if not customer_email:
                logger.warning(f"No email found for student {student_id}")
                return

            # Get updated balance if student account refund
            balance_text = ""
            if method == 'Student Account' and FINANCE_INTEGRATION_AVAILABLE:
                try:
                    new_balance = get_student_finance_account_balance(student_id)
                    if new_balance is not None:
                        balance_text = f"\n\nYour updated account balance is: \u00a3{new_balance:.2f}"
                except Exception:
                    logger.debug("Could not retrieve updated student finance balance")

            # Prepare template variables
            from education_system.university_system.infrastructure.email.template_utils import render_template

            template_vars = {
                'customer_name': customer_name,
                'transaction_id': transaction_id,
                'amount': f"{amount:.2f}",
                'method': method,
                'refund_ref': refund_ref,
                'refund_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'balance_text': balance_text
            }

            subject, body = render_template('commerce/charity_shop_payment_refund_receipt', template_vars)
            if not subject or not body:
                logger.error("Failed to render email template")
                return

            if EMAIL_SERVICE_AVAILABLE:
                result = send_email(customer_email, subject, body)
                if result:
                    logger.info(f"Refund receipt sent to {customer_email}")
                else:
                    logger.warning(f"Failed to send refund receipt to {customer_email}")

        except Exception as e:
            logger.error(f"Error sending refund receipt: {e}")

    def _notify_charity_finance_gui(self, transaction_id, amount, method, refund_ref, student_id):
        """Notify finance GUI about the refund"""
        try:
            conn = sqlite3.connect(str(DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Insert into finance_refunds table (use 'amount' column name to match existing schema)
            processed_by = self.current_user.get('username', 'System') if self.current_user else 'System'
            cursor.execute('''
                INSERT INTO finance_refunds
                (transaction_id, refund_date, amount, refund_method, refund_reference,
                 student_id, department, processed_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (transaction_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), amount, method,
                  refund_ref, student_id, 'Charity Shop', processed_by))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error notifying finance GUI: {e}")
