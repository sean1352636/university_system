"""Careers & Work Experience GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.student_life.careers.services.careers_service import (
    CareersService, WE_STATUSES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class CareersFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = CareersService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Careers & Work Experience", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=15, pady=10)

        # --- Meetings tab ---
        mtab = tk.Frame(nb, bg=MAIN_BG)
        nb.add(mtab, text="Careers Meetings")
        toolbar = tk.Frame(mtab, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Add Meeting", command=self._on_add_meeting).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete_meeting).pack(side="left", padx=4)

        tree_frame = tk.Frame(mtab)
        tree_frame.pack(fill="both", expand=True, pady=(0, 10))
        cols = ("student", "year", "date", "adviser", "interests", "destination")
        self._mtree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("student", "Student", 130), ("year", "Year", 40),
                           ("date", "Date", 80), ("adviser", "Adviser", 100),
                           ("interests", "Career Interests", 180), ("destination", "Destination", 100)]:
            self._mtree.heading(col, text=h)
            self._mtree.column(col, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._mtree.yview)
        self._mtree.configure(yscrollcommand=vsb.set)
        self._mtree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # --- Work Experience tab ---
        wtab = tk.Frame(nb, bg=MAIN_BG)
        nb.add(wtab, text="Work Experience")
        wtoolbar = tk.Frame(wtab, bg=MAIN_BG, pady=8)
        wtoolbar.pack(fill="x")
        ttk.Button(wtoolbar, text="Add Placement", command=self._on_add_placement).pack(side="left", padx=4)
        ttk.Button(wtoolbar, text="Update Status", command=self._on_update_we_status).pack(side="left", padx=4)
        ttk.Button(wtoolbar, text="Delete", command=self._on_delete_placement).pack(side="left", padx=4)

        wf = tk.Frame(wtab)
        wf.pack(fill="both", expand=True, pady=(0, 10))
        wcols = ("student", "year", "employer", "role", "dates", "risk", "consent", "insurance", "status")
        self._wtree = ttk.Treeview(wf, columns=wcols, show="headings", selectmode="browse")
        for col, h, w in [("student", "Student", 120), ("year", "Year", 35),
                           ("employer", "Employer", 120), ("role", "Role", 90),
                           ("dates", "Dates", 120), ("risk", "Risk", 35),
                           ("consent", "Consent", 45), ("insurance", "Ins", 30),
                           ("status", "Status", 70)]:
            self._wtree.heading(col, text=h)
            self._wtree.column(col, width=w, anchor="center")
        wvsb = ttk.Scrollbar(wf, orient="vertical", command=self._wtree.yview)
        self._wtree.configure(yscrollcommand=wvsb.set)
        self._wtree.pack(side="left", fill="both", expand=True)
        wvsb.pack(side="right", fill="y")

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load_meetings()
        self._load_placements()

    def _load_meetings(self):
        self._mtree.delete(*self._mtree.get_children())
        try:
            records = self._svc.list_meetings()
            for r in records:
                self._mtree.insert("", "end", iid=r["id"], values=(
                    f"{r['first_name']} {r['last_name']}", r.get("year_group") or "",
                    r["meeting_date"], r.get("adviser") or "",
                    r.get("career_interests") or "", r.get("destination") or ""))
            self._status_var.set(f"{len(records)} meeting(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_placements(self):
        self._wtree.delete(*self._wtree.get_children())
        try:
            records = self._svc.list_placements()
            for r in records:
                self._wtree.insert("", "end", iid=r["id"], values=(
                    f"{r['first_name']} {r['last_name']}", r.get("year_group") or "",
                    r["employer"], r.get("role") or "",
                    f"{r['start_date']} – {r['end_date']}",
                    "Yes" if r["risk_assessment_done"] else "",
                    "Yes" if r["parent_consent"] else "",
                    "Yes" if r["insurance_confirmed"] else "",
                    r["status"]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _get_students(self):
        from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
        return StudentService(self._db_path).list_students(status="active")

    def _on_add_meeting(self):
        students = self._get_students()
        if not students:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Add Careers Meeting")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        vars_ = {}
        fields = [("Student", "stu", "", stu_names), ("Date (YYYY-MM-DD)", "date", "", None),
                  ("Adviser", "adviser", "", None), ("Career Interests", "interests", "", None),
                  ("Action Points", "actions", "", None), ("Destination", "dest", "", None)]
        for row, (l, k, d, vals) in enumerate(fields):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            if vals:
                ttk.Combobox(c, textvariable=vars_[k], values=vals, state="readonly", width=28).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[k], width=30).grid(row=row, column=1, **pad)
        result = [None]

        def save():
            sv = vars_["stu"].get()
            dt = vars_["date"].get().strip()
            if not sv or not dt:
                messagebox.showwarning("Validation", "Student and date required.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()

        ttk.Button(c, text="Save", command=save).grid(row=len(fields), column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        sid_str = d["stu"].split(" - ")[0]
        sid = next((s["id"] for s in students if s["student_id"] == sid_str), None)
        try:
            self._svc.add_meeting(sid, d["date"], d.get("adviser") or None,
                                  d.get("interests") or None, d.get("actions") or None,
                                  d.get("dest") or None)
            self._load_meetings()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_delete_meeting(self):
        sel = self._mtree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this meeting record?"):
            self._svc.delete_meeting(int(sel[0]))
            self._load_meetings()

    def _on_add_placement(self):
        students = self._get_students()
        if not students:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Add Work Experience Placement")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        vars_ = {}
        fields = [("Student", "stu", "", stu_names), ("Employer", "employer", "", None),
                  ("Role", "role", "", None), ("Start Date", "start", "", None),
                  ("End Date", "end", "", None), ("Contact Name", "cname", "", None),
                  ("Contact Phone", "cphone", "", None)]
        for row, (l, k, d, vals) in enumerate(fields):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            if vals:
                ttk.Combobox(c, textvariable=vars_[k], values=vals, state="readonly", width=28).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[k], width=25).grid(row=row, column=1, **pad)
        result = [None]

        def save():
            sv = vars_["stu"].get()
            emp = vars_["employer"].get().strip()
            sd = vars_["start"].get().strip()
            ed = vars_["end"].get().strip()
            if not sv or not emp or not sd or not ed:
                messagebox.showwarning("Validation", "Student, employer, and dates required.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()

        ttk.Button(c, text="Save", command=save).grid(row=len(fields), column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        sid_str = d["stu"].split(" - ")[0]
        sid = next((s["id"] for s in students if s["student_id"] == sid_str), None)
        try:
            self._svc.add_placement(sid, d["employer"], d["start"], d["end"],
                                    d.get("role") or None, d.get("cname") or None,
                                    d.get("cphone") or None)
            self._load_placements()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_update_we_status(self):
        sel = self._wtree.selection()
        if not sel:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Update Status")
        dlg.resizable(False, False)
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        var = tk.StringVar()
        tk.Label(c, text="New Status", font=("Helvetica", 9, "bold")).pack(anchor="w")
        ttk.Combobox(c, textvariable=var, values=list(WE_STATUSES), state="readonly", width=15).pack(pady=5)
        result = [None]

        def save():
            if var.get():
                result[0] = var.get()
            dlg.destroy()

        ttk.Button(c, text="Update", command=save).pack(pady=10)
        self.wait_window(dlg)
        if result[0]:
            self._svc.update_placement_status(int(sel[0]), result[0])
            self._load_placements()

    def _on_delete_placement(self):
        sel = self._wtree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this placement?"):
            self._svc.delete_placement(int(sel[0]))
            self._load_placements()
