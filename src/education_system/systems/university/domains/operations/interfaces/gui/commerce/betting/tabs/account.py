"""AccountTab mixin."""

from ..shared import *


class AccountTabMixin:
    def create_account_tab(self):
        """Create account management tab"""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t("betting.tabs.account", default="My Account"))

        # Account info
        info_frame = ttk.LabelFrame(tab, text=_t("betting.account_info", default="Account Information"), padding="15")
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        info_grid = ttk.Frame(info_frame)
        info_grid.pack()

        ttk.Label(info_grid, text=_t("betting.labels.username", default="Username") + ":").grid(row=0, column=0, sticky=tk.W, pady=3)
        ttk.Label(info_grid, text=self.current_user.get('username', 'N/A'), font=('Arial', 10, 'bold')).grid(row=0, column=1, sticky=tk.W, padx=10)

        ttk.Label(info_grid, text=_t("betting.labels.balance", default="Balance") + ":").grid(row=1, column=0, sticky=tk.W, pady=3)
        self.account_balance_var = tk.StringVar(value=f"GBP {self.account['balance']:.2f}" if self.account else "GBP 0.00")
        ttk.Label(info_grid, textvariable=self.account_balance_var, font=('Arial', 12, 'bold'), foreground='green').grid(row=1, column=1, sticky=tk.W, padx=10)

        ttk.Label(info_grid, text=_t("betting.labels.total_deposited", default="Total Deposited") + ":").grid(row=2, column=0, sticky=tk.W, pady=3)
        ttk.Label(info_grid, text=f"GBP {self.account.get('total_deposited', 0):.2f}" if self.account else "GBP 0.00").grid(row=2, column=1, sticky=tk.W, padx=10)

        ttk.Label(info_grid, text=_t("betting.labels.total_wagered", default="Total Wagered") + ":").grid(row=3, column=0, sticky=tk.W, pady=3)
        ttk.Label(info_grid, text=f"GBP {self.account.get('total_wagered', 0):.2f}" if self.account else "GBP 0.00").grid(row=3, column=1, sticky=tk.W, padx=10)

        ttk.Label(info_grid, text=_t("betting.labels.total_won", default="Total Won") + ":").grid(row=4, column=0, sticky=tk.W, pady=3)
        ttk.Label(info_grid, text=f"GBP {self.account.get('total_won', 0):.2f}" if self.account else "GBP 0.00").grid(row=4, column=1, sticky=tk.W, padx=10)

        # Actions
        action_frame = ttk.LabelFrame(tab, text=_t("betting.actions", default="Actions"), padding="10")
        action_frame.pack(fill=tk.X, padx=10, pady=10)

        btn_grid = ttk.Frame(action_frame)
        btn_grid.pack()

        ttk.Button(btn_grid, text=_t("betting.btn.deposit", default="Deposit Funds"), command=self.deposit_funds, width=20).grid(row=0, column=0, padx=10, pady=5)
        ttk.Button(btn_grid, text=_t("betting.btn.withdraw", default="Withdraw Funds"), command=self.withdraw_funds, width=20).grid(row=0, column=1, padx=10, pady=5)
        ttk.Button(btn_grid, text=_t("betting.btn.view_history", default="View Bet History"), command=self.view_bet_history, width=20).grid(row=1, column=0, padx=10, pady=5)
        ttk.Button(btn_grid, text=_t("betting.btn.cash_out", default="Cash Out Bet"), command=self.cash_out_bet, width=20).grid(row=1, column=1, padx=10, pady=5)
        ttk.Button(btn_grid, text=_t("betting.btn.view_transactions", default="View Transactions"), command=self.view_transactions, width=20).grid(row=2, column=0, padx=10, pady=5)
        ttk.Button(btn_grid, text=_t("betting.btn.view_odds", default="View Current Odds"), command=self.view_odds, width=20).grid(row=2, column=1, padx=10, pady=5)

        # Transaction history
        history_frame = ttk.LabelFrame(tab, text=_t("betting.recent_transactions", default="Recent Transactions"), padding="10")
        history_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ('date', 'type', 'amount', 'balance')
        self.trans_tree = ttk.Treeview(history_frame, columns=columns, show='headings', height=8)

        self.trans_tree.heading('date', text=_t("betting.labels.date", default="Date"))
        self.trans_tree.heading('type', text=_t("betting.labels.type", default="Type"))
        self.trans_tree.heading('amount', text=_t("betting.labels.amount", default="Amount"))
        self.trans_tree.heading('balance', text=_t("betting.labels.balance", default="Balance"))

        self.trans_tree.column('date', width=150)
        self.trans_tree.column('type', width=100)
        self.trans_tree.column('amount', width=100)
        self.trans_tree.column('balance', width=100)

        self.trans_tree.pack(fill=tk.BOTH, expand=True)

        self.load_transactions()

    def load_transactions(self):
        """Load recent transactions"""
        try:
            for item in self.trans_tree.get_children():
                self.trans_tree.delete(item)

            transactions = AccountManager.get_transaction_history(self.user_id, limit=20)

            for trans in transactions:
                self.trans_tree.insert('', tk.END, values=(
                    trans['created_at'][:19],
                    trans['transaction_type'].title(),
                    f"GBP {trans['amount']:.2f}",
                    f"GBP {trans['balance_after']:.2f}"
                ))

        except Exception as e:
            print(f"Error loading transactions: {e}")

    def view_transactions(self):
        """View full transaction history"""
        try:
            transactions = AccountManager.get_transaction_history(self.user_id, limit=100)

            dialog = tk.Toplevel(self.window)
            dialog.title(_t("betting.transaction_history", default="Transaction History"))
            dialog.geometry("600x500")
            dialog.transient(self.window)

            text = scrolledtext.ScrolledText(dialog, wrap=tk.WORD, font=('Courier', 10))
            text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            if transactions:
                history = "TRANSACTION HISTORY\n" + "="*60 + "\n\n"
                for trans in transactions:
                    history += f"Date: {trans['created_at']}\n"
                    history += f"Type: {trans['transaction_type'].upper()}\n"
                    history += f"Amount: GBP {trans['amount']:.2f}\n"
                    history += f"Balance: GBP {trans['balance_after']:.2f}\n"
                    history += f"Reference: {trans.get('reference', 'N/A')}\n"
                    history += "-"*40 + "\n\n"
            else:
                history = "No transactions yet."

            text.insert('1.0', history)
            text.config(state='disabled')

            ttk.Button(dialog, text=_t("common.close", default="Close"), command=dialog.destroy).pack(pady=10)

        except Exception as e:
            messagebox.showerror(_t("common.error", default="Error"), str(e))
