"""Student management GUI for the Sixth Form College Management System.

The dialog is laid out to mirror the university system CRUD dialog: a
scrollable form with sectioned ``LabelFrame``s ("Personal Information",
"Academic Information") and an inline validation feedback strip, rather
than a flat grid of entries. Email is no longer a user input — it is
auto-generated from the student id.
"""

import logging
import random
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.students.services.student_service import StudentService
from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.modules.domain.enrollment.services.enrollment_service import EnrollmentService
from education_system.college_system.modules.domain.staff.services.staff_service import StaffService
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.core.exceptions import StudentError, ValidationError, EnrollmentError, AuthError
from education_system.college_system.core.i18n import t
from education_system.secondary_school.core.paths import DB_FILE as SECONDARY_DB_FILE

logger = logging.getLogger(__name__)


class _StudentDialog(tk.Toplevel):
    """Modal dialog for adding or editing a student record.

    Visual layout mirrors the university student CRUD dialog: title at the
    top, sectioned ``LabelFrame``s inside a scrollable canvas, and an inline
    red validation label above the buttons.
    """

    TITLES = ["", "Mr", "Ms", "Mrs", "Miss", "Mx", "Dr"]
    GENDERS = ["", "male", "female", "other", "prefer_not_to_say"]

    def __init__(self, parent, title="Student", student=None,
                 courses: list[dict] | None = None,
                 form_groups: list[str] | None = None,
                 form_tutors: list[dict] | None = None):
        super().__init__(parent)
        self.title(title)
        self._dialog_title = title
        self.geometry("640x720")
        self.minsize(560, 600)
        self.grab_set()

        self.result: dict | None = None
        self._student = student
        self._courses = courses
        self._form_groups = form_groups or []
        self._form_tutors = form_tutors or []
        self._imported_secondary_student = None
        self._vars: dict[str, tk.StringVar] = {}
        self._course_vars: list[tk.StringVar] = []
        self._status_var: tk.StringVar | None = None
        self._validation_var = tk.StringVar(value="")

        self._build_ui()
        self._center_on_parent(parent)
        self.bind("<Escape>", lambda e: self.destroy())

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------

    def _center_on_parent(self, parent):
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width() // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        w = self.winfo_width()
        h = self.winfo_height()
        self.geometry(f"+{pw - w // 2}+{ph - h // 2}")

    def _build_ui(self):
        # Outer frame holds a scrollable canvas + a fixed footer.
        outer = ttk.Frame(self)
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        body = ttk.Frame(canvas, padding=15)
        body_id = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(body_id, width=e.width),
        )

        # Title bar
        ttk.Label(
            body, text=self._dialog_title, font=("Helvetica", 16, "bold"),
        ).grid(row=0, column=0, columnspan=2, pady=(0, 12), sticky="w")

        # Import button (add mode only)
        if not self._student:
            ttk.Button(
                body, text="Import from Secondary School",
                command=self._import_from_secondary,
            ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self._build_personal_section(body, row=2)
        self._build_academic_section(body, row=3)

        # Inline validation feedback (matches university dialog).
        ttk.Label(
            body, textvariable=self._validation_var, foreground="red",
            font=("Helvetica", 9, "italic"), wraplength=560, justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="we", pady=(8, 0))

        # Footer buttons (always visible, outside the scroll region).
        footer = ttk.Frame(self, padding=(15, 8, 15, 12))
        footer.pack(fill="x", side="bottom")
        ttk.Button(footer, text=t("common.save"), command=self._on_save).pack(
            side="right", padx=4)
        ttk.Button(footer, text=t("common.cancel"), command=self.destroy).pack(
            side="right", padx=4)

    def _build_personal_section(self, parent, row: int):
        frame = ttk.LabelFrame(parent, text="Personal Information", padding=12)
        frame.grid(row=row, column=0, columnspan=2, sticky="we", pady=(0, 10))
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        student = self._student or {}

        def _str_var(key, default=""):
            v = tk.StringVar(value=str(student.get(key) or default))
            self._vars[key] = v
            return v

        # Title (combobox) | Gender (combobox)
        ttk.Label(frame, text="Title").grid(row=0, column=0, sticky="w", pady=4)
        ttk.Combobox(
            frame, textvariable=_str_var("title"),
            values=self.TITLES, state="readonly", width=14,
        ).grid(row=0, column=1, sticky="w", padx=(8, 16), pady=4)

        ttk.Label(frame, text="Gender").grid(row=0, column=2, sticky="w", pady=4)
        ttk.Combobox(
            frame, textvariable=_str_var("gender"),
            values=self.GENDERS, state="readonly", width=18,
        ).grid(row=0, column=3, sticky="we", padx=(8, 0), pady=4)

        # First / Middle / Last name
        ttk.Label(frame, text="First name *").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=_str_var("first_name")).grid(
            row=1, column=1, sticky="we", padx=(8, 16), pady=4)

        ttk.Label(frame, text="Middle name").grid(row=1, column=2, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=_str_var("middle_name")).grid(
            row=1, column=3, sticky="we", padx=(8, 0), pady=4)

        ttk.Label(frame, text="Last name *").grid(row=2, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=_str_var("last_name")).grid(
            row=2, column=1, sticky="we", padx=(8, 16), pady=4)

        # DOB | Phone
        ttk.Label(frame, text="Date of birth (YYYY-MM-DD)").grid(
            row=3, column=0, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=_str_var("date_of_birth")).grid(
            row=3, column=1, sticky="we", padx=(8, 16), pady=4)

        ttk.Label(frame, text="Phone").grid(row=3, column=2, sticky="w", pady=4)
        ttk.Entry(frame, textvariable=_str_var("phone")).grid(
            row=3, column=3, sticky="we", padx=(8, 0), pady=4)

        # Address (full width)
        ttk.Label(frame, text="Address").grid(row=4, column=0, sticky="nw", pady=4)
        ttk.Entry(frame, textvariable=_str_var("address")).grid(
            row=4, column=1, columnspan=3, sticky="we", padx=(8, 0), pady=4)

        # Email is no longer collected from the user — it is auto-generated
        # from the student id (e.g. sfc0002@sixthform.ac.uk).
        note = (
            "Email will be auto-generated from the student ID "
            f"(e.g. SFC0002@{StudentService.EMAIL_DOMAIN})."
            if not self._student
            else f"Email: {student.get('email') or '(auto-generated)'}"
        )
        ttk.Label(frame, text=note, foreground="#2c3e50",
                  font=("Helvetica", 9, "italic")).grid(
            row=5, column=0, columnspan=4, sticky="w", pady=(8, 0))

    def _build_academic_section(self, parent, row: int):
        frame = ttk.LabelFrame(parent, text="Academic Information", padding=12)
        frame.grid(row=row, column=0, columnspan=2, sticky="we")
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(3, weight=1)

        student = self._student or {}

        # Year group
        ttk.Label(frame, text="Year group").grid(row=0, column=0, sticky="w", pady=4)
        self._vars["year_group"] = tk.StringVar(value=student.get("year_group") or "12")
        ttk.Combobox(
            frame, textvariable=self._vars["year_group"],
            values=["12", "13"], state="readonly", width=10,
        ).grid(row=0, column=1, sticky="w", padx=(8, 16), pady=4)

        # Form group
        ttk.Label(frame, text="Form group").grid(row=0, column=2, sticky="w", pady=4)
        self._vars["form_group"] = tk.StringVar(value=student.get("form_group") or "")
        fg_values = [""] + (self._form_groups if self._form_groups
                            else ["12A", "12B", "12C", "12D",
                                  "13A", "13B", "13C", "13D"])
        ttk.Combobox(
            frame, textvariable=self._vars["form_group"],
            values=fg_values, width=18,
        ).grid(row=0, column=3, sticky="we", padx=(8, 0), pady=4)

        # Form tutor
        ttk.Label(frame, text="Form tutor").grid(row=1, column=0, sticky="w", pady=4)
        self._vars["form_tutor"] = tk.StringVar(value=student.get("form_tutor") or "")
        tutor_names = [""]
        for tutor in self._form_tutors:
            tt = tutor.get("title") or ""
            tutor_names.append(
                f"{tt} {tutor['first_name']} {tutor['last_name']}".strip()
            )
        ttk.Combobox(
            frame, textvariable=self._vars["form_tutor"],
            values=tutor_names,
        ).grid(row=1, column=1, columnspan=3, sticky="we",
               padx=(8, 0), pady=4)

        # Course pickers (add mode only).
        if not self._student and self._courses:
            course_values = [t("student.none_selected")] + [
                f"{c['course_code']} - {c['title']}" for c in self._courses
            ]
            for i in range(3):
                r = 2 + i
                ttk.Label(frame, text=f"Course {i + 1}").grid(
                    row=r, column=0, sticky="w", pady=4)
                var = tk.StringVar(value=t("student.none_selected"))
                ttk.Combobox(
                    frame, textvariable=var, values=course_values,
                    state="readonly",
                ).grid(row=r, column=1, columnspan=3, sticky="we",
                       padx=(8, 0), pady=4)
                self._course_vars.append(var)

        # Status (edit mode only).
        if self._student:
            ttk.Label(frame, text="Status").grid(row=5, column=0, sticky="w", pady=4)
            self._status_var = tk.StringVar(value=student.get("status", "active"))
            ttk.Combobox(
                frame, textvariable=self._status_var,
                values=["active", "inactive", "graduated", "suspended"],
                state="readonly", width=18,
            ).grid(row=5, column=1, sticky="w", padx=(8, 0), pady=4)

    # ------------------------------------------------------------------
    # Import-from-secondary picker
    # ------------------------------------------------------------------

    def _import_from_secondary(self):
        try:
            sec_students = StudentService(None).fetch_secondary_students(
                str(SECONDARY_DB_FILE))
        except Exception as e:
            logger.exception("Failed to load secondary school students for import")
            messagebox.showerror("Error", f"Could not load secondary school students:\n{e}")
            return
        if not sec_students:
            messagebox.showinfo("Import", "No active students found in the secondary school system.")
            return

        sel_dlg = tk.Toplevel(self)
        sel_dlg.title("Select Secondary School Student")
        sel_dlg.geometry("550x400")
        sel_dlg.transient(self)
        sel_dlg.grab_set()
        tk.Label(sel_dlg, text="Select a student from the Secondary School:",
                 font=('Helvetica', 11, 'bold')).pack(padx=10, pady=(10, 5))
        srch_frame = tk.Frame(sel_dlg)
        srch_frame.pack(fill="x", padx=10)
        tk.Label(srch_frame, text="Search:").pack(side="left")
        srch_var = tk.StringVar()
        ttk.Entry(srch_frame, textvariable=srch_var, width=30).pack(side="left", padx=5)
        lf = tk.Frame(sel_dlg)
        lf.pack(fill="both", expand=True, padx=10, pady=5)
        lb_scroll = tk.Scrollbar(lf)
        lb_scroll.pack(side="right", fill="y")
        lb = tk.Listbox(lf, yscrollcommand=lb_scroll.set, font=('Courier', 10))
        lb.pack(fill="both", expand=True)
        lb_scroll.config(command=lb.yview)
        _stu_map: dict[int, dict] = {}

        def _populate(ft=""):
            lb.delete(0, tk.END)
            _stu_map.clear()
            for s in sec_students:
                name = f"{s['first_name']} {s['last_name']}"
                if ft and ft.lower() not in name.lower() and ft.lower() not in (s['student_id'] or '').lower():
                    continue
                pos = lb.size()
                lb.insert(tk.END, f"{s['student_id']}  {s['first_name']:15s} {s['last_name']:15s}  DOB: {s['date_of_birth'] or 'N/A'}")
                _stu_map[pos] = s

        _populate()
        srch_var.trace_add("write", lambda *_: _populate(srch_var.get()))

        def _on_pick():
            sel = lb.curselection()
            if not sel:
                messagebox.showwarning("Selection", "Please select a student.", parent=sel_dlg)
                return
            s = _stu_map[sel[0]]
            self._vars['first_name'].set(s['first_name'] or '')
            self._vars['last_name'].set(s['last_name'] or '')
            if s['date_of_birth']:
                self._vars['date_of_birth'].set(s['date_of_birth'])
            if s['address']:
                self._vars['address'].set(s['address'])
            if s['parent_phone']:
                self._vars['phone'].set(s['parent_phone'])
            self._imported_secondary_student = dict(s)
            sel_dlg.destroy()

        bf = tk.Frame(sel_dlg)
        bf.pack(pady=10)
        ttk.Button(bf, text="Select & Import", command=_on_pick).pack(side="left", padx=5)
        ttk.Button(bf, text="Cancel", command=sel_dlg.destroy).pack(side="left", padx=5)

    # ------------------------------------------------------------------
    # Save / validation
    # ------------------------------------------------------------------

    def _validate(self, data: dict) -> list[str]:
        errors: list[str] = []
        if not data.get("first_name"):
            errors.append("First name is required.")
        if not data.get("last_name"):
            errors.append("Last name is required.")
        dob = data.get("date_of_birth")
        if dob:
            try:
                datetime.strptime(dob, "%Y-%m-%d")
            except ValueError:
                errors.append("Date of birth must be YYYY-MM-DD.")
        return errors

    def _on_save(self):
        data = {k: v.get().strip() for k, v in self._vars.items()}
        errors = self._validate(data)
        if errors:
            self._validation_var.set(" • ".join(errors))
            return
        self._validation_var.set("")

        if self._imported_secondary_student:
            data["_imported_secondary_student"] = self._imported_secondary_student
        if self._status_var:
            data["status"] = self._status_var.get()

        if self._course_vars and self._courses:
            selected_ids: list[int] = []
            for var in self._course_vars:
                val = var.get()
                if val and val != t("student.none_selected"):
                    code = val.split(" - ")[0]
                    for c in self._courses:
                        if c["course_code"] == code:
                            selected_ids.append(c["id"])
                            break
            if len(selected_ids) != len(set(selected_ids)):
                self._validation_var.set("The same course is selected more than once.")
                return
            data["selected_course_ids"] = selected_ids

        self.result = data
        self.destroy()


