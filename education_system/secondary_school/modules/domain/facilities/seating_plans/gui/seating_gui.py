"""Seating Plans GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.facilities.seating_plans.services.seating_service import SeatingService

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class SeatingFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = SeatingService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Seating Plans", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="New Plan", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View Seats", command=self._on_view_seats).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Assign Seat", command=self._on_assign).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete Plan", command=self._on_delete).pack(side="left", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("name", "room", "year", "teacher", "grid", "assigned")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("name", "Plan Name", 140), ("room", "Room", 70),
                           ("year", "Year", 40), ("teacher", "Teacher", 110),
                           ("grid", "Grid", 60), ("assigned", "Assigned", 55)]:
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
            plans = self._svc.list_plans()
            for p in plans:
                cnt = self._svc.seat_count(p["id"])
                self._tree.insert("", "end", iid=p["id"], values=(
                    p["name"], p["room"], p.get("year_group") or "",
                    p.get("teacher") or "", f"{p['rows']}x{p['columns']}", cnt))
            self._status_var.set(f"{len(plans)} plan(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Seating Plan")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        fields = [("Plan Name", "name", "", None), ("Room", "room", "", None),
                  ("Year Group", "year", "", ["7", "8", "9", "10", "11"]),
                  ("Teacher", "teacher", "", None),
                  ("Rows", "rows", "5", None), ("Columns", "cols", "6", None)]
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
            r = vars_["room"].get().strip()
            if not n or not r:
                messagebox.showwarning("Validation", "Name and room required.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()

        ttk.Button(c, text="Create", command=save).grid(row=len(fields), column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            rows = int(d["rows"]) if d["rows"] else 5
            cols = int(d["cols"]) if d["cols"] else 6
        except ValueError:
            rows, cols = 5, 6
        try:
            self._svc.create_plan(d["name"], d["room"], year_group=d.get("year") or None,
                                  teacher=d.get("teacher") or None, rows=rows, columns=cols)
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_view_seats(self):
        sel = self._tree.selection()
        if not sel:
            return
        assignments = self._svc.list_assignments(int(sel[0]))
        dlg = tk.Toplevel(self)
        dlg.title(f"Seating Assignments ({len(assignments)})")
        dlg.geometry("400x300")
        cols = ("student", "row", "col")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        for col, h, w in [("student", "Student", 180), ("row", "Row", 50), ("col", "Col", 50)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        for a in assignments:
            tree.insert("", "end", values=(
                f"{a['first_name']} {a['last_name']}", a["seat_row"] + 1, a["seat_col"] + 1))
        tree.pack(fill="both", expand=True, padx=10, pady=10)

    def _on_assign(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a plan first.")
            return
        plan_id = int(sel[0])
        from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
        students = StudentService(self._db_path).list_students(status="active")
        if not students:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Assign Seat")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        stu_var = tk.StringVar()
        row_var = tk.StringVar(value="1")
        col_var = tk.StringVar(value="1")
        tk.Label(c, text="Student", font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=stu_var, values=stu_names, state="readonly", width=28).grid(row=0, column=1, **pad)
        tk.Label(c, text="Row", font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=row_var, width=5).grid(row=1, column=1, sticky="w", **pad)
        tk.Label(c, text="Column", font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=col_var, width=5).grid(row=2, column=1, sticky="w", **pad)
        result = [None]

        def save():
            sv = stu_var.get()
            if not sv:
                return
            sid_str = sv.split(" - ")[0]
            sid = next((s["id"] for s in students if s["student_id"] == sid_str), None)
            try:
                r = int(row_var.get()) - 1
                co = int(col_var.get()) - 1
            except ValueError:
                r, co = 0, 0
            result[0] = {"sid": sid, "row": r, "col": co}
            dlg.destroy()

        ttk.Button(c, text="Assign", command=save).grid(row=3, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            self._svc.assign_seat(plan_id, d["sid"], d["row"], d["col"])
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this seating plan and all assignments?"):
            self._svc.delete_plan(int(sel[0]))
            self._load()
