"""Visitor Management GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.facilities.visitors.services.visitor_service import VisitorService

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class VisitorFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = VisitorService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Visitor Management", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Sign In Visitor", command=self._on_sign_in).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Sign Out", command=self._on_sign_out).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)
        self._onsite_var = tk.BooleanVar()
        ttk.Checkbutton(toolbar, text="On-Site Only", variable=self._onsite_var,
                        command=self._load).pack(side="left", padx=10)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("name", "org", "purpose", "visiting", "badge", "dbs", "sign_in", "sign_out", "car")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("name", "Name", 120), ("org", "Organisation", 100),
                           ("purpose", "Purpose", 110), ("visiting", "Visiting", 80),
                           ("badge", "Badge", 45), ("dbs", "DBS", 35),
                           ("sign_in", "Sign In", 110), ("sign_out", "Sign Out", 110),
                           ("car", "Car Reg", 70)]:
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
        try:
            visitors = self._svc.list_visitors(on_site_only=self._onsite_var.get())
            for v in visitors:
                self._tree.insert("", "end", iid=v["id"], values=(
                    v["visitor_name"], v.get("organisation") or "", v["purpose"],
                    v.get("visiting") or "", v.get("badge_number") or "",
                    "Yes" if v["dbs_checked"] else "No",
                    v["sign_in_time"][:16] if v.get("sign_in_time") else "",
                    v["sign_out_time"][:16] if v.get("sign_out_time") else "",
                    v.get("car_registration") or ""))
            on_site = self._svc.on_site_count()
            self._status_var.set(f"{len(visitors)} visitor(s) | On-site: {on_site}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_sign_in(self):
        dlg = tk.Toplevel(self)
        dlg.title("Sign In Visitor")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        fields = [("Visitor Name", "name", ""), ("Organisation", "org", ""),
                  ("Purpose", "purpose", ""), ("Visiting", "visiting", ""),
                  ("Badge Number", "badge", ""), ("Car Registration", "car", "")]
        for row, (l, k, d) in enumerate(fields):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            ttk.Entry(c, textvariable=vars_[k], width=25).grid(row=row, column=1, **pad)
        row = len(fields)
        vars_["dbs"] = tk.BooleanVar()
        ttk.Checkbutton(c, text="DBS Checked", variable=vars_["dbs"]).grid(row=row, column=1, sticky="w", **pad)
        result = [None]
        def save():
            n = vars_["name"].get().strip()
            p = vars_["purpose"].get().strip()
            if not n or not p:
                messagebox.showwarning("Validation", "Name and purpose required.")
                return
            result[0] = {k: v.get().strip() if isinstance(v, tk.StringVar) else v.get() for k, v in vars_.items()}
            dlg.destroy()
        ttk.Button(c, text="Sign In", command=save).grid(row=row + 1, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            self._svc.sign_in(d["name"], d["purpose"], d.get("visiting") or None,
                              d.get("org") or None, d.get("badge") or None,
                              d.get("dbs", False), d.get("car") or None)
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_sign_out(self):
        sel = self._tree.selection()
        if not sel:
            return
        self._svc.sign_out(int(sel[0]))
        self._load()

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this visitor record?"):
            self._svc.delete_visitor(int(sel[0]))
            self._load()
