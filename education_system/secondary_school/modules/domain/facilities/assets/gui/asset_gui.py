"""Asset Management GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.facilities.assets.services.asset_service import (
    AssetService, ASSET_CATEGORIES, CONDITIONS, STATUSES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class AssetFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = AssetService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Asset Management", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Add Asset", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)
        tk.Label(toolbar, text="Category:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._cat_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._cat_var,
                     values=["All"] + list(ASSET_CATEGORIES), state="readonly", width=14).pack(side="left")
        self._cat_var.trace_add("write", lambda *_: self._load())
        tk.Label(toolbar, text="Search:", bg=MAIN_BG).pack(side="left", padx=(10, 4))
        self._search_var = tk.StringVar()
        se = ttk.Entry(toolbar, textvariable=self._search_var, width=15)
        se.pack(side="left")
        se.bind("<Return>", lambda *_: self._load())

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("tag", "name", "category", "serial", "location", "assigned", "condition", "status", "cost")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("tag", "Tag", 70), ("name", "Name", 140), ("category", "Category", 80),
                           ("serial", "Serial", 90), ("location", "Location", 70),
                           ("assigned", "Assigned To", 90), ("condition", "Condition", 60),
                           ("status", "Status", 60), ("cost", "Cost", 60)]:
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
        search = self._search_var.get().strip()
        try:
            assets = self._svc.list_assets(
                category=cat if cat != "All" else None,
                search=search or None)
            for a in assets:
                self._tree.insert("", "end", iid=a["id"], values=(
                    a["asset_tag"], a["name"], a["category"],
                    a.get("serial_number") or "", a.get("location") or "",
                    a.get("assigned_to") or "", a["condition"], a["status"],
                    f"£{a['purchase_cost']:.2f}" if a.get("purchase_cost") else ""))
            self._status_var.set(f"{len(assets)} asset(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        dlg = tk.Toplevel(self)
        dlg.title("Add Asset")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        fields = [("Asset Tag", "tag", "", None), ("Name", "name", "", None),
                  ("Category", "category", "IT", list(ASSET_CATEGORIES)),
                  ("Serial Number", "serial", "", None), ("Location", "location", "", None),
                  ("Assigned To", "assigned", "", None), ("Department", "department", "", None),
                  ("Purchase Date", "purchase_date", "", None), ("Purchase Cost (£)", "cost", "", None),
                  ("Warranty Expiry", "warranty", "", None),
                  ("Condition", "condition", "good", list(CONDITIONS))]
        for row, (l, k, d, vals) in enumerate(fields):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            if vals:
                ttk.Combobox(c, textvariable=vars_[k], values=vals, state="readonly", width=20).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[k], width=22).grid(row=row, column=1, **pad)
        result = [None]
        def save():
            tag = vars_["tag"].get().strip()
            nm = vars_["name"].get().strip()
            if not tag or not nm:
                messagebox.showwarning("Validation", "Tag and name required.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()
        ttk.Button(c, text="Save", command=save).grid(row=len(fields), column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            cost = float(d["cost"]) if d["cost"] else None
        except ValueError:
            cost = None
        try:
            self._svc.add_asset(d["tag"], d["name"], d.get("category") or "IT",
                                None, d.get("serial") or None, d.get("location") or None,
                                d.get("assigned") or None, d.get("department") or None,
                                d.get("purchase_date") or None, cost,
                                d.get("warranty") or None, d.get("condition") or "good")
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this asset?"):
            self._svc.delete_asset(int(sel[0]))
            self._load()
