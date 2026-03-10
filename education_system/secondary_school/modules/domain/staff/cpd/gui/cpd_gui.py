"""CPD (Staff Training) GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.staff.cpd.services.cpd_service import (
    CPDService, CPD_CATEGORIES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class CPDFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = CPDService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="CPD / Staff Training", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Add Record", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Staff Summary", command=self._on_summary).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)
        tk.Label(toolbar, text="Category:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._cat_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._cat_var,
                     values=["All"] + list(CPD_CATEGORIES), state="readonly", width=16).pack(side="left")
        self._cat_var.trace_add("write", lambda *_: self._load())

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("staff", "training", "category", "provider", "date", "hours", "cost", "cert")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("staff", "Staff", 110), ("training", "Training", 160),
                           ("category", "Category", 90), ("provider", "Provider", 100),
                           ("date", "Date", 80), ("hours", "Hours", 45),
                           ("cost", "Cost", 55), ("cert", "Cert", 35)]:
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
            records = self._svc.list_records(category=cat if cat != "All" else None)
            for r in records:
                self._tree.insert("", "end", iid=r["id"], values=(
                    r["staff_name"], r["training_title"], r["category"],
                    r.get("provider") or "", r["date"],
                    r.get("duration_hours") or "",
                    f"£{r['cost']:.2f}" if r.get("cost") else "",
                    "Yes" if r["certificate"] else ""))
            self._status_var.set(f"{len(records)} record(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        dlg = tk.Toplevel(self)
        dlg.title("Add CPD Record")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        fields = [("Staff Name", "staff", "", None), ("Training Title", "title", "", None),
                  ("Category", "category", "general", list(CPD_CATEGORIES)),
                  ("Provider", "provider", "", None), ("Date (YYYY-MM-DD)", "date", "", None),
                  ("Duration (hours)", "hours", "", None), ("Cost (£)", "cost", "0", None)]
        for row, (l, k, d, vals) in enumerate(fields):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            if vals:
                ttk.Combobox(c, textvariable=vars_[k], values=vals, state="readonly", width=20).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[k], width=25).grid(row=row, column=1, **pad)
        row = len(fields)
        vars_["cert"] = tk.BooleanVar()
        ttk.Checkbutton(c, text="Certificate Received", variable=vars_["cert"]).grid(row=row, column=1, sticky="w", **pad)
        result = [None]
        def save():
            s = vars_["staff"].get().strip()
            t = vars_["title"].get().strip()
            d = vars_["date"].get().strip()
            if not s or not t or not d:
                messagebox.showwarning("Validation", "Staff, title and date required.")
                return
            result[0] = {k: v.get().strip() if isinstance(v, tk.StringVar) else v.get() for k, v in vars_.items()}
            dlg.destroy()
        ttk.Button(c, text="Save", command=save).grid(row=row + 1, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            hours = float(d["hours"]) if d["hours"] else None
        except ValueError:
            hours = None
        try:
            cost = float(d["cost"]) if d["cost"] else 0.0
        except ValueError:
            cost = 0.0
        try:
            self._svc.add_record(d["staff"], d["title"], d["date"],
                                 d.get("category") or "general", d.get("provider") or None,
                                 hours, cost, d.get("cert", False))
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_summary(self):
        try:
            summary = self._svc.staff_summary()
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        dlg = tk.Toplevel(self)
        dlg.title("Staff CPD Summary")
        dlg.geometry("400x300")
        cols = ("staff", "courses", "hours")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        for col, h, w in [("staff", "Staff", 160), ("courses", "Courses", 60), ("hours", "Total Hours", 80)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        for s in summary:
            tree.insert("", "end", values=(s["staff_name"], s["courses"], f"{s['total_hours']:.1f}"))
        tree.pack(fill="both", expand=True, padx=10, pady=10)

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this CPD record?"):
            self._svc.delete_record(int(sel[0]))
            self._load()
