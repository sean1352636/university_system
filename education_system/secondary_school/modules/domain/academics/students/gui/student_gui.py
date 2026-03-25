"""Student management GUI for the Secondary School Management System."""

import random
import secrets
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.secondary_school.modules.domain.academics.students.services.student_service import StudentService
from education_system.secondary_school.modules.domain.academics.subjects.services.subject_service import SubjectService
from education_system.secondary_school.modules.domain.academics.enrollment.services.enrollment_service import EnrollmentService
from education_system.secondary_school.infrastructure.auth.core import UserAuth
from education_system.secondary_school.core.exceptions import StudentError, ValidationError, EnrollmentError, AuthError
from education_system.primary_school.core.paths import DB_FILE as PRIMARY_DB_FILE

# Core subject codes that every student is auto-enrolled into
CORE_CODES_KS3 = ("MATH01", "ENG01", "ENG02", "SCI01")
CORE_CODES_KS4 = ("MATH02", "ENG03", "ENG04", "SCI02")


class _StudentDialog(tk.Toplevel):
    """Modal dialog for adding or editing a student record."""

    def __init__(self, parent, title="Student", student=None, option_subjects=None):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.grab_set()
        self.result: dict | None = None
        self._student = student
        self._option_subjects = option_subjects  # non-core subjects for the key stage
        self._imported_primary_pupil = None
        self._build_ui()
        self._center(parent)

    def _center(self, parent):
        self.update_idletasks()
        px = parent.winfo_rootx() + parent.winfo_width() // 2
        py = parent.winfo_rooty() + parent.winfo_height() // 2
        self.geometry(f"+{px - self.winfo_width() // 2}+{py - self.winfo_height() // 2}")

    def _import_from_primary(self):
        """Show dialog to select a pupil from the primary school system."""
        try:
            svc = StudentService(None)
            pupils = svc.fetch_primary_pupils(str(PRIMARY_DB_FILE))
        except Exception as e:
            messagebox.showerror("Error", f"Could not load primary school pupils:\n{e}")
            return
        if not pupils:
            messagebox.showinfo("Import", "No active pupils found in the primary school system.")
            return
        sel_dlg = tk.Toplevel(self)
        sel_dlg.title("Select Primary School Pupil")
        sel_dlg.geometry("550x400")
        sel_dlg.transient(self)
        sel_dlg.grab_set()
        tk.Label(sel_dlg, text="Select a pupil from the Primary School:",
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
        _pupil_map = {}
        def _populate(ft=""):
            lb.delete(0, tk.END)
            _pupil_map.clear()
            for p in pupils:
                name = f"{p['first_name']} {p['last_name']}"
                if ft and ft.lower() not in name.lower() and ft.lower() not in (p['pupil_id'] or '').lower():
                    continue
                pos = lb.size()
                lb.insert(tk.END, f"{p['pupil_id']}  {p['first_name']:15s} {p['last_name']:15s}  DOB: {p['date_of_birth'] or 'N/A'}")
                _pupil_map[pos] = p
        _populate()
        srch_var.trace_add("write", lambda *_: _populate(srch_var.get()))
        def _on_pick():
            sel = lb.curselection()
            if not sel:
                messagebox.showwarning("Selection", "Please select a pupil.", parent=sel_dlg)
                return
            p = _pupil_map[sel[0]]
            self._vars['first_name'].set(p['first_name'] or '')
            self._vars['last_name'].set(p['last_name'] or '')
            if p['date_of_birth']:
                self._vars['date_of_birth'].set(p['date_of_birth'])
            if p['address']:
                self._vars['address'].set(p['address'])
            if p['parent1_name']:
                self._vars['parent_name'].set(p['parent1_name'])
            if p['parent1_email']:
                self._vars['parent_email'].set(p['parent1_email'])
            if p['parent1_phone']:
                self._vars['parent_phone'].set(p['parent1_phone'])
            if p['emergency_contact_name']:
                self._vars['emergency_contact_name'].set(p['emergency_contact_name'])
            if p['emergency_contact_phone']:
                self._vars['emergency_contact_phone'].set(p['emergency_contact_phone'])
            self._imported_primary_pupil = dict(p)
            sel_dlg.destroy()
        bf = tk.Frame(sel_dlg)
        bf.pack(pady=10)
        ttk.Button(bf, text="Select & Import", command=_on_pick).pack(side="left", padx=5)
        ttk.Button(bf, text="Cancel", command=sel_dlg.destroy).pack(side="left", padx=5)

    def _build_ui(self):
        pad = {"padx": 10, "pady": 5}

        # Import from Primary School button (add mode only)
        if not self._student:
            import_frame = tk.Frame(self, padx=20, pady=(10, 0))
            import_frame.pack(fill="x")
            ttk.Button(import_frame, text="Import from Primary School",
                       command=self._import_from_primary).pack(anchor="w")

        container = tk.Frame(self, padx=20, pady=15)
        container.pack(fill="both", expand=True)

        # Student details
        fields = [
            ("First Name", "first_name"),
            ("Last Name", "last_name"),
            ("Date of Birth (YYYY-MM-DD)", "date_of_birth"),
            ("Address", "address"),
        ]

        # Parent / guardian details
        parent_fields = [
            ("Parent/Guardian Name", "parent_name"),
            ("Parent/Guardian Email", "parent_email"),
            ("Parent/Guardian Phone", "parent_phone"),
        ]

        # Emergency contact (separate from parent)
        emergency_fields = [
            ("Emergency Contact Name", "emergency_contact_name"),
            ("Emergency Contact Phone", "emergency_contact_phone"),
        ]

        self._vars: dict[str, tk.StringVar] = {}
        row_idx = 0

        # -- Student section header --
        tk.Label(container, text="Student Details", anchor="w",
                 font=("Helvetica", 10, "bold"), fg="#1a5276").grid(
            row=row_idx, column=0, columnspan=2, sticky="w", padx=10, pady=(5, 2))
        row_idx += 1

        for label_text, key in fields:
            tk.Label(container, text=label_text, anchor="w",
                     font=("Helvetica", 9, "bold")).grid(row=row_idx, column=0, sticky="w", **pad)
            var = tk.StringVar(
                value=self._student.get(key, "") if self._student and self._student.get(key) else ""
            )
            ttk.Entry(container, textvariable=var, width=36).grid(
                row=row_idx, column=1, sticky="ew", **pad)
            self._vars[key] = var
            row_idx += 1

        # -- Parent section header --
        tk.Label(container, text="Parent/Guardian Details", anchor="w",
                 font=("Helvetica", 10, "bold"), fg="#1a5276").grid(
            row=row_idx, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 2))
        row_idx += 1

        for label_text, key in parent_fields:
            tk.Label(container, text=label_text, anchor="w",
                     font=("Helvetica", 9, "bold")).grid(row=row_idx, column=0, sticky="w", **pad)
            var = tk.StringVar(
                value=self._student.get(key, "") if self._student and self._student.get(key) else ""
            )
            ttk.Entry(container, textvariable=var, width=36).grid(
                row=row_idx, column=1, sticky="ew", **pad)
            self._vars[key] = var
            row_idx += 1

        # -- Emergency contact section header --
        tk.Label(container, text="Emergency Contact", anchor="w",
                 font=("Helvetica", 10, "bold"), fg="#1a5276").grid(
            row=row_idx, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 2))
        row_idx += 1

        for label_text, key in emergency_fields:
            tk.Label(container, text=label_text, anchor="w",
                     font=("Helvetica", 9, "bold")).grid(row=row_idx, column=0, sticky="w", **pad)
            var = tk.StringVar(
                value=self._student.get(key, "") if self._student and self._student.get(key) else ""
            )
            ttk.Entry(container, textvariable=var, width=36).grid(
                row=row_idx, column=1, sticky="ew", **pad)
            self._vars[key] = var
            row_idx += 1

        # -- School details section --
        tk.Label(container, text="School Details", anchor="w",
                 font=("Helvetica", 10, "bold"), fg="#1a5276").grid(
            row=row_idx, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 2))
        row_idx += 1

        # Year Group
        tk.Label(container, text="Year Group", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=row_idx, column=0, sticky="w", **pad)
        self._vars["year_group"] = tk.StringVar(
            value=self._student.get("year_group", "7") if self._student else "7"
        )
        ttk.Combobox(container, textvariable=self._vars["year_group"],
                     values=["7", "8", "9", "10", "11"], state="readonly", width=33).grid(
            row=row_idx, column=1, sticky="ew", **pad)
        row_idx += 1

        # Form Group
        tk.Label(container, text="Form Group", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=row_idx, column=0, sticky="w", **pad)
        fg_default = self._student.get("form_group", "") if self._student else ""
        self._vars["form_group"] = tk.StringVar(value=fg_default)
        fg_values = [""] + [f"{y}{c}" for y in range(7, 12) for c in "ABCDE"]
        ttk.Combobox(container, textvariable=self._vars["form_group"],
                     values=fg_values, width=33).grid(row=row_idx, column=1, sticky="ew", **pad)
        row_idx += 1

        # SEN Status
        tk.Label(container, text="SEN Status", anchor="w",
                 font=("Helvetica", 9, "bold")).grid(row=row_idx, column=0, sticky="w", **pad)
        self._vars["sen_status"] = tk.StringVar(
            value=self._student.get("sen_status", "none") if self._student else "none"
        )
        ttk.Combobox(container, textvariable=self._vars["sen_status"],
                     values=["none", "SEN Support", "EHCP"], state="readonly", width=33).grid(
            row=row_idx, column=1, sticky="ew", **pad)
        row_idx += 1

        # Pupil Premium
        self._pp_var = tk.BooleanVar(
            value=bool(self._student.get("pupil_premium", 0)) if self._student else False
        )
        ttk.Checkbutton(container, text="Pupil Premium", variable=self._pp_var).grid(
            row=row_idx, column=0, columnspan=2, sticky="w", **pad)
        row_idx += 1

        # Option subject selection (add mode only — 4 options auto-picked by default)
        self._subject_vars: list[tk.StringVar] = []
        if not self._student and self._option_subjects:
            tk.Label(container, text="Option Subjects (4 auto-picked, change if needed)", anchor="w",
                     font=("Helvetica", 10, "bold"), fg="#1a5276").grid(
                row=row_idx, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 2))
            row_idx += 1

            # Pre-pick 4 random option subjects
            pre_picked = random.sample(
                self._option_subjects,
                min(4, len(self._option_subjects)),
            )

            subj_values = ["-- None --"] + [
                f"{s['subject_code']} - {s['title']}" for s in self._option_subjects
            ]
            for i in range(4):
                tk.Label(container, text=f"Option {i + 1}", anchor="w",
                         font=("Helvetica", 9, "bold")).grid(row=row_idx, column=0, sticky="w", **pad)
                default = "-- None --"
                if i < len(pre_picked):
                    default = f"{pre_picked[i]['subject_code']} - {pre_picked[i]['title']}"
                var = tk.StringVar(value=default)
                ttk.Combobox(container, textvariable=var, values=subj_values,
                             state="readonly", width=33).grid(row=row_idx, column=1, sticky="ew", **pad)
                self._subject_vars.append(var)
                row_idx += 1

        # Status (edit mode only)
        if self._student:
            tk.Label(container, text="Status", anchor="w",
                     font=("Helvetica", 9, "bold")).grid(row=row_idx, column=0, sticky="w", **pad)
            self._status_var = tk.StringVar(value=self._student.get("status", "active"))
            ttk.Combobox(container, textvariable=self._status_var,
                         values=["active", "inactive", "transferred", "excluded"],
                         state="readonly", width=33).grid(row=row_idx, column=1, sticky="ew", **pad)
            row_idx += 1
        else:
            self._status_var = None

        # Buttons
        btn_frame = tk.Frame(container)
        btn_frame.grid(row=row_idx, column=0, columnspan=2, pady=(15, 0))
        ttk.Button(btn_frame, text="Save", command=self._on_save).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="left", padx=5)

    def _on_save(self):
        self.result = {k: v.get().strip() for k, v in self._vars.items()}
        if self._imported_primary_pupil:
            self.result["_imported_primary_pupil"] = self._imported_primary_pupil
        self.result["pupil_premium"] = self._pp_var.get()
        if self._status_var:
            self.result["status"] = self._status_var.get()

        # Collect chosen option subject IDs
        if self._subject_vars and self._option_subjects:
            selected_ids = []
            for var in self._subject_vars:
                val = var.get()
                if val != "-- None --":
                    code = val.split(" - ")[0]
                    for s in self._option_subjects:
                        if s["subject_code"] == code:
                            selected_ids.append(s["id"])
                            break
            if len(selected_ids) != len(set(selected_ids)):
                messagebox.showwarning("Duplicate Subject",
                                       "Please choose different option subjects.")
                return
            self.result["selected_option_ids"] = selected_ids

        self.destroy()


