"""Enrollment management GUI for the College Management System."""

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.enrollment.services.enrollment_service import EnrollmentService
from education_system.college_system.modules.domain.students.services.student_service import StudentService
from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.core.exceptions import EnrollmentError
from education_system.college_system.core.i18n import t

logger = logging.getLogger(__name__)


# Statuses the service stores in the ``enrollments`` table. "All" maps to
# ``None`` (no filter); the rest are passed through verbatim.
ENROLLMENT_STATUSES = ("All", "enrolled", "waitlisted", "dropped", "completed")


class _SearchPickerDialog(tk.Toplevel):
    """Modal "type-to-filter" picker over a list of dict rows."""

    def __init__(self, parent, title: str, rows: list[dict],
                 display: callable, search_text: callable):
        super().__init__(parent)
        self.title(title)
        self.geometry("520x420")
        self.transient(parent)
        self.grab_set()
        self.result: dict | None = None

        self._rows = rows
        self._display = display
        self._search_text = search_text
        self._row_map: dict[int, dict] = {}

        tk.Label(self, text=title, font=("Helvetica", 11, "bold")).pack(
            padx=10, pady=(10, 4))

        srch_frame = tk.Frame(self)
        srch_frame.pack(fill="x", padx=10)
        tk.Label(srch_frame, text="Search:").pack(side="left")
        self._srch_var = tk.StringVar()
        entry = ttk.Entry(srch_frame, textvariable=self._srch_var)
        entry.pack(side="left", fill="x", expand=True, padx=5)
        entry.focus_set()

        lf = tk.Frame(self)
        lf.pack(fill="both", expand=True, padx=10, pady=6)
        sb = tk.Scrollbar(lf)
        sb.pack(side="right", fill="y")
        self._lb = tk.Listbox(lf, yscrollcommand=sb.set, font=("Courier", 10))
        self._lb.pack(fill="both", expand=True)
        sb.config(command=self._lb.yview)
        self._lb.bind("<Double-1>", lambda _e: self._on_pick())
        self._lb.bind("<Return>", lambda _e: self._on_pick())

        bf = tk.Frame(self)
        bf.pack(pady=8)
        ttk.Button(bf, text="Select", command=self._on_pick).pack(side="left", padx=4)
        ttk.Button(bf, text="Cancel", command=self.destroy).pack(side="left", padx=4)

        self._populate()
        self._srch_var.trace_add("write", lambda *_: self._populate())
        self.bind("<Escape>", lambda _e: self.destroy())

    def _populate(self):
        ft = self._srch_var.get().lower().strip()
        self._lb.delete(0, tk.END)
        self._row_map.clear()
        for row in self._rows:
            if ft and ft not in self._search_text(row).lower():
                continue
            pos = self._lb.size()
            self._lb.insert(tk.END, self._display(row))
            self._row_map[pos] = row

    def _on_pick(self):
        sel = self._lb.curselection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a row.", parent=self)
            return
        self.result = self._row_map[sel[0]]
        self.destroy()


