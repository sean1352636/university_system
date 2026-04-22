"""Student-facing finance view — merged into FinanceGUI.

Opens a Toplevel with Overview / Transactions / Scholarships & Aid tabs for
the currently logged-in student. FinanceGUI delegates here when the user's
role is 'student', so students and admins share one entry point.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.university_system.infrastructure.database.db import get_connection
from education_system.university_system.modules.shared.services.dashboard.student_services import (
    StudentDashboardService,
)

logger = logging.getLogger(__name__)


class StudentFinanceView:
    """Toplevel window showing a unified student financial dashboard."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.student_id = (
            auth.current_user.get("username", "") if auth and auth.current_user else ""
        )

        self.window = tk.Toplevel(parent)
        self.window.title("Student Financial Dashboard")
        self.window.geometry("1000x650")
        self.window.minsize(800, 500)

        if not self.student_id:
            messagebox.showerror(
                "Error",
                "You must be logged in to view your financial dashboard.",
                parent=self.window,
            )
            self.window.destroy()
            return

        self._build_ui()
        logger.info("StudentFinanceView opened for student %s", self.student_id)

    def _build_ui(self):
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.overview_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.overview_frame, text="Overview")
        self._build_overview_tab()

        self.transactions_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.transactions_frame, text="Transactions")
        self._build_transactions_tab()

        self.aid_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.aid_frame, text="Scholarships & Aid")
        self._build_aid_tab()

    def _build_overview_tab(self):
        summary = StudentDashboardService.get_financial_summary(self.student_id)

        balance_card = ttk.LabelFrame(self.overview_frame, text="Current Balance")
        balance_card.pack(fill=tk.X, padx=20, pady=(20, 10))

        balance_value = summary.get("balance", 0.0)
        balance_color = "#c0392b" if balance_value > 0 else "#27ae60"
        tk.Label(
            balance_card,
            text=f"${balance_value:,.2f}",
            font=("Helvetica", 32, "bold"),
            fg=balance_color,
        ).pack(pady=15)

        note_text = (
            "Amount owed" if balance_value > 0
            else ("No balance due" if balance_value == 0 else "Credit on account")
        )
        tk.Label(balance_card, text=note_text, font=("Helvetica", 10), fg="#888888").pack(pady=(0, 10))

        summary_frame = ttk.LabelFrame(self.overview_frame, text="Financial Summary")
        summary_frame.pack(fill=tk.X, padx=20, pady=10)

        items = [
            ("Total Charges", summary.get("total_charges", 0.0)),
            ("Total Aid", summary.get("total_aid", 0.0)),
            ("Total Scholarships", summary.get("total_scholarships", 0.0)),
            ("Net Balance", balance_value),
        ]

        for idx, (label_text, value) in enumerate(items):
            col_frame = ttk.Frame(summary_frame)
            col_frame.grid(row=0, column=idx, padx=20, pady=15, sticky="nsew")
            summary_frame.columnconfigure(idx, weight=1)

            ttk.Label(col_frame, text=label_text, font=("Helvetica", 10)).pack()

            color = "#c0392b" if label_text == "Net Balance" and value > 0 else "#2c3e50"
            if label_text in ("Total Aid", "Total Scholarships"):
                color = "#27ae60"

            tk.Label(
                col_frame,
                text=f"${value:,.2f}",
                font=("Helvetica", 16, "bold"),
                fg=color,
            ).pack(pady=(5, 0))

    def _build_transactions_tab(self):
        filter_frame = ttk.Frame(self.transactions_frame)
        filter_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(filter_frame, text="Filter by type:").pack(side=tk.LEFT, padx=(0, 5))

        self.txn_filter_var = tk.StringVar(value="All")
        self.txn_filter_combo = ttk.Combobox(
            filter_frame,
            textvariable=self.txn_filter_var,
            values=["All", "charge", "payment", "refund", "aid_disbursement"],
            state="readonly",
            width=20,
        )
        self.txn_filter_combo.pack(side=tk.LEFT)
        self.txn_filter_combo.bind("<<ComboboxSelected>>", lambda _e: self._load_transactions())

        columns = ("date", "type", "description", "amount", "balance_after")
        tree_frame = ttk.Frame(self.transactions_frame)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL)
        self.txn_tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            yscrollcommand=scrollbar.set,
        )
        scrollbar.config(command=self.txn_tree.yview)

        headings = [
            ("date", "Date", 130, "center"),
            ("type", "Type", 120, "center"),
            ("description", "Description", 300, "w"),
            ("amount", "Amount", 100, "e"),
            ("balance_after", "Balance After", 110, "e"),
        ]
        for key, heading, width, anchor in headings:
            self.txn_tree.heading(key, text=heading)
            self.txn_tree.column(key, width=width, anchor=anchor)

        self.txn_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_transactions()

    def _load_transactions(self):
        for item in self.txn_tree.get_children():
            self.txn_tree.delete(item)

        txn_type = self.txn_filter_var.get()

        try:
            with get_connection() as conn:
                if txn_type == "All":
                    rows = conn.execute(
                        "SELECT created_at, transaction_type, description, "
                        "amount, balance_after "
                        "FROM transactions "
                        "WHERE source_type = 'student_finance' AND student_id = ? "
                        "ORDER BY created_at DESC",
                        (self.student_id,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT created_at, transaction_type, description, "
                        "amount, balance_after "
                        "FROM transactions "
                        "WHERE source_type = 'student_finance' AND student_id = ? AND transaction_type = ? "
                        "ORDER BY created_at DESC",
                        (self.student_id, txn_type),
                    ).fetchall()

            for row in rows:
                date_val = row[0] or ""
                type_val = row[1] or ""
                desc_val = row[2] or ""
                amount_val = f"${row[3]:,.2f}" if row[3] is not None else "$0.00"
                balance_val = f"${row[4]:,.2f}" if row[4] is not None else ""
                self.txn_tree.insert(
                    "", tk.END, values=(date_val, type_val, desc_val, amount_val, balance_val)
                )

            if not rows:
                self.txn_tree.insert("", tk.END, values=("", "", "No transactions found.", "", ""))

        except Exception as exc:
            logger.warning("Could not load transactions: %s", exc)
            self.txn_tree.insert("", tk.END, values=("", "", "No transaction history available.", "", ""))

    def _build_aid_tab(self):
        scholarship_frame = ttk.LabelFrame(self.aid_frame, text="Scholarships")
        scholarship_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))

        s_cols = ("name", "amount", "status", "awarded_date")
        s_scroll = ttk.Scrollbar(scholarship_frame, orient=tk.VERTICAL)
        self.scholarship_tree = ttk.Treeview(
            scholarship_frame, columns=s_cols, show="headings", height=6, yscrollcommand=s_scroll.set,
        )
        s_scroll.config(command=self.scholarship_tree.yview)
        for key, heading, width, anchor in [
            ("name", "Name", 280, "w"),
            ("amount", "Amount", 120, "e"),
            ("status", "Status", 120, "center"),
            ("awarded_date", "Awarded Date", 130, "center"),
        ]:
            self.scholarship_tree.heading(key, text=heading)
            self.scholarship_tree.column(key, width=width, anchor=anchor)
        self.scholarship_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        s_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_scholarships()

        aid_lf = ttk.LabelFrame(self.aid_frame, text="Financial Aid")
        aid_lf.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        a_cols = ("aid_type_id", "awarded_amount", "disbursed_amount", "status")
        a_scroll = ttk.Scrollbar(aid_lf, orient=tk.VERTICAL)
        self.aid_tree = ttk.Treeview(
            aid_lf, columns=a_cols, show="headings", height=6, yscrollcommand=a_scroll.set,
        )
        a_scroll.config(command=self.aid_tree.yview)
        for key, heading, width, anchor in [
            ("aid_type_id", "Aid Type ID", 200, "w"),
            ("awarded_amount", "Awarded Amount", 150, "e"),
            ("disbursed_amount", "Disbursed Amount", 150, "e"),
            ("status", "Status", 120, "center"),
        ]:
            self.aid_tree.heading(key, text=heading)
            self.aid_tree.column(key, width=width, anchor=anchor)
        self.aid_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        a_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_financial_aid()

    def _load_scholarships(self):
        for item in self.scholarship_tree.get_children():
            self.scholarship_tree.delete(item)

        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT ss.scholarship_id, sp.scholarship_name, ss.amount, "
                    "ss.status, ss.awarded_date "
                    "FROM student_scholarships ss "
                    "LEFT JOIN scholarships sp ON ss.scholarship_id = sp.scholarship_id "
                    "WHERE ss.student_id = ?",
                    (self.student_id,),
                ).fetchall()

            for row in rows:
                name = row[1] or f"Scholarship #{row[0]}"
                amount = f"${row[2]:,.2f}" if row[2] is not None else "$0.00"
                status = row[3] or ""
                awarded_date = row[4] or ""
                self.scholarship_tree.insert("", tk.END, values=(name, amount, status, awarded_date))

            if not rows:
                self.scholarship_tree.insert("", tk.END, values=("No scholarships found.", "", "", ""))

        except Exception as exc:
            logger.warning("Could not load scholarships: %s", exc)
            self.scholarship_tree.insert("", tk.END, values=("No scholarship data available.", "", "", ""))

    def _load_financial_aid(self):
        for item in self.aid_tree.get_children():
            self.aid_tree.delete(item)

        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT aid_type_id, awarded_amount, disbursed_amount, status "
                    "FROM student_financial_aid "
                    "WHERE student_id = ?",
                    (self.student_id,),
                ).fetchall()

            for row in rows:
                aid_type = row[0] or ""
                awarded = f"${row[1]:,.2f}" if row[1] is not None else "$0.00"
                disbursed = f"${row[2]:,.2f}" if row[2] is not None else "$0.00"
                status = row[3] or ""
                self.aid_tree.insert("", tk.END, values=(aid_type, awarded, disbursed, status))

            if not rows:
                self.aid_tree.insert("", tk.END, values=("No financial aid records found.", "", "", ""))

        except Exception as exc:
            logger.warning("Could not load financial aid: %s", exc)
            self.aid_tree.insert("", tk.END, values=("No financial aid data available.", "", "", ""))
