"""SEND management GUI."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.secondary_school.modules.domain.pastoral_care.send.services.send_service import (
    SENDService, SEN_TYPES, PRIMARY_NEEDS,
)
from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
from education_system.secondary_school.core.exceptions import SENDError

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class SENDFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._svc = SENDService(db_path)
        self._stu_svc = StudentService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="SEND Register", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Add Record", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View Provisions", command=self._on_provisions).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("student", "year", "type", "need", "ehcp", "key_worker", "status")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("student", "Student", 150), ("year", "Year", 40),
                           ("type", "SEN Type", 90), ("need", "Primary Need", 180),
                           ("ehcp", "EHCP", 40), ("key_worker", "Key Worker", 100),
                           ("status", "Status", 60)]:
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
            records = self._svc.list_records()
            for r in records:
                self._tree.insert("", "end", iid=r["id"], values=(
                    f"{r['first_name']} {r['last_name']}", r["year_group"],
                    r["sen_type"], r.get("primary_need") or "", "Yes" if r["ehcp"] else "No",
                    r.get("key_worker") or "", r["status"]))
            self._status_var.set(f"{len(records)} SEND record(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        students = self._stu_svc.list_students(status="active")
        if not students:
            messagebox.showwarning("Warning", "No students found.")
            return
        dlg = tk.Toplevel(self)
        dlg.title("Add SEND Record")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        row = 0
        tk.Label(c, text="Student", font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        vars_["student"] = tk.StringVar()
        ttk.Combobox(c, textvariable=vars_["student"], values=stu_names, state="readonly", width=30).grid(row=row, column=1, **pad)
        for label, key, default, values in [
            ("SEN Type", "sen_type", "SEN Support", list(SEN_TYPES)),
            ("Primary Need", "primary_need", "", list(PRIMARY_NEEDS)),
            ("Key Worker", "key_worker", "", None),
            ("Diagnosis", "diagnosis", "", None),
            ("Strategies", "strategies", "", None),
            ("Access Arrangements", "access_arrangements", "", None),
        ]:
            row += 1
            tk.Label(c, text=label, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[key] = tk.StringVar(value=default)
            if values:
                ttk.Combobox(c, textvariable=vars_[key], values=values, state="readonly", width=30).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[key], width=32).grid(row=row, column=1, **pad)
        row += 1
        vars_["ehcp"] = tk.BooleanVar()
        ttk.Checkbutton(c, text="Has EHCP", variable=vars_["ehcp"]).grid(row=row, column=1, sticky="w", **pad)
        result = [None]
        def save():
            sv = vars_["student"].get()
            if not sv:
                messagebox.showwarning("Validation", "Select a student.")
                return
            sid = sv.split(" - ")[0]
            stu_pk = next((s["id"] for s in students if s["student_id"] == sid), None)
            result[0] = {"student_id": stu_pk}
            for k in ("sen_type", "primary_need", "key_worker", "diagnosis", "strategies", "access_arrangements"):
                result[0][k] = vars_[k].get().strip() or None
            result[0]["ehcp"] = vars_["ehcp"].get()
            dlg.destroy()
        row += 1
        btn = tk.Frame(c)
        btn.grid(row=row, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn, text="Save", command=save).pack(side="left", padx=5)
        ttk.Button(btn, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)
        self.wait_window(dlg)
        if result[0] is None:
            return
        try:
            self._svc.create_record(**result[0])
            messagebox.showinfo("Success", "SEND record created.")
            self._load()
        except SENDError as e:
            messagebox.showerror("Error", str(e))

    def _on_provisions(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a SEND record first.")
            return
        record_id = int(sel[0])
        provisions = self._svc.list_provisions(record_id)
        dlg = tk.Toplevel(self)
        dlg.title("Provisions")
        dlg.geometry("600x400")
        cols = ("type", "description", "frequency", "staff", "start", "end", "status")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        for col, h, w in [("type", "Type", 100), ("description", "Description", 150),
                           ("frequency", "Frequency", 70), ("staff", "Staff", 100),
                           ("start", "Start", 80), ("end", "End", 80), ("status", "Status", 60)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        for p in provisions:
            tree.insert("", "end", values=(p["provision_type"], p.get("description") or "",
                        p.get("frequency") or "", p.get("staff_responsible") or "",
                        p.get("start_date") or "", p.get("end_date") or "", p["status"]))
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        def add_prov():
            pd = tk.Toplevel(dlg)
            pd.title("Add Provision")
            pd.resizable(False, False)
            fc = tk.Frame(pd, padx=15, pady=10)
            fc.pack()
            pv = {}
            for i, (l, k, d) in enumerate([("Type", "provision_type", ""),
                                             ("Description", "description", ""),
                                             ("Frequency", "frequency", ""),
                                             ("Staff", "staff_responsible", ""),
                                             ("Start Date", "start_date", ""),
                                             ("End Date", "end_date", "")]):
                tk.Label(fc, text=l, font=("Helvetica", 9, "bold")).grid(row=i, column=0, sticky="w", padx=5, pady=3)
                pv[k] = tk.StringVar(value=d)
                ttk.Entry(fc, textvariable=pv[k], width=25).grid(row=i, column=1, padx=5, pady=3)
            def sv():
                pt = pv["provision_type"].get().strip()
                if not pt:
                    return
                self._svc.add_provision(record_id, pt, pv["description"].get().strip() or None,
                                        pv["frequency"].get().strip() or None,
                                        pv["staff_responsible"].get().strip() or None,
                                        pv["start_date"].get().strip() or None,
                                        pv["end_date"].get().strip() or None)
                pd.destroy()
                dlg.destroy()
                self._on_provisions()
            ttk.Button(fc, text="Save", command=sv).grid(row=6, column=0, columnspan=2, pady=8)
        ttk.Button(dlg, text="Add Provision", command=add_prov).pack(pady=(0, 10))

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this SEND record and all provisions?"):
            self._svc.delete_record(int(sel[0]))
            self._load()
