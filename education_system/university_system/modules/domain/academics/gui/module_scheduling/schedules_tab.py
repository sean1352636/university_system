from education_system.university_system.infrastructure.database.db import DEFAULT_DB_PATH, get_connection, transaction  # injected
from education_system.university_system.core.exceptions import (
    CourseNotFoundError,
    ValidationError,
)

# Import internationalization (i18n) for multi-language support
try:
    from education_system.university_system.core.i18n import (
        get_text as _t,
        get_current_language,
        get_current_language_name,
        set_language,
        get_available_language_list,
        init_i18n,
    )
    from education_system.university_system.modules.shared.utils.gui_language_selector import (
        show_gui_language_selector,
    )
    I18N_AVAILABLE = True
    GUI_LANG_SELECTOR_AVAILABLE = True
    # Initialize i18n if not already done
    init_i18n()
except ImportError:
    I18N_AVAILABLE = False
    GUI_LANG_SELECTOR_AVAILABLE = False
    _t = lambda key, **kwargs: key  # Fallback: return key as-is
    get_current_language = lambda: "en"
    get_current_language_name = lambda: "English"
    set_language = lambda lang, save=True: False
    get_available_language_list = lambda: [("en", "English")]
    show_gui_language_selector = lambda parent=None: "en"

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
from tkinter.font import Font
import os
import sys
from datetime import datetime, timedelta
import threading
import subprocess
import webbrowser
from pathlib import Path

# This ensures full backward compatibility
try:
    from education_system.university_system.modules.domain.academics.services.module_scheduling import (
        ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES,
        display_enhanced_scheduling_menu  # Keep CLI available
    )
except ImportError:
    # If the original module isn't available, we'll define basic constants
    DAYS_OF_WEEK = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    TIME_SLOTS = ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
    SESSION_TYPES = ['Lecture', 'Lab', 'Tutorial', 'Seminar', 'Workshop']
    ROOM_TYPES = ['Lecture Hall', 'Lab', 'Tutorial Room', 'Seminar Room', 'Workshop Room', 'Computer Lab', 'Other']

    # Import the ModuleScheduler class from the document
    try:
        from education_system.university_system.modules.domain.academics.services.module_scheduling import (ModuleScheduler, DAYS_OF_WEEK, TIME_SLOTS, SESSION_TYPES, ROOM_TYPES, display_enhanced_scheduling_menu)
    except Exception:
        class ModuleScheduler: pass

from education_system.university_system.modules.domain.academics.gui.module_scheduling.main_gui import ModuleSchedulingGUI
from education_system.university_system.modules.domain.academics.gui.module_scheduling.dialogs import AddScheduleDialog, EditScheduleDialog

