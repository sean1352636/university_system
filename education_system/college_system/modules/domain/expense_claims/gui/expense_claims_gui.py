"""Expense Claims GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.expense_claims.services.expense_claims_service import ExpenseClaimService


class ExpenseClaimFrame(tk.Frame):
    """Expense Claims management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = ExpenseClaimService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Expense Claims",
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_claims_tab()
        self._build_pending_tab()
        self._build_stats_tab()

    # ------------------------------------------------------------------ #
    #  Tab 1: Claims                                                      #
    # ------------------------------------------------------------------ #

    def _build_claims_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text="Claims")

        # Toolbar
        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)

        ttk.Button(toolbar, text="New", command=self._new_claim).pack(side="left", padx=2)
        ttk.Button(toolbar, text="View", command=self._view_claim).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Edit", command=self._edit_claim).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Approve", command=self._approve_claim).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Reject", command=self._reject_claim).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Mark Paid", command=self._mark_paid).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Delete", command=self._delete_claim).pack(side="left", padx=2)

        # Filters
        filter_frame = tk.Frame(tab, bg="#ecf0f1")
        filter_frame.pack(fill="x", padx=5, pady=2)

        tk.Label(filter_frame, text="Category:", bg="#ecf0f1").pack(side="left", padx=2)
        self._cat_var = tk.StringVar(value="All")
        ttk.Combobox(filter_frame, textvariable=self._cat_var,
                     values=["All", "travel", "subsistence", "equipment",
                             "stationery", "training", "other"],
                     state="readonly", width=14).pack(side="left", padx=2)

        tk.Label(filter_frame, text="Status:", bg="#ecf0f1").pack(side="left", padx=2)
        self._status_var = tk.StringVar(value="All")
        ttk.Combobox(filter_frame, textvariable=self._status_var,
                     values=["All", "submitted", "approved", "rejected", "paid"],
                     state="readonly", width=10).pack(side="left", padx=2)

        tk.Label(filter_frame, text="Search:", bg="#ecf0f1").pack(side="left", padx=2)
        self._search_var = tk.StringVar()
        tk.Entry(filter_frame, textvariable=self._search_var, width=18).pack(side="left", padx=2)

        ttk.Button(filter_frame, text="Filter", command=self._load_claims).pack(side="left", padx=5)

        # Treeview
        cols = ("id", "claimant", "date", "description", "category", "amount", "status")
        self._claims_tree = ttk.Treeview(tab, columns=cols, show="headings", height=16)
        for c, heading, w in zip(
            cols,
            ("ID", "Claimant", "Date", "Description", "Category", "Amount", "Status"),
            (50, 150, 90, 200, 90, 80, 80),
        ):
            self._claims_tree.heading(c, text=heading)
            self._claims_tree.column(c, width=w, minwidth=40)
        self._claims_tree.pack(fill="both", expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=self._claims_tree.yview)
        self._claims_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

    def _load_claims(self):
        for item in self._claims_tree.get_children():
            self._claims_tree.delete(item)
        try:
            cat = self._cat_var.get()
            status = self._status_var.get()
            search = self._search_var.get().strip()
            rows = self._svc.list_claims(
                category=None if cat == "All" else cat,
                status=None if status == "All" else status,
                search=search or None,
            )
            for r in rows:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
                self._claims_tree.insert("", "end", iid=str(r["id"]), values=(
                    r["id"],
                    name or f"Staff #{r.get('claimant_id', '')}",
                    r.get("claim_date", ""),
                    r.get("description", ""),
                    r.get("category", ""),
                    f"{r.get('amount', 0):.2f}",
                    r.get("status", ""),
                ))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _new_claim(self):
        win = tk.Toplevel(self)
        win.title("New Expense Claim")
        win.geometry("450x480")
        win.resizable(False, False)

        entries = {}
        row = 0
        for label, key in [
            ("Claimant ID*:", "claimant_id"),
            ("Claim Date (YYYY-MM-DD):", "claim_date"),
            ("Description*:", "description"),
            ("Amount*:", "amount"),
            ("Mileage:", "mileage"),
            ("Mileage Rate [0.45]:", "mileage_rate"),
            ("Receipt Path:", "receipt_path"),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=4, sticky="e")
            e = tk.Entry(win, width=28)
            e.grid(row=row, column=1, padx=10, pady=4)
            entries[key] = e
            row += 1

        tk.Label(win, text="Category:").grid(row=row, column=0, padx=10, pady=4, sticky="e")
        cat_var = tk.StringVar(value="travel")
        ttk.Combobox(win, textvariable=cat_var,
                     values=["travel", "subsistence", "equipment",
                             "stationery", "training", "other"],
                     state="readonly", width=25).grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Notes:").grid(row=row, column=0, padx=10, pady=4, sticky="ne")
        notes_text = tk.Text(win, width=25, height=3)
        notes_text.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            try:
                claimant_id = int(entries["claimant_id"].get().strip())
                description = entries["description"].get().strip()
                if not description:
                    messagebox.showwarning("Warning", "Description is required.")
                    return
                amount_str = entries["amount"].get().strip()
                if not amount_str:
                    messagebox.showwarning("Warning", "Amount is required.")
                    return
                amount = float(amount_str)

                kwargs = {"category": cat_var.get()}
                claim_date = entries["claim_date"].get().strip()
                if claim_date:
                    kwargs["claim_date"] = claim_date
                mileage = entries["mileage"].get().strip()
                if mileage:
                    kwargs["mileage"] = float(mileage)
                rate = entries["mileage_rate"].get().strip()
                if rate:
                    kwargs["mileage_rate"] = float(rate)
                receipt = entries["receipt_path"].get().strip()
                if receipt:
                    kwargs["receipt_path"] = receipt
                notes = notes_text.get("1.0", "end").strip()
                if notes:
                    kwargs["notes"] = notes

                self._svc.create_claim(claimant_id, description, amount, **kwargs)
                messagebox.showinfo("Success", "Expense claim created.")
                win.destroy()
                self._load_claims()
            except ValueError:
                messagebox.showerror("Error", "Claimant ID must be an integer; Amount and Mileage must be numbers.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=15
        )

    def _view_claim(self):
        sel = self._claims_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a claim to view.")
            return
        claim = self._svc.get_claim(int(sel[0]))
        if not claim:
            messagebox.showerror("Error", "Claim not found.")
            return

        win = tk.Toplevel(self)
        win.title(f"Expense Claim #{claim['id']}")
        win.geometry("460x520")
        win.resizable(False, False)

        claimant = f"{claim.get('first_name', '')} {claim.get('last_name', '')}".strip()
        details = [
            ("ID", claim["id"]),
            ("Claimant", claimant or f"#{claim.get('claimant_id', '')}"),
            ("Claim Date", claim.get("claim_date", "")),
            ("Description", claim.get("description", "")),
            ("Category", claim.get("category", "")),
            ("Amount", f"{claim.get('amount', 0):.2f}"),
            ("Mileage", claim.get("mileage", "") or ""),
            ("Mileage Rate", claim.get("mileage_rate", "") or ""),
            ("Receipt", claim.get("receipt_path", "") or ""),
            ("Status", claim.get("status", "")),
            ("Approved By", claim.get("approved_by", "") or ""),
            ("Approved Date", claim.get("approved_date", "") or ""),
            ("Paid", "Yes" if claim.get("paid") else "No"),
            ("Paid Date", claim.get("paid_date", "") or ""),
            ("Notes", claim.get("notes", "") or ""),
            ("Created", claim.get("created_at", "")),
            ("Updated", claim.get("updated_at", "")),
        ]
        for i, (lbl, val) in enumerate(details):
            tk.Label(win, text=f"{lbl}:", font=("Helvetica", 10, "bold"),
                     anchor="e").grid(row=i, column=0, padx=10, pady=2, sticky="ne")
            tk.Label(win, text=str(val), wraplength=280,
                     anchor="w").grid(row=i, column=1, padx=10, pady=2, sticky="w")

        ttk.Button(win, text="Close", command=win.destroy).grid(
            row=len(details), column=0, columnspan=2, pady=10
        )

    def _edit_claim(self):
        sel = self._claims_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a claim to edit.")
            return
        claim_id = int(sel[0])
        claim = self._svc.get_claim(claim_id)
        if not claim:
            messagebox.showerror("Error", "Claim not found.")
            return

        win = tk.Toplevel(self)
        win.title(f"Edit Expense Claim #{claim_id}")
        win.geometry("450x480")
        win.resizable(False, False)

        entries = {}
        row = 0
        for label, key, default in [
            ("Claim Date:", "claim_date", claim.get("claim_date", "")),
            ("Description:", "description", claim.get("description", "")),
            ("Amount:", "amount", str(claim.get("amount", 0))),
            ("Mileage:", "mileage", str(claim.get("mileage", "") or "")),
            ("Mileage Rate:", "mileage_rate", str(claim.get("mileage_rate", "") or "")),
            ("Receipt Path:", "receipt_path", claim.get("receipt_path", "") or ""),
        ]:
            tk.Label(win, text=label).grid(row=row, column=0, padx=10, pady=4, sticky="e")
            e = tk.Entry(win, width=28)
            e.insert(0, default)
            e.grid(row=row, column=1, padx=10, pady=4)
            entries[key] = e
            row += 1

        tk.Label(win, text="Category:").grid(row=row, column=0, padx=10, pady=4, sticky="e")
        cat_var = tk.StringVar(value=claim.get("category", "travel"))
        ttk.Combobox(win, textvariable=cat_var,
                     values=["travel", "subsistence", "equipment",
                             "stationery", "training", "other"],
                     state="readonly", width=25).grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Status:").grid(row=row, column=0, padx=10, pady=4, sticky="e")
        status_var = tk.StringVar(value=claim.get("status", "submitted"))
        ttk.Combobox(win, textvariable=status_var,
                     values=["submitted", "approved", "rejected", "paid"],
                     state="readonly", width=25).grid(row=row, column=1, padx=10, pady=4)
        row += 1

        tk.Label(win, text="Notes:").grid(row=row, column=0, padx=10, pady=4, sticky="ne")
        notes_text = tk.Text(win, width=25, height=3)
        notes_text.insert("1.0", claim.get("notes", "") or "")
        notes_text.grid(row=row, column=1, padx=10, pady=4)
        row += 1

        def save():
            try:
                kwargs = {
                    "category": cat_var.get(),
                    "status": status_var.get(),
                }
                for key in ("claim_date", "description", "receipt_path"):
                    val = entries[key].get().strip()
                    kwargs[key] = val if val else None
                amt = entries["amount"].get().strip()
                kwargs["amount"] = float(amt) if amt else 0
                mileage = entries["mileage"].get().strip()
                kwargs["mileage"] = float(mileage) if mileage else None
                rate = entries["mileage_rate"].get().strip()
                kwargs["mileage_rate"] = float(rate) if rate else None
                notes = notes_text.get("1.0", "end").strip()
                kwargs["notes"] = notes if notes else None

                self._svc.update_claim(claim_id, **kwargs)
                messagebox.showinfo("Success", "Claim updated.")
                win.destroy()
                self._load_claims()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Save", command=save).grid(
            row=row, column=0, columnspan=2, pady=15
        )

    def _approve_claim(self):
        sel = self._claims_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a claim to approve.")
            return
        claim_id = int(sel[0])
        claim = self._svc.get_claim(claim_id)
        if not claim:
            messagebox.showerror("Error", "Claim not found.")
            return
        if claim.get("status") != "submitted":
            messagebox.showinfo("Info", "Only submitted claims can be approved.")
            return

        win = tk.Toplevel(self)
        win.title(f"Approve Claim #{claim_id}")
        win.geometry("340x140")
        win.resizable(False, False)

        tk.Label(win, text="Approver ID*:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        approver_entry = tk.Entry(win, width=20)
        approver_entry.grid(row=0, column=1, padx=10, pady=10)

        def save():
            try:
                approved_by = int(approver_entry.get().strip())
                self._svc.approve_claim(claim_id, approved_by)
                messagebox.showinfo("Success", "Claim approved.")
                win.destroy()
                self._load_claims()
                self._load_pending()
            except ValueError:
                messagebox.showerror("Error", "Approver ID must be a number.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Approve", command=save).grid(
            row=1, column=0, columnspan=2, pady=10
        )

    def _reject_claim(self):
        sel = self._claims_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a claim to reject.")
            return
        claim_id = int(sel[0])
        claim = self._svc.get_claim(claim_id)
        if not claim:
            messagebox.showerror("Error", "Claim not found.")
            return
        if claim.get("status") != "submitted":
            messagebox.showinfo("Info", "Only submitted claims can be rejected.")
            return

        win = tk.Toplevel(self)
        win.title(f"Reject Claim #{claim_id}")
        win.geometry("380x200")
        win.resizable(False, False)

        tk.Label(win, text="Rejection Reason:").grid(row=0, column=0, padx=10, pady=10, sticky="ne")
        notes_text = tk.Text(win, width=25, height=4)
        notes_text.grid(row=0, column=1, padx=10, pady=10)

        def save():
            try:
                notes = notes_text.get("1.0", "end").strip() or None
                self._svc.reject_claim(claim_id, notes=notes)
                messagebox.showinfo("Success", "Claim rejected.")
                win.destroy()
                self._load_claims()
                self._load_pending()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Reject", command=save).grid(
            row=1, column=0, columnspan=2, pady=10
        )

    def _mark_paid(self):
        sel = self._claims_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a claim to mark as paid.")
            return
        claim_id = int(sel[0])
        claim = self._svc.get_claim(claim_id)
        if not claim:
            messagebox.showerror("Error", "Claim not found.")
            return
        if claim.get("status") != "approved":
            messagebox.showinfo("Info", "Only approved claims can be marked as paid.")
            return
        if messagebox.askyesno("Confirm", f"Mark claim #{claim_id} as paid?"):
            try:
                self._svc.mark_paid(claim_id)
                messagebox.showinfo("Success", "Claim marked as paid.")
                self._load_claims()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _delete_claim(self):
        sel = self._claims_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a claim to delete.")
            return
        if messagebox.askyesno("Confirm", "Delete this expense claim?"):
            try:
                self._svc.delete_claim(int(sel[0]))
                self._load_claims()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    # ------------------------------------------------------------------ #
    #  Tab 2: Pending Approvals                                           #
    # ------------------------------------------------------------------ #

    def _build_pending_tab(self):
        tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(tab, text="Pending Approvals")

        toolbar = tk.Frame(tab, bg="#ecf0f1")
        toolbar.pack(fill="x", padx=5, pady=5)
        ttk.Button(toolbar, text="Approve", command=self._approve_pending).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Reject", command=self._reject_pending).pack(side="left", padx=2)
        ttk.Button(toolbar, text="View", command=self._view_pending).pack(side="left", padx=2)

        cols = ("id", "claimant", "date", "description", "category", "amount")
        self._pending_tree = ttk.Treeview(tab, columns=cols, show="headings", height=16)
        for c, heading, w in zip(
            cols,
            ("ID", "Claimant", "Date", "Description", "Category", "Amount"),
            (50, 150, 90, 220, 90, 80),
        ):
            self._pending_tree.heading(c, text=heading)
            self._pending_tree.column(c, width=w, minwidth=40)
        self._pending_tree.pack(fill="both", expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(tab, orient="vertical", command=self._pending_tree.yview)
        self._pending_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

    def _load_pending(self):
        for item in self._pending_tree.get_children():
            self._pending_tree.delete(item)
        try:
            rows = self._svc.list_claims(status="submitted")
            for r in rows:
                name = f"{r.get('first_name', '')} {r.get('last_name', '')}".strip()
                self._pending_tree.insert("", "end", iid=str(r["id"]), values=(
                    r["id"],
                    name or f"Staff #{r.get('claimant_id', '')}",
                    r.get("claim_date", ""),
                    r.get("description", ""),
                    r.get("category", ""),
                    f"{r.get('amount', 0):.2f}",
                ))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _approve_pending(self):
        sel = self._pending_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a claim to approve.")
            return
        claim_id = int(sel[0])

        win = tk.Toplevel(self)
        win.title(f"Approve Claim #{claim_id}")
        win.geometry("340x140")
        win.resizable(False, False)

        tk.Label(win, text="Approver ID*:").grid(row=0, column=0, padx=10, pady=10, sticky="e")
        approver_entry = tk.Entry(win, width=20)
        approver_entry.grid(row=0, column=1, padx=10, pady=10)

        def save():
            try:
                approved_by = int(approver_entry.get().strip())
                self._svc.approve_claim(claim_id, approved_by)
                messagebox.showinfo("Success", "Claim approved.")
                win.destroy()
                self._load_pending()
                self._load_claims()
            except ValueError:
                messagebox.showerror("Error", "Approver ID must be a number.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Approve", command=save).grid(
            row=1, column=0, columnspan=2, pady=10
        )

    def _reject_pending(self):
        sel = self._pending_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a claim to reject.")
            return
        claim_id = int(sel[0])

        win = tk.Toplevel(self)
        win.title(f"Reject Claim #{claim_id}")
        win.geometry("380x200")
        win.resizable(False, False)

        tk.Label(win, text="Rejection Reason:").grid(row=0, column=0, padx=10, pady=10, sticky="ne")
        notes_text = tk.Text(win, width=25, height=4)
        notes_text.grid(row=0, column=1, padx=10, pady=10)

        def save():
            try:
                notes = notes_text.get("1.0", "end").strip() or None
                self._svc.reject_claim(claim_id, notes=notes)
                messagebox.showinfo("Success", "Claim rejected.")
                win.destroy()
                self._load_pending()
                self._load_claims()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(win, text="Reject", command=save).grid(
            row=1, column=0, columnspan=2, pady=10
        )

    def _view_pending(self):
        sel = self._pending_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a claim to view.")
            return
        claim = self._svc.get_claim(int(sel[0]))
        if not claim:
            messagebox.showerror("Error", "Claim not found.")
            return

        win = tk.Toplevel(self)
        win.title(f"Expense Claim #{claim['id']}")
        win.geometry("460x480")
        win.resizable(False, False)

        claimant = f"{claim.get('first_name', '')} {claim.get('last_name', '')}".strip()
        details = [
            ("ID", claim["id"]),
            ("Claimant", claimant or f"#{claim.get('claimant_id', '')}"),
            ("Claim Date", claim.get("claim_date", "")),
            ("Description", claim.get("description", "")),
            ("Category", claim.get("category", "")),
            ("Amount", f"{claim.get('amount', 0):.2f}"),
            ("Mileage", claim.get("mileage", "") or ""),
            ("Mileage Rate", claim.get("mileage_rate", "") or ""),
            ("Receipt", claim.get("receipt_path", "") or ""),
            ("Status", claim.get("status", "")),
            ("Notes", claim.get("notes", "") or ""),
            ("Created", claim.get("created_at", "")),
        ]
        for i, (lbl, val) in enumerate(details):
            tk.Label(win, text=f"{lbl}:", font=("Helvetica", 10, "bold"),
                     anchor="e").grid(row=i, column=0, padx=10, pady=2, sticky="ne")
            tk.Label(win, text=str(val), wraplength=280,
                     anchor="w").grid(row=i, column=1, padx=10, pady=2, sticky="w")

        ttk.Button(win, text="Close", command=win.destroy).grid(
            row=len(details), column=0, columnspan=2, pady=10
        )

    # ------------------------------------------------------------------ #
    #  Tab 3: Statistics                                                  #
    # ------------------------------------------------------------------ #

    def _build_stats_tab(self):
        self._stats_tab = tk.Frame(self._nb, bg="#ecf0f1")
        self._nb.add(self._stats_tab, text="Statistics")

        self._stats_container = tk.Frame(self._stats_tab, bg="#ecf0f1")
        self._stats_container.pack(fill="both", expand=True, padx=20, pady=20)

    def _load_stats(self):
        for widget in self._stats_container.winfo_children():
            widget.destroy()
        try:
            stats = self._svc.get_stats()

            # Summary cards
            summary_frame = tk.LabelFrame(self._stats_container, text="Summary",
                                          bg="#ecf0f1", font=("Helvetica", 11, "bold"))
            summary_frame.pack(fill="x", pady=5)

            labels = [
                ("Total Claims:", stats.get("total_claims", 0)),
                ("Total Amount:", f"{stats.get('total_amount', 0):.2f}"),
                ("Total Paid:", f"{stats.get('total_paid', 0):.2f}"),
                ("Total Pending:", f"{stats.get('total_pending', 0):.2f}"),
                ("Mileage Claims:", stats.get("total_mileage_claims", 0)),
            ]
            for i, (lbl, val) in enumerate(labels):
                r, c = divmod(i, 3)
                tk.Label(summary_frame, text=lbl, font=("Helvetica", 10, "bold"),
                         bg="#ecf0f1", anchor="e").grid(row=r, column=c * 2, padx=8, pady=4, sticky="e")
                tk.Label(summary_frame, text=str(val), font=("Helvetica", 10),
                         bg="#ecf0f1", anchor="w").grid(row=r, column=c * 2 + 1, padx=8, pady=4, sticky="w")

            # By-status breakdown
            status_frame = tk.LabelFrame(self._stats_container, text="Claims by Status",
                                         bg="#ecf0f1", font=("Helvetica", 11, "bold"))
            status_frame.pack(fill="x", pady=10)

            by_status = stats.get("by_status", {})
            if by_status:
                tk.Label(status_frame, text="Status", font=("Helvetica", 10, "bold"),
                         bg="#ecf0f1").grid(row=0, column=0, padx=10, pady=2)
                tk.Label(status_frame, text="Count", font=("Helvetica", 10, "bold"),
                         bg="#ecf0f1").grid(row=0, column=1, padx=10, pady=2)
                for i, (st, cnt) in enumerate(by_status.items(), start=1):
                    tk.Label(status_frame, text=st or "",
                             bg="#ecf0f1").grid(row=i, column=0, padx=10, pady=2)
                    tk.Label(status_frame, text=str(cnt),
                             bg="#ecf0f1").grid(row=i, column=1, padx=10, pady=2)
            else:
                tk.Label(status_frame, text="No claim data.",
                         bg="#ecf0f1").pack(padx=10, pady=10)

            # By-category breakdown
            cat_frame = tk.LabelFrame(self._stats_container, text="Claims by Category",
                                      bg="#ecf0f1", font=("Helvetica", 11, "bold"))
            cat_frame.pack(fill="x", pady=10)

            by_category = stats.get("by_category", [])
            if by_category:
                tk.Label(cat_frame, text="Category", font=("Helvetica", 10, "bold"),
                         bg="#ecf0f1").grid(row=0, column=0, padx=10, pady=2)
                tk.Label(cat_frame, text="Count", font=("Helvetica", 10, "bold"),
                         bg="#ecf0f1").grid(row=0, column=1, padx=10, pady=2)
                tk.Label(cat_frame, text="Total Amount", font=("Helvetica", 10, "bold"),
                         bg="#ecf0f1").grid(row=0, column=2, padx=10, pady=2)
                for i, bc in enumerate(by_category, start=1):
                    tk.Label(cat_frame, text=bc.get("category", ""),
                             bg="#ecf0f1").grid(row=i, column=0, padx=10, pady=2)
                    tk.Label(cat_frame, text=str(bc.get("cnt", 0)),
                             bg="#ecf0f1").grid(row=i, column=1, padx=10, pady=2)
                    tk.Label(cat_frame, text=f"{bc.get('total_amount', 0):.2f}",
                             bg="#ecf0f1").grid(row=i, column=2, padx=10, pady=2)
            else:
                tk.Label(cat_frame, text="No claim data.",
                         bg="#ecf0f1").pack(padx=10, pady=10)
        except Exception as e:
            tk.Label(self._stats_container, text=f"Error loading stats: {e}",
                     bg="#ecf0f1", fg="red").pack(pady=20)

    # ------------------------------------------------------------------ #
    #  Refresh                                                            #
    # ------------------------------------------------------------------ #

    def refresh(self):
        self._load_claims()
        self._load_pending()
        self._load_stats()
