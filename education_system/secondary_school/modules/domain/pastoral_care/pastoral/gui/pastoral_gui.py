"""Pastoral Care GUI."""

import tkinter as tk
from tkinter import ttk, messagebox
from education_system.secondary_school.modules.domain.pastoral_care.pastoral.services.pastoral_service import (
    PastoralService, NOTE_TYPES,
)

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class PastoralFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = PastoralService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Pastoral Care", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=15, pady=10)

        # --- Notes tab ---
        notes_tab = tk.Frame(nb, bg=MAIN_BG)
        nb.add(notes_tab, text="Pastoral Notes")
        toolbar = tk.Frame(notes_tab, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=10)
        ttk.Button(toolbar, text="Add Note", command=self._on_add_note).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Mark Follow-Up Done", command=self._on_follow_up).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete_note).pack(side="left", padx=4)
        tk.Label(toolbar, text="Type:", bg=MAIN_BG).pack(side="left", padx=(15, 4))
        self._type_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._type_var,
                     values=["All"] + list(NOTE_TYPES), state="readonly", width=12).pack(side="left", padx=4)
        self._type_var.trace_add("write", lambda *_: self._load_notes())

        tree_frame = tk.Frame(notes_tab)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        cols = ("student", "year", "form", "type", "content", "by", "follow_up", "date")
        self._notes_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("student", "Student", 120), ("year", "Year", 40), ("form", "Form", 50),
                           ("type", "Type", 70), ("content", "Content", 200), ("by", "By", 80),
                           ("follow_up", "Follow-Up", 80), ("date", "Date", 110)]:
            self._notes_tree.heading(col, text=h)
            self._notes_tree.column(col, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._notes_tree.yview)
        self._notes_tree.configure(yscrollcommand=vsb.set)
        self._notes_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # --- House Points tab ---
        hp_tab = tk.Frame(nb, bg=MAIN_BG)
        nb.add(hp_tab, text="House Points")
        hp_toolbar = tk.Frame(hp_tab, bg=MAIN_BG, pady=8)
        hp_toolbar.pack(fill="x", padx=10)
        ttk.Button(hp_toolbar, text="Award Points", command=self._on_award_hp).pack(side="left", padx=4)

        self._hp_summary_frame = tk.Frame(hp_tab, bg=MAIN_BG)
        self._hp_summary_frame.pack(fill="x", padx=10, pady=5)

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load_notes()
        self._load_hp_summary()

    def _load_notes(self):
        self._notes_tree.delete(*self._notes_tree.get_children())
        t = self._type_var.get()
        try:
            notes = self._svc.list_notes(note_type=t if t != "All" else None)
            for n in notes:
                fu = ""
                if n.get("follow_up_date"):
                    fu = n["follow_up_date"]
                    if n["follow_up_done"]:
                        fu += " (done)"
                content_preview = (n["content"][:60] + "...") if len(n["content"]) > 60 else n["content"]
                self._notes_tree.insert("", "end", iid=n["id"], values=(
                    f"{n['first_name']} {n['last_name']}", n.get("year_group") or "",
                    n.get("form_group") or "", n["note_type"], content_preview,
                    n.get("recorded_by") or "", fu,
                    n["created_at"][:16] if n.get("created_at") else ""))
            self._status_var.set(f"{len(notes)} note(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _load_hp_summary(self):
        for w in self._hp_summary_frame.winfo_children():
            w.destroy()
        try:
            summary = self._svc.house_points_summary()
            if not summary:
                tk.Label(self._hp_summary_frame, text="No house points awarded yet.",
                         bg=MAIN_BG, font=("Helvetica", 10)).pack(anchor="w")
                return
            for s in summary:
                tk.Label(self._hp_summary_frame,
                         text=f"  {s['house']}: {s['total']} pts",
                         bg=MAIN_BG, font=("Helvetica", 11, "bold")).pack(anchor="w", pady=2)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add_note(self):
        from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
        students = StudentService(self._db_path).list_students(status="active")
        if not students:
            messagebox.showinfo("Info", "No active students.")
            return
        dlg = tk.Toplevel(self)
        dlg.title("Add Pastoral Note")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 4}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        row = 0
        tk.Label(c, text="Student", font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        stu_var = tk.StringVar()
        ttk.Combobox(c, textvariable=stu_var, values=stu_names, state="readonly", width=28).grid(row=row, column=1, **pad)
        row += 1
        tk.Label(c, text="Type", font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        type_var = tk.StringVar(value="general")
        ttk.Combobox(c, textvariable=type_var, values=list(NOTE_TYPES), state="readonly", width=28).grid(row=row, column=1, **pad)
        row += 1
        tk.Label(c, text="Follow-Up Date", font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        fu_var = tk.StringVar()
        ttk.Entry(c, textvariable=fu_var, width=30).grid(row=row, column=1, **pad)
        row += 1
        conf_var = tk.BooleanVar()
        ttk.Checkbutton(c, text="Confidential", variable=conf_var).grid(row=row, column=1, sticky="w", **pad)
        row += 1
        tk.Label(c, text="Content", font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="nw", **pad)
        content_text = tk.Text(c, width=35, height=6, wrap="word", font=("Helvetica", 10))
        content_text.grid(row=row, column=1, **pad)
        result = [None]

        def save():
            sv = stu_var.get()
            ct = content_text.get("1.0", "end").strip()
            if not sv or not ct:
                messagebox.showwarning("Validation", "Student and content required.")
                return
            sid_str = sv.split(" - ")[0]
            spk = next((s["id"] for s in students if s["student_id"] == sid_str), None)
            result[0] = {"student_id": spk, "content": ct, "note_type": type_var.get(),
                         "confidential": conf_var.get(), "follow_up": fu_var.get().strip() or None}
            dlg.destroy()
        row += 1
        ttk.Button(c, text="Save", command=save).grid(row=row, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        recorded_by = self._auth.get("username") if self._auth else None
        try:
            self._svc.add_note(d["student_id"], d["content"], d["note_type"],
                               recorded_by, d["confidential"], d["follow_up"])
            self._load_notes()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_follow_up(self):
        sel = self._notes_tree.selection()
        if not sel:
            return
        self._svc.mark_follow_up_done(int(sel[0]))
        self._load_notes()

    def _on_delete_note(self):
        sel = self._notes_tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this pastoral note?"):
            self._svc.delete_note(int(sel[0]))
            self._load_notes()

    def _on_award_hp(self):
        from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
        students = StudentService(self._db_path).list_students(status="active")
        if not students:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Award House Points")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        stu_names = [f"{s['student_id']} - {s['first_name']} {s['last_name']}" for s in students]
        row = 0
        tk.Label(c, text="Student", font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        stu_var = tk.StringVar()
        ttk.Combobox(c, textvariable=stu_var, values=stu_names, state="readonly", width=28).grid(row=row, column=1, **pad)
        for rr, (l, k, d) in enumerate([("House", "house", ""), ("Points", "points", "1"), ("Reason", "reason", "")], start=1):
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=rr, column=0, sticky="w", **pad)
        house_var = tk.StringVar()
        ttk.Entry(c, textvariable=house_var, width=20).grid(row=1, column=1, **pad)
        pts_var = tk.StringVar(value="1")
        ttk.Entry(c, textvariable=pts_var, width=20).grid(row=2, column=1, **pad)
        reason_var = tk.StringVar()
        ttk.Entry(c, textvariable=reason_var, width=20).grid(row=3, column=1, **pad)
        result = [None]

        def save():
            sv = stu_var.get()
            h = house_var.get().strip()
            if not sv or not h:
                messagebox.showwarning("Validation", "Student and house required.")
                return
            sid_str = sv.split(" - ")[0]
            spk = next((s["id"] for s in students if s["student_id"] == sid_str), None)
            try:
                pts = int(pts_var.get().strip())
            except ValueError:
                pts = 1
            result[0] = {"student_id": spk, "house": h, "points": pts,
                         "reason": reason_var.get().strip() or None}
            dlg.destroy()
        ttk.Button(c, text="Award", command=save).grid(row=4, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        awarded_by = self._auth.get("username") if self._auth else None
        try:
            self._svc.award_house_points(d["student_id"], d["house"], d["points"], d["reason"], awarded_by)
            self._load_hp_summary()
        except Exception as e:
            messagebox.showerror("Error", str(e))
