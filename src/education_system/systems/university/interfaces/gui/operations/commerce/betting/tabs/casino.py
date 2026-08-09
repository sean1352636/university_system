"""CasinoTab mixin."""

from ..shared import *


class CasinoTabMixin:
    def create_casino_tab(self):
        """Create casino games tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("betting.tabs.casino", default="Casino"))

        # Arcade games: standalone games launched in their own windows.
        self._create_arcade_games(tab)

        # History button
        btn_frame2 = ttk.Frame(tab)
        btn_frame2.pack(fill=tk.X, padx=10, pady=5)
        ttk.Button(btn_frame2, text=_t("betting.btn.view_history", default="View Game History"), command=self.view_game_history).pack(side=tk.RIGHT)

    def _create_arcade_games(self, tab):
        """Build a grid of buttons that launch the standalone arcade games.

        Each game runs in its own window/process (see the games package), so
        clicking a button opens the game independently of this application.
        """
        from education_system.systems.university.interfaces.gui.operations.commerce.betting.games import GAMES

        # Shared credit wallet bar: all arcade games play against these credits,
        # which roll over from one game to the next.
        wallet_frame = ttk.LabelFrame(
            tab, text=_t("betting.arcade_credits", default="Arcade Credits"), padding="10"
        )
        wallet_frame.pack(fill=tk.X, padx=10, pady=(10, 0))

        ttk.Label(
            wallet_frame,
            text=_t("betting.credits", default="Credits") + ": ",
            font=("Arial", 11),
        ).pack(side=tk.LEFT)
        self.credits_var = tk.StringVar()
        ttk.Label(
            wallet_frame, textvariable=self.credits_var, font=("Arial", 12, "bold"),
            foreground="#b8860b",
        ).pack(side=tk.LEFT)
        ttk.Button(
            wallet_frame, text=_t("betting.btn.buy_credits", default="Buy Credits"),
            command=self.buy_credits,
        ).pack(side=tk.LEFT, padx=(10, 4))
        ttk.Button(
            wallet_frame, text=_t("betting.btn.cash_out", default="Cash Out"),
            command=self.cash_out_credits,
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(
            wallet_frame, text=_t("betting.btn.refresh", default="Refresh"),
            command=self.update_credits_display,
        ).pack(side=tk.LEFT)
        ttk.Label(
            wallet_frame,
            text=_t(
                "betting.arcade_credits_hint",
                default="  (1 credit = GBP 1, buy from or cash out to your betting balance)",
            ),
            font=("Arial", 9), foreground="grey",
        ).pack(side=tk.LEFT)
        self.update_credits_display()

        arcade_frame = ttk.LabelFrame(
            tab, text=_t("betting.arcade_games", default="Arcade Games"), padding="10"
        )
        arcade_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        columns = 5
        for index, (filename, label) in enumerate(GAMES):
            row, col = divmod(index, columns)
            ttk.Button(
                arcade_frame,
                text=label,
                width=18,
                command=lambda f=filename, name=label: self._launch_arcade_game(f, name),
            ).grid(row=row, column=col, padx=5, pady=5, sticky="ew")

        for col in range(columns):
            arcade_frame.columnconfigure(col, weight=1)

    def _launch_arcade_game(self, filename, name):
        """Launch a single arcade game in its own window."""
        from education_system.systems.university.interfaces.gui.operations.commerce.betting.games import (
            launch_game,
        )

        try:
            launch_game(filename, name, user=self.user_id)
        except Exception as exc:  # pragma: no cover - defensive UI guard
            messagebox.showerror(
                _t("betting.arcade_launch_failed", default="Could not launch game"),
                _t(
                    "betting.arcade_launch_failed_msg",
                    default="Failed to launch {name}:\n{error}",
                ).format(name=name, error=exc),
            )
            return
        # Games run in their own process against the shared wallet; refresh the
        # credit display so the balance updates once the player returns.
        self.update_credits_display()

    def update_credits_display(self):
        """Refresh the arcade credit balance shown on the casino tab."""
        from education_system.systems.university.interfaces.gui.operations.commerce.betting.games import (
            wallet,
        )

        try:
            self.credits_var.set(str(wallet.get_credits(user=self.user_id)))
        except Exception:  # pragma: no cover - defensive UI guard
            self.credits_var.set("0")

    def buy_credits(self):
        """Buy arcade credits from the student's betting account balance (1:1)."""
        from education_system.systems.university.interfaces.gui.operations.commerce.betting.games import (
            wallet,
        )

        amount = simpledialog.askinteger(
            _t("betting.buy_credits", default="Buy Credits"),
            _t(
                "betting.prompts.buy_credits",
                default="How many credits to buy? (GBP 1 each)",
            ),
            initialvalue=100,
            minvalue=1,
            parent=self.window,
        )
        if not amount:
            return

        # Ensure the betting account can cover the purchase.
        self.account = AccountManager.get_account(self.user_id)
        balance = self.account["balance"] if self.account else 0
        if balance < amount:
            messagebox.showerror(
                _t("betting.errors.insufficient_title", default="Insufficient balance"),
                _t(
                    "betting.errors.insufficient_credits",
                    default=(
                        "You need GBP {amount:.2f} but your betting balance is "
                        "GBP {balance:.2f}. Deposit more funds first."
                    ),
                ).format(amount=float(amount), balance=float(balance)),
            )
            return

        # Debit the real betting account, then credit the arcade wallet.
        txn = AccountManager.withdraw(self.user_id, float(amount), "arcade_credits")
        if not txn:
            messagebox.showerror(
                _t("betting.errors.purchase_failed_title", default="Purchase failed"),
                _t(
                    "betting.errors.purchase_failed",
                    default="Could not debit your betting account. No credits were bought.",
                ),
            )
            return

        new_total = wallet.buy_credits(amount, user=self.user_id)
        self.update_balance_display()
        self.update_credits_display()

        # Email the buyer a receipt for the purchase.
        self.send_credits_receipt("purchase", amount, new_total, txn)

        messagebox.showinfo(
            _t("betting.buy_credits", default="Buy Credits"),
            _t(
                "betting.msgs.credits_bought",
                default=(
                    "Bought {amount} credits. Arcade balance: {total} credits.\n"
                    "A receipt has been emailed to you."
                ),
            ).format(amount=amount, total=new_total),
        )

    def _ask_cash_out_amount(self, current, min_cash, max_cash):
        """Prompt for how many credits to cash out.

        Offers a "Cash Out All" button (fills in the maximum allowed) as well
        as free-form entry of a number. Returns the chosen integer amount, or
        ``None`` if the user cancels or enters an invalid/out-of-range value.
        """
        dialog = tk.Toplevel(self.window)
        dialog.title(_t("betting.cash_out", default="Cash Out"))
        dialog.geometry("360x200")
        dialog.transient(self.window)
        dialog.grab_set()

        ttk.Label(
            dialog,
            text=_t("betting.cash_out", default="Cash Out"),
            font=("Arial", 14, "bold"),
        ).pack(pady=10)
        ttk.Label(
            dialog,
            text=_t(
                "betting.prompts.cash_out",
                default="How many credits to cash out? (GBP 1 each, {min}-{max})",
            ).format(min=min_cash, max=max_cash),
        ).pack(pady=2)

        amount_row = ttk.Frame(dialog)
        amount_row.pack(pady=8)
        amount_entry = ttk.Entry(amount_row, width=18)
        amount_entry.insert(0, str(max_cash))
        amount_entry.pack(side=tk.LEFT)

        def cash_out_all():
            amount_entry.delete(0, tk.END)
            amount_entry.insert(0, str(max_cash))

        ttk.Button(
            amount_row,
            text=_t("betting.btn.cash_out_all", default="All"),
            width=6,
            command=cash_out_all,
        ).pack(side=tk.LEFT, padx=(6, 0))

        result = {"amount": None}

        def confirm():
            try:
                value = int(float(amount_entry.get()))
            except (TypeError, ValueError):
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t("betting.errors.invalid_amount", default="Please enter a valid amount"),
                    parent=dialog,
                )
                return
            if value < min_cash or value > max_cash:
                messagebox.showwarning(
                    _t("common.warning", default="Warning"),
                    _t(
                        "betting.errors.cash_out_range",
                        default="Amount must be between {min} and {max} credits.",
                    ).format(min=min_cash, max=max_cash),
                    parent=dialog,
                )
                return
            result["amount"] = value
            dialog.destroy()

        ttk.Button(
            dialog, text=_t("betting.btn.cash_out", default="Cash Out"), command=confirm
        ).pack(pady=12)

        dialog.wait_window()
        return result["amount"]

    def cash_out_credits(self):
        """Convert arcade credits back into betting-account funds (1:1)."""
        from education_system.systems.university.interfaces.gui.operations.commerce.betting.games import (
            wallet,
        )

        current = wallet.get_credits(user=self.user_id)
        # Cash-out is an internal credit->funds transfer (via credit_funds),
        # so the card-deposit MAX_DEPOSIT ceiling does not apply. The user can
        # cash out anything from MIN_DEPOSIT up to their full credit balance.
        min_cash = int(MIN_DEPOSIT)
        max_cash = current
        if current < min_cash:
            messagebox.showinfo(
                _t("betting.cash_out", default="Cash Out"),
                _t(
                    "betting.msgs.below_min_cash_out",
                    default=(
                        "You need at least {min} credits to cash out "
                        "(minimum GBP {min:.2f}). You have {current}."
                    ),
                ).format(min=min_cash, current=current),
            )
            return

        amount = self._ask_cash_out_amount(current, min_cash, max_cash)
        if not amount:
            return

        # Deduct the arcade credits first, then pay the funds into the betting
        # account. If the deposit fails, refund the credits so nothing is lost.
        new_total = wallet.set_credits(current - amount, user=self.user_id)
        txn = AccountManager.credit_funds(self.user_id, float(amount), "arcade_credits")
        if not txn:
            wallet.set_credits(current, user=self.user_id)  # refund
            self.update_credits_display()
            messagebox.showerror(
                _t("betting.errors.cash_out_failed_title", default="Cash out failed"),
                _t(
                    "betting.errors.cash_out_failed",
                    default="Could not credit your betting account. Your credits were kept.",
                ),
            )
            return

        self.update_balance_display()
        self.update_credits_display()

        # Email the user a receipt for the cash-out.
        self.send_credits_receipt("cash_out", amount, new_total, txn)

        messagebox.showinfo(
            _t("betting.cash_out", default="Cash Out"),
            _t(
                "betting.msgs.credits_cashed_out",
                default=(
                    "Cashed out {amount} credits to GBP {amount:.2f}. "
                    "Arcade balance: {total} credits.\n"
                    "A receipt has been emailed to you."
                ),
            ).format(amount=amount, total=new_total),
        )

    def send_credits_receipt(self, kind, amount, new_total, transaction_id):
        """Email a receipt for an arcade-credit purchase or cash-out.

        ``kind`` is ``"purchase"`` (money -> credits) or ``"cash_out"``
        (credits -> money). Mirrors the deposit/withdrawal receipt behaviour:
        silently skips if email is unavailable or the user has no valid address.
        """
        user_email = self.user_email or (self.account.get("email", "") if self.account else "")
        if not EMAIL_AVAILABLE or not user_email or "@" not in user_email:
            logger.info(f"Credit receipt email skipped - invalid email: {user_email}")
            return

        if kind == "purchase":
            title = "Arcade Credit Purchase"
            detail_line = f"Credits Purchased:     {amount} (GBP {float(amount):.2f} debited)"
            note = "Your credits are ready to play in the betting shop arcade."
        else:
            title = "Arcade Credit Cash-Out"
            detail_line = f"Credits Cashed Out:    {amount} (GBP {float(amount):.2f} credited)"
            note = "The funds have been added to your betting account balance."

        betting_balance = f"GBP {self.account['balance']:.2f}" if self.account else "GBP 0.00"
        template_vars = {
            "user_name": self.user_name,
            "title": title,
            "title_lower": title.lower(),
            "title_upper": title.upper(),
            "amount": f"GBP {float(amount):.2f}",
            "transaction_id": transaction_id,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "detail_line": detail_line,
            "credit_balance": f"{new_total} credits",
            "betting_balance": betting_balance,
            "note": note,
        }

        # Render from the shared JSON template; fall back to an inline body if
        # the template is unavailable (mirrors the deposit/withdrawal receipts).
        subject = body = None
        if render_template:
            subject, body = render_template("commerce/betting/credit_receipt", template_vars)
        if not subject or not body:
            subject = f"{title} - GBP {float(amount):.2f}"
            body = (
                f"Dear {self.user_name},\n\n"
                f"This confirms your {title.lower()} at the University Betting Shop.\n\n"
                f"Transaction ID:        {transaction_id}\n"
                f"Date:                  {template_vars['date']}\n"
                f"{detail_line}\n"
                f"Arcade Credit Balance: {new_total} credits\n"
                f"Betting Account Balance: {betting_balance}\n\n"
                f"{note}\n\nPlease gamble responsibly.\n\nUniversity Betting Shop"
            )

        try:
            result = send_email(recipient_email=user_email, subject=subject, body=body)
            if result:
                logger.info(f"Credit {kind} receipt email sent to {user_email}")
            else:
                logger.warning(f"Failed to send credit {kind} receipt email to {user_email}")
        except Exception as e:
            logger.error(f"Error sending credit {kind} receipt email: {e}")

    def view_game_history(self):
        """View arcade game history (credit changes recorded by the games)."""
        from education_system.systems.university.interfaces.gui.operations.commerce.betting.games import (
            wallet,
        )

        try:
            plays = wallet.get_history(limit=100, user=self.user_id)

            dialog = tk.Toplevel(self.window)
            dialog.title(_t("betting.game_history", default="Game History"))
            dialog.geometry("600x500")
            dialog.transient(self.window)

            text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=('Courier', 10))
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            if plays:
                history = "ARCADE GAME HISTORY\n" + "=" * 60 + "\n\n"
                for play in plays:
                    change = play.get("change", 0)
                    sign = "+" if change >= 0 else ""
                    history += f"Game:    {play.get('game', 'Arcade')}\n"
                    history += f"Result:  {sign}{change} credits\n"
                    history += f"Balance: {play.get('balance', 0)} credits\n"
                    history += f"Played:  {play.get('played_at', '')}\n"
                    history += "-" * 40 + "\n\n"
            else:
                history = "No arcade games played yet."

            text.insert('1.0', history)
            text.config(state='disabled')

            ttk.Button(dialog, text=_t("common.close", default="Close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