class EnrollmentFrame(tk.Frame):
    """Enrollment management screen.

    Provides enroll / drop actions, a Treeview of enrollments with search +
    status / student / course filters, a waitlist sidebar, and toolbar
    actions to drop, view or promote from waitlist directly off the
    selection.
    """

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._enrollment_svc = EnrollmentService(db_path)
        self._student_svc = StudentService(db_path)
        self._course_svc = CourseService(db_path)

        # Pagination + filter state
        self._page = 0
        self._page_size = 50
        self._total_count = 0
        self._current_status_filter: str | None = None
        self._current_search: str | None = None
        self._filter_student: dict | None = None  # {"id": pk, "student_id": "SFC...", "first_name": ..}
        self._filter_course: dict | None = None   # {"id": pk, "course_code": "XX01", ...}

        self._build_ui()
        # Auto-load so opening the frame standalone doesn't show empty.
        self._load_enrollments()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=t("enrollment.management"),
                 font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        self._build_enroll_drop_section()
        self._build_filters_section()
        self._build_main_content()
        self._build_action_toolbar()
        self._build_pagination_and_status()
        self._bind_shortcuts()

    def _build_enroll_drop_section(self):
        form_frame = tk.LabelFrame(
            self, text=t("enrollment.enroll_drop"), padx=12, pady=8,
            bg="#ecf0f1", font=("Helvetica", 10, "bold"))
        form_frame.pack(fill="x", padx=15, pady=(10, 5))

        tk.Label(form_frame, text=t("enrollment.student_id_colon"), bg="#ecf0f1").grid(
            row=0, column=0, sticky="w", padx=5, pady=4)
        self._student_id_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self._student_id_var,
                  width=16).grid(row=0, column=1, padx=(5, 0), pady=4)
        ttk.Button(form_frame, text="Browse…", width=8,
                   command=self._pick_student).grid(
            row=0, column=2, padx=(2, 8), pady=4)

        tk.Label(form_frame, text=t("enrollment.course_code_colon"), bg="#ecf0f1").grid(
            row=0, column=3, sticky="w", padx=5, pady=4)
        self._course_code_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self._course_code_var,
                  width=16).grid(row=0, column=4, padx=(5, 0), pady=4)
        ttk.Button(form_frame, text="Browse…", width=8,
                   command=self._pick_course).grid(
            row=0, column=5, padx=(2, 8), pady=4)

        ttk.Button(form_frame, text=t("enrollment.enroll"),
                   command=self._on_enroll).grid(row=0, column=6, padx=4, pady=4)
        ttk.Button(form_frame, text=t("enrollment.drop"),
                   command=self._on_drop).grid(row=0, column=7, padx=4, pady=4)
        ttk.Button(form_frame, text="Clear",
                   command=self._on_clear_form).grid(row=0, column=8, padx=4, pady=4)

    def _build_filters_section(self):
        flt = tk.LabelFrame(
            self, text="Filters & Search", padx=10, pady=6,
            bg="#ecf0f1", font=("Helvetica", 10, "bold"))
        flt.pack(fill="x", padx=15, pady=(0, 5))

        # Row 0: search box
        tk.Label(flt, text=t("common.search_colon"), bg="#ecf0f1").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self._search_var = tk.StringVar()
        self._search_entry = ttk.Entry(flt, textvariable=self._search_var, width=28)
        self._search_entry.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        self._search_entry.bind("<Return>", lambda _e: self._on_search())
        ttk.Button(flt, text=t("common.go"), command=self._on_search).grid(
            row=0, column=2, padx=2, pady=4)
        ttk.Button(flt, text=t("common.clear"), command=self._on_clear_search).grid(
            row=0, column=3, padx=2, pady=4)

        # Row 0 (right): status combobox
        tk.Label(flt, text="Status:", bg="#ecf0f1").grid(
            row=0, column=4, sticky="e", padx=(20, 4), pady=4)
        self._status_filter_var = tk.StringVar(value="All")
        status_cb = ttk.Combobox(
            flt, textvariable=self._status_filter_var,
            values=list(ENROLLMENT_STATUSES), state="readonly", width=14,
        )
        status_cb.grid(row=0, column=5, sticky="w", padx=4, pady=4)
        status_cb.bind("<<ComboboxSelected>>", lambda _e: self._on_status_filter_change())

        # Row 1: per-student / per-course filters
        tk.Label(flt, text="Student:", bg="#ecf0f1").grid(
            row=1, column=0, sticky="w", padx=4, pady=4)
        self._filter_student_var = tk.StringVar(value="All students")
        ttk.Label(flt, textvariable=self._filter_student_var,
                  background="#ecf0f1", foreground="#2c3e50",
                  font=("Helvetica", 9, "italic")).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Button(flt, text="Pick…", command=self._set_student_filter).grid(
            row=1, column=2, padx=2, pady=4)
        ttk.Button(flt, text="×", width=3,
                   command=self._clear_student_filter).grid(
            row=1, column=3, padx=2, pady=4)

        tk.Label(flt, text="Course:", bg="#ecf0f1").grid(
            row=1, column=4, sticky="e", padx=(20, 4), pady=4)
        self._filter_course_var = tk.StringVar(value="All courses")
        ttk.Label(flt, textvariable=self._filter_course_var,
                  background="#ecf0f1", foreground="#2c3e50",
                  font=("Helvetica", 9, "italic")).grid(
            row=1, column=5, sticky="w", padx=4, pady=4)
        ttk.Button(flt, text="Pick…", command=self._set_course_filter).grid(
            row=1, column=6, padx=2, pady=4)
        ttk.Button(flt, text="×", width=3,
                   command=self._clear_course_filter).grid(
            row=1, column=7, padx=2, pady=4)

    def _build_main_content(self):
        content = tk.Frame(self, bg="#ecf0f1")
        content.pack(fill="both", expand=True, padx=15, pady=5)
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        # Enrollments Treeview
        enroll_lf = tk.LabelFrame(content, text=t("enrollment.enrollments"),
                                  bg="#ecf0f1", font=("Helvetica", 10, "bold"))
        enroll_lf.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        tree_frame = tk.Frame(enroll_lf)
        tree_frame.pack(fill="both", expand=True, padx=4, pady=4)

        columns = ("sid", "student_name", "course_code", "course_title",
                   "status", "enrolled_at")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                  selectmode="browse")

        headings = {
            "sid":          (t("enrollment.col_student_id"),  90),
            "student_name": (t("enrollment.col_name"),       140),
            "course_code":  (t("enrollment.col_course"),      80),
            "course_title": (t("enrollment.col_title"),      160),
            "status":       (t("enrollment.col_status"),      80),
            "enrolled_at":  (t("enrollment.col_date"),       130),
        }
        for col, (heading, width) in headings.items():
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Waitlist panel
        wl_lf = tk.LabelFrame(content, text=t("enrollment.waitlist"), bg="#ecf0f1",
                              font=("Helvetica", 10, "bold"))
        wl_lf.grid(row=0, column=1, sticky="nsew")

        wl_inner = tk.Frame(wl_lf, bg="#ecf0f1")
        wl_inner.pack(fill="both", expand=True, padx=4, pady=4)

        tk.Label(wl_inner, text=t("enrollment.course_code_colon"), bg="#ecf0f1").pack(anchor="w")
        self._wl_course_var = tk.StringVar()
        wl_row = tk.Frame(wl_inner, bg="#ecf0f1")
        wl_row.pack(anchor="w", fill="x", pady=(0, 4))
        ttk.Entry(wl_row, textvariable=self._wl_course_var, width=16).pack(side="left")
        ttk.Button(wl_row, text="Browse…", width=8,
                   command=self._pick_waitlist_course).pack(side="left", padx=(2, 0))

        wl_btns = tk.Frame(wl_inner, bg="#ecf0f1")
        wl_btns.pack(anchor="w", fill="x", pady=(0, 8))
        ttk.Button(wl_btns, text=t("enrollment.view_waitlist"),
                   command=self._on_view_waitlist).pack(side="left", padx=(0, 4))
        ttk.Button(wl_btns, text="Promote", command=self._on_promote_waitlist).pack(
            side="left", padx=4)
        ttk.Button(wl_btns, text="Export CSV",
                   command=self._export_waitlist_csv).pack(side="left", padx=4)

        wl_cols = ("position", "sid", "name")
        self._wl_tree = ttk.Treeview(wl_inner, columns=wl_cols,
                                     show="headings", height=8)
        for col, heading, w in [("position", "#", 40),
                                ("sid", t("enrollment.col_student_id"), 90),
                                ("name", t("enrollment.col_name"), 130)]:
            self._wl_tree.heading(col, text=heading)
            self._wl_tree.column(col, width=w, anchor="center")
        self._wl_tree.pack(fill="both", expand=True)

    def _build_action_toolbar(self):
        bar = tk.Frame(self, bg="#ecf0f1")
        bar.pack(fill="x", padx=15, pady=(2, 4))
        ttk.Button(bar, text="View Selected",
                   command=self._on_view_selected_enrollment).pack(side="left", padx=4)
        ttk.Button(bar, text="Drop Selected",
                   command=self._on_drop_selected).pack(side="left", padx=4)
        ttk.Button(bar, text="Export CSV", command=self._export_csv).pack(
            side="right", padx=4)

    def _build_pagination_and_status(self):
        pag_frame = tk.Frame(self, bg="#ecf0f1")
        pag_frame.pack(fill="x", padx=15, pady=(0, 4))

        self._prev_btn = ttk.Button(pag_frame, text=t("common.previous", "Previous"),
                                     command=self._prev_page, state="disabled")
        self._prev_btn.pack(side="left", padx=4)

        self._page_label_var = tk.StringVar(
            value=t("common.page_x_of_y", "Page {current} of {total}",
                    current=1, total=1))
        tk.Label(pag_frame, textvariable=self._page_label_var,
                 bg="#ecf0f1", font=("Helvetica", 9)).pack(side="left", padx=8)

        self._next_btn = ttk.Button(pag_frame, text=t("common.next", "Next"),
                                     command=self._next_page, state="disabled")
        self._next_btn.pack(side="left", padx=4)

        self._record_count_var = tk.StringVar(value="")
        tk.Label(pag_frame, textvariable=self._record_count_var,
                 bg="#ecf0f1", font=("Helvetica", 9), fg="#7f8c8d").pack(
            side="right", padx=8)

        self._status_var = tk.StringVar(value=t("common.ready"))
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1",
                 anchor="w", font=("Helvetica", 9), fg="#7f8c8d").pack(
            fill="x", padx=15, pady=(0, 8))

    def _bind_shortcuts(self):
        self._tree.bind("<Return>", lambda _e: self._on_view_selected_enrollment())
        self._tree.bind("<Delete>", lambda _e: self._on_drop_selected())
        self._tree.bind("<Double-1>", lambda _e: self._on_view_selected_enrollment())
        self._bind_when_visible("<Control-n>", lambda _e: self._on_enroll())
        self._bind_when_visible("<Control-f>", lambda _e: self._focus_search())

    def _bind_when_visible(self, sequence, callback):
        def _handler(event):
            if self.winfo_ismapped():
                callback(event)
                return "break"
        self.bind(sequence, _handler)
        top = self.winfo_toplevel()
        top.bind(sequence, _handler, add=True)

    def _focus_search(self):
        self._search_entry.focus_set()
        self._search_entry.select_range(0, tk.END)

    # ------------------------------------------------------------------
    # Selection-driven actions
    # ------------------------------------------------------------------

    def _selected_row_values(self) -> tuple | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"),
                                   "Please select an enrollment first.")
            return None
        return self._tree.item(sel[0], "values")

    def _on_view_selected_enrollment(self):
        values = self._selected_row_values()
        if not values:
            return
        detail = (
            f"Student ID: {values[0]}\n"
            f"Name: {values[1]}\n"
            f"Course: {values[2]} - {values[3]}\n"
            f"Status: {values[4]}\n"
            f"Enrolled: {values[5]}"
        )
        messagebox.showinfo("Enrollment Details", detail)

    def _on_drop_selected(self):
        values = self._selected_row_values()
        if not values:
            return
        self._student_id_var.set(values[0])
        self._course_code_var.set(values[2])
        self._on_drop()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _safe_load(self, label: str, fn, default):
        """Run ``fn()``; on failure log + warn the user and return ``default``."""
        try:
            return fn()
        except Exception as exc:
            logger.exception("Failed to load %s", label)
            messagebox.showerror(t("common.error"),
                                 f"Failed to load {label}:\n{exc}")
            return default

    def refresh(self):
        self._load_enrollments()

    def _load_enrollments(self):
        self._tree.delete(*self._tree.get_children())
        kwargs = dict(
            status=self._current_status_filter,
            search=self._current_search,
            student_pk=self._filter_student["id"] if self._filter_student else None,
            course_pk=self._filter_course["id"] if self._filter_course else None,
        )
        try:
            self._total_count = self._enrollment_svc.count_enrollments(**kwargs)
            enrollments = self._enrollment_svc.list_enrollments(
                limit=self._page_size,
                offset=self._page * self._page_size,
                **kwargs,
            )
        except Exception as exc:
            logger.exception("Failed to load enrollments (filters=%s)", kwargs)
            messagebox.showerror(t("common.error"),
                                 f"Failed to load enrollments:\n{exc}")
            return

        for e in enrollments:
            name = f"{e.get('first_name', '')} {e.get('last_name', '')}".strip()
            self._tree.insert("", "end", values=(
                e.get("sid", ""),
                name,
                e.get("course_code", ""),
                e.get("title", ""),
                e.get("status", ""),
                e.get("enrolled_at", ""),
            ))

        self._update_pagination()
        count = len(enrollments)
        self._status_var.set(t("enrollment.count_loaded", count=count))

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def _update_pagination(self):
        total_pages = max(1, (self._total_count + self._page_size - 1) // self._page_size)
        current = self._page + 1
        self._page_label_var.set(
            t("common.page_x_of_y", "Page {current} of {total}",
              current=current, total=total_pages))

        if self._total_count == 0:
            self._record_count_var.set(t("common.no_records", "No records"))
        else:
            start = self._page * self._page_size + 1
            end = min((self._page + 1) * self._page_size, self._total_count)
            self._record_count_var.set(t(
                "common.showing_x_y_of_z",
                "Showing {start}-{end} of {total} records",
                start=start, end=end, total=self._total_count,
            ))

        self._prev_btn.configure(
            state="normal" if self._page > 0 else "disabled")
        self._next_btn.configure(
            state="normal" if current < total_pages else "disabled")

    def _next_page(self):
        self._page += 1
        self._load_enrollments()

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
        self._load_enrollments()

    # ------------------------------------------------------------------
    # Filters / search
    # ------------------------------------------------------------------

    def _on_search(self):
        self._current_search = self._search_var.get().strip() or None
        self._page = 0
        self._load_enrollments()

    def _on_clear_search(self):
        self._search_var.set("")
        self._current_search = None
        self._page = 0
        self._load_enrollments()

    def _on_status_filter_change(self):
        val = self._status_filter_var.get()
        self._current_status_filter = None if val == "All" else val
        self._page = 0
        self._load_enrollments()

    def _set_student_filter(self):
        student = self._open_student_picker("Filter by Student")
        if not student:
            return
        self._filter_student = student
        self._filter_student_var.set(
            f"{student.get('student_id', '')} — "
            f"{student.get('first_name', '')} {student.get('last_name', '')}")
        self._page = 0
        self._load_enrollments()

    def _clear_student_filter(self):
        if not self._filter_student:
            return
        self._filter_student = None
        self._filter_student_var.set("All students")
        self._page = 0
        self._load_enrollments()

    def _set_course_filter(self):
        course = self._open_course_picker("Filter by Course")
        if not course:
            return
        self._filter_course = course
        self._filter_course_var.set(
            f"{course.get('course_code', '')} — {course.get('title', '')}")
        self._page = 0
        self._load_enrollments()

    def _clear_course_filter(self):
        if not self._filter_course:
            return
        self._filter_course = None
        self._filter_course_var.set("All courses")
        self._page = 0
        self._load_enrollments()

    # ------------------------------------------------------------------
    # Pickers
    # ------------------------------------------------------------------

    def _open_student_picker(self, title: str) -> dict | None:
        students = self._safe_load(
            "students", lambda: self._student_svc.list_students(limit=10000), [])
        if not students:
            messagebox.showinfo("Pick student", "No students found.")
            return None

        def _disp(s):
            return (f"{s.get('student_id', ''):<8}  "
                    f"{(s.get('first_name') or ''):<15s} "
                    f"{(s.get('last_name') or ''):<15s}  "
                    f"Year {s.get('year_group') or '-'}")

        def _haystack(s):
            return " ".join(str(s.get(k) or "") for k in
                            ("student_id", "first_name", "last_name",
                             "form_group", "year_group"))

        dlg = _SearchPickerDialog(self, title, students, _disp, _haystack)
        self.wait_window(dlg)
        return dlg.result

    def _open_course_picker(self, title: str) -> dict | None:
        courses = self._safe_load(
            "courses",
            lambda: self._course_svc.list_courses(status="active", limit=10000),
            [])
        if not courses:
            messagebox.showinfo("Pick course", "No active courses found.")
            return None

        def _disp(c):
            return (f"{c.get('course_code', ''):<10}  "
                    f"{(c.get('title') or '')[:40]:<40s}  "
                    f"cap {c.get('capacity', '-')}")

        def _haystack(c):
            return " ".join(str(c.get(k) or "") for k in
                            ("course_code", "title", "subject_area",
                             "department", "instructor", "term"))

        dlg = _SearchPickerDialog(self, title, courses, _disp, _haystack)
        self.wait_window(dlg)
        return dlg.result

    def _pick_student(self):
        student = self._open_student_picker("Select Student")
        if student:
            self._student_id_var.set(student.get("student_id", ""))

    def _pick_course(self):
        course = self._open_course_picker("Select Course")
        if course:
            self._course_code_var.set(course.get("course_code", ""))

    def _pick_waitlist_course(self):
        course = self._open_course_picker("Select Course (Waitlist)")
        if course:
            self._wl_course_var.set(course.get("course_code", ""))

    def _on_clear_form(self):
        self._student_id_var.set("")
        self._course_code_var.set("")

    # ------------------------------------------------------------------
    # Resolve helpers (lookup by code/id with friendly errors and logging)
    # ------------------------------------------------------------------

    def _resolve_ids(self):
        """Resolve the student-id / course-code entries to PKs.

        Both inputs are case-folded so a typo like ``sfc0002`` or ``cs101``
        resolves the same as the canonical form.
        """
        sid_str = self._student_id_var.get().strip().upper()
        code_str = self._course_code_var.get().strip().upper()

        if not sid_str or not code_str:
            raise EnrollmentError("Both student ID and course code are required.")

        try:
            student = self._student_svc.get_student_by_student_id(sid_str)
        except Exception as exc:
            logger.exception("Lookup failed for student '%s'", sid_str)
            raise EnrollmentError(f"Failed to look up student '{sid_str}': {exc}") from exc
        if not student:
            raise EnrollmentError(f"Student '{sid_str}' not found.")

        try:
            course = self._course_svc.get_course_by_code(code_str)
        except Exception as exc:
            logger.exception("Lookup failed for course '%s'", code_str)
            raise EnrollmentError(f"Failed to look up course '{code_str}': {exc}") from exc
        if not course:
            raise EnrollmentError(f"Course '{code_str}' not found.")

        return student["id"], course["id"]

    # ------------------------------------------------------------------
    # Enroll / Drop / Promote
    # ------------------------------------------------------------------

    def _on_enroll(self):
        try:
            student_pk, course_pk = self._resolve_ids()
            result = self._enrollment_svc.enroll_student(student_pk, course_pk)
        except EnrollmentError as exc:
            logger.warning("Enroll rejected: %s", exc)
            messagebox.showerror(t("enrollment.error"), str(exc))
            return
        except Exception as exc:
            logger.exception("Unexpected error enrolling student")
            messagebox.showerror(t("common.error"), f"Unexpected error:\n{exc}")
            return

        status = result.get("status", "unknown")
        if status == "waitlisted":
            messagebox.showinfo(
                t("enrollment.waitlisted"),
                t("enrollment.waitlisted_msg", position=result.get("position", "?")),
            )
        else:
            messagebox.showinfo(t("enrollment.enrolled"),
                                t("enrollment.enrolled_msg"))

        self._load_enrollments()
        self._status_var.set(t("common.ready"))

    def _on_drop(self):
        try:
            student_pk, course_pk = self._resolve_ids()
        except EnrollmentError as exc:
            logger.warning("Drop rejected (resolve): %s", exc)
            messagebox.showerror(t("common.error"), str(exc))
            return

        if not messagebox.askyesno(t("enrollment.confirm_drop"),
                                   t("enrollment.confirm_drop_msg")):
            return

        try:
            result = self._enrollment_svc.drop_student(student_pk, course_pk)
        except EnrollmentError as exc:
            logger.warning("Drop rejected by service: %s", exc)
            messagebox.showerror(t("enrollment.drop_error"), str(exc))
            return
        except Exception as exc:
            logger.exception("Unexpected error dropping student")
            messagebox.showerror(t("common.error"), f"Unexpected error:\n{exc}")
            return

        msg = t("enrollment.dropped_msg")
        if result.get("promoted_student_pk"):
            msg += "\n" + t("enrollment.promoted_msg")
        messagebox.showinfo(t("enrollment.dropped"), msg)
        self._load_enrollments()
        self._status_var.set(t("common.ready"))

    def _on_promote_waitlist(self):
        code = self._wl_course_var.get().strip().upper()
        if not code:
            messagebox.showwarning(t("common.input"), t("enrollment.enter_course_code"))
            return
        try:
            course = self._course_svc.get_course_by_code(code)
        except Exception as exc:
            logger.exception("Course lookup failed for promote: %s", code)
            messagebox.showerror(t("common.error"),
                                 f"Failed to look up course '{code}': {exc}")
            return
        if not course:
            messagebox.showerror(t("common.error"), f"Course '{code}' not found.")
            return

        if not messagebox.askyesno(
            "Promote from waitlist",
            f"Promote the next student from the waitlist for {code}?"):
            return

        try:
            promoted_pk = self._enrollment_svc.promote_from_waitlist(course["id"])
        except EnrollmentError as exc:
            logger.warning("Promote rejected: %s", exc)
            messagebox.showerror(t("common.error"), str(exc))
            return
        except Exception as exc:
            logger.exception("Unexpected error promoting from waitlist for %s", code)
            messagebox.showerror(t("common.error"), f"Unexpected error:\n{exc}")
            return

        if promoted_pk is None:
            messagebox.showinfo("Promote from waitlist",
                                f"The waitlist for {code} is empty.")
            return

        # Look up the promoted student's display id for the toast.
        try:
            student = self._student_svc.get_student(promoted_pk)
            sid = student["student_id"] if student else f"pk={promoted_pk}"
        except Exception:
            logger.warning("Could not resolve promoted student pk=%s", promoted_pk,
                           exc_info=True)
            sid = f"pk={promoted_pk}"

        messagebox.showinfo("Promote from waitlist",
                            f"Promoted student {sid} into {code}.")
        self._load_enrollments()
        self._on_view_waitlist()
        self._status_var.set(t("common.ready"))

    # ------------------------------------------------------------------
    # Waitlist sidebar
    # ------------------------------------------------------------------

    def _on_view_waitlist(self):
        code = self._wl_course_var.get().strip().upper()
        if not code:
            messagebox.showwarning(t("common.input"), t("enrollment.enter_course_code"))
            return

        try:
            course = self._course_svc.get_course_by_code(code)
        except Exception as exc:
            logger.exception("Waitlist course lookup failed: %s", code)
            messagebox.showerror(t("common.error"),
                                 f"Failed to look up course '{code}': {exc}")
            return
        if not course:
            messagebox.showerror(t("common.error"), f"Course '{code}' not found.")
            return

        self._wl_tree.delete(*self._wl_tree.get_children())
        try:
            waitlist = self._enrollment_svc.get_waitlist(course["id"])
        except Exception as exc:
            logger.exception("Failed to load waitlist for %s (pk=%s)",
                             code, course["id"])
            messagebox.showerror(t("common.error"),
                                 f"Failed to load waitlist:\n{exc}")
            return

        for w in waitlist:
            name = f"{w.get('first_name', '')} {w.get('last_name', '')}".strip()
            self._wl_tree.insert("", "end", values=(
                w.get("position", ""),
                w.get("sid", ""),
                name,
            ))

        if not waitlist:
            self._status_var.set(t(
                "enrollment.waitlist_empty",
                "No students on waitlist for {code}",
                code=code,
            ))
        else:
            self._status_var.set(t(
                "enrollment.waitlist_count",
                "{count} student(s) on waitlist for {code}",
                count=len(waitlist), code=code,
            ))

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        try:
            export_treeview_to_csv(self._tree, default_filename="enrollments.csv")
        except Exception as exc:
            logger.exception("Enrollment CSV export failed")
            messagebox.showerror(t("common.error"), f"Export failed:\n{exc}")

    def _export_waitlist_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        if not self._wl_tree.get_children():
            messagebox.showinfo("Export", "The waitlist is empty — nothing to export.")
            return
        code = (self._wl_course_var.get().strip().lower() or "course")
        try:
            export_treeview_to_csv(
                self._wl_tree, default_filename=f"waitlist_{code}.csv")
        except Exception as exc:
            logger.exception("Waitlist CSV export failed")
            messagebox.showerror(t("common.error"), f"Export failed:\n{exc}")
