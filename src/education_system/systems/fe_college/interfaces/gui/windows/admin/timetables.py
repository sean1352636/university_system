"""Admin timetabling — the weekly grid, and placing sessions into it.

The grid is the point of this screen: a text list of sessions tells you
nothing about whether Tuesday afternoon is empty. Clashes (teacher, room,
group and staff availability) are checked by the service before anything is
placed, so a clash is reported rather than created.
"""

from __future__ import annotations

import logging
import tkinter as tk
from tkinter import ttk

from education_system.systems.fe_college.config import ROOM_TYPES
from education_system.systems.fe_college.domain.facilities.rooms import (
    ROOM_STATUSES,
    Room,
)
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.domain.teaching.timetable import Session
from education_system.systems.fe_college.interfaces.gui import timetable_grid
from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "Timetable"

# How the grid is filtered: label -> (service call name, picker source).
VIEWS = ("Whole college", "By course", "By staff", "By room")


def open_window(host) -> None:
    Screen(host)


class Screen:
    def __init__(self, host):
        self.host = host
        self.ctl = host.ctl
        host.clear_content()
        parent = host.content_frame

        w.page_header(
            parent, TITLE,
            "The weekly teaching grid. Clashes are checked against the "
            "teacher, the room, the group and staff availability.",
            actions=[
                ("+ Add session", self.add_session),
                ("Rooms", self.manage_rooms),
                ("↻ Refresh", self.refresh),
            ],
        )

        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 8))
        ttk.Label(bar, text="View:").pack(side="left")
        self.view_var = tk.StringVar(value=VIEWS[0])
        view_combo = ttk.Combobox(bar, textvariable=self.view_var, values=list(VIEWS),
                                  state="readonly", width=16)
        view_combo.pack(side="left", padx=(4, 12))
        view_combo.bind("<<ComboboxSelected>>", lambda _e: self._on_view_change())

        ttk.Label(bar, text="Subject:").pack(side="left")
        self.target_var = tk.StringVar()
        self.target_combo = ttk.Combobox(bar, textvariable=self.target_var,
                                         state="readonly", width=42)
        self.target_combo.pack(side="left", padx=(4, 12))
        self.target_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh())

        self.summary_var = tk.StringVar()
        ttk.Label(bar, textvariable=self.summary_var,
                  foreground=w.TONE["muted"]).pack(side="right")

        self.grid_holder = ttk.Frame(parent)
        self.grid_holder.pack(fill="both", expand=True)

        w.button_bar(parent, [
            ("Move session", self.move_session),
            ("Remove session", self.remove_session),
            ("Find a free room", self.find_room),
        ])

        self.selected_session: Session | None = None
        self._on_view_change()

    # ── View selection ─────────────────────────────────────────────────────

    def _on_view_change(self) -> None:
        view = self.view_var.get()
        if view == "By course":
            options = [f"{c.course_id} — {c.title}" for c in self.ctl.courses.list_all()]
        elif view == "By staff":
            options = [
                f"{s.staff_id} — {s.full_name}" for s in self.ctl.staff.teaching_staff()
            ]
        elif view == "By room":
            options = [f"{r.room_id} — {r.name}" for r in self.ctl.timetable.rooms()]
        else:
            options = []

        self.target_combo.configure(values=options,
                                    state="readonly" if options else "disabled")
        if options:
            self.target_combo.current(0)
        else:
            self.target_var.set("")
        self.refresh()

    def _current_key(self) -> str:
        raw = self.target_var.get()
        return raw.split(" — ")[0] if raw else ""

    # ── Grid ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        view, key = self.view_var.get(), self._current_key()
        try:
            if view == "By course" and key:
                timetable = self.ctl.timetable.for_course(key)
            elif view == "By staff" and key:
                timetable = self.ctl.timetable.for_staff(key)
            elif view == "By room" and key:
                timetable = self.ctl.timetable.for_room(key)
            else:
                timetable = self.ctl.timetable.whole_college()
        except Exception as exc:
            logger.exception("Could not build the FE College timetable")
            w.error(self.host, TITLE, f"Could not load the timetable: {exc}")
            return

        self.summary_var.set(
            f"{timetable.total_sessions} session(s) · {timetable.hours:g} hours/week"
        )
        self._draw(timetable)
        self.host.set_status(f"{timetable.title}: {timetable.total_sessions} session(s)")

    def _draw(self, timetable) -> None:
        w.clear(self.grid_holder)
        timetable_grid.render(
            self.grid_holder, timetable, self.ctl, on_click=self._select,
        )

    def _select(self, session: Session) -> None:
        self.selected_session = session
        self.host.set_status(
            f"Selected: {session.course_id} {session.label} "
            f"(teacher {session.teacher_id or '—'}, room {session.room_id or '—'})"
        )

    # ── Actions ────────────────────────────────────────────────────────────

    def add_session(self) -> None:
        courses = self.ctl.courses.list_all()
        if not courses:
            w.info(self.host, "Add session", "Create a course first.")
            return
        teachers = [""] + [
            f"{s.staff_id} — {s.full_name}" for s in self.ctl.staff.teaching_staff()
        ]
        rooms = [""] + [f"{r.room_id} — {r.name}" for r in self.ctl.timetable.rooms()]
        groups = [""] + [g.group_id for g in self.ctl.courses.groups()]

        result = w.ask(self.host, "Add timetabled session", [
            ("course", "Course", "choice",
             [f"{c.course_id} — {c.title}" for c in courses]),
            ("group", "Class group", "choice", groups),
            ("teacher", "Teacher", "choice", teachers),
            ("room", "Room", "choice", rooms),
            ("day", "Day", "choice", list(self.ctl.timetable.days()[:6])),
            ("period", "Period", "choice", list(self.ctl.timetable.period_codes())),
            ("unit_id", "Unit (optional)", "text"),
            ("force", "Place even if it clashes", "bool"),
        ])
        if result is None:
            return

        session = Session(
            session_id=None,
            course_id=result["course"].split(" — ")[0],
            group_id=result["group"],
            teacher_id=result["teacher"].split(" — ")[0] if result["teacher"] else "",
            room_id=result["room"].split(" — ")[0] if result["room"] else "",
            day=result["day"],
            period=result["period"],
            academic_year=self.ctl.academic_year,
            unit_id=result["unit_id"],
        )
        try:
            self.ctl.timetable.place(session, force=result["force"])
        except ValidationError as exc:
            w.error(self.host, "Clash", f"That session could not be placed:\n\n{exc}")
            return
        self.refresh()

    def move_session(self) -> None:
        if self.selected_session is None:
            w.info(self.host, "Move session", "Click a session in the grid first.")
            return
        session = self.selected_session
        result = w.ask(self.host, f"Move {session.course_id} {session.label}", [
            ("day", "New day", "choice", list(self.ctl.timetable.days()[:6])),
            ("period", "New period", "choice", list(self.ctl.timetable.period_codes())),
            ("force", "Move even if it clashes", "bool"),
        ], initial={"day": session.day, "period": session.period})
        if result is None:
            return
        try:
            self.ctl.timetable.move(
                session.session_id, result["day"], result["period"],
                force=result["force"],
            )
        except ValidationError as exc:
            w.error(self.host, "Clash", f"That move would clash:\n\n{exc}")
            return
        self.selected_session = None
        self.refresh()

    def remove_session(self) -> None:
        if self.selected_session is None:
            w.info(self.host, "Remove session", "Click a session in the grid first.")
            return
        session = self.selected_session
        if not w.confirm(self.host, "Remove session",
                         f"Remove {session.course_id} from {session.label}?"):
            return
        self.ctl.timetable.remove(session.session_id)
        self.selected_session = None
        self.refresh()

    def find_room(self) -> None:
        result = w.ask(self.host, "Find a free room", [
            ("day", "Day", "choice", list(self.ctl.timetable.days()[:6])),
            ("period", "Period", "choice", list(self.ctl.timetable.period_codes())),
            ("min_capacity", "Minimum capacity", "int"),
            ("room_type", "Room type", "choice", ["", *ROOM_TYPES]),
        ])
        if result is None:
            return
        free = self.ctl.timetable.free_rooms(
            result["day"], result["period"],
            min_capacity=result["min_capacity"],
            room_type=result["room_type"] or None,
        )
        if not free:
            w.info(self.host, "No free rooms",
                   f"Nothing matches in {result['day']} {result['period']}.")
            return
        w.show_text(
            self.host, "Free rooms",
            f"Free in {result['day']} {result['period']}:\n\n"
            + "\n".join(f"  {r.display_name}" for r in free),
            height=min(24, len(free) + 4),
        )

    def manage_rooms(self) -> None:
        RoomsWindow(self.host)


