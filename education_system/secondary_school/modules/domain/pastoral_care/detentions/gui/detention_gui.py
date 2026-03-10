"""Detention Management GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.pastoral_care.detentions.services.detention_service import (
    DetentionService, DETENTION_TYPES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class DetentionFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = DetentionService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Detentions", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Schedule Detention", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Mark Attended", command=self._on_attended).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Mark Missed", command=self._on_missed).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)

        tk.Label(toolbar, text="Status:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._filter_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._filter_var,
                     values=["All", "scheduled", "completed", "missed"], state="readonly", width=12).pack(side="left")
        self._filter_var.trace_add("write", lambda *_: self._load())

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("student", "year", "type", "date", "time", "room", "supervisor", "reason", "attended", "status")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("student", "Student", 120), ("year", "Yr", 30), ("type", "Type", 85),
                           ("date", "Date", 80), ("time", "Time", 80), ("room", "Room", 55),
                           ("supervisor", "Supervisor", 80), ("reason", "Reason", 140),
                           ("attended", "Attended", 55), ("status", "Status", 65)]:
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
        f = self._filter_var.get()
        try:
            dets = self._svc.list_detentions(status=f if f != "All" else None)
            for d in dets:
                time_str = d.get("start_time") or ""
                if d.get("end_time"):
                    time_str += f"-{d['end_time']}"
                att = ""
                if d["attended"] is not None:
                    att = "Yes" if d["attended"] else "No"
                reason = (d["reason"][:30] + "...") if len(d["reason"]) > 30 else d["reason"]
                self._tree.insert("", "end", iid=d["id"], values=(
                    f"{d['first_name']} {d['last_name']}", d.get("year_group") or "",
                    d["detention_type"], d["date"], time_str, d.get("room") or "",
                    d.get("supervisor") or "", reason, att, d["status"]))
            self._status_var.set(f"{len(dets)} detention(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
        students = StudentService(self._db_path).list_students(status="active")
        if not students:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Schedule Detention")
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
            ("Type", "type", "lunchtime", list(DETENTION_TYPES)),
            ("Date (YYYY-MM-DD)", "date", "", None),
            ("Start Time", "start_time", "", None), ("End Time", "end_time", "", None),
            ("Room", "room", "", None), ("Supervisor", "supervisor", "", None),
            ("Reason", "reason", "", None)], start=1):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=rr, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            if vals:
                ttk.Combobox(c, textvariable=vars_[k], values=vals, state="readonly", width=20).grid(row=rr, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[k], width=22).grid(row=rr, column=1, **pad)
        result = [None]
        def save():
            sv = vars_["student"].get()
            dt = vars_["date"].get().strip()
            rs = vars_["reason"].get().strip()
            if not sv or not dt or not rs:
                messagebox.showwarning("Validation", "Student, date and reason required.")
                return
            sid_str = sv.split(" - ")[0]
            spk = next((s["id"] for s in students if s["student_id"] == sid_str), None)
            result[0] = {"student_id": spk, "date": dt, "reason": rs}
            for k in ("type", "start_time", "end_time", "room", "supervisor"):
                result[0][k] = vars_[k].get().strip() or None
            dlg.destroy()
        ttk.Button(c, text="Schedule", command=save).grid(row=8, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            self._svc.create_detention(d["student_id"], d["reason"], d["date"],
                                       d.get("type") or "lunchtime", d.get("start_time"),
                                       d.get("end_time"), d.get("room"), d.get("supervisor"))
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_attended(self):
        sel = self._tree.selection()
        if not sel:
            return
        self._svc.mark_attended(int(sel[0]))
        self._load()

    def _on_missed(self):
        sel = self._tree.selection()
        if not sel:
            return
        self._svc.mark_missed(int(sel[0]))
        self._load()

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this detention?"):
            self._svc.delete_detention(int(sel[0]))
            self._load()