def create_schedules_tab(self):
    """Create the schedules management tab"""
    schedules_frame = ttk.Frame(self.notebook)
    self.notebook.add(schedules_frame, text=_t("scheduling.tabs.schedules"))

    # Controls frame
    controls_frame = ttk.Frame(schedules_frame)
    controls_frame.pack(fill=tk.X, padx=10, pady=5)

    # Add schedule button
    ttk.Button(controls_frame, text=_t("scheduling.buttons.add_schedule"),
              command=self.show_add_schedule_dialog).pack(side=tk.LEFT, padx=5)

    # Edit/Delete buttons
    ttk.Button(controls_frame, text=_t("common.edit_selected"),
              command=self.edit_selected_schedule).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("common.delete_selected"),
              command=self.delete_selected_schedule).pack(side=tk.LEFT, padx=5)
    ttk.Button(controls_frame, text=_t("common.refresh"),
              command=self.refresh_schedules).pack(side=tk.LEFT, padx=5)
    from education_system.university_system.modules.domain.academics.gui.module_scheduling.tooltip import Tooltip
    # Publish Selected — promotes draft → published. Calls the same service
    # path as the Edit dialog so schedule_history captures the state change.
    btn_publish = ttk.Button(controls_frame, text="Publish Selected",
                             command=self._publish_selected_schedule)
    btn_publish.pack(side=tk.LEFT, padx=5)
    Tooltip(btn_publish,
            "Promote selected draft schedules to 'published'. "
            "Notifications will fire and conflict checks apply.")
    # Bulk Actions — reassign instructor / cancel / shift time across many rows.
    btn_bulk = ttk.Button(controls_frame, text="Bulk Actions…",
                          command=self._show_bulk_actions_dialog)
    btn_bulk.pack(side=tk.LEFT, padx=5)
    Tooltip(btn_bulk,
            "Bulk reassign instructor, cancel, or shift the start/end "
            "time of every selected row by ±N minutes.")
    # Clone Term — opens the what-if dialog.
    btn_clone = ttk.Button(controls_frame, text="Clone Term…",
                           command=self._show_clone_term_dialog)
    btn_clone.pack(side=tk.LEFT, padx=5)
    Tooltip(btn_clone,
            "Copy every published row of one term into draft rows of "
            "another term — for what-if scenario planning.")

    # Term + status filter row (above search). Sets the visible scope so
    # planners working on Spring don't see Fall noise.
    filter_frame = ttk.Frame(schedules_frame)
    filter_frame.pack(fill=tk.X, padx=10, pady=(0, 5))
    ttk.Label(filter_frame, text="Term:").pack(side=tk.LEFT)
    self.schedule_semester_var = tk.StringVar(value="(all)")
    sem_combo = ttk.Combobox(filter_frame, textvariable=self.schedule_semester_var,
                             values=["(all)", "Fall", "Spring", "Summer", "Winter"],
                             width=10, state="readonly")
    sem_combo.pack(side=tk.LEFT, padx=(4, 8))
    sem_combo.bind("<<ComboboxSelected>>", lambda _e: self._sched_filter_changed())
    self.schedule_year_var = tk.StringVar(value="(all)")
    year_combo = ttk.Combobox(filter_frame, textvariable=self.schedule_year_var,
                              values=["(all)"] + [str(y) for y in range(
                                  datetime.now().year - 2, datetime.now().year + 4)],
                              width=8, state="readonly")
    year_combo.pack(side=tk.LEFT, padx=(0, 12))
    year_combo.bind("<<ComboboxSelected>>", lambda _e: self._sched_filter_changed())
    ttk.Label(filter_frame, text="Status:").pack(side=tk.LEFT)
    self.schedule_status_var = tk.StringVar(value="(all)")
    status_combo = ttk.Combobox(filter_frame, textvariable=self.schedule_status_var,
                                values=["(all)", "published", "draft", "archived"],
                                width=10, state="readonly")
    status_combo.pack(side=tk.LEFT, padx=(4, 0))
    status_combo.bind("<<ComboboxSelected>>", lambda _e: self._sched_filter_changed())

    # Saved views — persist filter combo state per user so a planner can
    # snap back to "Spring 2026 drafts" without re-picking the combos.
    saved_frame = ttk.Frame(filter_frame)
    saved_frame.pack(side=tk.RIGHT)
    ttk.Label(saved_frame, text="View:").pack(side=tk.LEFT)
    self.saved_view_var = tk.StringVar()
    self.saved_view_combo = ttk.Combobox(saved_frame, textvariable=self.saved_view_var,
                                         width=22, state="readonly")
    self.saved_view_combo.pack(side=tk.LEFT, padx=(4, 4))
    ttk.Button(saved_frame, text="Apply",
               command=self._apply_saved_view).pack(side=tk.LEFT, padx=2)
    ttk.Button(saved_frame, text="Save…",
               command=self._save_current_view).pack(side=tk.LEFT, padx=2)
    ttk.Button(saved_frame, text="Delete",
               command=self._delete_saved_view).pack(side=tk.LEFT, padx=2)
    self._refresh_saved_views()

    # Search frame
    search_frame = ttk.Frame(controls_frame)
    search_frame.pack(side=tk.RIGHT, padx=5)

    ttk.Label(search_frame, text=_t("common.search") + ":").pack(side=tk.LEFT)
    self.schedule_search_var = tk.StringVar()
    self.schedule_search_var.trace('w', lambda *a: self._sched_filter_changed())
    search_entry = ttk.Entry(search_frame, textvariable=self.schedule_search_var, width=20)
    search_entry.pack(side=tk.LEFT, padx=5)

    # Schedules treeview
    tree_frame = ttk.Frame(schedules_frame)
    tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    columns = ("ID", "Module", "Module Name", "Day", "Time", "Room",
               "Instructor", "Type", "Term", "Status")
    self.schedules_tree = ttk.Treeview(tree_frame, columns=columns,
                                       show="headings", style='Data.Treeview',
                                       selectmode="extended")

    # Configure columns
    for col in columns:
        self.schedules_tree.heading(col, text=col)
        if col == "ID":
            self.schedules_tree.column(col, width=50)
        elif col == "Module Name":
            self.schedules_tree.column(col, width=200)
        elif col == "Term":
            self.schedules_tree.column(col, width=110)
        elif col == "Status":
            self.schedules_tree.column(col, width=80)
        else:
            self.schedules_tree.column(col, width=100)

    # Visual cue for non-published rows so they're easy to spot in a busy term.
    self.schedules_tree.tag_configure("draft", foreground="#888")
    self.schedules_tree.tag_configure("archived", foreground="#aaa")
    # Conflict tag — overlapping room/instructor/same-course pairs get a
    # rose-tinted background so users see clashes without leaving the tab.
    self.schedules_tree.tag_configure("conflict", background="#ffd9d9")

    # Scrollbars
    v_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.schedules_tree.yview)
    h_scrollbar = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.schedules_tree.xview)
    self.schedules_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

    # Pack treeview and scrollbars
    self.schedules_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

    # Double-click to edit
    self.schedules_tree.bind("<Double-1>", lambda e: self.edit_selected_schedule())

    # Right-click → reverse link into the absence tracker for that module.
    # Mirrors the scholarship→attendance reverse link for symmetry.
    self._sched_context_menu = tk.Menu(self.schedules_tree, tearoff=0)
    self._sched_context_menu.add_command(
        label="View attendance for this module…",
        command=lambda: _show_module_attendance_popup(
            self, _selected_module_code(self)),
    )
    def _show_ctx(event):
        row = self.schedules_tree.identify_row(event.y)
        if row:
            self.schedules_tree.selection_set(row)
            self._sched_context_menu.tk_popup(event.x_root, event.y_root)
    self.schedules_tree.bind("<Button-3>", _show_ctx)

    # Pagination — keep the unbounded SELECT off this tab. State lives on
    # `self` so refresh and filter share it.
    if not hasattr(self, "_sched_page"):
        self._sched_page = 0
    if not hasattr(self, "_sched_page_size"):
        self._sched_page_size = 100
    if not hasattr(self, "_sched_page_total"):
        self._sched_page_total = 0

    pager = ttk.Frame(schedules_frame)
    pager.pack(fill=tk.X, padx=10)
    ttk.Button(pager, text="<<", width=3,
               command=lambda: self._sched_page_jump("first")).pack(side=tk.LEFT)
    ttk.Button(pager, text="<", width=3,
               command=lambda: self._sched_page_jump("prev")).pack(side=tk.LEFT, padx=(2, 6))
    self._sched_page_label_var = tk.StringVar(value="Page 1 of 1")
    ttk.Label(pager, textvariable=self._sched_page_label_var,
              width=26, anchor=tk.CENTER).pack(side=tk.LEFT)
    ttk.Button(pager, text=">", width=3,
               command=lambda: self._sched_page_jump("next")).pack(side=tk.LEFT, padx=(6, 2))
    ttk.Button(pager, text=">>", width=3,
               command=lambda: self._sched_page_jump("last")).pack(side=tk.LEFT)
    ttk.Label(pager, text="  Rows per page:").pack(side=tk.LEFT, padx=(15, 2))
    self._sched_page_size_var = tk.StringVar(value=str(self._sched_page_size))
    ps_combo = ttk.Combobox(pager, textvariable=self._sched_page_size_var,
                            values=["50", "100", "250", "500", "1000"],
                            width=6, state="readonly")
    ps_combo.pack(side=tk.LEFT)
    ps_combo.bind("<<ComboboxSelected>>",
                  lambda _e: self._sched_on_page_size_change())

