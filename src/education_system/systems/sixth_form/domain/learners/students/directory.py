"""What the Student Directory and Student Profile show about each learner.

The ``students`` table holds the record itself. Everything a member of
staff looks for next lives with the feature that owns it:
- year group (enrolments);
- tutor group;
- attendance;
- the SEND register;
- medical alerts;
- open safeguarding concerns;
- contacts, photo and login.

This module gathers all of that. The list view reads it in one pass over
``sixthform.db``, where every feature's tables live, rather than one query
per learner per feature.

Sensitive flags (SEND, medical, safeguarding) are returned only to a
principal holding that capability. Anyone else gets ``None``, which a
screen shows as a blank column rather than "no concerns", so a missing
flag can never be read as reassurance. Opening a profile that shows
them is written to the sensitive-access log.
"""

from __future__ import annotations

import csv
import logging
from education_system.systems.sixth_form.infrastructure import database as db
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from education_system.systems.sixth_form.domain.governance.user_management import access
from education_system.systems.sixth_form.domain.learners.students import students as _students
from education_system.systems.sixth_form.domain.learners.students.students import Student

logger = logging.getLogger(__name__)

#: Directory status filter → the record statuses it shows. "On roll" is
#: the default: a learner who has left is history, not the current roll.
STATUS_FILTERS: dict[str, tuple[str, ...]] = {
    "On roll": _students.ON_ROLL_STATUSES,
    **{s: (s,) for s in _students.STATUSES},
    "All": _students.STATUSES,
}
DEFAULT_STATUS_FILTER = "On roll"

# Same vocabularies as the owning modules (safeguarding.OPEN_STATUSES,
# medical_records' severe bands, the SEND register's exit states), kept
# here as SQL literals so the list view need not import every feature.
_OPEN_CONCERN_STATUSES = ("Open", "Under Investigation", "Escalated")
_SEVERE_ALLERGY = ("Severe", "Life-threatening")
_SEND_CLOSED = ("Exited", "Archived")


@dataclass
class DirectoryRow:
    student: Student
    year_group: int | None = None
    academic_year: str | None = None
    enrolment_status: str | None = None
    tutor_group: str | None = None
    attendance_pct: float | None = None
    #: SEND register status, "" for not on the register, None = not visible.
    send: str | None = None
    #: Severe condition / allergy / epipen, None = not visible.
    medical_alert: bool | None = None
    #: Open safeguarding concerns, None = not visible.
    safeguarding_open: int | None = None

    @property
    def year_label(self) -> str:
        if self.year_group is None:
            return ""
        label = f"Year {self.year_group}"
        if self.enrolment_status and self.enrolment_status != "Enrolled":
            label += f" ({self.enrolment_status})"
        return label

    def flags(self) -> list[str]:
        out = []
        if self.send:
            out.append(f"SEND: {self.send}")
        if self.medical_alert:
            out.append("Medical")
        if self.safeguarding_open:
            out.append(f"Safeguarding ({self.safeguarding_open})")
        return out


@dataclass
class Visibility:
    """Which sensitive columns a principal may see."""
    send: bool
    medical: bool
    safeguarding: bool
    attendance: bool

    @classmethod
    def of(cls, p: access.Principal) -> "Visibility":
        return cls(
            send=p.can(access.SEND),
            medical=p.can(access.MEDICAL),
            safeguarding=p.can(access.SAFEGUARDING),
            attendance=p.is_staff,
        )


def _rows(conn: db.Connection, sql: str, args: tuple = ()) -> list[db.Row]:
    """A feature's table only exists once that feature has been opened."""
    try:
        return conn.execute(sql, args).fetchall()
    except db.OperationalError as e:
        logger.debug("Directory lookup skipped (%s): %s", e, sql.split()[3:4])
        return []


def _marks(values: tuple[str, ...]) -> str:
    return ",".join("?" * len(values))


