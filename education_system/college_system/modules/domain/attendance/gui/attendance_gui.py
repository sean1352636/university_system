"""Attendance management GUI for the College Management System.

Tabbed Notebook interface with:
  Tab 1: Take Attendance — dropdown course selector, roster grid with radio buttons
  Tab 2: View Records — course + session selectors, treeview of records
  Tab 3: Reports — student attendance summary with colour-coded rates
"""

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from education_system.college_system.modules.domain.attendance.services.attendance_service import AttendanceService
from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.modules.domain.students.services.student_service import StudentService
from education_system.college_system.core.exceptions import AttendanceError
from education_system.college_system.core.i18n import t


class AttendanceFrame(tk.Frame):
    """Attendance management screen with tabbed Notebook layout."""

    _STATUSES = ("present", "absent", "late", "excused")

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._attendance_svc = AttendanceService(db_path)
        self._course_svc = CourseService(db_path)
        self._student_svc = StudentService(db_path)

        self._courses: list[dict] = []
        self._roster_widgets: list[dict] = []

        # Pagination state for records tab
        self._rec_page = 0
        self._rec_page_size = 50
        self._rec_total_count = 0
        self._rec_current_session_id: int | None = None

        self._build_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("attendance.management"),
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        # Notebook
        self._nb = ttk.Notebook(self)
        self._nb.pack(fill="both", expand=True, padx=10, pady=10)

        self._build_take_tab()
        self._build_records_tab()
        self._build_reports_tab()
        self._build_generate_tab()

        # Status bar
        self._status_var = tk.StringVar(value=t("common.ready"))
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(
            fill="x", padx=15, pady=(0, 8))

        # --- Keyboard shortcuts for accessibility ---
        self._bind_when_visible("<Control-n>", lambda e: self._on_create_and_load())

    def _bind_when_visible(self, sequence, callback):
        """Bind a keyboard shortcut that only fires when this frame is visible."""
        def _handler(event):
            if self.winfo_ismapped():
                callback(event)
                return "break"
        self.bind(sequence, _handler)
        top = self.winfo_toplevel()
        top.bind(sequence, _handler, add=True)

    def _build_take_tab(self):
        """Tab 1: Take Attendance (admin/staff/instructor only)."""
        self._take_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(self._take_tab, text=t("attendance.tab_take"))

        # Course + date + topic row
        form = tk.Frame(self._take_tab, bg="#ecf0f1")
        form.pack(fill="x", pady=(0, 10))

        tk.Label(form, text=t("attendance.course_colon"), bg="#ecf0f1").grid(
            row=0, column=0, sticky="w", padx=5, pady=4)
        self._take_course_var = tk.StringVar()
        self._take_course_combo = ttk.Combobox(
            form, textvariable=self._take_course_var,
            state="readonly", width=25)
        self._take_course_combo.grid(row=0, column=1, padx=5, pady=4)

        tk.Label(form, text=t("attendance.date_colon"), bg="#ecf0f1").grid(
            row=0, column=2, sticky="w", padx=5, pady=4)
        self._take_date_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(form, textvariable=self._take_date_var, width=12).grid(
            row=0, column=3, padx=5, pady=4)

        tk.Label(form, text=t("attendance.topic_colon"), bg="#ecf0f1").grid(
            row=0, column=4, sticky="w", padx=5, pady=4)
        self._take_topic_var = tk.StringVar()
        ttk.Entry(form, textvariable=self._take_topic_var, width=18).grid(
            row=0, column=5, padx=5, pady=4)

        ttk.Button(form, text=t("attendance.create_session"),
                   command=self._on_create_and_load).grid(
            row=0, column=6, padx=10, pady=4)

        # Scrollable roster area
        roster_container = tk.Frame(self._take_tab, bg="#ecf0f1")
        roster_container.pack(fill="both", expand=True)

        canvas = tk.Canvas(roster_container, bg="white", highlightthickness=0)
        vsb = ttk.Scrollbar(roster_container, orient="vertical",
                            command=canvas.yview)
        self._roster_frame = tk.Frame(canvas, bg="white")
        self._roster_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._roster_frame, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Header row for roster
        for col, text, w in [(0, t("attendance.col_student_id"), 12), (1, t("attendance.col_name"), 25),
                              (2, t("attendance.col_present"), 8), (3, t("attendance.col_absent"), 8),
                              (4, t("attendance.col_late"), 8), (5, t("attendance.col_excused"), 8)]:
            tk.Label(self._roster_frame, text=text, font=("Helvetica", 9, "bold"),
                     bg="#dfe6e9", width=w, anchor="center", relief="ridge").grid(
                row=0, column=col, sticky="ew")

        # Submit button
        ttk.Button(self._take_tab, text=t("attendance.submit_all"),
                   command=self._on_submit_all).pack(pady=8)

    def _build_records_tab(self):
        """Tab 2: View Records (all roles)."""
        records_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(records_tab, text=t("attendance.tab_records"))

        sel_row = tk.Frame(records_tab, bg="#ecf0f1")
        sel_row.pack(fill="x", pady=(0, 8))

        tk.Label(sel_row, text=t("attendance.course_colon"), bg="#ecf0f1").pack(side="left", padx=(0, 5))
        self._rec_course_var = tk.StringVar()
        self._rec_course_combo = ttk.Combobox(
            sel_row, textvariable=self._rec_course_var,
            state="readonly", width=25)
        self._rec_course_combo.pack(side="left", padx=(0, 10))
        self._rec_course_combo.bind("<<ComboboxSelected>>", self._on_rec_course_selected)

        tk.Label(sel_row, text=t("attendance.session_colon"), bg="#ecf0f1").pack(side="left", padx=(0, 5))
        self._rec_session_var = tk.StringVar()
        self._rec_session_combo = ttk.Combobox(
            sel_row, textvariable=self._rec_session_var,
            state="readonly", width=30)
        self._rec_session_combo.pack(side="left", padx=(0, 10))
        self._rec_session_combo.bind("<<ComboboxSelected>>", self._on_rec_session_selected)

        # Treeview
        rec_tree_frame = tk.Frame(records_tab)
        rec_tree_frame.pack(fill="both", expand=True)

        columns = ("sid", "name", "status", "recorded_at")
        self._rec_tree = ttk.Treeview(rec_tree_frame, columns=columns,
                                      show="headings", selectmode="browse")
        for col, heading, w in [
            ("sid", t("attendance.col_student_id"), 100), ("name", t("attendance.col_name"), 180),
            ("status", t("attendance.col_status"), 90), ("recorded_at", t("attendance.col_recorded"), 150),
        ]:
            self._rec_tree.heading(col, text=heading)
            self._rec_tree.column(col, width=w, anchor="center")

        rec_vsb = ttk.Scrollbar(rec_tree_frame, orient="vertical",
                                command=self._rec_tree.yview)
        self._rec_tree.configure(yscrollcommand=rec_vsb.set)
        self._rec_tree.pack(side="left", fill="both", expand=True)
        rec_vsb.pack(side="right", fill="y")

        # Return key on records treeview shows selected record details
        self._rec_tree.bind("<Return>", lambda e: self._on_rec_view_selected())

        # Pagination bar for records
        rec_pag_frame = tk.Frame(records_tab, bg="#ecf0f1")
        rec_pag_frame.pack(fill="x", pady=(4, 0))

        self._rec_prev_btn = ttk.Button(rec_pag_frame, text="Previous",
                                         command=self._rec_prev_page, state="disabled")
        self._rec_prev_btn.pack(side="left", padx=4)

        self._rec_page_label_var = tk.StringVar(value="Page 1 of 1")
        tk.Label(rec_pag_frame, textvariable=self._rec_page_label_var,
                 bg="#ecf0f1", font=("Helvetica", 9)).pack(side="left", padx=8)

        self._rec_next_btn = ttk.Button(rec_pag_frame, text="Next",
                                         command=self._rec_next_page, state="disabled")
        self._rec_next_btn.pack(side="left", padx=4)

        self._rec_record_count_var = tk.StringVar(value="")
        tk.Label(rec_pag_frame, textvariable=self._rec_record_count_var,
                 bg="#ecf0f1", font=("Helvetica", 9), fg="#7f8c8d").pack(
            side="right", padx=8)

        ttk.Button(rec_pag_frame, text="Export CSV", command=self._export_csv).pack(
            side="right", padx=5)

        self._sessions_data: list[dict] = []

    def _build_reports_tab(self):
        """Tab 3: Reports (all roles)."""
        reports_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(reports_tab, text=t("attendance.tab_reports"))

        input_row = tk.Frame(reports_tab, bg="#ecf0f1")
        input_row.pack(fill="x", pady=(0, 10))

        tk.Label(input_row, text=t("attendance.student_id_colon"), bg="#ecf0f1").pack(side="left", padx=(0, 5))
        self._rpt_student_var = tk.StringVar()
        ttk.Entry(input_row, textvariable=self._rpt_student_var, width=12).pack(
            side="left", padx=(0, 10))

        tk.Label(input_row, text=t("attendance.course_code_colon"), bg="#ecf0f1").pack(side="left", padx=(0, 5))
        self._rpt_course_var = tk.StringVar()
        ttk.Entry(input_row, textvariable=self._rpt_course_var, width=12).pack(
            side="left", padx=(0, 10))

        ttk.Button(input_row, text=t("attendance.show_summary"),
                   command=self._on_show_summary).pack(side="left", padx=5)

        # Summary display
        self._summary_frame = tk.LabelFrame(reports_tab, text=t("attendance.summary"),
                                            bg="#ecf0f1", font=("Helvetica", 10, "bold"))
        self._summary_frame.pack(fill="x", pady=5)

        self._summary_labels: dict[str, tk.StringVar] = {}
        summary_inner = tk.Frame(self._summary_frame, bg="#ecf0f1")
        summary_inner.pack(fill="x", padx=10, pady=8)

        for i, label in enumerate((t("attendance.total_sessions"), t("attendance.present"),
                                    t("attendance.absent"), t("attendance.late"),
                                    t("attendance.excused"), t("attendance.rate"))):
            var = tk.StringVar(value="--")
            row = tk.Frame(summary_inner, bg="#ecf0f1")
            row.grid(row=i // 3, column=i % 3, padx=15, pady=4, sticky="w")
            tk.Label(row, text=f"{label}:", bg="#ecf0f1",
                     font=("Helvetica", 10, "bold"), anchor="w").pack(side="left")
            lbl = tk.Label(row, textvariable=var, bg="#ecf0f1",
                           font=("Helvetica", 10), fg="#2980b9")
            lbl.pack(side="left", padx=(5, 0))
            self._summary_labels[label] = var
            if label == t("attendance.rate"):
                self._rate_label = lbl

    def _build_generate_tab(self):
        """Tab 4: Generate from Timetable (admin/staff only)."""
        self._gen_tab = tk.Frame(self._nb, bg="#ecf0f1", padx=10, pady=10)
        self._nb.add(self._gen_tab, text=t("attendance.tab_generate"))

        form = tk.Frame(self._gen_tab, bg="#ecf0f1")
        form.pack(fill="x", pady=(0, 10))

        tk.Label(form, text=t("attendance.date_colon"), bg="#ecf0f1").pack(side="left", padx=(0, 5))
        self._gen_date_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(form, textvariable=self._gen_date_var, width=12).pack(side="left", padx=(0, 10))

        ttk.Button(form, text=t("attendance.generate_registers"),
                   command=self._on_generate_registers).pack(side="left", padx=5)

        # Results area
        self._gen_results = tk.Text(self._gen_tab, height=15, wrap="word", state="disabled")
        self._gen_results.pack(fill="both", expand=True)

    def _on_generate_registers(self):
        target = self._gen_date_var.get().strip()
        if not target:
            messagebox.showwarning(t("common.input"), t("attendance.enter_date"))
            return

        created_by = None
        if self._auth and self._auth.current_user:
            created_by = self._auth.current_user.get("username")

        try:
            sessions = self._attendance_svc.generate_registers_for_date(
                target, created_by=created_by)
            self._gen_results.configure(state="normal")
            self._gen_results.delete("1.0", "end")
            self._gen_results.insert("end", f"Generated {len(sessions)} register(s) for {target}\n\n")
            for s in sessions:
                self._gen_results.insert(
                    "end",
                    f"Session {s['id']}: {s.get('course_code', '?')} - {s.get('topic', '')}\n",
                )
            self._gen_results.configure(state="disabled")
            self._status_var.set(f"{len(sessions)} registers generated for {target}")
        except Exception as e:
            messagebox.showerror(t("common.error"), str(e))

    # ------------------------------------------------------------------
    # Refresh & permissions
    # ------------------------------------------------------------------

    def refresh(self):
        """Called when frame is shown."""
        self._load_courses()
        self._apply_permissions()

    def _apply_permissions(self):
        role = ""
        if self._auth and self._auth.current_user:
            role = self._auth.current_user.get("role", "student")
        is_student = role == "student"
        try:
            self._nb.tab(self._take_tab,
                         state="hidden" if is_student else "normal")
            self._nb.tab(self._gen_tab,
                         state="hidden" if is_student else "normal")
        except Exception:
            pass

    def _load_courses(self):
        try:
            self._courses = self._course_svc.list_courses(status="active")
        except Exception:
            self._courses = []

        display = [f"{c['course_code']} - {c['title']}" for c in self._courses]
        self._take_course_combo["values"] = display
        self._rec_course_combo["values"] = display

    def _get_selected_course(self, combo) -> dict | None:
        idx = combo.current()
        if idx < 0 or idx >= len(self._courses):
            return None
        return self._courses[idx]

    # ------------------------------------------------------------------
    # Tab 1: Take Attendance
    # ------------------------------------------------------------------

    def _on_create_and_load(self):
        course = self._get_selected_course(self._take_course_combo)
        if not course:
            messagebox.showwarning(t("common.input"), t("attendance.select_course_first"))
            return

        date_str = self._take_date_var.get().strip() or None
        topic = self._take_topic_var.get().strip() or None
        created_by = None
        if self._auth and self._auth.current_user:
            created_by = self._auth.current_user.get("username")

        try:
            session = self._attendance_svc.create_session(
                course["id"], session_date=date_str,
                topic=topic, created_by=created_by,
            )
        except AttendanceError as exc:
            messagebox.showerror(t("common.error"), str(exc))
            return

        self._current_session_id = session["id"]
        self._status_var.set(f"Session created (ID: {session['id']})")

        # Load roster
        try:
            roster = self._course_svc.get_roster(course["id"])
        except Exception:
            roster = []

        # Clear old roster widgets
        for w in self._roster_widgets:
            for widget in w.values():
                if hasattr(widget, "destroy"):
                    widget.destroy()
        self._roster_widgets.clear()

        # Clear the frame except header row
        for child in self._roster_frame.winfo_children():
            info = child.grid_info()
            if info and int(info.get("row", 0)) > 0:
                child.destroy()

        if not roster:
            tk.Label(self._roster_frame, text=t("attendance.no_students_enrolled"),
                     bg="white").grid(row=1, column=0, columnspan=6, pady=10)
            return

        for i, student in enumerate(roster, start=1):
            name = f"{student['first_name']} {student['last_name']}"
            sid_lbl = tk.Label(self._roster_frame, text=student["student_id"],
                               bg="white", width=12)
            sid_lbl.grid(row=i, column=0, sticky="ew")
            name_lbl = tk.Label(self._roster_frame, text=name,
                                bg="white", width=25, anchor="w")
            name_lbl.grid(row=i, column=1, sticky="ew")

            status_var = tk.StringVar(value="present")
            for col, status_val in enumerate(self._STATUSES, start=2):
                rb = tk.Radiobutton(self._roster_frame, variable=status_var,
                                    value=status_val, bg="white")
                rb.grid(row=i, column=col)

            self._roster_widgets.append({
                "student_pk": student["id"],
                "status_var": status_var,
                "sid_lbl": sid_lbl,
                "name_lbl": name_lbl,
            })

        self._status_var.set(
            f"Session {session['id']} created — {len(roster)} students loaded")

    def _on_submit_all(self):
        if not self._roster_widgets:
            messagebox.showwarning(t("common.input"), t("attendance.load_roster_first"))
            return

        records = []
        for w in self._roster_widgets:
            records.append({
                "student_pk": w["student_pk"],
                "status": w["status_var"].get(),
            })

        try:
            count = self._attendance_svc.bulk_record_attendance(
                self._current_session_id, records)
            messagebox.showinfo(t("common.success"),
                                t("attendance.recorded_for", count=count))
            self._status_var.set(t("attendance.records_submitted", count=count))
        except AttendanceError as exc:
            messagebox.showerror(t("common.error"), str(exc))

    # ------------------------------------------------------------------
    # Tab 2: View Records
    # ------------------------------------------------------------------

    def _on_rec_course_selected(self, event=None):
        course = self._get_selected_course(self._rec_course_combo)
        if not course:
            return

        try:
            self._sessions_data = self._attendance_svc.get_course_sessions(course["id"])
        except Exception:
            self._sessions_data = []

        display = [
            f"#{s['id']} — {s['session_date']} ({s.get('topic') or 'no topic'})"
            for s in self._sessions_data
        ]
        self._rec_session_combo["values"] = display

    def _on_rec_session_selected(self, event=None):
        idx = self._rec_session_combo.current()
        if idx < 0 or idx >= len(self._sessions_data):
            return
        self._rec_current_session_id = self._sessions_data[idx]["id"]
        self._rec_page = 0
        self._load_rec_records()

    def _load_rec_records(self):
        """Load attendance records for the current session with pagination."""
        if self._rec_current_session_id is None:
            return

        self._rec_tree.delete(*self._rec_tree.get_children())
        try:
            self._rec_total_count = self._attendance_svc.count_session_records(
                self._rec_current_session_id)
            records = self._attendance_svc.get_session_records(
                self._rec_current_session_id,
                limit=self._rec_page_size,
                offset=self._rec_page * self._rec_page_size,
            )
        except Exception as exc:
            messagebox.showerror(t("common.error"), f"Failed to load records:\n{exc}")
            return

        for r in records:
            name = f"{r.get('first_name', '')} {r.get('last_name', '')}"
            self._rec_tree.insert("", "end", values=(
                r.get("sid", ""), name.strip(),
                r.get("status", ""), r.get("recorded_at", ""),
            ))

        self._update_rec_pagination()
        self._status_var.set(
            f"{len(records)} record(s) for session {self._rec_current_session_id}")

    def _update_rec_pagination(self):
        """Update pagination controls for the records tab."""
        total_pages = max(1, (self._rec_total_count + self._rec_page_size - 1) // self._rec_page_size)
        current = self._rec_page + 1
        self._rec_page_label_var.set(f"Page {current} of {total_pages}")

        start = self._rec_page * self._rec_page_size + 1
        end = min((self._rec_page + 1) * self._rec_page_size, self._rec_total_count)
        if self._rec_total_count == 0:
            self._rec_record_count_var.set("No records")
        else:
            self._rec_record_count_var.set(
                f"Showing {start}-{end} of {self._rec_total_count} records")

        self._rec_prev_btn.configure(
            state="normal" if self._rec_page > 0 else "disabled")
        self._rec_next_btn.configure(
            state="normal" if current < total_pages else "disabled")

    def _rec_next_page(self):
        self._rec_page += 1
        self._load_rec_records()

    def _rec_prev_page(self):
        if self._rec_page > 0:
            self._rec_page -= 1
        self._load_rec_records()

    # ------------------------------------------------------------------
    # Tab 3: Reports
    # ------------------------------------------------------------------

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._rec_tree, default_filename="attendance.csv")

    def _on_show_summary(self):
        sid_str = self._rpt_student_var.get().strip()
        code_str = self._rpt_course_var.get().strip().upper()

        if not sid_str or not code_str:
            messagebox.showwarning(t("common.input"), t("attendance.enter_both_ids"))
            return

        try:
            student = self._student_svc.get_student_by_student_id(sid_str)
            if not student:
                raise AttendanceError(f"Student '{sid_str}' not found.")
            course = self._course_svc.get_course_by_code(code_str)
            if not course:
                raise AttendanceError(f"Course '{code_str}' not found.")
        except AttendanceError as exc:
            messagebox.showerror(t("common.error"), str(exc))
            return

        try:
            summary = self._attendance_svc.get_attendance_summary(
                student["id"], course["id"])
        except Exception as exc:
            messagebox.showerror(t("common.error"), f"Failed to get summary:\n{exc}")
            return

        self._summary_labels[t("attendance.total_sessions")].set(
            str(summary.get("total_sessions", 0)))
        self._summary_labels[t("attendance.present")].set(str(summary.get("present", 0)))
        self._summary_labels[t("attendance.absent")].set(str(summary.get("absent", 0)))
        self._summary_labels[t("attendance.late")].set(str(summary.get("late", 0)))
        self._summary_labels[t("attendance.excused")].set(str(summary.get("excused", 0)))

        rate = summary.get("attendance_rate", 0.0)
        self._summary_labels[t("attendance.rate")].set(f"{rate}%")

        # Colour-code the rate
        if rate >= 90:
            colour = "#27ae60"  # green
        elif rate >= 75:
            colour = "#f39c12"  # amber
        else:
            colour = "#e74c3c"  # red
        self._rate_label.configure(fg=colour)

        self._status_var.set(
            f"Summary for {sid_str} in {code_str}")

    def _on_rec_view_selected(self):
        """Handle Return key on records treeview -- show details of selected record."""
        sel = self._rec_tree.selection()
        if not sel:
            return
        values = self._rec_tree.item(sel[0], "values")
        if values:
            detail = (
                f"Student ID: {values[0]}\n"
                f"Name: {values[1]}\n"
                f"Status: {values[2]}\n"
                f"Recorded: {values[3]}"
            )
            messagebox.showinfo("Attendance Record", detail)
