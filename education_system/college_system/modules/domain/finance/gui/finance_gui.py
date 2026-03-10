"""Finance GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.finance.services.finance_service import FinanceService


class FinanceFrame(tk.Frame):
    """Finance management frame with tabbed layout."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = FinanceService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Finance Management",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_fees_tab()
        self._build_invoices_tab()
        self._build_payments_tab()
        self._build_payroll_tab()

    def _build_fees_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Fee Items")

        form = tk.LabelFrame(tab, text="New Fee Item", bg="#ecf0f1", padx=10, pady=8)
        self._fee_form = form
        form.pack(fill="x", pady=(0, 8))
        row = tk.Frame(form, bg="#ecf0f1")
        row.pack(fill="x", pady=2)
        tk.Label(row, text="Title:", bg="#ecf0f1").pack(side="left")
        self._fee_title_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._fee_title_var, width=20).pack(side="left", padx=5)
        tk.Label(row, text="Amount:", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._fee_amount_var = tk.StringVar()
        ttk.Entry(row, textvariable=self._fee_amount_var, width=10).pack(side="left", padx=5)
        tk.Label(row, text="Type:", bg="#ecf0f1").pack(side="left", padx=(10, 0))
        self._fee_type_var = tk.StringVar(value="tuition")
        ttk.Combobox(row, textvariable=self._fee_type_var,
                     values=["tuition", "exam", "trip", "materials", "other"],
                     width=10, state="readonly").pack(side="left", padx=5)
        ttk.Button(row, text="Create", command=self._create_fee).pack(side="left", padx=10)

        cols = ("id", "title", "fee_type", "amount", "mandatory")
        self._fee_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("title", "Title", 180), ("fee_type", "Type", 80),
                         ("amount", "Amount", 80), ("mandatory", "Mandatory", 70)]:
            self._fee_tree.heading(c, text=h)
            self._fee_tree.column(c, width=w, anchor="center")
        self._fee_tree.pack(fill="both", expand=True)

    def _build_invoices_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Invoices")

        cols = ("id", "student_id", "amount", "paid_amount", "status", "due_date")
        self._inv_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("student_id", "Student", 60),
                         ("amount", "Amount", 80), ("paid_amount", "Paid", 80),
                         ("status", "Status", 70), ("due_date", "Due Date", 90)]:
            self._inv_tree.heading(c, text=h)
            self._inv_tree.column(c, width=w, anchor="center")
        self._inv_tree.pack(fill="both", expand=True)

    def _build_payments_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Payments")

        cols = ("id", "invoice_id", "amount", "payment_method", "reference", "created_at")
        self._pay_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("invoice_id", "Invoice", 60),
                         ("amount", "Amount", 80), ("payment_method", "Method", 100),
                         ("reference", "Reference", 100), ("created_at", "Date", 120)]:
            self._pay_tree.heading(c, text=h)
            self._pay_tree.column(c, width=w, anchor="center")
        self._pay_tree.pack(fill="both", expand=True)

    def _build_payroll_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(tab, text="Payroll")

        cols = ("id", "staff_id", "pay_period", "gross_pay", "deductions", "net_pay", "status")
        self._payroll_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        for c, h, w in [("id", "ID", 40), ("staff_id", "Staff", 50),
                         ("pay_period", "Period", 80), ("gross_pay", "Gross", 80),
                         ("deductions", "Deductions", 80), ("net_pay", "Net", 80),
                         ("status", "Status", 70)]:
            self._payroll_tree.heading(c, text=h)
            self._payroll_tree.column(c, width=w, anchor="center")
        self._payroll_tree.pack(fill="both", expand=True)

    def refresh(self):
        role = ""
        if self._auth and self._auth.current_user:
            role = self._auth.current_user.get("role", "student")
        if role not in ("admin", "staff"):
            self._fee_form.pack_forget()
        self._load_fees()
        self._load_invoices()
        self._load_payments()
        self._load_payroll()

    def _load_fees(self):
        self._fee_tree.delete(*self._fee_tree.get_children())
        try:
            for f in self._svc.list_fee_items():
                self._fee_tree.insert("", "end", values=(
                    f["id"], f["title"], f["fee_type"],
                    f"{f['amount']:.2f}", "Yes" if f["mandatory"] else "No"))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_invoices(self):
        self._inv_tree.delete(*self._inv_tree.get_children())
        try:
            for inv in self._svc.list_invoices():
                self._inv_tree.insert("", "end", values=(
                    inv["id"], inv["student_id"], f"{inv['amount']:.2f}",
                    f"{inv['paid_amount']:.2f}", inv["status"],
                    inv.get("due_date") or "-"))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_payments(self):
        self._pay_tree.delete(*self._pay_tree.get_children())
        try:
            for p in self._svc.list_payments():
                self._pay_tree.insert("", "end", values=(
                    p["id"], p["invoice_id"], f"{p['amount']:.2f}",
                    p["payment_method"], p.get("reference") or "-",
                    p.get("created_at") or "-"))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_payroll(self):
        self._payroll_tree.delete(*self._payroll_tree.get_children())
        try:
            for r in self._svc.list_payroll():
                self._payroll_tree.insert("", "end", values=(
                    r["id"], r["staff_id"], r["pay_period"],
                    f"{r['gross_pay']:.2f}", f"{r['deductions']:.2f}",
                    f"{r['net_pay']:.2f}", r["status"]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _create_fee(self):
        try:
            fee = self._svc.create_fee_item(
                self._fee_title_var.get().strip(),
                self._fee_type_var.get(),
                float(self._fee_amount_var.get().strip()),
            )
            messagebox.showinfo("Success", f"Fee item created (ID: {fee['id']}).")
            self._fee_title_var.set("")
            self._fee_amount_var.set("")
            self._load_fees()
        except Exception as e:
            messagebox.showerror("Error", str(e))
