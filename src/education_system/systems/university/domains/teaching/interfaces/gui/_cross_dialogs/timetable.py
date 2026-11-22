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
      * ``scope='room'``       + ``scope_id=10`` (sessions plus room bookings)

    Sessions are the *dated* ones for the week shown
    (``application/teaching/occurrences``): term dates, holidays, teaching
    weeks, the student's delivery and one-off cancellations / moves all apply.
    A cancelled session stays visible, greyed out.

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
    _CANCELLED_BG = "#eeeeee"
    _CANCELLED_FG = "#888888"
    _BOOKING_BG = "#d6e4f5"
    _BOOKING_FG = "#1f3a5f"
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
        self._unplaced = 0
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

        booking_rows = [r for r in lecture_rows if r.get("kind") == "booking"]
        lecture_rows = [r for r in lecture_rows if r.get("kind") != "booking"]
        cancelled = sum(1 for r in lecture_rows if r.get("status") == "cancelled")
        note = f"  ·  {self._unplaced} weekly slot(s) match no term" if self._unplaced else ""
        if not lecture_rows and not exam_rows and not booking_rows:
            self._status_var.set("No sessions this week." + note)
            return
        self._status_var.set(
            f"{len(lecture_rows) - cancelled} session(s)"
            + (f" · {cancelled} cancelled" if cancelled else "")
            + f" · {len(exam_rows)} exam(s)"
            + (f" · {len(booking_rows)} room booking(s)" if booking_rows else "") + note
        )

        # Conflict overlay — set of module codes that appear in
        # unresolved conflicts. Cell ribbons are rendered for these.
        try:
            from education_system.systems.university.domains.teaching.interfaces.gui._cross_services import (
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

        for row in booking_rows:
            self._draw_cell(row, kind="booking", conflict_codes=set())
        for row in lecture_rows:
            self._draw_cell(row, kind="lecture", conflict_codes=conflict_codes)
        for row in exam_rows:
            self._draw_cell(row, kind="exam", conflict_codes=conflict_codes)

    # ------------------------------------------------------------------ #

    def _load_rows(self) -> tuple[list[dict], list[dict]]:
        from datetime import timedelta as _td

        from education_system.systems.university.application.teaching import occurrences as tt
        from education_system.systems.university.infrastructure.database.db import get_connection
        week_from = self._week_start
        week_to = self._week_start + _td(days=6)
        exam_rows: list[dict] = []
        with get_connection() as conn:
            slot_list = self._slots_in_scope(conn, tt)
            self._unplaced = len(tt.unplaced(conn, slot_list))
            rows = tt.occurrences(conn, week_from, week_to, slot_list)
            if self._scope == "room":
                rows += [dict(kind="booking", date=str(b["start_datetime"])[:10],
                              start_time=str(b["start_datetime"])[11:16],
                              end_time=str(b["end_datetime"])[11:16],
                              module_code=b["booking_type"] or "booking",
                              room=b["purpose"] or "")
                         for b in tt.bookings(conn, self._scope_id, week_from, week_to)]
            if self._scope == "student":
                rows += self._office_hours(conn, week_from, week_to)
            modules = sorted({r["module_code"] for r in rows if r.get("kind") != "booking"})
            if self._scope == "module":
                modules = [str(self._scope_id)]
            if modules:
                placeholders = ",".join("?" for _ in modules)
                # Exams are bounded to the displayed week; drawing them in every
                # week made a single exam look like a weekly commitment.
                try:
                    # db-audit: ignore[DBW001] - only placeholders are interpolated
                    for r in conn.execute(
                        f"""
                        SELECT id, module_code, date, start_time, end_time, room
                        FROM exams
                        WHERE module_code IN ({placeholders})
                          AND date(date) BETWEEN date(?) AND date(?)
                        ORDER BY date, start_time
                        """,
                        modules + [week_from.isoformat(), week_to.isoformat()],
                    ).fetchall():
                        exam_rows.append(dict(r))
                except Exception:
                    logger.debug("Suppressed exception", exc_info=True)
        return rows, exam_rows

    def _office_hours(self, conn, week_from, week_to) -> list[dict]:
        """The student's office-hours appointments in the week shown."""
        try:
            from education_system.systems.university.application.teaching import office_hours
            rows = office_hours.bookings_for(conn, student_id=self._scope_id, include_past=True)
        except Exception:
            logger.debug("office hours unavailable for the grid", exc_info=True)
            return []
        return [dict(kind="booking", date=b["booking_date"],
                     start_time=b["slot_start"] or b["start_time"],
                     end_time=b["slot_end"] or b["end_time"],
                     module_code=f"Office hrs: {b['instructor_id']}",
                     room="Online" if b.get("mode") == "online" else b["location"])
                for b in rows if b["status"] == "confirmed"
                and week_from.isoformat() <= b["booking_date"] <= week_to.isoformat()]

    def _slots_in_scope(self, conn, tt) -> list[dict]:
        """The weekly slots behind this panel's target."""
        sid = self._scope_id
        if self._scope == "student":
            return tt.student_slots(conn, sid)
        if self._scope == "instructor":
            # Only this instructor's own sessions, not every session of the
            # modules they teach on.
            return tt.slots(conn, instructor_id=sid)
        if self._scope == "room":
            return tt.slots(conn, room_id=sid)
        if self._scope == "course":
            try:
                codes = [r[0] for r in conn.execute(
                    "SELECT module_code FROM modules WHERE course = ?", (str(sid),))]
            except Exception:
                return []
            return tt.slots(conn, module_codes=codes)
        return tt.slots(conn, module_codes=[str(sid)])

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
        if kind == "lecture" and not row.get("date"):
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

        status = row.get("status")
        bg, fg = {"lecture": (self._LECTURE_BG, self._LECTURE_FG),
                  "exam": (self._EXAM_BG, self._EXAM_FG),
                  "booking": (self._BOOKING_BG, self._BOOKING_FG)}[kind]
        if status == "cancelled":
            bg, fg = self._CANCELLED_BG, self._CANCELLED_FG
        cell.configure(bg=bg)
        if (row.get("module_code") or "").lower() in conflict_codes:
            cell.configure(highlightthickness=2,
                           highlightbackground=self._CONFLICT_BORDER)

        prefix = {"exam": "EXAM ",
                  "booking": "BOOKED " if self._scope == "room" else ""}.get(kind, "")
        where = row.get("room") or ("Online" if row.get("online_url") else "")
        flag = {"cancelled": "\nCANCELLED", "moved": "\n(moved)"}.get(status, "")
        label = tk.Label(
            cell,
            text=f"{prefix}{row.get('module_code', '')}\n{where}{flag}",
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
