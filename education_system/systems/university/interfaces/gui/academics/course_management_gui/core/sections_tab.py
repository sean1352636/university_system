"""Feature 1 — Academic Terms & Course Sections.

Adds a "Terms & Sections" tab with a sub-notebook:

* **Academic Terms** – the semesters / quarters a course can be offered in.
* **Course Sections** – concrete offerings of a course in a term (the thing
  students actually enrol in): section number, instructor, capacity,
  delivery mode and status.

This separates the *catalog definition* of a course from its per-term
*offerings*, which the original GUI conflated.
"""

from education_system.systems.university.interfaces.gui.academics.course_management_gui.core.ext_common import (
    ExtFormDialog, tk, ttk, messagebox, _, logger,
)

# Live cross-sync with the Academic Calendar. Optional: if the event bus
# isn't importable we simply fall back to sync-on-refresh.
try:
    from education_system.systems.university.interfaces.gui.academics._event_bus import (
        subscribe_tk as _bus_subscribe_tk,
        EVENT_CALENDAR_CHANGED,
    )
except Exception:  # pragma: no cover - defensive
    _bus_subscribe_tk = None
    EVENT_CALENDAR_CHANGED = "calendar.changed"

TERM_TYPES = ["Semester", "Quarter", "Trimester", "Summer Session", "Intersession"]
TERM_STATUSES = ["Planned", "Open", "In Progress", "Closed", "Archived"]
DELIVERY_MODES = ["In Person", "Online", "Hybrid", "Blended"]
SECTION_STATUSES = ["Open", "Waitlist", "Closed", "Cancelled"]


