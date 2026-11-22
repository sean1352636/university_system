"""Standalone Timetable Manager.

Extracted from the Module Scheduling GUI's old "Timetables" tab so the
timetable feature can live in its own window and be launched from the main
GUI. Generates, displays, emails and exports student / instructor
timetables.

Data access goes through the two module-level helpers below
(``get_student_schedule_data`` / ``get_instructor_schedule_data``), which are
the single source of truth shared with ``module_scheduling/exports.py`` and
``module_scheduling/instructors_tab.py``. Both only surface *published*
schedule rows so what-if drafts don't leak into personal timetables.
"""
from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk, messagebox

from education_system.systems.university.infrastructure.database.db import (
    DEFAULT_DB_PATH,
    get_connection,
)

# i18n with fallback
try:
    from education_system.systems.university.infrastructure.i18n import get_text as _t
except ImportError:  # pragma: no cover - fallback
    _t = lambda key, **kwargs: key  # noqa: E731

# Schedule constants + scheduler service, with defaults if unavailable.
try:
    from education_system.systems.university.domains.teaching.domain.module_scheduling import (
        ModuleScheduler,
        DAYS_OF_WEEK,
        TIME_SLOTS,
    )
except ImportError:  # pragma: no cover - fallback
    DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    TIME_SLOTS = ["09:00", "10:00", "11:00", "12:00", "13:00",
                  "14:00", "15:00", "16:00", "17:00"]

    class ModuleScheduler:  # type: ignore
        pass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Shared schedule-data helpers (single source of truth)
