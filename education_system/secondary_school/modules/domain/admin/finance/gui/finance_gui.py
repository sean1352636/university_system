"""Finance management GUI — admin only."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.secondary_school.modules.domain.admin.finance.services.finance_service import (
    FinanceService, TRANSACTION_TYPES, INCOME_CATEGORIES, EXPENSE_CATEGORIES,
)
from education_system.secondary_school.core.exceptions import FinanceError

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class FinanceFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = FinanceService(db_path)
        self._current_tab = "transactions"
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)

        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Finance Management", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        # Summary cards
        self._summary_frame = tk.Frame(self, bg=MAIN_BG, pady=8)
        self._summary_frame.pack(fill="x", padx=15)

        # Tab bar
        tab_bar = tk.Frame(self, bg=MAIN_BG, pady=4)
        tab_bar.pack(fill="x", padx=15)
        for label in ("Transactions", "Budgets"):
            ttk.Button(tab_bar, text=label,
                       command=lambda l=label: self._switch_tab(l)).pack(side="left", padx=4)

        # Transactions toolbar
        self._txn_toolbar = tk.Frame(self, bg=MAIN_BG, pady=4)
        ttk.Button(self._txn_toolbar, text="Add Income", command=self._on_add_income).pack(side="left", padx=4)
        ttk.Button(self._txn_toolbar, text="Add Expense", command=self._on_add_expense).pack(side="left", padx=4)
        ttk.Button(self._txn_toolbar, text="Delete", command=self._on_delete_txn).pack(side="left", padx=4)

        tk.Label(self._txn_toolbar, text="Filter:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._filter_var = tk.StringVar(value="All")
        ttk.Combobox(self._txn_toolbar, textvariable=self._filter_var,
                     values=["All", "income", "expense"],
                     state="readonly", width=10).pack(side="left", padx=4)
        self._filter_var.trace_add("write", lambda *_: self._load_transactions())

        # Budget toolbar
        self._budget_toolbar = tk.Frame(self, bg=MAIN_BG, pady=4)
        ttk.Button(self._budget_toolbar, text="Set Budget", command=self._on_set_budget).pack(side="left", padx=4)
        ttk.Button(self._budget_toolbar, text="Delete Budget", command=self._on_delete_budget).pack(side="left", padx=4)

        # Transaction tree
        self._txn_frame = tk.Frame(self)
        txn_cols = ("date", "type", "category", "description", "amount", "reference", "status")
        self._txn_tree = ttk.Treeview(self._txn_frame, columns=txn_cols,
                                      show="headings", selectmode="browse")
        for col, heading, w in [
            ("date", "Date", 85), ("type", "Type", 65),
            ("category", "Category", 120), ("description", "Description", 200),
            ("amount", "Amount", 90), ("reference", "Reference", 90),
            ("status", "Status", 70),
        ]:
            self._txn_tree.heading(col, text=heading)
            self._txn_tree.column(col, width=w, anchor="center")
        vsb1 = ttk.Scrollbar(self._txn_frame, orient="vertical", command=self._txn_tree.yview)
        self._txn_tree.configure(yscrollcommand=vsb1.set)
        self._txn_tree.pack(side="left", fill="both", expand=True)
        vsb1.pack(side="right", fill="y")

        # Budget tree
        self._budget_frame = tk.Frame(self)
        bud_cols = ("department", "year", "allocated", "spent", "remaining", "notes")
        self._budget_tree = ttk.Treeview(self._budget_frame, columns=bud_cols,
                                         show="headings", selectmode="browse")
        for col, heading, w in [
            ("department", "Department", 150), ("year", "Year", 80),
            ("allocated", "Allocated", 100), ("spent", "Spent", 100),
            ("remaining", "Remaining", 100), ("notes", "Notes", 180),
        ]:
            self._budget_tree.heading(col, text=heading)
            self._budget_tree.column(col, width=w, anchor="center")
        vsb2 = ttk.Scrollbar(self._budget_frame, orient="vertical", command=self._budget_tree.yview)
        self._budget_tree.configure(yscrollcommand=vsb2.set)
        self._budget_tree.pack(side="left", fill="both", expand=True)
        vsb2.pack(side="right", fill="y")

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15,
                                                           pady=(0, 8), side="bottom")

        self._switch_tab("Transactions")

    def _switch_tab(self, tab):
        self._txn_toolbar.pack_forget()
        self._budget_toolbar.pack_forget()
        self._txn_frame.pack_forget()
        self._budget_frame.pack_forget()

        if tab == "Transactions":
            self._current_tab = "transactions"
            self._txn_toolbar.pack(fill="x", padx=15)
            self._txn_frame.pack(fill="both", expand=True, padx=15, pady=(0, 5))
            self._load_transactions()
        else:
            self._current_tab = "budgets"
            self._budget_toolbar.pack(fill="x", padx=15)
            self._budget_frame.pack(fill="both", expand=True, padx=15, pady=(0, 5))
            self._load_budgets()

        self._update_summary()

    def refresh(self):
        self._update_summary()
        if self._current_tab == "transactions":
            self._load_transactions()
        else:
            self._load_budgets()

    def _update_summary(self):
        for w in self._summary_frame.winfo_children():
            w.destroy()
        try:
            s = self._svc.get_summary()
            cards = [
                ("Total Income", f"\u00a3{s['total_income']:,.2f}", "#27ae60"),
                ("Total Expenses", f"\u00a3{s['total_expense']:,.2f}", "#e74c3c"),
                ("Balance", f"\u00a3{s['balance']:,.2f}",
                 "#2ecc71" if s["balance"] >= 0 else "#c0392b"),
            ]
            for i, (label, value, color) in enumerate(cards):
                card = tk.Frame(self._summary_frame, bg=color, width=180, height=60)
                card.grid(row=0, column=i, padx=8, pady=4, sticky="nsew")
                card.grid_propagate(False)
                tk.Label(card, text=value, font=("Helvetica", 16, "bold"),
                         bg=color, fg="white").pack(expand=True)
                tk.Label(card, text=label, font=("Helvetica", 9),
                         bg=color, fg="white").pack(pady=(0, 6))
        except Exception:
            pass

    def _load_transactions(self):
        self._txn_tree.delete(*self._txn_tree.get_children())
        filt = self._filter_var.get()
        try:
            txns = self._svc.list_transactions(
                transaction_type=filt if filt != "All" else None,
            )
            for t in txns:
                self._txn_tree.insert("", "end", iid=t["id"], values=(
                    t["date"],
                    t["transaction_type"],
                    t["category"],
                    t.get("description", "") or "",
                    f"\u00a3{t['amount']:,.2f}",
                    t.get("reference", "") or "",
                    t["status"],
                ))
            self._status_var.set(f"{len(txns)} transaction(s)")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _load_budgets(self):
        self._budget_tree.delete(*self._budget_tree.get_children())
        try:
            budgets = self._svc.list_budgets()
            for b in budgets:
                remaining = b["allocated"] - b["spent"]
                self._budget_tree.insert("", "end", iid=b["id"], values=(
                    b["department"],
                    b["academic_year"],
                    f"\u00a3{b['allocated']:,.2f}",
                    f"\u00a3{b['spent']:,.2f}",
                    f"\u00a3{remaining:,.2f}",
                    b.get("notes", "") or "",
                ))
            self._status_var.set(f"{len(budgets)} budget(s)")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _add_transaction(self, txn_type: str):
        cats = list(INCOME_CATEGORIES) if txn_type == "income" else list(EXPENSE_CATEGORIES)

        dlg = tk.Toplevel(self)
        dlg.title(f"Add {txn_type.title()}")
        dlg.resizable(False, False)

        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()

        vars_ = {}
        fields = [
            ("Category", "category", cats[0], cats),
            ("Amount (\u00a3)", "amount", "", None),
            ("Description", "description", "", None),
            ("Reference", "reference", "", None),
            ("Date (YYYY-MM-DD)", "date", "", None),
        ]

        for row, (label, key, default, values) in enumerate(fields):
            tk.Label(c, text=label, font=("Helvetica", 9, "bold")).grid(
                row=row, column=0, sticky="w", **pad)
            vars_[key] = tk.StringVar(value=default)
            if values:
                ttk.Combobox(c, textvariable=vars_[key], values=values,
                             state="readonly", width=28).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[key], width=30).grid(row=row, column=1, **pad)

        result = [None]

        def save():
            amt = vars_["amount"].get().strip()
            if not amt:
                messagebox.showwarning("Validation", "Enter an amount.")
                return
            try:
                float(amt)
            except ValueError:
                messagebox.showwarning("Validation", "Amount must be a number.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()

        btn = tk.Frame(c)
        btn.grid(row=len(fields), column=0, columnspan=2, pady=(12, 0))
        ttk.Button(btn, text="Save", command=save).pack(side="left", padx=5)
        ttk.Button(btn, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)

        self.wait_window(dlg)
        if result[0] is None:
            return

        d = result[0]
        recorded_by = self._auth.get("username", "admin") if self._auth else "admin"
        try:
            self._svc.add_transaction(
                transaction_type=txn_type,
                category=d["category"],
                amount=float(d["amount"]),
                description=d["description"] or None,
                reference=d["reference"] or None,
                date=d["date"] or None,
                recorded_by=recorded_by,
            )
            messagebox.showinfo("Success", f"{txn_type.title()} recorded.")
            self._load_transactions()
            self._update_summary()
        except FinanceError as exc:
            messagebox.showerror("Error", str(exc))

    def _on_add_income(self):
        self._add_transaction("income")

    def _on_add_expense(self):
        self._add_transaction("expense")

    def _on_delete_txn(self):
        sel = self._txn_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a transaction first.")
            return
        if not messagebox.askyesno("Confirm", "Delete this transaction?"):
            return
        self._svc.delete_transaction(int(sel[0]))
        self._load_transactions()
        self._update_summary()

    def _on_set_budget(self):
        dlg = tk.Toplevel(self)
        dlg.title("Set Department Budget")
        dlg.resizable(False, False)

        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()

        vars_ = {}
        fields = [
            ("Department", "department", "", None),
            ("Academic Year", "academic_year", "2025/2026", None),
            ("Allocated (\u00a3)", "allocated", "", None),
            ("Notes", "notes", "", None),
        ]

        for row, (label, key, default, values) in enumerate(fields):
            tk.Label(c, text=label, font=("Helvetica", 9, "bold")).grid(
                row=row, column=0, sticky="w", **pad)
            vars_[key] = tk.StringVar(value=default)
            ttk.Entry(c, textvariable=vars_[key], width=30).grid(row=row, column=1, **pad)

        result = [None]

        def save():
            dept = vars_["department"].get().strip()
            amt = vars_["allocated"].get().strip()
            if not dept or not amt:
                messagebox.showwarning("Validation", "Department and amount are required.")
                return
            try:
                float(amt)
            except ValueError:
                messagebox.showwarning("Validation", "Amount must be a number.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()

        btn = tk.Frame(c)
        btn.grid(row=len(fields), column=0, columnspan=2, pady=(12, 0))
        ttk.Button(btn, text="Save", command=save).pack(side="left", padx=5)
        ttk.Button(btn, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)

        self.wait_window(dlg)
        if result[0] is None:
            return

        d = result[0]
        try:
            self._svc.set_budget(
                department=d["department"],
                allocated=float(d["allocated"]),
                academic_year=d["academic_year"] or "2025/2026",
                notes=d["notes"] or None,
            )
            messagebox.showinfo("Success", "Budget set.")
            self._load_budgets()
        except FinanceError as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete_budget(self):
        sel = self._budget_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a budget first.")
            return
        if not messagebox.askyesno("Confirm", "Delete this budget?"):
            return
        self._svc.delete_budget(int(sel[0]))
        self._load_budgets()
