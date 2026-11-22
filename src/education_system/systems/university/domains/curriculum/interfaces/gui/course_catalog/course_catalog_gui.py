"""Course Catalog & Self-Registration GUI (Feature 36).

Allows students to search the course catalog, view enrollment counts, and
register for (or drop) courses.  If a course is full the student is offered
a spot on the waitlist.
"""

from education_system.systems.university.infrastructure.i18n import get_text as _t

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.application.programmes import catalogue
from education_system.systems.university.application.self_service.identity import resolve_student
from education_system.systems.university.infrastructure.database.db import get_connection, transaction
from education_system.systems.university.infrastructure.utils.activity_logger import log_activity
from education_system.systems.university.services.bus.enrolment_bus import (
    check_enrolment_eligibility,
)
from education_system.systems.university.services.bus.registration_calendar import (
    classify_drop,
    record_status_change,
)
from education_system.systems.university.domains.curriculum.interfaces.gui._section_picker import (
    choose_section,
)

logger = logging.getLogger(__name__)


class CourseCatalogGUI:
    """Toplevel window for browsing and registering for courses."""

    def __init__(self, parent, auth=None):
        self.parent = parent
        self.auth = auth
        self.student_id = self._signed_in_student()

        self.window = tk.Toplevel(parent)
        self.window.title(_t('gui.academics.course_catalog.course_catalog.windows.course_catalog_registration', default="Course Catalog & Registration"))
        self.window.geometry("1100x700")
        self.window.transient(parent)

        self._setup_ui()
        self._search_courses()

    def _signed_in_student(self):
        """The signed-in student's number; '' for staff, who have no student record."""
        user = getattr(self.auth, 'current_user', None) if self.auth else None
        if not user:
            return ''
        try:
            with get_connection() as conn:
                student = resolve_student(conn, user)
        except Exception:
            logger.exception("Could not work out the signed-in student")
            return ''
        return student.student_id if student else ''

    def _refuse_without_student(self):
        """True (after saying why) if this account has no student record to act on."""
        if self.student_id:
            return False
        messagebox.showinfo(
            _t('gui.academics.course_catalog.course_catalog.dialogs.no_student_record', default="No student record"),
            _t('gui.academics.course_catalog.course_catalog.dialogs.account_has_no_student_record',
               default="This account has no student record, so it can only browse the catalogue. "
                       "Students register from their own login."),
            parent=self.window,
        )
        return True

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        """Build the catalog layout."""
        ttk.Label(
            self.window,
            text=_t('gui.academics.course_catalog.course_catalog.labels.course_catalog_registration', default="Course Catalog & Registration"),
            font=('Arial', 16, 'bold'),
        ).pack(pady=(10, 5))

        # ---- Search / filter bar ----
        search_frame = ttk.Frame(self.window)
        search_frame.pack(fill=tk.X, padx=15, pady=5)

        ttk.Label(search_frame, text=_t('gui.academics.course_catalog.course_catalog.labels.search', default="Search:")).pack(side=tk.LEFT, padx=(0, 5))
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=(0, 10))
        search_entry.bind('<Return>', lambda e: self._search_courses())

        ttk.Label(search_frame, text=_t('gui.academics.course_catalog.course_catalog.labels.type', default="Type:")).pack(side=tk.LEFT, padx=(0, 5))
        self.type_var = tk.StringVar(value=_t('gui.academics.course_catalog.course_catalog.values.all', default='All'))
        self.type_combo = ttk.Combobox(
            search_frame, textvariable=self.type_var,
            values=['All'], state='readonly', width=12,
        )
        self.type_combo.pack(side=tk.LEFT, padx=(0, 10))
        self.type_combo.bind('<<ComboboxSelected>>', lambda _e: self._search_courses())

        ttk.Button(search_frame, text=_t('gui.academics.course_catalog.course_catalog.buttons.search', default="Search"), command=self._search_courses).pack(side=tk.LEFT)

        # ---- Courses, then the modules of the chosen one ----
        panes = ttk.PanedWindow(self.window, orient=tk.VERTICAL)
        panes.pack(fill=tk.BOTH, expand=True, padx=15, pady=5)

        course_frame = ttk.LabelFrame(panes, text=_t('gui.academics.course_catalog.course_catalog.labels.courses', default="Courses"))
        panes.add(course_frame, weight=1)
        cols = ('code', 'name', 'credits', 'type', 'department', 'enrolled_capacity', 'status')
        self.tree = ttk.Treeview(course_frame, columns=cols, show='headings', height=9, selectmode='browse')
        self.tree.heading('code', text=_t('gui.academics.course_catalog.course_catalog.headings.code', default='Code'))
        self.tree.heading('name', text=_t('gui.academics.course_catalog.course_catalog.headings.course_name', default='Course Name'))
        self.tree.heading('credits', text=_t('gui.academics.course_catalog.course_catalog.headings.credits', default='Credits'))
        self.tree.heading('type', text=_t('gui.academics.course_catalog.course_catalog.headings.type', default='Type'))
        self.tree.heading('department', text=_t('gui.academics.course_catalog.course_catalog.headings.department', default='Department'))
        self.tree.heading('enrolled_capacity', text=_t('gui.academics.course_catalog.course_catalog.headings.enrolled_cap', default='Enrolled/Cap'))
        self.tree.heading('status', text=_t('gui.academics.course_catalog.course_catalog.headings.status', default='Status'))
        for col, width, anchor in (('code', 80, 'w'), ('name', 280, 'w'), ('credits', 70, 'center'),
                                   ('type', 90, 'center'), ('department', 200, 'w'),
                                   ('enrolled_capacity', 110, 'center'), ('status', 100, 'center')):
            self.tree.column(col, width=width, anchor=anchor)
        tree_scroll = ttk.Scrollbar(course_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tree_scroll.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind('<<TreeviewSelect>>', lambda _e: self._load_modules())

        self.module_frame = ttk.LabelFrame(panes, text=_t('gui.academics.course_catalog.course_catalog.labels.modules_on_course', default="Modules on this course"))
        panes.add(self.module_frame, weight=1)
        cols = ('code', 'name', 'year', 'credits', 'type', 'enrolled', 'status')
        self.module_tree = ttk.Treeview(self.module_frame, columns=cols, show='headings', height=10, selectmode='browse')
        for col, title, width, anchor in (('code', 'Code', 110, 'w'), ('name', 'Module Name', 300, 'w'),
                                          ('year', 'Year', 50, 'center'), ('credits', 'Credits', 70, 'center'),
                                          ('type', 'Type', 110, 'center'), ('enrolled', 'Enrolled', 80, 'center'),
                                          ('status', 'Status', 100, 'center')):
            self.module_tree.heading(col, text=title)
            self.module_tree.column(col, width=width, anchor=anchor)
        module_scroll = ttk.Scrollbar(self.module_frame, orient=tk.VERTICAL, command=self.module_tree.yview)
        self.module_tree.configure(yscrollcommand=module_scroll.set)
        self.module_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        module_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Action buttons ----
        btn_frame = ttk.Frame(self.window)
        btn_frame.pack(fill=tk.X, padx=15, pady=(5, 10))

        ttk.Button(btn_frame, text=_t('gui.academics.course_catalog.course_catalog.buttons.register', default="Register"), command=self._register).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.course_catalog.course_catalog.buttons.drop', default="Drop"), command=self._drop).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text=_t('gui.academics.course_catalog.course_catalog.buttons.refresh', default="Refresh"), command=self._search_courses).pack(side=tk.RIGHT, padx=5)

        self.status_var = tk.StringVar(value="")
        ttk.Label(self.window, textvariable=self.status_var).pack(anchor='w', padx=15, pady=(0, 5))

    # ------------------------------------------------------------------
    # Searching
    # ------------------------------------------------------------------

    def _search_courses(self):
        """List the courses matching the search and type, keeping the selection."""
        chosen = self.tree.selection()
        for item in self.tree.get_children():
            self.tree.delete(item)

        type_filter = self.type_var.get()
        try:
            with get_connection() as conn:
                self.type_combo['values'] = ['All', *catalogue.course_types(conn)]
                rows = catalogue.courses(
                    conn, self.search_var.get(),
                    type_filter if type_filter and type_filter != 'All' else None,
                    self.student_id or None)
        except Exception as e:
            logger.error(f"Error searching courses: {e}")
            self.status_var.set(f"Error: {e}")
            messagebox.showerror(_t('gui.academics.course_catalog.course_catalog.dialogs.error', default="Error"), f"Failed to search courses: {e}", parent=self.window)
            return

        own = None
        for row in rows:
            self.tree.insert('', tk.END, iid=row['code'], values=(
                row['code'], row['name'], row['credits'], row['type'], row['department'],
                f"{row['enrolled']}/{row['capacity']}", row['status'],
            ))
            if row['status'] == 'Your course':
                own = row['code']
        self.status_var.set(f"{len(rows)} course(s) found.")

        select = chosen[0] if chosen and self.tree.exists(chosen[0]) else own
        if select:
            self.tree.selection_set(select)
            self.tree.see(select)
        self._load_modules()

    def _load_modules(self):
        """List the modules of the selected course."""
        chosen_module = self.module_tree.selection()
        for item in self.module_tree.get_children():
            self.module_tree.delete(item)
        chosen = self.tree.selection()
        if not chosen:
            self.module_frame.configure(text=_t('gui.academics.course_catalog.course_catalog.labels.modules_on_course', default="Modules on this course"))
            return
        code = chosen[0]
        try:
            with get_connection() as conn:
                rows = catalogue.modules_on(conn, code, self.student_id or None)
        except Exception as e:
            logger.error(f"Error loading modules of {code}: {e}")
            self.status_var.set(f"Error: {e}")
            return
        self.module_frame.configure(text=f"Modules on {code} ({len(rows)})")
        for row in rows:
            self.module_tree.insert('', tk.END, iid=row['code'], values=(
                row['code'], row['name'], row['year'], row['credits'], row['designation'],
                row['enrolled'], row['status'],
            ))
        if chosen_module and self.module_tree.exists(chosen_module[0]):
            self.module_tree.selection_set(chosen_module[0])

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def _get_selected_code(self):
        """Return the module_code of the selected module row, or None."""
        sel = self.module_tree.selection()
        if not sel:
            messagebox.showwarning(_t('gui.academics.course_catalog.course_catalog.dialogs.no_selection', default="No Selection"), _t('gui.academics.course_catalog.course_catalog.dialogs.select_a_module_first', default="Choose a course, then select a module from its list."), parent=self.window)
            return None
        return sel[0]

    def _register(self):
        """Register the student for the selected module, or offer waitlist if full."""
        if self._refuse_without_student():
            return

        module_code = self._get_selected_code()
        if not module_code:
            return

        try:
            with get_connection() as conn:
                # Check if already enrolled
                existing = conn.execute(
                    "SELECT status FROM student_modules "
                    "WHERE student_id = ? AND module_code = ?",
                    (self.student_id, module_code),
                ).fetchone()
                if existing and existing[0] == 'Enrolled':
                    messagebox.showinfo(
                        _t('gui.academics.course_catalog.course_catalog.dialogs.already_enrolled', default="Already Enrolled"),
                        f"You are already enrolled in {module_code}.",
                        parent=self.window,
                    )
                    return
                if existing and existing[0] != 'Dropped':
                    # One row per student and module, and only a clean drop is
                    # reopened here: a withdrawal or a result stays on the record.
                    messagebox.showinfo(
                        _t('gui.academics.course_catalog.course_catalog.dialogs.module_on_record', default="Already on your record"),
                        f"{module_code} is on your record as {existing[0]}, "
                        "so it can't be registered for again here.",
                        parent=self.window,
                    )
                    return

                # One gate for the registration window, prerequisites,
                # co-requisites, capacity and sections — shared with the
                # student registration GUI and the REST route so the three
                # cannot drift apart.
                eligibility = check_enrolment_eligibility(
                    self.student_id, module_code, conn=conn,
                )

                section_id = None
                if eligibility.needs_section and eligibility.sections:
                    section_id = choose_section(
                        self.window, module_code, eligibility.sections)
                    if section_id is None:
                        return
                    eligibility = check_enrolment_eligibility(
                        self.student_id, module_code, section_id=section_id,
                        conn=conn,
                    )

            if not eligibility.ok:
                if eligibility.only_capacity:
                    # Full, but otherwise eligible -- offer the waitlist.
                    if messagebox.askyesno(
                        _t('gui.academics.course_catalog.course_catalog.dialogs.course_full', default="Course Full"),
                        f"{eligibility.reason()} "
                        "Would you like to join the waitlist?",
                        parent=self.window,
                    ):
                        self._add_to_waitlist(module_code, section_id)
                    return
                # A prerequisite or co-requisite is missing: the waitlist
                # would not help, so say what is actually required.
                messagebox.showwarning(
                    _t('gui.academics.course_catalog.course_catalog.dialogs.enrolment_not_permitted',
                       default="Enrolment not permitted"),
                    f"You cannot register for {module_code} yet.\n\n"
                    f"{eligibility.reason()}",
                    parent=self.window,
                )
                logger.info(
                    "Registration blocked for %s in %s: %s",
                    self.student_id, module_code,
                    eligibility.reason().replace("\n", "; "),
                )
                return

            # Perform enrollment inside a transaction
            with transaction() as conn:
                # Check for a dropped record to update, otherwise insert
                dropped = conn.execute(
                    "SELECT rowid FROM student_modules "
                    "WHERE student_id = ? AND module_code = ? AND status = 'Dropped'",
                    (self.student_id, module_code),
                ).fetchone()

                if dropped:
                    if section_id is None:
                        conn.execute(
                            "UPDATE student_modules SET status = 'Enrolled', "
                            "enrollment_date = datetime('now') "
                            "WHERE student_id = ? AND module_code = ? AND status = 'Dropped'",
                            (self.student_id, module_code),
                        )
                    else:
                        conn.execute(
                            "UPDATE student_modules SET status = 'Enrolled', "
                            "enrollment_date = datetime('now'), section_id = ? "
                            "WHERE student_id = ? AND module_code = ? AND status = 'Dropped'",
                            (section_id, self.student_id, module_code),
                        )
                elif section_id is None:
                    conn.execute(
                        "INSERT INTO student_modules "
                        "(student_id, module_code, status, enrollment_date) "
                        "VALUES (?, ?, 'Enrolled', datetime('now'))",
                        (self.student_id, module_code),
                    )
                else:
                    conn.execute(
                        "INSERT INTO student_modules "
                        "(student_id, module_code, status, enrollment_date, section_id) "
                        "VALUES (?, ?, 'Enrolled', datetime('now'), ?)",
                        (self.student_id, module_code, section_id),
                    )
                record_status_change(
                    self.student_id, module_code, 'Enrolled',
                    from_status='Dropped' if dropped else None,
                    changed_by=self.student_id, source='course_catalog',
                    verdict=eligibility.window, conn=conn,
                )

            try:
                log_activity(
                    self.student_id, self.student_id, 'student',
                    'create', 'enrollment',
                    details=f"Enrolled in {module_code}",
                )
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

            messagebox.showinfo(
                _t('gui.academics.course_catalog.course_catalog.dialogs.enrolled', default="Enrolled"),
                f"Successfully enrolled in {module_code}.",
                parent=self.window,
            )
            self._search_courses()

        except Exception as e:
            logger.error(f"Error registering for {module_code}: {e}")
            messagebox.showerror(
                _t('gui.academics.course_catalog.course_catalog.dialogs.error', default="Error"), f"Registration failed: {e}", parent=self.window
            )

    def _add_to_waitlist(self, module_code, section_id=None):
        """Add the student to the module waitlist.

        ``module_waitlist`` (application/modules/enrolment) is the queue
        Module Management promotes from when a place frees up. The old
        ``course_waitlist`` insert could never succeed: that table's
        ``course_id`` is NOT NULL and ``added_at`` has no default.
        """
        from education_system.systems.university.application.modules import (
            enrolment as module_enrolment,
        )
        try:
            with transaction() as conn:
                next_pos = module_enrolment.join_waitlist(
                    conn, module_code, self.student_id, section_id)

            try:
                log_activity(
                    self.student_id, self.student_id, 'student',
                    'create', 'waitlist',
                    details=f"Added to waitlist for {module_code} at position {next_pos}",
                )
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

            messagebox.showinfo(
                _t('gui.academics.course_catalog.course_catalog.dialogs.waitlisted', default="Waitlisted"),
                f"You have been added to the waitlist for {module_code} "
                f"at position {next_pos}.",
                parent=self.window,
            )
            self._search_courses()

        except Exception as e:
            logger.error(f"Error adding to waitlist for {module_code}: {e}")
            messagebox.showerror(
                _t('gui.academics.course_catalog.course_catalog.dialogs.error', default="Error"), f"Failed to join waitlist: {e}", parent=self.window
            )

    # ------------------------------------------------------------------
    # Drop
    # ------------------------------------------------------------------

    def _drop(self):
        """Drop the student from the selected module."""
        if self._refuse_without_student():
            return

        module_code = self._get_selected_code()
        if not module_code:
            return

        # The academic calendar decides whether this is a clean drop, a
        # transcript-visible withdrawal, or something only the formal process
        # can do now.
        verdict = classify_drop()
        if not verdict["allowed"]:
            messagebox.showwarning(
                _t('gui.academics.course_catalog.course_catalog.dialogs.deadline_passed',
                   default="Deadline passed"),
                f"{module_code} cannot be dropped here.\n\n{verdict['reason']}",
                parent=self.window,
            )
            return

        new_status = verdict["status"]
        prompt = [f"Are you sure you want to drop {module_code}?"]
        if verdict["reason"]:
            prompt += ["", verdict["reason"]]
        if not messagebox.askyesno(
            _t('gui.academics.course_catalog.course_catalog.dialogs.confirm_drop', default="Confirm Drop"),
            "\n".join(prompt),
            parent=self.window,
        ):
            return

        try:
            with transaction() as conn:
                conn.execute(
                    "UPDATE student_modules SET status = ? "
                    "WHERE student_id = ? AND module_code = ? AND status = 'Enrolled'",
                    (new_status, self.student_id, module_code),
                )
                record_status_change(
                    self.student_id, module_code, new_status,
                    from_status='Enrolled', changed_by=self.student_id,
                    source='course_catalog', verdict=verdict, conn=conn,
                )
                # The freed place goes to the first eligible student waiting.
                from education_system.systems.university.application.modules import (
                    enrolment as module_enrolment,
                )
                try:
                    module_enrolment.promote_all(conn, module_code, 'course_catalog')
                except Exception:
                    logger.exception("waitlist promotion after dropping %s failed", module_code)

            try:
                log_activity(
                    self.student_id, self.student_id, 'student',
                    'update', 'enrollment',
                    details=f"{new_status} {module_code} ({verdict['phase']})",
                )
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

            messagebox.showinfo(
                _t('gui.academics.course_catalog.course_catalog.dialogs.dropped', default="Dropped"),
                f"You have been {'withdrawn from' if verdict['on_transcript'] else 'dropped from'} "
                f"{module_code}.",
                parent=self.window,
            )
            self._search_courses()

        except Exception as e:
            logger.error(f"Error dropping {module_code}: {e}")
            messagebox.showerror(
                _t('gui.academics.course_catalog.course_catalog.dialogs.error', default="Error"), f"Failed to drop course: {e}", parent=self.window
            )