def _gather(students: list[Student], vis: Visibility) -> dict[str, DirectoryRow]:
    out = {s.student_id: DirectoryRow(student=s) for s in students}
    if not out:
        return out
    with _students._connect() as conn:
        # Enrolments: newest academic year first, preferring an active one —
        # the same rule as enrolments.current_enrolment. Archived rows
        # (entered in error / undone) never count.
        seen: set[str] = set()
        for r in _rows(conn, "SELECT student_id, academic_year, year_group, "
                             "tutor_group, status FROM enrolments "
                             "WHERE archived_at IS NULL "
                             "ORDER BY academic_year DESC, "
                             "CASE status WHEN 'Enrolled' THEN 0 ELSE 1 END"):
            row = out.get(r["student_id"])
            if row is None or r["student_id"] in seen:
                continue
            seen.add(r["student_id"])
            row.year_group, row.academic_year = r["year_group"], r["academic_year"]
            row.enrolment_status = r["status"]
            row.tutor_group = r["tutor_group"]
        # Tutor group membership is the source of truth where it exists.
        for r in _rows(conn, "SELECT m.student_id, g.name FROM tutor_group_students m "
                             "JOIN tutor_groups g ON g.tutor_group_id = m.tutor_group_id"):
            if r["student_id"] in out:
                out[r["student_id"]].tutor_group = r["name"]
        if vis.attendance:
            counts: dict[str, dict[str, int]] = {}
            for r in _rows(conn, "SELECT student_id, status, COUNT(*) AS n "
                                 "FROM attendance_records WHERE voided = 0 "
                                 "GROUP BY student_id, status"):
                counts.setdefault(r["student_id"], {})[r["status"]] = r["n"]
            for sid, c in counts.items():
                total = sum(c.values())
                if sid in out and total:
                    out[sid].attendance_pct = round(
                        100.0 * (c.get("Present", 0) + c.get("Late", 0)) / total, 1)
        if vis.send:
            for row in out.values():
                row.send = ""
            # db-audit: ignore[DBW001] - only placeholders are interpolated
            for r in _rows(conn, "SELECT student_id, register_status FROM send_register "
                                 f"WHERE register_status NOT IN ({_marks(_SEND_CLOSED)}) "
                                 f"AND COALESCE(status, '') NOT IN ({_marks(_SEND_CLOSED)}) "
                                 "ORDER BY date_added", _SEND_CLOSED * 2):
                if r["student_id"] in out:
                    out[r["student_id"]].send = r["register_status"]
        if vis.medical:
            for row in out.values():
                row.medical_alert = False
            # db-audit: ignore[DBW001] - only placeholders are interpolated
            for r in _rows(conn, "SELECT student_id FROM med_conditions "
                                 "WHERE active = 1 AND severity = 'Severe' "
                                 "UNION SELECT student_id FROM med_allergies "
                                 f"WHERE severity IN ({_marks(_SEVERE_ALLERGY)}) "
                                 "OR has_epipen = 1", _SEVERE_ALLERGY):
                if r["student_id"] in out:
                    out[r["student_id"]].medical_alert = True
        if vis.safeguarding:
            for row in out.values():
                row.safeguarding_open = 0
            # db-audit: ignore[DBW001] - only placeholders are interpolated
            for r in _rows(conn, "SELECT student_id, COUNT(*) AS n FROM safeguarding_concerns "
                                 f"WHERE status IN ({_marks(_OPEN_CONCERN_STATUSES)}) "
                                 "GROUP BY student_id", _OPEN_CONCERN_STATUSES):
                if r["student_id"] in out:
                    out[r["student_id"]].safeguarding_open = r["n"]
    return out


def list_directory(*, status: str = DEFAULT_STATUS_FILTER,
                   year_group: int | None = None,
                   tutor_group: str | None = None,
                   subject: str | None = None,
                   query: str | None = None,
                   principal: access.Principal | None = None) -> list[DirectoryRow]:
    """The directory, filtered. ``query`` matches everything
    :func:`students.search_students` does, plus the tutor group name."""
    p = principal or access.current()
    allowed = STATUS_FILTERS.get(status or DEFAULT_STATUS_FILTER)
    if allowed is None:
        raise _students.ValidationError(
            f"Status filter must be one of: {', '.join(STATUS_FILTERS)}")
    everyone = _students.list_students()
    rows = _gather(everyone, Visibility.of(p))
    q = (query or "").strip()
    matched: set[str] | None = None
    if q:
        matched = {s.student_id for s in _students.search_students(q)}
        matched |= {sid for sid, r in rows.items()
                    if r.tutor_group and q.lower() in r.tutor_group.lower()}
    out = []
    for s in everyone:
        r = rows[s.student_id]
        if s.status not in allowed:
            continue
        if matched is not None and s.student_id not in matched:
            continue
        if year_group is not None and r.year_group != year_group:
            continue
        if tutor_group and (r.tutor_group or "") != tutor_group:
            continue
        if subject and subject not in s.subjects:
            continue
        out.append(r)
    return out


def _current_year() -> str:
    from education_system.systems.sixth_form.domain.admissions.enrolments import (
        enrolments as _enrolments,
    )
    return _enrolments.current_academic_year()