class RoomsWindow:
    """Room list in its own window — estates data, not timetabling."""

    def __init__(self, host):
        self.host = host
        self.ctl = host.ctl
        master = host.root
        self.win = tk.Toplevel(master)
        self.win.title("Rooms")
        self.win.geometry("900x520")
        self.win.transient(master)

        frame = ttk.Frame(self.win, padding=12)
        frame.pack(fill="both", expand=True)
        w.page_header(frame, "Rooms", "Teaching spaces available to timetable.",
                      actions=[("+ New room", self.new)])

        self.table = w.DataTable(frame, [
            ("id", "Code", 80),
            ("name", "Name", 200),
            ("type", "Type", 130),
            ("capacity", "Capacity", 80, "e"),
            ("building", "Building", 110),
            ("status", "Status", 110),
            ("access", "Accessible", 90),
        ], on_double_click=lambda _r: self.edit())
        w.button_bar(frame, [("Edit", self.edit), ("Delete", self.delete),
                             ("Close", self.win.destroy)])
        self.refresh()

    def refresh(self) -> None:
        rooms = self.ctl.timetable.rooms()
        self.table.set_rows([
            {
                "id": r.room_id,
                "name": r.name,
                "type": r.room_type,
                "capacity": r.capacity,
                "building": r.building or "—",
                "status": r.status,
                "access": w.yes_no(r.is_accessible),
                "_tone": "muted" if not r.is_bookable else "plain",
                "_obj": r,
            }
            for r in rooms
        ])

    def _form(self, room: Room | None):
        return w.ask(
            self.win, "Room" if room is None else f"Edit {room.room_id}", [
                ("room_id", "Code", "text"),
                ("name", "Name", "text"),
                ("room_type", "Type", "choice", ROOM_TYPES),
                ("capacity", "Capacity", "int"),
                ("building", "Building", "text"),
                ("floor", "Floor", "text"),
                ("campus", "Campus", "text"),
                ("status", "Status", "choice", ROOM_STATUSES),
                ("has_projector", "Has a projector", "bool"),
                ("is_accessible", "Step-free access", "bool"),
                ("notes", "Notes", "multiline"),
            ],
            initial={
                "room_id": room.room_id if room else "",
                "name": room.name if room else "",
                "room_type": room.room_type if room else ROOM_TYPES[0],
                "capacity": room.capacity if room else 24,
                "building": room.building if room else "",
                "floor": room.floor if room else "",
                "campus": room.campus if room else "Main Campus",
                "status": room.status if room else "available",
                "has_projector": room.has_projector if room else True,
                "is_accessible": room.is_accessible if room else True,
                "notes": room.notes if room else "",
            },
        )

    def new(self) -> None:
        result = self._form(None)
        if result is None:
            return
        try:
            self.ctl.timetable.save_room(Room(**result))
        except ValidationError as exc:
            w.error(self.win, "Room", str(exc))
            return
        self.refresh()

    def edit(self) -> None:
        room = self.table.require_selection("a room")
        if room is None:
            return
        result = self._form(room)
        if result is None:
            return
        try:
            self.ctl.timetable.save_room(Room(**result))
        except ValidationError as exc:
            w.error(self.win, "Room", str(exc))
            return
        self.refresh()

    def delete(self) -> None:
        room = self.table.require_selection("a room")
        if room is None:
            return
        if not w.confirm(self.win, "Delete room",
                         f"Delete {room.display_name}?\n\n"
                         "Sessions booked into it keep running but lose the room."):
            return
        self.ctl.timetable.delete_room(room.room_id)
        self.refresh()


__all__ = ["TITLE", "RoomsWindow", "Screen", "open_window"]