class SectionsTabMixin:
    """Terms & Sections management tab."""

    # ------------------------------------------------------------------
    # Tab creation
    # ------------------------------------------------------------------

    def create_sections_tab(self):
        if not self._ensure_extension_schema():
            return
        try:
            frame = ttk.Frame(self.notebook)
            self.notebook.add(frame, text=_("course_management.tabs.sections",
                                            default="Terms & Sections"))

            self._sections_notebook = ttk.Notebook(frame)
            self._sections_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            self._create_terms_subtab()
            self._create_course_sections_subtab()

            # Reverse sync: when a term/semester is created on the Academic
            # Calendar side, mirror it into this tab automatically. Bound to
            # the tab's lifetime so it's torn down with the window.
            if _bus_subscribe_tk is not None:
                try:
                    _bus_subscribe_tk(EVENT_CALENDAR_CHANGED, frame,
                                      self._on_calendar_changed)
                except Exception:
                    logger.debug("Calendar event subscription failed", exc_info=True)

            self._reload_terms()
            self._reload_sections()
        except Exception as exc:
            self._ext_report_error("build Terms & Sections tab", exc)

    def _on_calendar_changed(self, **_payload):
        """Event-bus handler: a calendar term/semester changed → refresh terms."""
        if not hasattr(self, "_terms_tree"):
            return
        try:
            imported = self._import_terms_from_calendar()
            if imported:
                self._reload_terms()
        except Exception:
            logger.debug("Reverse calendar→terms sync failed", exc_info=True)

    # ------------------------------------------------------------------
    # Academic Terms sub-tab
    # ------------------------------------------------------------------

    def _create_terms_subtab(self):
        tab = ttk.Frame(self._sections_notebook, padding=10)
        self._sections_notebook.add(tab, text=_("course_management.tabs.terms",
                                                 default="Academic Terms"))

        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, pady=5)
        if self._ext_can_edit():
            ttk.Button(bar, text=_("common.add", default="Add Term"),
                       command=self._add_term).pack(side=tk.LEFT, padx=5)
            ttk.Button(bar, text=_("common.edit", default="Edit"),
                       command=self._edit_term).pack(side=tk.LEFT, padx=5)
            ttk.Button(bar, text=_("common.delete", default="Delete"),
                       command=self._delete_term).pack(side=tk.LEFT, padx=5)
        ttk.Button(bar, text=_("common.refresh", default="Refresh"),
                   command=self._reload_terms).pack(side=tk.LEFT, padx=5)
        # Terms are now pushed to the Academic Calendar automatically when
        # they're added or edited (see _sync_term_to_calendar), so the manual
        # "Publish term to Calendar" button has been removed. A launcher to
        # open the calendar itself remains.
        ttk.Button(bar, text=_("course_management.buttons.open_calendar",
                               default="Open Academic Calendar →"),
                   command=self._open_academic_calendar).pack(side=tk.RIGHT, padx=5)

        cols = ("ID", "Name", "Type", "Year", "Start", "End", "Status")
        self._terms_tree = ttk.Treeview(tab, columns=cols, show="headings", height=14)
        widths = {"ID": 50, "Name": 200, "Type": 110, "Year": 90,
                  "Start": 100, "End": 100, "Status": 110}
        for c in cols:
            self._terms_tree.heading(c, text=c)
            self._terms_tree.column(c, width=widths.get(c, 100))
        sb = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self._terms_tree.yview)
        self._terms_tree.configure(yscrollcommand=sb.set)
        self._terms_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _reload_terms(self, *_a):
        if not hasattr(self, "_terms_tree"):
            return
        # Pull in any terms created on the Academic Calendar side first, so a
        # plain refresh of this tab surfaces them.
        self._import_terms_from_calendar()
        self._ext_clear_tree(self._terms_tree)
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT id, name, term_type, academic_year, start_date, "
                    "end_date, status FROM academic_terms "
                    "ORDER BY academic_year DESC, name"
                )
                rows = cur.fetchall()
            for row in rows:
                self._terms_tree.insert("", tk.END, values=row)
            self._refresh_term_combo()
            logger.debug("Loaded %d academic terms", len(rows))
        except Exception as exc:
            self._ext_report_error("load academic terms", exc)

    def _term_form_fields(self, data=None):
        data = data or {}
        return [
            ("name", "Term Name:", {"default": data.get("name", "")}),
            ("term_type", "Type:", {"type": "combo", "values": TERM_TYPES,
                                    "default": data.get("term_type", "Semester")}),
            ("academic_year", "Academic Year:",
             {"default": data.get("academic_year", ""), "width": 20}),
            ("start_date", "Start Date (YYYY-MM-DD):",
             {"default": data.get("start_date", "")}),
            ("end_date", "End Date (YYYY-MM-DD):",
             {"default": data.get("end_date", "")}),
            ("status", "Status:", {"type": "combo", "values": TERM_STATUSES,
                                   "default": data.get("status", "Planned")}),
        ]

    def _add_term(self):
        if not self._ext_can_edit():
            return

        def submit(values):
            name = (values.get("name") or "").strip()
            if not name:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     "Term name is required.")
                return False
            try:
                with self._ext_db(write=True) as conn:
                    conn.execute(
                        "INSERT INTO academic_terms "
                        "(name, term_type, academic_year, start_date, end_date, "
                        " status, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (name, values["term_type"], values["academic_year"],
                         values["start_date"], values["end_date"], values["status"],
                         self._ext_now(), self._ext_now()),
                    )
            except Exception as exc:
                # Likely a UNIQUE clash on name — report and keep the form open.
                self._ext_report_error("add term", exc)
                return False
            self._ext_audit("create", "academic_term", name=name)
            # Auto-push the new term onto the Academic Calendar.
            self._sync_term_to_calendar(
                name, values["term_type"], values["academic_year"],
                values["start_date"], values["end_date"])
            self._reload_terms()
            return True

        ExtFormDialog(self.root, self, "Add Academic Term",
                      self._term_form_fields(), submit, submit_label="Add Term",
                      geometry="480x430")

    def _selected_term(self):
        vals = self._ext_selected_values(self._terms_tree)
        if not vals:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a term first.")
            return None
        return vals

    # -- Academic Calendar tie-in --------------------------------------
    def _calendar_event_name(self, term_name):
        """Deterministic calendar-event name for a curriculum term, so pushes
        are idempotent (one event per term, updated in place)."""
        return f"{term_name} (Academic Term)"

    def _sync_term_to_calendar(self, name, term_type, year, start, end):
        """Push (or update) an Academic Calendar event for a curriculum term.

        Called automatically whenever a term is added or edited — the manual
        "Publish term to Calendar" button was removed in favour of this. It's
        idempotent: the event is keyed by a deterministic name, so a term
        edited multiple times updates the same event instead of creating
        duplicates. Best-effort — a failure here never blocks saving the term
        (the term already exists in academic_terms by the time we're called).
        """
        start = (start or "").strip()
        end = (end or "").strip()
        # A calendar event needs a valid, ordered date span; skip quietly if
        # the term hasn't got usable dates yet (it'll sync on the next edit).
        if not start or not end or start >= end:
            return
        canonical = self._calendar_event_name(name)
        description = f"Course-management term '{name}' ({term_type}, {year})."
        try:
            with self._ext_db() as conn:
                row = conn.execute(
                    "SELECT id, date_start, date_end, description "
                    "FROM academic_calendar_events WHERE name = ? LIMIT 1",
                    (canonical,),
                ).fetchone()

            from education_system.systems.university.domain.academics.services.academic_calendar.calendar_core import (
                AcademicCalendarManager,
            )
            mgr = AcademicCalendarManager(auth_manager=getattr(self, "auth", None))

            if row is None:
                mgr.add_event(
                    name=canonical, date_start=start, date_end=end,
                    event_type="Academic", description=description)
                self._ext_audit("publish", "calendar_term", term=name)
            else:
                event_id, cur_start, cur_end, cur_desc = row
                if ((cur_start or "") != start or (cur_end or "") != end
                        or (cur_desc or "") != description):
                    mgr.update_event(event_id, {
                        "date_start": start, "date_end": end,
                        "description": description})
                    self._ext_audit("update", "calendar_term", term=name)
        except Exception as exc:
            # Never surface a modal error for the auto-push; the term is saved
            # regardless. Log for diagnostics.
            logger.warning("Auto-push of term '%s' to calendar failed: %s",
                           name, exc)

    def _import_terms_from_calendar(self):
        """Reverse sync: mirror terms created on the Academic Calendar side
        (its ``semesters``) into ``academic_terms`` so they show up in this
        tab automatically.

        Idempotent — imported terms are named ``"<Semester> <Year>"`` and
        matched against existing term names (``academic_terms.name`` is
        UNIQUE), so re-running never duplicates. Returns the number of new
        terms imported.
        """
        if not hasattr(self, "_terms_tree"):
            return 0
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                # Guard: the calendar's semesters table may not exist yet.
                cur.execute("SELECT name FROM sqlite_master "
                            "WHERE type='table' AND name='semesters'")
                if not cur.fetchone():
                    return 0
                cur.execute("SELECT LOWER(name) FROM academic_terms")
                existing = {r[0] for r in cur.fetchall()}
                cur.execute(
                    "SELECT name, COALESCE(academic_year_id, ''), "
                    "       start_date, end_date FROM semesters")
                semesters = cur.fetchall()

            new_terms = []
            for sem_name, year, start, end in semesters:
                sem_name = (sem_name or "").strip()
                if not sem_name:
                    continue
                term_name = f"{sem_name} {year}".strip() if year else sem_name
                if term_name.lower() in existing:
                    continue
                new_terms.append((term_name, year, start or "", end or ""))
                existing.add(term_name.lower())

            if not new_terms:
                return 0

            with self._ext_db(write=True) as conn:
                for term_name, year, start, end in new_terms:
                    conn.execute(
                        "INSERT OR IGNORE INTO academic_terms "
                        "(name, term_type, academic_year, start_date, end_date, "
                        " status, created_at, updated_at) "
                        "VALUES (?, 'Semester', ?, ?, ?, 'Planned', ?, ?)",
                        (term_name, year, start, end,
                         self._ext_now(), self._ext_now()))
            for term_name, *_ in new_terms:
                self._ext_audit("import", "academic_term",
                                name=term_name, source="calendar")
            logger.debug("Imported %d calendar term(s) into academic_terms",
                         len(new_terms))
            return len(new_terms)
        except Exception as exc:
            logger.warning("Import of calendar terms failed: %s", exc)
            return 0

    def _open_academic_calendar(self):
        """Open the Academic Calendar GUI in its own window."""
        def _build(top):
            from education_system.systems.university.interfaces.gui.academics.academic_calendar import (
                CalendarGUI,
            )
            CalendarGUI(auth_manager=getattr(self, "auth", None), parent_window=top)
        self._ext_launch_window(
            _("course_management.titles.academic_calendar", default="Academic Calendar"),
            _build, geometry="1400x900", minsize=(1000, 600))

    def _edit_term(self):
        if not self._ext_can_edit():
            return
        vals = self._selected_term()
        if not vals:
            return
        term_id = vals[0]
        data = {"name": vals[1], "term_type": vals[2], "academic_year": vals[3],
                "start_date": vals[4], "end_date": vals[5], "status": vals[6]}

        def submit(values):
            name = (values.get("name") or "").strip()
            if not name:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     "Term name is required.")
                return False
            try:
                with self._ext_db(write=True) as conn:
                    conn.execute(
                        "UPDATE academic_terms SET name=?, term_type=?, "
                        "academic_year=?, start_date=?, end_date=?, status=?, "
                        "updated_at=? WHERE id=?",
                        (name, values["term_type"], values["academic_year"],
                         values["start_date"], values["end_date"], values["status"],
                         self._ext_now(), term_id),
                    )
            except Exception as exc:
                self._ext_report_error("update term", exc)
                return False
            self._ext_audit("update", "academic_term", term_id=term_id, name=name)
            # Keep the term's Academic Calendar event in sync with the edit.
            self._sync_term_to_calendar(
                name, values["term_type"], values["academic_year"],
                values["start_date"], values["end_date"])
            self._reload_terms()
            return True

        ExtFormDialog(self.root, self, "Edit Academic Term",
                      self._term_form_fields(data), submit,
                      submit_label="Save", geometry="480x430")

    def _delete_term(self):
        if not self._ext_can_edit():
            return
        vals = self._selected_term()
        if not vals:
            return
        term_id, name = vals[0], vals[1]
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM course_sections WHERE term_id=?",
                            (term_id,))
                section_count = cur.fetchone()[0]
        except Exception as exc:
            self._ext_report_error("check term usage", exc)
            return
        msg = f"Delete term '{name}'?"
        if section_count:
            msg += (f"\n\n{section_count} course section(s) are scheduled in this "
                    "term and will also be deleted.")
        if not messagebox.askyesno(_("common.confirm", default="Confirm"), msg):
            return
        try:
            with self._ext_db(write=True) as conn:
                conn.execute("DELETE FROM course_sections WHERE term_id=?", (term_id,))
                conn.execute("DELETE FROM academic_terms WHERE id=?", (term_id,))
        except Exception as exc:
            self._ext_report_error("delete term", exc)
            return
        self._ext_audit("delete", "academic_term", term_id=term_id, name=name)
        self._reload_terms()
        self._reload_sections()

    # ------------------------------------------------------------------
    # Course Sections sub-tab
    # ------------------------------------------------------------------

    def _create_course_sections_subtab(self):
        tab = ttk.Frame(self._sections_notebook, padding=10)
        self._sections_notebook.add(tab, text=_("course_management.tabs.course_sections",
                                                 default="Course Sections"))

        flt = ttk.Frame(tab)
        flt.pack(fill=tk.X, pady=5)
        ttk.Label(flt, text="Filter by term:").pack(side=tk.LEFT, padx=5)
        self._section_term_filter = ttk.Combobox(flt, width=30, state="readonly")
        self._section_term_filter.pack(side=tk.LEFT, padx=5)
        self._section_term_filter.bind("<<ComboboxSelected>>", self._reload_sections)

        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, pady=5)
        if self._ext_can_edit():
            ttk.Button(bar, text=_("common.add", default="Add Section"),
                       command=self._add_section).pack(side=tk.LEFT, padx=5)
            ttk.Button(bar, text=_("common.edit", default="Edit"),
                       command=self._edit_section).pack(side=tk.LEFT, padx=5)
            ttk.Button(bar, text=_("common.delete", default="Delete"),
                       command=self._delete_section).pack(side=tk.LEFT, padx=5)
        ttk.Button(bar, text=_("common.refresh", default="Refresh"),
                   command=self._reload_sections).pack(side=tk.LEFT, padx=5)

        cols = ("ID", "Course", "Term", "Section", "Instructor", "Mode",
                "Cap", "Enrolled", "Status")
        self._sections_tree = ttk.Treeview(tab, columns=cols, show="headings", height=14)
        widths = {"ID": 45, "Course": 90, "Term": 160, "Section": 70,
                  "Instructor": 150, "Mode": 90, "Cap": 55, "Enrolled": 70,
                  "Status": 90}
        for c in cols:
            self._sections_tree.heading(c, text=c)
            self._sections_tree.column(c, width=widths.get(c, 100))
        # Highlight full / over-capacity sections.
        self._sections_tree.tag_configure("full", foreground="#d97706")
        sb = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self._sections_tree.yview)
        self._sections_tree.configure(yscrollcommand=sb.set)
        self._sections_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)

    def _refresh_term_combo(self):
        """Keep the section filter / form term lists in sync with terms."""
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute("SELECT id, name FROM academic_terms "
                            "ORDER BY academic_year DESC, name")
                rows = cur.fetchall()
            self._term_label_to_id = {name: tid for tid, name in rows}
            self._term_id_to_label = {tid: name for tid, name in rows}
            labels = list(self._term_label_to_id.keys())
            if hasattr(self, "_section_term_filter"):
                current = self._section_term_filter.get()
                self._section_term_filter["values"] = ["(All terms)"] + labels
                if current not in (["(All terms)"] + labels):
                    self._section_term_filter.set("(All terms)")
        except Exception as exc:
            logger.warning("Could not refresh term combo: %s", exc)

    def _reload_sections(self, *_a):
        if not hasattr(self, "_sections_tree"):
            return
        self._ext_clear_tree(self._sections_tree)
        try:
            term_filter = (getattr(self, "_section_term_filter", None)
                           and self._section_term_filter.get())
            query = (
                "SELECT s.id, s.course_code, t.name, s.section_number, "
                "       s.instructor, s.delivery_mode, s.capacity, s.enrolled, "
                "       s.status "
                "FROM course_sections s "
                "LEFT JOIN academic_terms t ON s.term_id = t.id "
            )
            params = ()
            if term_filter and term_filter != "(All terms)":
                tid = getattr(self, "_term_label_to_id", {}).get(term_filter)
                if tid is not None:
                    query += "WHERE s.term_id = ? "
                    params = (tid,)
            query += "ORDER BY s.course_code, t.name, s.section_number"
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute(query, params)
                rows = cur.fetchall()
            for row in rows:
                cap, enrolled = row[6] or 0, row[7] or 0
                tags = ("full",) if cap and enrolled >= cap else ()
                self._sections_tree.insert("", tk.END, values=row, tags=tags)
            logger.debug("Loaded %d course sections", len(rows))
        except Exception as exc:
            self._ext_report_error("load course sections", exc)

    def _section_form_fields(self, course_labels, term_labels, data=None):
        data = data or {}
        return [
            ("course", "Course:", {"type": "combo", "values": course_labels,
                                   "default": data.get("course", ""), "width": 43}),
            ("term", "Term:", {"type": "combo", "values": term_labels,
                               "default": data.get("term", ""), "width": 43}),
            ("section_number", "Section #:",
             {"default": data.get("section_number", "001"), "width": 15}),
            ("instructor", "Instructor:", {"default": data.get("instructor", "")}),
            ("delivery_mode", "Delivery Mode:",
             {"type": "combo", "values": DELIVERY_MODES,
              "default": data.get("delivery_mode", "In Person")}),
            ("location", "Location / Room:", {"default": data.get("location", "")}),
            ("capacity", "Capacity:", {"default": data.get("capacity", "30"), "width": 10}),
            ("enrolled", "Enrolled:", {"default": data.get("enrolled", "0"), "width": 10}),
            ("status", "Status:", {"type": "combo", "values": SECTION_STATUSES,
                                   "default": data.get("status", "Open")}),
            ("notes", "Notes:", {"type": "text", "default": data.get("notes", ""),
                                 "height": 3}),
        ]

    def _parse_section_numbers(self, values):
        """Validate and coerce capacity/enrolled. Returns (cap, enrolled) or None."""
        try:
            cap = int(values.get("capacity") or 0)
            enrolled = int(values.get("enrolled") or 0)
        except (TypeError, ValueError):
            messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                 "Capacity and Enrolled must be whole numbers.")
            return None
        if cap < 0 or enrolled < 0:
            messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                 "Capacity and Enrolled cannot be negative.")
            return None
        return cap, enrolled

    def _add_section(self):
        if not self._ext_can_edit():
            return
        course_labels, course_map = self._ext_course_choices()
        self._refresh_term_combo()
        term_labels = list(getattr(self, "_term_label_to_id", {}).keys())
        if not term_labels:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Create an academic term before adding sections.")
            return

        def submit(values):
            code = self._ext_code_from_label(values.get("course"), course_map)
            term_id = getattr(self, "_term_label_to_id", {}).get(values.get("term"))
            if not code or term_id is None:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     "Select both a course and a term.")
                return False
            nums = self._parse_section_numbers(values)
            if nums is None:
                return False
            cap, enrolled = nums
            try:
                with self._ext_db(write=True) as conn:
                    conn.execute(
                        "INSERT INTO course_sections "
                        "(course_code, term_id, section_number, instructor, "
                        " capacity, enrolled, delivery_mode, location, status, "
                        " notes, created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (code, term_id, values["section_number"].strip() or "001",
                         values["instructor"], cap, enrolled, values["delivery_mode"],
                         values["location"], values["status"], values["notes"],
                         self._ext_now(), self._ext_now()),
                    )
            except Exception as exc:
                # Most likely the UNIQUE(course, term, section) constraint.
                self._ext_report_error("add section (duplicate section number?)", exc)
                return False
            self._ext_audit("create", "course_section", course_code=code,
                            term_id=term_id, section=values["section_number"])
            self._ext_notify_course_changed(code, "section_added")
            self._reload_sections()
            return True

        ExtFormDialog(self.root, self, "Add Course Section",
                      self._section_form_fields(course_labels, term_labels),
                      submit, submit_label="Add Section", geometry="560x600")

    def _selected_section(self):
        vals = self._ext_selected_values(self._sections_tree)
        if not vals:
            messagebox.showwarning(_("common.warning", default="Warning"),
                                   "Select a section first.")
            return None
        return vals

    def _edit_section(self):
        if not self._ext_can_edit():
            return
        vals = self._selected_section()
        if not vals:
            return
        section_id = vals[0]
        # Load the full row for fields not shown in the tree (location, notes).
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT course_code, term_id, section_number, instructor, "
                    "capacity, enrolled, delivery_mode, location, status, notes "
                    "FROM course_sections WHERE id=?", (section_id,))
                row = cur.fetchone()
        except Exception as exc:
            self._ext_report_error("load section", exc)
            return
        if not row:
            messagebox.showerror(_("common.error", default="Error"), "Section not found.")
            return

        course_labels, course_map = self._ext_course_choices()
        self._refresh_term_combo()
        term_labels = list(getattr(self, "_term_label_to_id", {}).keys())
        code = row[0]
        course_label = next((l for l in course_labels
                             if self._ext_code_from_label(l, course_map) == code), code)
        data = {
            "course": course_label,
            "term": getattr(self, "_term_id_to_label", {}).get(row[1], ""),
            "section_number": row[2], "instructor": row[3], "capacity": row[4],
            "enrolled": row[5], "delivery_mode": row[6], "location": row[7],
            "status": row[8], "notes": row[9],
        }

        def submit(values):
            new_code = self._ext_code_from_label(values.get("course"), course_map)
            term_id = getattr(self, "_term_label_to_id", {}).get(values.get("term"))
            if not new_code or term_id is None:
                messagebox.showerror(_("common.validation_error", default="Validation Error"),
                                     "Select both a course and a term.")
                return False
            nums = self._parse_section_numbers(values)
            if nums is None:
                return False
            cap, enrolled = nums
            try:
                with self._ext_db(write=True) as conn:
                    conn.execute(
                        "UPDATE course_sections SET course_code=?, term_id=?, "
                        "section_number=?, instructor=?, capacity=?, enrolled=?, "
                        "delivery_mode=?, location=?, status=?, notes=?, updated_at=? "
                        "WHERE id=?",
                        (new_code, term_id, values["section_number"].strip() or "001",
                         values["instructor"], cap, enrolled, values["delivery_mode"],
                         values["location"], values["status"], values["notes"],
                         self._ext_now(), section_id),
                    )
            except Exception as exc:
                self._ext_report_error("update section", exc)
                return False
            self._ext_audit("update", "course_section", section_id=section_id,
                            course_code=new_code)
            self._ext_notify_course_changed(new_code, "section_updated")
            self._reload_sections()
            return True

        ExtFormDialog(self.root, self, "Edit Course Section",
                      self._section_form_fields(course_labels, term_labels, data),
                      submit, submit_label="Save", geometry="560x600")

    def _delete_section(self):
        if not self._ext_can_edit():
            return
        vals = self._selected_section()
        if not vals:
            return
        section_id = vals[0]
        label = f"{vals[1]} · {vals[2]} · section {vals[3]}"
        if not messagebox.askyesno(_("common.confirm", default="Confirm"),
                                   f"Delete section: {label}?"):
            return
        try:
            with self._ext_db(write=True) as conn:
                conn.execute("DELETE FROM course_sections WHERE id=?", (section_id,))
        except Exception as exc:
            self._ext_report_error("delete section", exc)
            return
        self._ext_audit("delete", "course_section", section_id=section_id)
        self._reload_sections()