def filter_options() -> dict[str, list[Any]]:
    """Values for the directory's filter drop-downs."""
    years, groups = set(), set()
    with _students._connect() as conn:
        years.update(r[0] for r in _rows(
            conn, "SELECT DISTINCT year_group FROM enrolments "
                  "WHERE archived_at IS NULL") if r[0] is not None)
        groups.update(r[0] for r in _rows(conn, "SELECT name FROM tutor_groups") if r[0])
        # Tutor group names still written on a live enrolment of the
        # current year (an old year's or an archived row's text is history).
        groups.update(r[0] for r in _rows(
            conn, "SELECT DISTINCT tutor_group FROM enrolments "
                  "WHERE archived_at IS NULL AND status IN ('Enrolled', 'Pending') "
                  "AND academic_year = ?", (_current_year(),)) if r[0])
    try:
        from education_system.systems.sixth_form.domain.academics.subjects import subjects
        subject_names = subjects.get_active_names() or list(_students.A_LEVEL_SUBJECTS)
    except Exception:
        logger.exception("Falling back to the seed subject list")
        subject_names = list(_students.A_LEVEL_SUBJECTS)
    return {
        "statuses": list(STATUS_FILTERS),
        "years": sorted(years),
        "tutor_groups": sorted(groups),
        "subjects": sorted(subject_names),
    }


# ── Export ──────────────────────────────────────────────────────────

def export_columns(vis: Visibility) -> list[tuple[str, Any]]:
    cols: list[tuple[str, Any]] = [
        ("Student ID", lambda r: r.student.student_id),
        ("Surname", lambda r: r.student.last_name),
        ("First name", lambda r: r.student.first_name),
        ("Preferred name", lambda r: r.student.preferred_name or ""),
        ("Status", lambda r: r.student.status),
        ("Start date", lambda r: r.student.start_date or ""),
        ("Leaving date", lambda r: r.student.leaving_date or ""),
        ("Year", lambda r: r.year_group or ""),
        ("Tutor group", lambda r: r.tutor_group or ""),
        ("College email", lambda r: r.student.email),
        ("Phone", lambda r: r.student.phone or ""),
        ("A-levels", lambda r: "; ".join(r.student.subjects)),
    ]
    if vis.attendance:
        cols.append(("Attendance %", lambda r: "" if r.attendance_pct is None
                     else r.attendance_pct))
    if vis.send:
        cols.append(("SEND", lambda r: r.send or ""))
    if vis.medical:
        cols.append(("Medical alert", lambda r: "Yes" if r.medical_alert else ""))
    if vis.safeguarding:
        cols.append(("Open safeguarding concerns",
                     lambda r: r.safeguarding_open or ""))
    return cols


def export_csv(rows: list[DirectoryRow], path: str | Path, *,
               principal: access.Principal | None = None) -> int:
    """Write the rows on screen to CSV with only the columns the principal
    may see. Returns the number of learners written."""
    p = principal or access.current()
    p.require(access.STUDENTS_VIEW, "the Student Directory")
    vis = Visibility.of(p)
    cols = export_columns(vis)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([c[0] for c in cols])
        for r in rows:
            w.writerow([c[1](r) for c in cols])
    if vis.send or vis.medical or vis.safeguarding:
        access.log_sensitive_access(p, "student_directory", "export",
                                    record_ref=f"{len(rows)} learner(s)")
    logger.info("Exported %d directory row(s) to %s", len(rows), path)
    return len(rows)


# ── Profile ─────────────────────────────────────────────────────────

@dataclass
class RecordSummary:
    """One line of "their records" on the profile, with the menu entry
    that opens the full record."""
    area: str
    summary: str
    menu_label: str


@dataclass
class StudentProfile:
    student: Student
    year_label: str | None = None
    tutor_group: str | None = None
    tutor: str | None = None
    tutor_room: str | None = None
    contacts: list[Any] = field(default_factory=list)
    photo_path: str | None = None
    account: dict[str, Any] | None = None
    records: list[RecordSummary] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    linked_records: dict[str, int] = field(default_factory=dict)
    contact_log: list[Any] = field(default_factory=list)


