"""Admissions GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.admin.admissions.services.admissions_service import (
    AdmissionsService, APPLICATION_STATUSES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"
YEAR_GROUPS = ("7", "8", "9", "10", "11")


class AdmissionsFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = AdmissionsService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Admissions", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="New Application", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Change Status", command=self._on_status).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)
        tk.Label(toolbar, text="Status:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._filter_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._filter_var,
                     values=["All"] + list(APPLICATION_STATUSES), state="readonly", width=14).pack(side="left")
        self._filter_var.trace_add("write", lambda *_: self._load())

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        cols = ("name", "dob", "year", "parent", "phone", "prev_school", "applied", "status")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("name", "Applicant", 130), ("dob", "DOB", 80), ("year", "Year", 40),
                           ("parent", "Parent", 110), ("phone", "Phone", 90),
                           ("prev_school", "Previous School", 110), ("applied", "Applied", 80),
                           ("status", "Status", 90)]:
            self._tree.heading(col, text=h)
            self._tree.column(col, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._summary_frame = tk.Frame(self, bg=MAIN_BG)
        self._summary_frame.pack(fill="x", padx=15)

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load()
        self._load_summary()

    def _load(self):
        self._tree.delete(*self._tree.get_children())
        f = self._filter_var.get()
        try:
            apps = self._svc.list_applications(status=f if f != "All" else None)
            for a in apps:
                self._tree.insert("", "end", iid=a["id"], values=(
                    f"{a['applicant_first_name']} {a['applicant_last_name']}",
                    a.get("date_of_birth") or "", a["year_group_applying"],
                    a["parent_name"], a.get("parent_phone") or "",
                    a.get("previous_school") or "", a["application_date"], a["status"]))
            self._status_var.set(f"{len(apps)} application(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_summary(self):
        for w in self._summary_frame.winfo_children():
            w.destroy()
        try:
            summary = self._svc.status_summary()
            if summary:
                parts = [f"{s['status']}: {s['cnt']}" for s in summary]
                tk.Label(self._summary_frame, text="  |  ".join(parts),
                         bg=MAIN_BG, font=("Helvetica", 9), fg="#7f8c8d").pack(anchor="w")
        except Exception:
            pass

    def _on_add(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Application")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        fields = [("First Name", "first_name", "", None), ("Last Name", "last_name", "", None),
                  ("Date of Birth", "dob", "", None), ("Gender", "gender", "", ["Male", "Female", "Other"]),
                  ("Year Group", "year", "7", list(YEAR_GROUPS)),
                  ("Address", "address", "", None),
                  ("Parent Name", "parent_name", "", None), ("Parent Email", "parent_email", "", None),
                  ("Parent Phone", "parent_phone", "", None), ("Previous School", "prev_school", "", None),
                  ("SEN Needs", "sen", "", None), ("Medical Info", "medical", "", None)]
        for row, (l, k, d, vals) in enumerate(fields):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            if vals:
                ttk.Combobox(c, textvariable=vars_[k], values=vals, state="readonly", width=20).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[k], width=25).grid(row=row, column=1, **pad)
        result = [None]
        def save():
            fn = vars_["first_name"].get().strip()
            ln = vars_["last_name"].get().strip()
            pn = vars_["parent_name"].get().strip()
            yr = vars_["year"].get().strip()
            if not fn or not ln or not pn or not yr:
                messagebox.showwarning("Validation", "Name, year group and parent name required.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()
        ttk.Button(c, text="Submit", command=save).grid(row=len(fields), column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            self._svc.create_application(
                d["first_name"], d["last_name"], d["year"], d["parent_name"],
                d.get("dob") or None, d.get("gender") or None, d.get("address") or None,
                d.get("parent_email") or None, d.get("parent_phone") or None,
                d.get("prev_school") or None, d.get("sen") or None, d.get("medical") or None)
            self._load()
            self._load_summary()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_status(self):
        sel = self._tree.selection()
        if not sel:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Change Status")
        dlg.resizable(False, False)
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        tk.Label(c, text="New Status:", font=("Helvetica", 9, "bold")).pack(anchor="w")
        status_var = tk.StringVar(value="under_review")
        ttk.Combobox(c, textvariable=status_var, values=list(APPLICATION_STATUSES),
                     state="readonly", width=20).pack(pady=5)
        result = [None]
        def save():
            result[0] = status_var.get()
            dlg.destroy()
        ttk.Button(c, text="Update", command=save).pack(pady=10)
        self.wait_window(dlg)
        if result[0]:
            decision_by = self._auth.get("username") if self._auth else None
            try:
                self._svc.update_status(int(sel[0]), result[0], decision_by)
                self._load()
                self._load_summary()
            except Exception as e:
                messagebox.showerror("Error", str(e))

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this application?"):
            self._svc.delete_application(int(sel[0]))
            self._load()
            self._load_summary()
