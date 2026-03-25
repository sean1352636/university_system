"""Homework GUI."""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from education_system.secondary_school.modules.domain.academics.homework.services.homework_service import HomeworkService
from education_system.secondary_school.modules.domain.academics.subjects.services.subject_service import SubjectService
from education_system.secondary_school.core.exceptions import HomeworkError

HEADER_BG = "#1a5276"
MAIN_BG = "#ecf0f1"


class HomeworkFrame(tk.Frame):
    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = HomeworkService(db_path)
        self._subj_svc = SubjectService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg=MAIN_BG)
        header = tk.Frame(self, bg=HEADER_BG, height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Homework", font=("Helvetica", 15, "bold"),
                 bg=HEADER_BG, fg="white").pack(side="left", padx=20, pady=10)
        toolbar = tk.Frame(self, bg=MAIN_BG, pady=8)
        toolbar.pack(fill="x", padx=15)
        ttk.Button(toolbar, text="Set Homework", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="View Submissions", command=self._on_view_subs).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Manage Rubric", command=self._on_manage_rubric).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Late Submissions", command=self._on_late_subs).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Stats", command=self._on_stats).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Extend Deadline", command=self._on_extend_deadline).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete", command=self._on_delete).pack(side="left", padx=4)

        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        cols = ("subject", "title", "year", "set_by", "set_date", "due_date", "max_marks", "status")
        self._tree = ttk.Treeview(tree_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("subject", "Subject", 120), ("title", "Title", 160),
                           ("year", "Year", 40), ("set_by", "Set By", 90),
                           ("set_date", "Set", 80), ("due_date", "Due", 80),
                           ("max_marks", "Marks", 45), ("status", "Status", 55)]:
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
            hws = self._svc.list_homework()
            for h in hws:
                self._tree.insert("", "end", iid=h["id"], values=(
                    h.get("subject_title", ""), h["title"], h.get("year_group") or "",
                    h.get("set_by") or "", h["set_date"], h["due_date"],
                    h.get("max_marks") or "", h["status"]))
            self._status_var.set(f"{len(hws)} homework(s)")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_add(self):
        subjects = self._subj_svc.list_subjects(status="active")
        if not subjects:
            return
        dlg = tk.Toplevel(self)
        dlg.title("Set Homework")
        dlg.resizable(False, False)
        pad = {"padx": 10, "pady": 5}
        c = tk.Frame(dlg, padx=20, pady=15)
        c.pack()
        vars_ = {}
        subj_names = [f"{s['subject_code']} - {s['title']}" for s in subjects]
        row = 0
        tk.Label(c, text="Subject", font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
        vars_["subject"] = tk.StringVar()
        ttk.Combobox(c, textvariable=vars_["subject"], values=subj_names, state="readonly", width=28).grid(row=row, column=1, **pad)
        for l, k, d in [("Title", "title", ""), ("Year Group", "year_group", ""),
                          ("Description", "description", ""), ("Due Date (YYYY-MM-DD)", "due_date", ""),
                          ("Max Marks", "max_marks", "")]:
            row += 1
            tk.Label(c, text=l, font=("Helvetica", 9, "bold")).grid(row=row, column=0, sticky="w", **pad)
            vars_[k] = tk.StringVar(value=d)
            ttk.Entry(c, textvariable=vars_[k], width=30).grid(row=row, column=1, **pad)
        result = [None]
        def save():
            sv = vars_["subject"].get()
            t = vars_["title"].get().strip()
            dd = vars_["due_date"].get().strip()
            if not sv or not t or not dd:
                messagebox.showwarning("Validation", "Subject, title and due date required.")
                return
            code = sv.split(" - ")[0]
            spk = next((s["id"] for s in subjects if s["subject_code"] == code), None)
            result[0] = {"subject_id": spk, "title": t, "due_date": dd}
            for k in ("year_group", "description", "max_marks"):
                result[0][k] = vars_[k].get().strip() or None
            dlg.destroy()
        row += 1
        ttk.Button(c, text="Save", command=save).grid(row=row, column=0, columnspan=2, pady=10)
        self.wait_window(dlg)
        if result[0] is None:
            return
        d = result[0]
        set_by = self._auth.get("username") if self._auth else None
        try:
            mm = int(d["max_marks"]) if d["max_marks"] else None
        except ValueError:
            mm = None
        try:
            self._svc.create_homework(d["subject_id"], d["title"], d["due_date"],
                                       d["year_group"], d["description"], set_by, mm)
            messagebox.showinfo("Success", "Homework set.")
            self._load()
        except HomeworkError as e:
            messagebox.showerror("Error", str(e))

    def _on_view_subs(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a homework first.")
            return
        hw_id = int(sel[0])
        subs = self._svc.get_submissions(hw_id)
        dlg = tk.Toplevel(self)
        dlg.title("Submissions")
        dlg.geometry("750x450")

        notebook = ttk.Notebook(dlg)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Submissions tab ---
        sub_frame = tk.Frame(notebook)
        notebook.add(sub_frame, text="Submissions")
        cols = ("id", "student", "submitted", "marks", "attachment", "late", "status")
        tree = ttk.Treeview(sub_frame, columns=cols, show="headings", selectmode="browse")
        for col, h, w in [("id", "ID", 35), ("student", "Student", 130), ("submitted", "Submitted", 115),
                           ("marks", "Marks", 45), ("attachment", "Attachment", 90),
                           ("late", "Late", 35), ("status", "Status", 60)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        for s in subs:
            fp = s.get("file_path") or ""
            late_flag = "Yes" if s.get("is_late") else ""
            tree.insert("", "end", iid=s["id"], values=(
                s["id"],
                f"{s['first_name']} {s['last_name']}", s.get("submitted_at") or "",
                s.get("marks") if s.get("marks") is not None else "",
                fp.split("/")[-1] if fp else "",
                late_flag, s["status"]))
        tree.pack(fill="both", expand=True, padx=5, pady=5)

        btn_row = tk.Frame(sub_frame)
        btn_row.pack(fill="x", padx=5, pady=5)

        def _add_feedback_dlg():
            s = tree.selection()
            if not s:
                messagebox.showwarning("Selection", "Select a submission first.")
                return
            sub_id = int(s[0])
            fb_dlg = tk.Toplevel(dlg)
            fb_dlg.title("Add Feedback")
            fb_dlg.geometry("400x250")
            fb_dlg.grab_set()
            tk.Label(fb_dlg, text="Feedback:", font=("Helvetica", 9, "bold")).pack(anchor="w", padx=10, pady=(10, 2))
            fb_text = tk.Text(fb_dlg, height=6, width=45)
            fb_text.pack(padx=10, pady=5)
            # Load existing feedback
            existing_fb = self._svc.get_detailed_feedback(sub_id)
            if existing_fb:
                for f in existing_fb:
                    fb_text.insert("end", f"[{f.get('marked_by', '?')} @ {f['created_at']}]\n{f['feedback_text']}\n\n")
            def save_fb():
                txt = fb_text.get("1.0", "end").strip()
                if not txt:
                    return
                teacher = self._auth.get("username") if self._auth else "unknown"
                try:
                    self._svc.add_feedback(sub_id, txt, teacher)
                    messagebox.showinfo("Success", "Feedback saved.", parent=fb_dlg)
                    fb_dlg.destroy()
                except HomeworkError as e:
                    messagebox.showerror("Error", str(e), parent=fb_dlg)
            ttk.Button(fb_dlg, text="Save Feedback", command=save_fb).pack(pady=8)

        ttk.Button(btn_row, text="Add Feedback", command=_add_feedback_dlg).pack(side="left", padx=4)

        def _view_feedback():
            s = tree.selection()
            if not s:
                messagebox.showwarning("Selection", "Select a submission first.")
                return
            sub_id = int(s[0])
            fbs = self._svc.get_detailed_feedback(sub_id)
            fb_dlg = tk.Toplevel(dlg)
            fb_dlg.title(f"Feedback for Submission #{sub_id}")
            fb_dlg.geometry("450x300")
            txt = tk.Text(fb_dlg, wrap="word")
            txt.pack(fill="both", expand=True, padx=10, pady=10)
            if fbs:
                for f in fbs:
                    txt.insert("end", f"--- {f.get('marked_by', 'Unknown')} ({f['created_at']}) ---\n")
                    txt.insert("end", f"{f['feedback_text']}\n\n")
            else:
                txt.insert("end", "No feedback recorded yet.")
            txt.config(state="disabled")

        ttk.Button(btn_row, text="View Feedback", command=_view_feedback).pack(side="left", padx=4)

        # --- Drafts tab ---
        draft_frame = tk.Frame(notebook)
        notebook.add(draft_frame, text="Drafts")
        tk.Label(draft_frame, text="Student drafts for this homework are managed via the student portal.",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(pady=20)

    def _on_manage_rubric(self):
        """Open the rubric management dialog for the selected homework."""
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a homework first.")
            return
        hw_id = int(sel[0])
        dlg = tk.Toplevel(self)
        dlg.title("Rubric Management")
        dlg.geometry("520x400")
        dlg.grab_set()

        # Rubric list
        cols = ("id", "criteria", "max_marks")
        tree = ttk.Treeview(dlg, columns=cols, show="headings", selectmode="browse", height=8)
        for col, h, w in [("id", "ID", 40), ("criteria", "Criteria", 320), ("max_marks", "Max Marks", 80)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center" if col != "criteria" else "w")
        tree.pack(fill="both", expand=True, padx=10, pady=(10, 5))

        def load_rubric():
            tree.delete(*tree.get_children())
            rubrics = self._svc.get_rubric(hw_id)
            total = 0
            for r in rubrics:
                tree.insert("", "end", values=(r["id"], r["criteria"], r["max_marks"]))
                total += r["max_marks"]
            total_var.set(f"Total rubric marks: {total}")

        total_var = tk.StringVar(value="Total rubric marks: 0")
        tk.Label(dlg, textvariable=total_var, font=("Helvetica", 9, "bold")).pack(anchor="w", padx=10)

        # Add rubric form
        add_frame = tk.LabelFrame(dlg, text="Add Criterion", padx=10, pady=5)
        add_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(add_frame, text="Criteria:").grid(row=0, column=0, sticky="w", padx=5, pady=3)
        crit_var = tk.StringVar()
        tk.Entry(add_frame, textvariable=crit_var, width=35).grid(row=0, column=1, padx=5, pady=3)
        tk.Label(add_frame, text="Max Marks:").grid(row=1, column=0, sticky="w", padx=5, pady=3)
        marks_var = tk.StringVar()
        tk.Entry(add_frame, textvariable=marks_var, width=10).grid(row=1, column=1, sticky="w", padx=5, pady=3)

        def add_criterion():
            c = crit_var.get().strip()
            m = marks_var.get().strip()
            if not c or not m:
                messagebox.showwarning("Validation", "Both fields are required.", parent=dlg)
                return
            try:
                self._svc.add_rubric(hw_id, c, int(m))
                crit_var.set("")
                marks_var.set("")
                load_rubric()
            except (HomeworkError, ValueError) as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(add_frame, text="Add", command=add_criterion).grid(row=1, column=2, padx=5, pady=3)
        load_rubric()

    def _on_late_subs(self):
        """Show late submissions across all or selected homework."""
        sel = self._tree.selection()
        hw_id = int(sel[0]) if sel else None
        late = self._svc.list_late_submissions(hw_id)
        dlg = tk.Toplevel(self)
        dlg.title("Late Submissions")
        dlg.geometry("600x350")
        cols = ("student", "homework", "due", "submitted", "status")
        tree = ttk.Treeview(dlg, columns=cols, show="headings")
        for col, h, w in [("student", "Student", 140), ("homework", "Homework", 150),
                           ("due", "Due Date", 90), ("submitted", "Submitted", 120), ("status", "Status", 60)]:
            tree.heading(col, text=h)
            tree.column(col, width=w, anchor="center")
        for s in late:
            tree.insert("", "end", values=(
                f"{s['first_name']} {s['last_name']}",
                s.get("homework_title", ""),
                s.get("due_date", ""),
                s.get("submitted_at", ""),
                s["status"]))
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        tk.Label(dlg, text=f"{len(late)} late submission(s)", anchor="w").pack(fill="x", padx=10, pady=(0, 8))

    def _on_stats(self):
        """Show submission statistics for the selected homework."""
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a homework first.")
            return
        hw_id = int(sel[0])
        stats = self._svc.get_submission_stats(hw_id)
        if not stats:
            messagebox.showinfo("Stats", "No submission data available.")
            return
        avg = stats.get("avg_marks")
        avg_str = f"{avg:.1f}" if avg is not None else "N/A"
        msg = (
            f"Total submissions: {stats.get('total_submissions', 0)}\n"
            f"Submitted: {stats.get('submitted_count', 0)}\n"
            f"Marked: {stats.get('marked_count', 0)}\n"
            f"Late: {stats.get('late_count', 0)}\n"
            f"Pending: {stats.get('pending_count', 0)}\n"
            f"Average marks: {avg_str}"
        )
        messagebox.showinfo("Submission Statistics", msg)

    def _on_extend_deadline(self):
        """Extend the deadline for the selected homework."""
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Select a homework first.")
            return
        hw_id = int(sel[0])
        dlg = tk.Toplevel(self)
        dlg.title("Extend Deadline")
        dlg.geometry("380x180")
        dlg.grab_set()
        c = tk.Frame(dlg, padx=15, pady=10)
        c.pack(fill="both", expand=True)
        tk.Label(c, text="New Due Date (YYYY-MM-DD):", font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(5, 2))
        date_var = tk.StringVar()
        tk.Entry(c, textvariable=date_var, width=20).pack(anchor="w", pady=2)
        tk.Label(c, text="Reason:", font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(5, 2))
        reason_var = tk.StringVar()
        tk.Entry(c, textvariable=reason_var, width=35).pack(anchor="w", pady=2)

        def save():
            d = date_var.get().strip()
            r = reason_var.get().strip()
            if not d or not r:
                messagebox.showwarning("Validation", "Both fields are required.", parent=dlg)
                return
            try:
                self._svc.extend_deadline(hw_id, d, r)
                messagebox.showinfo("Success", "Deadline extended.", parent=dlg)
                dlg.destroy()
                self._load()
            except HomeworkError as e:
                messagebox.showerror("Error", str(e), parent=dlg)

        ttk.Button(c, text="Extend", command=save).pack(pady=10)

    def _on_delete(self):
        sel = self._tree.selection()
        if not sel:
            return
        if messagebox.askyesno("Confirm", "Delete this homework and all submissions?"):
            self._svc.delete_homework(int(sel[0]))
            self._load()
