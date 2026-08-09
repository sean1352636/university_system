"""Staff commands — directory, workload and availability."""

from __future__ import annotations

from datetime import date

from education_system.systems.fe_college.config import (
    EMPLOYMENT_STATUSES,
    STAFF_ROLES,
)
from education_system.systems.fe_college.domain.staff.models import Staff
from education_system.systems.fe_college.domain.students.models import ValidationError
from education_system.systems.fe_college.interfaces.cli import shell as sh


def directory(ctl) -> None:
    """List staff with their teaching load."""
    sh.header("Staff", "Contracted hours against what is timetabled.")
    role = sh.choose("Role", ["any", *STAFF_ROLES])
    if role is sh.CANCEL:
        return

    staff = ctl.staff.search(**({} if role == "any" else {"role": role}))
    loads = {wl.staff_id: wl for wl in ctl.staff.workloads()}
    sh.table(
        [("id", "ID"), ("name", "Name"), ("role", "Role"),
         ("department", "Department"), ("contract", "Contract"),
         ("hours", "Assigned/contracted"), ("band", "Load")],
        [
            {
                "id": s.staff_id,
                "name": s.full_name,
                "role": s.role,
                "department": s.department,
                "contract": s.employment_status,
                "hours": (
                    f"{loads[s.staff_id].assigned_hours:g}/"
                    f"{loads[s.staff_id].contracted_hours:g}h"
                    if s.staff_id in loads else sh.DASH
                ),
                "band": loads[s.staff_id].band if s.staff_id in loads else sh.DASH,
            }
            for s in staff
        ],
        empty="No staff match.",
        limit=40,
    )


def view(ctl) -> None:
    """Show one member of staff in full."""
    member = _pick(ctl)
    if member is None:
        return
    profile = ctl.staff.profile(member.staff_id)
    if profile is None:
        sh.error("That staff record no longer exists.")
        return

    s, load = profile.staff, profile.workload
    sh.header(s.display_name, f"{s.role} · {s.department or 'no department'}")
    sh.key_values([
        ("Email", s.email),
        ("Phone", s.phone),
        ("Contract", f"{s.employment_status} · {s.contracted_hours:g}h contracted"),
        ("Base room", s.room),
        ("Started", s.start_date),
        ("Left", s.end_date),
        ("Safeguarding lead", s.is_safeguarding_lead),
        ("Exams officer", s.is_exams_officer),
        ("DBS checked", s.dbs_checked),
    ])

    sh.section("Workload")
    sh.key_values([
        ("Assigned", f"{load.assigned_hours:g}h of {load.contracted_hours:g}h "
                     f"({load.band})"),
        ("Utilisation", sh.pct(load.utilisation_pct)),
        ("Sessions", load.class_count),
        ("Courses", load.course_count),
        ("Marking outstanding", profile.marking_outstanding),
    ])

    sh.section("Responsibilities")
    sh.key_values([
        ("Courses led", ", ".join(profile.courses_led) or sh.DASH),
        ("Groups taught", ", ".join(profile.groups_taught) or sh.DASH),
    ])

    blocked = sorted(str(slot) for slot in profile.availability.unavailable)
    sh.section("Unavailable slots")
    sh.note(", ".join(blocked) if blocked else "Available all week.")


def create(ctl) -> None:
    """Add a member of staff."""
    sh.header("New staff member")
    suggested = ctl.staff.next_reference()
    result = sh.form("Staff details", [
        ("staff_id", "Staff ID", "text"),
        ("first_name", "First name", "text"),
        ("last_name", "Last name", "text"),
        ("email", "Email", "text"),
        ("role", "Role", "choice", STAFF_ROLES),
        ("department", "Department", "choice", ctl.staff.departments()),
        ("employment_status", "Contract", "choice", EMPLOYMENT_STATUSES),
        ("contracted_hours", "Contracted teaching hours", "float"),
        ("phone", "Phone", "text"),
        ("start_date", "Start date", "date"),
        ("dbs_checked", "DBS checked", "bool"),
    ], initial={"staff_id": suggested, "contracted_hours": 24.0,
                "start_date": date.today()})
    if result is sh.CANCEL:
        return

    try:
        created = ctl.staff.create(Staff(
            staff_id=result["staff_id"] or suggested,
            first_name=result["first_name"],
            last_name=result["last_name"],
            email=result["email"],
            role=result["role"] or "Lecturer",
            department=result["department"],
            employment_status=result["employment_status"] or "Full-time",
            contracted_hours=result["contracted_hours"],
            phone=result["phone"],
            start_date=result["start_date"],
            dbs_checked=result["dbs_checked"],
        ))
    except ValidationError as exc:
        sh.error(str(exc))
        return
    sh.success(f"Created {created.display_name}")


