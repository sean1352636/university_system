"""Shared infrastructure for the course-management *curriculum extensions*.

This module backs five feature tabs that were missing from the course
management GUI:

1. Academic Terms & Course Sections   (:mod:`...core.sections_tab`)
2. Co-requisites & enrolment restrictions (:mod:`...core.requisites_tab`)
3. Syllabus & course materials         (:mod:`...core.materials_tab`)
4. Learning outcomes & curriculum mapping (:mod:`...core.outcomes_tab`)
5. Course approval workflow            (:mod:`...core.approvals_tab`)

All of the new tables key off ``course_code`` rather than the courses
``id`` column: in this deployment ``courses.id`` is a TEXT column that, for
existing rows, simply mirrors ``course_code``.  ``course_code`` is the stable,
UNIQUE, human-meaningful key, so linking against it avoids id-type ambiguity
and keeps the UI readable.

``ExtCommonMixin`` centralises connection handling, structured logging and the
error-reporting pattern used by every extension tab so that "error handling
and logging throughout" is implemented once and reused, not copy-pasted.
"""

from contextlib import contextmanager

from education_system.post_18.university_system.modules.domain.academics.gui.course_management_gui.core._imports import (
    _, tk, ttk, messagebox, sqlite3, DEFAULT_DB_PATH, datetime, logging,
)

logger = logging.getLogger(__name__)

# Optional central activity log — mirrors the pattern used by ``lms_tab``.
try:
    from education_system.post_18.university_system.core.activity_logger import log_activity
except Exception:  # pragma: no cover - logging must never break the GUI
    def log_activity(*_a, **_kw):
        return None

# Optional cross-GUI event bus. Publishing is best-effort; a missing bus must
# never stop a write from succeeding.
try:
    from education_system.post_18.university_system.modules.domain.academics.gui._event_bus import (
        publish as _bus_publish,
        EVENT_COURSE_CHANGED,
    )
except Exception:  # pragma: no cover
    _bus_publish = None
    EVENT_COURSE_CHANGED = "course_changed"


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

