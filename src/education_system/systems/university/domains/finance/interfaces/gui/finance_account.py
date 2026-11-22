"""My Finance Account — the one screen for a student's university finance
account: balance, top-ups, sending money to another student, transactions
(recent, filtered, full history, CSV export) and a spending summary.

The main window's "My Finance Account" button and the Finance window's tab
both build this screen (they used to be two screens, "My Finance Account"
and "Student Bank", over the same account).
"""
from __future__ import annotations

import logging
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

from education_system.systems.university.infrastructure.i18n import get_text as _t

logger = logging.getLogger(__name__)


def build_finance_account(host, auth):
    """Build the account screen inside ``host`` (a Toplevel or a Frame) for
    the signed-in user's own account. Returns the refresh function, or None
    if the screen could not be built (the error has been shown)."""
    if not auth or not getattr(auth, "current_user", None):
        messagebox.showerror(_t("common.error"), _t("finance_gui.errors.login_required"))
        return None

    try:
        from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
            ensure_student_finance_account_exists,
            top_up_student_finance_account
        )
        from education_system.systems.university.domains.finance.domain.student_account import (
            export_account_transactions_csv,
            get_account_overview,
            list_account_transactions,
            resolve_account_owner,
            signed_amount,
        )

        # Get current user's student ID
        current_user = auth.current_user
        student_id = resolve_account_owner(current_user)
        first_name = current_user.get('first_name', '')
        last_name = current_user.get('last_name', '')
        student_name = f"{first_name} {last_name}".strip() or student_id

        # Ensure account exists
        ensure_student_finance_account_exists(student_id)


        # Create main scrollable container
        main_canvas = tk.Canvas(host, bg='white', highlightthickness=0)
        scrollbar = ttk.Scrollbar(host, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )

        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)

        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Mouse wheel scrolling
        def on_mousewheel(event):
            main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        main_canvas.bind("<Enter>", lambda _e: main_canvas.bind_all("<MouseWheel>", on_mousewheel))
        main_canvas.bind("<Leave>", lambda _e: main_canvas.unbind_all("<MouseWheel>"))

        # Variables for dynamic updates
        balance_var = tk.StringVar(value=_t('gui.shell.main.features.finance.values.loading', default="Loading..."))
        total_deposited_var = tk.StringVar(value="£0.00")
        total_spent_var = tk.StringVar(value="£0.00")
        transaction_count_var = tk.StringVar(value="0")

        def refresh_all_data():
            """Refresh balance and statistics"""
            try:
                overview = get_account_overview(student_id)
                balance_var.set(f"£{overview['balance']:,.2f}")
                transaction_count_var.set(str(overview['transaction_count']))
                total_deposited_var.set(f"£{overview['total_deposited']:,.2f}")
                total_spent_var.set(f"£{overview['total_spent']:,.2f}")

                # Refresh transaction list
                load_transactions()
            except Exception as e:
                balance_var.set(f"Error: {e}")

        # ==== HEADER SECTION ====
        header_frame = tk.Frame(scrollable_frame, bg='#2c3e50')
        header_frame.pack(fill='x', pady=(0, 20))

        tk.Label(header_frame, text=_t("finance_gui.account.header", name=student_name),
                font=('Arial', 16, 'bold'), bg='#2c3e50', fg='white', pady=15).pack()

        # ==== BALANCE CARD ====
        balance_card = tk.Frame(scrollable_frame, bg='#27ae60', relief='raised', bd=2)
        balance_card.pack(fill='x', padx=20, pady=10)

        tk.Label(balance_card, text=_t("finance_gui.account.current_balance"),
                font=('Arial', 12, 'bold'), bg='#27ae60', fg='white').pack(pady=(15, 5))
        tk.Label(balance_card, textvariable=balance_var,
                font=('Arial', 32, 'bold'), bg='#27ae60', fg='white').pack(pady=5)

        refresh_btn = tk.Button(balance_card, text=_t('gui.shell.main.features.finance.buttons.refresh', default="🔄 Refresh"), command=refresh_all_data,
                               bg='#229954', fg='white', font=('Arial', 10, 'bold'),
                               relief='flat', padx=20, pady=5, cursor='hand2')
        refresh_btn.pack(pady=(5, 15))

        # ==== STATISTICS CARDS ====
        stats_container = tk.Frame(scrollable_frame, bg='white')
        stats_container.pack(fill='x', padx=20, pady=10)

        # Total Deposited Card
        deposit_card = tk.Frame(stats_container, bg='#3498db', relief='raised', bd=2)
        deposit_card.pack(side='left', expand=True, fill='both', padx=5)
        tk.Label(deposit_card, text=_t("finance_gui.account.total_deposited"), font=('Arial', 10, 'bold'),
                bg='#3498db', fg='white').pack(pady=(10, 5))
        tk.Label(deposit_card, textvariable=total_deposited_var, font=('Arial', 18, 'bold'),
                bg='#3498db', fg='white').pack(pady=(0, 10))

        # Total Spent Card
        spent_card = tk.Frame(stats_container, bg='#e74c3c', relief='raised', bd=2)
        spent_card.pack(side='left', expand=True, fill='both', padx=5)
        tk.Label(spent_card, text=_t("finance_gui.account.total_spent"), font=('Arial', 10, 'bold'),
                bg='#e74c3c', fg='white').pack(pady=(10, 5))
        tk.Label(spent_card, textvariable=total_spent_var, font=('Arial', 18, 'bold'),
                bg='#e74c3c', fg='white').pack(pady=(0, 10))

        # Transactions Count Card
        count_card = tk.Frame(stats_container, bg='#f39c12', relief='raised', bd=2)
        count_card.pack(side='left', expand=True, fill='both', padx=5)
        tk.Label(count_card, text=_t("finance_gui.account.transactions"), font=('Arial', 10, 'bold'),
                bg='#f39c12', fg='white').pack(pady=(10, 5))
        tk.Label(count_card, textvariable=transaction_count_var, font=('Arial', 18, 'bold'),
                bg='#f39c12', fg='white').pack(pady=(0, 10))

        # ==== QUICK ACTIONS ====
        actions_frame = ttk.LabelFrame(scrollable_frame, text=_t("finance_gui.account.quick_actions"), padding=15)
        actions_frame.pack(fill='x', padx=20, pady=15)

        # Quick amount buttons
        tk.Label(actions_frame, text=_t("finance_gui.account.quick_top_up_amounts"), font=('Arial', 9, 'bold')).pack(anchor='w', pady=(0, 5))
        quick_amounts = tk.Frame(actions_frame, bg='white')
        quick_amounts.pack(fill='x')

        def quick_top_up(amount):
            """Quick top-up with preset amount"""
            try:
                processed_by = auth.current_user.get('username', 'Unknown') if auth.current_user else 'Unknown'

                result = top_up_student_finance_account(
                    student_id=student_id,
                    amount=amount,
                    payment_method='quick_topup',
                    processed_by=processed_by
                )

                if result['success']:
                    messagebox.showinfo(_t("common.success"), _t("finance_gui.account.top_up_success", amount=amount, balance=result['new_balance']))
                    refresh_all_data()
                else:
                    messagebox.showerror(_t("common.error"), result['message'])
            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("finance_gui.account.top_up_failed", error=str(e)))

        for amount in [10, 20, 50, 100]:
            tk.Button(quick_amounts, text=f"£{amount}", command=lambda amt=amount: quick_top_up(amt),
                     bg='#ecf0f1', fg='#2c3e50', font=('Arial', 10, 'bold'),
                     relief='flat', padx=15, pady=5, cursor='hand2').pack(side='left', padx=3)

        # Send Money, Full History and Spending Summary (from the old Student
        # Bank window, merged here 2026-10-18 — one account screen).
        bank_tools = tk.Frame(actions_frame, bg='white')
        bank_tools.pack(fill='x', pady=(10, 0))
        for label, command in (
                (_t("bank_app.send_money.header", default="Send Money"),
                 lambda: _send_money_dialog(host, student_id, refresh_all_data)),
                (_t("bank_app.history.window_title", default="Full Transaction History"),
                 lambda: _history_dialog(host, student_id)),
                (_t("bank_app.summary.window_title", default="Spending Summary"),
                 lambda: _summary_dialog(host, student_id))):
            tk.Button(bank_tools, text=label, command=command,
                      bg='#2c3e50', fg='white', font=('Arial', 10, 'bold'),
                      relief='flat', padx=15, pady=5, cursor='hand2').pack(side='left', padx=3)

        # ==== RECENT TRANSACTIONS ====
        trans_frame = ttk.LabelFrame(scrollable_frame, text=_t('gui.shell.main.features.finance.labels.recent_transactions_last_20', default="📜 Recent Transactions (Last 20)"), padding=10)
        trans_frame.pack(fill='both', expand=True, padx=20, pady=15)

        # Filter buttons
        filter_frame = tk.Frame(trans_frame)
        filter_frame.pack(fill='x', pady=(0, 10))

        filter_var = tk.StringVar(value=_t('gui.shell.main.features.finance.values.all', default='all'))

        def apply_filter():
            load_transactions(filter_var.get())

        tk.Radiobutton(filter_frame, text=_t('gui.shell.main.features.finance.buttons.all', default="All"), variable=filter_var, value='all',
                      command=apply_filter).pack(side='left', padx=5)
        tk.Radiobutton(filter_frame, text=_t('gui.shell.main.features.finance.buttons.deposits', default="Deposits ⬆️"), variable=filter_var, value='deposit',
                      command=apply_filter).pack(side='left', padx=5)
        tk.Radiobutton(filter_frame, text=_t('gui.shell.main.features.finance.buttons.spending', default="Spending ⬇️"), variable=filter_var, value='spend',
                      command=apply_filter).pack(side='left', padx=5)

        # Export button
        def export_transactions():
            try:
                import csv
                from tkinter import filedialog

                filename = filedialog.asksaveasfilename(
                    defaultextension=".csv",
                    filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                    initialfile=f"finance_account_{student_id}.csv"
                )

                if not filename:
                    return

                export_account_transactions_csv(student_id, filename)
                messagebox.showinfo(_t("common.success"), _t("finance_gui.account.export_success", filename=filename))
            except Exception as e:
                messagebox.showerror(_t("common.error"), _t("finance_gui.account.export_failed", error=str(e)))

        tk.Button(filter_frame, text=_t('gui.shell.main.features.finance.buttons.export_csv', default="📥 Export CSV"), command=export_transactions,
                 bg='#34495e', fg='white', font=('Arial', 9, 'bold'),
                 relief='flat', padx=10, pady=3, cursor='hand2').pack(side='right', padx=5)

        # Transaction table
        trans_table_frame = tk.Frame(trans_frame)
        trans_table_frame.pack(fill='both', expand=True)

        columns = ('Date', 'Type', 'Amount', 'Balance', 'Description')
        trans_tree = ttk.Treeview(trans_table_frame, columns=columns, show='headings', height=10)

        trans_tree.heading('Date', text=_t('gui.shell.main.features.finance.headings.date_time', default='Date/Time'))
        trans_tree.heading('Type', text=_t('gui.shell.main.features.finance.headings.type', default='Type'))
        trans_tree.heading('Amount', text=_t('gui.shell.main.features.finance.headings.amount', default='Amount'))
        trans_tree.heading('Balance', text=_t('gui.shell.main.features.finance.headings.balance_after', default='Balance After'))
        trans_tree.heading('Description', text=_t('gui.shell.main.features.finance.headings.description', default='Description'))

        trans_tree.column('Date', width=150, anchor='center')
        trans_tree.column('Type', width=100, anchor='center')
        trans_tree.column('Amount', width=100, anchor='e')
        trans_tree.column('Balance', width=100, anchor='e')
        trans_tree.column('Description', width=250, anchor='w')

        trans_scrollbar = ttk.Scrollbar(trans_table_frame, orient='vertical', command=trans_tree.yview)
        trans_tree.configure(yscrollcommand=trans_scrollbar.set)

        trans_tree.pack(side='left', fill='both', expand=True)
        trans_scrollbar.pack(side='right', fill='y')

        def load_transactions(filter_type='all'):
            """Load and display transactions"""
            for item in trans_tree.get_children():
                trans_tree.delete(item)

            try:
                for txn in list_account_transactions(student_id, filter_type, limit=20):
                    trans_type = txn['type'].replace('_', ' ').title()
                    signed = signed_amount(txn['type'], txn['amount'])

                    # Format amount with +/- indicator
                    if signed < 0:
                        amount_str = f"-£{txn['amount']:.2f}"
                        tag = 'negative'
                    else:
                        amount_str = f"+£{txn['amount']:.2f}"
                        tag = 'positive'

                    trans_tree.insert('', 'end', values=(
                        txn['timestamp'], trans_type, amount_str, f"£{txn['balance_after']:.2f}", txn['description']
                    ), tags=(tag,))

                # Configure tag colors
                trans_tree.tag_configure('positive', foreground='#27ae60')
                trans_tree.tag_configure('negative', foreground='#e74c3c')
            except Exception as e:
                print(f"Error loading transactions: {e}")

        # Initial data load
        refresh_all_data()
        return refresh_all_data

        logger.info("Student finance account screen built for %s", student_id)

    except Exception as e:
        logger.exception("Student finance account screen failed")
        messagebox.showerror(_t("common.error"), _t("finance_gui.account.failed_to_open", error=str(e)))
        return None


