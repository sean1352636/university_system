"""Finance management GUI for the Primary School Management System."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.primary_school.modules.domain.admin.finance.services.finance_service import FinanceService
import traceback


TRANSACTION_TYPES = ["Income", "Expense"]
PAYMENT_METHODS = ["Cash", "Card", "Bank Transfer", "Online"]
BUDGET_STATUSES = ["Active", "Closed"]


class _TransactionDialog(tk.Toplevel):
    """Add / Edit transaction dialog."""

    def __init__(self, parent, db_path, transaction=None):
        super().__init__(parent)
        self.result = None
        self._transaction = transaction
        self.title("Edit Transaction" if transaction else "Add Transaction")
        self.geometry("450x420")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        frm = tk.Frame(self, padx=15, pady=10)
        frm.pack(fill="both", expand=True)

        self._add_combo(frm, "transaction_type", "Type *", TRANSACTION_TYPES)
        self._add_field(frm, "category", "Category *")
        self._add_field(frm, "description", "Description *")
        self._add_field(frm, "amount", "Amount *")
        self._add_field(frm, "pupil_id", "Pupil ID (optional)")
        self._add_combo(frm, "payment_method", "Payment Method", PAYMENT_METHODS)
        self._add_field(frm, "reference", "Reference")

        if transaction:
            self._add_combo(frm, "status", "Status", ["Completed", "Pending", "Cancelled"])

        # Buttons
        btn_frame = tk.Frame(frm)
        btn_frame.pack(fill="x", pady=15)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        # Pre-fill for edit
        if transaction:
            for key, widget in self._entries.items():
                val = transaction.get(key)
                if val is None:
                    continue
                if isinstance(widget, ttk.Combobox):
                    widget.set(str(val))
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(val))

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _add_field(self, parent, key, label):
        frm = tk.Frame(parent)
        frm.pack(fill="x", pady=3)
        tk.Label(frm, text=label, width=20, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        self._entries[key] = entry

    def _add_combo(self, parent, key, label, values):
        frm = tk.Frame(parent)
        frm.pack(fill="x", pady=3)
        tk.Label(frm, text=label, width=20, anchor="w").pack(side="left")
        combo = ttk.Combobox(frm, values=values, state="readonly", width=27)
        combo.pack(side="left", fill="x", expand=True)
        if values:
            combo.set(values[0])
        self._entries[key] = combo

    def _save(self):
        data = {}
        for key, widget in self._entries.items():
            if isinstance(widget, ttk.Combobox):
                data[key] = widget.get()
            else:
                data[key] = widget.get().strip()
        if not data.get("transaction_type"):
            messagebox.showwarning("Validation", "Type is required.", parent=self)
            return
        if not data.get("category"):
            messagebox.showwarning("Validation", "Category is required.", parent=self)
            return
        if not data.get("description"):
            messagebox.showwarning("Validation", "Description is required.", parent=self)
            return
        if not data.get("amount"):
            messagebox.showwarning("Validation", "Amount is required.", parent=self)
            return
        try:
            data["amount"] = float(data["amount"])
        except ValueError:
            messagebox.showwarning("Validation", "Amount must be a number.", parent=self)
            return
        self.result = data
        self.destroy()


class _BudgetDialog(tk.Toplevel):
    """Add / Edit budget dialog."""

    def __init__(self, parent, db_path, budget=None):
        super().__init__(parent)
        self.result = None
        self._budget = budget
        self.title("Edit Budget" if budget else "Add Budget")
        self.geometry("450x320")
        self.resizable(False, False)
        self.grab_set()

        self._entries = {}

        frm = tk.Frame(self, padx=15, pady=10)
        frm.pack(fill="both", expand=True)

        self._add_field(frm, "budget_name", "Budget Name *")
        self._add_field(frm, "category", "Category *")
        self._add_field(frm, "allocated_amount", "Allocated Amount *")
        self._add_field(frm, "academic_year", "Academic Year *")

        if budget:
            self._add_combo(frm, "status", "Status", BUDGET_STATUSES)

        # Buttons
        btn_frame = tk.Frame(frm)
        btn_frame.pack(fill="x", pady=15)
        tk.Button(btn_frame, text="Save", command=self._save, width=12).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Cancel", command=self.destroy, width=12).pack(side="right", padx=5)

        # Pre-fill for edit
        if budget:
            for key, widget in self._entries.items():
                val = budget.get(key)
                if val is None:
                    continue
                if isinstance(widget, ttk.Combobox):
                    widget.set(str(val))
                else:
                    widget.delete(0, tk.END)
                    widget.insert(0, str(val))

        self.transient(parent)
        self.wait_visibility()
        self.grab_set()

    def _add_field(self, parent, key, label):
        frm = tk.Frame(parent)
        frm.pack(fill="x", pady=3)
        tk.Label(frm, text=label, width=20, anchor="w").pack(side="left")
        entry = tk.Entry(frm, width=30)
        entry.pack(side="left", fill="x", expand=True)
        self._entries[key] = entry

    def _add_combo(self, parent, key, label, values):
        frm = tk.Frame(parent)
        frm.pack(fill="x", pady=3)
        tk.Label(frm, text=label, width=20, anchor="w").pack(side="left")
        combo = ttk.Combobox(frm, values=values, state="readonly", width=27)
        combo.pack(side="left", fill="x", expand=True)
        if values:
            combo.set(values[0])
        self._entries[key] = combo

    def _save(self):
        data = {}
        for key, widget in self._entries.items():
            if isinstance(widget, ttk.Combobox):
                data[key] = widget.get()
            else:
                data[key] = widget.get().strip()
        if not data.get("budget_name"):
            messagebox.showwarning("Validation", "Budget name is required.", parent=self)
            return
        if not data.get("category"):
            messagebox.showwarning("Validation", "Category is required.", parent=self)
            return
        if not data.get("allocated_amount"):
            messagebox.showwarning("Validation", "Allocated amount is required.", parent=self)
            return
        try:
            data["allocated_amount"] = float(data["allocated_amount"])
        except ValueError:
            messagebox.showwarning("Validation", "Allocated amount must be a number.", parent=self)
            return
        if not data.get("academic_year"):
            messagebox.showwarning("Validation", "Academic year is required.", parent=self)
            return
        self.result = data
        self.destroy()


class FinanceFrame(tk.Frame):
    """Main finance management screen with Transactions and Budgets tabs."""

    HEADER_BG = "#1a5276"

    def __init__(self, parent, db_path, auth=None):
        super().__init__(parent)
        self._db_path = db_path
        self._auth = auth
        self._service = FinanceService(db_path)

        # Header
        header = tk.Frame(self, bg=self.HEADER_BG, height=40)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Finance Management", fg="white", bg=self.HEADER_BG,
                 font=("Helvetica", 14, "bold")).pack(side="left", padx=15)

        # Notebook with tabs
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, padx=5, pady=5)

        self._build_transactions_tab()
        self._build_budgets_tab()

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, anchor="w", bg="#ecf0f1",
                 padx=10).pack(fill="x", side="bottom")

        self._load_transactions()
        self._load_budgets()

    # ── Transactions Tab ─────────────────────────────────────────────────

    def _build_transactions_tab(self):
        tab = tk.Frame(self._notebook)
        self._notebook.add(tab, text="Transactions")

        toolbar = tk.Frame(tab, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Transaction", command=self._on_add_transaction).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit_transaction).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete_transaction).pack(side="left", padx=3)

        columns = ("transaction_type", "category", "description", "amount",
                    "payment_method", "date", "status")
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._txn_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._txn_tree.heading(col, text=col.replace("_", " ").title())
            self._txn_tree.column(col, width=110)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._txn_tree.yview)
        self._txn_tree.configure(yscrollcommand=vsb.set)
        self._txn_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _load_transactions(self):
        for item in self._txn_tree.get_children():
            self._txn_tree.delete(item)
        try:
            txns = self._service.get_transactions()
            for t in txns:
                self._txn_tree.insert("", tk.END, iid=t.get("id"), values=(
                    t.get("transaction_type", ""), t.get("category", ""),
                    t.get("description", ""), t.get("amount", ""),
                    t.get("payment_method", ""), t.get("date", ""),
                    t.get("status", ""),
                ))
            self._status_var.set(f"{len(txns)} transaction(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load transactions: {e}")

    def _selected_txn_id(self):
        sel = self._txn_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a transaction first.")
            return None
        return sel[0]

    def _on_add_transaction(self):
        dlg = _TransactionDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.record_transaction(**dlg.result)
                self._load_transactions()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit_transaction(self):
        tid = self._selected_txn_id()
        if not tid:
            return
        results = self._service.get_transactions()
        txn = next((t for t in results if str(t.get("id")) == str(tid)), None)
        if not txn:
            messagebox.showerror("Error", "Transaction not found.")
            return
        dlg = _TransactionDialog(self, self._db_path, transaction=txn)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_transaction(tid, **dlg.result)
                self._load_transactions()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete_transaction(self):
        tid = self._selected_txn_id()
        if not tid:
            return
        if not messagebox.askyesno("Confirm", f"Delete transaction {tid}?"):
            return
        try:
            # Note: finance service does not support delete_transaction
            messagebox.showwarning("Not Supported", "Deleting transactions is not supported.")
            return
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    # ── Budgets Tab ──────────────────────────────────────────────────────

    def _build_budgets_tab(self):
        tab = tk.Frame(self._notebook)
        self._notebook.add(tab, text="Budgets")

        toolbar = tk.Frame(tab, bg="#d5dbdb", padx=5, pady=5)
        toolbar.pack(fill="x")

        tk.Button(toolbar, text="Add Budget", command=self._on_add_budget).pack(side="left", padx=3)
        tk.Button(toolbar, text="Edit Selected", command=self._on_edit_budget).pack(side="left", padx=3)
        tk.Button(toolbar, text="Delete Selected", command=self._on_delete_budget).pack(side="left", padx=3)

        columns = ("budget_name", "category", "allocated", "spent",
                    "remaining", "academic_year", "status")
        tree_frame = tk.Frame(tab)
        tree_frame.pack(fill="both", expand=True, padx=5, pady=5)
        self._budget_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
        for col in columns:
            self._budget_tree.heading(col, text=col.replace("_", " ").title())
            self._budget_tree.column(col, width=110)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._budget_tree.yview)
        self._budget_tree.configure(yscrollcommand=vsb.set)
        self._budget_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

    def _load_budgets(self):
        for item in self._budget_tree.get_children():
            self._budget_tree.delete(item)
        try:
            budgets = self._service.get_budgets()
            for b in budgets:
                allocated = b.get("allocated_amount", b.get("allocated", 0))
                spent = b.get("spent", 0)
                remaining = allocated - spent if isinstance(allocated, (int, float)) and isinstance(spent, (int, float)) else ""
                self._budget_tree.insert("", tk.END, iid=b.get("id"), values=(
                    b.get("budget_name", ""), b.get("category", ""),
                    allocated, spent, remaining,
                    b.get("academic_year", ""), b.get("status", ""),
                ))
            self._status_var.set(f"{len(budgets)} budget(s) loaded")
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", f"Failed to load budgets: {e}")

    def _selected_budget_id(self):
        sel = self._budget_tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a budget first.")
            return None
        return sel[0]

    def _on_add_budget(self):
        dlg = _BudgetDialog(self, self._db_path)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.create_budget(**dlg.result)
                self._load_budgets()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_edit_budget(self):
        bid = self._selected_budget_id()
        if not bid:
            return
        results = self._service.get_budgets()
        budget = next((b for b in results if str(b.get("id")) == str(bid)), None)
        if not budget:
            messagebox.showerror("Error", "Budget not found.")
            return
        dlg = _BudgetDialog(self, self._db_path, budget=budget)
        self.wait_window(dlg)
        if dlg.result:
            try:
                self._service.update_budget(bid, **dlg.result)
                self._load_budgets()
            except Exception as e:
                traceback.print_exc()
                messagebox.showerror("Error", str(e))

    def _on_delete_budget(self):
        bid = self._selected_budget_id()
        if not bid:
            return
        if not messagebox.askyesno("Confirm", f"Delete budget {bid}?"):
            return
        try:
            # Note: finance service does not support delete_budget
            messagebox.showwarning("Not Supported", "Deleting budgets is not supported.")
            return
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror("Error", str(e))

    def refresh(self):
        self._load_transactions()
        self._load_budgets()