# Every statement is idempotent (``IF NOT EXISTS``) so it is safe to run on
# each launch regardless of whether the enhanced CLI schema or the GUI
# fallback created the database.
_EXTENSION_TABLES = (
    # --- Feature 1: Academic terms ------------------------------------
    """
    CREATE TABLE IF NOT EXISTS academic_terms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        term_type TEXT NOT NULL DEFAULT 'Semester',
        academic_year TEXT NOT NULL DEFAULT '',
        start_date TEXT DEFAULT '',
        end_date TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'Planned',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # --- Feature 1: Course sections (offerings) -----------------------
    """
    CREATE TABLE IF NOT EXISTS course_sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL,
        term_id INTEGER NOT NULL,
        section_number TEXT NOT NULL DEFAULT '001',
        instructor TEXT DEFAULT '',
        capacity INTEGER NOT NULL DEFAULT 30,
        enrolled INTEGER NOT NULL DEFAULT 0,
        delivery_mode TEXT NOT NULL DEFAULT 'In Person',
        location TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'Open',
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (term_id) REFERENCES academic_terms (id),
        UNIQUE(course_code, term_id, section_number)
    )
    """,
    # --- Feature 2: Co-requisites -------------------------------------
    # NB: a legacy ``course_corequisites`` table (keyed by course *id*)
    # already exists in some databases. We use a distinct name so we never
    # collide with or clobber it.
    """
    CREATE TABLE IF NOT EXISTS course_corequisites_ext (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL,
        corequisite_code TEXT NOT NULL,
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(course_code, corequisite_code)
    )
    """,
    # --- Feature 2: Enrolment restrictions / reserved seats -----------
    """
    CREATE TABLE IF NOT EXISTS course_restrictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL,
        restriction_type TEXT NOT NULL DEFAULT 'Major',
        restriction_value TEXT NOT NULL DEFAULT '',
        reserved_seats INTEGER NOT NULL DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # --- Feature 3: Syllabus & materials ------------------------------
    """
    CREATE TABLE IF NOT EXISTS course_materials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL,
        material_type TEXT NOT NULL DEFAULT 'Textbook',
        title TEXT NOT NULL,
        author TEXT DEFAULT '',
        isbn TEXT DEFAULT '',
        edition TEXT DEFAULT '',
        url TEXT DEFAULT '',
        cost REAL NOT NULL DEFAULT 0.0,
        required INTEGER NOT NULL DEFAULT 1,
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # --- Feature 4: Course learning outcomes --------------------------
    """
    CREATE TABLE IF NOT EXISTS course_learning_outcomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL,
        outcome_code TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # --- Feature 4: Outcome -> program/accreditation mapping ----------
    """
    CREATE TABLE IF NOT EXISTS outcome_program_mappings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        outcome_id INTEGER NOT NULL,
        standard_type TEXT NOT NULL DEFAULT 'Program Outcome',
        standard_code TEXT NOT NULL DEFAULT '',
        standard_description TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (outcome_id) REFERENCES course_learning_outcomes (id)
    )
    """,
    # --- Feature 5: Approval workflow (current state, one row/course) --
    """
    CREATE TABLE IF NOT EXISTS course_approvals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL UNIQUE,
        stage TEXT NOT NULL DEFAULT 'Draft',
        submitted_by TEXT DEFAULT '',
        reviewer TEXT DEFAULT '',
        comments TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # --- Feature 5: Approval history (append-only audit trail) --------
    """
    CREATE TABLE IF NOT EXISTS course_approval_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL,
        from_stage TEXT DEFAULT '',
        to_stage TEXT NOT NULL,
        actor TEXT DEFAULT '',
        comments TEXT DEFAULT '',
        changed_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # --- Feature 6: Section meeting times (drives the timetable) ------
    """
    CREATE TABLE IF NOT EXISTS section_meetings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        section_id INTEGER NOT NULL,
        day_of_week TEXT NOT NULL,
        start_time TEXT NOT NULL DEFAULT '09:00',
        end_time TEXT NOT NULL DEFAULT '10:00',
        location TEXT DEFAULT '',
        room_id INTEGER,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY (section_id) REFERENCES course_sections (id),
        FOREIGN KEY (room_id) REFERENCES rooms (id)
    )
    """,
    # --- Feature 8: Cross-listing & equivalency -----------------------
    """
    CREATE TABLE IF NOT EXISTS course_crosslistings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL,
        related_code TEXT NOT NULL,
        relation_type TEXT NOT NULL DEFAULT 'Cross-listed',
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(course_code, related_code, relation_type)
    )
    """,
    # --- Feature 9: Grading scheme (one row per course) ---------------
    """
    CREATE TABLE IF NOT EXISTS course_grading_schemes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL UNIQUE,
        scheme_type TEXT NOT NULL DEFAULT 'Letter',
        pass_mark REAL NOT NULL DEFAULT 50.0,
        notes TEXT DEFAULT '',
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # --- Feature 9: Assessment components / weighting -----------------
    """
    CREATE TABLE IF NOT EXISTS course_assessment_components (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL,
        name TEXT NOT NULL,
        weight REAL NOT NULL DEFAULT 0.0,
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
    # --- Feature 10: Waitlist automation rules (one row per course) ---
    """
    CREATE TABLE IF NOT EXISTS waitlist_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT NOT NULL UNIQUE,
        auto_promote INTEGER NOT NULL DEFAULT 0,
        promotion_order TEXT NOT NULL DEFAULT 'FIFO',
        notify INTEGER NOT NULL DEFAULT 1,
        max_auto INTEGER NOT NULL DEFAULT 0,
        active INTEGER NOT NULL DEFAULT 1,
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
    """,
)