def _txn_date(timestamp):
    timestamp = timestamp or ''
    if 'T' in timestamp:
        try:
            return datetime.fromisoformat(timestamp.replace('Z', '')).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            pass
    return timestamp[:16]


def _send_money_dialog(parent, student_id, on_sent):
    """Send money from this account to another student's finance account."""
    from education_system.systems.university.domains.finance.domain.student_account import (
        get_account_overview,
    )
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
        transfer_student_finance_funds,
    )
    dialog = tk.Toplevel(parent)
    dialog.title(_t("bank_app.send_money.window_title", default="Send Money"))
    dialog.geometry("480x380")
    dialog.transient(parent.winfo_toplevel())

    try:
        balance = get_account_overview(student_id)['balance']
    except Exception:
        logger.exception("send money: balance lookup failed")
        balance = 0.0
    ttk.Label(dialog, text=_t("bank_app.send_money.available",
                              default="Available: £{balance}").format(balance=f"{balance:,.2f}"),
              font=("Helvetica", 14)).pack(pady=(15, 5))

    form = ttk.Frame(dialog)
    form.pack(pady=10, padx=30, fill="x")
    form.columnconfigure(1, weight=1)
    entries = {}
    for row, (key, label) in enumerate((
            ("recipient", _t("bank_app.send_money.recipient_label",
                             default="Recipient (Student ID or username):")),
            ("amount", _t("bank_app.send_money.amount_label", default="Amount: £")),
            ("reference", _t("bank_app.send_money.reference_label", default="Reference:")))):
        ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=5)
        entries[key] = ttk.Entry(form, width=22)
        entries[key].grid(row=row, column=1, sticky="ew", padx=5, pady=5)
    ttk.Label(form, text=_t("bank_app.send_money.reference_hint", default="e.g. Meal out, money owed"),
              font=("Helvetica", 9, "italic"), foreground="gray").grid(row=3, column=1, sticky="w", padx=5)
    entries["recipient"].focus()

    def send():
        recipient = entries["recipient"].get().strip()
        reference = entries["reference"].get().strip()
        if not recipient:
            messagebox.showerror(_t("bank_app.error.title"), _t(
                "bank_app.send_money.missing_recipient", default="Please enter a recipient"), parent=dialog)
            return
        if not reference:
            messagebox.showerror(_t("bank_app.error.title"), _t(
                "bank_app.send_money.missing_reference",
                default="Please enter a reference (e.g. Meal out, money owed)"), parent=dialog)
            return
        try:
            amount = float(entries["amount"].get())
        except ValueError:
            messagebox.showerror(_t("bank_app.error.title"), _t("bank_app.error.valid_amount"), parent=dialog)
            return
        if amount <= 0:
            messagebox.showerror(_t("bank_app.error.title"), _t("bank_app.error.positive_amount"), parent=dialog)
            return
        if recipient == str(student_id):
            messagebox.showerror(_t("bank_app.error.title"), _t("bank_app.transfer.self_transfer_error"),
                                 parent=dialog)
            return
        if not messagebox.askyesno(
                _t("bank_app.send_money.confirm_title", default="Confirm Transfer"),
                _t("bank_app.send_money.confirm_message",
                   default="Send £{amount} to {recipient}?\nReference: {reference}").format(
                    amount=f"{amount:,.2f}", recipient=recipient, reference=reference), parent=dialog):
            return
        result = transfer_student_finance_funds(
            from_student_id=student_id, to_student_id=recipient, amount=amount,
            reference=reference, processed_by=student_id)
        if not result.get('success'):
            messagebox.showerror(_t("bank_app.error.title"),
                                 result.get('message') or _t("bank_app.transfer.failed"), parent=dialog)
            return
        dialog.destroy()
        messagebox.showinfo(
            _t("bank_app.success.title"),
            _t("bank_app.send_money.success_message",
               default="£{amount} sent to {recipient}.\n\nReference Number: {reference_number}\nNew balance: £{balance}").format(
                amount=f"{amount:,.2f}", recipient=result.get('recipient_name') or recipient,
                reference_number=result.get('reference_number') or '',
                balance=f"{result.get('new_balance') or 0:,.2f}"))
        on_sent()

    ttk.Button(dialog, text=_t("bank_app.send_money.send_button", default="Send Money"),
               command=send).pack(pady=15)


