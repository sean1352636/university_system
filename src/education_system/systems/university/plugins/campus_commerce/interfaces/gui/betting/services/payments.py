"""Payment mixin."""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from ..shared import *


class PaymentMixin:
    def deposit_funds(self):
        """Deposit funds to account"""
        # Get student account balance - try student_id, then username, then user_id
        student_id = self.current_user.get('student_id') or self.current_user.get('username') or self.user_id
        student_balance = get_student_finance_account_balance(student_id)

        dialog = tk.Toplevel(self.window)
        dialog.title(_t("betting.btn.deposit", default="Deposit Funds"))
        dialog.geometry("400x350")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text=_t("betting.deposit_funds", default="Deposit Funds"), font=('Arial', 14, 'bold')).pack(pady=10)
        ttk.Label(dialog, text=f"User: {self.user_name}", font=('Arial', 10)).pack(pady=2)

        ttk.Label(dialog, text=_t("betting.labels.amount", default="Amount (GBP)") + f" ({MIN_DEPOSIT}-{MAX_DEPOSIT}):").pack(pady=5)
        amount_entry = ttk.Entry(dialog, width=20)
        amount_entry.insert(0, "50.00")
        amount_entry.pack(pady=5)

        ttk.Label(dialog, text=_t("betting.labels.payment_method", default="Payment Method") + ":", font=('Arial', 10, 'bold')).pack(pady=(10, 5))

        # Payment method radio buttons
        payment_method_var = tk.StringVar(value=_t('gui.operations.commerce.betting.services.payments.values.cash', default="Cash"))
        methods_frame = ttk.Frame(dialog)
        methods_frame.pack(pady=5)

        ttk.Radiobutton(methods_frame, text=_t("betting.payment_methods.cash", default="Cash"), variable=payment_method_var, value="Cash").pack(anchor=tk.W)
        ttk.Radiobutton(methods_frame, text=_t("betting.payment_methods.card", default="Card"), variable=payment_method_var, value="Card").pack(anchor=tk.W)

        # Student Account option with balance display
        student_frame = ttk.Frame(methods_frame)
        student_frame.pack(anchor=tk.W)
        ttk.Radiobutton(student_frame, text=_t("betting.payment_methods.student_account", default="Student Account"), variable=payment_method_var, value="Student Account").pack(side=tk.LEFT)
        balance_text = f" (Balance: £{student_balance:.2f})" if student_balance else " (No account)"
        ttk.Label(student_frame, text=balance_text, font=('Arial', 9)).pack(side=tk.LEFT)

        def confirm_deposit():
            try:
                amount = float(amount_entry.get())

                if amount < MIN_DEPOSIT or amount > MAX_DEPOSIT:
                    messagebox.showwarning(
                        _t("common.warning", default="Warning"),
                        f"Amount must be between GBP {MIN_DEPOSIT} and GBP {MAX_DEPOSIT}"
                    )
                    return

                method = payment_method_var.get()

                # Handle Student Account payment
                if method == "Student Account":
                    if student_balance < amount:
                        messagebox.showerror(
                            _t("common.error", default="Error"),
                            f"Insufficient balance. Current balance: £{student_balance:.2f}"
                        )
                        return
                    # Process student account payment
                    payment_result = process_student_finance_account_payment(
                        student_id=student_id,
                        amount=amount,
                        description="Betting shop deposit",
                        transaction_source="BettingShop",
                        transaction_ref=f"deposit_{self.user_id}",
                        processed_by=self.current_user.get('username', 'System')
                    )
                    if not payment_result.get('success'):
                        messagebox.showerror(_t("common.error", default="Error"), payment_result.get('message', "Failed to process student account payment"))
                        return

                transaction_id = AccountManager.deposit(
                    self.user_id, amount, method, self.current_user.get('username')
                )

                if transaction_id:
                    # Record revenue in central finance system
                    record_payment_to_finance(
                        student_id=student_id,
                        amount=amount,
                        payment_method=method,
                        transaction_source='BettingShop',
                        transaction_ref=f"DEP-{transaction_id}",
                        notes=f"Betting deposit via {method}",
                        created_by=self.current_user.get('username')
                    )
                    logger.info(f"Revenue recorded: £{amount:.2f} for betting deposit")

                    # Send receipt
                    self.send_deposit_receipt(amount, method, transaction_id)

                    self.update_balance_display()
                    self.load_transactions()

                    messagebox.showinfo(
                        _t("common.success", default="Success"),
                        _t("betting.messages.deposit_success", default="GBP {amount:.2f} deposited successfully!").format(amount=amount)
                    )
                    dialog.destroy()
                else:
                    messagebox.showerror(_t("common.error", default="Error"), _t('gui.operations.commerce.betting.services.payments.dialogs.deposit_failed', default="Deposit failed"))

            except ValueError:
                messagebox.showwarning(_t("common.warning", default="Warning"), _t('gui.operations.commerce.betting.services.payments.dialogs.please_enter_a_valid_amount', default="Please enter a valid amount"))

        ttk.Button(dialog, text=_t("betting.btn.deposit", default="Deposit"), command=confirm_deposit).pack(pady=20)

    def withdraw_funds(self):
        """Withdraw funds from account"""
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("betting.btn.withdraw", default="Withdraw Funds"))
        dialog.geometry("400x350")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(dialog, text=_t("betting.withdraw_funds", default="Withdraw Funds"), font=('Arial', 14, 'bold')).pack(pady=10)
        ttk.Label(dialog, text=f"Available: GBP {self.account['balance']:.2f}", font=('Arial', 11)).pack()

        ttk.Label(dialog, text=_t("betting.labels.amount", default="Amount (GBP)") + ":").pack(pady=5)
        amount_row = ttk.Frame(dialog)
        amount_row.pack(pady=5)
        amount_entry = ttk.Entry(amount_row, width=20)
        amount_entry.pack(side=tk.LEFT)

        def withdraw_all():
            """Fill the amount box with the full available balance."""
            amount_entry.delete(0, tk.END)
            amount_entry.insert(0, f"{self.account['balance']:.2f}")

        ttk.Button(
            amount_row,
            text=_t("betting.btn.withdraw_all", default="All"),
            width=6,
            command=withdraw_all,
        ).pack(side=tk.LEFT, padx=(6, 0))

        # Get student info for student account option
        student_id = self.current_user.get('student_id') or self.current_user.get('username') or self.user_id
        student_balance = None
        if FINANCE_AVAILABLE and student_id:
            try:
                student_balance = get_student_finance_account_balance(student_id)
            except Exception as e:
                logger.warning(f"Could not get student balance: {e}")

        ttk.Label(dialog, text=_t("betting.labels.payment_method", default="Withdraw To") + ":").pack(pady=5)

        # Add Student Finance Account option if available
        withdrawal_options = ['Bank Account', 'PayPal', 'Debit Card']
        if FINANCE_AVAILABLE and student_balance is not None:
            withdrawal_options.append('Student Finance Account')

        method_combo = ttk.Combobox(dialog, values=withdrawal_options, state='readonly', width=25)
        method_combo.set('Bank Account')
        method_combo.pack(pady=5)

        # Display student account balance if available
        balance_label = ttk.Label(dialog, text="", font=('Arial', 9), foreground='blue')
        balance_label.pack(pady=2)

        def update_balance_display(*args):
            if method_combo.get() == 'Student Finance Account' and student_balance is not None:
                balance_label.config(text=f"Current Student Account Balance: GBP {student_balance:.2f}")
            else:
                balance_label.config(text="")

        method_combo.bind('<<ComboboxSelected>>', update_balance_display)

        def confirm_withdrawal():
            try:
                amount = float(amount_entry.get())

                if amount > self.account['balance']:
                    messagebox.showwarning(_t("common.warning", default="Warning"), _t('gui.operations.commerce.betting.services.payments.dialogs.insufficient_balance', default="Insufficient balance"))
                    return

                if amount < 10:
                    messagebox.showwarning(_t("common.warning", default="Warning"), _t('gui.operations.commerce.betting.services.payments.dialogs.minimum_withdrawal_is_gbp_10', default="Minimum withdrawal is GBP 10"))
                    return

                method = method_combo.get()

                # Handle Student Finance Account withdrawal separately
                if method == 'Student Finance Account':
                    if not FINANCE_AVAILABLE:
                        messagebox.showerror(_t("common.error", default="Error"),
                                           _t('gui.operations.commerce.betting.services.payments.dialogs.student_finance_system_is_not_available', default="Student finance system is not available"))
                        return

                    success = self.withdraw_to_student_account(amount, student_id, student_balance)
                    if success:
                        dialog.destroy()
                    return

                # Regular withdrawal for other methods
                transaction_id = AccountManager.withdraw(
                    self.user_id, amount, method, self.current_user.get('username')
                )

                if transaction_id:
                    self.update_balance_display()
                    self.load_transactions()

                    # Send withdrawal confirmation email
                    self.send_withdrawal_receipt(amount, method, transaction_id)

                    messagebox.showinfo(
                        _t("common.success", default="Success"),
                        _t("betting.messages.withdrawal_success", default="GBP {amount:.2f} withdrawal processed!").format(amount=amount)
                    )
                    dialog.destroy()
                else:
                    messagebox.showerror(_t("common.error", default="Error"), _t('gui.operations.commerce.betting.services.payments.dialogs.withdrawal_failed', default="Withdrawal failed"))

            except ValueError:
                messagebox.showwarning(_t("common.warning", default="Warning"), _t('gui.operations.commerce.betting.services.payments.dialogs.please_enter_a_valid_amount', default="Please enter a valid amount"))

        ttk.Button(dialog, text=_t("betting.btn.withdraw", default="Withdraw"), command=confirm_withdrawal).pack(pady=20)

    def withdraw_to_student_account(self, amount: float, student_id: str, current_balance: float):
        """Withdraw betting funds to student finance account"""
        try:
            # Import the function to ensure student account exists
            from education_system.systems.university.domains.finance.infrastructure.finance_integration import ensure_student_finance_account_exists

            # Ensure student account exists
            ensure_student_finance_account_exists(student_id)

            # Get old balance
            old_balance = current_balance if current_balance is not None else 0.0
            new_balance = old_balance + amount

            # Withdraw from betting account first
            transaction_id = AccountManager.withdraw(
                self.user_id, amount, 'Student Finance Account', self.current_user.get('username')
            )

            if not transaction_id:
                messagebox.showerror(_t("common.error", default="Error"),
                                   _t('gui.operations.commerce.betting.services.payments.dialogs.failed_to_withdraw_from_betting_account', default="Failed to withdraw from betting account"))
                return False

            # Generate withdrawal reference
            withdrawal_ref = f"BETTING-WITHDRAWAL-{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Add funds to student finance account
            with transaction() as conn:
                cursor = conn.cursor()

                # Update student account balance
                cursor.execute('''
                    UPDATE student_finance_accounts
                    SET balance = balance + ?
                    WHERE student_id = ?
                ''', (amount, student_id))

                # Get account_id for the transaction
                cursor.execute('''
                    SELECT account_id FROM student_finance_accounts WHERE student_id = ?
                ''', (student_id,))
                account_result = cursor.fetchone()
                account_id = account_result[0] if account_result else None

                # Log transaction in student finance system
                cursor.execute('''
                    INSERT INTO transactions
                    (source_type, account_id, student_id, transaction_type, amount, balance_after, description,
                     reference_id, processed_by, created_at)
                    VALUES ('student_finance', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (account_id, student_id, 'credit', amount, new_balance,
                      f'Betting shop withdrawal - {withdrawal_ref}',
                      withdrawal_ref,
                      self.current_user.get('username', 'System'),
                      datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

            # Update UI
            self.update_balance_display()
            self.load_transactions()

            # Send confirmation email
            self.send_withdrawal_receipt(amount, 'Student Finance Account', transaction_id,
                                        old_balance, new_balance, withdrawal_ref)

            # Show success message
            messagebox.showinfo(
                _t("common.success", default="Success"),
                f"GBP {amount:.2f} successfully withdrawn to your student account!\n\n"
                f"Withdrawal Reference: {withdrawal_ref}\n"
                f"Old Balance: GBP {old_balance:.2f}\n"
                f"New Balance: GBP {new_balance:.2f}"
            )

            # Log activity
            log_activity(
                'betting_withdrawal_to_student_account',
                'betting_shop',
                user=self.current_user.get('username'),
                details={
                    'amount': amount,
                    'withdrawal_ref': withdrawal_ref,
                    'student_id': student_id
                }
            )

            return True

        except Exception as e:
            logger.error(f"Error withdrawing to student account: {e}")
            messagebox.showerror(_t("common.error", default="Error"),
                               f"Error processing withdrawal to student account: {str(e)}")
            return False

    def record_revenue_transaction(self, amount: float, description: str):
        """Record deposit as revenue in finance system.

        8.117.104: routed through unified record_payment() with
        source_type='betting'.
        """
        try:
            from education_system.systems.university.domains.finance.domain.core.unified_payments import (
                record_payment as _record_payment,
            )
            _record_payment(
                student_id=self.user_id,
                amount=amount,
                payment_method='betting_deposit',
                source_type='betting',
                payment_type='deposit',
                department='betting',
                description=description,
                created_by=self.current_user.get('username'),
            )
        except Exception as e:
            print(f"Error recording revenue: {e}")
