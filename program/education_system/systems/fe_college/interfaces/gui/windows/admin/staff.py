"""Admin staff directory — who works here, and how loaded they are.

The workload columns are the reason this screen exists rather than being a
plain contact list: a curriculum manager comes here to see who is over- or
under-allocated before assigning the next class.
"""

from __future__ import annotations

import logging
from datetime import date
from tkinter import ttk

from education_system.systems.fe_college.config import (
    EMPLOYMENT_STATUSES,
    STAFF_ROLES,
)
from education_system.systems.fe_college.domain.staff.models import Staff
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.interfaces.gui import widgets as w

logger = logging.getLogger(__name__)

TITLE = "Staff"


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
            "Directory, teaching workload and availability.",
            actions=[
                ("+ New staff member", self.new),
                ("Workload report", lambda: host.open_screen("reports", report="workload")),
                ("↻ Refresh", self.refresh),
            ],
        )

        self.filters = w.FilterBar(
            parent, self.refresh,
            search_label="Name / ID / email",
            filters=[
                ("role", "Role", STAFF_ROLES),
                ("department", "Department", self.ctl.staff.departments()),
                ("employment_status", "Contract", EMPLOYMENT_STATUSES),
            ],
        )

        self.table = w.DataTable(parent, [
            ("id", "ID", 85),
            ("name", "Name", 180),
            ("role", "Role", 165),
            ("department", "Department", 190),
            ("contract", "Contract", 90),
            ("contracted", "Contracted", 85, "e"),
            ("assigned", "Assigned", 80, "e"),
            ("band", "Load", 115),
            ("email", "Email", 220),
        ], on_double_click=lambda _s: self.view())

        w.button_bar(parent, [
            ("View", self.view),
            ("Edit", self.edit),
            ("Availability", self.availability),
            ("Mark leaver", self.mark_leaver),
            ("Delete", self.delete),
        ])
        self.refresh()

    # ── Data ───────────────────────────────────────────────────────────────

    def refresh(self) -> None:
        try:
            staff = self.ctl.staff.search(
                query=self.filters.query, **self.filters.values()
            )
            loads = {wl.staff_id: wl for wl in self.ctl.staff.workloads()}
        except Exception as exc:
            logger.exception("Could not list FE College staff")
            w.error(self.host, TITLE, f"Could not load staff: {exc}")
            return

        rows = []
        for member in staff:
            load = loads.get(member.staff_id)
            band = load.band if load else "—"
            rows.append({
                "id": member.staff_id,
                "name": member.full_name,
                "role": member.role,
                "department": member.department or "—",
                "contract": member.employment_status,
                "contracted": f"{member.contracted_hours:g}h",
                "assigned": f"{load.assigned_hours:g}h" if load else "—",
                "band": band,
                "email": member.email,
                "_tone": (
                    "muted" if not member.is_active
                    else w.tone_for(band) if load else "plain"
                ),
                "_obj": member,
            })
        self.table.set_rows(rows)
        self.filters.set_count(len(rows), "staff member")
        self.host.set_status(f"{len(rows)} staff member(s)")

    # ── Actions ────────────────────────────────────────────────────────────

    def view(self) -> None:
        member = self.table.require_selection("a staff member")
        if member is None:
            return
        profile = self.ctl.staff.profile(member.staff_id)
        if profile is None:
            self.refresh()
            return
        w.show_text(self.host, member.display_name, _profile_text(profile))

    def new(self) -> None:
        result = w.ask(
            self.host, "New staff member", _fields(self.ctl),
            initial={
                "staff_id": self.ctl.staff.next_reference(),
                "role": "Lecturer",
                "employment_status": "Full-time",
                "contracted_hours": 24,
                "start_date": date.today().isoformat(),
            },
            submit_label="Create",
        )
        if result is None:
            return
        try:
            self.ctl.staff.create(_to_staff(result))
        except ValidationError as exc:
            w.error(self.host, "New staff member", str(exc))
            return
        self.refresh()

    def edit(self) -> None:
        member = self.table.require_selection("a staff member")
        if member is None:
            return
        result = w.ask(
            self.host, f"Edit {member.display_name}", _fields(self.ctl),
            initial=_from_staff(member), submit_label="Save",
        )
        if result is None:
            return
        try:
            self.ctl.staff.update(_to_staff(result))
        except ValidationError as exc:
            w.error(self.host, "Edit staff member", str(exc))
            return
        self.refresh()

    def availability(self) -> None:
        """Edit which days a member of staff cannot be timetabled."""
        member = self.table.require_selection("a staff member")
        if member is None:
            return
        current = self.ctl.staff.availability(member.staff_id)
        days = self.ctl.timetable.days()[:5]
        blocked_days = {
            day for day in days
            if all(not current.is_free(day, p) for p in self.ctl.timetable.period_codes())
        }
        result = w.ask(
            self.host, f"Availability — {member.full_name}",
            [(day, f"{day} unavailable", "bool") for day in days],
            initial={day: day in blocked_days for day in days},
            submit_label="Save",
        )
        if result is None:
            return

        blocked = [
            (day, period)
            for day in days if result.get(day)
            for period in self.ctl.timetable.period_codes()
        ]
        try:
            self.ctl.staff.set_availability(
                member.staff_id, blocked, reason="Not contracted"
            )
        except ValidationError as exc:
            w.error(self.host, "Availability", str(exc))
            return
        self.host.set_status(
            f"{member.full_name} unavailable on "
            + (", ".join(d for d in days if result.get(d)) or "no days")
        )

    def mark_leaver(self) -> None:
        member = self.table.require_selection("a staff member")
        if member is None:
            return
        if not w.confirm(
            self.host, "Mark leaver",
            f"Mark {member.full_name} as having left?\n\n"
            "They drop out of the teacher and tutor pickers but keep their "
            "history of teaching and marking.",
        ):
            return
        try:
            self.ctl.staff.mark_leaver(member.staff_id)
        except ValidationError as exc:
            w.error(self.host, "Mark leaver", str(exc))
            return
        self.refresh()

    def delete(self) -> None:
        member = self.table.require_selection("a staff member")
        if member is None:
            return
        if not w.confirm(
            self.host, "Delete staff record",
            f"Permanently delete {member.display_name}?\n\n"
            "Courses, groups and sessions they were assigned to keep running "
            "but lose the assignment. 'Mark leaver' is almost always the right "
            "choice instead.",
        ):
            return
        self.ctl.staff.delete(member.staff_id)
        self.refresh()