def account_status(student_id: str) -> dict[str, Any] | None:
    """The learner's own login: active, locked, last sign-in, and whether it
    still has sixth-form access. None when there is no account."""
    try:
        from education_system.platform.identity.auth.db import connect as _auth_connect
        with _auth_connect() as conn:
            u = conn.execute("SELECT id, is_active, locked_until, last_login "
                             "FROM users WHERE username = ?", (student_id,)).fetchone()
            if u is None:
                return None
            roles = [r[0] for r in conn.execute(
                "SELECT role FROM user_systems WHERE user_id = ? AND system_key = ?",
                (u["id"], _students.AUTH_SYSTEM_KEY))]
    except Exception:
        logger.exception("Could not read the login of %s", student_id)
        return None
    locked = bool(u["locked_until"]) and str(u["locked_until"]) > _now_iso()
    if not u["is_active"]:
        state = "Disabled"
    elif locked:
        state = "Locked"
    elif not roles:
        state = "No sixth form access"
    else:
        state = "Active"
    return {"username": student_id, "state": state,
            "last_login": u["last_login"], "roles": roles}


def _now_iso() -> str:
    import datetime as _dt
    return _dt.datetime.now().isoformat(sep=" ", timespec="seconds")


def _record_summaries(conn: db.Connection, sid: str,
                      p: access.Principal) -> list[RecordSummary]:
    out: list[RecordSummary] = []

    def add(area: str, menu: str, text: str | None) -> None:
        if text is not None:
            out.append(RecordSummary(area, text, menu))

    def one(sql: str) -> db.Row | None:
        rows = _rows(conn, sql, (sid,))
        return rows[0] if rows else None

    if p.can_open("Attendance"):
        try:
            from education_system.systems.sixth_form.domain.academics.attendance import (
                attendance,
            )
            a = attendance.summary_for_student(sid)
            add("Attendance", "Attendance",
                f"{a.percentage:.1f}% ({a.attending}/{a.total} sessions, "
                f"{a.absent} absent)" if a.total else "No sessions recorded")
        except Exception:
            logger.exception("Attendance summary failed for %s", sid)
    if p.can_open("Behaviour Log") and access.can_see_student(
            p, sid, capability=access.PASTORAL):
        r = one("SELECT COUNT(*) AS n, COALESCE(SUM(points), 0) AS pts, "
                "MAX(entry_date) AS last FROM behaviour_entries WHERE student_id = ?")
        add("Behaviour", "Behaviour Log",
            f"{r['n']} entr{'y' if r['n'] == 1 else 'ies'}, {r['pts']} point(s)"
            + (f", latest {r['last']}" if r["last"] else "") if r and r["n"]
            else "No entries")
    if p.can_open("SEND"):
        r = one("SELECT register_status, primary_need, next_review_due FROM send_register "
                "WHERE student_id = ? AND register_status != 'Exited' "
                "ORDER BY date_added DESC LIMIT 1")
        add("SEND", "SEND",
            f"{r['register_status']} — {r['primary_need']}"
            + (f", review due {r['next_review_due']}" if r["next_review_due"] else "")
            if r else "Not on the SEND register")
    if p.can_open("Medical Records"):
        try:
            from education_system.systems.sixth_form.domain.pastoral.health.medical_records import (
                medical_records,
            )
            m = medical_records.summary_for_student(sid)
            bits = []
            if m.active_conditions:
                bits.append(f"{m.active_conditions} condition(s)"
                            + (f", {m.severe_conditions} severe" if m.severe_conditions else ""))
            if m.allergies:
                bits.append(f"{m.allergies} allerg{'y' if m.allergies == 1 else 'ies'}"
                            + (f", {m.severe_allergies} severe" if m.severe_allergies else ""))
            if m.current_medications:
                bits.append(f"{m.current_medications} medication(s)"
                            + (f", {m.emergency_medications} emergency"
                               if m.emergency_medications else ""))
            add("Medical", "Medical Records", "; ".join(bits) or "Nothing recorded")
        except Exception:
            logger.exception("Medical summary failed for %s", sid)
    if p.can_open("Safeguarding"):
        # db-audit: ignore[DBW001] - only placeholders are interpolated
        rows = _rows(conn, "SELECT COUNT(*) AS n, SUM(CASE WHEN status IN "
                           f"({_marks(_OPEN_CONCERN_STATUSES)}) THEN 1 ELSE 0 END) AS open "
                           "FROM safeguarding_concerns WHERE student_id = ?",
                     (*_OPEN_CONCERN_STATUSES, sid))
        r = rows[0] if rows else None
        add("Safeguarding", "Safeguarding",
            f"{r['open'] or 0} open of {r['n']} concern(s)" if r and r["n"]
            else "No concerns recorded")
    if p.can_open("ILP"):
        r = one("SELECT COUNT(*) AS n, MIN(next_review_due) AS due FROM ilp_plans "
                "WHERE student_id = ? AND status = 'Active'")
        add("ILP", "ILP", f"{r['n']} active plan(s)"
            + (f", next review {r['due']}" if r["due"] else "")
            if r and r["n"] else "No active plan")
    if p.can_open("Target Setting"):
        r = one("SELECT COUNT(*) AS n FROM targets WHERE student_id = ?")
        add("Targets", "Target Setting",
            f"{r['n']} target(s)" if r and r["n"] else "No targets set")
    if p.can_open("Exam Entries"):
        r = one("SELECT COUNT(*) AS n FROM exam_entries WHERE student_id = ?")
        add("Exam entries", "Exam Entries",
            f"{r['n']} entr{'y' if r['n'] == 1 else 'ies'}" if r and r["n"] else "None")
    if p.can_open("Bursary Applications"):
        r = one("SELECT bursary_type, academic_year, status FROM bursary_applications "
                "WHERE student_id = ? ORDER BY application_date DESC, application_id DESC "
                "LIMIT 1")
        add("Bursary", "Bursary Applications",
            f"{r['bursary_type']} {r['academic_year']}: {r['status']}" if r
            else "No applications")
    if p.can_open("University & UCAS"):
        r = one("SELECT cycle_year, status FROM ucas_applications WHERE student_id = ? "
                "ORDER BY cycle_year DESC LIMIT 1")
        add("UCAS", "University & UCAS",
            f"{r['cycle_year']} cycle: {r['status']}" if r else "No application")
    if p.can_open("Destinations"):
        r = one("SELECT checkpoint, destination_type, institution, employer FROM dest_records "
                "WHERE student_id = ? ORDER BY record_id DESC LIMIT 1")
        add("Destinations", "Destinations",
            f"{r['checkpoint']}: {r['destination_type']}"
            + (f" — {r['institution'] or r['employer']}"
               if (r["institution"] or r["employer"]) else "")
            if r else "None recorded")
    return out


