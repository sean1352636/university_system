"""The weekly timetable grid and its layout constants."""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

from education_system.systems.university.infrastructure.i18n import get_text as _t

import tkinter as tk
from tkinter import ttk
from typing import Any


_WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
_DEFAULT_TIME_SLOTS = (
    "09:00", "10:00", "11:00", "12:00", "13:00",
    "14:00", "15:00", "16:00", "17:00",
)


class WeeklyGridPanel(ttk.Frame):
    """Embeddable weekly timetable grid.

    Single read-side widget for *every* timetable surface — the
    Student Timetable, the per-module detail in Module Scheduling,
    the per-course detail in Course Management, and the per-instructor
    drill-down. The host picks a ``scope`` and the panel queries the
    right slice; the rendering and refresh wiring is identical.

    Scopes:
      * ``scope='module'``     + ``scope_id='CS101'``
      * ``scope='course'``     + ``scope_id='CS-BSC'``
      * ``scope='instructor'`` + ``scope_id=42``
      * ``scope='student'``    + ``scope_id='S12345'``

    Auto-refreshes on ``module.schedule.changed`` / ``exam.changed`` /
    ``enrolment.changed`` / ``calendar.changed`` / ``term.changed``.

    Cells are click-aware: clicking publishes a soft
    ``selection.changed`` so sibling GUIs can highlight the row.
    Cells with an unresolved schedule conflict get a red ribbon.
    Exams are overlaid in orange so you can see lectures + exams in
    a single view.
    """

    _LECTURE_BG = "#d4edda"
    _LECTURE_FG = "#155724"
    _EXAM_BG = "#fde2c4"
    _EXAM_FG = "#7a3e00"
    _CONFLICT_BORDER = "#c0392b"
    _EMPTY_BG = "#ffffff"

    def __init__(self, master: tk.Misc, *,
                 scope: str = "module",
                 scope_id: Any = None,
                 week_start: Any = None,
                 listen_to_events: bool = True) -> None:
        super().__init__(master)
        self._scope = scope
        self._scope_id = scope_id
        # Which concrete week this grid represents. Lecture slots recur weekly
        # so they render the same whatever the week; exams do not — an exam has
        # a single date, and drawing it in every week (which is what deriving a
        # weekday from its date used to do) tells the student they sit it over
        # and over. Only exams inside this week are drawn.
        self._week_start = self._monday_of(week_start)
        self._cells: dict[tuple[int, int], tk.Frame] = {}
        self._heading_var = tk.StringVar(value=_t('gui.academics.cross_dialogs.values.weekly_timetable', default="Weekly timetable"))

        ttk.Label(
            self, textvariable=self._heading_var,
            font=("Helvetica", 11, "bold"),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        self._grid_frame = ttk.Frame(self)
        self._grid_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._build_grid()

        self._status_var = tk.StringVar(value="")
        ttk.Label(
            self, textvariable=self._status_var, foreground="#7f8c8d",
        ).pack(anchor="w", padx=10, pady=(0, 6))

        if listen_to_events:
            try:
                from education_system.systems.university.infrastructure.event_bus import (
                    subscribe_tk,
                    EVENT_MODULE_SCHEDULE_CHANGED,
                    EVENT_EXAM_CHANGED,
                    EVENT_ENROLMENT_CHANGED,
                    EVENT_CALENDAR_CHANGED,
                    EVENT_TERM_CHANGED,
                )

                def _on_change(**_payload):
                    if self._scope_id is not None:
                        self.refresh()

                for evt in (EVENT_MODULE_SCHEDULE_CHANGED, EVENT_EXAM_CHANGED,
                            EVENT_ENROLMENT_CHANGED, EVENT_CALENDAR_CHANGED,
                            EVENT_TERM_CHANGED):
                    subscribe_tk(evt, self, _on_change)
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        if scope_id is not None:
            self.refresh()

    # ------------------------------------------------------------------ #

    def _build_grid(self) -> None:
        # Top-left corner.
        tk.Label(
            self._grid_frame, text=_t('gui.academics.cross_dialogs.labels.time', default="Time"), width=8,
            font=("Helvetica", 9, "bold"), bg="#4a90e2", fg="white",
            relief="ridge",
        ).grid(row=0, column=0, sticky="nsew", padx=1, pady=1)
        # Day headers.
        for c, day in enumerate(_WEEKDAYS, start=1):
            tk.Label(
                self._grid_frame, text=day[:3], width=14,
                font=("Helvetica", 9, "bold"), bg="#4a90e2", fg="white",
                relief="ridge",
            ).grid(row=0, column=c, sticky="nsew", padx=1, pady=1)
        # Time rows.
        for r, slot in enumerate(_DEFAULT_TIME_SLOTS, start=1):
            tk.Label(
                self._grid_frame, text=slot, width=8,
                font=("Helvetica", 9, "bold"), bg="#e8f4f8",
                relief="ridge",
            ).grid(row=r, column=0, sticky="nsew", padx=1, pady=1)
            for c in range(1, len(_WEEKDAYS) + 1):
                cell = tk.Frame(
                    self._grid_frame, bg=self._EMPTY_BG,
                    relief="ridge", borderwidth=1,
                    width=140, height=60,
                )
                cell.grid(row=r, column=c, sticky="nsew", padx=1, pady=1)
                cell.grid_propagate(False)
                self._cells[(c - 1, r - 1)] = cell

        for c in range(len(_WEEKDAYS) + 1):
            self._grid_frame.columnconfigure(c, weight=1)

    @staticmethod
    def _monday_of(value: Any = None):
        """Monday of the week containing *value* (today when None)."""
        from datetime import date as _date, datetime as _dt, timedelta as _td
        if value is None:
            day = _date.today()
        elif isinstance(value, _dt):
            day = value.date()
        elif isinstance(value, _date):
            day = value
        else:
            try:
                day = _dt.strptime(str(value)[:10], "%Y-%m-%d").date()
            except ValueError:
                day = _date.today()
        return day - _td(days=day.weekday())

    @property
    def week_start(self):
        """Monday of the week currently displayed."""
        return self._week_start

    def set_week(self, value: Any) -> None:
        """Show the week containing *value*."""
        self._week_start = self._monday_of(value)
        self.refresh()

    def shift_week(self, weeks: int) -> None:
        """Move the displayed week by *weeks* (negative goes back)."""
        from datetime import timedelta as _td
        self._week_start = self._week_start + _td(weeks=weeks)
        self.refresh()

    def set_target(self, *, scope: str, scope_id: Any) -> None:
        self._scope = scope
        self._scope_id = scope_id
        self.refresh()

    def refresh(self) -> None:
        self._clear_cells()
        if self._scope_id is None:
            self._heading_var.set("Weekly timetable")
            self._status_var.set("No target selected.")
            return
        from datetime import timedelta as _td
        week_end = self._week_start + _td(days=4)
        self._heading_var.set(
            f"Weekly timetable — {self._scope}: {self._scope_id}"
            f"   (week of {self._week_start:%d %b %Y} – {week_end:%d %b})"
        )

        try:
            lecture_rows, exam_rows = self._load_rows()
        except Exception as exc:
            self._status_var.set(f"(load failed: {exc})")
            return

        if not lecture_rows and not exam_rows:
            self._status_var.set("No scheduled sessions.")
            return
        self._status_var.set(
            f"{len(lecture_rows)} lecture slots · {len(exam_rows)} exam(s)"
        )

        # Conflict overlay — set of module codes that appear in
        # unresolved conflicts. Cell ribbons are rendered for these.
        try:
            from education_system.systems.university.domains.academics.interfaces.gui._cross_services import (
                _all_conflicts,
            )
            conflict_codes = set()
            for c in _all_conflicts():
                desc = (c.get("description") or "").lower()
                for code in {r["module_code"].lower() for r in lecture_rows
                             if r.get("module_code")}:
                    if code in desc:
                        conflict_codes.add(code)
        except Exception:
            conflict_codes = set()

        for row in lecture_rows:
            self._draw_cell(row, kind="lecture", conflict_codes=conflict_codes)
        for row in exam_rows:
            self._draw_cell(row, kind="exam", conflict_codes=conflict_codes)

    # ------------------------------------------------------------------ #

    def _load_rows(self) -> tuple[list[dict], list[dict]]:
        from education_system.systems.university.infrastructure.database.db import get_connection
        lecture_rows: list[dict] = []
        exam_rows: list[dict] = []
        with get_connection() as conn:
            modules = self._modules_in_scope(conn)
            if not modules:
                return [], []
            placeholders = ",".join("?" for _ in modules)

            # db-audit: ignore[DBW001] - string literal
            for r in conn.execute(
                f"""
                SELECT ms.id, ms.module_code, ms.day_of_week,
                       ms.start_time, ms.end_time,
                       COALESCE(ms.session_type, 'lecture') AS session_type,
                       COALESCE(r.building || ' ' || r.room_number, '') AS room
                FROM module_schedule ms
                LEFT JOIN rooms r ON ms.room_id = r.id
                WHERE ms.module_code IN ({placeholders})
                  -- Drafts are what-if rows (a term clone copies every
                  -- published slot as a draft for the next term); drawing
                  -- them put a second copy of the same session in the week.
                  AND COALESCE(ms.status, 'published') = 'published'
                ORDER BY ms.day_of_week, ms.start_time
                """,
                modules,
            ).fetchall():
                lecture_rows.append(dict(r))

            # Exams are bounded to the displayed week. Without this the grid
            # drew every exam on its weekday in *all* weeks, so a single exam
            # looked like a recurring weekly commitment.
            from datetime import timedelta as _td
            week_from = self._week_start.isoformat()
            week_to = (self._week_start + _td(days=6)).isoformat()
            try:
                # db-audit: ignore[DBW001] - string literal
                for r in conn.execute(
                    f"""
                    SELECT id, module_code, date, start_time, end_time, room
                    FROM exams
                    WHERE module_code IN ({placeholders})
                      AND date(date) BETWEEN date(?) AND date(?)
                    ORDER BY date, start_time
                    """,
                    modules + [week_from, week_to],
                ).fetchall():
                    exam_rows.append(dict(r))
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)
        return lecture_rows, exam_rows

    def _modules_in_scope(self, conn) -> list[str]:
        sid = self._scope_id
        if self._scope == "module":
            return [str(sid)]
        if self._scope == "course":
            try:
                rows = conn.execute(
                    "SELECT module_code FROM modules WHERE course = ?",
                    (str(sid),),
                ).fetchall()
                return [r[0] for r in rows]
            except Exception:
                return []
        if self._scope == "instructor":
            try:
                rows = conn.execute(
                    "SELECT DISTINCT module_code FROM module_schedule "
                    "WHERE instructor_id = ?",
                    (sid,),
                ).fetchall()
                return [r[0] for r in rows]
            except Exception:
                return []
        if self._scope == "student":
            try:
                rows = conn.execute(
                    "SELECT module_code FROM student_modules "
                    "WHERE student_id = ? AND LOWER(status) = 'enrolled'",
                    (str(sid),),
                ).fetchall()
                return [r[0] for r in rows]
            except Exception:
                return []
        return []

    # ------------------------------------------------------------------ #

    def _clear_cells(self) -> None:
        for cell in self._cells.values():
            cell.configure(bg=self._EMPTY_BG, highlightthickness=0)
            for child in cell.winfo_children():
                child.destroy()

    def _slot_index(self, t: str) -> int | None:
        if not t or len(t) < 5:
            return None
        head = t[:5]
        try:
            return _DEFAULT_TIME_SLOTS.index(head)
        except ValueError:
            # Map to the nearest hour bucket.
            try:
                hour = int(t[:2])
                for i, slot in enumerate(_DEFAULT_TIME_SLOTS):
                    if int(slot[:2]) == hour:
                        return i
            except Exception:
                return None
        return None

    def _day_index(self, day: str) -> int | None:
        if not day:
            return None
        for i, d in enumerate(_WEEKDAYS):
            if day.strip().lower().startswith(d[:3].lower()):
                return i
        return None

    def _draw_cell(self, row: dict, *, kind: str,
                   conflict_codes: set[str]) -> None:
        if kind == "lecture":
            d_idx = self._day_index(row.get("day_of_week", ""))
        else:
            try:
                from datetime import datetime as _dt
                day_name = _dt.strptime(
                    (row.get("date") or "")[:10], "%Y-%m-%d"
                ).strftime("%A")
                d_idx = self._day_index(day_name)
            except Exception:
                d_idx = None
        s_idx = self._slot_index(row.get("start_time") or "")
        if d_idx is None or s_idx is None:
            return
        cell = self._cells.get((d_idx, s_idx))
        if cell is None:
            return

        bg, fg = (self._LECTURE_BG, self._LECTURE_FG) if kind == "lecture" \
            else (self._EXAM_BG, self._EXAM_FG)
        cell.configure(bg=bg)
        if (row.get("module_code") or "").lower() in conflict_codes:
            cell.configure(highlightthickness=2,
                           highlightbackground=self._CONFLICT_BORDER)

        prefix = "EXAM " if kind == "exam" else ""
        label = tk.Label(
            cell,
            text=f"{prefix}{row.get('module_code', '')}\n{row.get('room') or ''}",
            bg=bg, fg=fg, font=("Helvetica", 8, "bold"),
            wraplength=130, anchor="center", justify="center",
        )
        label.pack(fill="both", expand=True, padx=2, pady=2)

        # Click → soft selection broadcast.
        module_code = row.get("module_code")
        kind_local = kind

        def _on_click(_event=None, mc=module_code, k=kind_local):
            try:
                from education_system.systems.university.services.bus.academic_state import (
                    set_current_selection,
                )
                set_current_selection(module_code=mc, source=f"timetable_{k}")
            except Exception:
                logger.debug("Suppressed exception", exc_info=True)

        for w in (cell, label):
            w.bind("<Button-1>", _on_click)


__all__ = [
    "WeeklyGridPanel",
]