# ── Form plumbing ───────────────────────────────────────────────────────────

def _fields(ctl):
    return (
        ("staff_id", "Staff ID", "text"),
        ("first_name", "First name", "text"),
        ("last_name", "Last name", "text"),
        ("email", "Email", "text"),
        ("role", "Role", "choice", STAFF_ROLES),
        ("department", "Department", "choice", ["", *ctl.staff.departments()]),
        ("employment_status", "Contract", "choice", EMPLOYMENT_STATUSES),
        ("contracted_hours", "Contracted teaching hours", "float"),
        ("phone", "Phone", "text"),
        ("room", "Base room", "text"),
        ("start_date", "Start date", "date"),
        ("end_date", "Leaving date", "date"),
        ("is_safeguarding_lead", "Safeguarding lead", "bool"),
        ("is_exams_officer", "Exams officer", "bool"),
        ("dbs_checked", "DBS checked", "bool"),
        ("qualifications", "Qualifications", "text"),
        ("notes", "Notes", "multiline"),
    )


def _from_staff(s: Staff) -> dict:
    return {
        "staff_id": s.staff_id,
        "first_name": s.first_name,
        "last_name": s.last_name,
        "email": s.email,
        "role": s.role,
        "department": s.department,
        "employment_status": s.employment_status,
        "contracted_hours": s.contracted_hours,
        "phone": s.phone,
        "room": s.room,
        "start_date": w.when(s.start_date, ""),
        "end_date": w.when(s.end_date, ""),
        "is_safeguarding_lead": s.is_safeguarding_lead,
        "is_exams_officer": s.is_exams_officer,
        "dbs_checked": s.dbs_checked,
        "qualifications": s.qualifications,
        "notes": s.notes,
    }


def _to_staff(d: dict) -> Staff:
    return Staff(
        staff_id=d["staff_id"],
        first_name=d["first_name"],
        last_name=d["last_name"],
        email=d["email"],
        role=d["role"],
        department=d["department"],
        employment_status=d["employment_status"],
        contracted_hours=d["contracted_hours"],
        phone=d["phone"],
        room=d["room"],
        start_date=d["start_date"],
        end_date=d["end_date"],
        is_safeguarding_lead=d["is_safeguarding_lead"],
        is_exams_officer=d["is_exams_officer"],
        dbs_checked=d["dbs_checked"],
        qualifications=d["qualifications"],
        notes=d["notes"],
    )


def _profile_text(profile) -> str:
    s, load = profile.staff, profile.workload
    blocked = sorted(str(slot) for slot in profile.availability.unavailable)
    lines = [
        f"{s.full_name}  ({s.staff_id})",
        "=" * 64,
        f"Role         : {s.role}",
        f"Department   : {s.department or '—'}",
        f"Contract     : {s.employment_status} · {s.contracted_hours:g}h contracted",
        f"Email / phone: {s.email} / {s.phone or '—'}",
        f"Base room    : {s.room or '—'}",
        f"Started      : {w.when(s.start_date)}"
        + (f"   Left: {w.when(s.end_date)}" if s.end_date else ""),
        f"Safeguarding lead: {w.yes_no(s.is_safeguarding_lead)}   "
        f"Exams officer: {w.yes_no(s.is_exams_officer)}   "
        f"DBS: {w.yes_no(s.dbs_checked)}",
        "",
        "Workload",
        "-" * 64,
        f"  {load.assigned_hours:g}h assigned of {load.contracted_hours:g}h contracted "
        f"({load.band})",
        f"  {load.class_count} session(s) across {load.course_count} course(s)",
        f"  Utilisation: {w.pct(load.utilisation_pct)}",
        "",
        "Responsibilities",
        "-" * 64,
        f"  Courses led : {', '.join(profile.courses_led) or '—'}",
        f"  Groups      : {', '.join(profile.groups_taught) or '—'}",
        f"  Marking outstanding: {profile.marking_outstanding}",
        "",
        "Unavailable slots",
        "-" * 64,
        "  " + (", ".join(blocked) if blocked else "None — available all week"),
    ]
    if s.qualifications:
        lines += ["", "Qualifications", "-" * 64, f"  {s.qualifications}"]
    if s.notes:
        lines += ["", "Notes", "-" * 64, f"  {s.notes}"]
    return "\n".join(lines)


__all__ = ["TITLE", "Screen", "open_window"]
