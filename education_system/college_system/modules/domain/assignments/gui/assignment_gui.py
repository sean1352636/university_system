"""Assignment GUI frame."""

import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.assignments.services.assignment_service import AssignmentService
from education_system.college_system.core.i18n import t


class AssignmentFrame(tk.Frame):
    """Assignment management frame."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = AssignmentService(db_path)

        # Pagination state
        self._page = 0
        self._page_size = 50
        self._total_count = 0

        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("assignment.management"),
                 font=("Helvetica", 15, "bold"), bg="#2c3e50", fg="white"
                 ).pack(side="left", padx=20, pady=10)

        # Notebook for tabs
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Create tab (staff/instructor only) ---
        self._create_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(self._create_tab, text=t("assignment.tab_create"))
        create_frame = self._create_tab

        fields = [
            (t("assignment.course_id_colon"), "_create_course_var"),
            (t("assignment.title_colon"), "_create_title_var"),
            (t("assignment.description_colon"), "_create_desc_var"),
            (t("assignment.due_date_colon"), "_create_due_var"),
            (t("assignment.max_score_colon"), "_create_max_var"),
        ]
        for i, (label, var_name) in enumerate(fields):
            tk.Label(create_frame, text=label, bg="#ecf0f1").grid(
                row=i, column=0, sticky="e", padx=5, pady=3)
            var = tk.StringVar(value="100" if "max" in var_name.lower() else "")
            setattr(self, var_name, var)
            ttk.Entry(create_frame, textvariable=var, width=30).grid(
                row=i, column=1, sticky="w", padx=5, pady=3)

        self._create_late_var = tk.BooleanVar()
        ttk.Checkbutton(create_frame, text=t("assignment.allow_late"),
                        variable=self._create_late_var).grid(
            row=len(fields), column=1, sticky="w", padx=5, pady=3)

        ttk.Button(create_frame, text=t("assignment.create"),
                   command=self._create_assignment).grid(
            row=len(fields) + 1, column=1, sticky="w", padx=5, pady=10)

        # --- List tab ---
        list_frame = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(list_frame, text=t("assignment.tab_assignments"))

        filter_row = tk.Frame(list_frame, bg="#ecf0f1")
        filter_row.pack(fill="x", pady=(0, 5))
        tk.Label(filter_row, text=t("assignment.course_id_colon"), bg="#ecf0f1").pack(side="left")
        self._list_filter_var = tk.StringVar()
        ttk.Entry(filter_row, textvariable=self._list_filter_var, width=8).pack(side="left", padx=5)
        ttk.Button(filter_row, text=t("common.load"), command=self._on_filter_load).pack(side="left", padx=5)
        ttk.Button(filter_row, text="Export CSV", command=self._export_csv).pack(side="right", padx=5)

        cols = ("id", "course", "title", "due_date", "max_score", "late")
        self._assign_tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=12)
        for c, w in zip(cols, (40, 80, 180, 100, 70, 50)):
            self._assign_tree.heading(c, text=c.replace("_", " ").capitalize())
            self._assign_tree.column(c, width=w)
        self._assign_tree.pack(fill="both", expand=True)

        # Pagination bar
        pag_frame = tk.Frame(list_frame, bg="#ecf0f1")
        pag_frame.pack(fill="x", pady=(4, 0))

        self._prev_btn = ttk.Button(pag_frame, text="Previous",
                                     command=self._prev_page, state="disabled")
        self._prev_btn.pack(side="left", padx=4)

        self._page_label_var = tk.StringVar(value="Page 1 of 1")
        tk.Label(pag_frame, textvariable=self._page_label_var,
                 bg="#ecf0f1", font=("Helvetica", 9)).pack(side="left", padx=8)

        self._next_btn = ttk.Button(pag_frame, text="Next",
                                     command=self._next_page, state="disabled")
        self._next_btn.pack(side="left", padx=4)

        self._record_count_var = tk.StringVar(value="")
        tk.Label(pag_frame, textvariable=self._record_count_var,
                 bg="#ecf0f1", font=("Helvetica", 9), fg="#7f8c8d").pack(
            side="right", padx=8)

        # --- Submit tab (student only) ---
        self._submit_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(self._submit_tab, text=t("assignment.tab_submit"))
        submit_frame = self._submit_tab

        tk.Label(submit_frame, text=t("assignment.assignment_id_colon"), bg="#ecf0f1").grid(
            row=0, column=0, sticky="e", padx=5, pady=3)
        self._submit_id_var = tk.StringVar()
        ttk.Entry(submit_frame, textvariable=self._submit_id_var, width=8).grid(
            row=0, column=1, sticky="w", padx=5, pady=3)

        tk.Label(submit_frame, text=t("assignment.content_colon"), bg="#ecf0f1").grid(
            row=1, column=0, sticky="ne", padx=5, pady=3)
        self._submit_text = tk.Text(submit_frame, width=50, height=8)
        self._submit_text.grid(row=1, column=1, sticky="w", padx=5, pady=3)

        ttk.Button(submit_frame, text=t("common.submit"), command=self._submit_assignment).grid(
            row=2, column=1, sticky="w", padx=5, pady=10)

        # --- Grade tab (staff/instructor only) ---
        self._grade_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(self._grade_tab, text=t("assignment.tab_grade"))
        grade_frame = self._grade_tab

        tk.Label(grade_frame, text=t("assignment.submission_id_colon"), bg="#ecf0f1").grid(
            row=0, column=0, sticky="e", padx=5, pady=3)
        self._grade_sub_var = tk.StringVar()
        ttk.Entry(grade_frame, textvariable=self._grade_sub_var, width=8).grid(
            row=0, column=1, sticky="w", padx=5, pady=3)

        tk.Label(grade_frame, text=t("assignment.score_colon"), bg="#ecf0f1").grid(
            row=1, column=0, sticky="e", padx=5, pady=3)
        self._grade_score_var = tk.StringVar()
        ttk.Entry(grade_frame, textvariable=self._grade_score_var, width=8).grid(
            row=1, column=1, sticky="w", padx=5, pady=3)

        tk.Label(grade_frame, text=t("assignment.feedback_colon"), bg="#ecf0f1").grid(
            row=2, column=0, sticky="ne", padx=5, pady=3)
        self._grade_feedback = tk.Text(grade_frame, width=50, height=4)
        self._grade_feedback.grid(row=2, column=1, sticky="w", padx=5, pady=3)

        ttk.Button(grade_frame, text=t("assignment.grade"), command=self._grade_submission).grid(
            row=3, column=1, sticky="w", padx=5, pady=10)

    def refresh(self):
        self._apply_permissions()
        self._load_assignments()

    def _apply_permissions(self):
        """Show or hide tabs based on user role."""
        role = ""
        if self._auth and self._auth.current_user:
            role = self._auth.current_user.get("role", "student")
        is_student = role == "student"
        try:
            self._nb.tab(self._create_tab, state="hidden" if is_student else "normal")
            self._nb.tab(self._grade_tab, state="hidden" if is_student else "normal")
            self._nb.tab(self._submit_tab, state="normal" if is_student else "hidden")
        except Exception:
            pass

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._assign_tree, default_filename="assignments.csv")

    def _on_filter_load(self):
        """Reset page and reload when filter changes."""
        self._page = 0
        self._load_assignments()

    def _load_assignments(self):
        self._assign_tree.delete(*self._assign_tree.get_children())
        try:
            cid = self._list_filter_var.get().strip()
            course_id = int(cid) if cid else None
            self._total_count = self._svc.count_assignments(course_id)
            assignments = self._svc.list_assignments(
                course_id,
                limit=self._page_size,
                offset=self._page * self._page_size,
            )
            for a in assignments:
                self._assign_tree.insert("", "end", values=(
                    a["id"], a["course_code"], a["title"],
                    a["due_date"], a["max_score"],
                    "Yes" if a["allow_late"] else "No",
                ))
            self._update_pagination()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def _update_pagination(self):
        """Update pagination controls based on current state."""
        total_pages = max(1, (self._total_count + self._page_size - 1) // self._page_size)
        current = self._page + 1
        self._page_label_var.set(f"Page {current} of {total_pages}")

        start = self._page * self._page_size + 1
        end = min((self._page + 1) * self._page_size, self._total_count)
        if self._total_count == 0:
            self._record_count_var.set("No records")
        else:
            self._record_count_var.set(
                f"Showing {start}-{end} of {self._total_count} records")

        self._prev_btn.configure(
            state="normal" if self._page > 0 else "disabled")
        self._next_btn.configure(
            state="normal" if current < total_pages else "disabled")

    def _next_page(self):
        self._page += 1
        self._load_assignments()

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
        self._load_assignments()

    def _create_assignment(self):
        try:
            a = self._svc.create_assignment(
                course_id=int(self._create_course_var.get()),
                title=self._create_title_var.get(),
                description=self._create_desc_var.get() or None,
                due_date=self._create_due_var.get(),
                max_score=float(self._create_max_var.get() or 100),
                allow_late=self._create_late_var.get(),
                created_by=self._auth.current_user["user_id"] if self._auth and self._auth.current_user else None,
            )
            messagebox.showinfo(t("common.success"), t("assignment.created", id=a['id']))
            self._load_assignments()
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _submit_assignment(self):
        try:
            from education_system.college_system.infrastructure.database.db import connect
            conn = connect(self._db_path)
            try:
                student = conn.execute(
                    "SELECT id FROM students WHERE user_id = ?",
                    (self._auth.current_user["user_id"] if self._auth and self._auth.current_user else None,),
                ).fetchone()
            finally:
                conn.close()

            if not student:
                messagebox.showinfo(t("common.info"), t("assignment.no_student_record"))
                return

            content = self._submit_text.get("1.0", "end").strip()
            sub = self._svc.submit(
                int(self._submit_id_var.get()), student["id"], content
            )
            late_str = " (LATE)" if sub["is_late"] else ""
            messagebox.showinfo(t("common.success"), t("assignment.submitted", id=sub['id'], late=late_str))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    def _grade_submission(self):
        try:
            feedback = self._grade_feedback.get("1.0", "end").strip() or None
            result = self._svc.grade_submission(
                int(self._grade_sub_var.get()),
                float(self._grade_score_var.get()),
                feedback,
                graded_by=self._auth.current_user["user_id"] if self._auth and self._auth.current_user else None,
            )
            messagebox.showinfo(t("common.success"), t("assignment.graded", score=result['score']))
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))
