"""Exam management GUI."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.secondary_school.modules.domain.academics.exams.services.exam_service import (
    ExamService, EXAM_TYPES, EXAM_STATUSES,
)
from education_system.secondary_school.modules.domain.academics.subjects.services.subject_service import SubjectService
from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
from education_system.secondary_school.core.exceptions import ExamError

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class ExamFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = ExamService(db_path)
        self._subj_svc = SubjectService(db_path)
        self._stu_svc = StudentService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)

        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Exam Management", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)

        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Schedule Exam", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Edit Exam", command=self._on_edit).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Cancel Exam", command=self._on_cancel).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Record Results", command=self._on_record_results).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View Results", command=self._on_view_results).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete Exam", command=self._on_delete).pack(side="left", padx=4)

        tk.Label(toolbar, text="Year:", bg=MAIN_BG).pack(side="left", padx=(20, 4))
        self._year_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._year_var,
                     values=["All", "7", "8", "9", "10", "11"],
                     state="readonly", width=5).pack(side="left", padx=4)
        self._year_var.trace_add("write", lambda *_: self._load_exams())

        tk.Label(toolbar, text="Status:", bg=MAIN_BG).pack(side="left", padx=(10, 4))
        self._status_var = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._status_var,
                     values=["All"] + list(EXAM_STATUSES),
                     state="readonly", width=10).pack(side="left", padx=4)
        self._status_var.trace_add("write", lambda *_: self._load_exams())

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columns = ("subject", "title", "type", "year", "date", "time", "duration", "room", "marks", "status")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")

        for col, heading, w in [
            ("subject", "Subject", 120), ("title", "Title", 150),
            ("type", "Type", 80), ("year", "Year", 40),
            ("date", "Date", 85), ("time", "Time", 55),
            ("duration", "Mins", 40), ("room", "Room", 60),
            ("marks", "Marks", 45), ("status", "Status", 75),
        ]:
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=w, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        self._status_label = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_label, bg=MAIN_BG, anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load_exams()

    def _load_exams(self):
        self._tree.delete(*self._tree.get_children())
        yg = self._year_var.get()
        st = self._status_var.get()
        try:
            exams = self._svc.list_exams(
                year_group=yg if yg != "All" else None,
                status=st if st != "All" else None,
            )
            for e in exams:
                self._tree.insert("", "end", iid=e["id"], values=(
                    e.get("subject_title", ""),
                    e["title"],
                    e["exam_type"],
                    e.get("year_group", "") or "",
                    e.get("date", "") or "",
                    e.get("start_time", "") or "",
                    e["duration_minutes"],
                    e.get("room", "") or "",
                    e["total_marks"],
                    e["status"],
                ))
            self._status_label.set(f"{len(exams)} exam(s)")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

    def _on_add(self):
        subjects = self._subj_svc.list_subjects(status="active")
        if not subjects:
            messagebox.showwarning("Warning", "No subjects available.")
            return

        dlg = tk.Toplevel(self)
        dlg.title("Schedule Exam")
        dlg.resizable(False, False)

        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()

        vars_ = {}
        row = 0

        tk.Label(c, text="Subject", font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        subj_names = [f"{s['subject_code']} - {s['title']}" for s in subjects]
        vars_["subject"] = tk.StringVar()
        ttk.Combobox(c, textvariable=vars_["subject"], values=subj_names,
                     state="readonly", width=30).grid(row=row, column=1, **pad)

        for label, key, default, values in [
            ("Title", "title", "", None),
            ("Type", "type", "end_of_term", list(EXAM_TYPES)),
            ("Year Group", "year_group", "7", ["7", "8", "9", "10", "11"]),
            ("Date (YYYY-MM-DD)", "date", "", None),
            ("Start Time (HH:MM)", "start_time", "09:00", None),
            ("Duration (mins)", "duration", "60", None),
            ("Room", "room", "", None),
            ("Invigilator", "invigilator", "", None),
            ("Total Marks", "total_marks", "100", None),
        ]:
            row += 1
            tk.Label(c, text=label, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[key] = tk.StringVar(value=default)
            if values:
                ttk.Combobox(c, textvariable=vars_[key], values=values,
                             state="readonly", width=30).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[key], width=32).grid(row=row, column=1, **pad)

        result = [None]

        def save():
            subj_val = vars_["subject"].get()
            title = vars_["title"].get().strip()
            if not subj_val or not title:
                messagebox.showwarning("Validation", "Select a subject and enter a title.")
                return
            code = subj_val.split(" - ")[0]
            subj_pk = None
            for s in subjects:
                if s["subject_code"] == code:
                    subj_pk = s["id"]
                    break
            result[0] = {"subject_id": subj_pk, "title": title}
            for k in ("type", "year_group", "date", "start_time", "duration", "room",
                       "invigilator", "total_marks"):
                result[0][k] = vars_[k].get().strip()
            dlg.destroy()

        row += 1
        btn = tk.Frame(c)
        btn.grid(row=row, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn, text="Save", command=save).pack(side="left", padx=5)
        ttk.Button(btn, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)

        self.wait_window(dlg)
        if result[0] is None:
            return

        d = result[0]
        try:
            dur = int(d["duration"]) if d["duration"] else 60
            marks = int(d["total_marks"]) if d["total_marks"] else 100
        except ValueError:
            dur, marks = 60, 100

        try:
            self._svc.create_exam(
                subject_id=d["subject_id"], title=d["title"],
                exam_type=d["type"] or "end_of_term",
                year_group=d["year_group"] or None,
                date=d["date"] or None,
                start_time=d["start_time"] or None,
                duration_minutes=dur, room=d["room"] or None,
                invigilator=d["invigilator"] or None,
                total_marks=marks,
            )
            messagebox.showinfo("Success", "Exam scheduled.")
            self._load_exams()
        except ExamError as exc:
            messagebox.showerror("Error", str(exc))

    def _on_record_results(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an exam first.")
            return
        exam_id = int(sel[0])

        # Get year group from the exam row
        vals = self._tree.item(sel[0], "values")
        year_group = vals[3] if vals[3] else None

        students = self._stu_svc.list_students(status="active", year_group=year_group)
        if not students:
            messagebox.showwarning("Warning", "No students found for this year group.")
            return

        existing = {r["student_id"]: r for r in self._svc.get_exam_results(exam_id)}

        dlg = tk.Toplevel(self)
        dlg.title(f"Record Results — {vals[1]}")
        dlg.geometry("650x500")

        # Scrollable list
        canvas = tk.Canvas(dlg)
        scrollbar = ttk.Scrollbar(dlg, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas)

        frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        tk.Label(frame, text="Student", font=("Helvetica", 9, "bold"), width=25, anchor="w").grid(row=0, column=0, padx=5, pady=3)
        tk.Label(frame, text="Marks", font=("Helvetica", 9, "bold"), width=8).grid(row=0, column=1, padx=5, pady=3)
        tk.Label(frame, text="Grade", font=("Helvetica", 9, "bold"), width=6).grid(row=0, column=2, padx=5, pady=3)
        tk.Label(frame, text="Absent", font=("Helvetica", 9, "bold"), width=6).grid(row=0, column=3, padx=5, pady=3)

        entries = []
        for i, stu in enumerate(students, 1):
            tk.Label(frame, text=f"{stu['first_name']} {stu['last_name']}",
                     anchor="w", width=25).grid(row=i, column=0, padx=5, pady=2)

            ex = existing.get(stu["id"], {})
            marks_var = tk.StringVar(value=str(ex.get("marks_obtained", "")) if ex.get("marks_obtained") is not None else "")
            grade_var = tk.StringVar(value=ex.get("grade", "") or "")
            absent_var = tk.BooleanVar(value=bool(ex.get("absent", 0)))

            ttk.Entry(frame, textvariable=marks_var, width=8).grid(row=i, column=1, padx=5, pady=2)
            ttk.Entry(frame, textvariable=grade_var, width=6).grid(row=i, column=2, padx=5, pady=2)
            ttk.Checkbutton(frame, variable=absent_var).grid(row=i, column=3, padx=5, pady=2)

            entries.append((stu["id"], marks_var, grade_var, absent_var))

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def save_all():
            count = 0
            for stu_id, m_var, g_var, a_var in entries:
                m_val = m_var.get().strip()
                g_val = g_var.get().strip()
                absent = a_var.get()
                if not m_val and not g_val and not absent:
                    continue
                try:
                    marks = float(m_val) if m_val else None
                except ValueError:
                    marks = None
                self._svc.record_result(
                    exam_id=exam_id, student_id=stu_id,
                    marks_obtained=marks, grade=g_val or None,
                    absent=absent,
                )
                count += 1
            messagebox.showinfo("Saved", f"{count} result(s) recorded.")
            dlg.destroy()

        btn_frame = tk.Frame(dlg, pady=8)
        btn_frame.pack(fill="x")
        ttk.Button(btn_frame, text="Save All", command=save_all).pack(side="left", padx=15)
        ttk.Button(btn_frame, text="Cancel", command=dlg.destroy).pack(side="right", padx=15)

    def _on_view_results(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an exam first.")
            return
        exam_id = int(sel[0])
        vals = self._tree.item(sel[0], "values")

        results = self._svc.get_exam_results(exam_id)
        if not results:
            messagebox.showinfo("Results", "No results recorded for this exam yet.")
            return

        dlg = tk.Toplevel(self)
        dlg.title(f"Results — {vals[1]}")
        dlg.geometry("600x400")

        columns = ("student", "marks", "grade", "absent", "comment")
        tree = ttk.Treeview(dlg, columns=columns, show="headings")
        for col, heading, w in [
            ("student", "Student", 180), ("marks", "Marks", 70),
            ("grade", "Grade", 60), ("absent", "Absent", 60),
            ("comment", "Comment", 200),
        ]:
            tree.heading(col, text=heading)
            tree.column(col, width=w, anchor="center")

        for r in results:
            tree.insert("", "end", values=(
                f"{r['first_name']} {r['last_name']}",
                r["marks_obtained"] if r["marks_obtained"] is not None else "",
                r.get("grade", "") or "",
                "Yes" if r["absent"] else "No",
                r.get("comment", "") or "",
            ))

        tree.pack(fill="both", expand=True, padx=10, pady=10)
        ttk.Button(dlg, text="Close", command=dlg.destroy).pack(pady=(0, 10))

    def _on_edit(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an exam first.")
            return
        exam_id = int(sel[0])
        vals = self._tree.item(sel[0], "values")
        # vals: subject, title, type, year, date, time, duration, room, marks, status

        dlg = tk.Toplevel(self)
        dlg.title(f"Edit Exam — {vals[1]}")
        dlg.resizable(False, False)

        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()

        vars_ = {}
        fields = [
            ("Title", "title", vals[1], None),
            ("Type", "exam_type", vals[2], list(EXAM_TYPES)),
            ("Year Group", "year_group", vals[3], ["7", "8", "9", "10", "11"]),
            ("Date (YYYY-MM-DD)", "date", vals[4], None),
            ("Start Time (HH:MM)", "start_time", vals[5], None),
            ("Duration (mins)", "duration_minutes", vals[6], None),
            ("Room", "room", vals[7], None),
            ("Total Marks", "total_marks", vals[8], None),
        ]

        for row, (label, key, default, values) in enumerate(fields):
            tk.Label(c, text=label, font=("Helvetica", 9, "bold")).grid(
                row=row, column=0, sticky="w", **pad)
            vars_[key] = tk.StringVar(value=default)
            if values:
                ttk.Combobox(c, textvariable=vars_[key], values=values,
                             state="readonly", width=30).grid(row=row, column=1, **pad)
            else:
                ttk.Entry(c, textvariable=vars_[key], width=32).grid(row=row, column=1, **pad)

        result = [None]

        def save():
            result[0] = {k: v.get().strip() for k, v in vars_.items()}
            dlg.destroy()

        btn = tk.Frame(c)
        btn.grid(row=len(fields), column=0, columnspan=2, pady=(12, 0))
        ttk.Button(btn, text="Save", command=save).pack(side="left", padx=5)
        ttk.Button(btn, text="Cancel", command=dlg.destroy).pack(side="left", padx=5)

        self.wait_window(dlg)
        if result[0] is None:
            return

        d = result[0]
        # Convert numeric fields
        for k in ("duration_minutes", "total_marks"):
            try:
                d[k] = int(d[k]) if d[k] else None
            except ValueError:
                d[k] = None
        # Remove empty strings
        updates = {k: (v if v else None) for k, v in d.items()}

        try:
            self._svc.update_exam(exam_id, **updates)
            messagebox.showinfo("Success", "Exam updated. Students have been notified.")
            self._load_exams()
        except ExamError as exc:
            messagebox.showerror("Error", str(exc))

    def _on_cancel(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an exam first.")
            return
        if not messagebox.askyesno("Cancel Exam",
                                   "Cancel this exam?\n\nAll enrolled students will be notified."):
            return
        try:
            self._svc.update_exam_status(int(sel[0]), "cancelled")
            messagebox.showinfo("Cancelled", "Exam cancelled. Students have been notified.")
            self._load_exams()
        except ExamError as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select an exam first.")
            return
        if not messagebox.askyesno("Confirm", "Delete this exam and all its results?\n\n"
                                   "This will permanently remove the exam. Use 'Cancel Exam' "
                                   "to cancel and notify students instead."):
            return
        self._svc.delete_exam(int(sel[0]))
        self._load_exams()