_EXTENSION_INDEXES = (
    "CREATE INDEX IF NOT EXISTS idx_sections_course ON course_sections(course_code)",
    "CREATE INDEX IF NOT EXISTS idx_sections_term ON course_sections(term_id)",
    "CREATE INDEX IF NOT EXISTS idx_coreq_course ON course_corequisites_ext(course_code)",
    "CREATE INDEX IF NOT EXISTS idx_restrict_course ON course_restrictions(course_code)",
    "CREATE INDEX IF NOT EXISTS idx_materials_course ON course_materials(course_code)",
    "CREATE INDEX IF NOT EXISTS idx_clo_course ON course_learning_outcomes(course_code)",
    "CREATE INDEX IF NOT EXISTS idx_mapping_outcome ON outcome_program_mappings(outcome_id)",
    "CREATE INDEX IF NOT EXISTS idx_approval_history_course ON course_approval_history(course_code)",
    "CREATE INDEX IF NOT EXISTS idx_meetings_section ON section_meetings(section_id)",
    "CREATE INDEX IF NOT EXISTS idx_crosslist_course ON course_crosslistings(course_code)",
    "CREATE INDEX IF NOT EXISTS idx_assess_course ON course_assessment_components(course_code)",
)


class ExtCommonMixin:
    """Connection handling, logging, and small UI helpers shared by the
    curriculum-extension tabs (sections, requisites, materials, outcomes,
    approvals)."""

    # -- schema ---------------------------------------------------------

    def _ensure_extension_schema(self):
        """Create the curriculum-extension tables if they do not yet exist.

        Idempotent and defensive: a failure here disables the new tabs but
        must never prevent the rest of the GUI from loading.
        """
        if getattr(self, "_ext_schema_ready", False):
            return True
        try:
            # Each statement is committed independently so one failure (e.g. a
            # name collision with a legacy table) cannot disable every tab.
            conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0)
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                failures = 0
                for ddl in (*_EXTENSION_TABLES, *_EXTENSION_INDEXES):
                    try:
                        conn.execute(ddl)
                        conn.commit()
                    except Exception:
                        failures += 1
                        logger.exception(
                            "Curriculum-extension DDL failed (continuing): %s",
                            " ".join(ddl.split())[:80])
                # Migration: add section_meetings.room_id to pre-existing DBs so
                # meetings can reference a real room (precise cross-system clash
                # detection) instead of only free-text location.
                try:
                    cols = {r[1] for r in conn.execute(
                        "PRAGMA table_info(section_meetings)").fetchall()}
                    if "room_id" not in cols:
                        conn.execute("ALTER TABLE section_meetings ADD COLUMN room_id INTEGER")
                        conn.commit()
                except Exception:
                    logger.debug("section_meetings.room_id migration skipped", exc_info=True)
            finally:
                conn.close()
        except Exception:
            logger.exception("Failed to open DB for curriculum-extension schema")
            self._ext_schema_ready = False
            return False
        # Treat the schema as ready as long as the connection itself worked;
        # individual statement failures are logged but non-fatal.
        self._ext_schema_ready = True
        if failures:
            logger.warning("Curriculum-extension schema ready with %d skipped statement(s).",
                           failures)
        else:
            logger.info("Curriculum-extension schema ensured.")
        return True

    # -- connections ----------------------------------------------------

    @contextmanager
    def _ext_db(self, write=False):
        """Context manager yielding a WAL-mode connection.

        On a clean exit it commits when ``write`` is True; on any exception it
        rolls back, logs, and re-raises so the calling handler can surface the
        error to the user. The connection is always closed.
        """
        conn = sqlite3.connect(str(DEFAULT_DB_PATH), timeout=30.0)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
            if write:
                conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                logger.debug("Rollback failed", exc_info=True)
            raise
        finally:
            try:
                conn.close()
            except Exception:
                logger.debug("Connection close failed", exc_info=True)

    # -- error reporting ------------------------------------------------

    def _ext_report_error(self, context, exc, *, title=None):
        """Log ``exc`` with its traceback and show a user-facing dialog.

        ``context`` is a short operator-facing phrase such as "load sections".
        """
        logger.exception("Curriculum extension error during %s", context)
        try:
            self.update_status(
                _("course_management.status.ext_error",
                  default="Error during {context}: {error}").format(
                    context=context, error=exc),
                error=True,
            )
        except Exception:
            logger.debug("update_status failed while reporting error", exc_info=True)
        try:
            messagebox.showerror(
                title or _("common.error", default="Error"),
                _("course_management.messages.ext_error",
                  default="Could not {context}.\n\n{error}").format(
                    context=context, error=exc),
            )
        except Exception:
            logger.debug("messagebox failed while reporting error", exc_info=True)

    def _ext_audit(self, action, entity_type, **details):
        """Best-effort write to the central activity log."""
        try:
            log_activity(action, entity_type, user=self._ext_username(),
                         details=details or None)
        except Exception:
            logger.debug("Activity log write failed", exc_info=True)

    def _ext_notify_course_changed(self, course_code, action):
        """Best-effort publish of a course-changed event to sibling GUIs."""
        if not _bus_publish:
            return
        try:
            _bus_publish(EVENT_COURSE_CHANGED, course_code=course_code, action=action)
        except Exception:
            logger.debug("Event bus publish failed", exc_info=True)

    # -- identity / role ------------------------------------------------

    def _ext_username(self):
        """Current username, or 'system' when unauthenticated."""
        try:
            user = getattr(self.auth, "current_user", None)
            if isinstance(user, dict):
                return user.get("username") or user.get("user_id") or "system"
            if user is not None:
                return getattr(user, "username", None) or "system"
        except Exception:
            logger.debug("Could not resolve username", exc_info=True)
        return "system"

    def _ext_can_edit(self):
        """Admin and staff may create/modify curriculum data."""
        try:
            return bool(self.is_admin() or self.is_staff())
        except Exception:
            return False

    # -- shared data helpers -------------------------------------------

    def _ext_course_choices(self):
        """Return ``["CODE - Name", ...]`` plus a ``{label: code}`` map.

        Used to populate course-selector combo boxes across the extension
        tabs. Falls back to an empty list on any error.
        """
        labels, mapping = [], {}
        try:
            with self._ext_db() as conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT COALESCE(course_code, code) AS cc, "
                    "       COALESCE(course_name, name) AS cn "
                    "FROM courses "
                    "WHERE COALESCE(course_code, code) IS NOT NULL "
                    "ORDER BY cc"
                )
                for code, name in cur.fetchall():
                    if not code:
                        continue
                    label = f"{code} - {name}" if name else str(code)
                    labels.append(label)
                    mapping[label] = code
        except Exception as exc:
            # Non-fatal: the combo simply renders empty.
            logger.warning("Could not load course choices: %s", exc)
        return labels, mapping

    @staticmethod
    def _ext_code_from_label(label, mapping):
        """Resolve a combo label back to a course code (tolerant of free text)."""
        if not label:
            return None
        if label in mapping:
            return mapping[label]
        # User may have typed a bare code.
        return label.split(" - ", 1)[0].strip() or None

    def _ext_clear_tree(self, tree):
        """Remove every row from a treeview, guarding against a missing widget."""
        try:
            tree.delete(*tree.get_children())
        except Exception:
            logger.debug("Tree clear failed", exc_info=True)

    def _ext_selected_values(self, tree):
        """Return the values tuple of the selected row, or ``None``."""
        try:
            sel = tree.selection()
            if not sel:
                return None
            return tree.item(sel[0], "values")
        except Exception:
            logger.debug("Reading tree selection failed", exc_info=True)
            return None

    @staticmethod
    def _ext_now():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _ext_launch_window(self, title, builder, *, geometry="1400x900",
                           minsize=(1000, 600)):
        """Open a related GUI in its own Toplevel and hand it to *builder*.

        Used by the curriculum tabs to cross-link to sibling systems (Grade
        Management, Library, Academic Calendar). ``builder(top)`` constructs the
        target GUI inside the new window. Errors are reported, never raised."""
        try:
            top = tk.Toplevel(self.root)
            top.title(title)
            top.geometry(geometry)
            if minsize:
                top.minsize(*minsize)
            try:
                top.transient(self.root)
            except Exception:
                logger.debug("Could not set %s window transient", title, exc_info=True)
            builder(top)
            return top
        except Exception as exc:
            self._ext_report_error(f"open {title}", exc)
            return None