ModuleSchedulingGUI.create_schedules_tab = create_schedules_tab


def _selected_module_code(gui):
    """Pull the Module column out of the currently-selected schedules row.

    Schedules tree columns: ID, Module, Module Name, Day, Time, Room,
    Instructor, Type, Term, Status. ``Module`` is values[1].
    """
    sel = gui.schedules_tree.selection()
    if not sel:
        return None
    values = gui.schedules_tree.item(sel[0], "values")
    return values[1] if len(values) > 1 else None


def _show_module_attendance_popup(gui, module_code):
    """Reverse link from the Schedules tab → attendance summary for a module."""
    if not module_code:
        messagebox.showinfo("No selection",
                            "Select a schedule row first.",
                            parent=gui.root)
        return
    try:
        with get_connection() as conn:
            tables = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            if "attendance" not in tables:
                messagebox.showwarning("Attendance",
                                       "Attendance table not available in this DB.",
                                       parent=gui.root)
                return
            summary = conn.execute(
                """SELECT COUNT(*) AS total,
                          SUM(CASE WHEN LOWER(status)='present' THEN 1 ELSE 0 END)
                              AS present_n
                   FROM attendance WHERE module_code = ?""",
                (module_code,)).fetchone()
            recent = conn.execute(
                """SELECT date,
                          SUM(CASE WHEN LOWER(status)='present' THEN 1 ELSE 0 END)
                              AS present_n,
                          COUNT(*) AS total
                   FROM attendance WHERE module_code = ?
                   GROUP BY date ORDER BY date DESC LIMIT 25""",
                (module_code,)).fetchall()
    except Exception as e:
        messagebox.showerror("Attendance", str(e), parent=gui.root)
        return

    win = tk.Toplevel(gui.root)
    win.title(f"Attendance — {module_code}")
    win.geometry("520x500")
    ttk.Label(win, text=f"Module: {module_code}",
              font=("Arial", 12, "bold")).pack(anchor="w", padx=12, pady=(10, 4))

    total = (summary[0] if summary else 0) or 0
    present = (summary[1] if summary else 0) or 0
    pct = (present / total * 100) if total else None
    pct_text = f"{pct:.1f}%" if pct is not None else "—"
    ttk.Label(
        win,
        text=(f"Rows logged: {total}    Present: {present}    "
              f"Module pct: {pct_text}"),
    ).pack(anchor="w", padx=12, pady=2)

    ttk.Label(win, text="Most recent dates (up to 25):",
              font=("Arial", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 2))
    body = ttk.Frame(win)
    body.pack(fill="both", expand=True, padx=12, pady=4)
    cols = ("date", "present", "total", "pct")
    tv = ttk.Treeview(body, columns=cols, show="headings", height=14)
    for c, w in zip(cols, (110, 90, 90, 90)):
        tv.heading(c, text=c.title())
        tv.column(c, width=w, anchor="w")
    for d, p, t in recent:
        per = f"{(p / t * 100):.1f}%" if t else "—"
        tv.insert("", "end", values=(d, p, t, per))
    tv.pack(side="left", fill="both", expand=True)
    vsb = ttk.Scrollbar(body, orient="vertical", command=tv.yview)
    tv.configure(yscrollcommand=vsb.set)
    vsb.pack(side="right", fill="y")
    ttk.Button(win, text="Close", command=win.destroy).pack(pady=8)


