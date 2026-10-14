"""Methods __init__ through create_whatif_tab."""

from .. import degree_audit_gui_shared as _shared
globals().update({name: value for name, value in _shared.__dict__.items() if not name.startswith("__")})

# Imported after the namespace splat so it cannot be shadowed.
from .. import report_widgets as _report


class DegreeAuditGUI:
    def __init__(self, parent, auth: UserAuth):
        self.root = tk.Toplevel(parent)
        self.root.title(_("degree_audit.title"))
        self.root.geometry("1200x700")
        self.auth = auth

        # Initialize database
        try:
            initialize_degree_audit_database()
        except Exception as e:
            print(f"Database initialization warning: {e}")

        self.create_widgets()
        self.load_courses()  # Changed from load_programs to load_courses

    def _load_student_options(self):
        """Return [(label, student_id, course_code), ...] sorted by id.

        Label format: ``"S12345 — Jane Doe (CS)"``. Empty courses
        render as ``"(unassigned)"`` so the user can still see the
        student. Cached on first call; call ``_load_student_options(refresh=True)``
        if you've added a student mid-session and want it to appear.
        """
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT student_id, "
                    "       COALESCE(first_name, '') AS fn, "
                    "       COALESCE(last_name, '')  AS ln, "
                    "       COALESCE(course, '')     AS course "
                    "FROM students "
                    "WHERE student_id IS NOT NULL "
                    "ORDER BY student_id"
                ).fetchall()
        except Exception:
            return []
        out = []
        for sid, fn, ln, course in rows:
            name = f"{fn} {ln}".strip() or "—"
            label = f"{sid} — {name} ({course or 'unassigned'})"
            out.append((label, sid, course))
        return out

    def _student_id_from_label(self, label):
        """Reverse the formatted label back to the bare student_id."""
        if not label:
            return ""
        return label.split(" — ", 1)[0].strip()

    def _populate_student_combo(self, combo):
        """Wire a Combobox to ``_load_student_options``."""
        opts = self._load_student_options()
        combo['values'] = [lbl for lbl, _sid, _c in opts]
        return opts

    def _student_modules(self, student_id):
        """Return [(module_code, module_name), ...] the student is
        enrolled on. Empty list if the student has none or the table
        is missing."""
        if not student_id:
            return []
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT sm.module_code, COALESCE(m.module_name, sm.module_code) "
                    "FROM student_modules sm "
                    "LEFT JOIN modules m ON m.module_code = sm.module_code "
                    "WHERE sm.student_id = ? "
                    "AND   LOWER(COALESCE(sm.status, 'enrolled')) = 'enrolled' "
                    "ORDER BY sm.module_code",
                    (student_id,)
                ).fetchall()
            return list(rows)
        except Exception:
            return []

    def _student_course(self, student_id):
        """Return the student's current course code, or empty string."""
        if not student_id:
            return ""
        try:
            with get_connection() as conn:
                row = conn.execute(
                    "SELECT COALESCE(course, '') FROM students WHERE student_id = ?",
                    (student_id,)
                ).fetchone()
            return row[0] if row else ""
        except Exception:
            return ""

    def _send_appointment_emails(self, *, student_id, advisor_id, date, time,
                                 duration, appointment_type, topic, notes):
        """Send appointment confirmation to both student and advisor.

        Returns ``{"sent": [...], "skipped": [...], "failed": [...]}`` so the
        caller can tell the user which notifications actually went out. It
        used to swallow every outcome, so a missing address and a delivered
        email looked identical from the GUI.

        Delivery goes through the shared email system's template loader using
        the templates registered in ``templates/email_template_mapping.json``
        (``appointment_student`` / ``appointment_advisor`` →
        ``academics/advising/…``). The templates use ``string.Template``
        ``$name`` placeholders so stray ``{}`` in the notes never interpolate.
        """
        from education_system.systems.university.infrastructure.email import (
            send_template_email,
        )

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT email_address, first_name, last_name FROM students "
                "WHERE student_id = ?", (student_id,))
            stu = cursor.fetchone()
            cursor.execute(
                "SELECT email, first_name, last_name FROM instructors WHERE id = ?",
                (advisor_id,))
            adv = cursor.fetchone()

        student_name = (
            f"{(stu[1] or '').strip()} {(stu[2] or '').strip()}".strip()
            if stu else student_id) or "Student"
        advisor_name = (
            f"{(adv[1] or '').strip()} {(adv[2] or '').strip()}".strip()
            if adv else advisor_id) or "Advisor"

        template_vars = {
            "student_name":     student_name,
            "student_id":       student_id,
            "advisor_name":     advisor_name,
            "date":             date,
            "time":             time,
            "duration":         str(duration),
            "appointment_type": appointment_type,
            "topic":            topic or "N/A",
            "notes":            notes or "(no additional notes)",
        }

        # Report what actually happened so the window can confirm it, rather
        # than the caller assuming both emails went out.
        sent, skipped, failed = [], [], []

        def _send(template_name, recipient_email, who):
            if not recipient_email:
                skipped.append(who)
                return
            try:
                send_template_email(template_name, recipient_email, template_vars)
                sent.append(f"{who} ({recipient_email})")
            except Exception as e:  # noqa: BLE001 - best-effort delivery
                print(f"Could not send advising email '{template_name}': {e}")
                failed.append(f"{who}: {e}")

        _send("appointment_student", stu[0] if stu else None, "the student")
        _send("appointment_advisor", adv[0] if adv else None, "the advisor")

        if failed and not sent:
            raise RuntimeError("; ".join(failed))
        return {"sent": sent, "skipped": skipped, "failed": failed}

    def create_widgets(self):
        """Create all GUI widgets"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        # Title
        title = ttk.Label(main_frame, text=_("degree_audit.title"),
                         font=('Arial', 16, 'bold'))
        title.pack(pady=10)

        # Notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs. Degree Audit is advising: progress, prerequisites,
        # what-if planning and appointments. The graduation audit moved to
        # the Graduation GUI, which owns eligibility through to certificate;
        # create_graduation_tab() stays defined because that GUI builds it
        # from a headless instance of this class.
        self.create_progress_tab()
        self.create_prerequisites_tab()
        self.create_whatif_tab()
        self.create_advising_tab()

    def create_progress_tab(self):
        """Create Degree Progress tracking tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("degree_audit.tabs.degree_progress"))

        # Top frame for student selection
        select_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.student_selection"), padding="10")
        select_frame.pack(fill=tk.X, pady=5)

        ttk.Label(select_frame, text=_("degree_audit.labels.student_id")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        # 8.117.92: replaced free-text Entry with Combobox sourced from
        # the students table. The legacy attribute name
        # ``progress_student_entry`` is preserved (and aliased to the
        # combo) so existing callers like ``load_student_progress`` /
        # ``update_progress`` continue to work via ``.get()``.
        self.progress_student_entry = ttk.Combobox(select_frame, width=42, state='readonly')
        self.progress_student_entry.grid(row=0, column=1, padx=5, pady=5)
        self._populate_student_combo(self.progress_student_entry)

        ttk.Button(select_frame, text=_("degree_audit.buttons.load_progress"),
                  command=self.load_student_progress).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(select_frame, text=_("degree_audit.buttons.update_progress"),
                  command=self.update_progress).grid(row=0, column=3, padx=5, pady=5)
        # 8.117.92: "Initialise Progress" button removed — it conflicted
        # with existing degree-progress data by overwriting it. The
        # ``initialize_progress`` method itself is kept in case other
        # callers use it; it just isn't reachable from the UI.

        # Progress summary frame
        summary_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.progress_summary"), padding="10")
        summary_frame.pack(fill=tk.X, pady=5)

        self.progress_labels = {}
        self.progress_label_keys = ['Program', 'Credits Earned', 'Credits Required', 'Current GPA',
                 'Completion %', 'Enrollment Year', 'Expected Graduation']
        label_translations = {
            'Program': _("degree_audit.labels.program"),
            'Credits Earned': _("degree_audit.labels.credits_earned"),
            'Credits Required': _("degree_audit.labels.credits_required"),
            'Current GPA': _("degree_audit.labels.current_gpa"),
            'Completion %': _("degree_audit.labels.completion_percent"),
            'Enrollment Year': _("degree_audit.labels.enrollment_year"),
            'Expected Graduation': _("degree_audit.labels.expected_graduation")
        }

        for i, label in enumerate(self.progress_label_keys):
            ttk.Label(summary_frame, text=f"{label_translations[label]}:", font=('Arial', 10, 'bold')).grid(
                row=i//2, column=(i%2)*2, sticky=tk.W, padx=10, pady=5)
            self.progress_labels[label] = ttk.Label(summary_frame, text=_("common.not_available"))
            self.progress_labels[label].grid(row=i//2, column=(i%2)*2+1, sticky=tk.W, padx=10, pady=5)

        # Detailed progress treeview
        list_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.requirement_details"), padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        columns = ('Requirement Type', 'Name', 'Credits Required', 'Status', 'Grade Required')
        column_translations = {
            'Requirement Type': _("degree_audit.columns.requirement_type"),
            'Name': _("degree_audit.columns.name"),
            'Credits Required': _("degree_audit.columns.credits_required"),
            'Status': _("degree_audit.columns.status"),
            'Grade Required': _("degree_audit.columns.grade_required")
        }
        self.progress_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=12)

        for col in columns:
            self.progress_tree.heading(col, text=column_translations[col])
            width = 200 if col == 'Name' else 120
            self.progress_tree.column(col, width=width)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                 command=self.progress_tree.yview)
        self.progress_tree.configure(yscrollcommand=scrollbar.set)

        self.progress_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def create_prerequisites_tab(self):
        """Create Prerequisites checking tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("degree_audit.tabs.prerequisites"))

        ttk.Label(tab, text=_("degree_audit.labels.check_course_prerequisites"),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Check prerequisite frame
        check_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.check_prerequisites"), padding="10")
        check_frame.pack(fill=tk.X, pady=5)

        # 8.117.92: Combobox for the student, with the module Combobox
        # below it scoped to that student's enrolments. Selecting a
        # different student rebuilds the module list.
        ttk.Label(check_frame, text=_("degree_audit.labels.student_id")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.prereq_student_entry = ttk.Combobox(check_frame, width=42, state='readonly')
        self.prereq_student_entry.grid(row=0, column=1, padx=5, pady=5)
        self._populate_student_combo(self.prereq_student_entry)

        ttk.Label(check_frame, text=_("degree_audit.labels.module_code")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.prereq_module_entry = ttk.Combobox(check_frame, width=42, state='readonly')
        self.prereq_module_entry.grid(row=1, column=1, padx=5, pady=5)

        def _refresh_prereq_modules(_e=None):
            sid = self._student_id_from_label(self.prereq_student_entry.get())
            modules = self._student_modules(sid)
            self.prereq_module_entry['values'] = [
                f"{code} — {name}" for code, name in modules]
            if not modules:
                self.prereq_module_entry.set("")
        self.prereq_student_entry.bind('<<ComboboxSelected>>', _refresh_prereq_modules)

        ttk.Button(check_frame, text=_("degree_audit.buttons.check_prerequisites"),
                  command=self.check_prerequisites).grid(row=0, column=2, rowspan=2, padx=10, pady=5)

        # "Add new prerequisite" is packed first, against the bottom, so the
        # results area below can grow without pushing the form off-screen —
        # which is what clipped the old fixed-height text box.
        add_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.add_new_prerequisite"), padding="10")
        add_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        # Results display: cards on a scrolling canvas rather than a fixed
        # 12-line text box that clipped anything longer.
        results_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.prerequisite_check_results"), padding="6")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.prereq_results = _report.scrollable(results_frame)
        self._prereq_placeholder()

        ttk.Label(add_frame, text=_("degree_audit.labels.course")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.prereq_course_entry = ttk.Entry(add_frame, width=25)
        self.prereq_course_entry.grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(add_frame, text=_("degree_audit.labels.prerequisite")).grid(row=0, column=2, sticky=tk.W, padx=5, pady=5)
        self.prereq_prereq_entry = ttk.Entry(add_frame, width=25)
        self.prereq_prereq_entry.grid(row=0, column=3, padx=5, pady=5)

        ttk.Label(add_frame, text=_("degree_audit.labels.min_grade")).grid(row=0, column=4, sticky=tk.W, padx=5, pady=5)
        self.prereq_grade_entry = ttk.Entry(add_frame, width=10)
        self.prereq_grade_entry.grid(row=0, column=5, padx=5, pady=5)

        ttk.Button(add_frame, text=_("degree_audit.buttons.add_prerequisite"),
                  command=self.add_prerequisite).grid(row=0, column=6, padx=10, pady=5)

    def _prereq_placeholder(self):
        """Empty state for the prerequisite results area."""
        _report.clear(self.prereq_results)
        body = _report.card(self.prereq_results, accent=_report.MUTED)
        tk.Label(body,
                 text="Select a student and one of their modules, then click "
                      "Check Prerequisites.",
                 bg=_report.CARD, fg=_report.MUTED,
                 font=(_report.FONT, 9)).pack(anchor="w")

    def create_whatif_tab(self):
        """Create What-If Scenarios tab"""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=_("degree_audit.tabs.whatif_scenarios"))

        ttk.Label(tab, text=_("degree_audit.labels.analyze_program_change"),
                 font=('Arial', 12, 'bold')).pack(pady=10)

        # Create scenario frame
        create_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.create_whatif_scenario"), padding="10")
        create_frame.pack(fill=tk.X, pady=5)

        ttk.Label(create_frame, text=_("degree_audit.labels.student_id")).grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.whatif_student_entry = ttk.Combobox(create_frame, width=42, state='readonly')
        self.whatif_student_entry.grid(row=0, column=1, padx=5, pady=5)
        self._populate_student_combo(self.whatif_student_entry)

        ttk.Label(create_frame, text=_("degree_audit.labels.scenario_name")).grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.whatif_name_entry = ttk.Entry(create_frame, width=42)
        self.whatif_name_entry.grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(create_frame, text=_("degree_audit.labels.target_program")).grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.whatif_program_combo = ttk.Combobox(create_frame, width=40, state='readonly')
        self.whatif_program_combo.grid(row=2, column=1, padx=5, pady=5)

        # 8.117.92: when the student changes, autofill target_program
        # with their *current* course (admin can change it before
        # creating the scenario).
        def _autofill_whatif_course(_e=None):
            sid = self._student_id_from_label(self.whatif_student_entry.get())
            current = self._student_course(sid)
            if not current:
                return
            for opt in self.whatif_program_combo['values']:
                if f": {current} -" in opt or opt.startswith(f"{current} -") \
                        or opt.split(":", 1)[-1].strip().startswith(current):
                    self.whatif_program_combo.set(opt)
                    return
        self.whatif_student_entry.bind('<<ComboboxSelected>>', _autofill_whatif_course)

        ttk.Label(create_frame, text=_("degree_audit.labels.notes")).grid(row=3, column=0, sticky=tk.NW, padx=5, pady=5)
        self.whatif_notes_text = tk.Text(create_frame, width=40, height=4)
        self.whatif_notes_text.grid(row=3, column=1, padx=5, pady=5)

        button_frame = ttk.Frame(create_frame)
        button_frame.grid(row=4, column=0, columnspan=2, pady=10)

        ttk.Button(button_frame, text=_("degree_audit.buttons.create_scenario"),
                  command=self.create_whatif_scenario).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text=_("degree_audit.buttons.analyze"),
                  command=self.analyze_whatif).pack(side=tk.LEFT, padx=5)

        # Saved scenarios list. The analysis itself opens in its own window
        # (see analyze_whatif) rather than filling a text box down here.
        results_frame = ttk.LabelFrame(tab, text=_("degree_audit.labels.scenario_analysis_results"), padding="10")
        results_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        ttk.Label(results_frame,
                  text="Choose a student and a target course, then click Analyze. "
                       "The comparison opens in its own window.",
                  foreground="#7f8c8d").pack(anchor=tk.W, padx=4, pady=6)
