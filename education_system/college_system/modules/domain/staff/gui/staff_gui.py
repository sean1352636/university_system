"""Staff management GUI for the Sixth Form College Management System."""

import random
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.college_system.modules.domain.staff.services.staff_service import StaffService
from education_system.college_system.modules.domain.courses.services.course_service import CourseService
from education_system.college_system.infrastructure.auth.core import UserAuth
from education_system.college_system.core.exceptions import StaffError, ValidationError, AuthError


_FORM_GROUPS = ["12A", "12B", "12C", "12D", "13A", "13B", "13C", "13D"]
_TITLES = ["", "Mr", "Mrs", "Ms", "Miss", "Dr", "Prof"]


class _StaffDialog(tk.Toplevel):
    """Modal dialog for adding or editing a staff member."""

    def __init__(self, parent, title="Staff Member", staff=None,
                 courses: list[dict] | None = None,
                 assigned_course_ids: list[int] | None = None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()

        self.result: dict | None = None
        self._staff = staff
        self._courses = courses or []
        self._assigned_course_ids = set(assigned_course_ids or [])

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

        self._vars: dict[str, tk.StringVar] = {}
        row_idx = 0

        # Title (Mr, Mrs, Dr, etc.)
        tk.Label(container, text="Title", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(
            row=row_idx, column=0, sticky="w", **pad)
        self._vars["title"] = tk.StringVar(
            value=self._staff.get("title", "") if self._staff else ""
        )
        ttk.Combobox(container, textvariable=self._vars["title"],
                     values=_TITLES, width=33).grid(
            row=row_idx, column=1, sticky="ew", **pad)

        # Text entry fields
        entry_fields = [
            ("First Name", "first_name"),
            ("Last Name",  "last_name"),
            ("Phone",      "phone"),
        ]
        for label_text, key in entry_fields:
            row_idx += 1
            tk.Label(container, text=label_text, anchor="w",
                     font=("Helvetica", 9, "bold")).grid(
                row=row_idx, column=0, sticky="w", **pad)
            var = tk.StringVar(
                value=self._staff.get(key, "") if self._staff and self._staff.get(key) else ""
            )
            ttk.Entry(container, textvariable=var, width=36).grid(
                row=row_idx, column=1, sticky="ew", **pad)
            self._vars[key] = var

        # Subject Area
        row_idx += 1
        tk.Label(container, text="Subject Area", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(
            row=row_idx, column=0, sticky="w", **pad)
        self._vars["subject_area"] = tk.StringVar(
            value=self._staff.get("subject_area", "") if self._staff and self._staff.get("subject_area") else ""
        )
        subject_areas = ["", "Mathematics", "Science", "Technology", "English",
                         "Humanities", "Social Sciences", "Business",
                         "Creative Arts", "Modern Languages", "Health"]
        ttk.Combobox(container, textvariable=self._vars["subject_area"],
                     values=subject_areas, width=33).grid(
            row=row_idx, column=1, sticky="ew", **pad)

        # Form Group (if they are a form tutor)
        row_idx += 1
        tk.Label(container, text="Form Group (if tutor)", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(
            row=row_idx, column=0, sticky="w", **pad)
        self._vars["form_group"] = tk.StringVar(
            value=self._staff.get("form_group", "") if self._staff and self._staff.get("form_group") else ""
        )
        ttk.Combobox(container, textvariable=self._vars["form_group"],
                     values=[""] + _FORM_GROUPS, width=33).grid(
            row=row_idx, column=1, sticky="ew", **pad)

        # Status (edit only)
        if self._staff:
            row_idx += 1
            tk.Label(container, text="Status", anchor="w",
                     font=("Helvetica", 9, "bold")).grid(
                row=row_idx, column=0, sticky="w", **pad)
            self._status_var = tk.StringVar(
                value=self._staff.get("status", "active"))
            ttk.Combobox(container, textvariable=self._status_var,
                         values=["active", "inactive"],
                         state="readonly", width=33).grid(
                row=row_idx, column=1, sticky="ew", **pad)
        else:
            self._status_var = None

        # Course assignment (checkboxes in a scrollable frame)
        if self._courses:
            row_idx += 1
            tk.Label(container, text="Assign Courses", anchor="w",
                     font=("Helvetica", 9, "bold")).grid(
                row=row_idx, column=0, sticky="nw", **pad)

            course_frame = tk.Frame(container, relief="sunken", borderwidth=1)
            course_frame.grid(row=row_idx, column=1, sticky="ew", **pad)

            canvas = tk.Canvas(course_frame, height=120, highlightthickness=0)
            scrollbar = ttk.Scrollbar(course_frame, orient="vertical", command=canvas.yview)
            inner = tk.Frame(canvas)
            inner.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
            )
            canvas.create_window((0, 0), window=inner, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)
            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            self._course_check_vars: list[tuple[int, tk.BooleanVar]] = []
            for course in self._courses:
                var = tk.BooleanVar(value=course["id"] in self._assigned_course_ids)
                cb = ttk.Checkbutton(
                    inner,
                    text=f"{course['course_code']} - {course['title']}",
                    variable=var,
                )
                cb.pack(anchor="w", padx=4, pady=1)
                self._course_check_vars.append((course["id"], var))
        else:
            self._course_check_vars = []

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

        # Collect selected course IDs
        selected = []
        for course_id, var in self._course_check_vars:
            if var.get():
                selected.append(course_id)
        self.result["selected_course_ids"] = selected

        self.destroy()


class StaffFrame(tk.Frame):
    """Staff management screen with Treeview and CRUD controls."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = StaffService(db_path)
        self._course_svc = CourseService(db_path)

        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#2c3e50", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Staff Management", font=("Helvetica", 15, "bold"),
                 bg="#2c3e50", fg="white").pack(side="left", padx=20, pady=10)

        # Toolbar
        toolbar = tk.Frame(self, bg="#ecf0f1", pady=8)
        toolbar.pack(fill="x", padx=15)

        ttk.Button(toolbar, text="Add Staff", command=self._on_add).pack(
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

        columns = ("staff_id", "title", "first_name", "last_name",
                   "subject_area", "form_group", "status")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                  selectmode="browse")

        headings = {
            "staff_id":     ("Staff ID",     90),
            "title":        ("Title",        50),
            "first_name":   ("First Name",  120),
            "last_name":    ("Last Name",   120),
            "subject_area": ("Subject",     130),
            "form_group":   ("Form",         70),
            "status":       ("Status",       80),
        }
        for col, (heading, width) in headings.items():
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self._status_lbl_var = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_lbl_var, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(
            fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load_staff()

    def _load_staff(self, search: str | None = None):
        self._tree.delete(*self._tree.get_children())
        try:
            staff_list = self._svc.list_staff(search=search, limit=500)
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load staff:\n{exc}")
            return

        for s in staff_list:
            self._tree.insert("", "end", iid=s["id"], values=(
                s.get("staff_id", ""),
                s.get("title", "") or "",
                s.get("first_name", ""),
                s.get("last_name", ""),
                s.get("subject_area", "") or "",
                s.get("form_group", "") or "",
                s.get("status", ""),
            ))

        self._status_lbl_var.set(f"{len(staff_list)} staff member(s) loaded")

    def _selected_pk(self) -> int | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a staff member first.")
            return None
        return int(sel[0])

    def _on_add(self):
        try:
            courses = self._course_svc.list_courses(status="active")
        except Exception:
            courses = []

        dlg = _StaffDialog(self, title="Add Staff Member", courses=courses)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        data = dlg.result
        if not data.get("first_name") or not data.get("last_name"):
            messagebox.showwarning("Validation", "First name and last name are required.")
            return

        first_name = data["first_name"]
        last_name = data["last_name"]

        # Generate email
        email = (
            f"{first_name.lower().replace(' ', '')}"
            f".{last_name.lower().replace(' ', '')}"
            f"@sixthform.ac.uk"
        )

        # 1. Create the staff record
        try:
            staff = self._svc.create_staff(
                first_name=first_name,
                last_name=last_name,
                title=data.get("title") or None,
                email=email,
                phone=data.get("phone") or None,
                subject_area=data.get("subject_area") or None,
                form_group=data.get("form_group") or None,
            )
        except (StaffError, ValidationError) as exc:
            messagebox.showerror("Error", str(exc))
            return

        staff_id = staff["staff_id"]

        # 2. Create user account
        auth = UserAuth(self._db_path)
        digits = f"{random.randint(0, 9999):04d}"
        password = f"{first_name.capitalize()}{digits}!"
        username = staff_id

        try:
            user_id = auth.create_user(
                username=username,
                password=password,
                role="teacher",
                email=email,
            )
            self._svc.update_staff(staff["id"], user_id=user_id)
        except (AuthError, Exception) as exc:
            messagebox.showwarning(
                "Partial Success",
                f"Staff created ({staff_id}) but account creation failed:\n{exc}",
            )
            self._load_staff()
            return

        # 3. Assign courses
        selected_ids = data.get("selected_course_ids", [])
        courses_assigned = 0
        if selected_ids:
            try:
                courses_assigned = self._svc.assign_courses(staff["id"], selected_ids)
            except StaffError as exc:
                messagebox.showwarning("Warning", f"Course assignment failed: {exc}")

        # 4. Show credentials
        parts = [
            "Staff member created successfully!\n",
            f"Staff ID:    {staff_id}",
            f"Username:    {username}",
            f"Password:    {password}",
            f"Email:       {email}",
        ]
        if data.get("form_group"):
            parts.append(f"Form Group:  {data['form_group']}")
        if courses_assigned:
            parts.append(f"\nCourses assigned: {courses_assigned}")

        messagebox.showinfo("Staff Account Created", "\n".join(parts))
        self._load_staff()

    def _on_edit(self):
        pk = self._selected_pk()
        if pk is None:
            return

        staff = self._svc.get_staff(pk)
        if not staff:
            messagebox.showerror("Error", "Staff member not found.")
            return

        try:
            courses = self._course_svc.list_courses(status="active")
        except Exception:
            courses = []

        assigned = self._svc.get_assigned_courses(pk)
        assigned_ids = [c["id"] for c in assigned]

        dlg = _StaffDialog(self, title="Edit Staff Member", staff=staff,
                           courses=courses, assigned_course_ids=assigned_ids)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        data = dlg.result
        try:
            update_fields = {}
            for key in ("first_name", "last_name", "title", "phone",
                        "subject_area", "form_group", "status"):
                val = data.get(key)
                if val is not None:
                    update_fields[key] = val

            if update_fields:
                self._svc.update_staff(pk, **update_fields)

            # Update course assignments
            selected_ids = data.get("selected_course_ids", [])
            # Clear old assignments that are no longer selected
            for old_id in assigned_ids:
                if old_id not in selected_ids:
                    try:
                        self._course_svc.update_course(old_id, teacher="", status=None)
                    except Exception:
                        pass

            # Assign new courses
            if selected_ids:
                self._svc.assign_courses(pk, selected_ids)

            messagebox.showinfo("Success", "Staff member updated successfully.")
            self._load_staff()
        except (StaffError, ValidationError) as exc:
            messagebox.showerror("Error", str(exc))

    def _on_delete(self):
        pk = self._selected_pk()
        if pk is None:
            return

        if not messagebox.askyesno("Confirm Delete",
                                   "This will permanently delete the staff member, their user account, "
                                   "and remove them from any assigned courses.\n\n"
                                   "This cannot be undone. Continue?"):
            return

        try:
            self._svc.delete_staff(pk)
            messagebox.showinfo("Success", "Staff member deleted permanently.")
            self._load_staff()
        except (StaffError, ValidationError) as exc:
            messagebox.showerror("Error", str(exc))

    def _on_search(self):
        term = self._search_var.get().strip()
        self._load_staff(search=term if term else None)

    def _on_clear_search(self):
        self._search_var.set("")
        self._load_staff()