def _history_dialog(parent, student_id):
    """Every transaction on the account (the main screen shows the last 20)."""
    from education_system.systems.university.domains.finance.domain.student_account import (
        list_account_transactions, signed_amount,
    )
    dialog = tk.Toplevel(parent)
    dialog.title(_t("bank_app.history.window_title", default="Full Transaction History"))
    dialog.geometry("800x500")
    dialog.transient(parent.winfo_toplevel())

    frame = ttk.Frame(dialog, padding=10)
    frame.pack(fill="both", expand=True)
    columns = ("Date", "Type", "Amount", "Balance", "Description")
    tree = ttk.Treeview(frame, columns=columns, show="headings")
    for col, key in zip(columns, ("date", "type", "amount", "balance", "description")):
        tree.heading(col, text=_t(f"bank_app.transactions.columns.{key}", default=col))
        tree.column(col, width=120 if col != "Description" else 250)
    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    try:
        for txn in list_account_transactions(student_id, "all"):
            sign = "-" if signed_amount(txn['type'], txn['amount']) < 0 else "+"
            tree.insert("", "end", values=(
                _txn_date(txn.get('timestamp')), txn['type'].replace("_", " ").title(),
                f"{sign}£{txn['amount']:,.2f}", f"£{txn['balance_after'] or 0:,.2f}",
                txn.get('description') or ''))
    except Exception as e:
        logger.exception("full history failed")
        messagebox.showerror(_t("common.error"), str(e), parent=dialog)

    ttk.Button(dialog, text=_t("bank_app.buttons.close", default="Close"), command=dialog.destroy).pack(pady=10)


