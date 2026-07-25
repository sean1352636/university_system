"""
Enrollment Mixin

Handles enrolling in modules, dropping modules, and displaying the
student's current enrollment list.
"""

from datetime import date
from tkinter import ttk, messagebox

from education_system.systems.university.interfaces.gui.academics.student_registration.common_imports import get_connection, logger


def _send_lifecycle_email(template_name: str, student_id: str,
                          vars_: dict) -> bool:
    """Render ``student_lifecycle/<template_name>`` for the student and
    dispatch best-effort. Skips if the student has no email on file."""
    try:
        from education_system.systems.university.infrastructure.email.template_utils import (
            render_template,
        )
        from education_system.systems.university.infrastructure.email.email_service import (
            send_email,
        )
    except Exception:
        logger.exception("email infrastructure unavailable")
        return False
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT TRIM(COALESCE(first_name,'')||' '||COALESCE(last_name,'')) AS name,"
                "       COALESCE(email_address,'') AS email"
                "  FROM students WHERE student_id = ?",
                (student_id,),
            ).fetchone()
    except Exception:
        logger.exception("student lookup failed sid=%s", student_id)
        return False
    if not row:
        return False
    recipient = (row[1] or '').strip()
    if not recipient:
        return False
    full = {'student_id': student_id, 'student_name': (row[0] or '').strip() or student_id}
    full.update(vars_)
    subject, body = render_template(f"student_lifecycle/{template_name}", full)
    if not subject or not body:
        return False
    try:
        send_email(recipient_email=recipient, subject=subject, body=body)
        return True
    except Exception:
        logger.exception("send_email failed student_lifecycle/%s", template_name)
        return False


