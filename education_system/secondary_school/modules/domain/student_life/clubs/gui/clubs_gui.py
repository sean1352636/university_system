"""Clubs & Extracurricular GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.student_life.clubs.services.clubs_service import (
    ClubsService, CATEGORIES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")


class ClubsFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = ClubsService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Clubs & Extracurricular", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="New Club", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View Members", command=self._on_view_members).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Add Member", command=self._on_add_member).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete Club", command=self._on_delete).pack(side="left", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("name", "category", "day", "time", "location", "teacher", "members", "max")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("name", "Club", 140), ("category", "Category", 70), ("day", "Day", 75),
                           ("time", "Time", 90), ("location", "Location", 80),
                           ("teacher", "Teacher", 90), ("members", "Members", 55), ("max", "Max", 40)]:
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
            clubs = self._svc.list_clubs()
            for c in clubs:
                time_str = ""
                if c.get("start_time"):
                    time_str = c["start_time"]
                    if c.get("end_time"):
                        time_str += f"-{c['end_time']}"
                count = self._svc.member_count(c["id"])
                self._tree.insert("", "end", iid=c["id"], values=(
                    c["name"], c["category"], c.get("day_of_week") or "",
                    time_str, c.get("location") or "", c.get("teacher") or "",
                    count, c.get("max_members") or ""))
            self._status_var.set(f"{len(clubs)} club(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        dlg = tk.Toplevel(self)
        dlg.title("New Club")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        fields = [("Name", "name", "", None), ("Category", "category", "general", list(CATEGORIES)),
                  ("Day", "day", "", list(DAYS)), ("Start Time", "start_time", "", None),
                  ("End Time", "end_time", "", None), ("Location", "location", "", None),
                  ("Teacher", "teacher", "", None), ("Max Members", "max_members", "", None),
                  ("Year Groups", "year_groups", "", None)]
        for row, (l, k, d, vals) in enumerate(fields):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            if vals:
                ttk.Combobox(c, textvariable=vars_[k], values=vals, state="readonly", width=20).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[k], width=22).grid(row=row, column=1, **pad)
        result = [None]
        def save():
            n = vars_["name"].get().strip()
            if not n:
                messagebox.showwarning("Validation", "Name required.")
                return
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()
        ttk.Button(c, text="Create", command=save).grid(row=len(fields), column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        try:
            max_m = int(d["max_members"]) if d["max_members"] else None
        except ValueError:
            max_m = None
        try:
            self._svc.create_club(d["name"], d["category"] or "general", None,
                                  d["day"] or None, d["start_time"] or None,
                                  d["end_time"] or None, d["location"] or None,
                                  d["teacher"] or None, max_m, d["year_groups"] or None)
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_view_members(self):
        sel = self._tree.selection()
        if not sel:
            return
        members = self._svc.list_members(int(sel[0]))
        dlg = tk.Toplevel(self)
        dlg.title(f"Members ({len(members)})")
        dlg.geometry("400x300")
        cols = ("student", "year", "joined")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        for col, h, w in [("student", "Student", 160), ("year", "Year", 50), ("joined", "Joined", 120)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        for m in members:
            tree.insert("", "end", values=(
                f"{m['first_name']} {m['last_name']}", m.get("year_group") or "",
                m["joined_at"][:10] if m.get("joined_at") else ""))
        tree.pack(fill="both", expand=True, padx=10, pady=10)

    def _on_add_member(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a club first.")
            return
        club_id = int(sel[0])
        from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
        students = StudentService(self._db_path).list_students(status="active")
        if not students:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Add Member")
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
            self._svc.add_member(club_id, result[0])
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this club and all members?"):
            self._svc.delete_club(int(sel[0]))
            self._load()