ModuleSchedulingGUI._show_module_attendance_popup = staticmethod(
    _show_module_attendance_popup)
ModuleSchedulingGUI._selected_module_code = staticmethod(_selected_module_code)


def _sched_update_pager_label(self):
    if not hasattr(self, "_sched_page_label_var"):
        return
    if self._sched_page_total <= 0:
        self._sched_page_label_var.set("Page 0 of 0")
        return
    pages = max(1, (self._sched_page_total + self._sched_page_size - 1) // self._sched_page_size)
    if self._sched_page >= pages:
        self._sched_page = pages - 1
    self._sched_page_label_var.set(
        f"Page {self._sched_page + 1} of {pages}  ({self._sched_page_total} total)")


ModuleSchedulingGUI._sched_update_pager_label = _sched_update_pager_label


def _sched_on_page_size_change(self):
    try:
        new_size = max(1, int(self._sched_page_size_var.get()))
    except ValueError:
        return
    self._sched_page_size = new_size
    self._sched_page = 0
    self.filter_schedules()


ModuleSchedulingGUI._sched_on_page_size_change = _sched_on_page_size_change


def _sched_filter_changed(self):
    """Reset to page 1 then re-run filter — prevents stuck-on-page-N bug
    when the user narrows results."""
    self._sched_page = 0
    self.filter_schedules()


ModuleSchedulingGUI._sched_filter_changed = _sched_filter_changed


def _sched_page_jump(self, where):
    last = max(0, (self._sched_page_total - 1) // max(1, self._sched_page_size))
    if where == "first":
        self._sched_page = 0
    elif where == "prev":
        self._sched_page = max(0, self._sched_page - 1)
    elif where == "next":
        self._sched_page = min(last, self._sched_page + 1)
    elif where == "last":
        self._sched_page = last
    self.filter_schedules()


ModuleSchedulingGUI._sched_page_jump = _sched_page_jump

def _build_filter_clause(self):
    """Translate the term/status filter combos into a SQL WHERE fragment."""
    where = []
    params = []
    sem = getattr(self, 'schedule_semester_var', None)
    yr = getattr(self, 'schedule_year_var', None)
    st = getattr(self, 'schedule_status_var', None)
    if sem and sem.get() and sem.get() != "(all)":
        where.append("ms.semester = ?")
        params.append(sem.get())
    if yr and yr.get() and yr.get() != "(all)":
        try:
            params.append(int(yr.get()))
            where.append("ms.year = ?")
        except ValueError:
            pass
    if st and st.get() and st.get() != "(all)":
        where.append("ms.status = ?")
        params.append(st.get())
    return where, params


ModuleSchedulingGUI._build_filter_clause = _build_filter_clause


def _detect_conflict_ids(self, schedules):
    """Return the set of schedule_ids whose row clashes with another visible row.

    Two rows clash when they share the same (semester, year, day_of_week)
    and their time ranges overlap *and* one of:
      - they share a room
      - they share an instructor
      - they're the same module_code (data-integrity duplicate)

    Drafts and archived rows are excluded — by design they're allowed to
    overlap published rows.
    """
    def _t2m(hhmm):
        try:
            h, m = hhmm.split(":"); return int(h) * 60 + int(m)
        except (TypeError, ValueError, AttributeError):
            return None

    rows = []
    for s in schedules:
        (sid, code, _name, day, start, end, building, rnum,
         fn, ln, _stype, semester, year, status) = s
        if (status or "published") != "published":
            continue
        sm, em = _t2m(start), _t2m(end)
        if sm is None or em is None or em <= sm:
            continue
        room_key = f"{building}-{rnum}" if building and rnum else None
        inst_key = f"{fn}-{ln}" if fn and ln else None
        rows.append({
            "id": sid, "code": code, "day": day,
            "term": (semester, year), "start": sm, "end": em,
            "room": room_key, "inst": inst_key,
        })

    conflict_ids: set = set()
    for i in range(len(rows)):
        a = rows[i]
        for j in range(i + 1, len(rows)):
            b = rows[j]
            if a["term"] != b["term"] or a["day"] != b["day"]:
                continue
            if not (a["start"] < b["end"] and b["start"] < a["end"]):
                continue
            if (a["room"] and a["room"] == b["room"]) \
               or (a["inst"] and a["inst"] == b["inst"]) \
               or a["code"] == b["code"]:
                conflict_ids.add(a["id"])
                conflict_ids.add(b["id"])
    return conflict_ids


ModuleSchedulingGUI._detect_conflict_ids = _detect_conflict_ids


def _populate_schedule_rows(self, schedules):
    """Insert rows into self.schedules_tree, tagging by status + conflict."""
    conflict_ids = self._detect_conflict_ids(schedules)
    for s in schedules:
        (schedule_id, module_code, module_name, day, start_time, end_time,
         building, room_number, first_name, last_name, session_type,
         semester, year, status) = s
        module_name = module_name or "Unknown"
        time_slot = f"{start_time}-{end_time}"
        room_str = f"{building}-{room_number}" if building and room_number else "TBA"
        instructor = f"{first_name} {last_name}" if first_name and last_name else "TBA"
        if year and int(year) > 0:
            term = f"{semester or '?'} {year}"
        else:
            term = semester or ""
        status = status or "published"
        # Compose tags: conflict wins visually (background colour) and
        # combines with status (foreground colour) so a draft conflict
        # still shows both signals.
        tags = []
        if status in ("draft", "archived"):
            tags.append(status)
        if schedule_id in conflict_ids:
            tags.append("conflict")
        self.schedules_tree.insert("", tk.END, values=(
            schedule_id, module_code, module_name, day, time_slot, room_str,
            instructor, session_type, term, status,
        ), tags=tuple(tags))


ModuleSchedulingGUI._populate_schedule_rows = _populate_schedule_rows


def refresh_schedules(self):
    """Refresh the schedules treeview, paginated."""
    try:
        for item in self.schedules_tree.get_children():
            self.schedules_tree.delete(item)

        from education_system.university_system.infrastructure.database.db import sqlite3
        where, params = self._build_filter_clause()
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""

        page_size = max(1, getattr(self, "_sched_page_size", 100))
        page = getattr(self, "_sched_page", 0)
        offset = page * page_size

        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM module_schedule ms{where_sql}", params)
            self._sched_page_total = cursor.fetchone()[0] or 0
            self._sched_update_pager_label()

            cursor.execute(f'''
            SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week,
                   ms.start_time, ms.end_time, r.building, r.room_number,
                   i.first_name, i.last_name, ms.session_type,
                   ms.semester, ms.year, ms.status
            FROM module_schedule ms
            LEFT JOIN rooms r ON ms.room_id = r.id
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            LEFT JOIN modules m ON ms.module_code = m.module_code
            {where_sql}
            ORDER BY ms.year DESC, ms.semester, ms.module_code, ms.day_of_week, ms.start_time
            LIMIT ? OFFSET ?
            ''', (*params, page_size, offset))
            schedules = cursor.fetchall()

        self._populate_schedule_rows(schedules)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to refresh schedules: {str(e)}", parent=self.root)

ModuleSchedulingGUI.refresh_schedules = refresh_schedules

def filter_schedules(self, *args):
    """Filter schedules based on search term + term/status combos, paginated."""
    search_term = (self.schedule_search_var.get() or "").lower()
    where, params = self._build_filter_clause()

    for item in self.schedules_tree.get_children():
        self.schedules_tree.delete(item)

    if search_term:
        where.append(
            "(LOWER(ms.module_code) LIKE ? OR LOWER(m.module_name) LIKE ? "
            "OR LOWER(ms.day_of_week) LIKE ? OR LOWER(ms.session_type) LIKE ? "
            "OR LOWER(i.first_name) LIKE ? OR LOWER(i.last_name) LIKE ?)"
        )
        params.extend([f'%{search_term}%'] * 6)

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    page_size = max(1, getattr(self, "_sched_page_size", 100))
    page = getattr(self, "_sched_page", 0)
    offset = page * page_size

    try:
        from education_system.university_system.infrastructure.database.db import sqlite3
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT COUNT(*) FROM module_schedule ms "
                f"LEFT JOIN modules m ON ms.module_code = m.module_code "
                f"LEFT JOIN instructors i ON ms.instructor_id = i.id"
                f"{where_sql}",
                params)
            self._sched_page_total = cursor.fetchone()[0] or 0
            self._sched_update_pager_label()

            cursor.execute(f'''
            SELECT ms.id, ms.module_code, m.module_name, ms.day_of_week,
                   ms.start_time, ms.end_time, r.building, r.room_number,
                   i.first_name, i.last_name, ms.session_type,
                   ms.semester, ms.year, ms.status
            FROM module_schedule ms
            LEFT JOIN rooms r ON ms.room_id = r.id
            LEFT JOIN instructors i ON ms.instructor_id = i.id
            LEFT JOIN modules m ON ms.module_code = m.module_code
            {where_sql}
            ORDER BY ms.year DESC, ms.semester, ms.module_code, ms.day_of_week, ms.start_time
            LIMIT ? OFFSET ?
            ''', (*params, page_size, offset))
            schedules = cursor.fetchall()

        self._populate_schedule_rows(schedules)

    except Exception as e:
        messagebox.showerror("Error", f"Failed to filter schedules: {str(e)}", parent=self.root)

ModuleSchedulingGUI.filter_schedules = filter_schedules

def show_add_schedule_dialog(self):
    """Show dialog for adding a new schedule"""
    dialog = AddScheduleDialog(self.root, self.scheduler, gui=self)
    if dialog.result:
        self.refresh_schedules()
        self.refresh_dashboard()
        self.update_activity_log("New schedule added")

ModuleSchedulingGUI.show_add_schedule_dialog = show_add_schedule_dialog

def edit_selected_schedule(self):
    """Edit the selected schedule"""
    selected = self.schedules_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select a schedule to edit.", parent=self.root)
        return

    schedule_data = self.schedules_tree.item(selected[0])['values']
    schedule_id = schedule_data[0]

    dialog = EditScheduleDialog(self.root, self.scheduler, schedule_id, gui=self)
    if dialog.result:
        self.refresh_schedules()
        self.update_activity_log(f"Schedule {schedule_id} updated")

ModuleSchedulingGUI.edit_selected_schedule = edit_selected_schedule

def delete_selected_schedule(self):
    """Delete the selected schedule"""
    selected = self.schedules_tree.selection()
    if not selected:
        messagebox.showwarning("Warning", "Please select a schedule to delete.", parent=self.root)
        return

    schedule_data = self.schedules_tree.item(selected[0])['values']
    schedule_id = schedule_data[0]
    module_code = schedule_data[1]

    if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete the schedule for {module_code}?", parent=self.root):
        try:
            from education_system.university_system.infrastructure.database.db import sqlite3
            with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM module_schedule WHERE id = ?', (schedule_id,))
                conn.commit()

            self.refresh_schedules()
            self.refresh_dashboard()
            self.update_activity_log(f"Schedule {schedule_id} deleted")
            messagebox.showinfo("Success", "Schedule deleted successfully.", parent=self.root)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete schedule: {str(e)}", parent=self.root)

ModuleSchedulingGUI.delete_selected_schedule = delete_selected_schedule

def quick_add_schedule(self):
    """Quick add schedule from dashboard"""
    self.notebook.select(1)  # Switch to schedules tab
    self.show_add_schedule_dialog()

ModuleSchedulingGUI.quick_add_schedule = quick_add_schedule

def view_module_schedule(self, module_code=None):
    """View schedule for a specific module"""
    if not module_code:
        # Show dialog to select module
        module_code = self._select_module_dialog()
        if not module_code:
            return

    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
        SELECT ms.day_of_week, ms.start_time, ms.end_time,
               r.building, r.room_number,
               i.first_name, i.last_name,
               ms.session_type
        FROM module_schedule ms
        LEFT JOIN rooms r ON ms.room_id = r.id
        LEFT JOIN instructors i ON ms.instructor_id = i.id
        WHERE ms.module_code = ?
        ORDER BY ms.day_of_week, ms.start_time
        ''', (module_code,))

        schedules = cursor.fetchall()

    if not schedules:
        messagebox.showinfo("No Schedule", f"No schedule found for module {module_code}", parent=self.root)
        return

    # Create dialog to show schedule
    dialog = tk.Toplevel(self.root)
    dialog.title(f"Schedule for Module {module_code}")
    dialog.geometry("900x400")
    dialog.transient(self.root)

    # Create treeview
    columns = ('Day', 'Time', 'Room', 'Instructor', 'Type')
    tree = ttk.Treeview(dialog, columns=columns, show='headings')

    for col in columns:
        tree.heading(col, text=col)

    tree.column('Day', width=120)
    tree.column('Time', width=140)
    tree.column('Room', width=150)
    tree.column('Instructor', width=200)
    tree.column('Type', width=120)

    for schedule in schedules:
        day, start, end, building, room, first, last, session_type = schedule
        time_str = f"{start} - {end}"
        room_str = f"{building}-{room}" if building and room else "TBA"
        instructor = f"{first} {last}" if first and last else "TBA"
        tree.insert('', tk.END, values=(day, time_str, room_str, instructor, session_type))

    tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Buttons
    btn_frame = ttk.Frame(dialog)
    btn_frame.pack(fill=tk.X, padx=10, pady=5)

    ttk.Button(btn_frame, text="Close", command=dialog.destroy).pack(side=tk.RIGHT)

ModuleSchedulingGUI.view_module_schedule = view_module_schedule


def _resolve_changed_by(self):
    """Best-effort current-user lookup for schedule_history's changed_by."""
    try:
        if hasattr(self, "auth") and self.auth:
            user = getattr(self.auth, "current_user", None)
            if isinstance(user, dict):
                return str(user.get("username") or user.get("user_id") or "gui")
            if user and hasattr(user, "username"):
                return str(user.username)
    except Exception:
        pass
    return "gui"


ModuleSchedulingGUI._resolve_changed_by = _resolve_changed_by


def _publish_selected_schedule(self):
    """Promote one or many selected draft rows to status='published'.

    Uses the service-layer update path so schedule_history records the
    state change and notifications fire (since publishing is meaningful
    to students).
    """
    selected = self.schedules_tree.selection()
    if not selected:
        messagebox.showwarning("No selection",
                               "Select one or more draft schedules to publish.",
                               parent=self.root)
        return

    rows = []
    for iid in selected:
        vals = self.schedules_tree.item(iid).get("values") or []
        if len(vals) >= 10:
            sched_id = vals[0]
            status = vals[9]
            rows.append((sched_id, status))
    drafts = [sid for sid, status in rows if status != "published"]
    if not drafts:
        messagebox.showinfo("Nothing to publish",
                            "All selected rows are already published.",
                            parent=self.root)
        return

    if not messagebox.askyesno("Publish",
                               f"Publish {len(drafts)} schedule(s)? "
                               "This will fire student notifications.",
                               parent=self.root):
        return

    changed_by = self._resolve_changed_by()
    published = 0
    failures = []
    for sid in drafts:
        try:
            ok = self.scheduler.update_module_schedule(
                sid, status="published", changed_by=changed_by)
        except Exception as e:
            failures.append(f"{sid}: {e}")
            continue
        if ok:
            published += 1
        else:
            failures.append(str(sid))

    self.refresh_schedules()
    msg = f"Published {published} of {len(drafts)} draft(s)."
    if failures:
        msg += f"\nFailures: {', '.join(failures)}"
    messagebox.showinfo("Publish complete", msg, parent=self.root)


ModuleSchedulingGUI._publish_selected_schedule = _publish_selected_schedule


def _show_clone_term_dialog(self):
    """Open the what-if clone-term dialog."""
    try:
        from education_system.university_system.modules.domain.academics.gui.module_scheduling.clone_term_dialog import CloneTermDialog
        CloneTermDialog(self.root, self.scheduler, gui=self)
    except Exception as e:
        messagebox.showerror("Error",
                             f"Failed to open clone-term dialog: {e}",
                             parent=self.root)


ModuleSchedulingGUI._show_clone_term_dialog = _show_clone_term_dialog


def _ensure_saved_views_table(self, cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS module_scheduling_saved_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            criteria_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(user_id, name)
        )
    """)


ModuleSchedulingGUI._ensure_saved_views_table = _ensure_saved_views_table


def _refresh_saved_views(self):
    """Populate the saved-view combo with this user's saved view names."""
    user = self._resolve_changed_by()
    try:
        from education_system.university_system.infrastructure.database.db import sqlite3
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()
            self._ensure_saved_views_table(cursor)
            cursor.execute(
                "SELECT name FROM module_scheduling_saved_views "
                "WHERE user_id = ? ORDER BY name", (user,))
            names = [r[0] for r in cursor.fetchall()]
    except Exception:
        names = []
    self.saved_view_combo["values"] = names
    if not names:
        self.saved_view_var.set("")


ModuleSchedulingGUI._refresh_saved_views = _refresh_saved_views


def _save_current_view(self):
    """Snapshot the current filter combos as a named view."""
    from tkinter import simpledialog
    import json
    name = simpledialog.askstring("Save view",
                                  "Name for this view:",
                                  parent=self.root)
    if not name or not name.strip():
        return
    name = name.strip()
    criteria = {
        "semester": self.schedule_semester_var.get(),
        "year": self.schedule_year_var.get(),
        "status": self.schedule_status_var.get(),
        "search": self.schedule_search_var.get(),
    }
    user = self._resolve_changed_by()
    from datetime import datetime as _dt
    try:
        from education_system.university_system.infrastructure.database.db import sqlite3
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()
            self._ensure_saved_views_table(cursor)
            cursor.execute("""
                INSERT INTO module_scheduling_saved_views
                (user_id, name, criteria_json, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, name) DO UPDATE
                    SET criteria_json = excluded.criteria_json,
                        created_at    = excluded.created_at
            """, (user, name, json.dumps(criteria),
                  _dt.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to save view: {e}",
                             parent=self.root)
        return
    self._refresh_saved_views()
    self.saved_view_var.set(name)


ModuleSchedulingGUI._save_current_view = _save_current_view


def _apply_saved_view(self):
    """Load the selected saved view back into the filter combos + refresh."""
    import json
    name = (self.saved_view_var.get() or "").strip()
    if not name:
        messagebox.showinfo("Saved views",
                            "Pick a saved view from the dropdown first.",
                            parent=self.root)
        return
    user = self._resolve_changed_by()
    try:
        from education_system.university_system.infrastructure.database.db import sqlite3
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()
            self._ensure_saved_views_table(cursor)
            cursor.execute(
                "SELECT criteria_json FROM module_scheduling_saved_views "
                "WHERE user_id = ? AND name = ?", (user, name))
            row = cursor.fetchone()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load view: {e}",
                             parent=self.root)
        return
    if not row:
        messagebox.showwarning("Not found",
                               f"Saved view '{name}' no longer exists.",
                               parent=self.root)
        self._refresh_saved_views()
        return
    try:
        criteria = json.loads(row[0])
    except Exception as e:
        messagebox.showerror("Error", f"View data is corrupt: {e}",
                             parent=self.root)
        return
    self.schedule_semester_var.set(criteria.get("semester", "(all)"))
    self.schedule_year_var.set(criteria.get("year", "(all)"))
    self.schedule_status_var.set(criteria.get("status", "(all)"))
    self.schedule_search_var.set(criteria.get("search", ""))
    self.filter_schedules()


ModuleSchedulingGUI._apply_saved_view = _apply_saved_view


def _delete_saved_view(self):
    name = (self.saved_view_var.get() or "").strip()
    if not name:
        return
    if not messagebox.askyesno("Confirm",
                               f"Delete saved view '{name}'?",
                               parent=self.root):
        return
    user = self._resolve_changed_by()
    try:
        from education_system.university_system.infrastructure.database.db import sqlite3
        with get_connection(str(DEFAULT_DB_PATH), row_factory=False) as conn:
            cursor = conn.cursor()
            self._ensure_saved_views_table(cursor)
            cursor.execute(
                "DELETE FROM module_scheduling_saved_views "
                "WHERE user_id = ? AND name = ?", (user, name))
            conn.commit()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to delete view: {e}",
                             parent=self.root)
        return
    self._refresh_saved_views()


ModuleSchedulingGUI._delete_saved_view = _delete_saved_view


def _show_bulk_actions_dialog(self):
    """Open the bulk-actions dialog scoped to the multi-selected rows."""
    selected = self.schedules_tree.selection()
    if not selected:
        messagebox.showwarning("No selection",
                               "Select one or more schedules first "
                               "(Ctrl/Shift-click to multi-select).",
                               parent=self.root)
        return
    schedule_ids = []
    for iid in selected:
        vals = self.schedules_tree.item(iid).get("values") or []
        if vals:
            try:
                schedule_ids.append(int(vals[0]))
            except (TypeError, ValueError):
                pass
    if not schedule_ids:
        messagebox.showerror("Error", "Could not extract schedule IDs.",
                             parent=self.root)
        return
    try:
        from education_system.university_system.modules.domain.academics.gui.module_scheduling.bulk_actions_dialog import BulkActionsDialog
        BulkActionsDialog(self.root, self.scheduler, gui=self,
                          schedule_ids=schedule_ids)
    except Exception as e:
        messagebox.showerror("Error",
                             f"Failed to open bulk-actions dialog: {e}",
                             parent=self.root)


ModuleSchedulingGUI._show_bulk_actions_dialog = _show_bulk_actions_dialog

