"""Assets GUI for managing equipment and device loans."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.assets.services.assets_service import AssetsService


class AssetsFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = AssetsService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Asset Loans", font=("Helvetica", 14, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self)
        toolbar.pack(fill="x", padx=10, pady=5)
        tk.Label(toolbar, text="Status:").pack(side="left", padx=5)
        self._status_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._status_var,
                      values=["All", "on_loan", "returned", "overdue", "lost"],
                      state="readonly", width=12).pack(side="left", padx=5)
        ttk.Button(toolbar, text="Filter", command=self._load_loans).pack(side="left", padx=5)
        ttk.Button(toolbar, text="New Loan", command=self._new_loan).pack(side="right", padx=5)
        ttk.Button(toolbar, text="Return Asset", command=self._return_asset).pack(side="right", padx=5)

        cols = ("id", "asset", "tag", "type", "student", "condition", "loan_date", "status")
        self._tree = ttk.Treeview(self, columns=cols, show="headings", height=18)
        for c, w in zip(cols, (50, 150, 80, 80, 120, 80, 100, 80)):
            self._tree.heading(c, text=c.replace("_", " ").title())
            self._tree.column(c, width=w)
        self._tree.pack(fill="both", expand=True, padx=10, pady=5)

    def _load_loans(self):
        for item in self._tree.get_children():
            self._tree.delete(item)
        try:
            status = self._status_var.get()
            loans = self._svc.list_loans(status=None if status == "All" else status)
            for l in loans:
                name = f"{l.get('first_name', '')} {l.get('last_name', '')}".strip() or str(l.get("loaned_to", ""))
                self._tree.insert("", "end", iid=str(l["id"]), values=(
                    l["id"], l.get("asset_name", ""), l.get("asset_tag", ""),
                    l.get("asset_type", ""), name,
                    l.get("condition_out", ""), l.get("loan_date", ""),
                    l.get("status", "")))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _new_loan(self):
        win = tk.Toplevel(self)
        win.title("New Asset Loan")
        win.geometry("400x300")
        fields = {}
        row = 0
        for label, key in [("Asset Name*:", "asset_name"), ("Asset Tag*:", "asset_tag"),
                           ("Student ID*:", "loaned_to"), ("Condition:", "condition_out")]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=5, sticky="e")
            e = tk.Entry(win, width=25)
            e.grid(row=row, column=1, padx=10, pady=5)
            fields[key] = e
            row += 1
        fields["condition_out"].insert(0, "good")
        tk.Label(win, text="Type:").grid(row=row, column=0, padx=10, pady=5, sticky="e")
        type_var = tk.StringVar(value="laptop")
        ttk.Combobox(win, textvariable=type_var,
                      values=["laptop", "tablet", "camera", "calculator", "textbook", "other"],
                      state="readonly", width=22).grid(row=row, column=1, padx=10, pady=5)
        row += 1

        def save():
            try:
                user_id = self._auth.current_user["user_id"] if self._auth and self._auth.current_user else None
                self._svc.create_loan(
                    asset_name=fields["asset_name"].get().strip(),
                    asset_tag=fields["asset_tag"].get().strip(),
                    loaned_to=int(fields["loaned_to"].get().strip()),
                    asset_type=type_var.get(),
                    condition_out=fields["condition_out"].get().strip() or "good",
                    issued_by=user_id)
                messagebox.showinfo("Success", "Loan created")
                win.destroy()
                self._load_loans()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(win, text="Save", command=save).grid(row=row, column=0, columnspan=2, pady=15)

    def _return_asset(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a loan to return")
            return
        loan_id = int(sel[0])
        win = tk.Toplevel(self)
        win.title("Return Asset")
        win.geometry("300x150")
        tk.Label(win, text="Condition:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        cond_var = tk.StringVar(value="good")
        ttk.Combobox(win, textvariable=cond_var,
                      values=["good", "fair", "poor", "damaged"],
                      state="readonly", width=15).grid(row=0, column=1, padx=10, pady=10)
        tk.Label(win, text="Notes:").grid(row=1, column=0, padx=10, pady=5, sticky="e")
        notes = tk.Entry(win, width=25)
        notes.grid(row=1, column=1, padx=10, pady=5)

        def save():
            try:
                self._svc.return_asset(loan_id, condition_in=cond_var.get(),
                                        notes=notes.get().strip() or None)
                messagebox.showinfo("Success", "Asset returned")
                win.destroy()
                self._load_loans()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        ttk.Button(win, text="Return", command=save).grid(row=2, column=0, columnspan=2, pady=15)

    def refresh(self):
        self._load_loans()