def workload(ctl) -> None:
    """The workload report, over- and under-allocated staff first."""
    sh.header("Staff workload", "Timetabled hours against contracted hours.")
    department = sh.choose("Department", ["all", *ctl.staff.departments()])
    if department is sh.CANCEL:
        return
    target = None if department == "all" else department

    summary = ctl.staff.workload_summary(target)
    sh.key_values([
        ("Staff", summary["staff"]),
        ("Assigned hours", f"{summary['assigned_hours']:g}"),
        ("Contracted hours", f"{summary['contracted_hours']:g}"),
        ("Utilisation", sh.pct(summary["utilisation_pct"])),
        ("Over-allocated", summary["over_allocated"]),
        ("Under-allocated", summary["under_allocated"]),
    ])

    rows = ctl.reports.workload_report(target)
    sh.table(
        [("staff_id", "ID"), ("name", "Name"), ("contracted", "Contracted"),
         ("assigned", "Assigned"), ("variance", "Variance"),
         ("utilisation_pct", "Utilisation"), ("band", "Band")],
        [
            {**r,
             "contracted": f"{r['contracted']:g}h",
             "assigned": f"{r['assigned']:g}h",
             "variance": f"{r['variance']:+g}h",
             "utilisation_pct": sh.pct(r["utilisation_pct"])}
            for r in rows
        ],
        empty="No staff to report on.",
    )


def availability(ctl) -> None:
    """Block or clear whole days for a member of staff."""
    member = _pick(ctl)
    if member is None:
        return
    current = ctl.staff.availability(member.staff_id)
    days = list(ctl.timetable.days()[:5])
    periods = ctl.timetable.period_codes()

    sh.section(f"Availability — {member.full_name}")
    blocked_now = [
        day for day in days
        if all(not current.is_free(day, p) for p in periods)
    ]
    sh.note("Currently unavailable: " + (", ".join(blocked_now) or "no days"))

    blocked: list[tuple[str, str]] = []
    for day in days:
        answer = sh.ask_bool(f"Unavailable on {day}?", day in blocked_now)
        if answer is sh.CANCEL:
            return
        if answer:
            blocked.extend((day, period) for period in periods)

    try:
        ctl.staff.set_availability(member.staff_id, blocked, reason="Not contracted")
    except ValidationError as exc:
        sh.error(str(exc))
        return
    sh.success(
        f"{member.full_name} unavailable on "
        + (", ".join(sorted({d for d, _p in blocked})) or "no days")
    )


def sampling(ctl) -> None:
    """Assessors whose marking is under-sampled by internal verification."""
    sh.header("Internal verification sampling",
              "Awarding bodies expect at least 20% of each assessor's marking "
              "to be verified.")
    rows = ctl.staff.sampling_shortfalls()
    sh.table(
        [("id", "ID"), ("name", "Name"), ("marked", "Marked"),
         ("verified", "Verified"), ("short", "Shortfall")],
        [
            {"id": s.staff_id, "name": s.full_name, "marked": marked,
             "verified": verified, "short": short}
            for s, marked, verified, short in rows
        ],
        empty="Every assessor meets the sampling rule.",
    )


def _pick(ctl):
    query = sh.prompt("Staff member — search by name or ID")
    if query is sh.CANCEL:
        return None
    matches = ctl.staff.search(query=query)
    if not matches:
        sh.note("No staff match.")
        return None
    if len(matches) == 1:
        return matches[0]
    chosen = sh.choose_object("Which one?", matches[:30], lambda s: s.display_name)
    return None if chosen is sh.CANCEL else chosen


__all__ = [
    "availability", "create", "directory", "sampling", "view", "workload",
]
