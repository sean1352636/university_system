"""Behaviour management GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from education_system.secondary_school.modules.domain.pastoral_care.behaviour.services.behaviour_service import BehaviourService
from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
from education_system.secondary_school.infrastructure.database.constants import (
    BEHAVIOUR_CATEGORIES, BEHAVIOUR_TYPES, SANCTION_LEVELS,
)
from education_system.secondary_school.core.exceptions import BehaviourError


class _BehaviourDialog(tk.Toplevel):
    def __init__(self, parent, students):
        super().__init__(parent)
        self.title("Record Behaviour")
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self._students = students
        self._build_ui()
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        self.geometry(f"+{px - self.winfo_width() // 2}+{py - self.winfo_height() // 2}")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(self, padx=20, pady=15)
        c.pack(fill="both", expand=True)

        row = 0
        tk.Label(c, text="Student", anchor="w", font=("Helvetica", 9, "bold")).grid(
            row=row, column=0, sticky="w", **pad)
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in self._students]
        self._stu_var = tk.StringVar()
        ttk.Combobox(c, textvariable=self._stu_var, values=stu_names,
                     state="readonly", width=33).grid(row=row, column=1, sticky="ew", **pad)

        row += 1
        tk.Label(c, text="Type", anchor="w", font=("Helvetica", 9, "bold")).grid(
            row=row, column=0, sticky="w", **pad)
        self._type_var = tk.StringVar(value="positive")
        ttk.Combobox(c, textvariable=self._type_var, values=list(BEHAVIOUR_TYPES),
                     state="readonly", width=33).grid(row=row, column=1, sticky="ew", **pad)

        row += 1
        tk.Label(c, text="Category", anchor="w", font=("Helvetica", 9, "bold")).grid(
            row=row, column=0, sticky="w", **pad)
        self._cat_var = tk.StringVar(value="achievement")
        ttk.Combobox(c, textvariable=self._cat_var, values=list(BEHAVIOUR_CATEGORIES),
                     state="readonly", width=33).grid(row=row, column=1, sticky="ew", **pad)

        row += 1
        tk.Label(c, text="Points", anchor="w", font=("Helvetica", 9, "bold")).grid(
            row=row, column=0, sticky="w", **pad)
        self._points_var = tk.StringVar(value="1")
        ttk.Entry(c, textvariable=self._points_var, width=36).grid(
            row=row, column=1, sticky="ew", **pad)

        row += 1
        tk.Label(c, text="Description", anchor="w", font=("Helvetica", 9, "bold")).grid(
            row=row, column=0, sticky="w", **pad)
        self._desc_var = tk.StringVar()
        ttk.Entry(c, textvariable=self._desc_var, width=36).grid(
            row=row, column=1, sticky="ew", **pad)

        row += 1
        tk.Label(c, text="Sanction (if negative)", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        self._sanction_var = tk.StringVar()
        ttk.Combobox(c, textvariable=self._sanction_var,
                     values=[""] + list(SANCTION_LEVELS), width=33).grid(
            row=row, column=1, sticky="ew", **pad)

        btn = tk.Frame(c)
        btn.grid(row=row + 1, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn, text="Save", command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn, text="Cancel", command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        stu_val = self._stu_var.get()
        if not stu_val:
            messagebox.showwarning("Validation", "Select a student.")
            return

        stu_sid = stu_val.split(" - ")[0]
        student_pk = None
        for s in self._students:
            if s["student_id"] == stu_sid:
                student_pk = s["id"]
                break

        try:
            points = int(self._points_var.get())
        except ValueError:
            points = 1

        self.result = {
            "student_id": student_pk,
            "type": self._type_var.get(),
            "category": self._cat_var.get(),
            "points": points,
            "description": self._desc_var.get().strip() or None,
            "sanction": self._sanction_var.get().strip() or None,
        }
        self.destroy()


class BehaviourFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = BehaviourService(db_path)
        self._stu_svc = StudentService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        header = tk.Frame(self, bg="#1a5276", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Behaviour Management", font=("Helvetica", 15, "bold"),
                 bg="#1a5276", fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self, bg="#ecf0f1", pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Record Behaviour", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Mark Resolved", command=self._on_resolve).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Notify Parent", command=self._on_notify_parent).pack(side="left", padx=4)

        tk.Label(toolbar, text="Show:", bg="#ecf0f1").pack(side="left", padx=(20, 4))
        self._filter_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._filter_var,
                     values=["All", "positive", "negative"],
                     state="readonly", width=10).pack(side="left", padx=4)
        self._filter_var.trace_add("write", lambda *_: self._load_records())

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columns = ("date", "student", "type", "category", "points", "description", "sanction", "resolved")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        for col, heading, w in [
            ("date", "Date", 80), ("student", "Student", 140),
            ("type", "Type", 70), ("category", "Category", 100),
            ("points", "Pts", 40), ("description", "Description", 180),
            ("sanction", "Sanction", 100), ("resolved", "Resolved", 60),
        ]:
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=w, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load_records()

    def _load_records(self):
        self._tree.delete(*self._tree.get_children())
        try:
            from education_system.secondary_school.infrastructure.database.db import connect
            conn = connect(self._db_path)
            filt = self._filter_var.get()
            sql = """SELECT b.*, s.student_id as sid, s.first_name, s.last_name
                     FROM behaviour_records b JOIN students s ON b.student_id = s.id
                     WHERE 1=1"""
            params = []
            if filt != "All":
                sql += " AND b.type = ?"
                params.append(filt)
            sql += " ORDER BY b.incident_date DESC LIMIT 500"

            rows = conn.execute(sql, params).fetchall()
            for row in rows:
                r = dict(row)
                self._tree.insert("", "end", iid=r["id"], values=(
                    r["incident_date"],
                    f"{r['first_name']} {r['last_name']}",
                    r["type"], r["category"], r["points"],
                    r.get("description", "") or "",
                    r.get("sanction", "") or "",
                    "Yes" if r["resolved"] else "No",
                ))
            self._status_var.set(f"{len(rows)} record(s) loaded")
            conn.close()
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_add(self):
        students = self._stu_svc.list_students(status="active")
        if not students:
            messagebox.showwarning("Warning", "No active students found.")
            return

        dlg = _BehaviourDialog(self, students)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        d = dlg.result
        recorded_by = self._auth["username"] if self._auth else "system"
        try:
            self._svc.add_record(
                student_id=d["student_id"],
                record_type=d["type"],
                category=d["category"],
                description=d.get("description"),
                points=d["points"],
                sanction=d.get("sanction"),
                recorded_by=recorded_by,
            )
            messagebox.showinfo("Success", "Behaviour record added.")
            self._load_records()
        except BehaviourError as exc:
            messagebox.showerror("Error", str(exc))

    def _on_resolve(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a record first.")
            return
        self._svc.resolve_record(int(sel[0]))
        self._load_records()

    def _on_notify_parent(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a record first.")
            return
        self._svc.mark_parent_notified(int(sel[0]))
        messagebox.showinfo("Notified", "Parent notification recorded.")
        self._load_records()