class StudentFrame(tk.Frame):
    """Student management screen with Treeview and CRUD controls."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = StudentService(db_path)
        self._course_svc = CourseService(db_path)
        self._enrollment_svc = EnrollmentService(db_path)
        self._staff_svc = StaffService(db_path)

        # Pagination state
        self._page = 0
        self._page_size = 50
        self._total_count = 0
        self._current_search: str | None = None

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
        tk.Label(header, text=t("student.management"), font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        # Toolbar
        toolbar = tk.Frame(self, bg="#ecf0f1", pady=8)
        toolbar.pack(fill="x", padx=15)

        ttk.Button(toolbar, text=t("student.add"), command=self._on_add).pack(
            side="left", padx=4)
        ttk.Button(toolbar, text=t("common.edit_selected"), command=self._on_edit).pack(
            side="left", padx=4)
        ttk.Button(toolbar, text=t("common.delete_selected"), command=self._on_delete).pack(
            side="left", padx=4)

        # Search
        tk.Label(toolbar, text=t("common.search_colon"), bg="#ecf0f1").pack(side="left", padx=(20, 4))
        self._search_var = tk.StringVar()
        self._search_entry = ttk.Entry(toolbar, textvariable=self._search_var, width=24)
        self._search_entry.pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.go"), command=self._on_search).pack(side="left", padx=4)
        ttk.Button(toolbar, text=t("common.clear"), command=self._on_clear_search).pack(
            side="left", padx=4)
        ttk.Button(toolbar, text="Export CSV", command=self._export_csv).pack(
            side="right", padx=4)
        self._search_entry.bind("<Return>", lambda _e: self._on_search())

        # Treeview
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columns = ("student_id", "first_name", "last_name", "year_group", "form_group", "status")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                  selectmode="browse")

        headings = {
            "student_id": (t("student.col_student_id"), 100),
            "first_name": (t("student.col_first_name"), 130),
            "last_name":  (t("student.col_last_name"),  130),
            "year_group": (t("student.col_year"),        60),
            "form_group": (t("student.col_form"),        80),
            "status":     (t("student.col_status"),     100),
        }
        for col, (heading, width) in headings.items():
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Admin/staff: double-click a row to view full student details
        self._tree.bind("<Double-1>", self._on_double_click_student)

        # Pagination bar
        self._pag_frame = tk.Frame(self, bg="#ecf0f1")
        self._pag_frame.pack(fill="x", padx=15, pady=(0, 4))

        self._prev_btn = ttk.Button(self._pag_frame, text="Previous",
                                     command=self._prev_page, state="disabled")
        self._prev_btn.pack(side="left", padx=4)

        self._page_label_var = tk.StringVar(value="Page 1 of 1")
        tk.Label(self._pag_frame, textvariable=self._page_label_var,
                 bg="#ecf0f1", font=("Helvetica", 9)).pack(side="left", padx=8)

        self._next_btn = ttk.Button(self._pag_frame, text="Next",
                                     command=self._next_page, state="disabled")
        self._next_btn.pack(side="left", padx=4)

        self._record_count_var = tk.StringVar(value="")
        tk.Label(self._pag_frame, textvariable=self._record_count_var,
                 bg="#ecf0f1", font=("Helvetica", 9), fg="#7f8c8d").pack(
            side="right", padx=8)

        # Status bar
        self._status_var = tk.StringVar(value=t("common.ready"))
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(
            fill="x", padx=15, pady=(0, 8))

        # --- Keyboard shortcuts for accessibility ---
        self._tree.bind("<Return>", lambda e: self._on_edit())
        self._tree.bind("<Delete>", lambda e: self._on_delete())
        self.bind_all_for_frame("<Control-f>", lambda e: self._focus_search())
        self.bind_all_for_frame("<Control-n>", lambda e: self._on_add())

    def bind_all_for_frame(self, sequence, callback):
        """Bind a keyboard shortcut that only fires when this frame is visible."""
        def _handler(event):
            if self.winfo_ismapped():
                callback(event)
                return "break"
        self.bind(sequence, _handler)
        # Also bind on the top-level so it works regardless of focus
        top = self.winfo_toplevel()
        top.bind(sequence, _handler, add=True)

    def _focus_search(self):
        """Move keyboard focus to the search entry."""
        self._search_entry.focus_set()
        self._search_entry.select_range(0, tk.END)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def refresh(self):
        """Reload the student list from the database."""
        self._load_students()

    def _load_students(self, search: str | None = None):
        if search is not None:
            self._current_search = search
        self._tree.delete(*self._tree.get_children())
        try:
            self._total_count = self._svc.count_students(
                search=self._current_search)
            students = self._svc.list_students(
                search=self._current_search,
                limit=self._page_size,
                offset=self._page * self._page_size,
            )
        except Exception as exc:
            logger.exception("Failed to load students (search=%r)", self._current_search)
            messagebox.showerror(t("common.error"), f"Failed to load students:\n{exc}")
            return

        for s in students:
            self._tree.insert("", "end", iid=s["id"], values=(
                s.get("student_id", ""),
                s.get("first_name", ""),
                s.get("last_name", ""),
                s.get("year_group", "") or "",
                s.get("form_group", "") or "",
                s.get("status", ""),
            ))

        self._update_pagination()
        count = len(students)
        self._status_var.set(t("student.count_loaded", count=count))

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def _update_pagination(self):
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
        self._load_students()

    def _prev_page(self):
        if self._page > 0:
            self._page -= 1
        self._load_students()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _selected_pk(self) -> int | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning(t("common.selection_required"), t("student.select_first"))
            return None
        return int(sel[0])

    def _safe_load(self, label: str, fn, default):
        """Call ``fn()``; on failure log and return ``default``."""
        try:
            return fn()
        except Exception:
            logger.warning("Failed to load %s for student dialog", label, exc_info=True)
            return default

    def _on_add(self):
        courses = self._safe_load(
            "active courses",
            lambda: self._course_svc.list_courses(status="active"), [])
        form_groups = self._safe_load(
            "form groups", self._staff_svc.get_form_groups, [])
        staff_list = self._safe_load(
            "active staff",
            lambda: self._staff_svc.list_staff(status="active"), [])

        dlg = _StudentDialog(self, title="Add Student", courses=courses,
                             form_groups=form_groups, form_tutors=staff_list)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        data = dlg.result
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        if not first_name or not last_name:
            # Defensive — dialog already validates, but handler should not trust it.
            messagebox.showwarning(t("common.validation"), t("student.name_required"))
            return

        # 1. Create the student record (service auto-generates the email
        #    from the resulting student_id).
        try:
            student = self._svc.create_student(
                first_name=first_name,
                last_name=last_name,
                phone=data.get("phone") or None,
                date_of_birth=data.get("date_of_birth") or None,
                address=data.get("address") or None,
                year_group=data.get("year_group") or "12",
                form_group=data.get("form_group") or None,
                form_tutor=data.get("form_tutor") or None,
                title=data.get("title") or None,
                middle_name=data.get("middle_name") or None,
                gender=data.get("gender") or None,
            )
        except (StudentError, ValidationError) as exc:
            logger.warning("Student create rejected: %s", exc)
            messagebox.showerror(t("common.error"), str(exc))
            return
        except Exception as exc:
            logger.exception("Unexpected error creating student")
            messagebox.showerror(t("common.error"),
                                 f"Unexpected error creating student:\n{exc}")
            return

        student_id = student["student_id"]
        email = student["email"]
        username = student_id

        # 2. Create the user account in shared auth + local users table.
        digits = f"{random.randint(0, 9999):04d}"
        password = f"{first_name.capitalize()}{last_name.capitalize()}{digits}!"
        while len(password) < 12:
            password = f"Student{password}"

        try:
            UserAuth(self._db_path).create_user(
                username=username,
                password=password,
                email=email,
                systems=[("college", "student")],
            )
            from education_system.college_system.infrastructure.database.db import connect as college_connect
            from education_system.shared.auth.password_manager import hash_password
            local_conn = college_connect(self._db_path)
            try:
                local_conn.execute(
                    "INSERT INTO users (username, password_hash, role, email) "
                    "VALUES (?, ?, ?, ?)",
                    (username, hash_password(password), "student", email),
                )
                local_conn.commit()
                local_user_id = local_conn.execute(
                    "SELECT id FROM users WHERE username = ?", (username,),
                ).fetchone()["id"]
            finally:
                local_conn.close()
            self._svc.update_student(student["id"], user_id=local_user_id)
            logger.info("Student account created for %s (user_id=%s)",
                        student_id, local_user_id)
        except AuthError as exc:
            logger.warning("Auth account creation failed for %s: %s", student_id, exc)
            messagebox.showwarning(
                t("student.partial_success"),
                f"Student created ({student_id}) but account creation failed:\n{exc}",
            )
            self._load_students()
            return
        except Exception as exc:
            logger.exception("Unexpected error creating account for %s", student_id)
            messagebox.showwarning(
                t("student.partial_success"),
                f"Student created ({student_id}) but account creation failed:\n{exc}",
            )
            self._load_students()
            return

        # 3. Enroll in selected courses.
        selected_ids = data.get("selected_course_ids", [])
        enrolled = waitlisted = failed = 0
        for course_id in selected_ids:
            try:
                result = self._enrollment_svc.enroll_student(student["id"], course_id)
                if result["status"] == "enrolled":
                    enrolled += 1
                elif result["status"] == "waitlisted":
                    waitlisted += 1
            except EnrollmentError as exc:
                failed += 1
                logger.warning("Enrolment failed: student=%s course=%s err=%s",
                               student_id, course_id, exc)
            except Exception:
                failed += 1
                logger.exception("Unexpected enrolment error: student=%s course=%s",
                                 student_id, course_id)

        # 4. Show credentials and summary.
        parts = [
            "Student created successfully!\n",
            f"Student ID:  {student_id}",
            f"Username:    {username}",
            f"Password:    {password}",
            f"Email:       {email}",
        ]
        if selected_ids:
            summary = []
            if enrolled:
                summary.append(f"{enrolled} enrolled")
            if waitlisted:
                summary.append(f"{waitlisted} waitlisted")
            if failed:
                summary.append(f"{failed} failed")
            parts.append(f"\nCourses: {', '.join(summary)}")
        messagebox.showinfo(t("student.account_created"), "\n".join(parts))

        # 5. Transfer academic history from secondary school if imported.
        imported = data.get("_imported_secondary_student")
        if imported:
            try:
                self._svc.import_from_secondary(
                    student["id"], imported, str(SECONDARY_DB_FILE))
            except Exception:
                logger.exception("Failed to import academic history from secondary")

            imp_name = f"{imported.get('first_name', '')} {imported.get('last_name', '')}"
            if messagebox.askyesno(
                "Transfer Student",
                f"Mark {imp_name} as transferred in the Secondary School?",
            ):
                try:
                    self._svc.mark_secondary_as_transferred(
                        imported['id'], str(SECONDARY_DB_FILE))
                    logger.info(
                        "Secondary student %s (%s) transferred to college as %s",
                        imported.get('student_id', ''), imp_name, student_id)
                    self._svc.notify_transfer(
                        student_id, imported, self._auth, str(SECONDARY_DB_FILE))
                except Exception as exc:
                    logger.exception("Could not mark secondary student as transferred")
                    messagebox.showwarning(
                        "Import",
                        f"Student created but could not mark as transferred in secondary school:\n{exc}",
                    )

        self._load_students()

    def _on_edit(self):
        pk = self._selected_pk()
        if pk is None:
            return

        try:
            student = self._svc.get_student(pk)
        except Exception as exc:
            logger.exception("Failed to fetch student pk=%s", pk)
            messagebox.showerror(t("common.error"), f"Failed to load student:\n{exc}")
            return
        if not student:
            messagebox.showerror(t("common.error"), t("student.not_found"))
            return

        form_groups = self._safe_load(
            "form groups (edit)", self._staff_svc.get_form_groups, [])
        staff_list = self._safe_load(
            "active staff (edit)",
            lambda: self._staff_svc.list_staff(status="active"), [])

        dlg = _StudentDialog(self, title="Edit Student", student=student,
                             form_groups=form_groups, form_tutors=staff_list)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        data = dlg.result
        update_fields = {}
        for key in ("title", "first_name", "middle_name", "last_name",
                    "gender", "phone", "date_of_birth", "address",
                    "year_group", "form_group", "form_tutor", "status"):
            val = data.get(key)
            if val:
                update_fields[key] = val

        if not update_fields:
            return
        try:
            self._svc.update_student(pk, **update_fields)
            messagebox.showinfo(t("common.success"), t("student.updated"))
            self._load_students()
        except (StudentError, ValidationError) as exc:
            logger.warning("Student update rejected for pk=%s: %s", pk, exc)
            messagebox.showerror(t("common.error"), str(exc))
        except Exception as exc:
            logger.exception("Unexpected error updating student pk=%s", pk)
            messagebox.showerror(t("common.error"),
                                 f"Unexpected error updating student:\n{exc}")

    # ------------------------------------------------------------------
    # Details viewer (admin/staff double-click)
    # ------------------------------------------------------------------

    def _user_role(self) -> str:
        if self._auth and getattr(self._auth, "current_user", None):
            return self._auth.current_user.get("role", "")
        return ""

    def _on_double_click_student(self, _event=None):
        if self._user_role() not in ("admin", "staff", "instructor"):
            return
        sel = self._tree.selection()
        if not sel:
            return
        try:
            pk = int(sel[0])
        except (TypeError, ValueError):
            return
        self._show_student_details(pk)

    def _show_student_details(self, pk: int):
        try:
            student = self._svc.get_student(pk)
        except Exception as exc:
            logger.exception("Failed to load student details pk=%s", pk)
            messagebox.showerror(t("common.error"), f"Failed to load student:\n{exc}")
            return
        if not student:
            messagebox.showerror(t("common.error"), t("student.not_found"))
            return

        win = tk.Toplevel(self)
        win.title(f"Student Details — {student.get('student_id', '')}")
        win.geometry("700x600")
        win.transient(self.winfo_toplevel())

        notebook = ttk.Notebook(win)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        personal_tab = ttk.Frame(notebook)
        notebook.add(personal_tab, text="Personal")
        personal_text = tk.Text(personal_tab, wrap="word", font=("Courier", 10),
                                padx=15, pady=15, bd=0)
        personal_text.pack(fill="both", expand=True)

        na = "—"
        full_name = " ".join(p for p in (
            student.get("title"), student.get("first_name"),
            student.get("middle_name"), student.get("last_name"),
        ) if p) or na

        personal_lines = [
            "STUDENT RECORD",
            "=" * 60,
            "",
            "Personal Information",
            f"  Student ID:    {student.get('student_id') or na}",
            f"  Title:         {student.get('title') or na}",
            f"  First name:    {student.get('first_name') or na}",
            f"  Middle name:   {student.get('middle_name') or na}",
            f"  Last name:     {student.get('last_name') or na}",
            f"  Full name:     {full_name}",
            f"  Gender:        {student.get('gender') or na}",
            f"  Date of birth: {student.get('date_of_birth') or na}",
            "",
            "Contact",
            f"  Email:         {student.get('email') or na}",
            f"  Phone:         {student.get('phone') or na}",
            f"  Address:       {student.get('address') or na}",
            "",
            "Academic",
            f"  Year group:    {student.get('year_group') or na}",
            f"  Form group:    {student.get('form_group') or na}",
            f"  Form tutor:    {student.get('form_tutor') or na}",
            f"  Status:        {student.get('status') or na}",
            "",
            "Record",
            f"  Created:       {student.get('created_at') or na}",
            f"  Updated:       {student.get('updated_at') or na}",
        ]
        personal_text.insert("end", "\n".join(personal_lines))
        personal_text.config(state="disabled")

        enrol_tab = ttk.Frame(notebook)
        notebook.add(enrol_tab, text="Enrollments")
        enrol_tree = ttk.Treeview(
            enrol_tab,
            columns=("course_id", "course", "status", "enrolled_at"),
            show="headings",
        )
        for col, hd, w in [
            ("course_id", "Course ID", 100),
            ("course", "Course", 250),
            ("status", "Status", 100),
            ("enrolled_at", "Enrolled", 130),
        ]:
            enrol_tree.heading(col, text=hd)
            enrol_tree.column(col, width=w, anchor="w")
        enrol_tree.pack(fill="both", expand=True, padx=10, pady=10)
        try:
            enrolments = self._enrollment_svc.list_enrollments(student_pk=pk)
            for e in enrolments or []:
                enrol_tree.insert("", "end", values=(
                    e.get("course_id", ""),
                    e.get("course_name") or e.get("course") or "",
                    e.get("status", ""),
                    (e.get("enrolled_at") or "")[:16],
                ))
        except Exception:
            logger.warning("Failed to load enrolments for student %s", pk, exc_info=True)

        footer = tk.Frame(win, pady=8)
        footer.pack(fill="x")
        if self._user_role() == "admin":
            ttk.Button(
                footer, text="Edit",
                command=lambda: (win.destroy(), self._tree.selection_set(str(pk)),
                                 self._on_edit()),
            ).pack(side="left", padx=10)
        ttk.Button(footer, text="Close", command=win.destroy).pack(side="right", padx=10)

    def _on_delete(self):
        pk = self._selected_pk()
        if pk is None:
            return

        if not messagebox.askyesno(t("common.confirm_delete"),
                                   t("student.delete_confirm")):
            return

        try:
            self._svc.delete_student(pk)
            messagebox.showinfo(t("common.success"), t("student.deleted"))
            self._load_students()
        except (StudentError, ValidationError) as exc:
            logger.warning("Student delete rejected pk=%s: %s", pk, exc)
            messagebox.showerror(t("common.error"), str(exc))
        except Exception as exc:
            logger.exception("Unexpected error deleting student pk=%s", pk)
            messagebox.showerror(t("common.error"),
                                 f"Unexpected error deleting student:\n{exc}")

    def _on_search(self):
        term = self._search_var.get().strip()
        self._page = 0
        self._load_students(search=term if term else None)

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        try:
            export_treeview_to_csv(self._tree, default_filename="students.csv")
        except Exception as exc:
            logger.exception("CSV export failed")
            messagebox.showerror(t("common.error"), f"Export failed:\n{exc}")

    def _on_clear_search(self):
        self._search_var.set("")
        self._page = 0
        self._current_search = None
        self._load_students()