class StudentFrame(tk.Frame):
    """Student management screen with Treeview and CRUD controls."""

    def __init__(self, parent, db_path=None, auth=None, **kwargs):
        super().__init__(parent, **kwargs)
        self._db_path = db_path
        self._auth = auth
        self._svc = StudentService(db_path)
        self._subj_svc = SubjectService(db_path)
        self._enroll_svc = EnrollmentService(db_path)
        self._build_ui()

    def _build_ui(self):
        self.configure(bg="#ecf0f1")

        # Header
        header = tk.Frame(self, bg="#1a5276", height=50)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="Student Management", font=("Helvetica", 15, "bold"),
                 bg="#1a5276", fg="white").pack(side="left", padx=20, pady=10)

        # Toolbar
        toolbar = tk.Frame(self, bg="#ecf0f1", pady=8)
        toolbar.pack(fill="x", padx=15)

        ttk.Button(toolbar, text="Add Student", command=self._on_add).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Edit Selected", command=self._on_edit).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Delete Selected", command=self._on_delete).pack(side="left", padx=4)

        # Filter by year group
        tk.Label(toolbar, text="Year:", bg="#ecf0f1").pack(side="left", padx=(20, 4))
        self._year_filter = tk.StringVar(value="All")
        ttk.Combobox(toolbar, textvariable=self._year_filter,
                     values=["All", "7", "8", "9", "10", "11"],
                     state="readonly", width=5).pack(side="left", padx=4)
        self._year_filter.trace_add("write", lambda *_: self._load_students())

        # Search
        tk.Label(toolbar, text="Search:", bg="#ecf0f1").pack(side="left", padx=(20, 4))
        self._search_var = tk.StringVar()
        search_entry = ttk.Entry(toolbar, textvariable=self._search_var, width=20)
        search_entry.pack(side="left", padx=4)
        ttk.Button(toolbar, text="Go", command=self._on_search).pack(side="left", padx=4)
        ttk.Button(toolbar, text="Clear", command=self._on_clear_search).pack(side="left", padx=4)
        search_entry.bind("<Return>", lambda _: self._on_search())

        # Treeview
        tree_frame = tk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        columns = ("student_id", "first_name", "last_name", "year_group",
                    "form_group", "key_stage", "sen_status", "status")
        self._tree = ttk.Treeview(tree_frame, columns=columns, show="headings",
                                  selectmode="browse")

        headings = {
            "student_id": ("ID", 80),
            "first_name": ("First Name", 120),
            "last_name": ("Last Name", 120),
            "year_group": ("Year", 50),
            "form_group": ("Form", 60),
            "key_stage": ("KS", 50),
            "sen_status": ("SEN", 90),
            "status": ("Status", 80),
        }
        for col, (heading, width) in headings.items():
            self._tree.heading(col, text=heading)
            self._tree.column(col, width=width, anchor="center")

        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Status bar
        self._status_var_label = tk.StringVar(value="Ready")
        tk.Label(self, textvariable=self._status_var_label, bg="#ecf0f1", anchor="w",
                 font=("Helvetica", 9), fg="#7f8c8d").pack(fill="x", padx=15, pady=(0, 8))

    def refresh(self):
        self._load_students()

    def _load_students(self, search: str | None = None):
        self._tree.delete(*self._tree.get_children())
        year = self._year_filter.get()
        year_group = year if year != "All" else None

        try:
            students = self._svc.list_students(search=search, year_group=year_group, limit=500)
        except Exception as exc:
            messagebox.showerror("Error", f"Failed to load students:\n{exc}")
            return

        for s in students:
            self._tree.insert("", "end", iid=s["id"], values=(
                s.get("student_id", ""),
                s.get("first_name", ""),
                s.get("last_name", ""),
                s.get("year_group", ""),
                s.get("form_group", "") or "",
                s.get("key_stage", ""),
                s.get("sen_status", "") or "",
                s.get("status", ""),
            ))

        self._status_var_label.set(f"{len(students)} student(s) loaded")

    def _selected_pk(self) -> int | None:
        sel = self._tree.selection()
        if not sel:
            messagebox.showwarning("Selection", "Please select a student first.")
            return None
        return int(sel[0])

    def _get_core_subject_ids(self, year_group: str) -> list[int]:
        """Get the DB IDs of the 4 mandatory core subjects for the given year group."""
        from education_system.secondary_school.infrastructure.database.constants import KS3_YEARS
        codes = CORE_CODES_KS3 if year_group in KS3_YEARS else CORE_CODES_KS4
        ids = []
        for code in codes:
            subj = self._subj_svc.get_subject_by_code(code)
            if subj:
                ids.append(subj["id"])
        return ids

    def _get_option_subjects(self, year_group: str) -> list[dict]:
        """Get non-core subjects matching the student's key stage."""
        from education_system.secondary_school.infrastructure.database.constants import KS3_YEARS
        ks = "KS3" if year_group in KS3_YEARS else "KS4"
        all_subjs = self._subj_svc.list_subjects(status="active", key_stage=ks)
        codes = CORE_CODES_KS3 if ks == "KS3" else CORE_CODES_KS4
        return [s for s in all_subjs if s["subject_code"] not in codes]

    def _on_add(self):
        # Default year group for option subject list — dialog will show options for year 7
        option_subjects = self._get_option_subjects("7")

        dlg = _StudentDialog(self, title="Add Student", option_subjects=option_subjects)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        data = dlg.result
        if not data.get("first_name") or not data.get("last_name"):
            messagebox.showwarning("Validation", "First name and last name are required.")
            return

        first_name = data["first_name"]
        last_name = data["last_name"]
        year_group = data.get("year_group") or "7"

        email = (
            f"{first_name.lower().replace(' ', '')}"
            f".{last_name.lower().replace(' ', '')}"
            f"@school.local"
        )

        # Create user account
        auth = UserAuth(self._db_path)
        digits = f"{secrets.randbelow(10000):04d}"
        password = f"{first_name.capitalize()}{digits}!"

        try:
            student = self._svc.create_student(
                first_name=first_name,
                last_name=last_name,
                email=email,
                date_of_birth=data.get("date_of_birth") or None,
                address=data.get("address") or None,
                year_group=year_group,
                form_group=data.get("form_group") or None,
                sen_status=data.get("sen_status") or "none",
                pupil_premium=data.get("pupil_premium", False),
                parent_name=data.get("parent_name") or None,
                parent_email=data.get("parent_email") or None,
                parent_phone=data.get("parent_phone") or None,
                emergency_contact_name=data.get("emergency_contact_name") or None,
                emergency_contact_phone=data.get("emergency_contact_phone") or None,
            )
        except (StudentError, ValidationError) as exc:
            messagebox.showerror("Error", str(exc))
            return

        student_id = student["student_id"]
        username = student_id

        try:
            user_id = auth.create_user(
                username=username, password=password, role="student", email=email,
            )
            self._svc.update_student(student["id"], user_id=user_id)
        except (AuthError, Exception) as exc:
            messagebox.showwarning("Partial Success",
                                   f"Student created ({student_id}) but account failed:\n{exc}")
            self._load_students()
            return

        # --- Auto-enroll in core subjects (Maths, English Lang, English Lit, Science) ---
        core_ids = self._get_core_subject_ids(year_group)
        option_ids = data.get("selected_option_ids", [])
        all_subject_ids = core_ids + option_ids

        enrolled = failed = 0
        enrolled_names = []
        for subj_id in all_subject_ids:
            try:
                self._enroll_svc.enroll_student(student["id"], subj_id)
                subj = self._subj_svc.get_subject(subj_id)
                enrolled_names.append(subj["title"] if subj else f"ID {subj_id}")
                enrolled += 1
            except EnrollmentError:
                failed += 1

        parts = [
            "Student created successfully!\n",
            f"Student ID:  {student_id}",
            f"Username:    {username}",
            f"Password:    {password}",
            f"Email:       {email}",
            f"\nEnrolled in {enrolled} subject(s):",
        ]
        for name in enrolled_names:
            parts.append(f"  - {name}")
        if failed:
            parts.append(f"\n({failed} enrollment(s) failed)")

        messagebox.showinfo("Student Account Created", "\n".join(parts))

        # Transfer academic history from primary school if imported
        imported = data.get("_imported_primary_pupil")
        if imported:
            self._svc.import_from_primary(
                student["id"], imported, str(PRIMARY_DB_FILE)
            )

        # Mark imported pupil as transferred in primary school if applicable
        if imported:
            imp_name = f"{imported.get('first_name', '')} {imported.get('last_name', '')}"
            if messagebox.askyesno(
                "Transfer Pupil",
                f"Mark {imp_name} as transferred in the Primary School?",
            ):
                try:
                    self._svc.mark_primary_as_transferred(
                        imported['id'], str(PRIMARY_DB_FILE)
                    )
                    print(f"[AUDIT] Pupil {imported.get('pupil_id', '')} ({imp_name}) "
                          f"transferred from primary school to secondary as {student_id}")
                    self._svc.notify_transfer(
                        student_id, imported, self._auth, str(PRIMARY_DB_FILE)
                    )
                except Exception as exc:
                    messagebox.showwarning(
                        "Import",
                        f"Student created but could not mark as transferred in primary school:\n{exc}",
                    )

        self._load_students()

    def _on_edit(self):
        pk = self._selected_pk()
        if pk is None:
            return

        student = self._svc.get_student(pk)
        if not student:
            messagebox.showerror("Error", "Student not found.")
            return

        dlg = _StudentDialog(self, title="Edit Student", student=student)
        self.wait_window(dlg)
        if dlg.result is None:
            return

        data = dlg.result
        try:
            update_fields = {}
            for key in ("first_name", "last_name",
                        "date_of_birth", "address", "year_group", "form_group",
                        "sen_status", "status",
                        "parent_name", "parent_email", "parent_phone",
                        "emergency_contact_name", "emergency_contact_phone"):
                val = data.get(key)
                if val:
                    update_fields[key] = val

            if "pupil_premium" in data:
                update_fields["pupil_premium"] = int(data["pupil_premium"])

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
        if not messagebox.askyesno(
            "Confirm Delete",
            "This will permanently delete the student and all related data.\n\nContinue?"
        ):
            return
        try:
            self._svc.delete_student(pk)
            messagebox.showinfo("Success", "Student deleted.")
            self._load_students()
        except StudentError as exc:
            messagebox.showerror("Error", str(exc))

    def _on_search(self):
        term = self._search_var.get().strip()
        self._load_students(search=term if term else None)

    def _on_clear_search(self):
        self._search_var.set("")
        self._load_students()
