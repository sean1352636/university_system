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

                # Student Account: pre-check the balance for a clear message;
                # the debit and the Finance posting happen in AccountManager.deposit
                if method == "Student Account":
                    if (student_balance or 0) < amount:
                        messagebox.showerror(
                            _t("common.error", default="Error"),
                            f"Insufficient balance. Current balance: £{(student_balance or 0):.2f}"
                        )
                        return

                transaction_id = AccountManager.deposit(
                    self.user_id, amount, method, self.current_user.get('username'),
                    student_id=student_id,
                )

                if transaction_id:
                    logger.info(f"Deposit recorded: £{amount:.2f} via {method}")

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
        """Withdraw betting funds to student finance account (via the betting service)."""
        try:
            old_balance = current_balance if current_balance is not None else 0.0

            result = AccountManager.withdraw_to_student_account(
                self.user_id, amount, student_id, self.current_user.get('username')
            )
            transaction_id = result.get('transaction_id')
            if not transaction_id:
                messagebox.showerror(_t("common.error", default="Error"),
                                   _t('gui.operations.commerce.betting.services.payments.dialogs.failed_to_withdraw_from_betting_account', default="Failed to withdraw from betting account"))
                return False
            if result.get('new_balance') is None:
                messagebox.showerror(_t("common.error", default="Error"),
                                   f"Error processing withdrawal to student account: {result.get('message')}")
                return False

            withdrawal_ref = result['reference']
            new_balance = float(result['new_balance'])

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