def _summary_dialog(parent, student_id):
    """Payments, refunds and spending by category."""
    from education_system.systems.university.domains.finance.domain.student_account import (
        get_account_overview,
    )
    from education_system.systems.university.domains.finance.infrastructure.finance_integration import (
        get_student_financial_summary,
    )
    dialog = tk.Toplevel(parent)
    dialog.title(_t("bank_app.summary.window_title", default="Spending Summary"))
    dialog.geometry("600x500")
    dialog.transient(parent.winfo_toplevel())
    try:
        summary = get_student_financial_summary(student_id)
        balance = get_account_overview(student_id)['balance']
        overview = ttk.LabelFrame(dialog, text=_t("bank_app.summary.overview_title"), padding=20)
        overview.pack(fill="x", padx=20, pady=10)
        for i, (label, value) in enumerate((
                (_t("bank_app.summary.current_balance"), f"£{balance:,.2f}"),
                (_t("bank_app.summary.total_payments"), str(summary.get('total_payments', 0))),
                (_t("bank_app.summary.total_paid"), f"£{summary.get('total_paid', 0):,.2f}"),
                (_t("bank_app.summary.total_refunds"), str(summary.get('total_refunds', 0))),
                (_t("bank_app.summary.total_refunded"), f"£{summary.get('total_refunded', 0):,.2f}"),
                (_t("bank_app.summary.net_spent"), f"£{summary.get('net_paid', 0):,.2f}"))):
            ttk.Label(overview, text=label, font=("Helvetica", 11)).grid(row=i, column=0, sticky="w", pady=3)
            ttk.Label(overview, text=value, font=("Helvetica", 11, "bold")).grid(
                row=i, column=1, sticky="e", pady=3, padx=20)
        if summary.get('payments_by_source'):
            cats = ttk.LabelFrame(dialog, text=_t("bank_app.summary.spending_by_category"), padding=20)
            cats.pack(fill="both", expand=True, padx=20, pady=10)
            columns = ("Category", "Transactions", "Total Spent")
            tree = ttk.Treeview(cats, columns=columns, show="headings", height=8)
            for col, key in zip(columns, ("category", "transactions", "total_spent")):
                tree.heading(col, text=_t(f"bank_app.summary.columns.{key}", default=col))
                tree.column(col, width=150)
            tree.pack(fill="both", expand=True)
            for source, data in summary['payments_by_source'].items():
                tree.insert("", "end", values=(source, data.get('count', 0), f"£{data.get('amount', 0):,.2f}"))
    except Exception as e:
        logger.exception("spending summary failed")
        ttk.Label(dialog, text=_t("bank_app.error.loading_summary", error=str(e))).pack(pady=20)
    ttk.Button(dialog, text=_t("bank_app.buttons.close", default="Close"), command=dialog.destroy).pack(pady=10)
