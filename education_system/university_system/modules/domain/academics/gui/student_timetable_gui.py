"""Student Timetable GUI.

Provides a Tkinter frame with a weekly grid view of a student's class
schedule, colour-coded by session type.  Falls back to a flat Treeview
list when the grid has no data to display.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging

from education_system.university_system.infrastructure.database.db import get_connection, sqlite3

# i18n with fallback
try:
    from education_system.university_system.core.i18n import get_text as _t
except ImportError:
    _t = lambda key, **kwargs: key

# Schedule constants -- prefer the canonical module, fall back to defaults
try:
    from education_system.university_system.modules.domain.academics.services.module_scheduling.constants import (
        DAYS_OF_WEEK,
        TIME_SLOTS,
    )
except ImportError:
    DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    TIME_SLOTS = [
        "09:00", "10:00", "11:00", "12:00", "13:00",
        "14:00", "15:00", "16:00", "17:00",
    ]

logger = logging.getLogger(__name__)

# Colour map for session types (bg, fg)
SESSION_COLOURS = {
    "Lecture":  ("#BBDEFB", "#0D47A1"),
    "Lab":      ("#C8E6C9", "#1B5E20"),
    "Tutorial": ("#FFE0B2", "#E65100"),
    "Seminar":  ("#E1BEE7", "#4A148C"),
    "Workshop": ("#FFECB3", "#F57F17"),
}
DEFAULT_CELL_BG = "#F5F5F5"
DEFAULT_CELL_FG = "#333333"


class StudentTimetableGUI:
    """Weekly timetable view for the currently logged-in student."""

    def __init__(self, parent_frame, auth_instance=None):
        self.parent = parent_frame
        self.auth = auth_instance
        self.student_id = self._resolve_student_id()
        self.schedule_rows = []  # raw DB rows
        self.exam_rows = []     # one-off exam bookings overlaid on the grid
        self._grid_cells = {}   # (day_index, slot_index) -> Label

        self._build_ui()
        self.refresh_data()

        # Live participation in the cross-GUI bus. Anything that changes
        # the underlying schedule, exams, enrolment, calendar, or term
        # filter triggers a redraw. Each click on a grid cell publishes
        # a soft selection so sibling GUIs can highlight the row.
        try:
            from education_system.university_system.modules.domain.academics.gui._event_bus import (
                subscribe_tk,
                EVENT_MODULE_SCHEDULE_CHANGED,
                EVENT_EXAM_CHANGED,
                EVENT_ENROLMENT_CHANGED,
                EVENT_CALENDAR_CHANGED,
                EVENT_TERM_CHANGED,
                EVENT_SELECTION_CHANGED,
            )

            host = self.parent

            def _on_change(**_payload):
                self.refresh_data()

            def _on_selection(**payload):
                # Soft pointer — highlight the matching row in the
                # fallback list if it's the module currently selected
                # elsewhere. Don't navigate away.
                target = payload.get("module_code")
                if not target or not hasattr(self, "tree"):
                    return
                try:
                    for iid in self.tree.get_children():
                        vals = self.tree.item(iid, "values")
                        if vals and len(vals) >= 3 and vals[2] == target:
                            self.tree.selection_set(iid)
                            self.tree.see(iid)
                            break
                except Exception:
                    pass

            for evt in (EVENT_MODULE_SCHEDULE_CHANGED, EVENT_EXAM_CHANGED,
                        EVENT_ENROLMENT_CHANGED, EVENT_CALENDAR_CHANGED,
                        EVENT_TERM_CHANGED):
                subscribe_tk(evt, host, _on_change)
            subscribe_tk(EVENT_SELECTION_CHANGED, host, _on_selection)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_student_id(self):
        """Extract student_id from the auth object."""
        if self.auth and getattr(self.auth, "current_user", None):
            user = self.auth.current_user
            return user.get("student_id") or user.get("username")
        return None

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Assemble the full interface inside parent_frame."""
        # Title
        ttk.Label(
            self.parent,
            text=_t("Weekly Timetable"),
            font=("Arial", 16, "bold"),
        ).pack(pady=(10, 5))

        # Container that holds either the grid or the list fallback
        self.view_container = ttk.Frame(self.parent)
        self.view_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 5))

        # Build both views inside the container; we show/hide as needed
        self._build_grid_view()
        self._build_list_view()

        # Buttons
        btn_frame = ttk.Frame(self.parent)
        btn_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        ttk.Button(
            btn_frame, text=_t("Refresh"), command=self.refresh_data
        ).pack(side=tk.LEFT, padx=5)

        # Status label
        self.status_lbl = ttk.Label(self.parent, text="", foreground="gray")
        self.status_lbl.pack(pady=(0, 5))

    # -- Grid view ---------------------------------------------------------

    def _build_grid_view(self):
        """Create a Label-based weekly grid (rows = time slots, cols = days)."""
        self.grid_frame = ttk.LabelFrame(
            self.view_container, text=_t("Schedule Grid"), padding=5
        )

        # Header row: day names
        tk.Label(
            self.grid_frame, text=_t("Time"), width=8,
            font=("Arial", 10, "bold"), relief=tk.RIDGE, bg="#E0E0E0",
        ).grid(row=0, column=0, sticky="nsew", padx=1, pady=1)

        for col_idx, day in enumerate(DAYS_OF_WEEK, start=1):
            tk.Label(
                self.grid_frame, text=day[:3], width=14,
                font=("Arial", 10, "bold"), relief=tk.RIDGE, bg="#E0E0E0",
            ).grid(row=0, column=col_idx, sticky="nsew", padx=1, pady=1)

        # Data cells
        for row_idx, slot in enumerate(TIME_SLOTS, start=1):
            tk.Label(
                self.grid_frame, text=slot, width=8,
                font=("Arial", 9, "bold"), relief=tk.RIDGE, bg="#EEEEEE",
            ).grid(row=row_idx, column=0, sticky="nsew", padx=1, pady=1)

            for col_idx, _day in enumerate(DAYS_OF_WEEK, start=1):
                cell = tk.Label(
                    self.grid_frame, text="", width=14, height=2,
                    relief=tk.RIDGE, bg=DEFAULT_CELL_BG, fg=DEFAULT_CELL_FG,
                    font=("Arial", 8), anchor="center", wraplength=110,
                )
                cell.grid(
                    row=row_idx, column=col_idx, sticky="nsew", padx=1, pady=1
                )
                self._grid_cells[(col_idx - 1, row_idx - 1)] = cell

        # Let columns stretch
        for c in range(len(DAYS_OF_WEEK) + 1):
            self.grid_frame.columnconfigure(c, weight=1)

    # -- List view (fallback) ----------------------------------------------

    def _build_list_view(self):
        """Treeview table used when the grid has no data."""
        self.list_frame = ttk.Frame(self.view_container)

        columns = ("day", "time", "module", "room", "instructor", "type")
        self.tree = ttk.Treeview(
            self.list_frame, columns=columns, show="headings", height=14
        )
        col_conf = {
            "day":        (_t("Day"), 90),
            "time":       (_t("Time"), 100),
            "module":     (_t("Module"), 120),
            "room":       (_t("Room"), 120),
            "instructor": (_t("Instructor"), 140),
            "type":       (_t("Type"), 90),
        }
        for col, (heading, width) in col_conf.items():
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=width, minwidth=50)

        vsb = ttk.Scrollbar(
            self.list_frame, orient=tk.VERTICAL, command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def refresh_data(self):
        """Reload timetable data from the database."""
        self._clear_grid()
        self.tree.delete(*self.tree.get_children())
        self.schedule_rows.clear()
        self.exam_rows = []
        self.status_lbl.config(text="")

        if not self.student_id:
            self._show_fallback_list()
            self.status_lbl.config(text=_t("No student ID available."))
            return

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Enrolled modules for the student
            # Status values in student_modules are inconsistent across rows
            # (mix of 'Enrolled' and 'enrolled') — match both.
            cursor.execute(
                "SELECT module_code FROM student_modules "
                "WHERE student_id = ? AND LOWER(status) = 'enrolled'",
                (self.student_id,),
            )
            enrolled = [row[0] for row in cursor.fetchall()]

            if not enrolled:
                conn.close()
                self._show_fallback_list()
                self.status_lbl.config(
                    text=_t("No enrolled modules found.")
                )
                return

            placeholders = ",".join("?" for _ in enrolled)
            cursor.execute(
                f"""
                SELECT ms.module_code, m.module_name,
                       ms.day_of_week, ms.start_time, ms.end_time,
                       r.building, r.room_number,
                       i.first_name, i.last_name,
                       ms.session_type
                FROM module_schedule ms
                LEFT JOIN rooms r ON ms.room_id = r.id
                LEFT JOIN instructors i ON ms.instructor_id = i.id
                LEFT JOIN modules m ON ms.module_code = m.module_code
                WHERE ms.module_code IN ({placeholders})
                ORDER BY ms.day_of_week, ms.start_time
                """,
                enrolled,
            )
            self.schedule_rows = cursor.fetchall()

            # Pull exam overlays for the same enrolled modules so the
            # student sees lectures + exams in one grid.
            try:
                cursor.execute(
                    f"""
                    SELECT module_code, date, start_time, end_time, room
                    FROM exams WHERE module_code IN ({placeholders})
                    """,
                    enrolled,
                )
                self.exam_rows = cursor.fetchall()
            except Exception:
                self.exam_rows = []

            conn.close()

            if self.schedule_rows:
                self._populate_grid()
                self._populate_exam_overlay()
                self._populate_conflict_ribbons()
                self._show_grid()
            else:
                self._show_fallback_list()
                self.status_lbl.config(
                    text=_t("No schedule data found for enrolled modules.")
                )

        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc).lower():
                self.status_lbl.config(
                    text=_t("Timetable data not available")
                )
            else:
                logger.exception("Database error loading timetable")
                self.status_lbl.config(text=_t("Database error occurred."))
            self._show_fallback_list()
        except Exception:
            logger.exception("Unexpected error loading timetable")
            self.status_lbl.config(text=_t("An error occurred loading data."))
            self._show_fallback_list()

    # ------------------------------------------------------------------
    # Grid population
    # ------------------------------------------------------------------

    def _populate_grid(self):
        """Fill the grid cells and the fallback list from schedule_rows."""
        day_index_map = {d: i for i, d in enumerate(DAYS_OF_WEEK)}

        for row in self.schedule_rows:
            (module_code, module_name, day, start, end,
             building, room_num, inst_first, inst_last, stype) = row

            room_str = ""
            if building and room_num:
                room_str = f"{building} {room_num}"
            elif room_num:
                room_str = str(room_num)

            instructor = ""
            if inst_first and inst_last:
                instructor = f"{inst_first} {inst_last}"

            # Grid cell
            d_idx = day_index_map.get(day)
            s_idx = self._slot_index(start)
            if d_idx is not None and s_idx is not None:
                cell = self._grid_cells.get((d_idx, s_idx))
                if cell:
                    cell_text = module_code
                    if room_str:
                        cell_text += f"\n{room_str}"
                    bg, fg = SESSION_COLOURS.get(
                        stype, (DEFAULT_CELL_BG, DEFAULT_CELL_FG)
                    )
                    cell.config(text=cell_text, bg=bg, fg=fg)
                    self._bind_cell_selection(cell, module_code)

            # Also insert into fallback list
            time_str = f"{start}-{end}" if start and end else (start or "")
            self.tree.insert("", tk.END, values=(
                day, time_str, module_code, room_str, instructor, stype or ""
            ))

    def _populate_exam_overlay(self):
        """Overlay one-off exams on top of the lecture grid in orange.

        Exams have specific dates rather than weekday recurrence; we
        derive the weekday from ``exams.date`` and tag the cell with
        ``EXAM …`` so the student spots the difference at a glance.
        """
        from datetime import datetime as _dt
        day_index_map = {d: i for i, d in enumerate(DAYS_OF_WEEK)}
        for row in self.exam_rows or []:
            try:
                module_code = row["module_code"] if hasattr(row, "keys") else row[0]
                date_str = row["date"] if hasattr(row, "keys") else row[1]
                start = row["start_time"] if hasattr(row, "keys") else row[2]
                room = row["room"] if hasattr(row, "keys") else row[4]
            except Exception:
                continue
            if not date_str or not start:
                continue
            try:
                day = _dt.strptime(date_str[:10], "%Y-%m-%d").strftime("%A")
            except Exception:
                continue
            d_idx = day_index_map.get(day)
            s_idx = self._slot_index(start)
            if d_idx is None or s_idx is None:
                continue
            cell = self._grid_cells.get((d_idx, s_idx))
            if not cell:
                continue
            existing = cell.cget("text")
            cell.config(
                text=f"EXAM {module_code}\n{room or ''}"
                     + (f"\n(also: {existing.splitlines()[0]})" if existing else ""),
                bg="#fde2c4", fg="#7a3e00",
            )
            self._bind_cell_selection(cell, module_code)

    def _populate_conflict_ribbons(self):
        """Outline cells whose module appears in unresolved conflicts."""
        try:
            from education_system.university_system.modules.domain.academics.gui._cross_services import (
                _all_conflicts,
            )
            descs = [(c.get("description") or "").lower()
                     for c in _all_conflicts()]
        except Exception:
            descs = []
        if not descs:
            return
        for cell in self._grid_cells.values():
            text = (cell.cget("text") or "").lower()
            if not text:
                continue
            for desc in descs:
                if any(tok and tok in desc
                       for tok in text.replace("\n", " ").split()):
                    try:
                        cell.config(
                            highlightthickness=2,
                            highlightbackground="#c0392b",
                        )
                    except Exception:
                        pass
                    break

    def _bind_cell_selection(self, cell, module_code):
        """Click a cell → publish soft selection so siblings highlight.

        Drag-and-drop a populated cell onto another cell → route the
        move through ``slot_writer.move_slot`` (#7). The bus broadcast
        and conflict re-check happen inside the writer; the timetable
        just refreshes on the resulting EVENT_MODULE_SCHEDULE_CHANGED.
        """
        if not module_code:
            return

        def _on_click(_event=None, mc=module_code):
            try:
                from education_system.university_system.modules.services.academic_state import (
                    set_current_selection,
                )
                set_current_selection(module_code=mc, source="student_timetable")
            except Exception:
                pass

        def _on_press(event=None, mc=module_code, src_cell=cell):
            self._drag_state = {
                "module_code": mc,
                "src_cell": src_cell,
                "x_root": event.x_root if event else 0,
                "y_root": event.y_root if event else 0,
            }

        def _on_release(event=None):
            state = getattr(self, "_drag_state", None)
            if not state:
                return
            try:
                target = self.parent.winfo_containing(event.x_root, event.y_root)
            except Exception:
                target = None
            self._drag_state = None
            if target is None or target is state["src_cell"]:
                return
            # Find which (day, slot) the target cell maps to.
            target_day_idx = target_slot_idx = None
            for (d, s), c in self._grid_cells.items():
                if c is target:
                    target_day_idx, target_slot_idx = d, s
                    break
            if target_day_idx is None:
                return
            try:
                from education_system.university_system.modules.domain.academics.services.module_scheduling.slot_writer import (
                    move_slot,
                )
                from education_system.university_system.infrastructure.database.db import (
                    get_connection,
                )
                # Resolve the schedule_id from the source module + a
                # current weekday/start_time guess by inspecting the
                # row that placed this cell.
                src_d = src_s = None
                for (d, s), c in self._grid_cells.items():
                    if c is state["src_cell"]:
                        src_d, src_s = d, s
                        break
                if src_d is None:
                    return
                src_day = DAYS_OF_WEEK[src_d]
                src_start = TIME_SLOTS[src_s]
                with get_connection() as conn:
                    row = conn.execute(
                        "SELECT id FROM module_schedule "
                        "WHERE module_code = ? AND day_of_week = ? "
                        "  AND start_time LIKE ? LIMIT 1",
                        (state["module_code"], src_day, f"{src_start}%"),
                    ).fetchone()
                if not row:
                    return
                new_day = DAYS_OF_WEEK[target_day_idx]
                new_start = TIME_SLOTS[target_slot_idx]
                # Preserve duration: assume 1h grid step.
                from datetime import datetime as _dt, timedelta as _td
                try:
                    new_end = (_dt.strptime(new_start, "%H:%M")
                               + _td(hours=1)).strftime("%H:%M")
                except Exception:
                    new_end = new_start
                result = move_slot(
                    int(row[0]),
                    new_day=new_day,
                    new_start_time=new_start,
                    new_end_time=new_end,
                    moved_by="timetable_drag",
                )
                if not result.get("ok"):
                    try:
                        from tkinter import messagebox
                        messagebox.showwarning(
                            "Move blocked",
                            result.get("reason") or "Schedule move was rejected.",
                        )
                    except Exception:
                        pass
            except Exception as exc:
                logger.warning("timetable drag move failed: %s", exc)

        try:
            cell.bind("<Button-1>", _on_click)
            cell.bind("<ButtonPress-1>", _on_press, add="+")
            cell.bind("<ButtonRelease-1>", _on_release, add="+")
        except Exception:
            pass

    def _slot_index(self, start_time):
        """Return the row index for a given start_time string, or None."""
        if not start_time:
            return None
        # Normalise to HH:MM
        normalised = start_time[:5] if len(start_time) >= 5 else start_time
        try:
            return TIME_SLOTS.index(normalised)
        except ValueError:
            return None

    def _clear_grid(self):
        """Reset every grid cell to the default empty state."""
        for cell in self._grid_cells.values():
            cell.config(text="", bg=DEFAULT_CELL_BG, fg=DEFAULT_CELL_FG)

    # ------------------------------------------------------------------
    # View switching
    # ------------------------------------------------------------------

    def _show_grid(self):
        """Display the grid view and hide the list."""
        self.list_frame.pack_forget()
        self.grid_frame.pack(fill=tk.BOTH, expand=True)

    def _show_fallback_list(self):
        """Display the list view and hide the grid."""
        self.grid_frame.pack_forget()
        self.list_frame.pack(fill=tk.BOTH, expand=True)