def student_profile(student_id: str, *,
                    principal: access.Principal | None = None) -> StudentProfile | None:
    p = principal or access.current()
    s = _students.get_student(student_id)
    if s is None:
        return None
    prof = StudentProfile(student=s)
    try:
        from education_system.systems.sixth_form.domain.admissions.enrolments import (
            enrolments,
        )
        prof.year_label = enrolments.current_year_group_label(student_id)
        e = enrolments.current_enrolment(student_id)
        prof.tutor_group = e.tutor_group if e else None
    except Exception:
        logger.exception("Enrolment lookup failed for %s", student_id)
    try:
        from education_system.systems.sixth_form.domain.pastoral.tutor_groups import (
            tutor_groups,
        )
        g = tutor_groups.group_for_student(student_id)
        if g is not None:
            prof.tutor_group, prof.tutor, prof.tutor_room = g.name, g.tutor, g.room
    except Exception:
        logger.exception("Tutor group lookup failed for %s", student_id)
    if p.can_open("Parent Contacts"):
        try:
            from education_system.systems.sixth_form.domains.communications.domain.parent_contacts import (
                parent_contacts,
            )
            prof.contacts = parent_contacts.list_contacts(student_id=student_id)
        except Exception:
            logger.exception("Contacts lookup failed for %s", student_id)
    try:
        from education_system.systems.sixth_form.domain.admissions.enrolments import (
            identity_checks,
        )
        c = identity_checks.get_check(student_id)
        if c is not None and c.has_photo:
            prof.photo_path = c.photo_path
    except Exception:
        logger.exception("Photo lookup failed for %s", student_id)
    if p.can(access.STUDENTS_MANAGE):
        prof.account = account_status(student_id)
        prof.linked_records = _students.linked_record_counts(student_id)
    prof.history = _students.list_history(student_id)
    if p.can_open("Contact Log"):
        try:
            from education_system.systems.sixth_form.domain.pastoral.contact_log import (
                contact_log,
            )
            # Already filtered to the entries this user may see.
            prof.contact_log = contact_log.contacts_for_student(student_id)
        except Exception:
            logger.exception("Contact log lookup failed for %s", student_id)
    with _students._connect() as conn:
        prof.records = _record_summaries(conn, student_id, p)
    shown = [r.area for r in prof.records
             if r.area in ("SEND", "Medical", "Safeguarding")]
    if shown:
        access.log_sensitive_access(p, "student_profile", "view",
                                    student_id=student_id,
                                    record_ref=", ".join(shown))
    return prof


__all__ = [
    "STATUS_FILTERS", "DEFAULT_STATUS_FILTER", "DirectoryRow", "Visibility",
    "list_directory", "filter_options", "export_columns", "export_csv",
    "RecordSummary", "StudentProfile", "account_status", "student_profile",
]
