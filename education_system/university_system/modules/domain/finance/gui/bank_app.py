#!/usr/bin/env python3
"""
University Bank GUI Application
A Python tkinter-based banking application integrated with the Student Finance System.
Shows student finance account, allows deposits/top-ups, and displays transaction history.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
import hashlib
from education_system.university_system.infrastructure.database.db import sqlite3
from education_system.university_system.modules.shared.utils.i18n import get_text as _t

# Try to import finance integration
try:
    from education_system.university_system.modules.shared.utils.finance_integration import (
        get_student_finance_account_balance,
        ensure_student_finance_account_exists,
        top_up_student_finance_account,
        get_student_financial_summary,
        get_student_info,
        _ensure_finance_tables_exist
    )
    from education_system.university_system.modules.shared.constants import paths
    FINANCE_INTEGRATION_AVAILABLE = True
except ImportError:
    FINANCE_INTEGRATION_AVAILABLE = False
    paths = None

# --- Data Models for Standalone Mode ---

@dataclass
class Transaction:
    """Represents a single transaction."""
    timestamp: str
    type: str
    amount: float
    balance_after: float
    description: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

@dataclass
class Account:
    """Represents a bank account."""
    account_number: str
    holder_name: str
    pin_hash: str
    balance: float = 0.0
    transactions: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def deposit(self, amount: float, description: str = "") -> Transaction:
        """Deposit money into the account."""
        self.balance += amount
        txn = Transaction(
            timestamp=datetime.now().isoformat(),
            type="deposit",
            amount=amount,
            balance_after=self.balance,
            description=description or "Cash deposit"
        )
        self.transactions.append(txn)
        return txn

    def withdraw(self, amount: float, description: str = "") -> Optional[Transaction]:
        """Withdraw money from the account."""
        if amount > self.balance:
            return None
        self.balance -= amount
        txn = Transaction(
            timestamp=datetime.now().isoformat(),
            type="withdrawal",
            amount=amount,
            balance_after=self.balance,
            description=description or "Cash withdrawal"
        )
        self.transactions.append(txn)
        return txn

    def to_dict(self):
        return {
            "account_number": self.account_number,
            "holder_name": self.holder_name,
            "pin_hash": self.pin_hash,
            "balance": self.balance,
            "transactions": [t.to_dict() for t in self.transactions],
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data):
        transactions = [Transaction.from_dict(t) for t in data.get("transactions", [])]
        return cls(
            account_number=data["account_number"],
            holder_name=data["holder_name"],
            pin_hash=data["pin_hash"],
            balance=data["balance"],
            transactions=transactions,
            created_at=data.get("created_at", datetime.now().isoformat())
        )

class Bank:
    """Manages all bank accounts and operations (standalone mode)."""

    def __init__(self, data_file: str = "bank_data.json"):
        self.data_file = data_file
        self.accounts: dict[str, Account] = {}
        self.next_account_number = 1001
        self.load_data()

    def hash_pin(self, pin: str) -> str:
        return hashlib.sha256(pin.encode()).hexdigest()

    def create_account(self, holder_name: str, pin: str, initial_deposit: float = 0) -> Account:
        account_number = str(self.next_account_number)
        self.next_account_number += 1

        account = Account(
            account_number=account_number,
            holder_name=holder_name,
            pin_hash=self.hash_pin(pin),
            balance=0.0
        )

        if initial_deposit > 0:
            account.deposit(initial_deposit, "Initial deposit")

        self.accounts[account_number] = account
        self.save_data()
        return account

    def authenticate(self, account_number: str, pin: str) -> Optional[Account]:
        account = self.accounts.get(account_number)
        if account and account.pin_hash == self.hash_pin(pin):
            return account
        return None

    def get_account(self, account_number: str) -> Optional[Account]:
        return self.accounts.get(account_number)

    def transfer(self, from_account: Account, to_account_number: str, amount: float) -> bool:
        to_account = self.accounts.get(to_account_number)
        if not to_account or amount > from_account.balance:
            return False

        from_account.balance -= amount
        from_txn = Transaction(
            timestamp=datetime.now().isoformat(),
            type="transfer_out",
            amount=amount,
            balance_after=from_account.balance,
            description=f"Transfer to {to_account_number}"
        )
        from_account.transactions.append(from_txn)

        to_account.balance += amount
        to_txn = Transaction(
            timestamp=datetime.now().isoformat(),
            type="transfer_in",
            amount=amount,
            balance_after=to_account.balance,
            description=f"Transfer from {from_account.account_number}"
        )
        to_account.transactions.append(to_txn)

        self.save_data()
        return True

    def save_data(self):
        data = {
            "next_account_number": self.next_account_number,
            "accounts": {num: acc.to_dict() for num, acc in self.accounts.items()}
        }
        with open(self.data_file, "w") as f:
            json.dump(data, f, indent=2)

    def load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r") as f:
                    data = json.load(f)
                self.next_account_number = data.get("next_account_number", 1001)
                self.accounts = {
                    num: Account.from_dict(acc)
                    for num, acc in data.get("accounts", {}).items()
                }
            except (json.JSONDecodeError, KeyError):
                pass

# --- GUI Application ---

class BankApp:
    """Main banking application window with Student Finance integration."""

    def __init__(self, parent=None, auth=None):
        """
        Initialize the Bank App.

        Args:
            parent: Parent Tk window (None for standalone mode)
            auth: Authentication manager from the university system (for integration)
        """
        # Store auth reference
        self.auth = auth
        self.student_id = None
        self.student_info = None
        self.is_student_mode = False

        # If parent is provided, use it; otherwise create a new Tk window.
        # Detect "embedded in a Frame" — when the parent isn't a Tk/Toplevel
        # window, skip window-only calls (title/geometry/minsize) since
        # ttk.Frame doesn't support them.
        if parent is None:
            self.root = tk.Tk()
            self.is_standalone = True
            self.is_embedded = False
        else:
            self.root = parent
            self.is_standalone = False
            self.is_embedded = not isinstance(parent, (tk.Tk, tk.Toplevel))

        if not self.is_embedded:
            self.root.title(_t("bank_app.window.title"))
            if self.is_standalone:
                self.root.geometry("900x700")
                self.root.minsize(800, 600)

        # Configure style
        self.style = ttk.Style()
        try:
            self.style.theme_use('clam')
        except Exception:
            pass

        # Custom styles
        self.style.configure("Title.TLabel", font=("Helvetica", 24, "bold"))
        self.style.configure("Subtitle.TLabel", font=("Helvetica", 14))
        self.style.configure("Balance.TLabel", font=("Helvetica", 32, "bold"), foreground="#2E7D32")
        self.style.configure("Action.TButton", font=("Helvetica", 12), padding=10)
        self.style.configure("Header.TLabel", font=("Helvetica", 16, "bold"))
        self.style.configure("Money.TLabel", font=("Helvetica", 14), foreground="#1565C0")

        # Initialize bank for standalone mode
        self.bank = Bank()
        self.current_account: Optional[Account] = None

        # Create main container
        self.container = ttk.Frame(self.root)
        self.container.pack(fill="both", expand=True, padx=20, pady=20)

        # Check if we should use student finance mode
        if self._check_student_login():
            self.show_student_dashboard()
        else:
            self.show_login_screen()

    def _check_student_login(self) -> bool:
        """Check if user is logged in via university auth and has a student account."""
        if not self.auth or not FINANCE_INTEGRATION_AVAILABLE:
            return False

        try:
            current_user = self.auth.current_user if hasattr(self.auth, 'current_user') else None
            if not current_user:
                return False

            # Get student_id from user
            self.student_id = current_user.get('student_id') or current_user.get('username')
            if not self.student_id:
                return False

            # Ensure finance account exists
            ensure_student_finance_account_exists(self.student_id)

            # Get student info
            self.student_info = get_student_info(self.student_id)
            if not self.student_info:
                # Create basic info from current_user
                self.student_info = {
                    'student_id': self.student_id,
                    'first_name': current_user.get('first_name', 'Student'),
                    'last_name': current_user.get('last_name', ''),
                    'full_name': f"{current_user.get('first_name', 'Student')} {current_user.get('last_name', '')}".strip(),
                    'email': current_user.get('email')
                }

            self.is_student_mode = True
            return True

        except Exception as e:
            print(f"Error checking student login: {e}")
            return False

    def _get_student_balance(self) -> float:
        """Get the current student finance account balance."""
        if not self.student_id or not FINANCE_INTEGRATION_AVAILABLE:
            return 0.0
        try:
            balance = get_student_finance_account_balance(self.student_id)
            return balance if balance is not None else 0.0
        except Exception:
            return 0.0

    def _get_student_transactions(self) -> List[Dict]:
        """Get student finance transactions from the database."""
        if not self.student_id or not FINANCE_INTEGRATION_AVAILABLE:
            return []

        try:
            conn = sqlite3.connect(str(paths.DEFAULT_DB_PATH))
            cursor = conn.cursor()

            # Get transactions from transactions table
            cursor.execute('''
                SELECT created_at, transaction_type, amount, balance_after, description
                FROM transactions
                WHERE source_type = 'student_finance' AND student_id = ?
                ORDER BY created_at DESC
                LIMIT 50
            ''', (self.student_id,))

            transactions = []
            for row in cursor.fetchall():
                transactions.append({
                    'timestamp': row[0],
                    'type': row[1],
                    'amount': float(row[2]),
                    'balance_after': float(row[3]) if row[3] else 0.0,
                    'description': row[4] or ''
                })

            conn.close()
            return transactions

        except Exception as e:
            print(f"Error getting student transactions: {e}")
            return []

    def run(self):
        """Run the main loop (only for standalone mode)."""
        if self.is_standalone:
            self.root.mainloop()

    def clear_container(self):
        """Clear all widgets from container."""
        for widget in self.container.winfo_children():
            widget.destroy()

    # ==================== STUDENT FINANCE MODE ====================

    def show_student_dashboard(self):
        """Display the student finance account dashboard."""
        self.clear_container()

        # Header
        header_frame = ttk.Frame(self.container)
        header_frame.pack(fill="x", pady=10)

        student_name = self.student_info.get('full_name', _t("bank_app.student.default_name")) if self.student_info else _t("bank_app.student.default_name")
        ttk.Label(header_frame, text=_t("bank_app.dashboard.welcome", name=student_name),
                  style="Header.TLabel").pack(side="left")

        ttk.Button(header_frame, text=_t("bank_app.buttons.refresh"),
                   command=self.show_student_dashboard).pack(side="right", padx=5)

        ttk.Label(header_frame, text=_t("bank_app.dashboard.student_id", student_id=self.student_id),
                  font=("Helvetica", 10)).pack(side="right", padx=20)

        # Balance display
        balance = self._get_student_balance()

        balance_frame = ttk.LabelFrame(self.container, text=_t("bank_app.dashboard.balance_title"), padding=20)
        balance_frame.pack(fill="x", pady=20)

        balance_inner = ttk.Frame(balance_frame)
        balance_inner.pack()

        ttk.Label(balance_inner, text=f"£{balance:,.2f}",
                  style="Balance.TLabel").pack()

        if balance < 20:
            ttk.Label(balance_inner, text=_t("bank_app.dashboard.low_balance_warning"),
                      foreground="red", font=("Helvetica", 10, "italic")).pack(pady=5)

        # Action buttons
        actions_frame = ttk.Frame(self.container)
        actions_frame.pack(pady=20)

        ttk.Button(actions_frame, text=_t("bank_app.buttons.top_up"), style="Action.TButton",
                   command=self.show_topup_dialog, width=18).pack(side="left", padx=10)
        ttk.Button(actions_frame, text=_t("bank_app.buttons.transaction_history"), style="Action.TButton",
                   command=self.show_student_transaction_history, width=18).pack(side="left", padx=10)
        ttk.Button(actions_frame, text=_t("bank_app.buttons.financial_summary"), style="Action.TButton",
                   command=self.show_financial_summary, width=18).pack(side="left", padx=10)

        # Recent transactions
        self.show_student_recent_transactions()

        # Info section
        info_frame = ttk.LabelFrame(self.container, text=_t("bank_app.dashboard.account_info_title"), padding=10)
        info_frame.pack(fill="x", pady=10)

        ttk.Label(info_frame, text=_t("bank_app.dashboard.account_info_text"), justify="left").pack(anchor="w")

    def show_student_recent_transactions(self):
        """Show recent student finance transactions."""
        trans_frame = ttk.LabelFrame(self.container, text=_t("bank_app.transactions.recent_title"), padding=10)
        trans_frame.pack(fill="both", expand=True, pady=10)

        # Create treeview
        columns = ("Date", "Type", "Amount", "Balance", "Description")
        column_names = (
            _t("bank_app.transactions.columns.date"),
            _t("bank_app.transactions.columns.type"),
            _t("bank_app.transactions.columns.amount"),
            _t("bank_app.transactions.columns.balance"),
            _t("bank_app.transactions.columns.description")
        )
        tree = ttk.Treeview(trans_frame, columns=columns, show="headings", height=8)

        for col, name in zip(columns, column_names):
            tree.heading(col, text=name)
            tree.column(col, width=100 if col != "Description" else 250)

        # Add scrollbar
        scrollbar = ttk.Scrollbar(trans_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Populate with transactions
        transactions = self._get_student_transactions()

        for txn in transactions[:10]:
            try:
                # Parse timestamp
                timestamp = txn.get('timestamp', '')
                if 'T' in timestamp:
                    date = datetime.fromisoformat(timestamp.replace('Z', '')).strftime("%Y-%m-%d %H:%M")
                else:
                    date = timestamp[:16] if len(timestamp) >= 16 else timestamp

                txn_type = txn.get('type', 'unknown')
                amount = txn.get('amount', 0)
                balance = txn.get('balance_after', 0)
                desc = txn.get('description', '')

                # Format amount
                if txn_type in ['top_up', 'topup', 'deposit', 'credit', 'refund']:
                    amount_str = f"+£{amount:,.2f}"
                else:
                    amount_str = f"-£{amount:,.2f}"

                tree.insert("", "end", values=(
                    date,
                    txn_type.replace("_", " ").title(),
                    amount_str,
                    f"£{balance:,.2f}",
                    desc[:50] + "..." if len(desc) > 50 else desc
                ))
            except Exception as e:
                print(f"Error formatting transaction: {e}")
                continue

        if not transactions:
            tree.insert("", "end", values=("", _t("bank_app.transactions.no_transactions"), "", "", ""))

    def show_topup_dialog(self):
        """Show top-up dialog for student finance account."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("bank_app.topup.window_title"))
        dialog.geometry("450x350")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=_t("bank_app.topup.header"), style="Header.TLabel").pack(pady=20)

        current_balance = self._get_student_balance()
        ttk.Label(dialog, text=_t("bank_app.topup.current_balance", balance=f"{current_balance:,.2f}"),
                  style="Money.TLabel").pack()

        # Amount frame
        amount_frame = ttk.Frame(dialog)
        amount_frame.pack(pady=20)

        ttk.Label(amount_frame, text=_t("bank_app.topup.amount_label"), font=("Helvetica", 14)).pack(side="left")
        amount_entry = ttk.Entry(amount_frame, width=15, font=("Helvetica", 14))
        amount_entry.pack(side="left", padx=5)
        amount_entry.focus()

        # Quick amount buttons
        quick_frame = ttk.LabelFrame(dialog, text=_t("bank_app.topup.quick_topup"), padding=10)
        quick_frame.pack(pady=10)

        def set_amount(val):
            amount_entry.delete(0, tk.END)
            amount_entry.insert(0, str(val))

        for amount in [10, 20, 50, 100]:
            ttk.Button(quick_frame, text=f"£{amount}",
                       command=lambda a=amount: set_amount(a)).pack(side="left", padx=5)

        # Payment method
        method_frame = ttk.Frame(dialog)
        method_frame.pack(pady=10)

        ttk.Label(method_frame, text=_t("bank_app.topup.payment_method")).pack(side="left")
        method_var = tk.StringVar(value="card")
        ttk.Radiobutton(method_frame, text=_t("bank_app.topup.method_card"), variable=method_var, value="card").pack(side="left", padx=10)
        ttk.Radiobutton(method_frame, text=_t("bank_app.topup.method_bank_transfer"), variable=method_var, value="bank_transfer").pack(side="left", padx=10)
        ttk.Radiobutton(method_frame, text=_t("bank_app.topup.method_cash"), variable=method_var, value="cash").pack(side="left", padx=10)

        def process_topup():
            try:
                amount = float(amount_entry.get())
                if amount <= 0:
                    messagebox.showerror(_t("bank_app.error.title"), _t("bank_app.error.positive_amount"))
                    return
                if amount > 10000:
                    messagebox.showerror(_t("bank_app.error.title"), _t("bank_app.error.max_topup"))
                    return

                # Process top-up through finance integration
                result = top_up_student_finance_account(
                    student_id=self.student_id,
                    amount=amount,
                    payment_method=method_var.get(),
                    processed_by=self.student_id,
                    description=_t("bank_app.topup.description")
                )

                if result.get('success'):
                    new_balance = result.get('new_balance', current_balance + amount)
                    dialog.destroy()
                    messagebox.showinfo(_t("bank_app.success.title"),
                        _t("bank_app.topup.success_message", amount=f"{amount:,.2f}", balance=f"{new_balance:,.2f}"))
                    self.show_student_dashboard()
                else:
                    messagebox.showerror(_t("bank_app.error.title"), result.get('message', _t("bank_app.error.topup_failed")))

            except ValueError:
                messagebox.showerror(_t("bank_app.error.title"), _t("bank_app.error.valid_amount"))

        ttk.Button(dialog, text=_t("bank_app.buttons.complete_topup"), style="Action.TButton",
                   command=process_topup).pack(pady=20)

    def show_student_transaction_history(self):
        """Show full student transaction history."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("bank_app.history.window_title"))
        dialog.geometry("800x500")
        dialog.transient(self.root)

        ttk.Label(dialog, text=_t("bank_app.history.header"), style="Header.TLabel").pack(pady=10)
        ttk.Label(dialog, text=_t("bank_app.dashboard.student_id", student_id=self.student_id)).pack()

        # Create treeview
        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill="both", expand=True)

        columns = ("Date", "Type", "Amount", "Balance", "Description")
        column_names = (
            _t("bank_app.transactions.columns.date"),
            _t("bank_app.transactions.columns.type"),
            _t("bank_app.transactions.columns.amount"),
            _t("bank_app.transactions.columns.balance"),
            _t("bank_app.transactions.columns.description")
        )
        tree = ttk.Treeview(frame, columns=columns, show="headings")

        for col, name in zip(columns, column_names):
            tree.heading(col, text=name)
            tree.column(col, width=120 if col != "Description" else 250)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Populate all transactions
        transactions = self._get_student_transactions()

        for txn in transactions:
            try:
                timestamp = txn.get('timestamp', '')
                if 'T' in timestamp:
                    date = datetime.fromisoformat(timestamp.replace('Z', '')).strftime("%Y-%m-%d %H:%M")
                else:
                    date = timestamp[:16] if len(timestamp) >= 16 else timestamp

                txn_type = txn.get('type', 'unknown')
                amount = txn.get('amount', 0)
                balance = txn.get('balance_after', 0)
                desc = txn.get('description', '')

                if txn_type in ['top_up', 'topup', 'deposit', 'credit', 'refund']:
                    amount_str = f"+£{amount:,.2f}"
                else:
                    amount_str = f"-£{amount:,.2f}"

                tree.insert("", "end", values=(
                    date,
                    txn_type.replace("_", " ").title(),
                    amount_str,
                    f"£{balance:,.2f}",
                    desc
                ))
            except Exception:
                continue

        ttk.Button(dialog, text=_t("bank_app.buttons.close"), command=dialog.destroy).pack(pady=10)

    def show_financial_summary(self):
        """Show financial summary for student."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("bank_app.summary.window_title"))
        dialog.geometry("600x500")
        dialog.transient(self.root)

        ttk.Label(dialog, text=_t("bank_app.summary.header"), style="Header.TLabel").pack(pady=20)

        try:
            summary = get_student_financial_summary(self.student_id)
            balance = self._get_student_balance()

            # Summary frame
            summary_frame = ttk.LabelFrame(dialog, text=_t("bank_app.summary.overview_title"), padding=20)
            summary_frame.pack(fill="x", padx=20, pady=10)

            info = [
                (_t("bank_app.summary.current_balance"), f"£{balance:,.2f}"),
                (_t("bank_app.summary.total_payments"), str(summary.get('total_payments', 0))),
                (_t("bank_app.summary.total_paid"), f"£{summary.get('total_paid', 0):,.2f}"),
                (_t("bank_app.summary.total_refunds"), str(summary.get('total_refunds', 0))),
                (_t("bank_app.summary.total_refunded"), f"£{summary.get('total_refunded', 0):,.2f}"),
                (_t("bank_app.summary.net_spent"), f"£{summary.get('net_paid', 0):,.2f}"),
            ]

            for i, (label, value) in enumerate(info):
                ttk.Label(summary_frame, text=label, font=("Helvetica", 11)).grid(
                    row=i, column=0, sticky="w", pady=3)
                ttk.Label(summary_frame, text=value, font=("Helvetica", 11, "bold")).grid(
                    row=i, column=1, sticky="e", pady=3, padx=20)

            # Spending by category
            if summary.get('payments_by_source'):
                category_frame = ttk.LabelFrame(dialog, text=_t("bank_app.summary.spending_by_category"), padding=20)
                category_frame.pack(fill="both", expand=True, padx=20, pady=10)

                columns = ("Category", "Transactions", "Total Spent")
                column_names = (
                    _t("bank_app.summary.columns.category"),
                    _t("bank_app.summary.columns.transactions"),
                    _t("bank_app.summary.columns.total_spent")
                )
                tree = ttk.Treeview(category_frame, columns=columns, show="headings", height=8)

                for col, name in zip(columns, column_names):
                    tree.heading(col, text=name)
                    tree.column(col, width=150)

                tree.pack(fill="both", expand=True)

                for source, data in summary.get('payments_by_source', {}).items():
                    tree.insert("", "end", values=(
                        source,
                        data.get('count', 0),
                        f"£{data.get('amount', 0):,.2f}"
                    ))

        except Exception as e:
            ttk.Label(dialog, text=_t("bank_app.error.loading_summary", error=str(e))).pack(pady=20)

        ttk.Button(dialog, text=_t("bank_app.buttons.close"), command=dialog.destroy).pack(pady=10)

    # ==================== STANDALONE MODE ====================

    def show_login_screen(self):
        """Display the login/welcome screen."""
        self.clear_container()
        self.current_account = None

        # Title
        title_frame = ttk.Frame(self.container)
        title_frame.pack(pady=40)

        ttk.Label(title_frame, text=_t("bank_app.login.title"), style="Title.TLabel").pack()
        ttk.Label(title_frame, text=_t("bank_app.login.subtitle"), style="Subtitle.TLabel").pack(pady=5)

        # Info about student mode
        if FINANCE_INTEGRATION_AVAILABLE:
            info_frame = ttk.Frame(self.container)
            info_frame.pack(pady=10)
            ttk.Label(info_frame, text=_t("bank_app.login.student_tip"),
                      font=("Helvetica", 9, "italic"), foreground="gray").pack()

        # Login form
        login_frame = ttk.LabelFrame(self.container, text=_t("bank_app.login.form_title"), padding=20)
        login_frame.pack(pady=20, padx=50, fill="x")

        ttk.Label(login_frame, text=_t("bank_app.login.account_number")).grid(row=0, column=0, sticky="w", pady=5)
        self.login_account_entry = ttk.Entry(login_frame, width=30, font=("Helvetica", 12))
        self.login_account_entry.grid(row=0, column=1, pady=5, padx=10)

        ttk.Label(login_frame, text=_t("bank_app.login.pin")).grid(row=1, column=0, sticky="w", pady=5)
        self.login_pin_entry = ttk.Entry(login_frame, width=30, show="*", font=("Helvetica", 12))
        self.login_pin_entry.grid(row=1, column=1, pady=5, padx=10)

        ttk.Button(login_frame, text=_t("bank_app.buttons.login"), style="Action.TButton",
                   command=self.handle_login).grid(row=2, column=0, columnspan=2, pady=20)

        self.login_pin_entry.bind("<Return>", lambda e: self.handle_login())

        # Create account section
        ttk.Separator(self.container, orient="horizontal").pack(fill="x", pady=20)

        ttk.Label(self.container, text=_t("bank_app.login.new_user"), style="Subtitle.TLabel").pack()
        ttk.Button(self.container, text=_t("bank_app.buttons.create_account"), style="Action.TButton",
                   command=self.show_create_account_screen).pack(pady=10)

    def show_create_account_screen(self):
        """Display the account creation screen."""
        self.clear_container()

        ttk.Label(self.container, text=_t("bank_app.create_account.title"), style="Title.TLabel").pack(pady=20)

        form_frame = ttk.LabelFrame(self.container, text=_t("bank_app.create_account.form_title"), padding=20)
        form_frame.pack(pady=20, padx=50, fill="x")

        ttk.Label(form_frame, text=_t("bank_app.create_account.full_name")).grid(row=0, column=0, sticky="w", pady=8)
        self.name_entry = ttk.Entry(form_frame, width=35, font=("Helvetica", 12))
        self.name_entry.grid(row=0, column=1, pady=8, padx=10)

        ttk.Label(form_frame, text=_t("bank_app.create_account.pin_label")).grid(row=1, column=0, sticky="w", pady=8)
        self.new_pin_entry = ttk.Entry(form_frame, width=35, show="*", font=("Helvetica", 12))
        self.new_pin_entry.grid(row=1, column=1, pady=8, padx=10)

        ttk.Label(form_frame, text=_t("bank_app.create_account.confirm_pin")).grid(row=2, column=0, sticky="w", pady=8)
        self.confirm_pin_entry = ttk.Entry(form_frame, width=35, show="*", font=("Helvetica", 12))
        self.confirm_pin_entry.grid(row=2, column=1, pady=8, padx=10)

        ttk.Label(form_frame, text=_t("bank_app.create_account.initial_deposit")).grid(row=3, column=0, sticky="w", pady=8)
        self.initial_deposit_entry = ttk.Entry(form_frame, width=35, font=("Helvetica", 12))
        self.initial_deposit_entry.insert(0, "0.00")
        self.initial_deposit_entry.grid(row=3, column=1, pady=8, padx=10)

        btn_frame = ttk.Frame(self.container)
        btn_frame.pack(pady=20)

        ttk.Button(btn_frame, text=_t("bank_app.buttons.create_account"), style="Action.TButton",
                   command=self.handle_create_account).pack(side="left", padx=10)
        ttk.Button(btn_frame, text=_t("bank_app.buttons.back_to_login"), style="Action.TButton",
                   command=self.show_login_screen).pack(side="left", padx=10)

    def show_dashboard(self):
        """Display the main account dashboard."""
        self.clear_container()

        if not self.current_account:
            self.show_login_screen()
            return

        header_frame = ttk.Frame(self.container)
        header_frame.pack(fill="x", pady=10)

        ttk.Label(header_frame, text=_t("bank_app.dashboard.welcome", name=self.current_account.holder_name),
                  style="Header.TLabel").pack(side="left")
        ttk.Button(header_frame, text=_t("bank_app.buttons.logout"), command=self.show_login_screen).pack(side="right")

        ttk.Label(header_frame, text=_t("bank_app.standalone.account_label", account=self.current_account.account_number),
                  font=("Helvetica", 10)).pack(side="right", padx=20)

        balance_frame = ttk.LabelFrame(self.container, text=_t("bank_app.standalone.current_balance"), padding=20)
        balance_frame.pack(fill="x", pady=20)

        ttk.Label(balance_frame, text=f"£{self.current_account.balance:,.2f}",
                  style="Balance.TLabel").pack()

        actions_frame = ttk.Frame(self.container)
        actions_frame.pack(pady=20)

        actions = [
            (_t("bank_app.buttons.deposit"), self.show_deposit_dialog),
            (_t("bank_app.buttons.withdraw"), self.show_withdraw_dialog),
            (_t("bank_app.buttons.transfer"), self.show_transfer_dialog),
            (_t("bank_app.buttons.history"), self.show_transaction_history),
        ]

        for text, command in actions:
            btn = ttk.Button(actions_frame, text=text, style="Action.TButton",
                           command=command, width=15)
            btn.pack(side="left", padx=10)

        self.show_recent_transactions()

    def show_recent_transactions(self):
        """Show recent transactions on dashboard."""
        trans_frame = ttk.LabelFrame(self.container, text=_t("bank_app.transactions.recent_title"), padding=10)
        trans_frame.pack(fill="both", expand=True, pady=10)

        columns = ("Date", "Type", "Amount", "Balance", "Description")
        column_names = (
            _t("bank_app.transactions.columns.date"),
            _t("bank_app.transactions.columns.type"),
            _t("bank_app.transactions.columns.amount"),
            _t("bank_app.transactions.columns.balance"),
            _t("bank_app.transactions.columns.description")
        )
        tree = ttk.Treeview(trans_frame, columns=columns, show="headings", height=8)

        for col, name in zip(columns, column_names):
            tree.heading(col, text=name)
            tree.column(col, width=120 if col != "Description" else 200)

        scrollbar = ttk.Scrollbar(trans_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for txn in reversed(self.current_account.transactions[-10:]):
            date = datetime.fromisoformat(txn.timestamp).strftime("%Y-%m-%d %H:%M")
            amount_str = f"+£{txn.amount:,.2f}" if txn.type in ["deposit", "transfer_in"] else f"-£{txn.amount:,.2f}"
            tree.insert("", "end", values=(
                date,
                txn.type.replace("_", " ").title(),
                amount_str,
                f"£{txn.balance_after:,.2f}",
                txn.description
            ))

    def show_deposit_dialog(self):
        """Show deposit dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title(_t("bank_app.deposit.window_title"))
        dialog.geometry("400x200")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text=_t("bank_app.deposit.header"), style="Header.TLabel").pack(pady=20)

        frame = ttk.Frame(dialog)
        frame.pack(pady=10)

        ttk.Label(frame, text="£", font=("Helvetica", 16)).pack(side="left")
        amount_entry = ttk.Entry(frame, width=20, font=("Helvetica", 16))
        amount_entry.pack(side="left", padx=5)
        amount_entry.focus()

        def process_deposit():
            try:
                amount = float(amount_entry.get())
                if amount <= 0:
                    raise ValueError("Amount must be positive")
                self.current_account.deposit(amount)
                self.bank.save_data()
                dialog.destroy()
                messagebox.showinfo(_t("bank_app.success.title"), _t("bank_app.deposit.success", amount=f"{amount:,.2f}"))
                self.show_dashboard()
            except ValueError:
                messagebox.showerror(_t("bank_app.error.title"), _t("bank_app.error.valid_positive_amount"))

        ttk.Button(dialog, text=_t("bank_app.buttons.deposit"), style="Action.TButton",
                   command=process_deposit).pack(pady=20)

    def show_withdraw_dialog(self):
        """Show withdrawal dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Make a Withdrawal")
        dialog.geometry("400x250")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Withdraw Funds", style="Header.TLabel").pack(pady=20)
        ttk.Label(dialog, text=f"Available: £{self.current_account.balance:,.2f}").pack()

        frame = ttk.Frame(dialog)
        frame.pack(pady=10)

        ttk.Label(frame, text="£", font=("Helvetica", 16)).pack(side="left")
        amount_entry = ttk.Entry(frame, width=20, font=("Helvetica", 16))
        amount_entry.pack(side="left", padx=5)
        amount_entry.focus()

        def process_withdrawal():
            try:
                amount = float(amount_entry.get())
                if amount <= 0:
                    raise ValueError("Amount must be positive")
                if amount > self.current_account.balance:
                    messagebox.showerror("Error", "Insufficient funds")
                    return
                self.current_account.withdraw(amount)
                self.bank.save_data()
                dialog.destroy()
                messagebox.showinfo("Success", f"Successfully withdrew £{amount:,.2f}")
                self.show_dashboard()
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid positive amount")

        ttk.Button(dialog, text="Withdraw", style="Action.TButton",
                   command=process_withdrawal).pack(pady=20)

    def show_transfer_dialog(self):
        """Show transfer dialog."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Transfer Funds")
        dialog.geometry("450x300")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Transfer Funds", style="Header.TLabel").pack(pady=20)
        ttk.Label(dialog, text=f"Available: £{self.current_account.balance:,.2f}").pack()

        form = ttk.Frame(dialog, padding=20)
        form.pack()

        ttk.Label(form, text="Recipient Account:").grid(row=0, column=0, sticky="w", pady=5)
        recipient_entry = ttk.Entry(form, width=25, font=("Helvetica", 12))
        recipient_entry.grid(row=0, column=1, pady=5)

        ttk.Label(form, text="Amount: £").grid(row=1, column=0, sticky="w", pady=5)
        amount_entry = ttk.Entry(form, width=25, font=("Helvetica", 12))
        amount_entry.grid(row=1, column=1, pady=5)

        def process_transfer():
            try:
                recipient = recipient_entry.get().strip()
                amount = float(amount_entry.get())

                if amount <= 0:
                    raise ValueError("Amount must be positive")
                if amount > self.current_account.balance:
                    messagebox.showerror("Error", "Insufficient funds")
                    return
                if recipient == self.current_account.account_number:
                    messagebox.showerror("Error", "Cannot transfer to yourself")
                    return
                if recipient not in self.bank.accounts:
                    messagebox.showerror("Error", "Recipient account not found")
                    return

                success = self.bank.transfer(self.current_account, recipient, amount)
                if success:
                    dialog.destroy()
                    messagebox.showinfo("Success", f"Successfully transferred £{amount:,.2f} to account {recipient}")
                    self.show_dashboard()
                else:
                    messagebox.showerror("Error", "Transfer failed")
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid amount")

        ttk.Button(dialog, text="Transfer", style="Action.TButton",
                   command=process_transfer).pack(pady=20)

    def show_transaction_history(self):
        """Show full transaction history."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Transaction History")
        dialog.geometry("700x500")
        dialog.transient(self.root)

        ttk.Label(dialog, text="Transaction History", style="Header.TLabel").pack(pady=10)

        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill="both", expand=True)

        columns = ("Date", "Type", "Amount", "Balance", "Description")
        tree = ttk.Treeview(frame, columns=columns, show="headings")

        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=100 if col != "Description" else 180)

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)

        tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for txn in reversed(self.current_account.transactions):
            date = datetime.fromisoformat(txn.timestamp).strftime("%Y-%m-%d %H:%M")
            if txn.type in ["deposit", "transfer_in"]:
                amount_str = f"+£{txn.amount:,.2f}"
            else:
                amount_str = f"-£{txn.amount:,.2f}"
            tree.insert("", "end", values=(
                date,
                txn.type.replace("_", " ").title(),
                amount_str,
                f"£{txn.balance_after:,.2f}",
                txn.description
            ))

        ttk.Button(dialog, text="Close", command=dialog.destroy).pack(pady=10)

    def handle_login(self):
        """Handle login attempt."""
        account_num = self.login_account_entry.get().strip()
        pin = self.login_pin_entry.get()

        if not account_num or not pin:
            messagebox.showerror("Error", "Please enter account number and PIN")
            return

        account = self.bank.authenticate(account_num, pin)
        if account:
            self.current_account = account
            self.show_dashboard()
        else:
            messagebox.showerror("Login Failed", "Invalid account number or PIN")

    def handle_create_account(self):
        """Handle account creation."""
        name = self.name_entry.get().strip()
        pin = self.new_pin_entry.get()
        confirm_pin = self.confirm_pin_entry.get()

        try:
            initial_deposit = float(self.initial_deposit_entry.get())
        except ValueError:
            initial_deposit = 0.0

        if not name:
            messagebox.showerror("Error", "Please enter your full name")
            return
        if len(pin) < 4 or len(pin) > 6 or not pin.isdigit():
            messagebox.showerror("Error", "PIN must be 4-6 digits")
            return
        if pin != confirm_pin:
            messagebox.showerror("Error", "PINs do not match")
            return
        if initial_deposit < 0:
            messagebox.showerror("Error", "Initial deposit cannot be negative")
            return

        account = self.bank.create_account(name, pin, initial_deposit)
        messagebox.showinfo("Account Created",
            f"Your account has been created!\n\n"
            f"Account Number: {account.account_number}\n"
            f"Please remember your account number and PIN.")

        self.show_login_screen()

def main():
    """Run the banking application."""
    app = BankApp()
    app.run()

if __name__ == "__main__":
    main()
