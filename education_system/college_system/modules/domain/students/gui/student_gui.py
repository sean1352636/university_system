"""Student management GUI for the Sixth Form College Management System."""

import random
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.students.services.student_service import StudentService
from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.modules.domain.enrollment.services.enrollment_service import EnrollmentService
from education_system.college_system.modules.domain.staff.services.staff_service import StaffService
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.core.exceptions import StudentError, ValidationError, EnrollmentError, AuthError
from education_system.college_system.core.i18n import t
from education_system.secondary_school.core.paths import DB_FILE as SECONDARY_DB_FILE
from education_system.college_system.modules.domain.notifications.services.notification_service import NotificationService


class _StudentDialog(tk.Toplevel):
    """Modal dialog for adding or editing a student record."""

    def __init__(self, parent, title="Student", student=None,
                 courses: list[dict] | None = None,
                 form_groups: list[str] | None = None,
                 form_tutors: list[dict] | None = None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()

        self.result: dict | None = None
        self._student = student
        self._courses = courses
        self._form_groups = form_groups or []
        self._form_tutors = form_tutors or []
        self._imported_secondary_student = None

        self._build_ui()
        self._center_on_parent(parent)
        self.bind("<Escape>", lambda e: self.destroy())

    def _center_on_parent(self, parent):
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width() // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        w = self.winfo_width()
        h = self.winfo_height()
        self.geometry(f"+{pw - w // 2}+{ph - h // 2}")

    def _import_from_secondary(self):
        """Show dialog to select a student from the secondary school system."""
        try:
            svc = StudentService(None)
            sec_students_raw = svc.fetch_secondary_students(str(SECONDARY_DB_FILE))
            # Convert to list of dicts usable by the picker (already dicts)
            sec_students = sec_students_raw
        except Exception as e:
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
        _stu_map = {}

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

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}

        # Import from Secondary School button (add mode only)
        if not self._student:
            import_frame = tk.Frame(self, padx=20, pady=10)
            import_frame.pack(fill="x")
            ttk.Button(import_frame, text="Import from Secondary School",
                       command=self._import_from_secondary).pack(anchor="w")

        container = tk.Frame(self, padx=20, pady=15)
        container.pack(fill="both", expand=True)

        fields = [
            (t("student.first_name"), "first_name"),
            (t("student.last_name"),  "last_name"),
            (t("student.email"),      "email"),
            (t("student.phone"),      "phone"),
            (t("student.date_of_birth"), "date_of_birth"),
            (t("student.address"),    "address"),
        ]

        self._vars: dict[str, tk.StringVar] = {}
        row_idx = 0
        for row_idx, (label_text, key) in enumerate(fields):
            tk.Label(container, text=label_text, anchor="w",
                     font=("Helvetica", 9, "bold")).grid(
                row=row_idx, column=0, sticky="w", **pad)
            var = tk.StringVar(
                value=self._student.get(key, "") if self._student and self._student.get(key) else ""
            )
            ttk.Entry(container, textvariable=var, width=36).grid(
                row=row_idx, column=1, sticky="ew", **pad)
            self._vars[key] = var

        # Year Group (Combobox)
        row_idx += 1
        tk.Label(container, text=t("student.year_group"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(
            row=row_idx, column=0, sticky="w", **pad)
        self._vars["year_group"] = tk.StringVar(
            value=self._student.get("year_group", "12") if self._student else "12"
        )
        ttk.Combobox(container, textvariable=self._vars["year_group"],
                     values=["12", "13"], state="readonly", width=33).grid(
            row=row_idx, column=1, sticky="ew", **pad)

        # Form Group (dropdown)
        row_idx += 1
        tk.Label(container, text=t("student.form_group"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(
            row=row_idx, column=0, sticky="w", **pad)
        fg_default = ""
        if self._student and self._student.get("form_group"):
            fg_default = self._student["form_group"]
        self._vars["form_group"] = tk.StringVar(value=fg_default)
        fg_values = [""] + (self._form_groups if self._form_groups
                            else ["12A", "12B", "12C", "12D", "13A", "13B", "13C", "13D"])
        ttk.Combobox(container, textvariable=self._vars["form_group"],
                     values=fg_values, width=33).grid(
            row=row_idx, column=1, sticky="ew", **pad)

        # Form Tutor (dropdown populated from staff)
        row_idx += 1
        tk.Label(container, text=t("student.form_tutor"), anchor="w",
                 font=("Helvetica", 9, "bold")).grid(
            row=row_idx, column=0, sticky="w", **pad)
        ft_default = ""
        if self._student and self._student.get("form_tutor"):
            ft_default = self._student["form_tutor"]
        self._vars["form_tutor"] = tk.StringVar(value=ft_default)
        tutor_names = [""]
        for tutor in self._form_tutors:
            title = tutor.get("title") or ""
            name = f"{title} {tutor['first_name']} {tutor['last_name']}".strip()
            tutor_names.append(name)
        ttk.Combobox(container, textvariable=self._vars["form_tutor"],
                     values=tutor_names, width=33).grid(
            row=row_idx, column=1, sticky="ew", **pad)

        # Course selection (add mode only, when courses are available)
        self._course_vars: list[tk.StringVar] = []
        if not self._student and self._courses:
            course_values = [t("student.none_selected")] + [
                f"{c['course_code']} - {c['title']}" for c in self._courses
            ]
            for i in range(3):
                row_idx += 1
                tk.Label(container, text=f"Course {i + 1}", anchor="w",
                         font=("Helvetica", 9, "bold")).grid(
                    row=row_idx, column=0, sticky="w", **pad)
                var = tk.StringVar(value=t("student.none_selected"))
                ttk.Combobox(container, textvariable=var, values=course_values,
                             state="readonly", width=33).grid(
                    row=row_idx, column=1, sticky="ew", **pad)
                self._course_vars.append(var)

        # Status (only shown when editing)
        if self._student:
            row_idx += 1
            tk.Label(container, text=t("student.status"), anchor="w",
                     font=("Helvetica", 9, "bold")).grid(
                row=row_idx, column=0, sticky="w", **pad)
            self._status_var = tk.StringVar(
                value=self._student.get("status", "active"))
            combo = ttk.Combobox(container, textvariable=self._status_var,
                                 values=["active", "inactive", "graduated", "suspended"],
                                 state="readonly", width=33)
            combo.grid(row=row_idx, column=1, sticky="ew", **pad)
        else:
            self._status_var = None

        # Buttons
        btn_frame = tk.Frame(container)
        btn_frame.grid(row=row_idx + 1, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text=t("common.save"), command=self._on_save).pack(
            side="left", padx=5)
        ttk.Button(btn_frame, text=t("common.cancel"), command=self.destroy).pack(
            side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        if self._imported_secondary_student:
            self.result["_imported_secondary_student"] = self._imported_secondary_student
        if self._status_var:
            self.result["status"] = self._status_var.get()

        # Extract selected course IDs (add mode only)
        if self._course_vars and self._courses:
            selected_ids = []
            for var in self._course_vars:
                val = var.get()
                if val != t("student.none_selected"):
                    code = val.split(" - ")[0]
                    for c in self._courses:
                        if c["course_code"] == code:
                            selected_ids.append(c["id"])
                            break

            # Check for duplicates
            if len(selected_ids) != len(set(selected_ids)):
                messagebox.showwarning(
                    t("student.duplicate_course"),
                    t("student.duplicate_course_msg"),
                )
                return

            self.result["selected_course_ids"] = selected_ids

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

    def _on_add(self):
        # Fetch active courses for the dropdown
        try:
            courses = self._course_svc.list_courses(status="active")
        except Exception:
            import logging
            logging.getLogger(__name__).warning("Failed to load active courses for student dialog", exc_info=True)
            courses = []

        # Fetch form groups and staff for dropdowns
        try:
            form_groups = self._staff_svc.get_form_groups()
        except Exception:
            import logging
            logging.getLogger(__name__).warning("Failed to load form groups for student dialog", exc_info=True)
            form_groups = []
        try:
            staff_list = self._staff_svc.list_staff(status="active")
        except Exception:
            import logging
            logging.getLogger(__name__).warning("Failed to load staff list for student dialog", exc_info=True)
            staff_list = []

        dlg = _StudentDialog(self, title="Add Student", courses=courses,
                             form_groups=form_groups, form_tutors=staff_list)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        data = dlg.result
        if not data.get("first_name") or not data.get("last_name"):
            messagebox.showwarning(t("common.validation"), t("student.name_required"))
            return

        first_name = data["first_name"]
        last_name = data["last_name"]

        # Generate college email address
        email = (
            f"{first_name.lower().replace(' ', '')}"
            f".{last_name.lower().replace(' ', '')}"
            f"@sixthform.ac.uk"
        )

        # 1. Create the user account first
        auth = UserAuth(self._db_path)
        digits = f"{random.randint(0, 9999):04d}"
        password = f"{first_name.capitalize()}{last_name.capitalize()}{digits}!"
        while len(password) < 12:
            password = f"Student{password}"
        # Username will be set to student_id after student is created;
        # create with a temporary username first, then update.
        # Actually, we need the student_id which comes from create_student.
        # So create student first (without user_id), then create user, then link.

        try:
            student = self._svc.create_student(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=data.get("phone") or None,
                date_of_birth=data.get("date_of_birth") or None,
                address=data.get("address") or None,
                year_group=data.get("year_group") or "12",
                form_group=data.get("form_group") or None,
                form_tutor=data.get("form_tutor") or None,
            )
        except (StudentError, ValidationError) as exc:
            messagebox.showerror(t("common.error"), str(exc))
            return

        student_id = student["student_id"]  # e.g. SFC0002
        username = student_id

        # 2. Create user account in shared auth + college local users table
        try:
            # Create in shared auth DB (returns shared auth user ID)
            auth.create_user(
                username=username,
                password=password,
                email=email,
                systems=[("college", "student")],
            )
            # Create matching record in college local users table for FK
            from education_system.college_system.infrastructure.database.db import connect as college_connect
            from education_system.shared.auth.password_manager import hash_password
            _local_conn = college_connect(self._db_path)
            try:
                _local_conn.execute(
                    "INSERT INTO users (username, password_hash, role, email) VALUES (?, ?, ?, ?)",
                    (username, hash_password(password), "student", email),
                )
                _local_conn.commit()
                local_user_id = _local_conn.execute(
                    "SELECT id FROM users WHERE username = ?", (username,)
                ).fetchone()["id"]
            finally:
                _local_conn.close()
            # 3. Link local user_id to student record
            self._svc.update_student(student["id"], user_id=local_user_id)
        except (AuthError, Exception) as exc:
            # Student was created but account failed — still show student info
            messagebox.showwarning(
                t("student.partial_success"),
                f"Student created ({student_id}) but account creation failed:\n{exc}",
            )
            self._load_students()
            return

        # 4. Enroll in selected courses
        selected_ids = data.get("selected_course_ids", [])
        enrolled = 0
        waitlisted = 0
        failed = 0
        if selected_ids:
            for course_id in selected_ids:
                try:
                    result = self._enrollment_svc.enroll_student(student["id"], course_id)
                    if result["status"] == "enrolled":
                        enrolled += 1
                    elif result["status"] == "waitlisted":
                        waitlisted += 1
                except EnrollmentError:
                    failed += 1

        # 5. Show credentials and summary
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

        # Transfer academic history from secondary school if imported
        imported = data.get("_imported_secondary_student")
        if imported:
            self._svc.import_from_secondary(
                student["id"], imported, str(SECONDARY_DB_FILE)
            )

        # Mark imported student as transferred in secondary school if applicable
        if imported:
            imp_name = f"{imported.get('first_name', '')} {imported.get('last_name', '')}"
            if messagebox.askyesno(
                "Transfer Student",
                f"Mark {imp_name} as transferred in the Secondary School?",
            ):
                try:
                    self._svc.mark_secondary_as_transferred(
                        imported['id'], str(SECONDARY_DB_FILE)
                    )
                    print(f"[AUDIT] Student {imported.get('student_id', '')} ({imp_name}) "
                          f"transferred from secondary school to college as {student_id}")
                    self._svc.notify_transfer(
                        student_id, imported, self._auth, str(SECONDARY_DB_FILE)
                    )
                except Exception as exc:
                    messagebox.showwarning(
                        "Import",
                        f"Student created but could not mark as transferred in secondary school:\n{exc}",
                    )

        self._load_students()

    def _on_edit(self):
        pk = self._selected_pk()
        if pk is None:
            return

        student = self._svc.get_student(pk)
        if not student:
            messagebox.showerror(t("common.error"), t("student.not_found"))
            return

        try:
            form_groups = self._staff_svc.get_form_groups()
        except Exception:
            import logging
            logging.getLogger(__name__).warning("Failed to load form groups for edit dialog", exc_info=True)
            form_groups = []
        try:
            staff_list = self._staff_svc.list_staff(status="active")
        except Exception:
            import logging
            logging.getLogger(__name__).warning("Failed to load staff list for edit dialog", exc_info=True)
            staff_list = []

        dlg = _StudentDialog(self, title="Edit Student", student=student,
                             form_groups=form_groups, form_tutors=staff_list)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        data = dlg.result
        try:
            update_fields = {}
            for key in ("first_name", "last_name", "email", "phone",
                        "date_of_birth", "address", "year_group",
                        "form_group", "form_tutor", "status"):
                val = data.get(key)
                if val:
                    update_fields[key] = val

            if update_fields:
                self._svc.update_student(pk, **update_fields)
                messagebox.showinfo(t("common.success"), t("student.updated"))
                self._load_students()
        except (StudentError, ValidationError) as exc:
            messagebox.showerror(t("common.error"), str(exc))

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
            messagebox.showerror(t("common.error"), str(exc))

    def _on_search(self):
        term = self._search_var.get().strip()
        self._page = 0
        self._load_students(search=term if term else None)

    def _export_csv(self):
        from education_system.college_system.modules.shared.csv_export import export_treeview_to_csv
        export_treeview_to_csv(self._tree, default_filename="students.csv")

    def _on_clear_search(self):
        self._search_var.set("")
        self._page = 0
        self._current_search = None
        self._load_students()
