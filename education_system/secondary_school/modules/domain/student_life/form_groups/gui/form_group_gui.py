"""Form Groups / Tutor Groups GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.student_life.form_groups.services.form_group_service import (
    FormGroupService, YEAR_GROUPS,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class FormGroupFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = FormGroupService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Form Groups", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="New Group", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View Students", command=self._on_view_students).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Add Student", command=self._on_add_student).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete Group", command=self._on_delete).pack(side="left", padx=4)
        tk.Label(toolbar, text="Year:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._year_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._year_var,
                     values=["All"] + list(YEAR_GROUPS), state="readonly", width=6).pack(side="left")
        self._year_var.trace_add("write", lambda *_: self._load())

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("name", "year", "tutor", "room", "students", "max", "reg_time")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("name", "Form Group", 100), ("year", "Year", 40),
                           ("tutor", "Form Tutor", 120), ("room", "Room", 60),
                           ("students", "Students", 55), ("max", "Max", 35),
                           ("reg_time", "Reg Time", 60)]:
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
        year = self._year_var.get()
        try:
            groups = self._svc.list_groups(year_group=year if year != "All" else None)
            for g in groups:
                cnt = self._svc.student_count(g["id"])
                self._tree.insert("", "end", iid=g["id"], values=(
                    g["name"], g["year_group"], g.get("form_tutor") or "",
                    g.get("room") or "", cnt, g.get("max_students") or "",
                    g.get("registration_time") or ""))
            self._status_var.set(f"{len(groups)} form group(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Form Group")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        fields = [("Group Name", "name", "", None), ("Year Group", "year", "7", list(YEAR_GROUPS)),
                  ("Form Tutor", "tutor", "", None), ("Room", "room", "", None),
                  ("Max Students", "max", "30", None), ("Reg Time", "time", "08:40", None)]
        for row, (l, k, d, vals) in enumerate(fields):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            if vals:
                ttk.Combobox(c, textvariable=vars_[k], values=vals, state="readonly", width=8).grid(row=row, column=1, sticky="w", **pad)
            else:
                ttk.Entry(c, textvariable=vars_[k], width=20).grid(row=row, column=1, **pad)
        result = [None]

        def save():
            n = vars_["name"].get().strip()
            if not n:
                messagebox.showwarning("Validation", "Group name required.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()

        ttk.Button(c, text="Create", command=save).grid(row=len(fields), column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            mx = int(d["max"]) if d["max"] else 30
        except ValueError:
            mx = 30
        try:
            self._svc.create_group(d["name"], d["year"], d.get("tutor") or None,
                                   d.get("room") or None, mx, d.get("time") or "08:40")
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_view_students(self):
        sel = self._tree.selection()
        if not sel:
            return
        students = self._svc.list_students(int(sel[0]))
        dlg = tk.Toplevel(self)
        dlg.title(f"Students ({len(students)})")
        dlg.geometry("400x300")
        cols = ("student", "code", "year")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        for col, h, w in [("student", "Student", 160), ("code", "ID", 80), ("year", "Year", 50)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        for s in students:
            tree.insert("", "end", values=(
                f"{s['first_name']} {s['last_name']}", s.get("stu_code") or "", s.get("year_group") or ""))
        tree.pack(fill="both", expand=True, padx=10, pady=10)

    def _on_add_student(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a form group first.")
            return
        group_id = int(sel[0])
        from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
        students = StudentService(self._db_path).list_students(status="active")
        if not students:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Add Student to Form Group")
        dlg.resizable(False, False)
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        stu_var = tk.StringVar()
        tk.Label(c, text="Student", font=("Helvetica", 9, "bold")).pack(anchor="w")
        ttk.Combobox(c, textvariable=stu_var, values=stu_names, state="readonly", width=28).pack(pady=5)
        result = [None]

        def save():
            sv = stu_var.get()
            if not sv:
                return
            sid_str = sv.split(" - ")[0]
            result[0] = next((s["id"] for s in students if s["student_id"] == sid_str), None)
            dlg.destroy()

        ttk.Button(c, text="Add", command=save).pack(pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        try:
            self._svc.add_student(group_id, result[0])
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this form group and all student assignments?"):
            self._svc.delete_group(int(sel[0]))
            self._load()
