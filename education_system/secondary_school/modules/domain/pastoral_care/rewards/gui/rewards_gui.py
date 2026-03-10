"""Rewards & Merits GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.pastoral_care.rewards.services.rewards_service import (
    RewardsService, REWARD_TYPES, REWARD_CATEGORIES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class RewardsFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = RewardsService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Rewards & Merits", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=15, pady=10)

        # --- Awards tab ---
        awards_tab = tk.Frame(nb, bg=MAIN_BG)
        nb.add(awards_tab, text="Awards")
        toolbar = tk.Frame(awards_tab, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Give Award", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)
        tk.Label(toolbar, text="Type:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._type_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._type_var,
                     values=["All"] + list(REWARD_TYPES), state="readonly", width=14).pack(side="left")
        self._type_var.trace_add("write", lambda *_: self._load())

        tree_frame = tk.Frame(awards_tab)
        tree_frame.pack(fill="both", expand=True, pady=(0, 10))
        cols = ("student", "year", "type", "category", "points", "reason", "by", "date")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("student", "Student", 120), ("year", "Year", 40),
                           ("type", "Type", 90), ("category", "Category", 70),
                           ("points", "Pts", 35), ("reason", "Reason", 180),
                           ("by", "Awarded By", 90), ("date", "Date", 80)]:
            self._tree.heading(col, text=h)
            self._tree.column(col, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # --- Leaderboard tab ---
        lb_tab = tk.Frame(nb, bg=MAIN_BG)
        nb.add(lb_tab, text="Leaderboard")
        lb_toolbar = tk.Frame(lb_tab, bg=MAIN_BG, pady=8)
        lb_toolbar.pack(fill="x")
        ttk.Button(lb_toolbar, text="Refresh", command=self._load_leaderboard).pack(side="left", padx=4)
        tk.Label(lb_toolbar, text="Year:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._lb_year_var = tk.StringVar(value="All")
        ttk.Combobox(lb_toolbar, textvariable=self._lb_year_var,
                     values=["All", "7", "8", "9", "10", "11"], state="readonly", width=6).pack(side="left")
        self._lb_year_var.trace_add("write", lambda *_: self._load_leaderboard())

        lb_frame = tk.Frame(lb_tab)
        lb_frame.pack(fill="both", expand=True, pady=(0, 10))
        lb_cols = ("rank", "student", "year", "points")
        self._lb_tree = ttk.Treeview(lb_frame, columns=lb_cols, show="headings", selectmode="browse")
        for col, h, w in [("rank", "#", 30), ("student", "Student", 180),
                           ("year", "Year", 50), ("points", "Total Points", 80)]:
            self._lb_tree.heading(col, text=h)
            self._lb_tree.column(col, width=w, anchor="center")
        self._lb_tree.pack(fill="both", expand=True)

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load()

    def _load(self):
        self._tree.delete(*self._tree.get_children())
        rtype = self._type_var.get()
        try:
            records = self._svc.list_rewards(
                reward_type=rtype if rtype != "All" else None)
            for r in records:
                self._tree.insert("", "end", iid=r["id"], values=(
                    f"{r['first_name']} {r['last_name']}", r.get("year_group") or "",
                    r["reward_type"], r["category"], r["points"],
                    r["reason"], r.get("awarded_by") or "", r["awarded_date"]))
            self._status_var.set(f"{len(records)} award(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_leaderboard(self):
        self._lb_tree.delete(*self._lb_tree.get_children())
        year = self._lb_year_var.get()
        try:
            rows = self._svc.leaderboard(year_group=year if year != "All" else None)
            for i, r in enumerate(rows, 1):
                self._lb_tree.insert("", "end", values=(
                    i, f"{r['first_name']} {r['last_name']}", r.get("year_group") or "",
                    r["total_points"]))
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
        students = StudentService(self._db_path).list_students(status="active")
        if not students:
            messagebox.showinfo("Info", "No active students.")
            return
        dlg = tk.Toplevel(self)
        dlg.title("Give Award")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        stu_var = tk.StringVar()
        tk.Label(c, text="Student", font=("Helvetica", 9, "bold")).grid(row=0, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=stu_var, values=stu_names, state="readonly", width=28).grid(row=0, column=1, **pad)
        type_var = tk.StringVar(value="merit")
        tk.Label(c, text="Type", font=("Helvetica", 9, "bold")).grid(row=1, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=type_var, values=list(REWARD_TYPES), state="readonly", width=18).grid(row=1, column=1, **pad)
        cat_var = tk.StringVar(value="general")
        tk.Label(c, text="Category", font=("Helvetica", 9, "bold")).grid(row=2, column=0, sticky="w", **pad)
        ttk.Combobox(c, textvariable=cat_var, values=list(REWARD_CATEGORIES), state="readonly", width=18).grid(row=2, column=1, **pad)
        pts_var = tk.StringVar(value="1")
        tk.Label(c, text="Points", font=("Helvetica", 9, "bold")).grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=pts_var, width=6).grid(row=3, column=1, sticky="w", **pad)
        reason_var = tk.StringVar()
        tk.Label(c, text="Reason", font=("Helvetica", 9, "bold")).grid(row=4, column=0, sticky="w", **pad)
        ttk.Entry(c, textvariable=reason_var, width=30).grid(row=4, column=1, **pad)
        result = [None]

        def save():
            sv = stu_var.get()
            r = reason_var.get().strip()
            if not sv or not r:
                messagebox.showwarning("Validation", "Student and reason required.")
                return
            sid_str = sv.split(" - ")[0]
            sid = next((s["id"] for s in students if s["student_id"] == sid_str), None)
            try:
                pts = int(pts_var.get())
            except ValueError:
                pts = 1
            result[0] = {"student_id": sid, "type": type_var.get(), "category": cat_var.get(),
                         "points": pts, "reason": r}
            dlg.destroy()

        ttk.Button(c, text="Award", command=save).grid(row=5, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        user = self._auth.get("username", "") if self._auth else ""
        try:
            self._svc.award(d["student_id"], d["reason"], d["type"], d["category"],
                            d["points"], awarded_by=user)
            self._load()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this award?"):
            self._svc.delete_reward(int(sel[0]))
            self._load()
