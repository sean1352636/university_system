"""Policy Management GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.admin.policies.services.policy_service import (
    PolicyService, POLICY_CATEGORIES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class PolicyFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = PolicyService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Policies", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Add Policy", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Acknowledge", command=self._on_acknowledge).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View Acks", command=self._on_view_acks).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)
        tk.Label(toolbar, text="Category:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._cat_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._cat_var,
                     values=["All"] + list(POLICY_CATEGORIES), state="readonly", width=16).pack(side="left")
        self._cat_var.trace_add("write", lambda *_: self._load())

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("title", "category", "version", "approved", "approval_date", "review", "acks")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("title", "Title", 180), ("category", "Category", 100),
                           ("version", "Ver", 35), ("approved", "Approved By", 100),
                           ("approval_date", "Approved", 80), ("review", "Review Date", 80),
                           ("acks", "Acks", 35)]:
            self._tree.heading(col, text=h)
            self._tree.column(col, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load()

    def _load(self):
        self._tree.delete(*self._tree.get_children())
        cat = self._cat_var.get()
        try:
            policies = self._svc.list_policies(category=cat if cat != "All" else None)
            for p in policies:
                ack_cnt = self._svc.acknowledgement_count(p["id"])
                self._tree.insert("", "end", iid=p["id"], values=(
                    p["title"], p["category"], p.get("version") or "",
                    p.get("approved_by") or "", p.get("approval_date") or "",
                    p.get("review_date") or "", ack_cnt))
            self._status_var.set(f"{len(policies)} policy/policies")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        dlg = tk.Toplevel(self)
        dlg.title("Add Policy")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        fields = [("Title", "title", "", None), ("Category", "cat", "general", list(POLICY_CATEGORIES)),
                  ("Version", "ver", "1.0", None), ("Approved By", "approved", "", None),
                  ("Approval Date", "adate", "", None), ("Review Date", "rdate", "", None),
                  ("Summary", "summary", "", None)]
        for row, (l, k, d, vals) in enumerate(fields):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            if vals:
                ttk.Combobox(c, textvariable=vars_[k], values=vals, state="readonly", width=18).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[k], width=25).grid(row=row, column=1, **pad)
        result = [None]

        def save():
            t = vars_["title"].get().strip()
            if not t:
                messagebox.showwarning("Validation", "Title required.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()

        ttk.Button(c, text="Save", command=save).grid(row=len(fields), column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            self._svc.add_policy(d["title"], d.get("cat") or "general", d.get("ver") or "1.0",
                                 d.get("approved") or None, d.get("adate") or None,
                                 d.get("rdate") or None, d.get("summary") or None)
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_acknowledge(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a policy first.")
            return
        policy_id = int(sel[0])
        dlg = tk.Toplevel(self)
        dlg.title("Acknowledge Policy")
        dlg.resizable(False, False)
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        name_var = tk.StringVar()
        tk.Label(c, text="Staff Name", font=("Helvetica", 9, "bold")).pack(anchor="w")
        ttk.Entry(c, textvariable=name_var, width=25).pack(pady=5)
        result = [None]

        def save():
            n = name_var.get().strip()
            if n:
                result[0] = n
            dlg.destroy()

        ttk.Button(c, text="Acknowledge", command=save).pack(pady=10)
        self.wait_window(dlg)
        if result[0]:
            try:
                self._svc.acknowledge(policy_id, result[0])
                self._load()
                messagebox.showinfo("Success", "Policy acknowledged.")
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _on_view_acks(self):
        sel = self._tree.selection()
        if not sel:
            return
        acks = self._svc.list_acknowledgements(int(sel[0]))
        dlg = tk.Toplevel(self)
        dlg.title(f"Acknowledgements ({len(acks)})")
        dlg.geometry("350x250")
        cols = ("staff", "date")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        for col, h, w in [("staff", "Staff Name", 180), ("date", "Date", 130)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        for a in acks:
            tree.insert("", "end", values=(a["staff_name"], a["acknowledged_at"]))
        tree.pack(fill="both", expand=True, padx=10, pady=10)

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this policy and all acknowledgements?"):
            self._svc.delete_policy(int(sel[0]))
            self._load()
