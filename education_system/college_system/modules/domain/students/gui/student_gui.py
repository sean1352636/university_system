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

        self._build_ui()
        self._center_on_parent(parent)

    def _center_on_parent(self, parent):
        self.update_idletasks()
        pw = parent.winfo_rootx() + parent.winfo_width() // 2
        ph = parent.winfo_rooty() + parent.winfo_height() // 2
        w = self.winfo_width()
        h = self.winfo_height()
        self.geometry(f"+{pw - w // 2}+{ph - h // 2}")

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}
        container = tk.Frame(self, padx=20, pady=15)
        container.pack(fill="both", expand=True)

        fields = [
            ("First Name", "first_name"),
            ("Last Name",  "last_name"),
            ("Email",      "email"),
            ("Phone",      "phone"),
            ("Date of Birth (YYYY-MM-DD)", "date_of_birth"),
            ("Address",    "address"),
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
        tk.Label(container, text="Year Group", anchor="w",
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
        tk.Label(container, text="Form Group", anchor="w",
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
        tk.Label(container, text="Form Tutor", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(
            row=row_idx, column=0, sticky="w", **pad)
        ft_default = ""
        if self._student and self._student.get("form_tutor"):
            ft_default = self._student["form_tutor"]
        self._vars["form_tutor"] = tk.StringVar(value=ft_default)
        tutor_names = [""]
        for t in self._form_tutors:
            title = t.get("title") or ""
            name = f"{title} {t['first_name']} {t['last_name']}".strip()
            tutor_names.append(name)
        ttk.Combobox(container, textvariable=self._vars["form_tutor"],
                     values=tutor_names, width=33).grid(
            row=row_idx, column=1, sticky="ew", **pad)

        # Course selection (add mode only, when courses are available)
        self._course_vars: list[tk.StringVar] = []
        if not self._student and self._courses:
            course_values = ["-- None --"] + [
                f"{c['course_code']} - {c['title']}" for c in self._courses
            ]
            for i in range(3):
                row_idx += 1
                tk.Label(container, text=f"Course {i + 1}", anchor="w",
                         font=("Helvetica", 9, "bold")).grid(
                    row=row_idx, column=0, sticky="w", **pad)
                var = tk.StringVar(value="-- None --")
                ttk.Combobox(container, textvariable=var, values=course_values,
                             state="readonly", width=33).grid(
                    row=row_idx, column=1, sticky="ew", **pad)
                self._course_vars.append(var)

        # Status (only shown when editing)
        if self._student:
            row_idx += 1
            tk.Label(container, text="Status", anchor="w",
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
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(
            side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(
            side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        if self._status_var:
            self.result["status"] = self._status_var.get()

        # Extract selected course IDs (add mode only)
        if self._course_vars and self._courses:
            selected_ids = []
            for var in self._course_vars:
                val = var.get()
                if val != "-- None --":
                    code = val.split(" - ")[0]
                    for c in self._courses:
                        if c["course_code"] == code:
                            selected_ids.append(c["id"])
                            break

            # Check for duplicates
            if len(selected_ids) != len(set(selected_ids)):
                messagebox.showwarning(
                    "Duplicate Course",
                    "You have selected the same course more than once.\n"
                    "Please choose different courses.",
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
        tk.Label(header, text="Student Management", font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        # Toolbar
        toolbar = tk.Frame(self, bg="#ecf0f1", pady=8)
        toolbar.pack(fill="x", padx=15)

        ttk.Button(toolbar, text="Add Student", command=self._on_add).pack(
            side="left", padx=4)
        ttk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(
            side="left", padx=4)
        ttk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(
            side="left", padx=4)

        # Search
        tk.Label(toolbar, text="Search:", bg="#ecf0f1").pack(side="left", padx=(20, 4))
        self._search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=self._search_var, width=24)
        search_entry.pack(side="left", padx=4)
        ttk.Button(toolbar, text="Go", command=self._on_search).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Clear", command=self._on_clear_search).pack(
            side="left", padx=4)
        search_entry.bind("<Return>", lambda _e: self._on_search())

        # Treeview
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columns = ("student_id", "first_name", "last_name", "year_group", "form_group", "status")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                  selectmode="browse")

        headings = {
            "student_id": ("Student ID", 100),
            "first_name": ("First Name", 130),
            "last_name":  ("Last Name",  130),
            "year_group": ("Year",        60),
            "form_group": ("Form",        80),
            "status":     ("Status",     100),
        }
        for col, (heading, width) in headings.items():
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(
            fill="x", padx=15, pady=(0, 8))

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def refresh(self):
        """Reload the student list from the database."""
        self._load_students()

    def _load_students(self, search: str | None = None):
        self._tree.delete(*self._tree.get_children())
        try:
            students = self._svc.list_students(search=search, limit=500)
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load students:\n{exc}")
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

        self._status_var.set(f"{len(students)} student(s) loaded")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _selected_pk(self) -> int | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a student first.")
            return None
        return int(sel[0])

    def _on_add(self):
        # Fetch active courses for the dropdown
        try:
            courses = self._course_svc.list_courses(status="active")
        except Exception:
            courses = []

        # Fetch form groups and staff for dropdowns
        try:
            form_groups = self._staff_svc.get_form_groups()
        except Exception:
            form_groups = []
        try:
            staff_list = self._staff_svc.list_staff(status="active")
        except Exception:
            staff_list = []

        dlg = _StudentDialog(self, title="Add Student", courses=courses,
                             form_groups=form_groups, form_tutors=staff_list)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        data = dlg.result
        if not data.get("first_name") or not data.get("last_name"):
            messagebox.showwarning("Validation", "First name and last name are required.")
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
        password = f"{first_name.capitalize()}{digits}!"
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
            messagebox.showerror("Error", str(exc))
            return

        student_id = student["student_id"]  # e.g. SFC0002
        username = student_id

        # 2. Create user account linked to this student
        try:
            user_id = auth.create_user(
                username=username,
                password=password,
                role="student",
                email=email,
            )
            # 3. Link user_id to student record
            self._svc.update_student(student["id"], user_id=user_id)
        except (AuthError, Exception) as exc:
            # Student was created but account failed — still show student info
            messagebox.showwarning(
                "Partial Success",
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

        messagebox.showinfo("Student Account Created", "\n".join(parts))
        self._load_students()

    def _on_edit(self):
        pk = self._selected_pk()
        if pk is None:
            return

        student = self._svc.get_student(pk)
        if not student:
            messagebox.showerror("Error", "Student not found.")
            return

        try:
            form_groups = self._staff_svc.get_form_groups()
        except Exception:
            form_groups = []
        try:
            staff_list = self._staff_svc.list_staff(status="active")
        except Exception:
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
                messagebox.showinfo("Success", "Student updated successfully.")
                self._load_students()
        except (StudentError, ValidationError) as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete(self):
        pk = self._selected_pk()
        if pk is None:
            return

        if not messagebox.askyesno("Confirm Delete",
                                   "This will permanently delete the student, their user account, "
                                   "and all related data (enrollments, grades, attendance, submissions).\n\n"
                                   "This cannot be undone. Continue?"):
            return

        try:
            self._svc.delete_student(pk)
            messagebox.showinfo("Success", "Student deleted permanently.")
            self._load_students()
        except (StudentError, ValidationError) as exc:
            messagebox.showerror("Error", str(exc))

    def _on_search(self):
        term = self._search_var.get().strip()
        self._load_students(search=term if term else None)

    def _on_clear_search(self):
        self._search_var.set("")
        self._load_students()