class ExtFormDialog:
    """A small, reusable modal form.

    ``fields`` is a list of ``(key, label, spec)`` where ``spec`` is a dict:

    * ``type``    – 'entry' (default) | 'text' | 'combo' | 'check' | 'readonly'
    * ``default`` – initial value
    * ``values``  – options for 'combo'
    * ``width`` / ``height`` – widget sizing

    ``on_submit(values: dict)`` is called with the collected values and must
    return a truthy value to close the dialog (falsy keeps it open so the
    handler can show a validation error). Any exception raised by the callback
    is reported via ``owner._ext_report_error`` and the dialog stays open.
    """

    def __init__(self, parent, owner, title, fields, on_submit,
                 *, submit_label=None, geometry="520x560"):
        self.owner = owner
        self.fields = fields
        self.on_submit = on_submit
        self._widgets = {}

        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry(geometry)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        frm = ttk.Frame(self.dialog, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        for row, (key, label, spec) in enumerate(fields):
            ftype = spec.get("type", "entry")
            anchor = tk.NW if ftype == "text" else tk.W
            ttk.Label(frm, text=label).grid(row=row, column=0, sticky=anchor,
                                            padx=5, pady=5)
            widget = self._build_widget(frm, ftype, spec)
            widget.grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
            self._widgets[key] = (ftype, widget)

        btns = ttk.Frame(frm)
        btns.grid(row=len(fields), column=0, columnspan=2, pady=16)
        ttk.Button(btns, text=submit_label or _("common.save", default="Save"),
                   command=self._submit).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text=_("common.cancel", default="Cancel"),
                   command=self.dialog.destroy).pack(side=tk.LEFT, padx=5)

        self.dialog.focus_set()

    def _build_widget(self, parent, ftype, spec):
        width = spec.get("width", 40)
        default = spec.get("default", "")
        if ftype == "text":
            w = tk.Text(parent, width=width, height=spec.get("height", 4))
            if default:
                w.insert("1.0", str(default))
            return w
        if ftype == "combo":
            var = tk.StringVar(value=str(default))
            w = ttk.Combobox(parent, textvariable=var, width=width - 3,
                             values=spec.get("values", []),
                             state=spec.get("state", "readonly"))
            w._var = var  # keep a reference
            return w
        if ftype == "check":
            var = tk.BooleanVar(value=bool(default))
            w = ttk.Checkbutton(parent, variable=var)
            w._var = var
            return w
        # entry / readonly
        var = tk.StringVar(value=str(default))
        w = ttk.Entry(parent, textvariable=var, width=width,
                      state="readonly" if ftype == "readonly" else "normal")
        w._var = var
        return w

    def _collect(self):
        values = {}
        for key, (ftype, widget) in self._widgets.items():
            if ftype == "text":
                values[key] = widget.get("1.0", tk.END).strip()
            elif ftype == "check":
                values[key] = bool(widget._var.get())
            else:
                values[key] = widget._var.get().strip() if isinstance(
                    widget._var.get(), str) else widget._var.get()
        return values

    def _submit(self):
        try:
            if self.on_submit(self._collect()):
                self.dialog.destroy()
        except Exception as exc:
            self.owner._ext_report_error("save form", exc)


# Re-export tk/ttk so the tab modules can ``from .ext_common import ...`` a
# single, consistent toolkit surface.
__all__ = [
    "ExtCommonMixin", "ExtFormDialog",
    "tk", "ttk", "messagebox", "_", "logger",
]
