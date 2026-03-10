"""Medical / First Aid GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.student_life.medical.services.medical_service import (
    MedicalService, SEVERITIES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class MedicalFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = MedicalService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Medical / First Aid", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=15, pady=10)

        # --- Conditions tab ---
        cond_tab = tk.Frame(nb, bg=MAIN_BG)
        nb.add(cond_tab, text="Medical Conditions")
        ct = tk.Frame(cond_tab, bg=MAIN_BG, pady=8)
        ct.pack(fill="x", padx=10)
        ttk.Button(ct, text="Add Condition", command=self._on_add_condition).pack(side="left", padx=4)
        ttk.Button(ct, text="Delete", command=self._on_delete_condition).pack(side="left", padx=4)

        cf = tk.Frame(cond_tab)
        cf.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols = ("student", "year", "condition", "severity", "medications", "allergies")
        self._cond_tree = ttk.Treeview(cf, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("student", "Student", 130), ("year", "Year", 40),
                           ("condition", "Condition", 130), ("severity", "Severity", 65),
                           ("medications", "Medications", 130), ("allergies", "Allergies", 130)]:
            self._cond_tree.heading(col, text=h)
            self._cond_tree.column(col, width=w, anchor="center")
        vsb = ttk.Scrollbar(cf, orient="vertical", command=self._cond_tree.yview)
        self._cond_tree.configure(yscrollcommand=vsb.set)
        self._cond_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # --- First Aid tab ---
        fa_tab = tk.Frame(nb, bg=MAIN_BG)
        nb.add(fa_tab, text="First Aid Log")
        ft = tk.Frame(fa_tab, bg=MAIN_BG, pady=8)
        ft.pack(fill="x", padx=10)
        ttk.Button(ft, text="Log Incident", command=self._on_add_incident).pack(side="left", padx=4)
        ttk.Button(ft, text="Delete", command=self._on_delete_incident).pack(side="left", padx=4)

        ff = tk.Frame(fa_tab)
        ff.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        fcols = ("date", "time", "student", "year", "description", "treatment", "by", "parent", "home")
        self._fa_tree = ttk.Treeview(ff, columns=fcols, show="headings", selectmode="browse")
        for col, h, w in [("date", "Date", 80), ("time", "Time", 50), ("student", "Student", 110),
                           ("year", "Yr", 30), ("description", "Description", 160),
                           ("treatment", "Treatment", 130), ("by", "By", 80),
                           ("parent", "Parent", 50), ("home", "Home", 45)]:
            self._fa_tree.heading(col, text=h)
            self._fa_tree.column(col, width=w, anchor="center")
        fvsb = ttk.Scrollbar(ff, orient="vertical", command=self._fa_tree.yview)
        self._fa_tree.configure(yscrollcommand=fvsb.set)
        self._fa_tree.pack(side="left", fill="both", expand=True)
        fvsb.pack(side="right", fill="y")

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load_conditions()
        self._load_incidents()

    def _load_conditions(self):
        self._cond_tree.delete(*self._cond_tree.get_children())
        try:
            conds = self._svc.list_conditions()
            for c in conds:
                self._cond_tree.insert("", "end", iid=c["id"], values=(
                    f"{c['first_name']} {c['last_name']}", c.get("year_group") or "",
                    c["condition_name"], c["severity"],
                    c.get("medications") or "", c.get("allergies") or ""))
            self._status_var.set(f"{len(conds)} condition(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_incidents(self):
        self._fa_tree.delete(*self._fa_tree.get_children())
        try:
            incidents = self._svc.list_incidents()
            for i in incidents:
                desc = (i["description"][:40] + "...") if len(i["description"]) > 40 else i["description"]
                self._fa_tree.insert("", "end", iid=i["id"], values=(
                    i["incident_date"], i.get("incident_time") or "",
                    f"{i['first_name']} {i['last_name']}", i.get("year_group") or "",
                    desc, i.get("treatment") or "", i.get("treated_by") or "",
                    "Yes" if i["parent_notified"] else "No",
                    "Yes" if i["sent_home"] else "No"))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add_condition(self):
        from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
        students = StudentService(self._db_path).list_students(status="active")
        if not students:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Add Medical Condition")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        vars_ = {}
        row = 0
        tk.Label(c, text="Student", font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        vars_["student"] = tk.StringVar()
        ttk.Combobox(c, textvariable=vars_["student"], values=stu_names, state="readonly", width=28).grid(row=row, column=1, **pad)
        for rr, (l, k, d, vals) in enumerate([
            ("Condition", "condition_name", "", None),
            ("Severity", "severity", "low", list(SEVERITIES)),
            ("Medications", "medications", "", None),
            ("Allergies", "allergies", "", None),
            ("Care Plan", "care_plan", "", None),
            ("Doctor Name", "doctor_name", "", None),
            ("Doctor Phone", "doctor_phone", "", None)], start=1):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=rr, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            if vals:
                ttk.Combobox(c, textvariable=vars_[k], values=vals, state="readonly", width=20).grid(row=rr, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[k], width=25).grid(row=rr, column=1, **pad)
        result = [None]
        def save():
            sv = vars_["student"].get()
            cn = vars_["condition_name"].get().strip()
            if not sv or not cn:
                messagebox.showwarning("Validation", "Student and condition required.")
                return
            sid_str = sv.split(" - ")[0]
            spk = next((s["id"] for s in students if s["student_id"] == sid_str), None)
            result[0] = {"student_id": spk}
            for k in ("condition_name", "severity", "medications", "allergies", "care_plan", "doctor_name", "doctor_phone"):
                result[0][k] = vars_[k].get().strip() or None
            dlg.destroy()
        ttk.Button(c, text="Save", command=save).grid(row=8, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            self._svc.add_condition(d["student_id"], d["condition_name"], d.get("severity") or "low",
                                    d.get("medications"), d.get("allergies"), d.get("care_plan"),
                                    None, d.get("doctor_name"), d.get("doctor_phone"))
            self._load_conditions()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_delete_condition(self):
        sel = self._cond_tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this medical condition?"):
            self._svc.delete_condition(int(sel[0]))
            self._load_conditions()

    def _on_add_incident(self):
        from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
        students = StudentService(self._db_path).list_students(status="active")
        if not students:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Log First Aid Incident")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        vars_ = {}
        row = 0
        tk.Label(c, text="Student", font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        vars_["student"] = tk.StringVar()
        ttk.Combobox(c, textvariable=vars_["student"], values=stu_names, state="readonly", width=28).grid(row=row, column=1, **pad)
        for rr, (l, k, d) in enumerate([
            ("Date (YYYY-MM-DD)", "date", ""), ("Time", "time", ""),
            ("Location", "location", ""), ("Description", "description", ""),
            ("Treatment", "treatment", ""), ("Treated By", "treated_by", "")], start=1):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=rr, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            ttk.Entry(c, textvariable=vars_[k], width=25).grid(row=rr, column=1, **pad)
        row = 7
        vars_["parent_notified"] = tk.BooleanVar()
        ttk.Checkbutton(c, text="Parent Notified", variable=vars_["parent_notified"]).grid(row=row, column=1, sticky="w", **pad)
        row += 1
        vars_["sent_home"] = tk.BooleanVar()
        ttk.Checkbutton(c, text="Sent Home", variable=vars_["sent_home"]).grid(row=row, column=1, sticky="w", **pad)
        result = [None]
        def save():
            sv = vars_["student"].get()
            desc = vars_["description"].get().strip()
            if not sv or not desc:
                messagebox.showwarning("Validation", "Student and description required.")
                return
            sid_str = sv.split(" - ")[0]
            spk = next((s["id"] for s in students if s["student_id"] == sid_str), None)
            result[0] = {"student_id": spk, "description": desc,
                         "date": vars_["date"].get().strip() or None,
                         "time": vars_["time"].get().strip() or None,
                         "location": vars_["location"].get().strip() or None,
                         "treatment": vars_["treatment"].get().strip() or None,
                         "treated_by": vars_["treated_by"].get().strip() or None,
                         "parent_notified": vars_["parent_notified"].get(),
                         "sent_home": vars_["sent_home"].get()}
            dlg.destroy()
        row += 1
        ttk.Button(c, text="Log", command=save).grid(row=row, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            self._svc.log_incident(d["student_id"], d["description"], d["date"], d["time"],
                                   d["location"], d["treatment"], d["treated_by"],
                                   d["parent_notified"], d["sent_home"])
            self._load_incidents()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_delete_incident(self):
        sel = self._fa_tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this first aid record?"):
            self._svc.delete_incident(int(sel[0]))
            self._load_incidents()