# ---------------------------------------------------------------------------
def _schedule_rows(where_clause: str, params: list) -> list[dict]:
    """Run the common schedule query and shape rows into dicts.

    Only ``published`` schedule rows are returned so draft / what-if rows
    stay out of personal timetables.
    """
    query = f"""
        SELECT ms.module_code, m.module_name, ms.day_of_week, ms.start_time,
               ms.end_time, r.building, r.room_number, i.first_name,
               i.last_name, ms.session_type, ms.recurrence, ms.recurrence_until,
               ms.week_pattern, ms.online_url
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        LEFT JOIN modules m ON ms.module_code = m.module_code
        WHERE {where_clause}
          AND COALESCE(ms.status, 'published') = 'published'
        ORDER BY ms.day_of_week, ms.start_time
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

    schedule_data = []
    for row in rows:
        (module_code, module_name, day, start, end, building, room,
         first_name, last_name, session_type, recurrence,
         recurrence_until, week_pattern, online_url) = row
        schedule_data.append({
            "module_code": module_code,
            "module_name": module_name or "Unknown",
            "day": day,
            "start_time": start,
            "end_time": end,
            "room": f"{building}-{room}" if building and room else "TBA",
            "instructor": (f"{first_name} {last_name}"
                           if first_name and last_name else "TBA"),
            "session_type": session_type,
            "recurrence": recurrence or "weekly",
            "recurrence_until": recurrence_until,
            "week_pattern": week_pattern,
            "online_url": online_url,
        })
    return schedule_data


def get_student_schedule_data(student_id) -> list[dict]:
    """Published weekly slots of the modules a student is *currently* on —
    and, where a module runs in deliveries, only their delivery's slots.

    It used to include every module the student had ever enrolled on, so a
    withdrawn module stayed on their timetable and in its emails.
    """
    from education_system.systems.university.application.teaching import occurrences as tt
    with get_connection() as conn:
        ids = [s["id"] for s in tt.student_slots(conn, student_id)]
        conn.commit()
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    return _schedule_rows(f"ms.id IN ({placeholders})", ids)


def get_instructor_schedule_data(instructor_id) -> list[dict]:
    """Published schedule rows taught by a given instructor."""
    from education_system.systems.university.application.teaching import occurrences as tt
    with get_connection() as conn:
        tt.ensure(conn)
        conn.commit()
    return _schedule_rows("ms.instructor_id = ?", [instructor_id])


# ---------------------------------------------------------------------------
# Standalone window
# ---------------------------------------------------------------------------
class TimetableManagementGUI:
    """Self-contained timetable window (student & instructor timetables)."""

    #: Tab keys accepted by ``initial_tab`` / :meth:`select_tab`, in the order
    #: the notebook builds them. Callers deep-link by key, not by index, so
    #: inserting a tab never silently repoints an existing entry point.
    TAB_KEYS = ("student", "instructor", "module", "rooms", "term", "exams",
                "sections", "conflicts", "generate")

    def __init__(self, parent=None, auth=None, initial_tab=None):
        self.parent = parent
        self.auth = auth
        self.scheduler = ModuleScheduler()
        self.last_timetable_data = None
        self.last_timetable_type = None
        self.last_timetable_id = None

        self.window = tk.Toplevel(parent) if parent else tk.Tk()
        # ``self.root`` mirrors the attribute the moved methods (and the
        # reused export helpers) expect as their messagebox parent.
        self.root = self.window
        self.window.title(_t("scheduling.tabs.timetables") or "Timetable Manager")
        self.window.geometry("1100x700")
        if parent:
            try:
                self.window.transient(parent)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
        self._build_ui()
        if initial_tab:
            self.select_tab(initial_tab)

    def select_tab(self, key):
        """Bring the tab named by *key* to the front. Unknown keys are ignored."""
        try:
            self.notebook.select(self.TAB_KEYS.index(key))
        except (ValueError, tk.TclError, AttributeError):
            logger.debug("timetable: cannot select tab %r", key)

    # -- misc host surface the moved methods rely on -----------------------
    def set_auth(self, auth):
        self.auth = auth

    def update_activity_log(self, message):
        logger.info("[timetable] %s", message)

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        """Build the tabbed window.

        This is the single timetable surface for the university. It replaced
        six separate entry points across three GUIs — Main GUI "Timetable" and
        "Timetable Manager", Course Management "Timetable", Module Scheduling
        "Timetable Manager" and "Student Timetables", plus a tab inside the
        Student CRUD GUI — which between them had four independent weekly-grid
        renderers over two unrelated data models.

        The read surfaces are unified on :class:`WeeklyGridPanel`, which was
        written as the "single read-side widget for every timetable surface"
        and had no callers at all until this merge.
        """
        self._load_pickers()

        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self._build_student_tab()
        self._build_instructor_tab()
        self._build_module_tab()
        self._build_room_tab()
        self._build_term_tab()
        self._build_exams_tab()
        self._build_sections_tab()
        self._build_conflicts_tab()

        # The original single-pane layout becomes the last tab. Keeping it
        # intact means every existing method (generate/email/export, which
        # render into ``self.timetable_frame``) keeps working untouched.
        generate_tab = ttk.Frame(self.notebook)
        self.notebook.add(generate_tab, text=_t(
            'gui.academics.timetable_management.tabs.generate_export',
            default="Generate & Export"))
        self._build_generate_tab(generate_tab)

    # -- pickers ----------------------------------------------------------
    def _load_pickers(self):
        """Load the student / instructor / module dropdown choices.

        Typing raw IDs was the old interface and it made every tab a guessing
        game — you had to know a student number or an instructor's numeric row
        id before you could see anything. Each map is ``label -> id``; the
        label carries a human name so the list is searchable by eye, and the
        id is what the grid is actually targeted with.

        One connection for all three queries, and every one degrades to an
        empty map rather than raising: an unreadable table must not stop the
        window opening.
        """
        self._student_choices = {}
        self._instructor_choices = {}
        self._module_choices = {}
        self._room_choices = {}
        try:
            with get_connection() as conn:
                self._student_choices = self._query_choices(
                    conn,
                    "SELECT student_id, "
                    "  COALESCE(first_name, '') || ' ' || COALESCE(last_name, '') "
                    "FROM students WHERE student_id IS NOT NULL "
                    "ORDER BY last_name, first_name",
                )
                self._instructor_choices = self._query_choices(
                    conn,
                    "SELECT id, "
                    "  COALESCE(first_name, '') || ' ' || COALESCE(last_name, '') "
                    "FROM instructors ORDER BY last_name, first_name",
                )
                self._module_choices = self._query_choices(
                    conn,
                    "SELECT module_code, COALESCE(module_name, '') "
                    "FROM modules WHERE module_code IS NOT NULL "
                    "ORDER BY module_code",
                )
                self._room_choices = self._query_choices(
                    conn,
                    "SELECT id, TRIM(COALESCE(building, '') || ' ' || "
                    "COALESCE(room_number, room_name, '')) || "
                    "COALESCE(' (' || capacity || ' seats)', '') "
                    "FROM rooms WHERE COALESCE(is_active, 1) = 1 ORDER BY building, room_number",
                )
        except Exception as exc:
            logger.warning("timetable: could not load pickers: %s", exc)

    @staticmethod
    def _query_choices(conn, sql):
        """Run *sql* returning ``(id, name)`` rows into a ``label -> id`` map."""
        try:
            rows = conn.execute(sql).fetchall()
        except Exception as exc:
            logger.debug("timetable picker query failed: %s", exc)
            return {}
        choices = {}
        for ident, name in rows:
            if ident is None:
                continue
            name = (name or "").strip()
            choices[f"{ident} — {name}" if name else str(ident)] = ident
        return choices

    def _picker(self, parent, choices, on_pick):
        """A readonly combobox over *choices*, calling *on_pick* with the id."""
        var = tk.StringVar()
        combo = ttk.Combobox(parent, textvariable=var, width=38,
                             state="readonly", values=list(choices))
        combo.pack(side=tk.LEFT, padx=(6, 6))
        combo.bind("<<ComboboxSelected>>",
                   lambda e: on_pick(choices.get(var.get())))
        if not choices:
            combo.set(_t(
                'gui.academics.timetable_management.labels.nothing_to_choose',
                default="(nothing to choose from)"))
        return var, combo

    def _week_bar(self, parent, get_panel):
        """Previous / This week / Next controls for a weekly grid.

        Week navigation exists because exams are pinned to a single date. A
        grid that could only ever show "a typical week" had nowhere truthful to
        put them.
        """
        bar = ttk.Frame(parent)
        bar.pack(fill=tk.X, padx=8, pady=(0, 4))

        def shift(weeks):
            panel = get_panel()
            if panel is not None:
                panel.shift_week(weeks)

        def today():
            panel = get_panel()
            if panel is not None:
                panel.set_week(None)

        ttk.Button(bar, text="◀ " + _t(
            'gui.academics.timetable_management.buttons.prev_week',
            default="Previous week"), command=lambda: shift(-1)).pack(side=tk.LEFT)
        ttk.Button(bar, text=_t(
            'gui.academics.timetable_management.buttons.this_week',
            default="This week"), command=today).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text=_t(
            'gui.academics.timetable_management.buttons.next_week',
            default="Next week") + " ▶", command=lambda: shift(1)).pack(side=tk.LEFT)
        return bar

    # -- tab 1: student ---------------------------------------------------
    def _build_student_tab(self):
        """A student's week, across *both* scheduling models.

        The grid is module-based (``module_schedule``). Section meetings live
        in the other model entirely, so they are listed alongside via
        ``timetable_bridge`` rather than being silently omitted — which is
        exactly the gap the bridge was written to close.
        """
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t(
            'gui.academics.timetable_management.tabs.student', default="Student"))

        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(bar, text=_t("scheduling.student") + ":").pack(side=tk.LEFT)
        self.tab_student_id_var, self.tab_student_combo = self._picker(
            bar, self._student_choices,
            lambda sid: self._refresh_student_tab(sid))
        ttk.Button(bar, text=_t(
            'gui.academics.timetable_management.buttons.show', default="Show"),
            command=self._refresh_student_tab).pack(side=tk.LEFT)

        self.student_grid = self._make_grid(tab, scope="student")
        self._week_bar(tab, lambda: self.student_grid)

        sections_box = ttk.LabelFrame(tab, text=_t(
            'gui.academics.timetable_management.labels.section_meetings',
            default="Section meetings (course-based schedule)"), padding=6)
        sections_box.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.student_sections_list = tk.Listbox(sections_box, height=4)
        self.student_sections_list.pack(fill=tk.X)

    def select_student(self, student_id):
        """Point the Student tab at *student_id*, if that student exists.

        The dropdown is keyed by display label, so callers holding a bare ID
        (the main GUI pre-filling a logged-in student's own timetable) need
        this rather than setting the variable directly.
        """
        student_id = str(student_id)
        for label, ident in self._student_choices.items():
            if str(ident) == student_id:
                self.tab_student_id_var.set(label)
                self._refresh_student_tab(ident)
                return True
        return False

    def _refresh_student_tab(self, student_id=None):
        if student_id is None:
            student_id = self._student_choices.get(
                self.tab_student_id_var.get())
        if not student_id:
            messagebox.showwarning(
                _t("scheduling.student_timetables"),
                _t('gui.academics.timetable_management.dialogs.pick_student',
                   default="Choose a student first."),
                parent=self.window)
            return

        self._set_grid_target(self.student_grid, "student", student_id)

        self.student_sections_list.delete(0, tk.END)
        try:
            from education_system.systems.university.domains.teaching.domain.timetable_bridge import (
                get_student_section_meetings,
            )
            meetings = get_student_section_meetings(student_id)
        except Exception as exc:
            self.student_sections_list.insert(tk.END, f"(unavailable: {exc})")
            return

        if not meetings:
            self.student_sections_list.insert(tk.END, _t(
                'gui.academics.timetable_management.labels.no_section_meetings',
                default="No section meetings for this student."))
            return
        for m in meetings:
            self.student_sections_list.insert(tk.END, (
                f"{m.get('day_of_week', '')} {m.get('start_time', '')}"
                f"-{m.get('end_time', '')}  {m.get('code', '')} "
                f"{m.get('name', '')}  [{m.get('location', '') or 'no room'}]"
            ))

    # -- tab 2: instructor ------------------------------------------------
    def _build_instructor_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t(
            'gui.academics.timetable_management.tabs.instructor',
            default="Instructor"))

        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(bar, text=_t("scheduling.instructor") + ":").pack(side=tk.LEFT)
        self.tab_instructor_id_var, self.tab_instructor_combo = self._picker(
            bar, self._instructor_choices,
            lambda iid: self._set_grid_target(
                self.instructor_grid, "instructor", iid))
        ttk.Button(bar, text=_t(
            'gui.academics.timetable_management.buttons.show', default="Show"),
            command=lambda: self._set_grid_target(
                self.instructor_grid, "instructor",
                self._instructor_choices.get(
                    self.tab_instructor_id_var.get()))).pack(side=tk.LEFT)

        self.instructor_grid = self._make_grid(tab, scope="instructor")
        self._week_bar(tab, lambda: self.instructor_grid)

    # -- tab 3: module ----------------------------------------------------
    def _build_module_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t(
            'gui.academics.timetable_management.tabs.module', default="Module"))

        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(bar, text=_t(
            'gui.academics.timetable_management.labels.module',
            default="Module:")).pack(side=tk.LEFT)
        self.tab_module_code_var, self.tab_module_combo = self._picker(
            bar, self._module_choices,
            lambda code: self._set_grid_target(
                self.module_grid, "module", code))
        ttk.Button(bar, text=_t(
            'gui.academics.timetable_management.buttons.show', default="Show"),
            command=lambda: self._set_grid_target(
                self.module_grid, "module",
                self._module_choices.get(
                    self.tab_module_code_var.get()))).pack(side=tk.LEFT)

        self.module_grid = self._make_grid(tab, scope="module")
        self._week_bar(tab, lambda: self.module_grid)

    # -- shared grid plumbing ---------------------------------------------
    def _make_grid(self, parent, *, scope):
        """Embed a WeeklyGridPanel, degrading to a message if unavailable."""
        try:
            from education_system.systems.university.domains.teaching.interfaces.gui._cross_dialogs.timetable import (
                WeeklyGridPanel,
            )
        except Exception as exc:
            ttk.Label(parent, text=f"Weekly grid unavailable: {exc}").pack(
                padx=10, pady=10)
            return None
        panel = WeeklyGridPanel(parent, scope=scope, scope_id=None)
        panel.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        return panel

    def _set_grid_target(self, panel, scope, scope_id):
        if panel is None:
            return
        if not scope_id:
            messagebox.showwarning(
                _t("scheduling.tabs.timetables"),
                _t('gui.academics.timetable_management.dialogs.pick_one_first',
                   default="Choose one from the list first."),
                parent=self.window)
            return
        panel.set_target(scope=scope, scope_id=scope_id)

    # -- rooms ------------------------------------------------------------
    def _build_room_tab(self):
        """A room's week: timetabled sessions plus its bookings (exams,
        events), so a free-looking room really is free."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t(
            'gui.academics.timetable_management.tabs.rooms', default="Rooms"))
        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(bar, text=_t(
            'gui.academics.timetable_management.labels.room', default="Room:")).pack(
            side=tk.LEFT)
        self._picker(bar, self._room_choices,
                     lambda rid: self._set_grid_target(self.room_grid, "room", rid))
        self.room_grid = self._make_grid(tab, scope="room")
        self._week_bar(tab, lambda: self.room_grid)

    def _can_edit_timetable(self):
        try:
            return bool(self.auth and (self.auth.check_permission("manage_course_schedules")
                                       or self.auth.check_permission("manage_modules")))
        except Exception:
            return False

    def _actor(self):
        user = getattr(self.auth, "current_user", None) or {}
        name = user.get("username") if isinstance(user, dict) else getattr(user, "username", None)
        return name or "timetable"

    # -- tab 4: whole term ------------------------------------------------
    def _build_term_tab(self):
        """Every session across a whole term, as concrete dates.

        The weekly grid answers "what does a normal week look like"; it cannot
        answer "when do I actually have to be somewhere over the next three
        months". Recurring ``module_schedule`` slots are expanded to real dates
        between the term's start and end, exams are merged in on their own
        dates, and the result is ordered by date — so an exam appears exactly
        once, on the day it is sat.
        """
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t(
            'gui.academics.timetable_management.tabs.term', default="Full Term"))

        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, padx=8, pady=8)

        ttk.Label(bar, text=_t(
            'gui.academics.timetable_management.labels.term', default="Term:")).pack(
            side=tk.LEFT)
        self.term_view_term_var = tk.StringVar()
        self.term_view_term_combo = ttk.Combobox(
            bar, textvariable=self.term_view_term_var, width=26, state="readonly")
        self.term_view_term_combo.pack(side=tk.LEFT, padx=(6, 12))

        ttk.Label(bar, text=_t(
            'gui.academics.timetable_management.labels.for', default="For:")).pack(
            side=tk.LEFT)
        self.term_scope_var = tk.StringVar(value="student")
        scope_combo = ttk.Combobox(
            bar, textvariable=self.term_scope_var, width=11, state="readonly",
            values=["student", "instructor", "module", "room"])
        scope_combo.pack(side=tk.LEFT, padx=(6, 6))
        scope_combo.bind("<<ComboboxSelected>>",
                         lambda e: self._sync_term_target_choices())

        self.term_target_var = tk.StringVar()
        self.term_target_combo = ttk.Combobox(
            bar, textvariable=self.term_target_var, width=34, state="readonly")
        self.term_target_combo.pack(side=tk.LEFT, padx=(0, 6))

        ttk.Button(bar, text=_t(
            'gui.academics.timetable_management.buttons.show', default="Show"),
            command=self._refresh_term_tab).pack(side=tk.LEFT)

        actions = ttk.Frame(tab)
        actions.pack(fill=tk.X, padx=8, pady=(0, 4))
        if self._can_edit_timetable():
            ttk.Button(actions, text="Cancel this session…",
                       command=self._cancel_selected_session).pack(side=tk.LEFT)
            ttk.Button(actions, text="Move / change room…",
                       command=self._move_selected_session).pack(side=tk.LEFT, padx=4)
            ttk.Button(actions, text="Undo change",
                       command=self._undo_selected_change).pack(side=tk.LEFT)
        ttk.Button(actions, text="Export these dates (.ics)",
                   command=self._export_term_ics).pack(side=tk.RIGHT)

        columns = ("date", "day", "start", "end", "kind", "module", "room", "week", "status")
        self.term_tree = ttk.Treeview(
            tab, columns=columns, show="headings", height=18)
        self.term_tree.tag_configure("cancelled", foreground="#999999")
        self.term_tree.tag_configure("moved", foreground="#b9770e")
        for col, heading, width in zip(
                columns,
                ("Date", "Day", "Start", "End", "Type", "Module", "Room", "Week", "Status"),
                (95, 85, 60, 60, 80, 100, 140, 50, 170)):
            self.term_tree.heading(col, text=heading)
            self.term_tree.column(col, width=width, anchor="w")
        self.term_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        self.term_status_var = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.term_status_var,
                  foreground="#7f8c8d").pack(anchor="w", padx=10, pady=(0, 8))

        self._load_term_view_terms()
        self._sync_term_target_choices()

    def _load_term_view_terms(self):
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT id, name, start_date, end_date FROM academic_terms "
                    "WHERE start_date IS NOT NULL AND end_date IS NOT NULL "
                    "ORDER BY start_date DESC"
                ).fetchall()
        except Exception as exc:
            logger.warning("timetable: could not load terms: %s", exc)
            rows = []
        self._term_view_map = {
            f"{r[1]} ({r[2]} → {r[3]})": (r[2], r[3]) for r in rows
        }
        self.term_view_term_combo["values"] = list(self._term_view_map)
        if self._term_view_map:
            self.term_view_term_var.set(next(iter(self._term_view_map)))

    def _sync_term_target_choices(self):
        """Repoint the target dropdown at whichever kind of thing is selected."""
        scope = self.term_scope_var.get()
        choices = {
            "student": self._student_choices,
            "instructor": self._instructor_choices,
            "module": self._module_choices,
            "room": self._room_choices,
        }.get(scope, {})
        self._term_target_choices = choices
        self.term_target_combo["values"] = list(choices)
        self.term_target_var.set("")

    def _refresh_term_tab(self):
        for item in self.term_tree.get_children():
            self.term_tree.delete(item)
        self.term_status_var.set("")

        span = getattr(self, "_term_view_map", {}).get(self.term_view_term_var.get())
        target = getattr(self, "_term_target_choices", {}).get(
            self.term_target_var.get())
        if not span:
            self.term_status_var.set("Select a term with start and end dates.")
            return
        if not target:
            self.term_status_var.set("Select a student, instructor or module.")
            return

        try:
            rows = self._collect_term_rows(
                span[0], span[1], self.term_scope_var.get(), target)
        except Exception as exc:
            self.term_status_var.set(f"(load failed: {exc})")
            return

        for i, row in enumerate(rows):
            status = row[8] if len(row) > 8 else ""
            tag = ("cancelled",) if status.startswith("Cancelled") else (
                ("moved",) if status.startswith("Moved") else ())
            self.term_tree.insert("", "end", iid=str(i), values=row, tags=tag)

        sessions = sum(1 for r in rows if r[4] != "Exam" and not str(r[8]).startswith("Cancelled"))
        exams = sum(1 for r in rows if r[4] == "Exam")
        cancelled = sum(1 for r in rows if str(r[8]).startswith("Cancelled"))
        self.term_status_var.set(
            f"{span[0]} → {span[1]}   ·   {sessions} session(s), {exams} exam(s)"
            + (f", {cancelled} cancelled" if cancelled else "")
            + ("   ·   holidays, teaching weeks and one-off changes applied"))

    @staticmethod
    def _slots_for(conn, tt, scope, target):
        """Weekly slots in scope — the same rules as the weekly grid."""
        if scope == "student":
            return tt.student_slots(conn, target)
        if scope == "instructor":
            return tt.slots(conn, instructor_id=target)
        if scope == "room":
            return tt.slots(conn, room_id=target)
        return tt.slots(conn, module_codes=[str(target)])

    def _collect_term_rows(self, start_date, end_date, scope, target):
        """Real dated sessions across the term, with exams merged in.

        Rows are ``(date, day, start, end, type, module, room, week, status)``;
        ``self._term_occurrences`` holds the session behind each row (None for
        an exam) so a single week can be cancelled or moved from the list.
        """
        from datetime import datetime as _dt

        from education_system.systems.university.application.teaching import occurrences as tt
        term_start = _dt.strptime(str(start_date)[:10], "%Y-%m-%d").date()
        term_end = _dt.strptime(str(end_date)[:10], "%Y-%m-%d").date()
        if term_end < term_start:
            raise ValueError("term ends before it starts")

        entries = []
        with get_connection() as conn:
            slot_list = self._slots_for(conn, tt, scope, target)
            for o in tt.occurrences(conn, term_start, term_end, slot_list):
                status = {"cancelled": f"Cancelled: {o.get('reason') or ''}",
                          "moved": f"Moved from {o.get('moved_from')}"}.get(o["status"], "")
                day = _dt.strptime(o["date"], "%Y-%m-%d").strftime("%A")
                entries.append(((o["date"], day, o["start_time"] or "", o["end_time"] or "",
                                 str(o["session_type"]).title(), o["module_code"],
                                 o.get("room") or ("Online" if o.get("online_url") else ""),
                                 o.get("week") or "", status), o))
            modules = sorted({s["module_code"] for s in slot_list})
            if scope == "module":
                modules = [str(target)]
            entries += self._term_exams(conn, modules, term_start, term_end)
            conn.commit()

        entries.sort(key=lambda e: (e[0][0], e[0][2]))
        self._term_occurrences = [o for _row, o in entries]
        return [row for row, _o in entries]

    @staticmethod
    def _term_exams(conn, modules, term_start, term_end):
        """Exams sit on a single date, so they are taken as-is."""
        from datetime import datetime as _dt
        if not modules:
            return []
        placeholders = ",".join("?" for _ in modules)
        out = []
        try:
            # db-audit: ignore[DBW001] - only placeholders are interpolated
            for code, date, start, end, room in conn.execute(
                f"""
                SELECT module_code, date, start_time, end_time, COALESCE(room, '')
                FROM exams
                WHERE module_code IN ({placeholders})
                  AND date(date) BETWEEN date(?) AND date(?)
                """,
                modules + [term_start.isoformat(), term_end.isoformat()],
            ).fetchall():
                try:
                    day_name = _dt.strptime(str(date)[:10], "%Y-%m-%d").strftime("%A")
                except ValueError:
                    day_name = ""
                out.append(((str(date)[:10], day_name, start or "", end or "",
                             "Exam", code, room, "", ""), None))
        except Exception as exc:
            logger.debug("term view: exams unavailable: %s", exc)
        return out

    # -- one-off changes to a single week ----------------------------------
    def _selected_occurrence(self):
        sel = self.term_tree.selection()
        occ = None
        if sel:
            occurrences = getattr(self, "_term_occurrences", [])
            index = int(sel[0])
            occ = occurrences[index] if index < len(occurrences) else None
        if occ is None:
            messagebox.showinfo(_t('gui.academics.timetable_management.tabs.term',
                                   default="Full Term"),
                                "Select a teaching session (not an exam) first.",
                                parent=self.window)
        return occ

    def _run_change(self, title, fn, *args, **kwargs):
        from education_system.systems.university.application.teaching import occurrences as tt
        try:
            with get_connection() as conn:
                result = fn(conn, *args, **kwargs)
                conn.commit()
        except ValueError as exc:
            if str(exc).startswith("Clashes with") and "force" in fn.__code__.co_varnames \
                    and messagebox.askyesno(title, f"{exc}\n\nGo ahead anyway?",
                                            parent=self.window):
                return self._run_change(title, fn, *args, force=True, **kwargs)
            messagebox.showerror(title, str(exc), parent=self.window)
            return None
        except Exception as exc:
            logger.exception("%s failed", title)
            messagebox.showerror(title, f"{title} failed: {exc}", parent=self.window)
            return None
        sent = tt.send_emails(result.get("emails", []))
        self.update_activity_log(f"{title}: {sent} email(s) sent")
        self._refresh_term_tab()
        return result

    def _cancel_selected_session(self):
        from tkinter import simpledialog

        from education_system.systems.university.application.teaching import occurrences as tt
        occ = self._selected_occurrence()
        if not occ or occ["status"] == "cancelled":
            return
        reason = simpledialog.askstring(
            "Cancel session", f"Cancel {occ['module_code']} on {occ['date']} "
            f"{occ['start_time']}?\n\nReason (sent to the students):", parent=self.window)
        if reason:
            self._run_change("Cancel session", tt.cancel_session, occ["id"],
                             occ.get("moved_from") or occ["date"], reason, self._actor())

    def _move_selected_session(self):
        from education_system.systems.university.application.teaching import occurrences as tt
        occ = self._selected_occurrence()
        if not occ:
            return
        dialog = tk.Toplevel(self.window)
        dialog.title(f"Move {occ['module_code']} on {occ.get('moved_from') or occ['date']}")
        dialog.transient(self.window)
        form = ttk.Frame(dialog, padding=12)
        form.pack(fill=tk.BOTH, expand=True)
        fields = {}
        for row, (key, label, value) in enumerate((
                ("date", "New date (YYYY-MM-DD)", occ["date"]),
                ("start", "Start (HH:MM)", occ["start_time"]),
                ("end", "End (HH:MM)", occ["end_time"]),
                ("reason", "Reason (sent to the students)", ""))):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=3)
            fields[key] = tk.StringVar(value=value or "")
            ttk.Entry(form, textvariable=fields[key], width=28).grid(row=row, column=1, pady=3)
        ttk.Label(form, text="Room").grid(row=4, column=0, sticky="w", pady=3)
        rooms = ["(same room)"] + list(self._room_choices)
        room_var = tk.StringVar(value=rooms[0])
        ttk.Combobox(form, textvariable=room_var, values=rooms, width=26,
                     state="readonly").grid(row=4, column=1, pady=3)

        def save():
            result = self._run_change(
                "Move session", tt.move_session, occ["id"], occ.get("moved_from") or occ["date"],
                new_date=fields["date"].get().strip(), new_start=fields["start"].get().strip(),
                new_end=fields["end"].get().strip(),
                new_room_id=self._room_choices.get(room_var.get()),
                reason=fields["reason"].get(), actor=self._actor())
            if result:
                dialog.destroy()

        buttons = ttk.Frame(form)
        buttons.grid(row=5, column=0, columnspan=2, sticky="w", pady=(8, 0))
        ttk.Button(buttons, text="Move", command=save).pack(side=tk.LEFT)
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side=tk.LEFT, padx=6)

    def _undo_selected_change(self):
        from education_system.systems.university.application.teaching import occurrences as tt
        occ = self._selected_occurrence()
        if not occ:
            return
        if not occ.get("change_id"):
            messagebox.showinfo("Undo change", "That session runs as timetabled; "
                                "there is nothing to undo.", parent=self.window)
            return
        if messagebox.askyesno("Undo change", "Put this session back as originally "
                               "timetabled? The students are told.", parent=self.window):
            self._run_change("Undo change", tt.restore_session, occ["change_id"], self._actor())

    def _export_term_ics(self):
        from tkinter import filedialog

        from education_system.systems.university.application.teaching import occurrences as tt
        sessions = [o for o in getattr(self, "_term_occurrences", []) if o]
        if not sessions:
            messagebox.showinfo("Export", "Show a term's sessions first.", parent=self.window)
            return
        path = filedialog.asksaveasfilename(parent=self.window, defaultextension=".ics",
                                            filetypes=[("iCalendar", "*.ics")],
                                            initialfile="timetable.ics")
        if path:
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(tt.ical(sessions, self.term_target_var.get() or "Timetable"))
            messagebox.showinfo("Export", f"Saved {len(sessions)} session(s) to {path}",
                                parent=self.window)

    # -- tab 5: exams -----------------------------------------------------
    def _build_exams_tab(self):
        """The exam timetable, read straight from the Exam Scheduling system."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t(
            'gui.academics.timetable_management.tabs.exams', default="Exams"))

        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(bar, text=_t(
            'gui.academics.timetable_management.labels.module',
            default="Module:")).pack(side=tk.LEFT)
        self.exam_filter_var = tk.StringVar()
        self.exam_filter_combo = ttk.Combobox(
            bar, textvariable=self.exam_filter_var, width=34, state="readonly",
            values=[_t('gui.academics.timetable_management.values.all_modules',
                       default="(all modules)")] + list(self._module_choices))
        self.exam_filter_combo.current(0)
        self.exam_filter_combo.pack(side=tk.LEFT, padx=(6, 6))
        self.exam_filter_combo.bind("<<ComboboxSelected>>",
                                    lambda e: self._refresh_exams_tab())
        ttk.Button(bar, text=_t(
            'gui.academics.timetable_management.buttons.refresh',
            default="Refresh"), command=self._refresh_exams_tab).pack(side=tk.LEFT)
        ttk.Button(bar, text=_t(
            'gui.academics.timetable_management.buttons.open_exam_scheduler',
            default="Open Exam Management…"),
            command=self._open_exam_scheduler).pack(side=tk.RIGHT)

        columns = ("date", "day", "start", "end", "module", "room", "instructor",
                   "students")
        self.exams_tree = ttk.Treeview(
            tab, columns=columns, show="headings", height=18)
        for col, heading, width in zip(
                columns,
                ("Date", "Day", "Start", "End", "Module", "Room", "Instructor",
                 "Students"),
                (95, 85, 65, 65, 110, 130, 150, 75)):
            self.exams_tree.heading(col, text=heading)
            self.exams_tree.column(col, width=width, anchor="w")
        self.exams_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 4))

        self.exams_status_var = tk.StringVar(value="")
        ttk.Label(tab, textvariable=self.exams_status_var,
                  foreground="#7f8c8d").pack(anchor="w", padx=10, pady=(0, 8))

        self._refresh_exams_tab()

    def _refresh_exams_tab(self):
        from datetime import datetime as _dt

        for item in self.exams_tree.get_children():
            self.exams_tree.delete(item)

        module_code = self._module_choices.get(self.exam_filter_var.get())
        sql = ("SELECT date, start_time, end_time, module_code, "
               "COALESCE(room, ''), COALESCE(instructor_name, ''), "
               "COALESCE(students_enrolled, 0) FROM exams")
        params = []
        if module_code:
            sql += " WHERE module_code = ?"
            params.append(module_code)
        sql += " ORDER BY date, start_time"

        try:
            with get_connection() as conn:
                rows = conn.execute(sql, params).fetchall()
        except Exception as exc:
            # `exams` is created lazily by the Exam Scheduling GUI.
            self.exams_status_var.set(
                f"No exam data available ({exc}). Schedule exams in the "
                f"Exam Management first.")
            return

        for date, start, end, code, room, instructor, enrolled in rows:
            try:
                day_name = _dt.strptime(str(date)[:10], "%Y-%m-%d").strftime("%A")
            except ValueError:
                day_name = ""
            self.exams_tree.insert("", "end", values=(
                str(date)[:10], day_name, start or "", end or "", code,
                room, instructor, enrolled))

        self.exams_status_var.set(
            f"{len(rows)} exam(s)" if rows else "No exams scheduled.")

    def _open_exam_scheduler(self):
        try:
            from education_system.systems.university.domains.teaching.interfaces.gui._cross_launchers import (
                open_exam_gui,
            )
            open_exam_gui(self.window, self.auth)
        except Exception as exc:
            messagebox.showerror(
                _t('gui.academics.timetable_management.dialogs.error', default="Error"),
                f"Failed to open Exam Management: {exc}", parent=self.window)

    # -- tab 6: sections (the other data model) ---------------------------
    def _build_sections_tab(self):
        """Section meetings — ``course_sections`` / ``section_meetings``.

        This is the model behind Course Management's old Timetable tab. It is
        a genuinely different schema from ``module_schedule``, so it gets its
        own tab and its own reader rather than being forced through
        WeeklyGridPanel, which only knows the module-based tables.

        Editing meetings stays in Course Management: that editor is built on
        that GUI's own dialog helpers, and moving it was not worth the risk in
        the same change as the merge. The button below goes there.
        """
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t(
            'gui.academics.timetable_management.tabs.sections',
            default="Sections"))

        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, padx=8, pady=8)
        ttk.Label(bar, text=_t(
            'gui.academics.timetable_management.labels.term', default="Term:")).pack(
            side=tk.LEFT)
        self.tab_term_var = tk.StringVar()
        self.tab_term_combo = ttk.Combobox(
            bar, textvariable=self.tab_term_var, width=28, state="readonly")
        self.tab_term_combo.pack(side=tk.LEFT, padx=(6, 6))
        self.tab_term_combo.bind(
            "<<ComboboxSelected>>", lambda e: self._refresh_sections_tab())
        ttk.Button(bar, text=_t(
            'gui.academics.timetable_management.buttons.refresh',
            default="Refresh"), command=self._refresh_sections_tab).pack(side=tk.LEFT)
        ttk.Button(bar, text=_t(
            'gui.academics.timetable_management.buttons.edit_in_course_management',
            default="Edit in Course Management…"),
            command=self._open_course_management).pack(side=tk.RIGHT)

        columns = ("day", "start", "end", "course", "section", "location")
        self.sections_tree = ttk.Treeview(
            tab, columns=columns, show="headings", height=14)
        for col, heading in zip(columns, (
                "Day", "Start", "End", "Course", "Section", "Location")):
            self.sections_tree.heading(col, text=heading)
            self.sections_tree.column(col, width=120, anchor="w")
        self.sections_tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self._load_terms()

    def _load_terms(self):
        try:
            with get_connection() as conn:
                rows = conn.execute(
                    "SELECT id, name, COALESCE(status, '') FROM academic_terms "
                    "ORDER BY id DESC"
                ).fetchall()
        except Exception:
            rows = []
        self._term_map = {
            f"{r[1]}{(' — ' + r[2]) if r[2] else ''} (#{r[0]})": r[0]
            for r in rows
        }
        self.tab_term_combo["values"] = list(self._term_map)
        if self._term_map:
            self.tab_term_var.set(next(iter(self._term_map)))
            self._refresh_sections_tab()

    def _refresh_sections_tab(self):
        for item in self.sections_tree.get_children():
            self.sections_tree.delete(item)

        term_id = getattr(self, "_term_map", {}).get(self.tab_term_var.get())
        if term_id is None:
            return
        try:
            with get_connection() as conn:
                # course_sections already carries course_code, so `courses` is
                # not joined — it holds both `code` and `course_code` columns
                # and picking between them is an ambiguity worth avoiding.
                rows = conn.execute(
                    """
                    SELECT sm.day_of_week, sm.start_time, sm.end_time,
                           COALESCE(cs.course_code, ''),
                           COALESCE(cs.section_number, ''),
                           COALESCE(sm.location, cs.location, '')
                    FROM section_meetings sm
                    JOIN course_sections cs ON sm.section_id = cs.id
                    WHERE cs.term_id = ?
                    ORDER BY sm.day_of_week, sm.start_time
                    """,
                    (term_id,),
                ).fetchall()
        except Exception as exc:
            self.sections_tree.insert(
                "", "end", values=(f"(load failed: {exc})", "", "", "", "", ""))
            return

        for row in rows:
            self.sections_tree.insert("", "end", values=tuple(row))

    def _open_course_management(self):
        try:
            from education_system.systems.university.domains.teaching.interfaces.gui._cross_launchers import (
                open_course_gui,
            )
            open_course_gui(self.window, self.auth)
        except Exception as exc:
            messagebox.showerror(
                _t('gui.academics.timetable_management.dialogs.error', default="Error"),
                f"Failed to open Course Management: {exc}", parent=self.window)

    # -- tab 5: conflicts (spans both models) -----------------------------
    def _build_conflicts_tab(self):
        """Unresolved clashes, plus a slot checker that reads both models."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text=_t(
            'gui.academics.timetable_management.tabs.conflicts',
            default="Conflicts"))

        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, padx=8, pady=8)
        ttk.Button(bar, text=_t(
            'gui.academics.timetable_management.buttons.refresh',
            default="Refresh"), command=self._refresh_conflicts).pack(side=tk.LEFT)

        self.conflicts_list = tk.Listbox(tab)
        self.conflicts_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        check = ttk.LabelFrame(tab, text=_t(
            'gui.academics.timetable_management.labels.check_a_slot',
            default="Check a slot (both scheduling models)"), padding=6)
        check.pack(fill=tk.X, padx=8, pady=(0, 8))
        self.check_day_var = tk.StringVar(value=DAYS_OF_WEEK[0])
        self.check_start_var = tk.StringVar(value="09:00")
        self.check_end_var = tk.StringVar(value="10:00")
        self.check_location_var = tk.StringVar()
        ttk.Combobox(check, textvariable=self.check_day_var,
                     values=list(DAYS_OF_WEEK), width=10,
                     state="readonly").pack(side=tk.LEFT, padx=2)
        ttk.Entry(check, textvariable=self.check_start_var, width=7).pack(
            side=tk.LEFT, padx=2)
        ttk.Entry(check, textvariable=self.check_end_var, width=7).pack(
            side=tk.LEFT, padx=2)
        ttk.Entry(check, textvariable=self.check_location_var, width=18).pack(
            side=tk.LEFT, padx=2)
        ttk.Button(check, text=_t(
            'gui.academics.timetable_management.buttons.check', default="Check"),
            command=self._check_slot).pack(side=tk.LEFT, padx=6)

        self._refresh_conflicts()

    def _refresh_conflicts(self):
        self.conflicts_list.delete(0, tk.END)
        try:
            # One detection pass for the whole database. Never call this per
            # row — it re-runs the full detector every time.
            from education_system.systems.university.domains.teaching.interfaces.gui._cross_services import (
                _all_conflicts,
            )
            conflicts = _all_conflicts()
        except Exception as exc:
            self.conflicts_list.insert(tk.END, f"(unavailable: {exc})")
            return

        if not conflicts:
            self.conflicts_list.insert(tk.END, _t(
                'gui.academics.timetable_management.labels.no_conflicts',
                default="No unresolved scheduling conflicts."))
        for c in conflicts:
            self.conflicts_list.insert(tk.END, (
                c.get("description") or c.get("conflict_type") or str(c)))
        self._list_timetable_checks()

    def _list_timetable_checks(self):
        """Room size, staff limits, room bookings and slots that match no term."""
        from education_system.systems.university.application.teaching import occurrences as tt
        try:
            with get_connection() as conn:
                every = tt.slots(conn)
                sections = (
                    ("Room too small", tt.capacity_issues(conn)),
                    ("Staff hours / preferences", tt.staff_issues(conn)),
                    ("Room also booked", [
                        f"{s['module_code']} {s['day_of_week']} {s['start_time']}: {label}"
                        for s in every for _i, label, _a, _b in tt.booking_clashes_for_slot(
                            conn, s["room_id"], s["day_of_week"], s["start_time"],
                            s["end_time"])]),
                    ("Never shown — matches no term", [
                        f"{s['module_code']} {s['day_of_week']} {s['start_time']} "
                        f"({s['semester'] or 'no semester'} {s['year'] or ''})"
                        for s in tt.unplaced(conn, every)]),
                )
                conn.commit()
        except Exception as exc:
            self.conflicts_list.insert(tk.END, f"(timetable checks unavailable: {exc})")
            return
        for title, items in sections:
            if items:
                self.conflicts_list.insert(tk.END, "")
                self.conflicts_list.insert(tk.END, f"— {title} ({len(items)}) —")
                for item in items:
                    self.conflicts_list.insert(tk.END, f"  {item}")

    def _check_slot(self):
        location = self.check_location_var.get().strip()
        if not location:
            messagebox.showwarning(
                _t('gui.academics.timetable_management.tabs.conflicts',
                   default="Conflicts"),
                _t('gui.academics.timetable_management.dialogs.enter_a_location',
                   default="Enter a room/location to check against."),
                parent=self.window)
            return
        try:
            from education_system.systems.university.domains.teaching.domain.timetable_bridge import (
                find_timetable_conflicts,
            )
            clashes = find_timetable_conflicts(
                self.check_day_var.get(), self.check_start_var.get(),
                self.check_end_var.get(), location=location)
        except Exception as exc:
            messagebox.showerror(
                _t('gui.academics.timetable_management.dialogs.error', default="Error"),
                f"Conflict check failed: {exc}", parent=self.window)
            return

        if not clashes:
            messagebox.showinfo(
                _t('gui.academics.timetable_management.tabs.conflicts',
                   default="Conflicts"),
                _t('gui.academics.timetable_management.dialogs.slot_is_free',
                   default="That slot is free in both scheduling models."),
                parent=self.window)
        else:
            messagebox.showwarning(
                _t('gui.academics.timetable_management.tabs.conflicts',
                   default="Conflicts"),
                "\n".join(f"• {c}" for c in clashes), parent=self.window)

    # -- tab 6: the original generate / email / export pane ----------------
    def _build_generate_tab(self, container):
        # Left panel: controls
        left = ttk.Frame(container, width=260)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        left.pack_propagate(False)

        # Student timetable section
        student_frame = ttk.LabelFrame(
            left, text=_t("scheduling.student_timetables"), padding=10)
        student_frame.pack(fill=tk.X, pady=5)
        ttk.Label(student_frame,
                  text=_t("scheduling.student_id") + ":").pack(anchor=tk.W)
        self.student_id_var = tk.StringVar()
        ttk.Entry(student_frame, textvariable=self.student_id_var,
                  width=20).pack(fill=tk.X, pady=2)
        ttk.Button(student_frame,
                   text=_t("scheduling.generate_student_timetable"),
                   command=self.generate_student_timetable).pack(fill=tk.X, pady=2)
        ttk.Button(student_frame,
                   text=_t("scheduling.email_timetable_to_student"),
                   command=self.email_student_timetable).pack(fill=tk.X, pady=2)
        ttk.Button(student_frame,
                   text=_t("scheduling.check_student_conflicts"),
                   command=self.check_student_conflicts).pack(fill=tk.X, pady=2)
        # "Open Student Timetable Viewer…" used to sit here and open a second
        # window. The Student tab is that viewer now, so the button would only
        # duplicate it.

        # Instructor timetable section
        instructor_frame = ttk.LabelFrame(
            left, text=_t("scheduling.instructor_timetables"), padding=10)
        instructor_frame.pack(fill=tk.X, pady=5)
        ttk.Label(instructor_frame,
                  text=_t("scheduling.instructor_id") + ":").pack(anchor=tk.W)
        self.instructor_id_var = tk.StringVar()
        ttk.Entry(instructor_frame, textvariable=self.instructor_id_var,
                  width=20).pack(fill=tk.X, pady=2)
        ttk.Button(instructor_frame,
                   text=_t("scheduling.generate_instructor_timetable"),
                   command=self.generate_instructor_timetable).pack(fill=tk.X, pady=2)
        ttk.Button(instructor_frame,
                   text=_t("scheduling.email_timetable_to_instructor"),
                   command=self.email_instructor_timetable).pack(fill=tk.X, pady=2)

        # Export options
        export_frame = ttk.LabelFrame(
            left, text=_t("scheduling.export_options"), padding=10)
        export_frame.pack(fill=tk.X, pady=5)
        self.export_format_var = tk.StringVar(value=_t('gui.academics.timetable_management.values.pdf', default="PDF"))
        for fmt in ("PDF", "CSV", "Excel", "iCal"):
            ttk.Radiobutton(export_frame, text=fmt,
                            variable=self.export_format_var,
                            value=fmt).pack(anchor=tk.W)
        ttk.Button(export_frame, text=_t("scheduling.export_last_generated"),
                   command=self.export_last_timetable).pack(fill=tk.X, pady=5)

        # Right panel: scrollable timetable display
        right = ttk.Frame(container)
        right.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        display_frame = ttk.LabelFrame(
            right, text=_t("scheduling.timetable_display"), padding=10)
        display_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(display_frame)
        v_scroll = ttk.Scrollbar(display_frame, orient=tk.VERTICAL,
                                 command=canvas.yview)
        h_scroll = ttk.Scrollbar(display_frame, orient=tk.HORIZONTAL,
                                 command=canvas.xview)
        self.timetable_frame = ttk.Frame(canvas)
        self.timetable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.timetable_frame, anchor="nw")
        canvas.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

    # ---- schedule-data (instance wrappers over the shared helpers) -------
    def _get_student_schedule_data(self, student_id):
        return get_student_schedule_data(student_id)

    def _get_instructor_schedule_data(self, instructor_id):
        return get_instructor_schedule_data(instructor_id)

    # ------------------------------------------------------------ actions
    def generate_student_timetable(self):
        student_id = self.student_id_var.get().strip()
        if not student_id:
            messagebox.showwarning(_t('gui.academics.timetable_management.dialogs.warning', default="Warning"), _t('gui.academics.timetable_management.dialogs.please_enter_a_student_id', default="Please enter a student ID."),
                                   parent=self.root)
            return
        try:
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT first_name, last_name FROM students WHERE student_id = ?",
                    (student_id,))
                student = cursor.fetchone()
            if not student:
                messagebox.showerror(
                    _t('gui.academics.timetable_management.dialogs.error', default="Error"), f"Student ID {student_id} does not exist.",
                    parent=self.root)
                return
            student_name = f"{student[0]} {student[1]}"
            schedule_data = get_student_schedule_data(student_id)
            if not schedule_data:
                for widget in self.timetable_frame.winfo_children():
                    widget.destroy()
                tk.Label(self.timetable_frame,
                         text=f"No schedule found for student {student_id}",
                         font=("Arial", 12)).pack(pady=20)
                return
            self._display_timetable_grid(
                schedule_data,
                f"Timetable for {student_name} ({student_id})")
            conflicts = self.scheduler.check_student_conflicts(student_id)
            if conflicts:
                tk.Label(
                    self.timetable_frame,
                    text=f"⚠️ {len(conflicts)} scheduling conflict(s) detected",
                    font=("Arial", 10, "bold"), fg="red").pack(pady=10)
            self.update_activity_log(f"Generated timetable for student {student_id}")
            self.last_timetable_data = schedule_data
            self.last_timetable_type = "student"
            self.last_timetable_id = student_id
        except Exception as e:
            messagebox.showerror(
                _t('gui.academics.timetable_management.dialogs.error', default="Error"), f"Failed to generate student timetable: {e}",
                parent=self.root)

    def generate_instructor_timetable(self):
        instructor_id_str = self.instructor_id_var.get().strip()
        if not instructor_id_str:
            messagebox.showwarning(_t('gui.academics.timetable_management.dialogs.warning', default="Warning"), _t('gui.academics.timetable_management.dialogs.please_enter_an_instructor_id', default="Please enter an instructor ID."),
                                   parent=self.root)
            return
        try:
            instructor_id = int(instructor_id_str)
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT first_name, last_name FROM instructors WHERE id = ?",
                    (instructor_id,))
                instructor = cursor.fetchone()
            if not instructor:
                messagebox.showerror(
                    _t('gui.academics.timetable_management.dialogs.error', default="Error"), f"Instructor ID {instructor_id} does not exist.",
                    parent=self.root)
                return
            instructor_name = f"{instructor[0]} {instructor[1]}"
            schedule_data = get_instructor_schedule_data(instructor_id)
            if not schedule_data:
                for widget in self.timetable_frame.winfo_children():
                    widget.destroy()
                tk.Label(self.timetable_frame,
                         text=f"No schedule found for instructor {instructor_name}",
                         font=("Arial", 12)).pack(pady=20)
                return
            self._display_timetable_grid(
                schedule_data,
                f"Timetable for {instructor_name} (ID: {instructor_id})")
            self.update_activity_log(
                f"Generated timetable for instructor {instructor_name}")
            self.last_timetable_data = schedule_data
            self.last_timetable_type = "instructor"
            self.last_timetable_id = instructor_id
        except ValueError:
            messagebox.showerror(
                _t('gui.academics.timetable_management.dialogs.error', default="Error"), _t('gui.academics.timetable_management.dialogs.invalid_instructor_id_please_enter_a_number', default="Invalid instructor ID. Please enter a number."),
                parent=self.root)
        except Exception as e:
            messagebox.showerror(
                _t('gui.academics.timetable_management.dialogs.error', default="Error"), f"Failed to generate instructor timetable: {e}",
                parent=self.root)

    def email_student_timetable(self):
        student_id = self.student_id_var.get().strip()
        if not student_id:
            messagebox.showwarning(_t('gui.academics.timetable_management.dialogs.warning', default="Warning"), _t('gui.academics.timetable_management.dialogs.please_enter_a_student_id', default="Please enter a student ID."),
                                   parent=self.root)
            return
        try:
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT first_name, last_name, email_address FROM students "
                    "WHERE student_id = ?", (student_id,))
                student = cursor.fetchone()
            if not student:
                messagebox.showerror(_t('gui.academics.timetable_management.dialogs.error', default="Error"), f"Student ID {student_id} not found.",
                                     parent=self.root)
                return
            first_name, last_name, email = student
            student_name = f"{first_name} {last_name}"
            if not email:
                messagebox.showerror(
                    _t('gui.academics.timetable_management.dialogs.error', default="Error"), f"No email address found for student {student_name}.",
                    parent=self.root)
                return
            schedule_data = get_student_schedule_data(student_id)
            if not schedule_data:
                messagebox.showinfo(
                    _t('gui.academics.timetable_management.dialogs.info', default="Info"), f"No schedule found for student {student_id}.",
                    parent=self.root)
                return
            body = self._format_timetable_email(schedule_data, student_name, "student")
            from education_system.systems.university.infrastructure.email.email_service import (
                send_email,
            )
            success = send_email(email, f"Your Timetable - {student_name}", body)
            if success:
                messagebox.showinfo(_t('gui.academics.timetable_management.dialogs.success', default="Success"), f"Timetable emailed to {email}",
                                    parent=self.root)
                self.update_activity_log(
                    f"Emailed timetable to student {student_id} ({email})")
            else:
                messagebox.showerror(_t('gui.academics.timetable_management.dialogs.error', default="Error"), _t('gui.academics.timetable_management.dialogs.failed_to_send_timetable_email', default="Failed to send timetable email."),
                                     parent=self.root)
        except Exception as e:
            messagebox.showerror(_t('gui.academics.timetable_management.dialogs.error', default="Error"), f"Failed to email timetable: {e}",
                                 parent=self.root)

    def email_instructor_timetable(self):
        instructor_id_str = self.instructor_id_var.get().strip()
        if not instructor_id_str:
            messagebox.showwarning(_t('gui.academics.timetable_management.dialogs.warning', default="Warning"), _t('gui.academics.timetable_management.dialogs.please_enter_an_instructor_id', default="Please enter an instructor ID."),
                                   parent=self.root)
            return
        try:
            instructor_id = int(instructor_id_str)
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT first_name, last_name, email FROM instructors WHERE id = ?",
                    (instructor_id,))
                instructor = cursor.fetchone()
            if not instructor:
                messagebox.showerror(_t('gui.academics.timetable_management.dialogs.error', default="Error"),
                                     f"Instructor ID {instructor_id} not found.",
                                     parent=self.root)
                return
            first_name, last_name, email = instructor
            instructor_name = f"{first_name} {last_name}"
            if not email:
                messagebox.showerror(
                    _t('gui.academics.timetable_management.dialogs.error', default="Error"),
                    f"No email address found for instructor {instructor_name}.",
                    parent=self.root)
                return
            schedule_data = get_instructor_schedule_data(instructor_id)
            if not schedule_data:
                messagebox.showinfo(
                    _t('gui.academics.timetable_management.dialogs.info', default="Info"), f"No schedule found for instructor {instructor_id}.",
                    parent=self.root)
                return
            body = self._format_timetable_email(
                schedule_data, instructor_name, "instructor")
            from education_system.systems.university.infrastructure.email.email_service import (
                send_email,
            )
            success = send_email(
                email, f"Your Teaching Schedule - {instructor_name}", body)
            if success:
                messagebox.showinfo(_t('gui.academics.timetable_management.dialogs.success', default="Success"), f"Timetable emailed to {email}",
                                    parent=self.root)
                self.update_activity_log(
                    f"Emailed timetable to instructor {instructor_id} ({email})")
            else:
                messagebox.showerror(_t('gui.academics.timetable_management.dialogs.error', default="Error"), _t('gui.academics.timetable_management.dialogs.failed_to_send_timetable_email', default="Failed to send timetable email."),
                                     parent=self.root)
        except ValueError:
            messagebox.showerror(_t('gui.academics.timetable_management.dialogs.error', default="Error"),
                                 _t('gui.academics.timetable_management.dialogs.invalid_instructor_id_please_enter_a_number', default="Invalid instructor ID. Please enter a number."),
                                 parent=self.root)
        except Exception as e:
            messagebox.showerror(_t('gui.academics.timetable_management.dialogs.error', default="Error"), f"Failed to email timetable: {e}",
                                 parent=self.root)

    def _format_timetable_email(self, schedule_data, name, recipient_type):
        lines = [f"Dear {name},\n"]
        lines.append("Here is your class timetable:\n"
                     if recipient_type == "student"
                     else "Here is your teaching schedule:\n")
        lines.append("=" * 60)
        lines.append("")
        days_data: dict = {}
        for entry in schedule_data:
            day = entry.get("day", entry.get("day_of_week", "Unknown"))
            days_data.setdefault(day, []).append(entry)
        day_order = {"Monday": 1, "Tuesday": 2, "Wednesday": 3, "Thursday": 4,
                     "Friday": 5, "Saturday": 6, "Sunday": 7}
        for day in sorted(days_data.keys(), key=lambda d: day_order.get(d, 8)):
            lines.append(f"\n{day.upper()}")
            lines.append("-" * 40)
            for entry in sorted(days_data[day],
                                key=lambda x: x.get("start_time", "")):
                module_code = entry.get("module_code", "N/A")
                module_name = entry.get("module_name", "")
                lines.append(f"  {entry.get('start_time', 'TBA')} - "
                             f"{entry.get('end_time', 'TBA')}")
                lines.append(f"    {module_code}: {module_name}"
                             if module_name else f"    {module_code}")
                lines.append(f"    Type: {entry.get('session_type', 'Session')}")
                lines.append(f"    Room: {entry.get('room', 'TBA')}")
                lines.append("")
        lines.append("=" * 60)
        lines.append("\nIf you have any questions about your schedule, please "
                     "contact the Academic Office.")
        lines.append("\nBest regards,")
        lines.append("Academic Scheduling System")
        lines.append("University Management System")
        return "\n".join(lines)

    def _display_timetable_grid(self, schedule_data, title):
        for widget in self.timetable_frame.winfo_children():
            widget.destroy()
        tk.Label(self.timetable_frame, text=title,
                 font=("Arial", 14, "bold")).pack(pady=10)

        grid_data = {day: {slot: [] for slot in TIME_SLOTS}
                     for day in DAYS_OF_WEEK}
        for entry in schedule_data:
            day = entry.get("day", entry.get("day_of_week", ""))
            start_time = entry.get("start_time", "")
            if not day or not start_time:
                continue
            try:
                closest_slot = min(
                    TIME_SLOTS, key=lambda x: abs(int(x[:2]) - int(start_time[:2])))
            except (ValueError, TypeError, IndexError):
                continue
            session_info = {
                "module": entry.get("module_code", "N/A"),
                "type": entry.get("session_type", "Session"),
                "room": entry.get("room", "TBA"),
                "time": f"{entry.get('start_time', '')}-{entry.get('end_time', '')}",
            }
            if day in grid_data and closest_slot in grid_data[day]:
                grid_data[day][closest_slot].append(session_info)

        grid_frame = tk.Frame(self.timetable_frame)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        tk.Label(grid_frame, text=_t('gui.academics.timetable_management.labels.time', default="Time"), font=("Arial", 10, "bold"),
                 relief=tk.SOLID, borderwidth=2, bg="#4a90e2", fg="white",
                 width=10, height=2).grid(row=0, column=0, padx=1, pady=1,
                                          sticky="nsew")
        for col, day in enumerate(DAYS_OF_WEEK, 1):
            tk.Label(grid_frame, text=day, font=("Arial", 10, "bold"),
                     relief=tk.SOLID, borderwidth=2, bg="#4a90e2", fg="white",
                     width=18, height=2).grid(row=0, column=col, padx=1, pady=1,
                                              sticky="nsew")
        for row, time_slot in enumerate(TIME_SLOTS, 1):
            tk.Label(grid_frame, text=time_slot, font=("Arial", 9, "bold"),
                     relief=tk.SOLID, borderwidth=2, bg="#e8f4f8",
                     width=10, height=4).grid(row=row, column=0, padx=1, pady=1,
                                              sticky="nsew")
            for col, day in enumerate(DAYS_OF_WEEK, 1):
                entries = grid_data[day][time_slot]
                cell_frame = tk.Frame(grid_frame, relief=tk.SOLID, borderwidth=2,
                                      bg="#d4edda" if entries else "white",
                                      width=160, height=80)
                cell_frame.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")
                cell_frame.grid_propagate(False)
                if not entries:
                    continue
                inner = tk.Frame(cell_frame, bg="#d4edda")
                inner.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
                for i, entry in enumerate(entries):
                    if i < 2:
                        box = tk.Frame(inner, relief=tk.RAISED, borderwidth=1,
                                       bg="#c3e6cb", padx=2, pady=2)
                        box.pack(fill=tk.X, pady=1)
                        tk.Label(box, text=entry["module"], font=("Arial", 8, "bold"),
                                 bg="#c3e6cb", fg="#155724").pack(anchor="w")
                        tk.Label(box, text=entry["type"], font=("Arial", 7),
                                 bg="#c3e6cb", fg="#155724").pack(anchor="w")
                        tk.Label(box, text=f"Room: {entry['room']}",
                                 font=("Arial", 6), bg="#c3e6cb",
                                 fg="#155724").pack(anchor="w")
                if len(entries) > 2:
                    tk.Label(inner, text=f"+ {len(entries) - 2} more...",
                             font=("Arial", 7, "italic"), bg="#d4edda",
                             fg="#155724").pack(anchor="w", pady=2)

    def check_student_conflicts(self):
        student_id = self.student_id_var.get().strip()
        if not student_id:
            messagebox.showwarning(_t('gui.academics.timetable_management.dialogs.warning', default="Warning"), _t('gui.academics.timetable_management.dialogs.please_enter_a_student_id', default="Please enter a student ID."),
                                   parent=self.root)
            return
        try:
            conflicts = self.scheduler.check_student_conflicts(student_id)
            for widget in self.timetable_frame.winfo_children():
                widget.destroy()
            if not conflicts:
                tk.Label(
                    self.timetable_frame,
                    text=f"No scheduling conflicts found for student {student_id}",
                    font=("Arial", 12)).pack(pady=20)
            else:
                tk.Label(self.timetable_frame,
                         text=f"Scheduling Conflicts for Student {student_id}",
                         font=("Arial", 14, "bold")).pack(pady=10)
                for i, conflict in enumerate(conflicts, 1):
                    module1 = conflict.get("module1", {}) if hasattr(conflict, "get") else {}
                    module2 = conflict.get("module2", {}) if hasattr(conflict, "get") else {}
                    frame = ttk.LabelFrame(self.timetable_frame,
                                           text=f"Conflict {i}", padding=10)
                    frame.pack(fill=tk.X, padx=10, pady=5)
                    tk.Label(frame,
                             text=f"Module 1: {module1.get('code', '?')} - "
                                  f"{module1.get('name', '')}",
                             font=("Arial", 10, "bold"), fg="red").pack(anchor="w")
                    tk.Label(frame,
                             text=f"    {module1.get('day', '')} "
                                  f"{module1.get('time', '')} in "
                                  f"{module1.get('room', '')}",
                             font=("Arial", 10)).pack(anchor="w")
                    tk.Label(frame,
                             text=f"Module 2: {module2.get('code', '?')} - "
                                  f"{module2.get('name', '')}",
                             font=("Arial", 10, "bold"),
                             fg="red").pack(anchor="w", pady=(5, 0))
                    tk.Label(frame,
                             text=f"    {module2.get('day', '')} "
                                  f"{module2.get('time', '')} in "
                                  f"{module2.get('room', '')}",
                             font=("Arial", 10)).pack(anchor="w")
            self.update_activity_log(f"Checked conflicts for student {student_id}")
        except Exception as e:
            messagebox.showerror(_t('gui.academics.timetable_management.dialogs.error', default="Error"),
                                 f"Failed to check student conflicts: {e}",
                                 parent=self.root)

    def export_last_timetable(self):
        if not self.last_timetable_data:
            messagebox.showwarning(
                _t('gui.academics.timetable_management.dialogs.warning', default="Warning"),
                _t('gui.academics.timetable_management.dialogs.no_timetable_to_export_please_generate_a_timetable_first', default="No timetable to export. Please generate a timetable first."),
                parent=self.root)
            return
        fmt = self.export_format_var.get()
        # Reuse the module-scheduling export implementations (they operate on
        # ``self`` and only need ``self.root`` as a messagebox parent).
        from education_system.systems.university.domains.teaching.interfaces.gui.module_scheduling import (
            exports as _exports,
        )
        try:
            if fmt == "iCal" and self.last_timetable_type in ("student", "instructor"):
                # Real dated sessions (term dates, holidays, changes applied),
                # not each weekly slot repeated blindly.
                _exports.export_to_ical(self, self.last_timetable_type, self.last_timetable_id)
            elif fmt == "iCal":
                _exports._export_timetable_to_ical(self, self.last_timetable_data)
            elif fmt == "PDF":
                _exports._export_timetable_to_pdf(self, self.last_timetable_data)
            elif fmt == "CSV":
                _exports._export_timetable_to_csv(self, self.last_timetable_data)
            elif fmt == "Excel":
                _exports._export_timetable_to_excel(self, self.last_timetable_data)
        except Exception as e:
            messagebox.showerror(_t('gui.academics.timetable_management.dialogs.error', default="Error"), f"Failed to export timetable: {e}",
                                 parent=self.root)

    def _show_student_timetable_dialog(self):
        """Jump to the Student tab, carrying the ID already typed here.

        No longer bound to a button — the Student tab replaced it. Kept
        because it is a documented hook name on the Module Scheduling GUI, and
        because it now does the right thing if anything still calls it: this
        used to open ``StudentTimetableDialog`` in a second window, a separate
        weekly-grid renderer showing the same data as the Student tab.
        """
        self.select_tab("student")
        student_id = self.student_id_var.get().strip()
        if student_id:
            self.select_student(student_id)
