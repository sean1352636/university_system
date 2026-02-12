"""Unified Student Financial Dashboard (Feature 40).

Provides students with a single view of their financial standing,
transaction history, scholarships, and financial aid awards.
"""

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from university_system.infrastructure.database.db import get_connection, transaction
from university_system.modules.shared.utils.simple_activity_logger import log_activity
from university_system.modules.shared.services.dashboard.student_services import (
    StudentDashboardService,
)

logger = logging.getLogger(__name__)


class StudentFinanceGUI:
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
        logger.info("StudentFinanceGUI opened for student %s", self.student_id)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Create the main notebook with three tabs."""
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Tab 1 - Overview
        self.overview_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.overview_frame, text="Overview")
        self._build_overview_tab()

        # Tab 2 - Transactions
        self.transactions_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.transactions_frame, text="Transactions")
        self._build_transactions_tab()

        # Tab 3 - Scholarships & Aid
        self.aid_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.aid_frame, text="Scholarships & Aid")
        self._build_aid_tab()

    # ------------------------------------------------------------------
    # Tab 1 - Overview
    # ------------------------------------------------------------------

    def _build_overview_tab(self):
        """Build the financial overview tab."""
        summary = StudentDashboardService.get_financial_summary(self.student_id)

        # Balance card ---------------------------------------------------
        balance_card = ttk.LabelFrame(self.overview_frame, text="Current Balance")
        balance_card.pack(fill=tk.X, padx=20, pady=(20, 10))

        balance_value = summary.get("balance", 0.0)
        balance_color = "#c0392b" if balance_value > 0 else "#27ae60"
        balance_label = tk.Label(
            balance_card,
            text=f"${balance_value:,.2f}",
            font=("Helvetica", 32, "bold"),
            fg=balance_color,
        )
        balance_label.pack(pady=15)

        if balance_value > 0:
            note = tk.Label(
                balance_card,
                text="Amount owed",
                font=("Helvetica", 10),
                fg="#888888",
            )
        else:
            note = tk.Label(
                balance_card,
                text="No balance due" if balance_value == 0 else "Credit on account",
                font=("Helvetica", 10),
                fg="#888888",
            )
        note.pack(pady=(0, 10))

        # Summary row ----------------------------------------------------
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

            ttk.Label(
                col_frame,
                text=label_text,
                font=("Helvetica", 10),
            ).pack()

            color = "#c0392b" if label_text == "Net Balance" and value > 0 else "#2c3e50"
            if label_text in ("Total Aid", "Total Scholarships"):
                color = "#27ae60"

            tk.Label(
                col_frame,
                text=f"${value:,.2f}",
                font=("Helvetica", 16, "bold"),
                fg=color,
            ).pack(pady=(5, 0))

    # ------------------------------------------------------------------
    # Tab 2 - Transactions
    # ------------------------------------------------------------------

    def _build_transactions_tab(self):
        """Build the transaction history tab with filter."""
        # Filter bar
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
        self.txn_filter_combo.bind("<<ComboboxSelected>>", self._on_txn_filter_changed)

        # Treeview
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

        self.txn_tree.heading("date", text="Date")
        self.txn_tree.heading("type", text="Type")
        self.txn_tree.heading("description", text="Description")
        self.txn_tree.heading("amount", text="Amount")
        self.txn_tree.heading("balance_after", text="Balance After")

        self.txn_tree.column("date", width=130, anchor="center")
        self.txn_tree.column("type", width=120, anchor="center")
        self.txn_tree.column("description", width=300)
        self.txn_tree.column("amount", width=100, anchor="e")
        self.txn_tree.column("balance_after", width=110, anchor="e")

        self.txn_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_transactions()

    def _on_txn_filter_changed(self, _event=None):
        """Reload transactions when the filter combobox selection changes."""
        self._load_transactions()

    def _load_transactions(self):
        """Query transactions and populate the treeview."""
        for item in self.txn_tree.get_children():
            self.txn_tree.delete(item)

        txn_type = self.txn_filter_var.get()

        try:
            with get_connection() as conn:
                if txn_type == "All":
                    rows = conn.execute(
                        "SELECT created_at, transaction_type, description, "
                        "amount, balance_after "
                        "FROM student_finance_transactions "
                        "WHERE student_id = ? "
                        "ORDER BY created_at DESC",
                        (self.student_id,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT created_at, transaction_type, description, "
                        "amount, balance_after "
                        "FROM student_finance_transactions "
                        "WHERE student_id = ? AND transaction_type = ? "
                        "ORDER BY created_at DESC",
                        (self.student_id, txn_type),
                    ).fetchall()

            for row in rows:
                date_val = row[0] if row[0] else ""
                type_val = row[1] if row[1] else ""
                desc_val = row[2] if row[2] else ""
                amount_val = f"${row[3]:,.2f}" if row[3] is not None else "$0.00"
                balance_val = f"${row[4]:,.2f}" if row[4] is not None else ""
                self.txn_tree.insert(
                    "", tk.END, values=(date_val, type_val, desc_val, amount_val, balance_val)
                )

            if not rows:
                self.txn_tree.insert(
                    "", tk.END, values=("", "", "No transactions found.", "", "")
                )

        except Exception as exc:
            logger.warning("Could not load transactions: %s", exc)
            self.txn_tree.insert(
                "", tk.END, values=("", "", "No transaction history available.", "", "")
            )

    # ------------------------------------------------------------------
    # Tab 3 - Scholarships & Aid
    # ------------------------------------------------------------------

    def _build_aid_tab(self):
        """Build the scholarships and financial aid tab."""
        # Section 1: Scholarships ----------------------------------------
        scholarship_frame = ttk.LabelFrame(self.aid_frame, text="Scholarships")
        scholarship_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 5))

        s_columns = ("name", "amount", "status", "awarded_date")
        s_scroll = ttk.Scrollbar(scholarship_frame, orient=tk.VERTICAL)
        self.scholarship_tree = ttk.Treeview(
            scholarship_frame,
            columns=s_columns,
            show="headings",
            height=6,
            yscrollcommand=s_scroll.set,
        )
        s_scroll.config(command=self.scholarship_tree.yview)

        self.scholarship_tree.heading("name", text="Name")
        self.scholarship_tree.heading("amount", text="Amount")
        self.scholarship_tree.heading("status", text="Status")
        self.scholarship_tree.heading("awarded_date", text="Awarded Date")

        self.scholarship_tree.column("name", width=280)
        self.scholarship_tree.column("amount", width=120, anchor="e")
        self.scholarship_tree.column("status", width=120, anchor="center")
        self.scholarship_tree.column("awarded_date", width=130, anchor="center")

        self.scholarship_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        s_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_scholarships()

        # Section 2: Financial Aid ---------------------------------------
        aid_lf = ttk.LabelFrame(self.aid_frame, text="Financial Aid")
        aid_lf.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        a_columns = ("aid_type_id", "awarded_amount", "disbursed_amount", "status")
        a_scroll = ttk.Scrollbar(aid_lf, orient=tk.VERTICAL)
        self.aid_tree = ttk.Treeview(
            aid_lf,
            columns=a_columns,
            show="headings",
            height=6,
            yscrollcommand=a_scroll.set,
        )
        a_scroll.config(command=self.aid_tree.yview)

        self.aid_tree.heading("aid_type_id", text="Aid Type ID")
        self.aid_tree.heading("awarded_amount", text="Awarded Amount")
        self.aid_tree.heading("disbursed_amount", text="Disbursed Amount")
        self.aid_tree.heading("status", text="Status")

        self.aid_tree.column("aid_type_id", width=200)
        self.aid_tree.column("awarded_amount", width=150, anchor="e")
        self.aid_tree.column("disbursed_amount", width=150, anchor="e")
        self.aid_tree.column("status", width=120, anchor="center")

        self.aid_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        a_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._load_financial_aid()

    def _load_scholarships(self):
        """Load scholarship data for the current student."""
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
                name = row[1] if row[1] else f"Scholarship #{row[0]}"
                amount = f"${row[2]:,.2f}" if row[2] is not None else "$0.00"
                status = row[3] if row[3] else ""
                awarded_date = row[4] if row[4] else ""
                self.scholarship_tree.insert("", tk.END, values=(name, amount, status, awarded_date))

            if not rows:
                self.scholarship_tree.insert(
                    "", tk.END, values=("No scholarships found.", "", "", "")
                )

        except Exception as exc:
            logger.warning("Could not load scholarships: %s", exc)
            self.scholarship_tree.insert(
                "", tk.END, values=("No scholarship data available.", "", "", "")
            )

    def _load_financial_aid(self):
        """Load financial aid data for the current student."""
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
                aid_type = row[0] if row[0] else ""
                awarded = f"${row[1]:,.2f}" if row[1] is not None else "$0.00"
                disbursed = f"${row[2]:,.2f}" if row[2] is not None else "$0.00"
                status = row[3] if row[3] else ""
                self.aid_tree.insert("", tk.END, values=(aid_type, awarded, disbursed, status))

            if not rows:
                self.aid_tree.insert(
                    "", tk.END, values=("No financial aid records found.", "", "", "")
                )

        except Exception as exc:
            logger.warning("Could not load financial aid: %s", exc)
            self.aid_tree.insert(
                "", tk.END, values=("No financial aid data available.", "", "", "")
            )
