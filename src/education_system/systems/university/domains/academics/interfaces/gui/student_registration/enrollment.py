"""
Enrollment Mixin

Handles enrolling in modules, dropping modules, and displaying the
student's current enrollment list.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.domains.academics.interfaces.gui._section_picker import (
    choose_section,
)

from education_system.systems.university.domains.academics.interfaces.gui.student_registration.common_imports import get_connection, logger
from education_system.systems.university.services.bus.enrolment_bus import (
    check_enrolment_eligibility,
)
from education_system.systems.university.services.bus.registration_calendar import (
    classify_drop,
    record_status_change,
)


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
    #  Eligibility
    # ------------------------------------------------------------------ #
    def _picker_parent(self):
        """A window to parent the section chooser on.

        The portal is composed of mixins with no single agreed attribute for
        its window, so take the first that exists and fall back to the default
        root rather than failing the enrolment over a dialog parent.
        """
        for attr in ('window', 'root', 'parent', 'master'):
            widget = getattr(self, attr, None)
            if widget is not None:
                return widget
        return tk._default_root

    def _confirm_eligibility_override(self, module_code, eligibility) -> bool:
        """Report why enrolment is blocked; return True only to proceed anyway.

        Students are refused outright. A privileged user (registry/admin
        acting through the student picker) is offered an override, which is
        logged with the reasons so the exception is auditable.
        """
        reasons = eligibility.reason()
        if not getattr(self, 'is_privileged', False):
            messagebox.showwarning(
                _t('gui.academics.student_registration.enrollment.dialogs.enrolment_not_permitted',
                   default="Enrolment not permitted"),
                f"You cannot enrol in {module_code} yet.\n\n{reasons}",
            )
            logger.info(
                "Enrolment blocked for %s in %s: %s",
                self.student_id, module_code, reasons.replace("\n", "; "),
            )
            return False

        proceed = messagebox.askyesno(
            _t('gui.academics.student_registration.enrollment.dialogs.override_enrolment_rules',
               default="Override enrolment rules?"),
            f"{module_code} is blocked for {self.student_id}:\n\n{reasons}\n\n"
            "Enrol anyway? The override will be recorded.",
        )
        if proceed:
            logger.warning(
                "Enrolment rules overridden by staff for %s in %s: %s",
                self.student_id, module_code, reasons.replace("\n", "; "),
            )
        else:
            logger.info(
                "Enrolment blocked for %s in %s: %s",
                self.student_id, module_code, reasons.replace("\n", "; "),
            )
        return proceed

    # ------------------------------------------------------------------ #
    #  Enroll
    # ------------------------------------------------------------------ #
    def enroll_in_module(self, module_code):
        """
        Enroll the current student in *module_code*.

        Validates:
        - The identity is a real student record.
        - Student is not already enrolled.
        - No finance hold is active.
        - Enrolment rules pass: prerequisites, co-requisites and capacity
          (see ``services.bus.enrolment_bus``). Staff may override with an
          audited confirmation; a student may not.
        """
        if not self.student_id:
            if getattr(self, 'is_privileged', False):
                messagebox.showinfo(
                    _t('gui.academics.student_registration.enrollment.dialogs.select_a_student', default="Select a student"),
                    _t('gui.academics.student_registration.enrollment.dialogs.choose_a_student_from_the_picker_at_the_top_of_the_portal_before', default="Choose a student from the picker at the top of the "
                    "portal before changing module registration."))
            else:
                messagebox.showerror(
                    _t('gui.academics.student_registration.enrollment.dialogs.error', default="Error"), _t('gui.academics.student_registration.enrollment.dialogs.no_student_id_found_please_log_in_again', default="No student ID found. Please log in again."))
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
                    _t('gui.academics.student_registration.enrollment.dialogs.not_a_student_account', default="Not a student account"),
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
            if existing and existing[0] == 'Enrolled':
                messagebox.showwarning(
                    _t('gui.academics.student_registration.enrollment.dialogs.already_enrolled', default="Already Enrolled"),
                    f"You are already enrolled in {module_code}.",
                )
                conn.close()
                return
            # A dropped row is re-activated further down rather than here:
            # re-enrolling is still an enrolment, and used to skip the finance
            # hold and every rule below by returning early.
            previous_status = existing[0] if existing else None

            # Check module exists
            cursor.execute(
                "SELECT module_code FROM modules WHERE module_code = ?",
                (module_code,),
            )
            row = cursor.fetchone()
            if not row:
                messagebox.showerror(_t('gui.academics.student_registration.enrollment.dialogs.error', default="Error"), f"Module {module_code} not found.")
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
                        _t('gui.academics.student_registration.enrollment.dialogs.enrolment_blocked', default="Enrolment blocked"),
                        f"Cannot enrol {self.student_id} in {module_code}: "
                        f"finance hold active ({reasons}).\n\n"
                        "Resolve outstanding charges or have an admin "
                        "release the hold, then retry.",
                    )
                    conn.close()
                    return
            except Exception as hold_err:
                logger.warning("Hold check failed (proceeding): %s", hold_err)

            # Eligibility gate — prerequisites, co-requisites and capacity.
            # This replaces a dead capacity check (`max_capacity = None`
            # followed by `if max_capacity:`) that could never fire, and adds
            # the prerequisite enforcement that previously existed only on
            # the advisory degree-audit screens. Staff acting on a student's
            # behalf may override with an audited confirmation; a student
            # cannot.
            eligibility = check_enrolment_eligibility(
                self.student_id, module_code, conn=conn,
            )

            # A module that runs in sections needs one chosen before the rest
            # of the verdict means anything; re-check with the choice made.
            section_id = None
            if eligibility.needs_section and eligibility.sections:
                section_id = choose_section(
                    self._picker_parent(), module_code, eligibility.sections)
                if section_id is None:
                    conn.close()
                    return
                eligibility = check_enrolment_eligibility(
                    self.student_id, module_code, section_id=section_id, conn=conn,
                )

            if not eligibility.ok:
                if not self._confirm_eligibility_override(module_code, eligibility):
                    conn.close()
                    return

            # Perform enrollment: reactivate the dropped row if there is one,
            # otherwise insert. Section is only written when one was chosen,
            # so databases without the column are untouched.
            enrollment_date = date.today().isoformat()
            if previous_status:
                if section_id is None:
                    cursor.execute(
                        "UPDATE student_modules SET status = 'Enrolled', enrollment_date = ? "
                        "WHERE student_id = ? AND module_code = ?",
                        (enrollment_date, self.student_id, module_code),
                    )
                else:
                    cursor.execute(
                        "UPDATE student_modules SET status = 'Enrolled', "
                        "enrollment_date = ?, section_id = ? "
                        "WHERE student_id = ? AND module_code = ?",
                        (enrollment_date, section_id, self.student_id, module_code),
                    )
            elif section_id is None:
                cursor.execute(
                    "INSERT INTO student_modules "
                    "(student_id, module_code, status, enrollment_date) "
                    "VALUES (?, ?, 'Enrolled', ?)",
                    (self.student_id, module_code, enrollment_date),
                )
            else:
                cursor.execute(
                    "INSERT INTO student_modules "
                    "(student_id, module_code, status, enrollment_date, section_id) "
                    "VALUES (?, ?, 'Enrolled', ?, ?)",
                    (self.student_id, module_code, enrollment_date, section_id),
                )
            conn.commit()
            record_status_change(
                self.student_id, module_code, 'Enrolled',
                from_status=previous_status, changed_by=self.student_id,
                source='student_registration', verdict=eligibility.window, conn=conn,
            )
            conn.close()

            messagebox.showinfo(
                _t('gui.academics.student_registration.enrollment.dialogs.enrollment_successful', default="Enrollment Successful"),
                f"You have been {'re-enrolled' if previous_status else 'enrolled'} "
                f"in {module_code}.",
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
                logger.debug("Suppressed exception", exc_info=True)

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
            messagebox.showerror(_t('gui.academics.student_registration.enrollment.dialogs.error', default="Error"), f"Failed to enroll: {exc}")

    # ------------------------------------------------------------------ #
    #  Drop
    # ------------------------------------------------------------------ #
    def drop_module(self, module_code):
        """Drop *module_code* for the current student after confirmation."""
        if not self.student_id:
            if getattr(self, 'is_privileged', False):
                messagebox.showinfo(
                    _t('gui.academics.student_registration.enrollment.dialogs.select_a_student', default="Select a student"),
                    _t('gui.academics.student_registration.enrollment.dialogs.choose_a_student_from_the_picker_at_the_top_of_the_portal_before', default="Choose a student from the picker at the top of the "
                    "portal before changing module registration."))
            else:
                messagebox.showerror(
                    _t('gui.academics.student_registration.enrollment.dialogs.error', default="Error"), _t('gui.academics.student_registration.enrollment.dialogs.no_student_id_found_please_log_in_again', default="No student ID found. Please log in again."))
            return

        # What leaving the module means today depends on the calendar: a clean
        # drop before the deadline, a transcript-visible withdrawal after it,
        # or the formal process once the withdrawal deadline has passed.
        verdict = classify_drop()
        if not verdict["allowed"]:
            messagebox.showwarning(
                _t('gui.academics.student_registration.enrollment.dialogs.drop_deadline_passed',
                   default="Deadline passed"),
                f"{module_code} cannot be dropped here.\n\n{verdict['reason']}",
            )
            logger.info("Drop refused for %s in %s: %s",
                        self.student_id, module_code, verdict["reason"])
            return

        new_status = verdict["status"]
        confirm_lines = [f"Are you sure you want to drop module {module_code}?"]
        if verdict["reason"]:
            confirm_lines.append("")
            confirm_lines.append(verdict["reason"])
        confirm_lines.append("")
        confirm_lines.append(
            "This will appear on your transcript as a withdrawal."
            if verdict["on_transcript"]
            else "This action can be undone by re-enrolling."
        )
        confirmed = messagebox.askyesno(
            _t('gui.academics.student_registration.enrollment.dialogs.confirm_drop', default="Confirm Drop"),
            "\n".join(confirm_lines),
        )
        if not confirmed:
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE student_modules SET status = ? "
                "WHERE student_id = ? AND module_code = ? AND status = 'Enrolled'",
                (new_status, self.student_id, module_code),
            )
            conn.commit()
            # Recorded with the deadline context, so "was this drop inside the
            # window?" stays answerable after the dates are next edited.
            record_status_change(
                self.student_id, module_code, new_status,
                from_status='Enrolled', changed_by=self.student_id,
                source='student_registration', verdict=verdict, conn=conn,
            )
            conn.close()

            messagebox.showinfo(
                _t('gui.academics.student_registration.enrollment.dialogs.module_dropped', default="Module Dropped"),
                f"You have {'withdrawn from' if verdict['on_transcript'] else 'dropped'} "
                f"module {module_code}.",
            )
            logger.info(
                "Student %s %s %s (%s)", self.student_id,
                new_status.lower(), module_code, verdict["phase"],
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
                    'withdrawal_reason': f'(self-service {new_status.lower()})',
                    'recorded_by':       'Student Tools',
                    'transcript_status': ('Appears on transcript as a withdrawal'
                                          if verdict['on_transcript']
                                          else 'Does not appear on the transcript'),
                })
            except Exception:
                logger.exception("withdrawal email dispatch failed")
            self._refresh_views()

        except Exception as exc:
            logger.error("Drop module error: %s", exc)
            messagebox.showerror(_t('gui.academics.student_registration.enrollment.dialogs.error', default="Error"), f"Failed to drop module: {exc}")

    # ------------------------------------------------------------------ #
    #  My Enrollment tab
    # ------------------------------------------------------------------ #
    def show_my_enrollment(self, parent):
        """Display a treeview of the student's enrolled modules."""
        header = ttk.Label(
            parent, text=_t('gui.academics.student_registration.enrollment.labels.my_enrollment', default="My Enrollment"),
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
            btn_frame, text=_t('gui.academics.student_registration.enrollment.buttons.drop_selected_module', default="Drop Selected Module"),
            command=self._drop_selected_module,
        ).pack(side='left', padx=5)

        ttk.Button(
            btn_frame, text=_t('gui.academics.student_registration.enrollment.buttons.refresh', default="Refresh"),
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
            messagebox.showerror(_t('gui.academics.student_registration.enrollment.dialogs.error', default="Error"), f"Failed to load enrollment: {exc}")

    def _drop_selected_module(self):
        """Drop the module currently selected in the enrollment treeview."""
        sel = self.enrollment_tree.selection()
        if not sel:
            messagebox.showwarning(_t('gui.academics.student_registration.enrollment.dialogs.no_selection', default="No Selection"), _t('gui.academics.student_registration.enrollment.dialogs.please_select_a_module_to_drop', default="Please select a module to drop."))
            return
        values = self.enrollment_tree.item(sel[0], 'values')
        module_code = values[0]
        status = values[3]
        if status != 'Enrolled':
            messagebox.showwarning(
                _t('gui.academics.student_registration.enrollment.dialogs.cannot_drop', default="Cannot Drop"),
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
            logger.debug("Suppressed exception", exc_info=True)
        try:
            if hasattr(self, 'enrollment_tree'):
                self._refresh_enrollment_tree()
        except Exception:
            logger.debug("Suppressed exception", exc_info=True)