class EnrollmentMixin:
    """Mixin that adds enroll, drop, and enrollment-list capabilities."""

    # ------------------------------------------------------------------ #
    #  Enroll
    # ------------------------------------------------------------------ #
    def enroll_in_module(self, module_code):
        """
        Enroll the current student in *module_code*.

        Validates:
        - Student is not already enrolled.
        - Module capacity has not been exceeded.
        """
        if not self.student_id:
            if getattr(self, 'is_privileged', False):
                messagebox.showinfo(
                    "Select a student",
                    "Choose a student from the picker at the top of the "
                    "portal before changing module registration.")
            else:
                messagebox.showerror(
                    "Error", "No student ID found. Please log in again.")
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # The enrolling identity must be a real student row, or the
            # INSERT below trips the student_modules→students foreign key.
            # Admins/staff have auth IDs that are not student records, so
            # fail with a clear message instead of a raw IntegrityError.
            cursor.execute(
                "SELECT 1 FROM students WHERE student_id = ?",
                (self.student_id,),
            )
            if not cursor.fetchone():
                messagebox.showerror(
                    "Not a student account",
                    f"Account '{self.student_id}' has no student record, so it "
                    "cannot be enrolled in modules.\n\n"
                    "Log in with a student account to register for modules.",
                )
                conn.close()
                return

            # Check if already enrolled or previously enrolled (dropped)
            cursor.execute(
                "SELECT status FROM student_modules "
                "WHERE student_id = ? AND module_code = ?",
                (self.student_id, module_code),
            )
            existing = cursor.fetchone()
            if existing:
                if existing[0] == 'Enrolled':
                    messagebox.showwarning(
                        "Already Enrolled",
                        f"You are already enrolled in {module_code}.",
                    )
                    conn.close()
                    return
                else:
                    # Re-enroll: update existing row back to Enrolled
                    enrollment_date = date.today().isoformat()
                    cursor.execute(
                        "UPDATE student_modules SET status = 'Enrolled', enrollment_date = ? "
                        "WHERE student_id = ? AND module_code = ?",
                        (enrollment_date, self.student_id, module_code),
                    )
                    conn.commit()
                    conn.close()
                    messagebox.showinfo("Success", f"Re-enrolled in {module_code}.")
                    if hasattr(self, '_refresh_enrollment_tree'):
                        self._refresh_enrollment_tree()
                    if hasattr(self, '_refresh_available_modules'):
                        self._refresh_available_modules()
                    return

            # Check module exists
            cursor.execute(
                "SELECT module_code FROM modules WHERE module_code = ?",
                (module_code,),
            )
            row = cursor.fetchone()
            if not row:
                messagebox.showerror("Error", f"Module {module_code} not found.")
                conn.close()
                return

            # Finance hold gate — refuse enrolment if the student has any
            # active hold (overdue library fines, unpaid fees, etc.). Soft
            # fail on lookup errors so a finance outage doesn't block
            # registration.
            try:
                from education_system.systems.university.services.bus.finance_bus import (
                    has_active_hold, list_active_holds,
                )
                if has_active_hold(self.student_id):
                    holds = list_active_holds(self.student_id)
                    reasons = ", ".join(h.get("reason", "") for h in holds[:3]) or "active hold"
                    messagebox.showerror(
                        "Enrolment blocked",
                        f"Cannot enrol {self.student_id} in {module_code}: "
                        f"finance hold active ({reasons}).\n\n"
                        "Resolve outstanding charges or have an admin "
                        "release the hold, then retry.",
                    )
                    conn.close()
                    return
            except Exception as hold_err:
                logger.warning("Hold check failed (proceeding): %s", hold_err)

            # Capacity check (no limit if column doesn't exist)
            max_capacity = None
            if max_capacity:
                cursor.execute(
                    "SELECT COUNT(*) FROM student_modules "
                    "WHERE module_code = ? AND status = 'Enrolled'",
                    (module_code,),
                )
                current_count = cursor.fetchone()[0]
                if current_count >= max_capacity:
                    messagebox.showwarning(
                        "Module Full",
                        f"Module {module_code} has reached its maximum capacity "
                        f"({current_count}/{max_capacity}).",
                    )
                    conn.close()
                    return

            # Perform enrollment
            enrollment_date = date.today().isoformat()
            cursor.execute(
                "INSERT INTO student_modules "
                "(student_id, module_code, status, enrollment_date) "
                "VALUES (?, ?, 'Enrolled', ?)",
                (self.student_id, module_code, enrollment_date),
            )
            conn.commit()
            conn.close()

            messagebox.showinfo(
                "Enrollment Successful",
                f"You have been enrolled in {module_code}.",
            )
            logger.info(
                "Student %s enrolled in %s", self.student_id, module_code,
            )
            try:
                from education_system.systems.university.services.bus.integration_bus import (
                    publish_enrolment_added,
                )
                publish_enrolment_added(
                    str(self.student_id), module_code,
                    source="student_registration",
                )
            except Exception:
                pass

            # Best-effort enrolment confirmation email.
            try:
                with get_connection() as conn2:
                    mod_row = conn2.execute(
                        "SELECT module_name, credits, academic_year, semester "
                        "FROM modules WHERE module_code = ?",
                        (module_code,),
                    ).fetchone()
                _send_lifecycle_email('enrolment_confirmation', str(self.student_id), {
                    'module_code':         module_code,
                    'module_name':         (mod_row[0] if mod_row else module_code),
                    'credits':             (mod_row[1] if mod_row else '(see portal)'),
                    'academic_year':       (mod_row[2] if mod_row else '(see portal)'),
                    'semester':            (mod_row[3] if mod_row else '(see portal)'),
                    'enrolment_date':      enrollment_date,
                    'mode_of_study':       '(see student record)',
                    'first_session_date':  '(see timetable)',
                    'drop_deadline':       '(see academic calendar)',
                })
            except Exception:
                logger.exception("enrolment email dispatch failed")
            self._refresh_views()

        except Exception as exc:
            logger.error("Enrollment error: %s", exc)
            messagebox.showerror("Error", f"Failed to enroll: {exc}")

    # ------------------------------------------------------------------ #
    #  Drop
    # ------------------------------------------------------------------ #
    def drop_module(self, module_code):
        """Drop *module_code* for the current student after confirmation."""
        if not self.student_id:
            if getattr(self, 'is_privileged', False):
                messagebox.showinfo(
                    "Select a student",
                    "Choose a student from the picker at the top of the "
                    "portal before changing module registration.")
            else:
                messagebox.showerror(
                    "Error", "No student ID found. Please log in again.")
            return

        confirmed = messagebox.askyesno(
            "Confirm Drop",
            f"Are you sure you want to drop module {module_code}?\n"
            "This action can be undone by re-enrolling.",
        )
        if not confirmed:
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE student_modules SET status = 'Dropped' "
                "WHERE student_id = ? AND module_code = ? AND status = 'Enrolled'",
                (self.student_id, module_code),
            )
            conn.commit()
            conn.close()

            messagebox.showinfo(
                "Module Dropped",
                f"You have dropped module {module_code}.",
            )
            logger.info(
                "Student %s dropped %s", self.student_id, module_code,
            )

            # Best-effort withdrawal acknowledgement email.
            try:
                with get_connection() as conn2:
                    mod_row = conn2.execute(
                        "SELECT module_name FROM modules WHERE module_code = ?",
                        (module_code,),
                    ).fetchone()
                _send_lifecycle_email('withdrawal_acknowledgement', str(self.student_id), {
                    'module_code':       module_code,
                    'module_name':       (mod_row[0] if mod_row else module_code),
                    'withdrawal_date':   date.today().isoformat(),
                    'withdrawal_reason': '(self-service drop)',
                    'recorded_by':       'Student Tools',
                    'transcript_status': '(see academic calendar for whether this shows on transcript)',
                })
            except Exception:
                logger.exception("withdrawal email dispatch failed")
            self._refresh_views()

        except Exception as exc:
            logger.error("Drop module error: %s", exc)
            messagebox.showerror("Error", f"Failed to drop module: {exc}")

    # ------------------------------------------------------------------ #
    #  My Enrollment tab
    # ------------------------------------------------------------------ #
    def show_my_enrollment(self, parent):
        """Display a treeview of the student's enrolled modules."""
        header = ttk.Label(
            parent, text="My Enrollment",
            font=('Arial', 16, 'bold'),
        )
        header.pack(pady=(15, 10))

        # --- Treeview -------------------------------------------------- #
        columns = ('Code', 'Name', 'Credits', 'Status', 'Enrolled Date')
        tree_frame = ttk.Frame(parent)
        tree_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.enrollment_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings', height=15,
        )
        widths = {'Code': 100, 'Name': 250, 'Credits': 70, 'Status': 100, 'Enrolled Date': 120}
        for col in columns:
            self.enrollment_tree.heading(col, text=col)
            self.enrollment_tree.column(col, width=widths.get(col, 100), anchor='w')

        vsb = ttk.Scrollbar(
            tree_frame, orient='vertical', command=self.enrollment_tree.yview,
        )
        self.enrollment_tree.configure(yscrollcommand=vsb.set)

        self.enrollment_tree.grid(row=0, column=0, sticky='nsew')
        vsb.grid(row=0, column=1, sticky='ns')
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # --- Buttons --------------------------------------------------- #
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill='x', padx=10, pady=(5, 10))

        ttk.Button(
            btn_frame, text="Drop Selected Module",
            command=self._drop_selected_module,
        ).pack(side='left', padx=5)

        ttk.Button(
            btn_frame, text="Refresh",
            command=self._refresh_enrollment_tree,
        ).pack(side='left', padx=5)

        # Populate
        self._refresh_enrollment_tree()

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #
    def _refresh_enrollment_tree(self):
        """Reload the enrollment treeview from the database."""
        self.enrollment_tree.delete(*self.enrollment_tree.get_children())

        if not self.student_id:
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT sm.module_code, m.module_name, m.credits, "
                "sm.status, sm.enrollment_date "
                "FROM student_modules sm "
                "JOIN modules m ON sm.module_code = m.module_code "
                "WHERE sm.student_id = ? "
                "ORDER BY sm.enrollment_date DESC",
                (self.student_id,),
            )
            for row in cursor.fetchall():
                self.enrollment_tree.insert('', 'end', values=tuple(row))
            conn.close()
        except Exception as exc:
            logger.error("Refresh enrollment error: %s", exc)
            messagebox.showerror("Error", f"Failed to load enrollment: {exc}")

    def _drop_selected_module(self):
        """Drop the module currently selected in the enrollment treeview."""
        sel = self.enrollment_tree.selection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select a module to drop.")
            return
        values = self.enrollment_tree.item(sel[0], 'values')
        module_code = values[0]
        status = values[3]
        if status != 'Enrolled':
            messagebox.showwarning(
                "Cannot Drop",
                f"Module {module_code} has status '{status}' and cannot be dropped.",
            )
            return
        self.drop_module(module_code)

    def _refresh_views(self):
        """Refresh both the available-modules and enrollment treeviews."""
        try:
            if hasattr(self, 'modules_tree'):
                self._refresh_available_modules()
        except Exception:
            pass
        try:
            if hasattr(self, 'enrollment_tree'):
                self._refresh_enrollment_tree()
        except Exception:
            pass
